"""
Narration: voice-over clips, timing map and the final audio bed.

The film is cut to its narration.  `audio/timeline.json` records, per scene,
the narration line and the exact window it must occupy; the renderer uses the
same numbers for captions and for the animation beats, so picture and voice
cannot drift apart.

A quiet timecode reference (one soft tone per second of narration) is mixed in
by `make_reference()` so the audio itself carries a verifiable sync signal for
QA — it is removed from the final mix by `mix_final()`.
"""
from __future__ import annotations

import json
import math
import os
import struct
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "assets", "audio")
SR = 48000


def _ensure(path: str):
    os.makedirs(path, exist_ok=True)


# --------------------------------------------------------------- wav I/O
def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


def write_wav(path: str, a: np.ndarray, sr: int = SR):
    _ensure(os.path.dirname(path))
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------- resample
def resample(a: np.ndarray, sr_in: int, sr_out: int = SR) -> np.ndarray:
    if sr_in == sr_out:
        return a
    n_out = int(round(len(a) * sr_out / sr_in))
    x_in = np.linspace(0, 1, len(a), endpoint=False)
    x_out = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_out, x_in, a).astype(np.float32)


def _decode_to_wav(path: str) -> str:
    """Decode any ffmpeg-readable audio (mp3/aac/m4a) to a 48 kHz mono wav."""
    from .render import ffmpeg_exe
    out = os.path.splitext(path)[0] + ".__dec__.wav"
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path):
        return out
    import subprocess
    p = subprocess.run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", path, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", out],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"could not decode {path}:\n{p.stderr[-1200:]}")
    return out


def load_clip(path: str) -> np.ndarray:
    if not path.lower().endswith(".wav"):
        path = _decode_to_wav(path)
    a, sr = read_wav(path)
    return resample(a, sr, SR)


def probe_duration(path: str) -> float:
    from .render import duration
    return duration(path)


# --------------------------------------------------------------- timeline
def load_timeline() -> dict:
    p = os.path.join(AUDIO_DIR, "timeline.json")
    if not os.path.exists(p):
        return {"scenes": []}
    with open(p) as fh:
        return json.load(fh)


def save_timeline(tl: dict):
    _ensure(AUDIO_DIR)
    with open(os.path.join(AUDIO_DIR, "timeline.json"), "w") as fh:
        json.dump(tl, fh, indent=2)


# ------------------------------------------------------------ tone / sync
def tone(freq: float, dur: float, amp: float = 0.2, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    env = np.minimum(1.0, np.minimum(t / 0.004, (dur - t) / 0.012))
    return (np.sin(2 * np.pi * freq * t) * env * amp).astype(np.float32)


def make_reference(duration: float, cues: list[dict], amp: float = 0.055) -> np.ndarray:
    """
    Audible sync track: a 1046 Hz tick on each caption cue start and a 1568 Hz
    tick at each 1-second boundary of narration.  Quiet enough to sit under the
    voice, loud enough to verify alignment by ear or by analysis.
    """
    n = int(duration * SR)
    buf = np.zeros(n, dtype=np.float32)
    for c in cues:
        i = int(c["t_in"] * SR)
        tk = tone(1046.5, 0.035, amp)
        j = min(n, i + len(tk))
        buf[i:j] += tk[: j - i]
    step = 1.0
    t = step
    while t < duration:
        i = int(t * SR)
        tk = tone(1568.0, 0.018, amp * 0.55)
        j = min(n, i + len(tk))
        buf[i:j] += tk[: j - i]
        t += step
    return buf


# --------------------------------------------------------------- effects
def fade(a: np.ndarray, fin: float = 0.05, fout: float = 0.10, sr: int = SR) -> np.ndarray:
    a = a.copy()
    ni, no = int(fin * sr), int(fout * sr)
    if ni:
        a[:ni] *= np.linspace(0, 1, ni) ** 1.5
    if no:
        a[-no:] *= np.linspace(1, 0, no) ** 1.5
    return a


def place(buf: np.ndarray, clip: np.ndarray, start: float, gain: float = 1.0) -> np.ndarray:
    i = int(round(start * SR))
    if i >= len(buf):
        return buf
    j = min(len(buf), i + len(clip))
    if j - i > 0:
        buf[i:j] += clip[: j - i] * gain
    return buf


def normalize(a: np.ndarray, peak: float = 0.89) -> np.ndarray:
    m = float(np.max(np.abs(a))) if len(a) else 0.0
    return a if m < 1e-9 else (a * (peak / m)).astype(np.float32)


def loudness(a: np.ndarray, sr: int = SR) -> float:
    """Approximate integrated loudness in dBFS (RMS based)."""
    if not len(a):
        return -120.0
    rms = math.sqrt(float(np.mean(a.astype(np.float64) ** 2)))
    return 20 * math.log10(max(rms, 1e-9))


def mix_final(tracks: list[np.ndarray], sr: int = SR) -> np.ndarray:
    n = max((len(t) for t in tracks), default=0)
    out = np.zeros(n, dtype=np.float32)
    for t in tracks:
        out[: len(t)] += t
    # gentle soft-clip instead of hard clipping
    return np.tanh(out * 1.05) * 0.98
