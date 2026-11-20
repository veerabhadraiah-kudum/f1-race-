"""Marching squares: iso-level curves of a sampled scalar field."""
from __future__ import annotations

import numpy as np


def marching_squares(X, Y, Z, level: float):
    """
    Return iso-contour segments of `level` as [(xa, ya, xb, yb), ...] in world
    (x, y) coordinates.  Standard 16-case marching squares with linear edge
    interpolation; robust for smooth analytic fields.
    """
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    Z = np.asarray(Z, dtype=float)
    ny, nx = Z.shape
    segs: list[tuple[float, float, float, float]] = []

    above = Z > level

    def interp(i, j, i2, j2):
        z1, z2 = Z[j, i], Z[j2, i2]
        t = 0.0 if z1 == z2 else (level - z1) / (z2 - z1)
        x = X[j, i] + (X[j2, i2] - X[j, i]) * t
        y = Y[j, i] + (Y[j2, i2] - Y[j, i]) * t
        return x, y

    for j in range(ny - 1):
        for i in range(nx - 1):
            a = above[j, i]
            b = above[j, i + 1]
            c = above[j + 1, i + 1]
            d = above[j + 1, i]
            idx = (1 if a else 0) | (2 if b else 0) | (4 if c else 0) | (8 if d else 0)
            if idx in (0, 15):
                continue
            # edge points: top(a-b), right(b-c), bottom(d-c), left(a-d)
            top = interp(i, j, i + 1, j)
            right = interp(i + 1, j, i + 1, j + 1)
            bottom = interp(i, j + 1, i + 1, j + 1)
            left = interp(i, j, i, j + 1)
            cases = {
                1: [(left, top)], 2: [(top, right)], 3: [(left, right)],
                4: [(right, bottom)], 5: [(left, top), (right, bottom)],
                6: [(top, bottom)], 7: [(left, bottom)],
                8: [(bottom, left)], 9: [(top, bottom)], 10: [(top, right), (bottom, left)],
                11: [(right, bottom)], 12: [(left, right)], 13: [(top, right)],
                14: [(left, top)], 15: [],
            }[idx]
            for (p, q) in cases:
                segs.append((p[0], p[1], q[0], q[1]))
    return segs
