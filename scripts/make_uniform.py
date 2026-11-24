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
          and painted into the beret's texture where the stiffened front stands up.
  Wings   subdued (black thread on olive drab cloth) parachutist badge, 8.5 by 3.2 cm, over
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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
TOP_Z = 1.915                         # the crown's top (the cap's is 1.902)
TOP_SHIFT = (0.025, -0.005)           # the crown's top, off the head's middle, to his right
FLASH_AT = math.radians(120)          # around the head from his right: over his left eye
FLASH_W, FLASH_H = 0.044, 0.050
FLASH_UP = 0.004                      # its foot over the band's top
STIFF = 0.45                          # radians: how far round the stiffened front reaches
N_AROUND = 96
V_SPAN = 0.22                         # metres of beret, band foot to top, along the texture's v
BERET_TEX = (2048, 512)

# --- The wings ------------------------------------------------------------------------------
CHEST_X = [-0.13, -0.11, -0.09, -0.07, -0.05, -0.03]
CHEST_Z = [1.425, 1.44, 1.455, 1.47, 1.485]
CHEST_Y = [                           # his front's y at each (z, x): FatiguesM.nif's, measured
    [0.1108, 0.1228, 0.1303, 0.1315, 0.1332, 0.1432],
    [0.1041, 0.1168, 0.1229, 0.1275, 0.1281, 0.1374],
    [0.0971, 0.1107, 0.1154, 0.1200, 0.1234, 0.1309],
    [0.0907, 0.1026, 0.1071, 0.1116, 0.1160, 0.1236],
    [0.0858, 0.0918, 0.0975, 0.1020, 0.1064, 0.1141],
]
WINGS_AT = (-0.085, 1.455)            # its middle: x (his left is -x) and height
WINGS_W, WINGS_H = 0.085, 0.032
WINGS_OFF = 0.003
WINGS_TEX = (512, 192)

MAROON = (92, 22, 34)
GOLD = (214, 172, 62)
BLUE = (34, 62, 168)
DARK_BLUE = (22, 40, 120)
OD = (82, 90, 60)
THREAD = (22, 22, 20)
MATERIALS = {"beret": (None, {"double_sided": True}), "wings": (None, {})}


def _lerp(a, b, t):
    return a + (b - a) * t


def _bez(p0, p1, p2, t):
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2


def beret_grid():
    """Points (around x along), metres, and each column's angle."""
    thetas = np.linspace(-math.pi / 2, 3 * math.pi / 2, N_AROUND + 1)
    cx, cy = CENTRE
    top = np.array([cx + TOP_SHIFT[0], cy + TOP_SHIFT[1], TOP_Z])
    cols = []
    for th in thetas:
        right = max(0.0, math.cos(th))
        d = (th - FLASH_AT + math.pi) % (2 * math.pi) - math.pi
        stiff = math.exp(-(d / STIFF) ** 2)
        e = np.array([cx + BAND_A * math.cos(th), cy + BAND_B * math.sin(th)])
        zb = BAND_Z + BAND_TILT * math.sin(th)
        zt = zb + BAND_H
        k = 1.20 + 0.20 * right - 0.15 * stiff
        zr = zt + 0.030 - 0.045 * right ** 1.5 + 0.025 * stiff
        rel = e - np.array([cx, cy])
        at = lambda r, z: np.array([cx + r * rel[0], cy + r * rel[1], z])
        a, r = at(1.0, zt), at(k, zr)
        q1 = at(_lerp(k * 0.9, 1.0, stiff), _lerp(zt + 0.012, zr, stiff))
        q2 = at(0.8 * k, TOP_Z)
        pts = [at(1.0, zb), at(1.0, zb + BAND_H / 2), a]
        pts += [_bez(a, q1, r, t) for t in np.linspace(0, 1, 11)[1:]]
        pts += [_bez(r, q2, top, t) for t in np.linspace(0, 1, 13)[1:]]
        cols.append(pts)
    return np.array(cols), thetas


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
        yb = H * 0.62
        pts = [(x0, y0), (x1, y0), (x1, yb)]
        for t in np.linspace(0, 1, 24):
            pts.append((_lerp(x1, W / 2, t), _lerp(yb, H - inset, math.sin(t * math.pi / 2))))
        for t in np.linspace(1, 0, 24):
            pts.append((_lerp(x0, W / 2, t), _lerp(yb, H - inset, math.sin(t * math.pi / 2))))
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
    # The flash: its width in u at the band (the band's speed there), its height in v, upright
    # on the beret (v runs up it, the image down: flipped).
    th = FLASH_AT
    speed = math.hypot(BAND_A * math.sin(th), BAND_B * math.cos(th))      # metres per radian
    du = FLASH_W / speed / (2 * math.pi)
    u0 = (th + math.pi / 2) / (2 * math.pi)
    w_px, h_px = int(du * W), int(FLASH_H / V_SPAN * H)
    flash = draw_flash(w_px, h_px).transpose(Image.FLIP_TOP_BOTTOM)
    y0 = int((BAND_H + FLASH_UP) / V_SPAN * H)
    img.paste(flash, (int(u0 * W - w_px / 2), y0), flash)
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


def tex_wings():
    """Black embroidered wings on olive drab: the canopy and its shroud lines in the middle, a
    wing curling up each side, feathered along its underside."""
    W, H = WINGS_TEX
    S = 4
    img = Image.new("RGB", (W * S, H * S), OD)
    d = ImageDraw.Draw(img)
    cx, cy = W * S / 2, H * S * 0.5
    # The canopy: a dome, its lines down to a point.
    cw, chh = W * S * 0.19, H * S * 0.30
    d.chord([cx - cw / 2, cy - chh * 1.25, cx + cw / 2, cy + chh * 0.75], 180, 360, fill=THREAD)
    for k in range(-3, 4):
        d.line([(cx + k * cw / 7, cy - chh * 0.25), (cx, cy + chh * 1.05)], fill=THREAD, width=S * 3)
    for side in (-1, 1):
        # A wing: its top edge sweeps out from the canopy and rises to the tip, which curls
        # back in; its underside is a row of feather tips back to the root.
        sx = lambda f: cx + side * f * W * S
        root_top, root_bot = (sx(0.085), cy - chh * 0.15), (sx(0.085), cy + chh * 0.55)
        top = [root_top]
        for t in np.linspace(0, 1, 16)[1:]:
            top.append((sx(0.085 + 0.37 * t), cy - chh * (0.15 + 0.95 * t ** 2.2)))
        tip = top[-1]
        curl = [(sx(0.47), tip[1] + chh * 0.35), (sx(0.445), tip[1] + chh * 0.75)]
        under = []
        n_f = 7
        for k in range(n_f + 1):
            t = 1 - k / n_f
            x = 0.085 + 0.34 * t
            y = cy + chh * (0.55 - 0.55 * t ** 2.4)
            under.append((sx(x), y + chh * 0.28))                  # a feather's tip
            if k < n_f:
                tn = 1 - (k + 0.5) / n_f
                under.append((sx(0.085 + 0.34 * tn), cy + chh * (0.55 - 0.55 * tn ** 2.4) - chh * 0.02))
        d.polygon(top + curl + under + [root_bot], fill=THREAD)
        # Feather lines: the cloth showing between the rows.
        for k in range(1, n_f):
            t = 1 - k / n_f
            x = sx(0.085 + 0.34 * t)
            y = cy + chh * (0.55 - 0.55 * t ** 2.4)
            d.line([(x, y + chh * 0.22), (x - side * W * S * 0.025, y - chh * 0.35)], fill=OD, width=S * 2)
        d.line([(sx(0.10), cy + chh * 0.05), (sx(0.44), tip[1] + chh * 0.45)], fill=OD, width=S * 2)
    img = img.resize((W, H), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    rng = np.random.default_rng(55)
    weave = rng.normal(0, 0.04, (H, W))
    rgb = np.asarray(img, np.float32) * (1 + weave[..., None])
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB"), a.mean(axis=2) * 0.4 + weave


def save_set(tex_dir, name, img, height, shine, smooth):
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
    worn.write_worn(mesh_dir / "Beret.nif", "Beret", {"Beret": ("beret", beret, worn.rigid("HEAD"))},
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
