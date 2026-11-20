"""Stand markers: once up, each jumper walks to his own marker and locks into it, like his seat,
so he stands exactly on his spot facing aft (his static line's hook on the cable) and isn't shoved.
- FURN DevilsC130StandMarker, from the vanilla NPCStandingInvGuardPost (invisible, standing).
- 8 persistent markers, one on each jumper's reference (his place in line), facing aft.
- PACK DevilsStandOutboard / DevilsStandInboard: the sit packages on LinkCustom02, run while the
  half's global is 1. Each NPC_ gets his ahead of the stay-put fallback.
- The jumpmaster's StickStands / StandLink properties."""
import sys, struct
from esplib import *
from esmrec import esm_body
import vmadlib

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
JM, SEAT_BASE = 0x010073B2, 0x010073D5
PACKS = {0x010073D6: ("DevilsStandOutboard", 0x010073D7), 0x010073EA: ("DevilsStandInboard", 0x010073EB)}
JUMPERS = [0x010073D9, 0x010073DB, 0x010073DD, 0x010073DF, 0x010073E1, 0x010073E3, 0x010073E5, 0x010073E7]
GUARD_POST = 0x0005DD9B
LINK1, LINK2 = 0x0005D5E6, 0x0005D5E7
STAY_PACK = 0x000D4AD3

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
        assert b"DevilsC130StandMarker" not in n.raw, "already done"
VER = bytes(f[SEAT_BASE][0].raw[16:24])


def make(typ, fid, sl, flags=0):
    body = pack_subs(sl)
    return Rec(typ.encode() + struct.pack("<III", len(body), flags, fid) + VER + body)


# The marker.
seat_rec, furn_sib = f[SEAT_BASE]
_, gp = esm_body("FURN", GUARD_POST)
stand_base = new_id()
furn_sib.append(make("FURN", stand_base, [
    (t, b"DevilsC130StandMarker\0" if t == b"EDID" else v) for t, v in sublist(gp)]))

# One on each jumper's place in line, facing as he does.
stands = []
for j in JUMPERS:
    r, sib = f[j]
    pos = dict(sublist(r.body()))[b"DATA"]
    sid = new_id()
    stands.append(sid)
    sib.append(make("REFR", sid, [(b"NAME", struct.pack("<I", stand_base)), (b"DATA", pos)], 0x400))
    x, y, z, *_r, rz = struct.unpack("<6f", pos)
    print(f"stand {sid:08X} at ({x:.0f}, {y:.0f}, {z:.0f}) heading {rz:.3f}")

# The packages: stand at LinkCustom02 while the global is 1.
for pid, (edid, npc_id) in PACKS.items():
    p, psib = f[pid]
    sl = []
    for t, v in sublist(p.body()):
        if t == b"EDID":
            v = edid.encode() + b"\0"
        elif t == b"CTDA":
            v = v[:4] + struct.pack("<f", 1.0) + v[8:]
        elif t == b"PTDA" and struct.unpack_from("<I", v, 4)[0] == LINK1:
            v = v[:4] + struct.pack("<I", LINK2) + v[8:]
        sl.append((t, v))
    assert any(t == b"PTDA" and struct.unpack_from("<I", v, 4)[0] == LINK2 for t, v in sl)
    stand_pack = new_id()
    psib.append(make("PACK", stand_pack, sl, p.flags & ~0x40000))
    npc, _ = f[npc_id]
    nsl = []
    for t, v in sublist(npc.body()):
        if t == b"PKID" and struct.unpack("<I", v)[0] == STAY_PACK:
            nsl.append((b"PKID", struct.pack("<I", stand_pack)))
        nsl.append((t, v))
    assert len(nsl) == len(list(sublist(npc.body()))) + 1
    npc.set_body(pack_subs(nsl))
    print(f"PACK {stand_pack:08X} {edid} -> NPC_ {npc_id:08X}")

jm, _ = f[JM]
props = [["StickStands", 11, 1, vmadlib.obj_array(stands)],
         ["StandLink", 1, 1, struct.pack("<HhI", 0, -1, LINK2)]]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        names = {q[0] for q in props}
        s[2] = [q for q in s[2] if q[0] not in names] + props
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))

after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
