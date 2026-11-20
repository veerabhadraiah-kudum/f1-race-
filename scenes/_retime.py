"""
Retiming helpers.

`scenes/_timing.py` is generated from the *measured length of the narration
clips*; scenes declare their timing in a neutral "authored" space and this mixer
rescales it to the real narration timeline. Nothing in the motion code changes
when a line is re-recorded — only the numbers in the generated module.
"""
from __future__ import annotations

from ._timing import TIMING


class Retimed:
    """Expects: name, duration, cues, beats (dict of Beat)."""

    ANCHOR_DELAY = 0.35

    def apply_timing(self):
        entry = TIMING.get(self.name)
        if not entry:
            self._anchors = [(0.0, 0.0)]
            return
        new_dur = float(entry["duration"])
        new_cues = entry.get("cues") or []
        self._authored_beats = dict(self.beats)
        self._authored_dur = float(self.duration)

        # ---- cues ------------------------------------------------------
        old_dur = float(self.duration)
        if new_cues and len(new_cues) == len(self.cues):
            from engine.scene import Cue
            rebuilt = []
            for cue, (a, b) in zip(self.cues, new_cues):
                rebuilt.append(Cue(a, b, cue.text, cue.speaker, cue.emphasis))
            self.cues = rebuilt

        # ---- beats: map authored windows through the cue anchors -------
        from engine.scene import Beat
        mapped = {}
        for k, (bname, beat) in enumerate(self.beats.items()):
            a = self._map_time(beat.t_in, old_dur, new_dur, new_cues)
            b = self._map_time(beat.t_out, old_dur, new_dur, new_cues)
            if b <= a:
                b = a + 0.35
            mapped[bname] = Beat(bname, a, b, beat.label)
        self.beats = mapped
        self.duration = new_dur
        self.beat = self.beats

        # ---- piecewise time warp: authored seconds -> narration seconds ----
        anchors = [(0.0, 0.0)]
        for bname, beat in self._authored_beats.items():
            nb = mapped[bname]
            anchors.append((beat.t_in, nb.t_in))
        anchors.append((self._authored_dur, new_dur))
        anchors.sort()
        # enforce monotonicity
        clean = [anchors[0]]
        for a, b in anchors[1:]:
            if a > clean[-1][0] and b > clean[-1][1]:
                clean.append((a, b))
        self._anchors = clean

    def T(self, t):
        """
        Map an authored time to the retimed timeline.

        Scenes are written against a comfortable authored duration; this warp
        makes the motion follow the narration when a line comes in long or short.
        Outside the anchor range it extrapolates along the nearest segment.
        """
        A = getattr(self, "_anchors", None)
        if not A or len(A) < 2:
            return t
        if t <= A[0][0]:
            return A[0][1] - (A[0][0] - t)
        if t >= A[-1][0]:
            return A[-1][1] + (t - A[-1][0])
        lo, hi = 0, len(A) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if A[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        (ta, tb), (va, vb) = A[lo], A[hi]
        u = (t - ta) / (tb - ta) if tb > ta else 0.0
        return va + (vb - va) * u

    def _map_time(self, t, old_dur, new_dur, new_cues):
        # stretch the whole scene proportionally, then snap the final beat to
        # the end of the last line so the closing state always gets screen time
        return t * (new_dur / max(old_dur, 1e-6))
