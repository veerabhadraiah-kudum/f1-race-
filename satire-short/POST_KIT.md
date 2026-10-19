# POST KIT — ఏపీ రాజకీయ రోస్ట్ (AP Politics Roast, v2)

**File to upload:** `out/ap-politics-roast-v2.mp4` — 1080×1920, 47.7 s, 30 fps,
−14 LUFS, 20 MB. Subs: `out/captions.srt`. Cover: `out/cover.jpg`.

---

## Title options

**Telugu-first**

1. ఏపీ రాజకీయ రోస్ట్ 😂 | విజన్ 2020 నుంచి 2047 వరకు నడక ఆగలేదు! | Satire
2. రౌడీ కాదు… ఇన్ఫ్లుయెన్సర్! 😭 | AP Politics Roast | Episode 01
3. ఓటే అసలైన రౌడీ! | AP రాజకీయాల ROAST — ఎవరూ తప్పించుకోలేరు

**English-first**

1. AP Politics Roast 😂 CBN, Lokesh & the Whole Circus | Satire
2. Rowdy or Influencer? | AP Politics Roast — Episode 01
3. Vision 2020 → 2047: Still Walking | AP Politics Satire

> Keep **SATIRE / PARODY** in the title. It sets expectations, it is honest, and
> it is the platform-safe framing.

---

## Caption (YouTube Shorts / Instagram / Facebook)

```
విజన్ 2020 నుంచి విజన్ 2047 వరకు… నడక మాత్రం ఆగలేదు 😭
పాదయాత్ర vs ట్విట్టర్ మారథాన్ vs ఓటర్ చెప్పు — ఎపిసోడ్ 01.

ఇది పూర్తి సాటిర్ / పారడీ. పాత్రలు కామెడీ కోసం చేసిన క్యారికేచర్లు మాత్రమే.
ఏ వ్యక్తి లేదా పార్టీపై ద్వేషం కాదు, ఎవరి మద్దతు కూడా కాదు.
నవ్వు మీ ఇష్టం. ఓటు మీ హక్కు. 🙏

CBN has been walking from Vision 2020 to Vision 2047; Lokesh covered more
ground on Twitter. Full satire, exaggerated caricatures, no hatred, no
endorsement. Laugh freely, vote seriously.

#APPolitics #TeluguComedy #Satire #Parody #TeluguShorts #AndhraPradesh
#ChandrababuNaidu #Lokesh #TeluguMemes
```

**Pinned first comment**

> ఈ వీడియోలో ఎవరూ గెలవరు, ఎవరూ ఓడరు — ఓటర్ మాత్రం నవ్వుతాడు 😄
> This is parody. No party affiliation. Which scene should Episode 02 roast? 👇

---

## Hashtags — pick one set, don't stack all three

- **Reach:** `#TeluguShorts #TeluguComedy #AndhraPradesh #APPolitics #Roast`
- **Polity:** `#ChandrababuNaidu #Lokesh #TDP #APPolitics`
- **Satire:** `#Satire #Parody #PoliticalComedy #TeluguMemes`

---

## Platform notes

| Platform | Notes |
|---|---|
| Instagram Reels | Upload 1080×1920; captions are already burned in, so leave IG captions off. Cover `out/cover.jpg`. |
| YouTube Shorts | Title + `#Shorts`; upload `out/captions.srt` as Telugu subtitles. Put the disclaimer in the description. |
| Facebook / WhatsApp | 20 MB fits WhatsApp's 64 MB limit as-is; the file is also under FB's 1080p ceiling. |
| X / Twitter | Trim the first 20 s if you need a tighter clip; scene 2 is the strongest standalone. |

Post time in IST: **7:30–9:30 pm**, when Telugu comedy shorts get their evening
scroll. Reply to early comments with the pinned line, not with party arguments.

---

## Episode 02 — the Jagan episode (what you originally asked)

Short answer: **Jagan "makes good" in this format only if the episode roasts the
brand, not the man.** Viewers can smell a hit-piece in three seconds, and the
joke dies with it. Here is the playbook that keeps it comedy and keeps it
shareable.

**Five rules for a Jagan-centric roast**

1. **Pick a public performance, not a private life.** The "why did you come into
   politics" tear, the "only one leader" party structure, the three-capitals
   rollout, the welfare-vs-branding split. These are public acts — fair game.
2. **No case files as punchlines.** Anything sub judice ("liquor policy", CBI/ED
   references) turns a joke into a legal risk and a comment war. Skip it.
3. **Let his own words do the work.** Comedy lands hardest when the line is a
   real, widely-reported quote or a campaign visual, quoted straight and then
   undercut by the edit.
4. **Give him a valid point.** One honest concession ("the welfare delivery is
   real, the PR is louder") makes the rest of the roast feel fair, and it gives
   supporters a reason to keep watching instead of reporting.
5. **End on the voter, never on a rival.** The series rule stays: the last laugh
   belongs to the electorate, so no episode reads like an ad for somebody else.

**Suggested Episode 02 structure (same 4-scene template)**

| Beat | Visual | Joke target |
|---|---|---|
| Hook | Giant microphone on an empty stage | "Press meet every day, results every five years" |
| Scene 1 | A leader speaking to a mirror that answers back | The one-man-party echo chamber |
| Scene 2 | Three signboards for one state capital | The capital-hopping rollout, presented as a travel ad |
| Scene 3 | Welfare cheques vs billboards, side by side | "The scheme reached the village; the flex reached the moon" |
| Close | The same ballot box from this episode | Same closing line: ఓటే అసలైన రౌడీ |

Reuse `assets/scene4_ballot.png` for the close so the series stays visually
consistent, and keep the same HUD, fonts and disclaimer — brand recognition is
what makes episode 5 easier to sell than episode 1.

---

## Reuse checklist

- [ ] Replace the take in `audio/vo_sN.mp3`
- [ ] Edit the `SCENES` list in `build_video.py`
- [ ] `python build_video.py --stills` → check frames
- [ ] `python build_video.py` → master, then the CRF 26 / loudnorm publish pass
- [ ] Regenerate `out/captions.srt` timings (scene length = VO + 1.05 s)
- [ ] Keep the disclaimer on the title card, HUD chip and end card
