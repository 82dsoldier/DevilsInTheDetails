"""SSG Brannock's uniform pieces, worn models skinned to the vanilla skeleton (worn.py): his
maroon beret with the 1-504 flash, and the subdued jump wings over his left breast pocket (the
author's reference photos, 2026-11-24). Vanilla has no beret.

  Beret   a leather band round his head at the brow, then a felt crown that overhangs it and,
          worn the airborne way, drops over his right ear; the front left is stiffened and
          stands up over his left eye, and the flash is sewn there. Fitted to the vanilla
          military cap's head (Clothes\\Ronnie\\MCap.nif: the head 0.20 m across, 0.24 front
          to back, the brow about 1.80 m up). On the HEAD bone, body slot 30 (hair top), as the
          cap is.
  Flash   the 1st Battalion, 504th PIR's: a shield, gold border, blue field, a thin gold bar
          across, and the regiment's crest on it (a blue shield with a gold sword and oak
          leaf, the gold "STRIKE HOLD" scroll under it). Drawn here, not taken from a photo,
          and its own patch (cut to its outline) laid on the stiffened front, over his left eye.
  Wings   subdued (black thread on olive drab cloth) parachutist badge, 6.0 by 3.15 cm, above
          his left breast pocket, shaped to his chest (the vanilla FatiguesM.nif's front,
          measured, CHEST_*), 3 mm off it. On his torso's bones, body slot 55.

    python scripts/make_uniform.py [--install "<Fallout 4>/Data"]

Writes out/uniform/mod/Meshes/DevilsInTheDetails/Uniform/{Beret,Wings}.nif and
Textures/DevilsInTheDetails/Uniform/uniform_{beret,wings}{,_n,_s}.dds. The plugin's armor
(DevilsBeret, DevilsJumpWings; scripts/esp/esp_uniform.py) points at them.
"""
import argparse
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import shapely
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_c130_blockout as c                                    # noqa: E402
import worn                                                       # noqa: E402
from ddsutil import save_dds                                      # noqa: E402
from make_heightmap import out_dir                                # noqa: E402

MOD_PATH = "DevilsInTheDetails/Uniform"
PREFIX = "uniform_"

# --- The beret (metres, his frame: feet at the origin, facing +Y, his right +X) --------------
CENTRE = (0.010, -0.006)              # his head's middle, seen from above (the cap's)
BAND_A, BAND_B = 0.103, 0.123         # the band's half-width and half-length (the cap's, + 4 mm)
BAND_Z, BAND_TILT = 1.792, 0.008      # the band's foot, and how much higher in front than behind
BAND_H = 0.020
# A beret lies tight and flat (the author, 2026-11-24: the first, puffed out all round 20%,
# "looks more like a jester's hat"; data/reference/...Alexander_Woody...jpg). Its crown
# barely overhangs the band (OVERHANG, of the band's size), stands up stiff at the front left
# for the flash (STIFF_UP over the band), dips just behind the flash (BEHIND_AT), slants down
# to the right, and its spare cloth is pulled over and hangs straight down over his right ear
# (RIGHT_OUT more overhang there, RIGHT_DROP below the band's top).
# How far his head reaches above the brow, each 15 degrees round from his right, as a fraction
# of the band's size that way (the cap's, measured): the back of the head bulges out past the
# band, so there the band and crown follow it, HEAD_CLEAR out.
HEAD_REACH = [0.965, 0.929, 0.919, 0.919, 0.851, 0.65, 0.531, 0.613, 0.749, 0.949, 0.949, 0.932,
              0.959, 1.005, 1.05, 1.05, 1.037, 1.056, 1.067, 1.067, 1.053, 1.02, 0.999, 0.995]
HEAD_CLEAR = 0.03
TOP = (-0.005, -0.020, 1.908)
# The crown slants down to his right, from the flash's side (from X_HIGH), as the cloth is pulled
# over to hang on that side (the author, 2026-11-24: the first passes were round on top).
X_HIGH, SLANT = -0.03, 0.22          # the crown's middle: just over his head (the cap's top 1.902)
OVERHANG = 0.04
STIFF_UP = 0.085
CROWN_UP = 0.032                      # the crown's edge over the band's top, elsewhere
BEHIND_AT, BEHIND_DIP = math.radians(170), 0.008
RIGHT_OUT, RIGHT_DROP = 0.09, 0.042
FLASH_AT = math.radians(120)          # around the head from his right: over his left eye
FLASH_W, FLASH_H = 0.044, 0.054
FLASH_UP = 0.008                      # its foot over the band's top
FLASH_LIFT = 0.0015                   # the patch off the felt
FLASH_TEX, FLASH_TEX_FILL = 512, FLASH_W / FLASH_H     # the flash fills this much of its square
STIFF = 0.42                          # radians: how far round the stiffened front reaches
N_AROUND = 96
V_SPAN = 0.22                         # metres of beret, band foot to top, along the texture's v
BERET_TEX = (2048, 512)

# --- The wings ------------------------------------------------------------------------------
CHEST_X = [-0.16, -0.14, -0.12, -0.10, -0.08, -0.06]
CHEST_Z = [1.455, 1.470, 1.485, 1.500, 1.515, 1.530]
CHEST_Y = [                           # his front's y at each (z, x): FatiguesM.nif's, measured
    [0.0731, 0.0891, 0.1050, 0.1131, 0.1177, 0.1223],
    [0.0669, 0.0828, 0.0987, 0.1049, 0.1094, 0.1138],
    [0.0620, 0.0779, 0.0891, 0.0947, 0.0997, 0.1042],
    [0.0568, 0.0728, 0.0783, 0.0839, 0.0896, 0.0946],
    [0.0502, 0.0621, 0.0676, 0.0731, 0.0788, 0.0844],
    [0.0447, 0.0522, 0.0577, 0.0629, 0.0677, 0.0725],
]
# Centred over his left breast pocket, just above its flap (the author, 2026-11-24). The
# pocket, read off the vanilla fatigues' texture (ArmyFatigues_d.dds) through the model's UVs:
# x -0.044 to -0.176 (his left), its flap's top 1.47 m up.
WINGS_AT = (-0.110, 1.490)            # its middle: x (his left is -x) and height
WINGS_W, WINGS_H = 0.060, 0.0315
WINGS_OFF = 0.003
WINGS_TEX = (512, 256)                # powers of two: 512 x 270 crashed the game (2026-11-24)

MAROON = (92, 22, 34)
GOLD = (214, 172, 62)
BLUE = (34, 62, 168)
DARK_BLUE = (22, 40, 120)
OD = (82, 90, 60)
THREAD = (22, 22, 20)
MATERIALS = {"beret": (None, {"double_sided": True}), "flash": (None, {}), "wings": (None, {})}


def _lerp(a, b, t):
    return a + (b - a) * t


def _bez(p0, p1, p2, t):
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2


def _bump(th, at, w):
    return math.exp(-((((th - at + math.pi) % (2 * math.pi)) - math.pi) / w) ** 2)


def beret_column(th):
    """One line of the beret from the band's foot over to the crown's middle, at angle th
    round his head (from his right): (its points, and the band-to-edge curve (a, q1, edge))."""
    cx, cy = CENTRE
    top = np.array(TOP)
    right = max(0.0, math.cos(th)) ** 1.3
    stiff = _bump(th, FLASH_AT, STIFF)
    behind = _bump(th, BEHIND_AT, 0.45) * (1 - stiff)
    f = (math.degrees(th) % 360) / 15
    i0 = int(f) % 24
    reach = _lerp(HEAD_REACH[i0], HEAD_REACH[(i0 + 1) % 24], f - int(f))
    size = max(1.0, reach + HEAD_CLEAR)
    e = np.array([cx + size * BAND_A * math.cos(th), cy + size * BAND_B * math.sin(th)])
    zb = BAND_Z + BAND_TILT * math.sin(th)
    zt = zb + BAND_H
    k = 1.0 + OVERHANG * (1 - stiff) + RIGHT_OUT * right
    ze = zt + CROWN_UP * (1 - stiff) * (1 - right) + STIFF_UP * stiff - BEHIND_DIP * behind - RIGHT_DROP * right
    rel = e - np.array([cx, cy])
    at = lambda r, z: np.array([cx + r * rel[0], cy + r * rel[1], z])
    a, edge = at(1.0, zt), at(k, ze)
    # Band to the crown's edge: straight up where it's stiff; elsewhere out and up; on the
    # right, out over the band and then down over his ear.
    q1 = at(1.0 + (k - 1.0) * (0.5 + 0.6 * right), _lerp(_lerp(zt, ze, 0.6), ze, stiff) + 0.03 * right)
    # The crown's edge to its middle: flat across his head, slanting down to his right; on the
    # right, back up from the hanging cloth first.
    q2 = at(_lerp(0.85 * k, 1.02 * k, right), 0.0)
    q2[2] = top[2] + 0.002 - SLANT * max(0.0, q2[0] - X_HIGH)
    pts = [at(1.0, zb), at(1.0, zb + BAND_H / 2), a]
    pts += [_bez(a, q1, edge, t) for t in np.linspace(0, 1, 11)[1:]]
    pts += [_bez(edge, q2, top, t) for t in np.linspace(0, 1, 13)[1:]]
    return pts, (a, q1, edge)


def beret_grid():
    """Points (around x along), metres, and each column's angle."""
    thetas = np.linspace(-math.pi / 2, 3 * math.pi / 2, N_AROUND + 1)
    return np.array([beret_column(th)[0] for th in thetas]), thetas


def flash_outline():
    """The flash's outline, metres: across (s, to the viewer's right as he faces you) and up
    (h, from its foot): straight sides, then a round bottom the whole width."""
    w2, low = FLASH_W / 2, FLASH_H * 0.30
    pts = [(-w2, FLASH_H), (w2, FLASH_H)]
    for a in np.linspace(0, math.pi, 40):
        pts.append((w2 * math.cos(a), low - low * math.sin(a)))
    return Polygon(pts)


def flash_mesh():
    """The flash as its own patch on the beret's stiffened front (painted into the beret's
    texture, it stretched up over the crown and squashed at its foot; the author, 2026-11-24):
    each point of its outline laid on the beret's band-to-edge curve there, FLASH_LIFT out."""
    poly = flash_outline()
    grid = 0.006
    xs = np.arange(-FLASH_W / 2 - grid, FLASH_W / 2 + grid, grid)
    hs = np.arange(-grid, FLASH_H + grid, grid)
    squares = np.array([box(x, h, x + grid, h + grid) for h in hs for x in xs])
    squares = squares[shapely.intersects(squares, poly)]
    m = c.Mesh()
    index = {}
    th0 = FLASH_AT
    speed = math.hypot(BAND_A * math.sin(th0), BAND_B * math.cos(th0))       # metres per radian
    cx, cy = CENTRE

    def place(sv, h):
        th = th0 + sv / speed
        _, (a, q1, edge) = beret_column(th)
        curve = np.array([_bez(a, q1, edge, t) for t in np.linspace(0, 1, 200)])
        z = a[2] + FLASH_UP + h
        i = int(np.clip(np.searchsorted(curve[:, 2], z), 1, len(curve) - 1))
        f = (z - curve[i - 1, 2]) / max(curve[i, 2] - curve[i - 1, 2], 1e-9)
        p = curve[i - 1] + (curve[i] - curve[i - 1]) * f
        out = np.array([p[0] - cx, p[1] - cy, 0.0])
        out /= np.linalg.norm(out)
        return p + out * FLASH_LIFT, out

    for gc in shapely.constrained_delaunay_triangles(shapely.intersection(squares, poly)):
        for tri in getattr(gc, "geoms", [gc]):
            if tri.is_empty or tri.area < 1e-8:
                continue
            ids = []
            for sv, h in list(tri.exterior.coords)[:3]:
                key = (round(sv, 6), round(h, 6))
                if key not in index:
                    p, n = place(sv, h)
                    uv = ((sv + FLASH_W / 2) / FLASH_W * FLASH_TEX_FILL, 1 - h / FLASH_H)
                    index[key] = m.vert(tuple(p), tuple(n), uv)
                ids.append(index[key])
            if len(set(ids)) == 3:
                m.tri(*ids)
    return m


def tex_flash():
    """The flash's texture: drawn at its own shape's proportions, in the left of a square."""
    size = FLASH_TEX
    w = int(size * FLASH_TEX_FILL)
    img = Image.new("RGB", (size, size), GOLD)
    flash = draw_flash(w, size)
    img.paste(flash, (0, 0), flash)
    return img


def beret_mesh():
    g, thetas = beret_grid()
    n_a, n_v, _ = g.shape
    # v: metres along the beret from the band's foot, the same for every column at each row
    # (the mean), so the texture's rows run round the beret.
    seg = np.linalg.norm(np.diff(g, axis=1), axis=2).mean(axis=0)
    v = np.concatenate([[0.0], np.cumsum(seg)]) / V_SPAN
    m = c.Mesh()
    mid = np.array([CENTRE[0], CENTRE[1], 1.80])
    idx = np.zeros((n_a, n_v), int)
    for i in range(n_a):
        for j in range(n_v):
            p = g[i, j]
            dp_a = g[(i + 1) % (n_a - 1)] [j] - g[i - 1 if i else n_a - 2][j]
            dp_v = g[i, min(j + 1, n_v - 1)] - g[i, max(j - 1, 0)]
            n = np.cross(dp_a, dp_v)
            if np.linalg.norm(n) < 1e-12:
                n = p - mid
            if n @ (p - mid) < 0:
                n = -n
            n /= np.linalg.norm(n)
            idx[i, j] = m.vert(tuple(p), tuple(n), (i / (n_a - 1), float(v[j])))
    for i in range(n_a - 1):
        for j in range(n_v - 1):
            m.quad(idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1])
    return m, thetas, v


def draw_flash(w_px, h_px):
    """The 1-504 flash, w_px x h_px, upright."""
    S = 8
    W, H = w_px * S, h_px * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def shield(inset):
        x0, x1, y0 = inset, W - inset, inset
        # As wide all the way down, then a round bottom across the whole width (the first
        # narrowed to a point; the author, 2026-11-24).
        yb = H * 0.70
        pts = [(x0, y0), (x1, y0)]
        for a in np.linspace(0, math.pi, 40):
            pts.append((W / 2 + (x1 - W / 2) * math.cos(a), yb + (H - inset - yb) * math.sin(a)))
        return pts
    border = W * 0.11
    d.polygon(shield(0), fill=GOLD)
    d.polygon(shield(border), fill=BLUE)
    bar_y = H * 0.40
    d.rectangle([0, bar_y - H * 0.025, W, bar_y + H * 0.025], fill=GOLD)
    d.polygon(shield(0), outline=GOLD, width=int(border))           # the bar stays inside
    # The crest: a blue shield edged in gold, a gold sword with an oak leaf, the scroll.
    cw, ch = W * 0.44, H * 0.48
    cx0, cy0 = (W - cw) / 2, H * 0.18
    crest = [(cx0, cy0), (cx0 + cw, cy0), (cx0 + cw, cy0 + ch * 0.62),
             (W / 2, cy0 + ch), (cx0, cy0 + ch * 0.62)]
    d.polygon(crest, fill=DARK_BLUE, outline=GOLD, width=S * 2)
    d.line([(cx0 + cw * 0.3, cy0 + ch * 0.85), (cx0 + cw * 0.72, cy0 + ch * 0.12)], fill=GOLD, width=S * 3)
    for k in range(5):
        t = 0.25 + k * 0.12
        px, py = _lerp(cx0 + cw * 0.3, cx0 + cw * 0.72, t), _lerp(cy0 + ch * 0.85, cy0 + ch * 0.12, t)
        d.ellipse([px - S * 4, py - S * 2, px + S * 1, py + S * 2], fill=GOLD)
    sy = cy0 + ch + H * 0.02
    d.rounded_rectangle([W * 0.16, sy, W * 0.84, sy + H * 0.11], radius=S * 4, fill=GOLD)
    try:
        font = ImageFont.truetype("arialbd.ttf", int(H * 0.075))
    except OSError:
        font = ImageFont.load_default()
    d.text((W / 2, sy + H * 0.055), "STRIKE HOLD", fill=DARK_BLUE, font=font, anchor="mm")
    return img.resize((w_px, h_px), Image.LANCZOS)


def tex_beret(thetas, v_rows):
    W, H = BERET_TEX
    rng = np.random.default_rng(504)
    felt = rng.normal(0, 1, (H, W))
    felt = np.array(Image.fromarray(((felt - felt.min()) / np.ptp(felt) * 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255 - 0.5
    rgb = np.array(MAROON, np.float32)[None, None, :] * (1 + 0.18 * felt[..., None])
    height = felt * 0.3
    band_px = int(BAND_H / V_SPAN * H)
    rgb[:band_px] = np.array([28, 22, 20], np.float32) * (1 + 0.1 * felt[:band_px, :, None])
    height[:band_px] = 0.1
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    return img, height


def wings_mesh():
    m = c.Mesh()
    cx, cz = WINGS_AT
    xs = np.linspace(cx - WINGS_W / 2, cx + WINGS_W / 2, 7)
    zs = np.linspace(cz - WINGS_H / 2, cz + WINGS_H / 2, 3)
    yi = lambda x, z: _bilinear(x, z)
    idx = {}
    for a, z in enumerate(zs):
        for b, x in enumerate(xs):
            y = yi(x, z)
            n = np.array([-(yi(x + 0.002, z) - yi(x - 0.002, z)) / 0.004, 1.0,
                          -(yi(x, z + 0.002) - yi(x, z - 0.002)) / 0.004])
            n /= np.linalg.norm(n)
            p = np.array([x, y, z]) + n * WINGS_OFF
            idx[a, b] = m.vert(tuple(p), tuple(n), (b / (len(xs) - 1), 1 - a / (len(zs) - 1)))
    for a in range(len(zs) - 1):
        for b in range(len(xs) - 1):
            m.quad(idx[a, b], idx[a, b + 1], idx[a + 1, b + 1], idx[a + 1, b])
    return m


def _bilinear(x, z):
    gx, gz, gy = np.array(CHEST_X), np.array(CHEST_Z), np.array(CHEST_Y)
    i = int(np.clip(np.searchsorted(gx, x) - 1, 0, len(gx) - 2))
    j = int(np.clip(np.searchsorted(gz, z) - 1, 0, len(gz) - 2))
    tx, tz = (x - gx[i]) / (gx[i + 1] - gx[i]), (z - gz[j]) / (gz[j + 1] - gz[j])
    return float((gy[j, i] * (1 - tx) + gy[j, i + 1] * tx) * (1 - tz)
                 + (gy[j + 1, i] * (1 - tx) + gy[j + 1, i + 1] * tx) * tz)


def tex_wings(cloth=OD, thread=THREAD, size=WINGS_TEX):
    """The parachutist badge, black thread on olive drab (the author's reference: the badge's
    own shape, data/reference/5-5-Inch-Army-Jump-Wings...avif, subdued). The canopy in the
    middle, its gores in thread with the cloth between, its lines narrowing to a point below;
    each side, a wing that rises from the canopy's skirt in a round loop, open in the middle,
    and fans its feathers out and down, flaring sideways (not curling up at the tips).
    Other colours (white on black) give the badge's shape as a mask, for the metal pin
    (make_black_hat.py)."""
    W, H = size
    S = 4
    w, h = W * S, H * S
    img = Image.new("RGB", (w, h), cloth)
    d = ImageDraw.Draw(img)
    X = lambda f: f * w                       # the badge's span, 0 to 1 across
    Y = lambda f: f * h                       # 0 to 1 down
    line = max(2, S * 2)
    # The canopy: a dome, its skirt, and gores.
    d.chord([X(0.315), Y(0.0), X(0.685), Y(0.46)], 180, 360, fill=thread)
    d.polygon([(X(0.315), Y(0.23)), (X(0.685), Y(0.23)), (X(0.5), Y(1.0))], fill=thread)
    for k in range(1, 12):
        f = k / 12
        d.line([(X(0.315 + 0.37 * f), Y(0.235)), (X(0.5), Y(0.97))], fill=cloth, width=line)
    for k in range(1, 8):
        f = k / 8
        d.arc([X(0.5 - 0.185 * (1 - f) - 0.0), Y(0.0), X(0.5 + 0.185 * (1 - f)), Y(0.46)], 200, 340,
              fill=cloth, width=line) if False else None
        d.line([(X(0.5 + (f - 0.5) * 0.30), Y(0.03 + 0.18 * abs(f - 0.5) ** 1.5)), (X(0.5 + (f - 0.5) * 0.36), Y(0.225))],
               fill=cloth, width=line)
    d.line([(X(0.315), Y(0.235)), (X(0.685), Y(0.235))], fill=cloth, width=line)
    FC, FRX, FRY = (0.26, 0.40), 0.22, 0.45                # the feathers' fan: its middle, reach
    fan = lambda phi, r=1.0: (FC[0] + FRX * r * math.cos(math.radians(phi)),
                              FC[1] - FRY * r * math.sin(math.radians(phi)))
    for side in (-1, 1):
        sx = lambda f: X(0.5 + side * (f - 0.5))          # mirrored: f < 0.5 is out from the middle
        # The wing: up from the canopy's skirt and round the loop's top, down its outer side to
        # the feathers, whose tips fan out sideways and down round to the shroud lines.
        loop = [(0.335, 0.28), (0.31, 0.13), (0.25, 0.045), (0.17, 0.025), (0.10, 0.06),
                (0.055, 0.15), (0.04, 0.27)]
        n_f = 9
        tips = []
        for k in range(n_f + 1):
            phi = 175 + 90 * k / n_f
            tips.append(fan(phi, 1.0))
            if k < n_f:
                tips.append(fan(phi + 45 / n_f, 0.86))         # the notch between two feathers
        root = [(0.37, 0.74), (0.375, 0.42)]
        d.polygon([(sx(fx), Y(fy)) for fx, fy in loop + tips + root], fill=thread)
        # The loop's open middle.
        d.ellipse([min(sx(0.12), sx(0.29)), Y(0.10), max(sx(0.12), sx(0.29)), Y(0.36)], fill=cloth)
        # The cloth between the feathers, fanning out from under the loop.
        for k in range(1, n_f):
            phi = 175 + 90 * (k + 0.5) / n_f
            (x0, y0), (x1, y1) = fan(phi, 0.45), fan(phi, 0.84)
            d.line([(sx(x0), Y(y0)), (sx(x1), Y(y1))], fill=cloth, width=line)
    img = img.resize((W, H), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    rng = np.random.default_rng(55)
    weave = rng.normal(0, 0.04, (H, W))
    rgb = np.asarray(img, np.float32) * (1 + weave[..., None])
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB"), a.mean(axis=2) * 0.4 + weave


def save_set(tex_dir, name, img, height, shine, smooth):
    pow2 = lambda n: n > 0 and n & (n - 1) == 0
    assert pow2(img.width) and pow2(img.height), f"{name}: {img.size} isn't powers of two (the game crashes)"
    files = []
    f = tex_dir / f"{PREFIX}{name}.dds"
    save_dds(img, f)
    fn = tex_dir / f"{PREFIX}{name}_n.dds"
    save_dds(Image.fromarray(np.clip(c.normal_map(height, 0.15), 0, 255).astype(np.uint8), "RGB"), fn)
    fs = tex_dir / f"{PREFIX}{name}_s.dds"
    Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
    return [f, fn, fs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    pyn = worn.load_pyn()
    out = out_dir("uniform")
    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex = "DevilsInTheDetails\\Uniform"

    beret, thetas, v = beret_mesh()
    img, height = tex_beret(thetas, v)
    files = save_set(tex_dir, "beret", img, height, 0.03, 0.15)
    img.save(out / "beret_texture.png")
    flash = flash_mesh()
    fimg = tex_flash()
    files += save_set(tex_dir, "flash", fimg, np.zeros((FLASH_TEX, FLASH_TEX)), 0.05, 0.2)
    fimg.save(out / "flash_texture.png")
    worn.write_worn(mesh_dir / "Beret.nif", "Beret", {"Beret": ("beret", beret, worn.rigid("HEAD")),
                                                     "Flash": ("flash", flash, worn.rigid("HEAD"))},
                    tex, pyn, MATERIALS, PREFIX)
    files.append(mesh_dir / "Beret.nif")

    wings = wings_mesh()
    img, height = tex_wings()
    files += save_set(tex_dir, "wings", img, height, 0.03, 0.15)
    img.save(out / "wings_texture.png")
    worn.write_worn(mesh_dir / "Wings.nif", "Wings", {"Wings": ("wings", wings, worn.torso_weights)},
                    tex, pyn, MATERIALS, PREFIX)
    files.append(mesh_dir / "Wings.nif")

    vb = np.array(beret.verts)
    print(f"beret: {len(beret.verts)} verts, {len(beret.tris)} tris, x {vb[:, 0].min():.3f}..{vb[:, 0].max():.3f}, "
          f"y {vb[:, 1].min():.3f}..{vb[:, 1].max():.3f}, z {vb[:, 2].min():.3f}..{vb[:, 2].max():.3f}")
    print(f"wings: {len(wings.verts)} verts")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
