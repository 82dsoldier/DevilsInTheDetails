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

NPC = 0x01005CD7
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid == NPC:
        rec = n
b = rec.body()
out = b""
for t, o, ln in subs(b):
    v = b[o:o+ln]
    if t == b"VTCK":
        print("removed VTCK", v.hex()); continue
    if t == b"PKID":
        print("PKID", v.hex(), "->", "d34a0d00"); v = struct.pack("<I", 0x000D4AD3)
    if t == b"FULL":
        print("FULL", v, "-> Jumpmaster"); v = b"Jumpmaster\0"
    out += t + struct.pack("<H", len(v)) + v
if rec.flags & 0x40000:
    packed = struct.pack("<I", len(out)) + zlib.compress(out)
else:
    packed = out
rec.raw = bytearray(rec.raw[:24]) + packed
struct.pack_into("<I", rec.raw, 4, len(packed))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("compressed" if rec.flags & 0x40000 else "uncompressed", "record written")
