"""The stick's combat equipment, worn: the early-90s kit each man jumps with (the author: combat
equipment, period gear, not today's), as one skinned model so it goes where he goes.

    python scripts/make_jump_kit.py [--install "<Fallout 4>/Data"]

  T-10C main     on his back, olive drab, the rest of his static line stowed on it in yellow
                 loops (data/reference/1_958e...jpg)
  harness        olive drab webbing: main lift webs over his shoulders and down his front, a
                 chest strap, steel hardware
  T-10R reserve  across his belly on the harness, olive drab: four flaps closed over its front,
                 the ripcord pin where they meet, its cable to the silver handle (the author;
                 data/reference/T-10R reserve troop parachute-500x500w.png)
  ALICE ruck     under the reserve, as wide as his legs (the author). Seated it rides his
                 thighs, low on them, so it lies in his lap out toward his knees; standing it
                 hangs right under the reserve.
  M1950 case     the weapons case, flat, pale grey quilted canvas, armpit to mid-shin down his
                 left side (data/reference/1_bacd...jpg), rigid on his pelvis: standing, forward
                 of where his arm hangs; seated, tipped forward so its foot clears the seat.

The ruck and case differ seated and standing, which one skinned model can't do (on the thighs,
the ruck that sits right in his lap hangs too low standing; the case mustn't bend). So two
models, and the script swaps them as he gets up.

Built in his own frame (worn.py) and fitted to the vanilla male body in fatigues, measured off
FatiguesM.nif in its bind pose: his front about 0.11 m ahead of his middle at the chest (1.5 m
up), 0.17 at the belly (1.2-1.3 m), 0.14 at the hips (1.0 m); his back 0.17 behind at the
shoulder blades, 0.13 at the waist; his thighs about 0.21 m out each side.

Writes out/c130/mod/Meshes/DevilsInTheDetails/Aircraft/C130_JumpKit.nif (main, harness, reserve)
and C130_JumpGearSeated.nif / ...Standing.nif (the ruck and case, as he sits and as he stands).
The plugin's armor (DevilsJumpKit, body slot 57; DevilsJumpGearSeated / ...Standing, both slot
58) points at them; the jumpmaster's script dresses each man as he's seated and as he stands.
"""
import argparse
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_c130_blockout as c                                    # noqa: E402
import worn                                                       # noqa: E402
from make_heightmap import out_dir                                # noqa: E402

LIE = 0.012                        # webbing lies on his fatigues, not in them
# His front's y at heights z, 11 cm out from his middle where the main lift webs run (raycast
# off FatiguesM.nif); over the shoulder, the top of it at y (back to front) along the same line.
FRONT = [(0.97, 0.135), (1.05, 0.140), (1.15, 0.135), (1.25, 0.137), (1.35, 0.130), (1.42, 0.127),
         (1.50, 0.089), (1.56, 0.047), (1.60, 0.021)]
SHOULDER = [(-0.13, 1.60), (-0.05, 1.636), (0.02, 1.62)]


def front_y(z):
    for (z0, y0), (z1, y1) in zip(FRONT, FRONT[1:]):
        if z <= z1:
            t = max(0.0, (z - z0) / (z1 - z0))
            return y0 + t * (y1 - y0)
    return FRONT[-1][1]


def _spow(c_, e):
    return math.copysign(abs(c_) ** e, c_)


def pillow(m, centre, half, e=0.35, steps=(24, 14), tile=0.25):
    """A padded box: a superellipsoid, `e` small for boxy (0.35 a packed parachute), half its
    extents `half`."""
    cx, cy, cz = centre
    a, b, h = half
    nu, nv = steps
    rows = []
    for j in range(nv + 1):
        eta = -math.pi / 2 + math.pi * j / nv
        row = []
        for i in range(nu + 1):
            om = -math.pi + 2 * math.pi * i / nu
            ce, se, co, so = math.cos(eta), math.sin(eta), math.cos(om), math.sin(om)
            p = (cx + a * _spow(ce, e) * _spow(co, e), cy + b * _spow(ce, e) * _spow(so, e),
                 cz + h * _spow(se, e))
            n = (_spow(ce, 2 - e) * _spow(co, 2 - e) / a, _spow(ce, 2 - e) * _spow(so, 2 - e) / b,
                 _spow(se, 2 - e) / h)
            ln = math.sqrt(sum(k * k for k in n)) or 1.0
            if ln < 1e-9 or j in (0, nv):
                n = (0.0, 0.0, -1.0 if j == 0 else 1.0)
                ln = 1.0
            perim = 2 * (a + b) * 2 * i / nu
            row.append(m.vert(p, tuple(k / ln for k in n), (perim / tile, (p[2] - cz + h) / tile)))
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            m.quad(rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i])


def band(m, pts, width, across, tile=0.25):
    """A flat strap along pts, `width` wide in the direction `across` (a unit vector square to
    it), facing out from the man; u along it, v across."""
    along = 0.0
    last = prev = None
    for i, p in enumerate(pts):
        q, r = pts[min(i + 1, len(pts) - 1)], pts[max(i - 1, 0)]
        t = [q[k] - r[k] for k in range(3)]
        n = (across[1] * t[2] - across[2] * t[1], across[2] * t[0] - across[0] * t[2],
             across[0] * t[1] - across[1] * t[0])
        ln = math.sqrt(sum(k * k for k in n)) or 1.0
        n = tuple(k / ln for k in n)
        if sum(n[k] * (p[k] - (0, 0, p[2])[k]) for k in range(3)) < 0:     # out from his middle
            n = tuple(-k for k in n)
        if prev is not None:
            along += math.dist(prev, p)
        a = m.vert(tuple(p[k] - across[k] * width / 2 for k in range(3)), n, (along / tile, 0.0))
        b = m.vert(tuple(p[k] + across[k] * width / 2 for k in range(3)), n, (along / tile, 1.0))
        if last is not None:
            m.quad(last[0], last[1], b, a)
        last, prev = (a, b), p




def plate(m, outline, y, t, lift=None):
    """A flat panel on a face looking +Y: outline [(x, z)] (convex, any winding), its back at y,
    t thick, with edges; lift [dy] raises its face at each outline point, tilting it."""
    lift = lift or [0.0] * len(outline)
    top = [(x, y + t + d, z) for (x, z), d in zip(outline, lift)]
    # The face's normal (Newell), facing +Y.
    n = [0.0, 0.0, 0.0]
    for i in range(len(top)):
        a, b = top[i], top[(i + 1) % len(top)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    if n[1] < 0:
        n = [-k for k in n]
    ln = math.sqrt(sum(k * k for k in n)) or 1.0
    n = tuple(k / ln for k in n)
    cx = sum(p[0] for p in top) / len(top)
    cy = sum(p[1] for p in top) / len(top)
    cz = sum(p[2] for p in top) / len(top)
    f = m.vert((cx, cy, cz), n)
    ring = [m.vert(p, n) for p in top]
    for i in range(len(ring)):
        m.tri(f, ring[i], ring[(i + 1) % len(ring)])
    for i in range(len(outline)):
        (x0, z0), (x1, z1) = outline[i], outline[(i + 1) % len(outline)]
        nx, nz = z1 - z0, -(x1 - x0)
        if nx * (x0 - cx) + nz * (z0 - cz) < 0:
            nx, nz = -nx, -nz
        ln = math.hypot(nx, nz) or 1.0
        e = (nx / ln, 0.0, nz / ln)
        m.quad(m.vert((x0, y, z0), e), m.vert((x1, y, z1), e), m.vert(top[(i + 1) % len(top)], e),
               m.vert(top[i], e))


W = 0.044                          # webbing width (1.75 in)
MAIN = ((0.0, -0.275, 1.29), (0.19, 0.095, 0.25))        # centre, half extents
RESERVE = ((0.0, 0.222, 1.15), (0.17, 0.072, 0.11))   # snug on the harness at his belly
# The ruck, as wide as his legs. Seated it rides his thighs, low on them so it lies in his lap
# out toward his knees, clear of the reserve (the author: "the ruck position looks good");
# standing it hangs right under the reserve (the author: the seated one hung "entirely too low").
RUCK_SEATED = ((0.0, 0.185, 0.49), (0.21, 0.10, 0.19))
RUCK_STANDING = ((0.0, 0.225, 0.80), (0.21, 0.10, 0.19))
# The weapons case: flat, armpit to mid-shin down his left side (his left is -X), and rigid, "like
# trying to carry a crutch under your arm" (the author). Standing, forward of where his arm hangs;
# seated, tipped forward from the hip so its foot clears the front of the seat.
CASE = ((-0.245, 0.085, 0.80), (0.032, 0.10, 0.50))
CASE_TILT = math.radians(38)       # seated: its foot forward
HIP_Z = 0.95
CASE_TILE = 0.2                    # its quilting: one tile is two 10 cm squares


def kit_parts():
    """The kit he wears throughout: main, harness, reserve. {shape: (material, Mesh, weights)}."""
    main, harness, steel, stowed, reserve, flaps = (c.Mesh() for _ in range(6))

    # The main, on his back, its closing bands and the static line stowed on it.
    pillow(main, *MAIN)
    (mx, my, mz), (ma, mb, mh) = MAIN
    back = my - mb                                           # its outer face
    for z in (mz - 0.12, mz + 0.12):                          # retainer bands across it
        band(harness, [(-ma, back + 0.035, z), (-ma * 0.7, back - 0.004, z), (ma * 0.7, back - 0.004, z),
                       (ma, back + 0.035, z)], 0.03, (0, 0, 1))
    for x in (-0.08, 0.0, 0.08):                              # the static line, folded in loops
        pillow(stowed, (x, back - 0.012, mz + 0.05), (0.022, 0.012, 0.11), e=0.6, steps=(12, 8))

    # The harness: main lift webs from the top of the main, over his shoulders, down his front
    # to the reserve's connectors and on to the leg straps.
    for s in (-1, 1):
        x = s * 0.115
        pts = [(x, my + mb - 0.02, mz + mh - 0.02)]
        pts += [(x, y, z + LIE) for y, z in SHOULDER]
        pts += [(x, front_y(z) + LIE, z) for z in (1.56, 1.50, 1.42, 1.32, 1.22)]
        pts += [(x * 0.95, RESERVE[0][1] - RESERVE[1][1] - 0.005, 1.10), (x * 0.9, front_y(0.98) + LIE, 0.98),
                (x * 0.7, 0.11, 0.90)]
        band(harness, c._catmull(pts, 5), W, (1, 0, 0))
        # Steel: the riser connector at his collarbone and the reserve's connector snap.
        steel.box(x - 0.022, front_y(1.50) + LIE, 1.47, x + 0.022, front_y(1.50) + LIE + 0.012, 1.55)
        steel.box(x - 0.018, RESERVE[0][1] - RESERVE[1][1] - 0.01, 1.20, x + 0.018,
                  RESERVE[0][1] - RESERVE[1][1] + 0.01, 1.235)
    # The chest strap and the waistband, across his front.
    zc = 1.40
    band(harness, [(-0.12, front_y(zc) + LIE, zc), (0.0, 0.147 + LIE, zc), (0.12, front_y(zc) + LIE, zc)],
         W, (0, 0, 1))
    zw = 0.97
    band(harness, [(-0.19, 0.02, zw), (-0.16, front_y(zw) + LIE - 0.02, zw), (0.0, front_y(zw) + LIE, zw),
                   (0.16, front_y(zw) + LIE - 0.02, zw), (0.19, 0.02, zw)], W, (0, 0, 1))
    steel.box(-0.025, 0.147 + LIE, zc - 0.02, 0.025, 0.147 + LIE + 0.012, zc + 0.02)

    # The reserve: four flaps closed over its front, meeting at the middle where the ripcord pin
    # holds them; the pin's cable runs to the silver ripcord handle on his right of it (the
    # author). Pull the handle, the pin comes out, the flaps spring open.
    pillow(reserve, *RESERVE)
    (rx, ry, rz), (ra, rb, rh) = RESERVE
    yf = ry + rb - 0.004                                      # its front face
    ex, ez = ra * 0.86, rh * 0.80                             # flaps reach this far from the middle
    # Each flap rises toward the pin, padded over the packed canopy, so each catches the light
    # its own way and the four read apart.
    T, R = 0.008, 0.016                                       # thickness; the rise to the middle
    side = [(ex, -ez), (0.03, -0.035), (0.03, 0.035), (ex, ez)]
    for sx in (-1, 1):
        plate(flaps, [(rx + sx * px, rz + pz) for px, pz in side], yf, T, [0, R, R, 0])
    tb = [(-ex, ez), (ex, ez), (0.03, 0.012), (-0.03, 0.012)]
    for sz in (-1, 1):
        plate(flaps, [(rx + px, rz + sz * pz) for px, pz in tb], yf + T, T, [0, 0, R, R])
    yp = yf + 2 * T + R                                         # on top of the flaps
    steel.tube((rx, yp - 0.006, rz), (rx, yp + 0.006, rz), 0.012, steps=10, caps=True)        # the cone
    steel.tube((rx - 0.03, yp + 0.009, rz), (rx + 0.01, yp + 0.009, rz), 0.003, steps=6)       # the pin
    hx = rx + 0.10                                            # the handle, on his right of the pin
    steel.tube((rx + 0.01, yp + 0.009, rz), (hx - 0.02, yp + 0.012, rz - 0.01), 0.002, steps=6)  # cable
    for k in range(9):                                        # a D-shaped grip, standing off the flaps
        a0, a1 = math.pi * k / 9 - math.pi / 2, math.pi * (k + 1) / 9 - math.pi / 2
        steel.tube((hx - 0.02 + 0.035 * math.cos(a0), yp + 0.014, rz - 0.01 + 0.035 * math.sin(a0)),
                   (hx - 0.02 + 0.035 * math.cos(a1), yp + 0.014, rz - 0.01 + 0.035 * math.sin(a1)),
                   0.005, steps=6)
    steel.tube((hx - 0.02, yp + 0.014, rz - 0.045), (hx - 0.02, yp + 0.014, rz + 0.025), 0.005, steps=6)

    return {"main": ("nylon", main, worn.torso_weights),
            "stowed_line": ("static_line", stowed, worn.torso_weights),
            "reserve": ("nylon", reserve, worn.torso_weights),
            "reserve_flaps": ("nylon", flaps, worn.torso_weights),
            "harness": ("harness", harness, worn.torso_weights),
            "hardware": ("snap_hook", steel, worn.torso_weights)}


def _tilt(m, pivot_z, angle):
    """Tip a mesh forward about a line across him at pivot_z: below it moves forward (+Y)."""
    ca, sa = math.cos(angle), math.sin(angle)
    def rot(y, z):
        dz = z - pivot_z
        return y * ca - dz * sa, pivot_z + y * sa + dz * ca
    out = []
    for x, y, z in m.verts:
        y2, z2 = rot(y, z)
        out.append((x, y2, z2))
    m.verts = out
    m.norms = [(nx, ny * ca - nz * sa, ny * sa + nz * ca) for nx, ny, nz in m.norms]


def gear_parts(seated):
    """The ruck and the weapons case, as he wears them seated or standing (the script swaps them
    as he gets up). {shape: (material, Mesh, weights)}."""
    ruck, straps, case, case_straps, case_steel = (c.Mesh() for _ in range(5))

    # The ALICE ruck: its flap, three pockets, the straps that hang it under the reserve.
    (kx, ky, kz), (ka, kb, kh) = RUCK_SEATED if seated else RUCK_STANDING
    pillow(ruck, (kx, ky, kz), (ka, kb, kh), e=0.45)
    front = ky + kb
    pillow(ruck, (0.0, ky + 0.01, kz + kh - 0.02), (ka * 0.96, kb * 0.96, 0.05), e=0.5)   # top flap
    for px in (-0.14, 0.0, 0.14):
        pillow(ruck, (px, front + 0.02, kz - 0.04), (0.06, 0.03, 0.08), e=0.5, steps=(16, 10))
    rb = RESERVE[0][2] - RESERVE[1][2]                        # the reserve's bottom
    for s in (-1, 1):
        pts = [(s * 0.12, RESERVE[0][1], rb + 0.02)]
        if kz + kh + 0.06 < rb:
            pts.append((s * 0.12, front - 0.03, kz + kh + 0.04))
        pts += [(s * 0.12, front + 0.006, kz + kh - 0.03), (s * 0.12, front + 0.006, kz - kh + 0.05)]
        band(straps, pts, 0.03, (1, 0, 0))

    # The M1950 weapons case (data/reference/1_bacd...jpg): flat, pale grey canvas quilted in
    # squares, a strap with its quick-release buckle, a tie-down strap.
    pillow(case, *CASE, e=0.5, steps=(20, 24), tile=CASE_TILE)
    (cx, cy, cz), (ca, cb, ch) = CASE
    for z, buckle in ((cz + 0.22, True), (cz - 0.28, False)):
        band(case_straps, [(cx - ca - 0.004, cy + cb * 0.9, z), (cx - ca - 0.004, cy - cb * 0.9, z)],
             0.025, (0, 0, 1))
        if buckle:
            case_steel.box(cx - ca - 0.012, cy + 0.01, z - 0.02, cx - ca - 0.004, cy + 0.06, z + 0.02)
    if seated:
        for m in (case, case_straps, case_steel):
            _tilt(m, HIP_Z, CASE_TILT)

    thighs = lambda v: {"LLeg_Thigh": 0.5, "RLeg_Thigh": 0.5}      # noqa: E731

    def strap_weights(v):
        """From the reserve (his torso) down to the ruck (his thighs)."""
        if v[2] >= rb:
            return worn.torso_weights(v)
        top = kz + kh
        if v[2] <= top:
            return thighs(v)
        t = (v[2] - top) / max(rb - top, 1e-3)
        return {"Pelvis": t, "LLeg_Thigh": (1 - t) / 2, "RLeg_Thigh": (1 - t) / 2}

    rigid = worn.rigid("Pelvis")                              # the case doesn't bend
    return {"ruck": ("alice", ruck, thighs),
            "ruck_straps": ("harness", straps, strap_weights),
            "weapons_case": ("weapons_case", case, rigid),
            "case_straps": ("harness", case_straps, rigid),
            "case_buckle": ("snap_hook", case_steel, rigid)}


MODELS = {"C130_JumpKit": kit_parts,
          "C130_JumpGearSeated": lambda: gear_parts(True),
          "C130_JumpGearStanding": lambda: gear_parts(False)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    pyn = worn.load_pyn()
    mod = out_dir("c130") / "mod"
    mesh_dir = mod / "Meshes" / c.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex = "textures\\" + c.MOD_PATH.replace("/", "\\")
    for name, make in MODELS.items():
        path = mesh_dir / f"{name}.nif"
        parts = make()
        worn.write_worn(path, name, parts, tex, pyn, c.MATERIALS)
        print(f"{path}: {sum(len(m.verts) for _, m, _ in parts.values())} vertices")
        if args.install:
            dest = Path(args.install) / path.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
