"""
Optimisation math used by the gradient-descent scenes.

Everything here is exact: the gradients are analytic, the step rule is the real
update equation, and the recorded trajectory is what the visuals animate.  No
hand-placed curves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class Loss:
    """A 2-D loss surface with analytic gradient."""
    f: Callable[[float, float], float]
    grad: Callable[[float, float], tuple[float, float]]
    name: str = "L"

    def __call__(self, x, y):
        return self.f(x, y)


def anisotropic_bowl(a: float = 1.0, b: float = 1.30, ripple: float = 0.25, base: float = 0.9) -> Loss:
    """
    L(x, y) = ½a x² + ½b y² + ripple·sin(2x)cos(1.7y) + base
    with the exact analytic gradient.  The ripple creates a non-convex flank so
    the descent has visible structure instead of a straight slide.
    """
    def f(x, y):
        return 0.5 * a * x * x + 0.5 * b * y * y + ripple * np.sin(2.0 * x) * np.cos(1.7 * y) + base

    def grad(x, y):
        dx = a * x + 2.0 * ripple * np.cos(2.0 * x) * np.cos(1.7 * y)
        dy = b * y - 1.7 * ripple * np.sin(2.0 * x) * np.sin(1.7 * y)
        return float(dx), float(dy)

    return Loss(f, grad, "L")


@dataclass
class Trajectory:
    """Result of an optimisation run, in parameter space."""
    xs: np.ndarray
    ys: np.ndarray
    losses: np.ndarray
    grads: np.ndarray
    lr: float

    def __len__(self):
        return len(self.xs)

    def points(self, t: float) -> tuple[float, float]:
        """Continuous position at optimisation time t (0..n-1), linearly interpolated."""
        t = max(0.0, min(len(self.xs) - 1, t))
        i = int(np.floor(t))
        j = min(i + 1, len(self.xs) - 1)
        u = t - i
        return (float(self.xs[i] + (self.xs[j] - self.xs[i]) * u),
                float(self.ys[i] + (self.ys[j] - self.ys[i]) * u))


def gradient_descent(loss: Loss, x0: float, y0: float, lr: float = 0.16, steps: int = 26,
                     momentum: float = 0.0) -> Trajectory:
    xs, ys, ls, gs = [], [], [], []
    x, y = float(x0), float(y0)
    vx = vy = 0.0
    for _ in range(steps):
        gx, gy = loss.grad(x, y)
        xs.append(x); ys.append(y); ls.append(loss.f(x, y)); gs.append((gx, gy))
        vx = momentum * vx - lr * gx
        vy = momentum * vy - lr * gy
        x, y = x + vx, y + vy
    gx, gy = loss.grad(x, y)
    xs.append(x); ys.append(y); ls.append(loss.f(x, y)); gs.append((gx, gy))
    return Trajectory(np.array(xs), np.array(ys), np.array(ls), np.array(gs), lr)


def descent_frames(tr: Trajectory, n_steps: int, ease: str = "in_out_sine"):
    """Map an optimisation index to eased progress for smooth playback."""
    from .animate import ease as _ease
    return [_ease(ease, i / max(n_steps - 1, 1)) * (len(tr) - 1) for i in range(n_steps)]
