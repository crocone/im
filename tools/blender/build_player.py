"""Powered armor suit (player).

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

Poses: 'standing', 'hover' (combat hover) and 'flight' are exported as actions named
``<pose>__<node>`` and blended at runtime.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (  # noqa: E402
    box, cylinder, empty, export, hull, icosphere, keyframe_poses, log, loft, palette,
    parent_keep, part, reset_scene, tube,
)


def mirror(points, s):
    return [(x * s, y, z) for x, y, z in points]


def plate(front, depth, mat, bevel=0.006, shrink=0.96):
    """Armour plate: a front face polygon extruded backwards (+Y) by ``depth``."""
    back = [(x * shrink, y + depth, z) for x, y, z in front]
    return hull("plate", list(front) + back, mat, bevel)


def torso_parts(P):
    t = []
    t.append(loft("pelvis", [(-0.15, 0, 0.0, 0.22, 0.17, 0.04), (0.0, 0, 0.0, 0.33, 0.23, 0.05),
                             (0.06, 0, 0.0, 0.34, 0.24, 0.05)], P["armor"], 0.012))
    t.append(plate([(-0.06, -0.125, 0.02), (0.06, -0.125, 0.02), (0.035, -0.118, -0.12),
                    (-0.035, -0.118, -0.12)], 0.03, P["accent"]))
    t.append(loft("belt", [(0.05, 0, 0.0, 0.35, 0.25, 0.05), (0.09, 0, 0.0, 0.34, 0.245, 0.05)], P["joint"]))
    t.append(cylinder("abdomen", 0.125, 0.24, (0, 0, 0.18), P["joint"], segments=12))
    for row in range(3):
        z = 0.12 + row * 0.07
        for x in (-0.055, 0.055):
            t.append(loft("ab", [(z - 0.03, x, -0.118, 0.095, 0.028, 0.012),
                                 (z + 0.03, x, -0.121, 0.09, 0.028, 0.012)], P["armor"], 0.005))
    for s in (1, -1):
        t.append(hull("tasset", mirror([(0.15, -0.1, 0.03), (0.15, 0.1, 0.03), (0.2, -0.09, -0.1), (0.2, 0.09, -0.1),
                                        (0.12, -0.1, 0.03), (0.12, 0.1, 0.03), (0.17, -0.09, -0.1),
                                        (0.17, 0.09, -0.1)], s), P["accent"], 0.006))
        t.append(loft("oblique", [(0.1, s * 0.12, 0.0, 0.03, 0.16, 0.01), (0.28, s * 0.14, 0.0, 0.03, 0.18, 0.01)],
                      P["accent"], 0.005))
    t.append(loft("chest", [(0.26, 0, 0.0, 0.34, 0.22, 0.05), (0.4, 0, -0.01, 0.47, 0.31, 0.07),
                            (0.56, 0, -0.01, 0.52, 0.32, 0.08), (0.7, 0, 0.01, 0.43, 0.26, 0.07)], P["armor"], 0.012))
    for s in (1, -1):
        t.append(plate(mirror([(0.085, -0.178, 0.62), (0.225, -0.155, 0.645), (0.25, -0.14, 0.47),
                               (0.09, -0.17, 0.42)], s), 0.045, P["accent"], 0.007))
        # trapezius plates carrying the mini-missile pods
        t.append(hull("trap", mirror([(0.06, -0.08, 0.72), (0.06, 0.1, 0.72), (0.2, -0.07, 0.7), (0.2, 0.1, 0.7),
                                      (0.08, -0.05, 0.775), (0.08, 0.08, 0.775), (0.16, -0.04, 0.755),
                                      (0.16, 0.07, 0.755)], s), P["armor"], 0.008))
        # chest side emissive strips
        t.append(box("strip", (0.012, 0.014, 0.15), (s * 0.258, -0.04, 0.5), P["glow"]))
        # mini-missile pod (shoulder weapon mount)
        t.append(box("minipod", (0.09, 0.16, 0.07), (s * 0.175, 0.0, 0.805), P["accent"], bevel=0.006))
        t.append(box("minipod_rail", (0.1, 0.05, 0.02), (s * 0.175, 0.06, 0.765), P["joint"]))
        for dx in (-0.028, 0.0, 0.028):
            for dz in (-0.016, 0.016):
                t.append(cylinder("minitube", 0.011, 0.02, (s * 0.175 + dx, -0.082, 0.805 + dz), P["joint"],
                                  (90, 0, 0), segments=8))
        # homing missile rails on the upper back
        t.append(cylinder("rail", 0.032, 0.26, (s * 0.125, 0.21, 0.735), P["trim"], (90, 0, 0), segments=12,
                          bevel=0.004))
        t.append(tube("rail_mouth", 0.037, 0.026, 0.03, (s * 0.125, 0.085, 0.735), P["joint"], (90, 0, 0), 12))
        t.append(box("rail_mount", (0.05, 0.12, 0.05), (s * 0.125, 0.22, 0.69), P["joint"]))
        # backpack nozzles
        t.append(cylinder("nozzle", 0.035, 0.06, (s * 0.09, 0.2, 0.31), P["joint"], r2=0.045, segments=12))
        t.append(box("vent", (0.018, 0.012, 0.2), (s * 0.07, 0.243, 0.5), P["glow"]))
    t.append(cylinder("collar", 0.1, 0.07, (0, 0, 0.735), P["joint"], segments=12))
    t.append(cylinder("neck", 0.065, 0.1, (0, 0, 0.79), P["joint"], segments=12))
    t.append(box("backpack", (0.3, 0.1, 0.32), (0, 0.19, 0.49), P["armor"], bevel=0.012))
    t.append(box("spine", (0.06, 0.03, 0.26), (0, 0.25, 0.49), P["accent"], bevel=0.005))
    t.append(cylinder("reactor_bezel", 0.078, 0.03, (0, -0.172, 0.52), P["trim"], (90, 0, 0), segments=6,
                      bevel=0.004))
    return t


def helmet_parts(P):
    h = []
    h.append(loft("head", [(0.785, 0, 0.005, 0.17, 0.19, 0.03), (0.86, 0, 0.0, 0.215, 0.255, 0.05),
                           (0.975, 0, 0.005, 0.228, 0.265, 0.06), (1.045, 0, 0.02, 0.17, 0.2, 0.05)],
                  P["armor"], 0.01))
    front = [(0, -0.152, 0.805), (0.07, -0.128, 0.8), (0.1, -0.12, 0.885), (0.098, -0.128, 0.975),
             (0, -0.148, 0.995), (-0.07, -0.128, 0.8), (-0.1, -0.12, 0.885), (-0.098, -0.128, 0.975)]
    back = [(x * 0.95, y + 0.035, z) for x, y, z in front]
    h.append(hull("faceplate", front + back, P["accent"], 0.006))
    for s in (1, -1):
        eye = mirror([(0.022, -0.157, 0.93), (0.08, -0.137, 0.938), (0.078, -0.138, 0.952), (0.022, -0.158, 0.946)], s)
        h.append(hull("eye", eye + [(x, y + 0.02, z) for x, y, z in eye], P["glow"]))
        h.append(cylinder("ear", 0.04, 0.03, (s * 0.117, 0.01, 0.915), P["joint"], (0, 90, 0), segments=12))
        h.append(cylinder("ear_ring", 0.026, 0.04, (s * 0.117, 0.01, 0.915), P["trim"], (0, 90, 0), segments=12))
        h.append(box("jaw_vent", (0.03, 0.01, 0.018), (s * 0.045, -0.148, 0.83), P["joint"]))
    fin = []
    for x in (-0.016, 0.016):
        fin += [(x, -0.14, 0.99), (x, 0.02, 1.07), (x, 0.12, 1.04), (x, -0.08, 1.035)]
    h.append(hull("crest", fin, P["trim"], 0.004))
    return h


def arm_parts(P, s):
    arm = [
        hull("pauldron", mirror([(0.215, -0.125, 0.6), (0.215, 0.125, 0.6), (0.225, -0.105, 0.765),
                                 (0.225, 0.105, 0.765), (0.415, -0.115, 0.53), (0.415, 0.115, 0.53),
                                 (0.37, -0.095, 0.72), (0.37, 0.095, 0.72), (0.3, -0.12, 0.785),
                                 (0.3, 0.12, 0.785)], s), P["accent"], 0.01),
        hull("pauldron_under", mirror([(0.3, -0.125, 0.46), (0.3, 0.125, 0.46), (0.43, -0.115, 0.44),
                                       (0.43, 0.115, 0.44), (0.3, -0.125, 0.58), (0.3, 0.125, 0.58),
                                       (0.425, -0.115, 0.555), (0.425, 0.115, 0.555)], s), P["armor"], 0.008),
        icosphere("shoulder_ball", 0.075, (s * 0.28, 0, 0.64), P["joint"]),
        cylinder("bicep_core", 0.05, 0.3, (s * 0.305, 0, 0.47), P["joint"], segments=10),
        loft("bicep", [(0.37, s * 0.308, 0.0, 0.11, 0.115, 0.03), (0.47, s * 0.31, 0.0, 0.125, 0.13, 0.035)],
             P["armor"], 0.007),
        box("pauldron_strip", (0.012, 0.13, 0.012), (s * 0.4, 0, 0.6), P["glow"], rot=(0, s * -20, 0)),
    ]
    fore = [
        cylinder("elbow", 0.05, 0.1, (s * 0.305, 0, 0.335), P["joint"], (0, 90, 0), segments=10),
        loft("bracer", [(0.085, s * 0.31, 0.0, 0.1, 0.1, 0.025), (0.2, s * 0.312, 0.0, 0.128, 0.122, 0.03),
                        (0.3, s * 0.307, 0.0, 0.116, 0.112, 0.03)], P["armor"], 0.008),
        loft("bracer_plate", [(0.11, s * 0.373, 0.0, 0.018, 0.085, 0.004),
                              (0.28, s * 0.372, 0.0, 0.018, 0.095, 0.004)], P["accent"], 0.004),
        box("bracer_glow", (0.012, 0.01, 0.13), (s * 0.312, -0.063, 0.19), P["glow"]),
        cylinder("cuff", 0.05, 0.03, (s * 0.31, 0, 0.075), P["trim"], segments=10),
    ]
    hand = [
        loft("palm", [(-0.035, s * 0.31, 0.0, 0.086, 0.044, 0.012), (0.055, s * 0.31, 0.0, 0.094, 0.05, 0.012)],
             P["armor"], 0.005),
        loft("knuckles", [(-0.03, s * 0.31, -0.027, 0.07, 0.012, 0.004), (0.045, s * 0.31, -0.029, 0.078, 0.012, 0.004)],
             P["accent"], 0.003),
        loft("thumb", [(-0.06, s * 0.262, -0.01, 0.018, 0.02, 0.004), (0.02, s * 0.268, -0.005, 0.022, 0.026, 0.004)],
             P["armor"], 0.003),
        cylinder("palm_bezel", 0.03, 0.008, (s * 0.31, 0.024, 0.012), P["trim"], (90, 0, 0), segments=12),
    ]
    for i in range(4):
        fx = s * (0.31 + (i - 1.5) * 0.021)
        hand.append(loft("finger", [(-0.115, fx, 0.012, 0.016, 0.02, 0.004), (-0.035, fx, 0.0, 0.019, 0.025, 0.004)],
                         P["armor"] if i % 2 == 0 else P["joint"], 0.003))
    return arm, fore, hand


def leg_parts(P, s):
    cx = s * 0.125
    leg = [
        cylinder("hip", 0.07, 0.1, (s * 0.12, 0, -0.04), P["joint"], (0, 90, 0), segments=12),
        loft("thigh", [(-0.46, cx, 0.005, 0.12, 0.13, 0.03), (-0.22, s * 0.13, 0.0, 0.158, 0.17, 0.04),
                       (-0.08, s * 0.122, 0.0, 0.15, 0.16, 0.04)], P["armor"], 0.01),
        plate(mirror([(0.1, -0.092, -0.12), (0.16, -0.09, -0.12), (0.165, -0.09, -0.36), (0.105, -0.085, -0.4)], s),
              0.03, P["accent"]),
        box("thigh_glow", (0.01, 0.012, 0.14), (s * 0.2105, 0.0, -0.25), P["glow"]),
        cylinder("knee", 0.058, 0.11, (cx, 0.0, -0.5), P["joint"], (0, 90, 0), segments=12),
        hull("kneecap", mirror([(0.09, -0.07, -0.44), (0.16, -0.07, -0.44), (0.09, -0.085, -0.5), (0.16, -0.085, -0.5),
                                (0.1, -0.07, -0.56), (0.15, -0.07, -0.56), (0.09, -0.035, -0.47), (0.16, -0.035, -0.47),
                                (0.1, -0.035, -0.54), (0.15, -0.035, -0.54)], s), P["accent"], 0.006),
        loft("shin", [(-0.9, cx, 0.005, 0.092, 0.098, 0.025), (-0.7, cx, 0.01, 0.124, 0.13, 0.03),
                      (-0.54, cx, 0.0, 0.114, 0.12, 0.03)], P["armor"], 0.01),
        plate(mirror([(0.1, -0.07, -0.57), (0.15, -0.07, -0.57), (0.14, -0.062, -0.86), (0.11, -0.062, -0.86)], s),
              0.03, P["accent"]),
        box("calf_glow", (0.01, 0.012, 0.14), (s * 0.1895, 0.01, -0.72), P["glow"]),
    ]
    boot = [
        cylinder("ankle", 0.042, 0.1, (cx, 0.0, -0.915), P["joint"], (0, 90, 0), segments=10),
        hull("boot", [(cx - 0.05, 0.065, -1.0), (cx + 0.05, 0.065, -1.0), (cx + 0.05, -0.15, -1.0),
                      (cx - 0.05, -0.15, -1.0), (cx - 0.048, 0.05, -0.89), (cx + 0.048, 0.05, -0.89),
                      (cx + 0.048, -0.035, -0.89), (cx - 0.048, -0.035, -0.89), (cx - 0.044, -0.16, -0.965),
                      (cx + 0.044, -0.16, -0.965)], P["armor"], 0.008),
        hull("toecap", [(cx - 0.049, -0.05, -0.895), (cx + 0.049, -0.05, -0.895), (cx - 0.047, -0.165, -0.962),
                        (cx + 0.047, -0.165, -0.962), (cx - 0.049, -0.05, -0.925), (cx + 0.049, -0.05, -0.925),
                        (cx - 0.047, -0.165, -0.99), (cx + 0.047, -0.165, -0.99)], P["accent"], 0.005),
        box("heel", (0.09, 0.04, 0.07), (cx, 0.06, -0.955), P["accent"], bevel=0.005),
        tube("sole_ring", 0.046, 0.034, 0.018, (cx, -0.03, -1.009), P["joint"], segments=16),
    ]
    return leg, boot


def build():
    reset_scene()
    P = palette()
    root = empty("PlayerRoot")
    torso = part(torso_parts(P), "Torso", (0, 0, 0), root)
    part(helmet_parts(P), "Helmet", (0, 0, 0.78), torso)
    part([cylinder("reactor", 0.058, 0.03, (0, -0.185, 0.52), P["glow"], (90, 0, 0), segments=6)],
         "ChestReactor", (0, -0.185, 0.52), torso)

    nodes = {"Torso": torso}
    for s, side in ((1, "L"), (-1, "R")):
        arm_objs, fore_objs, hand_objs = arm_parts(P, s)
        arm = part(arm_objs, f"Arm_{side}", (s * 0.29, 0, 0.62), torso)
        fore = part(fore_objs, f"Forearm_{side}", (s * 0.305, 0, 0.335), arm)
        hand = part(hand_objs, f"Hand_{side}", (s * 0.31, 0, 0.065), fore)
        palm = cylinder(f"PalmReactor_{side}", 0.022, 0.01, (0, 0, 0), P["glow"], segments=12)
        palm.location = (s * 0.31, 0.03, 0.012)
        palm.rotation_euler = (1.5707963, 0.0, 0.0)  # local -Z -> out of the palm (+Y)
        parent_keep(palm, hand)

        leg_objs, boot_objs = leg_parts(P, s)
        leg = part(leg_objs, f"Leg_{side}", (s * 0.12, 0, -0.04), torso)
        boot = part(boot_objs, f"Boot_{side}", (s * 0.125, 0, -0.915), leg)
        thr = cylinder(f"FootThruster_{side}", 0.034, 0.008, (0, 0, 0), P["glow"], segments=16)
        thr.location = (s * 0.125, -0.03, -1.012)
        parent_keep(thr, boot)

        empty(f"Launcher_{side}", (s * 0.125, 0.06, 0.735), parent=torso)
        empty(f"MiniLauncher_{side}", (s * 0.175, -0.1, 0.805), parent=torso)
        for key, obj in (("Arm", arm), ("Forearm", fore), ("Hand", hand), ("Leg", leg), ("Boot", boot)):
            nodes[f"{key}_{side}"] = obj
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
