"""The C-130's cargo compartment, rigged for a jump: the right size and shape, with its main
structure and textures made here in code (from the author's reference photos). Not final art,
but it reads as the inside of a Herc.

    python scripts/make_c130_blockout.py [--length 15] [--scale 1.0] [--install "<Fallout 4>/Data"]

The cabin, in its own coordinates (metres; +y runs forward toward the flight deck, +x to the
right (starboard), the cargo floor at z 0, the origin at the middle of the floor between the
forward bulkhead and the ramp hinge):
  hull          seen from inside: the side walls bulge gently outward as they rise, then round
                over into an arched ceiling, lined with quilted insulation blankets; the closed
                ramp (RAMP_L) aft
  frames        the fuselage frames, every 20 in, curving up the walls and over the ceiling
  floor         dark aluminium with tie-down rings; a roller conveyor down each aisle
  troop seats   four rows: red seat pans on aluminium legs, with red webbing nets for backs
                (on the side walls, hung from a tube rail; down the centerline, back to back
                between stanchions that run floor to ceiling)
  doors         one paratroop doorway in each side wall, just forward of the ramp hinge, open
                for the jump (the doors themselves are C130_Door.nif, the activator); round red
                and green jump lights forward of each
  portholes     round windows down each side
  overhead      two air ducts down the ceiling, conduits along the upper walls, dome lights
  anchor cables one each side, overhead, running aft to the doors
  forward end   the bulkhead, panelled, with steps up to the flight deck on the left (port) side
The hull, floor, seats, centre backrests and steps have collision; the rest is for looks.

--length is the cargo floor's length (the true C-130H is 12.2 m; the author found that too short
in game, so the default is longer). --scale makes everything bigger, if it's too tight to move
through in power armor.

Writes to out/c130/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Aircraft/C130_Blockout.nif, C130_Door.nif
  Textures/DevilsInTheDetails/Aircraft/c130_<material>.dds, _n.dds (normal), _s.dds (specular)
The cabin keeps the name C130_Blockout.nif so references placed in the Creation Kit still find it.
"""
import argparse
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, UNIT_M, out_dir                  # noqa: E402
from make_photo_overlay import load_pynifly                      # noqa: E402
from ddsutil import save_dds                                      # noqa: E402

# Size, metres (C-130H cargo compartment, except the length).
DEFAULT_LENGTH = 15.0          # the true 12.2 m (40 ft) felt short in game
FLOOR_W = 3.12                 # 10 ft 3 in at the floor
CABIN_H = 2.74                 # 9 ft at the centreline
WALL_TOP = 1.75                # where the side wall stops rising and rounds into the ceiling
BULGE = 0.12                   # how far each wall bows out between the floor and WALL_TOP
RAMP_L = 3.7                   # the closed ramp, aft of the hinge (the true 3 m, stretched like the cabin)
RAMP_ANGLE = 25.0              # degrees the closed ramp rises aft (data/reference/ramp.jpg)
AFT_WIDTH = 0.85               # the tail's width at the ramp's end, against the cabin's
RAMP_STOP_HEADROOM = 2.3       # an invisible wall across the ramp where headroom falls to this
AFT_HEIGHT = 0.08             # floor to ceiling at the ramp's end: the ramp meets the sloping cargo door, no end wall
DOOR_W, DOOR_H, DOOR_R = 0.91, 1.83, 0.15   # paratroop doors, 36 x 72 in; corner radius
DOOR_AFT = 0.15                # door's aft edge, forward of the ramp hinge
PORTHOLE_D, PORTHOLE_Z = 0.30, 1.45         # diameter, centre height
PORTHOLES = 6                  # each side, between the doors and the forward bulkhead
SEAT_W, SEAT_D, SEAT_Z = 0.52, 0.40, 0.45   # one troop seat: width, depth, height
SEAT_AFT_GAP = 0.9             # clear floor between the doors and the seats
CENTER_BACK_W = 0.10           # the gap between the centerline rows' seat pans
WALL_NET_TOP = 1.30            # the side seats' webbing hangs from a rail this high
CENTER_NET_TOP = 1.15          # the centerline seats' shared webbing, up to its rail
STANCHION_PITCH = 2.6          # centerline stanchions, floor to ceiling
CABLE_Z, CABLE_X, CABLE_D = 2.25, 0.75, 0.03   # anchor cables
STEPS_W, STEPS_L, STEPS_H = 0.8, 1.0, 1.0   # up to the flight deck, port side forward
LIGHT_D = 0.12                 # jump light diameter
FRAME_PITCH = 0.508            # fuselage frames, 20 in apart
FRAME_W, FRAME_DEPTH = 0.07, 0.035          # a frame's width, and how far it stands proud of the blankets
DUCT_X, DUCT_Z, DUCT_R = 0.35, 2.55, 0.10   # the two overhead air ducts
DOME_Z, DOME_PITCH, DOME_D = 2.3, 2.5, 0.18 # dome lights, high on each wall
ROLLER_PITCH, ROLLER_R = 0.254, 0.025       # roller conveyor, one down each aisle
# Cargo forward (DESIGN.md, "The stick"): pallets from the Boston run, the seats forward of the
# stick folded up against the walls behind them.
PALLETS = 3
PALLET_L, PALLET_W, PALLET_T = 2.235, 2.743, 0.057   # 463L: 88 x 108 x 2.25 in, the 108 across
PALLET_GAP = 0.10              # between pallets
PALLET_FWD_GAP = 0.15          # the last one short of the flight deck steps
SEAT_FWD_GAP = 0.45            # clear floor between the last seat down and the first pallet
LOAD_H = 1.55                  # each load's height off the pallet: under the walls' curve
NET_PITCH = 0.40               # the cargo net's squares
NET_STRAP = 0.045
ARC_STEPS, WALL_STEPS, ROUND_STEPS = 12, 6, 24
# The open doorway's top: the arch's first profile point, 1.88 m, near enough the door's 1.83 m
# plus its sill.
DOOR_TOP = WALL_TOP + (CABIN_H - WALL_TOP) * math.sin(math.pi / 2 / ARC_STEPS) + 1e-6
JAMB = 0.12                    # the hull's thickness, shown at the doorway's edges

MOD_PATH = "DevilsInTheDetails/Aircraft"
TEX_SIZE = 256


# --- Textures ----------------------------------------------------------------------------
# Each material: an RGB(A) image and a height map (for its normal map), made from numpy. A tile
# is one texture repeat; the meshes' UVs are set so a tile is the size given here.

def _uv(n=TEX_SIZE):
    v, u = np.mgrid[0:n, 0:n] / n
    return u, v


def _noise(seed, n=TEX_SIZE, scale=1.0):
    rng = np.random.default_rng(seed)
    return rng.normal(0, scale, (n, n))


def _flat(rgb):
    return lambda: (np.broadcast_to(np.array(rgb, float), (TEX_SIZE, TEX_SIZE, 3)).copy(), None)


def tex_quilt():
    """Insulation blanket, one tile per frame bay (FRAME_PITCH wide, 0.5 m tall): a puffy
    pillow, pale khaki-grey, with diagonal quilting stitches."""
    u, v = _uv()
    h = np.sqrt(np.clip(np.sin(np.pi * u) * np.sin(np.pi * v), 0, 1))
    d = np.minimum(np.abs(((u + v) * 2) % 1 - 0.5), np.abs(((u - v) * 2) % 1 - 0.5))
    stitch = np.exp(-((0.5 - d) / 0.025) ** 2)
    h = h - 0.25 * stitch
    # Shading baked in, so the pillows read even in flat light: dark seams round each pillow and
    # along the stitches, crowns lit a little from above.
    shade = (0.5 + 0.5 * np.clip(h, 0, 1) ** 0.7) * (1 - 0.25 * stitch)
    shade *= 1 + 0.12 * (0.5 - v) * np.clip(h, 0, 1)
    shade += _noise(1, scale=0.015)
    rgb = np.array([196, 196, 176])[None, None, :] * shade[..., None]
    return rgb, h


def tex_floor():
    """Cargo floor, one tile 1.016 m square: dark aluminium with a recessed tie-down ring in the
    middle and black anti-skid slots."""
    u, v = _uv()
    rgb = np.ones((TEX_SIZE, TEX_SIZE, 3)) * np.array([66, 68, 68]) * (1 + _noise(2, scale=0.04))[..., None]
    h = np.zeros((TEX_SIZE, TEX_SIZE))
    r = np.hypot(u - 0.5, v - 0.5) * 1.016                 # metres from the tile's centre
    ring = (r > 0.032) & (r < 0.05)
    cup = r <= 0.05
    rgb[cup] = [40, 40, 40]
    rgb[ring] = [160, 160, 155]
    h[cup] -= 0.5
    h[ring] += 0.8
    for cv in (0.18, 0.32, 0.68, 0.82):                     # slots along the tile, across it
        s = (np.abs(v - cv) * 1.016 < 0.018) & (np.abs(u - 0.5) * 1.016 < 0.07)
        rgb[s] = [22, 22, 22]
        h[s] -= 0.6
    seam = (u < 0.006) | (u > 0.994)
    rgb[seam] *= 0.6
    h[seam] -= 0.4
    return rgb, h


def tex_fabric():
    """Seat pans, one tile per seat: red-maroon nylon, a fine weave, a seam between seats."""
    u, v = _uv()
    weave = 0.5 + 0.5 * np.sin(u * TEX_SIZE * np.pi / 2) * np.sin(v * TEX_SIZE * np.pi / 2)
    seam = np.exp(-(np.minimum(u, 1 - u) / 0.015) ** 2)
    shade = (0.88 + 0.12 * weave + _noise(3, scale=0.03)) * (1 - 0.45 * seam)
    return np.array([150, 30, 32])[None, None, :] * shade[..., None], weave * 0.004 - seam * 0.02


def _smooth_noise(seed, cutoff):
    """Tileable noise with features about 1/cutoff of the tile across, unit spread."""
    f = np.fft.fft2(_noise(seed))
    fy = np.fft.fftfreq(TEX_SIZE)[:, None]
    fx = np.fft.fftfreq(TEX_SIZE)[None, :]
    r = np.real(np.fft.ifft2(f * np.exp(-(fx ** 2 + fy ** 2) / (2 * cutoff ** 2))))
    return r / r.std()


def tex_static_line():
    """Static line webbing, one tile per 25 cm along it (u), its width across (v): yellow nylon,
    a tight weave across the strap, grimy and stained from use, one stitch line along it
    (data/reference/1_3b9c...jpg)."""
    u, v = _uv()
    ribs = 0.5 + 0.5 * np.sin(2 * np.pi * u * 64)
    twill = 0.5 + 0.5 * np.sin(2 * np.pi * (u * 64 + v * 8))
    weave = 0.6 * ribs + 0.4 * twill
    grime = np.clip(0.5 + 0.35 * _smooth_noise(7, 0.02), 0, 1)
    stains = np.clip(_smooth_noise(8, 0.06) - 1.0, 0, 1)
    edge = np.exp(-(np.minimum(v, 1 - v) / 0.06) ** 2)
    stitch = np.exp(-((v - 0.80) / 0.02) ** 2) * (((u * 32) % 1) < 0.65)
    shade = (0.84 + 0.16 * weave) * (1 - 0.35 * grime) * (1 - 0.4 * stains) * (1 - 0.3 * edge)
    shade += _noise(9, scale=0.02)
    rgb = np.array([218, 178, 42])[None, None, :] * shade[..., None]
    rgb = rgb * (1 - stitch[..., None]) + np.array([60, 66, 36])[None, None, :] * stitch[..., None]
    return rgb, weave * 0.003 - stitch * 0.008 - edge * 0.004


def tex_nylon(base=(66, 70, 50), seed=20, weave_n=96):
    """Parachute packs, one tile 25 cm square: olive drab nylon duck, a fine weave, a little worn
    (data/reference/1_958e...jpg, T-10R...png). Plain: big grime blotches read as camouflage in
    the game (the author)."""
    def make():
        u, v = _uv()
        weave = 0.5 + 0.5 * np.sin(2 * np.pi * u * weave_n) * np.sin(2 * np.pi * v * weave_n)
        wear = _smooth_noise(seed, 0.08)
        shade = (0.92 + 0.08 * weave) * (1 + 0.04 * wear) + _noise(seed + 2, scale=0.015)
        return np.array(base)[None, None, :] * shade[..., None], weave * 0.002
    return make


def tex_weapons_case():
    """The M1950 weapons case, one tile 20 cm square: pale grey-olive canvas quilted in 10 cm
    squares, the padding puffed between the stitching (data/reference/1_bacd...jpg)."""
    u, v = _uv()
    fu, fv = (u * 2) % 1, (v * 2) % 1
    puff = np.sqrt(np.clip(np.sin(np.pi * fu) * np.sin(np.pi * fv), 0, 1))
    seam = np.exp(-(np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) / 0.02) ** 2)
    weave = 0.5 + 0.5 * np.sin(2 * np.pi * u * 80) * np.sin(2 * np.pi * v * 80)
    shade = (0.8 + 0.2 * puff) * (1 - 0.25 * seam) * (0.95 + 0.05 * weave) + _noise(26, scale=0.015)
    return np.array([128, 130, 108])[None, None, :] * shade[..., None], puff * 0.25 - seam * 0.05


def tex_od_webbing():
    """Harness webbing, one tile 25 cm along (u) by its width (v): olive drab nylon, ribbed along,
    stitched down both edges."""
    u, v = _uv()
    ribs = 0.5 + 0.5 * np.sin(2 * np.pi * v * 24)
    stitch = (np.exp(-((v - 0.12) / 0.02) ** 2) + np.exp(-((v - 0.88) / 0.02) ** 2)) * (((u * 40) % 1) < 0.6)
    grime = np.clip(0.5 + 0.3 * _smooth_noise(23, 0.03), 0, 1)
    shade = (0.85 + 0.15 * ribs) * (1 - 0.25 * grime) * (1 - 0.3 * stitch) + _noise(24, scale=0.02)
    return np.array([70, 76, 50])[None, None, :] * shade[..., None], ribs * 0.003 - stitch * 0.004


def tex_tarmac():
    """The apron, one tile a 7.5 m concrete slab: pale weathered concrete, a dark sealed joint
    round it, tyre and oil stains."""
    u, v = _uv()
    joint = (np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) * TARMAC_SLAB) < 0.02
    patch = _smooth_noise(40, 0.04)
    stain = np.clip(_smooth_noise(41, 0.02) - 1.2, 0, 1)
    grit = _noise(42, scale=0.05)
    shade = (0.92 + 0.05 * patch + grit) * (1 - 0.35 * stain)
    rgb = np.array([150, 150, 144])[None, None, :] * shade[..., None]
    rgb[joint] = [52, 52, 50]
    return rgb, grit * 0.2 - joint * 0.4


def tex_webbing():
    """Webbing net, one tile per seat (SEAT_W wide, the net's full height): red straps hanging
    from the rail, crossed by horizontal bands; transparent between them."""
    u, v = _uv()
    # Five straps across a seat (about 10 cm apart), seven bands down the net: 10 cm squares,
    # straps about 3.5 cm wide.
    vert = np.abs(((u * 5) % 1) - 0.5) < 0.17
    horiz = np.abs(((v * 7) % 1) - 0.5) < 0.15
    strap = vert | horiz
    edge = vert & ~(np.abs(((u * 5) % 1) - 0.5) < 0.12)
    rgb = np.ones((TEX_SIZE, TEX_SIZE, 3)) * np.array([196, 28, 30])
    rgb[edge] *= 0.75
    rgb *= (1 + _noise(4, scale=0.03))[..., None]
    alpha = np.where(strap, 255, 0)
    return np.dstack([rgb, alpha]), strap.astype(float) * 0.6


def tex_carton():
    """One carton face (each face its own 0-1 tile): kraft board, a strip of tape across the
    middle, the edges darker with handling."""
    u, v = _uv()
    rgb = np.ones((TEX_SIZE, TEX_SIZE, 3)) * np.array([176, 140, 96])
    flute = 0.5 + 0.5 * np.sin(2 * np.pi * u * 60)
    edge = np.clip(1 - np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) / 0.06, 0, 1)
    shade = (0.96 + 0.03 * flute) * (1 - 0.18 * edge) * (1 + 0.05 * _smooth_noise(50, 0.05)) + _noise(51, scale=0.02)
    rgb *= shade[..., None]
    tape = np.abs(v - 0.5) < 0.07
    rgb[tape] = rgb[tape] * 0.75 + np.array([150, 120, 80]) * 0.25 * 1.2
    return rgb, flute * 0.002 - edge * 0.05 + tape * 0.01


def tex_crate():
    """One ammunition crate face (its own 0-1 tile): olive drab painted wood, four planks, a
    cleat round the edge."""
    u, v = _uv()
    plank = ((v * 4) % 1)
    seam = np.exp(-(np.minimum(plank, 1 - plank) / 0.02) ** 2)
    cleat = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) < 0.08
    grain = _smooth_noise(52, 0.15) * 0.04
    shade = (0.95 + grain) * (1 - 0.35 * seam) * np.where(cleat, 0.88, 1.0) + _noise(53, scale=0.02)
    return np.array([86, 90, 60])[None, None, :] * shade[..., None], cleat * 0.3 - seam * 0.2


def tex_bulkhead():
    """The forward bulkhead, one tile 1 m square: pale green panels, riveted seams."""
    u, v = _uv()
    rgb = np.ones((TEX_SIZE, TEX_SIZE, 3)) * np.array([150, 170, 152]) * (1 + _noise(5, scale=0.02))[..., None]
    h = np.zeros((TEX_SIZE, TEX_SIZE))
    seam = (np.abs(u - 0.5) > 0.495) | (np.abs(v - 0.5) > 0.495) | (np.abs(u - 0.5) < 0.004)
    rgb[seam] *= 0.65
    h[seam] -= 0.5
    rivet_rows = (np.abs(v - 0.5) > 0.48) | (np.abs(u - 0.5) > 0.48) | (np.abs(u - 0.5) < 0.02)
    dots = (np.hypot(((u * 25) % 1) - 0.5, ((v * 25) % 1) - 0.5) < 0.18)
    riv = rivet_rows & dots & ~seam
    rgb[riv] *= 1.15
    h[riv] += 0.5
    return rgb, h


MATERIALS = {
    # name: (texture maker, {alpha, double_sided, emit})
    "quilt": (tex_quilt, {}),
    "floor": (tex_floor, {}),
    "fabric": (tex_fabric, {}),
    "webbing": (tex_webbing, {"alpha": True, "double_sided": True}),
    "bulkhead": (tex_bulkhead, {}),
    "frame": (_flat((172, 178, 170)), {}),        # the frames, painted pale grey-green
    "aluminium": (_flat((188, 190, 192)), {}),    # tubes, rails, stanchions, rollers
    "duct": (_flat((205, 202, 188)), {}),
    "dark": (_flat((48, 48, 48)), {}),            # conveyor rails
    "conduit": (_flat((128, 130, 124)), {}),
    "door": (_flat((176, 176, 166)), {}),
    "glass": (_flat((150, 185, 215)), {}),        # sky through the portholes
    "red": (_flat((230, 30, 25)), {}),
    "green": (_flat((40, 210, 60)), {}),
    "cable": (_flat((190, 190, 190)), {}),
    "static_line": (tex_static_line, {"double_sided": True}),   # yellow webbing (the author)
    "snap_hook": (_flat((168, 170, 172)), {}),    # stamped steel
    # The stick's kit: early-90s olive drab (the author: period gear, not today's).
    "nylon": (tex_nylon(), {}),                   # T-10C main, T-10R reserve
    "alice": (tex_nylon((62, 68, 46), 30, 48), {}),   # the ALICE ruck, coarser and greener
    "weapons_case": (tex_weapons_case, {}),
    "tarmac": (tex_tarmac, {}),                   # the apron under the plane, before takeoff       # M1950, pale grey quilted canvas (the author)
    "harness": (tex_od_webbing, {"double_sided": True}),
    "lamp": (_flat((255, 246, 222)), {"emit": True}),
    "carton": (tex_carton, {}),                   # the pallets' loads
    "crate": (tex_crate, {}),
    "pallet": (_flat((150, 152, 150)), {}),       # 463L: aluminium skin, weathered
}


def normal_map(h, strength=0.5):
    """Tangent-space normal map from a height map (tiling). Heights are in units of the tile's
    width times `strength`: a pillow rising 1 across half a tile tilts the surface about 15-35
    degrees, enough to catch the light."""
    if h is None:
        h = np.zeros((TEX_SIZE, TEX_SIZE))
    k = strength * TEX_SIZE / 2                  # central difference over 2 pixels, in tile units
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * k
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * k
    n = np.dstack([-dx, -dy, np.ones_like(h)])     # DirectX style: green points down the image
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return (n * 0.5 + 0.5) * 255


# Specular (the _s map): (shine, smoothness), 0-1. Cloth is dull; bare metal and glass gleam.
# Without these the shader's default shine made the blankets look like aluminium.
SPECULAR = {"quilt": (0.03, 0.1), "fabric": (0.04, 0.12), "webbing": (0.04, 0.12),
            "floor": (0.3, 0.35), "aluminium": (0.5, 0.55), "glass": (0.6, 0.8),
            "dark": (0.25, 0.3), "red": (0.3, 0.5), "green": (0.3, 0.5), "lamp": (0.3, 0.5),
            "static_line": (0.05, 0.15), "snap_hook": (0.45, 0.45),
            "nylon": (0.05, 0.15), "alice": (0.05, 0.12), "harness": (0.05, 0.15),
            "weapons_case": (0.03, 0.1), "tarmac": (0.08, 0.2),
            "carton": (0.02, 0.08), "crate": (0.06, 0.15), "pallet": (0.35, 0.4)}
SPECULAR_PAINT = (0.12, 0.25)    # everything else: painted metal, ducting, cable


def write_textures(tex_dir):
    files = []
    for name, (make, opts) in MATERIALS.items():
        img, h = make()
        img = np.clip(img, 0, 255).astype(np.uint8)
        mode = "RGBA" if img.shape[2] == 4 else "RGB"
        f = tex_dir / f"c130_{name}.dds"
        save_dds(Image.fromarray(img, mode), f, "DXT5" if mode == "RGBA" else "DXT1")   # with mipmaps: no shimmer
        fn = tex_dir / f"c130_{name}_n.dds"
        save_dds(Image.fromarray(np.clip(normal_map(h), 0, 255).astype(np.uint8), "RGB"), fn)
        shine, smooth = SPECULAR.get(name, SPECULAR_PAINT)
        fs = tex_dir / f"c130_{name}_s.dds"
        Image.new("RGB", (64, 64), (round(shine * 255), round(smooth * 255), 0)).save(fs, pixel_format="DXT1")
        files += [f, fn, fs]
    return files


# --- The hull's cross-section ------------------------------------------------------------

def wall_x(z):
    """Half-width of the cabin at height z (the starboard wall's x)."""
    top = FLOOR_W / 2 + BULGE
    if z <= WALL_TOP:
        return FLOOR_W / 2 + BULGE * math.sin(math.pi / 2 * z / WALL_TOP)
    t = min(1.0, (z - WALL_TOP) / (CABIN_H - WALL_TOP))
    return top * math.sqrt(max(0.0, 1 - t * t))


def wall_normal(z, side):
    """Unit normal of the side wall at height z, pointing into the cabin."""
    dz = 1e-4
    dx = (wall_x(z + dz) - wall_x(z - dz)) / (2 * dz)     # slope of x against z
    nx, nz = -1.0, dx                                      # inward for the starboard wall
    m = math.hypot(nx, nz)
    return (side * nx / m, 0.0, nz / m)


def hull_normal(x, z):
    """The hull's inward normal at a point (x, z) on its cross-section."""
    if z <= WALL_TOP:
        return wall_normal(z, 1 if x > 0 else -1)
    top, b = FLOOR_W / 2 + BULGE, CABIN_H - WALL_TOP       # the arch: the ellipse's normal
    nx, nz = -x / (top * top), -(z - WALL_TOP) / (b * b)
    m = math.hypot(nx, nz)
    return (nx / m, 0.0, nz / m)


def profile():
    """The hull's cross-section, port floor edge up and over to starboard floor edge: [(x, z)]."""
    top = FLOOR_W / 2 + BULGE
    right = [(wall_x(WALL_TOP * i / WALL_STEPS), WALL_TOP * i / WALL_STEPS)
             for i in range(WALL_STEPS + 1)]
    for i in range(1, ARC_STEPS + 1):
        a = math.pi / 2 * i / ARC_STEPS
        right.append((top * math.cos(a), WALL_TOP + (CABIN_H - WALL_TOP) * math.sin(a)))
    left = [(-x, z) for x, z in right[:-1]]     # port floor edge up to just short of the top
    return left + right[::-1]                   # then over the top and down to starboard


def arc_lengths(prof):
    s = [0.0]
    for (x0, z0), (x1, z1) in zip(prof, prof[1:]):
        s.append(s[-1] + math.hypot(x1 - x0, z1 - z0))
    return s


# --- Mesh building -----------------------------------------------------------------------

class Mesh:
    """Triangles with per-vertex normals; each triangle wound to face its normals' way."""

    def __init__(self):
        self.verts, self.norms, self.uvs, self.tris = [], [], [], []

    def vert(self, p, n, uv=None):
        self.verts.append(tuple(p))
        self.norms.append(tuple(n))
        self.uvs.append(uv if uv else (p[1] / 2, p[2] / 2))
        return len(self.verts) - 1

    def tri(self, a, b, c):
        pa, pb, pc = self.verts[a], self.verts[b], self.verts[c]
        u = [pb[i] - pa[i] for i in range(3)]
        v = [pc[i] - pa[i] for i in range(3)]
        cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        n = [sum(self.norms[k][i] for k in (a, b, c)) for i in range(3)]
        if sum(cr[i] * n[i] for i in range(3)) < 0:
            b, c = c, b
        self.tris.append((a, b, c))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def box(self, x0, y0, z0, x1, y1, z1, sides="tbnsew", tile=1.0):
        faces = {
            "t": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1), (0, 1)),
            "b": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1), (0, 1)),
            "s": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0), (0, 2)),
            "e": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0), (1, 2)),
            "n": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0), (0, 2)),
            "w": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0), (1, 2)),
        }
        for s in sides:
            pts, n, (a, b) = faces[s]
            self.quad(*[self.vert(p, n, (p[a] / tile, p[b] / tile)) for p in pts])

    def tube(self, p0, p1, r, steps=8, caps=False):
        """A tube from p0 to p1, any direction."""
        ax = [p1[i] - p0[i] for i in range(3)]
        ln = math.sqrt(sum(a * a for a in ax))
        ax = [a / ln for a in ax]
        ref = (0, 0, 1) if abs(ax[2]) < 0.9 else (1, 0, 0)
        e1 = [ax[1] * ref[2] - ax[2] * ref[1], ax[2] * ref[0] - ax[0] * ref[2], ax[0] * ref[1] - ax[1] * ref[0]]
        m = math.sqrt(sum(a * a for a in e1))
        e1 = [a / m for a in e1]
        e2 = [ax[1] * e1[2] - ax[2] * e1[1], ax[2] * e1[0] - ax[0] * e1[2], ax[0] * e1[1] - ax[1] * e1[0]]
        rings = []
        for k, p in enumerate((p0, p1)):
            ring = []
            for i in range(steps + 1):
                a = 2 * math.pi * i / steps
                n = [math.cos(a) * e1[j] + math.sin(a) * e2[j] for j in range(3)]
                ring.append(self.vert([p[j] + r * n[j] for j in range(3)], n, (i / steps, k * ln)))
            rings.append(ring)
        for i in range(steps):
            self.quad(rings[0][i], rings[0][i + 1], rings[1][i + 1], rings[1][i])
        if caps:
            for p, ring, sgn in ((p0, rings[0], -1), (p1, rings[1], 1)):
                n = [sgn * a for a in ax]
                c = self.vert(p, n, (0.5, 0.5))
                rim = [self.vert(self.verts[i], n, (0.5, 0.5)) for i in ring[:-1]]
                for i in range(steps):
                    self.tri(c, rim[i], rim[(i + 1) % steps])

    def on_wall(self, outline, side, inset):
        """A flat shape laid onto a side wall, following its curve: outline is [(y, z)] around a
        convex shape; inset is how far proud of the wall it sits."""
        cy = sum(p[0] for p in outline) / len(outline)
        cz = sum(p[1] for p in outline) / len(outline)

        def place(y, z):
            n = wall_normal(z, side)
            x = side * wall_x(z)
            return self.vert((x + n[0] * inset, y, z + n[2] * inset), n)

        c = place(cy, cz)
        ring = [place(y, z) for y, z in outline]
        for i in range(len(ring)):
            self.tri(c, ring[i], ring[(i + 1) % len(ring)])


def circle(cy, cz, r, steps=ROUND_STEPS):
    return [(cy + r * math.cos(2 * math.pi * i / steps), cz + r * math.sin(2 * math.pi * i / steps))
            for i in range(steps)]


def rounded_rect(y0, z0, y1, z1, r, steps=6):
    pts = []
    for cy, cz, a0 in ((y1 - r, z0 + r, -90), (y1 - r, z1 - r, 0), (y0 + r, z1 - r, 90),
                       (y0 + r, z0 + r, 180)):
        for i in range(steps + 1):
            a = math.radians(a0 + 90 * i / steps)
            pts.append((cy + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def doorway(da, db, steps=6):
    """The paratroop doorway's edge, from the sill at its aft edge up, round the top (its upper
    corners rounded, DOOR_R) and down its forward edge to the sill: [(y, z, (ny, nz))], each
    with its normal across the opening, pointing into it. The sill is square: the jump platform
    runs out level from the floor."""
    top, r = DOOR_TOP, DOOR_R
    zs = [WALL_TOP * i / WALL_STEPS for i in range(WALL_STEPS + 1) if WALL_TOP * i / WALL_STEPS < top - r]
    pts = [(da, z, (1.0, 0.0)) for z in zs + [top - r]]
    for cy, a0, a1, ks in ((da + r, 180, 90, range(1, steps + 1)), (db - r, 90, 0, range(steps))):
        for i in ks:
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cy + r * math.cos(a), top - r + r * math.sin(a), (-math.cos(a), -math.sin(a))))
    pts += [(db, z, (-1.0, 0.0)) for z in [top - r] + zs[::-1]]
    return pts


# --- The parts ---------------------------------------------------------------------------

def parts(length):
    """{name: (material, collides, Mesh)} in metres; material None is collision only."""
    fwd, hinge = length / 2, -length / 2
    aft = hinge - RAMP_L
    hw = FLOOR_W / 2
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    p = {}

    # Hull: the cross-section run from the ramp's end to the forward bulkhead, seen from inside,
    # lined with blankets (one texture tile per frame bay). Over the ramp the tail sweeps up: the
    # closed ramp rises aft from its hinge, the upper cargo door slopes down to meet it, and the
    # sides draw in. The paratroop doors are open: a hole in each side wall from the floor to the
    # first profile point of the arch, which sits at the door's top.
    hull, bulkhead = Mesh(), Mesh()
    prof = profile()
    arc = arc_lengths(prof)
    rise = RAMP_L * math.tan(math.radians(RAMP_ANGLE))

    def section(t):
        """The profile t of the way from the hinge (0) to the ramp's end (1): (x, z) pairs."""
        w = 1 - t * (1 - AFT_WIDTH)
        h = 1 - t * (1 - AFT_HEIGHT / CABIN_H)
        return [(x * w, rise * t + z * h) for x, z in prof]

    stations = [(aft, section(1.0)), (hinge, section(0.0)), (da, section(0.0)),
                (db, section(0.0)), (fwd, section(0.0))]
    rows = [[hull.vert((x, y, z), hull_normal(x0, z0), ((y - hinge) / FRAME_PITCH, s / 0.5))
             for (x, z), (x0, z0), s in zip(sec, prof, arc)]
            for y, sec in stations]
    for k, (r0, r1) in enumerate(zip(rows, rows[1:])):
        for i in range(len(prof) - 1):
            (xa, za), (xb, zb) = prof[i], prof[i + 1]
            if stations[k][0] == da and max(za, zb) <= DOOR_TOP and xa * xb > 0:
                continue                                   # the doorway
            hull.quad(r0[i], r0[i + 1], r1[i + 1], r1[i])
    # The doorway's rounded top corners: the wall fills in between each corner of the square hole
    # and the arc, fanned from the corner (its edge points follow the wall's bow).
    wall = [(x, z, si) for (x, z), si in zip(prof, arc) if x > 0]

    def arc_at(z):
        for (x0, z0, s0), (x1, z1, s1) in zip(wall, wall[1:]):
            if min(z0, z1) <= z <= max(z0, z1):
                return s0 + (s1 - s0) * (z - z0) / ((z1 - z0) or 1)
        return wall[0][2]
    edge = doorway(da, db)
    k = next(i for i, (_, z, _) in enumerate(edge) if z >= DOOR_TOP - DOOR_R - 1e-9)
    n = len(edge)
    bow = [z for _, z, _ in wall if DOOR_TOP - DOOR_R < z < DOOR_TOP - 1e-6]   # on the edges
    corners = ((da, [(da, z) for z in bow] + [(y, z) for y, z, _ in edge[k:k + 7]]),
               (db, [(y, z) for y, z, _ in edge[k + 7:k + 14]] + [(db, z) for z in bow[::-1]]))
    for side in (1, -1):
        for cy, run in corners:
            pts = [(cy, DOOR_TOP)] + run
            # the run starts or ends on the corner's own edge at DOOR_TOP - DOOR_R; on the top
            # edge it ends at the arc's last point
            vs = []
            for y, z in pts:
                x = side * wall_x(z)
                sa = arc_at(z)
                vs.append(hull.vert((x, y, z), hull_normal(x, z),
                                    ((y - hinge) / FRAME_PITCH, (sa if side > 0 else arc[-1] - sa) / 0.5)))
            for a, b in zip(vs[1:], vs[2:]):
                hull.tri(vs[0], a, b)
    for (y, sec), ny, m in ((stations[0], 1.0, hull), (stations[-1], -1.0, bulkhead)):
        cz = sum(z for _, z in sec) / len(sec)
        c = m.vert((0.0, y, cz), (0, ny, 0), (0.5, cz))
        ring = [m.vert((x, y, z), (0, ny, 0), (x + 0.5, z)) for x, z in sec]
        for i in range(len(ring)):
            m.tri(c, ring[i], ring[(i + 1) % len(ring)])   # closes along the floor too
    p["hull"] = ("quilt", True, hull)

    # An invisible wall across the ramp where the headroom drops to RAMP_STOP_HEADROOM: further up,
    # the ramp's floor and the sloping cargo door squeeze the player (2 m in power armor) and the
    # camera pokes through the ceiling.
    t = (CABIN_H - RAMP_STOP_HEADROOM) / (CABIN_H - AFT_HEIGHT)   # headroom falls linearly aft
    stop = Mesh()
    ys, sec = hinge - t * RAMP_L, section(t)
    cz = sum(z for _, z in sec) / len(sec)
    c = stop.vert((0.0, ys, cz), (0, 1, 0), (0, 0))
    ring = [stop.vert((x, ys, z), (0, 1, 0), (0, 0)) for x, z in sec]
    for i in range(len(ring)):
        stop.tri(c, ring[i], ring[(i + 1) % len(ring)])
    p["ramp_stop"] = (None, True, stop)
    p["bulkhead"] = ("bulkhead", True, bulkhead)

    # Frames: bands standing proud of the blankets, every FRAME_PITCH from the hinge forward,
    # up one wall, over the ceiling and down the other (none across the doorways).
    frames = Mesh()
    inner = []
    for (x, z) in prof:
        n = hull_normal(x, z)
        inner.append(((x, z), (x + n[0] * FRAME_DEPTH, z + n[2] * FRAME_DEPTH), n))
    y = hinge + FRAME_PITCH
    while y < fwd - 0.05:
        if not (da - 0.1 < y < db + 0.1):
            y0, y1 = y - FRAME_W / 2, y + FRAME_W / 2
            for (pa, qa, na), (pb, qb, nb) in zip(inner, inner[1:]):
                frames.quad(frames.vert((qa[0], y0, qa[1]), na), frames.vert((qb[0], y0, qb[1]), nb),
                            frames.vert((qb[0], y1, qb[1]), nb), frames.vert((qa[0], y1, qa[1]), na))
                for yy, ny in ((y0, -1.0), (y1, 1.0)):
                    frames.quad(*[frames.vert((pt[0], yy, pt[1]), (0, ny, 0)) for pt in (pa, pb, qb, qa)])
        y += FRAME_PITCH
    p["frames"] = ("frame", False, frames)

    # Floor and ramp: the floor texture tiles every 1.016 m, a tie-down ring in each.
    floor, ramp = Mesh(), Mesh()
    ft = 1.016
    floor.quad(*[floor.vert((x, yy, 0.002), (0, 0, 1), (x / ft + 0.5, yy / ft))
                 for x, yy in ((-hw, hinge), (hw, hinge), (hw, fwd), (-hw, fwd))])
    up = (0.0, -math.sin(math.radians(RAMP_ANGLE)), math.cos(math.radians(RAMP_ANGLE)))
    aw = hw * AFT_WIDTH
    ramp.quad(*[ramp.vert(v, up, (v[0] / ft + 0.5, s / ft)) for v, s in
                (((-hw, hinge, 0.002), 0), ((hw, hinge, 0.002), 0),
                 ((aw, aft, rise + 0.002), -RAMP_L), ((-aw, aft, rise + 0.002), -RAMP_L))])
    p["floor"] = ("floor", True, floor)
    p["ramp"] = ("floor", True, ramp)

    # Troop seats, from just forward of the doors to the pallets; forward of them the outboard
    # seats are folded up against the wall (their nets run on to the flight deck steps) and the
    # centerline seats are out.
    y0 = db + SEAT_AFT_GAP
    y_end = y0 + int((fwd - STEPS_L - 0.3 - y0) / SEAT_W) * SEAT_W   # the full run, seats all down
    per_row = int((pallet_spans(length)[0][0] - SEAT_FWD_GAP - y0) / SEAT_W)
    y1 = y0 + per_row * SEAT_W
    pans, nets, metal, backs = Mesh(), Mesh(), Mesh(), Mesh()
    legs_y = [y0 + 0.08 + k * 2 * SEAT_W for k in range(per_row // 2 + 1)]
    legs_y[-1] = min(legs_y[-1], y1 - 0.08)
    pan_t = 0.03
    for side in (-1, 1):
        # Outboard: the pan along the wall, its front edge on a rail and legs; the net from the
        # pan's back edge up the wall to a rail.
        wall = wall_x(SEAT_Z) - 0.01
        xa, xb = sorted((side * wall, side * (wall - SEAT_D)))
        pans.box(xa, y0, SEAT_Z - pan_t, xb, y1, SEAT_Z, tile=SEAT_W)
        xf = side * (wall - SEAT_D + 0.03)
        metal.tube((xf, y0, SEAT_Z - 0.04), (xf, y1, SEAT_Z - 0.04), 0.016)
        for ly in legs_y:
            metal.tube((xf, ly, 0.0), (xf, ly, SEAT_Z - 0.04), 0.014)
        zs = [SEAT_Z + (WALL_NET_TOP - SEAT_Z) * i / 4 for i in range(5)]
        col = [(side * (wall_x(z) - 0.04), z, (z - SEAT_Z) / (WALL_NET_TOP - SEAT_Z)) for z in zs]
        n = (-side, 0, 0)
        for (xa_, za, va), (xb_, zb, vb) in zip(col, col[1:]):
            nets.quad(nets.vert((xa_, y0, za), n, (0, 1 - va)), nets.vert((xa_, y_end, za), n, ((y_end - y0) / SEAT_W, 1 - va)),
                      nets.vert((xb_, y_end, zb), n, ((y_end - y0) / SEAT_W, 1 - vb)), nets.vert((xb_, y0, zb), n, (0, 1 - vb)))
        xr = side * (wall_x(WALL_NET_TOP) - 0.05)
        metal.tube((xr, y0 - 0.1, WALL_NET_TOP), (xr, y_end + 0.1, WALL_NET_TOP), 0.018)
        # The folded seats: each pan swung up flat against the net, its front rail on top.
        if y_end > y1 + 0.01:
            xw = wall_x(SEAT_Z + SEAT_D / 2) - 0.06
            xa, xb = sorted((side * xw, side * (xw - pan_t)))
            pans.box(xa, y1 + 0.01, SEAT_Z - 0.04, xb, y_end, SEAT_Z + SEAT_D - 0.04, "tnsew", tile=SEAT_W)
            metal.tube((side * (xw - 0.02), y1 + 0.01, SEAT_Z + SEAT_D - 0.02),
                       (side * (xw - 0.02), y_end, SEAT_Z + SEAT_D - 0.02), 0.016)

        # Centerline: pans each side of the middle, back to back.
        xa, xb = sorted((side * CENTER_BACK_W / 2, side * (CENTER_BACK_W / 2 + SEAT_D)))
        pans.box(xa, y0, SEAT_Z - pan_t, xb, y1, SEAT_Z, tile=SEAT_W)
        xf = side * (CENTER_BACK_W / 2 + SEAT_D - 0.03)
        metal.tube((xf, y0, SEAT_Z - 0.04), (xf, y1, SEAT_Z - 0.04), 0.016)
        for ly in legs_y:
            metal.tube((xf, ly, 0.0), (xf, ly, SEAT_Z - 0.04), 0.014)

    # The centerline net, one sheet seen from both sides, from the pans up to its rail; the
    # stanchions floor to ceiling; and a solid (invisible) backrest so no one walks through it.
    nets.quad(nets.vert((0, y0, SEAT_Z), (1, 0, 0), (0, 1)), nets.vert((0, y1, SEAT_Z), (1, 0, 0), ((y1 - y0) / SEAT_W, 1)),
              nets.vert((0, y1, CENTER_NET_TOP), (1, 0, 0), ((y1 - y0) / SEAT_W, 0)),
              nets.vert((0, y0, CENTER_NET_TOP), (1, 0, 0), (0, 0)))
    metal.tube((0, y0, CENTER_NET_TOP), (0, y1, CENTER_NET_TOP), 0.018)
    sy = y0
    while sy <= y1 + 0.01:
        metal.tube((0, sy, 0.0), (0, sy, CABIN_H - 0.01), 0.03)
        sy += STANCHION_PITCH
    backs.box(-0.04, y0, 0.0, 0.04, y1, CENTER_NET_TOP)
    p["seat_pans"] = ("fabric", True, pans)
    p["seat_nets"] = ("webbing", False, nets)
    p["seat_frames"] = ("aluminium", False, metal)
    p["centre_backrest"] = (None, True, backs)

    # A roller conveyor down the middle of each aisle: two rails and the rollers between them.
    rollers, rails = Mesh(), Mesh()
    aisle_in, aisle_out = CENTER_BACK_W / 2 + SEAT_D, wall_x(SEAT_Z) - 0.01 - SEAT_D
    for side in (-1, 1):
        xc = side * (aisle_in + aisle_out) / 2
        r_end = fwd - (STEPS_L + 0.2 if side < 0 else 0.2)
        for xr in (xc - 0.13, xc + 0.11):
            rails.box(xr, hinge + 0.2, 0.0, xr + 0.02, r_end, 0.05, "tnsew")
        ry = hinge + 0.3
        while ry < r_end - 0.1:
            rollers.tube((xc - 0.11, ry, 0.03), (xc + 0.11, ry, 0.03), ROLLER_R, steps=6)
            ry += ROLLER_PITCH
    p["rollers"] = ("aluminium", False, rollers)
    p["roller_rails"] = ("dark", False, rails)

    # Round jump lights just forward of each door; portholes spaced down each side between the
    # seats' ends. The doors themselves are their own model (door_parts), for the activator.
    rims, glass, reds, greens, domes = Mesh(), Mesh(), Mesh(), Mesh(), Mesh()
    ports = [y0 + (y_end - y0) * (i + 0.5) / PORTHOLES for i in range(PORTHOLES)]
    for side in (-1, 1):
        for y in ports:
            rims.on_wall(circle(y, PORTHOLE_Z, PORTHOLE_D / 2 + 0.04), side, 0.01)
            glass.on_wall(circle(y, PORTHOLE_Z, PORTHOLE_D / 2), side, 0.025)
        ly = db + 0.15 + LIGHT_D / 2
        reds.on_wall(circle(ly, 1.81, LIGHT_D / 2), side, 0.02)
        greens.on_wall(circle(ly, 1.61, LIGHT_D / 2), side, 0.02)
        dy = hinge + DOME_PITCH / 2
        while dy < fwd - 0.5:
            domes.on_wall(circle(dy, DOME_Z, DOME_D / 2), side, FRAME_DEPTH + 0.01)
            dy += DOME_PITCH
    p["porthole_rims"] = ("door", False, rims)
    p["portholes"] = ("glass", False, glass)
    p["light_red"] = ("red", False, reds)
    p["light_green"] = ("green", False, greens)
    p["dome_lights"] = ("lamp", False, domes)

    # Overhead: two air ducts down the ceiling, and conduits along the top of each wall.
    ducts, conduits = Mesh(), Mesh()
    for side in (-1, 1):
        ducts.tube((side * DUCT_X, hinge - 0.2, DUCT_Z), (side * DUCT_X, fwd, DUCT_Z), DUCT_R, steps=12)
        for k, z in enumerate((1.92, 1.98, 2.04)):
            x = side * (wall_x(z) - FRAME_DEPTH - 0.025)
            conduits.tube((x, hinge, z), (x, fwd, z), 0.012 + 0.004 * k, steps=6)
    p["ducts"] = ("duct", False, ducts)
    p["conduits"] = ("conduit", False, conduits)

    cables = Mesh()
    for side in (-1, 1):
        cables.tube((side * CABLE_X, hinge - 0.3, CABLE_Z), (side * CABLE_X, fwd, CABLE_Z), CABLE_D / 2)
    p["anchor_cables"] = ("cable", False, cables)

    steps = Mesh()
    steps.box(-hw, fwd - STEPS_L, 0, -hw + STEPS_W, fwd, STEPS_H, "tsew", tile=1.016)
    p["flight_deck_steps"] = ("floor", True, steps)
    p.update(pallet_parts(length))
    return p, per_row


def pallet_spans(length):
    """Each pallet's (aft, forward) y, the last just short of the flight deck steps."""
    fwd = length / 2 - STEPS_L - PALLET_FWD_GAP
    first = fwd - PALLETS * PALLET_L - (PALLETS - 1) * PALLET_GAP
    return [(first + k * (PALLET_L + PALLET_GAP), first + k * (PALLET_L + PALLET_GAP) + PALLET_L)
            for k in range(PALLETS)]


def _block(m, x0, y0, z0, x1, y1, z1, sides="tnsew"):
    """A box with each face its own 0-1 texture tile (a carton's, a crate's)."""
    faces = {
        "t": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        "s": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        "e": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
        "n": ([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0)),
        "w": ([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0)),
    }
    for s in sides:
        pts, n = faces[s]
        m.quad(*[m.vert(p, n, uv) for p, uv in zip(pts, ((0, 1), (1, 1), (1, 0), (0, 0)))])


def pallet_parts(length):
    """The cargo forward: 463L pallets on the rollers, each built up square with cartons and
    olive drab crates in layers, under a cargo net hooked to the pallet's rim. One collision box
    a pallet."""
    rng = np.random.default_rng(130)
    base, rims, cartons, crates, net, solid = Mesh(), Mesh(), Mesh(), Mesh(), Mesh(), Mesh()
    z0 = ROLLER_R + 0.03                              # on the rollers
    hx = PALLET_W / 2
    for ya, yb in pallet_spans(length):
        base.box(-hx, ya, z0, hx, yb, z0 + PALLET_T, tile=1.0)
        lip = 0.03
        for xa, xb, y_a, y_b in ((-hx, -hx + lip, ya, yb), (hx - lip, hx, ya, yb),
                                 (-hx, hx, ya, ya + lip), (-hx, hx, yb - lip, yb)):
            rims.box(xa, y_a, z0 + PALLET_T, xb, y_b, z0 + PALLET_T + 0.012, "tnsew")
        # The load: layers, each in rows along the cabin, each row in boxes across it.
        lx, ly0, ly1 = hx - 0.06, ya + 0.06, yb - 0.06
        zt = z0 + PALLET_T
        top = zt + LOAD_H
        z = zt
        while z < top - 0.05:
            h = min(rng.choice([0.28, 0.36, 0.45]), top - z)
            y = ly0
            while y < ly1 - 0.05:
                d = min(rng.choice([0.4, 0.5, 0.6]), ly1 - y)
                x = -lx
                while x < lx - 0.05:
                    w = min(rng.choice([0.45, 0.55, 0.65, 0.8]), lx - x)
                    m = crates if rng.random() < 0.3 else cartons
                    g = 0.006
                    _block(m, x + g, y + g, z, x + w - g, y + d - g, z + h - g)
                    x += w
                y += d
            z += h
        # The net: straps over the top and down all four sides to the rim, NET_PITCH apart.
        e = 0.012                                     # standing off the boxes
        t = NET_STRAP / 2
        nx = max(2, round(2 * lx / NET_PITCH))
        ny = max(2, round((ly1 - ly0) / NET_PITCH))
        for i in range(nx + 1):                       # across the cabin: over the top, down the ends
            x = -lx + 2 * lx * i / nx
            net.box(x - t, ly0 - e, top, x + t, ly1 + e, top + e, "t")
            net.box(x - t, ly0 - e, zt, x + t, ly0 - e + 0.001, top + e, "s")
            net.box(x - t, ly1 + e - 0.001, zt, x + t, ly1 + e, top + e, "n")
        for j in range(ny + 1):                       # along it: over the top, down the sides
            y = ly0 + (ly1 - ly0) * j / ny
            net.box(-lx - e, y - t, top + e, lx + e, y + t, top + 2 * e, "t")
            net.box(-lx - e, y - t, zt, -lx - e + 0.001, y + t, top + 2 * e, "w")
            net.box(lx + e - 0.001, y - t, zt, lx + e, y + t, top + 2 * e, "e")
        for zz in (zt + LOAD_H * k / 3 for k in (1, 2)):   # two bands round the sides
            net.box(-lx - e - 0.002, ly0 - e - 0.002, zz - t, lx + e + 0.002, ly1 + e + 0.002, zz + t, "nsew")
        solid.box(-hx, ya, 0.0, hx, yb, top + 0.03)
    return {"pallets": ("pallet", False, base), "pallet_rims": ("dark", False, rims),
            "cargo_cartons": ("carton", False, cartons), "cargo_crates": ("crate", False, crates),
            "cargo_net": ("harness", False, net), "cargo_solid": (None, True, solid)}


# --- The stick ------------------------------------------------------------------------

STICK_GAP_SEATS = 1.5          # seats between one man and the next in line: at less, the game's
                               # collision bodies shove them about (tested)


def stick_aisle():
    """The middle of each side's aisle, from the centreline: where the stick stands."""
    wall = wall_x(SEAT_Z) - 0.01
    inner = CENTER_BACK_W / 2 + SEAT_D
    return (inner + wall - SEAT_D) / 2


def stick_places(length):
    """The stick's eight jumpers, four a side by the doors, staggered so they stand up into a line
    outboard 1, inboard 1, outboard 2, inboard 2 from the door: a list of dicts in the order the
    jumpmaster's script holds them (outboard starboard 1, 2; outboard port 1, 2; then inboard),
    each with outboard, side (+1 starboard), seat (x, y, facing +1 for +X) and stand (x, y),
    in metres. Each stands straight out from his seat into his side's aisle, facing aft."""
    hinge = -length / 2
    db = hinge + DOOR_AFT + DOOR_W
    y0 = db + SEAT_AFT_GAP
    wall = wall_x(SEAT_Z) - 0.01
    inner = CENTER_BACK_W / 2 + SEAT_D
    aisle = (inner + wall - SEAT_D) / 2
    out = []
    for outboard in (True, False):
        for side in (1, -1):
            for k in (0, 1):
                seat_no = 2 * STICK_GAP_SEATS * k + (0 if outboard else STICK_GAP_SEATS)
                y = y0 + (seat_no + 0.5) * SEAT_W
                x = side * (wall - SEAT_D / 2) if outboard else side * (inner - SEAT_D / 2)
                out.append({"outboard": outboard, "side": side, "seat": (x, y, -side if outboard else side),
                            "stand": (side * aisle, y)})
    return out


STATIC_LINE_W = 0.044           # 1-3/4 in webbing
# A Fallout man in fatigues, measured off the vanilla FatiguesM.nif (metres, his feet at the origin,
# facing +Y): the top of his shoulder, its offset from his middle, and his back at two heights.
SHOULDER_Z, SHOULDER_X = 1.62, 0.17
BACK_HIGH, BACK_LOW = (-0.169, 1.50), (-0.132, 1.20)


def _catmull(pts, per=6):
    """A smooth curve through pts (Catmull-Rom), `per` samples a span."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        for k in range(per):
            t = k / per
            out.append(tuple(0.5 * (2 * p[i][j] + (-p[i - 1][j] + p[i + 1][j]) * t
                                    + (2 * p[i - 1][j] - 5 * p[i][j] + 4 * p[i + 1][j] - p[i + 2][j]) * t * t
                                    + (-p[i - 1][j] + 3 * p[i][j] - 3 * p[i + 1][j] + p[i + 2][j]) * t ** 3)
                             for j in range(3)))
    out.append(tuple(pts[-1]))
    return out


def _ribbon(m, pts, width, tile=0.25):
    """A flat strap along pts, its width across X (across his shoulders); u runs along it, one
    texture tile every `tile` metres, v across it."""
    along = 0.0
    prev = last = None
    for i, p in enumerate(pts):
        q = pts[min(i + 1, len(pts) - 1)]
        r = pts[max(i - 1, 0)]
        t = [q[j] - r[j] for j in range(3)]
        n = (0.0, -t[2], t[1])                         # across (x) crossed with the tangent
        ln = math.sqrt(sum(c * c for c in n)) or 1.0
        n = tuple(c / ln for c in n)
        if prev is not None:
            along += math.dist(prev, p)
        a = m.vert((p[0] - width / 2, p[1], p[2]), n, (along / tile, 0.0))
        b = m.vert((p[0] + width / 2, p[1], p[2]), n, (along / tile, 1.0))
        if last is not None:
            m.quad(last[0], last[1], b, a)
        last, prev = (a, b), p


def _half_disc(m, cx, cy, cz, r, t, steps=8):
    """The rounded nose of the snap hook: a half disc in the x-z plane, round side up, t thick."""
    for face in (-1, 1):
        n = (0, face, 0)
        c = m.vert((cx, cy + face * t / 2, cz), n)
        rim = [m.vert((cx + r * math.cos(math.pi * i / steps), cy + face * t / 2,
                       cz + r * math.sin(math.pi * i / steps)), n) for i in range(steps + 1)]
        for i in range(steps):
            m.tri(c, rim[i], rim[i + 1])
    for i in range(steps):
        a0, a1 = math.pi * i / steps, math.pi * (i + 1) / steps
        n = (math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2))
        q = [m.vert((cx + r * math.cos(ang), cy + f * t / 2, cz + r * math.sin(ang)), n)
             for ang, f in ((a0, -1), (a1, -1), (a1, 1), (a0, 1))]
        m.quad(*q)


def static_line_parts(mirror=False, cable=None):
    """One man's static line, hooked up, in his own frame: his feet at the origin, facing +Y, his
    right +X. The snap hook hangs on the anchor cable ahead of him (toward the door); the webbing
    runs from its tail down over his inboard shoulder and down his back to the pack. His inboard
    shoulder is his right on the starboard side; mirror=True for the port side (his left).
    Worn: make_static_line.py binds it to his chest bone, so it goes where he goes.
      the hook  from data/reference/UGK-009.jpg: a flat stamped steel plate, rounded at the nose,
                the cable through a slot under it, a sliding gate with a round button, and a slot
                at the tail the webbing loops through
      the strap from data/reference/1_3b9c...jpg: flat yellow webbing, dirty, one stitch line"""
    sx = -1 if mirror else 1
    cx = sx * (stick_aisle() - CABLE_X)              # the cable, from his middle: inboard of him
    cy, cz = 0.45, CABLE_Z
    if cable is not None:                            # anyone else: the cable (x to his right, z up)
        cx, cz = cable
        sx = 1 if cx >= 0 else -1
    W, T = 0.036, 0.007
    hook = Mesh()
    hook.box(cx - W / 2, cy - T / 2, cz - 0.035, cx + W / 2, cy + T / 2, cz - 0.025)      # under the slot
    for e in (-1, 1):
        x0, x1 = sorted((cx + e * 0.008, cx + e * W / 2))                                  # beside the slot
        hook.box(x0, cy - T / 2, cz - 0.025, x1, cy + T / 2, cz + 0.016)
        x0, x1 = sorted((cx + e * 0.006, cx + e * W / 2))                                  # the tail slot
        hook.box(x0, cy - T / 2, cz - 0.135, x1, cy + T / 2, cz - 0.115)
    _half_disc(hook, cx, cy, cz + 0.016, W / 2, T)
    hook.box(cx - W / 2, cy - T / 2, cz - 0.115, cx + W / 2, cy + T / 2, cz - 0.035)     # the body
    hook.box(cx - W / 2, cy - T / 2, cz - 0.145, cx + W / 2, cy + T / 2, cz - 0.135)     # under the tail slot
    gate = Mesh()
    gate.box(cx - W / 2 + 0.002, cy - T / 2 - 0.003, cz - 0.09, cx + W / 2 - 0.002, cy - T / 2, cz - 0.03)
    gate.tube((cx + 0.004, cy - T / 2 - 0.003, cz - 0.06), (cx + 0.004, cy - T / 2 - 0.007, cz - 0.06),
              0.006, steps=10, caps=True)
    strap = Mesh()
    x = sx * SHOULDER_X
    lie = 0.012                                       # the strap lies on his fatigues, not in them
    pts = _catmull([(cx, cy, cz - 0.14), (cx, cy - 0.05, cz - 0.30),
                    (x, 0.11 + lie, SHOULDER_Z - 0.05), (x, -0.05, SHOULDER_Z + lie),
                    # over the top of his main (make_jump_kit.MAIN: its top 1.54 m up, its back
                    # 0.33 behind him) to where the rest of the line is stowed on it
                    (x * 0.9, -0.17, 1.585), (x * 0.55, -0.24, 1.56), (x * 0.25, -0.305, 1.535),
                    (x * 0.1, -0.345, 1.46), (0.0, -0.347, 1.40)])
    _ribbon(strap, pts, STATIC_LINE_W)
    return {"static_line": ("static_line", False, strap), "snap_hook": ("snap_hook", False, hook),
            "snap_gate": ("snap_hook", False, gate)}


def door_parts(length):
    """The starboard paratroop doorway, open for the jump, as its own model for the jump door
    activator: ({name: (material, collides, Mesh)}, origin). The origin is where the door's
    centre line meets the wall at the floor; the port door is the same model turned 180 degrees.
      jambs     the doorway's edges and top, the hull's thickness, in bright aluminium
      platform  the jump platform, out over the slipstream at the sill
      activation an invisible slab filling the doorway: walking into it stops you, using it jumps
    Nothing outside: the cabin flies in the Sicily worldspace, so the real land and sky show."""
    hinge = -length / 2
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    origin = (wall_x(0), (da + db) / 2, 0.0)
    jambs, panel, glass, platform, block = (Mesh() for _ in range(5))

    # The edges, the hull's thickness, all round the doorway but the sill, facing into it.
    col = [(jambs.vert((wall_x(z), y, z), (0, ny, nz)),
            jambs.vert((wall_x(z) + JAMB, y, z), (0, ny, nz))) for y, z, (ny, nz) in doorway(da, db)]
    for (a, b), (c, d) in zip(col, col[1:]):
        jambs.quad(a, b, d, c)

    # The platform runs on from the cargo floor's edge, across the sill, out past the hull.
    x0 = origin[0] - 0.01
    platform.box(x0, da, -0.04, origin[0] + JAMB + 0.55, db, 0.002, "tnsew")

    block.box(origin[0] - 0.04, da, 0.0, origin[0] + JAMB, db, DOOR_TOP)
    parts = {"jambs": ("door", False, jambs), "platform": ("aluminium", False, platform),
             "activation": (None, True, block)}
    for _, _, m in parts.values():
        m.verts = [tuple(v[i] - origin[i] for i in range(3)) for v in m.verts]
    return parts, origin


DOOR_SEGMENTS = 1        # the door in one piece (it was 5 panels bending round the track; the real door
                         # is rigid, see door_segments). Kept as panels for the scripts that move it.
DOOR_TRACK_INSET = 0.03  # the door's track, just inside the hull's lining above the doorway...
DOOR_RECESS = 0.04       # ...but set into the doorway, as the closed door was (flush with the side)
DOOR_JOG = 0.06          # over this much height above the doorway, the track jogs in from one to the other
DOOR_STOW_CLEAR = 0.07   # opened, its bottom edge this far above the doorway's top
DOOR_KEYS = 16           # poses along the track that the script slides each panel through
DOOR_LIP = 0.04          # each panel's lip, behind the one below it, so no gap shows between them


def door_track():
    """The door's track: up the starboard wall from the floor and over under the ceiling. In the
    doorway it's set into the opening (the door closed sits flush with the plane's side); above
    it, it jogs in to run just inside the lining. Returns (s, x, z) numpy arrays, s the distance
    along it."""
    top, b = FLOOR_W / 2 + BULGE, CABIN_H - WALL_TOP
    pts = [(wall_x(z), z) for z in np.linspace(0, WALL_TOP, 300)]
    pts += [(top * math.cos(a), WALL_TOP + b * math.sin(a)) for a in np.linspace(0, math.radians(92), 600)[1:]]
    xs, zs = [], []
    for x, z in pts:
        n = hull_normal(x, z)
        t = min(1.0, max(0.0, (z - DOOR_TOP) / DOOR_JOG))
        t = t * t * (3 - 2 * t)
        inset = -DOOR_RECESS + (DOOR_TRACK_INSET + DOOR_RECESS) * t
        xs.append(x + n[0] * inset)
        zs.append(z + n[2] * inset)
    xs, zs = np.array(xs), np.array(zs)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xs), np.diff(zs)))])
    return s, xs, zs


def door_segments(length):
    """The paratroop door, closed, as DOOR_SEGMENTS panels (bottom first), each its own model from
    the jump door's origin (as door_parts), and how each slides open along the track:
    ([{name: (material, collides, Mesh)}], [[(dx, dz, degrees)] * (DOOR_KEYS + 1)], origin).
    A key moves a panel from where it's modelled (closed): turned `degrees` about the long axis
    (positive: its top over toward the cabin's centre), then shifted (dx, dz), in metres.
    No collision: the engine won't slide a fixed body (the jump door's slab closes the doorway)."""
    hinge = -length / 2
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    origin = (wall_x(0), (da + db) / 2, 0.0)
    ts, tx, tz = door_track()

    def at(s, out=0.0):
        """The track's point s along it, pushed `out` toward the hull; and its inward normal."""
        x, z = float(np.interp(s, ts, tx)), float(np.interp(s, ts, tz))
        n = hull_normal(x, z)
        return (x - n[0] * out, z - n[2] * out), n

    def s_of(z):
        return float(np.interp(z, tz, ts))

    def width(z):
        """The door's edges at height z (closed): its top corners rounded as the doorway's."""
        r, c = DOOR_R, DOOR_TOP - DOOR_R
        cut = r - math.sqrt(max(0.0, r * r - (z - c) ** 2)) if z > c else 0.0
        return da + cut, db - cut

    bounds = [DOOR_TOP * k / DOOR_SEGMENTS for k in range(DOOR_SEGMENTS + 1)]
    corner = [DOOR_TOP - DOOR_R + DOOR_R * i / 8 for i in range(1, 9)]
    hole_z = 1.35                                     # the porthole's centre, as before
    segs, keys = [], []
    for k in range(DOOR_SEGMENTS):
        z0, z1 = bounds[k], bounds[k + 1]
        panel, glass = Mesh(), Mesh()
        rows = sorted(set([z0 + (z1 - z0) * i / 4 for i in range(5)] + [z for z in corner if z0 < z < z1]))

        def row(z, out=0.0, s_shift=0.0):
            (x, zz), n = at(s_of(z) + s_shift, out)
            ya, yb = width(z)
            return [panel.vert((x, ya + (yb - ya) * j / 4, zz), n,
                               ((ya + (yb - ya) * j / 4 - da) / (db - da), 1 - z / DOOR_TOP))
                    for j in range(5)]
        grid = [row(z) for z in rows]
        if k:                                         # the lip, behind the panel below
            grid = [row(z0, 0.012, -DOOR_LIP), row(z0, 0.012)] + grid
        for r0, r1 in zip(grid, grid[1:]):
            for j in range(4):
                panel.quad(r0[j], r0[j + 1], r1[j + 1], r1[j])
        if z0 < hole_z < z1:
            ring = []
            for y, z in [((da + db) / 2, hole_z)] + circle((da + db) / 2, hole_z, PORTHOLE_D / 2):
                (x, zz), n = at(s_of(z), -0.01)
                ring.append(glass.vert((x, y, zz), n))
            for i in range(1, len(ring)):
                glass.tri(ring[0], ring[i], ring[i % (len(ring) - 1) + 1])
        parts = {"door": ("door", False, panel)}
        if glass.verts:
            parts["door_porthole"] = ("glass", False, glass)
        for _, _, m in parts.values():
            m.verts = [tuple(v[i] - origin[i] for i in range(3)) for v in m.verts]
        segs.append(parts)

        # Its poses. The door is rigid (the author: a real C-130's doesn't bend): its bottom edge
        # rides the track straight up the doorway, its top edge the track along the ceiling, so
        # as the bottom rises the top swings in. Each pose: the bottom slid u up the track, the
        # top where the track is the door's own height (the chord) from it; the door turned to
        # that chord's slope, about the chord's middle.
        sa, sb = s_of(z0), s_of(z1)
        shift = s_of(DOOR_TOP + DOOR_STOW_CLEAR)
        (ax, az), _ = at(sa)
        (bx, bz), _ = at(sb)
        chord = math.hypot(bx - ax, bz - az)
        m0 = ((ax + bx) / 2 - origin[0], (az + bz) / 2)
        a0 = math.atan2(bz - az, bx - ax)

        def top_at(s_bottom):
            """Where along the track the top edge is, a chord from the bottom edge at s_bottom."""
            (px, pz), _ = at(s_bottom)
            lo, hi = s_bottom, ts[-1]
            for _ in range(60):
                mid = (lo + hi) / 2
                (qx, qz), _ = at(mid)
                lo, hi = (mid, hi) if math.hypot(qx - px, qz - pz) < chord else (lo, mid)
            return (lo + hi) / 2
        ks = []
        for j in range(DOOR_KEYS + 1):
            u = shift * j / DOOR_KEYS
            (ax, az), _ = at(sa + u)
            (bx, bz), _ = at(top_at(sa + u))
            a = math.atan2(bz - az, bx - ax) - a0
            mx, mz = (ax + bx) / 2 - origin[0], (az + bz) / 2
            ks.append((mx - (m0[0] * math.cos(a) - m0[1] * math.sin(a)),
                       mz - (m0[0] * math.sin(a) + m0[1] * math.cos(a)), math.degrees(a)))
        keys.append(ks)
    return segs, keys, origin


def door_open_parts(length):
    """The door slid open (every panel at its last key), as one static for when it's at rest."""
    segs, keys, _ = door_segments(length)
    out = {"door": ("door", False, Mesh()), "door_porthole": ("glass", False, Mesh())}
    for parts, ks in zip(segs, keys):
        dx, dz, deg = ks[-1]
        c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        for name, (_, _, m) in parts.items():
            o = out[name][2]
            base = len(o.verts)
            for (x, y, z), (nx, ny, nz), uv in zip(m.verts, m.norms, m.uvs):
                o.verts.append((x * c - z * s_ + dx, y, x * s_ + z * c + dz))
                o.norms.append((nx * c - nz * s_, ny, nx * s_ + nz * c))
                o.uvs.append(uv)
            o.tris += [(a + base, b + base, cc + base) for a, b, cc in m.tris]
    return out


def door_track_papyrus(keys, s):
    """DevilsC130DoorTrack.psc: each panel's keys, in game units and degrees, for the panels'
    script (DevilsC130DoorPanel)."""
    lines = ["Scriptname DevilsC130DoorTrack Hidden",
             "{Generated by scripts/make_c130_blockout.py: the jump door panels' poses along their",
             "track, closed (key 0) to open. Each key is dx, dz, the turn about the long axis",
             "(degrees, AngleY), from where the panel's modelled; dx is outboard on the starboard",
             "door, so turned with the door's heading.}", "",
             f"Int Function Count() Global", f"\tReturn {DOOR_KEYS + 1}", "EndFunction", "",
             "Float[] Function Keys(Int panel) Global",
             f"\tFloat[] k = new Float[{3 * (DOOR_KEYS + 1)}]"]
    for p, ks in enumerate(keys):
        lines.append(f"\t{'If' if p == 0 else 'ElseIf'} panel == {p}")
        for j, (dx, dz, deg) in enumerate(ks):
            lines.append(f"\t\tk[{3 * j}] = {dx * s:.3f}\n\t\tk[{3 * j + 1}] = {dz * s:.3f}\n\t\tk[{3 * j + 2}] = {deg:.3f}")
    lines += ["\tEndIf", "\tReturn k", "EndFunction", ""]
    return "\n".join(lines)


TARMAC_DROP = 1.03       # the cargo floor above the ground (a C-130H's, about 41 in)
TARMAC_HALF = 440.0      # metres each way: the most a static's bounds hold (32767 units)
TARMAC_SLAB = 7.5        # concrete apron slabs


def tarmac_parts():
    """The apron under the plane, seen out of the open doors on the ground: the plane flies at
    jump height the whole time, so before takeoff it was all sky out there (the author). The
    scene shows this until the doors close for takeoff. Concrete slabs, no collision, the
    cabin's origin above its middle."""
    m = Mesh()
    n = 16
    step = 2 * TARMAC_HALF / n
    grid = [[m.vert((-TARMAC_HALF + i * step, -TARMAC_HALF + j * step, -TARMAC_DROP), (0, 0, 1),
                    ((-TARMAC_HALF + i * step) / TARMAC_SLAB, (-TARMAC_HALF + j * step) / TARMAC_SLAB))
             for i in range(n + 1)] for j in range(n + 1)]
    for j in range(n):
        for i in range(n):
            m.quad(grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
    return {"apron": ("tarmac", False, m)}


def write_nif(path, root_name, built, s, tex, pyn):
    """One static model from {name: (material, collides, Mesh)}: material None is collision only."""
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, \
        PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR, SF1, SF2 = pyn
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="BSFadeNode", root_name=root_name)
    coll_verts, coll_tris = [], []
    for name, (mat, collides, m) in built.items():
        if not m.tris:
            continue
        verts = [tuple(c * s for c in v) for v in m.verts]
        if mat:
            opts = MATERIALS[mat][1]
            props = NiShapeBuf()
            props.bufType = PynBufferTypes.BSTriShapeBufType
            props.hasFullPrecision = 1
            shape = nif.createShapeFromData(name, verts, m.tris, m.uvs, m.norms,
                                            props=props, parent=nif.root)
            shape.shader._checked_for_materials = True
            shape.shader._materials = None
            sp = shape.shader.properties
            sp.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
            if opts.get("double_sided"):
                sp.shaderflags2_set(SF2.DOUBLE_SIDED)
            if opts.get("emit"):
                sp.shaderflags1_set(SF1.OWN_EMIT)
                sp.Emissive_Color[0], sp.Emissive_Color[1], sp.Emissive_Color[2] = 1.0, 0.96, 0.85
                sp.Emissive_Color[3] = 1.0
                sp.Emissive_Mult = 1.5
            shape.set_texture("Diffuse", f"{tex}\\c130_{mat}.dds")
            shape.set_texture("Normal", f"{tex}\\c130_{mat}_n.dds")
            shape.set_texture("Specular", f"{tex}\\c130_{mat}_s.dds")
            sp.Spec_Str, sp.Glossiness = 1.0, 1.0      # the _s map sets each material's shine
            shape.save_shader_attributes()
            if opts.get("alpha"):
                shape.has_alpha_property = True
                shape.alpha_property.properties.flags = 4844          # alpha test
                shape.alpha_property.properties.threshold = 128
                shape.save_alpha_property()
        if collides:
            base = len(coll_verts)
            coll_verts += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
            coll_tris += [[a + base, b + base, c + base] for a, b, c in m.tris]

    if not coll_verts:                   # nothing to bump into (the open door): no collision
        nif.save()
        return
    physics = PhysicsProps(is_dynamic=False,
                           body_props_raw=bytes.fromhex("00ff003f003fcd3e01024c3deeff7f7f"),
                           collision_filter_info=1)
    packed = pack_shapes([CollisionShape(shape_type="compressed_mesh", name="collision",
                                         transform=None, verts=coll_verts, faces=coll_tris,
                                         convex_radius=0.0, children=[], physics=physics)])
    # BSX "has Havok" (2) plus 128, and collision flags 128, as vanilla statics have them.
    BSXFlags.New(nif, flags=130, parent=nif.root)
    coll = nif.root.add_collision(None, flags=128,
                                  collision_type=PynBufferTypes.bhkNPCollisionObjectBufType,
                                  body_id=0)
    bhkPhysicsSystem.New(nif, data=packed, parent=coll)
    nif.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=DEFAULT_LENGTH,
                    help=f"cargo floor length in metres (true C-130H: 12.2; default {DEFAULT_LENGTH})")
    ap.add_argument("--scale", type=float, default=1.0, help="size multiplier (1 = true size)")
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4

    s = args.scale / UNIT_M          # metres -> game units
    mod = out_dir("c130") / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_files = write_textures(tex_dir)
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4)
    built, per_row = parts(args.length)
    nif_path = mesh_dir / "C130_Blockout.nif"
    write_nif(nif_path, "C130_Blockout", built, s, tex, pyn)
    door_built, door_origin = door_parts(args.length)
    door_path = mesh_dir / "C130_Door.nif"
    write_nif(door_path, "C130_Door", door_built, s, tex, pyn)
    # The same doorway with nothing in it, for the green light: shown in the jump door's place
    # so Nate steps out and falls (no teleport: the game sets a moved actor down on the navmesh).
    frame_path = mesh_dir / "C130_DoorFrame.nif"
    write_nif(frame_path, "C130_DoorFrame", {k: v for k, v in door_built.items() if k != "activation"},
              s, tex, pyn)
    # The doorway's way out, from the green light on: a load door to the exit point over Sicily
    # (the cabin is an interior; a door's teleport puts the jumper in the air, where a script move
    # set him on the ground's navmesh). Nothing to see or touch: the slab's script activates it
    # (DevilsJumpDoor), since as its own prompt it gave none (tested 2026-11-20).
    exit_path = mesh_dir / "C130_DoorExit.nif"
    write_nif(exit_path, "C130_DoorExit", {"activation": (None, False, door_built["activation"][2])}, s, tex, pyn)
    panel_paths = [mesh_dir / "C130_DoorOpen.nif"]
    write_nif(panel_paths[0], "C130_DoorOpen", door_open_parts(args.length), s, tex, pyn)
    segs, keys, _ = door_segments(args.length)
    for k, seg in enumerate(segs):
        panel_paths.append(mesh_dir / f"C130_DoorPanel{k}.nif")
        write_nif(panel_paths[-1], f"C130_DoorPanel{k}", seg, s, tex, pyn)
    track_psc = mod / "Scripts" / "Source" / "User" / "DevilsC130DoorTrack.psc"
    track_psc.parent.mkdir(parents=True, exist_ok=True)
    track_psc.write_text(door_track_papyrus(keys, s), newline="\r\n")
    (ROOT / "scripts" / "papyrus" / "DevilsC130DoorTrack.psc").write_text(door_track_papyrus(keys, s), newline="\r\n")
    panel_paths.append(track_psc)
    panel_paths.append(mesh_dir / "C130_Tarmac.nif")
    write_nif(panel_paths[-1], "C130_Tarmac", tarmac_parts(), s, tex, pyn)

    aisle = wall_x(SEAT_Z) - SEAT_D - (CENTER_BACK_W / 2 + SEAT_D)
    sc = args.scale
    tris = sum(len(m.tris) for _, _, m in built.values())
    print(f"{nif_path.relative_to(ROOT)} (length {args.length} m, scale {sc}, {tris} triangles)")
    print(f"  cabin {args.length * sc:.1f} m + ramp {RAMP_L * sc:.1f} m; widest "
          f"{2 * (FLOOR_W / 2 + BULGE) * sc:.2f} m; ceiling {CABIN_H * sc:.2f} m; "
          f"aisle {aisle * sc:.2f} m ({aisle * s:.0f} units); {per_row} seats a row, {4 * per_row} in all")
    print("  placed at 0, 0, 0 in its cell, or anywhere with the doors offset to match; floor z 0, forward +Y")
    ox, oy = door_origin[0] * s, door_origin[1] * s
    print(f"{door_path.relative_to(ROOT)}: the jump door activator, placed twice, from the cabin's origin:")
    print(f"  starboard X {ox:+.0f}  Y {oy:+.0f}  Z 0, rotation Z 0")
    print(f"  port      X {-ox:+.0f}  Y {oy:+.0f}  Z 0, rotation Z 180")
    if args.install:
        data = Path(args.install)
        for f in [nif_path, door_path, frame_path, exit_path] + panel_paths + tex_files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {2 + len(tex_files)} files under {data}")


if __name__ == "__main__":
    main()
