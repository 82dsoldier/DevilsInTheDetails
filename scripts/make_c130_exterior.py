"""The C-130 seen from outside, parked: a block-out at C-130H size, no detail.

    python scripts/make_c130_exterior.py [--install "<Fallout 4>/Data"]

The Devils' bird on Hanscom's East Ramp (DESIGN.md, "Hanscom Field: the first act"). The cabin
the player rides in is a separate model (make_c130_blockout.py), flying over Sicily; this one
never leaves the ground. Boarding is its open port paratroop door: a dark doorway with a
boarding step under it, where the boarding activator goes (C130_BoardingDoor.nif, the doorway's
size, no visible mesh).

In its own coordinates, metres: +y forward (the nose), +x to starboard, z up from the ground,
the origin on the ground under the fuselage at the wing's quarter chord.

  fuselage   29.8 m long, 4.3 m across, the cargo floor 1.0 m up; the nose rounded, the tail
             swept up over the ramp
  wing       40.4 m span, high on the fuselage, 4.9 m chord at the root, 2.4 m at the tips
  engines    four T56 nacelles under the wing, at 4.9 m and 9.9 m out, four-bladed props 4.1 m
             across
  tail       the fin's top 11.6 m up; the tailplane 16 m across
  gear       the main gear in sponsons low on each side, two wheels a side in tandem; twin
             nose wheels
All of it has collision except the propellers.

Writes to out/c130/mod/ (as make_c130_blockout.py):
  Meshes/DevilsInTheDetails/Aircraft/C130_Exterior.nif, C130_BoardingDoor.nif
  Textures/DevilsInTheDetails/Aircraft/c130_ext_<material>{,_n,_s}.dds
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
import make_c130_blockout as c130                                 # noqa: E402
from ddsutil import save_dds                                      # noqa: E402

LENGTH, NOSE_Y = 29.8, 15.0          # nose tip at +15, tail at -14.8
FUS_W, FUS_H = 4.3, 4.3
BELLY_Z = 0.9                        # the fuselage's underside (the floor's 1.0 m up)
SPAN = 40.4
ROOT_CHORD, TIP_CHORD = 4.9, 2.4
WING_Y = 0.5                         # the wing's chord centre
WING_Z = BELLY_Z + FUS_H - 0.15      # the wing's mid-plane, on top of the fuselage
ROOT_T, TIP_T = 0.75, 0.35           # wing thickness
ENGINES_X = (4.9, 9.9)
NACELLE_R, NACELLE_FRONT, NACELLE_BACK = 0.62, 5.4, -3.2
PROP_R, PROP_Y = 2.05, 5.75
FIN_TOP, FIN_ROOT, FIN_TIP = 11.6, 6.0, 2.6
TAILPLANE_SPAN, TP_ROOT, TP_TIP = 16.0, 3.6, 1.8
TAIL_UP_FROM = -5.5                  # where the underside starts sweeping up to the ramp
TAIL_END_Z = 4.4                     # the tail cone's centre at the very end
DOOR_Y, DOOR_W, DOOR_H = -5.2, 0.91, 1.83    # the port paratroop door's centre, size
DOOR_SILL = BELLY_Z + 0.15
SECTION_STEPS = 24

MATERIALS = {
    "ext_paint": (98, 104, 96),      # faded "European I" grey-green
    "ext_dark": (30, 30, 30),        # tyres, the open doorway, the props
    "ext_glass": (60, 75, 85),       # the flight deck windows
    "ext_metal": (150, 150, 146),    # gear legs, the step
}


def tex(rgb, seed):
    n = c130._smooth_noise(seed, 0.05)
    g = c130._noise(seed + 1, scale=0.03)
    img = np.array(rgb)[None, None, :] * (0.94 + 0.04 * n + g)[..., None]
    return img, g * 0.1


def write_textures(tex_dir):
    files = []
    for k, (name, rgb) in enumerate(MATERIALS.items()):
        img, h = tex(rgb, 80 + 2 * k)
        f = tex_dir / f"c130_{name}.dds"
        save_dds(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB"), f)
        fn = tex_dir / f"c130_{name}_n.dds"
        save_dds(Image.fromarray(np.clip(c130.normal_map(h), 0, 255).astype(np.uint8), "RGB"), fn)
        shine = {"ext_glass": (0.6, 0.7), "ext_metal": (0.4, 0.4)}.get(name, (0.12, 0.25))
        fs = tex_dir / f"c130_{name}_s.dds"
        Image.new("RGB", (64, 64), (round(shine[0] * 255), round(shine[1] * 255), 0)).save(fs, pixel_format="DXT1")
        files += [f, fn, fs]
        c130.MATERIALS[name] = (None, {})          # so c130.write_nif knows them
    return files


def section(y):
    """The fuselage's cross-section at y: (centre z, half width, half height)."""
    cz, hw, hh = BELLY_Z + FUS_H / 2, FUS_W / 2, FUS_H / 2
    nose_start = NOSE_Y - 4.5
    if y > nose_start:                                   # the nose rounds off
        f = (y - nose_start) / (NOSE_Y - nose_start)
        k = math.sqrt(max(0.0, 1 - f ** 2))
        return cz - 0.35 * f, max(hw * k, 0.05), max(hh * k * (1 - 0.1 * f), 0.05)
    if y < TAIL_UP_FROM:                                 # the belly sweeps up to the tail
        f = (TAIL_UP_FROM - y) / (TAIL_UP_FROM - (NOSE_Y - LENGTH))
        top = BELLY_Z + FUS_H - 0.6 * f ** 2
        bottom = BELLY_Z + (TAIL_END_Z - 0.4 - BELLY_Z) * f ** 1.3
        half_w = hw * (1 - 0.82 * f ** 1.5)
        return (top + bottom) / 2, max(half_w, 0.12), max((top - bottom) / 2, 0.12)
    return cz, hw, hh


def loft_fuselage(m):
    ys = list(np.linspace(NOSE_Y - LENGTH, TAIL_UP_FROM, 14)) + \
        list(np.linspace(TAIL_UP_FROM, NOSE_Y - 4.5, 10))[1:] + list(np.linspace(NOSE_Y - 4.5, NOSE_Y, 10))[1:]
    rings = []
    for y in ys:
        cz, hw, hh = section(y)
        ring = []
        for i in range(SECTION_STEPS + 1):
            a = 2 * math.pi * i / SECTION_STEPS
            # A rounded square-ish section (superellipse), like the C-130's.
            c, s = math.cos(a), math.sin(a)
            e = 2.6
            x = hw * math.copysign(abs(c) ** (2 / e), c)
            z = cz + hh * math.copysign(abs(s) ** (2 / e), s)
            n = (c / max(hw, 0.05), 0.0, s / max(hh, 0.05))
            ln = math.sqrt(n[0] ** 2 + n[2] ** 2)
            ring.append(m.vert((x, y, z), (n[0] / ln, 0, n[2] / ln), (i / SECTION_STEPS * 4, y / 4)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(SECTION_STEPS):
            m.quad(r0[i], r0[i + 1], r1[i + 1], r1[i])
    for ring, y, sgn in ((rings[0], ys[0], -1), (rings[-1], ys[-1], 1)):   # close the ends
        cz = section(y)[0]
        c = m.vert((0, y, cz), (0, sgn, 0))
        rim = [m.vert(m.verts[i], (0, sgn, 0)) for i in ring[:-1]]
        for i in range(SECTION_STEPS):
            m.tri(c, rim[i], rim[(i + 1) % SECTION_STEPS])


def surface(m, root, tip, chord_root, chord_tip, t_root, t_tip, axis="x", y_mid=0.0, sweep=0.0):
    """A wing-like surface from root to tip: a lens section (flat-ish bottom), chord along y.
    axis "x": spans across (root and tip are x); "z": spans upward (a fin; thickness along x)."""
    secs = []
    for f, base, chord, t in ((0, root, chord_root, t_root), (1, tip, chord_tip, t_tip)):
        yc = y_mid - sweep * f
        pts = []
        for k in range(9):                                  # leading edge round the top to trailing
            u = k / 8
            yy = yc + chord / 2 - u * chord
            thick = t * 4 * u * (1 - u) ** 0.9 * 1.2
            pts.append((yy, thick * 0.7))
        for k in range(7, 0, -1):
            u = k / 8
            yy = yc + chord / 2 - u * chord
            thick = t * 4 * u * (1 - u) ** 0.9 * 1.2
            pts.append((yy, -thick * 0.3))
        secs.append((base, pts))
    rings = []
    for base, pts in secs:
        ring = []
        for yy, off in pts:
            if axis == "x":
                p, n = (base[0], yy, base[2] + off), (0, 0, 1 if off >= 0 else -1)
            else:
                p, n = (base[0] + off, yy, base[2]), (1 if off >= 0 else -1, 0, 0)
            ring.append(m.vert(p, n, (yy / 3, (base[0] if axis == "x" else base[2]) / 3)))
        rings.append(ring)
    n = len(rings[0])
    for i in range(n):
        j = (i + 1) % n
        m.quad(rings[0][i], rings[0][j], rings[1][j], rings[1][i])
    for ring, sgn in ((rings[0], -1), (rings[1], 1)):       # end caps
        cen = [sum(m.verts[i][k] for i in ring) / n for k in range(3)]
        nn = (sgn, 0, 0) if axis == "x" else (0, 0, sgn)
        if axis == "x" and root[0] > tip[0]:
            nn = (-sgn, 0, 0)
        c = m.vert(cen, nn)
        rim = [m.vert(m.verts[i], nn) for i in ring]
        for i in range(n):
            m.tri(c, rim[i], rim[(i + 1) % n])


def parts():
    """{name: (material, collides, Mesh)} in metres."""
    paint, dark, glass, metal, props = (c130.Mesh() for _ in range(5))
    loft_fuselage(paint)

    # The wing, each side from the fuselage's centre line out (the root hidden inside).
    for sx in (-1, 1):
        surface(paint, (0.0, 0, WING_Z), (sx * SPAN / 2, 0, WING_Z + 0.25),
                ROOT_CHORD, TIP_CHORD, ROOT_T, TIP_T, y_mid=WING_Y, sweep=-0.4)
        for ex in ENGINES_X:
            x = sx * ex
            f = ex / (SPAN / 2)
            z = WING_Z + 0.25 * f - 0.45
            paint.tube((x, NACELLE_BACK, z), (x, NACELLE_FRONT, z), NACELLE_R, steps=12, caps=True)
            paint.tube((x, NACELLE_FRONT, z), (x, PROP_Y, z), NACELLE_R * 0.45, steps=10, caps=True)
            for b in range(4):                               # four blades, feathered
                a = math.radians(45 + 90 * b)
                tipx, tipz = x + PROP_R * math.cos(a), z + PROP_R * math.sin(a)
                props.tube((x, PROP_Y - 0.05, z), (tipx, PROP_Y - 0.05, tipz), 0.13, steps=4, caps=True)

    # The tail: the fin and the tailplane, on the tail cone.
    tail_y = NOSE_Y - LENGTH + 3.0
    cz, hw, hh = section(tail_y)
    fin_base = cz + hh - 0.2
    surface(paint, (0, 0, fin_base), (0, 0, FIN_TOP), FIN_ROOT, FIN_TIP, 0.55, 0.3,
            axis="z", y_mid=tail_y + 0.6, sweep=1.6)
    for sx in (-1, 1):
        surface(paint, (0.0, 0, cz + 0.2), (sx * TAILPLANE_SPAN / 2, 0, cz + 0.3),
                TP_ROOT, TP_TIP, 0.35, 0.2, y_mid=tail_y - 0.2, sweep=0.5)

    # The gear sponsons, low on each side, and the wheels.
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (FUS_W / 2 - 0.3), sx * (FUS_W / 2 + 0.55)))
        paint.box(x0, -3.4, BELLY_Z - 0.1, x1, 3.4, BELLY_Z + 1.9)
        for wy in (-0.8, 0.8):
            dark.tube((sx * (FUS_W / 2 + 0.05), wy, 0.6), (sx * (FUS_W / 2 + 0.55), wy, 0.6), 0.6, steps=14, caps=True)
    for wx in (-0.3, 0.3):
        dark.tube((wx - 0.15, 11.4, 0.45), (wx + 0.15, 11.4, 0.45), 0.45, steps=12, caps=True)
    metal.tube((0, 11.4, 0.45), (0, 11.4, BELLY_Z + 0.4), 0.09, steps=6)

    # The flight deck windows: a dark band round the nose.
    for sx in (-1, 1):
        y0, y1 = NOSE_Y - 4.2, NOSE_Y - 2.2
        z0, z1 = BELLY_Z + 3.0, BELLY_Z + 3.7
        x = sx * (FUS_W / 2 * 0.86) + sx * 0.02
        glass.quad(glass.vert((x, y0, z0), (sx, 0, 0)), glass.vert((x, y1, z0 - 0.15), (sx, 0, 0)),
                   glass.vert((x, y1, z1 - 0.1), (sx, 0, 0)), glass.vert((x, y0, z1), (sx, 0, 0)))
    yw = NOSE_Y - 1.6
    _, hwn, _ = section(yw)
    glass.quad(glass.vert((-hwn * 0.8, yw, BELLY_Z + 3.0), (0, 1, 0.3)), glass.vert((hwn * 0.8, yw, BELLY_Z + 3.0), (0, 1, 0.3)),
               glass.vert((hwn * 0.6, yw - 0.6, BELLY_Z + 3.6), (0, 1, 0.3)), glass.vert((-hwn * 0.6, yw - 0.6, BELLY_Z + 3.6), (0, 1, 0.3)))

    # The open port paratroop door: dark, just proud of the skin, with a step under it.
    x = -(FUS_W / 2) - 0.03
    y0, y1 = DOOR_Y - DOOR_W / 2, DOOR_Y + DOOR_W / 2
    z0, z1 = DOOR_SILL, DOOR_SILL + DOOR_H
    dark.quad(dark.vert((x, y0, z0), (-1, 0, 0)), dark.vert((x, y1, z0), (-1, 0, 0)),
              dark.vert((x, y1, z1), (-1, 0, 0)), dark.vert((x, y0, z1), (-1, 0, 0)))
    for k in range(3):                                       # a boarding stand: three steps
        h = DOOR_SILL * (k + 1) / 3
        metal.box(x - 0.3 * (3 - k), y0 - 0.1, 0.0, x - 0.3 * (2 - k), y1 + 0.1, h)
    return {"paint": ("ext_paint", True, paint), "dark": ("ext_dark", True, dark),
            "glass": ("ext_glass", True, glass), "metal": ("ext_metal", True, metal),
            "props": ("ext_dark", False, props)}


def door_parts():
    """The boarding activator's shape: a box filling the doorway, collision only."""
    m = c130.Mesh()
    x = -(FUS_W / 2)
    m.box(x - 0.25, DOOR_Y - DOOR_W / 2, DOOR_SILL, x + 0.05, DOOR_Y + DOOR_W / 2, DOOR_SILL + DOOR_H)
    return {"activation": (None, True, m)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.pynifly import BSXFlags, bhkPhysicsSystem
    from pyn.bhk_autounpack import CollisionShape, PhysicsProps
    from pyn.bhk_autopack import pack_shapes
    from pyn.nifconstants import HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, BSXFlags, bhkPhysicsSystem, CollisionShape,
           PhysicsProps, pack_shapes, HAVOC_SCALE_FACTOR, ShaderFlags1FO4, ShaderFlags2FO4)

    s = 1 / UNIT_M
    mod = out_dir("c130") / "mod"
    mesh_dir, tex_dir = mod / "Meshes" / c130.MOD_PATH, mod / "Textures" / c130.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    files = write_textures(tex_dir)
    tex = "textures\\" + c130.MOD_PATH.replace("/", "\\")
    nif = mesh_dir / "C130_Exterior.nif"
    c130.write_nif(nif, "C130_Exterior", parts(), s, tex, pyn)
    door = mesh_dir / "C130_BoardingDoor.nif"
    c130.write_nif(door, "C130_BoardingDoor", door_parts(), s, tex, pyn)
    files += [nif, door]
    print(f"{nif.relative_to(ROOT)}, {door.name}; the doorway's centre at "
          f"x {-(FUS_W / 2):.2f}, y {DOOR_Y:.2f}, z {DOOR_SILL + DOOR_H / 2:.2f} m")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed {len(files)} files under {data}")


if __name__ == "__main__":
    main()
