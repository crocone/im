"""Hostile machines: combat drone, rooftop missile turret and the armored boss.

Forward is -Y in Blender (+Z in three.js). Emissive exhaust markers (``Thruster*``) use
local -Z (Blender) = local -Y (three.js) as the exhaust direction.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (  # noqa: E402
    box, cylinder, empty, export, hull, icosphere, log, loft, material, palette, part, reset_scene, tube,
)


def mirror(points, s):
    return [(x * s, y, z) for x, y, z in points]


def plate(front, depth, mat, bevel=0.01):
    return hull("plate", list(front) + [(x * 0.97, y + depth, z) for x, y, z in front], mat, bevel)


# --------------------------------------------------------------------------- drone


def build_drone():
    reset_scene()
    P = palette()
    root = empty("Drone")
    body = [
        loft("hull", [(-1.05, 0, 0.0, 0.42, 0.34, 0.1), (-0.6, 0, 0.02, 0.82, 0.5, 0.15),
                      (0.2, 0, 0.04, 1.0, 0.62, 0.18), (0.8, 0, 0.02, 0.72, 0.44, 0.14)], P["e_hull"], 0.03, "Y"),
        loft("top_plate", [(-0.55, 0, 0.29, 0.58, 0.06, 0.02), (0.55, 0, 0.3, 0.66, 0.06, 0.02)], P["e_plate"],
             0.01, "Y"),
        loft("belly", [(-0.5, 0, -0.25, 0.6, 0.06, 0.02), (0.6, 0, -0.25, 0.6, 0.06, 0.02)], P["e_plate"], 0.01,
             "Y"),
        tube("bezel", 0.19, 0.12, 0.08, (0, -1.03, 0.0), P["e_plate"], (90, 0, 0), 16),
        cylinder("nozzle", 0.14, 0.22, (0, 0.91, 0.02), P["joint"], (-90, 0, 0), 14, r2=0.19),
    ]
    for s in (1, -1):
        body += [
            hull("cheek", mirror([(0.42, -0.5, 0.12), (0.52, 0.3, 0.14), (0.52, 0.3, -0.1), (0.42, -0.5, -0.08),
                                  (0.36, -0.5, 0.12), (0.44, 0.3, 0.14), (0.44, 0.3, -0.1), (0.36, -0.5, -0.08)], s),
                 P["e_accent"], 0.01),
            box("strip", (0.014, 0.6, 0.025), (s * 0.527, -0.1, 0.02), P["e_glow"]),
            cylinder("barrel", 0.045, 0.45, (s * 0.26, -0.85, -0.2), P["joint"], (90, 0, 0), 10),
            tube("brake", 0.065, 0.035, 0.07, (s * 0.26, -1.08, -0.2), P["e_plate"], (90, 0, 0), 10),
            box("fin", (0.02, 0.22, 0.26), (s * 0.13, 0.55, 0.42), P["e_plate"], rot=(-20, 0, 0)),
        ]
    ducts = [(1.02, -0.42), (-1.02, -0.42), (0.95, 0.5), (-0.95, 0.5)]
    for i, (x, y) in enumerate(ducts):
        s = 1 if x > 0 else -1
        body += [
            box("arm", (abs(x) - 0.35, 0.14, 0.08), (s * (abs(x) + 0.35) / 2, y, 0.06), P["e_plate"], bevel=0.015),
            tube("duct", 0.44, 0.37, 0.2, (x, y, 0.06), P["e_hull"], segments=24),
            tube("lip", 0.455, 0.43, 0.05, (x, y, 0.17), P["e_accent"], segments=24),
            box("strut", (0.74, 0.04, 0.04), (x, y, 0.0), P["e_plate"]),
            cylinder("glow", 0.06, 0.03, (x, y, -0.05), P["e_glow"], segments=10),
        ]
    part(body, "Body", (0, 0, 0), root)
    part([icosphere("sensor", 0.12, (0, -1.07, 0.0), P["e_glow"], 1)], "Sensor", (0, -1.07, 0), root)
    part([cylinder("thruster", 0.13, 0.02, (0, 1.02, 0.02), P["e_glow"], (90, 0, 0), 14)], "Thruster",
         (0, 1.02, 0.02), root)
    for i, (x, y) in enumerate(ducts):
        blades = [cylinder("hub", 0.07, 0.08, (x, y, 0.07), P["joint"], segments=10)]
        for k in range(3):
            a = 2 * math.pi * k / 3 + i
            blades.append(box("blade", (0.3, 0.07, 0.015), (x + math.cos(a) * 0.19, y + math.sin(a) * 0.19, 0.07),
                              P["e_plate"], rot=(12, 0, math.degrees(a))))
        part(blades, f"Rotor_{i}", (x, y, 0.07), root)
    empty("Muzzle_L", (0.26, -1.13, -0.2), parent=root)
    empty("Muzzle_R", (-0.26, -1.13, -0.2), parent=root)
    export("drone.glb")


# --------------------------------------------------------------------------- turret


def build_turret():
    reset_scene()
    P = palette()
    root = empty("Turret")
    base = [
        cylinder("plinth", 1.75, 0.5, (0, 0, 0.25), P["e_hull"], segments=6, bevel=0.04),
        cylinder("collar", 1.2, 0.7, (0, 0, 0.85), P["e_plate"], segments=12, r2=1.0, bevel=0.02),
        cylinder("hazard", 1.23, 0.14, (0, 0, 0.62), P["e_hazard"], segments=12),
    ]
    for k in range(6):
        a = math.radians(30 + 60 * k)
        base.append(box("bolt", (0.3, 0.3, 0.25), (1.42 * math.cos(a), 1.42 * math.sin(a), 0.6), P["joint"],
                        rot=(0, 0, math.degrees(a))))
    part(base, "Base", (0, 0, 0), root)
    yaw_parts = [
        cylinder("turntable", 1.15, 0.3, (0, 0, 1.35), P["e_hull"], segments=16, bevel=0.03),
        box("pedestal", (0.8, 0.9, 0.7), (0, 0.1, 1.85), P["e_plate"], bevel=0.04),
        box("rear_box", (1.3, 0.7, 0.7), (0, 0.85, 1.7), P["e_hull"], bevel=0.04),
        box("rear_vent", (1.0, 0.05, 0.4), (0, 1.21, 1.7), P["joint"]),
        box("rear_glow", (0.8, 0.03, 0.05), (0, 1.235, 1.95), P["e_glow"]),
        cylinder("trunnion", 0.2, 1.3, (0, 0, 2.15), P["joint"], (0, 90, 0), 12),
    ]
    yaw = part(yaw_parts, "Yaw", (0, 0, 1.35), root)
    head = [
        loft("head", [(-0.95, 0, 2.15, 0.62, 0.42, 0.1), (-0.55, 0, 2.18, 1.0, 0.72, 0.16),
                      (0.55, 0, 2.2, 1.05, 0.8, 0.16)], P["e_plate"], 0.03, "Y"),
        box("head_glow", (0.03, 0.8, 0.04), (0.53, -0.1, 2.35), P["e_glow"]),
        box("head_glow", (0.03, 0.8, 0.04), (-0.53, -0.1, 2.35), P["e_glow"]),
    ]
    muzzles = []
    for s in (1, -1):
        cx = s * 0.82
        head += [
            loft("pod", [(-0.85, cx, 2.15, 0.5, 0.56, 0.06), (0.55, cx, 2.18, 0.56, 0.62, 0.06)], P["e_hull"], 0.02,
                 "Y"),
            box("pod_band", (0.58, 0.12, 0.64), (cx, -0.3, 2.17), P["e_hazard"]),
            box("pod_band", (0.58, 0.12, 0.66), (cx, 0.2, 2.18), P["e_accent"]),
        ]
        for dx in (-0.13, 0.13):
            for dz in (-0.13, 0.13):
                head.append(tube("tube", 0.11, 0.075, 0.12, (cx + dx, -0.88, 2.15 + dz), P["joint"], (90, 0, 0), 12))
                head.append(cylinder("tube_back", 0.08, 0.02, (cx + dx, -0.84, 2.15 + dz), P["e_accent"], (90, 0, 0),
                                     12))
                muzzles.append((cx + dx, -0.97, 2.15 + dz))
    pitch = part(head, "Pitch", (0, 0, 2.15), yaw)
    part([box("sensor", (0.3, 0.06, 0.12), (0, -0.97, 2.24), P["e_glow"]),
          icosphere("lens", 0.07, (0, -0.93, 2.08), P["e_glow"])], "Sensor", (0, -0.97, 2.2), pitch)
    for k, m in enumerate(muzzles):
        empty(f"Muzzle_{k}", m, parent=pitch)
    export("turret.glb")


# --------------------------------------------------------------------------- boss


def boss_arm(P, s):
    parts = [
        hull("pauldron", mirror([(1.75, -1.05, 1.3), (1.75, 1.0, 1.3), (1.85, -0.9, 2.55), (1.85, 0.85, 2.55),
                                 (3.35, -1.0, 1.15), (3.35, 0.95, 1.15), (3.1, -0.85, 2.3), (3.1, 0.8, 2.3),
                                 (2.5, -1.0, 2.75), (2.5, 0.9, 2.75)], s), P["b_accent"], 0.05),
        hull("under", mirror([(2.3, -0.9, 0.7), (2.3, 0.9, 0.7), (3.45, -0.85, 0.6), (3.45, 0.85, 0.6),
                              (2.3, -0.9, 1.4), (2.3, 0.9, 1.4), (3.4, -0.85, 1.3), (3.4, 0.85, 1.3)], s),
             P["b_plate"], 0.04),
        loft("upper", [(-0.55, s * 2.75, 0, 0.8, 0.85, 0.2), (0.8, s * 2.75, 0, 0.95, 1.0, 0.25)], P["b_plate"], 0.04),
        cylinder("elbow", 0.5, 0.9, (s * 2.75, 0, -0.7), P["joint"], (0, 90, 0), 16),
        loft("cannon", [(0.5, s * 2.75, -0.75, 1.1, 1.05, 0.22), (-1.1, s * 2.75, -0.75, 1.25, 1.15, 0.25),
                        (-2.0, s * 2.75, -0.75, 0.95, 0.9, 0.2)], P["b_plate"], 0.05, "Y"),
        loft("cannon_top", [(0.2, s * 2.75, -0.13, 0.9, 0.12, 0.05), (-1.6, s * 2.75, -0.13, 0.95, 0.12, 0.05)],
             P["b_accent"], 0.02, "Y"),
        cylinder("barrel", 0.3, 1.0, (s * 2.75, -2.45, -0.75), P["joint"], (90, 0, 0), 16),
        tube("muzzle", 0.38, 0.22, 0.25, (s * 2.75, -2.95, -0.75), P["b_plate"], (90, 0, 0), 16),
        tube("muzzle_glow", 0.24, 0.18, 0.05, (s * 2.75, -3.06, -0.75), P["b_glow"], (90, 0, 0), 16),
        box("arm_glow", (0.05, 1.2, 0.05), (s * 3.36, -0.8, -0.75), P["b_glow"]),
        box("arm_glow2", (0.05, 0.05, 0.9), (s * 3.3, 0.0, 0.2), P["b_glow"]),
    ]
    return parts


def boss_leg(P, s):
    return [
        loft("thigh", [(-2.6, s * 0.95, 0.1, 0.85, 0.95, 0.2), (-1.5, s * 0.9, 0.0, 1.0, 1.1, 0.25)], P["b_plate"],
             0.04),
        cylinder("knee", 0.45, 0.8, (s * 0.95, 0.05, -2.7), P["joint"], (0, 90, 0), 14),
        plate(mirror([(0.7, -0.62, -2.35), (1.2, -0.62, -2.35), (1.15, -0.7, -3.0), (0.75, -0.7, -3.0)], s), 0.2,
              P["b_accent"], 0.03),
        loft("shin", [(-3.9, s * 0.95, 0.15, 0.95, 1.2, 0.25), (-2.75, s * 0.95, 0.0, 1.15, 1.3, 0.3)], P["b_plate"],
             0.05),
        cylinder("nozzle", 0.45, 0.4, (s * 0.95, 0.1, -4.05), P["joint"], segments=16, r2=0.35),
        cylinder("nozzle_glow", 0.3, 0.04, (s * 0.95, 0.1, -4.24), P["b_glow"], segments=16),
        box("shin_glow", (0.05, 0.05, 0.8), (s * 1.53, 0.0, -3.3), P["b_glow"]),
    ]


def build_boss():
    reset_scene()
    P = palette()
    root = empty("Boss")
    torso = [
        loft("body", [(-1.0, 0, 0.1, 1.9, 1.4, 0.3), (-0.3, 0, 0.0, 2.6, 1.9, 0.4), (0.8, 0, -0.1, 3.8, 2.4, 0.5),
                      (1.8, 0, 0.0, 4.0, 2.2, 0.5), (2.35, 0, 0.1, 3.0, 1.7, 0.4)], P["b_plate"], 0.06),
        loft("pelvis", [(-1.6, 0, 0.1, 1.6, 1.2, 0.3), (-0.95, 0, 0.1, 1.9, 1.4, 0.3)], P["b_plate"], 0.05),
        tube("core_bezel", 0.62, 0.4, 0.25, (0, -1.35, 1.0), P["joint"], (90, 0, 0), 8),
        loft("head", [(2.3, 0, -0.35, 1.0, 1.0, 0.2), (2.75, 0, -0.45, 1.1, 1.1, 0.25),
                      (3.05, 0, -0.35, 0.8, 0.8, 0.2)], P["b_plate"], 0.04),
        plate([(-0.38, -1.02, 2.72), (0.38, -1.02, 2.72), (0.3, -0.98, 2.62), (-0.3, -0.98, 2.62)], 0.08, P["b_glow"],
              0.0),
        box("backpack", (2.8, 1.1, 2.2), (0, 1.45, 1.1), P["b_plate"], bevel=0.05),
        box("spine_glow", (0.12, 0.05, 1.6), (0, 2.02, 1.1), P["b_glow"]),
    ]
    for s in (1, -1):
        torso += [
            plate(mirror([(0.35, -1.28, 1.9), (1.75, -1.12, 1.75), (1.85, -1.22, 0.7), (0.5, -1.32, 0.45)], s), 0.25,
                  P["b_accent"], 0.03),
            hull("collar", mirror([(0.6, -0.9, 2.2), (1.6, -0.7, 2.3), (0.6, 0.6, 2.2), (1.6, 0.6, 2.3),
                                   (0.7, -0.6, 3.0), (1.4, -0.4, 2.8), (0.7, 0.4, 3.0), (1.4, 0.4, 2.8)], s),
                 P["b_accent"], 0.04),
            box("rack", (1.0, 1.3, 0.75), (s * 1.3, 0.9, 3.1), P["b_plate"], bevel=0.04),
            box("rack_band", (1.02, 0.15, 0.77), (s * 1.3, 1.2, 3.1), P["e_hazard"]),
            box("side_glow", (0.05, 0.9, 0.06), (s * 1.93, -0.3, 1.2), P["b_glow"]),
        ]
        for dx in (-0.3, 0.0, 0.3):
            for dz in (-0.17, 0.17):
                torso.append(tube("rack_tube", 0.12, 0.08, 0.1, (s * 1.3 + dx, 0.22, 3.1 + dz), P["joint"], (90, 0, 0),
                                  10))
    exhaust = []
    d = (0.0, 0.6, -0.8)
    for x, z in ((0.75, 1.8), (-0.75, 1.8), (0.75, 0.5), (-0.75, 0.5)):
        mid = (x, 2.0 + d[1] * 0.4, z + d[2] * 0.4)
        tip = (x, 2.0 + d[1] * 0.78, z + d[2] * 0.78)
        torso.append(cylinder("thruster", 0.32, 0.8, mid, P["joint"], (-143.13, 0, 0), 16, r2=0.48))
        torso.append(cylinder("thruster_glow", 0.3, 0.04, tip, P["b_glow"], (-143.13, 0, 0), 16))
        exhaust.append((x, 2.0 + d[1] * 0.85, z + d[2] * 0.85))
    body = part(torso, "Torso", (0, 0, 0), root)
    part([icosphere("core", 0.38, (0, -1.4, 1.0), P["b_glow"], 1)], "Core", (0, -1.4, 1.0), body)
    arms = {}
    for s, side in ((1, "L"), (-1, "R")):
        arms[side] = part(boss_arm(P, s), f"Arm_{side}", (s * 2.3, 0, 1.6), body)
        empty(f"Muzzle_Arm_{side}", (s * 2.75, -3.15, -0.75), parent=arms[side])
        leg = part(boss_leg(P, s), f"Leg_{side}", (s * 0.85, 0, -1.5), body)
        empty(f"LegThruster_{side}", (s * 0.95, 0.1, -4.3), parent=leg)
        empty(f"RackMuzzle_{side}", (s * 1.3, 0.1, 3.2), parent=body)
    for i, p in enumerate(exhaust):
        empty(f"Thruster_{i}", p, (36.87, 0, 0), parent=body)
    shield_mat = material("Boss_Shield", (0.25, 0.55, 1.0), 0.0, 0.1, (0.3, 0.6, 1.0), 2.0)
    part([icosphere("shield", 5.6, (0, 0, -0.4), shield_mat, 3, smooth=True)], "Shield", (0, 0, -0.4), root)
    export("boss.glb")


def build():
    build_drone()
    build_turret()
    build_boss()
    log("enemies done")


if __name__ == "__main__":
    build()
