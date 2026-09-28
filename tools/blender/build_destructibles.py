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
    apply_modifiers, box, cylinder, empty, export, hull, icosphere, join, log, material, parent_keep, prism,
    regular_polygon, reset_scene, tube, _link,
)
from fracture import cell_fracture_available, fracture  # noqa: E402
from textures import ad_texture, house_wall_texture, image  # noqa: E402


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


def column_parts():
    marble = material("Marble", (0.72, 0.7, 0.65), 0.0, 0.5)
    dark = material("Marble_Dark", (0.36, 0.35, 0.33), 0.0, 0.6)
    inner = material("Marble_Broken", (0.55, 0.53, 0.5), 0.0, 0.95)
    flutes = [(r * (1.0 if i % 2 == 0 else 0.9) * math.cos(a), r * (1.0 if i % 2 == 0 else 0.9) * math.sin(a))
              for i, (a, r) in enumerate((2 * math.pi * k / 32, 0.58) for k in range(32))]
    return [
        (box("plinth", (1.7, 1.7, 0.6), (0, 0, 0.3), dark, bevel=0.03), 3, inner),
        (cylinder("torus", 0.78, 0.3, (0, 0, 0.75), marble, segments=20), 2, inner),
        (prism("shaft", flutes, 0.9, 8.1, [marble, marble], sharp=50), 9, inner),
        (cylinder("echinus", 0.6, 0.45, (0, 0, 8.33), marble, segments=20, r2=0.82), 2, inner),
        (box("abacus", (1.8, 1.8, 0.35), (0, 0, 8.73), marble, bevel=0.03), 2, inner),
    ]


def sign_parts():
    frame = material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5)
    inner = material("Metal_Broken", (0.26, 0.26, 0.27), 0.6, 0.6)
    lamp = material("Lamp_Warm", (1.0, 0.85, 0.6), 0.0, 0.4, (1.0, 0.76, 0.42), 9.0)
    ad = image("Billboard", ad_texture)
    face = material("Billboard", (1, 1, 1), 0.0, 0.5, (1, 1, 1), 1.6, ad, ad)
    parts = []
    for x in (-2.5, 2.5):
        parts.append((cylinder("pole", 0.18, 7.2, (x, 0, 3.6), frame, segments=12), 2, inner))
    parts.append((box("frame", (7.2, 0.35, 3.3), (0, 0, 8.6), frame, bevel=0.03), 6, inner))
    for y in (-0.195, 0.195):
        f = box("face", (6.8, 0.04, 2.9), (0, y, 8.6), face)
        planar_uv(f, 0, 2, 6.8, 2.9, 0.5, -7.15 / 2.9, mirror_back=(1, 1))
        parts.append((f, 3, inner))
    parts.append((box("catwalk", (7.2, 0.9, 0.1), (0, -0.55, 6.9), frame), 3, inner))
    for x in (-2.4, 0.0, 2.4):
        parts.append((join([box("lamp_arm", (0.08, 0.6, 0.08), (x, -0.45, 10.35), frame),
                            box("lamp", (0.4, 0.22, 0.12), (x, -0.75, 10.3), lamp)], "lamp"), 1, inner))
    return parts


def water_tower_parts():
    wood = material("Wood_Tank", (0.3, 0.17, 0.09), 0.0, 0.85)
    inner = material("Wood_Broken", (0.46, 0.3, 0.16), 0.0, 0.95)
    steel = material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5)
    roof = material("Metal_Roof", (0.34, 0.36, 0.39), 0.65, 0.45)
    broken = material("Metal_Broken", (0.26, 0.26, 0.27), 0.6, 0.6)
    parts = []
    legs = [(1.9, 1.9), (-1.9, 1.9), (-1.9, -1.9), (1.9, -1.9)]
    for x, y in legs:
        parts.append((cylinder("leg", 0.14, 4.1, (x, y, 2.05), steel, segments=8), 2, broken))
    for i in range(4):
        (x0, y0), (x1, y1) = legs[i], legs[(i + 1) % 4]
        length = math.hypot(x1 - x0, y1 - y0)
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        cross = [box("brace", (length * 1.25, 0.07, 0.07), ((x0 + x1) / 2, (y0 + y1) / 2, 2.1), steel,
                     rot=(0, tilt, ang)) for tilt in (38, -38)]
        parts.append((join(cross, "brace"), 1, broken))
    parts.append((tube("platform", 3.15, 2.5, 0.15, (0, 0, 4.17), steel, segments=20), 2, broken))
    parts.append((cylinder("tank", 2.8, 4.4, (0, 0, 6.45), wood, segments=20), 8, inner))
    for z in (5.0, 6.4, 7.8):
        parts.append((tube("band", 2.87, 2.79, 0.12, (0, 0, z), steel, segments=20), 1, broken))
    parts.append((cylinder("roof", 3.0, 1.5, (0, 0, 9.4), roof, segments=20, r2=0.25), 3, broken))
    parts.append((icosphere("finial", 0.2, (0, 0, 10.25), steel), 1, broken))
    return parts


def small_house_parts():
    wall_b, wall_e = house_wall_texture()
    wall = material("House_Wall", (1, 1, 1), 0.0, 0.85, (1, 1, 1), 1.5, image("House_Wall", wall_b),
                    image("House_Wall_Emit", wall_e))
    tile = material("Roof_Tile", (0.42, 0.13, 0.07), 0.0, 0.8)
    brick = material("Brick", (0.4, 0.18, 0.11), 0.0, 0.85)
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
    roof = hull("roof", [(-4.4, -4.4, 3.95), (4.4, -4.4, 3.95), (-4.4, 4.4, 3.95), (4.4, 4.4, 3.95), (0, -4.4, 6.35),
                         (0, 4.4, 6.35)], tile)
    parts.append((roof, 7, rubble))
    parts.append((box("chimney", (0.7, 0.7, 2.2), (2.2, 1.5, 5.4), brick), 2, rubble))
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
    export(f"{file}.glb")
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
