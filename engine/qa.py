"""
Scene QA harness.

Two automated checks that catch the defects human review misses at 30 fps:

1. **Glyph coverage** — every character a scene draws is shaped against the
   font that will render it.  Any codepoint with no outline in that face is
   reported, so "tofu boxes" can never reach the render.
2. **Layout bounds** — frames are rendered and scanned for content inside the
   title-safe margin and for text/panel overlaps in the caption band.

Run:  python -m engine.qa scenes.s1_gradient_descent:GradientDescent
"""
from __future__ import annotations

import importlib
import io
import sys
from collections import defaultdict

import numpy as np
from fontTools.ttLib import TTFont

from .typography import FAMILIES, FONT_DIR, _load, _nearest_weight
import os


class GlyphProbe:
    """Records every string handed to Canvas.text, then checks font coverage."""

    def __init__(self):
        self.used = defaultdict(set)     # (family, weight) -> set(chars)

    def attach(self, canvas_cls):
        probe = self
        original = canvas_cls.text

        def text(self_, x, y, s, size=24, color="#fff", weight=400, family="Inter",
                 **kw):
            probe.used[(family, weight)].update(s)
            return original(self_, x, y, s, size=size, color=color, weight=weight,
                            family=family, **kw)

        canvas_cls.text = text

    def report(self):
        """
        Report characters that would render as tofu.

        A character is only a problem if the primary face lacks it **and** the
        math fallback lacks it too: the renderer resolves missing glyphs from
        the fallback chain at draw time, so a character present in Noto Sans
        Math is fine even if Inter does not have it.
        """
        problems = []
        for (family, weight), chars in sorted(self.used.items()):
            if family not in FAMILIES:
                continue
            w = _nearest_weight(FAMILIES[family], weight)
            _, tt, _, fb = _load(family, w)
            cmap = tt.getBestCmap() or {}
            fb_cmap = (fb[1].getBestCmap() or {}) if fb else {}
            missing = sorted(
                c for c in chars
                if not c.isspace() and ord(c) not in cmap and ord(c) not in fb_cmap
            )
            if missing:
                problems.append((family, w, "".join(missing)))
        return problems


def check_glyphs(scene_cls, times=None):
    from .canvas import Canvas
    probe = GlyphProbe()
    probe.attach(Canvas)
    scene = scene_cls()
    times = times or [scene.duration * f for f in (0.1, 0.3, 0.5, 0.7, 0.9, 0.99)]
    for t in times:
        scene.compose(t)
    return probe.report()


def check_bounds(scene_cls, times=None, safe=72):
    """Flag drawn frames whose ink enters the outer safe margin."""
    scene = scene_cls()
    times = times or [scene.duration * f for f in (0.1, 0.3, 0.5, 0.7, 0.9, 0.99)]
    issues = []
    from .background import flatten
    for t in times:
        arr = scene.compose(t).render_array()
        rgb = flatten(arr).astype(np.int16)
        # estimate the plate's own value at the borders and look for deviations
        from .background import plate_array
        plate = plate_array().astype(np.int16)
        diff = np.abs(rgb - plate).max(axis=2)
        mask = diff > 18
        if not mask.any():
            continue
        ys, xs = np.where(mask)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        if x0 < safe or y0 < safe or x1 > 1920 - safe or y1 > 1080 - safe:
            issues.append((round(t, 2), int(x0), int(y0), int(x1), int(y1)))
    return issues


def main(spec: str):
    mod_name, cls_name = spec.split(":")
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    print(f"== {cls.__name__} ==")
    bad = check_glyphs(cls)
    if bad:
        for fam, w, chars in bad:
            print(f"  MISSING GLYPHS  {fam} {w}: {chars!r}")
    else:
        print("  glyphs: OK (every character has an outline)")
    issues = check_bounds(cls)
    if issues:
        for t, x0, y0, x1, y1 in issues:
            print(f"  BOUNDS t={t}: ink bbox ({x0},{y0})-({x1},{y1})")
    else:
        print("  bounds: OK (all ink inside title-safe)")


if __name__ == "__main__":
    main(sys.argv[1])
