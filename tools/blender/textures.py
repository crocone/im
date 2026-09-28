"""Procedural texture generation (numpy) for facades, streets, signage and props.

All textures are generated from fixed seeds, so every build produces identical pixels.
Arrays are (H, W, 3) sRGB values with row 0 at the bottom (Blender's image layout).
Facade textures cover 8 window bays (4 m) x 8 floors (3.5 m) = 32 m x 28 m.
"""
import numpy as np

from common import image_from_array

FACADE_SPAN = (32.0, 28.0)


def _rng(seed):
    return np.random.default_rng(seed)


def value_noise(rng, h, w, cy, cx):
    """Tileable smooth value noise with ``cy`` x ``cx`` lattice cells."""
    g = rng.random((cy + 1, cx + 1))
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    ys = np.arange(h) * cy / h
    xs = np.arange(w) * cx / w
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = ys - y0
    fx = xs - x0
    fy = (fy * fy * (3 - 2 * fy))[:, None]
    fx = (fx * fx * (3 - 2 * fx))[None, :]
    a = g[np.ix_(y0, x0)]
    b = g[np.ix_(y0, x0 + 1)]
    c = g[np.ix_(y0 + 1, x0)]
    d = g[np.ix_(y0 + 1, x0 + 1)]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


def fbm(rng, h, w, base=4, octaves=4):
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    aspect = w / h
    for o in range(octaves):
        n = base * (2 ** o)
        out += amp * value_noise(rng, h, w, n, max(1, int(round(n * aspect))))
        total += amp
        amp *= 0.5
    return out / total


def _c(rgb):
    return np.array(rgb, dtype=np.float32)


LIGHTS = {
    "warm": [(1.0, 0.78, 0.46), (1.0, 0.86, 0.6), (0.98, 0.7, 0.4)],
    "cool": [(0.78, 0.88, 1.0), (0.9, 0.95, 1.0), (0.7, 0.82, 0.95)],
    "mixed": [(1.0, 0.82, 0.55), (0.85, 0.92, 1.0), (1.0, 0.9, 0.75)],
}

# window rectangles are fractions of a bay: (x0, x1, y0, y1)
FACADES = {
    "office": dict(frame=(0.58, 0.56, 0.52), glass=(0.075, 0.11, 0.16), windows=[(0.1, 0.9, 0.3, 0.92)],
                   mullions=[0.5], lit=0.22, light="warm", seed=11),
    "glass": dict(frame=(0.15, 0.17, 0.19), glass=(0.12, 0.19, 0.27),
                  windows=[(0.03, 0.485, 0.07, 0.97), (0.515, 0.97, 0.07, 0.97)], mullions=[], lit=0.12,
                  light="cool", seed=12, tint=0.25),
    "band": dict(frame=(0.68, 0.66, 0.61), glass=(0.09, 0.12, 0.15), windows=[(0.0, 1.0, 0.42, 0.95)],
                 mullions=[0.0, 0.333, 0.667], lit=0.3, light="warm", seed=13),
    "brick": dict(frame=(0.4, 0.18, 0.11), glass=(0.06, 0.07, 0.08),
                  windows=[(0.13, 0.4, 0.3, 0.84), (0.6, 0.87, 0.3, 0.84)], mullions=[], lit=0.35,
                  light="warm", seed=14, surround=(0.7, 0.66, 0.58), brick=True),
    "metal": dict(frame=(0.31, 0.34, 0.37), glass=(0.1, 0.12, 0.13), windows=[(0.05, 0.95, 0.55, 0.85)],
                  mullions=[0.25, 0.5, 0.75], lit=0.25, light="cool", seed=15, rows=(1, 2), ribs=True),
    "residential": dict(frame=(0.72, 0.64, 0.52), glass=(0.07, 0.08, 0.1),
                        windows=[(0.1, 0.38, 0.32, 0.84), (0.56, 0.84, 0.03, 0.84)], mullions=[], lit=0.38,
                        light="warm", seed=16, surround=(0.86, 0.84, 0.8), curtains=True),
}


def facade(style, size=512):
    """Return (base_color, emission) arrays for a facade style."""
    S = FACADES[style]
    rng = _rng(S["seed"])
    H = W = size
    cols = rows = 8
    cw, ch = W // cols, H // rows
    n = fbm(rng, H, W, 8, 4)[..., None]
    base = np.empty((H, W, 3), np.float32)
    base[:] = _c(S["frame"]) * (0.82 + 0.3 * n)
    emit = np.zeros((H, W, 3), np.float32)
    if S.get("brick"):
        yy = np.arange(H)[:, None]
        mortar = (yy % 4 == 0).astype(np.float32)[..., None]
        base = base * (1.0 - 0.28 * mortar) + 0.05 * mortar
        base *= (0.9 + 0.2 * value_noise(rng, H, W, 64, 64))[..., None]
    if S.get("ribs"):
        xx = np.arange(W)[None, :]
        base *= (0.82 + 0.18 * np.sin(xx * 2 * np.pi / 6.0) ** 2)[..., None]
        rust = np.clip(fbm(rng, H, W, 6, 3) - 0.55, 0, 1)[..., None] * 1.6
        base = base * (1 - rust) + _c((0.35, 0.2, 0.12)) * rust
    lights = LIGHTS[S["light"]]
    row_range = S.get("rows", range(rows))
    for r in range(rows):
        for c in range(cols):
            y0, x0 = r * ch, c * cw
            if r not in row_range:
                continue
            for (fx0, fx1, fy0, fy1) in S["windows"]:
                wx0, wx1 = x0 + int(fx0 * cw), x0 + int(fx1 * cw)
                wy0, wy1 = y0 + int(fy0 * ch), y0 + int(fy1 * ch)
                if "surround" in S:
                    base[max(wy0 - 2, 0):wy1 + 2, wx0 - 2:wx1 + 2] = _c(S["surround"]) * (0.9 + 0.1 * rng.random())
                    if wy0 >= 4:
                        base[wy0 - 4:wy0 - 1, wx0 - 3:wx1 + 3] = _c(S["surround"]) * 0.92  # sill
                glass = _c(S["glass"]) * (1.0 + S.get("tint", 0.1) * (rng.random() - 0.5) * 2)
                grad = np.linspace(0.75, 1.35, wy1 - wy0, dtype=np.float32)[:, None, None]
                win = np.broadcast_to(glass, (wy1 - wy0, wx1 - wx0, 3)) * grad
                if rng.random() < S["lit"]:
                    col = _c(lights[rng.integers(len(lights))]) * rng.uniform(0.55, 1.0)
                    stripes = 1.0
                    if rng.random() < 0.35:  # blinds
                        yy = np.arange(wy1 - wy0)[:, None, None]
                        stripes = 0.72 + 0.28 * ((yy // 2) % 2)
                    base[wy0:wy1, wx0:wx1] = win * 0.35 + col * 0.65 * stripes
                    emit[wy0:wy1, wx0:wx1] = col * stripes
                elif S.get("curtains") and rng.random() < 0.4:
                    cur = _c((rng.uniform(0.3, 0.6), rng.uniform(0.2, 0.45), rng.uniform(0.15, 0.35)))
                    base[wy0:wy1, wx0:wx1] = win * 0.5 + cur * 0.5
                else:
                    base[wy0:wy1, wx0:wx1] = win
                for m in S["mullions"]:
                    mx = x0 + int(m * cw)
                    if wx0 <= mx < wx1:
                        base[wy0:wy1, max(mx - 1, 0):mx + 1] = _c(S["frame"]) * 0.55
                        emit[wy0:wy1, max(mx - 1, 0):mx + 1] = 0.0
    # subtle vertical grime streaks
    streak = value_noise(rng, H, W, 2, 96)[..., None]
    base *= 0.88 + 0.12 * streak
    return base, emit[::2, ::2]


def asphalt(rng, h, w, tone=0.1):
    n = fbm(rng, h, w, 6, 5)[..., None]
    fine = rng.random((h, w, 1)) * 0.035
    img = np.empty((h, w, 3), np.float32)
    img[:] = _c((tone, tone, tone * 1.04)) * (0.75 + 0.5 * n) + fine
    patches = (fbm(rng, h, w, 3, 3) > 0.62)[..., None]
    return np.where(patches, img * 0.8, img)


def _paint(img, mask, color, rng, wear=0.25):
    worn = rng.random(mask.shape) > wear * rng.random(mask.shape)
    m = (mask & worn)[..., None]
    return np.where(m, _c(color) * (0.85 + 0.15 * rng.random((*mask.shape, 1))), img)


def road_texture():
    """14 m wide x 40 m long carriageway (u across, v along)."""
    rng = _rng(21)
    h, w = 1024, 256
    img = asphalt(rng, h, w)
    ppm_u, ppm_v = w / 14.0, h / 40.0
    u = (np.arange(w) + 0.5) / ppm_u - 7.0
    v = (np.arange(h) + 0.5) / ppm_v
    U, V = np.meshgrid(u, v)
    edge = (np.abs(np.abs(U) - 6.6) < 0.09)
    center = (np.abs(np.abs(U) - 0.14) < 0.07)
    dash = (np.abs(np.abs(U) - 3.5) < 0.07) & ((V % 10.0) < 4.0)
    img = _paint(img, edge | dash, (0.85, 0.85, 0.8), rng)
    img = _paint(img, center, (0.85, 0.62, 0.1), rng)
    return img


def intersection_texture():
    """20 m x 20 m junction with zebra crossings on all four approaches."""
    rng = _rng(22)
    s = 512
    img = asphalt(rng, s, s)
    ppm = s / 20.0
    c = (np.arange(s) + 0.5) / ppm - 10.0
    X, Y = np.meshgrid(c, c)
    zebra_y = (np.abs(Y) > 7.4) & (np.abs(Y) < 9.8) & (np.abs(X) < 6.8) & (((X + 7.0) % 1.2) < 0.6)
    zebra_x = (np.abs(X) > 7.4) & (np.abs(X) < 9.8) & (np.abs(Y) < 6.8) & (((Y + 7.0) % 1.2) < 0.6)
    stop = ((np.abs(np.abs(Y) - 7.1) < 0.12) & (np.abs(X) < 6.8)) | ((np.abs(np.abs(X) - 7.1) < 0.12) & (np.abs(Y) < 6.8))
    return _paint(img, zebra_x | zebra_y | stop, (0.86, 0.86, 0.82), rng, 0.35)


def paving_texture(seed, tile_px, color, joint=0.55, size=256, jitter=0.12):
    rng = _rng(seed)
    img = np.empty((size, size, 3), np.float32)
    n = fbm(rng, size, size, 4, 4)[..., None]
    img[:] = _c(color) * (0.85 + 0.25 * n)
    tiles = size // tile_px
    tone = 1.0 + (rng.random((tiles, tiles)) - 0.5) * 2 * jitter
    img *= np.kron(tone, np.ones((tile_px, tile_px)))[..., None]
    yy, xx = np.mgrid[0:size, 0:size]
    j = ((yy % tile_px) < 2) | ((xx % tile_px) < 2)
    img[j] *= joint
    return img


def roof_texture():
    rng = _rng(31)
    s = 256
    n = fbm(rng, s, s, 5, 5)[..., None]
    grit = rng.random((s, s, 1)) * 0.08
    img = np.empty((s, s, 3), np.float32)
    img[:] = _c((0.2, 0.2, 0.205)) * (0.75 + 0.5 * n) + grit
    return img


def helipad_texture():
    rng = _rng(32)
    s = 512
    img = asphalt(rng, s, s, 0.13)
    c = (np.arange(s) + 0.5) / s * 15.0 - 7.5
    X, Y = np.meshgrid(c, c)
    R = np.sqrt(X * X + Y * Y)
    ring = (np.abs(R - 6.2) < 0.3)
    edge = (np.abs(R - 7.2) < 0.12)
    h_bar = (np.abs(X) < 2.0) & (np.abs(Y) < 0.35)
    h_legs = (np.abs(np.abs(X) - 1.8) < 0.35) & (np.abs(Y) < 3.0)
    img = _paint(img, ring | edge, (0.95, 0.72, 0.1), rng, 0.2)
    return _paint(img, h_bar | h_legs, (0.92, 0.92, 0.9), rng, 0.2)


def ad_texture():
    """Abstract neon billboard artwork (no text) for the destructible sign."""
    rng = _rng(41)
    h, w = 128, 320
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = xx / w
    img = np.empty((h, w, 3), np.float32)
    img[:] = (_c((0.35, 0.02, 0.35)) * (1 - t)[..., None] + _c((0.0, 0.3, 0.55)) * t[..., None])
    for cx, cy, r, col in ((70, 64, 44, (1.0, 0.45, 0.1)), (70, 64, 30, (0.1, 0.02, 0.1))):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        img[d < r] = _c(col)
    for i, (y0, length) in enumerate(((84, 170), (64, 120), (44, 150))):
        img[y0:y0 + 10, 140:140 + length] = _c((0.95, 0.95, 1.0)) if i == 0 else _c((0.3, 0.95, 1.0))
    img[4:8, 4:w - 4] = _c((1.0, 0.8, 0.2))
    img[h - 8:h - 4, 4:w - 4] = _c((1.0, 0.8, 0.2))
    img *= (0.92 + 0.08 * rng.random((h, w, 1)))
    return img


def house_wall_texture():
    """One 8 m x 4 m wall: stucco with two windows and a door."""
    rng = _rng(51)
    h, w = 128, 256
    ppm = w / 8.0
    n = fbm(rng, h, w, 4, 4)[..., None]
    img = np.empty((h, w, 3), np.float32)
    img[:] = _c((0.8, 0.72, 0.58)) * (0.85 + 0.25 * n)
    img[: int(0.5 * ppm)] = _c((0.45, 0.42, 0.38)) * (0.9 + 0.2 * n[: int(0.5 * ppm)])  # plinth
    emit = np.zeros_like(img)

    def rect(x0, x1, y0, y1, col):
        img[int(y0 * ppm):int(y1 * ppm), int(x0 * ppm):int(x1 * ppm)] = _c(col)

    for x in (1.0, 5.6):
        rect(x - 0.12, x + 1.52, 1.18, 3.12, (0.92, 0.9, 0.86))
        rect(x, x + 1.4, 1.3, 3.0, (0.08, 0.09, 0.11))
        rect(x + 0.67, x + 0.73, 1.3, 3.0, (0.92, 0.9, 0.86))
    rect(3.35, 4.65, 0.0, 2.6, (0.3, 0.16, 0.08))
    rect(3.95, 4.05, 0.0, 2.6, (0.2, 0.1, 0.05))
    lit = int(1.3 * ppm), int(3.0 * ppm), int(5.6 * ppm), int(7.0 * ppm)
    emit[lit[0]:lit[1], lit[2]:lit[3]] = _c((1.0, 0.75, 0.4)) * 0.8
    img[lit[0]:lit[1], lit[2]:lit[3]] = _c((0.9, 0.7, 0.42))
    return img, emit


def skyline_texture():
    rng = _rng(61)
    s = 256
    base = np.empty((s, s, 3), np.float32)
    base[:] = _c((0.07, 0.08, 0.1)) * (0.8 + 0.4 * fbm(rng, s, s, 4, 3)[..., None])
    emit = np.zeros((s, s, 3), np.float32)
    for r in range(32):
        for c in range(16):
            y0, x0 = r * 8 + 2, c * 16 + 3
            lit = rng.random() < 0.3
            col = _c(LIGHTS["mixed"][rng.integers(3)]) * rng.uniform(0.5, 1.0) if lit else _c((0.1, 0.12, 0.15))
            base[y0:y0 + 5, x0:x0 + 10] = col * (0.8 if lit else 1.0)
            if lit:
                emit[y0:y0 + 5, x0:x0 + 10] = col
    return base, emit


# ------------------------------------------------------------------ image cache per scene

_ARRAYS = {}


def _array(name, source):
    if name not in _ARRAYS:
        _ARRAYS[name] = source() if callable(source) else source
    return _ARRAYS[name]


def image(name, source):
    """Blender image for ``name``; ``source`` is an array or a zero-argument generator (cached)."""
    import bpy

    img = bpy.data.images.get(name)
    if img is None:
        img = image_from_array(name, _array(name, source))
    return img


def facade_images(style):
    if f"Facade_{style}" not in _ARRAYS:
        b, e = facade(style)
        _ARRAYS[f"Facade_{style}"], _ARRAYS[f"Facade_{style}_Emit"] = b, e
    return image(f"Facade_{style}", None), image(f"Facade_{style}_Emit", None)
