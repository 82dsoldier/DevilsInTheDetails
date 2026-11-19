"""The jumpmaster's hand-and-arm signals, as animations the game plays as he gives each command.

    python scripts/make_jm_signals.py [--install "<Fallout 4>/Data"] [--preview DIR]

The author knows the signals; this builds them in code (no Blender), each from the vanilla
standing body and a hand-set right arm:

  Hook up!      his right arm overhead, the index finger crooked like a hook, the whole arm
                pumped down and up (the author): elbow out and bent, hand by his head, then up
  Ten minutes!  both hands held out in front, fingers splayed (the author): ten fingers, palms
                to the stick

Each is a Fallout 4 Havok animation (hkaSplineCompressedAnimation) written by PyNifly's
anim_fo4 (data/tools/io_scene_nifly/hkx), bound to the vanilla human skeleton (95 bones, the
tracks in its order). His body comes from the first frame of the vanilla Brotherhood salute
(PoseA_BOSSalute1.hkx, read out of the game's animation archive), held still; the right arm,
hand and fingers are set here, the arm aimed with a little inverse kinematics.

The plugin plays each through a dynamic idle (as the vanilla BOS_Salute does), and the
jumpmaster's script plays it as he says the command.

Writes out/c130/mod/Meshes/Actors/Character/Animations/DevilsInTheDetails/JM_HookUp.hkx, and with
--preview, stick figures of the pose to check.
"""
import argparse
import math
import shutil
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, out_dir                          # noqa: E402

sys.path.insert(0, str(ROOT / "data" / "tools" / "io_scene_nifly" / "hkx"))
import anim_fo4 as hk                                             # noqa: E402

FPS = 30
ANIM_DIR = "DevilsInTheDetails"            # under Meshes\Actors\Character\Animations
BASE = "meshes\\actors\\character\\animations\\mt\\neutral\\posea_bossalute1.hkx"
SKELETON = "meshes\\actors\\character\\characterassets\\skeleton.hkx"


# --- The game's archive -----------------------------------------------------------------------

def ba2_file(data_dir, want):
    """One file out of Fallout4 - Animations.ba2 (a GNRL archive), by its full path."""
    with open(Path(data_dir) / "Fallout4 - Animations.ba2", "rb") as f:
        magic, ver, typ, n, names_off = struct.unpack("<4sI4sIQ", f.read(24))
        assert magic == b"BTDX" and typ == b"GNRL"
        recs = [struct.unpack("<I4sIIQIII", f.read(36)) for _ in range(n)]
        f.seek(names_off)
        for rec in recs:
            (ln,) = struct.unpack("<H", f.read(2))
            name = f.read(ln).decode("latin1")
            if name.lower() == want:
                off, packed, size = rec[4], rec[5], rec[6]
                here = f.tell()
                f.seek(off)
                raw = f.read(packed or size)
                f.seek(here)
                return zlib.decompress(raw) if packed else raw
    raise SystemExit(f"{want} not found in the animation archive")


# --- Quaternions (x, y, z, w) -----------------------------------------------------------------

def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def qrot(q, v):
    return qmul(qmul(q, (v[0], v[1], v[2], 0.0)), qconj(q))[:3]


def qaxis(axis, deg):
    a = math.radians(deg) / 2
    n = math.sqrt(sum(c * c for c in axis))
    return tuple(c / n * math.sin(a) for c in axis) + (math.cos(a),)


def qarc(u, v):
    """The shortest rotation taking direction u to direction v."""
    nu = math.sqrt(sum(c * c for c in u))
    nv = math.sqrt(sum(c * c for c in v))
    u = [c / nu for c in u]
    v = [c / nv for c in v]
    d = sum(a * b for a, b in zip(u, v))
    c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    q = (c[0], c[1], c[2], 1.0 + d)
    n = math.sqrt(sum(k * k for k in q)) or 1.0
    return tuple(k / n for k in q)


def qslerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        q = tuple(x + t * (y - x) for x, y in zip(a, b))
    else:
        th = math.acos(d)
        s = math.sin(th)
        q = tuple((math.sin((1 - t) * th) * x + math.sin(t * th) * y) / s for x, y in zip(a, b))
    n = math.sqrt(sum(k * k for k in q))
    return tuple(k / n for k in q)


# --- The body ---------------------------------------------------------------------------------

class Body:
    """The skeleton in one pose: local (translation, rotation) per bone; world by forward
    kinematics (his space: game units, feet at the origin, facing +Y, his right +X)."""

    def __init__(self, skel, local):
        self.skel = skel
        self.names = {b: i for i, b in enumerate(skel.bones)}
        self.local = [list(p) for p in local]

    def world(self):
        out = [None] * len(self.local)
        for i, (t, r) in enumerate(self.local):
            p = self.skel.parents[i]
            if p < 0:
                out[i] = (tuple(t), tuple(r))
            else:
                pt, pr = out[p]
                out[i] = (tuple(a + b for a, b in zip(pt, qrot(pr, t))), qmul(pr, r))
        return out

    def aim(self, bone, direction):
        """Turn a bone (in place, about its root) so it points (its +X) the given way."""
        i = self.names[bone]
        w = self.world()
        _, wr = w[i]
        q = qarc(qrot(wr, (1, 0, 0)), direction)
        _, pr = w[self.skel.parents[i]]
        self.local[i][1] = qmul(qconj(pr), qmul(q, wr))

    def roll(self, bone, a, b, want):
        """Turn a bone about its own length so the line from bone a to bone b (its children:
        across the knuckles, say) points as near `want` as it can."""
        i = self.names[bone]
        w = self.world()
        _, wr = w[i]
        x = qrot(wr, (1, 0, 0))
        def flat(v):
            d = sum(p * q for p, q in zip(v, x))
            v = [p - d * q for p, q in zip(v, x)]
            n = math.sqrt(sum(c * c for c in v)) or 1.0
            return [c / n for c in v]
        have = flat([p - q for p, q in zip(w[self.names[b]][0], w[self.names[a]][0])])
        want = flat(want)
        ang = math.degrees(math.atan2(sum(x[k] * (have[(k + 1) % 3] * want[(k + 2) % 3] - have[(k + 2) % 3] * want[(k + 1) % 3]) for k in range(3)),
                                      sum(p * q for p, q in zip(have, want))))
        q = qaxis(x, ang)
        _, pr = w[self.skel.parents[i]]
        self.local[i][1] = qmul(qconj(pr), qmul(q, wr))

    def turn(self, bone, axis, deg):
        """Turn a bone about one of its own axes (fingers curl about their Z)."""
        i = self.names[bone]
        self.local[i][1] = qmul(self.local[i][1], qaxis(axis, deg))


def hook_up_frames(base):
    """His right arm up overhead, the index finger hooked, the forearm pumped three times; up in
    0.5 s, pumping 1.8 s, down in 0.5 s. One Body per frame."""
    up = Body(base.skel, base.local)
    up.aim("RArm_UpperArm", (0.25, 0.05, 1.0))                    # overhead, a little out
    # The fist: thumb across, the others curled tight; the index finger crooked like a hook.
    for f, curls in (("1", (20, 30, 30)), ("3", (85, 95, 60)), ("4", (85, 95, 60)), ("5", (85, 95, 60)),
                     ("2", (15, 85, 75))):
        for k, deg in zip("123", curls):
            up.turn(f"RArm_Finger{f}{k}", (0, 0, 1), -deg)
    # The whole arm pumps (the author): up straight overhead, then down, the upper arm out to the
    # side and the elbow bent so the hand comes down beside his head, then up again.
    upper_up, upper_down = (0.25, 0.05, 1.0), (1.0, 0.1, -0.05)
    fore_up, fore_down = (0.15, 0.05, 1.0), (-0.45, 0.15, 0.9)
    def pose(arm_t, pump):
        b = Body(base.skel, up.local)
        b.aim("RArm_UpperArm", tuple(s + pump * (e - s) for s, e in zip(upper_up, upper_down)))
        b.aim("RArm_ForeArm1", tuple(s + pump * (e - s) for s, e in zip(fore_up, fore_down)))
        if arm_t < 1.0:                                           # raising or lowering: blend from rest
            for i in range(len(b.local)):
                b.local[i][1] = qslerp(tuple(base.local[i][1]), tuple(b.local[i][1]), arm_t)
        return b
    frames = []
    n_up, n_pump, n_down = int(0.5 * FPS), int(1.8 * FPS), int(0.5 * FPS)
    for k in range(n_up):
        t = k / n_up
        frames.append(pose(t * t * (3 - 2 * t), 0.0))
    for k in range(n_pump):
        frames.append(pose(1.0, 0.5 - 0.5 * math.cos(2 * math.pi * 3 * k / n_pump)))
    for k in range(n_down + 1):
        t = 1 - k / n_down
        frames.append(pose(t * t * (3 - 2 * t), 0.0))
    return frames


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def ten_minutes_frames(base):
    """Both arms out in front at chest height, hands up, palms to the stick, all ten fingers
    straight and splayed; out in 0.5 s, held 1.8 s, down in 0.5 s."""
    out = Body(base.skel, base.local)
    for side, sx in (("R", 1.0), ("L", -1.0)):
        out.aim(f"{side}Arm_UpperArm", (0.22 * sx, 1.0, -0.25))       # forward, a little out and down
        out.aim(f"{side}Arm_ForeArm1", (0.02 * sx, 1.0, 0.12))       # nearly straight
        up = _norm((0.0, 0.25, 1.0))                                  # the hand bent back, fingers up
        out.aim(f"{side}Arm_Hand", up)
        across = (sx, 0.0, 0.0)                                       # index to little finger: outward
        out.roll(f"{side}Arm_Hand", f"{side}Arm_Finger21", f"{side}Arm_Finger51", across)
        palm = (0.0, 1.0, -0.25)                                      # facing the stick
        for f, deg in (("2", -9), ("3", 0), ("4", 9), ("5", 19)):     # spread, index to little
            a = math.radians(deg)
            d = _norm(tuple(u * math.cos(a) + c * math.sin(a) for u, c in zip(up, across)))
            for k in "123":
                out.aim(f"{side}Arm_Finger{f}{k}", d)
        a = math.radians(55)                                          # the thumb out, toward his middle
        d = _norm(tuple(u * math.cos(a) - c * math.sin(a) + 0.15 * p for u, c, p in zip(up, across, palm)))
        for k in "123":
            out.aim(f"{side}Arm_Finger1{k}", d)

    def pose(t):
        b = Body(base.skel, out.local)
        for i in range(len(b.local)):
            b.local[i][1] = qslerp(tuple(base.local[i][1]), tuple(out.local[i][1]), t)
        return b
    frames = []
    n_up, n_hold, n_down = int(0.5 * FPS), int(1.8 * FPS), int(0.5 * FPS)
    for k in range(n_up):
        t = k / n_up
        frames.append(pose(t * t * (3 - 2 * t)))
    frames += [pose(1.0)] * n_hold
    for k in range(n_down + 1):
        t = 1 - k / n_down
        frames.append(pose(t * t * (3 - 2 * t)))
    return frames


SIGNALS = {"JM_HookUp": hook_up_frames, "JM_TenMinutes": ten_minutes_frames}


def to_animation(frames):
    n = len(frames)
    tracks = []
    for i in range(len(frames[0].local)):
        tracks.append(hk.TrackData(translations=[list(f.local[i][0]) for f in frames],
                                   rotations=[list(f.local[i][1]) for f in frames],
                                   scales=[[1.0, 1.0, 1.0] for _ in frames]))
    return hk.AnimationData(duration=(n - 1) / FPS, num_frames=n, num_tracks=len(tracks),
                            frame_duration=1.0 / FPS, bone_names=[""] * len(tracks), tracks=tracks,
                            track_to_bone_indices=list(range(len(tracks))),
                            original_skeleton_name="Root")


def preview(frames, path, picks):
    """Stick figures of the chosen frames, front and side, for checking the pose."""
    from PIL import Image, ImageDraw
    W, H, S = 300, 420, 1.9
    img = Image.new("RGB", (W * 2 * len(picks), H), (250, 250, 250))
    d = ImageDraw.Draw(img)
    for col, k in enumerate(picks):
        w = frames[k].world()
        sk = frames[k].skel
        for view in (0, 1):                                       # front (x, z), side (y, z)
            ox = (2 * col + view) * W + W // 2
            for i, (t, _) in enumerate(w):
                p = sk.parents[i]
                if p < 0:
                    continue
                pt = w[p][0]
                a = (ox + S * (t[0] if view == 0 else t[1]), H - 20 - S * t[2])
                b = (ox + S * (pt[0] if view == 0 else pt[1]), H - 20 - S * pt[2])
                hand = "Finger" in sk.bones[i]
                d.line([a, b], fill=(200, 40, 40) if "RArm" in sk.bones[i] else (60, 60, 60),
                       width=1 if hand else 2)
            d.text((ox - W // 2 + 6, 6), f"frame {k} {'front' if view == 0 else 'side (facing right)'}",
                   fill=(0, 0, 0))
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    ap.add_argument("--data", default="C:/Steam/steamapps/common/Fallout 4/Data",
                    help="the game's Data folder, to read the vanilla skeleton and salute from")
    ap.add_argument("--preview", help="a folder for stick-figure previews")
    args = ap.parse_args()

    tmp = out_dir("c130") / "vanilla"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "skeleton.hkx").write_bytes(ba2_file(args.data, SKELETON))
    (tmp / "base.hkx").write_bytes(ba2_file(args.data, BASE))
    skel = hk.load_fo4_skeleton(str(tmp / "skeleton.hkx"))
    salute = hk.load_fo4_animation(str(tmp / "base.hkx"))
    assert len(salute.tracks) == len(skel.bones)
    base = Body(skel, [(tuple(tr.translations[0]), tuple(tr.rotations[0])) for tr in salute.tracks])

    mod = out_dir("c130") / "mod"
    anim_dir = mod / "Meshes" / "Actors" / "Character" / "Animations" / ANIM_DIR
    anim_dir.mkdir(parents=True, exist_ok=True)
    for name, make in SIGNALS.items():
        frames = make(base)
        path = anim_dir / f"{name}.hkx"
        hk.write_fo4_animation(str(path), to_animation(frames))
        back = hk.load_fo4_animation(str(path))
        print(f"{path}: {back.num_frames} frames, {back.duration:.2f} s")
        if args.preview:
            n = len(frames)
            preview(frames, Path(args.preview) / f"{name}.png", [0, n // 4, n // 4 + 9, n // 2])
        if args.install:
            dest = Path(args.install) / path.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
