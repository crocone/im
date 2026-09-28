"""Procedural PBR texture sets and materials for hard-surface assets.

Every hard-surface material gets three tileable maps generated with numpy:
  * albedo  - base colour with per-panel tint variation, grime in grooves, worn bright edges
  * ORM     - R = ambient occlusion, G = roughness, B = metalness (glTF packing)
  * normal  - panel lines, bevelled panel edges, rivets, vent slots, hatches (OpenGL +Y)

Patterns are cached as arrays (so each is computed once per build) and turned into Blender
images per scene. All randomness is seeded, so the output is deterministic.
"""
import math

import bpy
import numpy as np

import common
from textures import fbm, value_noise

_PATTERNS = {}
_MAPS = {}


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _stamp(field, cx, cy, kernel, mode="add"):
    """Add (or max) a small kernel into a tileable field with wrap-around indexing."""
    size = field.shape[0]
    kh, kw = kernel.shape
    ys = (np.arange(kh) + cy - kh // 2) % size
    xs = (np.arange(kw) + cx - kw // 2) % size
    if mode == "max":
        field[np.ix_(ys, xs)] = np.maximum(field[np.ix_(ys, xs)], kernel)
    else:
        field[np.ix_(ys, xs)] += kernel


def _rivet(radius):
    r = int(math.ceil(radius * 2.2))
    y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    d = np.sqrt(x * x + y * y) / radius
    return np.clip(1.0 - d * d, 0.0, 1.0) ** 0.6


def _subdivide(rng, size, min_cell, max_depth):
    rects = []

    def split(x0, y0, x1, y1, depth):
        w, h = x1 - x0, y1 - y0
        can_x, can_y = w >= min_cell * 2, h >= min_cell * 2
        if depth >= max_depth or not (can_x or can_y) or (depth > 1 and rng.random() < 0.22):
            rects.append((x0, y0, x1, y1))
            return
        if can_x and (not can_y or w > h * rng.uniform(0.7, 1.4)):
            s = x0 + int(round(rng.uniform(0.3, 0.7) * w / 8.0)) * 8
            s = min(max(s, x0 + min_cell), x1 - min_cell)
            split(x0, y0, s, y1, depth + 1)
            split(s, y0, x1, y1, depth + 1)
        else:
            s = y0 + int(round(rng.uniform(0.3, 0.7) * h / 8.0)) * 8
            s = min(max(s, y0 + min_cell), y1 - min_cell)
            split(x0, y0, x1, s, depth + 1)
            split(x0, s, x1, y1, depth + 1)

    split(0, 0, size, size, 0)
    return rects


def panel_pattern(seed, size=512, min_cell=40, max_depth=6, groove=1.6, bevel=4.0, rivets=0.45, vents=0.1,
                  hatches=0.14):
    """Tileable sci-fi plating: height, cavity (grooves), edge (raised rims) and panel id maps."""
    key = ("panels", seed, size, min_cell, max_depth, rivets, vents, hatches)
    if key in _PATTERNS:
        return _PATTERNS[key]
    rng = np.random.default_rng(seed)
    H = np.zeros((size, size), np.float32)
    cav = np.zeros((size, size), np.float32)
    edge = np.zeros((size, size), np.float32)
    pid = np.zeros((size, size), np.float32)
    rivet_k = _rivet(1.7)
    for (x0, y0, x1, y1) in _subdivide(rng, size, min_cell, max_depth):
        ys = np.arange(y0, y1, dtype=np.float32)[:, None] + 0.5
        xs = np.arange(x0, x1, dtype=np.float32)[None, :] + 0.5
        d = np.minimum(np.minimum(xs - x0, x1 - xs), np.minimum(ys - y0, y1 - ys))
        lift = rng.uniform(0.55, 1.0)
        H[y0:y1, x0:x1] = lift * _smooth(groove, groove + bevel, d)
        cav[y0:y1, x0:x1] = 1.0 - _smooth(0.0, groove + 3.0, d)
        edge[y0:y1, x0:x1] = _smooth(groove + bevel + 3.0, groove + 0.8, d) * (d > groove)
        pid[y0:y1, x0:x1] = rng.random()
        w, h = x1 - x0, y1 - y0
        r = rng.random()
        if r < vents and w > 56 and h > 44:
            # louvred vent: parallel slots set into an inset frame
            ix0, ix1, iy0, iy1 = x0 + 10, x1 - 10, y0 + 10, y1 - 10
            H[iy0:iy1, ix0:ix1] -= 0.25
            for y in range(iy0 + 3, iy1 - 3):
                if (y - iy0) % 7 < 3:
                    H[y, ix0 + 3:ix1 - 3] -= 0.55
                    cav[y, ix0 + 3:ix1 - 3] = np.maximum(cav[y, ix0 + 3:ix1 - 3], 0.8)
        elif r < vents + hatches and w > 44 and h > 44:
            # inset service hatch
            inset = rng.uniform(7, 12)
            ring = (d > inset) & (d < inset + 1.6)
            H[y0:y1, x0:x1] -= ring * 0.7
            cav[y0:y1, x0:x1] = np.maximum(cav[y0:y1, x0:x1], ring * 0.85)
        if rng.random() < rivets:
            step = int(rng.uniform(12, 20))
            inset = int(groove + bevel + 3)
            for x in range(x0 + inset, x1 - inset + 1, step):
                for y in (y0 + inset, y1 - inset - 1):
                    _stamp(H, x, y, rivet_k * 0.45)
            for y in range(y0 + inset + step, y1 - inset - step + 1, step):
                for x in (x0 + inset, x1 - inset - 1):
                    _stamp(H, x, y, rivet_k * 0.45)
    out = {"height": H, "cavity": np.clip(cav, 0, 1), "edge": np.clip(edge, 0, 1), "pid": pid}
    _PATTERNS[key] = out
    return out


def rib_pattern(seed, size=256, period=10):
    """Flexible ribbed sleeve for joints / undersuit (ribs run along U)."""
    key = ("ribs", seed, size, period)
    if key in _PATTERNS:
        return _PATTERNS[key]
    rng = np.random.default_rng(seed)
    y = np.arange(size, dtype=np.float32)[:, None]
    phase = (y % period) / period
    rib = 0.5 + 0.5 * np.cos(phase * 2 * math.pi)
    H = np.repeat(rib, size, axis=1) * 0.8
    H += (value_noise(rng, size, size, 16, 16) - 0.5) * 0.25
    cav = np.repeat((1.0 - rib) ** 3, size, axis=1)
    out = {"height": H.astype(np.float32), "cavity": cav.astype(np.float32),
           "edge": np.zeros_like(H), "pid": value_noise(rng, size, size, 4, 4).astype(np.float32)}
    _PATTERNS[key] = out
    return out


def brushed_pattern(seed, size=256):
    """Large machined panels with fine directional brushing."""
    base = panel_pattern(seed, size, min_cell=64, max_depth=3, rivets=0.25, vents=0.0, hatches=0.1)
    key = ("brushed", seed, size)
    if key in _PATTERNS:
        return _PATTERNS[key]
    rng = np.random.default_rng(seed + 7)
    streak = value_noise(rng, size, size, 128, 4).astype(np.float32)
    out = dict(base)
    out["streak"] = streak
    _PATTERNS[key] = out
    return out


def normal_map(height, strength):
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    n = np.dstack([-dx * strength, -dy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float32)


def _to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)


def stripe_mask(size, period, duty=0.5):
    """Diagonal hazard bands (tileable when ``period`` divides the texture size), softly anti-aliased."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    t = ((x + y) % period) / period
    return _smooth(duty - 0.02, duty + 0.02, t) * (1.0 - _smooth(0.98, 1.0, t))


def material_maps(pat, color, metallic, roughness, seed, wear=0.35, grime=0.4, variation=0.07, painted=False,
                  stripes=None):
    """Albedo (sRGB) and ORM arrays for one material on a pattern.

    ``stripes`` = (second colour, period px) paints diagonal hazard bands over the plating.
    """
    size = pat["height"].shape[0]
    rng = np.random.default_rng(seed)
    low = fbm(rng, size, size, 3, 4).astype(np.float32)
    mid = fbm(rng, size, size, 12, 3).astype(np.float32)
    speck = rng.random((size, size)).astype(np.float32)
    cav, edge, pid = pat["cavity"], pat["edge"], pat["pid"]
    # edge wear only where a noise mask allows it (chipped, not uniform)
    wear_mask = _smooth(0.45, 0.75, mid) * edge * wear
    base = np.array(color, np.float32)[None, None, :]
    if stripes is not None:
        band = stripe_mask(size, stripes[1])[..., None]
        base = base * (1.0 - band) + np.array(stripes[0], np.float32)[None, None, :] * band
    tint = 1.0 + (pid[..., None] - 0.5) * 2 * variation + (low[..., None] - 0.5) * 0.12
    albedo = base * tint * (1.0 - grime * cav[..., None] * 0.65)
    worn = np.array([min(1.0, c * 0.5 + 0.3) if painted else min(1.0, c * 1.6 + 0.12) for c in color],
                    np.float32)[None, None, :]
    albedo = albedo * (1 - wear_mask[..., None]) + worn * wear_mask[..., None]
    albedo *= 1.0 - 0.05 * (speck[..., None] > 0.985)
    rough = roughness + (mid - 0.5) * 0.14 + cav * grime * 0.22 - wear_mask * 0.12
    if "streak" in pat:
        rough += (pat["streak"] - 0.5) * 0.12
    rough = np.clip(rough + (speck > 0.992) * 0.15, 0.04, 1.0)
    metal = np.full((size, size), metallic, np.float32)
    if painted:
        metal = np.clip(metal + wear_mask * (0.9 - metallic) * 1.6, 0, 1)
    ao = 1.0 - cav * 0.6
    orm = np.dstack([ao, rough, metal]).astype(np.float32)
    return _to_srgb(albedo).astype(np.float32), orm


# --------------------------------------------------------------------------- blender side


def _image(name, arr, non_color):
    img = bpy.data.images.get(name)
    if img is None:
        img = common.image_from_array(name, arr, non_color)
    return img


def gltf_output_group():
    """Node group the glTF exporter reads ambient occlusion from."""
    name = "glTF Material Output"
    g = bpy.data.node_groups.get(name)
    if g is None:
        g = bpy.data.node_groups.new(name, "ShaderNodeTree")
        if hasattr(g, "interface"):
            g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        else:
            g.inputs.new("NodeSocketFloat", "Occlusion")
    return g


def pattern(kind, seed, size):
    if kind == "panels":
        return panel_pattern(seed, size)
    if kind == "panels_fine":
        return panel_pattern(seed, size, min_cell=28, max_depth=7, rivets=0.35, vents=0.12, hatches=0.12)
    if kind == "panels_large":
        return panel_pattern(seed, size, min_cell=72, max_depth=4, rivets=0.5, vents=0.08, hatches=0.2)
    if kind == "ribs":
        return rib_pattern(seed, size)
    if kind == "brushed":
        return brushed_pattern(seed, size)
    raise ValueError(kind)


def pbr_material(name, color, metallic, roughness, kind="panels", seed=1, size=512, normal_strength=1.0,
                 bump=2.2, wear=0.35, grime=0.4, variation=0.07, painted=False, emission=None, strength=0.0,
                 coat=0.0, stripes=None):
    """Principled material driven by generated albedo / ORM / normal maps (cached per scene)."""
    if name in common._MATERIALS:
        return common._MATERIALS[name]
    pat = pattern(kind, seed, size)
    mkey = (name, kind, seed, size)
    if mkey not in _MAPS:
        _MAPS[mkey] = material_maps(pat, color, metallic, roughness, seed * 31 + len(name), wear, grime, variation,
                                    painted, stripes)
    albedo, orm = _MAPS[mkey]
    nkey = ("N", kind, seed, size, bump)
    if nkey not in _MAPS:
        _MAPS[nkey] = normal_map(pat["height"], bump)
    mat = common.material(name, color, metallic, roughness, emission, strength)
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t_albedo = nt.nodes.new("ShaderNodeTexImage")
    t_albedo.image = _image(f"{name}_albedo", albedo, False)
    nt.links.new(t_albedo.outputs["Color"], common._socket(bsdf, "Base Color"))
    t_orm = nt.nodes.new("ShaderNodeTexImage")
    t_orm.image = _image(f"{name}_orm", orm, True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_orm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], common._socket(bsdf, "Roughness"))
    nt.links.new(sep.outputs[2], common._socket(bsdf, "Metallic"))
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = gltf_output_group()
    nt.links.new(sep.outputs[0], grp.inputs["Occlusion"])
    t_n = nt.nodes.new("ShaderNodeTexImage")
    t_n.image = _image(f"N_{kind}_{seed}_{size}", _MAPS[nkey], True)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = normal_strength
    nt.links.new(t_n.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], common._socket(bsdf, "Normal"))
    if coat > 0:
        c = common._socket(bsdf, "Coat Weight", "Clearcoat")
        if c is not None:
            c.default_value = coat
        cr = common._socket(bsdf, "Coat Roughness", "Clearcoat Roughness")
        if cr is not None:
            cr.default_value = 0.06
    return mat
