"""A plain block-out of the C-130's cargo compartment, rigged for a jump: the right size, no detail.

    python scripts/make_c130_blockout.py [--scale 1.0] [--install "<Fallout 4>/Data"]

The cabin, in its own coordinates (metres; +y runs forward toward the flight deck, +x to the
right (starboard), the cargo floor at z 0, the origin at the middle of the floor between the
forward bulkhead and the ramp hinge):
  hull          the cargo compartment as a box, seen from inside: CABIN_L long plus the closed
                ramp (RAMP_L) aft, CABIN_W wide, CABIN_H high
  troop seats   four rows of SEATS_PER_ROW, red webbing: outboard along each side wall facing in,
                and the centerline rows back to back down the middle (64 jumpers, the C-130's
                load), packed in like sardines
  doors         one paratroop door in each side wall, just forward of the ramp hinge, closed;
                a red and a green jump light forward of each
  anchor cables one each side, overhead, running aft to the doors
  forward end   the bulkhead, with steps up to the flight deck on the left (port) side
Everything a player could bump into has collision; the cables and lights don't.

--scale makes it all bigger, if the true size is too tight to move through in power armor.

Writes to out/c130/mod/ (the layout of the game's Data folder):
  Meshes/DevilsInTheDetails/Aircraft/C130_Blockout.nif
  Textures/DevilsInTheDetails/Aircraft/blockout_<colour>.dds, flat_n.dds
Place it in an interior cell at 0, 0, 0.
"""
import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, UNIT_M, out_dir                  # noqa: E402
from make_photo_overlay import load_pynifly                      # noqa: E402

# Size, metres (C-130H cargo compartment).
CABIN_L, CABIN_W, CABIN_H = 12.2, 3.12, 2.74   # 40 ft floor, 10 ft 3 in wide, 9 ft high
RAMP_L = 3.0                                   # the closed ramp, aft of the hinge
DOOR_W, DOOR_H = 0.91, 1.83                    # paratroop doors, 36 x 72 in
DOOR_AFT = 0.15                                # door's aft edge, forward of the ramp hinge
SEAT_W, SEAT_D, SEAT_Z = 0.52, 0.40, 0.45      # one troop seat: width, depth, height
SEATS_PER_ROW = 16                             # four rows: 64 jumpers
SEAT_AFT_GAP = 0.9                             # clear floor between the doors and the seats
CENTER_BACK_W, CENTER_BACK_H = 0.10, 1.05      # the centerline seats' shared backrest frame
CABLE_Z, CABLE_X = 2.25, 0.75                  # anchor cables: height, distance off centreline
STEPS_W, STEPS_L, STEPS_H = 0.8, 1.0, 1.0      # up to the flight deck, port side forward
LIGHT = 0.12                                   # jump light, a small box

COLOURS = {
    "hull": (104, 110, 92),     # insulation blankets, drab green-grey
    "floor": (62, 62, 60),
    "ramp": (78, 74, 66),
    "seat": (150, 42, 36),      # red nylon webbing
    "frame": (150, 150, 145),   # aluminium tubing
    "door": (176, 176, 166),
    "red": (230, 30, 25),
    "green": (40, 210, 60),
    "cable": (190, 190, 190),
}
MOD_PATH = "DevilsInTheDetails/Aircraft"


def quad_faces(quads, flip=False):
    """Quads [(4 corners, normal)] -> verts, normals, UVs, triangles. flip: seen from inside."""
    verts, norms, uvs, tris = [], [], [], []
    for q, n in quads:
        if flip:
            q, n = q[::-1], tuple(-c for c in n)
        b = len(verts)
        verts += q
        norms += [n] * 4
        uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]   # counter-clockwise from the seen side
    return verts, norms, uvs, tris


def box_quads(x0, y0, z0, x1, y1, z1, sides="tbnsew"):
    """The faces of a box, counter-clockwise from outside."""
    q = {
        "t": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        "b": ([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], (0, 0, -1)),
        "s": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        "e": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
        "n": ([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0)),
        "w": ([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0)),
    }
    return [q[s] for s in sides]


def parts():
    """{name: (colour, collides, quads seen from outside, flip)} in metres."""
    hw, fwd, hinge = CABIN_W / 2, CABIN_L / 2, -CABIN_L / 2
    aft = hinge - RAMP_L
    p = {}
    # The hull, seen from inside: walls and ceiling, then the floor and ramp as their own colours.
    p["hull"] = ("hull", True, box_quads(-hw, aft, 0, hw, fwd, CABIN_H, "tnsew"), True)
    p["floor"] = ("floor", True, box_quads(-hw, hinge, -0.1, hw, fwd, 0, "t"), False)
    p["ramp"] = ("ramp", True, box_quads(-hw, aft, -0.1, hw, hinge, 0, "t"), False)

    # Troop seats: SEATS_PER_ROW a row, from just forward of the doors.
    y0 = hinge + DOOR_AFT + DOOR_W + SEAT_AFT_GAP
    y1 = y0 + SEATS_PER_ROW * SEAT_W
    seats, frames = [], []
    for side in (-1, 1):
        # Outboard: against the wall, facing in (the wall is the backrest).
        xa, xb = sorted((side * hw, side * (hw - SEAT_D)))
        seats += box_quads(xa, y0, SEAT_Z - 0.05, xb, y1, SEAT_Z)
        # Inboard: back to back on the centreline, facing out.
        xa, xb = sorted((side * CENTER_BACK_W / 2, side * (CENTER_BACK_W / 2 + SEAT_D)))
        seats += box_quads(xa, y0, SEAT_Z - 0.05, xb, y1, SEAT_Z)
    frames += box_quads(-CENTER_BACK_W / 2, y0, 0, CENTER_BACK_W / 2, y1, CENTER_BACK_H)
    p["seats"] = ("seat", True, seats, False)
    p["centre_frame"] = ("frame", True, frames, False)

    # Paratroop doors, closed, a hair proud of each wall; jump lights just forward of them.
    da, db = hinge + DOOR_AFT, hinge + DOOR_AFT + DOOR_W
    doors, reds, greens = [], [], []
    for side in (-1, 1):
        xa, xb = sorted((side * hw, side * (hw - 0.04)))
        doors += box_quads(xa, da, 0.05, xb, db, 0.05 + DOOR_H)
        la, lb = sorted((side * hw, side * (hw - 0.06)))
        ly = db + 0.15
        reds += box_quads(la, ly, 1.75, lb, ly + LIGHT, 1.75 + LIGHT)
        greens += box_quads(la, ly, 1.55, lb, ly + LIGHT, 1.55 + LIGHT)
    p["doors"] = ("door", True, doors, False)
    p["light_red"] = ("red", False, reds, False)
    p["light_green"] = ("green", False, greens, False)

    # Anchor cables, from the forward bulkhead aft to just past the doors.
    cables = []
    for side in (-1, 1):
        x = side * CABLE_X
        cables += box_quads(x - 0.015, aft + RAMP_L * 0.6, CABLE_Z - 0.015,
                            x + 0.015, fwd, CABLE_Z + 0.015)
    p["anchor_cables"] = ("cable", False, cables, False)

    # Steps up to the flight deck, port side at the forward bulkhead.
    p["flight_deck_steps"] = ("frame", True,
                              box_quads(-hw, fwd - STEPS_L, 0, -hw + STEPS_W, fwd, STEPS_H), False)
    return p


def main():
    ap = argparse.ArgumentParser()
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

    nif_path = mesh_dir / "C130_Blockout.nif"
    nif = NifFile()
    nif.initialize("FO4", str(nif_path), root_type="BSFadeNode", root_name="C130_Blockout")
    coll_verts, coll_tris = [], []
    for name, (colour, collides, quads, flip) in parts().items():
        verts, norms, uvs, tris = quad_faces(quads, flip)
        verts = [tuple(c * s for c in v) for v in verts]
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        props.hasFullPrecision = 1
        shape = nif.createShapeFromData(name, verts, tris, uvs, norms, props=props, parent=nif.root)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        shape.shader.properties.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        shape.set_texture("Diffuse", f"{tex}\\blockout_{colour}.dds")
        shape.set_texture("Normal", f"{tex}\\flat_n.dds")
        shape.save_shader_attributes()
        if collides:
            base = len(coll_verts)
            coll_verts += [tuple(c / HAVOC_SCALE_FACTOR for c in v) for v in verts]
            coll_tris += [[a + base, b + base, c + base] for a, b, c in tris]

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

    # The clearances that matter for moving through it.
    hw = CABIN_W / 2
    aisle = hw - SEAT_D - (CENTER_BACK_W / 2 + SEAT_D)
    print(f"{nif_path.relative_to(ROOT)} (scale {args.scale})")
    print(f"  aisle between the seat rows {aisle * args.scale:.2f} m ({aisle * s:.0f} units), "
          f"ceiling {CABIN_H * args.scale:.2f} m ({CABIN_H * s:.0f} units), "
          f"cables at {CABLE_Z * args.scale:.2f} m")
    print("  place in an interior cell at 0, 0, 0; the floor is z 0, forward is +Y")
    if args.install:
        data = Path(args.install)
        for f in [nif_path] + tex_files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
