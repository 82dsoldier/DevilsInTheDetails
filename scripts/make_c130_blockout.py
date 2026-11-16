"""A block-out of the C-130's cargo compartment, rigged for a jump: the right size and shape,
plain colours, no detail.

    python scripts/make_c130_blockout.py [--length 15] [--scale 1.0] [--install "<Fallout 4>/Data"]

The cabin, in its own coordinates (metres; +y runs forward toward the flight deck, +x to the
right (starboard), the cargo floor at z 0, the origin at the middle of the floor between the
forward bulkhead and the ramp hinge):
  hull          seen from inside: the side walls bulge gently outward as they rise, then round
                over into an arched ceiling; flat floor; the closed ramp (RAMP_L) aft
  troop seats   four rows, red webbing: outboard along each side wall facing in, and the
                centerline rows back to back down the middle, packed in like sardines
  doors         one paratroop doorway in each side wall, just forward of the ramp hinge, open
                for the jump (the doors themselves are C130_Door.nif, the activator); round red
                and green jump lights forward of each
  portholes     round windows down each side
  anchor cables one each side, overhead, running aft to the doors
  forward end   the bulkhead, with steps up to the flight deck on the left (port) side
The hull, seats and steps have collision; the door, lights, portholes and cables lie on or
near the hull and don't need their own.

--length is the cargo floor's length (the true C-130H is 12.2 m; the author found that too short
in game, so the default is longer). --scale makes everything bigger, if it's too tight to move
through in power armor.

Writes to out/c130/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Aircraft/C130_Blockout.nif
  Textures/DevilsInTheDetails/Aircraft/blockout_<colour>.dds, flat_n.dds
Place it in an interior cell at 0, 0, 0.
"""
import argparse
import math
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, UNIT_M, out_dir                  # noqa: E402
from make_photo_overlay import load_pynifly                      # noqa: E402

# Size, metres (C-130H cargo compartment, except the length).
DEFAULT_LENGTH = 15.0          # the true 12.2 m (40 ft) felt short in game
FLOOR_W = 3.12                 # 10 ft 3 in at the floor
CABIN_H = 2.74                 # 9 ft at the centreline
WALL_TOP = 1.75                # where the side wall stops rising and rounds into the ceiling
BULGE = 0.12                   # how far each wall bows out between the floor and WALL_TOP
RAMP_L = 3.7                   # the closed ramp, aft of the hinge (the true 3 m, stretched like the cabin)
RAMP_ANGLE = 25.0              # degrees the closed ramp rises aft (data/reference/ramp.jpg)
AFT_WIDTH = 0.85               # the tail's width at the ramp's end, against the cabin's
AFT_HEIGHT = 0.08              # floor to ceiling at the ramp's end: the ramp meets the sloping cargo door, no end wall
DOOR_W, DOOR_H, DOOR_R = 0.91, 1.83, 0.15   # paratroop doors, 36 x 72 in; corner radius
DOOR_AFT = 0.15                # door's aft edge, forward of the ramp hinge
PORTHOLE_D, PORTHOLE_Z = 0.30, 1.45         # diameter, centre height
PORTHOLES = 6                  # each side, between the doors and the forward bulkhead
SEAT_W, SEAT_D, SEAT_Z = 0.52, 0.40, 0.45   # one troop seat: width, depth, height
SEAT_AFT_GAP = 0.9             # clear floor between the doors and the seats
CENTER_BACK_W, CENTER_BACK_H = 0.10, 1.05   # the centreline seats' shared backrest frame
CABLE_Z, CABLE_X, CABLE_D = 2.25, 0.75, 0.03   # anchor cables
STEPS_W, STEPS_L, STEPS_H = 0.8, 1.0, 1.0   # up to the flight deck, port side forward
LIGHT_D = 0.12                 # jump light diameter
ARC_STEPS, WALL_STEPS, ROUND_STEPS = 12, 6, 24
# The open doorway's top: the arch's first profile point, 1.88 m, near enough the door's 1.83 m
# plus its sill.
DOOR_TOP = WALL_TOP + (CABIN_H - WALL_TOP) * math.sin(math.pi / 2 / ARC_STEPS) + 1e-6
JAMB = 0.12                    # the hull's thickness, shown at the doorway's edges

COLOURS = {
    "hull": (104, 110, 92),     # insulation blankets, drab green-grey
    "floor": (62, 62, 60),
    "ramp": (78, 74, 66),
    "seat": (150, 42, 36),      # red nylon webbing
    "frame": (150, 150, 145),   # aluminium tubing
    "door": (176, 176, 166),
    "glass": (150, 185, 215),   # sky through the portholes
    "red": (230, 30, 25),
    "green": (40, 210, 60),
    "cable": (190, 190, 190),
    "sky": (170, 196, 222),     # out the open doors
    "ground": (96, 112, 70),
}
MOD_PATH = "DevilsInTheDetails/Aircraft"


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

    def box(self, x0, y0, z0, x1, y1, z1, sides="tbnsew"):
        faces = {
            "t": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            "b": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "s": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "e": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "n": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "w": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
        }
        for s in sides:
            pts, n = faces[s]
            self.quad(*[self.vert(p, n) for p in pts])

    def cylinder(self, p0, p1, r, steps=8):
        """A closed tube from p0 to p1 along the y axis (cables)."""
        (x, y0, z), y1 = p0, p1[1]
        rings = []
        for y in (y0, y1):
            ring = []
            for i in range(steps):
                a = 2 * math.pi * i / steps
                n = (math.cos(a), 0, math.sin(a))
                ring.append(self.vert((x + r * n[0], y, z + r * n[2]), n))
            rings.append(ring)
        for i in range(steps):
            j = (i + 1) % steps
            self.quad(rings[0][i], rings[0][j], rings[1][j], rings[1][i])

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


# --- The parts ---------------------------------------------------------------------------

def parts(length):
    """{name: (colour, collides, Mesh)} in metres."""
    fwd, hinge = length / 2, -length / 2
    aft = hinge - RAMP_L
    hw = FLOOR_W / 2
    p = {}

    # Hull: the cross-section run from the ramp's end to the forward bulkhead, seen from inside,
    # with both end walls closing it. Over the ramp the tail sweeps up: the closed ramp rises
    # aft from its hinge, the upper cargo door slopes down to meet it, and the sides draw in,
    # so the aft wall is a smaller arch, high up.
    hull = Mesh()
    prof = profile()
    rise = RAMP_L * math.tan(math.radians(RAMP_ANGLE))

    def section(t):
        """The profile t of the way from the hinge (0) to the ramp's end (1): (x, z) pairs."""
        w = 1 - t * (1 - AFT_WIDTH)
        h = 1 - t * (1 - AFT_HEIGHT / CABIN_H)
        return [(x * w, rise * t + z * h) for x, z in prof]

    def normal(x, z):
        if z <= WALL_TOP:         # the side walls
            return wall_normal(z, 1 if x > 0 else -1)
        top, b = hw + BULGE, CABIN_H - WALL_TOP     # the arch: the ellipse's normal, pointing in
        nx, nz = -x / (top * top), -(z - WALL_TOP) / (b * b)
        m = math.hypot(nx, nz)
        return (nx / m, 0.0, nz / m)

    # The paratroop doors are open (slid up inside, as for a jump): a hole in each side wall
    # from the floor to the first profile point of the arch, which sits at the door's top.
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    stations = [(aft, section(1.0)), (hinge, section(0.0)), (da, section(0.0)),
                (db, section(0.0)), (fwd, section(0.0))]
    rows = [[hull.vert((x, y, z), normal(x0, z0)) for (x, z), (x0, z0) in zip(sec, prof)]
            for y, sec in stations]
    for k, (r0, r1) in enumerate(zip(rows, rows[1:])):
        for i in range(len(prof) - 1):
            (xa, za), (xb, zb) = prof[i], prof[i + 1]
            if stations[k][0] == da and max(za, zb) <= DOOR_TOP and xa * xb > 0:
                continue                                   # the doorway
            hull.quad(r0[i], r0[i + 1], r1[i + 1], r1[i])
    for (y, sec), ny in ((stations[0], 1.0), (stations[-1], -1.0)):
        cx = 0.0
        cz = sum(z for _, z in sec) / len(sec)
        c = hull.vert((cx, y, cz), (0, ny, 0), (cx / 2, cz / 2))
        ring = [hull.vert((x, y, z), (0, ny, 0), (x / 2, z / 2)) for x, z in sec]
        for i in range(len(ring)):
            hull.tri(c, ring[i], ring[(i + 1) % len(ring)])   # closes along the floor too
    p["hull"] = ("hull", True, hull)

    floor, ramp = Mesh(), Mesh()
    floor.box(-hw, hinge, -0.1, hw, fwd, 0.002, "t")
    up = (0.0, -math.sin(math.radians(RAMP_ANGLE)), math.cos(math.radians(RAMP_ANGLE)))
    aw = hw * AFT_WIDTH
    ramp.quad(*[ramp.vert(v, up) for v in ((-hw, hinge, 0.002), (hw, hinge, 0.002),
                                           (aw, aft, rise + 0.002), (-aw, aft, rise + 0.002))])
    p["floor"] = ("floor", True, floor)
    p["ramp"] = ("ramp", True, ramp)

    # Troop seats, from just forward of the doors to the flight deck steps.
    y0 = hinge + DOOR_AFT + DOOR_W + SEAT_AFT_GAP
    per_row = int((fwd - STEPS_L - 0.3 - y0) / SEAT_W)
    y1 = y0 + per_row * SEAT_W
    seats, frame = Mesh(), Mesh()
    for side in (-1, 1):
        wall = wall_x(SEAT_Z) - 0.01
        xa, xb = sorted((side * wall, side * (wall - SEAT_D)))
        seats.box(xa, y0, SEAT_Z - 0.05, xb, y1, SEAT_Z)
        xa, xb = sorted((side * CENTER_BACK_W / 2, side * (CENTER_BACK_W / 2 + SEAT_D)))
        seats.box(xa, y0, SEAT_Z - 0.05, xb, y1, SEAT_Z)
    frame.box(-CENTER_BACK_W / 2, y0, 0, CENTER_BACK_W / 2, y1, CENTER_BACK_H)
    p["seats"] = ("seat", True, seats)
    p["centre_frame"] = ("frame", True, frame)

    # Round jump lights just forward of each door; portholes spaced down each side between the
    # seats' ends. The doors themselves are their own model (door_parts), for the activator.
    rims, glass, reds, greens = Mesh(), Mesh(), Mesh(), Mesh()
    ports = [y0 + (y1 - y0) * (i + 0.5) / PORTHOLES for i in range(PORTHOLES)]
    for side in (-1, 1):
        for y in ports:
            rims.on_wall(circle(y, PORTHOLE_Z, PORTHOLE_D / 2 + 0.04), side, 0.01)
            glass.on_wall(circle(y, PORTHOLE_Z, PORTHOLE_D / 2), side, 0.025)
        ly = db + 0.15 + LIGHT_D / 2
        reds.on_wall(circle(ly, 1.81, LIGHT_D / 2), side, 0.02)
        greens.on_wall(circle(ly, 1.61, LIGHT_D / 2), side, 0.02)
    p["porthole_rims"] = ("door", False, rims)
    p["portholes"] = ("glass", False, glass)
    p["light_red"] = ("red", False, reds)
    p["light_green"] = ("green", False, greens)

    cables = Mesh()
    for side in (-1, 1):
        cables.cylinder((side * CABLE_X, hinge - 0.3, CABLE_Z), (0, fwd, 0), CABLE_D / 2)
    p["anchor_cables"] = ("cable", False, cables)

    steps = Mesh()
    steps.box(-hw, fwd - STEPS_L, 0, -hw + STEPS_W, fwd, STEPS_H, "tsew")
    p["flight_deck_steps"] = ("frame", True, steps)
    return p, per_row


def door_parts(length):
    """The starboard paratroop doorway, open for the jump, as its own model for the jump door
    activator: ({name: (colour, collides, Mesh)}, origin). The origin is where the door's centre
    line meets the wall at the floor; the port door is the same model turned 180 degrees.
      jambs     the doorway's edges and top, the hull's thickness, in bright aluminium
      door      the door itself, slid up on its tracks to lie against the upper wall and ceiling
      platform  the jump platform, out over the slipstream at the sill
      outside   sky and ground a few metres out, so the doorway isn't a black hole
      activation an invisible slab filling the doorway: walking into it stops you, using it jumps"""
    hinge = -length / 2
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    origin = (wall_x(0), (da + db) / 2, 0.0)
    jambs, panel, glass, platform, sky, ground, block = (Mesh() for _ in range(7))

    zs = [DOOR_TOP * i / WALL_STEPS for i in range(WALL_STEPS + 1)]
    for y, ny in ((da, 1.0), (db, -1.0)):           # the aft and forward edges, facing in
        col = [(jambs.vert((wall_x(z), y, z), (0, ny, 0)),
                jambs.vert((wall_x(z) + JAMB, y, z), (0, ny, 0))) for z in zs]
        for (a, b), (c, d) in zip(col, col[1:]):
            jambs.quad(a, b, d, c)
    xt = wall_x(DOOR_TOP)
    jambs.quad(*[jambs.vert(p, (0, 0, -1)) for p in
                 ((xt, da, DOOR_TOP), (xt + JAMB, da, DOOR_TOP),
                  (xt + JAMB, db, DOOR_TOP), (xt, db, DOOR_TOP))])

    panel.on_wall(rounded_rect(da, DOOR_TOP + 0.08, db, DOOR_TOP + 0.75, DOOR_R), 1, 0.06)
    glass.on_wall(circle((da + db) / 2, DOOR_TOP + 0.41, PORTHOLE_D / 2), 1, 0.08)
    x0 = origin[0] + JAMB
    platform.box(x0, da, -0.04, x0 + 0.55, db, 0.0, "tnsew")

    # Out the door: ground below eye height, sky above, far enough out to look like distance.
    xo, w, eye = origin[0] + 6.0, 30.0, 1.4
    for m, z0, z1 in ((ground, -12.0, eye), (sky, eye, 14.0)):
        m.quad(*[m.vert(p, (-1, 0, 0)) for p in
                 ((xo, origin[1] - w, z0), (xo, origin[1] + w, z0),
                  (xo, origin[1] + w, z1), (xo, origin[1] - w, z1))])

    block.box(origin[0] - 0.04, da, 0.0, origin[0] + JAMB, db, DOOR_TOP)
    parts = {"jambs": ("door", False, jambs), "door": ("door", False, panel),
             "door_porthole": ("glass", False, glass), "platform": ("frame", False, platform),
             "outside_ground": ("ground", False, ground), "outside_sky": ("sky", False, sky),
             "activation": (None, True, block)}
    for _, _, m in parts.values():
        m.verts = [tuple(v[i] - origin[i] for i in range(3)) for v in m.verts]
    return parts, origin


def write_nif(path, root_name, built, s, tex, pyn):
    """One static model from {name: (colour, collides, Mesh)}: colour None is collision only."""
    NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape, \
        PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR = pyn
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="BSFadeNode", root_name=root_name)
    coll_verts, coll_tris = [], []
    for name, (colour, collides, m) in built.items():
        verts = [tuple(c * s for c in v) for v in m.verts]
        if colour:
            props = NiShapeBuf()
            props.bufType = PynBufferTypes.BSTriShapeBufType
            props.hasFullPrecision = 1
            shape = nif.createShapeFromData(name, verts, m.tris, m.uvs, m.norms,
                                            props=props, parent=nif.root)
            shape.shader._checked_for_materials = True
            shape.shader._materials = None
            shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
            shape.set_texture("Diffuse", f"{tex}\\blockout_{colour}.dds")
            shape.set_texture("Normal", f"{tex}\\flat_n.dds")
            shape.save_shader_attributes()
        if collides:
            base = len(coll_verts)
            coll_verts += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
            coll_tris += [[a + base, b + base, c + base] for a, b, c in m.tris]

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
    from pyn.nifconstants import HAVOC_SCALE_FACTOR

    s = args.scale / UNIT_M          # metres -> game units
    mod = out_dir("c130") / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / MOD_PATH, mod / "Textures" / MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_files = [tex_dir / "flat_n.dds"]
    Image.new("RGB", (4, 4), (128, 128, 255)).save(tex_files[0], pixel_format="DXT1")
    for name, rgb in COLOURS.items():
        f = tex_dir / f"blockout_{name}.dds"
        Image.new("RGB", (16, 16), rgb).save(f, pixel_format="DXT1")
        tex_files.append(f)
    tex = "textures\\" + MOD_PATH.replace("/", "\\")

    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR)
    built, per_row = parts(args.length)
    nif_path = mesh_dir / "C130_Blockout.nif"
    write_nif(nif_path, "C130_Blockout", built, s, tex, pyn)
    door_built, door_origin = door_parts(args.length)
    door_path = mesh_dir / "C130_Door.nif"
    write_nif(door_path, "C130_Door", door_built, s, tex, pyn)

    aisle = wall_x(SEAT_Z) - SEAT_D - (CENTER_BACK_W / 2 + SEAT_D)
    sc = args.scale
    print(f"{nif_path.relative_to(ROOT)} (length {args.length} m, scale {sc})")
    print(f"  cabin {args.length * sc:.1f} m + ramp {RAMP_L * sc:.1f} m; widest "
          f"{2 * (FLOOR_W / 2 + BULGE) * sc:.2f} m; ceiling {CABIN_H * sc:.2f} m; "
          f"aisle {aisle * sc:.2f} m ({aisle * s:.0f} units); {per_row} seats a row, {4 * per_row} in all")
    print("  place in an interior cell at 0, 0, 0; the floor is z 0, forward is +Y")
    ox, oy = door_origin[0] * s, door_origin[1] * s
    print(f"{door_path.relative_to(ROOT)}: the jump door activator, placed twice:")
    print(f"  starboard X {ox:.0f}  Y {oy:.0f}  Z 0, rotation Z 0")
    print(f"  port      X {-ox:.0f}  Y {oy:.0f}  Z 0, rotation Z 180")
    if args.install:
        data = Path(args.install)
        for f in [nif_path, door_path] + tex_files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
