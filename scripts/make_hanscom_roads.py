"""Hanscom's streets as raised asphalt with vanilla's road material, one model per cell.

Painted on the terrain, a street lay flat in it and its colour was close to the grass's, so it
blended away; vanilla's roads stand a little proud, poured, with an edge (the author,
2026-11-24). So each street is a mesh again, but not the first try's (sunk edges that stood as
walls with their texture stretched down them where the ground fell away):

  - its top RAISE units over the ground, following the ground at every height point;
  - a lip LIP units wide at each edge, sloping from the top to SINK under the ground, so the
    street ends in a low poured edge and never in a wall (the slope is gentle, so its texture,
    mapped from above, doesn't stretch);
  - vanilla's road asphalt (Materials\\Landscape\\Roads\\Asphalt01.BGSM, its texture repeating
    every TILE units as on vanilla's road pieces), with collision.

The ground is the plugin's own terrain (its heights, as the game draws them), read from the
plugin given; the layout is make_hanscom_paving.py's streets, in the cells esp_crop.py keeps.
The ground paint puts gravel along the shoulders (make_hanscom_ground.py).

    python scripts/make_hanscom_roads.py <plugin.esp> [--install "<Fallout 4>/Data"]

Writes out/hanscom/mod/Meshes/DevilsInTheDetails/Hanscom/Road_<x>_<y>.nif and roads.json (for
scripts/esp/esp_roads.py).
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import Polygon, box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "esp"))
from make_heightmap import CELL_UNITS, out_dir                                  # noqa: E402
from make_photo_overlay import load_pynifly                                     # noqa: E402
import make_hanscom_paving as hp                                                # noqa: E402
from esplib import parse                                                        # noqa: E402
from landh import load_heights, height_at                                       # noqa: E402

HANSCOM = 0x0100A22E
KEEP = (-4, 15, -14, -2)          # esp_crop.py's kept cells: x0, x1, y0, y1
RAISE = 8.0                       # the top over the ground (about 11 cm)
LIP = 40.0                        # the edge's width (about 57 cm)
SINK = 6.0                        # the edge's outer side under the ground
TILE = 512.0                      # the texture's repeat, as on vanilla's road pieces
GRID = 128                        # the terrain's point spacing: the mesh follows every point
MATERIAL = r"Materials\Landscape\Roads\Asphalt01.BGSM"
TEXTURES = r"landscape\roads\asphalt01"


def cell_mesh(top, band, ground, cx, cy):
    """(verts, tris, uvs) of one cell's street, in the cell's own coordinates."""
    ox, oy = cx * CELL_UNITS, cy * CELL_UNITS
    cell = box(ox, oy, ox + CELL_UNITS, oy + CELL_UNITS)
    xs = np.arange(ox, ox + CELL_UNITS, GRID)
    squares = np.array([box(x, y, x + GRID, y + GRID) for y in xs - ox + oy for x in xs])
    index, verts, tris = {}, [], []
    for part in (top.intersection(cell), band.intersection(cell)):
        if part.is_empty:
            continue
        sq = squares[shapely.intersects(squares, part)]
        for gc in shapely.constrained_delaunay_triangles(shapely.intersection(sq, part)):
            for tri in getattr(gc, "geoms", [gc]):
                if tri.is_empty or tri.area < 1.0:
                    continue
                ring = list(tri.exterior.coords)[:3]
                if not Polygon(ring).exterior.is_ccw:
                    ring = ring[::-1]
                ids = []
                for x, y in ring:
                    k = (round(x, 2), round(y, 2))
                    if k not in index:
                        index[k] = len(verts)
                        verts.append(k)
                    ids.append(index[k])
                if len(set(ids)) == 3:
                    tris.append(tuple(ids))
    if not tris:
        return None
    v = np.array(verts)
    # From the top's edge out across the lip: RAISE over the ground down to SINK under it.
    t = np.clip(shapely.distance(top, shapely.points(v[:, 0], v[:, 1])) / LIP, 0, 1)
    z = np.array([ground(x, y) for x, y in v]) + RAISE - t * (RAISE + SINK)
    local = [(x - ox, y - oy, float(zz)) for (x, y), zz in zip(verts, z)]
    uvs = [(x / TILE, -y / TILE) for x, y in verts]
    return local, tris, uvs


def write_nif(path, name, mesh, pyn):
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, \
        PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR = pyn
    verts, tris, uvs = mesh
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="BSFadeNode", root_name=name)
    props = NiShapeBuf()
    props.bufType = PynBufferTypes.BSTriShapeBufType
    props.hasFullPrecision = 1
    shape = nif.createShapeFromData("asphalt", verts, tris, uvs, [(0.0, 0.0, 1.0)] * len(verts),
                                    props=props, parent=nif.root)
    shape.shader._checked_for_materials = True
    shape.shader._materials = None
    shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
    shape.set_texture("Diffuse", f"{TEXTURES}_d.dds")
    shape.set_texture("Normal", f"{TEXTURES}_n.dds")
    shape.set_texture("Specular", f"{TEXTURES}_s.dds")
    shape.shader.name = MATERIAL
    shape.save_shader_attributes()
    cv = [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
    physics = PhysicsProps(is_dynamic=False,
                           body_props_raw=bytes.fromhex("00ff003f003fcd3e01024c3deeff7f7f"),
                           collision_filter_info=1)
    packed = pack_shapes([CollisionShape(shape_type="compressed_mesh", name="collision",
                                         transform=None, verts=cv, faces=[list(t) for t in tris],
                                         convex_radius=0.0, children=[], physics=physics)])
    BSXFlags.New(nif, flags=130, parent=nif.root)
    coll = nif.root.add_collision(None, flags=128,
                                  collision_type=PynBufferTypes.bhkNPCollisionObjectBufType, body_id=0)
    bhkPhysicsSystem.New(nif, data=packed, parent=coll)
    nif.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin", help="the plugin whose terrain the streets lie on")
    ap.add_argument("--install", help="the game's Data folder, to copy the models into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR)

    out = out_dir(hp.AREA)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = hp.Terrain(out)
    world = box(terrain.x0, terrain.y1 - terrain.cells[1] * CELL_UNITS,
                terrain.x0 + terrain.cells[0] * CELL_UNITS, terrain.y1)
    areas = {}
    for mat, poly in hp.paved_areas(json.loads((out / "osm.json").read_text()), to_utm).items():
        g = shapely.transform(poly, lambda p: np.column_stack(terrain.game(p[:, 0], p[:, 1])))
        areas[mat] = g.intersection(world)
    kept = box(KEEP[0] * CELL_UNITS, KEEP[2] * CELL_UNITS, (KEEP[1] + 1) * CELL_UNITS, (KEEP[3] + 1) * CELL_UNITS)
    roads = hp.streets(out, terrain, to_utm, areas, world).intersection(kept)
    top = roads.buffer(-LIP)
    band = roads.difference(top)
    shapely.prepare(top)

    hs = load_heights(parse(open(args.plugin, "rb").read()), HANSCOM)
    ground = lambda x, y: height_at(hs, x, y)

    mesh_dir = out / "mod" / "Meshes" / hp.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    for old in mesh_dir.glob("Road_*.nif"):
        old.unlink()
    models, files = [], []
    for cy in range(KEEP[2], KEEP[3] + 1):
        for cx in range(KEEP[0], KEEP[1] + 1):
            mesh = cell_mesh(top, band, ground, cx, cy)
            if mesh is None:
                continue
            name = f"Road_{cx}_{cy}"
            path = mesh_dir / f"{name}.nif"
            write_nif(path, name, mesh, pyn)
            files.append(path)
            v = np.array(mesh[0])
            lo, hi = v.min(axis=0), v.max(axis=0)
            models.append({"name": name, "nif": f"{hp.MOD_PATH}/{name}.nif".replace("/", "\\"),
                           "position": [cx * CELL_UNITS, cy * CELL_UNITS, 0], "cell": [cx, cy],
                           "bounds": [int(math.floor(c)) for c in lo] + [int(math.ceil(c)) for c in hi],
                           "triangles": len(mesh[1])})
    (out / "roads.json").write_text(json.dumps(
        {"note": "place each model at its position (game units) with no rotation", "raise": RAISE,
         "models": models}, indent=1))
    print(f"{len(models)} street models, {sum(m['triangles'] for m in models)} triangles")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(out / "mod")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
