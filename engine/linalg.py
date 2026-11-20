"""
Tiny, dependency-free linear algebra + a real pinhole camera.

The 3D scenes in this film do not use a fixed isometric projection: they use a
perspective camera with position, orbit angles, focal length and a look-at
target, so camera *movement* is a first-class, differentiable animation channel
(pan / dolly / orbit / roll), exactly like a real motion-graphics rig.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------- vectors
def vadd(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vmul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vlen(a: Vec3) -> float:
    return math.sqrt(vdot(a, a))


def vnorm(a: Vec3) -> Vec3:
    n = vlen(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def vlerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


# --------------------------------------------------------------- camera
@dataclass
class Camera:
    """Perspective pinhole camera looking at `target` from spherical coords."""
    yaw: float = -38.0          # degrees, rotation around world Y
    pitch: float = 24.0         # degrees, elevation
    dist: float = 9.0           # distance from target
    target: Vec3 = (0.0, 0.0, 0.0)
    fov_deg: float = 34.0
    roll: float = 0.0           # degrees
    # screen-space offset of the projection centre (px)
    cx: float = 960.0
    cy: float = 560.0
    near: float = 0.08

    # ---- derived -------------------------------------------------------
    def position(self) -> Vec3:
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return (
            self.target[0] + self.dist * math.cos(p) * math.sin(y),
            self.target[1] + self.dist * math.sin(p),
            self.target[2] + self.dist * math.cos(p) * math.cos(y),
        )

    def focal(self) -> float:
        return (HEIGHT_HALF / math.tan(math.radians(self.fov_deg) / 2.0))

    def basis(self):
        eye = self.position()
        fwd = vnorm(vsub(self.target, eye))
        world_up = (0.0, 1.0, 0.0)
        if abs(vdot(fwd, world_up)) > 0.999:
            world_up = (0.0, 0.0, 1.0)
        right = vnorm(vcross(fwd, world_up))
        up = vcross(right, fwd)
        if abs(self.roll) > 1e-9:
            a = math.radians(self.roll)
            ca, sa = math.cos(a), math.sin(a)
            right, up = (
                vadd(vmul(right, ca), vmul(up, sa)),
                vadd(vmul(up, ca), vmul(right, -sa)),
            )
        return eye, fwd, right, up

    def project(self, p: Vec3) -> tuple[float, float, float]:
        """World -> (screen x, screen y, view-space depth)."""
        eye, fwd, right, up = self.basis()
        rel = vsub(p, eye)
        x = vdot(rel, right)
        y = vdot(rel, up)
        z = vdot(rel, fwd)
        z = max(z, 1e-4)
        f = self.focal()
        return (self.cx + f * x / z, self.cy - f * y / z, z)

    def depth(self, p: Vec3) -> float:
        eye, fwd, _, _ = self.basis()
        return vdot(vsub(p, eye), fwd)

    def visible(self, p: Vec3) -> bool:
        return self.depth(p) > self.near

    def scale_at(self, p: Vec3) -> float:
        """Pixels per world unit at p (for sizing sprites consistently)."""
        return self.focal() / max(self.depth(p), 1e-4)

    def lerp(self, other: "Camera", t: float) -> "Camera":
        return Camera(
            yaw=self.yaw + (other.yaw - self.yaw) * t,
            pitch=self.pitch + (other.pitch - self.pitch) * t,
            dist=self.dist + (other.dist - self.dist) * t,
            target=vlerp(self.target, other.target, t),
            fov_deg=self.fov_deg + (other.fov_deg - self.fov_deg) * t,
            roll=self.roll + (other.roll - self.roll) * t,
            cx=self.cx + (other.cx - self.cx) * t,
            cy=self.cy + (other.cy - self.cy) * t,
        )


HEIGHT_HALF = 540.0


# ------------------------------------------------------------- projection
def project_polyline(cam: Camera, pts: Iterable[Vec3], clip_near: bool = True):
    """
    Project a world polyline into *screen segments*, clipping against the near
    plane so geometry behind the camera never explodes across the screen.
    Returns [(x0,y0,x1,y1,depth), ...] plus per-vertex depths for sorting.
    """
    eye, fwd, right, up = cam.basis()
    f = cam.focal()
    zs, ss = [], []
    for p in pts:
        rel = vsub(p, eye)
        z = vdot(rel, fwd)
        zs.append(z)
        if z > cam.near:
            ss.append((cam.cx + f * vdot(rel, right) / z, cam.cy - f * vdot(rel, up) / z))
        else:
            ss.append(None)

    segs = []
    for i in range(len(zs) - 1):
        z0, z1 = zs[i], zs[i + 1]
        p0, p1 = pts[i], pts[i + 1]
        s0, s1 = ss[i], ss[i + 1]
        if z0 <= cam.near and z1 <= cam.near:
            continue
        if z0 <= cam.near or z1 <= cam.near:
            # clip to near plane
            t = (cam.near - z0) / (z1 - z0)
            pc = vlerp(p0, p1, t)
            rel = vsub(pc, eye)
            zc = vdot(rel, fwd)
            sc = (cam.cx + f * vdot(rel, right) / zc, cam.cy - f * vdot(rel, up) / zc)
            if z0 <= cam.near:
                s0, z0 = sc, zc
            else:
                s1, z1 = sc, zc
        segs.append((s0[0], s0[1], s1[0], s1[1], (z0 + z1) * 0.5))
    return segs


def fit_camera(
    cam: Camera,
    points,
    margin: float = 0.86,
    iters: int = 40,
) -> Camera:
    """
    Auto-framing: walk the camera's distance so every point lands inside the
    title-safe area.  This is what keeps generated scenes free of clipping
    without hand-tuning `dist` for every shot.
    """
    import math as _m
    pts = [tuple(p) for p in points]
    if not pts:
        return cam
    half_w = cam.cx if cam.cx < 1920 - cam.cx else 1920 - cam.cx
    half_h = min(cam.cy, 1080 - cam.cy)
    lo, hi = 0.6, 60.0
    for _ in range(iters):
        cam.dist = (lo + hi) * 0.5
        ok = True
        for p in pts:
            x, y, z = cam.project(p)
            if abs(x - cam.cx) > half_w * margin or abs(y - cam.cy) > half_h * margin:
                ok = False
                break
        if ok:
            hi = cam.dist
        else:
            lo = cam.dist
    cam.dist = hi
    return cam


def fit_camera_box(cam: Camera, points, box, margin: float = 0.94) -> Camera:
    """
    Frame `points` inside a screen-space rectangle `box = (x0, y0, x1, y1)`.
    Distance is searched so the projected cloud fits the box, then the camera
    centre is nudged to the box centre.  This is how every shot in the film is
    kept clear of the captions, titles and HUD without hand-tuned magic numbers.
    """
    x0, y0, x1, y1 = box
    cam.cx = (x0 + x1) / 2.0
    cam.cy = (y0 + y1) / 2.0
    hw, hh = (x1 - x0) / 2.0 * margin, (y1 - y0) / 2.0 * margin
    lo, hi = 0.7, 90.0
    for _ in range(48):
        cam.dist = (lo + hi) * 0.5
        ok = True
        for p in points:
            if cam.depth(p) <= cam.near:
                ok = False
                break
            sx, sy, _ = cam.project(p)
            if abs(sx - cam.cx) > hw or abs(sy - cam.cy) > hh:
                ok = False
                break
        if ok:
            hi = cam.dist
        else:
            lo = cam.dist
    cam.dist = hi
    return cam


def fit_target_only(cam: Camera, points, box, margin: float = 0.94, shift_iters: int = 6):
    """
    Fit, then re-centre the look-at target on the projected bounds and fit again
    (a couple of passes), which centres off-axis clouds properly.
    """
    for _ in range(shift_iters):
        fit_camera_box(cam, points, box, margin)
        xs, ys = [], []
        for p in points:
            sx, sy, _ = cam.project(p)
            xs.append(sx); ys.append(sy)
        if not xs:
            break
        dx = ((min(xs) + max(xs)) / 2) - cam.cx
        dy = ((min(ys) + max(ys)) / 2) - cam.cy
        if abs(dx) < 2 and abs(dy) < 2:
            break
        # convert the screen offset into a world-space pan along right/up
        eye, fwd, right, up = cam.basis()
        f = cam.focal()
        k = cam.dist / f
        cam.target = (
            cam.target[0] - right[0] * dx * k + up[0] * dy * k,
            cam.target[1] - right[1] * dx * k + up[1] * dy * k,
            cam.target[2] - right[2] * dx * k + up[2] * dy * k,
        )
    return cam


def fit_camera_screen(cam: Camera, points, box, margin: float = 0.96, iters: int = 7) -> Camera:
    """
    Stable auto-framing.

    Two coupled unknowns: how far back the camera stands (dist) and where the
    projection centre sits (cx, cy).  Each pass bisects `dist` for containment
    in the box, then shifts (cx, cy) by the residual offset of the projected
    bounding box — which moves the image exactly, because (cx, cy) *is* the
    projection centre.  Converges in a handful of passes and never disturbs the
    orbit geometry (unlike panning the look-at target).
    """
    x0, y0, x1, y1 = box
    bx_c, by_c = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hw = (x1 - x0) / 2.0 * margin
    hh = (y1 - y0) / 2.0 * margin
    pts = list(points)
    for _ in range(iters):
        cam.cx, cam.cy = bx_c, by_c
        lo, hi = 0.6, 120.0
        for _ in range(40):
            cam.dist = (lo + hi) * 0.5
            ok = True
            for p in pts:
                if cam.depth(p) <= cam.near:
                    ok = False
                    break
                sx, sy, _ = cam.project(p)
                if abs(sx - cam.cx) > hw or abs(sy - cam.cy) > hh:
                    ok = False
                    break
            if ok:
                hi = cam.dist
            else:
                lo = cam.dist
        cam.dist = hi
        xs, ys = [], []
        for p in pts:
            sx, sy, _ = cam.project(p)
            xs.append(sx); ys.append(sy)
        dx = bx_c - (min(xs) + max(xs)) / 2.0
        dy = by_c - (min(ys) + max(ys)) / 2.0
        if abs(dx) < 1.0 and abs(dy) < 1.0:
            break
        # shift the projection centre only partly per pass (damped) so the
        # dist search and the offset settle together
        cam.cx += dx * 0.9
        cam.cy += dy * 0.9
    return cam
