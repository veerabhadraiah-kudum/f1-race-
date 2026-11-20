#!/usr/bin/env python
"""
Film build CLI.

    python build.py preview  scenes.s1_gradient_descent:GradientDescent 10
    python build.py scene    scenes.s1_gradient_descent:GradientDescent
    python build.py stills   scenes.s1_gradient_descent:GradientDescent 2.0 5.5
    python build.py sheet    scenes.s1_gradient_descent:GradientDescent   # contact sheet
    python build.py film                                 # everything, 1080p
    python build.py audio                                # narration + sync track

Every command is deterministic: the same inputs always produce the same frames,
which is what makes the QA passes below reproducible.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time

os.environ.setdefault("PYTHONHASHSEED", "0")

from engine.render import encode, render_frames  # noqa: E402


def load_scene(spec: str):
    mod_name, cls_name = spec.split(":")
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


def cmd_preview(spec: str, seconds: float, scale: float = 0.5, fps: int = 30):
    """Render a short low-res slice of a scene: the fast inspection loop."""
    Scene = load_scene(spec)
    sc = Scene()
    out_dir = "out/preview"
    times = sc.times(fps=fps, start=0.0, end=min(seconds, sc.duration))
    t0 = time.time()
    render_frames(Scene, times, out_dir, scale=scale)
    print(f"\n  preview: {len(times)} frames in {time.time()-t0:.1f}s")
    path = f"out/preview_{sc.name}.mp4"
    encode(out_dir, path, fps=fps, crf=20, preset="veryfast")
    print(f"  -> {path}")
    return path


def cmd_scene(spec: str, scale: float = 1.0, fps: int = 30, crf: int = 16, fresh: bool = False):
    Scene = load_scene(spec)
    sc = Scene()
    out_dir = f"out/frames/{sc.name}"
    if fresh:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
    times = sc.times(fps=fps)
    t0 = time.time()
    render_frames(Scene, times, out_dir, scale=scale)
    print(f"\n  {sc.name}: {len(times)} frames in {time.time()-t0:.1f}s")
    path = f"out/scenes/{sc.name}.mp4"
    os.makedirs("out/scenes", exist_ok=True)
    encode(out_dir, path, fps=fps, crf=crf, preset="medium")
    print(f"  -> {path}")
    return path


def cmd_stills(spec: str, *ts: str):
    from PIL import Image
    Scene = load_scene(spec)
    sc = Scene()
    os.makedirs("out/stills", exist_ok=True)
    for t in ts:
        arr = sc.frame_array(float(t))
        p = f"out/stills/{sc.name}_{float(t):05.2f}.png"
        Image.fromarray(arr).save(p)
        print("  ->", p)


def cmd_sheet(spec: str, n: int = 12, cols: int = 4, scale: float = 0.34):
    """Contact sheet: n evenly spaced frames in one image (motion inspection)."""
    from PIL import Image, ImageDraw
    Scene = load_scene(spec)
    sc = Scene()
    n = max(2, n)
    ts = [sc.duration * i / (n - 1) * 0.999 for i in range(n)]
    frames = [Image.fromarray(sc.frame_array(t, scale=1.0)).resize(
        (int(1920 * scale), int(1080 * scale)), Image.LANCZOS) for t in ts]
    w, h = frames[0].size
    rows = (n + cols - 1) // cols
    pad = 8
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad, rows * h + (rows + 1) * pad), (8, 12, 18))
    d = ImageDraw.Draw(sheet)
    for i, (im, t) in enumerate(zip(frames, ts)):
        r, c = divmod(i, cols)
        x, y = pad + c * (w + pad), pad + r * (h + pad)
        sheet.paste(im, (x, y))
        d.text((x + 8, y + 6), f"t={t:5.2f}s", fill=(120, 220, 240))
    os.makedirs("out/sheets", exist_ok=True)
    p = f"out/sheets/{sc.name}_sheet.png"
    sheet.save(p)
    print("  ->", p)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["preview", "scene", "stills", "sheet", "film", "audio"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--fresh", action="store_true", help="clear cached frames first")
    a = ap.parse_args()

    if a.cmd == "preview":
        cmd_preview(a.args[0], float(a.args[1]) if len(a.args) > 1 else 10.0,
                    scale=a.scale or 0.5, fps=a.fps)
    elif a.cmd == "scene":
        cmd_scene(a.args[0], scale=a.scale or 1.0, fps=a.fps, crf=a.crf, fresh=a.fresh)
    elif a.cmd == "stills":
        cmd_stills(a.args[0], *a.args[1:])
    elif a.cmd == "sheet":
        cmd_sheet(a.args[0], int(a.args[1]) if len(a.args) > 1 else 12,
                  scale=a.scale or 0.34)
    elif a.cmd == "audio":
        from engine.film import load_all
        from engine.narration import build_narration, check_fit
        classes = load_all()
        total = sum(cls().duration for cls in classes)
        for sc, i, cd, wd, ok in check_fit(classes):
            flag = "ok" if ok else "FIT WARNING"
            print(f"  {sc:24} cue {i}: voice {cd:5.2f}s in window {wd:5.2f}s  {flag}")
        build_narration(classes, total)
    elif a.cmd == "film":
        from engine.film import build_film
        build_film(fps=a.fps, scale=a.scale or 1.0, crf=a.crf)


if __name__ == "__main__":
    main()
