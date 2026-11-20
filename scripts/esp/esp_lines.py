"""The stick's static lines: DevilsC130StaticLines (STAT, C130_StaticLines.nif, in the cabin's
frame), one persistent ref at the hull's origin, Initially Disabled, and the jumpmaster's
StaticLines property."""
import sys, struct
from esplib import *
import vmadlib
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
HULL_STAT, HULL_REF, JM, PERSIST_CELL = 0x01004D99, 0x010073B9, 0x010073B2, 0x01003E64
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
    if isinstance(n, Rec) and n.fid in (HULL_STAT, HULL_REF, JM):
        f[n.fid] = (n, sib)
    if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == PERSIST_CELL:
        pgroup = n
    assert not (isinstance(n, Rec) and b"DevilsC130StaticLines" in n.raw), "already done"
assert len(f) == 3 and pgroup

hull, hsib = f[HULL_STAT]
vs = [v for _, _, m in c.static_line_parts(c.DEFAULT_LENGTH).values() for v in m.verts]
lo = [int(min(v[i] for v in vs) * 70) - 1 for i in range(3)]
hi = [int(max(v[i] for v in vs) * 70) + 1 for i in range(3)]
stat = new_id()
sl = []
for t, v in sublist(hull.body()):
    if t == b"EDID":
        v = b"DevilsC130StaticLines\0"
    elif t == b"OBND":
        v = struct.pack("<6h", *lo, *hi)
    elif t == b"MODL":
        v = b"DevilsInTheDetails\\Aircraft\\C130_StaticLines.nif\0"
    elif t == b"FULL":
        continue
    sl.append((t, v))
body = pack_subs(sl)
hsib.append(Rec(b"STAT" + struct.pack("<III", len(body), 0, stat) + bytes(hull.raw[16:24]) + body))

hr, _ = f[HULL_REF]
pos = dict(sublist(hr.body()))[b"DATA"]
ref = new_id()
body = pack_subs([(b"NAME", struct.pack("<I", stat)), (b"DATA", pos)])
pgroup.kids.append(Rec(b"REFR" + struct.pack("<III", len(body), 0x400 | 0x800, ref) + bytes(hr.raw[16:24]) + body))

jm, _ = f[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] != "StaticLines"] + [["StaticLines", 1, 1, struct.pack("<HhI", 0, -1, ref)]]
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"STAT {stat:08X} bounds {lo} {hi}; ref {ref:08X} at {struct.unpack('<3f', pos[:12])}; {before} -> {after}")
