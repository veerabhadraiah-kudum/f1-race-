"""
Easing, interpolation and the keyframe track system.

Every animated property in the film is a Track: a list of (time, value)
keyframes with per-key easing.  Evaluation is monotone, C1-continuous for
smooth-motion keys, and fully deterministic, which is what makes frame-exact
rendering and parallel chunk rendering possible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

# ------------------------------------------------------------------ easing
def linear(t: float) -> float:
    return t


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) ** 2


def ease_in_cubic(t: float) -> float:
    return t ** 3


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_in_out_quart(t: float) -> float:
    return 8 * t ** 4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_out_quart(t: float) -> float:
    return 1 - (1 - t) ** 4


def ease_out_back(t: float, s: float = 1.70158) -> float:
    c3 = s + 1
    return 1 + c3 * (t - 1) ** 3 + s * (t - 1) ** 2


def ease_out_elastic(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


EASES: dict[str, Callable[[float], float]] = {
    "linear": linear,
    "in_quad": ease_in_quad,
    "out_quad": ease_out_quad,
    "in_cubic": ease_in_cubic,
    "out_cubic": ease_out_cubic,
    "in_out_cubic": ease_in_out_cubic,
    "in_out_quart": ease_in_out_quart,
    "in_out_sine": ease_in_out_sine,
    "out_expo": ease_out_expo,
    "out_quart": ease_out_quart,
    "out_back": ease_out_back,
    "out_elastic": ease_out_elastic,
    "smooth": ease_in_out_sine,          # alias, the house default
}


def ease(name: str | Callable[[float], float] | None, t: float) -> float:
    t = max(0.0, min(1.0, t))
    if name is None:
        return t
    fn = EASES.get(name, None) if isinstance(name, str) else name
    return fn(t) if fn is not None else t


# ---------------------------------------------------------------- helpers
def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3 - 2 * t)


def remap(t: float, a: float, b: float, easing: str | None = "smooth") -> float:
    """Normalised, eased 0..1 progress of t inside the window [a, b]."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return ease(easing, clamp((t - a) / (b - a)))


def window(t: float, a: float, b: float) -> float:
    """0 outside [a,b], 1 inside, smooth 0..1 ramps at both ends (in-place fades)."""
    fade = min(0.35, (b - a) * 0.25)
    return min(remap(t, a, a + fade), 1.0 - remap(t, b - fade, b))


# ---------------------------------------------------------------- tracks
@dataclass
class Key:
    t: float
    v: Any
    e: str | None = "in_out_cubic"


@dataclass
class Track:
    """
    Piecewise keyframe interpolation.  Values may be numbers, tuples or lists;
    tuples/lists are interpolated component-wise.  Before the first key the
    first value holds, after the last key the last value holds.
    """
    keys: list[Key] = field(default_factory=list)

    def at(self, t: float, default: Any = None) -> Any:
        ks = self.keys
        if not ks:
            return default
        if t <= ks[0].t:
            return ks[0].v
        if t >= ks[-1].t:
            return ks[-1].v
        # binary search
        lo, hi = 0, len(ks) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ks[mid].t <= t:
                lo = mid
            else:
                hi = mid
        a, b = ks[lo], ks[hi]
        u = ease(b.e, (t - a.t) / (b.t - a.t)) if b.t > a.t else 1.0
        return _mix_values(a.v, b.v, u)


def _mix_values(a: Any, b: Any, u: float) -> Any:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * u
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == len(b):
        out = _mix_values_lists(a, b, u)
        return tuple(out) if isinstance(a, tuple) else out
    return b if u >= 0.5 else a


def _mix_values_lists(a: Sequence, b: Sequence, u: float):
    out = []
    for x, y in zip(a, b):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            out.append(x + (y - x) * u)
        elif isinstance(x, (tuple, list)) and isinstance(y, (tuple, list)):
            out.append(_mix_values_lists(x, y, u))
        elif isinstance(x, str) and isinstance(y, str):
            out.append(x if u < 0.5 else y)
        else:
            out.append(y if u >= 0.5 else x)
    return out


def track(*pairs: tuple[float, Any], default_ease: str = "in_out_cubic") -> Track:
    """track((0, 0), (1, 1, 'out_cubic')) -> Track"""
    keys = []
    for p in pairs:
        if len(p) == 2:
            keys.append(Key(float(p[0]), p[1], default_ease))
        else:
            keys.append(Key(float(p[0]), p[1], p[2]))
    return Track(keys)


class Stagger:
    """
    Timeline helper: lays out a sequence of named beats and returns eased 0..1
    progress for each, so narration cues and motion stay locked together.
    """

    def __init__(self, start: float = 0.0):
        self.t = start

    def step(self, dur: float) -> tuple[float, float]:
        a = self.t
        self.t += dur
        return a, self.t


# ------------------------------------------------------------------ color
def mix_hex(c1: str, c2: str, t: float) -> str:
    t = clamp(t)
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))
