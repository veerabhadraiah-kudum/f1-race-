"""
Scene 4 — The mathematics, term by term.

This is the "connective tissue" scene: three canonical equations arrive one at a
time, and each is visually bound to the object it describes. As a term lights up
in the equation, the matching object on stage highlights and the link is drawn —
so the symbols stop being decoration and start being labels.

  0.0 – 3.4   F1  objective + loss        → the loss surface & the point on it
  3.4 – 6.6   F2  the update rule         → the descending path + step vector
  6.6 – 9.8   F3  a single activation     → the sigmoid curve & the neuron
  9.8 – 13.2  all three compose into the training loop diagram

Timing is driven by one table (`TERMS`) so captions, highlights and the video
all key off the same numbers.
"""
from __future__ import annotations

import math

import numpy as np

from engine import mathtex
from engine.animate import ease, lerp, remap, window
from engine.layout import HEADER_Y, panel, section_label
from ._retime import Retimed
from engine.scene import Beat, Cue, Scene
from engine.theme import C, HEIGHT, WIDTH, rgba

# equation x position, and where the matching object lives on stage
EQ_X = 150.0


def _lift(hex_color: str) -> str:
    """Highlight colour tuned for legibility on the dark plate."""
    from engine.theme import mix
    return mix(hex_color, "#ffffff", 0.28)
STAGE_X0, STAGE_X1 = 780.0, 1836.0
STAGE_Y0, STAGE_Y1 = 214.0, 742.0

F1 = r"\min_{w}\,\frac{1}{n}\sum_{i=1}^{n}\ell\big(h(x_i;w),\,y_i\big)"
F2 = r"w_{t+1} = w_t - \eta\,\nabla L(w_t)"
F3 = r"a = \sigma\!\left(\sum_{i} w_i x_i + b\right)"
F4 = r"\sigma(z) = \frac{1}{1+e^{-z}}"


class EquationsAndTerms(Retimed, Scene):
    name = "s4_equations"
    title = "The mathematics"
    subtitle = "Each symbol names something you can see"
    chapter = 4
    chapter_total = 4
    duration = 13.6
    # How long the closing card stays on screen, fully lit, before the film ends.
    # Both the card and the chrome fade are keyed off the *real* scene duration:
    # the retime warp compresses the authored tail, so expressing them in
    # authored seconds gave the card barely a second of screen time.
    CARD_HOLD = 2.2

    beats = {
        "f1": Beat("f1", 0.3, 3.5, "objective"),
        "f2": Beat("f2", 3.4, 6.7, "update rule"),
        "f3": Beat("f3", 6.6, 9.9, "activation"),
        "loop": Beat("loop", 9.8, 13.4, "training loop"),
    }

    cues = [
        Cue(0.9, 4.4, "Training minimises an average loss over the data."),
        Cue(4.6, 8.4, "Each step moves the weights against the gradient, scaled by a learning rate."),
        Cue(8.6, 13.3, "Repeat those two moves and the whole function is learned."),
    ]

    #: (equation, term label, highlight colour, stage object id)
    TERMS = [
        ("f1", F1, 0.0, 3.4, [
            (r"\min_{w}", "choose the weights", C.violet),
            (r"\frac{1}{n}\sum", "average over the data", C.cyan),
            (r"\ell", "per-example loss", C.amber),
            ("h", "the model", C.teal),
        ]),
        ("f2", F2, 3.4, 6.6, [
            ("w_{t+1}", "next weights", C.teal),
            (r"\eta", "learning rate", C.amber),
            (r"\nabla L", "gradient", C.rose),
        ]),
        ("f3", F3, 6.6, 9.8, [
            ("\\sigma", "activation", C.cyan),
            ("\\sum", "weighted sum", C.violet),
            ("b", "bias", C.amber),
        ]),
    ]

    def __init__(self):
        super().__init__()
        mathtex.prebuild([F1, F2, F3, F4])
        self.apply_timing()

    # ---------------------------------------------------------------- header
    def draw_title_card(self, cv, t):
        """Chapter card: resolves in the open canvas during the narration lead-in."""
        a = remap(t, 0.15, 0.9, "out_quad") * (1.0 - remap(t, 1.95, 2.6, "in_out_sine"))
        if a <= 0.01:
            return
        x, y = 132, 452
        cv.text(x, y, 'THE MATHEMATICS', size=13, color=C.cyan, weight=600,
                tracking=0.36, opacity=0.9 * a)
        rp = remap(t, 0.35, 1.25, "in_out_cubic")
        cv.line(x, y + 26, x + 118 * rp, y + 26, stroke=C.cyan, sw=1.6, opacity=0.55 * a)
        cv.text(x, y + 104, 'The mathematics', size=76, color=C.ink, weight=600,
                family="Fraunces", tracking=-0.01, opacity=a)
        cv.text(x, y + 156, 'symbols, bound to what they describe', size=25, color=C.ink_soft, weight=400,
                opacity=0.86 * a)

    def draw_header(self, cv, t):
        a = remap(t, 0.4, 1.4, "out_quad") * self._chrome(t)
        y = HEADER_Y + 46
        cv.raw(f'<rect x="96" y="{y-28}" width="2.6" height="32" fill="{C.cyan}" opacity="{0.9*a:.3f}"/>')
        cv.text(114, y, "THE MATHEMATICS", size=28, color=C.ink, weight=600, tracking=0.04, opacity=a)
        cv.text(114, y + 24, "four ideas, bound to what they describe", size=14, color=C.ink_mute,
                weight=400, tracking=0.06, opacity=0.9 * a)

    # ----------------------------------------------------------------- render
    @property
    def card_at(self) -> float:
        """Real second at which the closing card is fully lit."""
        return self.duration - self.CARD_HOLD

    @property
    def chrome_fade_at(self) -> float:
        """HUD + caption start leaving here, so the card arrives on a clean frame."""
        return self.card_at - 1.15

    def _chrome(self, t: float) -> float:
        """1 while the film's frame furniture is live, 0 behind the closing card."""
        return 1.0 - remap(t, self.chrome_fade_at, self.chrome_fade_at + 0.7, "in_out_sine")

    # ------------------------------------------------------------- retime
    def tw(self, t_authored: float) -> float:
        """Authored second -> narration-timed real second."""
        return self.T(t_authored)

    def render(self, cv, t):
        T = self.T(t)            # narration-timed clock
        self.draw_title_card(cv, T)
        self.draw_header(cv, t)
        # stage object (right) fades between the three views
        w1 = window(t, 0.4, 3.6)
        w2 = window(t, 3.4, 6.8)
        w3 = window(t, 6.6, 10.0)
        # the loop diagram hands over to the closing veil rather than fading out
        # early and leaving an empty beat before the card lands
        w4 = window(t, 9.8, self.card_at - 0.15)
        if w1 > 0.01:
            self.stage_loss(cv, t, w1)
        if w2 > 0.01:
            self.stage_descent(cv, t, w2)
        if w3 > 0.01:
            self.stage_sigmoid(cv, t, w3)
        if w4 > 0.01:
            self.stage_loop(cv, t, w4)
        # equations stack on the left, each revealed in its slot
        ys = [268.0, 476.0, 676.0]
        for k, (key, tex_s, t0, t1, terms) in enumerate(self.TERMS):
            a = remap(t, t0 + 0.15, t0 + 0.9, "out_quad") * (1.0 - remap(T, self.tw(9.9), self.tw(10.8), "in_out_sine") * 0.55)
            if a <= 0.01:
                continue
            self.draw_equation_block(cv, key, tex_s, ys[k], t, a, terms, t0, t1)

        # final: the loop
        la = remap(T, self.tw(10.2), self.tw(11.4), "out_quad")
        if la > 0.01:
            self.draw_loop_links(cv, t, la)
        self._closing_veil(cv, t)
        self.draw_closing_card(cv, t)

    # ------------------------------------------------------------- equations
    def draw_equation_block(self, cv, key, tex_s, y, t, a, terms, t0, t1):
        E = mathtex.tex(tex_s)
        size = 40
        # progressive draw-on of the whole expression
        reveal = remap(t, t0 + 0.15, t0 + 1.5, "in_out_sine")
        # active term cycling inside this equation's window
        n = len(terms)
        span = (t1 - t0 - 1.6)
        idx = None
        if span > 0:
            u = (t - (t0 + 1.5)) / span
            if 0 <= u < 1:
                idx = min(n - 1, int(u * n))
                idx = None  # handled below with per-term windows
        # per-term highlight windows
        hl = {}
        active_label = None
        for k, (sel, label, col) in enumerate(terms):
            s0 = t0 + 1.5 + k * (span / max(n, 1))
            s1 = s0 + (span / max(n, 1)) * 0.92
            w = window(t, s0, s1)
            if w > 0.02:
                hl[sel] = _lift(col)
                active_label = (label, col, w)
        # equation
        cv.raw(E.svg(EQ_X, y, size, C.ink, opacity=a, reveal=reveal, highlight=hl))
        # caption under the equation showing the active term's meaning.
        # Note: it sits below the equation's descender box, never on top of a term.
        if active_label:
            label, col, w = active_label
            lw = E.width * size
            below = y + E.height * size * 0.42 + 26
            ly = below if below < 780 else y - E.height * size - size * 0.45
            cv.circle(EQ_X - 5, ly - 6, 3.4, fill=col, opacity=0.95 * w * a)
            cv.text(EQ_X + 8, ly, label, size=16.5, color=col, weight=600,
                    opacity=w * a, tracking=0.06)
            # connector from the equation to the stage object
            self.draw_connector(cv, EQ_X + lw + 26, y - size * 0.30, col, w * a, key)
            self.draw_active_badge(cv, key, col, w, a)

    def draw_active_badge(self, cv, key, col, w, a):
        """Names the object the highlighted term points at, in the term's colour."""
        label = {"f1": "the loss surface", "f2": "the descent path", "f3": "the sigmoid"}.get(key)
        if not label or w <= 0.02:
            return
        x = STAGE_X1 - 24
        y = STAGE_Y0 + 12
        from engine.typography import Font
        f = Font("Inter", 600, 13, label, tracking=0.12)
        bw = f.advance + 30
        cv.rect(x - bw, y - 16, bw, 30, rx=15, fill=rgba(col, 0.14),
                stroke=rgba(col, 0.6), sw=1.1, opacity=w * a)
        cv.raw(f.svg(x - bw + 15, y + 4, col, opacity=w * a))

    def draw_connector(self, cv, x0, y0, col, a, key):
        """A thin curved leader from the highlighted term to its object."""
        if a <= 0.01:
            return
        tx = STAGE_X0 - 12
        ty = {"f1": 420.0, "f2": 470.0, "f3": 430.0}.get(key, 440.0)
        d = (f"M {x0:.1f} {y0:.1f} C {x0+70:.1f} {y0:.1f} {tx-90:.1f} {ty:.1f} "
             f"{tx:.1f} {ty:.1f}")
        p = remap(a, 0.0, 1.0, "linear")
        cv.raw(f'<path d="{d}" fill="none" stroke="{col}" stroke-opacity="{0.5*a:.3f}" '
               f'stroke-width="1.3" stroke-dasharray="4 6" stroke-linecap="round"/>')
        cv.circle(tx, ty, 3.2, fill=col, opacity=0.85 * a)

    # ---------------------------------------------------------------- stages
    def stage_frame(self, cv, a, title):
        panel(cv, STAGE_X0 - 24, STAGE_Y0 - 40, (STAGE_X1 - STAGE_X0) + 48,
              (STAGE_Y1 - STAGE_Y0) + 74, alpha=a, accent=C.cyan, accent_side="top",
              fill="rgba(8,16,26,0.55)", stroke=rgba(C.stroke_hi, 0.7))
        section_label(cv, STAGE_X0, STAGE_Y0 - 12, title, alpha=0.95 * a, size=12)

    def stage_loss(self, cv, t, a):
        """A quadratic bowl seen from the side, with the loss minimised by hand."""
        self.stage_frame(cv, a, "OBJECTIVE   ·   a loss surface over the weights")
        cx = (STAGE_X0 + STAGE_X1) / 2
        base_y = STAGE_Y1 - 60
        amp = 150.0
        half = 380.0
        # curve
        pts = []
        for k in range(121):
            u = k / 120
            x = cx - half + u * 2 * half
            y = base_y - amp * (u * 2 - 1) ** 2
            pts.append((x, y))
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        # filled area under the curve: reads as a surface, not a line
        fill_d = d + f" L {pts[-1][0]:.1f} {base_y + 4:.1f} L {pts[0][0]:.1f} {base_y + 4:.1f} Z"
        cv.raw(f'<path d="{fill_d}" fill="url(#bowlFill)" opacity="{0.9*a:.3f}"/>')
        cv.raw(f'<path d="{d}" fill="none" stroke="{C.teal}" stroke-opacity="{0.85*a:.3f}" stroke-width="2.6"/>')
        # iso-contour guides: the same loss at several levels
        for lv in (0.12, 0.30, 0.52, 0.78):
            yy = base_y - amp * lv
            half_w = half * math.sqrt(lv)
            cv.line(cx - half_w, yy, cx + half_w, yy, stroke=rgba(C.cyan_soft, 0.35),
                    sw=1.0, dash="3 7", opacity=a)
        # samples scattered on it = the data terms
        rng = np.random.default_rng(11)
        for k in range(16):
            u = rng.uniform(0.06, 0.94)
            x = cx - half + u * 2 * half
            y = base_y - amp * (u * 2 - 1) ** 2 - 12
            cv.circle(x, y, 3.4, fill=C.amber, opacity=0.55 * a)
        # the minimiser
        pulse = 1.0 + 0.06 * math.sin(t * 4)
        cv.circle(cx, base_y, 9 * pulse, fill=C.cyan, opacity=0.22 * a, extra='filter="url(#glowSmall)"')
        cv.circle(cx, base_y, 5.2, fill=C.ink, stroke=C.cyan, sw=2.0, opacity=a)
        cv.line(cx, base_y, cx, base_y + 26, stroke=rgba(C.cyan, 0.5), sw=1.2,
                dash="3 4", opacity=a)
        cv.text(cx, base_y + 48, "w*", size=18, color=C.cyan, weight=500,
                anchor="middle", opacity=0.95 * a)
        cv.text(cx + 250, base_y - amp * 0.72, "L(w)", size=18, color=C.teal,
                weight=500, anchor="middle", opacity=0.9 * a)

    def stage_descent(self, cv, t, a):
        """Contours + a stepping path + the -∇L vector, i.e. the update rule."""
        self.stage_frame(cv, a, "UPDATE RULE   ·   step against the gradient")
        cx, cy = (STAGE_X0 + STAGE_X1) / 2 + 10, (STAGE_Y0 + STAGE_Y1) / 2 + 20
        # contour ellipses of a quadratic
        for k, (rx, ry, al) in enumerate([(330, 168, 0.20), (252, 128, 0.26),
                                          (176, 90, 0.32), (104, 54, 0.38), (52, 27, 0.44)]):
            cv.ellipse(cx, cy, rx, ry, fill="none", stroke=C.cyan_soft, sw=1.2,
                       opacity=al * a)
        # stepped path from the rim into the centre
        n = 7
        path = []
        for k in range(n + 1):
            u = k / n
            r = 1.0 - 0.86 * (1 - (1 - u) ** 1.7)
            ang = 2.2 - u * 1.5
            path.append((cx + math.cos(ang) * 330 * r, cy + math.sin(ang) * 168 * r))
        prog = remap(self.T(t), self.tw(3.6), self.tw(6.2), "in_out_sine")
        vis = path[: max(2, int(len(path) * prog))]
        if len(vis) > 1:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in vis)
            cv.raw(f'<path d="{d}" fill="none" stroke="{C.amber}" stroke-opacity="{0.9*a:.3f}" '
                   f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')
        for k, (x, y) in enumerate(path[: len(vis)]):
            cv.circle(x, y, 4.0, fill="#fff", opacity=0.85 * a)
        # the gradient arrow at the current point
        if len(vis) >= 2:
            x0, y0 = vis[-1]
            x1, y1 = vis[-2]
            dx, dy = (x1 - x0), (y1 - y0)
            L = math.hypot(dx, dy) or 1.0
            ex, ey = x0 + dx / L * 56, y0 + dy / L * 56
            cv.line(x0, y0, ex, ey, stroke=C.rose, sw=2.6, opacity=0.9 * a)
            cv.circle(ex, ey, 4.4, fill=C.rose, opacity=0.9 * a)
        cv.text(cx, STAGE_Y1 - 26, "one step:  move against the gradient", size=15,
                color=C.rose, weight=500, anchor="middle", opacity=0.85 * a)

    def stage_sigmoid(self, cv, t, a):
        self.stage_frame(cv, a, "ACTIVATION   ·   any number, squashed into (0, 1)")
        x0, x1 = STAGE_X0 + 70, STAGE_X1 - 70
        y0, y1 = STAGE_Y0 + 70, STAGE_Y1 - 90
        def px(z, s):
            return (x0 + (z + 6) / 12 * (x1 - x0), y1 - s * (y1 - y0))
        cv.line(x0, y1, x1, y1, stroke=rgba(C.stroke_hi, 1.0), sw=1.2, opacity=0.9 * a)
        cv.line((x0 + x1) / 2, y0, (x0 + x1) / 2, y1, stroke=rgba(C.stroke_hi, 1.0), sw=1.2, opacity=0.9 * a)
        # asymptotes
        for s_ in (0.0, 1.0):
            yy = px(0, s_)[1]
            cv.line(x0, yy, x1, yy, stroke=rgba(C.ink_faint, 0.5), sw=1.0, dash="2 7", opacity=0.8 * a)
        prog = remap(self.T(t), self.tw(6.9), self.tw(8.4), "in_out_sine")
        pts = []
        zs = np.linspace(-6, 6, 200)
        for z in zs[: max(2, int(200 * prog))]:
            pts.append(px(float(z), 1 / (1 + math.exp(-float(z)))))
        if len(pts) > 1:
            d = "M " + " L ".join(f"{p[0]:.1f} {p[1]:.1f}" for p in pts)
            cv.raw(f'<path d="{d}" fill="none" stroke="{C.cyan}" stroke-opacity="{0.95*a:.3f}" stroke-width="2.8"/>')
        # sigma(0) = 0.5: the fixed point every zero passes through
        qx, qy = px(0.0, 0.5)
        cv.circle(qx, qy, 4.2, fill=C.ink, stroke=C.cyan, sw=1.8, opacity=a)
        cv.text(qx + 12, qy - 10, "σ(0) = ½", size=15, color=C.cyan_soft, weight=500,
                opacity=0.9 * a)
        # shaded saturation bands behind both tails
        cv.rect(x0, y0 - 6, x1 - x0, 26, fill=rgba(C.cyan, 0.13), opacity=0.55 * a)
        cv.rect(x0, y1 - 22, x1 - x0, 26, fill=rgba(C.violet, 0.13), opacity=0.55 * a)
        cv.text(x1, y1 + 24, "z", size=16, color=C.ink_mute, anchor="end", opacity=0.85 * a)
        cv.text(x0, y0 + 4, "1", size=16, color=C.ink_mute, opacity=0.85 * a)
        cv.text(x0, y1 - 4, "0", size=16, color=C.ink_mute, opacity=0.85 * a)

    def stage_loop(self, cv, t, a):
        """Three boxes: data → update → model, joined into a cycle."""
        self.stage_frame(cv, a, "TRAINING LOOP   ·   data, loss, step, repeat")
        cx, cy = (STAGE_X0 + STAGE_X1) / 2, (STAGE_Y0 + STAGE_Y1) / 2 + 10
        R = 168
        boxes = [("data", -90), ("loss", 30), ("step", 150)]
        pts = []
        for name, deg in boxes:
            ang = math.radians(deg)
            x = cx + math.cos(ang) * R * 1.55
            y = cy + math.sin(ang) * R * 0.95
            pts.append((name, x, y, ang))
        # cycle arrows
        for k in range(len(pts)):
            _, x0, y0, _ = pts[k]
            _, x1, y1, _ = pts[(k + 1) % len(pts)]
            ap = remap(t, 10.5 + k * 0.28, 11.2 + k * 0.28, "out_cubic")
            if ap <= 0.01:
                continue
            xa, ya = x0 + (x1 - x0) * 0.22, y0 + (y1 - y0) * 0.22
            xb, yb = x0 + (x1 - x0) * 0.78, y0 + (y1 - y0) * 0.78
            cv.line(xa, ya, xb, yb, stroke=rgba(C.cyan, 0.55), sw=1.8, opacity=ap * a)
        for name, x, y, ang in pts:
            bp = remap(self.T(t), self.tw(10.2), self.tw(11.0), "out_back")
            if bp <= 0.01:
                continue
            cols = {"data": C.violet, "loss": C.amber, "step": C.rose}
            col = cols[name]
            cv.rect(x - 78, y - 30, 156, 60, rx=30, fill=rgba(col, 0.13),
                    stroke=rgba(col, 0.65), sw=1.4, opacity=bp * a)
            cv.text(x, y + 7, name, size=20, color=col, weight=600, anchor="middle",
                    opacity=bp * a, tracking=0.04)

    def _closing_veil(self, cv, t):
        """Full-frame fade to near-black at the very end, under the closing card."""
        s = self.card_at
        a = remap(t, s - 1.00, s - 0.35, "in_out_sine")
        if a > 0.01:
            cv.rect(0, 0, WIDTH, HEIGHT, fill="#050a12", opacity=0.80 * a)

    def draw_closing_card(self, cv, t):
        """The film's last beat: title + a single line, over a quiet stage."""
        s = self.card_at
        a = remap(t, s - 0.90, s - 0.25, "out_quad")
        if a <= 0.01:
            return
        # the veil is emitted first in render() (see _closing_veil) so every
        # other layer is dimmed behind the card
        cx = WIDTH / 2
        cv.text(cx, 452, "MATHEMATICS BEHIND AI", size=13, color=C.cyan, weight=600,
                tracking=0.36, anchor="middle", opacity=0.9 * a)
        rp = remap(t, s - 0.70, s + 0.10, "in_out_cubic")
        cv.line(cx - 118 * rp, 486, cx + 118 * rp, 486, stroke=C.cyan, sw=1.6,
                opacity=0.55 * a)
        cv.text(cx, 580, "Every model is this loop.", size=58, color=C.ink,
                weight=600, family="Fraunces", anchor="middle", opacity=a)
        cv.text(cx, 634, "loss, gradient, step — repeated until the function is learned",
                size=24, color=C.ink_soft, weight=400, anchor="middle", opacity=0.86 * a)

    def draw_loop_links(self, cv, t, a):
        cv.text(WIDTH / 2, 986, "every modern model — transformers included — is this loop, many times over",
                size=17, color=C.ink_mute, weight=400, anchor="middle",
                opacity=0.8 * a * (1.0 - remap(self.T(t), self.tw(13.2), self.tw(14.0), "in_out_sine")),
                tracking=0.02)
