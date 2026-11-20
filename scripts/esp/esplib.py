import struct, zlib
class Group:
    def __init__(self, hdr, kids): self.hdr, self.kids = bytearray(hdr), kids
    @property
    def gtype(self): return struct.unpack_from("<i", self.hdr, 12)[0]
    @property
    def label(self): return bytes(self.hdr[8:12])
    def bytes(self):
        body = b"".join(k.bytes() for k in self.kids)
        struct.pack_into("<I", self.hdr, 4, 24 + len(body)); return bytes(self.hdr) + body
class Rec:
    def __init__(self, raw): self.raw = bytearray(raw)
    @property
    def type(self): return self.raw[:4].decode("latin1")
    @property
    def fid(self): return struct.unpack_from("<I", self.raw, 12)[0]
    @property
    def flags(self): return struct.unpack_from("<I", self.raw, 8)[0]
    def body(self):
        b = bytes(self.raw[24:]); return zlib.decompress(b[4:]) if self.flags & 0x40000 else b
    def set_body(self, out):
        packed = struct.pack("<I", len(out)) + zlib.compress(out) if self.flags & 0x40000 else out
        self.raw = bytearray(self.raw[:24]) + packed; struct.pack_into("<I", self.raw, 4, len(packed))
    def bytes(self): return bytes(self.raw)
def parse(data, i=0, end=None):
    end = len(data) if end is None else end; out = []
    while i < end:
        size = struct.unpack_from("<I", data, i + 4)[0]
        if data[i:i+4] == b"GRUP": out.append(Group(data[i:i+24], parse(data, i+24, i+size))); i += size
        else: out.append(Rec(data[i:i+24+size])); i += 24 + size
    return out
def subs(b):
    i, out = 0, []
    while i < len(b):
        t, n = b[i:i+4], struct.unpack_from("<H", b, i+4)[0]; out.append((t, i+6, n)); i += 6 + n
    return out
def pack_subs(lst): return b"".join(t + struct.pack("<H", len(v)) + v for t, v in lst)
def sublist(b): return [(t, b[o:o+n]) for t, o, n in subs(b)]
def count(nodes): return sum(1 + (count(n.kids) if isinstance(n, Group) else 0) for n in nodes)
def walk(nodes, parents=()):
    for idx, n in enumerate(nodes):
        yield n, nodes, idx, parents
        if isinstance(n, Group): yield from walk(n.kids, parents + (n,))
