"""Shared helpers for the Armored Flight Blender asset pipeline.

Every asset is authored procedurally with bpy/bmesh so the whole art set can be
regenerated deterministically (seeded RNGs, no timestamps, no manual edits).

Authoring conventions (Blender space):
  * +Z is up, -Y is the forward direction of every vehicle / character.
  * The glTF exporter converts to +Y up / +Z forward, which is what the game uses.
  * Geometry is baked in world space; objects start with an identity transform and
    get their pivot assigned afterwards with ``set_origin``.
"""
import math
import os
import warnings

import bpy  # must be imported first: it provides bmesh/mathutils when running as a Python module
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT_DIR = os.path.join(ROOT, "public", "assets")

_MATERIALS = {}

# World-space box-projection UVs are applied to every part built while a scale is set
# (metres per texture tile). Assets set it once before modelling: see ``set_uv_scale``.
UV = {"scale": None}


def set_uv_scale(scale):
    UV["scale"] = scale


def log(msg):
    print(f"[assets] {msg}", flush=True)


# --------------------------------------------------------------------------- scene


def reset_scene():
    """Delete every datablock so each asset build starts from an identical empty scene."""
    for coll in (
        bpy.data.objects,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.actions,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.curves,
    ):
        for block in list(coll):
            coll.remove(block)
    _MATERIALS.clear()
    UV["scale"] = None


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def trs(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Matrix from location, XYZ euler rotation in degrees and scale."""
    return Matrix.LocRotScale(
        Vector(loc), Euler([math.radians(a) for a in rot], "XYZ"), Vector(scale)
    )


# --------------------------------------------------------------------------- materials


def _socket(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def image_from_array(name, arr, non_color=False):
    """Create a Blender image from an (H, W, 3|4) float array (row 0 = bottom).

    Colour images hold sRGB-encoded values; ``non_color`` images (normal / ORM maps) hold raw data.
    """
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), dtype=np.float32)], axis=2)
    arr = np.clip(arr, 0.0, 1.0).astype(np.float32)
    img = bpy.data.images.new(name, w, h, alpha=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(arr.ravel())
    img.pack()
    return img


def material(
    name,
    color=(0.5, 0.5, 0.5),
    metallic=0.0,
    roughness=0.5,
    emission=None,
    strength=0.0,
    base_tex=None,
    emit_tex=None,
):
    """Cached Principled material. Emission strength > 1 exports via KHR_materials_emissive_strength."""
    if name in _MATERIALS:
        return _MATERIALS[name]
    mat = bpy.data.materials.new(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    _socket(bsdf, "Base Color").default_value = (*color, 1.0)
    _socket(bsdf, "Metallic").default_value = metallic
    _socket(bsdf, "Roughness").default_value = roughness
    if base_tex is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = base_tex
        nt.links.new(tex.outputs["Color"], _socket(bsdf, "Base Color"))
    if emission is not None:
        ec = _socket(bsdf, "Emission Color", "Emission")
        ec.default_value = (*emission, 1.0)
        _socket(bsdf, "Emission Strength").default_value = strength
        if emit_tex is not None:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = emit_tex
            nt.links.new(tex.outputs["Color"], ec)
    _MATERIALS[name] = mat
    return mat


def palette():
    """Project-wide material palette shared by the player, enemies and projectiles."""
    return {
        # powered armor
        "armor": material("Armor_Gunmetal", (0.075, 0.08, 0.092), 0.85, 0.3),
        "accent": material("Armor_Copper", (0.6, 0.17, 0.045), 0.9, 0.28),
        "trim": material("Armor_Steel", (0.48, 0.5, 0.53), 0.95, 0.22),
        "joint": material("Joint_Dark", (0.018, 0.018, 0.022), 0.55, 0.55),
        "glow": material("Emissive_Cyan", (0.55, 0.92, 1.0), 0.0, 0.3, (0.42, 0.85, 1.0), 4.0),
        # hostile machines
        "e_hull": material("Enemy_Hull", (0.045, 0.048, 0.055), 0.75, 0.42),
        "e_plate": material("Enemy_Plate", (0.2, 0.205, 0.215), 0.85, 0.34),
        "e_accent": material("Enemy_Crimson", (0.36, 0.025, 0.02), 0.7, 0.35),
        "e_hazard": material("Enemy_Hazard", (0.75, 0.38, 0.015), 0.4, 0.45),
        "e_glow": material("Emissive_Red", (1.0, 0.2, 0.1), 0.0, 0.3, (1.0, 0.09, 0.03), 12.0),
        # boss
        "b_plate": material("Boss_Plate", (0.11, 0.1, 0.095), 0.9, 0.33),
        "b_accent": material("Boss_Crimson", (0.3, 0.03, 0.022), 0.85, 0.3),
        "b_glow": material("Emissive_Core", (1.0, 0.35, 0.1), 0.0, 0.3, (1.0, 0.2, 0.04), 14.0),
        # munitions
        "m_body": material("Munition_White", (0.62, 0.63, 0.64), 0.35, 0.4),
        "m_band": material("Munition_Orange", (0.8, 0.25, 0.02), 0.3, 0.45),
        "m_exhaust": material("Emissive_Exhaust", (1.0, 0.7, 0.4), 0.0, 0.3, (1.0, 0.55, 0.2), 10.0),
    }


# --------------------------------------------------------------------------- mesh helpers


def mesh_object(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return _link(bpy.data.objects.new(name, me))


def mark_sharp(me, angle_deg=35.0):
    """Smooth shading with hard edges above ``angle_deg`` (works on Blender 3.x - 5.x)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    limit = math.radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < limit
        else:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    if hasattr(me, "use_auto_smooth"):
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.pi


def finish(obj, bevel=0.0, segments=1, sharp=35.0):
    """Bevel + weighted normals for hard-surface parts, angle based smoothing otherwise."""
    me = obj.data
    if UV["scale"]:
        box_uv(obj, UV["scale"])
    if bevel > 0.0:
        for p in me.polygons:
            p.use_smooth = True
        if hasattr(me, "use_auto_smooth"):
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.pi
        bev = obj.modifiers.new("Bevel", "BEVEL")
        bev.width = bevel
        bev.segments = segments
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(30.0)
        bev.use_clamp_overlap = True
        wn = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 100
        wn.mode = "FACE_AREA"
    else:
        mark_sharp(me, sharp)
    return obj


def box(name, size, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), bevel=0.0, segments=1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=trs(loc, rot, size))
    return finish(mesh_object(name, bm, [mat]), bevel, segments)


def cylinder(name, r, depth, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), segments=16, r2=None,
             bevel=0.0, caps=True):
    """Cylinder / cone along local Z (rotated by ``rot``)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=caps,
        cap_tris=False,
        segments=segments,
        radius1=r,
        radius2=r if r2 is None else r2,
        depth=depth,
        matrix=trs(loc, rot),
    )
    return finish(mesh_object(name, bm, [mat]), bevel)


def icosphere(name, r, loc=(0, 0, 0), mat=None, subdiv=1, scale=(1, 1, 1), smooth=False):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r, matrix=trs(loc, (0, 0, 0), scale))
    obj = mesh_object(name, bm, [mat])
    return finish(obj, 0.0, 1, 180.0 if smooth else 1.0)


def hull(name, points, mat=None, bevel=0.0, segments=1):
    """Convex hull of a point cloud: the workhorse for angular armour plates."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    loose = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    stray = [v for v in bm.verts if not v.link_faces]
    if stray:
        bmesh.ops.delete(bm, geom=stray, context="VERTS")
    bmesh.ops.dissolve_limit(
        bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:]
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return finish(mesh_object(name, bm, [mat]), bevel, segments)


def rect_pts(axis, a, c1, c2, w, d, chamfer=0.0):
    """Rectangle (optionally chamfered to an octagon) perpendicular to ``axis`` at coordinate ``a``."""
    hw, hd = w / 2.0, d / 2.0
    if chamfer > 0.0:
        c = min(chamfer, hw * 0.9, hd * 0.9)
        ring = [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
                (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]
    else:
        ring = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    out = []
    for u, v in ring:
        if axis == "Z":
            out.append((c1 + u, c2 + v, a))
        elif axis == "Y":
            out.append((c1 + u, a, c2 + v))
        else:
            out.append((a, c1 + u, c2 + v))
    return out


def loft(name, sections, mat=None, bevel=0.0, axis="Z", segments=1):
    """Hull through rectangular sections.

    axis 'Z': section = (z, cx, cy, width_x, depth_y, chamfer)
    axis 'Y': section = (y, cx, cz, width_x, height_z, chamfer)
    axis 'X': section = (x, cy, cz, depth_y, height_z, chamfer)
    """
    pts = []
    for s in sections:
        pts += rect_pts(axis, *s)
    return hull(name, pts, mat, bevel, segments)


def superellipse(c1, c2, a, b, p, n):
    """Points of a superellipse |x/a|^p + |y/b|^p = 1 (p = 2 ellipse, larger = boxier)."""
    out = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        out.append((c1 + a * math.copysign(abs(c) ** (2.0 / p), c), c2 + b * math.copysign(abs(s) ** (2.0 / p), s)))
    return out


def rloft(name, sections, mat=None, bevel=0.0, axis="Z", n=20, segments=1):
    """Hull through rounded (superellipse) sections: smooth armour shells.

    axis 'Z': section = (z, cx, cy, width_x, depth_y, p); axis 'Y': (y, cx, cz, width_x, height_z, p);
    axis 'X': (x, cy, cz, depth_y, height_z, p).
    """
    pts = []
    for a, c1, c2, w, d, p in sections:
        for u, v in superellipse(c1, c2, w / 2.0, d / 2.0, p, n):
            if axis == "Z":
                pts.append((u, v, a))
            elif axis == "Y":
                pts.append((u, a, v))
            else:
                pts.append((a, u, v))
    return hull(name, pts, mat, bevel, segments)


def ray_hit(obj, origin, direction):
    """World-space (location, normal) where a ray first hits ``obj``, or None."""
    bpy.context.view_layer.update()
    inv = obj.matrix_world.inverted()
    ok, loc, normal, _ = obj.ray_cast(inv @ Vector(origin), (inv.to_3x3() @ Vector(direction)).normalized())
    if not ok:
        return None
    n = (obj.matrix_world.to_3x3().inverted().transposed() @ normal).normalized()
    return obj.matrix_world @ loc, n


def ray_hit_any(objs, origin, direction):
    """Nearest hit over several objects."""
    best = None
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        hit = ray_hit(o, origin, direction)
        if hit and (best is None or (hit[0] - Vector(origin)).length < (best[0] - Vector(origin)).length):
            best = hit
    return best


def on_surface(obj, points, direction=(0, 1, 0), lift=0.0, depth=0.01):
    """Project (x, z) or (x, y, z) guide points onto ``obj`` along ``direction``.

    Returns front points lifted off the surface plus matching back points pushed ``depth`` inside,
    ready to hull into a conforming plate / lens / trim strip.
    """
    d = Vector(direction).normalized()
    front, back = [], []
    for p in points:
        o = Vector((p[0], -3.0, p[1])) if len(p) == 2 else Vector(p) - d * 3.0
        hit = ray_hit_any(obj, o, d)
        if hit is None:
            continue
        loc, n = hit
        front.append(tuple(loc + n * lift))
        back.append(tuple(loc - n * depth))
    return front + back


def tube(name, r_out, r_in, depth, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), segments=20):
    """Hollow ring (ducts, nozzles, bezels) along local Z."""
    bm = bmesh.new()
    m = trs(loc, rot)
    rings = []
    for z in (-depth / 2.0, depth / 2.0):
        for r in (r_out, r_in):
            ring = []
            for i in range(segments):
                a = 2.0 * math.pi * i / segments
                ring.append(bm.verts.new(m @ Vector((math.cos(a) * r, math.sin(a) * r, z))))
            rings.append(ring)
    bo, bi, to, ti = rings
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((bo[i], bo[j], to[j], to[i]))  # outer wall
        bm.faces.new((bi[j], bi[i], ti[i], ti[j]))  # inner wall
        bm.faces.new((to[i], to[j], ti[j], ti[i]))  # top lip
        bm.faces.new((bo[j], bo[i], bi[i], bi[j]))  # bottom lip
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return finish(mesh_object(name, bm, [mat]), 0.0, 1, 40.0)


def prism(name, pts2d, z0, z1, mats, uv_scale=None, side_idx=0, cap_idx=1, sharp=35.0):
    """Extrude a CCW 2D polygon from z0 to z1.

    Side faces use material ``side_idx``, caps ``cap_idx``. When ``uv_scale`` = (su, sv) is
    given, sides get perimeter-continuous UVs (u = arc length / su, v = z / sv) and caps get
    planar XY UVs, so facade textures wrap around corners and line up between stacked masses.
    """
    bm = bmesh.new()
    n = len(pts2d)
    bot = [bm.verts.new((x, y, z0)) for x, y in pts2d]
    top = [bm.verts.new((x, y, z1)) for x, y in pts2d]
    sides = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        f.material_index = side_idx
        sides.append((f, i))
    ftop = bm.faces.new(top)
    fbot = bm.faces.new(list(reversed(bot)))
    ftop.material_index = cap_idx
    fbot.material_index = cap_idx
    bm.verts.index_update()
    if uv_scale is not None:
        su, sv = uv_scale
        uv = bm.loops.layers.uv.verify()
        arc = [0.0]
        for i in range(n):
            j = (i + 1) % n
            arc.append(arc[-1] + math.dist(pts2d[i], pts2d[j]))
        for f, i in sides:
            for loop in f.loops:
                vi = loop.vert.index % n
                a = arc[i] if vi == i else arc[i + 1]
                loop[uv].uv = (a / su, loop.vert.co.z / sv)
        for f in (ftop, fbot):
            for loop in f.loops:
                loop[uv].uv = (loop.vert.co.x / su, loop.vert.co.y / su)
    obj = mesh_object(name, bm, mats)
    mark_sharp(obj.data, sharp)
    return obj


def _name_offset(name):
    """Stable per-part UV offset so neighbouring parts don't show identical panel layouts."""
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) % 100003
    return ((h % 97) / 97.0, ((h // 97) % 89) / 89.0)


def box_uv(obj, su, sv=None, offset=None):
    """World-space box projection: each face is mapped from the axis its normal is closest to."""
    sv = sv or su
    ou, ov = offset if offset is not None else _name_offset(obj.name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for loop in f.loops:
            co = loop.vert.co
            if ax == 2:
                loop[uv].uv = (co.x / su + ou, co.y / su + ov)
            elif ax == 0:
                loop[uv].uv = (co.y / su + ou, co.z / sv + ov)
            else:
                loop[uv].uv = (co.x / su + ou, co.z / sv + ov)
    bm.to_mesh(obj.data)
    bm.free()


def lathe(name, profile, segments=24, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), sharp=40.0, uv_scale=None, closed=False):
    """Surface of revolution around local Z from a (radius, z) profile (radius 0 = pole).

    UVs wrap around (u = arc length around the axis) and run along the profile (v = arc length).
    ``closed`` joins the last profile point back to the first (rings, ducts, rims).
    """
    su = uv_scale or UV["scale"] or 1.0
    m = trs(loc, rot)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    if closed:
        profile = list(profile) + [profile[0]]
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new(m @ Vector((0.0, 0.0, z)))])
        else:
            rings.append([bm.verts.new(m @ Vector((math.cos(2 * math.pi * i / segments) * r,
                                                   math.sin(2 * math.pi * i / segments) * r, z)))
                          for i in range(segments)])
    arc = [0.0]
    for k in range(1, len(profile)):
        arc.append(arc[-1] + math.dist(profile[k - 1], profile[k]))
    rmax = max(r for r, _ in profile) or 1.0
    circ = 2 * math.pi * rmax
    ou, ov = _name_offset(name)

    def uvs(k, i):
        return (i / segments * circ / su + ou, arc[k] / su + ov)

    if closed:
        rings[-1] = rings[0]
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(segments):
            j = i + 1
            if len(A) == 1 and len(B) == 1:
                break
            if len(A) == 1:
                verts, keys = (A[0], B[j % segments], B[i]), ((k, i + 0.5), (k + 1, j), (k + 1, i))
            elif len(B) == 1:
                verts, keys = (A[i], A[j % segments], B[0]), ((k, i), (k, j), (k + 1, i + 0.5))
            else:
                verts, keys = (A[i], A[j % segments], B[j % segments], B[i]), ((k, i), (k, j), (k + 1, j), (k + 1, i))
            try:
                f = bm.faces.new(verts)
            except ValueError:
                continue
            for loop, key in zip(f.loops, keys):
                loop[uv].uv = uvs(*key)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = mesh_object(name, bm, [mat])
    mark_sharp(obj.data, sharp)
    return obj


def skin(name, rings, mat=None, caps=True, closed=True, sharp=35.0):
    """Mesh through a list of vertex rings (equal counts): blades, fins, bent ducts, twisted parts.

    ``closed`` = each ring is a closed loop; ``caps`` fills the first and last ring.
    """
    bm = bmesh.new()
    vr = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(rings[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if caps and closed:
        bm.faces.new(list(reversed(vr[0])))
        bm.faces.new(vr[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = mesh_object(name, bm, [mat])
    if UV["scale"]:
        box_uv(obj, UV["scale"])
    mark_sharp(obj.data, sharp)
    return obj


def sweep(name, path, radius, mat=None, segments=8, caps=True):
    """Tube swept along a polyline (pipes, cables, hydraulic lines) with parallel-transport frames."""
    pts = [Vector(p) for p in path]
    bm = bmesh.new()
    rings = []
    normal = None
    for k, p in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        if normal is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            normal = t.cross(ref).normalized()
        else:
            normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal)
        r = radius(k / (len(pts) - 1)) if callable(radius) else radius
        rings.append([bm.verts.new(p + (normal * math.cos(2 * math.pi * i / segments) +
                                        binormal * math.sin(2 * math.pi * i / segments)) * r)
                      for i in range(segments)])
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = mesh_object(name, bm, [mat])
    return finish(obj, 0.0, 1, 50.0)


def regular_polygon(r, sides, phase=0.0, cx=0.0, cy=0.0):
    return [
        (cx + r * math.cos(phase + 2 * math.pi * i / sides), cy + r * math.sin(phase + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


def chamfered_rect(w, d, c, cx=0.0, cy=0.0):
    hw, hd = w / 2.0, d / 2.0
    pts = [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c), (hw - c, hd), (-hw + c, hd),
           (-hw, hd - c), (-hw, -hd + c)]
    return [(cx + x, cy + y) for x, y in pts]


def rect(w, d, cx=0.0, cy=0.0):
    hw, hd = w / 2.0, d / 2.0
    return [(cx - hw, cy - hd), (cx + hw, cy - hd), (cx + hw, cy + hd), (cx - hw, cy + hd)]


def split(obj, co, no, gap=0.008, names=None):
    """Cut a closed mesh with a plane into two capped pieces separated by ``gap``.

    Returns (piece on the +normal side, piece on the -normal side); a side may be None.
    Pieces inherit the source materials; the source object is removed.
    """
    co, no = Vector(co), Vector(no).normalized()
    names = names or (obj.name + "_a", obj.name + "_b")
    mats = list(obj.data.materials)
    out = []
    for sign, name in ((1, names[0]), (-1, names[1])):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        plane_no = no * sign
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                                     plane_co=co + plane_no * (gap / 2.0), plane_no=plane_no, clear_inner=True)
        cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
        if cut:
            bmesh.ops.holes_fill(bm, edges=cut, sides=0)
        if len(bm.faces) < 4:
            bm.free()
            out.append(None)
            continue
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        piece = mesh_object(name, bm, mats)
        out.append(piece)
    bpy.data.objects.remove(obj, do_unlink=True)
    return tuple(out)


def cut(obj, planes, gap=0.008):
    """Recursively split ``obj`` by a list of (co, no) planes; returns every resulting piece."""
    pieces = [obj]
    for co, no in planes:
        nxt = []
        for p in pieces:
            nxt += [q for q in split(p, co, no, gap) if q is not None]
        pieces = nxt
    return pieces


def inflate(obj, amount):
    """Push every vertex out along its normal (layered plates, clearance for detail parts)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * amount
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def set_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def centroid(obj):
    vs = obj.data.vertices
    return sum((obj.matrix_world @ v.co for v in vs), Vector()) / max(1, len(vs))


# --------------------------------------------------------------------------- hierarchy


def join(objs, name):
    """Apply modifiers and merge objects (keeps custom normals and material slots)."""
    objs = [o for o in objs if o is not None]
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    active = objs[0]
    with bpy.context.temp_override(
        active_object=active, object=active, selected_objects=objs, selected_editable_objects=objs
    ):
        bpy.ops.object.convert(target="MESH")
        if len(objs) > 1:
            bpy.ops.object.join()
    active.select_set(False)
    active.name = name
    active.data.name = name
    return active


def apply_modifiers(obj):
    return join([obj], obj.name)


def set_origin(obj, pivot):
    """Move the object's origin to ``pivot`` without moving its geometry (identity transform assumed)."""
    pivot = Vector(pivot)
    obj.data.transform(Matrix.Translation(-pivot))
    obj.location = pivot
    return obj


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)
    child.matrix_world = mw
    return child


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), parent=None, display="PLAIN_AXES"):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.location = loc
    obj.rotation_euler = Euler([math.radians(a) for a in rot], "XYZ")
    obj.scale = scale
    _link(obj)
    if parent is not None:
        parent_keep(obj, parent)
    return obj


def collider(name, center, half, parent, rot_z=0.0):
    """Cuboid collider marker: an empty whose scale is the box half-extents."""
    return empty(name, center, (0, 0, rot_z), half, parent, "CUBE")


def part(objs, name, pivot, parent=None):
    """Join ``objs`` into a named part, place its pivot and attach it to ``parent``."""
    obj = join(objs, name) if isinstance(objs, (list, tuple)) else objs
    obj.name = name
    set_origin(obj, pivot)
    if parent is not None:
        parent_keep(obj, parent)
    return obj


def keyframe_poses(nodes, poses):
    """Author static poses as per-node actions named ``<pose>__<node>``.

    The runtime merges every action sharing a pose prefix into one AnimationClip.
    """
    for pose_name, pose in poses.items():
        for node_name, obj in nodes.items():
            rot = pose.get(node_name, (0.0, 0.0, 0.0))
            obj.rotation_euler = Euler([math.radians(a) for a in rot], "XYZ")
            obj.keyframe_insert("rotation_euler", frame=1)
            obj.keyframe_insert("rotation_euler", frame=2)
            ad = obj.animation_data
            act = ad.action
            act.name = f"{pose_name}__{node_name}"
            track = ad.nla_tracks.new()
            track.name = pose_name
            track.strips.new(act.name, 1, act)
            ad.action = None
    for obj in nodes.values():
        for track in obj.animation_data.nla_tracks:
            track.mute = True  # keep the exported rest pose at identity rotations
        obj.rotation_euler = (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- export


def export(filename, animations=False, only=None):
    """Export the scene (or only the hierarchies rooted at ``only``) to public/assets/<filename>."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    bpy.context.view_layer.update()
    args = dict(
        filepath=path,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_cameras=False,
        export_lights=False,
        export_animations=animations,
    )
    if animations:
        args["export_animation_mode"] = "ACTIONS"
    if only:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for root in only:
            for o in [root] + list(root.children_recursive):
                o.select_set(True)
        args["use_selection"] = True
    # Generated textures are photographic noise: JPEG keeps the GLBs small.
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    args["export_image_format"] = "JPEG"
    for quality_prop in ("export_image_quality", "export_jpeg_quality"):
        if quality_prop in props:
            args[quality_prop] = 88
    bpy.ops.export_scene.gltf(**args)
    if not os.path.exists(path) or os.path.getsize(path) < 64:
        raise RuntimeError(f"export failed: {filename}")
    log(f"exported {filename} ({os.path.getsize(path) / 1024:.0f} KB)")
    return path
