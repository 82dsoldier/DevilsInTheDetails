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
Placement, size and the L come from make_barracks_blockout.py.

Writes to out/barracks/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Buildings/Barracks.nif
  Textures/DevilsInTheDetails/Buildings/<colour>.dds, flat_n.dds
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, POINT_UNITS, ROOT, UNIT_M, out_dir     # noqa: E402
from make_photo_overlay import load_pynifly                                   # noqa: E402
import make_barracks_blockout as bo                                           # noqa: E402

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
RAIL_H, RAIL_T = 0.95, 0.05
L_HEIGHT = 3.6                 # the one-story L, floor to roof

COLOURS = {
    "sandstone": (205, 188, 158), "band": (176, 160, 132), "glass": (38, 46, 54),
    "frame": (226, 224, 216), "door": (112, 74, 44), "concrete": (172, 170, 164),
    "rail": (92, 92, 90), "roof": (118, 114, 108),
}
MOD_PATH = "DevilsInTheDetails/Buildings"
FOOTING = bo.FOOTING


class Mesh:
    """Flat-shaded quads, one list per material, in metres."""

    def __init__(self):
        self.parts = {m: ([], [], [], []) for m in COLOURS}
        self.solids = []        # collision: boxes (x0, y0, z0, x1, y1, z1), and ramps
                                # (x0, y0, z0, x1, y1, (top at x0y0, x1y0, x1y1, x0y1))

    def quad(self, mat, pts, normal):
        pts = [np.array(p, float) for p in pts]
        n = np.array(normal, float)
        if np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), n) < 0:
            pts = pts[::-1]     # counter-clockwise seen from outside
        verts, norms, uvs, tris = self.parts[mat]
        b = len(verts)
        ax = int(np.argmax(np.abs(n)))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        for p in pts:
            verts.append(tuple(p / UNIT_M))
            norms.append(tuple(n))
            uvs.append((p[u_ax] / 3.0, p[v_ax] / 3.0))   # world-projected, 3 m per tile
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]

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
        pane = "door" if kind.startswith("door") else "glass"
        m.quad(pane, [P(ha, za, dp), P(hb, za, dp), P(hb, zb, dp), P(ha, zb, dp)], out)
        hm = (ha + hb) / 2
        if kind == "window":              # the mullion between the two panes
            a, b = P(hm - 0.03, za, dp), P(hm + 0.03, zb, dp - 0.05)
            m.box("frame", min(a[0], b[0]), min(a[1], b[1]), za, max(a[0], b[0]), max(a[1], b[1]), zb)
        elif kind == "door2":             # no strip: just the hairline where the leaves meet
            d2 = dp - 0.003
            m.quad("rail", [P(hm - 0.006, za, d2), P(hm + 0.006, za, d2), P(hm + 0.006, zb, d2),
                            P(hm - 0.006, zb, d2)], out)


def ledge(m, axis, side, face, h0, h1, z_top):
    """A sill ledge along a wall: a flat top LEDGE_OUT out from the wall at z_top, a face
    LEDGE_FACE deep, then a slope back into the wall over LEDGE_DROP."""
    def P(h, out, z):
        f = face + side * out
        return (f, h, z) if axis == "x" else (h, f, z)

    o, zf, zb = LEDGE_OUT, z_top - LEDGE_FACE, z_top - LEDGE_FACE - LEDGE_DROP
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR

    # Ground under the building, in metres above the reference's Z (the lowest point).
    out = out_dir("barracks")
    meta = json.loads((out / "heightmap.json").read_text())
    cells = json.loads((out / "cells.json").read_text())
    nx, ny = meta["points"]
    zmap = np.fromfile(out / "heightmap16.raw", dtype="<u2").reshape(ny, nx) * meta["game_units_per_pixel_step"]
    cx, cy = bo.CENTRE_PX
    pt_m = POINT_UNITS * UNIT_M

    def ground_units(x, y):
        e, n = bo.to_world(x, y)
        return zmap[int(round((cy - n) / pt_m)), int(round((cx + e) / pt_m))]

    corners = [(x, y) for b in bo.boxes() for x in (b[0], b[2]) for y in (b[1], b[3])]
    ref_z = min(ground_units(x, y) for x, y in corners)

    def ground(x, y):
        return (ground_units(x, y) - ref_z) * UNIT_M

    hw, hl = WING_W / 2, WING_L / 2
    wing_ground = [ground(x, y) for x in np.linspace(-hw, hw, 5) for y in np.linspace(-hl, hl, 20)]
    floor_z = max(wing_ground) + FLOOR_ABOVE
    top = floor_z + 3 * FLOOR_H + PARAPET
    bay = WING_L / BAYS

    m = Mesh()
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
            # stairs, the collision is a smooth ramp from the landing down to the ground.
            zx = {out0: floor_z, foot_x: g - 0.02}
            rx0, rx1 = sorted((out0, foot_x))
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
    g_pad = l_floor - RISER - 0.02
    m.solids.append((px0, oy0 - 1.2, -FOOTING, px1, oy0, (g_pad, g_pad, l_floor, l_floor)))

    # Textures: each colour with a little grain, so the walls aren't flat paint.
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
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    nif_path = mesh_dir / "Barracks.nif"
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="BSFadeNode", root_name="Barracks")
    for name, (verts, norms, uvs, tris) in m.parts.items():
        if not verts:
            continue
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(name, verts, tris, uvs, norms, props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\{name}.dds")
        shape.set_texture("Normal", f"{tex}\\flat_n.dds")
        shape.save_shader_attributes()

    coll_verts, coll_tris = [], []
    s = 1 / UNIT_M / HAVOC_SCALE_FACTOR
    for x0, y0, z0, x1, y1, z1 in m.solids:
        tops = z1 if isinstance(z1, tuple) else (z1,) * 4
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

    gx = cells["x_range"][0] * CELL_UNITS + cx / UNIT_M
    gy = (cells["y_range"][1] + 1) * CELL_UNITS - cy / UNIT_M
    nverts = sum(len(p[0]) for p in m.parts.values())
    print(f"{nif_path.relative_to(ROOT)}: {nverts} vertices, {len(m.solids)} collision boxes; "
          f"main floor {floor_z:.2f} m up, roof {top:.2f} m")
    print(f"Place at X {gx:.0f}  Y {gy:.0f}  Z {ref_z:.0f}, rotation Z {bo.HEADING_DEG % 360:.1f}")
    if args.install:
        data = Path(args.install)
        files = [nif_path, tex_dir / "flat_n.dds"] + [tex_dir / f"{n}.dds" for n in COLOURS]
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
