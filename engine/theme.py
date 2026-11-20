"""
Design system for the "Mathematics behind AI" film.

One palette, one type scale, one grid.  Everything on screen comes from here so
that every scene shares a single visual identity: a dark scientific canvas
(navy), cyan/teal as the "signal" colour, violet as the "parameter" colour and
a warm amber reserved for the loss / error idea.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    # canvas
    bg_top: str = "#0a1220"
    bg_bottom: str = "#050a12"
    bg_glow: str = "#12304a"
    panel: str = "#0d1826"
    panel_hi: str = "#122132"
    stroke: str = "#1d2f43"
    stroke_hi: str = "#2a4560"

    # signal colours
    cyan: str = "#22d3ee"
    cyan_soft: str = "#67e8f9"
    cyan_deep: str = "#0e7490"
    teal: str = "#2dd4bf"
    teal_deep: str = "#0f766e"
    violet: str = "#a78bfa"
    violet_soft: str = "#c4b5fd"
    violet_deep: str = "#6d28d9"
    amber: str = "#fbbf24"
    amber_deep: str = "#b45309"
    rose: str = "#fb7185"
    lime: str = "#a3e635"

    # type
    ink: str = "#f2f7fb"
    ink_soft: str = "#c3d3e0"
    ink_mute: str = "#8ba3b8"
    ink_faint: str = "#5b7386"


C = Palette()

# --------------------------------------------------------------------------
# type scale (px @ 1080p)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Type:
    family_sans: str = "Inter"
    family_serif: str = "Fraunces"
    family_mono: str = "JetBrains Mono"

    kicker: int = 22
    title: int = 66
    subtitle: int = 34
    h2: int = 44
    body: int = 27
    small: int = 21
    tiny: int = 17
    label: int = 19
    math: int = 46


T = Type()

# --------------------------------------------------------------------------
# canvas / grid
# --------------------------------------------------------------------------
WIDTH = 1920
HEIGHT = 1080
FPS = 30
SAFE = 96                 # title-safe margin
CONTENT_W = WIDTH - 2 * SAFE
CONTENT_H = HEIGHT - 2 * SAFE


# --------------------------------------------------------------------------
# CSS helpers
# --------------------------------------------------------------------------
def rgba(hex_color: str, alpha: float) -> str:
    """#rrggbb -> rgba(r,g,b,a) for SVG fill/stroke attributes."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{max(0.0, min(1.0, alpha)):.4f})"


def mix(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two #rrggbb colours (gamma-naive, sRGB)."""
    t = max(0.0, min(1.0, t))
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def lighten(hex_color: str, amount: float) -> str:
    return mix(hex_color, "#ffffff", amount)


def darken(hex_color: str, amount: float) -> str:
    return mix(hex_color, "#000000", amount)


# --------------------------------------------------------------------------
# shared SVG defs: gradients, soft shadows, glows, grain
# --------------------------------------------------------------------------
def shared_defs(theme_id: str = "mba") -> str:
    return f"""
<defs id="theme-{theme_id}">
  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{C.bg_top}"/>
    <stop offset="100%" stop-color="{C.bg_bottom}"/>
  </linearGradient>
  <radialGradient id="bgGlow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{C.bg_glow}" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="{C.bg_glow}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="cyanGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{C.cyan_deep}"/>
    <stop offset="55%" stop-color="{C.cyan}"/>
    <stop offset="100%" stop-color="{C.teal}"/>
  </linearGradient>
  <linearGradient id="violetGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{C.violet_soft}"/>
    <stop offset="100%" stop-color="{C.violet_deep}"/>
  </linearGradient>
  <linearGradient id="surfaceGrad" x1="0" y1="0" x2="0.3" y2="1">
    <stop offset="0%" stop-color="{lighten(C.teal, 0.18)}"/>
    <stop offset="45%" stop-color="{C.teal}"/>
    <stop offset="100%" stop-color="{C.cyan_deep}"/>
  </linearGradient>
  <radialGradient id="surfaceLight" cx="30%" cy="18%" r="80%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.35"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>
  <filter id="softShadow" x="-60%" y="-60%" width="220%" height="220%">
    <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#000000" flood-opacity="0.55"/>
  </filter>
  <filter id="panelShadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000000" flood-opacity="0.40"/>
  </filter>
  <filter id="glowCyan" x="-120%" y="-120%" width="340%" height="340%">
    <feGaussianBlur stdDeviation="10" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="glowSoft" x="-150%" y="-150%" width="400%" height="400%">
    <feGaussianBlur stdDeviation="26"/>
  </filter>
  <filter id="glowSmall" x="-120%" y="-120%" width="340%" height="340%">
    <feGaussianBlur stdDeviation="4"/>
  </filter>
  <filter id="grain">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>
    <feColorMatrix type="saturate" values="0"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.045"/></feComponentTransfer>
  </filter>
  <radialGradient id="vignette" cx="50%" cy="48%" r="72%">
    <stop offset="55%" stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.55"/>
  </radialGradient>
</defs>
"""
