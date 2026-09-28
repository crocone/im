"""City kit: nine building modules, street modules, street furniture, rooftop kit, skyline.

Building files contain:
  Render            one multi-material mesh (instanced at runtime)
  COL_BOX_n         empty; location = box centre, scale = half extents (Rapier cuboid)
  COL_CYL_n         empty; scale = (radius, radius, half height) (Rapier cylinder)
  Anchor_<Kind>_n   rooftop placement points: Roof (turrets / water towers / HVAC),
                    Small (HVAC / vents), Top (antennas), Pad (player spawn)
Footprints fit a 40 m x 40 m lot (<= 36 m), four lots per 80 m city block.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (  # noqa: E402
    box, box_uv, chamfered_rect, collider, cylinder, empty, export, hull, icosphere, join, lathe, log, loft,
    material, parent_keep, prism, rect, regular_polygon, reset_scene, rloft, sweep, tube,
)
import facades  # noqa: E402
import pbr  # noqa: E402
from textures import (  # noqa: E402
    FACADE_SPAN, ad_texture, helipad_texture, image, junction_set, paving_set, road_set, skyline_texture,
)


# --------------------------------------------------------------------------- materials


# Shared, heavily textured materials live in one library GLB (city_materials.glb). Building files
# carry untextured placeholders with the same names; the runtime swaps in the library versions,
# so every facade / roof / concrete texture is downloaded and uploaded to the GPU exactly once.
FACADE_NAMES = {"office": "office", "glass": "glass", "band": "band", "brick": "brick", "industrial": "metal",
                "residential": "residential"}
LIBRARY = {  # key: (material name, placeholder colour, metallic, roughness)
    "office": ("Facade_Office", (0.4, 0.39, 0.37), 0.2, 0.6),
    "glass": ("Facade_Glass", (0.2, 0.25, 0.3), 0.7, 0.2),
    "band": ("Facade_Band", (0.45, 0.44, 0.42), 0.2, 0.6),
    "brick": ("Facade_Brick", (0.3, 0.15, 0.1), 0.0, 0.85),
    "industrial": ("Facade_Industrial", (0.28, 0.3, 0.32), 0.6, 0.5),
    "residential": ("Facade_Residential", (0.55, 0.5, 0.42), 0.0, 0.8),
    "roof": ("Roof_Tar", (0.15, 0.15, 0.155), 0.0, 0.9),
    "concrete": ("Concrete", (0.44, 0.43, 0.4), 0.0, 0.85),
    "metal": ("Metal_Panel", (0.34, 0.36, 0.39), 0.85, 0.4),
    "storefront": ("Storefront", (0.3, 0.3, 0.3), 0.3, 0.4),
}
UV_TILE = {"concrete": 4.0, "metal": 6.0}


def _library(key):
    """Fully textured library material (albedo / ORM / normal, emission for lit windows)."""
    name, color, metal, rough = LIBRARY[key]
    if key in FACADE_NAMES:
        maps = facades.facade_maps(FACADE_NAMES[key])
        emit = pbr.image(f"{name}_emit", maps["emit"])
        mat = material(name, (1, 1, 1), metal, rough, (1, 1, 1), 1.4, pbr.image(f"{name}_albedo", maps["albedo"]), emit)
    elif key == "storefront":
        maps = facades.storefront_set()
        emit = pbr.image(f"{name}_emit", maps["emit"])
        mat = material(name, (1, 1, 1), metal, rough, (1, 1, 1), 1.3, pbr.image(f"{name}_albedo", maps["albedo"]), emit)
    else:
        maps = {"roof": facades.roof_set, "concrete": facades.concrete_set, "metal": facades.metal_panel_set}[key]()
        mat = material(name, (1, 1, 1), metal, rough, base_tex=pbr.image(f"{name}_albedo", maps["albedo"]))
    pbr.attach_maps(mat, None, pbr.image(f"{name}_orm", maps["orm"], True), pbr.image(f"{name}_normal", maps["normal"], True))
    return mat


def _surface(name, maps):
    """Street surface material from a generated map set (albedo is already in sRGB)."""
    mat = material(name, (1, 1, 1), 0.0, 0.88, base_tex=pbr.image(f"{name}_albedo", maps["albedo"]))
    pbr.attach_maps(mat, None, pbr.image(f"{name}_orm", maps["orm"], True), pbr.image(f"{name}_normal", maps["normal"], True))
    return mat


def _placeholder(key):
    name, color, metal, rough = LIBRARY[key]
    return material(name, color, metal, rough)


def _skyline():
    b, e = skyline_texture()
    return material("Skyline", (1, 1, 1), 0.2, 0.7, (1, 1, 1), 2.2, image("Skyline", b), image("Skyline_Emit", e))


def _sign():
    img = image("Billboard", ad_texture)
    return material("Billboard", (1, 1, 1), 0.0, 0.5, (1, 1, 1), 1.6, img, img)


MAT_DEFS = {
    "concrete_dark": lambda: material("Concrete_Dark", (0.17, 0.17, 0.17), 0.0, 0.9),
    "metal_dark": lambda: material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5),
    "metal_roof": lambda: material("Metal_Roof", (0.34, 0.36, 0.39), 0.65, 0.45),
    "glass_dark": lambda: material("Glass_Dark", (0.02, 0.03, 0.04), 0.9, 0.12),
    "foliage": lambda: material("Foliage_Hedge", (0.055, 0.15, 0.04), 0.0, 0.9),
    "beacon": lambda: material("Beacon_Red", (1.0, 0.1, 0.05), 0.0, 0.4, (1.0, 0.05, 0.02), 12.0),
    "lamp": lambda: material("Lamp_Warm", (1.0, 0.85, 0.6), 0.0, 0.4, (1.0, 0.76, 0.42), 3.5),
    "helipad": lambda: material("Helipad", (1, 1, 1), 0.0, 0.8, base_tex=image("Helipad", helipad_texture)),
    "road": lambda: _surface("Road", road_set()),
    "junction": lambda: _surface("Junction", junction_set()),
    "sidewalk": lambda: _surface("Sidewalk", paving_set(71, 64, (0.52, 0.51, 0.49))),
    "paving": lambda: _surface("Paving", paving_set(72, 128, (0.56, 0.52, 0.47), 0.7, 512, 0.18)),
    "curb": lambda: material("Curb", (0.55, 0.54, 0.52), 0.0, 0.8),
    "paint": lambda: material("Car_Paint", (0.8, 0.8, 0.8), 0.55, 0.32),
    "tire": lambda: material("Tire", (0.02, 0.02, 0.02), 0.0, 0.85),
    "chrome": lambda: material("Chrome", (0.7, 0.72, 0.75), 1.0, 0.2),
    "headlight": lambda: material("Headlight", (1, 1, 0.95), 0.0, 0.2, (1.0, 0.95, 0.85), 4.0),
    "taillight": lambda: material("Taillight", (0.8, 0.05, 0.03), 0.0, 0.3, (1.0, 0.04, 0.02), 4.0),
    "hazard": lambda: material("Barrier_Stripe", (0.8, 0.1, 0.05), 0.0, 0.6),
    "white": lambda: material("Barrier_White", (0.85, 0.85, 0.82), 0.0, 0.6),
    "skyline": _skyline,
    "sign": _sign,
}
class Mats(dict):
    """Materials are created on first use so each export only carries what it needs.

    Library keys resolve to untextured placeholders unless ``textured`` (the library export itself,
    or standalone assets such as the destructibles that are not remapped at runtime).
    """

    def __init__(self, textured=False):
        super().__init__()
        self.textured = textured

    def __missing__(self, key):
        if key in LIBRARY:
            mat = _library(key) if self.textured else _placeholder(key)
        else:
            mat = MAT_DEFS[key]()
        self[key] = mat
        return mat


def city_mats(textured=False):
    return Mats(textured)


def build_material_library():
    """city_materials.glb: one small swatch mesh per shared material."""
    reset_scene()
    M = city_mats(True)
    root = empty("CityMaterials")
    for i, key in enumerate(LIBRARY):
        swatch = box(f"Swatch_{LIBRARY[key][0]}", (1, 1, 1), (i * 1.5, 0, 0), M[key])
        box_uv(swatch, 1.0)
        parent_keep(swatch, root)
    export("city_materials.glb")


# --------------------------------------------------------------------------- helpers


def offset_poly(pts, d):
    """Offset a CCW polygon outward by ``d`` (mitred corners)."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (p1[0] - p0[0], p1[1] - p0[1])
        e2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*e1), math.hypot(*e2)
        n1 = (e1[1] / l1, -e1[0] / l1)
        n2 = (e2[1] / l2, -e2[0] / l2)
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        ml = math.hypot(mx, my)
        mx, my = mx / ml, my / ml
        cos = mx * n1[0] + my * n1[1]
        out.append((p1[0] + mx * d / cos, p1[1] + my * d / cos))
    return out


def parapet(pts, z, h, t, mat):
    objs = []
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length  # inward for CCW
        cx, cy = (x0 + x1) / 2 + nx * t / 2, (y0 + y1) / 2 + ny * t / 2
        objs.append(box("parapet", (length + t, t, h), (cx, cy, z + h / 2), mat,
                        rot=(0, 0, math.degrees(math.atan2(dy, dx)))))
    return objs


class Bld:
    def __init__(self, name, M):
        self.name, self.M = name, M
        self.parts, self.cols, self.anchors = [], [], []

    def add(self, *objs):
        for o in objs:
            if isinstance(o, (list, tuple)):
                self.parts.extend(o)
            else:
                self.parts.append(o)

    def mass(self, pts, z0, z1, facade, roof="roof", col=True):
        self.parts.append(prism("mass", pts, z0, z1, [self.M[facade], self.M[roof]], uv_scale=FACADE_SPAN))
        if col:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            self.box_col((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, z0,
                         max(xs) - min(xs), max(ys) - min(ys), z1 - z0)

    def ledge(self, pts, z, th=0.7, over=0.6, mat="concrete"):
        self.parts.append(prism("ledge", offset_poly(pts, over), z, z + th, [self.M[mat], self.M[mat]]))

    def parapet(self, pts, z, h=1.1, t=0.4, mat="concrete"):
        self.parts.extend(parapet(pts, z, h, t, self.M[mat]))

    def box_col(self, cx, cy, z0, w, d, h, rot=0.0):
        self.cols.append(("BOX", (cx, cy, z0 + h / 2), (w / 2, d / 2, h / 2), rot))

    def cyl_col(self, cx, cy, z0, r, h):
        self.cols.append(("CYL", (cx, cy, z0 + h / 2), (r, r, h / 2), 0.0))

    def anchor(self, kind, x, y, z):
        self.anchors.append((kind, (x, y, z)))

    def vents(self, pts, z):
        for i, (x, y) in enumerate(pts):
            self.add(cylinder("vent", 0.45, 1.0, (x, y, z + 0.5), self.M["metal"], segments=10),
                     cylinder("vent_cap", 0.7, 0.35, (x, y, z + 1.15), self.M["metal_dark"], r2=0.2, segments=10))

    def storefront(self, pts, z1=5.6, out=0.25):
        """Ground-floor retail band wrapped around the footprint (library 'Storefront' material)."""
        self.parts.append(prism("storefront", offset_poly(pts, out), 0.0, z1, [self.M["storefront"], self.M["concrete"]],
                                uv_scale=(32.0, 5.6)))

    def finish(self):
        root = empty(self.name)
        for o in self.parts:
            if not o.data.uv_layers:
                names = [m.name for m in o.data.materials if m]
                tile = next((UV_TILE[k] for k in UV_TILE if LIBRARY[k][0] in names), 4.0)
                box_uv(o, tile)
        render = join(self.parts, "Render")
        parent_keep(render, root)
        for i, (kind, c, half, rot) in enumerate(self.cols):
            collider(f"COL_{kind}_{i}", c, half, root, rot)
        for i, (kind, p) in enumerate(self.anchors):
            empty(f"Anchor_{kind}_{i}", p, parent=root)
        export(f"{self.name}.glb")


# --------------------------------------------------------------------------- buildings


def b01(M):
    """Setback office tower (~114 m)."""
    b = Bld("building_01", M)
    tiers = [(32, 0, 42), (26, 42, 80), (18, 80, 108)]
    for w, z0, z1 in tiers:
        b.mass(rect(w, w), z0, z1, "office")
        b.ledge(rect(w, w), z1 - 0.2, 0.9, 0.5)
        b.parapet(rect(w + 1.0, w + 1.0), z1 + 0.7, 1.0, 0.35)
    b.storefront(rect(32, 32))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.add(box("pilaster", (1.4, 1.4, 42), (sx * 16, sy * 16, 21), M["concrete"]))
            b.add(box("pilaster", (1.1, 1.1, 38), (sx * 13, sy * 13, 61), M["concrete"]))
    b.mass(rect(8, 8), 108, 114, "industrial", "roof")
    b.vents([(5, -6), (-6, 5)], 108.7)
    b.anchor("Roof", 6.0, 6.0, 108.7)
    b.anchor("Roof", -6.0, -6.0, 108.7)
    b.anchor("Top", 0.0, 0.0, 114.0)
    b.anchor("Small", 14.2, 4.0, 42.7)
    b.anchor("Small", -4.0, -14.2, 42.7)
    b.anchor("Small", 11.2, -3.0, 80.7)
    b.finish()


def b02(M):
    """Glass slab with vertical fins and an open crown frame (~93 m)."""
    b = Bld("building_02", M)
    b.mass(rect(36, 24), 0, 8, "glass", "roof")
    b.storefront(rect(36, 24), 5.6, 0.2)
    b.mass(rect(34, 22), 8, 84, "glass")
    b.ledge(rect(36, 24), 8, 0.6, 0.3, "metal")
    for i in range(9):
        x = -16 + i * 4
        for sy in (-1, 1):
            b.add(box("fin", (0.35, 1.2, 76), (x, sy * 11.6, 46), M["metal"]))
    b.parapet(rect(34, 22), 84, 1.0, 0.3, "metal")
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.add(box("crown_post", (1.2, 1.2, 9), (sx * 16.4, sy * 10.4, 88.5), M["metal"]))
        b.add(box("crown_beam", (1.0, 22, 1.0), (sx * 16.4, 0, 92.5), M["metal"]))
    for sy in (-1, 1):
        b.add(box("crown_beam", (34, 1.0, 1.0), (0, sy * 10.4, 92.5), M["metal"]))
    b.mass(rect(10, 6), 84, 88, "industrial", "roof")
    b.vents([(-3, 7), (3, -7)], 84)
    b.anchor("Roof", 11.0, 0.0, 84.0)
    b.anchor("Roof", -11.0, 0.0, 84.0)
    b.anchor("Small", 0.0, -7.8, 84.0)
    b.finish()


def b03(M):
    """Cylindrical tower with ledge rings and a rooftop helipad (~104 m)."""
    b = Bld("building_03", M)
    poly = regular_polygon(15, 20)
    b.parts.append(prism("drum", poly, 0, 96, [M["band"], M["roof"]], uv_scale=FACADE_SPAN, sharp=30))
    b.cyl_col(0, 0, 0, 15.0, 96)
    b.storefront(poly)
    for z in (24, 48, 72):
        b.parts.append(prism("ring", offset_poly(poly, 0.8), z - 0.35, z + 0.35, [M["concrete"], M["concrete"]], sharp=30))
    b.add(parapet(poly, 96, 1.1, 0.35, M["concrete"]))
    upper = regular_polygon(9, 16)
    b.parts.append(prism("upper", upper, 96, 103, [M["metal"], M["roof"]], uv_scale=(16, 16), sharp=30))
    b.cyl_col(0, 0, 96, 9.0, 7.4)
    pad = prism("pad", regular_polygon(7.6, 24), 103, 103.4, [M["metal_dark"], M["helipad"]], uv_scale=(15.2, 15.2),
                sharp=30)
    b.parts.append(pad)
    b.cyl_col(0, 0, 103, 7.6, 0.4)
    for i in range(8):
        a = 2 * math.pi * (i + 0.5) / 8
        b.add(box("pad_light", (0.3, 0.3, 0.2), (7.2 * math.cos(a), 7.2 * math.sin(a), 103.5), M["lamp"]))
    b.anchor("Pad", 0.0, 0.0, 103.4)
    for x, y in ((12, 0), (-12, 0), (0, 12), (0, -12)):
        b.anchor("Roof", x, y, 96.0)
    b.finish()


def b04(M):
    """L-shaped brick mid-rise with storefront glazing and parapet (~37 m)."""
    b = Bld("building_04", M)
    L = [(-17, -17), (17, -17), (17, 1), (1, 1), (1, 17), (-17, 17)]
    b.parts.append(prism("mass", L, 0, 36, [M["brick"], M["roof"]], uv_scale=FACADE_SPAN))
    b.box_col(0, -8, 0, 34, 18, 36)
    b.box_col(-8, 9, 0, 18, 16, 36)
    b.storefront(L)
    b.ledge(L, 5.6, 0.5, 0.45)
    b.ledge(L, 33.6, 0.6, 0.5)
    b.parapet(L, 36, 1.2, 0.4)
    b.add(box("stair", (5, 4, 3.5), (-10, 10, 37.75), M["concrete"]))
    b.box_col(-10, 10, 36, 5, 4, 3.5)
    b.vents([(-3, 13), (12, -3)], 36)
    b.anchor("Roof", 8.0, -9.0, 36.0)
    b.anchor("Roof", -8.0, -9.0, 36.0)
    b.anchor("Roof", -9.0, 2.0, 36.0)
    b.anchor("Small", -3.0, 5.0, 36.0)
    b.finish()


def b05(M):
    """Twin towers on a shared podium joined by a skybridge (~75 m)."""
    b = Bld("building_05", M)
    b.mass(rect(34, 24), 0, 14, "office")
    b.storefront(rect(34, 24))
    b.parapet(rect(34, 24), 14, 1.0, 0.35)
    b.mass(rect(14, 14, -9, 0), 14, 74, "glass")
    b.mass(rect(14, 14, 9, 0), 14, 62, "glass")
    for cx, top in ((-9, 74), (9, 62)):
        b.ledge(rect(14, 14, cx, 0), top - 0.3, 0.8, 0.4, "metal")
        for z in range(22, top - 4, 12):
            b.ledge(rect(14, 14, cx, 0), z, 0.35, 0.25, "metal")
    b.add(box("bridge", (4.4, 5, 4), (0, 0, 42), M["glass_dark"]))
    b.add(box("bridge_frame", (4.4, 5.4, 0.5), (0, 0, 44.2), M["metal"]))
    b.add(box("bridge_frame", (4.4, 5.4, 0.5), (0, 0, 39.8), M["metal"]))
    b.box_col(0, 0, 39.6, 4.4, 5.4, 4.8)
    b.mass(rect(7, 7, -9, 0), 74.5, 76.5, "industrial")
    b.anchor("Top", -9.0, 0.0, 76.5)
    b.anchor("Roof", 9.0, 0.0, 62.5)
    b.anchor("Roof", -9.0, 9.5, 14.0)
    b.anchor("Roof", 9.0, -9.5, 14.0)
    b.anchor("Small", 9.0, 9.5, 14.0)
    b.finish()


def b06(M):
    """Stepped ziggurat with planted terraces (~51 m)."""
    b = Bld("building_06", M)
    tiers = [(34, 0, 12), (28, 12, 24), (22, 24, 36), (16, 36, 48)]
    b.storefront(rect(34, 34))
    for i, (w, z0, z1) in enumerate(tiers):
        b.mass(rect(w, w), z0, z1, "band")
        b.parapet(rect(w, w), z1, 0.9, 0.35)
        if i < 3:
            inner = tiers[i + 1][0]
            mid = (w + inner) / 4.0
            for sx, sy, lw, ld in ((0, 1, inner, 1.2), (0, -1, inner, 1.2), (1, 0, 1.2, inner), (-1, 0, 1.2, inner)):
                cx, cy = sx * mid, sy * mid
                b.add(box("planter", (lw * 0.8, ld, 0.6), (cx, cy, z1 + 0.3), M["concrete_dark"]),
                      box("hedge", (lw * 0.78, ld * 0.85, 0.7), (cx, cy, z1 + 0.9), M["foliage"], bevel=0.2))
    b.mass(rect(8, 8), 48, 51, "industrial")
    b.anchor("Roof", 5.5, 5.5, 48.0)
    b.anchor("Roof", -5.5, -5.5, 48.0)
    b.anchor("Roof", 5.5, -5.5, 48.0)
    b.anchor("Top", 0.0, 0.0, 51.0)
    b.finish()


def b07(M):
    """Landmark spire tower (~177 m)."""
    b = Bld("building_07", M)
    poly = chamfered_rect(26, 26, 3.0)
    b.parts.append(prism("mass", poly, 0, 118, [M["glass"], M["roof"]], uv_scale=FACADE_SPAN))
    b.box_col(0, 0, 0, 26, 26, 118)
    b.storefront(poly)
    for z in (40, 80):
        b.ledge(poly, z, 0.9, 0.6, "metal")
    top = chamfered_rect(15, 15, 2.0)
    pts = [(x, y, 118) for x, y in poly] + [(x, y, 136) for x, y in top]
    b.add(hull("taper", pts, M["metal"]))
    b.box_col(0, 0, 118, 21, 21, 18)
    b.add(cylinder("spire", 1.3, 40, (0, 0, 156), M["metal"], r2=0.25, segments=12))
    b.cyl_col(0, 0, 136, 1.0, 40)
    b.add(icosphere("beacon", 0.5, (0, 0, 176.4), M["beacon"]))
    b.add(tube("crown", 8.2, 7.6, 1.2, (0, 0, 136.6), M["metal"], segments=24))
    b.anchor("Roof", 4.3, 0.0, 136.0)
    b.anchor("Roof", -4.3, 0.0, 136.0)
    b.finish()


def b08(M):
    """Industrial warehouse with sawtooth roof and loading docks (~16 m)."""
    b = Bld("building_08", M)
    b.mass(rect(36, 28), 0, 12, "industrial")
    for i in range(4):
        x0 = -18 + 6 * i
        pts = [(x0, -14, 12), (x0 + 6, -14, 12), (x0, 14, 12), (x0 + 6, 14, 12), (x0 + 6, -14, 16), (x0 + 6, 14, 16)]
        b.add(hull("tooth", pts, M["metal_roof"]))
        b.add(box("glazing", (0.12, 27.2, 3.4), (x0 + 6.05, 0, 13.9), M["glass_dark"]))
    b.box_col(-6, 0, 12, 24, 28, 4)
    b.parapet(rect(36, 28), 12, 0.8, 0.3, "metal_dark")
    for x in (-10, -3, 4):
        b.add(box("dock_door", (4.0, 0.3, 4.4), (x, -14.05, 2.4), M["metal_dark"]),
              box("dock_canopy", (5.0, 2.0, 0.25), (x, -15.0, 5.1), M["metal"]))
    b.vents([(9, 11), (15, 11), (9, -11)], 12)
    b.anchor("Roof", 12.5, -4.0, 12.0)
    b.anchor("Roof", 12.5, 5.0, 12.0)
    b.finish()


def b09(M):
    """Residential slab with continuous balconies (~52 m)."""
    b = Bld("building_09", M)
    b.mass(rect(30, 18), 0, 48, "residential")
    b.storefront(rect(30, 18))
    for k in range(11):
        z = 7.0 + 3.5 * k
        for x in (-10, 0, 10):
            for sy in (-1, 1):
                b.add(box("slab", (5.0, 1.5, 0.25), (x, sy * 9.75, z), M["concrete"]),
                      box("rail", (5.0, 0.06, 1.0), (x, sy * 10.47, z + 0.6), M["metal_dark"]))
    for sy in (-1, 1):
        b.box_col(0, sy * 9.75, 6.8, 30, 1.5, 36.4)
    b.parapet(rect(30, 18), 48, 1.1, 0.35)
    b.mass(rect(10, 8), 48, 51.5, "residential")
    b.vents([(-11, 6), (11, -6)], 48)
    b.anchor("Roof", 10.0, 3.0, 48.0)
    b.anchor("Roof", -10.0, -3.0, 48.0)
    b.anchor("Top", 0.0, 0.0, 51.5)
    b.finish()


# --------------------------------------------------------------------------- street modules


def flat_uv(obj, su, sv, ou=0.0, ov=0.0):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co.x / su + ou, co.y / sv + ov)
    bm.to_mesh(obj.data)
    bm.free()


def road(M):
    reset_scene()
    M = city_mats()
    root = empty("Road")
    slab = box("Road_Surface", (14, 80, 0.3), (0, 0, -0.15), M["road"])
    flat_uv(slab, 14, 40, 0.5, 0.0)
    parent_keep(slab, root)
    export("road.glb")


def intersection(M):
    reset_scene()
    M = city_mats()
    root = empty("Intersection")
    slab = box("Junction_Surface", (20, 20, 0.3), (0, 0, -0.15), M["junction"])
    flat_uv(slab, 20, 20, 0.5, 0.5)
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = box("corner", (3, 3, 0.2), (sx * 8.5, sy * 8.5, 0.1), M["sidewalk"])
            flat_uv(c, 4, 4)
            corners.append(c)
            corners.append(box("corner_curb", (3.0, 0.25, 0.26), (sx * 8.5, sy * 7.12, 0.13), M["curb"]))
            corners.append(box("corner_curb", (0.25, 3.0, 0.26), (sx * 7.12, sy * 8.5, 0.13), M["curb"]))
    parent_keep(slab, root)
    parent_keep(join(corners, "Corners"), root)
    export("intersection.glb")


def sidewalk(M):
    reset_scene()
    M = city_mats()
    root = empty("Sidewalk")
    s = box("Sidewalk_Surface", (3, 80, 0.2), (0, 0, 0.1), M["sidewalk"])
    flat_uv(s, 4, 4)
    curb = box("curb", (0.25, 80, 0.26), (-1.375, 0, 0.13), M["curb"])
    parent_keep(join([s, curb], "Sidewalk_Mesh"), root)
    export("sidewalk.glb")


def plaza(M):
    reset_scene()
    M = city_mats()
    root = empty("Plaza")
    s = box("Plaza_Surface", (80, 80, 0.2), (0, 0, 0.1), M["paving"])
    flat_uv(s, 8, 8)
    parent_keep(s, root)
    export("plaza.glb")


# --------------------------------------------------------------------------- props


def prop(name, objs, filename):
    root = empty(name)
    for o in objs:
        if not o.data.uv_layers:
            box_uv(o, 2.0)
    parent_keep(join(objs, f"{name}_Mesh"), root)
    export(filename)


def strut(name, a, b, t, mat):
    """Thin rectangular bar between two points (pillars, braces, rails)."""
    pts = []
    for p in (a, b):
        for dx in (-t, t):
            for dz in (-t, t):
                pts.append((p[0] + dx, p[1], p[2] + dz))
    return hull(name, pts, mat)


def street_lamp():
    reset_scene()
    M = city_mats()
    dark = M["metal_dark"]
    objs = [
        cylinder("base", 0.24, 0.9, (0, 0, 0.45), dark, segments=8, r2=0.17),
        box("door", (0.14, 0.03, 0.4), (0.0, -0.2, 0.5), M["metal"]),
        cylinder("pole", 0.11, 6.6, (0, 0, 4.2), dark, segments=8, r2=0.075),
        sweep("arm", [(0, 0, 7.3), (0, 0, 7.55), (-0.25, 0, 7.8), (-0.8, 0, 7.92), (-1.75, 0, 7.82)], 0.055, dark, 6),
        hull("head", [(-1.7, -0.19, 7.78), (-2.75, -0.17, 7.72), (-1.7, 0.19, 7.78), (-2.75, 0.17, 7.72),
                      (-1.75, -0.14, 7.9), (-2.68, -0.12, 7.84), (-1.75, 0.14, 7.9), (-2.68, 0.12, 7.84)], dark),
        box("light", (0.82, 0.26, 0.03), (-2.22, 0, 7.735), M["lamp"], rot=(0, -3.3, 0)),
    ]
    prop("StreetLamp", objs, "street_lamp.glb")


def car():
    reset_scene()
    M = city_mats()
    paint, dark, glass = M["paint"], M["metal_dark"], M["glass_dark"]
    objs = [
        rloft("body", [(-2.3, 0, 0.56, 1.6, 0.4, 3.2), (-2.08, 0, 0.62, 1.76, 0.58, 3.6), (-1.3, 0, 0.66, 1.82, 0.7, 3.8),
                       (1.3, 0, 0.67, 1.82, 0.72, 3.8), (2.08, 0, 0.66, 1.76, 0.62, 3.6), (2.32, 0, 0.66, 1.62, 0.44, 3.2)],
              paint, axis="Y", n=16),
        hull("cabin", [(-0.8, -0.95, 0.98), (0.8, -0.95, 0.98), (-0.8, 1.25, 1.0), (0.8, 1.25, 1.0),
                       (-0.66, -0.3, 1.44), (0.66, -0.3, 1.44), (-0.66, 0.78, 1.44), (0.66, 0.78, 1.44)], glass),
        hull("roof", [(-0.675, -0.3, 1.43), (0.675, -0.3, 1.43), (-0.675, 0.78, 1.43), (0.675, 0.78, 1.43),
                      (-0.62, -0.24, 1.47), (0.62, -0.24, 1.47), (-0.62, 0.72, 1.47), (0.62, 0.72, 1.47)], paint),
        box("grille", (1.0, 0.05, 0.2), (0, -2.31, 0.6), dark),
        rloft("bumper_f", [(-2.42, 0, 0.42, 1.72, 0.2, 3.0), (-2.2, 0, 0.42, 1.76, 0.22, 3.0)], dark, axis="Y", n=12),
        rloft("bumper_r", [(2.2, 0, 0.44, 1.76, 0.22, 3.0), (2.44, 0, 0.44, 1.72, 0.2, 3.0)], dark, axis="Y", n=12),
        box("plate_f", (0.5, 0.03, 0.12), (0, -2.43, 0.44), M["white"]),
        box("plate_r", (0.5, 0.03, 0.12), (0, 2.45, 0.5), M["white"]),
    ]
    for s in (1, -1):
        objs.append(strut("a_pillar", (s * 0.77, -0.93, 0.99), (s * 0.64, -0.3, 1.44), 0.035, paint))
        objs.append(strut("b_pillar", (s * 0.75, 0.25, 1.0), (s * 0.66, 0.25, 1.44), 0.04, paint))
        objs.append(strut("c_pillar", (s * 0.77, 1.22, 1.0), (s * 0.64, 0.77, 1.44), 0.04, paint))
        objs.append(box("mirror", (0.12, 0.08, 0.1), (s * 0.95, -0.78, 1.02), paint))
        objs.append(box("headlight", (0.36, 0.05, 0.12), (s * 0.6, -2.3, 0.74), M["headlight"], rot=(0, 0, s * -8)))
        objs.append(box("taillight", (0.38, 0.05, 0.1), (s * 0.6, 2.33, 0.78), M["taillight"], rot=(0, 0, s * 8)))
        for sy in (-1, 1):
            objs.append(cylinder("tire", 0.34, 0.24, (s * 0.8, sy * 1.38, 0.34), M["tire"], (0, 90, 0), 10))
            objs.append(cylinder("hub", 0.2, 0.25, (s * 0.8, sy * 1.38, 0.34), M["chrome"], (0, 90, 0), 8))
    prop("Car", objs, "car.glb")


def barrier():
    reset_scene()
    M = city_mats()
    prof = [(-0.33, 0.0), (0.33, 0.0), (0.2, 0.3), (0.11, 0.82), (-0.11, 0.82), (-0.2, 0.3)]
    pts = [(x, y, z) for x, z in prof for y in (-1.5, 1.5)]
    objs = [hull("jersey", pts, M["concrete"], bevel=0.02)]
    for i, y in enumerate((-1.1, -0.35, 0.4, 1.15)):
        objs.append(box("stripe", (0.26, 0.45, 0.14), (0, y, 0.66), M["hazard" if i % 2 == 0 else "white"],
                        rot=(0, 0, 0)))
    prop("Barrier", objs, "barrier.glb")


def rooftop_hvac():
    reset_scene()
    M = city_mats()
    dark = M["metal_dark"]
    objs = [
        box("skid", (3.2, 2.2, 0.22), (0, 0, 0.11), dark),
        box("unit", (3.0, 2.0, 1.5), (0, 0, 0.97), M["metal"], bevel=0.04),
        box("coil", (0.04, 1.8, 1.1), (1.52, 0, 0.9), dark),
        box("panel", (0.6, 0.04, 0.9), (-0.8, -1.02, 0.95), M["metal"], bevel=0.01),
        box("ebox", (0.4, 0.25, 0.5), (-1.2, 1.12, 0.8), dark),
    ]
    for x in (-0.75, 0.75):
        objs.append(tube("fan_ring", 0.62, 0.54, 0.24, (x, 0, 1.84), dark, segments=12))
        objs.append(cylinder("fan_hub", 0.12, 0.12, (x, 0, 1.8), dark, segments=6))
        for k in range(3):
            objs.append(box("fan_blade", (0.95, 0.14, 0.015), (x, 0, 1.79), M["metal"], rot=(12, 0, 60 * k)))
        for dy in (-0.2, 0.2):
            objs.append(box("grille", (1.16, 0.025, 0.025), (x, dy, 1.96), dark))
    for i in range(5):
        objs.append(box("louver", (0.05, 1.8, 0.07), (1.56, 0, 0.5 + i * 0.2), dark, rot=(0, 30, 0)))
    objs.append(sweep("pipe", [(-1.5, 0.5, 0.6), (-1.75, 0.5, 0.6), (-1.95, 0.5, 0.4), (-1.95, 0.5, 0.1)], 0.09, M["metal"], 6))
    prop("RooftopHVAC", objs, "rooftop_hvac.glb")


def rooftop_vent():
    reset_scene()
    M = city_mats()
    dark = M["metal_dark"]
    objs = [
        box("pad", (1.8, 1.8, 0.2), (0, 0, 0.1), M["concrete"]),
        cylinder("stack", 0.4, 1.8, (0.3, 0.2, 1.1), M["metal"], segments=12),
        tube("flange", 0.46, 0.38, 0.08, (0.3, 0.2, 0.24), dark, segments=12),
        lathe("cap", [(0.0, 0.42), (0.3, 0.36), (0.62, 0.12), (0.64, 0.06), (0.42, 0.08), (0.0, 0.12)], 12, (0.3, 0.2, 1.9),
              dark),
        box("box", (0.8, 0.6, 0.7), (-0.4, -0.4, 0.55), M["metal"], bevel=0.03),
        sweep("pipe", [(-0.4, -0.1, 0.7), (-0.4, 0.2, 0.85), (-0.1, 0.2, 1.0)], 0.1, dark, 8),
    ]
    prop("RooftopVent", objs, "rooftop_vent.glb")


def antenna():
    reset_scene()
    M = city_mats()
    dark = M["metal_dark"]
    objs = [box("base", (1.6, 1.6, 0.4), (0, 0, 0.2), M["concrete"])]
    r = 0.45
    legs = [(r * math.cos(a), r * math.sin(a)) for a in (0.0, 2.094, 4.189)]
    height = 13.0
    for x, y in legs:
        objs.append(cylinder("leg", 0.06, height, (x, y, 0.4 + height / 2), dark, segments=6))
    for k in range(8):
        z = 1.2 + k * 1.5
        for i in range(3):
            (x0, y0), (x1, y1) = legs[i], legs[(i + 1) % 3]
            length = math.hypot(x1 - x0, y1 - y0)
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            objs.append(box("brace", (length, 0.05, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, z), dark, rot=(0, 0, ang)))
            if k % 2 == 0:
                objs.append(box("diag", (length * 1.18, 0.035, 0.035), ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.75), dark,
                                rot=(0, 45, ang)))
    objs.append(lathe("dish", [(0.0, 0.0), (0.4, 0.05), (0.75, 0.18), (0.9, 0.28), (0.86, 0.3), (0.72, 0.22), (0.38, 0.1),
                               (0.0, 0.05)], 20, (0.75, 0, 8.5), M["metal"], (0, -70, 0)))
    objs.append(cylinder("feed", 0.03, 0.8, (1.05, 0, 8.6), dark, (0, -70, 0), 6))
    for z, a in ((5.5, 0), (10.0, 120)):
        objs.append(box("panel_antenna", (0.3, 0.12, 1.4), (0.5 * math.cos(math.radians(a)), 0.5 * math.sin(math.radians(a)), z),
                        M["white"], rot=(0, 0, a)))
    objs.append(cylinder("mast", 0.05, 3.0, (0, 0, height + 1.9), M["metal"], segments=6))
    objs.append(icosphere("beacon", 0.22, (0, 0, height + 3.5), M["beacon"]))
    prop("Antenna", objs, "antenna.glb")


def blob(name, r, loc, mat, rng, subdiv=2, scale=(1, 1, 1), amp=0.18):
    """Lumpy icosphere for foliage clumps (deterministic vertex jitter along the normals)."""
    import bmesh
    o = icosphere(name, r, loc, mat, subdiv, scale, smooth=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    c = sum((v.co for v in bm.verts), __import__("mathutils").Vector()) / len(bm.verts)
    for v in bm.verts:
        d = (v.co - c).normalized()
        v.co += d * r * amp * (rng.random() * 2 - 1)
    bm.to_mesh(o.data)
    bm.free()
    return o


def tree():
    import random
    reset_scene()
    M = city_mats()
    rng = random.Random(7)
    fmaps, bmaps = facades.foliage_set(), facades.bark_set()
    leaves = material("Foliage", (1, 1, 1), 0.0, 0.8, base_tex=pbr.image("Foliage_albedo", fmaps["albedo"]))
    pbr.attach_maps(leaves, None, pbr.image("Foliage_orm", fmaps["orm"], True), pbr.image("Foliage_normal", fmaps["normal"], True))
    bark = material("Bark", (1, 1, 1), 0.0, 0.9, base_tex=pbr.image("Bark_albedo", bmaps["albedo"]))
    pbr.attach_maps(bark, None, pbr.image("Bark_orm", bmaps["orm"], True), pbr.image("Bark_normal", bmaps["normal"], True))
    objs = [cylinder("trunk", 0.2, 3.2, (0, 0, 1.6), bark, r2=0.12, segments=8)]
    for a, h, L in ((0.3, 2.6, 1.3), (2.4, 2.9, 1.1), (4.3, 3.1, 1.0)):
        tip = (math.cos(a) * L, math.sin(a) * L, h + 0.9)
        objs.append(sweep("branch", [(0, 0, h - 0.4), (math.cos(a) * L * 0.5, math.sin(a) * L * 0.5, h + 0.4), tip],
                          lambda u: 0.1 - 0.06 * u, bark, 6))
    for (x, y, z, r) in ((0, 0, 4.1, 1.7), (0.9, 0.4, 4.7, 1.25), (-0.8, -0.5, 4.9, 1.15), (0.3, -0.9, 4.3, 1.1),
                         (-0.4, 0.8, 5.3, 1.0)):
        objs.append(blob("canopy", r, (x, y, z), leaves, rng, 2, (1, 1, 0.85)))
    for o in objs:
        box_uv(o, 1.5)
    prop("Tree", objs, "tree.glb")


def skyline():
    """Low-detail silhouettes for the distant horizon ring (instanced with random scale)."""
    reset_scene()
    M = city_mats()
    root = empty("Skyline")
    sk = M["skyline"]
    span = (32.0, 28.0)

    def mass(name, pts, z0, z1):
        return prism(name, pts, z0, z1, [sk, sk], uv_scale=span)

    variants = [
        [mass("s0a", rect(30, 20), 0, 90), mass("s0b", rect(22, 14), 90, 104)],
        [mass("s1a", rect(22, 22), 0, 120), mass("s1b", rect(16, 16), 120, 145), mass("s1c", rect(10, 10), 145, 158),
         cylinder("s1d", 0.9, 40, (0, 0, 178), sk, segments=6, r2=0.15)],
        [mass("s2a", regular_polygon(12, 12), 0, 110), mass("s2b", regular_polygon(10.5, 12), 110, 118)],
        [mass("s3a", rect(40, 40), 0, 45), mass("s3b", rect(20, 30, -8, 0), 45, 70)],
        [mass("s4a", rect(14, 14, -10, 0), 0, 130), mass("s4b", rect(14, 14, 10, 0), 0, 112)],
        [mass("s5a", rect(26, 26), 0, 80), mass("s5b", rect(20, 20), 80, 92), mass("s5c", rect(14, 14), 92, 102),
         mass("s5d", rect(8, 8), 102, 110)],
        [hull("s6", [(-13, -13, 0), (13, -13, 0), (13, 13, 0), (-13, 13, 0), (-13, -13, 140), (13, -13, 116),
                     (13, 13, 116), (-13, 13, 140)], sk)],
        [mass("s7a", chamfered_rect(24, 24, 4), 0, 150), cylinder("s7b", 0.5, 45, (0, 0, 172), sk, segments=6)],
    ]
    for i, parts in enumerate(variants):
        for o in parts:
            if not o.data.uv_layers:
                box_uv(o, 32.0, 28.0)
        parent_keep(join(parts, f"Skyline_{i}"), root)
    export("skyline.glb")


def build_buildings():
    for fn in (b01, b02, b03, b04, b05, b06, b07, b08, b09):
        reset_scene()
        fn(city_mats())


def build():
    build_material_library()
    build_buildings()
    road(None)
    intersection(None)
    sidewalk(None)
    plaza(None)
    street_lamp()
    car()
    barrier()
    rooftop_hvac()
    rooftop_vent()
    antenna()
    tree()
    skyline()
    log("city kit done")


if __name__ == "__main__":
    build()
