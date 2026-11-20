"""
LaTeX typesetting bridge.

MathJax runs once at build time (`tools/tex2svg.mjs`) and returns every glyph
outline with its MathML ancestry.  That ancestry is what lets the engine treat
*mathematical structure* as an animatable object: a fraction, a summation, a
radical or a single symbol all become addressable groups with their own
opacity / transform, so equations can build term by term, highlight, pulse or
be bound to the geometry elsewhere on screen.

Placement is em-based: 1 unit in the source SVG = 1/1000 em, so a 46px equation
is just `size=46` regardless of the resolution it was rasterised at.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "assets", "math", "cache.json")
TEX2SVG = os.path.join(ROOT, "tools", "tex2svg.mjs")
NODE = os.environ.get("NODE_BINARY", "node")


@dataclass
class MathGlyph:
    d: str
    matrix: list[float]
    key: str        # MathML ancestry path, e.g. //mrow//mfrac//mfrac//mtd...
    fill: str       # "currentColor" or a MathJax colour


@dataclass
class MathTex:
    tex: str
    view_w: float          # in em (already divided by 1000)
    view_h: float
    x0: float
    y0: float
    baseline: float        # em from top of the viewBox to the baseline
    glyphs: list[MathGlyph]

    # --------------------------------------------------------------- metrics
    @property
    def width(self) -> float:
        return self.view_w

    @property
    def height(self) -> float:
        return self.view_h

    def width_px(self, size: float) -> float:
        return self.view_w * size

    def height_px(self, size: float) -> float:
        return self.view_h * size

    # ---------------------------------------------------------------- render
    def svg(self, x: float, y: float, size: float, color: str, opacity: float = 1.0,
            anchor: str = "start", reveal: float = 1.0, scale: float = 1.0,
            color_map: dict[str, str] | None = None,
            highlight: dict[str, str] | None = None,
            highlight_alpha: float = 0.0,
            extra_attrs: str = "") -> str:
        """
        Render at (x, y) where y is the **baseline**.

        reveal  — 0..1 progressive left-to-right draw-on
        highlight — {key_substring: colour} tints matching glyph groups
        """
        # glyph matrices are in MathJax units (1/1000 em) -> px per raw unit
        u = size * scale / 1000.0
        s = u
        w_px = self.view_w * size * scale
        ox = x - (w_px if anchor == "end" else w_px / 2 if anchor == "middle" else 0.0)
        top = y - self.baseline * size * scale
        cmap = color_map or {}
        hl = highlight or {}
        out = [f'<g transform="translate({ox:.2f},{top:.2f}) scale({s:.4f}) translate({-self.x0:.2f},{-self.y0:.2f})" {extra_attrs}>']
        n = len(self.glyphs)
        for i, g in enumerate(self.glyphs):
            a = opacity
            if reveal < 0.999:
                prog = reveal * n
                a *= max(0.0, min(1.0, prog - i + 2.4))
                if a <= 0.004:
                    continue
            if a <= 0.004:
                continue
            fill = g.fill
            if fill in ("currentColor", "none", ""):
                fill = color
            if g.key in cmap:
                fill = cmap[g.key]
            for sub, c in hl.items():
                if sub and sub in g.key:
                    fill = c
            m = g.matrix
            out.append(
                f'<path transform="matrix({m[0]:.4f},{m[1]:.4f},{m[2]:.4f},{m[3]:.4f},{m[4]:.2f},{m[5]:.2f})" '
                f'd="{g.d}" fill="{fill}" opacity="{a:.3f}"/>'
            )
        out.append("</g>")
        return "".join(out)

    def bbox(self, x: float, y: float, size: float, anchor: str = "start"):
        w = self.view_w * size
        ox = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0.0)
        return (ox, y - self.baseline * size, ox + w, y + (self.view_h - self.baseline) * size)

    # ------------------------------------------------------------- searching
    def find(self, *needles: str) -> "MathGroup":
        """Select glyphs whose ancestry path contains all needles."""
        sel = [g for g in self.glyphs if all(n in g.key for n in needles)]
        return MathGroup(self, sel)


class MathGroup:
    """A sub-selection of an equation (a term, a fraction, one symbol)."""

    def __init__(self, tex: MathTex, glyphs: list[MathGlyph]):
        self.tex = tex
        self.glyphs = glyphs
        self.keys = {g.key for g in glyphs}

    def __len__(self):
        return len(self.glyphs)

    def bbox_px(self, x: float, y: float, size: float, anchor: str = "start"):
        """Approximate bounding box in px, from glyph outline extents."""
        if not self.glyphs:
            return (x, y, x, y)
        w = self.tex.view_w * size
        ox = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0.0)
        top = y - self.tex.baseline * size
        u = size / 1000.0
        xs, ys = [], []
        for g in self.glyphs:
            m = g.matrix
            b = _path_bbox_approx(g.d)
            if not b:
                continue
            for px, py in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])):
                X = m[0] * px + m[2] * py + m[4]
                Y = m[1] * px + m[3] * py + m[5]
                xs.append(ox + X * u)
                ys.append(top + Y * u)
        if not xs:
            return (x, y, x, y)
        return (min(xs), min(ys), max(xs), max(ys))


_BBOX_CACHE: dict[str, tuple] = {}


def _path_bbox_approx(d: str):
    """Cheap numeric bbox from path numbers (control points included: fine for layout)."""
    if d in _BBOX_CACHE:
        return _BBOX_CACHE[d]
    import re
    nums = re.findall(r"-?\d*\.?\d+(?:e[-+]?\d+)?", d)
    vals = [float(n) for n in nums]
    xs, ys = vals[0::2], vals[1::2]
    if not xs or not ys:
        return None
    r = (min(xs), min(ys), max(xs), max(ys))
    _BBOX_CACHE[d] = r
    return r


# ------------------------------------------------------------------- build
def _load_cache() -> dict:
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            return json.load(fh)
    return {}


def _save_cache(cache: dict):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as fh:
        json.dump(cache, fh)


def prebuild(tex_list: list[str], display: bool = True):
    """Batch-typeset a list of TeX strings (one node process for all of them)."""
    cache = _load_cache()
    todo = []
    for tex in tex_list:
        key = _key(tex, display)
        if key not in cache:
            todo.append({"key": key, "tex": tex, "display": display})
    if not todo:
        return
    jobs = os.path.join(CACHE + ".jobs.json")
    out = os.path.join(CACHE + ".out.json")
    with open(jobs, "w") as fh:
        json.dump(todo, fh)
    p = subprocess.run([NODE, TEX2SVG, jobs, out], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("MathJax conversion failed:\n" + p.stderr[-3000:])
    results = json.load(open(out))
    for r in results:
        if r.get("ok"):
            cache[r["key"]] = r["svg"]
        else:
            raise RuntimeError(f"TeX error in {r['key']}: {r.get('error')}")
    _save_cache(cache)


def _key(tex: str, display: bool) -> str:
    return hashlib.sha1(((("D" if display else "I") + tex)).encode()).hexdigest()[:16]


@lru_cache(maxsize=512)
def tex(s: str, display: bool = True) -> MathTex:
    """Get a typeset equation (prebuilt or on-demand)."""
    cache = _load_cache()
    key = _key(s, display)
    if key not in cache:
        prebuild([s], display)
        cache = _load_cache()
    raw = cache[key]
    vb = raw["viewBox"]
    scale = 1.0 / 1000.0
    glyphs = [
        MathGlyph(p["d"], p.get("matrix", [1, 0, 0, 1, 0, 0]), p.get("key", ""), p.get("fill", "currentColor"))
        for p in raw["paths"]
        if p.get("t") == "path"
    ]
    return MathTex(
        tex=s,
        view_w=vb[2] * scale,
        view_h=vb[3] * scale,
        x0=vb[0],
        y0=vb[1],
        baseline=raw.get("baseline_em", vb[3] / 1000.0),
        glyphs=glyphs,
    )
