"""Fix the jump references in DevilsInTheDetails.esp: move the starboard door from cell
(4,-71) to (4,-7) with Y corrected, delete the stray red light, drop the emptied cell."""
import struct, zlib, sys

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
PLANE = [0x010073B9, 0x010073B7, 0x010073B8, 0x010073B3, 0x010073B4, 0x010073B5, 0x010073B6, 0x010073B2]
JM, DY = 0x010073B2, 1400.0


class Group:
    def __init__(self, hdr, kids):
        self.hdr, self.kids = bytearray(hdr), kids

    @property
    def gtype(self): return struct.unpack_from("<i", self.hdr, 12)[0]
    @property
    def label(self): return bytes(self.hdr[8:12])

    def bytes(self):
        body = b"".join(k.bytes() for k in self.kids)
        struct.pack_into("<I", self.hdr, 4, 24 + len(body))
        return bytes(self.hdr) + body


class Rec:
    def __init__(self, raw): self.raw = bytearray(raw)
    @property
    def type(self): return self.raw[:4].decode("latin1")
    @property
    def fid(self): return struct.unpack_from("<I", self.raw, 12)[0]
    @property
    def flags(self): return struct.unpack_from("<I", self.raw, 8)[0]
    def body(self):
        b = bytes(self.raw[24:])
        return zlib.decompress(b[4:]) if self.flags & 0x40000 else b
    def bytes(self): return bytes(self.raw)


def parse(i, end):
    out = []
    while i < end:
        size = struct.unpack_from("<I", data, i + 4)[0]
        if data[i:i+4] == b"GRUP":
            out.append(Group(data[i:i+24], parse(i + 24, i + size))); i += size
        else:
            out.append(Rec(data[i:i + 24 + size])); i += 24 + size
    return out


def subs(b):
    i, out = 0, []
    while i < len(b):
        t, n = b[i:i+4], struct.unpack_from("<H", b, i + 4)[0]
        out.append((t, i + 6, n)); i += 6 + n
    return out


def count(nodes):
    return sum(1 + (count(n.kids) if isinstance(n, Group) else 0) for n in nodes)


top = parse(0, len(data))
before = count(top)
assert data == b"".join(n.bytes() for n in top), "round trip failed"


def walk(nodes, parents=()):
    for idx, n in enumerate(nodes):
        yield n, nodes, idx, parents
        if isinstance(n, Group):
            yield from walk(n.kids, parents + (n,))


def cell_xy(rec):
    for t, o, n in subs(rec.body()):
        if t == b"XCLC":
            return struct.unpack_from("<ii", rec.body(), o)
    return None

recs, cells = {}, {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        if n.fid in PLANE: recs[n.fid] = (n, sib)
        if n.type == "CELL": cells[n.fid] = (n, sib, cell_xy(n))
assert len(recs) == len(PLANE), [hex(f) for f in PLANE if f not in recs]
target = None
for fid, (c, sib, xy) in cells.items():
    if xy == (4, -7):
        for g in sib:
            if isinstance(g, Group) and g.gtype == 6 and struct.unpack("<I", g.label)[0] == fid:
                target = [t for t in g.kids if isinstance(t, Group) and t.gtype == 9][0]
assert target
for fid, (rec, sib) in recs.items():
    assert not rec.flags & 0x40000
    b = rec.body()
    (o,) = [o for t, o, n in subs(b) if t == b"DATA"]
    x, y = struct.unpack_from("<2f", b, o)
    struct.pack_into("<f", rec.raw, 24 + o + 4, y + DY)
    print(hex(fid), f"Y {y:.0f} -> {y + DY:.0f}")
rec, sib = recs[JM]
sib.remove(rec)
target.kids.append(rec)

def prune(nodes):
    for n in list(nodes):
        if isinstance(n, Group):
            prune(n.kids)
            if not n.kids:
                nodes.remove(n)
prune(top)
after = count(top)
hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num = struct.unpack_from("<i", hb, o + 4)[0]
struct.pack_into("<i", hdr.raw, 24 + o + 4, num + (after - before))
print(f"records+groups {before} -> {after}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
