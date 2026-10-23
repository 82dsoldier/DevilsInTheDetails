"""Drape an area's 1993 photo over its terrain, as a reference mesh for the Creation Kit.

    python scripts/make_photo_overlay.py                      # the barracks area
    python scripts/make_photo_overlay.py --area sicily
    python scripts/make_photo_overlay.py --install "C:/Steam/steamapps/common/Fallout 4/Data"

Run make_heightmap.py and make_overlay.py for the same area first. Needs PyNifly
(github.com/BadDogSkyrim/PyNifly, the io_scene_nifly release zip) unpacked to
data/tools/io_scene_nifly; it runs without Blender.

The mesh follows the heightmap point for point, Z_OFFSET units above it, so it shows the
photo on the ground without getting in the way: no collision, so you walk on the real
terrain underneath. It's in pieces of BLOCK x BLOCK cells (a piece can't have more than
65,535 vertices), all in one NIF, in game coordinates: place it at 0, 0, 0 with no rotation.
Delete the reference when the photo is no longer needed.

Writes to out/<area>/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Reference/<area>_photo.nif
  Textures/DevilsInTheDetails/Reference/<area>_photo.dds     the photo, BC1
  Textures/DevilsInTheDetails/Reference/flat_n.dds           a flat normal map
--install copies them into the game's Data folder.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import AREAS, CELL_UNITS, POINT_UNITS, ROOT, out_dir   # noqa: E402

BLOCK = 4          # cells per mesh piece, each way: 129 x 129 = 16,641 vertices
Z_OFFSET = 16      # game units above the terrain (about 23 cm)
TEX_MAX = 4096     # longest side of the photo texture, in pixels
MOD_PATH = "DevilsInTheDetails/Reference"


def load_pynifly():
    tools = ROOT / "data" / "tools" / "io_scene_nifly"
    if not (tools / "NiflyDLL.dll").exists():
        raise SystemExit(f"PyNifly not found: unpack io_scene_nifly to {tools}")
    sys.path.insert(0, str(tools))
    from pyn.pynifly import NifFile
    from pyn.nifdefs import NiShapeBuf, PynBufferTypes
    from pyn.nifconstants import ShaderFlags2FO4 as ShaderFlags2
    return NifFile, NiShapeBuf, PynBufferTypes, ShaderFlags2


def write_textures(area, out, tex_dir):
    with rasterio.open(out / "aerial_grid.tif") as src:
        photo = src.read(1)
    h, w = photo.shape
    scale = TEX_MAX / max(w, h)
    size = (max(4, round(w * scale / 4) * 4), max(4, round(h * scale / 4) * 4))
    img = Image.fromarray(photo).convert("RGB").resize(size, Image.LANCZOS)
    img.save(tex_dir / f"{area}_photo.dds", pixel_format="DXT1")
    Image.new("RGB", (4, 4), (128, 128, 255)).save(tex_dir / "flat_n.dds", pixel_format="DXT1")
    return size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="barracks", choices=sorted(AREAS))
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, ShaderFlags2 = load_pynifly()

    out = out_dir(args.area)
    meta = json.loads((out / "heightmap.json").read_text())
    cells = json.loads((out / "cells.json").read_text())
    nx, ny = meta["points"]
    step = meta["game_units_per_pixel_step"]
    h16 = np.fromfile(out / "heightmap16.raw", dtype="<u2").reshape(ny, nx)
    z = h16.astype(np.float64) * step                 # game units above the lowest point
    x0 = cells["x_range"][0] * CELL_UNITS             # west edge, game units
    y0 = (cells["y_range"][1] + 1) * CELL_UNITS       # north edge, game units

    # Normals from the height field: rows run south, so north is minus the row direction.
    dz_drow, dz_dcol = np.gradient(z, POINT_UNITS)
    n = np.dstack([-dz_dcol, dz_drow, np.ones_like(z)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)

    mod = out / "mod"
    mesh_dir = mod / "Meshes" / MOD_PATH
    tex_dir = mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_size = write_textures(args.area, out, tex_dir)

    nif_path = mesh_dir / f"{args.area}_photo.nif"
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="BSFadeNode", root_name=f"{args.area}_photo")
    span = BLOCK * 32
    pieces = 0
    for r0 in range(0, ny - 1, span):
        for c0 in range(0, nx - 1, span):
            r1, c1 = min(r0 + span, ny - 1), min(c0 + span, nx - 1)
            rows, cols = np.arange(r0, r1 + 1), np.arange(c0, c1 + 1)
            rr, cc = np.meshgrid(rows, cols, indexing="ij")
            verts = np.dstack([x0 + cc * POINT_UNITS, y0 - rr * POINT_UNITS,
                               z[rr, cc] + Z_OFFSET]).reshape(-1, 3)
            # PyNifly flips v (1 - v) on the way in, so give it Blender's bottom-up v.
            uvs = np.dstack([cc / (nx - 1), 1 - rr / (ny - 1)]).reshape(-1, 2)
            norms = n[rr, cc].reshape(-1, 3)
            w = len(cols)
            tris = []
            for i in range(len(rows) - 1):
                for j in range(len(cols) - 1):
                    a, b = i * w + j, i * w + j + 1
                    c, d = a + w, b + w
                    tris += [(a, c, b), (b, c, d)]    # counter-clockwise seen from above
            props = NiShapeBuf()
            props.bufType = PynBufferTypes.BSTriShapeBufType
            props.hasFullPrecision = 1   # 32-bit positions: half floats stop at 65,504 units
            shape = nif.createShapeFromData(
                f"photo_{r0 // span}_{c0 // span}", [tuple(v) for v in verts.tolist()], tris,
                [tuple(v) for v in uvs.tolist()], [tuple(v) for v in norms.tolist()],
                props=props, parent=nif.root)
            shape.shader._checked_for_materials = True
            shape.shader._materials = None
            shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
            shape.shader.properties.shaderflags2_set(ShaderFlags2.DOUBLE_SIDED)
            shape.set_texture("Diffuse", f"textures\\{MOD_PATH.replace('/', chr(92))}\\{args.area}_photo.dds")
            shape.set_texture("Normal", f"textures\\{MOD_PATH.replace('/', chr(92))}\\flat_n.dds")
            shape.save_shader_attributes()
            pieces += 1
    nif.save()

    print(f"{nif_path.relative_to(ROOT)}: {pieces} pieces; photo texture {tex_size[0]} x {tex_size[1]}")
    if args.install:
        data = Path(args.install)
        for f in (nif_path, tex_dir / f"{args.area}_photo.dds", tex_dir / "flat_n.dds"):
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
