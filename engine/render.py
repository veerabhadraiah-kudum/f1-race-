"""
Rendering pipeline: frames -> H.264 MP4 with FFmpeg.

* `render_frames` rasterises a scene in parallel worker processes.
* `encode` muxes PNG frames to H.264 (yuv420p, BT.709, faststart) — the same
  command line a Manim or Remotion pipeline ends with.
* Audio (narration) is mixed in with a light loudness pass so dialogue sits at
  broadcast-ish levels under the music bed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Callable

import imageio_ffmpeg


def ffmpeg_exe() -> str:
    env = os.environ.get("FFMPEG_BINARY")
    if env:
        return env
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        which = shutil.which("ffmpeg")
        if which:
            return which
        raise RuntimeError("ffmpeg not found")


def ffprobe_info(path: str) -> dict:
    """Minimal media probe using ffmpeg's stderr (no ffprobe wheel available)."""
    exe = ffmpeg_exe()
    p = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True)
    return {"stderr": p.stderr}


# ----------------------------------------------------------------- frames
_SCENE_CACHE = {}


def _get_scene(scene_cls):
    """One scene instance per worker process: surfaces and TeX are expensive to
    build and cheap to reuse across frames."""
    key = id(scene_cls)
    if key not in _SCENE_CACHE:
        _SCENE_CACHE[key] = scene_cls()
    return _SCENE_CACHE[key]


def _render_one(args):
    scene_cls, t, out_path, scale = args
    scene = _get_scene(scene_cls)
    img = scene.frame_array(t, scale=scale)
    from PIL import Image
    Image.fromarray(img).save(out_path, compress_level=2)
    return out_path


def render_frames(
    scene_factory: Callable[[], object],
    times: list[float],
    out_dir: str,
    scale: float = 1.0,
    workers: int | None = None,
    progress: bool = True,
    prefix: str = "f",
):
    os.makedirs(out_dir, exist_ok=True)
    workers = workers or max(1, min(4, (os.cpu_count() or 2)))
    tasks = [
        (scene_factory, t, os.path.join(out_dir, f"{prefix}{i:05d}.png"), scale)
        for i, t in enumerate(times)
    ]
    t0 = time.time()
    done = 0
    if workers == 1:
        for task in tasks:
            _render_one(task)
            done += 1
            if progress and done % 30 == 0:
                _log(done, len(tasks), t0)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for _ in ex.map(_render_one, tasks, chunksize=4):
                done += 1
                if progress and done % 30 == 0:
                    _log(done, len(tasks), t0)
    if progress:
        _log(len(tasks), len(tasks), t0)
    return tasks


def _log(done, total, t0):
    el = time.time() - t0
    rate = done / el if el > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0
    sys.stdout.write(f"\r  frames {done}/{total}  {rate:5.1f} fps  eta {eta:5.0f}s   ")
    sys.stdout.flush()


# ----------------------------------------------------------------- encode
def encode(
    frames_dir: str,
    out_path: str,
    fps: int = 30,
    crf: int = 16,
    preset: str = "slow",
    audio: str | None = None,
    audio_gain_db: float = 0.0,
    prefix: str = "f",
    threads: int | None = None,
):
    exe = ffmpeg_exe()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cmd = [
        exe, "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-framerate", str(fps), "-i", os.path.join(frames_dir, f"{prefix}%05d.png"),
    ]
    if audio:
        cmd += ["-i", audio]
    cmd += [
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
        "-x264-params", "keyint=60:min-keyint=30:ref=4",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-movflags", "+faststart",
    ]
    if threads:
        cmd += ["-threads", str(threads)]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-af", f"volume={audio_gain_db}dB" if audio_gain_db else "anull",
                "-shortest"]
    cmd += [out_path]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg encode failed:\n" + p.stderr[-4000:])
    return time.time() - t0


def mux_audio(video: str, audio: str, out: str, gain_db: float = 0.0):
    """Replace/attach an audio track without re-encoding video."""
    exe = ffmpeg_exe()
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-i", audio,
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    if gain_db:
        cmd += ["-af", f"volume={gain_db}dB"]
    cmd += ["-shortest", "-movflags", "+faststart", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg mux failed:\n" + p.stderr[-4000:])


def concat(paths: list[str], out: str):
    """Concat identical-codec MP4s with the concat demuxer (stream copy)."""
    exe = ffmpeg_exe()
    lst = out + ".txt"
    with open(lst, "w") as fh:
        for p in paths:
            fh.write(f"file '{os.path.abspath(p)}'\n")
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
           "-c", "copy", "-movflags", "+faststart", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg concat failed:\n" + p.stderr[-4000:])
    os.remove(lst)


def crossfade_concat(paths: list[str], out: str, fade: float = 0.6, fps: int = 30):
    """Concat with short cross-dissolves (re-encode; used for the final film)."""
    exe = ffmpeg_exe()
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", p]
    n = len(paths)
    if n == 1:
        shutil.copy(paths[0], out)
        return
    filt = []
    prev = "0:v"
    offset = 0.0
    for i in range(1, n):
        # duration of previous stream so far
        d = _duration(paths[i - 1])
        offset += d - fade
        outl = f"v{i}"
        filt.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={fade}:offset={max(offset,0):.3f}[{outl}]")
        prev = outl
    cmd += ["-filter_complex", ";".join(filt), "-map", f"[{prev}]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg crossfade failed:\n" + p.stderr[-4000:])


_DUR_CACHE: dict[str, float] = {}


def _duration(path: str) -> float:
    if path in _DUR_CACHE:
        return _DUR_CACHE[path]
    info = ffprobe_info(path)["stderr"]
    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info)
    d = 0.0
    if m:
        d = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    _DUR_CACHE[path] = d
    return d


def duration(path: str) -> float:
    return _duration(path)
