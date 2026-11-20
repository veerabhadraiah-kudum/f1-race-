"""
3D surface renderer: shaded height fields drawn with a perspective camera.

The surface is a real differentiable function sampled on a grid.  Each quad is
projected, depth-sorted (painter's algorithm), shaded with a Lambert term and
mapped through a scientific colour ramp, so the render responds to the actual
geometry — lighting changes as the camera orbits, and the descent path follows
the true gradient.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .canvas import Canvas
from .linalg import Camera, project_polyline, vadd, vcross, vnorm, vsub, vmul, vdot
from .theme import C, rgba


# ------------------------------------------------------------------ colormap
@dataclass
class Ramp:
    """Multi-stop colour ramp for surface shading."""
    stops: list[tuple[float, str]]

    def at(self, t: float) -> tuple[int, int, int]:
        t = min(1.0, max(0.0, t))
        for i in range(len(self.stops) - 1):
            a, ca = self.stops[i]
            b, cb = self.stops[i + 1]
            if a <= t <= b:
                u = (t - a) / (b - a) if b > a else 0.0
                u = u * u * (3 - 2 * u)
                return _lerp_rgb(_rgb(ca), _rgb(cb), u)
        return _rgb(self.stops[-1][1])

    def hex(self, t: float) -> str:
        r, g, b = self.at(t)
        return f"#{r:02x}{g:02x}{b:02x}"


def _rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_rgb(a, b, u):
    return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(3))


SURFACE_RAMP = Ramp([
    (0.00, "#04121c"),
    (0.18, "#07405a"),
    (0.42, "#0a7f95"),
    (0.66, "#16b8cd"),
    (0.84, "#5ce1e6"),
    (1.00, "#c8fbfa"),
])

AMBER_RAMP = Ramp([
    (0.00, "#1a1206"),
    (0.35, "#7c3f0a"),
    (0.70, "#f59e0b"),
    (1.00, "#fde68a"),
])


def _light(normal, light_dir, ambient=0.34, diffuse=0.86):
    return ambient + diffuse * max(0.0, vdot(normal, light_dir))


# ------------------------------------------------------------------ surface
class HeightField:
    """A function z = f(x, y) sampled on a regular grid, ready to draw."""

    def __init__(self, f: Callable[[float, float], float],
                 x_range: tuple[float, float], y_range: tuple[float, float],
                 nx: int = 64, ny: int = 52, zscale: float = 1.0,
                 glow: float = 0.0):
        self.f = f
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.nx, self.ny = nx, ny
        self.zscale = zscale
        xs = np.linspace(self.x0, self.x1, nx)
        ys = np.linspace(self.y0, self.y1, ny)
        X, Y = np.meshgrid(xs, ys, indexing="xy")
        Z = f(X, Y) * zscale
        self.X, self.Y, self.Z = X, Y, Z
        self.zmin, self.zmax = float(np.min(Z)), float(np.max(Z))
        # per-vertex normals from central differences
        dzdx = np.gradient(Z, axis=1)
        dzdy = np.gradient(Z, axis=0)
        sx = (self.x1 - self.x0) / max(nx - 1, 1)
        sy = (self.y1 - self.y0) / max(ny - 1, 1)
        gx = dzdx / sx
        gy = dzdy / sy
        n = np.stack([-gx, np.ones_like(gx), -gy], axis=-1)
        self.N = n / np.linalg.norm(n, axis=-1, keepdims=True)

    def point(self, x: float, y: float):
        return (x, float(self.f(x, y)) * self.zscale, y)

    def normal(self, x: float, y: float):
        h = 1e-4
        gx = (self.f(x + h, y) - self.f(x - h, y)) / (2 * h) * self.zscale
        gy = (self.f(x, y + h) - self.f(x, y - h)) / (2 * h) * self.zscale
        return vnorm((-gx, 1.0, -gy))

    def normalised(self, z: float) -> float:
        span = max(self.zmax - self.zmin, 1e-9)
        return (z - self.zmin) / span

    # ----------------------------------------------------------------- draw
    def draw(self, cv: Canvas, cam: Camera, ramp: Ramp = SURFACE_RAMP,
             light_dir=(0.42, 0.86, 0.36), opacity: float = 1.0,
             reveal: tuple[float, float] = (0.0, 1.0), wire: bool = False,
             wire_color: str | None = None, wire_alpha: float = 0.0,
             fade_by_depth: bool = True, height_tint: float = 0.0,
             tint: str | None = None, ambient: float = 0.46,
             diffuse: float = 0.78, rim: float = 0.30, rim_color: str | None = None,
             haze: float = 0.55, contrast: float = 1.0):
        """
        Painter's-algorithm surface render.

        Shading = ambient + wrapped Lambert + Fresnel-style rim light, then an
        atmospheric haze that pulls distant quads toward the background colour.
        That combination is what gives the surface volume and depth without
        looking like a flat-shaded CAD mesh.
        """
        nx, ny = self.nx, self.ny
        ld = vnorm(light_dir)
        eye, fwd, right, up = cam.basis()
        f = cam.focal()
        P = np.stack([self.X, self.Z, self.Y], axis=-1)          # (x, height, y)
        rel = P - np.array(eye)
        zc = rel @ np.array(fwd)
        xc = rel @ np.array(right)
        yc = rel @ np.array(up)
        zc_safe = np.maximum(zc, 1e-3)
        proj = np.empty((ny, nx, 3), dtype=np.float64)
        proj[..., 0] = cam.cx + f * xc / zc_safe
        proj[..., 1] = cam.cy - f * yc / zc_safe
        proj[..., 2] = zc_safe

        i0 = np.arange(nx - 1)
        j0 = np.arange(ny - 1)
        II, JJ = np.meshgrid(i0, j0, indexing="xy")
        d = 0.25 * (zc_safe[JJ, II] + zc_safe[JJ, II + 1] + zc_safe[JJ + 1, II] + zc_safe[JJ + 1, II + 1])
        order = np.argsort(-d.ravel())
        II, JJ, d = II.ravel(), JJ.ravel(), d.ravel()

        Z = self.Z
        heights = 0.25 * (Z[JJ, II] + Z[JJ, II + 1] + Z[JJ + 1, II] + Z[JJ + 1, II + 1])
        tvals = (heights - self.zmin) / max(self.zmax - self.zmin, 1e-9)
        norms = 0.25 * (self.N[JJ, II] + self.N[JJ, II + 1] + self.N[JJ + 1, II] + self.N[JJ + 1, II + 1])
        norms = norms / np.maximum(np.linalg.norm(norms, axis=-1, keepdims=True), 1e-9)

        ndl = np.clip(norms @ np.array(ld), 0.0, 1.0)
        # view direction per quad (approx: from camera to quad centre)
        cxw = 0.25 * (self.X[JJ, II] + self.X[JJ, II + 1] + self.X[JJ + 1, II] + self.X[JJ + 1, II + 1])
        cyw = 0.25 * (self.Y[JJ, II] + self.Y[JJ, II + 1] + self.Y[JJ + 1, II] + self.Y[JJ + 1, II + 1])
        view = np.stack([cxw - eye[0], heights - eye[1], cyw - eye[2]], axis=-1)
        view = view / np.maximum(np.linalg.norm(view, axis=-1, keepdims=True), 1e-9)
        fres = np.clip(1.0 - np.abs(np.sum(norms * view, axis=-1)), 0.0, 1.0) ** 2.2

        base_light = ambient + diffuse * ndl
        rc = _rgb(rim_color) if rim_color else (150, 245, 255)
        bgc = _rgb(C.bg_top)

        ylo, yhi = reveal
        out = []
        yv_all = (cyw - self.y0) / (self.y1 - self.y0)
        visible = (yv_all >= ylo) & (yv_all <= yhi) & (d > cam.near)
        dmax = float(np.percentile(d, 92)) if d.size else 1.0
        dmin = float(np.percentile(d, 8)) if d.size else 0.0
        haze_t = np.clip((d - dmin) / max(dmax - dmin, 1e-6), 0.0, 1.0) ** 1.3

        for k in order:
            if not visible[k]:
                continue
            j, i = JJ[k], II[k]
            r, g, b = ramp.at(float(tvals[k]))
            if tint:
                tr, tg, tb = _rgb(tint)
                mk = 0.3
                r = r * (1 - mk) + tr * mk
                g = g * (1 - mk) + tg * mk
                b = b * (1 - mk) + tb * mk
            L = float(base_light[k])
            fr = float(fres[k]) * rim
            rr = r * L + rc[0] * fr
            gg = g * L + rc[1] * fr
            bb = b * L + rc[2] * fr
            if contrast != 1.0:
                rr = 255.0 * (rr / 255.0) ** contrast
                gg = 255.0 * (gg / 255.0) ** contrast
                bb = 255.0 * (bb / 255.0) ** contrast
            hz = float(haze_t[k]) * haze
            rr = rr * (1 - hz) + bgc[0] * hz
            gg = gg * (1 - hz) + bgc[1] * hz
            bb = bb * (1 - hz) + bgc[2] * hz
            sc = "#%02x%02x%02x" % (
                max(0, min(255, int(rr))), max(0, min(255, int(gg))), max(0, min(255, int(bb))))
            pts = (
                f"{proj[j, i, 0]:.1f},{proj[j, i, 1]:.1f} "
                f"{proj[j, i + 1, 0]:.1f},{proj[j, i + 1, 1]:.1f} "
                f"{proj[j + 1, i + 1, 0]:.1f},{proj[j + 1, i + 1, 1]:.1f} "
                f"{proj[j + 1, i, 0]:.1f},{proj[j + 1, i, 1]:.1f}"
            )
            # stroke each quad in its own fill colour: removes the hairline seams
            # that antialiasing leaves between adjacent polygons
            out.append(f'<polygon points="{pts}" fill="{sc}" fill-opacity="{opacity:.3f}" '
                       f'stroke="{sc}" stroke-opacity="{opacity:.3f}" stroke-width="1.2"/>')
            if wire and wire_color:
                out.append(f'<polygon points="{pts}" fill="none" stroke="{wire_color}" '
                           f'stroke-opacity="{wire_alpha*opacity:.3f}" stroke-width="0.7"/>')
        cv.raw("".join(out))
        return proj

    # ------------------------------------------------------------- wireframe
    def wire(self, cv: Canvas, cam: Camera, step: int = 3, color: str = C.cyan_soft,
             alpha: float = 0.18, sw: float = 1.0, reveal=(0.0, 1.0)):
        for j in range(0, self.ny, step):
            pts = [self.point(self.X[j, i], self.Y[j, i]) for i in range(self.nx)]
            self._seg(cv, cam, pts, color, alpha, sw, reveal)
        for i in range(0, self.nx, step):
            pts = [self.point(self.X[j, i], self.Y[j, i]) for j in range(self.ny)]
            self._seg(cv, cam, pts, color, alpha, sw, reveal)

    def _seg(self, cv, cam, pts, color, alpha, sw, reveal):
        ylo, yhi = reveal
        run = []
        for (x, y, z) in pts:
            yv = (z - self.y0) / (self.y1 - self.y0)
            if ylo <= yv <= yhi:
                run.append((x, y, z))
            else:
                if len(run) > 1:
                    segs = project_polyline(cam, run)
                    d = " ".join(f"M{a:.1f} {b:.1f}L{c:.1f} {e:.1f}" for a, b, c, e, _ in segs)
                    cv.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{alpha:.3f}" '
                           f'stroke-width="{sw}" stroke-linecap="round"/>')
                run = []
        if len(run) > 1:
            segs = project_polyline(cam, run)
            d = " ".join(f"M{a:.1f} {b:.1f}L{c:.1f} {e:.1f}" for a, b, c, e, _ in segs)
            cv.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{alpha:.3f}" '
                   f'stroke-width="{sw}" stroke-linecap="round"/>')

    # -------------------------------------------------------------- contours
    def contours(self, levels: list[float], res: int = 120):
        """Marching squares -> list per level of screen-space-ready world polylines."""
        from .contours import marching_squares
        xs = np.linspace(self.x0, self.x1, res)
        ys = np.linspace(self.y0, self.y1, res)
        Xc, Yc = np.meshgrid(xs, ys, indexing="xy")
        Zc = self.f(Xc, Yc) * self.zscale
        out = []
        for lv in levels:
            out.append((lv, marching_squares(Xc, Yc, Zc, lv)))
        return out

    def draw_contours(self, cv: Canvas, cam: Camera, contours, color: str = C.cyan_soft,
                      alpha: float = 0.35, sw: float = 1.4, lift: float = 0.004,
                      reveal: tuple[float, float] = (0.0, 1.0), dash: str | None = None):
        ylo, yhi = reveal
        parts = []
        for lv, segs in contours:
            for (xa, ya, xb, yb) in segs:
                if not (ylo <= (ya - self.y0) / (self.y1 - self.y0) <= yhi):
                    continue
                pa = (xa, float(self.f(xa, ya)) * self.zscale + lift, ya)
                pb = (xb, float(self.f(xb, yb)) * self.zscale + lift, yb)
                sa = cam.project(pa)
                sb = cam.project(pb)
                parts.append(f"M{sa[0]:.1f} {sa[1]:.1f}L{sb[0]:.1f} {sb[1]:.1f}")
        if parts:
            d = "".join(parts)
            da = f' stroke-dasharray="{dash}"' if dash else ""
            cv.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{alpha:.3f}" '
                   f'stroke-width="{sw}" stroke-linecap="round"{da}/>')

    # ---------------------------------------------------------------- floor
    def draw_floor(self, cv: Canvas, cam: Camera, z: float | None = None, step: float = 1.0,
                   color: str = C.stroke_hi, alpha: float = 0.5, sw: float = 1.0,
                   fade_radius: float | None = None, radial: bool = True):
        z = self.zmin - 0.22 if z is None else z
        parts = []
        xs = np.arange(self.x0, self.x1 + 1e-6, step)
        ys = np.arange(self.y0, self.y1 + 1e-6, step)
        for x in xs:
            segs = project_polyline(cam, [(x, z, self.y0), (x, z, self.y1)])
            parts += [f"M{a:.1f} {b:.1f}L{c:.1f} {e:.1f}" for a, b, c, e, _ in segs]
        for y in ys:
            segs = project_polyline(cam, [(self.x0, z, y), (self.x1, z, y)])
            parts += [f"M{a:.1f} {b:.1f}L{c:.1f} {e:.1f}" for a, b, c, e, _ in segs]
        cv.raw(f'<path d="{"".join(parts)}" fill="none" stroke="{color}" stroke-opacity="{alpha:.3f}" '
               f'stroke-width="{sw}"/>')

    def draw_ground_glow(self, cv: Canvas, cam: Camera, color: str = C.cyan_deep, alpha: float = 0.30,
                         radius: float | None = None, z: float | None = None):
        """
        Soft pool of light under the surface. A radial gradient (not a blurred
        blob) so the falloff is smooth, cheap, and never reads as a solid disc.
        """
        z = self.zmin - 0.2 if z is None else z
        r = radius or max(self.x1 - self.x0, self.y1 - self.y0) * 0.55
        c = cam.project((0, z, 0))
        sx = cam.scale_at((0, z, 0)) * r
        sy = sx * max(0.18, math.sin(math.radians(cam.pitch)))
        cv.ellipse(c[0], c[1], sx, sy, fill="url(#groundGlow)", opacity=alpha)


# ------------------------------------------------------------------- arrows
def draw_arrow3d(cv: Canvas, cam: Camera, p0, p1, color: str = C.amber, sw: float = 3.0,
                 head: float = 13.0, opacity: float = 1.0, cap: str = "round"):
    """Screen-space arrow between two projected 3D points (shaft + solid head)."""
    a = cam.project(p0)
    b = cam.project(p1)
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1.5:
        return
    ux, uy = dx / L, dy / L
    hx, hy = b[0] - ux * head * 0.85, b[1] - uy * head * 0.85
    px, py = -uy, ux
    hw = head * 0.44
    cv.line(a[0], a[1], hx, hy, stroke=color, sw=sw, opacity=opacity, cap=cap)
    cv.poly([(b[0], b[1]), (hx + px * hw, hy + py * hw), (hx - px * hw, hy - py * hw)],
            fill=color, opacity=opacity, close=True)


def draw_label3d(cv: Canvas, cam: Camera, p, s: str, size: float = 20, color: str = C.ink,
                 dx: float = 0, dy: float = 0, opacity: float = 1.0, anchor="start",
                 weight: int = 500, family: str = "Inter", tracking: float = 0.0):
    q = cam.project(p)
    cv.text(q[0] + dx, q[1] + dy, s, size=size, color=color, opacity=opacity,
            anchor=anchor, weight=weight, family=family, tracking=tracking)
    return q


def screen_polyline(cv: Canvas, cam: Camera, pts, color=C.cyan, sw=3.0, opacity=1.0,
                    dash=None, glow: bool = False):
    segs = project_polyline(cam, pts)
    if not segs:
        return
    d = "".join(f"M{a:.1f} {b:.1f}L{c:.1f} {e:.1f}" for a, b, c, e, _ in segs)
    da = f' stroke-dasharray="{dash}"' if dash else ""
    if glow:
        cv.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{0.35*opacity:.3f}" '
               f'stroke-width="{sw*4.5:.1f}" filter="url(#glowSmall)" stroke-linecap="round"{da}/>')
    cv.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{opacity:.3f}" '
           f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"{da}/>')


def screen_dots(cv: Canvas, cam: Camera, pts, r: float = 3.0, color=C.cyan, opacity=1.0):
    for p in pts:
        if not cam.visible(p):
            continue
        x, y, z = cam.project(p)
        rr = r * (cam.focal() / z) / (cam.focal() / cam.dist)
        cv.circle(x, y, max(0.8, rr), fill=color, opacity=opacity)
