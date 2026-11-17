"""The stick's combat equipment, worn: the early-90s kit each man jumps with (the author: combat
equipment, period gear, not today's), as one skinned model so it goes where he goes.

    python scripts/make_jump_kit.py [--install "<Fallout 4>/Data"]

  T-10C main     on his back, olive drab, the rest of his static line stowed on it in yellow
                 loops (data/reference/1_958e...jpg)
  harness        olive drab webbing: main lift webs over his shoulders and down his front, a
                 chest strap, steel hardware
  T-10R reserve  across his belly on the harness, olive drab, the steel ripcord grip on his right
                 (data/reference/T-10R reserve troop parachute-500x500w.png)
  ALICE ruck     hung under the reserve, in front of his thighs (where it hangs in the modern
                 photos, 160804-F-BP133-218.jpg and others): it rides his thighs, so seated it
                 lies in his lap (the author: hooked up, the ruck on his lap)
  M1950 case     the weapons case, down his left side, riding his left thigh

Built in his own frame (worn.py) and fitted to the vanilla male body in fatigues, measured off
FatiguesM.nif in its bind pose: his front about 0.11 m ahead of his middle at the chest (1.5 m
up), 0.17 at the belly (1.2-1.3 m), 0.14 at the hips (1.0 m); his back 0.17 behind at the
shoulder blades, 0.13 at the waist; his thighs about 0.21 m out each side.

Writes out/c130/mod/Meshes/DevilsInTheDetails/Aircraft/C130_JumpKit.nif. The plugin's armor
(DevilsJumpKit) points at it; the jumpmaster's script gives it to each man as he's seated.
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


W = 0.044                          # webbing width (1.75 in)
MAIN = ((0.0, -0.275, 1.29), (0.19, 0.095, 0.25))        # centre, half extents
RESERVE = ((0.0, 0.222, 1.15), (0.17, 0.072, 0.11))   # snug on the harness at his belly
RUCK = ((0.0, 0.245, 0.70), (0.20, 0.125, 0.22))
CASE = ((-0.285, 0.0, 0.66), (0.05, 0.10, 0.34))         # his left is -X


def kit_parts():
    """{shape: (material, Mesh, weights)}."""
    main, harness, steel, stowed, reserve, ruck, case = (c.Mesh() for _ in range(7))

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

    # The reserve, its ripcord grip on his right.
    pillow(reserve, *RESERVE)
    (rx, ry, rz), (ra, rb, rh) = RESERVE
    for k in range(9):                                        # a D-shaped grip, out from the side
        a0, a1 = math.pi * k / 9 - math.pi / 2, math.pi * (k + 1) / 9 - math.pi / 2
        steel.tube((ra + 0.004 + 0.035 * math.cos(a0), ry + 0.035 * math.sin(a0), rz),
                   (ra + 0.004 + 0.035 * math.cos(a1), ry + 0.035 * math.sin(a1), rz), 0.005, steps=6)

    # The ALICE ruck, under the reserve in front of his thighs: its flap, three pockets, and the
    # straps that hang it from the harness.
    pillow(ruck, *RUCK, e=0.45)
    (kx, ky, kz), (ka, kb, kh) = RUCK
    front = ky + kb
    pillow(ruck, (0.0, ky + 0.02, kz + kh - 0.02), (ka * 0.95, kb * 0.95, 0.05), e=0.5)   # top flap
    for px in (-0.13, 0.0, 0.13):
        pillow(ruck, (px, front + 0.02, kz - 0.06), (0.055, 0.035, 0.08), e=0.5, steps=(16, 10))
    for s in (-1, 1):
        band(harness, [(s * 0.12, ky + 0.05, kz + kh + 0.1), (s * 0.12, front - 0.01, kz + kh - 0.01),
                       (s * 0.12, front + 0.006, kz + 0.1), (s * 0.12, front + 0.006, kz - kh + 0.05)],
             0.03, (1, 0, 0))

    # The M1950 weapons case down his left side, its tie-down bands.
    pillow(case, *CASE, e=0.4)
    (cx, cy, cz), (ca, cb, ch) = CASE
    for z in (cz - 0.18, cz + 0.12):
        steps = 12
        ring = [(cx + (ca + 0.006) * math.cos(2 * math.pi * k / steps),
                 cy + (cb + 0.006) * math.sin(2 * math.pi * k / steps), z) for k in range(steps + 1)]
        band(harness, ring, 0.03, (0, 0, 1))

    thighs = lambda v: {"LLeg_Thigh": 0.5, "RLeg_Thigh": 0.5}      # noqa: E731

    def harness_weights(v):
        if v[2] < 0.93 and v[1] > 0.2:                        # the ruck's straps
            return thighs(v)
        if v[0] < -0.22 and v[2] < 0.93:                      # the case's bands
            return {"LLeg_Thigh": 1.0}
        return worn.torso_weights(v)

    return {"main": ("nylon", main, worn.torso_weights),
            "stowed_line": ("static_line", stowed, worn.torso_weights),
            "reserve": ("nylon", reserve, worn.torso_weights),
            "ruck": ("alice", ruck, thighs),
            "weapons_case": ("nylon", case, worn.rigid("LLeg_Thigh")),
            "harness": ("harness", harness, harness_weights),
            "hardware": ("snap_hook", steel, worn.torso_weights)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    pyn = worn.load_pyn()
    mod = out_dir("c130") / "mod"
    mesh_dir = mod / "Meshes" / c.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex = "textures\\" + c.MOD_PATH.replace("/", "\\")
    path = mesh_dir / "C130_JumpKit.nif"
    parts = kit_parts()
    worn.write_worn(path, "C130_JumpKit", parts, tex, pyn, c.MATERIALS)
    print(f"{path}: {sum(len(m.verts) for _, m, _ in parts.values())} vertices")
    if args.install:
        dest = Path(args.install) / path.relative_to(mod)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        print(f"  installed {dest}")


if __name__ == "__main__":
    main()
