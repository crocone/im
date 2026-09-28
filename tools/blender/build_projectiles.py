"""Munitions: homing missile and shoulder mini-missile.

Both point down -Y (Blender) = +Z (three.js). Each file has a ``Body`` mesh and an
``Exhaust`` emissive disc at the nozzle that the runtime scales / flickers.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathutils import Matrix, Vector  # noqa: E402

from common import cylinder, empty, export, hull, icosphere, log, palette, part, reset_scene, tube  # noqa: E402


def fins(count, root_y, tip_y, r0, span, thickness, mat, phase=0.0, sweep=0.12):
    """Planar fins around the -Y axis: root chord (y0..y1) at radius r0, tip chord swept back."""
    out = []
    for i in range(count):
        rot = Matrix.Rotation(phase + 2 * math.pi * i / count, 4, "Y")
        pts = []
        for t in (-thickness / 2, thickness / 2):
            pts += [(r0, root_y[0], t), (r0, root_y[1], t), (r0 + span, tip_y[0] + sweep, t),
                    (r0 + span, tip_y[1], t)]
        out.append(hull("fin", [tuple(rot @ Vector(p)) for p in pts], mat, 0.0))
    return out


def build_missile():
    reset_scene()
    P = palette()
    root = empty("Missile")
    body = [
        cylinder("body", 0.1, 1.1, (0, 0, 0), P["m_body"], (90, 0, 0), 14),
        cylinder("nose", 0.1, 0.35, (0, -0.725, 0), P["m_body"], (90, 0, 0), 14, r2=0.025),
        icosphere("seeker", 0.028, (0, -0.9, 0), P["joint"]),
        cylinder("band", 0.103, 0.08, (0, -0.35, 0), P["m_band"], (90, 0, 0), 14),
        cylinder("band2", 0.103, 0.05, (0, 0.28, 0), P["m_band"], (90, 0, 0), 14),
        cylinder("nozzle", 0.08, 0.14, (0, 0.62, 0), P["joint"], (90, 0, 0), 14, r2=0.095),
        tube("nozzle_lip", 0.1, 0.075, 0.03, (0, 0.69, 0), P["joint"], (90, 0, 0), 14),
    ]
    body += fins(4, (0.28, 0.55), (0.42, 0.58), 0.09, 0.2, 0.014, P["trim"], math.pi / 4)
    body += fins(4, (-0.32, -0.2), (-0.26, -0.18), 0.09, 0.08, 0.01, P["trim"], math.pi / 4, 0.03)
    part(body, "Body", (0, 0, 0), root)
    part([cylinder("exhaust", 0.07, 0.02, (0, 0.7, 0), P["m_exhaust"], (90, 0, 0), 14)], "Exhaust", (0, 0.7, 0), root)
    export("missile.glb")


def build_mini_missile():
    reset_scene()
    P = palette()
    root = empty("MiniMissile")
    body = [
        cylinder("body", 0.045, 0.5, (0, 0.02, 0), P["armor"], (90, 0, 0), 10),
        cylinder("nose", 0.045, 0.16, (0, -0.31, 0), P["accent"], (90, 0, 0), 10, r2=0.008),
        cylinder("band", 0.047, 0.04, (0, -0.12, 0), P["glow"], (90, 0, 0), 10),
        cylinder("nozzle", 0.035, 0.06, (0, 0.3, 0), P["joint"], (90, 0, 0), 10, r2=0.042),
    ]
    body += fins(3, (0.12, 0.26), (0.2, 0.28), 0.04, 0.09, 0.008, P["trim"], 0.0, 0.05)
    part(body, "Body", (0, 0, 0), root)
    part([cylinder("exhaust", 0.032, 0.012, (0, 0.335, 0), P["m_exhaust"], (90, 0, 0), 10)], "Exhaust",
         (0, 0.335, 0), root)
    export("mini_missile.glb")


def build():
    build_missile()
    build_mini_missile()
    log("projectiles done")


if __name__ == "__main__":
    build()
