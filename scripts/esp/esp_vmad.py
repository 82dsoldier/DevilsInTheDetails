import struct, zlib, sys, math
data = open(sys.argv[1], "rb").read()
ed, recs = {}, []
def subs(b):
    i, out = 0, {}
    while i < len(b):
        t, n = b[i:i+4].decode("latin1"), struct.unpack_from("<H", b, i+4)[0]
        out.setdefault(t, b[i+6:i+6+n]); i += 6 + n
    return out
def walk(i, end, cell):
    while i < end:
        t = data[i:i+4].decode("latin1"); size = struct.unpack_from("<I", data, i+4)[0]
        if t == "GRUP": walk(i+24, i+size, cell); i += size; continue
        flags, fid = struct.unpack_from("<II", data, i+8)
        b = data[i+24:i+24+size]
        if flags & 0x40000: b = zlib.decompress(b[4:])
        d = subs(b)
        if "EDID" in d: ed[fid] = d["EDID"].rstrip(b"\0").decode("latin1")
        if t == "CELL":
            cell = ed.get(fid) or ("cell " + str(struct.unpack("<ii", d["XCLC"][:8])) if "XCLC" in d else hex(fid))
        recs.append((t, fid, cell, d, flags))
        i += 24 + size
walk(0, len(data), None)
for t, fid, cell, d, flags in recs:
    name = ed.get(fid, "")
    base = ed.get(struct.unpack("<I", d["NAME"])[0], "") if "NAME" in d and t in ("REFR","ACHR") else ""
    if "DevilsC130JumpDoor" in (name + base) or "DevilsJump" in (name + base) or "C130" in (name + base):
        pos = ""
        if "DATA" in d and t in ("REFR","ACHR"):
            p = struct.unpack("<6f", d["DATA"]); pos = f"X {p[0]:.0f} Y {p[1]:.0f} Z {p[2]:.0f} rz {math.degrees(p[5]):.0f}"
        print(t, hex(fid), name or base, "| cell", cell if t in ("REFR","ACHR") else "", "| script" if "VMAD" in d else "", "| disabled" if flags & 0x800 else "", pos)

