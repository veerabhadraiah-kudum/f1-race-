"""
Scene 3 — One neuron, by the numbers.

Every number on screen is the real arithmetic:

    x = (0.20, 0.50, 0.43)      w = (0.40, 0.26, 0.30)      b = 0.10
    z = Σᵢ wᵢxᵢ + b = 0.08 + 0.13 + 0.129 + 0.10 = 0.439
    a = σ(z) = 1 / (1 + e^{-0.439}) = 0.6080

Shot list:
  0.0 – 2.2   three inputs resolve on the left, weights label the links
  2.2 – 5.2   the three products count up, one at a time, each with its own
              animated multiplication and a bar in the sum register
  5.2 – 7.0   bias is added; the running sum in the register settles on z
  7.0 – 9.2   z travels into the sigmoid; the curve traces to the operating point
  9.2 – 11.4  the output value resolves, the register locks
 11.4 – 13.2  the formula assembles from the labelled parts
"""
from __future__ import annotations

import math

import numpy as np

from engine import mathtex
from engine.animate import ease, ease_out_back, lerp, remap, window
from engine.layout import HEADER_Y, panel, section_label
from ._retime import Retimed
from engine.scene import Beat, Cue, Scene
from engine.theme import C, HEIGHT, WIDTH, rgba

# ---- the actual numbers -------------------------------------------------
X = (0.20, 0.50, 0.43)
W = (0.40, 0.26, 0.30)
B = 0.10
PROD = tuple(x * w for x, w in zip(X, W))          # (0.080, 0.130, 0.129)
Z = sum(PROD) + B                                   # 0.439
A = 1.0 / (1.0 + math.exp(-Z))                      # 0.6080
A_I = A
dash_units = sum(PROD)                           # 0.339

# ---- geometry -----------------------------------------------------------
IN_X, IN_Y0, IN_GAP = 300.0, 396.0, 138.0
MULT_X = 520.0
REG_X, REG_Y, REG_W, REG_H = 786.0, 296.0, 300.0, 296.0
SUM_Y = 440.0
SIG = (1166.0, 268.0, 386.0, 372.0)      # x, y, w, h of the sigmoid panel
OUT_X = 1706.0


class SingleNeuron(Retimed, Scene):
    name = "s3_neuron"
    title = "One neuron"
    subtitle = "Each number in the chain, one step at a time"
    chapter = 3
    chapter_total = 4
    duration = 13.4

    beats = {
        "inputs": Beat("inputs", 0.3, 2.2, "inputs"),
        "products": Beat("products", 2.2, 5.3, "multiplications"),
        "bias": Beat("bias", 5.3, 6.9, "bias added"),
        "sigma": Beat("sigma", 7.0, 9.4, "activation"),
        "out": Beat("out", 9.2, 11.3, "output"),
        "formula": Beat("formula", 11.2, 13.2, "formula"),
    }

    cues = [
        Cue(1.0, 5.0, "A neuron multiplies each input by its weight, then adds them up."),
        Cue(5.2, 9.2, "Add a bias, and the result z becomes the input to an activation."),
        Cue(9.4, 13.2, "The sigmoid squeezes any number into a probability between zero and one."),
    ]

    FORMULA = r"a = \sigma\Big(\sum_{i} w_i x_i + b\Big)"
    SIGMOID = r"\sigma(z) = \frac{1}{1 + e^{-z}}"

    def __init__(self):
        super().__init__()
        mathtex.prebuild([self.FORMULA, self.SIGMOID])
        self.apply_timing()

    # ------------------------------------------------------------- timeline
    def product_p(self, i, t):
        """Per-product progress: the three multiplications are staggered."""
        a = 2.35 + i * 0.72
        return remap(t, a, a + 0.78, "in_out_cubic")

    def bias_p(self, t):
        return remap(t, 5.35, 6.35, "in_out_cubic")

    def z_p(self, t):
        return remap(t, 6.15, 7.0, "in_out_cubic")

    def sig_p(self, t):
        return remap(t, 7.1, 9.0, "in_out_cubic")

    def out_p(self, t):
        return remap(t, 9.1, 10.3, "in_out_cubic")

    # --------------------------------------------------------------- render
    # ------------------------------------------------------------- retime
    def tw(self, t_authored: float) -> float:
        """Authored second -> narration-timed real second."""
        return self.T(t_authored)

    def render(self, cv, t):
        T = self.T(t)            # narration-timed clock
        self.draw_title_card(cv, T)
        self.draw_header(cv, t)
        self.draw_links(cv, t)
        self.draw_inputs(cv, t)
        self.draw_register(cv, t)
        self.draw_bias(cv, t)
        self.draw_sigmoid(cv, t)
        self.draw_output(cv, t)
        self.draw_formula(cv, t)

    # ---------------------------------------------------------------- header
    def draw_title_card(self, cv, t):
        """Chapter card: resolves in the open canvas during the narration lead-in."""
        a = remap(t, 0.15, 0.9, "out_quad") * (1.0 - remap(t, 1.95, 2.6, "in_out_sine"))
        if a <= 0.01:
            return
        x, y = 132, 452
        cv.text(x, y, 'ONE NEURON', size=13, color=C.cyan, weight=600,
                tracking=0.36, opacity=0.9 * a)
        rp = remap(t, 0.35, 1.25, "in_out_cubic")
        cv.line(x, y + 26, x + 118 * rp, y + 26, stroke=C.cyan, sw=1.6, opacity=0.55 * a)
        cv.text(x, y + 104, 'One neuron', size=76, color=C.ink, weight=600,
                family="Fraunces", tracking=-0.01, opacity=a)
        cv.text(x, y + 156, 'the arithmetic of a single unit', size=25, color=C.ink_soft, weight=400,
                opacity=0.86 * a)

    def draw_header(self, cv, t):
        a = remap(self.T(t), self.tw(0.4), self.tw(1.4), "out_quad") * (1.0 - remap(self.T(t), self.tw(11.0), self.tw(11.9), "in_out_sine"))
        if a <= 0.01:
            return
        y = HEADER_Y + 46
        cv.raw(f'<rect x="96" y="{y-28}" width="2.6" height="32" fill="{C.amber}" opacity="{0.9*a:.3f}"/>')
        cv.text(114, y, "ONE NEURON", size=28, color=C.ink, weight=600, tracking=0.04, opacity=a)
        cv.text(114, y + 24, "x → w·x → Σ + b → σ → a", size=14, color=C.ink_mute,
                weight=400, tracking=0.10, opacity=0.9 * a)

    # ---------------------------------------------------------------- inputs
    def input_p(self, i, t):
        a = 0.45 + i * 0.22
        return max(0.0, remap(t, a, a + 0.65, "out_back"))

    def draw_inputs(self, cv, t):
        for i in range(3):
            p = self.input_p(i, t)
            if p <= 0.01:
                continue
            y = IN_Y0 + i * IN_GAP
            # pill
            pw, ph = 156, 72
            cv.rect(IN_X - pw / 2, y - ph / 2, pw * min(1.0, p), ph, rx=ph / 2,
                    fill=rgba(C.violet_deep, 0.30), stroke=rgba(C.violet, 0.75),
                    sw=1.3, opacity=min(1.0, p))
            if p > 0.6:
                o = (p - 0.6) / 0.4
                cv.text(IN_X, y + 10, f"{X[i]:.2f}", size=29, color=C.violet_soft,
                        weight=500, family="JetBrains Mono", anchor="middle",
                        opacity=o)
                cv.text(IN_X, y - 40, f"x<sub>{i+1}</sub>", size=16, color=C.ink_mute,
                        weight=500, anchor="middle", opacity=0.85 * o)
                pass

    def product_row_y(self, i):
        return REG_Y + 78 + i * 50

    def draw_links(self, cv, t):
        """Each input links to its own row in the sum register; the multiplication
        is labelled on the wire and the products land in the register."""
        vis = remap(self.T(t), self.tw(1.2), self.tw(2.0), "out_quad")
        if vis <= 0.01:
            return
        for i in range(3):
            y = IN_Y0 + i * IN_GAP
            x0 = IN_X + 82
            x1 = REG_X - 8
            y1 = self.product_row_y(i) - 6
            # draw the wire with a slight S-curve so crossings stay legible
            cx1, cx2 = x0 + (x1 - x0) * 0.45, x0 + (x1 - x0) * 0.55
            d = (f"M {x0:.1f} {y:.1f} C {cx1:.1f} {y:.1f} {cx2:.1f} {y1:.1f} "
                 f"{x1:.1f} {y1:.1f}")
            cv.raw(f'<path d="{d}" fill="none" stroke="{C.violet}" stroke-opacity="{0.42*vis:.3f}" '
                   f'stroke-width="1.7" stroke-linecap="round"/>')
            # weight chip on the wire
            wf = vis
            mx = x0 + (x1 - x0) * 0.36
            my = y + (y1 - y) * 0.30 - 12
            cv.rect(mx - 46, my - 15, 92, 30, rx=15, fill="rgba(9,18,29,0.86)",
                    stroke=rgba(C.cyan, 0.35), sw=1.0, opacity=wf * 0.95)
            cv.text(mx, my + 6, f"× {W[i]:.2f}", size=18, color=C.cyan_soft,
                    weight=500, family="JetBrains Mono", anchor="middle", opacity=wf * 0.98)

    # -------------------------------------------------------------- register
    def draw_register(self, cv, t):
        a = remap(self.T(t), self.tw(1.5), self.tw(2.4), "out_quad")
        if a <= 0.01:
            return
        cv.rect(REG_X, REG_Y, REG_W, REG_H, rx=14, fill="rgba(12,22,34,0.9)",
                stroke=rgba(C.cyan, 0.5), sw=1.4, opacity=a)
        section_label(cv, REG_X + 18, REG_Y + 26, "Σ  REGISTER", alpha=a, size=11.5)

        # three product rows count up
        for i in range(3):
            p = self.product_p(i, t)
            y = REG_Y + 78 + i * 50
            val = PROD[i] * p
            cv.text(REG_X + 22, y, f"w<sub>{i+1}</sub>x<sub>{i+1}</sub>", size=17,
                    color=C.ink_mute, weight=500, opacity=a)
            cv.text(REG_X + REG_W - 22, y, f"{val:.3f}", size=21, color=C.ink,
                    weight=500, family="JetBrains Mono", anchor="end", opacity=a)
            # mini bar
            bw = (REG_W - 44) * (val / 0.16) * 0.98
            cv.rect(REG_X + 22, y + 8, REG_W - 44, 3.6, fill=rgba(C.ink_faint, 0.22),
                    rx=1.7, opacity=a)
            cv.rect(REG_X + 22, y + 8, bw, 3.6, fill=C.violet, rx=1.7, opacity=a * 0.85)

        # bias row
        bp = self.bias_p(t)
        yb = REG_Y + 78 + 3 * 50
        cv.text(REG_X + 22, yb, "b", size=17, color=C.amber, weight=500, opacity=a * bp)
        cv.text(REG_X + REG_W - 22, yb, f"+{B:.3f}", size=21, color=C.amber,
                weight=500, family="JetBrains Mono", anchor="end", opacity=a * bp)

        # total row
        zp = self.z_p(t)
        cv.line(REG_X + 22, yb + 16, REG_X + REG_W - 22, yb + 16, stroke=rgba(C.stroke_hi, 0.9),
                sw=1.0, opacity=a * zp)
        zval = (sum(PROD) + B) * zp
        cv.text(REG_X + 22, yb + 52, "z", size=22, color=C.teal, weight=600, opacity=a * zp)
        cv.text(REG_X + REG_W - 22, yb + 52, f"{zval:.3f}", size=26, color=C.teal,
                weight=600, family="JetBrains Mono", anchor="end", opacity=a * zp)

    def draw_bias(self, cv, t):
        bp = self.bias_p(t)
        if bp <= 0.01:
            return
        # a bias token that slides from below into the register
        x = lerp(REG_X + REG_W / 2, REG_X + REG_W / 2, bp)
        y = lerp(REG_Y + REG_H + 76, REG_Y + REG_H + 26, bp)
        cv.line(x, y, x, REG_Y + REG_H - 8, stroke=rgba(C.amber, 0.6), sw=1.4,
                opacity=bp * (1 - remap(self.T(t), self.tw(6.3), self.tw(6.9), "in_out_sine") * 0.6))
        cv.rect(x - 42, y - 17, 84, 34, rx=17, fill=rgba(C.amber_deep, 0.34),
                stroke=rgba(C.amber, 0.85), sw=1.2, opacity=bp)
        cv.text(x, y + 6, f"b = {B:.2f}", size=18, color=C.amber, weight=500,
                family="JetBrains Mono", anchor="middle", opacity=bp)

    # --------------------------------------------------------------- sigmoid
    def sigmoid_point(self, z):
        return 1.0 / (1.0 + math.exp(-z))

    def draw_sigmoid(self, cv, t):
        a = remap(self.T(t), self.tw(6.5), self.tw(7.6), "out_quad")
        if a <= 0.01:
            return
        x, y, w, h = SIG
        panel(cv, x, y, w, h, alpha=a, accent=C.cyan, accent_side="top",
              fill="rgba(8,16,26,0.78)")
        section_label(cv, x + 18, y + 26, "ACTIVATION   σ(z)", alpha=a, size=11.5)

        # axes
        px0, px1 = x + 34, x + w - 26
        py0, py1 = y + h - 42, y + 54
        zmin, zmax = -6.0, 6.0
        def to_px(z, s):
            u = (z - zmin) / (zmax - zmin)
            return (px0 + u * (px1 - px0), py1 - s * (py1 - py0))

        cv.line(px0, py1, px1, py1, stroke=rgba(C.stroke_hi, 1.0), sw=1.1, opacity=0.9 * a)
        cv.line((px0 + px1) / 2, py1, (px0 + px1) / 2, py0, stroke=rgba(C.stroke_hi, 1.0),
                sw=1.1, opacity=0.9 * a)
        cv.text(px1 - 2, py1 + 18, "z", size=14, color=C.ink_mute, weight=500,
                anchor="end", opacity=0.8 * a)
        cv.text((px0 + px1) / 2 + 8, py0 - 6, "σ(z)", size=14, color=C.ink_mute,
                weight=500, opacity=0.8 * a)

        # the curve, traced progressively
        prog = remap(self.T(t), self.tw(7.0), self.tw(8.6), "in_out_sine")
        pts = []
        zs = np.linspace(zmin, zmax, 160)
        n = max(2, int(len(zs) * prog))
        for z in zs[:n]:
            pts.append(to_px(float(z), self.sigmoid_point(float(z))))
        if len(pts) > 1:
            d = "M " + " L ".join(f"{p[0]:.1f} {p[1]:.1f}" for p in pts)
            cv.raw(f'<path d="{d}" fill="none" stroke="{C.ink_mute}" stroke-opacity="{0.45*a:.3f}" stroke-width="1.4"/>')

        # z marker travels along the curve
        sp = self.sig_p(t)
        if sp > 0.01:
            z_now = lerp(zmin, Z, sp)
            s_now = self.sigmoid_point(z_now)
            qx, qy = to_px(z_now, s_now)
            cv.line(qx, py1, qx, qy, stroke=rgba(C.cyan, 0.5), sw=1.0, dash="3 4",
                    opacity=0.9 * a)
            cv.line(px0, qy, qx, qy, stroke=rgba(C.cyan, 0.5), sw=1.0, dash="3 4",
                    opacity=0.9 * a)
            cv.circle(qx, qy, 8.0, fill=C.cyan, opacity=0.2 * a, extra='filter="url(#glowSmall)"')
            cv.circle(qx, qy, 4.6, fill=C.ink, stroke=C.cyan, sw=2.0, opacity=a)
            # live readout of the pair
            cv.text(x + w - 18, y + 26, f"z = {z_now:+.3f}", size=13, color=C.cyan_soft,
                    weight=500, family="JetBrains Mono", anchor="end", opacity=a)
            cv.text(x + w - 18, y + 46, f"σ = {s_now:.4f}", size=13, color=C.teal,
                    weight=500, family="JetBrains Mono", anchor="end", opacity=a)

    # ---------------------------------------------------------------- output
    def draw_output(self, cv, t):
        op = self.out_p(t)
        if op <= 0.01:
            return
        x, y = OUT_X, SUM_Y
        # connecting arc from the sigmoid to the output node
        sx, sy, sw, sh = SIG
        cv.raw(f'<path d="M {sx+sw-10:.0f} {sy+sh*0.52:.0f} C {sx+sw+90:.0f} {sy+sh*0.52:.0f} '
               f'{x-140:.0f} {y:.0f} {x-76:.0f} {y:.0f}" fill="none" stroke="{C.cyan}" '
               f'stroke-opacity="{0.45*op:.3f}" stroke-width="2.0" stroke-linecap="round" '
               f'stroke-dasharray="6 6"/>')
        rr = 74 * ease_out_back(min(1.0, op * 1.2))
        cv.circle(x, y, rr, fill=rgba(C.teal_deep, 0.22), stroke=rgba(C.teal, 0.8),
                  sw=1.6, opacity=op)
        cv.circle(x, y, rr * 0.78, fill="none", stroke=rgba(C.teal, 0.25), sw=1.0, opacity=op)
        cv.text(x, y - 4, f"{A:.3f}", size=34, color=C.ink, weight=600,
                family="JetBrains Mono", anchor="middle", opacity=op)
        cv.text(x, y + 28, "activation", size=12.5, color=C.teal, weight=500,
                tracking=0.14, anchor="middle", opacity=0.85 * op)
        cv.text(x, y + 104, "a = σ(z)", size=19, color=C.ink_soft, weight=500,
                anchor="middle", opacity=0.85 * op)

    # --------------------------------------------------------------- formula
    def draw_formula(self, cv, t):
        a = remap(self.T(t), self.tw(11.1), self.tw(12.1), "out_quad")
        if a <= 0.01:
            return
        E = mathtex.tex(self.FORMULA)
        size = 34
        cv.raw(E.svg(WIDTH / 2, 806, size, C.ink, opacity=a, anchor="middle", reveal=remap(self.T(t), self.tw(11.2), self.tw(12.8), "linear")))
