"""Fracture generation for destructible props.

``fracture()`` uses Blender's Cell Fracture add-on when it is installed and enabled-able,
otherwise (e.g. Blender 4.2+ without the extension, or the standalone bpy module) it runs
an equivalent procedural fracture written with bmesh:

* seed points are scattered inside the part (stratified along its longest axis),
* every seed owns a convex cell of a *power diagram* (Voronoi with random weights, which
  gives irregular, differently sized cells that still tile space without overlaps),
* the part is clipped against each cell's bounding planes with ``bisect_plane`` and the
  open cuts are capped with ``holes_fill`` using an interior material.

Results are deterministic for a given seed.
"""
import os
import random

import bpy
import bmesh
from mathutils import Vector

from common import log, mark_sharp, mesh_object, parent_keep

_CELL_FRACTURE = None


def cell_fracture_available():
    """Try to enable the Cell Fracture add-on / extension once."""
    global _CELL_FRACTURE
    if _CELL_FRACTURE is not None:
        return _CELL_FRACTURE
    _CELL_FRACTURE = False
    if os.environ.get("AF_FRACTURE", "auto") == "procedural":
        return False
    try:
        import addon_utils

        for module in ("object_fracture_cell", "bl_ext.blender_org.cell_fracture"):
            try:
                addon_utils.enable(module, default_set=False)
            except Exception:  # noqa: BLE001 - add-on simply not installed
                pass
        _CELL_FRACTURE = hasattr(bpy.types, "OBJECT_OT_add_fracture_cell_objects")
    except Exception:  # noqa: BLE001
        _CELL_FRACTURE = False
    return _CELL_FRACTURE


def _world_bmesh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    return bm


def _seeds(bm, count, rng):
    lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    size = hi - lo
    axis = max(range(3), key=lambda k: size[k])
    seeds = []
    for i in range(count):
        p = Vector((rng.uniform(lo.x, hi.x), rng.uniform(lo.y, hi.y), rng.uniform(lo.z, hi.z)))
        p[axis] = lo[axis] + (i + rng.uniform(0.2, 0.8)) / count * size[axis]
        seeds.append(p)
    extent = max(size.x * size.y * size.z, 1e-6) ** (1.0 / 3.0)
    spacing = max(extent / max(count, 1) ** (1.0 / 3.0), max(size) / count)
    weights = [rng.uniform(0.0, (0.35 * spacing) ** 2) for _ in seeds]
    return seeds, weights


def procedural_cells(obj, count, seed, interior_index):
    """Return a list of world-space bmeshes, one per non-empty power-diagram cell."""
    rng = random.Random(seed)
    src = _world_bmesh(obj)
    if count <= 1:
        return [src]
    seeds, weights = _seeds(src, count, rng)
    cells = []
    for i in range(count):
        bm = src.copy()
        alive = True
        for j in range(count):
            if i == j:
                continue
            d = seeds[j] - seeds[i]
            dist = d.length
            if dist < 1e-6:
                continue
            normal = d / dist
            t = (dist * dist + weights[i] - weights[j]) / (2.0 * dist)
            co = seeds[i] + normal * t
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=co, plane_no=normal, clear_outer=True)
            if not bm.verts:
                alive = False
                break
            cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
            if cut:
                for f in bmesh.ops.holes_fill(bm, edges=cut, sides=0)["faces"]:
                    f.material_index = interior_index
        if alive and len(bm.faces) >= 4:
            bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            if bm.calc_volume(signed=False) > 1e-5:
                cells.append(bm)
                continue
        bm.free()
    src.free()
    return cells


def cell_fracture_cells(obj, count, seed, interior_index):
    """Run the Cell Fracture operator and convert its output to world-space bmeshes.

    Any objects the operator created are always removed again, so a failed run cannot leak
    stray meshes into the exported file (the caller then falls back to procedural fracture).
    """
    before = set(bpy.data.objects)
    mod = obj.modifiers.new("fracture_points", "PARTICLE_SYSTEM")
    try:
        ps = mod.particle_system
        ps.seed = seed
        ps.settings.count = count
        ps.settings.frame_start = ps.settings.frame_end = 1
        ps.settings.emit_from = "VOLUME"
        ps.settings.distribution = "RAND"
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        obj.select_set(True)
        with bpy.context.temp_override(active_object=obj, object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.add_fracture_cell_objects(
                source={"PARTICLE_OWN"}, source_limit=count, source_noise=0.3, cell_scale=(1.0, 1.0, 1.0),
                recursion=0, use_smooth_faces=False, use_sharp_edges=True, use_sharp_edges_apply=True,
                use_data_match=True, use_island_split=True, margin=0.0, material_index=interior_index,
                use_interior_vgroup=False, use_recenter=True, use_remove_original=False)
        created = sorted((o for o in bpy.data.objects if o not in before and o.type == "MESH"), key=lambda x: x.name)
        cells = [_world_bmesh(o) for o in created]
    finally:
        if mod.name in obj.modifiers:
            obj.modifiers.remove(mod)
        for o in [o for o in bpy.data.objects if o not in before]:
            bpy.data.objects.remove(o, do_unlink=True)
    if len(cells) < 2:
        for bm in cells:
            bm.free()
        raise RuntimeError("cell fracture produced no usable cells")
    return cells


def fracture(obj, count, seed, interior_mat, parent, counter):
    """Fracture ``obj`` into chunk_### children of ``parent``; returns the number of chunks."""
    names = [m.name for m in obj.data.materials]
    if interior_mat.name not in names:
        obj.data.materials.append(interior_mat)
    mats = list(obj.data.materials)
    interior_index = [m.name for m in mats].index(interior_mat.name)
    cells = None
    if count > 1 and cell_fracture_available():
        try:
            cells = cell_fracture_cells(obj, count, seed, interior_index)
        except Exception as exc:  # noqa: BLE001 - fall back to the procedural path
            log(f"cell fracture failed on {obj.name} ({exc}); using procedural fracture")
            cells = None
    if cells is None:
        cells = procedural_cells(obj, count, seed, interior_index)
    for bm in cells:
        centre = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        bmesh.ops.translate(bm, vec=-centre, verts=bm.verts[:])
        name = f"chunk_{counter[0]:03d}"
        counter[0] += 1
        chunk = mesh_object(name, bm, mats)
        chunk.location = centre
        mark_sharp(chunk.data, 30.0)
        parent_keep(chunk, parent)
    return len(cells)
