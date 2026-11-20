"""
Scene 2 — Neural network.

A real network, drawn as a graph and animated as a computation:

  0.0 – 2.0   layer frames resolve; nodes pop in with a spring, layer by layer
  2.0 – 4.6   connections draw on progressively (staggered by source node)
  4.6 – 8.6   a forward pass: signal pulses travel every edge; nodes accumulate
              their input, then fire (activation) layer by layer
  8.6 – 11.2  a second pass at higher intensity; the output layer settles on a
              decision read-out
 11.2 – 13.6  the network dims and the compact notation appears

The layout is a real feed-forward topology (4-5-4-2), and the propagation
timing follows the graph: a node can only fire once every incoming edge has
delivered. That is what makes the motion read as computation rather than as
decoration.
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

LAYERS = [4, 5, 4, 2]

# node x positions (px), the graph band
X0, X3 = 322.0, 1640.0
Y_MID = 500.0
V_GAP = 104.0
NODE_R = 25.0


class NeuralNetwork(Retimed, Scene):
    name = "s2_neural_network"
    title = "The network"
    subtitle = "Layers of weighted sums, stacked into a function"
    chapter = 2
    chapter_total = 4
    duration = 14.0

    beats = {
        "nodes": Beat("nodes", 0.25, 2.2, "nodes in"),
        "edges": Beat("edges", 2.0, 4.7, "edges drawn"),
        "pass1": Beat("pass1", 4.7, 8.7, "forward pass"),
        "pass2": Beat("pass2", 8.4, 11.3, "second pass"),
        "notation": Beat("notation", 11.0, 13.6, "notation"),
    }

    cues = [
        Cue(2.4, 6.4, "Each layer sums weighted inputs, then bends the result with a nonlinearity."),
        Cue(6.6, 11.6, "Stack enough of them and the network can approximate any continuous function."),
    ]

    NOTE_TEX = r"h(x) = \sigma_3\big(W_3\,\sigma_2(W_2\,\sigma_1(W_1 x + b_1) + b_2) + b_3\big)"

    def __init__(self):
        super().__init__()
        self.pos = []      # per layer: list of (x, y)
        for li, n in enumerate(LAYERS):
            x = X0 + (X3 - X0) * li / (len(LAYERS) - 1)
            ys = [Y_MID + (i - (n - 1) / 2) * V_GAP for i in range(n)]
            self.pos.append([(x, y) for y in ys])
        mathtex.prebuild([self.NOTE_TEX])
        self.apply_timing()

    # ------------------------------------------------------------- transform
    def graph_transform(self, t):
        """
        During the notation beat the graph shrinks into a schematic strip and
        lifts, so the composed function can own the frame. Returning
        (scale, dx, dy) keeps every graph primitive under one transform.
        """
        p = remap(t, 11.0, 12.2, "in_out_cubic")
        scale = lerp(1.0, 0.52, p)
        dx = lerp(0.0, -260.0, p)
        dy = lerp(0.0, 96.0, p)
        cx, cy = (X0 + X3) / 2, Y_MID
        return scale, dx + (cx - cx * scale), dy + (cy - cy * scale)

    def _tp(self, x, y, t):
        s_, dx, dy = self.graph_transform(t)
        return (x * s_ + dx, y * s_ + dy)

    # ------------------------------------------------------------------ timing
    def node_pop(self, li, i, t):
        """Springy pop, staggered left-to-right and top-to-bottom."""
        delay = 0.30 + li * 0.13 + i * 0.055
        p = remap(t, 0.25 + delay, 0.25 + delay + 0.55, "out_back")
        return max(0.0, p)

    def edge_draw(self, li, i, j, t):
        """Edges draw on in waves from the previous layer."""
        delay = 2.05 + li * 0.42 + (i + j) * 0.030
        return remap(t, delay, delay + 0.55, "in_out_cubic")

    # ------------------------------------------------------------------ render
    # ------------------------------------------------------------- retime
    def tw(self, t_authored: float) -> float:
        """Authored second -> narration-timed real second."""
        return self.T(t_authored)

    def render(self, cv, t: float):
        T = self.T(t)            # narration-timed clock
        self.draw_title_card(cv, T)
        s_, dx, dy = self.graph_transform(t)
        self.draw_header(cv, t)
        cv.raw(f'<g transform="translate({dx:.2f},{dy:.2f}) scale({s_:.4f})">')
        self.draw_edge_field(cv, t)
        self.draw_edges(cv, t)
        self.draw_nodes(cv, t)
        self.draw_pulses(cv, t)
        self.draw_layer_labels(cv, t)
        self.draw_readout(cv, t)
        cv.raw("</g>")
        self.draw_notation(cv, t)

    def draw_title_card(self, cv, t):
        """Chapter card: resolves in the open canvas during the narration lead-in."""
        a = remap(t, 0.15, 0.9, "out_quad") * (1.0 - remap(t, 1.95, 2.6, "in_out_sine"))
        if a <= 0.01:
            return
        x, y = 132, 452
        cv.text(x, y, 'THE NETWORK', size=13, color=C.cyan, weight=600,
                tracking=0.36, opacity=0.9 * a)
        rp = remap(t, 0.35, 1.25, "in_out_cubic")
        cv.line(x, y + 26, x + 118 * rp, y + 26, stroke=C.cyan, sw=1.6, opacity=0.55 * a)
        cv.text(x, y + 104, 'A neural network', size=76, color=C.ink, weight=600,
                family="Fraunces", tracking=-0.01, opacity=a)
        cv.text(x, y + 156, 'layers, weighted sums, and a forward pass', size=25, color=C.ink_soft, weight=400,
                opacity=0.86 * a)

    def draw_header(self, cv, t):
        a = remap(self.T(t), self.tw(0.6), self.tw(1.6), "out_quad") * (1.0 - remap(self.T(t), self.tw(10.9), self.tw(11.9), "in_out_sine"))
        if a <= 0.01:
            return
        y = HEADER_Y + 46
        cv.raw(f'<rect x="96" y="{y-28}" width="2.6" height="32" fill="{C.violet}" opacity="{0.9*a:.3f}"/>')
        cv.text(114, y, "A NEURAL NETWORK", size=28, color=C.ink, weight=600, tracking=0.04, opacity=a)
        cv.text(114, y + 24, "4 · 5 · 4 · 2 fully connected", size=14, color=C.ink_mute,
                weight=400, tracking=0.06, opacity=0.9 * a)

    def draw_edge_field(self, cv, t):
        """Soft glow behind the graph so edges read against the plate."""
        a = remap(self.T(t), self.tw(1.0), self.tw(2.6), "in_out_sine")
        if a <= 0.01:
            return
        cv.rect(X0 - 120, Y_MID - 300, (X3 - X0) + 240, 600, fill="url(#graphField)",
                opacity=0.55 * a, rx=40)

    def draw_edges(self, cv, t):
        for li in range(len(LAYERS) - 1):
            for i in range(LAYERS[li]):
                for j in range(LAYERS[li + 1]):
                    p = self.edge_draw(li, i, j, t)
                    if p <= 0.01:
                        continue
                    x0, y0 = self.pos[li][i]
                    x1, y1 = self.pos[li + 1][j]
                    # cubic that leaves/enters horizontally: reads as flow
                    mid = (x0 + x1) / 2
                    d = self._bezier_d(x0 + NODE_R, y0, mid, y0, mid, y1, x1 - NODE_R, y1, p)
                    heat = self.edge_heat(li, i, j, t)
                    base_a = 0.22 + 0.14 * heat
                    col = C.cyan if heat < 0.55 else C.cyan_soft
                    cv.raw(f'<path d="{d}" fill="none" stroke="{col}" '
                           f'stroke-opacity="{base_a * self.edge_alpha(t):.3f}" '
                           f'stroke-width="{0.9 + 1.5 * heat:.2f}" stroke-linecap="round"/>')

    def _bezier_d(self, x0, y0, c1x, c1y, c2x, c2y, x1, y1, p=1.0):
        pts = []
        n = 14
        for k in range(n + 1):
            u = p * k / n
            mu = 1 - u
            x = mu**3 * x0 + 3 * mu**2 * u * c1x + 3 * mu * u**2 * c2x + u**3 * x1
            y = mu**3 * y0 + 3 * mu**2 * u * c1y + 3 * mu * u**2 * c2y + u**3 * y1
            pts.append(f"{x:.1f} {y:.1f}")
        return "M " + " L ".join(pts)

    def edge_alpha(self, t):
        return remap(self.T(t), self.tw(1.9), self.tw(3.0), "out_quad")

    def edge_heat(self, li, i, j, t):
        """
        How "live" an edge is right now. Peaks as a pulse crosses it; the graph
        lights up layer by layer during a forward pass.
        """
        h = 0.0
        for k, (t0, t1) in enumerate(self.pass_windows(t)):
            pass_off = t0 + li * 0.42 + (i * 0.028) + (j * 0.016)
            w = window(t, pass_off - 0.32, pass_off + 0.30)
            h = max(h, w)
        return h

    def pass_windows(self, t):
        return [(4.65, 8.7), (8.4, 11.3)]

    # -------------------------------------------------------------- propagation
    def pulse_progress(self, li, i, j, t):
        """0..1 travel progress of the pulse on edge (li,i,j), or None."""
        for (t0, t1) in self.pass_windows(t):
            start = t0 + li * 0.44 + (i * 0.030) + (j * 0.020)
            dur = 0.52
            if start <= t <= start + dur and t > 0:
                return (t - start) / dur
        return None

    def draw_pulses(self, cv, t):
        for li in range(len(LAYERS) - 1):
            for i in range(LAYERS[li]):
                for j in range(LAYERS[li + 1]):
                    p = self.pulse_progress(li, i, j, t)
                    if p is None:
                        continue
                    x0, y0 = self.pos[li][i]
                    x1, y1 = self.pos[li + 1][j]
                    mid = (x0 + x1) / 2
                    mu = p
                    u = 1 - mu
                    x = u**3 * (x0 + NODE_R) + 3 * u**2 * mu * mid + 3 * u * mu**2 * mid + mu**3 * (x1 - NODE_R)
                    y = u**3 * y0 + 3 * u**2 * mu * y0 + 3 * u * mu**2 * y1 + mu**3 * y1
                    fade = math.sin(math.pi * min(1.0, max(0.0, p))) ** 0.55
                    r = 5.0 * fade + 1.2
                    cv.circle(x, y, r * 2.4, fill=C.cyan, opacity=0.22 * fade,
                              extra='filter="url(#glowSmall)"')
                    cv.circle(x, y, r, fill="#eafeff", opacity=0.95 * fade)
                    cv.circle(x, y, r * 0.5, fill=C.teal, opacity=0.9 * fade)

    # ------------------------------------------------------------------- nodes
    def node_activation(self, li, i, t):
        """A node fires when its incoming signals have landed."""
        a = 0.0
        for (t0, _) in self.pass_windows(t):
            fire = t0 + li * 0.44 + 0.50
            w = window(t, fire - 0.10, fire + 0.62)
            a = max(a, w)
        return a

    def draw_nodes(self, cv, t):
        # connection-completion: draw nodes under the pulses
        for li in range(len(LAYERS)):
            for i in range(LAYERS[li]):
                pop = self.node_pop(li, i, t)
                if pop <= 0.01:
                    continue
                x, y = self.pos[li][i]
                r = NODE_R * pop
                act = self.node_activation(li, i, t)
                heat = max(act, 0.0)

                # outer glow when firing
                if heat > 0.02:
                    cv.circle(x, y, r * 2.2, fill=C.cyan, opacity=0.13 * heat,
                              extra='filter="url(#glowSmall)"')
                # body: radial shading for a little dimensionality
                base = C.panel_hi
                body = self._mix(C.panel_hi, C.cyan if li < 3 else C.teal, 0.10 + 0.62 * heat)
                cv.circle(x, y, r, fill=body, stroke=self._mix(C.stroke_hi, C.cyan_soft, 0.2 + 0.7 * heat),
                          sw=1.6, opacity=min(1.0, pop))
                # specular rim
                cv.raw(f'<path d="M {x - r*0.62:.1f} {y - r*0.70:.1f} A {r*0.95:.1f} {r*0.95:.1f} 0 0 1 {x + r*0.66:.1f} {y - r*0.66:.1f}" '
                       f'fill="none" stroke="#ffffff" stroke-opacity="{0.22*min(1,pop):.3f}" stroke-width="1.6" stroke-linecap="round"/>')
                if heat > 0.03:
                    cv.circle(x, y, r * 0.42, fill="#ffffff", opacity=0.85 * heat)
                    cv.circle(x, y, r * 0.95, fill="none", stroke=C.cyan_soft, sw=1.2,
                              opacity=0.55 * heat)

    @staticmethod
    def _mix(c1, c2, t):
        from engine.theme import mix
        return mix(c1, c2, max(0.0, min(1.0, t)))

    # ---------------------------------------------------------------- labels
    def draw_layer_labels(self, cv, t):
        a = remap(self.T(t), self.tw(3.4), self.tw(4.6), "out_quad")
        if a <= 0.01:
            return
        names = ["INPUT", "HIDDEN", "HIDDEN", "OUTPUT"]
        subs = ["x", "a<sup>1</sup>", "a<sup>2</sup>", None]
        for li, (x, _) in enumerate([self.pos[0][0], self.pos[1][0], self.pos[2][0], self.pos[3][0]]):
            top = min(y for (_, y) in self.pos[li])
            yy = top - 92
            cv.text(x, yy, names[li], size=13, color=C.ink_mute, weight=600,
                    tracking=0.20, anchor="middle", opacity=0.9 * a)
            if subs[li] is None:
                from engine import mathtex
                mathtex.tex(r"\hat{y}").svg(x, yy + 26, 19, C.ink_soft, opacity=0.9 * a,
                                            anchor="middle")
            else:
                cv.text(x, yy + 26, subs[li], size=17, color=C.ink_soft, weight=500,
                        anchor="middle", opacity=0.85 * a)
            cv.line(x, yy + 38, x, yy + 50, stroke=C.stroke_hi, sw=1.0, opacity=0.7 * a)

    def draw_readout(self, cv, t):
        """Output decision read-out, appears as the last layer fires."""
        a = remap(self.T(t), self.tw(6.2), self.tw(7.4), "out_quad") * (1.0 - remap(self.T(t), self.tw(10.9), self.tw(11.7), "in_out_sine"))
        if a <= 0.01:
            return
        # a small probability readout under the output layer
        x = X3 + 30
        y = Y_MID + 296
        panel(cv, x - 300, y - 44, 300, 100, alpha=a, accent=C.teal, accent_side="top")
        section_label(cv, x - 278, y - 18, "OUTPUT  ·  SOFTMAX", alpha=a, size=12)
        p1 = self.output_prob(t, 0)
        p2 = self.output_prob(t, 1)
        for k, (p, col, lab) in enumerate([(p1, C.cyan, "class A"), (p2, C.violet, "class B")]):
            yy = y + 12 + k * 24
            cv.text(x - 278, yy + 5, lab, size=13, color=C.ink_mute, weight=500, opacity=a)
            cv.rect(x - 208, yy - 4, 130, 9, fill=rgba(C.ink_faint, 0.28), rx=4.5, opacity=a)
            cv.rect(x - 208, yy - 4, 130 * p, 9, fill=col, rx=4.5, opacity=a)
            cv.text(x - 58, yy + 5, f"{p*100:4.1f}%", size=13, color=col, weight=600,
                    family="JetBrains Mono", anchor="end", opacity=a)

    def output_prob(self, t, k):
        base = [0.34, 0.66] if k == 0 else [0.66, 0.34]
        p = base[0]
        for (t0, _) in self.pass_windows(t):
            fire = t0 + 3 * 0.44 + 0.55
            p = lerp(p, base[1], remap(t, fire, fire + 0.7, "out_cubic"))
        return min(0.985, max(0.015, p))

    def draw_notation(self, cv, t):
        a = remap(self.T(t), self.tw(11.0), self.tw(12.2), "out_quad")
        if a <= 0.01:
            return
        E = mathtex.tex(self.NOTE_TEX)
        size = 34
        cx = 1082.0
        cv.text(cx, 262, "THE WHOLE NETWORK IS ONE COMPOSED FUNCTION", size=14,
                color=C.ink_mute, weight=600, tracking=0.20, anchor="middle", opacity=0.9 * a)
        cv.raw(E.svg(cx, 348, size, C.ink, opacity=a, anchor="middle"))
        # underline the three nonlinearities as they resolve, left to right
        w = E.width * size
        y_line = 372
        pl = remap(self.T(t), self.tw(12.1), self.tw(13.5), "in_out_sine")
        cv.line(cx - w / 2, y_line, cx - w / 2 + w * pl, y_line,
                stroke=C.cyan, sw=1.6, opacity=0.45 * a)
        cv.text(cx, 424, "each σ  is  one layer's activation", size=15, color=C.teal,
                weight=500, anchor="middle", opacity=0.8 * a * pl)
