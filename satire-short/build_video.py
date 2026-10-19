#!/usr/bin/env python3
"""Builds the 9:16 satirical short "AP Politics Roast".

Pipeline
  1. clean + compress the Telugu VO clips (ffmpeg), measure durations
  2. synthesise an original music bed + SFX with numpy
  3. render 1080x1920 frames with PIL (Ken Burns, animated captions)
  4. stream raw RGB frames into ffmpeg, mux with the mixed audio

Usage:
    python build_video.py            # full render -> out/ap_politics_roast.mp4
    python build_video.py --stills   # write a few preview stills only
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import imageio_ffmpeg
from textutil import Shaper, wrap_lines, latin_block, text_layer

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
AUDIO = ROOT / "audio"
BUILD = ROOT / "build"
OUT = ROOT / "video"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS, SR = 1080, 1920, 30, 48000
SAFE = 64

TE_BOLD = str(FONTS / "NotoSansTelugu-Bold.ttf")
TE_XBOLD = str(FONTS / "NotoSansTelugu-ExtraBold.ttf")
ANTON = str(FONTS / "Anton-Regular.ttf")
BEBAS = str(FONTS / "BebasNeue-Regular.ttf")

YELLOW = (255, 212, 0, 255)
WHITE = (255, 255, 255, 255)
INK = (12, 14, 20, 255)

# --------------------------------------------------------------------------
# script
# --------------------------------------------------------------------------
SCENES = [
    dict(kind="title", art="scene1_confrontation.png", dur=3.0,
         te="ఏపీ రాజకీయ రోస్ట్",
         en="AP POLITICS ROAST",
         kicker="SEASON 1  •  EPISODE 01",
         sub="STARRING: CBN, LOKESH & THE WHOLE CIRCUS\nSATIRE • NO PARTY AFFILIATION",
         vo=None),
    dict(kind="scene", art="scene1_confrontation.png", vo="vo_s1.mp3",
         tag="POV: ANY AP POLICE STATION, 11 PM",
         te="రౌడీయిజం కాదు… రోజువారీ వ్యాయామం!",
         en="FILE A CASE. COUNTER-FILE. CALL IT CARDIO."),
    dict(kind="scene", art="scene2_yatra_app.png", vo="vo_s2.mp3",
         tag="MEANWHILE, ON THE PADAYATRA",
         te="విజన్ 2020 నుంచి 2047 వరకు… నడక ఆగలేదు!",
         en="CBN: WALKING SINCE VISION 2020. LOKESH: ALREADY A TWITTER MARATHON."),
    dict(kind="scene", art="scene3_voter_chappal.png", vo="vo_s3.mp3",
         tag="SAME DIALOGUE. NEW SHIRT.",
         te="రౌడీ కాదు… ఇన్ఫ్లుయెన్సర్!",
         en="ROWDEYISM ISN'T FEAR. IT'S A BRAND. CHECK THE MIRROR, SIR."),
    dict(kind="scene", art="scene4_ballot.png", vo="vo_s4.mp3",
         tag="THE FINAL BOSS",
         te="ఓటే అసలైన రౌడీ!",
         en="PADAYATRAS, APPS, PROMISES — THE VOTER STILL HOLDS THE SLIPPER."),
    dict(kind="outro", art="scene4_ballot.png", dur=3.4,
         te="నవ్వు పోయింది… ఓటు మిగిలింది.",
         en="THE JOKE IS ON THEM. THE VOTE IS YOURS.",
         kicker="THE TAKEAWAY",
         sub="SATIRE ONLY • NO PARTY AFFILIATION\nAI CARTOONS • MADE AS A PARODY", vo=None),
]

VO_CHAIN = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
    "areverse,"
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
    "areverse,"
    "atempo=1.10,"
    "highpass=f=85,"
    "equalizer=f=190:t=q:w=1.0:g=2.5,"
    "equalizer=f=3100:t=q:w=1.2:g=2.5,"
    "acompressor=threshold=-18dB:ratio=3.2:attack=6:release=150:makeup=2,"
    "alimiter=limit=0.97"
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def run(cmd: list[str]) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd[:4])}...\n{p.stderr[-1500:]}")
    return p


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"expected 16-bit wav, got {sw * 8} bit")
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


def save_wav(path: Path, data: np.ndarray, sr: int = SR) -> None:
    d = np.clip(data, -1.0, 1.0)
    pcm = (d * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    xi = np.linspace(0, len(x) - 1, n_out, dtype=np.float64)
    return np.interp(xi, np.arange(len(x)), x).astype(np.float32)


def one_pole_lp(x: np.ndarray, cutoff: float, sr: int) -> np.ndarray:
    """Cheap block-wise one-pole low-pass (vectorised in chunks)."""
    a = math.exp(-2.0 * math.pi * cutoff / sr)
    y = np.empty_like(x)
    acc = 0.0
    # 2048-sample chunks keep the python loop short
    for i in range(0, len(x), 2048):
        seg = x[i:i + 2048]
        out = np.empty_like(seg)
        for j in range(len(seg)):
            acc = a * acc + (1 - a) * seg[j]
            out[j] = acc
        y[i:i + len(seg)] = out
    return y


def env_follow(x: np.ndarray, attack=0.01, release=0.25, sr=SR):
    a_a = math.exp(-1.0 / (attack * sr))
    a_r = math.exp(-1.0 / (release * sr))
    env = np.zeros_like(x)
    e = 0.0
    absx = np.abs(x)
    for i in range(len(x)):
        a = a_a if absx[i] > e else a_r
        e = a * e + (1 - a) * absx[i]
        env[i] = e
    return env


def ease_out_back(u: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def fit_size(font_path: str, text: str, size: int, max_w: float, step: int = 2) -> Shaper:
    s = Shaper(font_path, size)
    while s.width(text) > max_w and size > 20:
        size -= step
        s = Shaper(font_path, size)
    return s


def with_alpha(img: Image.Image, k: float) -> Image.Image:
    if k >= 0.999:
        return img
    out = img.copy()
    a = np.asarray(out.getchannel("A"), dtype=np.float32) * max(0.0, min(1.0, k))
    out.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
    return out


def scaled(img: Image.Image, k: float) -> Image.Image:
    if abs(k - 1.0) < 0.004:
        return img
    return img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


# --------------------------------------------------------------------------
# art preparation
# --------------------------------------------------------------------------
def load_art(name: str) -> Image.Image:
    im = Image.open(ROOT / "assets" / name).convert("RGB")
    # crop to 9:16, biased slightly to the top so faces stay in frame
    target = W / H
    w, h = im.size
    if w / h > target:
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        top = int((h - nh) * 0.32)
        im = im.crop((0, top, w, top + nh))
    im = im.resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=95, threshold=2))
    return im


def scrim(im: Image.Image, *, top=205, start=1040, full=1620, strength=238) -> Image.Image:
    """Darken top+bottom for text legibility."""
    im = im.convert("RGBA")
    grad = Image.new("L", (1, H), 0)
    px = grad.load()
    for y in range(H):
        if y < 190:
            a = int(top * (1 - y / 190) ** 1.4)
        elif y < start:
            a = 0
        else:
            a = int(strength * min(1.0, ((y - start) / (full - start)) ** 1.25))
        px[0, y] = a
    shade = Image.new("RGBA", (W, H), (6, 8, 14, 255))
    shade.putalpha(grad.resize((W, H)))
    im.alpha_composite(shade)
    # vignette
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.35, -H * 0.18, W * 1.35, H * 1.18], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(180))
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    vig.putalpha(Image.eval(v, lambda p: int((255 - p) * 0.55)))
    im.alpha_composite(vig)
    return im


def blurred_bg(name: str) -> Image.Image:
    im = load_art(name)
    im = im.resize((W // 6, H // 6), Image.LANCZOS).filter(ImageFilter.GaussianBlur(9))
    im = im.resize((W, H), Image.BICUBIC)
    im = Image.eval(im, lambda p: int(p * 0.42))
    return im.convert("RGBA")


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------
def process_vo(name: str) -> tuple[np.ndarray, float]:
    src = AUDIO / name
    dst = BUILD / (Path(name).stem + "_p.wav")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
         "-af", VO_CHAIN, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
    a, sr = load_audio(dst)
    return resample(a, sr, SR), len(a) / sr


def synth_music(total: float) -> np.ndarray:
    n = int(total * SR)
    out = np.zeros(n, dtype=np.float32)
    bpm = 92.0
    beat = 60.0 / bpm
    bar = beat * 4

    def add(buf, start, sig, gain=1.0):
        i = int(start * SR)
        if i >= len(buf) or i < 0:
            return
        j = min(len(buf), i + len(sig))
        buf[i:j] += sig[: j - i] * gain

    def kick(dur=0.34):
        t = np.arange(int(dur * SR)) / SR
        f = 118 * np.exp(-t * 26) + 46
        ph = 2 * np.pi * np.cumsum(f) / SR
        env = np.exp(-t * 9)
        sig = np.sin(ph) * env
        click = np.random.default_rng(3).normal(0, 1, len(t)) * np.exp(-t * 260) * 0.35
        return (sig + click).astype(np.float32)

    def clap(dur=0.22):
        t = np.arange(int(dur * SR)) / SR
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 1, len(t))
        hp = noise - one_pole_lp(noise, 1500, SR)
        env = np.exp(-t * 26) * (1 + 0.6 * np.exp(-((t - 0.012) ** 2) / 2e-6))
        return (hp * env * 0.55).astype(np.float32)

    def hat(dur=0.07):
        t = np.arange(int(dur * SR)) / SR
        rng = np.random.default_rng(11)
        noise = rng.normal(0, 1, len(t))
        hp = noise - one_pole_lp(noise, 5200, SR)
        return (hp * np.exp(-t * 62) * 0.32).astype(np.float32)

    def bass(freq, dur=0.42):
        t = np.arange(int(dur * SR)) / SR
        ph = 2 * np.pi * freq * t
        sig = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.18 * np.sin(3 * ph))
        sig = np.tanh(1.6 * sig)
        env = np.exp(-t * 3.4) * np.clip(t / 0.012, 0, 1)
        return (sig * env * 0.42).astype(np.float32)

    def pluck(freq, dur=0.55):
        t = np.arange(int(dur * SR)) / SR
        sig = (np.sin(2 * np.pi * freq * t) * 0.7
               + np.sin(4 * np.pi * freq * t) * 0.22
               + np.sin(6 * np.pi * freq * t) * 0.08)
        env = np.exp(-t * 6.5) * np.clip(t / 0.006, 0, 1)
        return (sig * env).astype(np.float32)

    def bell(freq, dur=0.9):
        t = np.arange(int(dur * SR)) / SR
        sig = (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2.01 * t)
               + 0.25 * np.sin(2 * np.pi * freq * 3.02 * t))
        return (sig * np.exp(-t * 4.2) * 0.3).astype(np.float32)

    chords = [(110.00, [220.00, 261.63, 329.63]),   # Am
              (87.31, [174.61, 220.00, 261.63]),    # F
              (130.81, [196.00, 261.63, 329.63]),   # C
              (98.00, [196.00, 246.94, 293.66])]    # G
    melody = [440.0, 523.25, 659.25, 587.33, 523.25, 440.0, 392.0, 440.0]

    n_bars = int(math.ceil(total / bar)) + 1
    for b in range(n_bars):
        t0 = b * bar
        root, chord = chords[b % 4]
        # drums
        add(out, t0 + 0 * beat, kick(), 0.95)
        add(out, t0 + 2.5 * beat, kick(), 0.75)
        add(out, t0 + 1 * beat, clap(), 0.55)
        add(out, t0 + 3 * beat, clap(), 0.55)
        for k in range(8):
            add(out, t0 + k * beat / 2, hat(), 0.5 if k % 2 else 0.75)
        # bass eighths
        for k, off in enumerate([0, 0.75, 1.5, 2, 2.75, 3.5]):
            add(out, t0 + off * beat, bass(root * (2 if k % 2 else 1)), 0.5)
        # sparse pluck arpeggio in the second half of the bar
        for k, off in enumerate([2.0, 2.5, 3.0, 3.5]):
            add(out, t0 + off * beat, pluck(chord[k % 3] * 2), 0.18)
        if b % 4 == 3:
            add(out, t0 + 3.5 * beat, bell(melody[b % len(melody)]), 0.5)

    # gentle low-pass + stereo-ish width via a short delay
    out = 0.65 * out + 0.35 * one_pole_lp(out, 5200, SR)
    delay = int(0.011 * SR)
    wide = out.copy()
    wide[delay:] += out[:-delay] * 0.22
    out = wide / max(1.0, np.max(np.abs(wide)) * 1.05)
    return out.astype(np.float32)


def whoosh(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(21)
    noise = rng.normal(0, 1, n)
    # sweep the "cutoff" by blending three fixed bands over time
    lo = one_pole_lp(noise, 700, SR)
    mid = one_pole_lp(noise, 2200, SR) - one_pole_lp(noise, 700, SR)
    hi = noise - one_pole_lp(noise, 4200, SR)
    w = np.clip(t / dur, 0, 1)
    sig = mid * (1 - np.abs(w - 0.55) * 1.4) + hi * w * 0.8 + lo * (1 - w) * 0.5
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return (sig * env * 0.5).astype(np.float32)


def sting(dur=0.85):
    t = np.arange(int(dur * SR)) / SR
    sig = (np.sin(2 * np.pi * 110 * t) * np.exp(-t * 5)
           + np.sin(2 * np.pi * 82.4 * t) * np.exp(-t * 3.2) * 0.8
           + np.sin(2 * np.pi * 164.8 * t) * np.exp(-t * 9) * 0.3)
    n = len(t)
    rng = np.random.default_rng(5)
    imp = rng.normal(0, 1, n) * np.exp(-t * 40) * 0.25
    return (np.tanh(1.4 * (sig + imp)) * 0.55).astype(np.float32)


def ding(dur=0.7):
    t = np.arange(int(dur * SR)) / SR
    s = (np.sin(2 * np.pi * 1318.5 * t) + 0.4 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 7)
    return (s * 0.22).astype(np.float32)


# --------------------------------------------------------------------------
# scene layout
# --------------------------------------------------------------------------
def build_scene_assets(sc: dict, story_no: int, hero=False):
    """Pre-renders every static layer for one scene."""
    if sc["kind"] in ("title", "outro"):
        art = load_art(sc["art"])
        art = scrim(art, top=215, start=620, full=1420, strength=248)
        assets = {"art": art, "idx": story_no}
        max_w = W - 2 * SAFE
        te_size = 118 if sc["kind"] == "title" else 88
        shp = fit_size(TE_XBOLD, sc["te"], te_size, max_w)
        te_lines = wrap_lines(shp, sc["te"], max_w)
        assets["te"] = [shp.render(l, fill=WHITE, stroke=INK, stroke_w=8) for l in te_lines]

        # kicker pill
        kf = ImageFont.truetype(BEBAS, 36)
        ktxt = sc["kicker"].upper()
        kw = kf.getlength(ktxt)
        pill = Image.new("RGBA", (int(kw) + 62, 64), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], radius=32,
                             fill=(255, 212, 0, 255))
        pd.text(((pill.width - kw) / 2, 11), ktxt, font=kf, fill=INK)
        assets["kicker"] = pill

        en_font = ImageFont.truetype(ANTON, 80 if sc["kind"] == "title" else 60)
        en_lines = latin_block(en_font, sc["en"], max_w - 30)
        assets["en"] = text_layer(en_lines, en_font, YELLOW, 4, INK, spacing=10)
        sub_font = ImageFont.truetype(BEBAS, 34)
        assets["sub"] = text_layer(latin_block(sub_font, sc["sub"].replace("\n", "  |  "),
                                               max_w - 30),
                                   sub_font, (255, 255, 255, 210), 2, (0, 0, 0, 220), spacing=6)
        return assets

    art = scrim(load_art(sc["art"]))
    assets = {"art": art, "idx": story_no}

    # -- regular scene ---------------------------------------------------
    tag_font = ImageFont.truetype(ANTON, 34)
    tag_txt = sc["tag"].upper()
    tag_w = tag_font.getlength(tag_txt)
    pill = Image.new("RGBA", (int(tag_w) + 64, 66), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], radius=33, fill=YELLOW)
    d.text(((pill.width - tag_w) / 2, 12), tag_txt, font=tag_font, fill=INK)
    assets["tag"] = pill

    te_size = 68
    shp = fit_size(TE_BOLD, sc["te"], te_size, W - 2 * SAFE - 30)
    lines = wrap_lines(shp, sc["te"], W - 2 * SAFE)
    # widen toward a balanced 2-line block
    while len(lines) > 2:
        te_size -= 4
        shp = Shaper(TE_BOLD, te_size)
        lines = wrap_lines(shp, sc["te"], W - 2 * SAFE)
    assets["te"] = [shp.render(l, fill=WHITE, stroke=INK, stroke_w=6) for l in lines]

    en_font = ImageFont.truetype(ANTON, 50)
    en_lines = latin_block(en_font, sc["en"], W - 2 * SAFE)
    while len(en_lines) > 3:
        en_font = ImageFont.truetype(ANTON, en_font.size - 3)
        en_lines = latin_block(en_font, sc["en"], W - 2 * SAFE)
    assets["en"] = text_layer(en_lines, en_font, YELLOW, 3, INK, spacing=8)

    # header + footer
    head = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    hf = ImageFont.truetype(ANTON, 34)
    wordmark = "AP POLITICS ROAST"
    ww = hf.getlength(wordmark)
    hd.rounded_rectangle([SAFE - 16, 34, SAFE + ww + 22, 96], radius=20,
                         fill=(10, 12, 18, 170))
    hd.text((SAFE, 46), wordmark, font=hf, fill=(255, 255, 255, 240))
    chip = ImageFont.truetype(BEBAS, 34)
    chip_txt = "SATIRE • PARODY"
    cw = chip.getlength(chip_txt)
    hd.rounded_rectangle([W - SAFE - cw - 40, 40, W - SAFE, 92], radius=26,
                         fill=(255, 212, 0, 255))
    hd.text((W - SAFE - cw - 20, 47), chip_txt, font=chip, fill=(12, 14, 20, 255))
    assets["head"] = head

    foot = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    fd = ImageDraw.Draw(foot)
    ff = ImageFont.truetype(BEBAS, 30)
    txt = "SATIRE  •  NO PARTY AFFILIATION"
    fd.text(((W - ff.getlength(txt)) / 2, 62), txt, font=ff, fill=(255, 255, 255, 150))
    rr = 5
    total_w = 4 * (rr * 2) + 3 * 14
    x0 = (W - total_w) / 2
    for i in range(4):
        cx = x0 + i * (rr * 2 + 14)
        col = YELLOW if i == story_no - 1 else (255, 255, 255, 80)
        fd.ellipse([cx, 30, cx + rr * 2, 30 + rr * 2], fill=col)
    assets["foot"] = foot
    return assets


def stack_positions(assets, kind):
    """Returns a dict of (x, y) anchors for the bottom text block."""
    te_imgs, en_img = assets["te"], assets["en"]
    gap_te = 12
    te_h = sum(i.height for i in te_imgs) + gap_te * (len(te_imgs) - 1)
    gap = 30
    tag_h = assets["tag"].height if "tag" in assets else 0
    total = tag_h + (24 if tag_h else 0) + te_h + gap + en_img.height
    y = 1700 - total
    pos = {}
    if tag_h:
        pos["tag"] = ((W - assets["tag"].width) // 2, y)
        y += tag_h + 24
    pos["te"] = []
    for img in te_imgs:
        pos["te"].append(((W - img.width) // 2, y))
        y += img.height + gap_te
    y += gap - gap_te
    pos["en"] = ((W - en_img.width) // 2, y)
    return pos


# --------------------------------------------------------------------------
# frame renderer
# --------------------------------------------------------------------------
def ken_burns(base: Image.Image, u: float, direction: int) -> Image.Image:
    z = 1.02 + 0.085 * (u if direction > 0 else 1 - u)
    cw, ch = W / z, H / z
    max_dx = (W - cw) / 2
    max_dy = (H - ch) / 2
    cx = W / 2 + max_dx * (0.6 if direction > 0 else -0.6) * (u - 0.5) * 2 * 0.6
    cy = H / 2 + max_dy * 0.5 * (u - 0.5) * 2 * 0.45
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return base.resize((W, H), Image.BILINEAR, box=box)


def render_scene_frames(sc: dict, assets: dict, duration: float, t0: float):
    n = int(round(duration * FPS))
    kind = sc["kind"]
    dirn = 1 if assets["idx"] % 2 else -1
    punch = 0.60 * duration

    if kind in ("title", "outro"):
        te_imgs, en_img, sub_img = assets["te"], assets["en"], assets["sub"]
        kick = assets["kicker"]
        te_h = sum(i.height for i in te_imgs) + 16 * (len(te_imgs) - 1)
        block_h = kick.height + 34 + te_h + 34 + en_img.height + 34 + sub_img.height
        y0 = 1680 - block_h
        for f in range(n):
            u = f / max(1, n - 1)
            frame = ken_burns(assets["art"], u, dirn).convert("RGBA")
            y = y0
            a = np.clip((f - 3) / 9.0, 0, 1)
            im = with_alpha(kick, a)
            frame.alpha_composite(im, ((W - im.width) // 2, int(y + 18 * (1 - a))))
            y += kick.height + 34
            for i, img in enumerate(te_imgs):
                a = np.clip((f - 7 - i * 3) / 10.0, 0, 1)
                k = 0.94 + 0.06 * ease_out_back(a) if a < 1 else 1.0
                im = with_alpha(scaled(img, k), a)
                frame.alpha_composite(im, (int((W - im.width) / 2),
                                           int(y + (img.height - im.height) / 2 + 26 * (1 - a))))
                y += img.height + 16
            y += 34
            a = np.clip((f - 16) / 10.0, 0, 1)
            im = with_alpha(en_img, a)
            frame.alpha_composite(im, (int((W - im.width) / 2), int(y + 20 * (1 - a))))
            y += en_img.height + 34
            a2 = np.clip((f - 24) / 12.0, 0, 1)
            im2 = with_alpha(sub_img, a2)
            frame.alpha_composite(im2, (int((W - im2.width) / 2), int(y)))
            yield np.asarray(frame.convert("RGB"))

    else:
        art = assets["art"]
        pos = stack_positions(assets, kind)
        for f in range(n):
            u = f / max(1, n - 1)
            frame = ken_burns(art, u, dirn).convert("RGBA")
            t = f / FPS

            # punch-in shake + flash of light on the sting
            if punch - 0.10 <= t <= punch + 0.55:
                k = (t - (punch - 0.10)) / 0.65
                amp = 10 * (1 - k)
                dx = int(round(amp * math.sin(f * 2.7)))
                dy = int(round(amp * math.cos(f * 3.9)))
                if dx or dy:
                    frame = frame.transform(
                        frame.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy),
                        resample=Image.BILINEAR)
            frame.alpha_composite(assets["head"], (0, 0))

            # tag pill
            tag = assets["tag"]
            a = np.clip((t - 0.30) / 0.30, 0, 1)
            if a > 0:
                dy = int(26 * (1 - ease_out_back(min(1.0, a * 1.3))))
                frame.alpha_composite(with_alpha(tag, a), (pos["tag"][0], pos["tag"][1] + dy))

            # Telugu lines
            for i, (img, (x, y)) in enumerate(zip(assets["te"], pos["te"])):
                a = np.clip((t - 0.45 - i * 0.11) / 0.32, 0, 1)
                if a <= 0:
                    continue
                dy = int(44 * (1 - ease_out_back(a)))
                frame.alpha_composite(with_alpha(img, a), (x, y + dy))

            # English caption
            en = assets["en"]
            a = np.clip((t - 0.95) / 0.30, 0, 1)
            if a > 0:
                k = 0.90 + 0.10 * ease_out_back(a)
                im = scaled(en, k)
                im = with_alpha(im, a)
                frame.alpha_composite(im, (int((W - im.width) / 2),
                                           int(pos["en"][1] + (en.height - im.height) / 2)))

            # footer + progress
            a = np.clip((t - 1.1) / 0.4, 0, 1)
            frame.alpha_composite(with_alpha(assets["foot"], a), (0, H - 120))

            # opening flash for a hard, punchy cut
            if f < 3:
                flash = Image.new("RGBA", (W, H), (255, 255, 255, int(70 * (1 - f / 3))))
                frame.alpha_composite(flash)

            yield np.asarray(frame.convert("RGB"))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> None:
    BUILD.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)

    # ---- VO -----------------------------------------------------------
    vo_data, durations = {}, {}
    for sc in SCENES:
        if sc.get("vo"):
            a, d = process_vo(sc["vo"])
            vo_data[sc["vo"]] = a
            durations[sc["vo"]] = d
            print(f"  VO {sc['vo']}: {d:.2f}s")

    # ---- timeline -----------------------------------------------------
    t = 0.0
    timeline = []
    for sc in SCENES:
        if sc["kind"] == "scene":
            dur = durations[sc["vo"]] + 1.05
        else:
            dur = sc["dur"]
        timeline.append(dict(scene=sc, start=t, dur=dur))
        t += dur
    total = t
    print(f"  total duration: {total:.2f}s  ({total * FPS:.0f} frames)")

    # ---- audio --------------------------------------------------------
    n = int(total * SR)
    mix = np.zeros(n, dtype=np.float32)
    music = synth_music(total)

    voiced = np.zeros(n, dtype=np.float32)
    sfx = np.zeros(n, dtype=np.float32)

    def place(buf, start, sig, gain=1.0):
        i = int(start * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        buf[i:j] += sig[: j - i] * gain

    # whoosh on every cut, sting on every punchline
    for i, item in enumerate(timeline):
        sc = item["scene"]
        if i > 0:
            place(sfx, max(0, item["start"] - 0.22), whoosh(0.55), 0.55)
        if sc["kind"] == "scene":
            vstart = item["start"] + 0.45
            place(voiced, vstart, vo_data[sc["vo"]], 1.0)
            punch = vstart + durations[sc["vo"]] * 0.60
            place(sfx, punch, sting(), 0.35)
            if i % 2 == 1:
                place(sfx, vstart + 0.05, ding(), 0.5)

    # duck the music under the voice
    env = env_follow(voiced, 0.004, 0.30)
    duck = np.clip(env / 0.05, 0, 1)
    duck = one_pole_lp(duck.astype(np.float32), 6.0, SR)
    music = music * (1.0 - 0.62 * duck)

    mix = voiced * 0.96 + music * 0.30 + sfx
    # gentle bus compression + soft clip
    mix = np.tanh(mix * 1.25) / math.tanh(1.25)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.93
    # 0.4s fade out
    fo = int(0.5 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    save_wav(BUILD / "master.wav", mix)
    print("  audio mixed")

    # ---- frames -------------------------------------------------------
    if "--stills" in sys.argv:
        story_no = 0
        for i, item in enumerate(timeline[:5]):
            sc = item["scene"]
            if sc["kind"] == "scene":
                story_no += 1
            assets = build_scene_assets(sc, story_no, sc["kind"] != "scene")
            total_f = int(round(item["dur"] * FPS))
            want = min(total_f - 1, int(total_f * 0.75))
            for idx, fr in enumerate(render_scene_frames(sc, assets, item["dur"], item["start"])):
                if idx == want:
                    Image.fromarray(fr).save(BUILD / f"still_{i}_{sc['kind']}.jpg", quality=92)
                    break
            print("  still", sc["kind"])
        return

    video_tmp = BUILD / "video_only.mp4"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
           "-g", str(FPS * 2), "-movflags", "+faststart", str(video_tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    written = 0
    story_no = 0
    for i, item in enumerate(timeline):
        sc = item["scene"]
        if sc["kind"] == "scene":
            story_no += 1
        assets = build_scene_assets(sc, story_no, sc["kind"] != "scene")
        cnt = 0
        for fr in render_scene_frames(sc, assets, item["dur"], item["start"]):
            proc.stdin.write(fr.astype(np.uint8).tobytes())
            written += 1
            cnt += 1
        print(f"  scene {i + 1}/{len(timeline)} ({sc['kind']}) -> {cnt} frames")
    proc.stdin.close()
    err = proc.stderr.read().decode()[-2000:]
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encode failed:\n" + err)
    print(f"  encoded {written} frames")

    final = OUT / "ap_politics_roast.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video_tmp), "-i", str(BUILD / "master.wav"),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", str(final)])
    print("  wrote", final, f"{final.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
