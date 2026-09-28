"""Munitions: homing missile and shoulder mini-missile.

Both point down -Y (Blender) = +Z (three.js). Each file has a ``Body`` mesh and an
``Exhaust`` emissive disc at the nozzle that the runtime scales / flickers. Enemy missiles reuse
missile.glb with every ``Munition_White`` surface recoloured at runtime.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401  (must precede mathutils when running as a module)
from mathutils import Vector  # noqa: E402

from common import (  # noqa: E402
    cylinder, empty, export, lathe, log, material, part, reset_scene, set_uv_scale, skin, tube,
)
from pbr import pbr_material  # noqa: E402

AXIS = (90, 0, 0)  # lathe profiles run along local +Z; this maps it to world -Y (the flight direction)


def airfoil_fins(count, r0, span, root, tip, thick, mat, phase=0.0):
    """Tapered, swept fins with a lens-shaped section. ``root`` / ``tip`` = (a_front, a_back) along the axis
    (a = distance towards the nose, i.e. world y = -a)."""
    out = []
    for i in range(count):
        th = phase + 2 * math.pi * i / count
        radial = Vector((math.cos(th), 0.0, math.sin(th)))
        side = Vector((-math.sin(th), 0.0, math.cos(th)))
        rings = []
        for r, (a0, a1), t in ((r0 - 0.004, root, thick), (r0 + span, tip, thick * 0.45)):
            ring = []
            for u, v in ((0.0, 0.0), (0.25, 0.5), (0.7, 0.4), (1.0, 0.0), (0.7, -0.4), (0.25, -0.5)):
                a = a0 + (a1 - a0) * u
                ring.append(tuple(radial * r + Vector((0.0, -a, 0.0)) + side * (v * t)))
            rings.append(ring)
        out.append(skin("fin", rings, mat))
    return out


def build_missile():
    reset_scene()
    set_uv_scale(0.5)
    white = pbr_material("Munition_White", (0.62, 0.63, 0.64), 0.2, 0.38, "panels_large", seed=51, size=256, bump=1.0,
                         wear=0.3, grime=0.3, painted=True)
    band = material("Munition_Orange", (0.8, 0.25, 0.02), 0.3, 0.45)
    dark = material("Munition_Dark", (0.02, 0.02, 0.023), 0.7, 0.3)
    glow = material("Emissive_Exhaust", (1.0, 0.7, 0.4), 0.0, 0.3, (1.0, 0.55, 0.2), 10.0)
    root = empty("Missile")
    body = [
        lathe("body", [(0.0, 0.9), (0.03, 0.885), (0.052, 0.84), (0.072, 0.77), (0.088, 0.68), (0.097, 0.6), (0.1, 0.52),
                       (0.1, -0.5), (0.094, -0.54), (0.086, -0.58), (0.0, -0.58)], 20, (0, 0, 0), white, AXIS),
        lathe("seeker", [(0.0, 0.952), (0.012, 0.948), (0.024, 0.935), (0.032, 0.905), (0.034, 0.88)], 16, (0, 0, 0), dark,
              AXIS, 180.0),
        tube("band", 0.103, 0.095, 0.06, (0, -0.4, 0), band, AXIS, 20),
        tube("band", 0.103, 0.095, 0.035, (0, 0.3, 0), band, AXIS, 20),
        tube("joint_ring", 0.102, 0.095, 0.012, (0, 0.05, 0), dark, AXIS, 20),
        lathe("nozzle", [(0.084, -0.57), (0.088, -0.62), (0.096, -0.7), (0.088, -0.705), (0.072, -0.64), (0.0, -0.64)], 20,
              (0, 0, 0), dark, AXIS),
    ]
    body += airfoil_fins(4, 0.1, 0.17, (-0.28, -0.56), (-0.46, -0.58), 0.016, white, math.pi / 4)
    body += airfoil_fins(4, 0.1, 0.055, (0.46, 0.34), (0.4, 0.35), 0.01, white, math.pi / 4)
    part(body, "Body", (0, 0, 0), root)
    set_uv_scale(None)
    part([cylinder("exhaust", 0.07, 0.02, (0, 0.7, 0), glow, AXIS, 16)], "Exhaust", (0, 0.7, 0), root)
    export("missile.glb")


def build_mini_missile():
    reset_scene()
    armor = material("Armor_Gunmetal", (0.075, 0.08, 0.092), 0.85, 0.3)
    accent = material("Armor_Copper", (0.6, 0.17, 0.045), 0.9, 0.28)
    glow = material("Emissive_Cyan", (0.55, 0.92, 1.0), 0.0, 0.3, (0.42, 0.85, 1.0), 4.0)
    exhaust = material("Emissive_Exhaust", (1.0, 0.7, 0.4), 0.0, 0.3, (1.0, 0.55, 0.2), 10.0)
    root = empty("MiniMissile")
    body = [
        lathe("body", [(0.045, 0.2), (0.045, -0.26), (0.04, -0.285), (0.034, -0.3), (0.0, -0.3)], 14, (0, 0, 0), armor, AXIS),
        lathe("nose", [(0.0, 0.39), (0.012, 0.378), (0.026, 0.34), (0.038, 0.28), (0.045, 0.22), (0.045, 0.19), (0.0, 0.19)],
              14, (0, 0, 0), accent, AXIS),
        tube("band", 0.047, 0.04, 0.03, (0, -0.12, 0), glow, AXIS, 14),
        lathe("nozzle", [(0.034, -0.29), (0.04, -0.33), (0.036, -0.335), (0.028, -0.31), (0.0, -0.31)], 14, (0, 0, 0), armor,
              AXIS),
    ]
    body += airfoil_fins(3, 0.045, 0.075, (-0.14, -0.27), (-0.23, -0.28), 0.009, accent, 0.0)
    part(body, "Body", (0, 0, 0), root)
    part([cylinder("exhaust", 0.032, 0.012, (0, 0.335, 0), exhaust, AXIS, 12)], "Exhaust", (0, 0.335, 0), root)
    export("mini_missile.glb")


def build():
    build_missile()
    build_mini_missile()
    log("projectiles done")


if __name__ == "__main__":
    build()
