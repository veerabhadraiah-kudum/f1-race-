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

A quiet **timecode reference** (a tick per second, a marker on every cue) is
mixed under the voice at low level. It makes sync verifiable by ear and by
analysis, and it documents where each line belongs; remove it with
`--no-reference` for a delivery master.

---

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
camera-dolly regression and the empty-frame defects were found and fixed.

---

## Repository layout

```
engine/            the animation engine (see module table)
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
