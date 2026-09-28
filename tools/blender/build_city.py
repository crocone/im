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
    box, box_uv, chamfered_rect, collider, cylinder, empty, export, hull, icosphere, join, log, loft,
    material, parent_keep, prism, rect, regular_polygon, reset_scene, tube,
)
from textures import (  # noqa: E402
    FACADE_SPAN, ad_texture, facade_images, helipad_texture, image, intersection_texture,
    paving_texture, road_texture, roof_texture, skyline_texture,
)


# --------------------------------------------------------------------------- materials


FACADE_PBR = {
    "office": (0.55, 0.15, 2.4), "glass": (0.2, 0.55, 2.0), "band": (0.5, 0.2, 2.4),
    "brick": (0.82, 0.0, 2.4), "industrial": (0.45, 0.55, 2.0), "residential": (0.75, 0.0, 2.4),
}


def _facade(style):
    rough, metal, strength = FACADE_PBR[style]
    b, e = facade_images("metal" if style == "industrial" else style)
    return material(f"Facade_{style.capitalize()}", (1, 1, 1), metal, rough, (1, 1, 1), strength, b, e)


def _skyline():
    b, e = skyline_texture()
    return material("Skyline", (1, 1, 1), 0.2, 0.7, (1, 1, 1), 2.2, image("Skyline", b), image("Skyline_Emit", e))


def _sign():
    img = image("Billboard", ad_texture)
    return material("Billboard", (1, 1, 1), 0.0, 0.5, (1, 1, 1), 1.6, img, img)


MAT_DEFS = {
    "roof": lambda: material("Roof_Tar", (1, 1, 1), 0.0, 0.92, base_tex=image("Roof", roof_texture)),
    "concrete": lambda: material("Concrete", (0.44, 0.43, 0.4), 0.0, 0.85),
    "concrete_dark": lambda: material("Concrete_Dark", (0.17, 0.17, 0.17), 0.0, 0.9),
    "metal": lambda: material("Metal_Panel", (0.3, 0.32, 0.35), 0.7, 0.42),
    "metal_dark": lambda: material("Metal_Dark", (0.055, 0.06, 0.065), 0.75, 0.5),
    "metal_roof": lambda: material("Metal_Roof", (0.34, 0.36, 0.39), 0.65, 0.45),
    "glass_dark": lambda: material("Glass_Dark", (0.02, 0.03, 0.04), 0.9, 0.12),
    "foliage": lambda: material("Foliage", (0.055, 0.15, 0.04), 0.0, 0.9),
    "bark": lambda: material("Bark", (0.16, 0.1, 0.06), 0.0, 0.9),
    "beacon": lambda: material("Beacon_Red", (1.0, 0.1, 0.05), 0.0, 0.4, (1.0, 0.05, 0.02), 25.0),
    "lamp": lambda: material("Lamp_Warm", (1.0, 0.85, 0.6), 0.0, 0.4, (1.0, 0.76, 0.42), 9.0),
    "helipad": lambda: material("Helipad", (1, 1, 1), 0.0, 0.8, base_tex=image("Helipad", helipad_texture)),
    "road": lambda: material("Road", (1, 1, 1), 0.0, 0.88, base_tex=image("Road", road_texture)),
    "junction": lambda: material("Junction", (1, 1, 1), 0.0, 0.88,
                                 base_tex=image("Junction", intersection_texture)),
    "sidewalk": lambda: material("Sidewalk", (1, 1, 1), 0.0, 0.85, base_tex=image(
        "Sidewalk", lambda: paving_texture(71, 32, (0.52, 0.51, 0.49)))),
    "paving": lambda: material("Paving", (1, 1, 1), 0.0, 0.8, base_tex=image(
        "Paving", lambda: paving_texture(72, 64, (0.56, 0.52, 0.47), 0.7, 256, 0.18))),
    "curb": lambda: material("Curb", (0.55, 0.54, 0.52), 0.0, 0.8),
    "paint": lambda: material("Car_Paint", (0.8, 0.8, 0.8), 0.55, 0.32),
    "tire": lambda: material("Tire", (0.02, 0.02, 0.02), 0.0, 0.85),
    "chrome": lambda: material("Chrome", (0.7, 0.72, 0.75), 1.0, 0.2),
    "headlight": lambda: material("Headlight", (1, 1, 0.95), 0.0, 0.2, (1.0, 0.95, 0.85), 10.0),
    "taillight": lambda: material("Taillight", (0.8, 0.05, 0.03), 0.0, 0.3, (1.0, 0.04, 0.02), 8.0),
    "hazard": lambda: material("Barrier_Stripe", (0.8, 0.1, 0.05), 0.0, 0.6),
    "white": lambda: material("Barrier_White", (0.85, 0.85, 0.82), 0.0, 0.6),
    "skyline": _skyline,
    "sign": _sign,
}
for _style in FACADE_PBR:
    MAT_DEFS[_style] = (lambda st: (lambda: _facade(st)))(_style)


class Mats(dict):
    """Materials are created on first use so each export only carries what it needs."""

    def __missing__(self, key):
        mat = MAT_DEFS[key]()
        self[key] = mat
        return mat


def city_mats():
    return Mats()


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

    def finish(self):
        root = empty(self.name)
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
    b.parts.append(prism("storefront", offset_poly(L, 0.12), 0.2, 4.2, [M["glass_dark"], M["concrete"]]))
    b.ledge(L, 4.2, 0.5, 0.35)
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
    for k in range(11):
        z = 7.0 + 3.5 * k
        for x in (-10, 0, 10):
            for sy in (-1, 1):
                b.add(box("slab", (5.0, 1.5, 0.25), (x, sy * 9.75, z), M["concrete"]),
                      box("rail", (5.0, 0.06, 1.0), (x, sy * 10.47, z + 0.6), M["metal_dark"]),
                      box("rail", (0.06, 1.5, 1.0), (x - 2.47, sy * 9.75, z + 0.6), M["metal_dark"]),
                      box("rail", (0.06, 1.5, 1.0), (x + 2.47, sy * 9.75, z + 0.6), M["metal_dark"]))
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
    parent_keep(join(objs, f"{name}_Mesh"), root)
    export(filename)


def street_lamp():
    reset_scene()
    M = city_mats()
    objs = [
        box("base", (0.5, 0.5, 0.6), (0, 0, 0.3), M["metal_dark"], bevel=0.04),
        cylinder("pole", 0.11, 7.0, (0, 0, 3.8), M["metal_dark"], r2=0.07, segments=10),
        box("arm", (2.4, 0.12, 0.12), (-1.1, 0, 7.25), M["metal_dark"], rot=(0, -6, 0)),
        box("head", (0.9, 0.36, 0.16), (-2.2, 0, 7.12), M["metal_dark"], bevel=0.03),
        box("light", (0.7, 0.26, 0.04), (-2.2, 0, 7.03), M["lamp"]),
    ]
    prop("StreetLamp", objs, "street_lamp.glb")


def car():
    reset_scene()
    M = city_mats()
    objs = [
        loft("body", [(-2.25, 0, 0.58, 1.66, 0.46, 0.14), (-1.7, 0, 0.62, 1.8, 0.66, 0.18),
                      (1.6, 0, 0.64, 1.8, 0.7, 0.18), (2.25, 0, 0.66, 1.7, 0.5, 0.14)], M["paint"], axis="Y",
             bevel=0.04),
        hull("cabin", [(-0.78, -0.95, 0.96), (0.78, -0.95, 0.96), (-0.78, 1.25, 0.98), (0.78, 1.25, 0.98),
                       (-0.64, -0.35, 1.44), (0.64, -0.35, 1.44), (-0.64, 0.75, 1.44), (0.64, 0.75, 1.44)],
             M["glass_dark"]),
        loft("roof", [(-0.3, 0, 1.455, 1.26, 0.04, 0.05), (0.7, 0, 1.455, 1.26, 0.04, 0.05)], M["paint"], axis="Y"),
        box("bumper_f", (1.7, 0.18, 0.2), (0, -2.28, 0.42), M["metal_dark"]),
        box("bumper_r", (1.7, 0.18, 0.2), (0, 2.3, 0.44), M["metal_dark"]),
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(cylinder("wheel", 0.34, 0.24, (sx * 0.8, sy * 1.38, 0.34), M["tire"], (0, 90, 0), 14))
            objs.append(cylinder("hub", 0.2, 0.26, (sx * 0.8, sy * 1.38, 0.34), M["chrome"], (0, 90, 0), 10))
        objs.append(box("headlight", (0.38, 0.06, 0.12), (sx * 0.58, -2.26, 0.68), M["headlight"]))
        objs.append(box("taillight", (0.4, 0.06, 0.1), (sx * 0.6, 2.27, 0.72), M["taillight"]))
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
    objs = [
        box("frame", (3.2, 2.2, 0.25), (0, 0, 0.125), M["metal_dark"]),
        box("unit", (3.0, 2.0, 1.5), (0, 0, 1.0), M["metal"], bevel=0.05),
    ]
    for x in (-0.75, 0.75):
        objs.append(tube("fan_ring", 0.62, 0.52, 0.18, (x, 0, 1.82), M["metal_dark"], segments=18))
        objs.append(cylinder("fan", 0.52, 0.04, (x, 0, 1.76), M["concrete_dark"], segments=18))
    for i in range(6):
        objs.append(box("louver", (0.04, 1.8, 0.08), (1.52, 0, 0.5 + i * 0.18), M["metal_dark"]))
    objs.append(cylinder("duct", 0.25, 1.6, (-1.9, 0.5, 0.8), M["metal"], (0, 90, 0), 10))
    prop("RooftopHVAC", objs, "rooftop_hvac.glb")


def rooftop_vent():
    reset_scene()
    M = city_mats()
    objs = [
        box("pad", (1.8, 1.8, 0.2), (0, 0, 0.1), M["concrete_dark"]),
        cylinder("stack", 0.4, 1.8, (0.3, 0.2, 1.1), M["metal"], segments=12),
        cylinder("cap", 0.6, 0.35, (0.3, 0.2, 2.1), M["metal_dark"], r2=0.15, segments=12),
        box("box", (0.8, 0.6, 0.7), (-0.4, -0.4, 0.55), M["metal"], bevel=0.03),
        cylinder("pipe", 0.12, 1.2, (-0.4, 0.2, 0.9), M["metal_dark"], (90, 0, 0), 8),
    ]
    prop("RooftopVent", objs, "rooftop_vent.glb")


def antenna():
    reset_scene()
    M = city_mats()
    objs = [box("base", (1.6, 1.6, 0.4), (0, 0, 0.2), M["concrete_dark"])]
    r = 0.45
    legs = [(r * math.cos(a), r * math.sin(a)) for a in (0.0, 2.094, 4.189)]
    height = 13.0
    for x, y in legs:
        objs.append(cylinder("leg", 0.06, height, (x, y, 0.4 + height / 2), M["metal_dark"], segments=6))
    for k in range(8):
        z = 1.2 + k * 1.5
        for i in range(3):
            (x0, y0), (x1, y1) = legs[i], legs[(i + 1) % 3]
            length = math.hypot(x1 - x0, y1 - y0)
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            objs.append(box("brace", (length, 0.05, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, z), M["metal_dark"],
                            rot=(0, 0, ang)))
    objs.append(cylinder("dish", 0.9, 0.35, (0.8, 0, 8.5), M["metal"], (0, 70, 0), 16, r2=0.25))
    objs.append(cylinder("mast", 0.05, 3.0, (0, 0, height + 1.9), M["metal"], segments=6))
    objs.append(icosphere("beacon", 0.22, (0, 0, height + 3.5), M["beacon"]))
    prop("Antenna", objs, "antenna.glb")


def tree():
    reset_scene()
    M = city_mats()
    objs = [
        cylinder("trunk", 0.2, 3.2, (0, 0, 1.6), M["bark"], r2=0.12, segments=8),
        icosphere("canopy", 1.7, (0, 0, 3.9), M["foliage"], scale=(1, 1, 0.85)),
        icosphere("canopy", 1.3, (0.8, 0.4, 4.7), M["foliage"], scale=(1, 1, 0.9)),
        icosphere("canopy", 1.1, (-0.6, -0.4, 5.0), M["foliage"]),
    ]
    prop("Tree", objs, "tree.glb")


def skyline():
    """Low-detail silhouettes for the distant horizon ring."""
    reset_scene()
    M = city_mats()
    root = empty("Skyline")
    sk = M["skyline"]
    variants = [
        [prism("s0", rect(30, 20), 0, 90, [sk, sk], uv_scale=(16, 16))],
        [prism("s1a", rect(22, 22), 0, 120, [sk, sk], uv_scale=(16, 16)),
         prism("s1b", rect(14, 14), 120, 150, [sk, sk], uv_scale=(16, 16))],
        [prism("s2", regular_polygon(12, 12), 0, 110, [sk, sk], uv_scale=(16, 16))],
        [prism("s3a", rect(40, 40), 0, 45, [sk, sk], uv_scale=(16, 16)),
         prism("s3b", rect(20, 30, -8, 0), 45, 70, [sk, sk], uv_scale=(16, 16))],
    ]
    for i, parts in enumerate(variants):
        parent_keep(join(parts, f"Skyline_{i}"), root)
    export("skyline.glb")


def build_buildings():
    for fn in (b01, b02, b03, b04, b05, b06, b07, b08, b09):
        reset_scene()
        fn(city_mats())


def build():
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
