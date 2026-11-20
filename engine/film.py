"""
Film assembly.

The film is defined as an ordered list of scenes.  Each scene owns its own
duration, narration cues and beat table; the assembler joins them with short
cross-dissolves and mixes one continuous narration bed underneath.

Because every scene is a pure function of time, the whole film can be rendered
scene by scene (in parallel if desired) and concatenated without any frame-level
state — the same property that makes the previews trustworthy.
"""
from __future__ import annotations

import os
import time

import numpy as np

from .render import encode, render_frames


#: ordered shot list — the single source of truth for the film
SCENE_SPECS = [
    "scenes.s1_gradient_descent:GradientDescent",
    "scenes.s2_neural_network:NeuralNetwork",
    "scenes.s3_neuron:SingleNeuron",
    "scenes.s4_equations:EquationsAndTerms",
]


def load_all():
    import importlib
    out = []
    for spec in SCENE_SPECS:
        mod_name, cls_name = spec.split(":")
        mod = importlib.import_module(mod_name)
        out.append(getattr(mod, cls_name))
    return out


def render_scene(cls, fps=30, scale=1.0, crf=16, workers=None):
    sc = cls()
    out_dir = f"out/frames/{sc.name}"
    times = sc.times(fps=fps)
    t0 = time.time()
    render_frames(cls, times, out_dir, scale=scale, workers=workers)
    dur = time.time() - t0
    os.makedirs("out/scenes", exist_ok=True)
    path = f"out/scenes/{sc.name}.mp4"
    encode(out_dir, path, fps=fps, crf=crf, preset="medium")
    print(f"\n  {sc.name}: {len(times)} frames, {dur:.0f}s render -> {path}")
    return path


def build_film(fps: int = 30, scale: float = 1.0, crf: int = 16):
    """Render every scene, then assemble with a narration bed."""
    from .narration import build_narration

    classes = load_all()
    paths = []
    for cls in classes:
        paths.append(render_scene(cls, fps=fps, scale=scale, crf=crf))

    total = sum(d + 0.0 for d in [cls().duration for cls in classes]) - 0.55 * (len(classes) - 1)
    print(f"\n  film duration: {total:.2f}s")
    narration = build_narration(classes, total)
    final = "out/film/mathematics_behind_ai_1080p.mp4"
    os.makedirs("out/film", exist_ok=True)
    _assemble(paths, narration, final, fps=fps, classes=classes)
    print(f"  -> {final}")
    return final


def _assemble(paths, narration, out, fps=30, classes=None):
    """Cross-dissolve all scenes and lay the narration over the result."""
    from .render import crossfade_concat, mux_audio
    tmp = "out/scenes/_concatenated.mp4"
    crossfade_concat(paths, tmp, fade=0.55, fps=fps)
    if narration:
        mux_audio(tmp, narration, out, gain_db=0.0)
    else:
        import shutil
        shutil.copy(tmp, out)
