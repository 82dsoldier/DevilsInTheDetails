"""Make the stick stand up, and the closed door movable.
- Globals DevilsStickOutboardUp / DevilsStickInboardUp.
- DevilsSitLinkedSeatQuiet becomes DevilsSitOutboard, conditioned GetGlobalValue(OutboardUp) == 0;
  a copy, DevilsSitInboard, on InboardUp.
- DevilsParatrooper becomes DevilsParatrooperOutboard; a copy, DevilsParatrooperInboard, uses the
  inboard package; the four inboard jumpers point at it.
- DevilsC130DoorClosed: STAT -> ACTI (no name), so TranslateTo can slide it.
- The jumpmaster's OutboardUp / InboardUp properties."""
import sys, struct
from esplib import *
import vmadlib

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
GREEN_GLOB, PACK, NPC, DOOR_CLOSED, JM = 0x01005CDC, 0x010073D6, 0x010073D7, 0x010073CD, 0x010073B2
INBOARD_JUMPERS = (0x010073E1, 0x010073E3, 0x010073E5, 0x010073E7)
GET_GLOBAL_VALUE = 74

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
    if isinstance(n, Rec) and n.fid in (GREEN_GLOB, PACK, NPC, DOOR_CLOSED, JM) + INBOARD_JUMPERS:
        f[n.fid] = (n, sib)
    assert not (isinstance(n, Rec) and b"DevilsStickOutboardUp" in n.raw), "already done"
assert len(f) == 9, sorted(hex(x) for x in f)


def clone(rec, fid, sl, typ=None):
    body = pack_subs(sl)
    r = Rec((typ.encode() if typ else bytes(rec.raw[:4])) + struct.pack("<III", len(body), 0, fid)
            + bytes(rec.raw[16:24]) + body)
    return r


def ctda_global(glob):
    return struct.pack("<B3xfHHIIIIi", 0x00, 0.0, GET_GLOBAL_VALUE, 0, glob, 0, 0, 0, -1)


# Globals.
g, gsib = f[GREEN_GLOB]
globs = {}
for name in ("DevilsStickOutboardUp", "DevilsStickInboardUp"):
    fid = new_id()
    globs[name] = fid
    gsib.append(clone(g, fid, [(b"EDID", name.encode() + b"\0"), (b"FLTV", struct.pack("<f", 0))]))

# Packages: sit while the half's global is 0.
p, psib = f[PACK]


def pack_subs_for(edid, glob):
    out = []
    for t, v in sublist(p.body()):
        if t == b"EDID":
            v = edid.encode() + b"\0"
        out.append((t, v))
        if t == b"PSDT":
            out.append((b"CTDA", ctda_global(glob)))
    return out


inboard_pack = new_id()
psib.append(clone(p, inboard_pack, pack_subs_for("DevilsSitInboard", globs["DevilsStickInboardUp"])))
p.set_body(pack_subs(pack_subs_for("DevilsSitOutboard", globs["DevilsStickOutboardUp"])))

# Jumpers: an inboard base with the inboard package.
npc, nsib = f[NPC]
inboard_npc = new_id()
sl = []
seen_pack = False
for t, v in sublist(npc.body()):
    if t == b"EDID":
        v = b"DevilsParatrooperInboard\0"
    if t == b"PKID" and not seen_pack:
        v = struct.pack("<I", inboard_pack)
        seen_pack = True
    sl.append((t, v))
nsib.append(clone(npc, inboard_npc, sl))
npc.set_body(pack_subs([(t, b"DevilsParatrooperOutboard\0" if t == b"EDID" else v)
                        for t, v in sublist(npc.body())]))
for j in INBOARD_JUMPERS:
    r, _ = f[j]
    r.set_body(pack_subs([(t, struct.pack("<I", inboard_npc) if t == b"NAME" else v)
                          for t, v in sublist(r.body())]))

# The closed door: an activator (no name, so no prompt), so it can slide.
d, dsib = f[DOOR_CLOSED]
keep = [(t, v) for t, v in sublist(d.body()) if t in (b"EDID", b"OBND", b"MODL")]
acti = clone(d, DOOR_CLOSED, keep, "ACTI")
dsib.remove(d)
acti_group = next(g for g in top if isinstance(g, Group) and g.label == b"ACTI")
acti_group.kids.append(acti)

# The jumpmaster's properties.
jm, _ = f[JM]
props = [["OutboardUp", 1, 1, struct.pack("<HhI", 0, -1, globs["DevilsStickOutboardUp"])],
         ["InboardUp", 1, 1, struct.pack("<HhI", 0, -1, globs["DevilsStickInboardUp"])]]
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
print({k: hex(v) for k, v in globs.items()}, "inboard pack", hex(inboard_pack), "inboard npc",
      hex(inboard_npc), f"{before} -> {after}")
