"""Hanscom Field's paving: the runways, taxiways and aprons, as meshes draped on the terrain.

    python scripts/make_hanscom_paving.py [--install "<Fallout 4>/Data"] [--refetch]

Run make_heightmap.py --area hanscom first. Needs PyNifly (see make_photo_overlay.py) and
shapely 2.1 or later.

The layout is OpenStreetMap's (© OpenStreetMap contributors, ODbL), fetched once from the
Overpass API into out/hanscom/osm.json: runways and stopways (46 m wide), taxiways (their
centrelines, TAXIWAY_W wide) and aprons (their outlines). The East Ramp, the military apron
where the C-130 parks, is concrete slabs; everything else is asphalt, as OSM has it.

The ground under the paving is graded first, as a real field's is: the lidar has mounds and
ditch edges where OSM's outlines don't quite fit the ground, and paving draped over them
showed them as bumps (a 2.5 m mound on the East Ramp). Under the paving the ground becomes a
smooth fit of the paved points (a Gaussian of GRADE_SIGMA_M, refit without the points more
than GRADE_OUTLIER_M off it), blending back to the natural ground over BLEND_M outside. The
graded heights go into the plugin's terrain (graded16.raw, the heightmap's format and scale;
graded.dds for the Creation Kit's importer, if the terrain is ever imported again).

The paving follows the graded ground a grid square (GRID units) at a time, OFFSET units above
it, with collision, so the player and the navmesh walk on it. It's cut into one model per cell
(BLOCK; it loads with that cell), each with its origin at its cell's south-west corner, on the ground's lowest point (z 0): place each at the position in
paving.json with no rotation.

Writes to out/hanscom/:
  mod/Meshes/DevilsInTheDetails/Hanscom/Paving_<bx>_<by>.nif
  mod/Textures/DevilsInTheDetails/Hanscom/paving_<material>{,_n,_s}.dds
  graded16.raw     the heightmap with the ground under the paving graded
  graded.dds       the same for the Creation Kit's importer (same min and max as heightmap.dds)
  paving.json      each model: its file, where to place it, its bounds
  paving.png       the layout on the cell grid, for checking by eye
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import requests
import shapely
from scipy import ndimage
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, POINT_M, POINT_UNITS, ROOT, UNIT_M, out_dir, write_dds_r32f  # noqa: E402
from make_photo_overlay import load_pynifly                                   # noqa: E402
import make_c130_blockout as c130                                             # noqa: E402

AREA = "hanscom"
OVERPASS = "https://overpass-api.de/api/interpreter"
OSM_BBOX = (42.455, -71.32, 42.485, -71.26)    # south, west, north, east
RUNWAY_W = 46.0         # metres; OSM's width for both runways and the stopways
TAXIWAY_W = 23.0        # OSM gives no taxiway widths: 75 ft, the usual for a field this size
GRID = 256              # game units between the mesh's grid lines (every second height point)
OFFSET = 10             # game units above the terrain
BLOCK = 1               # cells per model, each way: a model loads with its own cell only, so a
                        # bigger one could be missing under a player near its far edge
SIMPLIFY_M = 0.3        # drop outline points closer than this to the line
MOD_PATH = "DevilsInTheDetails/Hanscom"
TILE_M = {"asphalt": 6.0, "concrete": c130.TARMAC_SLAB}   # one texture repeat, metres
GRADE_SIGMA_M = 10.0    # the graded surface: a Gaussian this wide of the paved ground
GRADE_OUTLIER_M = 0.4   # points further than this off the fit are left out of it (mounds, ditches)
BLEND_M = 12.0          # from the paving's edge back to the natural ground


def fetch_osm(path):
    s, w, n, e = OSM_BBOX
    q = f'[out:json][timeout:60];way["aeroway"]({s},{w},{n},{e});out geom tags;'
    r = requests.post(OVERPASS, data={"data": q}, headers={"User-Agent": "map-tool/1.0"}, timeout=120)
    r.raise_for_status()
    path.write_text(r.text)


def paved_areas(osm, to_utm):
    """{material: polygon, in UTM metres}."""
    asphalt, concrete = [], []
    for el in osm["elements"]:
        t, g = el.get("tags", {}), el.get("geometry")
        kind = t.get("aeroway")
        if not g or kind not in ("runway", "stopway", "taxiway", "apron"):
            continue
        pts = [to_utm.transform(p["lon"], p["lat"]) for p in g]
        if kind == "apron":
            if len(pts) < 4:
                continue
            shape = Polygon(pts).buffer(0)
            (concrete if t.get("surface") == "concrete" else asphalt).append(shape)
        else:
            w = float(t.get("width", RUNWAY_W if kind != "taxiway" else TAXIWAY_W))
            cap = "round" if kind == "taxiway" else "flat"
            asphalt.append(LineString(pts).buffer(w / 2, cap_style=cap, join_style="round"))
    conc = unary_union(concrete)
    asph = unary_union(asphalt).difference(conc)
    return {"asphalt": asph.simplify(SIMPLIFY_M), "concrete": conc.simplify(SIMPLIFY_M)}


def tex_asphalt():
    """Weathered asphalt: dark grey grit, lighter worn patches, a few cracks and tar seams."""
    patch = c130._smooth_noise(60, 0.05)
    grit = c130._noise(61, scale=0.09)
    crack = np.abs(c130._smooth_noise(62, 0.03)) < 0.025
    shade = 0.85 + 0.08 * patch + grit
    rgb = np.array([70, 70, 68])[None, None, :] * shade[..., None]
    rgb[crack] = [34, 34, 33]
    return rgb, grit * 0.3 - crack * 0.3


MATERIALS = {"asphalt": tex_asphalt, "concrete": c130.tex_tarmac}
SPECULAR = {"asphalt": (0.06, 0.2), "concrete": (0.08, 0.2)}


def write_textures(tex_dir):
    files = []
    for name, make in MATERIALS.items():
        img, h = make()
        f = tex_dir / f"paving_{name}.dds"
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(f, pixel_format="DXT1")
        fn = tex_dir / f"paving_{name}_n.dds"
        Image.fromarray(np.clip(c130.normal_map(h), 0, 255).astype(np.uint8), "RGB").save(fn, pixel_format="DXT1")
        shine, smooth = SPECULAR[name]
        fs = tex_dir / f"paving_{name}_s.dds"
        Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
        files += [f, fn, fs]
    return files


class Terrain:
    """The heightmap in game coordinates: z at any (x, y), bilinear between height points."""

    def __init__(self, out):
        meta = json.loads((out / "heightmap.json").read_text())
        self.nx, self.ny = meta["points"]
        cx, cy = meta["cells"]
        h16 = np.fromfile(out / "heightmap16.raw", dtype="<u2").reshape(self.ny, self.nx)
        self.z = h16.astype(np.float64) * meta["game_units_per_pixel_step"]
        # The Creation Kit's import (DESIGN.md): cells centred on 0, 0, x -25 to 25, y -19 to 18
        # here; the first height point is the north-west corner.
        self.cell_x0 = -(cx // 2)
        self.cell_y1 = cy - cy // 2 - 1
        self.x0 = self.cell_x0 * CELL_UNITS
        self.y1 = (self.cell_y1 + 1) * CELL_UNITS
        self.west, self.north = meta["north_west_corner_utm"]
        self.cells = (cx, cy)
        self.step = meta["game_units_per_pixel_step"]
        self.top = meta["height_range_game_units"]

    def grade(self, areas):
        """Grade the ground under the paving (see the module's notes); returns the largest change."""
        xs, ys = np.meshgrid(np.arange(self.nx) * POINT_UNITS + self.x0,
                             self.y1 - np.arange(self.ny) * POINT_UNITS)
        paved = np.zeros(self.z.shape, bool)
        for g in areas.values():
            paved |= shapely.contains_xy(g, xs, ys)
        sigma = GRADE_SIGMA_M / POINT_M
        use = paved.copy()
        for _ in range(4):
            w = ndimage.gaussian_filter(use.astype(float), sigma)
            fit = ndimage.gaussian_filter(np.where(use, self.z, 0.0), sigma) / np.maximum(w, 1e-9)
            use = paved & (np.abs(self.z - fit) < GRADE_OUTLIER_M / UNIT_M)
        d = ndimage.distance_transform_edt(~paved) * POINT_M          # metres outside the paving
        t = np.clip(1 - d / BLEND_M, 0, 1)
        t = t * t * (3 - 2 * t)                                        # smoothstep
        graded = np.clip(t * fit + (1 - t) * self.z, 0, self.top)
        change = float(np.abs(graded - self.z).max())
        self.z = graded
        return change

    def game(self, e, n):
        return self.x0 + (e - self.west) / UNIT_M, self.y1 - (self.north - n) / UNIT_M

    def at(self, x, y):
        fc = np.clip((np.asarray(x) - self.x0) / POINT_UNITS, 0, self.nx - 1.001)
        fr = np.clip((self.y1 - np.asarray(y)) / POINT_UNITS, 0, self.ny - 1.001)
        c, r = fc.astype(int), fr.astype(int)
        tx, ty = fc - c, fr - r
        z = self.z
        return (z[r, c] * (1 - tx) * (1 - ty) + z[r, c + 1] * tx * (1 - ty)
                + z[r + 1, c] * (1 - tx) * ty + z[r + 1, c + 1] * tx * ty)


def block_meshes(area_game, terrain, bx0, by0):
    """{material: (verts, tris, uvs)} for one block, in the block's local coordinates."""
    ox, oy = bx0 * CELL_UNITS, by0 * CELL_UNITS
    size = BLOCK * CELL_UNITS
    out = {}
    for mat, poly in area_game.items():
        part = poly.intersection(box(ox, oy, ox + size, oy + size))
        if part.is_empty:
            continue
        xs = np.arange(ox, ox + size, GRID)
        squares = np.array([box(x, y, x + GRID, y + GRID) for y in xs - ox + oy for x in xs])
        squares = squares[shapely.intersects(squares, part)]
        pieces = shapely.intersection(squares, part)
        tri_sets = shapely.constrained_delaunay_triangles(pieces)
        index, verts, tris = {}, [], []
        tile = TILE_M[mat] / UNIT_M
        for gc in tri_sets:
            for tri in getattr(gc, "geoms", [gc]):
                if tri.is_empty or tri.area < 1.0:
                    continue
                ring = list(tri.exterior.coords)[:3]
                if Polygon(ring).exterior.is_ccw is False:
                    ring = ring[::-1]
                ids = []
                for x, y in ring:
                    k = (round(x, 2), round(y, 2))
                    if k not in index:
                        index[k] = len(verts)
                        verts.append((x, y))
                    ids.append(index[k])
                tris.append(tuple(ids))
        if not tris:
            continue
        v = np.array(verts)
        z = terrain.at(v[:, 0], v[:, 1]) + OFFSET
        local = [(x - ox, y - oy, zz) for (x, y), zz in zip(verts, z)]
        uvs = [(x / tile, y / tile) for x, y in verts]
        out[mat] = (local, tris, uvs)
    return out


def write_block_nif(path, name, meshes, tex, pyn):
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, \
        PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR = pyn
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="BSFadeNode", root_name=name)
    cv, ct = [], []
    for mat, (verts, tris, uvs) in meshes.items():
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(mat, verts, tris, uvs, [(0.0, 0.0, 1.0)] * len(verts),
                                        props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        sp = shape.shader.properties
        sp.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\paving_{mat}.dds")
        shape.set_texture("Normal", f"{tex}\\paving_{mat}_n.dds")
        shape.set_texture("Specular", f"{tex}\\paving_{mat}_s.dds")
        sp.Spec_Str, sp.Glossiness = 1.0, 1.0
        shape.save_shader_attributes()
        base = len(cv)
        cv += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
        ct += [[a + base, b + base, c + base] for a, b, c in tris]
    physics = PhysicsProps(is_dynamic=False,
                           body_props_raw=bytes.fromhex("00ff003f003fcd3e01024c3deeff7f7f"),
                           collision_filter_info=1)
    packed = pack_shapes([CollisionShape(shape_type="compressed_mesh", name="collision",
                                         transform=None, verts=cv, faces=ct,
                                         convex_radius=0.0, children=[], physics=physics)])
    BSXFlags.New(nif, flags=130, parent=nif.root)
    coll = nif.root.add_collision(None, flags=128,
                                  collision_type=PynBufferTypes.bhkNPCollisionObjectBufType,
                                  body_id=0)
    bhkPhysicsSystem.New(nif, data=packed, parent=coll)
    nif.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    ap.add_argument("--refetch", action="store_true", help="download the OSM layout again")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR)

    out = out_dir(AREA)
    osm_path = out / "osm.json"
    if args.refetch or not osm_path.exists():
        print("Fetching the layout from OpenStreetMap...")
        fetch_osm(osm_path)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = Terrain(out)
    world = box(terrain.x0, terrain.y1 - terrain.cells[1] * CELL_UNITS,
                terrain.x0 + terrain.cells[0] * CELL_UNITS, terrain.y1)
    areas = {}
    for mat, poly in paved_areas(json.loads(osm_path.read_text()), to_utm).items():
        g = shapely.transform(poly, lambda p: np.column_stack(terrain.game(p[:, 0], p[:, 1])))
        areas[mat] = g.intersection(world)
        print(f"{mat}: {areas[mat].area * UNIT_M ** 2 / 1e4:.1f} ha")
    change = terrain.grade(areas)
    np.round(terrain.z / terrain.step).astype("<u2").tofile(out / "graded16.raw")
    write_dds_r32f(out / "graded.dds", (terrain.z / terrain.top).astype(np.float32))
    print(f"graded the ground under the paving: the most it moved is {change * UNIT_M:.2f} m")

    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    files = write_textures(tex_dir)
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    models, worst = [], 0.0
    cx0, cy0 = terrain.cell_x0, terrain.cell_y1 - terrain.cells[1] + 1
    for by in range(cy0, terrain.cell_y1 + 1, BLOCK):
        for bx in range(cx0, cx0 + terrain.cells[0], BLOCK):
            meshes = block_meshes(areas, terrain, bx, by)
            if not meshes:
                continue
            name = f"Paving_{bx}_{by}"
            path = mesh_dir / f"{name}.nif"
            write_block_nif(path, name, meshes, tex, pyn)
            files.append(path)
            allv = np.array([v for m in meshes.values() for v in m[0]])
            lo, hi = allv.min(axis=0), allv.max(axis=0)
            models.append({"name": name, "nif": f"{MOD_PATH}/{name}.nif".replace("/", "\\"),
                           "position": [bx * CELL_UNITS, by * CELL_UNITS, 0],
                           "cell": [bx, by],
                           "bounds": [int(math.floor(c)) for c in lo] + [int(math.ceil(c)) for c in hi],
                           "triangles": sum(len(m[1]) for m in meshes.values())})
    # How far the terrain pokes through between the mesh's grid lines, under the paving.
    for mat, g in areas.items():
        xs, ys = np.meshgrid(np.arange(terrain.nx) * POINT_UNITS + terrain.x0,
                             terrain.y1 - np.arange(terrain.ny) * POINT_UNITS)
        inside = shapely.contains_xy(g, xs, ys)
        if inside.any():
            gx = (np.floor((xs[inside] - terrain.x0) / GRID) * GRID) + terrain.x0
            gy = (np.floor((ys[inside] - terrain.x0) / GRID) * GRID) + terrain.x0
            tx, ty = (xs[inside] - gx) / GRID, (ys[inside] - gy) / GRID
            mesh_z = (terrain.at(gx, gy) * (1 - tx) * (1 - ty) + terrain.at(gx + GRID, gy) * tx * (1 - ty)
                      + terrain.at(gx, gy + GRID) * (1 - tx) * ty + terrain.at(gx + GRID, gy + GRID) * tx * ty)
            worst = max(worst, float((terrain.at(xs[inside], ys[inside]) - mesh_z).max()))
    (out / "paving.json").write_text(json.dumps(
        {"note": "place each model at its position (game units) with no rotation",
         "offset": OFFSET, "models": models}, indent=1))

    # The layout on the cell grid.
    S = 1 / 64
    W, H = int(terrain.cells[0] * CELL_UNITS * S), int(terrain.cells[1] * CELL_UNITS * S)
    img = Image.new("RGB", (W, H), (50, 70, 45))
    dr = ImageDraw.Draw(img)
    px = lambda x, y: ((x - terrain.x0) * S, (terrain.y1 - y) * S)
    for mat, col in (("asphalt", (60, 60, 60)), ("concrete", (170, 170, 160))):
        for p in getattr(areas[mat], "geoms", [areas[mat]]):
            dr.polygon([px(*q) for q in p.exterior.coords], fill=col)
            for hole in p.interiors:
                dr.polygon([px(*q) for q in hole.coords], fill=(50, 70, 45))
    for i in range(terrain.cells[0] + 1):
        dr.line([(i * CELL_UNITS * S, 0), (i * CELL_UNITS * S, H)], fill=(0, 0, 0) if i % BLOCK else (200, 60, 60))
    for j in range(terrain.cells[1] + 1):
        dr.line([(0, j * CELL_UNITS * S), (W, j * CELL_UNITS * S)], fill=(0, 0, 0) if j % BLOCK else (200, 60, 60))
    img.save(out / "paving.png")

    print(f"{len(models)} models, {sum(m['triangles'] for m in models)} triangles; terrain pokes "
          f"through the mesh by at most {worst - OFFSET:.1f} units (OFFSET {OFFSET} clears it if < 0)")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
