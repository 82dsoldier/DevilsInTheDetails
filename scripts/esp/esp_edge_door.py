"""The road between the Commonwealth and Hanscom Field: a pair of linked load doors.

  Commonwealth: on the elevated four-lane highway that leaves Lexington and runs due north off
    the map, at its north end just inside the map's border (vanilla Border region), on the
    east carriageway among the junk walls already there. Its arrival marker faces south, back
    toward Lexington. The Commonwealth (WRLD 0000003C) and its persistent cell are overridden
    to hold the door (the world record without its offset table, OFST, which is the master's).
  Hanscom: where Langley Road leaves the map's south edge, its arrival marker on the road a
    little inside, facing up the road into the base.
Both doors are a vanilla junk-wall gate (JunkWallGate01) across the road.

    python esp_edge_door.py in.esp out.esp
"""
import sys, struct, math, mmap, zlib
from esplib import *
from landh import load_heights, height_at

ESM = r"C:\Steam\steamapps\common\Fallout 4\Data\Fallout4.esm"
COMMONWEALTH, HANSCOM = 0x0000003C, 0x0100A22E
GATE = 0x000CE94B                         # JunkWallGate01 (DOOR)
TEMPLATE = 0x01008B42                     # a record of ours, for the header layout
# Commonwealth: the deck is at z 5486 (the vanilla clutter on it); the border crosses x -13500
# at y 107755.
CW_DOOR = (-13500.0, 107450.0, 5486.0)
CW_ARRIVE = (-13500.0, 107150.0, 5500.0)
CW_FACING = 180.0                         # south, toward Lexington
# Hanscom: Langley Road crosses the south edge (y -77824) at x 4344, heading 71 degrees inside.
HS_DOOR_XY = (4932.0, -77625.0)
HS_ROAD_BEARING = 71.3
HS_ARRIVE_IN = 300.0

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
assert [v for t, v in th if t == b"MAST"][0].rstrip(b"\0").lower() == b"fallout4.esm"
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
assert COMMONWEALTH not in recs, "the Commonwealth is already overridden"


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(recs[TEMPLATE].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


# From the master: the Commonwealth's world record and its persistent cell (the first record in
# its children group), as they are.
esm = open(ESM, "rb")
m = mmap.mmap(esm.fileno(), 0, access=mmap.ACCESS_READ)
wrld_raw = cell_raw = None
i = 0
while i < len(m) and cell_raw is None:
    typ = m[i:i+4]
    size, = struct.unpack_from("<I", m, i + 4)
    if typ == b"GRUP":
        label, gt = struct.unpack_from("<Ii", m, i + 8)
        if gt == 0 and m[i+8:i+12] != b"WRLD":
            i += size
            continue
        if gt == 1 and label != COMMONWEALTH:
            i += size
            continue
        i += 24
        continue
    if typ == b"WRLD" and struct.unpack_from("<I", m, i + 12)[0] == COMMONWEALTH:
        wrld_raw = bytes(m[i:i+24+size])
    elif typ == b"CELL" and wrld_raw is not None:
        cell_raw = bytes(m[i:i+24+size])
    i += 24 + size

# The world record without its OFST and CLSZ tables (sizes past 64K, behind XXXX; offsets into
# the master's own file).
w = Rec(wrld_raw)
b, j, keep = w.body(), 0, []
while j < len(b):
    t, n = b[j:j+4], struct.unpack_from("<H", b, j + 4)[0]
    if t == b"XXXX":
        n = struct.unpack_from("<I", b, j + 6)[0]
        t2 = b[j+10:j+14]
        assert t2 in (b"OFST", b"CLSZ"), t2
        j += 10 + 6 + n
        continue
    if t not in (b"OFST", b"CLSZ"):
        keep.append((t, b[j+6:j+6+n]))
    j += 6 + n
w.set_body(pack_subs(keep))
cw_cell = Rec(cell_raw)
assert cw_cell.flags & 0x400, "not the persistent cell"
cw_cell_fid = cw_cell.fid

# Hanscom's persistent cell and the groups to copy headers from.
hs_g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
hs_cells = [k for k in hs_g1.kids if isinstance(k, Rec) and k.type == "CELL"]
hs_pcell = [c for c in hs_cells if c.flags & 0x400][0]
hs_g6 = [k for k in hs_g1.kids if isinstance(k, Group) and k.gtype == 6 and struct.unpack("<I", k.label)[0] == hs_pcell.fid][0]
hs_g8 = [k for k in hs_g6.kids if isinstance(k, Group) and k.gtype == 8][0]

relabel = lambda g, label, kids: Group(bytes(g.hdr[:8]) + struct.pack("<I", label) + bytes(g.hdr[12:]), kids)
cw_g8 = relabel(hs_g8, cw_cell_fid, [])
cw_g1 = relabel(hs_g1, COMMONWEALTH, [cw_cell, relabel(hs_g6, cw_cell_fid, [cw_g8])])
wrld_group = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"WRLD"][0]
wrld_group.kids[0:0] = [w, cw_g1]          # the master's world first, as in load order

# Hanscom's end: on Langley Road at the south edge, the ground from the plugin's terrain.
hs = load_heights(top, HANSCOM)
hx, hy = HS_DOOR_XY
hz = height_at(hs, hx, hy)
br = math.radians(HS_ROAD_BEARING)
ax, ay = hx + HS_ARRIVE_IN * math.sin(br), hy + HS_ARRIVE_IN * math.cos(br)
az = height_at(hs, ax, ay)

xtel = lambda f, pos, rz: struct.pack("<I6fII", f, *pos, 0, 0, rz, 0, 0)
cw_fid, hs_fid = new_fid(), new_fid()
cw_ref = new_rec("REFR", cw_fid, [
    (b"NAME", struct.pack("<I", GATE)),
    (b"XTEL", xtel(hs_fid, (ax, ay, az + 16), br)),
    (b"DATA", struct.pack("<6f", *CW_DOOR, 0, 0, 0))], flags=0x400)
hs_ref = new_rec("REFR", hs_fid, [
    (b"NAME", struct.pack("<I", GATE)),
    (b"XTEL", xtel(cw_fid, CW_ARRIVE, math.radians(CW_FACING))),
    (b"DATA", struct.pack("<6f", hx, hy, hz, 0, 0, br))], flags=0x400)
cw_g8.kids.append(cw_ref)
hs_g8.kids.append(hs_ref)

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 4, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"Commonwealth door {cw_fid:08X} at {CW_DOOR}; Hanscom door {hs_fid:08X} at {hx:.0f}, {hy:.0f}, {hz:.0f} "
      f"(arrive {ax:.0f}, {ay:.0f}, {az:.0f}); world record {len(wrld_raw)} -> {len(w.raw)} bytes; "
      f"persistent cell {cw_cell_fid:08X}")
