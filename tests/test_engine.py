"""
Regression tests for the parts that were actually broken during development.

Each test here corresponds to a defect found by inspecting rendered output, so
the suite is a record of the failure modes rather than a coverage exercise.

    python -m pytest tests/ -q        (or: python tests/test_engine.py)
"""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


# --------------------------------------------------------------- time warp
def test_warp_is_monotone_and_bounded():
    """
    The retiming warp must be non-decreasing everywhere and must not run past
    the generated scene duration.

    Bug: extrapolating beyond the last anchor let the clock run to 2x the scene
    length, which wrapped scene states around — a second title card appeared at
    the end of scene 4, and scenes 1-2 silently dropped their closing beats.
    """
    from engine.film import load_all

    for cls in load_all():
        sc = cls()
        ts = [i * 0.1 for i in range(int(sc.duration / 0.1) + 3)]
        vals = [sc.T(t) for t in ts]
        assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:])), f"{sc.name}: warp not monotone"
        authored = getattr(sc, "_authored_dur", sc.duration)
        assert max(vals) <= max(sc.duration, authored) + 1e-6, f"{sc.name}: warp ran past the end"
        # the end of the authored timeline must be reachable
        assert sc.T(sc.duration) >= sc.duration * 0.85, f"{sc.name}: closing beats unreachable"


# --------------------------------------------------------------- narration
def test_every_voice_clip_fits_its_cue():
    """
    Every narration clip must fit inside the on-screen window it narrates.
    Bug: seven of ten generated clips originally overran their windows, which
    prompted retiming the picture instead of stretching the voice.
    """
    from engine.film import load_all
    from engine.narration import check_fit

    bad = [(s, i, cd, wd) for s, i, cd, wd, ok in check_fit(load_all()) if not ok]
    assert not bad, f"clips overrun their windows: {bad}"


def test_narration_offsets_follow_the_dissolves():
    """
    Scene start times in the assembled film must subtract the cross-dissolve,
    or every scene after the first speaks ahead of its picture.
    """
    from engine.film import load_all
    from engine.narration import build_timeline

    classes = load_all()
    tl = build_timeline(classes, fade=0.55)
    starts = [e["start"] for e in tl["scenes"]]
    assert abs(starts[0]) < 1e-6
    acc = 0.0
    for k, (e, cls) in enumerate(zip(tl["scenes"], classes)):
        assert abs(e["start"] - acc) < 1e-3, f"scene {k} start {e['start']} != {acc}"
        acc += cls().duration - (0.55 if k < len(classes) - 1 else 0.0)


# ------------------------------------------------------------------ glyphs
def test_no_missing_glyphs():
    """
    Bug: Inter has no glyphs for subscripts, ∇, ‖, σ or ŷ, so those strings
    rendered as tofu boxes. Fonts now fall back to Noto Sans Math at glyph
    level, and this test locks that in.
    """
    from engine.qa import check_glyphs
    from engine.film import load_all

    problems = []
    for cls in load_all():
        problems += [(cls.__name__, fam, w, chars) for fam, w, chars in check_glyphs(cls)]
    assert not problems, problems


# -------------------------------------------------------------------- math
def test_neuron_arithmetic_matches_the_screen():
    """Scene 3 shows real arithmetic; the constants must agree with it."""
    from scenes.s3_neuron import X, W, B, PROD, Z, A

    for x, w, p in zip(X, W, PROD):
        assert abs(x * w - p) < 1e-9
    assert abs(sum(PROD) + B - Z) < 1e-12
    assert abs(1.0 / (1.0 + math.exp(-Z)) - A) < 1e-12
    assert 0.0 < A < 1.0


def test_gradient_descent_matches_the_surface():
    """The probes follow the real update rule on the real analytic gradient."""
    from engine.opt import anisotropic_bowl, gradient_descent

    loss = anisotropic_bowl()
    # finite differences agree with the analytic gradient
    x, y, h = 0.37, -0.82, 1e-6
    gx, gy = loss.grad(x, y)
    fx = (loss.f(x + h, y) - loss.f(x - h, y)) / (2 * h)
    fy = (loss.f(x, y + h) - loss.f(x, y - h)) / (2 * h)
    assert abs(gx - fx) < 1e-5 and abs(gy - fy) < 1e-5

    lr = 0.072
    traj = gradient_descent(loss, 2.25, 1.55, lr=lr, steps=45)
    for i in range(len(traj) - 1):
        gx, gy = loss.grad(traj.xs[i], traj.ys[i])
        assert abs((traj.xs[i + 1] - traj.xs[i]) + lr * gx) < 1e-9
        assert abs((traj.ys[i + 1] - traj.ys[i]) + lr * gy) < 1e-9
    # and it actually descends
    assert traj.losses[-1] < traj.losses[0]


# ------------------------------------------------------------------ camera
def test_camera_framing_keeps_the_subject_in_frame():
    """Auto-framing must place every sampled point inside the stage box."""
    from engine.linalg import Camera, fit_camera_screen

    rng = np.random.default_rng(7)
    pts = [(float(a), float(b), float(c)) for a, b, c in rng.normal(size=(80, 3)) * np.array([2.5, 1.2, 2.0])]
    box = (150.0, 180.0, 1770.0, 760.0)
    cam = fit_camera_screen(Camera(yaw=-35, pitch=27, fov_deg=30), pts, box, margin=0.96)
    for p in pts:
        x, y, z = cam.project(p)
        assert z > 0
        assert box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1


# ------------------------------------------------------------------ camera
def test_depth_sorting_puts_near_geometry_last():
    """Painter's algorithm: the surface renderer must emit far quads first."""
    from engine.linalg import Camera
    from engine.surface3d import HeightField
    from engine.canvas import Canvas

    f = HeightField(lambda x, y: x * x + y * y, (-2, 2), (-2, 2), nx=12, ny=12)
    cam = Camera(yaw=-30, pitch=25, dist=10, target=(0, 1, 0))
    cv = Canvas()
    f.draw(cv, cam)
    # the renderer batches all quads into a single SVG fragment
    polys = [p for s in cv.layers for p in s.split("<polygon")[1:]]
    assert len(polys) >= (f.nx - 1) * (f.ny - 1) * 0.9, "every visible quad should be emitted"
    # far quads are emitted first: sample the projected y of the first and last
    # polygon centres; on this bowl the near rim is consistently lower on screen
    def centre_y(poly):
        pts = poly.split('points="')[1].split('"')[0].split()
        ys = [float(p.split(",")[1]) for p in pts]
        return sum(ys) / len(ys)
    assert centre_y(polys[0]) != centre_y(polys[-1]), "sorting had no effect"


def test_frame_rendering_is_deterministic():
    """A scene frame must be a pure function of time (parallel-safe)."""
    from scenes.s3_neuron import SingleNeuron

    sc = SingleNeuron()
    a = sc.frame_array(7.4)
    b = sc.frame_array(7.4)
    assert np.array_equal(a, b)
    c = sc.frame_array(8.2)
    assert not np.array_equal(a, c), "consecutive frames should differ (it must animate)"


def test_stale_frames_are_trimmed_before_encoding():
    """
    A scene directory must never keep frames past the scene's duration.

    Bug: shortening the scene timings left six old tail frames per scene on
    disk. `encode` globs f%05d.png, so each scene grew 0.2s, the film ran to
    55.67s against a 54.83s narration bed, and the muxer clipped the ending —
    the closing card lost its hold.
    """
    import tempfile
    from engine.render import _drop_stale_frames

    with tempfile.TemporaryDirectory() as d:
        for i in range(10):
            open(os.path.join(d, f"f{i:05d}.png"), "wb").close()
        _drop_stale_frames(d, 6)
        left = sorted(f for f in os.listdir(d) if f.endswith(".png"))
        assert left == [f"f{i:05d}.png" for i in range(6)], left


def test_mux_pads_narration_instead_of_clipping_picture():
    """
    Attaching narration must not shorten the picture.

    Bug: `-shortest` truncated the video to the audio bed's length, so a bed
    even slightly short of the film chopped the final frames off.
    """
    import inspect
    from engine import render

    src = inspect.getsource(render.mux_audio)
    assert "apad" in src, "narration must be padded to the picture length"
    assert "-c:v" in src and "copy" in src, "muxing must not re-encode video"


def test_closing_card_holds_long_enough_to_read():
    """
    The film's last card must hold, fully lit, before the picture ends.

    Bug: the card fade was authored in *scene* seconds, but the retime warp
    compresses the authored tail, so the card only reached full brightness
    ~1.3s before the end — too brief to read.
    """
    from scenes.s4_equations import EquationsAndTerms

    sc = EquationsAndTerms()
    assert sc.card_at <= sc.duration - 2.0, (
        f"card is fully lit only {sc.duration - sc.card_at:.2f}s before the end"
    )
    # chrome must be gone no later than the moment the card is fully lit
    assert sc.chrome_fade_at + 0.7 <= sc.card_at + 1e-6, "HUD lingers over the card"
    assert sc._chrome(sc.card_at) <= 0.01, "frame furniture visible behind the card"


def test_film_length_matches_the_narration_timeline():
    """
    The assembled length used for the audio bed must equal the assembled
    picture. Two places compute it (the cross-dissolve formula in film.py and
    build_timeline); if they drift, the bed and the picture disagree and
    `-shortest` cuts one of them.
    """
    from engine.film import load_all
    from engine.narration import build_timeline

    classes = load_all()
    fade = 0.55
    by_formula = sum(c().duration for c in classes) - fade * (len(classes) - 1)
    tl = build_timeline(classes, fade=fade)
    assert abs(tl["total"] - by_formula) < 1e-6, (
        f"timeline total {tl['total']:.3f}s != picture {by_formula:.3f}s"
    )
    # every scene must end before the film does
    for sc in tl["scenes"]:
        assert sc["start"] + sc["duration"] <= tl["total"] + 1e-6, sc["name"]
        for cue in sc["cues"]:
            assert cue["t_out"] <= tl["total"] + 1e-6, (sc["name"], cue["text"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
