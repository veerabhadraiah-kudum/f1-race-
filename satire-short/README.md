# ఏపీ రాజకీయ రోస్ట్ — AP Politics Roast (v2)

A **47.7-second vertical short (1080×1920, 30 fps)** spoofing Andhra Pradesh
political theatre — the Chandrababu Naidu / Nara Lokesh double act, the
"rowdyism as a brand" image problem, and the voter who gets the last word.

Telugu voiceover · Telugu + English on-screen captions · original music bed.

> **This is satire and parody.** Characters are exaggerated caricatures made
> for comedy. Nothing here is a factual accusation about any person, and no
> hatred or violence is intended toward anyone. Not affiliated with, endorsed
> or funded by any party. The disclaimer is burned into the video.

---

## Deliverable

| File | What it is |
|---|---|
| `out/ap-politics-roast-v2.mp4` | The finished short — 1080×1920, 30 fps, H.264 + AAC, −14 LUFS, 20 MB |
| `out/cover.jpg` | 1080×1920 cover / first-frame still |
| `out/captions.srt` | Telugu + English subtitles, timed to the finished cut |
| `POST_KIT.md` | Titles, captions, hashtags, platform notes + the Jagan-episode playbook |
| `script.md` | Full script, timecodes, translations, editorial guardrails |
| `assets/` | The four cartoon scenes |
| `audio/vo_s1–s4.mp3` | The Telugu voice takes (raw) |
| `build_video.py`, `textutil.py` | The render pipeline |
| `v1_archive/` | Previous 41 s "Family Edition" cut, kept but out of git |

---

## The cut, beat by beat

| Time | Scene | On screen | What it does |
|---|---|---|---|
| 0:00–0:03 | Title card over the police-station art | ఏపీ రాజకీయ రోస్ట్ / AP POLITICS ROAST | Sets the frame: season 1, episode 1, satire only |
| 0:03–0:13 | Two leaders point at each other over a bored constable | "రౌడీయిజం కాదు… రోజువారీ వ్యాయామం!" / FILE A CASE. COUNTER-FILE. CALL IT CARDIO. | The "every day is a fresh complaint" gag |
| 0:13–0:25 | Naidu's padayatra, a giant notification bell, Lokesh on a scooter with a laptop | "విజన్ 2020 నుంచి 2047 వరకు… నడక ఆగలేదు!" | The Vision 2020 → 2047 walk + the Twitter marathon |
| 0:25–0:36 | Voter with folded arms, a slipper under his arm; the mirror shows sunglasses | "రౌడీ కాదు… ఇన్ఫ్లుయెన్సర్!" | Rowdeyism reframed as a personal brand — punches at every party, not one |
| 0:36–0:44 | Ballot box in a spotlight, leaders peeking from the curtains | "ఓటే అసలైన రౌడీ!" | The turn: the voter is the only real power centre |
| 0:44–0:48 | Outro | నవ్వు పోయింది… ఓటు మిగిలింది. | Civic close + disclaimer |

---

## How it was made (and how to rebuild it)

1. **Art** — four flat-vector cartoon stills generated at 768×1376, cropped to
   9:16 and upscaled with an unsharp pass.
2. **Telugu type** — PIL here has no Raqm, so Telugu is shaped with
   **HarfBuzz** (`uharfbuzz`) and rasterised glyph-by-glyph with **FreeType**,
   which keeps conjuncts and vowel signs correct (`textutil.py`).
3. **Voice** — four Telugu takes, cleaned with ffmpeg
   (`silenceremove → atempo 1.10 → highpass → EQ → compressor → limiter`),
   then placed on the timeline with a 0.45 s lead-in.
4. **Music + SFX** — synthesised from scratch in numpy: 92 BPM groove
   (kick / clap / hats / bass / pluck), plus whooshes on each cut and a
   low "dun" sting on each punchline. Side-chain ducking keeps it under the VO.
5. **Frames** — `build_video.py` renders every frame with PIL: Ken Burns
   push-in, per-line caption reveals, a shake on the punchline, a 3-frame
   flash on each hard cut. Frames stream straight into ffmpeg's stdin.
6. **Master** — H.264 CRF 26 (`-tune animation`) + AAC 192k, loudness
   normalised to −14 LUFS / −1.5 dBTP for social.

```bash
# one-time
python3 -m venv .venv
.venv/bin/pip install pillow numpy uharfbuzz freetype-py imageio-ffmpeg fonttools

# preview stills / full render
cd satire-short
../.venv/bin/python build_video.py --stills
../.venv/bin/python build_video.py     # -> out/ap_politics_roast.mp4 (master)

# publish encode (loudness + size)
FF=$(.venv/bin/python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
$FF -i out/ap_politics_roast.mp4 -c:v libx264 -preset slow -crf 26 -tune animation \
    -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k out/ap-politics-roast-v2.mp4
```

### Editing the jokes

All copy lives in the `SCENES` list at the top of `build_video.py` (`te` is the
Telugu headline, `en` the English caption, `tag` the yellow sticker, `vo` the
take). Change a line, re-run, and the timing re-flows automatically because scene
length is `VO length + 1.05 s`.

---

## Licensing

- Fonts: Noto Sans Telugu, Anton, Bebas Neue — SIL Open Font License (see
  `fonts/OFL-*.txt`).
- Music and sound effects: synthesised in this repo, no third-party samples.
- Cartoons and voice: generated for this project.
