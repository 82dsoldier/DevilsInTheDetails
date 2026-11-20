import struct, zlib, sys
data = open(sys.argv[1], "rb").read()
edids, bases, refs = {}, {}, []
def subs(b):
    i, out = 0, []
    while i < len(b):
        t, n = b[i:i+4].decode("latin1"), struct.unpack_from("<H", b, i+4)[0]
        out.append((t, b[i+6:i+6+n])); i += 6 + n
    return out
def walk(i, end, cell):
    while i < end:
        t = data[i:i+4].decode("latin1")
        size = struct.unpack_from("<I", data, i+4)[0]
        if t == "GRUP":
            walk(i+24, i+size, cell); i += size; continue
        flags, fid = struct.unpack_from("<II", data, i+8)
        body = data[i+24:i+24+size]
        if flags & 0x40000: body = zlib.decompress(body[4:])
        sb = subs(body); d = dict(sb)
        if "EDID" in d: edids[fid] = d["EDID"].rstrip(b"\0").decode("latin1")
        if t == "CELL": cell = edids.get(fid, hex(fid))
        if t in ("REFR", "ACHR") and "NAME" in d:
            base = struct.unpack("<I", d["NAME"])[0]
            pos = struct.unpack("<6f", d["DATA"]) if "DATA" in d else None
            refs.append((cell, t, fid, base, edids.get(fid, ""), pos))
        if "MODL" in d: bases[fid] = d["MODL"].rstrip(b"\0").decode("latin1")
        i += 24 + size
walk(0, len(data), None)
import math
for cell, t, fid, base, ed, pos in refs:
    if cell and "C130" in cell:
        p = f"X {pos[0]:.0f} Y {pos[1]:.0f} Z {pos[2]:.0f} rotZ {math.degrees(pos[5]):.0f}" if pos else ""
        print(t, hex(fid), ed, "base", edids.get(base, hex(base)), bases.get(base, ""), p)
