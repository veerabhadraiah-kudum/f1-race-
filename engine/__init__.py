"""Mathematics behind AI — animation engine."""

from .theme import C, T, WIDTH, HEIGHT, FPS, rgba, mix, lighten, darken
from .animate import track, ease, remap, clamp, smoothstep, lerp, EASES
from .canvas import Canvas
from .scene import Scene, Cue, Beat, wrap
from .typography import Font, measure
from .linalg import Camera, vadd, vsub, vmul, vdot, vcross, vnorm, vlen, vlerp

__all__ = [
    "C", "T", "WIDTH", "HEIGHT", "FPS", "rgba", "mix", "lighten", "darken",
    "track", "ease", "remap", "clamp", "smoothstep", "lerp", "EASES",
    "Canvas", "Scene", "Cue", "Beat", "wrap", "Font", "measure",
    "Camera", "vadd", "vsub", "vmul", "vdot", "vcross", "vnorm", "vlen", "vlerp",
]
