"""
Typography.

Two complementary paths:

* `Font` — HarfBuzz shaping of real OpenType fonts (kerning, ligatures,
  fractional advances).  Text is emitted as SVG **paths**, so what the
  rasteriser draws is exactly the letterforms the designer chose: no font
  substitution, no missing-glyph boxes, pixel-identical on every machine.
* `Math` — TeX typeset by MathJax at build time into glyph paths, then placed
  with the engine's camera/opacity machinery.

All measurement is done during shaping, so layouts are exact and text can be
animated per glyph (counting reveals, per-letter stagger, tracking changes).
"""
from __future__ import annotations

import io
import json
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Sequence

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

FAMILIES = {
    "Inter": {400: "inter-400.woff2", 500: "inter-500.woff2", 600: "inter-600.woff2", 700: "inter-700.woff2"},
    "Fraunces": {400: "fraunces-400.woff2", 600: "fraunces-600.woff2", 700: "fraunces-700.woff2"},
    "JetBrains Mono": {400: "jetbrains-mono-400.woff2", 500: "jetbrains-mono-500.woff2", 600: "jetbrains-mono-600.woff2"},
}

#: Fallback chain. Display faces carry Latin only, so Greek/math symbols
#: (∇ σ θ η ‖ ∂ ⊤ …) are shaped by Noto Sans Math instead of becoming tofu.
FALLBACKS = {400: "noto-sans-math-400.woff2"}


def _nearest_weight(table: dict[int, str], weight: int) -> int:
    return min(table.keys(), key=lambda w: abs(w - weight))


@dataclass
class Glyph:
    char: str
    x: float             # pen position at draw time (px)
    advance: float       # px
    path: str            # SVG path data in px, y-down, origin at baseline
    bbox: tuple[float, float, float, float] | None  # x0,y0,x1,y1 relative to pen origin
    cluster: int


class Font:
    """A shaped text run on the baseline, ready to emit as SVG."""

    def __init__(self, family: str, weight: int, size: float, text: str,
                 tracking: float = 0.0, features: dict | None = None,
                 italic: bool = False):
        self.family = family
        self.weight = weight
        self.size = size
        self.text = text
        self.tracking = tracking       # extra px per gap (em-scaled if float<4)
        self._font, self._tt, self._upem, self._fb = _load(family, weight)
        self._cmap = self._tt.getBestCmap() or {}
        self.glyphs: list[Glyph] = []
        self._shape(text, features or {})
        self.ascent, self.descent, self.cap_height, self.x_height = _metrics(self._tt, self._upem, size)

    # ---------------------------------------------------------------- shape
    def _shape(self, text: str, features: dict):
        upem = self._upem
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self._font, buf, features or None)
        scale = self.size / upem
        gs = self._tt.getGlyphSet()
        order = self._tt.getGlyphOrder()
        pen_x = 0.0
        prev_x = 0.0
        track_px = self.tracking * (self.size if self.tracking and self.tracking < 4 else 1.0)
        fb = self._fb
        fb_scale = (self.size / fb[2]) if fb else scale
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            gname = order[info.codepoint] if info.codepoint < len(order) else None
            ch = text[info.cluster:info.cluster + 1] if info.cluster < len(text) else ""
            if self.glyphs:
                pen_x += track_px
            x = pen_x + pos.x_offset * scale
            y = -pos.y_offset * scale
            adv = pos.x_advance * scale
            path, bbox = _glyph_path(gs, gname, scale, x, y)
            # HarfBuzz maps unmapped characters to .notdef, whose outline *is* the
            # tofu box: treat it as a miss and use the math fallback face instead.
            missing = (ch and ord(ch) not in self._cmap) or gname in (None, ".notdef")
            if missing and fb is not None and ch:
                # fall back to the math face for symbols the display face lacks
                fb_cmap = fb[1].getBestCmap()
                gname_fb = fb_cmap.get(ord(ch))
                if gname_fb is not None:
                    path, bbox = _glyph_path(fb[1].getGlyphSet(), gname_fb, fb_scale, x, y)
                    if path:
                        adv = fb[1]["hmtx"][gname_fb][0] * fb_scale
            self.glyphs.append(Glyph(ch, x, adv, path, bbox, info.cluster))
            pen_x += adv
        self.advance = pen_x

    # --------------------------------------------------------------- metrics
    def width(self) -> float:
        return self.advance

    def bbox(self) -> tuple[float, float, float, float]:
        xs0, ys0, xs1, ys1 = [], [], [], []
        for g in self.glyphs:
            if g.bbox is None:
                continue
            xs0.append(g.bbox[0]); ys0.append(g.bbox[1])
            xs1.append(g.bbox[2]); ys1.append(g.bbox[3])
        if not xs0:
            return (0.0, -self.ascent, self.advance, self.descent)
        return (min(xs0), min(ys0), max(xs1), max(ys1))

    # ---------------------------------------------------------------- output
    def svg(self, x: float, y: float, fill: str, opacity: float = 1.0,
            anchor: str = "start", progress: float = 1.0,
            dx: float = 0.0, dy: float = 0.0, extra_attrs: str = "",
            size_mult: float = 1.0) -> str:
        if size_mult != 1.0:
            # scale about the baseline origin (used for sub/superscript runs)
            inner = self.svg(x, y, fill, opacity=opacity, anchor=anchor,
                             progress=progress, dx=0.0, dy=0.0,
                             extra_attrs=extra_attrs)
            w = self.advance
            ox = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0.0) + dx
            return (f'<g transform="translate({ox:.2f},{y + dy:.2f}) scale({size_mult:.3f}) '
                    f'translate({-ox:.2f},{-(y + dy):.2f})">{inner}</g>')
        """Emit the shaped run. `progress` reveals glyphs left-to-right."""
        w = self.advance
        ox = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0.0)
        n = len(self.glyphs)
        out = []
        op = f' opacity="{opacity:.3f}"' if opacity < 0.999 else ""
        if progress >= 0.999:
            parts = [f'<path d="{g.path}"/>' for g in self.glyphs if g.path]
            if parts:
                out.append(f'<g transform="translate({ox + dx:.2f},{y + dy:.2f})" fill="{fill}"{op} {extra_attrs}>')
                out.extend(parts)
                out.append("</g>")
        else:
            shown = progress * n
            for i, g in enumerate(self.glyphs):
                if not g.path:
                    continue
                a = max(0.0, min(1.0, shown - i + 1))
                if a <= 0:
                    continue
                gop = opacity * a
                if gop <= 0.002:
                    continue
                out.append(
                    f'<g transform="translate({ox + dx + g.x:.2f},{y + dy:.2f})" fill="{fill}" opacity="{gop:.3f}" {extra_attrs}><path d="{g.path}"/></g>'
                )
        return "".join(out)


# ------------------------------------------------------------------ caches
def _ttf_bytes(path: str) -> bytes:
    """woff2 -> raw TTF bytes (HarfBuzz reads woff2 poorly)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if path.endswith(".woff2"):
        tt = TTFont(io.BytesIO(data))
        tt.flavor = None
        raw = io.BytesIO()
        tt.save(raw)
        return raw.getvalue()
    return data


@lru_cache(maxsize=64)
def _load(family: str, weight: int):
    """Returns (hb_font, ttfont, upem, fallback(hb_font, ttfont, upem))."""
    if family not in FAMILIES:
        family = "Inter"
    table = FAMILIES[family]
    w = _nearest_weight(table, weight)
    ttf_bytes = _ttf_bytes(os.path.join(FONT_DIR, table[w]))
    tt2 = TTFont(io.BytesIO(ttf_bytes))     # fresh, for outlines
    face = hb.Face(hb.Blob(ttf_bytes))
    font = hb.Font(face)
    fb = None
    fb_path = os.path.join(FONT_DIR, FALLBACKS[400])
    if os.path.exists(fb_path):
        fb_bytes = _ttf_bytes(fb_path)
        fb_tt = TTFont(io.BytesIO(fb_bytes))
        fb_face = hb.Face(hb.Blob(fb_bytes))
        fb = (hb.Font(fb_face), fb_tt, fb_face.upem)
    return font, tt2, face.upem, fb


def _metrics(tt: TTFont, upem: int, size: float):
    hhea = tt["hhea"]
    os2 = tt["OS/2"] if "OS/2" in tt else None
    ascent = hhea.ascent / upem * size
    descent = abs(hhea.descent) / upem * size
    cap = (getattr(os2, "sCapHeight", 0) or hhea.ascent * 0.7) / upem * size
    xh = (getattr(os2, "sxHeight", 0) or cap * 0.72) / upem * size
    return ascent, descent, cap, xh


@lru_cache(maxsize=8192)
def _glyph_path_cached(family: str, weight: int, gname: str, scale_q: int):
    """Cached outline in font units scaled by scale_q/10000. Returns (path, bbox)."""
    _, tt, _ = _load(family, weight)
    gs = tt.getGlyphSet()
    pen = SVGPathPen(gs)
    try:
        gs[gname].draw(pen)
    except KeyError:
        return "", None
    d = pen.getCommands()
    if not d:
        return "", None
    bp = BoundsPen(gs)
    try:
        gs[gname].draw(bp)
    except KeyError:
        return d, None
    b = bp.bounds
    return d, b


def _glyph_path(gs, gname: str, scale: float, x: float, y: float):
    """Glyph outline in px with (x, y) pen origin, y-down screen space."""
    if gname is None:
        return "", None
    d, b = _raw_outline(gname, gs)
    if not d:
        return "", None
    # font units are y-up; flip and scale, then translate to pen origin
    tr = f"translate({x:.3f},{y:.3f}) scale({scale:.6f},{-scale:.6f})"
    path = f'<g transform="{tr}"><path d="{d}"/></g>' if False else _transformed_path(d, scale, x, y)
    bbox = None
    if b:
        bbox = (b[0] * scale + x, -b[3] * scale + y, b[2] * scale + x, -b[1] * scale + y)
    return path, bbox


def _raw_outline(gname: str, gs):
    pen = SVGPathPen(gs)
    try:
        gs[gname].draw(pen)
    except KeyError:
        return "", None
    d = pen.getCommands()
    if not d:
        return "", None
    bp = BoundsPen(gs)
    try:
        gs[gname].draw(bp)
    except KeyError:
        return d, None
    return d, bp.bounds


def _transformed_path(d: str, scale: float, x: float, y: float) -> str:
    """
    Bake translate+scale(1,-1) into the path coordinates so each glyph is a
    single <path> with absolute numbers (no nested <g>, smaller SVG, faster).
    """
    import re
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e[-+]?\d+)?", d)
    out: list[str] = []
    i = 0
    cmd = None
    cx = cy = 0.0
    nx = ny = 0.0  # current point in font units

    def num():
        nonlocal i
        v = float(tokens[i]); i += 1
        return v

    def pt(rel: bool, fx: float, fy: float):
        px = nx + fx if rel else fx
        py = ny + fy if rel else fy
        return px, py

    def emit(px, py):
        out.append(f"{x + px * scale:.3f} {y - py * scale:.3f}")

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
            if cmd in "Zz":
                out.append("Z")
                continue
        if cmd is None:
            break
        c = cmd.upper()
        rel = cmd.islower()
        if c == "M":
            fx, fy = num(), num()
            px, py = pt(rel, fx, fy)
            nx, ny = px, py
            out.append("M"); emit(px, py)
            cmd = "l" if rel else "L"      # implicit lineto after moveto
        elif c == "L":
            fx, fy = num(), num()
            px, py = pt(rel, fx, fy)
            nx, ny = px, py
            out.append("L"); emit(px, py)
        elif c == "H":
            fx = num()
            px = nx + fx if rel else fx
            nx = px
            out.append("L"); emit(px, ny)
        elif c == "V":
            fy = num()
            py = ny + fy if rel else fy
            ny = py
            out.append("L"); emit(nx, py)
        elif c == "Q":
            f1x, f1y = num(), num()
            fx, fy = num(), num()
            c1x, c1y = pt(rel, f1x, f1y)
            px, py = pt(rel, fx, fy)
            out.append("Q"); emit(c1x, c1y); emit(px, py)
            nx, ny = px, py
        elif c == "C":
            f1x, f1y = num(), num()
            f2x, f2y = num(), num()
            fx, fy = num(), num()
            c1x, c1y = pt(rel, f1x, f1y)
            c2x, c2y = pt(rel, f2x, f2y)
            px, py = pt(rel, fx, fy)
            out.append("C"); emit(c1x, c1y); emit(c2x, c2y); emit(px, py)
            nx, ny = px, py
        elif c == "S":
            f2x, f2y = num(), num()
            fx, fy = num(), num()
            c2x, c2y = pt(rel, f2x, f2y)
            px, py = pt(rel, fx, fy)
            out.append("S"); emit(c2x, c2y); emit(px, py)
            nx, ny = px, py
        elif c == "T":
            fx, fy = num(), num()
            px, py = pt(rel, fx, fy)
            out.append("T"); emit(px, py)
            nx, ny = px, py
        else:
            # unsupported command: bail out to a cheap fallback
            return d
    return " ".join(out).replace(" Z", "Z")


# --------------------------------------------------------------- convenience
def text(family: str, weight: int, size: float, s: str, tracking: float = 0.0) -> Font:
    return Font(family, weight, size, s, tracking=tracking)


def measure(family: str, weight: int, size: float, s: str, tracking: float = 0.0) -> float:
    return Font(family, weight, size, s, tracking=tracking).advance


# --------------------------------------------------------------- rich text
_RICH_CACHE: dict[tuple, "RichText"] = {}


class RichText:
    """
    Inline markup runs:  "w<sub>1</sub> + σ<sup>(2)</sup>"

    Sub/superscripts are real typographic offsets (62 % size, shifted 0.18 em
    down / 0.42 em up), not Unicode codepoints — so they render in every face
    and stay crisp at any resolution.
    """

    def __init__(self, markup: str, family: str, weight: int, size: float):
        self.runs = []          # (Font, dy, size_mult)
        self.size = size
        self.h = size
        for txt, mode in _parse_markup(markup):
            if mode == "sub":
                f = Font(family, weight, size * 0.64, txt)
                self.runs.append((f, size * 0.18, 0.64))
            elif mode == "sup":
                f = Font(family, weight, size * 0.64, txt)
                self.runs.append((f, -size * 0.40, 0.64))
            else:
                self.runs.append((Font(family, weight, size, txt), 0.0, 1.0))
        self.advance = sum(f.advance for f, _, _ in self.runs)

    def svg(self, x, y, fill, opacity=1.0, anchor="start", progress=1.0, dy=0.0, dx=0.0):
        w = self.advance
        ox = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0.0)
        out = []
        cx = ox + dx
        for f, ddy, smult in self.runs:
            if f.glyphs:
                out.append(f.svg(cx, y + dy + ddy, fill, opacity=opacity, progress=progress))
            cx += f.advance
        return "".join(out)

    def bbox(self):
        return (0.0, -self.size * 0.75, self.advance, self.size * 0.25)


def _parse_markup(markup: str):
    """-> [(text, mode)] with mode in {'normal','sub','sup'}"""
    import re
    runs = []
    pos = 0
    for m in re.finditer(r"<(sub|sup)>(.*?)</\1>", markup):
        if m.start() > pos:
            runs.append((markup[pos:m.start()], "normal"))
        runs.append((m.group(2), m.group(1)))
        pos = m.end()
    if pos < len(markup):
        runs.append((markup[pos:], "normal"))
    return [r for r in runs if r[0]]


def rich(markup: str, family: str = "Inter", weight: int = 500, size: float = 24) -> RichText:
    key = (markup, family, weight, size)
    if key not in _RICH_CACHE:
        _RICH_CACHE[key] = RichText(markup, family, weight, size)
    return _RICH_CACHE[key]


def has_markup(s: str) -> bool:
    return "<" in s and ("</sub>" in s or "</sup>" in s)
