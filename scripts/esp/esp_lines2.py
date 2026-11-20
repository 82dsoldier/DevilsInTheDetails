"""Per-man static lines: DevilsC130StaticLines becomes DevilsC130StaticLineR (C130_StaticLineR.nif,
over the right shoulder: the starboard men), plus DevilsC130StaticLineL for the port men; the
one cabin-wide ref goes, and each jumper gets his own (persistent, Initially Disabled), which the
jumpmaster's script keeps on him. The jumpmaster's StaticLines property becomes StickLines."""
import sys, struct
from esplib import *
import vmadlib
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
STAT_R, OLD_REF, JM, PERSIST_CELL = 0x010073EC, 0x010073ED, 0x010073B2, 0x01003E64
SIDES = [1, 1, -1, -1, 1, 1, -1, -1]        # the Stick's order: outboard stbd, port; inboard stbd, port
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
pgroup = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid in (STAT_R, OLD_REF, JM):
        f[n.fid] = (n, sib)
    if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == PERSIST_CELL:
        pgroup = n
    assert not (isinstance(n, Rec) and b"DevilsC130StaticLineL" in n.raw), "already done"
assert len(f) == 3 and pgroup


def bounds(mirror):
    vs = [v for _, _, m in c.static_line_parts(mirror).values() for v in m.verts]
    lo = [int(min(v[i] for v in vs) * 70) - 1 for i in range(3)]
    hi = [int(max(v[i] for v in vs) * 70) + 1 for i in range(3)]
    return struct.pack("<6h", *lo, *hi)


def stat_subs(rec, edid, nif, mirror):
    out = []
    for t, v in sublist(rec.body()):
        if t == b"EDID":
            v = edid
        elif t == b"OBND":
            v = bounds(mirror)
        elif t == b"MODL":
            v = nif
        out.append((t, v))
    return out


sr, ssib = f[STAT_R]
stat_l = new_id()
lsubs = stat_subs(sr, b"DevilsC130StaticLineL\0", b"DevilsInTheDetails\\Aircraft\\C130_StaticLineL.nif\0", True)
body = pack_subs(lsubs)
ssib.append(Rec(b"STAT" + struct.pack("<III", len(body), 0, stat_l) + bytes(sr.raw[16:24]) + body))
sr.set_body(pack_subs(stat_subs(sr, b"DevilsC130StaticLineR\0",
                                b"DevilsInTheDetails\\Aircraft\\C130_StaticLineR.nif\0", False)))

old, osib = f[OLD_REF]
pos = dict(sublist(old.body()))[b"DATA"]
osib.remove(old)
lines = []
for side in SIDES:
    rid = new_id()
    lines.append(rid)
    body = pack_subs([(b"NAME", struct.pack("<I", STAT_R if side > 0 else stat_l)), (b"DATA", pos)])
    pgroup.kids.append(Rec(b"REFR" + struct.pack("<III", len(body), 0x400 | 0x800, rid)
                           + bytes(old.raw[16:24]) + body))

jm, _ = f[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] not in ("StaticLines", "StickLines")]
        s[2].append(["StickLines", 11, 1, vmadlib.obj_array(lines)])
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"STAT L {stat_l:08X}; line refs {[hex(x) for x in lines]}; {before} -> {after}")
