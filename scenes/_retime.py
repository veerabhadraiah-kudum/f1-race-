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
        # Anchor on distinct beat starts. Beats may share an authored in-point
        # (deliberate overlapping reveals), which must not produce duplicate
        # anchors -- those broke the interpolation and made the clock jump
        # backwards mid-scene.
        pairs = {}
        for bname, beat in self._authored_beats.items():
            nb = mapped[bname]
            a0 = round(float(beat.t_in), 3)
            pairs[a0] = max(pairs.get(a0, 0.0), float(nb.t_in))
        anchors = [(0.0, 0.0)]
        for a0 in sorted(pairs):
            if a0 <= anchors[-1][0] or pairs[a0] <= anchors[-1][1]:
                continue
            anchors.append((a0, pairs[a0]))
        # Always anchor the scene end, otherwise authored keys after the last
        # beat would clamp and the closing beats (equation build, settle) would
        # never play.
        end_auth = float(self._authored_dur)
        if end_auth > anchors[-1][0]:
            anchors.append((end_auth, float(new_dur)))
        self._anchors = anchors

    def T(self, t):
        """
        Map an authored time to the retimed timeline.

        Scenes are written against a comfortable authored duration; this warp
        makes the motion follow the narration when a line runs long or short.
        The mapping is piecewise-linear between beat anchors and **clamped**
        outside them: anchors come from the declared beats, so any animation key
        beyond the last beat must hold rather than run off the end of the film.
        """
        A = getattr(self, "_anchors", None)
        if not A or len(A) < 2:
            return t
        if t <= A[0][0]:
            return A[0][1]
        for i in range(len(A) - 1):
            a0, v0 = A[i]
            a1, v1 = A[i + 1]
            if a0 <= t <= a1:
                if a1 <= a0:
                    return v0
                u = (t - a0) / (a1 - a0)
                return v0 + (v1 - v0) * u
        return A[-1][1]

    def _map_time(self, t, old_dur, new_dur, new_cues):
        # stretch the whole scene proportionally, then snap the final beat to
        # the end of the last line so the closing state always gets screen time
        return t * (new_dur / max(old_dur, 1e-6))
