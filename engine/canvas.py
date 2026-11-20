"""
Canvas: the drawing surface every scene renders into.

A Canvas accumulates SVG fragments for one frame and rasterises the assembled
document with resvg (a Rust port of the SVG spec's rendering model).  Drawing
is pure and deterministic — a scene is a function `render(t) -> Canvas`, so any
frame can be produced independently, in any order, on any process.  That is
what allows frame-exact previews and parallel final renders.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Iterable, Sequence

import resvg_py

from . import theme
from .theme import C, HEIGHT, WIDTH, rgba

try:  # optional fast path
    import numpy as np
except Exception:  # pragma: no cover
    np = None


_FONTS: list[str] | None = None


def font_files() -> list[str]:
    global _FONTS
    if _FONTS is None:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
        _FONTS = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith((".woff2", ".ttf")))
    return _FONTS


class Canvas:
    """Accumulates SVG for a single frame."""

    __slots__ = ("w", "h", "layers", "_defs", "bg")

    def __init__(self, w: int = WIDTH, h: int = HEIGHT, background: bool = False):
        self.w, self.h = w, h
        self.layers: list[str] = []
        self._defs: list[str] = []
        self.bg = background

    # ------------------------------------------------------------- layers
    def add(self, svg: str) -> "Canvas":
        if svg:
            self.layers.append(svg)
        return self

    def defs(self, svg: str) -> "Canvas":
        self._defs.append(svg)
        return self

    # -------------------------------------------------------------- basic
    def rect(self, x, y, w, h, fill="none", stroke="none", sw=1.0, rx=0, opacity=1.0,
             filter_=None, extra=""):
        f = f' filter="url(#{filter_})"' if filter_ else ""
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w,0):.2f}" height="{max(h,0):.2f}" rx="{rx:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:.2f}"{o}{f} {extra}/>'
        )
        return self

    def circle(self, cx, cy, r, fill="none", stroke="none", sw=1.0, opacity=1.0,
               filter_=None, extra=""):
        if r <= 0:
            return self
        f = f' filter="url(#{filter_})"' if filter_ else ""
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw:.2f}"{o}{f} {extra}/>'
        )
        return self

    def ellipse(self, cx, cy, rx, ry, fill="none", stroke="none", sw=1.0, opacity=1.0, extra=""):
        if rx <= 0 or ry <= 0:
            return self
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw:.2f}"{o} {extra}/>'
        )
        return self

    def line(self, x1, y1, x2, y2, stroke=C.ink, sw=2.0, opacity=1.0, cap="round",
             dash: str | None = None, filter_=None, extra=""):
        if opacity <= 0.002:
            return self
        d = f' stroke-dasharray="{dash}"' if dash else ""
        f = f' filter="url(#{filter_})"' if filter_ else ""
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" '
            f'stroke-width="{sw:.2f}" stroke-linecap="{cap}"{d}{o}{f} {extra}/>'
        )
        return self

    def poly(self, pts: Sequence[tuple[float, float]], fill="none", stroke="none", sw=1.0,
             opacity=1.0, close=True, cap="round", join="round", extra=""):
        if len(pts) < 2:
            return self
        d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + (" Z" if close else "")
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="{cap}" stroke-linejoin="{join}"{o} {extra}/>'
        )
        return self

    def polygon_fill(self, pts, fill, opacity=1.0, stroke="none", sw=0.0):
        return self.poly(pts, fill=fill, stroke=stroke, sw=sw, opacity=opacity)

    def path(self, d, fill="none", stroke="none", sw=1.0, opacity=1.0, extra=""):
        o = f' opacity="{opacity:.4f}"' if opacity < 0.999 else ""
        self.layers.append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round"{o} {extra}/>'
        )
        return self

    def text(self, x, y, s, size=24, color=C.ink, weight=400, family="Inter",
             anchor="start", opacity=1.0, tracking=0.0, progress=1.0, extra="", dy=0.0):
        """Draw a text run. Supports inline <sub>/<sup> markup."""
        from .typography import Font, has_markup, rich
        if has_markup(s):
            r = rich(s, family=family, weight=weight, size=size)
            self.layers.append(r.svg(x, y, color, opacity=opacity, anchor=anchor,
                                     progress=progress, dy=dy))
            return r
        f = Font(family, weight, size, s, tracking=tracking)
        self.layers.append(f.svg(x, y, color, opacity=opacity, anchor=anchor, progress=progress, extra_attrs=extra, dy=dy))
        return f

    def raw(self, svg: str):
        self.layers.append(svg)
        return self

    # ------------------------------------------------------------- compose
    def svg(self, defs_extra: str = "") -> str:
        """
        The background plate (gradient, glow, vignette, film grain) is composited
        once per film by `engine.background` and reused as an underlay; drawing it
        inside every frame would re-run two full-screen filters 30x per second.
        """
        body = "".join(self.layers)
        bg = ""
        if self.bg:
            bg = (f'<rect width="{self.w}" height="{self.h}" fill="url(#bgGrad)"/>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">'
            f'{theme.shared_defs()}{"".join(self._defs)}{defs_extra}'
            f'{bg}{body}</svg>'
        )

    # ------------------------------------------------------------- raster
    def render(self, scale: float = 1.0, background: str | None = None, transparent: bool = True):
        """Return PNG bytes (transparent by default, so the plate shows through)."""
        w, h = int(round(self.w * scale)), int(round(self.h * scale))
        if transparent and background is None:
            # resvg defaults to an opaque canvas; "none" keeps the alpha channel
            background = "rgba(0,0,0,0)"
        return resvg_py.svg_to_bytes(
            svg_string=self.svg(),
            width=w,
            height=h,
            background=background,
            skip_system_fonts=True,
            font_files=font_files(),
            shape_rendering="geometric_precision",
            text_rendering="geometric_precision",
        )

    def render_array(self, scale: float = 1.0, with_alpha: bool = True):
        """Return a numpy array (H, W, 4) RGBA by default."""
        import io
        from PIL import Image
        png = self.render(scale=scale)
        im = Image.open(io.BytesIO(png))
        return np.asarray(im.convert("RGBA") if with_alpha else im.convert("RGB"))


# ---------------------------------------------------------------- utilities
def gradient_defs(gid: str, stops: Iterable[tuple[float, str]], x1=0, y1=0, x2=1, y2=0, units="objectBoundingBox"):
    s = "".join(f'<stop offset="{o*100:.1f}%" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" gradientUnits="{units}">{s}</linearGradient>'


def radial_defs(gid: str, stops: Iterable[tuple[float, str]], cx=0.5, cy=0.5, r=0.5):
    s = "".join(f'<stop offset="{o*100:.1f}%" stop-color="{c}"/>' for o, c in stops)
    return f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}">{s}</radialGradient>'
