"""Add DevilsC130CabinLight (warm, no shadows) and five refs of it down the cabin, cell (4,-7)."""
import sys, struct
from esplib import *
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read(); top = parse(data)
assert data == b"".join(n.bytes() for n in top)
before = count(top)
RED, HULL, CELL = 0x01005CD1, 0x010073B9, 0x010034B8
HULL_X, HULL_Y, Z = 17390.0, -26770.0, 24300.0 + 2.2 * 70
YS = [-5.0, -2.5, 0.0, 2.5, 5.0]
hdr = top[0]; hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)
def new_id():
    global nxt
    f = 0x01000000 | nxt; nxt += 1; return f
red = hull = target = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        if n.fid == RED: red = (n, sib)
        if n.fid == HULL: hull = n
        assert not (n.type == "LIGH" and b"DevilsC130CabinLight" in n.body()), "already added"
    if isinstance(n, Group) and n.gtype == 9 and struct.unpack("<I", n.label)[0] == CELL: target = n
assert red and hull and target
rec, sib = red
# LIGH: copy of the red jump light, warm white, radius 300, no flags (non-shadow omni), fade 0.8
fid = new_id()
out = []
for t, v in sublist(rec.body()):
    if t == b"EDID": v = b"DevilsC130CabinLight\0"
    if t == b"DATA":
        v = bytearray(v)
        struct.pack_into("<I", v, 4, 300)
        v[8:12] = bytes((255, 214, 170, 0))
        struct.pack_into("<I", v, 12, 0)
        v = bytes(v)
    if t == b"FNAM": v = struct.pack("<f", 0.8)
    out.append((t, v))
body = pack_subs(out)
light = Rec(rec.raw[:24] + body); struct.pack_into("<I", light.raw, 4, len(body)); struct.pack_into("<I", light.raw, 12, fid)
sib.insert(sib.index(rec) + 1, light)
for y in YS:
    rid = new_id()
    b = pack_subs([(b"NAME", struct.pack("<I", fid)), (b"DATA", struct.pack("<6f", HULL_X, HULL_Y + 70 * y, Z, 0, 0, 0))])
    r = Rec(b"REFR" + struct.pack("<III", len(b), 0, rid) + bytes(hull.raw[16:24]) + b)
    target.kids.append(r); print(f"ref {rid:08X} at Y {HULL_Y + 70*y:.0f} Z {Z:.0f}")
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
print(f"LIGH {fid:08X}; records+groups {before} -> {after}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
