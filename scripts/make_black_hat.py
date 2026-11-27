"""Sergeant Airborne's black hat: the jump school instructor's black ball cap, with silver jump
wings and his rank pinned on the front (the author, 2026-11-27).

The cap is vanilla's baseball cap (Clothes\\BaseballUniform\\MHat.nif, read from the game's
archives) with its crown raised CROWN_RAISE (the vintage cap's crown is low, and a black hat's
front is tall enough for two pins), dyed black from vanilla's own texture, its wear kept. On
the front: the parachutist badge as a polished silver pin (the wings' own drawing,
make_uniform.tex_wings, as a cut-out) and under it his rank, RANK, as a polished pin. Each pin
is laid on the crown's front, PIN_OFF out from it.

    python scripts/make_black_hat.py [--install "<Fallout 4>/Data"]

Writes out/uniform/mod/Meshes/DevilsInTheDetails/Uniform/BlackHat.nif and
Textures/DevilsInTheDetails/Uniform/uniform_{blackhat,hatwings,hatrank}{,_n,_s}.dds. The plugin's
armor (DevilsBlackHat; scripts/esp/esp_airborne.py) points at it.
"""
import argparse
import io
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ba2                                                        # noqa: E402
import make_c130_blockout as c                                    # noqa: E402
import make_uniform as uni                                        # noqa: E402
import worn                                                       # noqa: E402
from ddsutil import save_dds                                      # noqa: E402
from make_heightmap import UNIT_M, out_dir                        # noqa: E402

DATA = Path(r"C:\Steam\steamapps\common\Fallout 4\Data")
CAP_NIF = r"Meshes\Clothes\BaseballUniform\MHat.nif"
CAP_TEX = r"textures\Clothes\VintageBaseball\VintageBaseballHat"
BLACK = np.array([24, 24, 26], float)
CROWN_BASE = 1.80               # metres (his frame): the bill's top; the crown above it is raised
CROWN_RAISE = 1.3
PIN_OFF = 0.0015
WINGS_W, WINGS_H = 0.060, 0.0315            # the badge's size, as the cloth one
WINGS_Z = 1.872                              # their middle's height (after the raise)
RANK = "SSG"                                 # three chevrons and a rocker
RANK_W, RANK_H = 0.020, 0.022
RANK_Z = 1.838
SILVER = (206, 208, 212)
MATERIALS = {"blackhat": (None, {}), "hatwings": (None, {"alpha": True}), "hatrank": (None, {"alpha": True})}


def load_cap(pyn):
    """The vanilla cap: verts (metres, his frame), tris, uvs, normals."""
    NifFile = pyn[0]
    raw = ba2.read(DATA / "Fallout4 - Meshes.ba2", CAP_NIF)
    tmp = out_dir("uniform") / "_vanilla_MHat.nif"
    tmp.write_bytes(raw)
    s = NifFile(str(tmp)).shapes[0]
    v = (np.array(s.verts) - np.array(worn.G2S_T)) * UNIT_M
    up = v[:, 2] > CROWN_BASE
    v[up, 2] = CROWN_BASE + (v[up, 2] - CROWN_BASE) * CROWN_RAISE
    return v, np.array(s.tris), list(s.uvs), np.array(s.normals)


def front_y(V, T, x, z):
    """The cap's front surface (largest y) at (x, z), or None."""
    best = None
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    d = (B[:, 0] - A[:, 0]) * (C[:, 2] - A[:, 2]) - (C[:, 0] - A[:, 0]) * (B[:, 2] - A[:, 2])
    ok = np.abs(d) > 1e-12
    u = np.where(ok, ((x - A[:, 0]) * (C[:, 2] - A[:, 2]) - (C[:, 0] - A[:, 0]) * (z - A[:, 2])) / np.where(ok, d, 1), -1)
    w = np.where(ok, ((B[:, 0] - A[:, 0]) * (z - A[:, 2]) - (x - A[:, 0]) * (B[:, 2] - A[:, 2])) / np.where(ok, d, 1), -1)
    hit = ok & (u >= 0) & (w >= 0) & (u + w <= 1)
    if not hit.any():
        return None
    y = A[hit, 1] + u[hit] * (B[hit, 1] - A[hit, 1]) + w[hit] * (C[hit, 1] - A[hit, 1])
    return float(y.max())


def pin_mesh(V, T, cx, cz, w, h, nx=7, nz=4):
    """A flat patch w x h centred at (cx, cz) on the cap's front, following its curve."""
    m = c.Mesh()
    xs = np.linspace(cx - w / 2, cx + w / 2, nx)
    zs = np.linspace(cz - h / 2, cz + h / 2, nz)
    fy = lambda x, z: front_y(V, T, x, z)
    idx = {}
    for a, z in enumerate(zs):
        for b, x in enumerate(xs):
            y = fy(x, z)
            assert y is not None, (x, z)
            e = 0.002
            n = np.array([-(fy(x + e, z) - fy(x - e, z)) / (2 * e), 1.0, -(fy(x, z + e) - fy(x, z - e)) / (2 * e)])
            n /= np.linalg.norm(n)
            idx[a, b] = m.vert(tuple(np.array([x, y, z]) + n * PIN_OFF), tuple(n),
                               (b / (nx - 1), 1 - a / (nz - 1)))
    for a in range(nz - 1):
        for b in range(nx - 1):
            m.quad(idx[a, b], idx[a, b + 1], idx[a + 1, b + 1], idx[a + 1, b])
    return m


def metal(mask, base, seed):
    """A polished pin: base colour where mask, a little bevel shading toward the edges, alpha
    the mask."""
    a = np.asarray(mask.convert("L"), np.float32) / 255
    blur = np.asarray(mask.convert("L").resize((mask.width // 4, mask.height // 4), Image.BILINEAR)
                      .resize(mask.size, Image.BILINEAR), np.float32) / 255
    rng = np.random.default_rng(seed)
    shade = 0.75 + 0.3 * blur + 0.02 * rng.normal(0, 1, a.shape)
    rgb = np.array(base, float)[None, None, :] * shade[..., None]
    rgba = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA"), blur * 0.5


def tex_rank(size=128):
    """SSG: three chevrons, points up, over one rocker (curving down at its ends), as a mask."""
    S = 4
    n = size * S
    img = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(img)
    t = n * 0.085                         # a bar's thickness
    for k in range(3):
        top = n * (0.06 + k * 0.17)
        d.line([(n * 0.06, top + n * 0.24), (n * 0.5, top), (n * 0.94, top + n * 0.24)], fill=255, width=int(t))
    d.arc([n * 0.02, n * 0.18, n * 0.98, n * 0.96], 25, 155, fill=255, width=int(t))
    return img.resize((size, size), Image.LANCZOS)


def tex_hat(pyn):
    """Vanilla's cap texture dyed black: its detail (stitching, wear) kept as light and shade."""
    img = ba2.texture(DATA / "Fallout4 - Textures2.ba2", CAP_TEX + "_d.dds").convert("RGB")
    a = np.asarray(img, np.float32).mean(axis=2)
    local = np.asarray(Image.fromarray(a.astype(np.uint8)).resize((32, 32), Image.BILINEAR)
                       .resize(img.size, Image.BILINEAR), np.float32) + 1
    detail = np.clip(a / local, 0.6, 1.6)
    rgb = BLACK[None, None, :] * (0.4 + 0.6 * detail[..., None])
    n = np.asarray(ba2.texture(DATA / "Fallout4 - Textures2.ba2", CAP_TEX + "_n.dds").convert("RGB"), np.float32)
    xy = n[..., :2] / 255 * 2 - 1                    # a two-channel map: its z rebuilt
    z = np.sqrt(np.clip(1 - (xy ** 2).sum(axis=2), 0, 1))
    nimg = Image.fromarray(np.clip(np.dstack([n[..., 0], n[..., 1], (z * 0.5 + 0.5) * 255]), 0, 255).astype(np.uint8), "RGB")
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB"), nimg


def save(tex_dir, name, img, normal, shine, smooth, fmt="DXT1"):
    f = tex_dir / f"{uni.PREFIX}{name}.dds"
    save_dds(img, f, fmt)
    fn = tex_dir / f"{uni.PREFIX}{name}_n.dds"
    if isinstance(normal, Image.Image):
        save_dds(normal, fn)
    else:
        save_dds(Image.fromarray(np.clip(c.normal_map(normal, 0.05), 0, 255).astype(np.uint8), "RGB"), fn)
    fs = tex_dir / f"{uni.PREFIX}{name}_s.dds"
    Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
    return [f, fn, fs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    pyn = worn.load_pyn()
    out = out_dir("uniform")
    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / uni.MOD_PATH, mod / "Textures" / uni.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex = "DevilsInTheDetails\\Uniform"

    V, T, uvs, N = load_cap(pyn)
    cap = c.Mesh()
    cap.verts, cap.tris, cap.uvs, cap.norms = [tuple(v) for v in V], [tuple(t) for t in T], uvs, [tuple(n) for n in N]
    wings = pin_mesh(V, T, 0.0, WINGS_Z, WINGS_W, WINGS_H)
    rank = pin_mesh(V, T, 0.0, RANK_Z, RANK_W, RANK_H, nx=4, nz=4)

    hat_img, hat_n = tex_hat(pyn)
    files = save(tex_dir, "blackhat", hat_img, hat_n, 0.04, 0.2)
    wmask = uni.tex_wings(cloth=(0, 0, 0), thread=(255, 255, 255), size=(512, 256))[0]
    wmask = wmask.convert("L").point(lambda q: 255 if q > 128 else 0)    # no cloth weave on metal
    wimg, wh = metal(wmask, SILVER, 1)
    files += save(tex_dir, "hatwings", wimg, wh, 0.7, 0.6, "DXT5")
    rimg, rh = metal(tex_rank(), SILVER, 2)
    files += save(tex_dir, "hatrank", rimg, rh, 0.7, 0.6, "DXT5")
    wimg.save(out / "hatwings_texture.png")
    rimg.save(out / "hatrank_texture.png")

    worn.write_worn(mesh_dir / "BlackHat.nif", "BlackHat",
                    {"BlackHat": ("blackhat", cap, worn.rigid("HEAD")),
                     "Wings": ("hatwings", wings, worn.rigid("HEAD")),
                     "Rank": ("hatrank", rank, worn.rigid("HEAD"))},
                    tex, pyn, MATERIALS, uni.PREFIX)
    files.append(mesh_dir / "BlackHat.nif")
    print(f"BlackHat.nif: cap {len(V)} verts (crown x{CROWN_RAISE}, top {V[:, 2].max():.3f} m), "
          f"wings at {WINGS_Z} m, {RANK} at {RANK_Z} m")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
