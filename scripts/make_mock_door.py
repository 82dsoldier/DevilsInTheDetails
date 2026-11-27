"""Jump school's mock door at Hanscom: a sawdust pit out on the East Ramp in front of jump school
(the East Coast Aero Club hangar), with a mock C-130 fuselage standing in it on posts: a plywood
box the width of the real cabin, one paratroop door on the side facing the open pit, open at the
aft end with steps up to it. Recruits climb in, stand in the door, and step out onto the
sawdust (DESIGN.md, "Jump school's mock door"; the spot is the author's pick, 2026-11-25).

    python scripts/make_mock_door.py [--floor 1.0] [--out 17] [--install "<Fallout 4>/Data"]

--floor is the fuselage's floor height above the sawdust, in metres; --out is how far the pit's
centre stands out from jump school's door wall.

The model, in its own coordinates (metres; origin at the pit's centre on the ground, +y out
toward the ramp, away from the hangar; +x along the hangar's wall, the mock fuselage's aft
end): the pit's timber kerb and sawdust, PIT_L x PIT_W; the fuselage toward the hangar side,
its door in its +y wall near the aft end, so a man steps out toward the open pit. Everything
has collision except the steps, which have a ramp under them instead (DESIGN.md: stairs built
of step boxes stop the player).

Writes:
  out/hanscom/mod/Meshes/DevilsInTheDetails/Hanscom/MockDoor.nif
  out/hanscom/mod/Textures/DevilsInTheDetails/Hanscom/mock_<material>{,_n,_s}.dds
  out/hanscom/mockdoor.json   where to place it (game units, heading), and the door's sill
                              and the landing spot, for the plugin step (esp_mock_door.py)
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import UNIT_M, out_dir                                    # noqa: E402
from make_photo_overlay import load_pynifly                                   # noqa: E402
from ddsutil import save_dds                                                  # noqa: E402
import make_c130_blockout as c130                                             # noqa: E402
import make_hanscom_paving as paving                                          # noqa: E402

AREA = "hanscom"
MOD_PATH = "DevilsInTheDetails/Hanscom"
BUILDING = "East Coast Aero Club"         # jump school

PIT_L, PIT_W = 16.0, 10.0                 # the pit, inside its kerb
KERB_W, KERB_H, KERB_SINK = 0.2, 0.3, 0.1  # 8 x 12 in timbers, sunk a little into the ramp
FILL = 0.22                               # the sawdust's top, above the ramp
FUSE_L = 6.0                              # the mock fuselage's length
FUSE_W = c130.FLOOR_W                     # the real cabin's floor width
FUSE_H = 2.45                             # floor to roof inside: a flat-topped box, not the
                                          # real arch, but room for power armor
PLY = 0.06                                # wall thickness
DECK_T = 0.12
FUSE_INSET = 0.5                          # from the kerb on the hangar side
FUSE_AFT = -1.0                           # x of the open aft end
DOOR_W, DOOR_H = c130.DOOR_W, c130.DOOR_H  # the real paratroop door, 36 x 72 in
DOOR_AFT = c130.DOOR_AFT + 0.25            # its aft edge from the aft end (the end wall's post too)
STEP_W, STEP_RUN = 1.4, 0.32              # the steps up to the aft end
POST = 0.12
LAND_OUT = 1.5                            # the landing spot, out from the door's sill

TEX = 256


# --- Textures (each one tile, a metre square unless said) ------------------------------------
def _uv():
    v, u = np.mgrid[0:TEX, 0:TEX] / TEX
    return u, v


def _blur(a, k=2):
    for _ in range(k):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
    return a


def tex_sawdust():
    """Pale sawdust and wood chips, raked and trodden: speckles, a few darker chips, low hollows."""
    rng = np.random.default_rng(504)
    fine = rng.normal(0, 1, (TEX, TEX))
    lumps = _blur(rng.normal(0, 1, (TEX, TEX)), 6) * 6
    chips = (_blur((rng.random((TEX, TEX)) > 0.985).astype(float), 1) > 0.25).astype(float)
    shade = 0.92 + 0.05 * fine + 0.06 * lumps - 0.18 * chips
    rgb = np.array([204, 176, 128])[None, None, :] * shade[..., None]
    rgb[..., 2] -= 10 * chips
    return rgb, 0.4 * lumps + 0.3 * chips + 0.1 * fine


def _soft(seed, size):
    """Smooth noise with features about `size` pixels across, tiling, scaled to about 1."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.normal(0, 1, (TEX, TEX)))
    k = np.fft.fftfreq(TEX)
    r2 = k[:, None] ** 2 + k[None, :] ** 2
    a = np.real(np.fft.ifft2(f * np.exp(-r2 * (size / 2.5) ** 2 * 2 * np.pi ** 2)))
    return a / a.std()


def _streaks(seed, axis):
    """Faint, uneven wood grain: noise smeared a long way along the grain (axis 1: lines run
    along u; axis 0: along v) and a little across it, scaled to about 1. Tiles. Not regular
    stripes: the first texture's sine-wave grain was too strong and too even (the author,
    2026-11-27)."""
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 1, (TEX, TEX))
    for _ in range(3):                          # a box blur ~60 px long along the grain
        a = sum(np.roll(a, k, axis) for k in range(-10, 11)) / 21
    a = (a + np.roll(a, 1, 1 - axis) + np.roll(a, -1, 1 - axis)) / 3
    return a / a.std()


def tex_timber():
    """Weathered timber: grey-brown, a faint grain along u, a few fine checks (splits)."""
    u, v = _uv()
    rng = np.random.default_rng(1504)
    grain = _streaks(1505, 1)
    checks = np.zeros((TEX, TEX))
    for _ in range(3):
        y0, x0, ln = rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0.1, 0.35)
        checks += (np.abs(v - y0) < 0.003) * (((u - x0) % 1) < ln)
    blotch = _soft(1506, 50)
    shade = 0.86 + 0.02 * grain + 0.03 * blotch + 0.015 * rng.normal(0, 1, (TEX, TEX)) - 0.08 * np.clip(checks, 0, 1)
    rgb = np.array([128, 112, 92])[None, None, :] * shade[..., None]
    return rgb, 0.03 * grain - 0.3 * np.clip(checks, 0, 1)


def tex_plywood():
    """Plywood painted olive drab, the paint a little uneven; the grain barely shows."""
    rng = np.random.default_rng(82)
    grain = _streaks(83, 1)
    wear = np.zeros((TEX, TEX))       # no worn spots: one tile's spots repeat in a grid down a wall
    paint = np.array([86, 90, 62], float)[None, None, :] * (0.95 + 0.008 * grain + 0.02 * _soft(85, 50) + 0.008 * rng.normal(0, 1, (TEX, TEX)))[..., None]
    wood = np.array([160, 134, 98], float)[None, None, :] * (0.92 + 0.025 * grain)[..., None]
    rgb = paint * (1 - wear[..., None]) + wood * wear[..., None]
    return rgb, 0.01 * grain - 0.2 * wear


def tex_deck():
    """The fuselage's floor: plywood painted dark grey, scuffed pale by boots."""
    rng = np.random.default_rng(130)
    grain = _streaks(131, 0)
    scuff = np.clip((_soft(132, 60) - 0.3) * 0.5, 0, 1)          # broad, soft
    shade = 0.9 + 0.008 * grain + 0.15 * scuff
    rgb = np.array([74, 74, 70])[None, None, :] * shade[..., None]
    return rgb, 0.01 * grain


MATERIALS = {"sawdust": (tex_sawdust, {}), "timber": (tex_timber, {}),
             "plywood": (tex_plywood, {"double_sided": True}), "deck": (tex_deck, {})}
SPECULAR = {"sawdust": (0.02, 0.05), "timber": (0.03, 0.1), "plywood": (0.06, 0.2), "deck": (0.05, 0.2)}


# How far the normal maps tilt the surface: the 95th percentile, degrees. Unscaled, the height
# maps tilted it 55 to 89 degrees, light catching on ridges everywhere (the walls and the steps'
# fronts looked "gnarly", the author, 2026-11-27).
BUMP_DEG = {"sawdust": 15.0, "timber": 6.0, "plywood": 2.5, "deck": 3.0}


def gentle(h, deg):
    """The height map scaled so its normal map tilts the surface `deg` (95th percentile)."""
    def tilt(k):
        nm = c130.normal_map(h * k) / 255 * 2 - 1
        return np.percentile(np.degrees(np.arccos(np.clip(nm[..., 2], -1, 1))), 95)
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if tilt(mid) < deg else (lo, mid)
    return h * lo


def write_textures(tex_dir):
    files = []
    for name, (make, _) in MATERIALS.items():
        img, h = make()
        f = tex_dir / f"mock_{name}.dds"
        save_dds(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB"), f)
        fn = tex_dir / f"mock_{name}_n.dds"
        save_dds(Image.fromarray(np.clip(c130.normal_map(gentle(h, BUMP_DEG[name])), 0, 255).astype(np.uint8), "RGB"), fn)
        shine, smooth = SPECULAR[name]
        fs = tex_dir / f"mock_{name}_s.dds"
        Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
        files += [f, fn, fs]
    return files


# --- The model ------------------------------------------------------------------------------
def fuselage_frame(floor):
    """(x0, x1, y0, y1, deck top z) of the fuselage."""
    y0 = -PIT_W / 2 + FUSE_INSET
    return FUSE_AFT - FUSE_L, FUSE_AFT, y0, y0 + FUSE_W, FILL + floor


def door_span():
    """The doorway along x: (forward edge, aft edge)."""
    b = FUSE_AFT - DOOR_AFT
    return b - DOOR_W, b


def parts(floor):
    M = c130.Mesh
    pit, kerb, ply, deck, steps, ramp = M(), M(), M(), M(), M(), M()
    # The sawdust: a grid, gently heaped (higher toward the middle, raked hollows), its edges
    # tucked under the kerb.
    n, m = int(PIT_L / 0.5), int(PIT_W / 0.5)
    rng = np.random.default_rng(34)
    bump = rng.normal(0, 0.012, (n + 1, m + 1))
    grid = {}
    for i in range(n + 1):
        for j in range(m + 1):
            x, y = -PIT_L / 2 + PIT_L * i / n, -PIT_W / 2 + PIT_W * j / m
            edge = min(i, n - i, j, m - j)
            z = FILL + (0.04 * min(edge, 4) / 4 + bump[i, j] if edge else -0.02)
            grid[i, j] = pit.vert((x, y, z), (0, 0, 1), (x, y))
    for i in range(n):
        for j in range(m):
            pit.quad(grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1])
    # The kerb, round the outside.
    L, W, t = PIT_L / 2, PIT_W / 2, KERB_W
    for x0, y0, x1, y1 in ((-L - t, -W - t, L + t, -W), (-L - t, W, L + t, W + t),
                           (-L - t, -W, -L, W), (L, -W, L + t, W)):
        kerb.box(x0, y0, -KERB_SINK, x1, y1, KERB_H, "tnsew")
    # The fuselage.
    fx0, fx1, fy0, fy1, dz = fuselage_frame(floor)
    top = dz + FUSE_H
    deck.box(fx0, fy0, dz - DECK_T, fx1, fy1, dz, "tbnsew", tile=1.22)
    for x in (fx0 + POST / 2, (fx0 + fx1) / 2, fx1 - POST / 2):          # posts into the sawdust
        for y in (fy0 + POST / 2, fy1 - POST / 2):
            kerb.box(x - POST / 2, y - POST / 2, 0.0, x + POST / 2, y + POST / 2, dz - DECK_T, "nsew")
    da, db = door_span()
    # The hangar-side wall, the forward end, the roof; the door wall in three pieces round the
    # doorway (its sill the deck), with a post at the aft end.
    ply.box(fx0, fy0, dz, fx1, fy0 + PLY, top, "tbnsew", tile=1.22)
    ply.box(fx0, fy0, dz, fx0 + PLY, fy1, top, "tbnsew", tile=1.22)
    ply.box(fx0, fy0, top, fx1, fy1, top + PLY, "tbnsew", tile=1.22)
    ply.box(fx0, fy1 - PLY, dz, da, fy1, top, "tbnsew", tile=1.22)
    ply.box(db, fy1 - PLY, dz, fx1, fy1, top, "tbnsew", tile=1.22)
    ply.box(da, fy1 - PLY, dz + DOOR_H, db, fy1, top, "tbnsew", tile=1.22)
    # Steps up to the open aft end, centred on the fuselage: treads for looks, a ramp to walk on.
    rise = dz
    k = max(2, round(rise / 0.2))
    cy = (fy0 + fy1) / 2
    for i in range(k):
        z = rise * (k - i) / k
        steps.box(fx1 + i * STEP_RUN, cy - STEP_W / 2, 0.0, fx1 + (i + 1) * STEP_RUN, cy + STEP_W / 2, z, "tnsew")
    run = k * STEP_RUN
    a = [ramp.vert(p, (0, 0, 1)) for p in ((fx1, cy - STEP_W / 2, dz), (fx1, cy + STEP_W / 2, dz),
                                             (fx1 + run, cy + STEP_W / 2, FILL), (fx1 + run, cy - STEP_W / 2, FILL))]
    ramp.quad(*a)
    built = {"sawdust": ("sawdust", True, pit), "kerb": ("timber", True, kerb),
             "fuselage": ("plywood", True, ply), "deck": ("deck", True, deck),
             "steps": ("timber", False, steps), "stepramp": (None, True, ramp)}
    return built, {"deck_z": dz, "door": ((da + db) / 2, fy1), "steps_foot": (fx1 + run, cy),
                   "landing": ((da + db) / 2, fy1 + LAND_OUT)}


# --- Where it goes ----------------------------------------------------------------------------
def placement(out_m):
    """The pit's centre (game units) and heading: out from jump school's door wall (the side
    facing the ramp) by out_m, centred on it; +y of the model out from the wall."""
    out = out_dir(AREA)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = paving.Terrain(out)
    el = [e for e in json.loads((out / "osm_buildings.json").read_text())["elements"]
          if e.get("tags", {}).get("name") == BUILDING and "building" in e["tags"]][0]
    e, n = np.array([to_utm.transform(p["lon"], p["lat"]) for p in el["geometry"]]).T
    poly = Polygon(np.column_stack(terrain.game(e, n))).buffer(0)
    pts = list(poly.exterior.coords)[:-1]
    c = poly.centroid
    best = None
    for p0, p1 in zip(pts, pts[1:] + pts[:1]):
        L = math.dist(p0, p1)
        if L * UNIT_M < 10:
            continue
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        nx, ny = uy, -ux
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        if (mx - c.x) * nx + (my - c.y) * ny < 0:
            nx, ny = -nx, -ny
        if best is None or ny > best[0]:                                 # the wall facing north
            best = (ny, mx, my, nx, ny, L)
    _, mx, my, nx, ny, L = best
    d = out_m / UNIT_M
    heading = math.degrees(math.atan2(nx, ny))      # the game turns local +y to (sin h, cos h)
    return mx + nx * d, my + ny * d, heading, L * UNIT_M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=1.0, help="fuselage floor above the sawdust, metres")
    ap.add_argument("--out", type=float, default=17.0, help="pit centre out from jump school's wall, metres")
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4)

    out = out_dir(AREA)
    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    files = write_textures(tex_dir)
    tex = "textures\\" + MOD_PATH.replace("/", "\\")
    s = 1 / UNIT_M
    built, spots = parts(args.floor)
    nif = mesh_dir / "MockDoor.nif"
    c130.write_nif(nif, "MockDoor", built, s, tex, pyn, prefix="mock", materials=MATERIALS)
    files.append(nif)
    allv = np.array([v for _, _, m in built.values() for v in m.verts]) * s
    bounds = [int(math.floor(v)) for v in allv.min(axis=0)] + [int(math.ceil(v)) for v in allv.max(axis=0)]
    # The doorway's activator (DevilsMockDoorExit, its script DevilsMockDoor): an invisible slab
    # across the doorway, just inside the wall, in the same frame, so it's placed where the
    # mock door is. Collision only: the crosshair finds it, and it keeps a man without a rig
    # from walking out (the doorway's the real size; power armor won't fit through anyway).
    da, db = door_span()
    _, _, _, fy1, dz = fuselage_frame(args.floor)
    slab = c130.Mesh()
    slab.box(da, fy1 - PLY - 0.12, dz, db, fy1 - PLY - 0.02, dz + DOOR_H, "tbnsew")
    exit_nif = mesh_dir / "MockDoorExit.nif"
    c130.write_nif(exit_nif, "MockDoorExit", {"activation": (None, True, slab)}, s, tex, pyn,
                   prefix="mock", materials=MATERIALS)
    files.append(exit_nif)
    sv = np.array(slab.verts) * s
    exit_bounds = [int(math.floor(v)) for v in sv.min(axis=0)] + [int(math.ceil(v)) for v in sv.max(axis=0)]

    x, y, heading, wall = placement(args.out)
    h = math.radians(heading)

    def world(px, py):            # model metres -> world units (the game's Rz(-heading))
        px, py = px * s, py * s
        return (x + px * math.cos(h) + py * math.sin(h), y - px * math.sin(h) + py * math.cos(h))

    info = {"note": "MockDoor.nif at position (z: the ground there) and heading; spots are world x, y "
                    "and their height above the model's origin",
            "nif": f"{MOD_PATH}/MockDoor.nif".replace("/", "\\"), "position": [round(x, 1), round(y, 1)],
            "heading": round(heading, 2), "bounds": bounds,
            "exit_nif": f"{MOD_PATH}/MockDoorExit.nif".replace("/", "\\"), "exit_bounds": exit_bounds,
            "spots": {"door_sill": [*map(lambda v: round(v, 1), world(*spots["door"])), round(spots["deck_z"] * s, 1)],
                      "landing": [*map(lambda v: round(v, 1), world(*spots["landing"])), round(FILL * s, 1)],
                      "steps_foot": [*map(lambda v: round(v, 1), world(*spots["steps_foot"])), round(FILL * s, 1)]}}
    (out / "mockdoor.json").write_text(json.dumps(info, indent=1))
    tris = sum(len(m.tris) for _, _, m in built.values())
    print(f"{nif.relative_to(out.parent.parent)}: {tris} triangles, bounds {bounds}")
    print(f"  at {x:.0f}, {y:.0f}, heading {heading:.1f} ({args.out} m out from jump school's "
          f"{wall:.0f} m door wall); floor {args.floor} m above the sawdust")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
