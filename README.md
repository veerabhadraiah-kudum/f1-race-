# Mathematics behind AI — an animation engine for mathematical film

A production-quality engine for **scientific explainer animation**: real
mathematics, real 3D, real typography, rendered to a 1080p film.

The demonstration project is a four-chapter film — *Mathematics behind AI* —
that builds gradient descent, a neural network, a single neuron and the three
canonical training equations, each as its own engineered shot.

| | |
|---|---|
| **Film** | `out/film/mathematics_behind_ai_1080p.mp4` — 1920×1080, 30 fps, H.264 + AAC narration |
| **Scenes** | `out/scenes/*.mp4` — independent, inspectable previews |
| **Stills** | `out/stills/*.png` |
| **Runtime** | ~57 s, 4 scenes, 10 narrated cues |
| **Dependencies** | Python 3.11, Node 18+, no LaTeX, no Blender, no browser |

---

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./setup.sh                 # fetches fonts + MathJax (Node) once
python build.py film       # render the whole film (1080p)
```

Fast iteration loop (half-res preview, ~2 min):

```bash
python build.py preview scenes.s1_gradient_descent:GradientDescent 10
python build.py sheet   scenes.s1_gradient_descent:GradientDescent 12   # contact sheet
python build.py stills  scenes.s3_neuron:SingleNeuron 8.0 12.5
```

---

## Why this is not "Manim with extra steps"

The brief asked for Manim Community, Three.js, React/Remotion, FFmpeg, SVG and
LaTeX. This repository delivers the same *capabilities* with a stack that is
faithful to the actual constraints of the target environment, and it documents
the swap rather than hiding it:

| Brief | Here | Why |
|---|---|---|
| Manim Community (Python) | `engine/` — scenes, timeline, camera, animation classes | Manim needs **cairo + pango + LaTeX + ffmpeg from apt**. The build host has no package manager mirror, no LaTeX and no cairo, so Manim cannot be installed at all. The engine reproduces the Manim model — `Scene.render(t)`, keyframe/easing tracks, `Camera`, 3D height fields, TeX objects — on a stack that installs from PyPI only. |
| Three.js (3D) | `engine/linalg.py` + `engine/surface3d.py` | A real perspective camera (yaw/pitch/dolly/roll, near-plane clipping, auto-framing), depth-sorted shaded height fields, marching-squares contours, Blinn-style rim lighting and atmospheric haze — rasterised as vectors, so it is resolution-independent and deterministic frame-to-frame. |
| React + Remotion (composition) | `engine/scene.py`, `engine/film.py`, `build.py` | The composition model is the same (declarative scenes, per-scene previews, final assembly), expressed in Python so a single process owns the timeline, the typography cache and the render farm. |
| FFmpeg | `imageio-ffmpeg` wheel + `engine/render.py` | The bundled static binary, with the same H.264/BT.709/faststart command line a Remotion or Manim pipeline ends with. |
| SVG | `engine/canvas.py` → `resvg` | Every frame is a real SVG document rendered by resvg (Rust), not a hand-rolled rasteriser. |
| LaTeX | MathJax → SVG glyph paths (`tools/tex2svg.mjs`) | No TeX installation required, and — critically — the output is *addressable*: each glyph keeps its MathML ancestry, so a term can be highlighted, revealed or bound to an object. |

The result is a stack that a reviewer can run from a bare `pip install`, while
the motion design, the maths and the typography are the real thing.

---

## How a scene is built

```python
class GradientDescent(Retimed, Scene):
    duration = 13.0
    beats = {"surface": Beat("surface", 0.45, 2.35, "surface in"), ...}
    cues  = [Cue(0.85, 5.59, "A model learns by sliding downhill…"), ...]

    def render(self, cv, t):
        T = self.T(t)              # narration-timed clock
        cam = self.camera(T)
        self.field.draw(cv, cam, reveal=(0, self.tw(2.35)))
```

* **`render(cv, t)` is pure.** Any frame can be rendered in any order, in any
  process. That is what makes previews trustworthy and the final render
  parallel.
* **`beats`** are named windows; captions, camera and object animation all key
  off them, so retiming a shot retimes everything at once.
* **`Retimed`** stretches the authored timeline onto the *measured* narration
  (see below).
* **`Canvas`** accumulates SVG; `Theme` holds the palette and type scale;
  everything is measured with real shaped advances, so panels never overlap.

### Engine modules

| module | responsibility |
|---|---|
| `engine/theme.py` | palette, type scale, shared SVG gradients/filters |
| `engine/animate.py` | easing library, keyframe `Track`, stagger helpers |
| `engine/typography.py` | HarfBuzz shaping, glyph outlines, `<sub>`/`<sup>` rich text, Noto-math fallback |
| `engine/mathtex.py` | MathJax TeX → addressable glyph groups |
| `engine/linalg.py` | vectors, perspective `Camera`, near-plane clipping, auto-framing |
| `engine/surface3d.py` | shaded height fields, contours, floor grid, 3D arrows/labels |
| `engine/contours.py` | marching squares |
| `engine/opt.py` | loss surfaces with analytic gradients, real gradient descent |
| `engine/canvas.py` | SVG scene graph + resvg rasterisation |
| `engine/background.py` | procedural plate (gradient, glows, vignette, grain) |
| `engine/scene.py` | `Scene` base: cues, captions, HUD, composition |
| `engine/render.py` | parallel frame rendering, x264 encode, muxing |
| `engine/narration.py` | voice clips, timeline, sync reference |
| `engine/audio.py` | wav/mp3 I/O, mixing, tones, loudness |
| `engine/film.py` | shot list, per-scene render, cross-dissolve assembly |
| `engine/qa.py` | glyph-coverage and title-safe automated checks |
| `engine/layout.py` | measured layout primitives, stage/caption zones |

---

## Typography

* **Display:** Inter (400/500/600/700), **titles:** Fraunces, **data:** JetBrains Mono.
* Text is **shaped with HarfBuzz** and emitted as outlines, so kerning and
  ligatures are real, and the rasterised frame matches the design exactly — no
  font substitution, no missing-glyph boxes.
* Characters a display face lacks (Greek, ∇, ‖, ⊤) fall back to **Noto Sans
  Math**, resolved at glyph level.
* Sub/superscripts are real typographic runs (`w<sub>1</sub>`), not Unicode
  codepoints, so they exist in every weight and stay crisp.
* Mathematics is typeset by **MathJax** into glyph paths with MathML ancestry,
  which is what allows a single term (`\nabla L`) to be highlighted while the
  rest of the equation holds.

---

## 3D and camera

`Camera` is a pinhole camera with `yaw`, `pitch`, `dist`, `target`, `fov`,
`roll` and projection centre. Surfaces are sampled height fields with analytic
normals:

* quads are **depth-sorted** and drawn painter's-algorithm style,
* each quad is stroked in its own fill colour to kill antialiasing hairlines,
* lighting = ambient + wrapped Lambert + **Fresnel rim**, then **atmospheric
  haze** by depth, which is what makes the surface read as volume rather than
  flat shading,
* `fit_camera_screen()` auto-frames a point cloud into a screen-space box by
  solving distance *and* projection centre together — every shot is composed
  without hand-tuned magic numbers.

The loss surface in Scene 1 is `L(w) = ½wᵀAw + ripple·sin(2w₁)cos(1.7w₂)` with
its **exact analytic gradient**; the probes follow the real iteration
`w ← w − η∇L(w)`, and the on-screen readout is the live value of that iterate.

---

## Narration, sync and retiming

The film is cut to its narration, in this order:

1. Write the cues in the scene (`cues = [Cue(t_in, t_out, text), …]`).
2. Generate/record voice clips into `assets/audio/clips/<scene>_c<N>.mp3`.
3. `python tools/fit_narration.py` measures each clip and writes
   `scenes/_timing.py` with the real cue windows and scene durations.
4. `Retimed` warps the authored timeline onto those windows, so **picture
   follows voice** — no speech is ever time-stretched to fit a fixed edit.
5. `python build.py audio` mixes the bed and writes `assets/audio/timeline.json`.

`python build.py audio` also prints a **fit report** — every clip against its
window. It is currently 10/10.

The last scene ends on a closing card, which needs more room than the generic
0.95 s tail after the final line. `tools/fit_narration.py` carries an `OUTRO`
allowance for exactly that, so the extra seconds survive regeneration instead of
being hand-edited into `_timing.py`. The card itself is keyed off the **real**
scene duration (`CARD_HOLD`), never authored seconds: the retime warp compresses
the authored tail, and keying it that way once left the card fully lit for
barely a second.

A quiet **timecode reference** (a tick per second, a marker on every cue) is
mixed under the voice at low level. It makes sync verifiable by ear and by
analysis, and it documents where each line belongs; remove it with
`--no-reference` for a delivery master.

---

## Scene designs

### 1 · Gradient descent (11.9 s)
A real loss surface `L(w) = ½wᵀAw + 0.25·sin(2w₁)cos(1.7w₂)` rendered as 74×60
shaded quads with depth-sorted painter's algorithm, marching-squares contours and
an atmospheric haze pass. Four probe particles sit on the rim, each with a `−∇L`
arrow whose length is `‖∇L‖`; they then follow the **actual iterate sequence**
`w ← w − η∇L(w)` (η = 0.072, 46 steps), leaving a traced path and marked steps.
A live mono readout shows the current `w`, `L(w)` and `‖∇L‖`. Camera: one
continuous move — high establishing dolly, drop into the basin, slow orbital
settle — with a real spring on the reveal.

### 2 · A neural network (12.5 s)
4-5-4-2 fully connected. Nodes pop with a spring in a staggered wave, edges draw
on with cubic Béziers, then two forward passes propagate: a pulse travels every
edge, each node accumulates and fires **only after its incoming edges land**
(the timing follows the graph), and a softmax read-out updates. The graph then
shrinks into a schematic strip while the composed-function equation resolves.

### 3 · One neuron (17.1 s)
Exact arithmetic, shown step by step:
`x = (0.20, 0.50, 0.43)`, `w = (0.40, 0.26, 0.30)`, `b = 0.10` →
`z = 0.439` → `a = σ(0.439) = 0.6080`. Each product counts into the Σ register
with its own bar, the bias token slides in, `z` travels into the sigmoid curve to
the operating point, and the output node locks the value.

### 4 · The mathematics (16.8 s)
Four equations arrive in sequence; as a term highlights, a dashed leader binds it
to the object it describes — loss surface, descent path, sigmoid curve — and the
object is named in the term's colour. It closes on the training loop and a title
card.

## Quality assurance

`python -m engine.qa scenes.s1_gradient_descent:GradientDescent` runs two
automated gates on a scene:

* **glyph coverage** — every string a scene draws is shaped against the face
  that will render it; any codepoint without an outline is reported (this is
  what caught `ŷ`, `‖∇` and the Unicode subscripts before they shipped),
* **title-safe bounds** — frames are rendered, diffed against the background
  plate, and any ink inside the outer margin is reported with its bbox.

Visual checks are done on **rendered output**, not source: `build.py sheet`
extracts frames from the encoded MP4 into a contact sheet, which is how the
camera-dolly regression, the empty opening frame, the tofu subscripts and the
overlapping term labels were all found and fixed.

The narration gate is equally literal — `python build.py audio` prints every
clip against its window and currently reports **10/10 fits**:

```
s1_gradient_descent      cue 1: voice  4.39s in window  4.74s  ok
...
```

Two bugs this caught: speech clips longer than their authored windows (fixed by
retiming the scenes, never the audio), and narration drifting early after the
first scene because the cross-dissolves shorten the assembled timeline by
0.55 s each (fixed by compensating the fade offsets in `build_timeline`).

---

## Tests

```bash
python tests/test_engine.py        # 13 checks, ~20 s
```

Each test encodes a defect that was found by looking at rendered output:

| test | defect it locks down |
|---|---|
| `test_warp_is_monotone_and_bounded` | retiming extrapolated past the last beat, so scene 4 showed its title card twice and scenes 1–2 dropped their closing beats |
| `test_every_voice_clip_fits_its_cue` | 7 of 10 narration clips overran their on-screen windows |
| `test_narration_offsets_follow_the_dissolves` | narration drifted early after scene 1 because cross-dissolves shorten the timeline |
| `test_no_missing_glyphs` | Unicode subscripts, `ŷ`, `∇ σ ‖` rendered as tofu boxes |
| `test_neuron_arithmetic_matches_the_screen` | the numbers on screen must be the real arithmetic |
| `test_gradient_descent_matches_the_surface` | analytic gradient vs finite differences; every iterate must satisfy `w ← w − η∇L` |
| `test_camera_framing_keeps_the_subject_in_frame` | auto-framing must not clip the subject |
| `test_depth_sorting_puts_near_geometry_last` | painter's-algorithm ordering of the surface quads |
| `test_frame_rendering_is_deterministic` | frames are a pure function of time, but consecutive frames differ (it must animate) |
| `test_stale_frames_are_trimmed_before_encoding` | shortening the timings left old tail frames on disk; `encode` globs `f%05d.png`, so every scene silently grew and the film overran its narration |
| `test_mux_pads_narration_instead_of_clipping_picture` | `-shortest` trimmed the *picture* to the audio bed, cutting the closing card off mid-hold |
| `test_closing_card_holds_long_enough_to_read` | the card fade was keyed to authored seconds, which the retime warp compresses, so the card was fully lit for barely a second |
| `test_film_length_matches_the_narration_timeline` | the assembled length is computed in two places; if they drift, the audio bed and the picture disagree |

## Repository layout

```
engine/            the animation engine (see module table)
tests/             regression tests for the defects found during the build
scripts/           qa_all.sh, make_previews.sh
scenes/            the four shots + generated _timing.py + retime mixin
tools/             tex2svg.mjs (MathJax), fit_narration.py
assets/fonts/      Inter, Fraunces, JetBrains Mono, Noto Sans Math (OFL)
assets/audio/      narration clips, mixed bed, timeline.json
out/               rendered scenes, film, previews, stills, contact sheets
build.py           CLI: preview | scene | stills | sheet | audio | film
setup.sh           one-time font + MathJax fetch
```

## Rendering reference

| command | output |
|---|---|
| `python build.py preview <scene> <seconds>` | `out/preview_<scene>.mp4` (half-res, fast) |
| `python build.py scene <scene>` | `out/scenes/<scene>.mp4` (1080p) |
| `python build.py sheet <scene> 12` | `out/sheets/<scene>_sheet.png` |
| `python build.py stills <scene> 2.5 8.1` | `out/stills/*.png` |
| `python build.py audio` | `assets/audio/narration.wav` + fit report |
| `python build.py film` | `out/film/mathematics_behind_ai_1080p.mp4` |

`--fps`, `--scale`, `--crf` are accepted for all render commands.

## Licences

Fonts are SIL Open Font License (see `assets/licenses/`). MathJax is Apache-2.0.
Inter/Apache attribution notices are kept alongside the font files.
