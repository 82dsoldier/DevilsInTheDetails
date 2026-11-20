"""Fix the jump references in DevilsInTheDetails.esp: move the starboard door from cell
(4,-71) to (4,-7) with Y corrected, delete the stray red light, drop the emptied cell."""
import struct, zlib, sys

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
DOOR, LIGHT = 0x010073B7, 0x01006479
DOOR_Y = -28653.0


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

# Find the door, the light, and cell (4,-7)'s temporary children group.
door = light = None
cells = {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        if n.fid == DOOR: door = (n, sib)
        if n.fid == LIGHT: light = (n, sib)
        if n.type == "CELL": cells[n.fid] = (n, sib, cell_xy(n))
target = None
for fid, (c, sib, xy) in cells.items():
    if xy == (4, -7):
        for g in sib:
            if isinstance(g, Group) and g.gtype == 6 and struct.unpack("<I", g.label)[0] == fid:
                for t in g.kids:
                    if isinstance(t, Group) and t.gtype == 9:
                        target = t
assert door and light and target, (door, light, target)

# Fix the door's Y (DATA: 6 floats, pos then rot) and move it.
rec, sib = door
assert not rec.flags & 0x40000
body = rec.body()
(o,) = [o for t, o, n in subs(body) if t == b"DATA"]
print("door DATA before", struct.unpack_from("<6f", body, o))
struct.pack_into("<f", rec.raw, 24 + o + 4, DOOR_Y)
print("door DATA after ", struct.unpack_from("<6f", rec.body(), o))
sib.remove(rec)
target.kids.append(rec)

# Delete the stray light.
rec, sib = light
sib.remove(rec)


# Drop empty groups, and any CELL whose children are all gone, at (4,-71).
def prune(nodes):
    for n in list(nodes):
        if isinstance(n, Group):
            prune(n.kids)
            if not n.kids:
                nodes.remove(n)
    for n in list(nodes):
        if isinstance(n, Rec) and n.type == "CELL" and cell_xy(n) == (4, -71):
            has_kids = any(isinstance(g, Group) and g.gtype == 6 and
                           struct.unpack("<I", g.label)[0] == n.fid for g in nodes)
            if not has_kids:
                nodes.remove(n); print("removed empty cell (4,-71)")
    # a block/sub-block left empty by that
    for n in list(nodes):
        if isinstance(n, Group) and not n.kids:
            nodes.remove(n)

for _ in range(3):
    prune(top)

after = count(top)
hdr = top[0]
assert hdr.type == "TES4"
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num = struct.unpack_from("<i", hb, o + 4)[0]
struct.pack_into("<i", hdr.raw, 24 + o + 4, num + (after - before))
print(f"records+groups {before} -> {after}; HEDR count {num} -> {num + after - before}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
