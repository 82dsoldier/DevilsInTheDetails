"""The stick moves up to Nate once they land: GLOB DevilsStickLanded (0 aboard, 1 once down, set
by the jumpmaster's LandStick); PACK DevilsStickFollowNate, the vanilla AO_TestNPCFollowPlayer
(the FollowPlayer template, target the player) on that global; first in both paratrooper bases'
packages. Also puts the two bases back as they were before the CK's navmesh save (it had
rewritten their unused race field to SynthGen2RaceValentine, among other recalculations)."""
import sys, struct
from esplib import *
from esmrec import esm_body
import vmadlib

src, before_path, dst = sys.argv[1], sys.argv[2], sys.argv[3]
top = parse(open(src, "rb").read())
old = {n.fid: n for n, *_ in walk(parse(open(before_path, "rb").read())) if isinstance(n, Rec)}
before = count(top)
JM, OUTBOARD_UP = 0x010073B2, 0x010073E8
BASES = (0x010073D7, 0x010073EB)
FOLLOW_TEST = 0x000260FF
hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


f = {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        f[n.fid] = (n, sib)
        assert b"DevilsStickLanded" not in n.raw, "already done"
glob, gsib = f[OUTBOARD_UP]
VER = bytes(glob.raw[16:24])

gid = new_id()
gb = pack_subs([(b"EDID", b"DevilsStickLanded" + bytes(1)) if t == b"EDID" else
                (t, struct.pack("<f", 0.0)) if t == b"FLTV" else (t, v) for t, v in sublist(glob.body())])
gsib.append(Rec(b"GLOB" + struct.pack("<III", len(gb), glob.flags & ~0x40000, gid) + VER + gb))
print(f"GLOB {gid:08X} DevilsStickLanded", [t.decode() for t, _ in sublist(gb)])

pack, psib = f[0x010073D6]
_, follow = esm_body("PACK", FOLLOW_TEST)
cond = struct.pack("<B3sfHHIIIIi", 0, bytes(3), 1.0, 0x4A, 0, gid, 0, 0, 0, -1)   # GetGlobalValue == 1
sl = []
for t, v in sublist(follow):
    if t == b"EDID":
        v = b"DevilsStickFollowNate" + bytes(1)
    sl.append((t, v))
    if t == b"PSDT":
        sl.append((b"CTDA", cond))
pid = new_id()
pb = pack_subs(sl)
psib.append(Rec(b"PACK" + struct.pack("<III", len(pb), 0, pid) + bytes(pack.raw[16:24]) + pb))
print(f"PACK {pid:08X} DevilsStickFollowNate")

for b in BASES:
    rec, _ = f[b]
    sl, done = [], False
    for t, v in sublist(old[b].body()):           # as they were before the CK's save
        if t == b"PKID" and not done:
            sl.append((b"PKID", struct.pack("<I", pid)))
            done = True
        sl.append((t, v))
    assert done
    rec.set_body(pack_subs(sl))
    print(f"NPC_ {b:08X}: restored, follow package first")

jm, _ = f[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] != "StickLanded"] + [["StickLanded", 1, 1, struct.pack("<HhI", 0, -1, gid)]]
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
