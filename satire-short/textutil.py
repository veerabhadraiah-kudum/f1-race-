"""Text layout helpers: HarfBuzz-shaped Telugu + Latin display type for PIL.

PIL on this box has no Raqm, so complex-script text is shaped with uharfbuzz and
rasterised glyph-by-glyph with FreeType, then composited into PIL RGBA layers.
"""
from __future__ import annotations

import numpy as np
import uharfbuzz as hb
import freetype
from PIL import Image, ImageDraw, ImageFilter

FT_LOAD_RENDER = freetype.FT_LOAD_RENDER
FT_LOAD_NO_HINTING = freetype.FT_LOAD_NO_HINTING


class Shaper:
    """Shapes text with HarfBuzz and rasterises it with FreeType."""

    def __init__(self, font_path: str, size: int):
        self.path = font_path
        self.size = int(size)
        data = open(font_path, "rb").read()
        self.face = hb.Face(data)
        self.font = hb.Font(self.face)
        self.upem = self.face.upem
        # Work in 26.6 fixed point at the requested pixel size.
        self.font.scale = (self.size * 64, self.size * 64)
        self.ft = freetype.Face(font_path)
        self.ft.set_pixel_sizes(0, self.size)
        self._glyphs: dict[int, tuple[np.ndarray, int, int]] = {}

    # -- glyph cache -------------------------------------------------------
    def _glyph(self, gid: int):
        hit = self._glyphs.get(gid)
        if hit is not None:
            return hit
        self.ft.load_glyph(gid, FT_LOAD_RENDER | FT_LOAD_NO_HINTING)
        g = self.ft.glyph
        bm = g.bitmap
        if bm.width and bm.rows:
            arr = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)
            arr = arr[:, : bm.width]
        else:
            arr = np.zeros((0, 0), dtype=np.uint8)
        out = (arr, g.bitmap_left, g.bitmap_top)
        self._glyphs[gid] = out
        return out

    def shape(self, text: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        return list(zip(buf.glyph_infos, buf.glyph_positions))

    def measure(self, text: str) -> tuple[float, float, float, float]:
        """Returns (advance_width, ink_left, ink_top, ink_bottom) in px."""
        pen_x = 0.0
        adv = 0.0
        left = top = None
        bottom = 0.0
        for info, pos in self.shape(text):
            arr, bl, bt = self._glyph(info.codepoint)
            if arr.size:
                x0 = pen_x + pos.x_offset / 64 + bl
                y0 = -bt + pos.y_offset / 64
                left = x0 if left is None else min(left, x0)
                top = y0 if top is None else min(top, y0)
                bottom = max(bottom, y0 + arr.shape[0])
            pen_x += pos.x_advance / 64
            adv = max(adv, pen_x)
        if left is None:
            return adv, 0.0, 0.0, 0.0
        return adv, left, top, bottom

    def width(self, text: str) -> float:
        return self.measure(text)[0]

    def render(self, text: str, fill=(255, 255, 255, 255), stroke=None,
               stroke_w: int = 0, pad: int | None = None) -> Image.Image:
        """Renders one line to a tight RGBA image."""
        adv, ink_l, ink_t, ink_b = self.measure(text)
        pad = (stroke_w + 2) if pad is None else pad
        x_shift = -ink_l + pad
        w = int(np.ceil(adv - ink_l + 2 * pad)) + 1
        h = int(np.ceil(ink_b - ink_t + 2 * pad)) + 1
        mask = Image.new("L", (max(w, 1), max(h, 1)), 0)

        pen_x = 0.0
        for info, pos in self.shape(text):
            arr, bl, bt = self._glyph(info.codepoint)
            if arr.size:
                gx = int(round(pen_x + pos.x_offset / 64 + bl + x_shift))
                gy = int(round(-ink_t + pos.y_offset / 64 - bt + pad))
                gmask = Image.fromarray(arr, mode="L")
                mask.paste(gmask, (gx, gy), gmask)
            pen_x += pos.x_advance / 64

        if stroke_w and stroke is not None:
            stroked = mask.filter(ImageFilter.MaxFilter(stroke_w * 2 + 1))
            base = Image.new("RGBA", mask.size, stroke)
            base.putalpha(stroked)
            fill_layer = Image.new("RGBA", mask.size, fill)
            fill_layer.putalpha(mask)
            base.alpha_composite(fill_layer)
            return base
        out = Image.new("RGBA", mask.size, fill)
        out.putalpha(mask)
        return out


def wrap_lines(shaper: Shaper, text: str, max_w: float) -> list[str]:
    """Greedy wrap using shaped widths (word boundaries on spaces)."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and shaper.width(trial) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def latin_block(font, text: str, max_w: int) -> list[str]:
    """Wrap Latin text by measured width using PIL font metrics."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and font.getlength(trial) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def text_layer(lines, font, fill, stroke_w=0, stroke_fill=(0, 0, 0, 255),
               spacing=8, align="center", max_w=None):
    """Compose a multi-line PIL text block into a tight RGBA image."""
    pad = stroke_w + 4
    widths, heights = [], []
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    asc, desc = font.getmetrics()
    for ln in lines:
        widths.append(probe.textlength(ln, font=font))
        heights.append(asc + desc)
    W = int(max(widths)) + pad * 2 if widths else 1
    H = int(sum(heights) + spacing * (len(lines) - 1)) + pad * 2 if lines else 1
    im = Image.new("RGBA", (max(W, 1), max(H, 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = pad
    for ln, wdt, hgt in zip(lines, widths, heights):
        x = pad if align == "left" else pad + (max(widths) - wdt) / 2
        d.text((x, y), ln, font=font, fill=fill,
               stroke_width=stroke_w, stroke_fill=stroke_fill)
        y += hgt + spacing
    return im
