"""Hanscom's streets painted on the terrain with vanilla's asphalt (LAsphalt01), in place of the
street meshes (the Road_ models esp_roads.py put in), which go, with their references. The
paint is out/hanscom/road_paint.npy (scripts/make_hanscom_road_paint.py). The ground the
streets were graded to stays.

Each cell's terrain (LAND) gets, per quadrant with any asphalt in it, a layer (ATXT) and its
opacity at each painted point (VTXT: the point's index in the quadrant's 17 x 17, then the
opacity), and the "has layers" flag in its DATA, as vanilla's are.

    python esp_road_paint.py in.esp out.esp
"""
import sys, struct, json
import numpy as np
from esplib import *

WORLD = 0x0100A22E
ASPHALT = 0x00021C68                 # LAsphalt01
OUT = "C:/source/repos/BraggMap/out/hanscom/"
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
meta = json.load(open(OUT + "heightmap.json"))
paint = np.load(OUT + "road_paint.npy")
cx_n, cy_n = meta["cells"]
cell_x0, cell_y1 = -(cx_n // 2), cy_n - cy_n // 2 - 1
assert paint.shape == (cy_n * 32 + 1, cx_n * 32 + 1), paint.shape

tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])

cells, children = {}, {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "CELL" and any(p.gtype == 1 and struct.unpack("<I", p.label)[0] == WORLD for p in par):
        d = dict(sublist(n.body()))
        if b"XCLC" in d and not n.flags & 0x400:
            cells[n.fid] = struct.unpack_from("<ii", d[b"XCLC"])
    if isinstance(n, Group) and n.gtype == 6:
        children[struct.unpack("<I", n.label)[0]] = n

painted = layers = 0
for fid, (cx, cy) in cells.items():
    if not (cell_x0 <= cx < cell_x0 + cx_n and cell_y1 - cy_n < cy <= cell_y1):
        continue                                  # the filler ring: no streets
    r0 = (cell_y1 - cy) * 32 + 32
    c0 = (cx - cell_x0) * 32
    p = paint[r0 - np.arange(33)][:, c0:c0 + 33]  # row 0 = the south edge, as VHGT's
    if not (p > 0).any():
        continue
    land = [k for t in children[fid].kids if isinstance(t, Group) and t.gtype == 9
            for k in t.kids if isinstance(k, Rec) and k.type == "LAND"][0]
    subs_ = [(t, v) for t, v in sublist(land.body()) if t not in (b"BTXT", b"ATXT", b"VTXT")]
    assert len(subs_) == len(sublist(land.body())), f"cell {cx},{cy} already has texture layers"
    for q in range(4):
        qr, qc = (q >> 1) * 16, (q & 1) * 16
        sq = p[qr:qr + 17, qc:qc + 17]
        idx = np.flatnonzero(sq > 0)
        if not len(idx):
            continue
        subs_.append((b"ATXT", struct.pack("<IBBh", ASPHALT, q, 0, 0)))
        subs_.append((b"VTXT", b"".join(struct.pack("<HHf", int(i), 0, float(sq.flat[i])) for i in idx)))
        layers += 1
    subs_ = [(t, struct.pack("<I", struct.unpack("<I", v)[0] | 0x4) if t == b"DATA" else v) for t, v in subs_]
    land.set_body(pack_subs(subs_))
    painted += 1

# The street meshes go: their STATs and every reference to them.
gone = set()
for n in top:
    if isinstance(n, Group) and n.gtype == 0 and n.label == b"STAT":
        for s in n.kids:
            m = dict(sublist(s.body())).get(b"MODL", b"").rstrip(b"\0").decode().lower()
            if m.startswith("devilsinthedetails\\hanscom\\road_"):
                gone.add(s.fid)
removed = 0
for n in [n for n, *_ in walk(top) if isinstance(n, Group)]:
    keep = [k for k in n.kids if not (isinstance(k, Rec) and (
        k.fid in gone or (k.type == "REFR" and struct.unpack("<I", dict(sublist(k.body()))[b"NAME"])[0] in gone)))]
    removed += len(n.kids) - len(keep)
    n.kids[:] = keep

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec - removed, nxt) if t == b"HEDR" else v)
                         for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{painted} cells painted ({layers} quadrant layers); {len(gone)} street models gone ({removed} records)")
