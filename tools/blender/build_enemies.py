"""Hostile machines: combat drone, rooftop missile turret and the armored boss.

Forward is -Y in Blender (+Z in three.js). Emissive exhaust markers (``Thruster*``) use
local -Z (Blender) = local -Y (three.js) as the exhaust direction.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from common import (  # noqa: E402
    box, cut, cylinder, empty, export, finish, hull, icosphere, inflate, lathe, log, loft, material, on_surface,
    palette, part, reset_scene, rloft, set_material, set_uv_scale, skin, split, sweep, tube,
)
from pbr import pbr_material  # noqa: E402


def mirror(points, s):
    return [(x * s, y, z) for x, y, z in points]


def plate(front, depth, mat, bevel=0.01):
    return hull("plate", list(front) + [(x * 0.97, y + depth, z) for x, y, z in front], mat, bevel)


# --------------------------------------------------------------------------- drone


def enemy_materials():
    """Hostile machine paint: graphite hull, dark armour, crimson markings, hazard bands, bare steel."""
    return {
        "hull": pbr_material("Enemy_Hull", (0.024, 0.026, 0.03), 0.5, 0.42, "panels", seed=31, wear=0.5, grime=0.5,
                             painted=True, bump=2.0),
        "plate": pbr_material("Enemy_Plate", (0.046, 0.048, 0.054), 0.55, 0.4, "panels_fine", seed=32, wear=0.5,
                              grime=0.45, painted=True, bump=1.8),
        "accent": pbr_material("Enemy_Crimson", (0.21, 0.01, 0.008), 0.25, 0.4, "panels", seed=33, wear=0.55,
                               grime=0.4, painted=True),
        "hazard": pbr_material("Enemy_Hazard", (0.6, 0.33, 0.015), 0.2, 0.48, "panels_large", seed=34, size=256,
                               stripes=((0.018, 0.018, 0.02), 32), painted=True, wear=0.6),
        "mech": pbr_material("Enemy_Mech", (0.085, 0.085, 0.09), 0.9, 0.32, "brushed", seed=35, size=256),
        "glow": material("Emissive_Red", (1.0, 0.12, 0.06), 0.0, 0.3, (1.0, 0.05, 0.018), 12.0),
    }


def rotor_blades(center, count, r0, r1, chord0, chord1, pitch0, pitch1, thick, mat, phase=0.0, stations=5):
    """Twisted airfoil blades around the local Z axis (one mesh per blade)."""
    cx, cy, cz = center
    out = []
    for k in range(count):
        th = phase + 2 * math.pi * k / count
        radial = Vector((math.cos(th), math.sin(th), 0.0))
        tangent = Vector((-math.sin(th), math.cos(th), 0.0))
        rings = []
        for i in range(stations):
            t = i / (stations - 1)
            r = r0 + (r1 - r0) * t
            c = chord0 + (chord1 - chord0) * t
            a = math.radians(pitch0 + (pitch1 - pitch0) * t)
            chord = tangent * math.cos(a) + Vector((0, 0, 1)) * math.sin(a)
            up = Vector((0, 0, 1)) * math.cos(a) - tangent * math.sin(a)
            tk = thick * (1.0 - 0.5 * t)
            ring = []
            for u, v in ((-0.5, 0.0), (-0.3, 0.5), (0.1, 0.42), (0.5, 0.0), (0.1, -0.2), (-0.3, -0.28)):
                p = Vector(center) + radial * r + chord * (u * c) + up * (v * tk)
                ring.append(tuple(p))
            rings.append(ring)
        out.append(skin("blade", rings, mat))
    return out


FUSE = [(-1.08, 0, -0.01, 0.32, 0.28, 2.5), (-0.92, 0, 0.0, 0.56, 0.42, 2.8), (-0.6, 0, 0.03, 0.82, 0.56, 3.2),
        (-0.1, 0, 0.05, 0.94, 0.6, 3.4), (0.42, 0, 0.05, 0.84, 0.54, 3.3), (0.8, 0, 0.04, 0.58, 0.42, 2.9),
        (0.94, 0, 0.04, 0.42, 0.32, 2.6)]
DUCTS = [(1.02, -0.42), (-1.02, -0.42), (0.95, 0.5), (-0.95, 0.5)]
DUCT_PROFILE = [(0.368, -0.07), (0.366, 0.06), (0.372, 0.1), (0.386, 0.126), (0.404, 0.136), (0.452, 0.136),
                (0.474, 0.114), (0.474, -0.07), (0.458, -0.1), (0.39, -0.1)]


def plates(objs, mat, bevel=0.01, grow=0.0):
    out = []
    for o in objs:
        if o is None:
            continue
        set_material(o, mat)
        if grow:
            inflate(o, grow)
        out.append(finish(o, bevel, 2))
    return out


def build_drone():
    reset_scene()
    set_uv_scale(0.8)
    M = enemy_materials()
    root = empty("Drone")
    body = [rloft("fuse_core", [(y, cx, cz, w * 0.93, h * 0.93, p) for y, cx, cz, w, h, p in FUSE], M["hull"], axis="Y",
                  n=24)]
    shell = rloft("fuse", FUSE, M["plate"], axis="Y", n=28)
    top, belly = split(shell, (0, 0, -0.03), (0, 0, 1), 0.018)
    nose, top_rear = split(top, (0, -0.5, 0.1), (0, -1, 0.35), 0.016)
    cowl, tail = split(top_rear, (0, 0.62, 0.1), (0, -1, -0.2), 0.016)
    body += plates([nose], M["accent"], 0.012, 0.004)
    body += plates(cut(cowl, [((0, 0, 0), (1, 0, 0))], 0.05), M["plate"], 0.012)
    body += plates([tail], M["plate"], 0.012)
    body += plates(cut(belly, [((0, 0.2, 0), (0, 1, 0))], 0.02), M["hull"], 0.012)
    # face: visor slot, main eye bezel (the red eye itself is the Sensor node), side eyes
    body.append(tube("eye_bezel", 0.1, 0.07, 0.07, (0, -1.1, -0.01), M["mech"], (90, 0, 0), 24))
    body.append(tube("eye_ring", 0.075, 0.066, 0.02, (0, -1.13, -0.01), M["hull"], (90, 0, 0), 24))
    body.append(tube("eye_iris", 0.042, 0.026, 0.012, (0, -1.15, -0.01), M["hull"], (90, 0, 0), 20))
    for s in (1, -1):
        body.append(cylinder("side_eye_housing", 0.034, 0.05, (s * 0.2, -0.93, 0.1), M["mech"], (90, 0, 0), 12, bevel=0.004))
        body.append(cylinder("side_eye", 0.022, 0.012, (s * 0.2, -0.958, 0.1), M["glow"], (90, 0, 0), 12))
    # twin cannons in gun pods under the chin
    for s in (1, -1):
        gx = s * 0.26
        body.append(rloft("gun_pod", [(-0.8, gx, -0.19, 0.12, 0.12, 2.6), (-0.52, gx, -0.18, 0.16, 0.16, 2.8),
                                      (-0.12, gx, -0.14, 0.13, 0.12, 2.6)], M["hull"], 0.01, axis="Y", n=16, segments=2))
        body.append(box("gun_mount", (0.07, 0.3, 0.08), (s * 0.2, -0.45, -0.12), M["mech"], bevel=0.01))
        body.append(cylinder("barrel", 0.026, 0.36, (gx, -0.96, -0.2), M["mech"], (90, 0, 0), 12))
        body.append(cylinder("shroud", 0.046, 0.2, (gx, -0.88, -0.2), M["mech"], (90, 0, 0), 14, bevel=0.004))
        for k in range(3):
            body.append(tube("shroud_ring", 0.052, 0.04, 0.014, (gx, -0.81 - k * 0.055, -0.2), M["hull"], (90, 0, 0), 14))
        body.append(tube("brake", 0.048, 0.022, 0.08, (gx, -1.11, -0.2), M["mech"], (90, 0, 0), 12))
        body.append(box("brake_slot", (0.1, 0.016, 0.02), (gx, -1.11, -0.2), M["hull"]))
    # cheek intake pods with running lights
    for s in (1, -1):
        body.append(rloft("cheek", [(-0.5, s * 0.49, 0.02, 0.1, 0.18, 2.6), (-0.3, s * 0.52, 0.03, 0.14, 0.24, 2.8),
                                    (0.3, s * 0.52, 0.04, 0.14, 0.24, 2.8), (0.45, s * 0.49, 0.04, 0.1, 0.18, 2.6)],
                          M["accent"], 0.012, axis="Y", n=16, segments=2))
        body.append(box("cheek_intake", (0.1, 0.02, 0.14), (s * 0.52, -0.52, 0.03), M["hull"], bevel=0.004))
        body.append(box("cheek_light", (0.012, 0.5, 0.018), (s * 0.592, -0.05, 0.06), M["glow"]))
    # pylons and ducted fans
    for i, (x, y) in enumerate(DUCTS):
        s = 1 if x > 0 else -1
        body.append(rloft("pylon", [(s * 0.3, y, 0.02, 0.24, 0.15, 2.6), (s * (abs(x) - 0.42), y, 0.06, 0.15, 0.1, 2.6)],
                          M["plate"], 0.01, axis="X", n=16, segments=2))
        body.append(box("pylon_stripe", (0.26, 0.05, 0.014), (s * 0.46, y, 0.104), M["accent"], rot=(0, s * -3, 0),
                        bevel=0.003))
        body.append(sweep("pylon_line", [(s * 0.36, y + 0.07, -0.02), (s * 0.5, y + 0.08, -0.04),
                                         (s * (abs(x) - 0.44), y + 0.06, 0.0)], 0.012, M["mech"], 8))
        duct = lathe("duct", DUCT_PROFILE, 32, (x, y, 0.06), M["plate"], closed=True)
        body += cut(duct, [((x, y, 0), (1, 1, 0)), ((x, y, 0), (1, -1, 0))], 0.012)
        body.append(tube("duct_band", 0.48, 0.468, 0.04, (x, y, 0.13), M["accent"], segments=32))
        body.append(tube("duct_hazard", 0.479, 0.468, 0.028, (x, y, 0.0), M["hazard"], segments=32))
        for k in range(4):
            a = math.radians(45 + 90 * k)
            body.append(box("duct_bracket", (0.035, 0.07, 0.2), (x + math.cos(a) * 0.482, y + math.sin(a) * 0.482, 0.05),
                            M["hull"], rot=(0, 0, math.degrees(a)), bevel=0.008))
        body.append(cylinder("motor", 0.075, 0.13, (x, y, -0.02), M["mech"], segments=16, bevel=0.006))
        body.append(lathe("motor_cap", [(0.075, 0.0), (0.06, -0.03), (0.03, -0.05), (0.0, -0.055)], 16,
                          (x, y, -0.085), M["hull"]))
        body.append(cylinder("duct_glow", 0.045, 0.01, (x, y, -0.14), M["glow"], segments=16))
        for k in range(3):
            a = math.radians(90 + k * 120 + (0 if x > 0 else 60))
            body.append(box("stator", (0.3, 0.03, 0.022), (x + math.cos(a) * 0.22, y + math.sin(a) * 0.22, -0.04),
                            M["hull"], rot=(0, 0, math.degrees(a)), bevel=0.004))
    # tail: thruster nozzle, canted fins, antenna, dorsal vents
    body.append(lathe("nozzle", [(0.17, 0.0), (0.18, 0.03), (0.165, 0.12), (0.14, 0.17), (0.12, 0.165), (0.125, 0.06),
                                 (0.0, 0.06)], 24, (0, 0.9, 0.04), M["mech"], (-90, 0, 0)))
    body.append(tube("nozzle_ring", 0.186, 0.17, 0.03, (0, 0.95, 0.04), M["hull"], (90, 0, 0), 24))
    for s in (1, -1):
        fin = [(s * 0.1, 0.42, 0.3), (s * 0.1, 0.84, 0.25), (s * 0.19, 0.72, 0.53), (s * 0.19, 0.86, 0.52)]
        body.append(hull("fin", fin + [(x + s * 0.018, y, z) for x, y, z in fin], M["accent"], 0.006, 2))
        body.append(box("fin_light", (0.006, 0.08, 0.012), (s * 0.2, 0.8, 0.53), M["glow"]))
        body.append(box("vent_well", (0.13, 0.26, 0.02), (s * 0.2, 0.05, 0.325), M["hull"], rot=(0, s * -12, 0), bevel=0.004))
        for k in range(5):
            body.append(box("louver", (0.12, 0.018, 0.012), (s * 0.2, -0.05 + k * 0.05, 0.337), M["mech"],
                            rot=(-35, s * -12, 0), bevel=0.002))
    body.append(cylinder("antenna", 0.008, 0.3, (0.1, 0.62, 0.42), M["mech"], (8, 0, 0), 6))
    body.append(icosphere("antenna_tip", 0.016, (0.1, 0.6, 0.57), M["glow"], 1))
    body.append(icosphere("belly_turret", 0.085, (0, -0.25, -0.3), M["mech"], 2, smooth=True))
    body.append(cylinder("belly_lens", 0.03, 0.02, (0, -0.33, -0.32), M["glow"], (70, 0, 0), 12))
    part(body, "Body", (0, 0, 0), root)
    set_uv_scale(None)
    eye = lathe("sensor", [(0.0, 0.03), (0.035, 0.026), (0.058, 0.012), (0.064, 0.0), (0.0, 0.0)], 20,
                (0, -1.125, -0.01), M["glow"], (90, 0, 0), 180.0)
    part([eye], "Sensor", (0, -1.07, 0), root)
    part([cylinder("thruster", 0.12, 0.02, (0, 0.95, 0.04), M["glow"], (90, 0, 0), 20)], "Thruster", (0, 1.02, 0.02), root)
    set_uv_scale(0.8)
    for i, (x, y) in enumerate(DUCTS):
        blades = rotor_blades((x, y, 0.075), 5, 0.05, 0.352, 0.085, 0.055, 32, 14, 0.014, M["mech"], phase=i * 0.4)
        blades.append(lathe("spinner", [(0.0, 0.055), (0.03, 0.05), (0.052, 0.03), (0.06, 0.0), (0.0, 0.0)], 16,
                            (x, y, 0.07), M["mech"]))
        part(blades, f"Rotor_{i}", (x, y, 0.07), root)
    set_uv_scale(None)
    empty("Muzzle_L", (0.26, -1.16, -0.2), parent=root)
    empty("Muzzle_R", (-0.26, -1.16, -0.2), parent=root)
    export("drone.glb")


# --------------------------------------------------------------------------- turret


def octagon(r, z, phase=22.5):
    return [(r * math.cos(math.radians(phase + 45 * k)), r * math.sin(math.radians(phase + 45 * k)), z) for k in range(8)]


def missile_pod(M, cx, muzzles):
    """Box launcher with 2x2 tubes; crimson warheads sit just inside the tube mouths."""
    out = []
    shell = rloft("pod", [(-0.96, cx, 2.15, 0.62, 0.7, 4.0), (0.52, cx, 2.17, 0.64, 0.72, 4.0),
                          (0.7, cx, 2.18, 0.56, 0.64, 3.6)], M["plate"], axis="Y", n=24)
    front, rear = split(shell, (0, -0.55, 0), (0, -1, 0), 0.016)
    out += plates([front], M["plate"], 0.014)
    band, rest = split(rear, (0, -0.1, 0), (0, -1, 0), 0.014)
    out += plates([band], M["accent"], 0.012, 0.006)
    out += plates([rest], M["plate"], 0.014)
    out.append(box("pod_hazard", (0.645, 0.08, 0.725), (cx, -0.38, 2.16), M["hazard"], bevel=0.006))
    out.append(box("pod_rail", (0.06, 1.3, 0.05), (cx + (0.33 if cx > 0 else -0.33), -0.2, 2.37), M["mech"], bevel=0.008))
    out.append(box("pod_face", (0.56, 0.03, 0.62), (cx, -0.965, 2.15), M["hull"], bevel=0.01))
    for dx in (-0.145, 0.145):
        for dz in (-0.155, 0.155):
            p = (cx + dx, -0.98, 2.15 + dz)
            out.append(tube("tube_rim", 0.12, 0.09, 0.05, p, M["mech"], (90, 0, 0), 20))
            out.append(cylinder("tube_bore", 0.092, 0.02, (p[0], -0.94, p[2]), M["hull"], (90, 0, 0), 16))
            out.append(lathe("warhead", [(0.0, 0.11), (0.024, 0.1), (0.05, 0.066), (0.068, 0.022), (0.072, 0.0),
                                         (0.072, -0.04)], 16, (p[0], -0.92, p[2]), M["accent"], (90, 0, 0)))
            muzzles.append((p[0], -1.04, p[2]))
    # rear exhaust vents
    for dz in (-0.155, 0.155):
        out.append(box("pod_vent", (0.46, 0.02, 0.1), (cx, 0.715, 2.18 + dz), M["hull"], bevel=0.004))
    return out


def build_turret():
    reset_scene()
    set_uv_scale(0.9)
    M = enemy_materials()
    root = empty("Turret")
    # --- static armoured plinth
    base = [hull("skirt", octagon(1.78, 0.0) + octagon(1.5, 0.46), M["plate"], 0.03, 2),
            hull("deck", octagon(1.5, 0.46) + octagon(1.4, 0.56), M["hull"], 0.015, 1),
            lathe("collar", [(1.2, 0.55), (1.22, 0.64), (1.08, 0.72), (0.98, 1.02), (1.02, 1.1), (1.02, 1.2), (0.0, 1.2)],
                  32, (0, 0, 0), M["hull"]),
            tube("collar_band", 1.045, 0.99, 0.12, (0, 0, 0.86), M["hazard"], segments=32)]
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        c, sn = math.cos(a), math.sin(a)
        foot = [(1.62 * c - 0.14 * sn, 1.62 * sn + 0.14 * c, 0.0), (1.62 * c + 0.14 * sn, 1.62 * sn - 0.14 * c, 0.0),
                (1.9 * c - 0.12 * sn, 1.9 * sn + 0.12 * c, 0.0), (1.9 * c + 0.12 * sn, 1.9 * sn - 0.12 * c, 0.0),
                (1.62 * c - 0.12 * sn, 1.62 * sn + 0.12 * c, 0.3), (1.62 * c + 0.12 * sn, 1.62 * sn - 0.12 * c, 0.3),
                (1.8 * c - 0.1 * sn, 1.8 * sn + 0.1 * c, 0.12), (1.8 * c + 0.1 * sn, 1.8 * sn - 0.1 * c, 0.12)]
        base.append(hull("foot", foot, M["mech"], 0.02, 1))
        base.append(cylinder("bolt", 0.035, 0.05, (1.84 * c, 1.84 * sn, 0.14), M["hull"], (0, 56, math.degrees(a)), 8))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        c, sn = math.cos(a), math.sin(a)
        base.append(sweep("conduit", [(1.45 * c, 1.45 * sn, 0.5), (1.3 * c, 1.3 * sn, 0.62), (1.12 * c, 1.12 * sn, 0.75),
                                      (1.03 * c, 1.03 * sn, 0.9)], 0.045, M["mech"], 10))
    base.append(box("hatch", (0.5, 0.05, 0.26), (0, -1.02, 0.66), M["plate"], rot=(-25, 0, 0), bevel=0.012))
    for s in (1, -1):
        base.append(box("warning_housing", (0.12, 0.08, 0.08), (s * 0.35, -0.99, 1.1), M["mech"], bevel=0.01))
        base.append(box("warning_light", (0.08, 0.02, 0.05), (s * 0.35, -1.03, 1.1), M["glow"]))
    part(base, "Base", (0, 0, 0), root)
    # --- rotating housing (yaw) with the yoke that carries the launcher axle
    yaw_parts = [
        lathe("turntable", [(1.04, 1.2), (1.06, 1.26), (1.0, 1.3), (1.02, 1.4), (0.94, 1.46), (0.0, 1.46)], 36,
              (0, 0, 0), M["mech"]),
        tube("bearing", 1.08, 0.98, 0.03, (0, 0, 1.28), M["hull"], segments=36),
    ]
    housing = loft("housing", [(1.46, 0, 0.12, 1.3, 1.5, 0.25), (1.8, 0, 0.14, 1.2, 1.4, 0.25),
                               (1.95, 0, 0.2, 0.9, 1.0, 0.18)], M["plate"])
    fwd, aft = split(housing, (0, -0.1, 0), (0, -1, 0), 0.02)
    yaw_parts += plates([fwd], M["plate"], 0.025) + plates([aft], M["plate"], 0.025)
    for s in (1, -1):
        cheek = [(s * 0.34, -0.45, 1.6), (s * 0.34, 0.45, 1.6), (s * 0.34, -0.3, 2.42), (s * 0.34, 0.25, 2.42),
                 (s * 0.34, -0.2, 2.55), (s * 0.34, 0.12, 2.55)]
        yaw_parts.append(hull("yoke", cheek + [(x + s * 0.16, y, z) for x, y, z in cheek], M["plate"], 0.02, 2))
        yaw_parts.append(hull("yoke_armor", [(s * 0.505, -0.36, 1.72), (s * 0.505, 0.36, 1.72), (s * 0.505, -0.22, 2.3),
                                             (s * 0.505, 0.18, 2.3), (s * 0.53, -0.3, 1.78), (s * 0.53, 0.3, 1.78),
                                             (s * 0.53, -0.18, 2.24), (s * 0.53, 0.14, 2.24)], M["accent"], 0.012, 2))
        yaw_parts.append(cylinder("bearing_cap", 0.2, 0.08, (s * 0.54, 0, 2.15), M["mech"], (0, 90, 0), 20, bevel=0.012))
        yaw_parts.append(tube("bearing_ring", 0.24, 0.19, 0.05, (s * 0.52, 0, 2.15), M["hull"], (0, 90, 0), 20))
    # rear electronics bay: radiator fins, power cable, status light
    yaw_parts.append(loft("rear_bay", [(0.5, 0, 1.78, 1.0, 0.6, 0.12), (1.0, 0, 1.75, 0.9, 0.52, 0.1)], M["hull"], 0.02,
                          "Y"))
    for k in range(7):
        yaw_parts.append(box("radiator", (0.02, 0.36, 0.44), (-0.33 + k * 0.11, 0.84, 1.76), M["mech"], bevel=0.004))
    yaw_parts.append(box("status_light", (0.3, 0.02, 0.04), (0, 1.02, 2.0), M["glow"]))
    yaw_parts.append(sweep("feed", [(0.22, 0.55, 2.02), (0.3, 0.3, 2.3), (0.32, 0.05, 2.4)], 0.04, M["mech"], 10))
    yaw = part(yaw_parts, "Yaw", (0, 0, 1.35), root)
    # --- elevating launcher (pitch): axle, sensor head, two missile pods
    muzzles_l, muzzles_r = [], []
    head = [cylinder("axle", 0.11, 1.9, (0, 0, 2.15), M["mech"], (0, 90, 0), 16)]
    head += missile_pod(M, 0.9, muzzles_l)
    head += missile_pod(M, -0.9, muzzles_r)
    sensor_shell = rloft("sensor_head", [(-0.72, 0, 2.2, 0.44, 0.4, 3.0), (-0.4, 0, 2.2, 0.56, 0.5, 3.4),
                                         (0.3, 0, 2.18, 0.5, 0.46, 3.2)], M["plate"], axis="Y", n=24)
    nose, aft_s = split(sensor_shell, (0, -0.45, 0), (0, -1, 0), 0.014)
    head += plates([nose], M["accent"], 0.012, 0.004) + plates([aft_s], M["plate"], 0.014)
    head.append(tube("lens_bezel", 0.13, 0.095, 0.06, (0, -0.74, 2.24), M["mech"], (90, 0, 0), 24))
    head.append(cylinder("rangefinder", 0.04, 0.08, (0.14, -0.74, 2.09), M["mech"], (90, 0, 0), 12))
    head.append(cylinder("rangefinder_lens", 0.026, 0.01, (0.14, -0.785, 2.09), M["glow"], (90, 0, 0), 12))
    head.append(box("antenna_mast", (0.03, 0.03, 0.3), (-0.16, 0.2, 2.55), M["mech"]))
    head.append(box("antenna_bar", (0.2, 0.02, 0.02), (-0.16, 0.2, 2.7), M["mech"]))
    pitch = part(head, "Pitch", (0, 0, 2.15), yaw)
    set_uv_scale(None)
    lens = lathe("lens", [(0.0, 0.035), (0.05, 0.028), (0.085, 0.01), (0.09, 0.0), (0.0, 0.0)], 24, (0, -0.765, 2.24),
                 M["glow"], (90, 0, 0), 180.0)
    part([lens], "Sensor", (0, -0.77, 2.24), pitch)
    order = [m for pair in zip(muzzles_l, muzzles_r) for m in pair]
    for k, m in enumerate(order):
        empty(f"Muzzle_{k}", m, parent=pitch)
    export("turret.glb")


# --------------------------------------------------------------------------- boss


def boss_materials():
    return {
        "plate": pbr_material("Boss_Plate", (0.05, 0.052, 0.056), 0.8, 0.36, "panels_large", seed=41, wear=0.5,
                              grime=0.55, bump=1.3),
        "accent": pbr_material("Boss_Crimson", (0.15, 0.011, 0.009), 0.3, 0.4, "panels_large", seed=42, wear=0.6,
                               grime=0.5, painted=True),
        "mech": pbr_material("Boss_Mech", (0.2, 0.2, 0.21), 0.95, 0.28, "brushed", seed=43, size=256),
        "hull": pbr_material("Boss_Hull", (0.02, 0.02, 0.023), 0.5, 0.5, "panels_fine", seed=44, wear=0.2, grime=0.6),
        "hazard": pbr_material("Boss_Hazard", (0.6, 0.33, 0.015), 0.2, 0.48, "panels_large", seed=45, size=256,
                               stripes=((0.018, 0.018, 0.02), 32), painted=True, wear=0.6),
        "glow": material("Emissive_Core", (1.0, 0.35, 0.1), 0.0, 0.3, (1.0, 0.2, 0.04), 14.0),
        # dim running lights: not pumped by the runtime, so the core, visor and exhausts stay the focal glow
        "lights": material("Emissive_Boss_Trim", (1.0, 0.45, 0.2), 0.0, 0.3, (1.0, 0.32, 0.1), 2.5),
    }


def strip_on(name, objs, guide, mat, direction, lift=0.01, depth=0.02, bevel=0.0):
    """Hull hugging the surface of ``objs`` from guide points projected along ``direction``."""
    pts = on_surface(objs, guide, direction, lift, depth)
    return hull(name, pts, mat, bevel, 2) if len(pts) >= 8 else None


def launch_rack(M, cx, cz, muzzle_out):
    """Shoulder missile rack: armoured box, 2x3 tubes with crimson warheads, hazard band, mounting frame."""
    out = []
    shell = rloft("rack", [(0.3, cx, cz, 1.05, 0.8, 4.0), (1.45, cx, cz, 1.1, 0.84, 4.0), (1.62, cx, cz - 0.02, 0.96, 0.7, 3.4)],
                  M["plate"], axis="Y", n=24)
    front, rear = split(shell, (0, 0.62, 0), (0, -1, 0), 0.03)
    out += plates([front], M["plate"], 0.02)
    band, rest = split(rear, (0, 0.95, 0), (0, -1, 0), 0.03)
    out += plates([band], M["accent"], 0.02, 0.01) + plates([rest], M["plate"], 0.02)
    out.append(box("rack_hazard", (1.07, 0.12, 0.82), (cx, 0.5, cz), M["hazard"], bevel=0.01))
    out.append(box("rack_face", (0.95, 0.04, 0.7), (cx, 0.285, cz), M["hull"], bevel=0.012))
    out.append(box("rack_frame", (0.7, 1.1, 0.24), (cx, 0.95, cz - 0.5), M["hull"], bevel=0.03))
    for dx in (-0.3, 0.0, 0.3):
        for dz in (-0.17, 0.17):
            p = (cx + dx, 0.27, cz + dz)
            out.append(tube("rack_rim", 0.13, 0.1, 0.06, p, M["mech"], (90, 0, 0), 16))
            out.append(cylinder("rack_bore", 0.1, 0.02, (p[0], 0.32, p[2]), M["hull"], (90, 0, 0), 14))
            out.append(lathe("rack_warhead", [(0.0, 0.13), (0.03, 0.115), (0.062, 0.075), (0.08, 0.025), (0.084, 0.0),
                                              (0.084, -0.05)], 14, (p[0], 0.34, p[2]), M["accent"], (90, 0, 0)))
    muzzle_out.append((cx, 0.1, cz + 0.1))
    return out


def boss_torso(M):
    t = []
    frame = rloft("frame", [(-1.0, 0, 0.1, 1.7, 1.3, 2.6), (-0.3, 0, 0.0, 2.3, 1.7, 2.8), (0.8, 0, -0.05, 3.2, 2.0, 3.0),
                            (1.8, 0, 0.0, 3.4, 1.95, 3.0), (2.4, 0, 0.1, 2.5, 1.55, 2.8)], M["hull"], n=28)
    t.append(frame)
    chest = rloft("chest", [(0.35, 0, -0.1, 3.3, 2.2, 3.2), (0.95, 0, -0.16, 3.95, 2.5, 3.4),
                            (1.8, 0, -0.06, 4.15, 2.4, 3.4), (2.45, 0, 0.05, 3.1, 1.9, 3.0)], M["plate"], n=32)
    back, front = split(chest, (0, 0.05, 0), (0, 1, 0), 0.05)
    half_l, rest = split(front, (0.48, 0, 0), (1, 0, 0), 0.0)
    half_r, middle = split(rest, (-0.48, 0, 0), (-1, 0, 0), 0.0)
    sternum, _hole = split(middle, (0, 0, 1.62), (0, 0, 1), 0.05)
    if _hole is not None:
        bpy.data.objects.remove(_hole, do_unlink=True)
    t += plates([sternum], M["accent"], 0.025, 0.02)
    for half, s in ((half_l, 1), (half_r, -1)):
        pec, lower = split(half, (0, 0, 1.45), (0, 0.3, 1), 0.05)
        t += plates([pec], M["accent"], 0.03, 0.03)
        side, fr = split(lower, (s * 1.45, 0, 0), (s, 0, 0), 0.04)
        t += plates([side, fr], M["plate"], 0.03)
    upper_b, lower_b = split(back, (0, 0, 1.25), (0, 0, 1), 0.05)
    t += plates(cut(upper_b, [((0, 0, 0), (1, 0, 0))], 0.3), M["plate"], 0.03)
    t += plates(cut(lower_b, [((0, 0, 0), (1, 0, 0))], 0.3), M["plate"], 0.03)
    # abdominal armour bands with a centre seam
    for k, (z0, z1, w, d) in enumerate([(0.02, 0.3, 2.95, 2.05), (-0.34, -0.06, 2.55, 1.85), (-0.7, -0.42, 2.2, 1.62)]):
        band = rloft("ab", [(z0, 0, -0.02, w * 0.94, d * 0.94, 3.0), (z1, 0, -0.02, w, d, 3.0)], M["plate"], n=28)
        t += plates(cut(band, [((0, 0, 0), (1, 0, 0))], 0.04), M["plate"], 0.025)
    t.append(rloft("pelvis", [(-1.65, 0, 0.1, 1.5, 1.15, 2.8), (-1.25, 0, 0.05, 1.95, 1.4, 3.0),
                              (-0.95, 0, 0.05, 2.0, 1.45, 3.0)], M["plate"], 0.03, n=28, segments=2))
    t.append(hull("codpiece", [(-0.42, -0.78, -0.95), (0.42, -0.78, -0.95), (-0.28, -0.7, -1.6), (0.28, -0.7, -1.6),
                               (-0.38, -0.55, -0.95), (0.38, -0.55, -0.95), (-0.25, -0.5, -1.6), (0.25, -0.5, -1.6)],
                  M["accent"], 0.03, 2))
    # caged reactor core (the glowing sphere itself is the Core node)
    t.append(tube("core_bezel", 0.68, 0.44, 0.34, (0, -1.24, 1.0), M["mech"], (90, 22.5, 0), 8))
    t.append(tube("core_ring", 0.47, 0.41, 0.06, (0, -1.42, 1.0), M["glow"], (90, 0, 0), 24))
    for k in range(3):
        a = math.radians(90 + k * 120)
        rim = (math.cos(a) * 0.58, -1.42, 1.0 + math.sin(a) * 0.58)
        mid = (math.cos(a) * 0.36, -1.78, 1.0 + math.sin(a) * 0.36)
        tip = (math.cos(a) * 0.1, -1.86, 1.0 + math.sin(a) * 0.1)
        t.append(sweep("cage", [rim, mid, tip], lambda u: 0.065 - 0.03 * u, M["mech"], 8))
    # head: armoured wedge with a glowing visor slit
    head = rloft("head", [(2.5, 0, -0.42, 0.95, 1.0, 2.8), (2.88, 0, -0.56, 1.15, 1.18, 3.2), (3.2, 0, -0.5, 1.02, 1.02, 3.0),
                          (3.34, 0, -0.42, 0.7, 0.72, 2.6)], M["plate"], n=28)
    face, dome = split(head, (0, -0.76, 2.88), (0, -1, 0.3), 0.025)
    face_p = plates([face], M["accent"], 0.02, 0.012)
    t += face_p + plates([dome], M["plate"], 0.025)
    visor = strip_on("visor", face_p, [(x, z) for x in (-0.36, -0.1, 0.1, 0.36) for z in (2.92, 2.98)], M["glow"],
                     (0, 1, 0), 0.012, 0.03)
    if visor:
        t.append(visor)
    t.append(hull("jaw", [(-0.36, -1.12, 2.6), (0.36, -1.12, 2.6), (-0.3, -1.04, 2.46), (0.3, -1.04, 2.46),
                          (-0.4, -0.72, 2.52), (0.4, -0.72, 2.52), (-0.34, -0.72, 2.4), (0.34, -0.72, 2.4)], M["hull"], 0.02, 2))
    for k in range(4):
        t.append(box("jaw_slot", (0.46 - k * 0.04, 0.03, 0.022), (0, -1.115, 2.56 - k * 0.035), M["lights"], rot=(-20, 0, 0)))
    for s in (1, -1):
        t.append(cylinder("head_sensor", 0.1, 0.16, (s * 0.58, -0.76, 2.88), M["mech"], (0, 90, 0), 16, bevel=0.012))
        t.append(cylinder("head_sensor_eye", 0.06, 0.02, (s * 0.665, -0.76, 2.88), M["lights"], (0, 90, 0), 12))
        t.append(hull("head_fin", [(s * 0.32, -0.1, 3.25), (s * 0.32, 0.3, 3.05), (s * 0.5, 0.2, 3.55), (s * 0.5, 0.4, 3.5),
                                   (s * 0.36, -0.1, 3.25), (s * 0.36, 0.3, 3.05), (s * 0.54, 0.2, 3.55), (s * 0.54, 0.4, 3.5)],
                      M["accent"], 0.012, 2))
    t.append(cylinder("neck", 0.42, 0.5, (0, -0.3, 2.45), M["hull"], segments=20, bevel=0.02))
    # shoulder cowls rising around the head, layered
    for s in (1, -1):
        outer = [(0.62, -0.95, 2.2), (1.62, -0.75, 2.32), (0.62, 0.65, 2.2), (1.62, 0.65, 2.32),
                 (0.72, -0.62, 3.0), (1.42, -0.42, 2.82), (0.72, 0.42, 3.0), (1.42, 0.42, 2.82)]
        t.append(hull("cowl", mirror(outer, s), M["accent"], 0.04, 2))
        inner = [(0.55, -0.7, 2.1), (1.0, -0.6, 2.1), (0.55, 0.5, 2.1), (1.0, 0.5, 2.1),
                 (0.6, -0.5, 3.12), (0.8, -0.4, 3.08), (0.6, 0.35, 3.12), (0.8, 0.3, 3.08)]
        t.append(hull("cowl_inner", mirror(inner, s), M["plate"], 0.03, 2))
        t.append(box("cowl_glow", (0.05, 0.9, 0.05), (s * 1.5, -0.1, 2.62), M["lights"], rot=(0, s * -12, 0)))
    # backpack reactor with thrusters
    pack = rloft("pack", [(0.85, 0, 1.15, 2.7, 2.2, 3.6), (1.6, 0, 1.1, 2.8, 2.3, 3.8), (2.05, 0, 1.08, 2.5, 2.0, 3.4)],
                 M["plate"], axis="Y", n=28)
    t += plates(cut(pack, [((0, 0, 0), (1, 0, 0)), ((0, 0, 1.1), (0, 0, 1))], 0.05), M["plate"], 0.03)
    for s in (1, -1):
        t.append(box("pack_vent", (0.7, 0.05, 0.5), (s * 0.62, 2.07, 1.72), M["hull"], bevel=0.02))
        for k in range(5):
            t.append(box("pack_louver", (0.64, 0.02, 0.07), (s * 0.62, 2.1, 1.54 + k * 0.09), M["mech"], rot=(-35, 0, 0),
                         bevel=0.005))
        t.append(box("pack_glow", (0.6, 0.02, 0.03), (s * 0.62, 2.09, 1.51), M["lights"]))
        t.append(sweep("pack_hose", [(s * 1.25, 1.3, 2.0), (s * 1.6, 1.0, 2.25), (s * 1.9, 0.5, 2.1)], 0.08, M["mech"], 10))
        t.append(sweep("pack_hose", [(s * 1.25, 1.1, 0.4), (s * 1.62, 0.8, 0.55), (s * 1.8, 0.2, 0.7)], 0.07, M["mech"], 10))
        t.append(box("side_glow", (0.05, 0.9, 0.06), (s * 2.02, -0.3, 1.2), M["lights"]))
        for k in range(4):
            t.append(box("side_fin", (0.1, 0.5, 0.06), (s * 1.98, 0.35, 0.5 + k * 0.16), M["mech"], bevel=0.008))
    exhaust = []
    d = Vector((0.0, 0.6, -0.8))
    for x, z in ((0.75, 1.8), (-0.75, 1.8), (0.75, 0.5), (-0.75, 0.5)):
        base = Vector((x, 2.0, z))
        t.append(box("thruster_mount", (0.5, 0.4, 0.5), tuple(base + d * 0.05), M["hull"], rot=(-36.87, 0, 0), bevel=0.03))
        t.append(lathe("thruster", [(0.3, 0.0), (0.34, 0.05), (0.46, 0.6), (0.49, 0.72), (0.43, 0.74), (0.35, 0.3),
                                    (0.24, 0.26), (0.0, 0.26)], 24, tuple(base + d * 0.12), M["mech"], (-143.13, 0, 0)))
        t.append(tube("thruster_ring", 0.5, 0.44, 0.08, tuple(base + d * 0.7), M["hull"], (-143.13, 0, 0), 24))
        t.append(cylinder("thruster_glow", 0.3, 0.02, tuple(base + d * 0.4), M["glow"], (-143.13, 0, 0), 20))
        exhaust.append(tuple(base + d * 0.85))
    racks = []
    for s in (1, -1):
        t += launch_rack(M, s * 1.3, 3.1, racks)
    return t, exhaust, racks


def boss_arm(M, s):
    x = s * 2.75
    parts = [cylinder("shoulder", 0.55, 0.9, (s * 2.3, 0, 1.6), M["hull"], (0, 90, 0), 20, bevel=0.03),
             cylinder("shoulder_disc", 0.36, 1.05, (s * 2.3, 0, 1.6), M["mech"], (0, 90, 0), 20, bevel=0.02)]
    top = [(1.75, -1.05, 2.2), (1.75, 1.0, 2.2), (1.9, -0.9, 2.62), (1.9, 0.85, 2.62), (3.35, -1.0, 2.05), (3.35, 0.95, 2.05),
           (3.1, -0.85, 2.5), (3.1, 0.8, 2.5), (2.5, -1.0, 2.8), (2.5, 0.9, 2.8)]
    parts.append(hull("pauldron", mirror(top, s), M["accent"], 0.05, 2))
    mid = [(2.9, -1.02, 1.45), (2.9, 0.98, 1.45), (3.5, -0.96, 1.3), (3.5, 0.92, 1.3), (3.0, -1.0, 2.15), (3.0, 0.95, 2.15),
           (3.46, -0.92, 2.02), (3.46, 0.88, 2.02)]
    parts.append(hull("pauldron_mid", mirror(mid, s), M["plate"], 0.04, 2))
    low = [(3.0, -0.95, 0.75), (3.0, 0.9, 0.75), (3.52, -0.9, 0.68), (3.52, 0.86, 0.68), (3.02, -0.97, 1.42), (3.02, 0.92, 1.42),
           (3.52, -0.92, 1.36), (3.52, 0.88, 1.36)]
    parts.append(hull("pauldron_low", mirror(low, s), M["plate"], 0.04, 2))
    parts.append(box("pauldron_glow", (0.05, 1.5, 0.06), (s * 3.54, 0.0, 1.04), M["lights"]))
    upper = rloft("upper_arm", [(-0.3, x, 0.0, 0.85, 0.9, 2.8), (0.3, x, 0.0, 1.0, 1.05, 3.0), (0.9, x, 0.0, 0.9, 0.95, 2.8)],
                  M["plate"], n=24)
    parts += plates(cut(upper, [((0, 0, 0), (0, 1, 0))], 0.03), M["plate"], 0.03)
    for dy in (-0.52, 0.52):
        parts.append(cylinder("piston_sleeve", 0.08, 0.6, (x, dy, 0.55), M["hull"], segments=12))
        parts.append(cylinder("piston_rod", 0.045, 0.7, (x, dy, -0.05), M["mech"], segments=12))
    parts.append(cylinder("elbow", 0.5, 0.95, (x, 0, -0.7), M["hull"], (0, 90, 0), 20, bevel=0.03))
    parts.append(cylinder("elbow_disc", 0.3, 1.08, (x, 0, -0.7), M["mech"], (0, 90, 0), 20, bevel=0.02))
    cannon = rloft("cannon", [(0.55, x, -0.75, 1.0, 0.95, 3.0), (0.0, x, -0.75, 1.25, 1.15, 3.4), (-1.3, x, -0.75, 1.3, 1.2, 3.4),
                              (-2.05, x, -0.75, 1.0, 0.95, 3.0)], M["plate"], axis="Y", n=28)
    segs = cut(cannon, [((0, -0.45, 0), (0, 1, 0)), ((0, -1.45, 0), (0, 1, 0))], 0.05)
    segs = plates(segs, M["plate"], 0.03)
    parts += segs
    cap = strip_on("cannon_cap", segs, [(x + dx, y, 0.5) for dx in (-0.28, 0.28) for y in (-1.8, -0.5, 0.35)], M["accent"],
                   (0, 0, -1), 0.03, 0.02, 0.012)
    if cap:
        parts.append(cap)
    for k in range(6):
        parts.append(box("cannon_fin", (0.12, 0.07, 0.8), (x + s * 0.68, -0.55 - k * 0.14, -0.75), M["mech"], bevel=0.01))
    parts.append(cylinder("cell", 0.24, 1.2, (x - s * 0.7, -0.9, -0.62), M["hull"], (90, 0, 0), 16, bevel=0.02))
    for k in range(3):
        parts.append(tube("cell_glow", 0.25, 0.2, 0.05, (x - s * 0.7, -0.5 - k * 0.4, -0.62), M["lights"], (90, 0, 0), 16))
    parts.append(lathe("barrel_shroud", [(0.44, 0.0), (0.44, 0.1), (0.38, 0.15), (0.35, 0.72), (0.4, 0.76), (0.43, 0.92),
                                         (0.37, 1.0), (0.24, 1.0), (0.24, 0.9), (0.0, 0.9)], 24, (x, -2.02, -0.75), M["mech"],
                       (90, 0, 0)))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        parts.append(box("brake_slot", (0.1, 0.16, 0.04), (x + math.cos(a) * 0.4, -2.83, -0.75 + math.sin(a) * 0.4), M["hull"],
                         rot=(0, -math.degrees(a), 0)))
    parts.append(tube("muzzle_glow", 0.25, 0.19, 0.06, (x, -3.0, -0.75), M["glow"], (90, 0, 0), 20))
    parts.append(box("arm_glow", (0.05, 1.2, 0.05), (x + s * 0.66, -0.8, -0.3), M["lights"]))
    return parts


def boss_leg(M, s):
    x = s * 0.95
    parts = [cylinder("hip", 0.5, 0.8, (s * 0.85, 0, -1.5), M["hull"], (0, 90, 0), 20, bevel=0.03),
             cylinder("hip_disc", 0.32, 0.92, (s * 0.85, 0, -1.5), M["mech"], (0, 90, 0), 20, bevel=0.02)]
    thigh = rloft("thigh", [(-2.6, x, 0.1, 0.85, 0.95, 2.8), (-2.0, x, 0.02, 1.05, 1.15, 3.0), (-1.5, x - s * 0.05, 0.0, 1.0, 1.1, 3.0)],
                  M["plate"], n=24)
    back_t, front_t = split(thigh, (0, 0.05, 0), (0, 1, 0), 0.03)
    parts += plates([back_t], M["plate"], 0.03)
    outer, inner = split(front_t, (x, 0, 0), (s, 0, 0), 0.03)
    parts += plates([outer], M["accent"], 0.03, 0.015) + plates([inner], M["plate"], 0.03)
    parts.append(cylinder("knee", 0.45, 0.85, (x, 0.05, -2.7), M["hull"], (0, 90, 0), 20, bevel=0.03))
    parts.append(cylinder("knee_disc", 0.26, 0.98, (x, 0.05, -2.7), M["mech"], (0, 90, 0), 20, bevel=0.02))
    parts.append(hull("kneecap", mirror([(0.62, -0.62, -2.35), (1.28, -0.62, -2.35), (0.66, -0.74, -2.72), (1.24, -0.74, -2.72),
                                         (0.72, -0.62, -3.05), (1.18, -0.62, -3.05), (0.64, -0.35, -2.5), (1.26, -0.35, -2.5),
                                         (0.7, -0.35, -2.95), (1.2, -0.35, -2.95)], s), M["plate"], 0.03, 2))
    parts.append(hull("knee_top", mirror([(0.7, -0.72, -2.38), (1.2, -0.72, -2.38), (0.7, -0.8, -2.62), (1.2, -0.8, -2.62),
                                          (0.7, -0.6, -2.36), (1.2, -0.6, -2.36), (0.7, -0.68, -2.64), (1.2, -0.68, -2.64)], s),
                      M["accent"], 0.015, 2))
    shin = rloft("shin", [(-3.95, x, 0.15, 0.95, 1.15, 2.8), (-3.3, x, 0.05, 1.2, 1.35, 3.2), (-2.78, x, 0.0, 1.12, 1.28, 3.0)],
                 M["plate"], n=24)
    calf, fshin = split(shin, (0, 0.1, -3.3), (0, 1, 0.1), 0.03)
    parts += plates([calf], M["plate"], 0.03) + plates([fshin], M["plate"], 0.03)
    guard = strip_on("shin_guard", [p for p in parts[-1:]], [(x + dx, z) for dx in (-0.22, 0.22) for z in (-2.85, -3.75)],
                     M["accent"], (0, 1, 0), 0.04, 0.02, 0.012)
    if guard:
        parts.append(guard)
    parts.append(box("shin_glow", (0.05, 0.05, 0.8), (s * 1.56, 0.0, -3.3), M["lights"]))
    for k in range(4):
        parts.append(box("calf_fin", (0.6, 0.08, 0.06), (x, 0.74, -3.0 - k * 0.16), M["mech"], bevel=0.008))
    parts.append(cylinder("leg_piston", 0.06, 1.1, (x, 0.62, -2.2), M["mech"], (-8, 0, 0), 12))
    parts.append(lathe("foot_nozzle", [(0.4, 0.0), (0.44, -0.06), (0.5, -0.32), (0.44, -0.36), (0.36, -0.12), (0.0, -0.12)], 24,
                       (x, 0.1, -3.92), M["mech"]))
    parts.append(tube("foot_ring", 0.52, 0.46, 0.06, (x, 0.1, -4.2), M["hull"], segments=24))
    parts.append(cylinder("nozzle_glow", 0.34, 0.02, (x, 0.1, -4.05), M["glow"], segments=20))
    return parts


def build_boss():
    reset_scene()
    set_uv_scale(2.2)
    M = boss_materials()
    root = empty("Boss")
    torso, exhaust, racks = boss_torso(M)
    body = part(torso, "Torso", (0, 0, 0), root)
    set_uv_scale(None)
    part([icosphere("core", 0.38, (0, -1.4, 1.0), M["glow"], 3, smooth=True)], "Core", (0, -1.4, 1.0), body)
    set_uv_scale(2.2)
    for s, side in ((1, "L"), (-1, "R")):
        arm = part(boss_arm(M, s), f"Arm_{side}", (s * 2.3, 0, 1.6), body)
        empty(f"Muzzle_Arm_{side}", (s * 2.75, -3.15, -0.75), parent=arm)
        leg = part(boss_leg(M, s), f"Leg_{side}", (s * 0.85, 0, -1.5), body)
        empty(f"LegThruster_{side}", (s * 0.95, 0.1, -4.3), parent=leg)
    for side, p in zip(("L", "R"), racks):
        empty(f"RackMuzzle_{side}", p, parent=body)
    for i, p in enumerate(exhaust):
        empty(f"Thruster_{i}", p, (36.87, 0, 0), parent=body)
    set_uv_scale(None)
    shield_mat = material("Boss_Shield", (0.25, 0.55, 1.0), 0.0, 0.1, (0.3, 0.6, 1.0), 2.0)
    part([icosphere("shield", 5.6, (0, 0, -0.4), shield_mat, 4, smooth=True)], "Shield", (0, 0, -0.4), root)
    export("boss.glb")


def build():
    build_drone()
    build_turret()
    build_boss()
    log("enemies done")


if __name__ == "__main__":
    build()
