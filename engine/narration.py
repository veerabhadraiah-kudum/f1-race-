"""
Narration bed.

Two modes:

* **Voice-over** — if `assets/audio/clips/<scene>.wav` exists (one file per
  scene, or one per cue with `_c1`, `_c2` suffixes), it is placed at the scene's
  start time and mixed with a light bed.  This is the production path: record or
  synthesise the lines, drop them in, re-run `python build.py audio`.
* **Sync reference** — with no clips, the bed becomes a quiet *timecode track*:
  a soft tick at every second and a marker tone on every caption cue.  It is
  audible in the preview so picture/sound sync can be verified directly, and it
  documents exactly where each line belongs.

`timeline.json` is written either way: it is what the caption system and the
scene beats are validated against.
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np

from . import audio as A

CLIPS = os.path.join(A.AUDIO_DIR, "clips")


def _find_clip(scene: str, idx: int) -> str | None:
    for ext in (".wav", ".mp3", ".m4a", ".aac", ".flac"):
        p = os.path.join(CLIPS, f"{scene}_c{idx}{ext}")
        if os.path.exists(p):
            return p
    return None


def check_fit(classes) -> list[tuple]:
    """
    QA gate: every voice clip must fit inside the on-screen window it narrates.
    Returns [(scene, cue, clip_len, window, ok)].
    """
    out = []
    for cls in classes:
        sc = cls()
        for i, c in enumerate(sc.cues):
            f = _find_clip(sc.name, i + 1)
            if not f:
                out.append((sc.name, i + 1, 0.0, c.dur, False))
                continue
            dur = A.probe_duration(f)
            out.append((sc.name, i + 1, round(dur, 2), round(c.dur, 2), dur <= c.dur - 0.1))
    return out


def scene_cues(cls) -> list[dict]:
    """Cue windows for a scene, with the lead-in the renderer actually uses."""
    sc = cls()
    return [
        {"t_in": c.t_in, "t_out": c.t_out, "text": c.text}
        for c in sc.cues
    ]


def build_timeline(classes, fade: float = 0.55) -> dict:
    """
    Scene start times **as they land in the assembled film**.

    The film joins scenes with cross-dissolves, and a dissolve shortens the
    timeline by its own duration: scene k really starts at
    sum(durations[:k]) - k*fade. Narration is placed against that corrected
    clock, otherwise every scene after the first speaks ahead of its picture.
    """
    scenes = []
    t = 0.0
    for k, cls in enumerate(classes):
        sc = cls()
        cues = scene_cues(cls)
        scenes.append({
            "name": sc.name,
            "title": sc.title,
            "start": round(t, 3),
            "duration": round(sc.duration, 3),
            "cues": [
                {"t_in": round(t + c["t_in"], 3), "t_out": round(t + c["t_out"], 3),
                 "text": c["text"]}
                for c in cues
            ],
        })
        t += sc.duration
        t -= fade if k < len(classes) - 1 else 0.0
    return {"version": 1, "scenes": scenes, "total": round(t, 3), "fade": fade}


def build_narration(classes, total: float | None = None) -> str | None:
    """
    Produce the full-length narration wav for the film.
    Returns the path (always produced — the reference track stands in when no
    voice clips exist, so the film is never silent by accident).
    """
    tl = build_timeline(classes)
    A.save_timeline(tl)
    if total is not None:
        tl["total"] = total
    total = tl["total"]
    n = int(total * A.SR)
    voice = np.zeros(n, dtype=np.float32)
    have_voice = False

    for entry in tl["scenes"]:
        name = entry["name"]
        start = entry["start"]
        per_cue = sorted(glob.glob(os.path.join(CLIPS, f"{name}_c*.wav")) +
                          glob.glob(os.path.join(CLIPS, f"{name}_c*.mp3")))
        whole = os.path.join(CLIPS, f"{name}.wav")
        if per_cue:
            for i, c in enumerate(entry["cues"]):
                f = _find_clip(name, i + 1)
                if f:
                    clip = A.fade(A.load_clip(f), 0.01, 0.06)
                    A.place(voice, clip, c["t_in"])
                    have_voice = True
        elif os.path.exists(whole):
            clip = A.fade(A.load_clip(whole), 0.01, 0.06)
            A.place(voice, clip, start + 0.15)
            have_voice = True

    # sync reference: always available, mixed low
    cues_flat = [c for e in tl["scenes"] for c in e["cues"]]
    ref = A.make_reference(total, cues_flat, amp=0.05 if have_voice else 0.10)

    if have_voice:
        mix = A.mix_final([voice, ref * 0.35])
    else:
        mix = A.mix_final([ref])
    mix = A.normalize(mix, 0.82)
    out = os.path.join(A.AUDIO_DIR, "narration.wav")
    A.write_wav(out, mix)
    print(f"  narration: {'voice + ' if have_voice else ''}sync reference "
          f"({total:.1f}s, {A.loudness(mix):.1f} dBFS RMS) -> {out}")
    return out


def add_silence_pad(path: str, seconds: float = 0.4):
    a, sr = A.read_wav(path)
    pad = np.zeros(int(seconds * sr), dtype=np.float32)
    A.write_wav(path, np.concatenate([a, pad]), sr)
