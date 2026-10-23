"""A plain block-out of the hammerhead barracks: the right size, no detail.

    python scripts/make_barracks_blockout.py [--install "<Fallout 4>/Data"]

The building, in its own coordinates (metres; +y runs along the main wing toward its north
end, +x across it to the east, the origin at the centre of the main wing, ground level 0):
  main wing     three floors, WING_W x WING_L
  office wing   one floor, across the north end, from the armory to OFFICE_INSET short of the
                wing's east wall, leaving room for the company entrance in the corner
  armory        one floor, the short leg of the L at the west end, pointing north
Walls run FOOTING m below 0 so sloping ground never shows a gap.

Placement comes from the 1993 photo (cells (-2, 9) and (-2, 8)) and the heightmap. It writes
out/barracks/blockout_check.png (the footprint drawn on the photo) and prints the reference's
position and rotation for the Creation Kit.

Writes to out/barracks/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Buildings/Barracks_Blockout.nif
  Textures/DevilsInTheDetails/Buildings/sandstone.dds, flat_n.dds
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, POINT_UNITS, ROOT, UNIT_M, out_dir   # noqa: E402
from make_photo_overlay import load_pynifly                                 # noqa: E402

# Size, metres.
WING_L, WING_W, WING_H = 85.0, 17.0, 11.0     # three floors and a parapet
LOW_H = 4.5                                   # the one-story L
OFFICE_DEPTH = 10.0                           # office wing, north of the main wing
OFFICE_WEST = -26.0                           # its west end (the armory's west wall)
OFFICE_INSET = 4.0                            # its east end, this far in from the wing's east wall
ARMORY_W, ARMORY_DEPTH = 12.0, 8.0            # the short leg, beyond the office wing
FOOTING = 2.0

# Placement, read off the 1993 photo: the main wing's centre, in metres from the photo's
# north-west corner, and the compass heading of its axis toward the north end.
CENTRE_PX = (684.5, 597.0)
HEADING_DEG = -10.9

SANDSTONE = (201, 184, 152)
MOD_PATH = "DevilsInTheDetails/Buildings"


def boxes():
    """(x0, y0, x1, y1, height) in building metres."""
    n = WING_L / 2
    return [
        (-WING_W / 2, -n, WING_W / 2, n, WING_H),
        (OFFICE_WEST, n, WING_W / 2 - OFFICE_INSET, n + OFFICE_DEPTH, LOW_H),
        (OFFICE_WEST, n + OFFICE_DEPTH, OFFICE_WEST + ARMORY_W, n + OFFICE_DEPTH + ARMORY_DEPTH, LOW_H),
    ]


def to_world(x, y):
    """Building metres -> metres east and north of the main wing's centre."""
    h = math.radians(HEADING_DEG)
    return (x * math.cos(h) + y * math.sin(h), -x * math.sin(h) + y * math.cos(h))


def box_faces(x0, y0, x1, y1, h):
    """Verts, normals, UVs and triangles of a box, flat-shaded, in game units."""
    s = 1 / UNIT_M
    z0, z1 = -FOOTING * s, h * s
    x0, y0, x1, y1 = x0 * s, y0 * s, x1 * s, y1 * s
    quads = [
        ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),     # roof
        ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),    # south
        ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),     # east
        ([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0)),     # north
        ([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0)),    # west
    ]
    verts, norms, uvs, tris = [], [], [], []
    for q, n in quads:
        b = len(verts)
        verts += q
        norms += [n] * 4
        uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]   # counter-clockwise from outside
    return verts, norms, uvs, tris


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR

    out = out_dir("barracks")
    meta = json.loads((out / "heightmap.json").read_text())
    cells = json.loads((out / "cells.json").read_text())
    nx, ny = meta["points"]
    h16 = np.fromfile(out / "heightmap16.raw", dtype="<u2").reshape(ny, nx)
    zmap = h16.astype(np.float64) * meta["game_units_per_pixel_step"]
    west_u = cells["x_range"][0] * CELL_UNITS
    north_u = (cells["y_range"][1] + 1) * CELL_UNITS

    # Footprint on the photo, for checking by eye.
    with rasterio.open(out / "aerial_grid.tif") as src:
        photo = src.read(1)
    cx, cy = CENTRE_PX
    x0, y0 = int(cx - 90), int(cy - 110)
    S = 5
    img = ImageOps.autocontrast(Image.fromarray(photo[y0:y0 + 220, x0:x0 + 180]), cutoff=1)
    img = img.resize((img.width * S, img.height * S), Image.BICUBIC).convert("RGB")
    d = ImageDraw.Draw(img)
    ground = []
    for bx0, by0, bx1, by1, _ in boxes():
        pts = []
        for x, y in ((bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)):
            e, n = to_world(x, y)
            px, py = cx + e, cy - n
            pts.append(((px - x0) * S, (py - y0) * S))
            c, r = px / (POINT_UNITS * UNIT_M), py / (POINT_UNITS * UNIT_M)
            ground.append(zmap[int(round(r)), int(round(c))])
        d.polygon(pts, outline=(255, 0, 255), width=3)
    img.save(out / "blockout_check.png")

    # The mesh, in the building's own coordinates, with collision of the same boxes.
    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), SANDSTONE).save(tex_dir / "sandstone.dds", pixel_format="DXT1")
    Image.new("RGB", (4, 4), (128, 128, 255)).save(tex_dir / "flat_n.dds", pixel_format="DXT1")
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    nif_path = mesh_dir / "Barracks_Blockout.nif"
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="BSFadeNode", root_name="Barracks_Blockout")
    coll_verts, coll_tris = [], []
    for i, b in enumerate(boxes()):
        verts, norms, uvs, tris = box_faces(*b)
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(f"block_{i}", verts, tris, uvs, norms,
                                        props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\sandstone.dds")
        shape.set_texture("Normal", f"{tex}\\flat_n.dds")
        shape.save_shader_attributes()
        base = len(coll_verts)
        coll_verts += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
        coll_tris += [[a + base, b_ + base, c + base] for a, b_, c in tris]

    physics = PhysicsProps(is_dynamic=False,
                           body_props_raw=bytes.fromhex("00ff003f003fcd3e01024c3deeff7f7f"),
                           collision_filter_info=1)
    packed = pack_shapes([CollisionShape(shape_type="compressed_mesh", name="collision",
                                         transform=None, verts=coll_verts, faces=coll_tris,
                                         convex_radius=0.0, children=[], physics=physics)])
    # As vanilla statics have them: BSX "has Havok" (2) plus 128, and collision flags 128.
    # Without the BSX flag the engine ignores the collision and you walk through the walls.
    BSXFlags.New(nif, flags=130, parent=nif.root)
    coll = nif.root.add_collision(None, flags=128,
                                  collision_type=PynBufferTypes.bhkNPCollisionObjectBufType,
                                  body_id=0)
    bhkPhysicsSystem.New(nif, data=packed, parent=coll)
    nif.save()

    # Where it goes: the wing's centre in game units, on the lowest ground under it.
    gx = west_u + cx / UNIT_M
    gy = north_u - cy / UNIT_M
    gz = min(ground)
    rot = HEADING_DEG % 360   # the Creation Kit turns clockwise seen from above, like a compass
    print(f"{nif_path.relative_to(ROOT)}")
    print(f"Place at X {gx:.0f}  Y {gy:.0f}  Z {gz:.0f}, rotation Z {rot:.1f} "
          f"(cell {math.floor(gx / CELL_UNITS)}, {math.floor(gy / CELL_UNITS)}); "
          f"ground under it {min(ground):.0f} to {max(ground):.0f}")
    if args.install:
        data = Path(args.install)
        for f in (nif_path, tex_dir / "sandstone.dds", tex_dir / "flat_n.dds"):
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
