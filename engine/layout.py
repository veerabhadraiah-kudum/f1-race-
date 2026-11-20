"""
Measured layout primitives.

Everything is measured with the real shaped widths, so panels, captions and
axis labels never overlap by accident.  The film reserves three zones and every
scene is composed inside them:

    ┌──────────────────────────────────────────────┐
    │  header  (chapter label / title)             │  y 56 … 132
    ├──────────────────────────────────────────────┤
    │                                              │
    │  stage   (the 3D / diagram space)            │  y 140 … 800
    │                                              │
    ├────────────────────────────────────────────────┤
    │  narration caption                           │  y 806 … 980
    └──────────────────────────────────────────────┘   HUD y 1018

`Stage` stores those numbers once and every scene reads them, which is what
keeps the composition consistent from shot to shot.
"""
from __future__ import annotations

from dataclasses import dataclass

from .theme import HEIGHT, SAFE, WIDTH

HEADER_Y = 66
STAGE_TOP = 150
STAGE_BOTTOM = 780
CAPTION_TOP = 812
CAPTION_BASELINE = 884
HUD_Y = HEIGHT - 54

#: where the narration caption is centred (keeps it clear of side panels)
CAPTION_CX = WIDTH // 2


@dataclass(frozen=True)
class Zone:
    top: float
    bottom: float

    @property
    def h(self) -> float:
        return self.bottom - self.top

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


STAGE = Zone(STAGE_TOP, STAGE_BOTTOM)
CAPTION = Zone(CAPTION_TOP, 994)


def panel(cv, x, y, w, h, alpha=1.0, accent=None, accent_side="left", radius=12,
          fill="rgba(9,18,29,0.68)", stroke="rgba(42,69,96,0.85)", accent_alpha=0.9):
    """The house panel: translucent navy, hairline stroke, accent bar."""
    cv.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.2, rx=radius, opacity=alpha)
    if accent:
        if accent_side == "left":
            cv.rect(x, y + 1, 3.2, h - 2, fill=accent, rx=1.6, opacity=accent_alpha * alpha)
        elif accent_side == "top":
            cv.rect(x + 1, y, w - 2, 2.6, fill=accent, rx=1.3, opacity=accent_alpha * alpha)


def section_label(cv, x, y, text_, color=None, alpha=1.0, size=13):
    from .theme import C
    cv.text(x, y, text_, size=size, color=color or C.ink_mute, weight=600,
            tracking=0.19, opacity=alpha)


def divider(cv, x0, x1, y, alpha=0.5, color=None):
    from .theme import C
    cv.line(x0, y, x1, y, stroke=color or C.stroke_hi, sw=1.0, opacity=alpha)


def chip(cv, x, y, label, color, size=15, pad_x=11, pad_y=6, alpha=1.0, fill_alpha=0.14):
    """A small pill label; returns its width."""
    from .theme import rgba
    from .typography import Font
    f = Font("Inter", 600, size, label, tracking=0.02)
    w = f.advance + pad_x * 2
    h = size + pad_y * 2
    cv.rect(x, y, w, h, fill=rgba(color, fill_alpha), stroke=rgba(color, 0.55), sw=1.0,
            rx=h / 2, opacity=alpha)
    cv.raw(f.svg(x + pad_x, y + h - pad_y - size * 0.24, color, opacity=alpha))
    return w
