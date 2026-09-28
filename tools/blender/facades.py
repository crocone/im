"""PBR facade texture sets (albedo, normal, ORM, emission) for the six facade styles.

One texture covers 8 window bays (4 m) x 8 floors (3.5 m) = 32 m x 28 m (``textures.FACADE_SPAN``)
and tiles in both directions. Depth without geometry: window reveals, frames, mullions, sills,
masonry joints and cladding ribs live in a height field that becomes the normal map and the
ambient occlusion; glass gets low roughness and a metallic tint so windows pick up the sky from
the environment map. Lit windows (warm / cool interiors, blinds, ceiling lights) go to emission.

Arrays are float32 with row 0 at the bottom (Blender's image layout). Deterministic (seeded).
"""
import numpy as np

from pbr import _smooth, _to_srgb, normal_map
from textures import LIGHTS, fbm, value_noise

SIZE = 1024
CELLS = 8  # bays across, floors up


def _c(rgb):
    return np.array(rgb, np.float32)


STYLES = {
    # punched windows in a stone grid
    "office": dict(seed=11, wall="stone", wall_color=(0.55, 0.53, 0.49), wall_rough=0.78,
                   windows=[(0.12, 0.88, 0.27, 0.9)], mull_v=[0.5], mull_h=[0.74], depth=1.0, frame=(0.16, 0.17, 0.18),
                   glass=(0.13, 0.17, 0.21), glass_metal=0.55, sill=True, lit=0.22, light="warm"),
    # flush curtain wall of mirror glass with aluminium mullions and dark spandrels
    "glass": dict(seed=12, wall="spandrel", wall_color=(0.1, 0.115, 0.13), wall_rough=0.2, wall_metal=0.6,
                  windows=[(0.0, 1.0, 0.16, 1.0)], mull_v=[0.0, 0.5], mull_h=[0.62], depth=0.35,
                  frame=(0.5, 0.52, 0.55), glass=(0.3, 0.38, 0.46), glass_metal=0.88, flush=True, lit=0.12,
                  light="cool", tint=0.12),
    # continuous ribbon windows between concrete spandrel bands
    "band": dict(seed=13, wall="concrete", wall_color=(0.66, 0.64, 0.6), wall_rough=0.85,
                 windows=[(0.0, 1.0, 0.4, 0.94)], mull_v=[0.0, 0.333, 0.667], mull_h=[], depth=0.8,
                 frame=(0.13, 0.14, 0.15), glass=(0.14, 0.19, 0.24), glass_metal=0.6, lit=0.3, light="warm"),
    # brick with stone surrounds, sills and double-hung sashes
    "brick": dict(seed=14, wall="brick", wall_color=(0.38, 0.17, 0.1), wall_rough=0.9,
                  windows=[(0.13, 0.4, 0.28, 0.84), (0.6, 0.87, 0.28, 0.84)], mull_v=[], mull_h=[0.56], depth=1.0,
                  frame=(0.82, 0.8, 0.74), frame_metal=0.0, glass=(0.07, 0.08, 0.09), glass_metal=0.5,
                  surround=(0.66, 0.62, 0.55), sill=True, lit=0.35, light="warm"),
    # corrugated cladding with high strip windows
    "metal": dict(seed=15, wall="ribbed", wall_color=(0.3, 0.33, 0.36), wall_rough=0.45, wall_metal=0.75,
                  windows=[(0.04, 0.96, 0.55, 0.86)], rows=(1, 2), mull_v=[0.25, 0.5, 0.75], mull_h=[], depth=0.7,
                  frame=(0.1, 0.11, 0.12), glass=(0.12, 0.15, 0.17), glass_metal=0.55, lit=0.25, light="cool"),
    # rendered residential slab: windows plus balcony doors, curtains
    "residential": dict(seed=16, wall="render", wall_color=(0.72, 0.65, 0.54), wall_rough=0.88,
                        windows=[(0.1, 0.38, 0.32, 0.84), (0.56, 0.84, 0.03, 0.84)], mull_v=[], mull_h=[0.62],
                        depth=0.9, frame=(0.88, 0.87, 0.84), frame_metal=0.0, glass=(0.07, 0.08, 0.1),
                        glass_metal=0.5, surround=(0.85, 0.83, 0.79), sill=True, curtains=True, lit=0.38,
                        light="warm"),
}


def _blur(a, r):
    """Separable box blur with wrap-around (keeps the texture tileable)."""
    out = a.copy()
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for k in range(-r, r + 1):
            acc += np.roll(out, k, axis=axis)
        out = acc / (2 * r + 1)
    return out


def _cells(rng, rows, cols):
    return rng.random((rows, cols)).astype(np.float32)


def wall_layer(kind, rng, S):
    """Height, albedo tint, roughness and metal of the bare wall."""
    H = W = SIZE
    y, x = np.mgrid[0:H, 0:W]
    n_low = fbm(rng, H, W, 6, 4).astype(np.float32)
    n_fine = value_noise(rng, H, W, 128, 128).astype(np.float32)
    h = np.zeros((H, W), np.float32)
    tint = np.ones((H, W), np.float32)
    if kind == "stone":
        bw, bh = 32, 16
        row = y // bh
        xo = (x + (row % 2) * (bw // 2)) % W
        tab = _cells(rng, H // bh, W // bw)
        tone = tab[row, xo // bw]
        joint = ((xo % bw) < 1) | ((y % bh) < 1)
        h = 0.25 * (1.0 - joint) + 0.05 * n_fine
        tint = 0.9 + 0.16 * tone + 0.1 * (n_low - 0.5)
        tint = np.where(joint, tint * 0.72, tint)
    elif kind == "concrete":
        joint = ((x % 64) < 1) | ((y % 128) < 2)
        ties = (((x + 8) % 16) < 2) & (((y + 12) % 32) < 2)
        h = 0.2 * (1.0 - joint) - 0.15 * ties + 0.06 * n_fine
        tint = 0.92 + 0.14 * (n_low - 0.5) + 0.06 * (n_fine - 0.5)
        tint = np.where(joint | ties, tint * 0.75, tint)
    elif kind == "brick":
        ch, bw = 4, 8
        row = y // ch
        xo = (x + (row % 2) * (bw // 2)) % W
        tab = _cells(rng, H // ch, W // bw)
        tone = tab[row, xo // bw]
        mortar = ((xo % bw) < 1) | ((y % ch) < 1)
        h = 0.3 * (1.0 - mortar) + 0.04 * n_fine
        burnt = tone > 0.93
        tint = 0.82 + 0.3 * tone + 0.12 * (n_low - 0.5)
        tint = np.where(burnt, tint * 0.6, tint)
        tint = np.where(mortar, 1.7, tint)  # light mortar lines
    elif kind == "ribbed":
        rib = 0.5 + 0.5 * np.cos((x % 8) / 8.0 * 2 * np.pi)
        seam = ((x % 128) < 2) | ((y % 256) < 2)
        h = 0.45 * rib - 0.3 * seam
        tint = (0.88 + 0.12 * rib) * (0.95 + 0.1 * (n_low - 0.5))
    elif kind == "render":
        h = 0.12 * n_fine + 0.08 * value_noise(rng, H, W, 256, 256).astype(np.float32)
        tint = 0.93 + 0.12 * (n_low - 0.5) + 0.04 * (n_fine - 0.5)
    elif kind == "spandrel":
        h = np.zeros((H, W), np.float32)
        tint = 0.95 + 0.1 * (n_low - 0.5)
    rough = np.full((H, W), S["wall_rough"], np.float32) + (n_low - 0.5) * 0.12
    metal = np.full((H, W), S.get("wall_metal", 0.0), np.float32)
    return h.astype(np.float32), tint.astype(np.float32), rough, metal


def facade_set(style):
    """Return dict(albedo, normal, orm, emit) arrays for ``style``."""
    S = STYLES[style]
    rng = np.random.default_rng(S["seed"])
    H = W = SIZE
    cw = ch = SIZE // CELLS
    h, tint, rough, metal = wall_layer(S["wall"], rng, S)
    alb = _c(S["wall_color"])[None, None, :] * tint[..., None]
    emit = np.zeros((H, W, 3), np.float32)
    grime = np.zeros((H, W), np.float32)
    lights = LIGHTS[S["light"]]
    rows = S.get("rows", range(CELLS))
    frame_col = _c(S["frame"])
    frame_metal = S.get("frame_metal", 0.85)
    depth = S["depth"]
    fw = 3  # frame width in px (~10 cm)
    for r in range(CELLS):
        if S["wall"] == "spandrel" or S["wall"] == "concrete":
            # floor slab line
            y0 = r * ch
            h[y0:y0 + 2, :] -= 0.3
        for c in range(CELLS):
            if r not in rows:
                continue
            for wi, (fx0, fx1, fy0, fy1) in enumerate(S["windows"]):
                x0, x1 = c * cw + int(fx0 * cw), c * cw + int(fx1 * cw)
                y0, y1 = r * ch + int(fy0 * ch), r * ch + int(fy1 * ch)
                x1 = min(x1, W)
                y1 = min(y1, H)
                wy, wx = np.mgrid[y0:y1, x0:x1]
                # distance to the window edge (px); ribbon / curtain windows continue across bays
                dx = np.minimum(wx - x0, x1 - 1 - wx).astype(np.float32)
                dy = np.minimum(wy - y0, y1 - 1 - wy).astype(np.float32)
                if fx0 <= 0.0 and fx1 >= 1.0:
                    dx = np.full_like(dx, 99.0)
                d = np.minimum(dx, dy)
                if "surround" in S:
                    sx0, sx1, sy0, sy1 = max(x0 - 4, 0), x1 + 4, max(y0 - 3, 0), y1 + 5
                    h[sy0:sy1, sx0:sx1] = np.maximum(h[sy0:sy1, sx0:sx1], 0.45)
                    alb[sy0:sy1, sx0:sx1] = _c(S["surround"]) * (0.9 + 0.1 * rng.random())
                    rough[sy0:sy1, sx0:sx1] = 0.8
                    metal[sy0:sy1, sx0:sx1] = 0.0
                if S.get("sill") and y0 >= 6:
                    sx0, sx1, sy0, sy1 = max(x0 - 6, 0), min(x1 + 6, W), y0 - 5, y0
                    h[sy0:sy1, sx0:sx1] = 0.8
                    alb[sy0:sy1, sx0:sx1] = _c(S.get("surround", S["wall_color"])) * 1.05
                    alb[sy0 - 1:sy0, sx0:sx1] *= 0.6
                    # rain streaks running down from the sill
                    run = rng.uniform(0.3, 1.0)
                    ya = max(sy0 - int(ch * rng.uniform(0.35, 0.9)), 0)
                    if sy0 - ya > 2:
                        fall = np.linspace(0.0, 1.0, sy0 - ya, dtype=np.float32)[:, None]
                        wob = value_noise(rng, sy0 - ya, sx1 - sx0, 2, 8).astype(np.float32)
                        grime[ya:sy0, sx0:sx1] += fall * run * (0.4 + 0.6 * wob)
                # reveal -> frame -> glass
                reveal = _smooth(0.0, 2.0, d)
                prof = -depth * reveal
                inner = d >= fw + 1
                prof = np.where((d >= 2) & ~inner, -depth * 0.55, prof)
                prof = np.where(inner, -depth * 0.9, prof)
                if S.get("flush"):
                    prof = np.where(inner, -depth, -depth * 0.2 * reveal)
                h[y0:y1, x0:x1] = prof
                is_frame = (d >= 1) & ~inner
                gl_tint = _c(S["glass"]) * (1.0 + S.get("tint", 0.08) * (rng.random() - 0.5) * 2)
                grad = np.linspace(0.85, 1.2, y1 - y0, dtype=np.float32)[:, None]
                glass = gl_tint[None, None, :] * grad[..., None]
                g_rough = 0.05 + 0.04 * rng.random()
                lit = rng.random() < S["lit"]
                interior = np.zeros((y1 - y0, x1 - x0, 3), np.float32)
                if lit:
                    col = _c(lights[rng.integers(len(lights))]) * rng.uniform(0.55, 1.0)
                    yy = (np.arange(y1 - y0, dtype=np.float32) / max(y1 - y0 - 1, 1))[:, None]
                    xx = (np.arange(x1 - x0, dtype=np.float32) / max(x1 - x0 - 1, 1))[None, :]
                    glow = 0.55 + 0.45 * yy + 0.35 * np.exp(-((xx - rng.uniform(0.2, 0.8)) ** 2) / 0.05) * yy
                    if rng.random() < 0.35:  # blinds
                        glow = glow * (0.65 + 0.35 * ((np.arange(y1 - y0)[:, None] // 3) % 2))
                    interior = col[None, None, :] * glow[..., None]
                    emit[y0:y1, x0:x1] = np.where(inner[..., None], interior, 0.0)
                    glass = glass * 0.4 + interior * 0.55
                elif S.get("curtains") and rng.random() < 0.45:
                    cur = _c((rng.uniform(0.3, 0.6), rng.uniform(0.2, 0.45), rng.uniform(0.15, 0.35)))
                    folds = 0.8 + 0.2 * np.sin(np.arange(x1 - x0) * 0.9)[None, :, None]
                    glass = glass * 0.5 + cur * folds * 0.35
                alb[y0:y1, x0:x1] = np.where(is_frame[..., None], frame_col, np.where(inner[..., None], glass,
                                                                                       alb[y0:y1, x0:x1] * 0.7))
                rough[y0:y1, x0:x1] = np.where(is_frame, 0.35, np.where(inner, g_rough, rough[y0:y1, x0:x1]))
                metal[y0:y1, x0:x1] = np.where(is_frame, frame_metal, np.where(inner, S["glass_metal"],
                                                                               metal[y0:y1, x0:x1]))
                # mullions / transoms (raised bars inside the glazing)
                for m in S["mull_v"]:
                    mx = c * cw + int(m * cw)
                    if x0 <= mx < x1 or (m == 0.0 and fx0 <= 0.0):
                        lo, hi = max(mx - 2, 0), min(mx + 2, W)
                        h[y0:y1, lo:hi] = -depth * (0.35 if not S.get("flush") else -0.25)
                        alb[y0:y1, lo:hi] = frame_col
                        rough[y0:y1, lo:hi] = 0.35
                        metal[y0:y1, lo:hi] = frame_metal
                        emit[y0:y1, lo:hi] = 0.0
                for m in S["mull_h"]:
                    my = r * ch + int(m * ch)
                    if y0 <= my < y1:
                        h[my - 1:my + 2, x0:x1] = -depth * (0.35 if not S.get("flush") else -0.25)
                        alb[my - 1:my + 2, x0:x1] = frame_col
                        rough[my - 1:my + 2, x0:x1] = 0.35
                        metal[my - 1:my + 2, x0:x1] = frame_metal
                        emit[my - 1:my + 2, x0:x1] = 0.0
    if S["wall"] == "spandrel":
        # curtain wall: horizontal mullion cap at every floor line too
        for r in range(CELLS):
            y0 = r * ch
            h[y0:y0 + 3, :] = 0.3
            alb[y0:y0 + 3, :] = frame_col
            rough[y0:y0 + 3, :] = 0.35
            metal[y0:y0 + 3, :] = frame_metal
    # weathering: soft dirt, darker base of every floor band, rain streak grime
    dirt = fbm(rng, H, W, 4, 4).astype(np.float32)
    grime = np.clip(grime + 0.35 * _smooth(0.55, 0.85, dirt), 0.0, 1.0)
    streaks = value_noise(rng, H, W, 3, 128).astype(np.float32)
    alb *= (1.0 - 0.28 * grime[..., None]) * (0.9 + 0.1 * streaks[..., None])
    rough = np.clip(rough + 0.08 * grime, 0.03, 1.0)
    # cavity occlusion from the height field
    cav = np.clip(_blur(h, 3) - h, 0.0, 1.0)
    ao = np.clip(1.0 - cav * 1.1, 0.35, 1.0) * (1.0 - 0.15 * grime)
    nrm = normal_map(h, 3.5)
    orm = np.dstack([ao, rough, np.clip(metal, 0, 1)]).astype(np.float32)
    orm = orm.reshape(H // 2, 2, W // 2, 2, 3).mean(axis=(1, 3))
    emit = emit.reshape(H // 2, 2, W // 2, 2, 3).mean(axis=(1, 3))
    return {"albedo": _to_srgb(alb).astype(np.float32), "normal": nrm, "orm": orm.astype(np.float32),
            "emit": _to_srgb(emit).astype(np.float32)}


_SETS = {}


def facade_maps(style):
    if style not in _SETS:
        _SETS[style] = facade_set(style)
    return _SETS[style]


# --------------------------------------------------------------------------- roof, concrete, metal, storefront


def _pack(alb, h, ao, rough, metal, strength, half=True):
    nrm = normal_map(h, strength)
    orm = np.dstack([ao, rough, metal]).astype(np.float32)
    if half:
        hh, ww = orm.shape[:2]
        orm = orm.reshape(hh // 2, 2, ww // 2, 2, 3).mean(axis=(1, 3))
    return {"albedo": _to_srgb(np.clip(alb, 0, 1)).astype(np.float32), "normal": nrm, "orm": orm.astype(np.float32)}


def roof_set(size=1024):
    """Bitumen membrane roof, one tile = 32 m: 1 m rolls with lapped seams, repair patches, ponding stains."""
    rng = np.random.default_rng(31)
    H = W = size
    y, x = np.mgrid[0:H, 0:W]
    low = fbm(rng, H, W, 3, 4).astype(np.float32)
    mid = fbm(rng, H, W, 16, 3).astype(np.float32)
    grit = rng.random((H, W)).astype(np.float32)
    roll = x // 32
    lap = (x % 32) < 3
    seam = (x % 32) == 3
    # staggered end laps inside every roll
    offs = rng.integers(0, 320, W // 32 + 1)
    end = ((y + offs[roll]) % 320) < 2
    h = 0.15 * lap + 0.25 * seam + 0.2 * end + 0.05 * (grit - 0.5) + 0.12 * (mid - 0.5)
    tone = rng.uniform(0.9, 1.1, W // 32 + 1).astype(np.float32)[roll]
    base = _c((0.15, 0.15, 0.155))[None, None, :]
    alb = base * (tone * (0.82 + 0.35 * low) + 0.1 * (grit - 0.5))[..., None]
    alb = np.where((lap | seam)[..., None], alb * 0.8, alb)
    rough = 0.9 - 0.05 * mid
    # ponding stains: darker, smoother rings of dried water
    pond = _smooth(0.62, 0.7, fbm(rng, H, W, 5, 3).astype(np.float32))
    rim = pond * (1 - _smooth(0.7, 0.76, fbm(rng, H, W, 5, 3).astype(np.float32)))
    alb *= (1.0 - 0.18 * pond[..., None]) * (1.0 + 0.25 * rim[..., None])
    rough = rough - 0.35 * pond
    # repair patches
    for _ in range(14):
        px, py = rng.integers(0, W - 90), rng.integers(0, H - 90)
        pw, ph = rng.integers(30, 90), rng.integers(30, 90)
        sl = (slice(py, py + ph), slice(px, px + pw))
        alb[sl] = alb[sl] * rng.uniform(0.75, 1.25)
        h[py:py + 2, px:px + pw] += 0.3
        h[py + ph - 2:py + ph, px:px + pw] += 0.3
        h[py:py + ph, px:px + 2] += 0.3
        h[py:py + ph, px + pw - 2:px + pw] += 0.3
    ao = np.clip(1.0 - np.clip(_blur(h, 2) - h, 0, 1) * 2.0, 0.5, 1.0)
    return _pack(alb, h, ao, np.clip(rough, 0.3, 1.0), np.zeros((H, W), np.float32), 2.5)


def concrete_set(size=512, seed=33, color=(0.46, 0.45, 0.42)):
    """Board-formed concrete, one tile = 4 m: formwork joints, tie holes, blotchy curing, fine pores."""
    rng = np.random.default_rng(seed)
    H = W = size
    y, x = np.mgrid[0:H, 0:W]
    low = fbm(rng, H, W, 4, 4).astype(np.float32)
    mid = fbm(rng, H, W, 12, 3).astype(np.float32)
    pores = (rng.random((H, W)) > 0.985).astype(np.float32)
    board = (y % 32) == 0
    joint = ((x % 256) < 2) | ((y % 256) < 2)
    ties = (((x + 64) % 128) < 4) & (((y + 64) % 128) < 4)
    h = -0.35 * joint - 0.12 * board - 0.6 * ties - 0.3 * pores + 0.1 * (mid - 0.5)
    tint = 0.86 + 0.24 * low + 0.06 * (mid - 0.5) - 0.08 * board
    alb = _c(color)[None, None, :] * tint[..., None]
    alb = np.where((joint | ties)[..., None], alb * 0.7, alb)
    streak = value_noise(rng, H, W, 2, 48).astype(np.float32)
    alb *= (0.88 + 0.12 * streak)[..., None]
    ao = np.clip(1.0 - np.clip(_blur(h, 2) - h, 0, 1) * 1.5, 0.45, 1.0)
    rough = 0.88 - 0.08 * mid
    return _pack(alb, h, ao, rough, np.zeros((H, W), np.float32), 2.0, half=False)


def metal_panel_set(size=512, seed=34, color=(0.36, 0.38, 0.41)):
    """Architectural metal cladding, one tile = 6 m: 1.5 m x 3 m panels, reveal joints, brushed streaks."""
    rng = np.random.default_rng(seed)
    H = W = size
    y, x = np.mgrid[0:H, 0:W]
    pw, ph = 128, 256
    col, row = x // pw, y // ph
    tone = rng.uniform(0.9, 1.1, (H // ph + 1, W // pw + 1)).astype(np.float32)[row, col]
    dx = np.minimum(x % pw, pw - 1 - x % pw)
    dy = np.minimum(y % ph, ph - 1 - y % ph)
    d = np.minimum(dx, dy).astype(np.float32)
    h = _smooth(0.0, 3.0, d) * 0.6
    streak = value_noise(rng, H, W, 256, 4).astype(np.float32)
    low = fbm(rng, H, W, 4, 3).astype(np.float32)
    alb = _c(color)[None, None, :] * (tone * (0.92 + 0.12 * low) + 0.05 * (streak - 0.5))[..., None]
    alb = np.where((d < 2)[..., None], alb * 0.45, alb)
    rough = 0.38 + 0.1 * (streak - 0.5) + 0.1 * (low - 0.5)
    metal = np.full((H, W), 0.85, np.float32)
    ao = np.clip(0.55 + 0.45 * _smooth(0.0, 4.0, d), 0.0, 1.0)
    return _pack(alb, h, ao, rough, metal, 2.0, half=False)


def storefront_set(w=1024, hgt=256):
    """Ground-floor retail band, one tile = 32 m x 5.6 m: four shops with glazing, doors, lit sign fascias."""
    rng = np.random.default_rng(35)
    H, W = hgt, w
    ppm_x, ppm_y = W / 32.0, H / 5.6
    y, x = np.mgrid[0:H, 0:W]
    X, Y = (x + 0.5) / ppm_x, (y + 0.5) / ppm_y
    low = fbm(rng, H, W, 4, 4).astype(np.float32)
    stone = _c((0.5, 0.48, 0.44))
    alb = np.broadcast_to(stone, (H, W, 3)) * (0.88 + 0.2 * low)[..., None]
    alb = alb.astype(np.float32)
    h = np.zeros((H, W), np.float32)
    rough = np.full((H, W), 0.75, np.float32)
    metal = np.zeros((H, W), np.float32)
    emit = np.zeros((H, W, 3), np.float32)
    frame = _c((0.08, 0.085, 0.09))
    sign_cols = [(1.0, 0.25, 0.1), (0.1, 0.8, 1.0), (1.0, 0.8, 0.2), (0.9, 0.2, 0.7), (0.3, 1.0, 0.4), (1.0, 1.0, 0.95)]
    for shop in range(4):
        sx0 = shop * 8.0 + 0.35
        sx1 = sx0 + 7.3
        inside = (X > sx0) & (X < sx1)
        # shop window with a transom and a door at one end
        glaze = inside & (Y > 0.35) & (Y < 3.5)
        dxe = np.minimum(X - sx0, sx1 - X) * ppm_x
        dye = np.minimum(Y - 0.35, 3.5 - Y) * ppm_y
        d = np.minimum(dxe, dye)
        h = np.where(glaze, -0.9 * _smooth(0.0, 2.0, d), h)
        fr = glaze & (d < 4)
        door_x = sx0 + (0.4 if rng.random() < 0.5 else 5.7)
        door = inside & (X > door_x) & (X < door_x + 1.2) & (Y > 0.02) & (Y < 2.6)
        mull = glaze & ((np.abs(Y - 2.8) * ppm_y < 1.5) | (np.abs(((X - sx0) % 1.85)) * ppm_x < 1.5))
        lit = rng.random() < 0.65
        col = _c(LIGHTS["warm" if rng.random() < 0.6 else "cool"][rng.integers(3)]) * rng.uniform(0.4, 0.75)
        yy = np.clip((Y - 0.35) / 3.15, 0, 1)
        # interior depth cues: dark shelving silhouettes against a brighter back wall / ceiling
        shelves = (np.sin((X - sx0) * 5.3 + shop) > 0.6) & (Y < 2.0) & (Y > 0.6)
        shade = (0.35 + 0.65 * yy) * np.where(shelves, 0.45, 1.0)
        interior = col[None, None, :] * shade[..., None] if lit else np.broadcast_to(_c((0.04, 0.05, 0.06)), (H, W, 3))
        glass = _c((0.1, 0.13, 0.16))[None, None, :] + (interior * 0.6 if lit else 0.0)
        alb = np.where(glaze[..., None], glass, alb)
        rough = np.where(glaze, 0.06, rough)
        metal = np.where(glaze, 0.5, metal)
        if lit:
            emit = np.where((glaze & ~fr & ~mull)[..., None], interior, emit)
        for m in (fr | mull, door & ((np.minimum(X - door_x, door_x + 1.2 - X) * ppm_x < 3) | (np.abs(Y - 2.6) * ppm_y < 3))):
            alb = np.where(m[..., None], frame, alb)
            rough = np.where(m, 0.35, rough)
            metal = np.where(m, 0.8, metal)
            emit = np.where(m[..., None], 0.0, emit)
            h = np.where(m, -0.4, h)
        # sign fascia with a glowing panel (abstract blocks, no text)
        fascia = inside & (Y > 3.75) & (Y < 4.75)
        alb = np.where(fascia[..., None], _c((0.03, 0.03, 0.035)), alb)
        h = np.where(fascia, 0.4, h)
        rough = np.where(fascia, 0.4, rough)
        sc = _c(sign_cols[rng.integers(len(sign_cols))])
        cx = sx0 + rng.uniform(1.5, 4.5)
        for k in range(rng.integers(3, 6)):
            bx0 = cx + k * 0.42
            blk = (X > bx0) & (X < bx0 + 0.3) & (Y > 4.0 + 0.1 * (k % 2)) & (Y < 4.5)
            alb = np.where(blk[..., None], sc * 0.8, alb)
            emit = np.where(blk[..., None], sc, emit)
        stripe = inside & (np.abs(Y - 3.82) * ppm_y < 1.2)
        emit = np.where(stripe[..., None], sc * 0.6, emit)
        alb = np.where(stripe[..., None], sc * 0.6, alb)
    # stone cornice and pilasters
    corn = (Y > 4.85) & (Y < 5.25)
    h = np.where(corn, 0.8, h)
    pil = ((X % 8.0) < 0.35) | ((X % 8.0) > 7.65)
    h = np.where(pil & (Y < 4.85), 0.5, h)
    alb *= (0.9 + 0.1 * value_noise(rng, H, W, 2, 64).astype(np.float32))[..., None]
    ao = np.clip(1.0 - np.clip(_blur(h, 2) - h, 0, 1) * 1.2, 0.4, 1.0)
    out = _pack(alb, h, ao, rough, metal, 3.0)
    e = emit.reshape(H // 2, 2, W // 2, 2, 3).mean(axis=(1, 3))
    out["emit"] = _to_srgb(np.clip(e, 0, 1)).astype(np.float32)
    return out


def foliage_set(size=256, seed=36):
    """Leaf clusters for tree canopies: dappled albedo, bumpy normals, occluded gaps between clumps."""
    rng = np.random.default_rng(seed)
    H = W = size
    h = np.zeros((H, W), np.float32)
    hue = np.zeros((H, W), np.float32)
    yy, xx = np.mgrid[0:9, 0:9].astype(np.float32) - 4.0
    for _ in range(1400):
        cx, cy = rng.integers(0, W), rng.integers(0, H)
        r = rng.uniform(2.0, 4.5)
        leaf = np.clip(1.0 - (xx * xx + yy * yy) / (r * r), 0.0, 1.0) ** 0.7
        ys = (np.arange(9) + cy - 4) % H
        xs = (np.arange(9) + cx - 4) % W
        cur = h[np.ix_(ys, xs)]
        top = leaf > cur
        h[np.ix_(ys, xs)] = np.where(top, leaf, cur)
        hue[np.ix_(ys, xs)] = np.where(top, rng.random(), hue[np.ix_(ys, xs)])
    low = fbm(rng, H, W, 4, 3).astype(np.float32)
    base = np.array((0.05, 0.13, 0.035), np.float32)
    alt = np.array((0.11, 0.17, 0.04), np.float32)
    alb = base * (1 - hue[..., None]) + alt * hue[..., None]
    alb = alb * (0.45 + 0.75 * h[..., None]) * (0.85 + 0.3 * low[..., None])
    ao = np.clip(0.35 + 0.65 * h, 0.0, 1.0)
    rough = 0.75 - 0.2 * h
    return _pack(alb, h * 2.0, ao, rough, np.zeros((H, W), np.float32), 1.5, half=False)


def bark_set(size=256, seed=37):
    """Furrowed bark: vertical ridges broken by noise."""
    rng = np.random.default_rng(seed)
    H = W = size
    warp = value_noise(rng, H, W, 16, 4).astype(np.float32)
    x = np.arange(W, dtype=np.float32)[None, :] + warp * 12.0
    ridge = np.abs(np.sin(x / W * np.pi * 12))
    ridge = ridge * (0.6 + 0.4 * value_noise(rng, H, W, 32, 8).astype(np.float32))
    alb = np.array((0.17, 0.11, 0.07), np.float32) * (0.5 + 0.7 * ridge[..., None])
    ao = 0.5 + 0.5 * ridge
    return _pack(alb, ridge * 1.5, ao, 0.9 - 0.1 * ridge, np.zeros((H, W), np.float32), 2.0, half=False)


# --------------------------------------------------------------------------- destructible props


def marble_set(size=512, seed=38):
    """Polished cream marble with turbulent grey veins; one tile = 2 m."""
    rng = np.random.default_rng(seed)
    H = W = size
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    turb = fbm(rng, H, W, 4, 5).astype(np.float32)
    t = np.sin((x / W * 3.0 + y / H * 7.0 + turb * 6.0) * np.pi)
    vein = np.exp(-np.abs(t) * 9.0)
    fine = np.exp(-np.abs(np.sin((x / W * 11 - y / H * 5 + turb * 9) * np.pi)) * 16.0) * 0.5
    cloud = fbm(rng, H, W, 3, 3).astype(np.float32)
    base = _c((0.74, 0.71, 0.65)) * (0.94 + 0.1 * cloud[..., None])
    alb = base * (1.0 - 0.45 * vein[..., None] - 0.2 * fine[..., None])
    h = 0.02 * cloud - 0.05 * vein
    rough = 0.22 + 0.1 * vein + 0.06 * cloud
    return _pack(alb, h, np.ones((H, W), np.float32), rough, np.zeros((H, W), np.float32), 1.0, half=False)


def planks_set(size=512, seed=39):
    """Weathered vertical wooden staves (water tank), one tile = 2 m: 14 staves per tile."""
    rng = np.random.default_rng(seed)
    H = W = size
    y, x = np.mgrid[0:H, 0:W]
    pw = W // 14 + (1 if W % 14 else 0)
    stave = x // pw
    gap = (x % pw) < 2
    tone = rng.uniform(0.75, 1.2, W // pw + 2).astype(np.float32)[stave]
    warp = value_noise(rng, H, W, 64, 16).astype(np.float32)
    grain = 0.5 + 0.5 * np.sin((x * 0.9 + warp * 20.0) * 1.3)
    stain = fbm(rng, H, W, 3, 4).astype(np.float32)
    drip = value_noise(rng, H, W, 2, 64).astype(np.float32)
    alb = _c((0.33, 0.21, 0.12))[None, None, :] * (tone * (0.8 + 0.25 * grain) * (0.75 + 0.4 * stain) * (0.85 + 0.2 * drip))[..., None]
    alb = np.where(gap[..., None], alb * 0.35, alb)
    h = 0.6 * (1.0 - gap) + 0.1 * grain
    ao = np.where(gap, 0.4, 1.0).astype(np.float32)
    rough = 0.85 - 0.1 * grain
    metal = np.zeros((H, W), np.float32)
    # three steel hoops per 2 m tile, with rust bleeding onto the staves below
    band_px = H // 3
    by = y % band_px
    hoop = by < 10
    bevel = np.minimum(by, 9 - by).astype(np.float32)
    rust = np.clip(1.0 - (by - 10) / 40.0, 0, 1) * (by >= 10) * (0.5 + 0.5 * drip)
    alb = alb * (1.0 - 0.35 * rust[..., None]) + _c((0.2, 0.08, 0.03)) * 0.35 * rust[..., None]
    alb = np.where(hoop[..., None], _c((0.06, 0.065, 0.07)) * (0.8 + 0.4 * stain[..., None]), alb)
    h = np.where(hoop, 1.2 + 0.15 * np.clip(bevel, 0, 2), h)
    ao = np.where((by >= 10) & (by < 13), 0.5, ao)
    rough = np.where(hoop, 0.5, rough)
    metal = np.where(hoop, 0.8, metal)
    return _pack(alb, h, ao, rough, metal, 2.5, half=False)


def roof_tiles_set(size=512, seed=40):
    """Overlapping clay roof tiles in staggered rows; one tile of texture = 4 m."""
    rng = np.random.default_rng(seed)
    H = W = size
    y, x = np.mgrid[0:H, 0:W]
    rh, tw = 32, 32
    row = y // rh
    xo = (x + (row % 2) * (tw // 2)) % W
    col = xo // tw
    tone = rng.uniform(0.8, 1.2, (H // rh + 1, W // tw + 1)).astype(np.float32)[row, col]
    fy = (y % rh) / rh
    fx = (xo % tw) / tw
    # each tile: lower edge overlaps the one below (a step), rounded across its width
    h = fy * 0.8 + 0.25 * np.sin(fx * np.pi)
    gap = (xo % tw) < 1
    alb = _c((0.4, 0.14, 0.07))[None, None, :] * (tone * (0.7 + 0.45 * fy))[..., None]
    moss = _smooth(0.6, 0.75, fbm(rng, H, W, 4, 4).astype(np.float32)) * (1 - fy)
    alb = alb * (1 - moss[..., None] * 0.5) + _c((0.1, 0.12, 0.05)) * moss[..., None] * 0.5
    alb = np.where(gap[..., None], alb * 0.5, alb)
    ao = np.clip(0.45 + 0.55 * fy, 0, 1) * np.where(gap, 0.6, 1.0)
    return _pack(alb, h, ao.astype(np.float32), 0.75 - 0.1 * fy, np.zeros((H, W), np.float32), 3.0, half=False)


def house_wall_set():
    """One 8 m x 4 m house wall (u across, v up): render, plinth, two sash windows and a panelled door."""
    rng = np.random.default_rng(51)
    H, W = 512, 1024
    ppm = W / 8.0
    y, x = np.mgrid[0:H, 0:W]
    X, Y = (x + 0.5) / ppm, (y + 0.5) / ppm
    n = fbm(rng, H, W, 4, 4).astype(np.float32)
    fine = value_noise(rng, H, W, 128, 256).astype(np.float32)
    alb = np.broadcast_to(_c((0.8, 0.72, 0.58)), (H, W, 3)) * (0.86 + 0.22 * n + 0.05 * fine)[..., None]
    alb = alb.astype(np.float32)
    h = 0.08 * fine
    rough = np.full((H, W), 0.88, np.float32)
    metal = np.zeros((H, W), np.float32)
    emit = np.zeros((H, W, 3), np.float32)
    plinth = Y < 0.5
    alb = np.where(plinth[..., None], _c((0.42, 0.4, 0.37)) * (0.9 + 0.2 * n[..., None]), alb)
    h = np.where(plinth, 0.3 + 0.1 * fine, h)
    trim = _c((0.93, 0.91, 0.87))

    def region(x0, x1, y0, y1):
        return (X > x0) & (X < x1) & (Y > y0) & (Y < y1)

    for i, wx in enumerate((1.0, 5.6)):
        surround = region(wx - 0.12, wx + 1.52, 1.18, 3.12)
        alb = np.where(surround[..., None], trim, alb)
        h = np.where(surround, 0.25, h)
        rough = np.where(surround, 0.6, rough)
        sill = region(wx - 0.2, wx + 1.6, 1.08, 1.2)
        alb = np.where(sill[..., None], trim * 0.95, alb)
        h = np.where(sill, 0.6, h)
        pane = region(wx, wx + 1.4, 1.3, 3.0)
        d = np.minimum(np.minimum(X - wx, wx + 1.4 - X), np.minimum(Y - 1.3, 3.0 - Y)) * ppm
        lit = i == 1
        glass = _c((0.08, 0.09, 0.11)) if not lit else _c((0.9, 0.7, 0.42))
        alb = np.where(pane[..., None], glass, alb)
        h = np.where(pane, -0.6 * _smooth(0.0, 3.0, d), h)
        rough = np.where(pane, 0.08, rough)
        metal = np.where(pane, 0.4, metal)
        bars = pane & ((np.abs(X - (wx + 0.7)) * ppm < 2) | (np.abs(Y - 2.15) * ppm < 2) | (d < 4))
        alb = np.where(bars[..., None], trim, alb)
        h = np.where(bars, -0.2, h)
        rough = np.where(bars, 0.5, rough)
        metal = np.where(bars, 0.0, metal)
        if lit:
            emit = np.where((pane & ~bars)[..., None], _c((1.0, 0.75, 0.4)) * 0.8, emit)
    door = region(3.35, 4.65, 0.0, 2.6)
    frame = region(3.25, 4.75, 0.0, 2.7) & ~door
    alb = np.where(frame[..., None], trim, alb)
    h = np.where(frame, 0.3, h)
    alb = np.where(door[..., None], _c((0.3, 0.12, 0.06)) * (0.9 + 0.1 * n[..., None]), alb)
    panels = door & ((np.abs(X - 4.0) * ppm > 6) & ((np.abs(Y - 0.8) < 0.5) | (np.abs(Y - 1.95) < 0.45)))
    h = np.where(door, np.where(panels, -0.15, 0.0), h)
    rough = np.where(door, 0.55, rough)
    knob = region(4.42, 4.5, 1.2, 1.28)
    alb = np.where(knob[..., None], _c((0.7, 0.55, 0.25)), alb)
    metal = np.where(knob, 1.0, metal)
    streak = value_noise(rng, H, W, 2, 96).astype(np.float32)
    alb *= (0.9 + 0.1 * streak)[..., None]
    ao = np.clip(1.0 - np.clip(_blur(h, 3) - h, 0, 1) * 1.4, 0.4, 1.0)
    out = _pack(alb, h, ao, rough, metal, 3.0)
    e = emit.reshape(H // 2, 2, W // 2, 2, 3).mean(axis=(1, 3))
    out["emit"] = _to_srgb(np.clip(e, 0, 1)).astype(np.float32)
    return out


def billboard_set():
    """Backlit billboard artwork (abstract energy-drink ad, no text): 6.8 m x 2.9 m."""
    rng = np.random.default_rng(41)
    H, W = 432, 1024
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = x / W, y / H
    bg = _c((0.02, 0.03, 0.12))[None, None, :] * (1 - u[..., None]) + _c((0.35, 0.02, 0.3))[None, None, :] * u[..., None]
    img = bg * (0.8 + 0.4 * v[..., None])
    # radiating rays behind the product
    ang = np.arctan2(v - 0.5, (u - 0.28) * W / H)
    rays = (np.sin(ang * 14) > 0.6) * np.exp(-((u - 0.28) ** 2 + (v - 0.5) ** 2) * 6)
    img += _c((0.25, 0.1, 0.35)) * rays[..., None]
    # product: tilted can with highlights
    cu, cv = (u - 0.28) * W / H, v - 0.48
    ca, sa = np.cos(0.25), np.sin(0.25)
    ru, rv = cu * ca + cv * sa, -cu * sa + cv * ca
    can = (np.abs(ru) < 0.16) & (np.abs(rv) < 0.36)
    cap = (np.abs(ru) < 0.13) & (np.abs(rv - 0.38) < 0.03)
    shade = 0.55 + 0.45 * np.cos((ru / 0.16) * 1.4)
    body = _c((0.05, 0.9, 0.95)) * shade[..., None]
    img = np.where(can[..., None], body, img)
    band = can & (np.abs(rv) < 0.07)
    img = np.where(band[..., None], _c((1.0, 0.85, 0.1)) * shade[..., None], img)
    img = np.where(cap[..., None], _c((0.75, 0.78, 0.8)), img)
    # lightning bolt
    bolt = (np.abs(ru + 0.3 * rv) < 0.035) & (np.abs(rv) < 0.2) & can
    img = np.where(bolt[..., None], _c((1.0, 1.0, 1.0)), img)
    # headline bars (stand-ins for type) and a price badge
    for i, (y0, x0, x1, col) in enumerate(((0.66, 0.5, 0.93, (1.0, 1.0, 1.0)), (0.5, 0.5, 0.82, (0.1, 1.0, 0.95)),
                                           (0.36, 0.5, 0.88, (0.1, 1.0, 0.95)))):
        bar = (u > x0) & (u < x1) & (np.abs(v - y0) < (0.06 if i == 0 else 0.035))
        img = np.where(bar[..., None], _c(col), img)
    badge = ((u - 0.86) * W / H) ** 2 + (v - 0.2) ** 2 < 0.012
    img = np.where(badge[..., None], _c((1.0, 0.3, 0.1)), img)
    border = (u < 0.01) | (u > 0.99) | (v < 0.02) | (v > 0.98)
    img = np.where(border[..., None], _c((1.0, 0.8, 0.2)), img)
    img = np.clip(img * (0.94 + 0.06 * rng.random((H, W, 1))), 0, 1)
    srgb = _to_srgb(img).astype(np.float32)
    return {"albedo": srgb, "emit": srgb}
