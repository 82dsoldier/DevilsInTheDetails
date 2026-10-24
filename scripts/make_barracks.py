"""The hammerhead barracks with its main wing's outside detailed: bays, windows, sill ledges,
doors, landings, steps and railings, and the one-story L: the orderly room with the
company entrance and office windows, and the windowless arms room.

    python scripts/make_barracks.py [--install "<Fallout 4>/Data"]

The main wing, from the 1993 photo and the photo in data/reference/barracks_exterior.jpg:
  - BAYS bays down each long side, split by paired vertical strips (the joints between the
    precast panels), with two windows per bay on each floor
  - a sill ledge under each upper row of windows: out from the wall just below the sills, a
    face about 3 ft deep, then a steep slope back to the wall; the end walls have the strips
    and ledges, no windows
  - the main floor FLOOR_ABOVE m above the highest ground under the wing, so the low end
    stands taller on its foundation
  - four sets of double doors, two on each long side (DOOR_BAYS), each with a landing and steps
    running straight out from the wall down to the ground, railings on both sides
Placement, size and the L come from make_barracks_blockout.py. Every building is weathered in
its own way, in its vertex colours (see Weathering).

Writes to out/barracks/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Buildings/Barracks.nif
  Textures/DevilsInTheDetails/Buildings/<colour>.dds, flat_n.dds
"""
import argparse
import json
import math
import shutil
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, POINT_UNITS, ROOT, UNIT_M, out_dir     # noqa: E402
from make_photo_overlay import load_pynifly                                   # noqa: E402
import make_barracks_blockout as bo                                           # noqa: E402
import ba2                                                                    # noqa: E402

WING_L, WING_W = bo.WING_L, bo.WING_W
BAYS = 10                      # about 8.5 m, measured off the photo's near end
FLOOR_H = 3.1                  # floor to floor
FLOOR_ABOVE = 0.5              # main floor above the highest ground under the wing
PARAPET = 0.6
WIN_W, WIN_H, WIN_SILL = 1.9, 1.2, 0.9   # wide and low, as in the photo
WIN_OFFSET = 1.9               # each window's centre from its bay's centre: the gap is one window
WIN_DEPTH = 0.15               # glass set back from the wall face
STRIP_W, STRIP_GAP, STRIP_OUT = 0.2, 0.15, 0.08
BAND_H, BAND_OUT = 0.3, 0.05   # the band under the L's roofline
LEDGE_OUT, LEDGE_FACE = 0.2, 0.9   # sill ledges: how far out, how deep the face before the slope
LEDGE_DROP = 0.45                  # how far down the slope runs back to the wall (a steep slope)
DOOR_BAYS = (2, 7)             # bays 3 and 8, counted from the south end, on both sides
DOOR_W, DOOR_H, DOOR_DEPTH = 2.1, 2.2, 0.3   # double doors, closing straight together
LANDING_OUT, LANDING_ALONG = 1.5, 2.6
RISER, TREAD = 0.18, 0.28   # the stair is as wide as the landing
RAMP_PAST = 1.0             # the collision ramp runs this far past the bottom step, underground
RAIL_H, RAIL_T = 0.95, 0.05
L_HEIGHT = 3.6                 # the one-story L, floor to roof

COLOURS = {
    "sandstone": (205, 188, 158), "band": (176, 160, 132), "glass": (38, 46, 54),
    "frame": (226, 224, 216), "door": (112, 74, 44), "concrete": (172, 170, 164),
    "rail": (92, 92, 90), "roof": (118, 114, 108),
    "crack": (34, 31, 28), "spall": (140, 134, 124), "void": (22, 21, 20), "board": (128, 110, 86),
}
MOD_PATH = "DevilsInTheDetails/Buildings"
FOOTING = bo.FOOTING


# Metres between the vertices that carry the weathering: fine across a wall, so streaks stay
# narrow, coarser up and down it, and coarse on flat roofs and landings.
WEAR_STEP_ALONG, WEAR_STEP_UP, WEAR_STEP_FLAT = 0.3, 0.6, 1.2
MAX_SHAPE_VERTS = 60000    # a shape's triangles index its vertices with 16 bits
WEAR_GAIN = {          # how strongly each material shows the dirt (1 = fully)
    "sandstone": 1.0, "band": 1.0, "concrete": 1.0, "roof": 0.8, "frame": 0.9,
    "door": 0.7, "glass": 0.4, "rail": 0.3, "crack": 0.2, "spall": 0.8, "void": 0.3, "board": 0.8,
}


def _hash(ix, iy, iz, seed):
    """A repeatable random number in 0..1 for each lattice point."""
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def noise(p, scale, seed):
    """Smooth value noise in 0..1 at points p (N, 3), features about `scale` metres across."""
    q = np.asarray(p, float) / scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * \
                    (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


class Weathering:
    """Two hundred years of rain, fire and neglect, painted into the vertex colours (which
    darken and tint the shared textures), different on every building: its own seed sets how
    old it looks, how far the grime climbs, how long the streaks run and which windows burned.

      streaks   down from every window sill, sill ledge and roofline (see Mesh.drips)
      splash    dark grime rising from the ground, higher in places
      moss      green on north-facing walls, ledge tops and low down
      scorch    soot plumes above a few windows on some buildings
      blotches  large uneven stains everywhere, and darker undersides"""

    def __init__(self, seed, heading_deg, ground):
        rng = np.random.default_rng(seed)
        self.seed = seed
        self.h = math.radians(heading_deg)
        self._ground, self._cache = ground, {}
        self.age = rng.uniform(0.62, 0.86)            # overall: lower is darker
        self.splash_h = rng.uniform(0.6, 1.8)         # how high the ground grime climbs
        self.streak_len = rng.uniform(1.5, 4.5)       # typical streak length below a drip edge
        self.streak_dark = rng.uniform(0.35, 0.6)
        self.moss = rng.uniform(0.2, 1.0)
        self.tint = rng.uniform(-0.05, 0.05, 3)       # a slight shift of the whole building's hue
        self.scorch_count = int(rng.choice([0, 0, 1, 2, 3, 5]))
        self.severity = rng.uniform(0.5, 1.3)          # how cracked and broken
        self.rng = rng
        self.scorched = []

    def rng_for(self, *key):
        """A generator seeded by this building and a place on it, so the damage there comes out
        the same however the building is put together."""
        key = (self.seed,) + tuple(round(float(v), 2) if isinstance(v, float) else v for v in key)
        return np.random.default_rng(zlib.crc32(repr(key).encode()))

    def window_state(self, wall_key, ha, zb, low):
        """intact, cracked, broken, missing or boarded; burned windows are always open, and
        more ground-floor windows are boarded."""
        k, side, face = wall_key
        if any(s[:3] == (k, side, face) and abs(s[3] - ha) < 0.01 and abs(s[5] - zb) < 0.01
               for s in self.scorched):
            return "missing" if self.rng_for("burn", *wall_key, ha).random() < 0.6 else "broken"
        r = self.rng_for("state", *wall_key, ha, zb).random()
        p_intact = max(0.05, 0.35 - 0.2 * self.severity)
        p_boarded = 0.35 if low else 0.08
        p_broken = 0.3 * self.severity
        p_missing = 0.15 * self.severity
        for state, pr in (("intact", p_intact), ("boarded", p_boarded), ("broken", p_broken),
                          ("missing", p_missing)):
            if r < pr:
                return state
            r -= pr
        return "cracked"

    def ground(self, x, y):
        k = (round(x * 2), round(y * 2))
        if k not in self._cache:
            self._cache[k] = self._ground(k[0] / 2, k[1] / 2)
        return self._cache[k]

    def pick_scorched(self, windows):
        if self.scorch_count and windows:
            idx = self.rng.choice(len(windows), min(self.scorch_count, len(windows)), replace=False)
            self.scorched = [windows[i] for i in idx]

    def colours(self, mat, p, n_bld, n_world, drips):
        """RGBA 0..1 for points p (N, 3, building metres before mirroring) on a face whose
        normal is n_bld in the building and n_world (east, north, up) in the world."""
        N = len(p)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        g = np.array([self.ground(a, b) for a, b in zip(x, y)])
        above = z - g
        s = self.seed
        dark = np.zeros(N)

        # Large blotches, and finer mottling.
        dark += 0.35 * np.clip(noise(p, 4.0, s) - 0.35, 0, 1)
        dark += 0.15 * noise(p, 0.9, s + 1)

        # Ground splash, its upper edge ragged.
        top = self.splash_h * (0.6 + 0.8 * noise(p * (1, 1, 0), 2.5, s + 2))
        dark += 0.55 * np.exp(-np.clip(above, 0, None) / np.maximum(top, 0.1))

        # Streaks below drip edges on vertical faces: a ragged profile along the edge, fading
        # downward over a length that changes from streak to streak.
        if abs(n_world[2]) < 0.5 and drips:
            out = 0 if abs(n_bld[0]) > 0.5 else 1
            along = 1 - out
            face = p[:, out]
            h = p[:, along]
            streak = np.zeros(N)
            for axis, side, fz, h0, h1, zd in drips:
                if axis != out or side != np.sign(n_bld[out]):
                    continue
                on = (np.abs(face - fz) < 0.35) & (h >= h0 - 0.1) & (h <= h1 + 0.1) & (z < zd)
                if not on.any():
                    continue
                q = np.stack([h, np.full(N, fz * 7.1 + zd * 3.3), np.zeros(N)], 1)
                prof = np.clip((noise(q, 0.35, s + 3) - 0.3) * 2.2, 0, 1)
                length = self.streak_len * (0.4 + 1.2 * noise(q, 1.2, s + 4))
                v = prof * np.exp(-(zd - z) / length)
                streak = np.where(on, np.maximum(streak, v), streak)
            dark += self.streak_dark * streak

        # Soot plumes above burned windows, widening as they rise.
        for axis, side, fz, h0, h1, zd in getattr(self, "scorched", []):
            if abs(n_world[2]) >= 0.5:
                continue
            out = 0 if abs(n_bld[0]) > 0.5 else 1
            if axis != out or side != np.sign(n_bld[out]):
                continue
            face, h = p[:, out], p[:, 1 - out]
            rise = z - zd
            hc, hw = (h0 + h1) / 2, (h1 - h0) / 2
            width = hw + 0.35 * np.clip(rise, 0, None)
            v = np.exp(-np.clip(rise, 0, None) / 3.5) * np.exp(-((h - hc) / np.maximum(width, 0.1)) ** 2)
            v = np.where((np.abs(face - fz) < 0.35) & (rise > -0.2), v, 0)
            v *= 0.6 + 0.6 * noise(p, 0.8, s + 5)
            dark += 0.9 * v

        # Undersides catch dirt; tops collect moss.
        if n_world[2] < -0.5:
            dark += 0.2
        mossy = np.zeros(N)
        if n_world[2] > 0.5:
            mossy += 0.6
        elif abs(n_world[2]) < 0.5:
            mossy += 0.5 * max(0.0, n_world[1])        # facing north
            mossy += 0.5 * np.exp(-np.clip(above, 0, None) / 1.2)
        mossy *= self.moss * np.clip((noise(p, 1.8, s + 6) - 0.25) * 2, 0, 1)

        gain = WEAR_GAIN.get(mat, 1.0)
        shade = self.age * (1 - gain * np.clip(dark, 0, 0.85))
        rgb = np.stack([shade * (1 + self.tint[0]), shade * (1 + self.tint[1]), shade * (1 + self.tint[2])], 1)
        rgb *= 1 - gain * mossy[:, None] * np.array([0.35, 0.15, 0.45])    # toward green-brown
        if mat == "rail":                                                  # rust
            rgb *= np.array([1.0, 0.62, 0.42]) * (0.8 + 0.4 * noise(p, 0.5, s + 7))[:, None]
        if mat == "door":                                                  # faded paint
            rgb *= np.array([0.95, 0.9, 0.92])
        return np.concatenate([np.clip(rgb, 0, 1), np.ones((N, 1))], 1)


class Mesh:
    """Flat-shaded quads, one list per material, in metres. With weathering, each quad is
    split into a grid about WEAR_STEP apart, each point carrying its own colour."""

    def __init__(self, mirror=False, weather=None, heading=0.0, drips=()):
        self.mirror = mirror    # flip across the long axis (x -> -x) as quads are written
        self.weather = weather
        self.heading = math.radians(heading)
        self.parts = {m: ([], [], [], []) for m in [*COLOURS, "lod_facade"]}
        self.colours = {m: [] for m in self.parts}
        self.drips = []         # edges rain runs off: (axis, side, face, h0, h1, z), building
                                # metres before mirroring; see wall() and ledge()
        self.known_drips = list(drips)   # from a first pass: colours are made as quads are, and
                                         # a streak can start at an edge not yet drawn
        self.windows = []       # the same, one per window, at its head (for soot)
        self.solids = []        # collision: boxes (x0, y0, z0, x1, y1, z1), and ramps
                                # (x0, y0, z0, x1, y1, (top at x0y0, x1y0, x1y1, x0y1))

    def quad(self, mat, pts, normal, uv=None):
        """uv: optional (u, v) per point, v counted up from the bottom; otherwise the texture is
        projected from the world, 3 m per tile."""
        pts = [np.array(p, float) for p in pts]
        n = np.array(normal, float)
        n_bld = n / np.linalg.norm(n)               # before mirroring, as the weathering sees it
        raw = [p.copy() for p in pts]
        if self.mirror:
            for p in pts:
                p[0] = -p[0]
            n[0] = -n[0]
        if np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), n) < 0:
            pts, raw = pts[::-1], raw[::-1]   # counter-clockwise seen from outside
            uv = uv[::-1] if uv else uv
        verts, norms, uvs, tris = self.parts[mat]
        b = len(verts)
        ax = int(np.argmax(np.abs(n)))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        if self.weather is None:
            for i, p in enumerate(pts):
                verts.append(tuple(p / UNIT_M))
                norms.append(tuple(n))
                uvs.append(uv[i] if uv else (p[u_ax] / 3.0, p[v_ax] / 3.0))
            tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
            return

        # A grid over the quad, by bilinear steps between its corners.
        def steps(a, b, c, d):
            e = (b - a + c - d) / 2
            if abs(n[2]) > 0.5:
                step = WEAR_STEP_FLAT
            else:
                step = WEAR_STEP_UP if abs(e[2]) > np.linalg.norm(e[:2]) else WEAR_STEP_ALONG
            return max(1, math.ceil(max(np.linalg.norm(b - a), np.linalg.norm(c - d)) / step))
        nu = steps(pts[0], pts[1], pts[2], pts[3])
        nv = steps(pts[0], pts[3], pts[2], pts[1])
        su, sv = np.meshgrid(np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1))
        su, sv = su.ravel()[:, None], sv.ravel()[:, None]
        lerp = lambda c: (c[0] * (1 - su) * (1 - sv) + c[1] * su * (1 - sv) + c[2] * su * sv + c[3] * (1 - su) * sv)
        grid, grid_raw = lerp(pts), lerp(raw)
        guv = lerp([np.array(t, float) for t in uv]) if uv else np.stack([grid[:, u_ax] / 3.0, grid[:, v_ax] / 3.0], 1)
        c, s = math.cos(self.heading), math.sin(self.heading)
        n_world = (n[0] * c + n[1] * s, -n[0] * s + n[1] * c, n[2])
        n_world = tuple(np.array(n_world) / np.linalg.norm(n_world))
        col = self.weather.colours(mat, grid_raw, n_bld, n_world, self.known_drips)
        verts += [tuple(p / UNIT_M) for p in grid]
        norms += [tuple(n)] * len(grid)
        uvs += [tuple(t) for t in guv]
        self.colours[mat] += [tuple(c_) for c_ in col]
        for j in range(nv):
            for i in range(nu):
                a = b + j * (nu + 1) + i
                tris += [(a, a + 1, a + nu + 2), (a, a + nu + 2, a + nu + 1)]

    def box(self, mat, x0, y0, z0, x1, y1, z1, bottom=False, solid=False):
        c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        self.quad(mat, [(x, y, z1) for x, y in c], (0, 0, 1))
        if bottom:
            self.quad(mat, [(x, y, z0) for x, y in c], (0, 0, -1))
        for (xa, ya), (xb, yb), n in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)),
                                       ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
            self.quad(mat, [(xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1)], n)
        if solid:
            self.solids.append((x0, y0, z0, x1, y1, z1))

    def beam(self, mat, p0, p1, t):
        """A square beam of side t from p0 to p1, with a block at each end, so beams meeting
        at a corner close it with no notch."""
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        for c in (p0, p1):
            self.box(mat, *(c - t / 2), *(c + t / 2), bottom=True)
        a = np.cross(d, (0, 0, 1)) if abs(d[2]) < 0.99 else np.array((1.0, 0, 0))
        a = a / np.linalg.norm(a) * t / 2
        b = np.cross(d, a)
        b = b / np.linalg.norm(b) * t / 2
        ring = [a + b, -a + b, -a - b, a - b]
        for i in range(4):
            r0, r1 = ring[i], ring[(i + 1) % 4]
            self.quad(mat, [p0 + r0, p0 + r1, p1 + r1, p1 + r0], (r0 + r1))


def wall(m, axis, side, face, h0, h1, z0, z1, openings):
    """A wall in the plane x = face (axis "x") or y = face (axis "y"), facing side (+1 or -1
    along that axis), running h0..h1 along the other axis, with rectangular openings
    (ha, hb, za, zb, kind); each opening gets reveals, and its glass or door set back."""
    def P(h, z, d=0.0):
        f = face - side * d
        return (f, h, z) if axis == "x" else (h, f, z)

    out = (side, 0, 0) if axis == "x" else (0, side, 0)
    along = (0, 1, 0) if axis == "x" else (1, 0, 0)
    k = 0 if axis == "x" else 1
    m.drips.append((k, side, face, h0, h1, z1))             # the roofline
    for ha, hb, za, zb, kind in openings:
        if kind in ("window", "small"):
            m.drips.append((k, side, face, ha, hb, za))     # the sill
            m.windows.append((k, side, face, ha, hb, zb))
    hs = sorted({h0, h1, *[o[0] for o in openings], *[o[1] for o in openings]})
    for ha, hb in zip(hs, hs[1:]):
        holes = sorted((o[2], o[3]) for o in openings if o[0] <= ha and o[1] >= hb)
        z = z0
        for za, zb in holes + [(z1, z1)]:
            if za > z:
                m.quad("sandstone", [P(ha, z), P(hb, z), P(hb, za), P(ha, za)], out)
            z = max(z, zb)
    for ha, hb, za, zb, kind in openings:
        dp = {"window": WIN_DEPTH, "small": WIN_DEPTH}.get(kind, DOOR_DEPTH)
        neg = tuple(-c for c in along)
        m.quad("frame", [P(ha, za), P(ha, za, dp), P(ha, zb, dp), P(ha, zb)], along)
        m.quad("frame", [P(hb, za), P(hb, za, dp), P(hb, zb, dp), P(hb, zb)], neg)
        m.quad("frame", [P(ha, za), P(ha, za, dp), P(hb, za, dp), P(hb, za)], (0, 0, 1))
        m.quad("frame", [P(ha, zb), P(ha, zb, dp), P(hb, zb, dp), P(hb, zb)], (0, 0, -1))
        hm = (ha + hb) / 2
        if kind.startswith("door"):
            m.quad("door", [P(ha, za, dp), P(hb, za, dp), P(hb, zb, dp), P(ha, zb, dp)], out)
            if kind == "door2":           # no strip: just the hairline where the leaves meet
                d2 = dp - 0.003
                m.quad("rail", [P(hm - 0.006, za, d2), P(hm + 0.006, za, d2), P(hm + 0.006, zb, d2),
                                P(hm - 0.006, zb, d2)], out)
        else:
            window_pane(m, P, out, along, (k, side, face), ha, hb, za, zb, dp, kind)
    if m.weather:
        wall_damage(m, P, out, (k, side, face), h0, h1, z0, z1, openings)


def _strip(m, mat, P, out, pts, w0, w1, d):
    """A thin line laid on a wall plane: pts are (h, z) points, its width tapering w0 to w1, d
    the depth into the wall (negative: out from it)."""
    pts = [np.array(p, float) for p in pts]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        t = b - a
        nrm = np.array((-t[1], t[0])) / (np.linalg.norm(t) + 1e-9)
        wa = (w0 + (w1 - w0) * i / (len(pts) - 1)) / 2
        wb = (w0 + (w1 - w0) * (i + 1) / (len(pts) - 1)) / 2
        q = [a - nrm * wa, b - nrm * wb, b + nrm * wb, a + nrm * wa]
        m.quad(mat, [P(h, z, d) for h, z in q], out)


def window_pane(m, P, out, along, wall_key, ha, hb, za, zb, dp, kind):
    """A window's glass in whatever state the weathering leaves it: intact, cracked, broken
    to shards round the frame, gone, or boarded up. An open one shows a dark, gutted room."""
    w = m.weather
    if w:
        x, y, _ = P((ha + hb) / 2, 0)
        state = w.window_state(wall_key, ha, zb, za - w.ground(x, y) < 2.5)
    else:
        state = "intact"
    rng = w.rng_for("pane", *wall_key, ha, za) if w else None
    hm = (ha + hb) / 2
    halves = [(ha, hm - 0.03), (hm + 0.03, hb)] if kind == "window" else [(ha, hb)]
    if state in ("broken", "missing", "boarded"):
        dark_room(m, P, out, along, ha, hb, za, dp, kind)
    if state in ("intact", "cracked"):
        m.quad("glass", [P(ha, za, dp), P(hb, za, dp), P(hb, zb, dp), P(ha, zb, dp)], out)
    if state == "cracked":            # a star of cracks in one pane or both
        for h0, h1 in halves:
            if rng.random() < 0.4:
                continue
            c = np.array((rng.uniform(h0 + 0.1, h1 - 0.1), rng.uniform(za + 0.1, zb - 0.1)))
            for a in rng.uniform(0, 2 * math.pi, rng.integers(4, 9)):
                end = c + rng.uniform(0.15, 0.8) * np.array((math.cos(a), math.sin(a)))
                end = np.clip(end, (h0 + 0.01, za + 0.01), (h1 - 0.01, zb - 0.01))
                mid = (c + end) / 2 + rng.normal(0, 0.02, 2)
                _strip(m, "frame", P, out, [c, mid, end], 0.008, 0.003, dp - 0.004)
    if state == "broken":             # jagged shards left in the frame
        for h0, h1 in halves:
            ring = [(h0, za), (h1, za), (h1, zb), (h0, zb)]
            centre = np.array(((h0 + h1) / 2, (za + zb) / 2))
            pts = []
            for i in range(4):
                a, b = np.array(ring[i]), np.array(ring[(i + 1) % 4])
                for t in np.linspace(0, 1, 5)[:-1]:
                    pts.append(a + (b - a) * t)
            inset = rng.uniform(0.0, 0.55, len(pts)) * (rng.random(len(pts)) < 0.75)
            inner = [p + (centre - p) * f for p, f in zip(pts, inset)]
            for i in range(len(pts)):
                j = (i + 1) % len(pts)
                if inset[i] + inset[j] > 0.02:
                    m.quad("glass", [P(*pts[i], dp), P(*pts[j], dp), P(*inner[j], dp), P(*inner[i], dp)], out)
    if state == "boarded":            # planks across, with gaps between them
        n = int(rng.integers(3, 6))
        edges = np.linspace(za - 0.05, zb + 0.05, n + 1)
        for z0, z1 in zip(edges, edges[1:]):
            if rng.random() < 0.15:
                continue              # a plank gone
            tilt = rng.normal(0, 0.04)
            pts = [(ha - 0.1, z0 + 0.02 - tilt), (hb + 0.1, z0 + 0.02 + tilt),
                   (hb + 0.1, z1 - 0.02 + tilt), (ha - 0.1, z1 - 0.02 - tilt)]
            m.quad("board", [P(h, z, -0.03) for h, z in pts], out)
    if kind == "window" and (state in ("intact", "cracked", "boarded") or rng.random() < 0.5):
        a, b = P(hm - 0.03, za, dp), P(hm + 0.03, zb, dp - 0.05)   # the mullion
        m.box("frame", min(a[0], b[0]), min(a[1], b[1]), za, max(a[0], b[0]), max(a[1], b[1]), zb)


def dark_room(m, P, out, along, ha, hb, za, dp, kind):
    """What shows through an open window until the interiors are built: a dark, empty room,
    its faces turned inward."""
    floor = za - (WIN_SILL if kind == "window" else 1.7)
    ceil = floor + FLOOR_H - 0.3
    r0, r1, d0, d1 = ha - 0.6, hb + 0.6, dp, dp + 3.0
    m.quad("void", [P(r0, floor, d1), P(r1, floor, d1), P(r1, ceil, d1), P(r0, ceil, d1)], out)
    m.quad("void", [P(r0, floor, d0), P(r1, floor, d0), P(r1, floor, d1), P(r0, floor, d1)], (0, 0, 1))
    m.quad("void", [P(r0, ceil, d0), P(r1, ceil, d0), P(r1, ceil, d1), P(r0, ceil, d1)], (0, 0, -1))
    m.quad("void", [P(r0, floor, d0), P(r0, floor, d1), P(r0, ceil, d1), P(r0, ceil, d0)], along)
    m.quad("void", [P(r1, floor, d0), P(r1, floor, d1), P(r1, ceil, d1), P(r1, ceil, d0)],
           tuple(-c for c in along))


def wall_damage(m, P, out, wall_key, h0, h1, z0, z1, openings):
    """Cracks and spalls on a wall: cracks running from the corners of its openings, up from
    the ground and down from the roofline; spalled patches where the face has fallen away, some
    showing rusted rebar."""
    w = m.weather
    rng = w.rng_for("wall", *wall_key, h0, h1)
    sev = w.severity
    holes = [(a - 0.03, b + 0.03, c - 0.03, d + 0.03) for a, b, c, d, _ in openings]

    def ground_at(h):
        x, y, _ = P(h, 0)
        return w.ground(x, y)

    def blocked(h, z):
        return (not h0 + 0.05 < h < h1 - 0.05 or not z0 < z < z1 - 0.05 or z < ground_at(h) - 0.05
                or any(a < h < b and c < z < d for a, b, c, d in holes))

    def crack(h, z, angle, length, width, branch=True):
        pts, p = [np.array((h, z))], np.array((h, z), float)
        for _ in range(max(2, int(length / 0.12))):
            angle += rng.normal(0, 0.35)
            p = p + 0.12 * np.array((math.cos(angle), math.sin(angle)))
            if blocked(*p):
                break
            pts.append(p)
        if len(pts) > 1:
            _strip(m, "crack", P, out, pts, width, 0.004, -0.012)
            if branch and len(pts) > 4 and rng.random() < 0.4:
                i = int(rng.integers(2, len(pts) - 1))
                crack(*pts[i], angle + rng.choice((-1, 1)) * rng.uniform(0.4, 1.0),
                      length * 0.4, width * 0.6, branch=False)

    # From the corners of openings: down and out from the bottom ones, up and out from the top.
    for a, b, c, d, _ in openings:
        for h, z, up, sgn in ((a, c, False, -1), (b, c, False, 1), (a, d, True, -1), (b, d, True, 1)):
            if rng.random() < 0.45 * sev:
                base = math.pi / 2 if up else -math.pi / 2
                crack(h, z, base + sgn * rng.uniform(0.3, 0.9), rng.uniform(0.6, 3.0), rng.uniform(0.025, 0.045))
    length = h1 - h0
    # Up from the ground, settling cracks.
    for _ in range(rng.poisson(length / 5 * sev)):
        h = rng.uniform(h0 + 0.2, h1 - 0.2)
        crack(h, ground_at(h) + 0.05, math.pi / 2 + rng.normal(0, 0.4), rng.uniform(0.8, 3.5),
              rng.uniform(0.03, 0.06))
    # Down from the roofline.
    for _ in range(rng.poisson(length / 12 * sev)):
        crack(rng.uniform(h0 + 0.2, h1 - 0.2), z1 - 0.1, -math.pi / 2 + rng.normal(0, 0.4),
              rng.uniform(0.6, 2.5), rng.uniform(0.025, 0.045))
    # Spalls: ragged patches where the face has fallen away, more of them low down.
    for _ in range(rng.poisson(length / 9 * sev)):
        h = rng.uniform(h0 + 0.5, h1 - 0.5)
        g = ground_at(h)
        z = g + min(rng.exponential(1.5), z1 - g - 0.6) + 0.3
        r = rng.uniform(0.15, 0.55)
        if blocked(h, z) or any(a - r < h < b + r and c - r < z < d + r for a, b, c, d in holes):
            continue
        ang = np.sort(rng.uniform(0, 2 * math.pi, 9))
        ring = [(h + r * rng.uniform(0.5, 1.0) * math.cos(t), z + r * rng.uniform(0.5, 1.0) * math.sin(t))
                for t in ang]
        for i in range(len(ring)):
            q = [(h, z), ring[i], ring[(i + 1) % len(ring)], (h, z)]
            m.quad("spall", [P(hh, zz, -0.008) for hh, zz in q], out)
        if r > 0.3 and rng.random() < 0.5:     # rusted rebar across it
            _strip(m, "rail", P, out, [(h - r * 0.6, z + r * 0.1), (h + r * 0.6, z - r * 0.1)],
                   0.025, 0.025, -0.014)


def ledge(m, axis, side, face, h0, h1, z_top):
    """A sill ledge along a wall: a flat top LEDGE_OUT out from the wall at z_top, a face
    LEDGE_FACE deep, then a slope back into the wall over LEDGE_DROP."""
    def P(h, out, z):
        f = face + side * out
        return (f, h, z) if axis == "x" else (h, f, z)

    o, zf, zb = LEDGE_OUT, z_top - LEDGE_FACE, z_top - LEDGE_FACE - LEDGE_DROP
    m.drips.append((0 if axis == "x" else 1, side, face, h0, h1, zb))
    n_out = (side, 0, 0) if axis == "x" else (0, side, 0)
    k = math.hypot(LEDGE_DROP, o)
    n_slope = tuple(c * LEDGE_DROP / k for c in n_out[:2]) + (-o / k,)
    m.quad("sandstone", [P(h0, 0, z_top), P(h1, 0, z_top), P(h1, o, z_top), P(h0, o, z_top)], (0, 0, 1))
    m.quad("sandstone", [P(h0, o, z_top), P(h1, o, z_top), P(h1, o, zf), P(h0, o, zf)], n_out)
    m.quad("sandstone", [P(h0, o, zf), P(h1, o, zf), P(h1, 0, zb), P(h0, 0, zb)], n_slope)
    for h, sgn in ((h0, -1), (h1, 1)):
        n_end = (0, sgn, 0) if axis == "x" else (sgn, 0, 0)
        m.quad("sandstone", [P(h, 0, z_top), P(h, o, z_top), P(h, o, zf), P(h, 0, zb)], n_end)


def wall_with_openings(m, side, x_face, y0, y1, z0, z1, openings):
    """A long side of the main wing: the plane x = x_face."""
    wall(m, "x", side, x_face, y0, y1, z0, z1,
         [(a, b, za, zb, "door2" if k == "door" else k) for a, b, za, zb, k in openings])


def build(ground, mirror=False, weather=None, heading=0.0, drips=()):
    """The mesh for one site; ground(x, y) is the ground in metres above the reference's Z, in
    the building's own coordinates before any mirroring. With weather (a Weathering), the quads
    carry its colours, streaking down from drips (the edges a first pass recorded)."""
    hw, hl = WING_W / 2, WING_L / 2
    wing_ground = [ground(x, y) for x in np.linspace(-hw, hw, 5) for y in np.linspace(-hl, hl, 20)]
    floor_z = max(wing_ground) + FLOOR_ABOVE
    top = floor_z + 3 * FLOOR_H + PARAPET
    bay = WING_L / BAYS

    m = Mesh(mirror, weather, heading, drips)
    m.solids.append((-hw, -hl, -FOOTING, hw, hl, top))

    # Long sides.
    for side in (1, -1):
        xf = side * hw
        openings = []
        for b in range(BAYS):
            yc = -hl + (b + 0.5) * bay
            for f in range(3):
                fz = floor_z + f * FLOOR_H
                if f == 0 and b in DOOR_BAYS:
                    openings.append((yc - DOOR_W / 2, yc + DOOR_W / 2, fz, fz + DOOR_H, "door"))
                    continue
                for k in (-1, 1):
                    wy = yc + k * WIN_OFFSET
                    openings.append((wy - WIN_W / 2, wy + WIN_W / 2, fz + WIN_SILL, fz + WIN_SILL + WIN_H, "window"))
        wall_with_openings(m, side, xf, -hl, hl, -FOOTING, top, openings)

        # Paired strips at every bay line, and the floor-line bands.
        for b in range(BAYS + 1):
            yb = -hl + b * bay
            for dy in (-(STRIP_GAP / 2 + STRIP_W), STRIP_GAP / 2):
                ya, yb2 = max(-hl, yb + dy), min(hl, yb + dy + STRIP_W)
                if yb2 > ya:
                    x0, x1 = sorted((xf, xf + side * STRIP_OUT))
                    m.box("sandstone", x0, ya, -FOOTING, x1, yb2, top)
        for f in (1, 2):
            ledge(m, "x", side, xf, -hl, hl, floor_z + f * FLOOR_H + WIN_SILL - 0.05)

        # Doors: a landing at floor level, then steps straight out from the wall to the ground,
        # with a railing down each side.
        for b in DOOR_BAYS:
            yc = -hl + (b + 0.5) * bay
            ly0, ly1 = yc - LANDING_ALONG / 2, yc + LANDING_ALONG / 2
            lx0, lx1 = sorted((xf, xf + side * LANDING_OUT))
            m.box("concrete", lx0, ly0, -FOOTING, lx1, ly1, floor_z, solid=True)
            out0 = xf + side * LANDING_OUT
            g = ground(out0 + side * 1.0, yc)
            steps = max(1, math.ceil((floor_z - g) / RISER))
            rise = (floor_z - g) / steps
            for i in range(1, steps):
                x0, x1 = sorted((out0 + side * (i - 1) * TREAD, out0 + side * i * TREAD))
                m.box("concrete", x0, ly0, -FOOTING, x1, ly1, floor_z - i * rise)
            foot_x = out0 + side * (steps - 1) * TREAD
            # Walking on steps of boxes stops the player at the first edge: like Bethesda's own
            # stairs, the collision is a smooth ramp from the landing down to the ground. It runs
            # RAMP_PAST beyond the bottom step at the same slope, so it ends underground and
            # rises out of the terrain wherever the ground really is, with no lip to trip on.
            slope = rise / TREAD
            end_x = foot_x + side * RAMP_PAST
            zx = {out0: floor_z, end_x: g - slope * RAMP_PAST}
            rx0, rx1 = sorted((out0, end_x))
            m.solids.append((rx0, ly0, -FOOTING, rx1, ly1, (zx[rx0], zx[rx1], zx[rx1], zx[rx0])))
            foot_z = floor_z - (steps - 1) * rise
            for ry in (ly0 + RAIL_T, ly1 - RAIL_T):
                for px, pz in ((xf + side * RAIL_T, floor_z), (out0, floor_z), (foot_x, foot_z)):
                    m.beam("rail", (px, ry, pz), (px, ry, pz + RAIL_H), RAIL_T)
                m.beam("rail", (xf + side * RAIL_T, ry, floor_z + RAIL_H), (out0, ry, floor_z + RAIL_H), RAIL_T)
                m.beam("rail", (out0, ry, floor_z + RAIL_H), (foot_x, ry, foot_z + RAIL_H), RAIL_T)

    # End walls: strips and bands, no windows.
    for end in (1, -1):
        yf = end * hl
        m.drips.append((1, end, yf, -hw, hw, top))
        m.quad("sandstone", [(-hw, yf, -FOOTING), (hw, yf, -FOOTING), (hw, yf, top), (-hw, yf, top)], (0, end, 0))
        for xs in (-hw + 2.0, 0.0, hw - 2.0):
            for dx in (-(STRIP_GAP / 2 + STRIP_W), STRIP_GAP / 2):
                y0, y1 = sorted((yf, yf + end * STRIP_OUT))
                m.box("sandstone", xs + dx, y0, -FOOTING, xs + dx + STRIP_W, y1, top)
        for f in (1, 2):
            ledge(m, "y", end, yf, -hw, hw, floor_z + f * FLOOR_H + WIN_SILL - 0.05)

    # Roof and parapet cap.
    m.quad("roof", [(-hw, -hl, top - 0.1), (hw, -hl, top - 0.1), (hw, hl, top - 0.1), (-hw, hl, top - 0.1)], (0, 0, 1))
    cap = 0.3
    for x0, y0, x1, y1 in ((-hw, -hl, hw, -hl + cap), (-hw, hl - cap, hw, hl),
                           (-hw, -hl, -hw + cap, hl), (hw - cap, -hl, hw, hl)):
        m.box("band", x0, y0, top - 0.1, x1, y1, top + 0.1)

    # The one-story L: the orderly room east of the main wing, the arms room on its west side
    # running further north. Its floor is a step above the ground at the company entrance.
    (ox0, oy0, ox1, oy1, _), (ax0, ay0, ax1, ay1, _) = bo.boxes()[1:]
    door_x = ox0 + 0.4 + DOOR_W / 2           # the entrance, at the orderly room's west end
    l_floor = ground(door_x, oy0 - 1.0) + RISER
    l_top = l_floor + L_HEIGHT
    sill, head = l_floor + 1.0, l_floor + 1.0 + WIN_H
    win = lambda c: (c - WIN_W / 2, c + WIN_W / 2, sill, head, "window")
    small = lambda c: (c - 0.4, c + 0.4, l_floor + 1.7, l_floor + 2.2, "small")
    m.solids += [(ox0, oy0, -FOOTING, ox1, oy1, l_top), (ax0, ay0, -FOOTING, ax1, ay1, l_top)]
    # Orderly room. South: the entrance, then the First Sergeant's window.
    wall(m, "y", -1, oy0, ox0, ox1, -FOOTING, l_top,
         [(door_x - DOOR_W / 2, door_x + DOOR_W / 2, l_floor, l_floor + DOOR_H, "door2"),
          win(ox1 - 2.5)])
    # East: the First Sergeant's window to the south, the CO's to the north.
    wall(m, "x", 1, ox1, oy0, oy1, -FOOTING, l_top, [win(oy0 + 2.5), win(oy1 - 2.5)])
    # North: the bathroom's small window to the west, the CO's window to the east.
    wall(m, "y", 1, oy1, ox0, ox1, -FOOTING, l_top, [small(ox0 + 1.5), win(ox1 - 2.5)])
    # Arms room: no windows, no outside door. West, north, and east beyond the orderly room.
    wall(m, "x", -1, ax0, ay0, ay1, -FOOTING, l_top, [])
    wall(m, "y", 1, ay1, ax0, ax1, -FOOTING, l_top, [])
    wall(m, "x", 1, ax1, oy1, ay1, -FOOTING, l_top, [])
    # Roofs, a band below the parapet, and the cap along every outside edge.
    for x0, y0, x1, y1 in ((ox0, oy0, ox1, oy1), (ax0, ay0, ax1, ay1)):
        m.quad("roof", [(x0, y0, l_top - 0.1), (x1, y0, l_top - 0.1), (x1, y1, l_top - 0.1), (x0, y1, l_top - 0.1)],
               (0, 0, 1))
    for x0, y0, x1, y1 in ((ox0, oy0 - BAND_OUT, ox1, oy0), (ox1, oy0, ox1 + BAND_OUT, oy1),
                           (ox0, oy1, ox1, oy1 + BAND_OUT), (ax0 - BAND_OUT, ay0, ax0, ay1),
                           (ax0, ay1, ax1, ay1 + BAND_OUT), (ax1, oy1, ax1 + BAND_OUT, ay1)):
        m.box("band", x0, y0, l_top - 0.9, x1, y1, l_top - 0.6)
        m.box("band", x0, y0, l_top - 0.1, x1, y1, l_top + 0.1)
    # The entrance step: a pad the width of the door, one riser up from the ground.
    px0, px1 = door_x - DOOR_W / 2 - 0.3, door_x + DOOR_W / 2 + 0.3
    m.box("concrete", px0, oy0 - 1.2, -FOOTING, px1, oy0, l_floor)
    pad_len = 1.2 + RAMP_PAST
    g_pad = l_floor - RISER * pad_len / 1.2
    m.solids.append((px0, oy0 - pad_len, -FOOTING, px1, oy0, (g_pad, g_pad, l_floor, l_floor)))

    return m, floor_z, top, l_top


LOD_PATH = "LOD/" + MOD_PATH
LOD_BELOW = 2.0                # the facade texture starts this far below the main floor
LOD_TEXTURES = ("sandstone", "roof", "lod_facade")
LOD_WEAR = (0.55, 0.55, 0.5)   # the weathering's typical darkening, for the LOD textures
LOD_MATERIAL_TEMPLATE = r"Materials\LOD\HitTechExtALargeLOD.BGSM"   # in Fallout4 - Materials.ba2


def facade_texture(path):
    """One long wall of the main wing, painted for distant LOD: windows, ledges and doors on
    sandstone. Covers the wall's whole length, and from LOD_BELOW under the main floor to the top.
    The same for every site, since the texture is laid out from the main floor."""
    W, H = 1024, 256
    span = LOD_BELOW + 3 * FLOOR_H + PARAPET
    px = lambda y: (y + WING_L / 2) / WING_L * W
    py = lambda z: (span - (z + LOD_BELOW)) / span * H        # z from the main floor
    img = Image.new("RGB", (W, H), COLOURS["sandstone"])
    d = ImageDraw.Draw(img)
    bay = WING_L / BAYS
    for f in (1, 2):                                          # the ledges' shadowed undersides
        zt = f * FLOOR_H + WIN_SILL - 0.05 - LEDGE_FACE
        d.rectangle([0, py(zt), W, py(zt - LEDGE_DROP)], fill=COLOURS["band"])
    for b in range(BAYS):
        yc = -WING_L / 2 + (b + 0.5) * bay
        for f in range(3):
            fz = f * FLOOR_H
            if f == 0 and b in DOOR_BAYS:
                d.rectangle([px(yc - DOOR_W / 2), py(fz + DOOR_H), px(yc + DOOR_W / 2), py(fz)], fill=COLOURS["door"])
                continue
            for k in (-1, 1):
                wy = yc + k * WIN_OFFSET
                d.rectangle([px(wy - WIN_W / 2), py(fz + WIN_SILL + WIN_H), px(wy + WIN_W / 2), py(fz + WIN_SILL)],
                            fill=COLOURS["glass"], outline=COLOURS["frame"])
    img.save(path, pixel_format="DXT1")


def build_lod(floor_z, top, l_top, mirror):
    """The distant stand-in: the main wing and the L as plain boxes, the long walls carrying the
    painted facade."""
    m = Mesh(mirror)
    hw, hl = WING_W / 2, WING_L / 2
    zb, span = floor_z - LOD_BELOW, LOD_BELOW + 3 * FLOOR_H + PARAPET
    for side in (1, -1):
        x = side * hw
        m.quad("sandstone", [(x, -hl, -FOOTING), (x, hl, -FOOTING), (x, hl, zb), (x, -hl, zb)], (side, 0, 0))
        m.quad("lod_facade", [(x, -hl, zb), (x, hl, zb), (x, hl, top), (x, -hl, top)], (side, 0, 0),
               uv=[(0, 0), (1, 0), (1, (top - zb) / span), (0, (top - zb) / span)])
    for end in (1, -1):
        y = end * hl
        m.quad("sandstone", [(-hw, y, -FOOTING), (hw, y, -FOOTING), (hw, y, top), (-hw, y, top)], (0, end, 0))
    m.quad("roof", [(-hw, -hl, top), (hw, -hl, top), (hw, hl, top), (-hw, hl, top)], (0, 0, 1))
    for x0, y0, x1, y1, _ in bo.boxes()[1:]:
        m.box("sandstone", x0, y0, -FOOTING, x1, y1, l_top)
    return m


def write_lod(m, nif_path, name, tex, pyn):
    NifFile, NiShapeBuf, PynBufferTypes = pyn[:3]
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="NiNode", root_name=name)
    for mat, (verts, norms, uvs, tris) in m.parts.items():
        if not verts:
            continue
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(mat, verts, tris, uvs, norms, props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\{mat}_d.dds")
        shape.set_texture("Normal", f"{tex}\\{mat}_n.dds")
        shape.set_texture("Specular", f"{tex}\\{mat}_s.dds")
        # The LOD generator reads the textures from the shape's material file, as vanilla LOD has.
        shape.shader.name = f"materials\\{LOD_PATH.replace('/', chr(92))}\\{mat}.BGSM"
        shape.save_shader_attributes()
    nif.save()


def lod_material(template, texture_dir, mat):
    """A LOD material: vanilla's own (read from the game's archive, so none of Bethesda's files
    are in this repository) with its _d, _n and _s texture paths swapped for ours. Strings in a
    BGSM are a 32-bit length, then the text with a closing zero."""
    out, i, swaps = bytearray(), 0, 0
    while i < len(template):
        if i + 4 <= len(template):
            (n,) = struct.unpack_from("<I", template, i)
            s = template[i + 4:i + 3 + n] if 5 <= n < 260 and i + 4 + n <= len(template) else b""
            if s and template[i + 3 + n] == 0 and s.lower()[-6:] in (b"_d.dds", b"_n.dds", b"_s.dds"):
                new = f"{texture_dir}/{mat}{s[-6:].decode().lower()}".encode() + b"\0"
                out += struct.pack("<I", len(new)) + new
                i += 4 + n
                swaps += 1
                continue
        out.append(template[i])
        i += 1
    assert swaps == 3, f"expected 3 texture paths in the template, found {swaps}"
    return bytes(out)


def write_nif(m, nif_path, name, tex, pyn):
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, PhysicsProps, \
        pack_shapes, HAVOC_SCALE_FACTOR, ShaderFlags2 = pyn
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="BSFadeNode", root_name=name)
    for name, (verts, norms, uvs, tris) in m.parts.items():
        # Split into shapes of at most MAX_SHAPE_VERTS, between quads (each quad's vertices are
        # its own and in order, so a cut before a triangle whose vertices all lie past it is safe).
        cuts, start = [0], 0
        for i, t in enumerate(tris):
            if max(t) - start >= MAX_SHAPE_VERTS:
                start = min(t)
                cuts.append(i)
        cuts.append(len(tris))
        for k, (t0, t1) in enumerate(zip(cuts, cuts[1:])):
            if t1 <= t0:
                continue
            v0 = min(min(t) for t in tris[t0:t1])
            v1 = max(max(t) for t in tris[t0:t1]) + 1
            part_tris = [tuple(i - v0 for i in t) for t in tris[t0:t1]]
            props = NiShapeBuf()
            props.bufType = PynBufferTypes.BSTriShapeBufType
            props.hasFullPrecision = 1
            shape = nif.createShapeFromData(name if k == 0 else f"{name}_{k}", verts[v0:v1], part_tris,
                                            uvs[v0:v1], norms[v0:v1], props=props, parent=nif.root)
            shape.shader._checked_for_materials = True
            shape.shader._materials = None
            shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
            shape.set_texture("Diffuse", f"{tex}\\{name}.dds")
            shape.set_texture("Normal", f"{tex}\\flat_n.dds")
            if m.colours[name]:            # the weathering: vertex colours darken the texture
                shape.set_colors(m.colours[name][v0:v1])
                shape.shader.properties.shaderflags2_set(ShaderFlags2.VERTEX_COLORS)
            shape.save_shader_attributes()

    coll_verts, coll_tris = [], []
    s = 1 / UNIT_M / HAVOC_SCALE_FACTOR
    for x0, y0, z0, x1, y1, z1 in m.solids:
        tops = z1 if isinstance(z1, tuple) else (z1,) * 4
        if m.mirror:
            x0, x1, tops = -x1, -x0, (tops[1], tops[0], tops[3], tops[2])
        foot = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        b = len(coll_verts)
        coll_verts += [(x * s, y * s, z0 * s) for x, y in foot]
        coll_verts += [(x * s, y * s, zt * s) for (x, y), zt in zip(foot, tops)]
        for q in ((4, 5, 6, 7), (0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            coll_tris += [[b + q[0], b + q[1], b + q[2]], [b + q[0], b + q[2], b + q[3]]]
    physics = PhysicsProps(is_dynamic=False,
                           body_props_raw=bytes.fromhex("00ff003f003fcd3e01024c3deeff7f7f"),
                           collision_filter_info=1)
    packed = pack_shapes([CollisionShape(shape_type="compressed_mesh", name="collision",
                                         transform=None, verts=coll_verts, faces=coll_tris,
                                         convex_radius=0.0, children=[], physics=physics)])
    BSXFlags.New(nif, flags=130, parent=nif.root)       # "has Havok": see make_barracks_blockout.py
    coll = nif.root.add_collision(None, flags=128,
                                  collision_type=PynBufferTypes.bhkNPCollisionObjectBufType, body_id=0)
    bhkPhysicsSystem.New(nif, data=packed, parent=coll)
    nif.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    ap.add_argument("--site", type=int, help="build only this site (see barracks_sites.json)")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, ShaderFlags2 = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, PhysicsProps,
           pack_shapes, HAVOC_SCALE_FACTOR, ShaderFlags2)

    out = out_dir("barracks")
    meta = json.loads((out / "heightmap.json").read_text())
    cells = json.loads((out / "cells.json").read_text())
    nx, ny = meta["points"]
    zmap = np.fromfile(out / "heightmap16.raw", dtype="<u2").reshape(ny, nx) * meta["game_units_per_pixel_step"]
    pt_m = POINT_UNITS * UNIT_M
    sites = json.loads((Path(__file__).parent / "barracks_sites.json").read_text())["sites"]
    if args.site:
        sites = [s for s in sites if s["n"] == args.site]

    # Textures: each colour with a little grain, so the walls aren't flat paint. Shared by all.
    mod = out / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1993)
    for name, rgb in COLOURS.items():
        grain = rng.normal(0, 5 if name in ("sandstone", "band", "concrete", "roof") else 1.5, (128, 128, 1))
        img = np.clip(np.array(rgb, float) + grain, 0, 255).astype(np.uint8)
        Image.fromarray(img).save(tex_dir / f"{name}.dds", pixel_format="DXT1")
    Image.new("RGB", (4, 4), (128, 128, 255)).save(tex_dir / "flat_n.dds", pixel_format="DXT1")
    facade_texture(tex_dir / "lod_facade.dds")
    # The Creation Kit's LOD generator wants every texture a LOD model uses under Textures\LOD,
    # and builds its atlas from uncompressed TGA copies under <game>\Source\TGATextures.
    lod_tex_dir = mod / "Textures" / LOD_PATH
    tga_dir = out / "source" / "TGATextures" / LOD_PATH
    lod_tex_dir.mkdir(parents=True, exist_ok=True)
    tga_dir.mkdir(parents=True, exist_ok=True)
    # Each diffuse needs a normal and a specular map named to match: name_d, name_n, name_s.
    # Specular: red is shine, green is smoothness; concrete has little of either.
    # All three the same size as the diffuse, or the atlas build fails.
    lod_files = []
    for t in LOD_TEXTURES:
        d = Image.open(tex_dir / f"{t}.dds").convert("RGB")
        # About as dark as the weathering leaves the close-up model, so nothing brightens as
        # the LOD swaps in.
        d = Image.fromarray((np.asarray(d, float) * LOD_WEAR).astype(np.uint8))
        for suffix, img in (("d", d), ("n", Image.new("RGB", d.size, (128, 128, 255))),
                            ("s", Image.new("RGB", d.size, (12, 20, 0)))):
            name = f"{t}_{suffix}"
            img.save(lod_tex_dir / f"{name}.dds", pixel_format="DXT1")
            img.save(tga_dir / f"{name}.tga")
            lod_files.append(name)
    lod_tex = "textures\\" + LOD_PATH.replace("/", "\\")
    tex = "textures\\" + MOD_PATH.replace("/", "\\")
    lod_dir = mod / "Meshes" / LOD_PATH
    lod_dir.mkdir(parents=True, exist_ok=True)

    # One model per site, its main floor, steps and entrance fitted to the ground there; each is
    # placed with its origin on the lowest ground under its footprint.
    rows = []
    for site in sites:
        cx, cy, hd = site["photo_x"], site["photo_y"], math.radians(site["heading"])

        sx = -1 if site.get("mirrored") else 1

        def ground_units(x, y):
            x = sx * x
            e, n = x * math.cos(hd) + y * math.sin(hd), -x * math.sin(hd) + y * math.cos(hd)
            return zmap[int(round((cy - n) / pt_m)), int(round((cx + e) / pt_m))]

        corners = [(x, y) for b in bo.boxes() for x in (b[0], b[2]) for y in (b[1], b[3])]
        ref_z = min(ground_units(x, y) for x, y in corners)
        ground = lambda x, y: (ground_units(x, y) - ref_z) * UNIT_M
        # A plain first pass finds the edges rain runs off and the windows; then the weathered
        # build, seeded by the site so every building wears differently.
        plain = build(ground, sx < 0)[0]
        weather = Weathering(site["n"], site["heading"], ground)
        weather.pick_scorched(plain.windows)
        m, floor_z, top, l_top = build(ground, sx < 0, weather, site["heading"], plain.drips)
        name = f"Barracks{site['n']:02d}"
        nif_path = mesh_dir / f"{name}.nif"
        write_nif(m, nif_path, name, tex, pyn)
        write_lod(build_lod(floor_z, top, l_top, sx < 0), lod_dir / f"{name}_lod.nif", f"{name}_lod", lod_tex, pyn)
        gx = cells["x_range"][0] * CELL_UNITS + cx / UNIT_M
        gy = (cells["y_range"][1] + 1) * CELL_UNITS - cy / UNIT_M
        v = np.array([p for part in m.parts.values() for p in part[0]])   # object bounds, game units
        lo, hi = np.floor(v.min(0)).astype(int), np.ceil(v.max(0)).astype(int)
        rows.append((site["n"], f"{MOD_PATH}/{name}.nif".replace("/", "\\"), round(gx), round(gy), round(ref_z),
                     site["heading"], math.floor(gx / CELL_UNITS), math.floor(gy / CELL_UNITS), *lo, *hi,
                     f"{LOD_PATH}/{name}_lod.nif".replace("/", "\\")))
        print(f"{name}: X {gx:.0f} Y {gy:.0f} Z {ref_z:.0f} rot {site['heading']:.1f}; "
              f"main floor {floor_z:.2f} m up")

    # The placement list for the FO4Edit script.
    if not args.site:
        with open(out / "barracks_placements.csv", "w", newline="") as f:
            f.write("n,model,x,y,z,rot_z,cell_x,cell_y,bound_x1,bound_y1,bound_z1,bound_x2,bound_y2,bound_z2,lod_model\n")
            for r in rows:
                f.write(",".join(str(v) for v in r) + "\n")
        print(f"{len(rows)} sites; placements in {(out / 'barracks_placements.csv').relative_to(ROOT)}")
    if args.install:
        data = Path(args.install)
        files = [mesh_dir / f"Barracks{r[0]:02d}.nif" for r in rows]
        files += [lod_dir / f"Barracks{r[0]:02d}_lod.nif" for r in rows]
        files += [tex_dir / "flat_n.dds", tex_dir / "lod_facade.dds"] + [tex_dir / f"{n}.dds" for n in COLOURS]
        files += [lod_tex_dir / f"{t}.dds" for t in lod_files]
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        for t in lod_files:   # the Creation Kit reads ..\Source\TGATextures from the game folder: beside it
            dest = data.parent.parent / "Source" / "TGATextures" / LOD_PATH / f"{t}.tga"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tga_dir / f"{t}.tga", dest)
        # The LOD materials, made from vanilla's own LOD material in the game's archive.
        template = ba2.read(data / "Fallout4 - Materials.ba2", LOD_MATERIAL_TEMPLATE)
        for t in LOD_TEXTURES:
            dest = data / "Materials" / LOD_PATH / f"{t}.BGSM"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(lod_material(template, LOD_PATH, t))
        print(f"  installed {len(files) + len(LOD_TEXTURES)} files under {data}")


if __name__ == "__main__":
    main()
