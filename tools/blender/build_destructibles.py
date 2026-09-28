"""Destructible props: intact + fractured GLB pairs.

<name>.glb             <Root>            -> <Root>_Intact (single multi-material mesh)
<name>_fractured.glb   <Root>_Fractured  -> chunk_001 ... chunk_NNN (irregular convex debris)

Chunks keep their exact position inside the intact silhouette, so the runtime swaps the
intact instance for the chunks and lets Rapier take over.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402

from common import (  # noqa: E402
    apply_modifiers, box, box_uv, cylinder, empty, export, hull, icosphere, join, lathe, log, material, parent_keep,
    reset_scene, skin, sweep, tube, _link,
)
import facades  # noqa: E402
import pbr  # noqa: E402
from fracture import cell_fracture_available, fracture  # noqa: E402


def planar_uv(obj, axis_u, axis_v, su, sv, ou=0.0, ov=0.0, mirror_back=None):
    """UVs from two world axes (0=x, 1=y, 2=z); optionally mirror u on faces facing ``mirror_back``."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        flip = mirror_back is not None and f.normal[mirror_back[0]] * mirror_back[1] > 0.5
        for loop in f.loops:
            co = loop.vert.co
            u = co[axis_u] / su + ou
            loop[uv].uv = ((1.0 - u) if flip else u, co[axis_v] / sv + ov)
    bm.to_mesh(obj.data)
    bm.free()


def wall_uv(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        along_x = abs(f.normal.y) >= abs(f.normal.x)
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = ((co.x if along_x else co.y) / 8.0 + 0.5, co.z / 4.0)
    bm.to_mesh(obj.data)
    bm.free()


# --------------------------------------------------------------------------- props


def tex_material(name, maps, metal, rough, emit_strength=0.0):
    """Material from a generated map set (albedo + optional ORM / normal / emission)."""
    albedo = pbr.image(f"{name}_albedo", maps["albedo"])
    emit = pbr.image(f"{name}_emit", maps["emit"]) if "emit" in maps else None
    mat = material(name, (1, 1, 1), metal, rough, (1, 1, 1) if emit else None, emit_strength, albedo, emit)
    pbr.attach_maps(mat, None, pbr.image(f"{name}_orm", maps["orm"], True) if "orm" in maps else None,
                    pbr.image(f"{name}_normal", maps["normal"], True) if "normal" in maps else None)
    return mat


def strut(name, a, b, t, mat):
    """Square bar between two points."""
    pts = []
    for p in (a, b):
        for dx in (-t, t):
            for dy in (-t, t):
                pts.append((p[0] + dx, p[1] + dy, p[2]))
    return hull(name, pts, mat)


def fluted_rings(heights, radii, flutes=20, per=5, depth=0.045):
    """Cross-section rings of a fluted shaft: concave flutes meeting at sharp arrises."""
    rings = []
    for z, radius in zip(heights, radii):
        ring = []
        for k in range(flutes):
            for j in range(per):
                t = j / per
                a = 2 * math.pi * (k + t) / flutes
                r = radius - depth * math.sin(math.pi * t) * radius / 0.58
                ring.append((r * math.cos(a), r * math.sin(a), z))
        rings.append(ring)
    return rings


def column_parts():
    marble = tex_material("Marble", facades.marble_set(), 0.0, 0.3)
    dark = material("Marble_Dark", (0.36, 0.35, 0.33), 0.0, 0.6)
    inner = material("Marble_Broken", (0.55, 0.53, 0.5), 0.0, 0.95)
    shaft = skin("shaft", fluted_rings([0.88, 3.2, 5.6, 7.85], [0.58, 0.595, 0.572, 0.53], flutes=16, per=3), marble)
    parts = [
        (box("plinth", (1.7, 1.7, 0.5), (0, 0, 0.25), dark, bevel=0.03), 3, inner),
        (lathe("base", [(0.0, 0.5), (0.8, 0.5), (0.83, 0.56), (0.8, 0.63), (0.7, 0.7), (0.7, 0.78), (0.64, 0.85),
                        (0.6, 0.88), (0.0, 0.88)], 20, (0, 0, 0), marble, uv_scale=2.0), 2, inner),
        (shaft, 9, inner),
        (lathe("necking", [(0.0, 7.85), (0.55, 7.85), (0.565, 7.91), (0.55, 7.97), (0.0, 7.97)], 20, (0, 0, 0), marble,
               uv_scale=2.0), 1, inner),
        (lathe("echinus", [(0.0, 7.97), (0.54, 7.97), (0.66, 8.08), (0.78, 8.26), (0.81, 8.42), (0.0, 8.42)], 20, (0, 0, 0),
               marble, uv_scale=2.0), 2, inner),
        (box("abacus", (1.8, 1.8, 0.34), (0, 0, 8.59), marble, bevel=0.03), 2, inner),
    ]
    for o, _, _ in parts:
        if not o.data.uv_layers:
            box_uv(o, 2.0)
    return parts


def sign_parts():
    frame = material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5)
    inner = material("Metal_Broken", (0.26, 0.26, 0.27), 0.6, 0.6)
    lamp = material("Lamp_Warm", (1.0, 0.85, 0.6), 0.0, 0.4, (1.0, 0.76, 0.42), 3.5)
    art = facades.billboard_set()
    ad = pbr.image("Billboard_albedo", art["albedo"])
    face = material("Billboard", (1, 1, 1), 0.0, 0.45, (1, 1, 1), 1.6, ad, ad)
    parts = []
    for x in (-2.5, 2.5):
        parts.append((cylinder("pole", 0.2, 7.2, (x, 0, 3.6), frame, segments=12), 2, inner))
    parts.append((join([box("crossbeam", (5.0, 0.16, 0.26), (0, 0, 4.8), frame),
                        strut("diag", (-2.4, 0, 1.2), (2.4, 0, 4.7), 0.05, frame),
                        strut("diag", (2.4, 0, 1.2), (-2.4, 0, 4.7), 0.05, frame)], "bracing"), 2, inner))
    parts.append((box("frame", (7.2, 0.35, 3.3), (0, 0, 8.6), frame, bevel=0.03), 6, inner))
    for y in (-0.195, 0.195):
        f = box("face", (6.8, 0.04, 2.9), (0, y, 8.6), face)
        planar_uv(f, 0, 2, 6.8, 2.9, 0.5, -7.15 / 2.9, mirror_back=(1, 1))
        parts.append((f, 3, inner))
    parts.append((box("catwalk", (7.2, 0.9, 0.08), (0, -0.62, 6.9), frame), 3, inner))
    rail = [box("post", (0.05, 0.05, 1.0), (x, -1.04, 7.44), frame) for x in (-3.55, -1.78, 0.0, 1.78, 3.55)]
    rail += [box("rail", (7.15, 0.05, 0.05), (0, -1.04, 7.93), frame), box("rail", (7.15, 0.04, 0.04), (0, -1.04, 7.45), frame)]
    parts.append((join(rail, "railing"), 2, inner))
    ladder = [box("ladder_rail", (0.04, 0.04, 6.6), (2.5 + dx, -0.32, 3.55), frame) for dx in (-0.22, 0.22)]
    ladder += [box("rung", (0.44, 0.03, 0.03), (2.5, -0.32, 0.5 + k * 0.36), frame) for k in range(18)]
    parts.append((join(ladder, "ladder"), 2, inner))
    for x in (-2.4, 0.0, 2.4):
        parts.append((join([sweep("lamp_arm", [(x, -0.15, 10.2), (x, -0.45, 10.5), (x, -0.85, 10.42)], 0.03, frame, 6),
                            hull("lamp_head", [(x - 0.22, -0.7, 10.36), (x + 0.22, -0.7, 10.36), (x - 0.22, -1.0, 10.33),
                                               (x + 0.22, -1.0, 10.33), (x - 0.18, -0.72, 10.48), (x + 0.18, -0.72, 10.48),
                                               (x - 0.18, -0.98, 10.44), (x + 0.18, -0.98, 10.44)], frame),
                            box("lamp", (0.36, 0.24, 0.03), (x, -0.85, 10.33), lamp, rot=(8, 0, 0))], "lamp"), 1, inner))
    return parts


def water_tower_parts():
    wood = tex_material("Wood_Tank", facades.planks_set(), 0.0, 0.85)
    inner = material("Wood_Broken", (0.46, 0.3, 0.16), 0.0, 0.95)
    steel = material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5)
    roof = material("Metal_Roof", (0.34, 0.36, 0.39), 0.65, 0.45)
    broken = material("Metal_Broken", (0.26, 0.26, 0.27), 0.6, 0.6)
    parts = []
    legs = [(1.9, 1.9), (-1.9, 1.9), (-1.9, -1.9), (1.9, -1.9)]
    for x, y in legs:
        parts.append((box("leg", (0.22, 0.22, 4.1), (x, y, 2.05), steel, bevel=0.02), 2, broken))
    for i in range(4):
        (x0, y0), (x1, y1) = legs[i], legs[(i + 1) % 4]
        parts.append((join([strut("brace", (x0, y0, 0.5), (x1, y1, 3.7), 0.035, steel),
                            strut("brace", (x1, y1, 0.5), (x0, y0, 3.7), 0.035, steel)], "brace"), 1, broken))
    parts.append((tube("platform", 3.15, 2.2, 0.15, (0, 0, 4.17), steel, segments=16), 2, broken))
    parts.append((join([box("joist", (5.6, 0.2, 0.2), (0, 0, 4.05), steel),
                        box("joist", (0.2, 5.6, 0.2), (0, 0, 4.05), steel)], "joists"), 1, broken))
    profile = [(0.0, 4.25), (2.85, 4.25), (2.82, 5.5), (2.78, 7.0), (2.72, 8.65), (0.0, 8.65)]
    # steel hoops are part of the stave texture (normal-mapped bands), not geometry
    parts.append((lathe("tank", profile, 20, (0, 0, 0), wood, uv_scale=2.0), 8, inner))
    parts.append((lathe("roof", [(0.0, 10.35), (0.22, 10.25), (3.05, 8.6), (3.08, 8.52), (0.0, 8.52)], 20, (0, 0, 0), roof),
                  3, broken))
    parts.append((icosphere("finial", 0.2, (0, 0, 10.45), steel), 1, broken))
    ladder = [box("ladder_rail", (0.04, 0.04, 6.0), (2.98, dy, 7.2), steel) for dy in (-0.22, 0.22)]
    ladder += [box("rung", (0.03, 0.44, 0.03), (2.98, 0.0, 4.4 + k * 0.62), steel) for k in range(9)]
    parts.append((join(ladder, "ladder"), 2, broken))
    parts.append((cylinder("outlet", 0.14, 4.2, (0.4, 0.4, 2.1), steel, segments=10), 1, broken))
    for o, _, _ in parts:
        if not o.data.uv_layers:
            box_uv(o, 2.0)
    return parts


def slope_uv(obj, ridge_z, su=4.0):
    """Roof slab UVs: u along the ridge, v down the slope (keeps tile rows horizontal)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co.y / su, math.hypot(co.x, ridge_z - co.z) / su)
    bm.to_mesh(obj.data)
    bm.free()


def small_house_parts():
    wall = tex_material("House_Wall", facades.house_wall_set(), 0.0, 0.85, 1.5)
    tiles = tex_material("Roof_Tile", facades.roof_tiles_set(), 0.0, 0.75)
    render = material("House_Render", (0.72, 0.64, 0.51), 0.0, 0.88)
    trim = material("House_Trim", (0.88, 0.86, 0.82), 0.0, 0.6)
    brick = material("Brick", (0.4, 0.18, 0.11), 0.0, 0.85)
    dark = material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5)
    rubble = material("Rubble", (0.5, 0.47, 0.42), 0.0, 0.95)
    parts = []
    for y in (-3.85, 3.85):
        w = box("wall", (8.0, 0.3, 4.0), (0, y, 2.0), wall)
        wall_uv(w)
        parts.append((w, 5, rubble))
    for x in (-3.85, 3.85):
        w = box("wall", (0.3, 7.4, 4.0), (x, 0, 2.0), wall)
        wall_uv(w)
        parts.append((w, 4, rubble))
    for y in (-3.85, 3.85):
        parts.append((hull("gable", [(-4.0, y - 0.15, 4.0), (4.0, y - 0.15, 4.0), (0.0, y - 0.15, 6.2),
                                     (-4.0, y + 0.15, 4.0), (4.0, y + 0.15, 4.0), (0.0, y + 0.15, 6.2)], render), 2, rubble))
    for sx in (1, -1):
        top = [(0.0, -4.4, 6.42), (0.0, 4.4, 6.42), (sx * 4.5, -4.4, 3.82), (sx * 4.5, 4.4, 3.82)]
        slab = hull("roof", top + [(x, y, z - 0.2) for x, y, z in top], tiles)
        slope_uv(slab, 6.42)
        parts.append((slab, 4, rubble))
        parts.append((box("gutter", (0.14, 8.8, 0.12), (sx * 4.55, 0, 3.78), dark), 1, rubble))
        parts.append((cylinder("downpipe", 0.05, 3.8, (sx * 4.55, 4.3, 1.9), dark, segments=8), 1, rubble))
    parts.append((box("ridge", (0.34, 8.9, 0.16), (0, 0, 6.43), trim), 1, rubble))
    parts.append((join([box("chimney", (0.7, 0.7, 2.6), (2.0, 1.5, 5.6), brick),
                        box("chimney_cap", (0.86, 0.86, 0.12), (2.0, 1.5, 6.95), trim)], "chimney"), 2, rubble))
    parts.append((join([box("canopy", (2.0, 0.9, 0.12), (0, -4.3, 2.85), trim),
                        strut("bracket", (-0.8, -3.72, 2.3), (-0.8, -4.6, 2.8), 0.04, trim),
                        strut("bracket", (0.8, -3.72, 2.3), (0.8, -4.6, 2.8), 0.04, trim)], "porch"), 1, rubble))
    for o, _, _ in parts:
        if not o.data.uv_layers:
            box_uv(o, 2.0)
    return parts


# --------------------------------------------------------------------------- pipeline


def make(file, root_name, builder, seed):
    reset_scene()
    parts = builder()
    parts = [(apply_modifiers(o), n, m) for o, n, m in parts]
    # intact: join copies of every part
    copies = []
    for o, _, _ in parts:
        c = o.copy()
        c.data = o.data.copy()
        _link(c)
        copies.append(c)
    root = empty(root_name)
    intact = join(copies, f"{root_name}_Intact")
    parent_keep(intact, root)
    export(f"{file}.glb", only=[root])
    bpy.data.objects.remove(intact, do_unlink=True)
    bpy.data.objects.remove(root, do_unlink=True)
    # fractured
    froot = empty(f"{root_name}_Fractured")
    counter = [1]
    for i, (o, n, m) in enumerate(parts):
        fracture(o, n, seed * 101 + i * 7, m, froot, counter)
        bpy.data.objects.remove(o, do_unlink=True)
    export(f"{file}_fractured.glb")
    log(f"{file}: {counter[0] - 1} chunks")


def build():
    log(f"fracture method: {'Cell Fracture add-on' if cell_fracture_available() else 'procedural (bmesh)'}")
    make("column", "Column", column_parts, 1)
    make("sign", "Sign", sign_parts, 2)
    make("water_tower", "WaterTower", water_tower_parts, 3)
    make("small_house", "SmallHouse", small_house_parts, 4)
    log("destructibles done")


if __name__ == "__main__":
    build()
