"""
Scene framework.

A Scene is a deterministic function of time.  It declares:

* `duration`  — seconds
* `narration` — the spoken script, split into cues with explicit windows
* `beats`     — named time windows that both the motion and the captions key off
* `render(canvas, t)` — pure drawing for time t

That structure is what keeps motion, captions and narration synchronised: all
three read from the same beat table, so re-timing a scene re-times everything
at once.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .canvas import Canvas
from .theme import C, HEIGHT, WIDTH


@dataclass
class Cue:
    """One narration line with an explicit on-screen window."""
    t_in: float
    t_out: float
    text: str
    speaker: str = "host"
    emphasis: str | None = None

    @property
    def dur(self) -> float:
        return self.t_out - self.t_in


@dataclass
class Beat:
    """A named window inside a scene. Both animation and captions reference beats."""
    name: str
    t_in: float
    t_out: float
    label: str = ""

    def p(self, t: float, ease: str | None = "in_out_cubic") -> float:
        from .animate import remap
        return remap(t, self.t_in, self.t_out, ease)


class Scene:
    name = "scene"
    title = ""
    duration = 10.0
    beats: dict[str, Beat] = {}
    cues: list[Cue] = []
    subtitle = ""

    # background plate is composited on top of the frames by the film pipeline
    background = False
    # chapter number used by the HUD, 0 = no HUD
    chapter = 0
    chapter_total = 4
    # small persistent brand mark bottom-left
    hud = True

    def __init__(self):
        self.beat = self._beat_lookup()

    def _beat_lookup(self):
        beats = self.beats
        return beats

    # ---------------------------------------------------------------- hook
    def render(self, cv: Canvas, t: float) -> None:  # noqa: D401
        raise NotImplementedError

    # ----------------------------------------------------------------- HUD
    def draw_hud(self, cv: Canvas, t: float, alpha: float = 1.0):
        """
        Persistent frame furniture: the film's brand mark (left) and chapter
        progress pips (right).  Kept in the outer 56 px band so it never
        competes with scene content.
        """
        if not self.hud:
            return
        a = alpha * _fade_in(t, 0.7, 1.6)
        if a <= 0.01:
            return
        # brand mark, top-left
        bx, by = 96, 66
        cv.circle(bx + 5, by - 6, 5.4, fill="none", stroke=C.cyan, sw=1.5, opacity=0.8 * a)
        cv.circle(bx + 5, by - 6, 1.8, fill=C.teal, opacity=0.95 * a)
        cv.text(bx + 22, by, "MATHEMATICA  ·  VISUAL LAB", size=12.5, color=C.ink_mute,
                weight=600, tracking=0.22, opacity=0.62 * a)
        # chapter pips, top-right
        if self.chapter:
            x = WIDTH - 96
            y = 62
            cv.text(x, y, f"{self.chapter:02d}", size=15, color=C.cyan, weight=600,
                    family="JetBrains Mono", anchor="end", opacity=0.95 * a)
            cv.text(x - 26, y, f"/ {self.chapter_total:02d}", size=15, color=C.ink_faint,
                    weight=500, family="JetBrains Mono", anchor="end", opacity=0.7 * a)
            for i in range(self.chapter_total):
                cxp = x - 4 - i * 16
                on = (self.chapter_total - i) <= self.chapter
                cv.circle(cxp, y - 20, 2.9, fill=C.cyan if on else C.ink_faint,
                          opacity=(0.95 if on else 0.4) * a)

    # ------------------------------------------------------------- caption
    def draw_caption(self, cv: Canvas, t: float):
        """Bottom-third narration caption, keyed to `cues`."""
        for cue in self.cues:
            if not (cue.t_in - 0.15 <= t <= cue.t_out + 0.15):
                continue
            a = _cue_alpha(t, cue)
            if a <= 0.01:
                continue
            from .typography import Font
            size = 30
            max_w = 1420
            lines = wrap(cue.text, "Inter", 500, size, max_w)
            total_h = len(lines) * size * 1.42
            base_y = HEIGHT - 152 - total_h + size
            # letterbox scrim for legibility
            cv.raw(
                f'<rect x="0" y="{HEIGHT - 200:.0f}" width="{WIDTH}" height="200" '
                f'fill="url(#captionScrim)" opacity="{a:.3f}"/>'
            )
            for i, line in enumerate(lines):
                f = Font("Inter", 500, size, line)
                cv.raw(f.svg(WIDTH / 2 + 1.5, base_y + i * size * 1.42 + 1.5, "#000000", opacity=0.55 * a, anchor="middle"))
                cv.raw(f.svg(WIDTH / 2, base_y + i * size * 1.42, C.ink, opacity=0.97 * a, anchor="middle"))

    def draw_defs(self, cv: Canvas):
        from .theme import C as _C
        cv.defs(
            '<radialGradient id="groundGlow" cx="50%" cy="50%" r="50%">'
            '<stop offset="0%" stop-color="#22d3ee" stop-opacity="0.30"/>'
            '<stop offset="45%" stop-color="#0e7490" stop-opacity="0.16"/>'
            '<stop offset="100%" stop-color="#0e7490" stop-opacity="0"/>'
            "</radialGradient>"
            '<linearGradient id="bowlFill" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#0e7490" stop-opacity="0.10"/>'
            '<stop offset="65%" stop-color="#0e7490" stop-opacity="0.34"/>'
            '<stop offset="100%" stop-color="#22d3ee" stop-opacity="0.42"/>'
            "</linearGradient>"
            '<radialGradient id="graphField" cx="50%" cy="50%" r="60%">'
            '<stop offset="0%" stop-color="#0e7490" stop-opacity="0.24"/>'
            '<stop offset="60%" stop-color="#0e4f66" stop-opacity="0.10"/>'
            '<stop offset="100%" stop-color="#0a1220" stop-opacity="0"/>'
            "</radialGradient>"
            '<radialGradient id="orbitGlow" cx="50%" cy="50%" r="50%">'
            '<stop offset="0%" stop-color="#22d3ee" stop-opacity="0.9"/>'
            '<stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>'
            "</radialGradient>"
            '<linearGradient id="captionScrim" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#000000" stop-opacity="0"/>'
            '<stop offset="55%" stop-color="#02060c" stop-opacity="0.72"/>'
            '<stop offset="100%" stop-color="#02060c" stop-opacity="0.88"/>'
            "</linearGradient>"
        )

    # ------------------------------------------------------------- compose
    def compose(self, t: float) -> Canvas:
        cv = Canvas(background=False)
        self.draw_defs(cv)
        self.render(cv, t)
        self.draw_hud(cv, t)
        if self.cues:
            self.draw_caption(cv, t)
        return cv

    def frame_array(self, t: float, scale: float = 1.0, composed: bool = True):
        """
        Render one frame. `composed=True` returns the final RGB frame with the
        background plate, vignette and grain already applied.
        """
        arr = self.compose(t).render_array(scale=scale)
        if not composed:
            return arr
        from .background import flatten
        if scale != 1.0:
            return arr  # caller is making thumbnails; plate applies at 1x only
        return flatten(arr)

    def frame_png(self, t: float, scale: float = 1.0) -> bytes:
        return self.compose(t).render(scale=scale)

    # ------------------------------------------------------------- timing
    def times(self, fps: int = 30, start: float = 0.0, end: float | None = None) -> list[float]:
        end = self.duration if end is None else end
        n = int(round((end - start) * fps))
        return [start + i / fps for i in range(n)]


# ------------------------------------------------------------------ helpers
def _fade_in(t: float, a: float, b: float) -> float:
    from .animate import remap
    return remap(t, a, b, "in_out_sine")


def _cue_alpha(t: float, cue: Cue, fade: float = 0.28) -> float:
    from .animate import remap
    a_in = remap(t, cue.t_in - 0.05, cue.t_in + fade, "out_quad")
    a_out = 1.0 - remap(t, cue.t_out - fade, cue.t_out + 0.1, "in_quad")
    return max(0.0, min(a_in, a_out))


def wrap(text: str, family: str, weight: int, size: float, max_w: float) -> list[str]:
    """Greedy line breaking with real shaped advances."""
    from .typography import Font
    words = text.split()
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if Font(family, weight, size, cand).advance <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def beat_p(t: float, a: float, b: float, ease: str | None = "in_out_cubic") -> float:
    from .animate import remap
    return remap(t, a, b, ease)
