"""
Scene 1 — Gradient descent on a real loss surface.

Shot list (one continuous camera move, 13 s):

  0.0 – 2.0   the surface sweeps in from the far edge; camera high and wide
  1.6 – 3.6   camera pushes in and drops toward the basin; contours bloom
  3.3 – 4.6   four probe particles appear on the rim, gradient arrows form
  4.6 – 9.6   probes slide down the *true* gradient path, arrows rotate downhill
  9.4 – 11.2  convergence: rings pulse, the update rule resolves
 11.0 – 13.0  holding shot, camera settles into a slow orbit

Mathematical content: L(w) = ½w₁ᵀAw + ripple, ∇L is analytic, the trajectory is
the real iterate sequence w←w−η∇L(w), and the HUD shows the live loss value.
"""
from __future__ import annotations

import math

import numpy as np

from engine import mathtex
from engine.animate import ease, lerp, remap, window
from engine.layout import (CAPTION_BASELINE, HEADER_Y, STAGE_BOTTOM, STAGE_TOP,
                           chip, panel, section_label)
from engine.linalg import Camera, fit_camera_screen, vnorm
from engine.opt import anisotropic_bowl, gradient_descent
from ._retime import Retimed
from engine.scene import Beat, Cue, Scene
from engine.surface3d import (HeightField, draw_arrow3d, screen_polyline)
from engine.theme import C, HEIGHT, WIDTH, rgba

ZSCALE = 0.30
LN = "L(w)"


class GradientDescent(Retimed, Scene):
    name = "s1_gradient_descent"
    title = "Gradient descent"
    subtitle = "A model learns by following the negative gradient"
    chapter = 1
    chapter_total = 4
    duration = 13.0

    beats = {
        "surface": Beat("surface", 0.2, 2.1, "surface in"),
        "push_in": Beat("push_in", 1.5, 4.2, "camera push"),
        "probes": Beat("probes", 3.2, 4.5, "probes appear"),
        "arrows": Beat("arrows", 4.1, 5.5, "gradient arrows"),
        "descend": Beat("descend", 4.8, 9.5, "descent"),
        "converge": Beat("converge", 9.3, 11.1, "converged"),
        "resolve": Beat("resolve", 10.4, 12.8, "equation"),
    }

    cues = [
        Cue(3.4, 7.3, "A model learns by sliding downhill — along the steepest way down."),
        Cue(7.5, 12.2, "Its position is a set of weights. The slope it feels is the gradient."),
    ]

    STARTS = [(2.25, 1.55), (1.55, 1.72), (2.40, 0.55), (1.02, 1.18)]
    STEPS = 46
    LR = 0.072
    RULE_TEX = r"w_{t+1} = w_t - \eta\,\nabla L(w_t)"

    def __init__(self):
        super().__init__()
        self.loss = anisotropic_bowl()
        self.field = HeightField(self.loss.f, (-2.7, 2.7), (-2.05, 2.05),
                                 nx=74, ny=60, zscale=ZSCALE)
        self.paths = [gradient_descent(self.loss, x0, y0, lr=self.LR, steps=self.STEPS)
                      for (x0, y0) in self.STARTS]
        self.contours = self.field.contours(
            [self.loss.f(0, 0) + d for d in (0.24, 0.72, 1.42, 2.4, 3.7, 5.2)], res=104)
        self.min_pt = (0.0, self.loss.f(0.0, 0.0) * ZSCALE, 0.0)
        self.cam_pts = [self.field.point(x, y) for x in np.linspace(-2.7, 2.7, 9)
                        for y in np.linspace(-2.05, 2.05, 9)]
        self.fit = self._fit_reference()
        mathtex.prebuild([self.RULE_TEX])
        self.apply_timing()

    # ------------------------------------------------------------------ camera
    #: the stage rectangle the surface may occupy (keeps clear of title, panel,
    #: caption and HUD)
    STAGE_BOX = (96.0, 150.0, 1824.0, 790.0)

    def _fit_reference(self) -> Camera:
        """Fit the framing once, at the hero pitch; camera moves then scale from
        this. Auto-fitting every frame would silently cancel a push-in."""
        ref = Camera(yaw=-30.0, pitch=26.0, dist=8.0, target=(0.0, 0.9, 0.0), fov_deg=30)
        # the surface is allowed to run past the safe area: a full-bleed
        # bowl reads far better than a small object adrift in the frame
        return fit_camera_screen(ref, self.cam_pts, self.STAGE_BOX, margin=1.06)

    def camera(self, t: float) -> Camera:
        p1 = remap(t, 1.4, 4.6, "in_out_sine")      # establishing -> low & close
        p2 = remap(t, 4.6, 13.0, "in_out_sine")     # slow orbital settle
        yaw = lerp(-59.0, -31.0, p1) + lerp(0.0, 26.0, p2)
        pitch = lerp(46.0, 26.5, p1) + lerp(0.0, 3.5, p2)
        # a real dolly: start well outside the fitted framing, end just inside it
        zoom = lerp(1.42, 1.0, p1) * lerp(1.0, 0.90, p2)
        f = self.fit
        return Camera(yaw=yaw, pitch=pitch, dist=f.dist * zoom, target=f.target,
                      fov_deg=30, cx=f.cx, cy=f.cy, roll=lerp(1.2, -1.0, p1))

    # ------------------------------------------------------------------ helpers
    def opt_pos(self, path, s: float):
        x, y = path.points(s)
        return (float(x), float(self.loss.f(x, y)) * ZSCALE, float(y))

    def probe_colour(self, i):
        return [C.amber, C.rose, C.lime, C.cyan_soft][i % 4]

    # ------------------------------------------------------------------ render
    # ------------------------------------------------------------- retime
    def tw(self, t_authored: float) -> float:
        """Authored second -> narration-timed real second."""
        return self.T(t_authored)

    def render(self, cv, t: float):
        T = self.T(t)            # narration-timed clock
        cam = self.camera(t)
        f = self.field

        # ---------------------------------------------------------- ground
        g = remap(T, self.tw(0.2), self.tw(2.4), "in_out_sine")
        f.draw_ground_glow(cv, cam, alpha=0.55 * g, radius=3.4)
        f.draw_floor(cv, cam, step=0.6, color=C.stroke_hi, alpha=0.13 * g, sw=1.0)

        # ---------------------------------------------------------- surface
        reveal = (0.0, remap(T, self.tw(0.45), self.tw(2.35), "in_out_cubic"))
        if reveal[1] > 0.001:
            f.draw(cv, cam, reveal=reveal, rim=0.36, haze=0.52, contrast=0.96)

        # ---------------------------------------------------------- contours
        ca = remap(T, self.tw(1.55), self.tw(3.5), "in_out_sine") * 0.32
        if ca > 0.01:
            f.draw_contours(cv, cam, self.contours, color="#d7fbff", alpha=ca,
                            sw=1.15, lift=0.01)

        # ---------------------------------------------------------- probes
        probe_a = remap(T, self.tw(3.15), self.tw(4.35), "out_cubic")
        arrow_a = remap(T, self.tw(4.05), self.tw(5.4), "out_cubic")
        des = remap(T, self.tw(4.75), self.tw(9.45), "in_out_sine")
        for idx, path in enumerate(self.paths):
            self.draw_probe(cv, cam, idx, path, probe_a, arrow_a, des, t)

        # ---------------------------------------------------------- optimum
        ring = window(t, 9.5, 13.2) if t > 9.4 else 0.0
        if ring > 0.01:
            self.draw_optimum(cv, cam, ring, t)

        # ---------------------------------------------------------- text layers
        self.draw_title_card(cv, T)
        self.draw_header(cv, t)
        self.draw_axis_labels(cv, cam, remap(T, self.tw(2.0), self.tw(3.3), "out_quad"))
        self.draw_readout(cv, t)
        self.draw_equation(cv, t)

    # ---------------------------------------------------------------- pieces
    def draw_title_card(self, cv, t):
        """
        The film's opening: title resolves over the empty canvas while the
        surface sweeps in underneath, then clears before the first narration
        beat so nothing competes with the words.
        """
        a = remap(t, 0.15, 0.9, "out_quad") * (1.0 - remap(t, 2.95, 3.7, "in_out_sine"))
        if a <= 0.01:
            return
        # left-aligned editorial title block over the empty canvas
        x = 132
        y = 430
        cv.text(x, y, "MATHEMATICS", size=13, color=C.cyan, weight=600,
                tracking=0.36, opacity=0.9 * a)
        # hairline rule that draws out from the kicker
        rp = remap(t, 0.35, 1.3, "in_out_cubic")
        cv.line(x, y + 26, x + 118 * rp, y + 26, stroke=C.cyan, sw=1.6, opacity=0.55 * a)
        cv.text(x, y + 104, "Mathematics behind AI", size=76, color=C.ink, weight=600,
                family="Fraunces", tracking=-0.01, opacity=a)
        cv.text(x, y + 156, "four ideas, animated from first principles", size=25,
                color=C.ink_soft, weight=400, opacity=0.86 * a)
        # chapter list, staggered
        items = [("01", "Gradient descent", C.cyan),
                 ("02", "A neural network", C.violet),
                 ("03", "One neuron", C.amber),
                 ("04", "The mathematics", C.teal)]
        for i, (num, label, col) in enumerate(items):
            ia = remap(t, 1.15 + i * 0.13, 1.85 + i * 0.13, "out_quad") * a
            if ia <= 0.01:
                continue
            yy = y + 232 + i * 32
            cv.text(x, yy, num, size=13, color=col, weight=600, family="JetBrains Mono",
                    opacity=0.9 * ia)
            cv.text(x + 38, yy, label, size=17, color=C.ink_soft, weight=500,
                    opacity=0.9 * ia)

    def draw_header(self, cv, t):
        """Scene title, top-left under the brand mark; fades as the shot opens."""
        a = remap(self.T(t), self.tw(0.9), self.tw(1.9), "out_quad") * (1.0 - remap(self.T(t), self.tw(4.6), self.tw(5.6), "in_out_sine"))
        if a <= 0.01:
            return
        y = HEADER_Y + 54
        cv.raw(f'<rect x="96" y="{y - 30}" width="{2.6}" height="{34}" fill="{C.cyan}" opacity="{0.9*a:.3f}"/>')
        cv.text(114, y, "GRADIENT DESCENT", size=30, color=C.ink, weight=600,
                tracking=0.04, opacity=a)
        cv.text(114, y + 26, "L(w)  surface  ·  steepest-descent path", size=15,
                color=C.ink_mute, weight=400, tracking=0.06, opacity=0.9 * a)

    def draw_axis_labels(self, cv, cam, a):
        """
        Axis labels are anchored in *screen* space to the projected near corner
        of the ground plane, then clamped into the stage band — so they never
        drift into the caption or the readout panel as the camera orbits.
        """
        if a <= 0.01:
            return
        f = self.field
        zf = f.zmin - 0.20
        # near-left corner -> w2, near-right corner -> w1
        cand = {
            "w<sub>2</sub>": (-2.70, zf, 2.06),
            "w<sub>1</sub>": (2.70, zf, 2.06),
        }
        for s_, p in cand.items():
            if not cam.visible(p):
                continue
            q = cam.project(p)
            lx = min(max(q[0], 150.0), 1770.0)
            ly = min(max(q[1] + 26, 300.0), 756.0)
            anc = "end" if s_.startswith("w<sub>2") else "start"
            dx = -16 if anc == "end" else 16
            cv.text(lx + dx, ly, s_, size=25, color=C.ink_soft, opacity=0.88 * a,
                    weight=500, anchor=anc)
        # the vertical loss axis: short baseline + label at its foot
        p0 = (-1.62, f.zmin - 0.24, -2.05)
        p1 = (-1.62, f.zmin + 1.15, -2.05)
        if cam.visible(p0) and cam.visible(p1):
            q0, q1 = cam.project(p0), cam.project(p1)
            if 150 < q0[1] < 760:
                cv.line(q0[0], q0[1], q1[0], q1[1], stroke=C.ink_faint, sw=1.3,
                        opacity=0.5 * a)
                cv.text(q1[0] + 12, q1[1] + 10, "L", size=26, color=C.ink_soft,
                        opacity=0.92 * a, weight=500, family="Fraunces")

    def draw_probe(self, cv, cam, idx, path, probe_a, arrow_a, des, t):
        if probe_a <= 0.01:
            return
        col = self.probe_colour(idx)
        n = len(path) - 1
        # staggered start so the four probes don't move as one rigid unit
        s_pos = min(max(0.0, des * (n + 1.1) - idx * 0.26), n)
        s0 = max(0.0, s_pos - (9.5 if idx % 2 == 0 else 7.0))

        samples = np.linspace(s0, s_pos, max(int((s_pos - s0) * 7) + 2, 2))
        pts = [self.opt_pos(path, s) for s in samples]
        if len(pts) > 1 and s_pos > 0.03:
            screen_polyline(cv, cam, pts, color=col, sw=2.5, opacity=0.92 * probe_a, glow=True)
        fut = np.linspace(s_pos, n, 48)
        fpts = [self.opt_pos(path, s) for s in fut]
        if len(fpts) > 1:
            screen_polyline(cv, cam, fpts, color=col, sw=1.0, opacity=0.12 * probe_a, dash="2 8")
        # discrete iterates: this is a *step* rule, so show the steps
        for k in range(int(math.ceil(s0)), int(s_pos) + 1):
            q = cam.project(self.opt_pos(path, k))
            if cam.visible(self.opt_pos(path, k)):
                cv.circle(q[0], q[1], 2.15, fill=col, opacity=0.55 * probe_a)

        x, y = path.points(s_pos)
        p = (float(x), float(self.loss.f(x, y)) * ZSCALE, float(y))
        if not cam.visible(p):
            return
        q = cam.project(p)
        r = 8.2 * (cam.scale_at(p) / (cam.focal() / 13.4))
        cv.circle(q[0], q[1], r * 4.0, fill=col, opacity=0.15 * probe_a, extra='filter="url(#glowSmall)"')
        cv.circle(q[0], q[1], r * 1.9, fill=col, opacity=0.30 * probe_a)
        cv.circle(q[0], q[1], r, fill="#ffffff", opacity=0.97 * probe_a)
        cv.circle(q[0] - r * 0.28, q[1] - r * 0.3, r * 0.40, fill=col, opacity=0.5 * probe_a)

        # -∇L arrow, length ∝ ‖∇L‖, rotating as the probe slides
        fa = arrow_a * (1.0 - remap(self.T(t), self.tw(9.3), self.tw(10.2), "in_out_sine"))
        gx, gy = self.loss.grad(x, y)
        gn = math.hypot(gx, gy)
        if fa > 0.01 and gn > 1e-5:
            L = 0.48 + 0.6 * min(1.0, gn / 2.4)
            pul = 1.0 + 0.04 * math.sin(t * 5.0 + idx * 1.3)
            tip = (p[0] - gx / gn * L, p[1] + 0.14, p[2] - gy / gn * L)
            draw_arrow3d(cv, cam, (p[0], p[1] + 0.015, p[2]), tip,
                         color=C.rose, sw=3.4 * pul, head=16.0 * pul, opacity=0.92 * fa)

    def draw_optimum(self, cv, cam, ring, t):
        p = self.min_pt
        if not cam.visible(p):
            return
        q = cam.project(p)
        base = 13.0 * (cam.scale_at(p) / (cam.focal() / 13.4))
        for k in range(3):
            ph = (t * 0.5 + k / 3.0) % 1.0
            cv.circle(q[0], q[1], base * (1.0 + 2.4 * ph), fill="none",
                      stroke=C.cyan_soft, sw=1.5, opacity=ring * 0.42 * (1.0 - ph) ** 1.6)
        cv.circle(q[0], q[1], base * 2.4, fill=C.cyan, opacity=0.13 * ring,
                  extra='filter="url(#glowSmall)"')
        cv.circle(q[0], q[1], 4.6, fill=C.ink, opacity=0.95 * ring, stroke=C.cyan, sw=2.0)

    def draw_readout(self, cv, t):
        """Live iterate readout, top-left of the stage."""
        a = remap(self.T(t), self.tw(5.6), self.tw(6.8), "out_quad")
        if a <= 0.01:
            return
        des = remap(self.T(t), self.tw(4.75), self.tw(9.45), "in_out_sine")
        path = self.paths[0]
        s = min(des * (len(path) - 1), len(path) - 1)
        x, y = path.points(s)
        gx, gy = self.loss.grad(x, y)
        loss = self.loss.f(x, y)
        gn = math.hypot(gx, gy)

        bx, by, w, h = 96, STAGE_TOP + 54, 356, 120
        panel(cv, bx, by, w, h, alpha=a, accent=C.cyan, fill="rgba(7,14,23,0.86)")
        section_label(cv, bx + 22, by + 30, "ITERATE", alpha=a)
        cv.text(bx + 22, by + 62, f"w = ({x:+.3f}, {y:+.3f})", size=18,
                color=C.ink, weight=500, family="JetBrains Mono", opacity=a)
        cv.text(bx + 22, by + 90, f"L(w) = {loss:.4f}", size=18, color=C.teal,
                weight=500, family="JetBrains Mono", opacity=a)
        # ‖∇L‖ meter
        frac = min(1.0, gn / 3.0)
        cv.text(bx + 226, by + 30, "‖∇L‖", size=15, color=C.ink_mute, weight=500,
                family="JetBrains Mono", opacity=a)
        cv.rect(bx + 226, by + 44, 104, 5, fill=rgba(C.ink_faint, 0.32), rx=2.5, opacity=a)
        cv.rect(bx + 226, by + 44, 104 * frac, 5, fill=C.rose, rx=2.5, opacity=a)
        cv.text(bx + 226, by + 76, f"{gn:5.3f}", size=15, color=C.rose, weight=500,
                family="JetBrains Mono", opacity=0.9 * a)

    def draw_equation(self, cv, t):
        """
        The update rule, bottom-right, with the three terms lighting up in turn as
        the probes converge (position — step size — gradient).
        """
        a = remap(self.T(t), self.tw(10.3), self.tw(11.4), "out_quad")
        if a <= 0.01:
            return
        E = mathtex.tex(self.RULE_TEX)
        size = 30
        wpx = E.width * size
        bx = 96
        by = 700
        panel(cv, bx, by, wpx + 64, 92, alpha=a * 0.95, accent=C.violet, accent_side="top")
        cv.text(bx + 32, by + 30, "UPDATE RULE", size=12, color=C.ink_mute, weight=600,
                tracking=0.2, opacity=a)
        cv.raw(E.svg(bx + 32, by + 68, size, C.ink, opacity=a))
        # term highlights (pulse through the equation)
        import re
        keys = ["msub", "mo"] if False else None
