"""
Background plate + compositing.

The canvas background (vertical gradient, two ambient glows, vignette, fine
film grain) is generated **once** per process as a numpy plate.  Doing it in
numpy rather than SVG matters: a full-screen feTurbulence grain filter costs
tens of seconds to rasterise, while the same look as a noise field costs a few
milliseconds and gives exact control over grain size and intensity.

Frames themselves are rendered by the SVG engine with a transparent background
and flattened onto this plate, so every scene shares one unchanged visual
identity and per-frame raster work stays cheap.
"""
from __future__ import annotations

import io
from functools import lru_cache

import numpy as np
from PIL import Image

from . import theme
from .theme import HEIGHT, WIDTH


def _hex_rgb(h: str):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.float32) / 255.0


def _radial(w: int, h: int, cx: float, cy: float, rx: float, ry: float, power: float = 2.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return np.clip(1.0 - d, 0.0, 1.0) ** power


@lru_cache(maxsize=12)
def plate_array(w: int = WIDTH, h: int = HEIGHT) -> np.ndarray:
    C = theme.C
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    top, bottom = _hex_rgb(C.bg_top), _hex_rgb(C.bg_bottom)
    # gentle s-curve so the top stays airy and the base falls off fast
    g = (yy ** 1.35)
    img = top[None, None, :] * (1 - g) + bottom[None, None, :] * g
    img = np.repeat(img, w, axis=1)

    # ambient key glow (upper-left, cool) + fill glow (lower-right, violet)
    key = _radial(w, h, w * 0.30, h * 0.20, w * 0.52, h * 0.62, 2.4) * 0.55
    fill = _radial(w, h, w * 0.88, h * 0.95, w * 0.45, h * 0.50, 2.6) * 0.30
    cool = _hex_rgb(C.bg_glow)
    vio = _hex_rgb(C.violet_deep)
    img = img * (1 - key[..., None]) + cool * key[..., None]
    img = img * (1 - fill[..., None]) + vio * fill[..., None]

    # vignette
    vig = 1.0 - 0.52 * _radial(w, h, w * 0.5, h * 0.47, w * 0.78, h * 0.92, 3.2)
    img = img * vig[..., None]

    # film grain (mono, soft, fixed seed for determinism)
    rng = np.random.default_rng(20261120)
    grain = rng.normal(0.0, 1.0, (h // 2 + 1, w // 2 + 1)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((grain * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8))
                       .resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0 - 0.5
    img = img + grain[..., None] * 0.030

    return np.clip(img * 255.0, 0, 255).astype(np.uint8)


def plate_image(w: int = WIDTH, h: int = HEIGHT) -> Image.Image:
    return Image.fromarray(plate_array(w, h))


def flatten(frame: np.ndarray, dim: float = 0.0, w: int = WIDTH, h: int = HEIGHT) -> np.ndarray:
    """
    Composite a frame (RGB or RGBA at 1x) onto the cached plate.

    `dim` fades the result toward black — used for scene-out transitions.
    """
    plate = plate_array(w, h)
    f = frame.astype(np.float32) / 255.0
    if f.shape[2] == 4:
        a = f[..., 3:4]
        out = plate.astype(np.float32) / 255.0 * (1 - a) + f[..., :3] * a
    else:
        out = f
    if dim:
        out = out * (1.0 - dim)
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def make_png(frame: np.ndarray, dim: float = 0.0, out_path: str | None = None) -> bytes:
    from PIL import Image as _I
    arr = flatten(frame, dim=dim)
    im = _I.fromarray(arr)
    if out_path:
        im.save(out_path, compress_level=1)
        return b""
    buf = io.BytesIO()
    im.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()
