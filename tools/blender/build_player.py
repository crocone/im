"""Powered armor suit (player) - hero asset.

Hierarchy (every name below is a separate node in player.glb):

PlayerRoot
  Torso                      pivot: hips / centre of mass
    Helmet                   pivot: neck
    ChestReactor
    Arm_L / Arm_R            pivot: shoulder
      Forearm_L / _R         pivot: elbow
        Hand_L / _R          pivot: wrist
          PalmReactor_L / _R local -Y (three.js) points out of the palm
    Leg_L / Leg_R            pivot: hip
      Boot_L / Boot_R        pivot: ankle
        FootThruster_L / _R  local -Y points out of the sole
    Launcher_L / _R          homing missile rails (upper back)
    MiniLauncher_L / _R      mini-missile pods (shoulders)

Construction: every armour region starts as a smooth lofted shell that is cut into separate
plates with real seam gaps (``common.cut``), layered over a ribbed undersuit, then bevelled with
weighted normals. Materials are PBR sets (panel-line normals, AO, roughness/metal variation, wear).
Poses 'standing', 'hover' and 'flight' are exported as actions named ``<pose>__<node>``.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (  # noqa: E402
    box, cut, cylinder, empty, export, finish, hull, icosphere, inflate, keyframe_poses, lathe, log, loft,
    material, on_surface, parent_keep, part, ray_hit_any, reset_scene, rloft, set_material, set_uv_scale, split,
    sweep, tube,
)
from pbr import pbr_material  # noqa: E402


def suit_materials():
    return {
        "armor": pbr_material("Armor_Gunmetal", (0.062, 0.066, 0.076), 0.86, 0.3, "panels_large", seed=21,
                              wear=0.45, grime=0.4, bump=1.5, normal_strength=0.85),
        "accent": pbr_material("Armor_Copper", (0.52, 0.16, 0.048), 0.92, 0.27, "panels_large", seed=22,
                               wear=0.4, grime=0.35, bump=1.5, normal_strength=0.85, variation=0.05),
        "trim": pbr_material("Armor_Steel", (0.5, 0.52, 0.55), 0.95, 0.22, "brushed", seed=23, size=256),
        "joint": pbr_material("Joint_Dark", (0.02, 0.021, 0.025), 0.35, 0.55, "ribs", seed=24, size=256, bump=3.0,
                              wear=0.1, grime=0.2),
        "glow": material("Emissive_Cyan", (0.55, 0.92, 1.0), 0.0, 0.3, (0.42, 0.85, 1.0), 4.0),
        "lens": material("Visor_Black", (0.008, 0.01, 0.013), 0.9, 0.06),
    }


def mirror(points, s):
    return [(x * s, y, z) for x, y, z in points]


def plate_finish(objs, mat, bevel=0.005, grow=0.0):
    for o in objs:
        if o is None:
            continue
        set_material(o, mat)
        if grow:
            inflate(o, grow)
        finish(o, bevel, 2)
    return [o for o in objs if o is not None]


# --------------------------------------------------------------------------- torso


CHEST = [(0.27, 0, 0.0, 0.36, 0.22, 2.5), (0.36, 0, -0.012, 0.47, 0.29, 2.6), (0.46, 0, -0.018, 0.54, 0.335, 2.8),
         (0.56, 0, -0.012, 0.57, 0.335, 2.9), (0.66, 0, 0.0, 0.51, 0.295, 2.8), (0.745, 0, 0.012, 0.33, 0.21, 2.5)]


def conform(name, objs, guide, mat, direction=(0, 1, 0), lift=0.004, depth=0.008, bevel=0.003):
    """Plate / strip hugging the surface of ``objs`` (guide points projected along ``direction``)."""
    pts = on_surface(objs, guide, direction, lift, depth)
    return hull(name, pts, mat, bevel, 2) if len(pts) >= 8 else None


def torso_parts(M):
    core = rloft("undersuit", [(-0.14, 0, 0.0, 0.22, 0.16, 2.4), (0.05, 0, 0.0, 0.26, 0.185, 2.4),
                               (0.24, 0, 0.0, 0.25, 0.18, 2.4), (0.4, 0, -0.005, 0.42, 0.26, 2.6),
                               (0.58, 0, -0.005, 0.5, 0.29, 2.6), (0.74, 0, 0.008, 0.3, 0.2, 2.4)], M["joint"], n=24)
    t = [finish(core, 0.0, 1, 40)]
    shell = rloft("chest", CHEST, M["armor"], n=28)
    back, front = split(shell, (0, 0.02, 0), (0, 1, 0), 0.012)
    left, right = split(front, (0, 0, 0), (1, 0, 0), 0.05)
    for half, s in ((left, 1), (right, -1)):
        upper, lower = split(half, (0, 0, 0.40), (0, 0.25, 1), 0.012)
        collar, pec = split(upper, (0, 0, 0.635), (0, 0.3, 1), 0.01)
        t += plate_finish([pec], M["accent"], 0.006, 0.004)
        t += plate_finish([collar], M["armor"], 0.005)
        side, rib = split(lower, (s * 0.165, 0, 0), (s, 0, 0), 0.01)
        t += plate_finish([rib, side], M["armor"], 0.005)
    upper_b, lower_b = split(back, (0, 0, 0.47), (0, 0, 1), 0.012)
    backs = plate_finish(list(split(upper_b, (0, 0, 0), (1, 0, 0), 0.03)), M["accent"], 0.005, 0.003)
    lows = plate_finish(list(split(lower_b, (0, 0, 0), (1, 0, 0), 0.03)), M["armor"], 0.005)
    t += backs + lows
    # sternum channel + reactor housing
    t.append(loft("sternum", [(0.29, 0, -0.158, 0.05, 0.03, 0.012), (0.7, 0, -0.14, 0.044, 0.03, 0.012)], M["trim"], 0.004))
    t.append(cylinder("reactor_bezel", 0.078, 0.034, (0, -0.185, 0.52), M["trim"], (90, 0, 0), 6, bevel=0.004))
    t.append(tube("reactor_frame", 0.1, 0.079, 0.026, (0, -0.178, 0.52), M["accent"], (90, 30, 0), 6))
    for k in range(3):
        a = math.radians(90 + k * 120)
        t.append(box("reactor_strut", (0.012, 0.008, 0.05), (math.cos(a) * 0.028, -0.203, 0.52 + math.sin(a) * 0.028),
                     M["trim"], rot=(0, -math.degrees(a) + 90, 0), bevel=0.002))
    # abdominal plates conforming to the undersuit
    for row in range(3):
        z = 0.1 + row * 0.066
        for s in (1, -1):
            g = [(s * 0.012, z - 0.026), (s * 0.098, z - 0.024), (s * 0.1, z + 0.024), (s * 0.012, z + 0.026),
                 (s * 0.055, z - 0.027), (s * 0.055, z + 0.027)]
            p = conform("ab", core, g, M["armor"], lift=0.012, depth=0.004, bevel=0.005)
            if p:
                t.append(p)
    for s in (1, -1):
        g = [(s * 0.12, 0.06), (s * 0.13, 0.27), (s * 0.075, 0.28), (s * 0.07, 0.08)]
        ob = on_surface(core, [(x, y, z) for x, z in g for y in (-0.04, 0.05)], (-s, 0, 0), 0.01, 0.004)
        t.append(hull("oblique", ob, M["armor"], 0.004, 2))
        t.append(box("oblique_glow", (0.006, 0.12, 0.008), (s * 0.172, 0.0, 0.2), M["glow"], rot=(0, s * 8, 0)))
    # belt, buckle, pelvis, tassets
    t.append(rloft("belt", [(0.012, 0, 0.0, 0.34, 0.245, 2.6), (0.062, 0, 0.0, 0.345, 0.25, 2.6)], M["trim"], 0.004, n=24,
                   segments=2))
    t.append(box("buckle", (0.075, 0.022, 0.05), (0, -0.128, 0.037), M["accent"], bevel=0.005, segments=2))
    for s in (1, -1):
        t.append(box("buckle_pip", (0.012, 0.006, 0.012), (s * 0.022, -0.14, 0.037), M["glow"]))
    t.append(rloft("pelvis", [(-0.16, 0, 0.012, 0.2, 0.15, 2.4), (-0.06, 0, 0.0, 0.3, 0.21, 2.6),
                              (0.02, 0, 0.0, 0.33, 0.235, 2.6)], M["armor"], 0.006, n=24, segments=2))
    t.append(hull("codpiece", [(-0.058, -0.125, 0.0), (0.058, -0.125, 0.0), (0.034, -0.116, -0.13), (-0.034, -0.116, -0.13),
                               (-0.05, -0.095, 0.0), (0.05, -0.095, 0.0), (0.03, -0.088, -0.13), (-0.03, -0.088, -0.13)],
                  M["armor"], 0.005, 2))
    t.append(box("cod_strip", (0.014, 0.01, 0.1), (0, -0.126, -0.06), M["accent"], rot=(-4, 0, 0), bevel=0.003))
    for s in (1, -1):
        t.append(hull("tasset", mirror([(0.15, -0.105, 0.03), (0.15, 0.105, 0.03), (0.205, -0.095, -0.11), (0.205, 0.095, -0.11),
                                        (0.125, -0.1, 0.03), (0.125, 0.1, 0.03), (0.178, -0.09, -0.11), (0.178, 0.09, -0.11)], s),
                      M["armor"], 0.005, 2))
        t.append(hull("tasset_edge", mirror([(0.198, -0.096, -0.085), (0.198, 0.096, -0.085), (0.21, -0.094, -0.118),
                                            (0.21, 0.094, -0.118), (0.186, -0.092, -0.086), (0.186, 0.092, -0.086),
                                            (0.195, -0.09, -0.12), (0.195, 0.09, -0.12)], s), M["accent"], 0.003, 2))
    t.append(hull("glute", [(-0.14, 0.1, 0.0), (0.14, 0.1, 0.0), (-0.12, 0.085, -0.14), (0.12, 0.085, -0.14),
                            (-0.14, 0.125, -0.02), (0.14, 0.125, -0.02), (-0.11, 0.105, -0.12), (0.11, 0.105, -0.12)],
                  M["armor"], 0.005, 2))
    t += back_module(M, lows)
    for k, z in enumerate((0.742, 0.765, 0.788)):
        t.append(cylinder("neck_ring", 0.07 - k * 0.004, 0.02, (0, 0.004, z), M["joint"], segments=20, bevel=0.003))
    return t


def back_module(M, lower_back):
    t = []
    pack = rloft("pack", [(0.13, 0, 0.5, 0.31, 0.34, 3.2), (0.2, 0, 0.5, 0.3, 0.33, 3.2), (0.255, 0, 0.5, 0.25, 0.28, 3.0)],
                 M["armor"], axis="Y", n=20)
    for piece in cut(pack, [((0, 0, 0), (1, 0, 0))], 0.022):
        t += plate_finish([piece], M["armor"], 0.006)
    # segmented spine guard following the lower back
    for k in range(5):
        z = 0.22 + k * 0.045
        p = conform("spine_seg", lower_back, [(x, y, z + dz) for x in (-0.03, 0.03) for dz in (-0.017, 0.017) for y in (0.5,)],
                    M["trim"], direction=(0, -1, 0), lift=0.012, depth=0.004, bevel=0.004)
        if p:
            t.append(p)
    for s in (1, -1):
        t.append(box("vent_well", (0.056, 0.012, 0.19), (s * 0.075, 0.258, 0.5), M["joint"], bevel=0.003))
        t.append(box("vent_frame", (0.062, 0.008, 0.196), (s * 0.075, 0.255, 0.5), M["trim"], bevel=0.002))
        for k in range(2):
            t.append(box("vent_slit", (0.005, 0.004, 0.15), (s * (0.064 + k * 0.022), 0.263, 0.5), M["glow"]))
        for k in range(7):
            t.append(box("louver", (0.05, 0.004, 0.016), (s * 0.075, 0.268, 0.43 + k * 0.0233), M["trim"], rot=(-38, 0, 0),
                         bevel=0.001))
        for k in range(4):
            t.append(box("fin", (0.006, 0.08, 0.05), (s * 0.158, 0.19, 0.42 + k * 0.045), M["trim"], bevel=0.002))
        t.append(lathe("nozzle", [(0.0, 0.0), (0.03, 0.0), (0.036, -0.02), (0.046, -0.06), (0.04, -0.062), (0.028, -0.025),
                                  (0.0, -0.025)], 16, (s * 0.09, 0.2, 0.345), M["joint"]))
        t.append(cylinder("nozzle_glow", 0.026, 0.004, (s * 0.09, 0.2, 0.3), M["glow"], segments=16))
        t.append(cylinder("rail", 0.032, 0.26, (s * 0.125, 0.21, 0.735), M["trim"], (90, 0, 0), 16, bevel=0.004))
        t.append(tube("rail_cap", 0.038, 0.029, 0.03, (s * 0.125, 0.085, 0.735), M["accent"], (90, 0, 0), 16))
        t.append(tube("rail_cap", 0.038, 0.029, 0.02, (s * 0.125, 0.33, 0.735), M["accent"], (90, 0, 0), 16))
        t.append(cylinder("rail_mouth", 0.029, 0.006, (s * 0.125, 0.071, 0.735), M["lens"], (90, 0, 0), 16))
        t.append(box("rail_mount", (0.05, 0.12, 0.05), (s * 0.125, 0.22, 0.69), M["armor"], bevel=0.005, segments=2))
        t.append(hull("trap", mirror([(0.06, -0.08, 0.72), (0.06, 0.1, 0.72), (0.2, -0.07, 0.7), (0.2, 0.1, 0.7),
                                      (0.08, -0.05, 0.775), (0.08, 0.08, 0.775), (0.16, -0.04, 0.755), (0.16, 0.07, 0.755)], s),
                      M["armor"], 0.006, 2))
        t.append(rloft("minipod", [(-0.085, s * 0.175, 0.806, 0.088, 0.066, 3.5), (0.08, s * 0.175, 0.806, 0.09, 0.07, 3.5)],
                       M["accent"], 0.004, axis="Y", n=16, segments=2))
        t.append(box("minipod_rail", (0.1, 0.05, 0.02), (s * 0.175, 0.06, 0.766), M["joint"], bevel=0.003))
        for dx in (-0.027, 0.0, 0.027):
            for dz in (-0.015, 0.015):
                t.append(tube("minitube", 0.012, 0.008, 0.012, (s * 0.175 + dx, -0.087, 0.806 + dz), M["trim"], (90, 0, 0), 10))
                t.append(cylinder("minihole", 0.008, 0.004, (s * 0.175 + dx, -0.084, 0.806 + dz), M["lens"], (90, 0, 0), 8))
    return t


# --------------------------------------------------------------------------- helmet


def helmet_parts(M):
    h = []
    skull = rloft("skull", [(0.786, 0, 0.012, 0.15, 0.17, 2.4), (0.83, 0, 0.0, 0.19, 0.22, 2.6),
                            (0.89, 0, -0.006, 0.212, 0.248, 2.7), (0.96, 0, -0.002, 0.216, 0.254, 2.7),
                            (1.02, 0, 0.01, 0.196, 0.232, 2.6), (1.058, 0, 0.02, 0.15, 0.18, 2.4),
                            (1.078, 0, 0.026, 0.07, 0.1, 2.2)], M["armor"], n=28)
    co = (0, -0.05, 0.9)
    side_l, front = split(skull, co, (0.62, 1, 0.14), 0.007)
    side_r, mask = split(front, co, (-0.62, 1, 0.14), 0.007)
    shells = plate_finish([side_l, side_r], M["armor"], 0.006)
    h += shells
    upper, chin = split(mask, (0, 0, 0.866), (0, 0.3, 1), 0.006)
    face = plate_finish([upper], M["accent"], 0.005, 0.002)
    jaw = plate_finish([chin], M["armor"], 0.005)
    h += face + jaw
    for s in (1, -1):
        rec = conform("eye_recess", face, [(s * 0.014, 0.922), (s * 0.05, 0.925), (s * 0.084, 0.93), (s * 0.082, 0.957),
                                           (s * 0.05, 0.952), (s * 0.016, 0.95)], M["lens"], lift=0.001, depth=0.006, bevel=0)
        eye = conform("eye", face, [(s * 0.022, 0.928), (s * 0.05, 0.93), (s * 0.077, 0.935), (s * 0.075, 0.951),
                                    (s * 0.05, 0.946), (s * 0.024, 0.944)], M["glow"], lift=0.0025, depth=0.004, bevel=0)
        brow = conform("brow", face, [(s * 0.004, 0.957), (s * 0.05, 0.96), (s * 0.095, 0.966), (s * 0.094, 0.978),
                                      (s * 0.05, 0.973), (s * 0.004, 0.97)], M["armor"], lift=0.006, depth=0.004, bevel=0.002)
        cheek = conform("cheek_line", face, [(s * 0.06, 0.905), (s * 0.095, 0.88), (s * 0.097, 0.886), (s * 0.062, 0.911)],
                        M["lens"], lift=0.001, depth=0.004, bevel=0)
        h += [p for p in (rec, eye, brow, cheek) if p]
        hit = ray_hit_any(shells, (s * 0.5, 0.01, 0.915), (-s, 0, 0))
        ex = hit[0].x if hit else s * 0.108
        h.append(cylinder("ear", 0.034, 0.026, (ex + s * 0.008, 0.012, 0.915), M["trim"], (0, 90, 0), 20, bevel=0.004))
        h.append(tube("ear_glow", 0.027, 0.021, 0.03, (ex + s * 0.008, 0.012, 0.915), M["glow"], (0, 90, 0), 20))
        h.append(cylinder("ear_core", 0.02, 0.032, (ex + s * 0.008, 0.012, 0.915), M["joint"], (0, 90, 0), 16))
    for k in range(3):
        g = [(-0.022 + k * 0.004, 0.843 - k * 0.011), (0.022 - k * 0.004, 0.843 - k * 0.011),
             (0.022 - k * 0.004, 0.848 - k * 0.011), (-0.022 + k * 0.004, 0.848 - k * 0.011)]
        slot = conform("grille", jaw, g, M["lens"], lift=0.001, depth=0.004, bevel=0)
        if slot:
            h.append(slot)
    crest = on_surface(shells + face, [(x, y, 1.2) for x in (-0.009, 0.009) for y in (-0.1, -0.05, 0.0, 0.05, 0.1, 0.13)],
                       (0, 0, -1), 0.012, 0.004)
    h.append(hull("crest", crest, M["accent"], 0.003, 2))
    h.append(hull("neck_guard", [(-0.1, 0.08, 0.8), (0.1, 0.08, 0.8), (-0.105, 0.115, 0.87), (0.105, 0.115, 0.87),
                                 (-0.09, 0.105, 0.8), (0.09, 0.105, 0.8), (-0.095, 0.14, 0.87), (0.095, 0.14, 0.87)],
                  M["armor"], 0.004, 2))
    return h


# --------------------------------------------------------------------------- arms


def pauldron(M, s):
    """Three angular bands stacked over the shoulder (top band in the accent colour)."""
    out = []
    bands = [(0.656, (0.125, 0.126, 0.092), (0, 50), 125, "accent", 0.006),
             (0.63, (0.137, 0.134, 0.104), (44, 74), 115, "armor", 0.0),
             (0.6, (0.145, 0.14, 0.11), (68, 96), 110, "armor", 0.0)]
    for cz, (rx, ry, rz), (t0, t1), span, key, grow in bands:
        pts = []
        for th in (t0, (t0 + t1) / 2, t1):
            for ph in range(-span, span + 1, 25 if th > 0 else 360):
                a, b = math.radians(th), math.radians(ph)
                for k in (1.0, 0.8):
                    pts.append((s * 0.305 + s * rx * k * math.sin(a) * math.cos(b), ry * k * math.sin(a) * math.sin(b),
                                cz + rz * k * math.cos(a)))
        band = hull("pauldron", pts, M[key])
        out += plate_finish([band], M[key], 0.005, grow)
    out.append(box("pauldron_glow", (0.008, 0.14, 0.007), (s * 0.435, 0.0, 0.598), M["glow"], rot=(0, s * -40, 0)))
    return out


def arm_parts(M, s):
    arm = pauldron(M, s) + [
        icosphere("shoulder_ball", 0.075, (s * 0.28, 0, 0.64), M["joint"], 2, smooth=True),
        cylinder("bicep_core", 0.052, 0.24, (s * 0.305, 0, 0.45), M["joint"], segments=16),
        tube("armband", 0.068, 0.054, 0.02, (s * 0.307, 0, 0.385), M["trim"], segments=20),
    ]
    sleeve = rloft("bicep", [(0.395, s * 0.308, 0.0, 0.112, 0.12, 2.4), (0.46, s * 0.31, 0.0, 0.128, 0.134, 2.5),
                             (0.53, s * 0.308, 0.0, 0.118, 0.124, 2.4)], M["armor"], n=18)
    arm += plate_finish(list(split(sleeve, (0, 0.0, 0), (0, 1, 0), 0.01)), M["armor"], 0.005)

    fore = [
        cylinder("elbow", 0.052, 0.1, (s * 0.305, 0, 0.335), M["joint"], (0, 90, 0), 16),
        cylinder("elbow_disc", 0.034, 0.12, (s * 0.305, 0, 0.335), M["trim"], (0, 90, 0), 16, bevel=0.003),
        hull("elbow_cop", mirror([(0.26, 0.035, 0.37), (0.35, 0.035, 0.37), (0.27, 0.075, 0.33), (0.34, 0.075, 0.33),
                                  (0.275, 0.05, 0.285), (0.335, 0.05, 0.285), (0.3, 0.085, 0.34)], s), M["armor"], 0.005, 2),
        tube("cuff", 0.052, 0.042, 0.026, (s * 0.31, 0, 0.078), M["trim"], segments=20),
    ]
    shell = rloft("bracer", [(0.085, s * 0.31, 0.0, 0.1, 0.1, 2.4), (0.2, s * 0.312, 0.0, 0.13, 0.124, 2.5),
                             (0.3, s * 0.307, 0.0, 0.118, 0.114, 2.5)], M["armor"], n=18)
    outer, inner = split(shell, (s * 0.31, 0, 0), (s, -0.45, 0), 0.009)
    outer_p = plate_finish([outer], M["accent"], 0.005, 0.002)
    fore += outer_p
    fore += plate_finish([inner], M["armor"], 0.005)
    strip = conform("bracer_glow", outer_p, [(s * 0.335, y, z) for y in (-0.1,) for z in (0.13, 0.25)] +
                    [(s * 0.345, -0.1, z) for z in (0.13, 0.25)], M["glow"], direction=(0, 1, 0), lift=0.002, depth=0.003,
                    bevel=0)
    if strip:
        fore.append(strip)
    for k, z in enumerate((0.27, 0.12)):
        fore.append(cylinder("piston", 0.009, 0.1, (s * (0.29 + k * 0.03), 0.058, z + 0.02), M["trim"], (0, 0, 0), 10))
    fore.append(sweep("hose", [(s * 0.34, 0.03, 0.29), (s * 0.36, 0.045, 0.2), (s * 0.35, 0.04, 0.1)], 0.007, M["joint"], 8))

    hand = [
        rloft("palm", [(-0.035, s * 0.31, 0.0, 0.086, 0.044, 3.0), (0.055, s * 0.31, 0.0, 0.094, 0.05, 3.0)],
              M["armor"], 0.004, n=16, segments=2),
        rloft("knuckles", [(-0.03, s * 0.31, -0.028, 0.072, 0.012, 3.5), (0.045, s * 0.31, -0.031, 0.08, 0.012, 3.5)],
              M["accent"], 0.003, n=16, segments=2),
        box("knuckle_guard", (0.086, 0.014, 0.016), (s * 0.31, -0.024, -0.032), M["trim"], bevel=0.003, segments=2),
        tube("palm_bezel", 0.031, 0.022, 0.008, (s * 0.31, 0.024, 0.012), M["trim"], (90, 0, 0), 20),
        cylinder("palm_pad", 0.024, 0.006, (s * 0.31, 0.022, 0.012), M["joint"], (90, 0, 0), 16),
    ]
    for i in range(4):
        fx = s * (0.31 + (i - 1.5) * 0.021)
        z, y = -0.036, 0.0
        for k, length in enumerate((0.034, 0.027, 0.022)):
            ang = 7 + k * 9
            cz = z - length / 2 * math.cos(math.radians(ang))
            cy = y + length / 2 * math.sin(math.radians(ang))
            hand.append(box("finger", (0.0165, 0.021 - k * 0.002, length), (fx, cy, cz), M["armor"], rot=(ang, 0, 0),
                            bevel=0.0035, segments=2))
            z -= length * math.cos(math.radians(ang)) + 0.003
            y += length * math.sin(math.radians(ang))
            hand.append(cylinder("knuckle", 0.007, 0.017, (fx, y - 0.001, z + 0.0015), M["joint"], (0, 90, 0), 8))
    hand.append(box("thumb_a", (0.02, 0.022, 0.034), (s * 0.262, -0.008, -0.01), M["armor"], rot=(0, s * 20, 0), bevel=0.0035, segments=2))
    hand.append(box("thumb_b", (0.018, 0.02, 0.026), (s * 0.252, -0.006, -0.042), M["armor"], rot=(12, s * 28, 0), bevel=0.0035, segments=2))
    return arm, fore, hand


# --------------------------------------------------------------------------- legs


def leg_parts(M, s):
    cx = s * 0.125
    leg = [
        cylinder("hip", 0.07, 0.1, (s * 0.12, 0, -0.04), M["joint"], (0, 90, 0), 16),
        cylinder("thigh_core", 0.062, 0.4, (cx, 0.0, -0.27), M["joint"], segments=16),
        cylinder("knee", 0.058, 0.11, (cx, 0.0, -0.5), M["joint"], (0, 90, 0), 16),
        cylinder("knee_disc", 0.032, 0.14, (cx, 0.0, -0.5), M["trim"], (0, 90, 0), 16, bevel=0.003),
        cylinder("shin_core", 0.052, 0.36, (cx, 0.004, -0.72), M["joint"], segments=16),
    ]
    thigh = rloft("thigh", [(-0.46, cx, 0.005, 0.132, 0.142, 2.4), (-0.3, s * 0.13, 0.0, 0.178, 0.19, 2.5),
                            (-0.13, s * 0.124, 0.0, 0.172, 0.182, 2.5), (-0.065, s * 0.118, 0.0, 0.152, 0.16, 2.4)],
                  M["armor"], n=20)
    back, front = split(thigh, (0, 0.012, 0), (0, 1, 0), 0.01)
    leg += plate_finish([back], M["armor"], 0.006)
    outer, inner = split(front, (cx + s * 0.018, 0, 0), (s, 0, 0), 0.009)
    leg += plate_finish([outer], M["accent"], 0.006, 0.003)
    leg += plate_finish([inner], M["armor"], 0.006)
    leg.append(box("thigh_glow", (0.008, 0.01, 0.13), (s * 0.214, 0.03, -0.26), M["glow"]))
    kp = mirror([(0.09, -0.066, -0.44), (0.16, -0.066, -0.44), (0.088, -0.086, -0.5), (0.162, -0.086, -0.5),
                 (0.1, -0.07, -0.565), (0.15, -0.07, -0.565), (0.09, -0.03, -0.47), (0.16, -0.03, -0.47),
                 (0.1, -0.03, -0.54), (0.15, -0.03, -0.54)], s)
    leg.append(hull("kneecap", kp, M["armor"], 0.005, 2))
    leg.append(hull("knee_top", mirror([(0.1, -0.08, -0.45), (0.15, -0.08, -0.45), (0.098, -0.094, -0.495), (0.152, -0.094, -0.495),
                                        (0.1, -0.07, -0.445), (0.15, -0.07, -0.445), (0.1, -0.08, -0.5), (0.15, -0.08, -0.5)], s),
                    M["accent"], 0.003, 2))
    shin = rloft("shin", [(-0.9, cx, 0.006, 0.1, 0.106, 2.4), (-0.72, cx, 0.012, 0.14, 0.149, 2.5),
                          (-0.555, cx, 0.0, 0.128, 0.134, 2.5)], M["armor"], n=20)
    calf, front_shin = split(shin, (0, 0.016, -0.72), (0, 1, 0.12), 0.01)
    fs = plate_finish([front_shin], M["armor"], 0.006)
    leg += fs + plate_finish([calf], M["accent"], 0.006, 0.002)
    guard = conform("shin_guard", fs, [(cx - 0.024, -0.58), (cx + 0.024, -0.58), (cx + 0.018, -0.86), (cx - 0.018, -0.86)],
                    M["accent"], lift=0.008, depth=0.004, bevel=0.003)
    if guard:
        leg.append(guard)
    leg.append(box("calf_well", (0.05, 0.012, 0.13), (cx, 0.088, -0.72), M["joint"], rot=(-6, 0, 0), bevel=0.003))
    for k in range(2):
        leg.append(box("calf_slit", (0.005, 0.004, 0.1), (cx + (k - 0.5) * 0.02, 0.093, -0.72), M["glow"], rot=(-6, 0, 0)))
    for k in range(5):
        leg.append(box("calf_louver", (0.044, 0.004, 0.014), (cx, 0.097 - k * 0.0012, -0.768 + k * 0.024), M["trim"],
                       rot=(-44, 0, 0), bevel=0.001))
    leg.append(box("calf_glow", (0.006, 0.008, 0.12), (s * 0.197, 0.012, -0.72), M["glow"]))

    boot = [cylinder("ankle", 0.043, 0.1, (cx, 0.0, -0.915), M["joint"], (0, 90, 0), 16),
            cylinder("ankle_disc", 0.028, 0.114, (cx, 0.0, -0.915), M["trim"], (0, 90, 0), 16, bevel=0.003)]
    foot = hull("foot", [(cx - 0.05, 0.068, -1.0), (cx + 0.05, 0.068, -1.0), (cx + 0.05, -0.15, -1.0),
                         (cx - 0.05, -0.15, -1.0), (cx - 0.049, 0.052, -0.885), (cx + 0.049, 0.052, -0.885),
                         (cx + 0.049, -0.035, -0.885), (cx - 0.049, -0.035, -0.885), (cx - 0.045, -0.165, -0.966),
                         (cx + 0.045, -0.165, -0.966), (cx - 0.046, -0.172, -0.99), (cx + 0.046, -0.172, -0.99)], M["armor"])
    toe, heel_part = split(foot, (0, -0.075, -0.95), (0, -1, -0.25), 0.007)
    boot += plate_finish([toe], M["accent"], 0.005, 0.002)
    boot += plate_finish([heel_part], M["armor"], 0.005)
    boot += [
        hull("heel", [(cx - 0.04, 0.05, -1.0), (cx + 0.04, 0.05, -1.0), (cx - 0.036, 0.085, -0.985), (cx + 0.036, 0.085, -0.985),
                      (cx - 0.04, 0.05, -0.93), (cx + 0.04, 0.05, -0.93), (cx - 0.03, 0.078, -0.94), (cx + 0.03, 0.078, -0.94)],
             M["trim"], 0.004, 2),
        loft("sole", [(-1.012, cx, -0.04, 0.104, 0.22, 0.03), (-0.999, cx, -0.04, 0.104, 0.22, 0.03)], M["joint"], 0.003),
        tube("sole_ring", 0.048, 0.034, 0.02, (cx, -0.03, -1.011), M["trim"], segments=20),
    ]
    for side in (1, -1):
        boot.append(hull("ankle_guard", [(cx + side * 0.052, -0.03, -0.87), (cx + side * 0.052, 0.04, -0.87),
                                         (cx + side * 0.055, -0.03, -0.94), (cx + side * 0.055, 0.045, -0.94),
                                         (cx + side * 0.04, -0.03, -0.87), (cx + side * 0.04, 0.04, -0.87),
                                         (cx + side * 0.043, -0.03, -0.94), (cx + side * 0.043, 0.045, -0.94)],
                         M["armor"], 0.003, 2))
    return leg, boot


# --------------------------------------------------------------------------- assembly


def build():
    reset_scene()
    set_uv_scale(0.55)
    M = suit_materials()
    root = empty("PlayerRoot")
    torso = part(torso_parts(M), "Torso", (0, 0, 0), root)
    part(helmet_parts(M), "Helmet", (0, 0, 0.78), torso)
    part([cylinder("reactor", 0.056, 0.03, (0, -0.19, 0.52), M["glow"], (90, 0, 0), 6)], "ChestReactor", (0, -0.19, 0.52), torso)

    nodes = {"Torso": torso}
    for s, side in ((1, "L"), (-1, "R")):
        arm_objs, fore_objs, hand_objs = arm_parts(M, s)
        arm = part(arm_objs, f"Arm_{side}", (s * 0.29, 0, 0.62), torso)
        fore = part(fore_objs, f"Forearm_{side}", (s * 0.305, 0, 0.335), arm)
        hand = part(hand_objs, f"Hand_{side}", (s * 0.31, 0, 0.065), fore)
        set_uv_scale(None)
        palm = cylinder(f"PalmReactor_{side}", 0.021, 0.01, (0, 0, 0), M["glow"], segments=16)
        set_uv_scale(0.55)
        palm.location = (s * 0.31, 0.029, 0.012)
        palm.rotation_euler = (1.5707963, 0.0, 0.0)  # local -Z -> out of the palm (+Y)
        parent_keep(palm, hand)

        leg_objs, boot_objs = leg_parts(M, s)
        leg = part(leg_objs, f"Leg_{side}", (s * 0.12, 0, -0.04), torso)
        boot = part(boot_objs, f"Boot_{side}", (s * 0.125, 0, -0.915), leg)
        set_uv_scale(None)
        thr = cylinder(f"FootThruster_{side}", 0.034, 0.008, (0, 0, 0), M["glow"], segments=20)
        set_uv_scale(0.55)
        thr.location = (s * 0.125, -0.03, -1.014)
        parent_keep(thr, boot)

        empty(f"Launcher_{side}", (s * 0.125, 0.06, 0.735), parent=torso)
        empty(f"MiniLauncher_{side}", (s * 0.175, -0.1, 0.806), parent=torso)
        for key, obj in (("Arm", arm), ("Forearm", fore), ("Hand", hand), ("Leg", leg), ("Boot", boot)):
            nodes[f"{key}_{side}"] = obj
    set_uv_scale(None)
    nodes["Helmet"] = next(o for o in torso.children if o.name == "Helmet")

    poses = {
        "standing": {
            "Arm_L": (0, -8, 0), "Arm_R": (0, 8, 0),
            "Forearm_L": (-12, 0, 0), "Forearm_R": (-12, 0, 0),
            "Leg_L": (0, -3, 0), "Leg_R": (0, 3, 0),
            "Boot_L": (0, 3, 0), "Boot_R": (0, -3, 0),
        },
        "hover": {
            "Torso": (6, 0, 0), "Helmet": (-6, 0, 0),
            "Arm_L": (-12, -28, 0), "Arm_R": (-12, 28, 0),
            "Forearm_L": (-20, 0, 0), "Forearm_R": (-20, 0, 0),
            "Hand_L": (-85, 0, 0), "Hand_R": (-85, 0, 0),
            "Leg_L": (-14, -6, 0), "Leg_R": (-4, 5, 0),
            "Boot_L": (25, 0, 0), "Boot_R": (20, 0, 0),
        },
        "flight": {
            "Torso": (82, 0, 0), "Helmet": (-78, 0, 0),
            "Arm_L": (-6, -14, 0), "Arm_R": (-6, 14, 0),
            "Hand_L": (-90, 0, 0), "Hand_R": (-90, 0, 0),
            "Leg_L": (-4, -3, 0), "Leg_R": (-10, 3, 0),
            "Boot_L": (5, 0, 0), "Boot_R": (10, 0, 0),
        },
    }
    keyframe_poses(nodes, poses)
    export("player.glb", animations=True)
    log("player done")


if __name__ == "__main__":
    build()
