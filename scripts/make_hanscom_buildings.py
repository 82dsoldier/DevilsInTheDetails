"""Hanscom Field's buildings, as block-outs: the right footprints and heights, no detail.

    python scripts/make_hanscom_buildings.py [--install "<Fallout 4>/Data"] [--refetch]

Run make_hanscom_paving.py first (this grades the ground the same way, and reads its OSM
layout). Footprints are OpenStreetMap's (© OpenStreetMap contributors, ODbL), fetched once into
out/hanscom/osm_buildings.json.

The act's buildings (DESIGN.md, "Hanscom Field: the first act") are hollow shells to walk into:
walls WALL_T thick, a concrete floor, a flat roof, and openings in the wall that faces the
ramp (a hangar door, or a loading door and a man door). Each is one model, its origin at its
footprint's centre. Every other building on the base is a solid block for the skyline, its
height from OSM (or FLOORS_M a floor, or DEFAULT_H), gathered into one model per cell like the
paving. All of them have collision; walls run FOOTING below the ground.

Writes to out/hanscom/:
  mod/Meshes/DevilsInTheDetails/Hanscom/Bldg_<role>.nif, Blocks_<x>_<y>.nif
  mod/Textures/DevilsInTheDetails/Hanscom/bldg_<material>{,_n,_s}.dds
  buildings.json      each model: its file, where to place it, its bounds (as paving.json)
  buildings.png       the footprints on the paving, the act's buildings labelled
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
from shapely.geometry import Polygon, box
from PIL import Image, ImageDraw
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, ROOT, UNIT_M, out_dir                  # noqa: E402
from make_photo_overlay import load_pynifly                                   # noqa: E402
import make_c130_blockout as c130                                             # noqa: E402
import make_hanscom_paving as paving                                          # noqa: E402

AREA = "hanscom"
OSM_BBOX = (42.4500, -71.3200, 42.4900, -71.2550)
MOD_PATH = "DevilsInTheDetails/Hanscom"
WALL_T = 0.3            # metres
FOOTING = 2.0           # walls run this far below the floor
FLOORS_M = 3.5          # a floor's height, for buildings OSM gives only levels for
DEFAULT_H = 6.0         # buildings OSM gives nothing for

# The act's buildings, by their OSM name: (role, height m, openings on the wall facing the
# ramp: (width m, height m, where along the wall 0-1), or a fraction of the wall's length).
ROLES = {
    "Hangar 1715": ("DevilsHangar", 16.0, [("frac", 0.8, 11.0, 0.5)]),
    "Hanscom Aero Club": ("Recruiting", 12.0, [("frac", 0.7, 8.0, 0.55), (1.2, 2.2, 0.12)]),
    "East Coast Aero Club": ("JumpSchool", 12.0, [("frac", 0.7, 8.0, 0.5), (1.2, 2.2, 0.1)]),
    "1727": ("DerelictA", 12.0, [("frac", 0.7, 8.0, 0.5)]),
    "1730": ("DerelictB", 12.0, [("frac", 0.7, 8.0, 0.5)]),
    "1614": ("DRMO", 7.0, [(5.0, 5.0, 0.3), (5.0, 5.0, 0.55), (1.2, 2.2, 0.8)]),
}
TILE_M = {"siding": 3.0, "block": 4.0, "roof": 6.0, "floor": c130.TARMAC_SLAB}


# --- Textures -------------------------------------------------------------------------------
def tex_siding():
    """Corrugated steel siding, faded green-grey paint, rust streaks running down."""
    u, v = c130._uv()
    rib = np.cos(u * 2 * math.pi * 12)
    streak = np.clip(c130._smooth_noise(70, 0.02) * (1 - v) - 0.6, 0, 1)
    shade = 0.86 + 0.08 * rib + c130._noise(71, scale=0.04)
    rgb = np.array([112, 120, 108])[None, None, :] * shade[..., None]
    rgb = rgb * (1 - streak[..., None]) + np.array([120, 70, 40]) * streak[..., None]
    return rgb, rib * 0.5


def tex_block():
    """Painted concrete block, 16 x 8 in courses, sand-coloured as the base's buildings are."""
    u, v = c130._uv()
    rows = 4.0 / 0.2032                               # courses in a 4 m tile
    cu = (u * rows / 2 + 0.5 * (np.floor(v * rows) % 2)) % 1
    mortar = ((v * rows) % 1 < 0.06) | (cu < 0.03)
    shade = 0.9 + 0.05 * c130._smooth_noise(72, 0.05) + c130._noise(73, scale=0.04)
    rgb = np.array([196, 180, 150])[None, None, :] * shade[..., None]
    rgb[mortar] *= 0.8
    return rgb, mortar * -0.3


def tex_roof():
    """Tar and gravel roofing."""
    shade = 0.8 + 0.1 * c130._smooth_noise(74, 0.05) + c130._noise(75, scale=0.12)
    return np.array([80, 78, 74])[None, None, :] * shade[..., None], c130._noise(75, scale=0.4)


MATERIALS = {"siding": tex_siding, "block": tex_block, "roof": tex_roof, "floor": c130.tex_tarmac}
SPECULAR = {"siding": (0.2, 0.3), "block": (0.04, 0.15), "roof": (0.03, 0.1), "floor": (0.08, 0.2)}


def write_textures(tex_dir):
    files = []
    for name, make in MATERIALS.items():
        img, h = make()
        f = tex_dir / f"bldg_{name}.dds"
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(f, pixel_format="DXT1")
        fn = tex_dir / f"bldg_{name}_n.dds"
        Image.fromarray(np.clip(c130.normal_map(h), 0, 255).astype(np.uint8), "RGB").save(fn, pixel_format="DXT1")
        shine, smooth = SPECULAR[name]
        fs = tex_dir / f"bldg_{name}_s.dds"
        Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
        files += [f, fn, fs]
    return files


# --- Geometry -------------------------------------------------------------------------------
class Mesh:
    """Triangles in game units, per material."""

    def __init__(self):
        self.parts = {}

    def _p(self, mat):
        return self.parts.setdefault(mat, ([], [], [], []))   # verts, tris, uvs, normals

    def quad(self, mat, a, b, c, d, n, uv):
        """a b c d counter-clockwise seen from the normal's side; uv: their (u, v) in metres."""
        vs, ts, us, ns = self._p(mat)
        k = len(vs)
        tile = TILE_M[mat]
        vs += [a, b, c, d]
        us += [(p[0] / tile, p[1] / tile) for p in uv]
        ns += [n] * 4
        ts += [(k, k + 1, k + 2), (k, k + 2, k + 3)]

    def polygon(self, mat, poly, z, up):
        """A flat polygon (game units) at height z, facing up or down."""
        vs, ts, us, ns = self._p(mat)
        tile = TILE_M[mat] / UNIT_M
        for tri in shapely.constrained_delaunay_triangles(poly).geoms:
            ring = list(tri.exterior.coords)[:3]
            ccw = Polygon(ring).exterior.is_ccw
            if ccw != up:
                ring = ring[::-1]
            k = len(vs)
            vs += [(x, y, z) for x, y in ring]
            us += [(x / tile, y / tile) for x, y in ring]
            ns += [(0.0, 0.0, 1.0 if up else -1.0)] * 3
            ts.append((k, k + 1, k + 2))


def wall_box(m, mat, p0, p1, inward, z0, z1, t, openings=(), inner=True):
    """A wall slab along p0-p1 (game units), t thick toward `inward` (a unit vector), from z0 to
    z1, with openings (a, b, top): along-the-wall spans from p0, in game units, z0 to top."""
    L = math.dist(p0, p1)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    out_n = (-inward[0], -inward[1], 0.0)
    in_n = (inward[0], inward[1], 0.0)
    at = lambda s, off: (p0[0] + ux * s + inward[0] * off, p0[1] + uy * s + inward[1] * off)
    # Pieces of the face: (s0, s1, zlo, zhi) - full height between openings, lintels above them.
    pieces, s = [], -t
    for a, b, top in sorted(openings):
        pieces.append((s, a, z0, z1))
        pieces.append((a, b, top, z1))
        s = b
    pieces.append((s, L + t, z0, z1))
    for s0, s1, za, zb in pieces:
        if s1 - s0 < 1 or zb - za < 1:
            continue
        for off, n, flip in ((0.0, out_n, False), (t, in_n, True)):
            if off and not inner:
                continue
            q0, q1 = at(s0, off), at(s1, off)
            a, b, c, d = (*q0, za), (*q1, za), (*q1, zb), (*q0, zb)
            uv = [(s0 * UNIT_M, za * UNIT_M), (s1 * UNIT_M, za * UNIT_M),
                  (s1 * UNIT_M, zb * UNIT_M), (s0 * UNIT_M, zb * UNIT_M)]
            if flip:
                a, b, c, d = b, a, d, c
                uv = [uv[1], uv[0], uv[3], uv[2]]
            # Outer face: counter-clockwise seen from outside means p0 -> p1 along the bottom
            # when inward is to the left of travel; check and swap if not.
            if not flip and (ux * inward[1] - uy * inward[0]) < 0:
                a, b, c, d = b, a, d, c
                uv = [uv[1], uv[0], uv[3], uv[2]]
            if flip and (ux * inward[1] - uy * inward[0]) < 0:
                a, b, c, d = b, a, d, c
                uv = [uv[1], uv[0], uv[3], uv[2]]
            m.quad(mat, a, b, c, d, n, uv)
    # The opening's sides and head, so the wall reads as thick.
    for a, b, top in openings:
        for s_, sign in ((a, 1), (b, -1)):
            q0, q1 = at(s_, 0.0), at(s_, t)
            n = (ux * sign, uy * sign, 0.0)
            m.quad(mat, (*q0, z0), (*q1, z0), (*q1, top), (*q0, top), n,
                   [(0, z0 * UNIT_M), (t * UNIT_M, z0 * UNIT_M), (t * UNIT_M, top * UNIT_M), (0, top * UNIT_M)])
        qa0, qb0, qb1, qa1 = at(a, 0.0), at(b, 0.0), at(b, t), at(a, t)
        m.quad(mat, (*qa0, top), (*qb0, top), (*qb1, top), (*qa1, top), (0.0, 0.0, -1.0),
               [(a * UNIT_M, 0), (b * UNIT_M, 0), (b * UNIT_M, t * UNIT_M), (a * UNIT_M, t * UNIT_M)])


def fix_quads(m):
    """Wind every triangle to face its normal (the wall code's bookkeeping is easy to get wrong)."""
    for vs, ts, us, ns in m.parts.values():
        for i, (a, b, c) in enumerate(ts):
            pa, pb, pc = (np.array(vs[k]) for k in (a, b, c))
            if np.dot(np.cross(pb - pa, pc - pa), ns[a]) < 0:
                ts[i] = (a, c, b)


def footprint_ground(terrain, poly):
    pts = np.array(poly.exterior.coords)
    inside = [poly.representative_point().coords[0]]
    xs = np.concatenate([pts[:, 0], [p[0] for p in inside]])
    ys = np.concatenate([pts[:, 1], [p[1] for p in inside]])
    minx, miny, maxx, maxy = poly.bounds
    gx, gy = np.meshgrid(np.arange(minx, maxx, 256), np.arange(miny, maxy, 256))
    keep = shapely.contains_xy(poly, gx, gy)
    xs, ys = np.concatenate([xs, gx[keep]]), np.concatenate([ys, gy[keep]])
    z = terrain.at(xs, ys)
    return float(z.max()), float(z.min())


def ramp_edge(poly, ramp):
    """The footprint's edge facing the ramp: the longest of those nearest it."""
    pts = list(poly.exterior.coords)[:-1]
    best = None
    for i in range(len(pts)):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(p0, p1)
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        d = shapely.distance(shapely.Point(mid), ramp)
        score = d - L * 0.25
        if best is None or score < best[0]:
            best = (score, i)
    return best[1]


def hollow(m, poly, ground_top, ground_low, height, openings, mats, ramp):
    """The act's building: walls with openings on the ramp side, floor, roof."""
    poly = shapely.orient_polygons(poly)                # exterior counter-clockwise
    t = WALL_T / UNIT_M
    z_floor = ground_top + paving.OFFSET                 # level with the paving outside
    z0, z1 = ground_low - FOOTING / UNIT_M, z_floor + height / UNIT_M
    pts = list(poly.exterior.coords)[:-1]
    door = ramp_edge(poly, ramp)
    for i in range(len(pts)):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        inward = (-uy, ux)                              # left of travel, for a ccw outline
        ops = []
        if i == door:
            for o in openings:
                if o[0] == "frac":
                    w, h, at = o[1] * L, o[2] / UNIT_M, o[3]
                else:
                    w, h, at = o[0] / UNIT_M, o[1] / UNIT_M, o[2]
                c = at * L
                ops.append((max(t, c - w / 2), min(L - t, c + w / 2), z_floor + h))
        # The openings start at the floor: the wall below them, down to the footing, is solid.
        wall_box(m, mats["wall"], p0, p1, inward, z_floor, z1, t, ops)
        wall_box(m, mats["wall"], p0, p1, inward, z0, z_floor, t, ())
    inner = poly.buffer(-t, join_style="mitre")
    m.polygon("floor", inner, z_floor, True)
    m.polygon("roof", poly, z1 + 1, True)
    m.polygon(mats["wall"], inner, z1 - 1, False)       # the ceiling
    return z_floor


def solid(m, poly, ground_low, ground_top, height, mat):
    poly = shapely.orient_polygons(poly)
    z0, z1 = ground_low - FOOTING / UNIT_M, ground_top + height / UNIT_M
    pts = list(poly.exterior.coords)[:-1]
    for i in range(len(pts)):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(p0, p1)
        if L < 1:
            continue
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        wall_box(m, mat, p0, p1, (-uy, ux), z0, z1, 0.0, (), inner=False)
    m.polygon("roof", poly, z1, True)


def height_of(tags):
    try:
        return float(tags["height"])
    except (KeyError, ValueError):
        pass
    try:
        return float(tags["building:levels"]) * FLOORS_M
    except (KeyError, ValueError):
        return DEFAULT_H


def write_nif(path, name, m, origin, tex, pyn):
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, \
        PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR = pyn
    fix_quads(m)
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="BSFadeNode", root_name=name)
    cv, ct, allv = [], [], []
    ox, oy = origin
    for mat, (vs, ts, us, ns) in m.parts.items():
        if not ts:
            continue
        local = [(x - ox, y - oy, z) for x, y, z in vs]
        allv += local
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(mat, local, ts, us, ns, props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        sp = shape.shader.properties
        sp.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\bldg_{mat}.dds")
        shape.set_texture("Normal", f"{tex}\\bldg_{mat}_n.dds")
        shape.set_texture("Specular", f"{tex}\\bldg_{mat}_s.dds")
        sp.Spec_Str, sp.Glossiness = 1.0, 1.0
        shape.save_shader_attributes()
        base = len(cv)
        cv += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in local]
        ct += [[a + base, b + base, c + base] for a, b, c in ts]
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
    a = np.array(allv)
    return [int(math.floor(v)) for v in a.min(axis=0)] + [int(math.ceil(v)) for v in a.max(axis=0)]


def fetch(path):
    s, w, n, e = OSM_BBOX
    q = f'[out:json][timeout:90];way["building"]({s},{w},{n},{e});out geom tags;'
    r = requests.post(paving.OVERPASS, data={"data": q}, headers={"User-Agent": "map-tool/1.0"}, timeout=180)
    r.raise_for_status()
    path.write_text(r.text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    ap.add_argument("--refetch", action="store_true", help="download the OSM footprints again")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR)

    out = out_dir(AREA)
    path = out / "osm_buildings.json"
    if args.refetch or not path.exists():
        print("Fetching building footprints from OpenStreetMap...")
        fetch(path)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = paving.Terrain(out)
    world = box(terrain.x0, terrain.y1 - terrain.cells[1] * CELL_UNITS,
                terrain.x0 + terrain.cells[0] * CELL_UNITS, terrain.y1)
    areas = {}
    for mat, poly in paving.paved_areas(json.loads((out / "osm.json").read_text()), to_utm).items():
        g = shapely.transform(poly, lambda p: np.column_stack(terrain.game(p[:, 0], p[:, 1])))
        areas[mat] = g.intersection(world)
    assert set(paving.ACT_BUILDINGS) == set(ROLES)
    terrain.grade(areas, paving.act_footprints(out, terrain, to_utm))   # the paving's ground
    ramp = areas["concrete"]

    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    files = write_textures(tex_dir)
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    models, blocks, story = [], {}, []
    for el in json.loads(path.read_text())["elements"]:
        tags, geom = el.get("tags", {}), el.get("geometry")
        if "building" not in tags or not geom or len(geom) < 4:
            continue
        e, n = np.array([to_utm.transform(p["lon"], p["lat"]) for p in geom]).T
        poly = Polygon(np.column_stack(terrain.game(e, n))).buffer(0).simplify(0.2 / UNIT_M)
        if poly.geom_type != "Polygon" or poly.area * UNIT_M ** 2 < 8 or not world.contains(poly):
            continue
        top, low = footprint_ground(terrain, poly)
        role = ROLES.get(tags.get("name"))
        if role:
            name, h, ops = role
            m = Mesh()
            mat = "block" if name == "DRMO" else "siding"
            z_floor = hollow(m, poly, top, low, h, ops, {"wall": mat}, ramp)
            c = poly.centroid
            f = mesh_dir / f"Bldg_{name}.nif"
            bounds = write_nif(f, f"Bldg_{name}", m, (c.x, c.y), tex, pyn)
            files.append(f)
            models.append({"name": f"Bldg_{name}", "nif": f"{MOD_PATH}/Bldg_{name}.nif".replace("/", "\\"),
                           "position": [round(c.x, 1), round(c.y, 1), 0],
                           "cell": [int(c.x // CELL_UNITS), int(c.y // CELL_UNITS)],
                           "bounds": bounds, "floor_z": round(z_floor, 1), "osm_name": tags.get("name")})
            story.append((poly, name))
        else:
            c = poly.centroid
            key = (int(c.x // CELL_UNITS), int(c.y // CELL_UNITS))
            m = blocks.setdefault(key, Mesh())
            solid(m, poly, low, top, height_of(tags), "block")
    for (bx, by), m in blocks.items():
        name = f"Blocks_{bx}_{by}"
        f = mesh_dir / f"{name}.nif"
        bounds = write_nif(f, name, m, (bx * CELL_UNITS, by * CELL_UNITS), tex, pyn)
        files.append(f)
        models.append({"name": name, "nif": f"{MOD_PATH}/{name}.nif".replace("/", "\\"),
                       "position": [bx * CELL_UNITS, by * CELL_UNITS, 0], "cell": [bx, by],
                       "bounds": bounds})
    too_big = [m["name"] for m in models if max(abs(v) for v in m["bounds"]) > 32767]
    if too_big:
        raise SystemExit(f"bounds past 32,767 units: {too_big}")
    (out / "buildings.json").write_text(json.dumps(
        {"note": "place each model at its position (game units) with no rotation", "models": models}, indent=1))

    S = 1 / 48
    W, H = int(terrain.cells[0] * CELL_UNITS * S), int(terrain.cells[1] * CELL_UNITS * S)
    img = Image.new("RGB", (W, H), (50, 70, 45))
    dr = ImageDraw.Draw(img)
    px = lambda x, y: ((x - terrain.x0) * S, (terrain.y1 - y) * S)
    for mat, col in (("asphalt", (60, 60, 60)), ("concrete", (165, 165, 155))):
        for p in getattr(areas[mat], "geoms", [areas[mat]]):
            dr.polygon([px(*q) for q in p.exterior.coords], fill=col)
    for el in models:
        pass
    for poly, name in story:
        dr.polygon([px(*q) for q in poly.exterior.coords], fill=(200, 90, 60), outline=(0, 0, 0))
        c = poly.centroid
        dr.text(px(c.x, c.y), name, fill=(255, 255, 255))
    img.save(out / "buildings.png")
    print(f"{len(story)} act buildings, {len(blocks)} cells of other buildings "
          f"({sum(len(t) for m in blocks.values() for _, t, _, _ in m.parts.values())} triangles)")
    for mdl in models:
        if "floor_z" in mdl:
            print(f"  {mdl['name']:<18} {mdl['osm_name']:<22} cell {mdl['cell']}, floor z {mdl['floor_z']}")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
