#!/usr/bin/env python3
"""
Narration-driven retiming.

Voice clips are generated from the script; their durations are then measured and
the *scene* is retimed to hold them — never the other way round.  Stretching or
cropping speech to fit a fixed picture is what makes explainer videos feel
rushed; moving the beats is free, because every animation is a pure function of
its beat table.

For each scene this tool emits `scenes/_timing.py`, a generated module the scenes
read their cue windows from. It also reports any cue that still does not fit and
the minimum scene duration required.

Run:  python tools/fit_narration.py
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.audio import probe_duration            # noqa: E402
from engine.film import load_all                   # noqa: E402
from engine.narration import _find_clip            # noqa: E402

LEAD_IN = 0.85       # picture establishes before the first word
GAP = 0.45           # breathing room between lines
TAIL = 0.95          # room for the final frame to land
MIN_LINE = 2.6       # never let a caption flash by faster than this

# Scenes that end on a closing card need more than the generic TAIL: the film's
# last words must land, then the card has to fade up *and* hold long enough to
# be read. Extra seconds appended after the last cue, per scene.
OUTRO = {
    "s4_equations": 1.8,
}


def build_plan() -> dict:
    plan = {}
    problems = []
    for cls in load_all():
        sc = cls()
        n = len(sc.cues)
        lengths = []
        for i in range(n):
            f = _find_clip(sc.name, i + 1)
            dur = probe_duration(f) if f else 4.0
            lengths.append(round(max(dur, 1.2), 3))
        # lay the cues out back-to-back with lead-in and gaps
        t = LEAD_IN
        cues = []
        for i, dur in enumerate(lengths):
            win = max(dur + 0.35, MIN_LINE)
            cues.append({"t_in": round(t, 2), "t_out": round(t + win, 2),
                         "voice": lengths[i]})
            t += win + GAP
        # compact: the last line needs room to breathe, not a second of silence
        last_end = cues[-1]["t_out"] if cues else 2.0
        outro = OUTRO.get(sc.name, 0.0)
        total = round(max(last_end + TAIL, sum(lengths) + LEAD_IN + GAP * (n - 1) + TAIL) + outro, 2)
        plan[sc.name] = {
            "cues": cues,
            "duration": total,
            "was": round(sc.duration, 2),
            "outro": outro,
            "n": n,
        }
    return plan


def write_module(plan: dict):
    lines = [
        '"""',
        "AUTO-GENERATED — do not edit by hand.",
        "",
        "Cue windows and scene durations derived from the measured length of each",
        "narration clip by tools/fit_narration.py. Regenerate after changing any",
        "voice clip:   python tools/fit_narration.py",
        '"""',
        "",
        "TIMING = {",
    ]
    for name, p in plan.items():
        lines.append(f'    "{name}": {{')
        lines.append(f'        "duration": {p["duration"]},')
        lines.append('        "cues": [')
        for c in p["cues"]:
            lines.append(f'            ({c["t_in"]}, {c["t_out"]}),')
        lines.append("        ],")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    path = os.path.join(ROOT, "scenes", "_timing.py")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


def main():
    plan = build_plan()
    path = write_module(plan)
    print(f"{'scene':24} {'cues':>4} {'was':>7} {'now':>7}   cue windows (voice length)")
    for name, p in plan.items():
        wins = "  ".join(f'{c["t_out"]-c["t_in"]:.2f}({c["voice"]:.2f})' for c in p["cues"])
        print(f"{name:24} {p['n']:4} {p['was']:7.2f} {p['duration']:7.2f}   {wins}")
    print(f"\n  wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
