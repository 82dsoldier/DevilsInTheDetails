"""Hanscom's paving into the plugin: the graded ground into the terrain (VHGT) of every cell it
changes, a STAT per paving and building model (paving.json, buildings.json), and a reference of each in its cell, at the cell's south-west
corner, z 0, no rotation (out/hanscom/paving.json).

    python esp_paving.py in.esp out.esp
"""
import sys, struct, json
import numpy as np
from esplib import *

WORLD = 0x0100A22E
OUT = "C:/source/repos/BraggMap/out/hanscom/"
TEMPLATE_STAT = 0x01008B42      # DevilsC130DoorFrame: header, MODT and DNAM to copy
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
meta = json.load(open(OUT + "heightmap.json"))
nx, ny = meta["points"]
step = meta["game_units_per_pixel_step"]
orig = np.fromfile(OUT + "heightmap16.raw", dtype="<u2").reshape(ny, nx).astype(np.int64)
graded = np.fromfile(OUT + "graded16.raw", dtype="<u2").reshape(ny, nx).astype(np.int64)
paving = {"models": json.load(open(OUT + "paving.json"))["models"] + json.load(open(OUT + "buildings.json"))["models"]}
cx_n, cy_n = meta["cells"]
cell_x0, cell_y1 = -(cx_n // 2), cy_n - cy_n // 2 - 1

tes4 = top[0]
hd = dict(sublist(tes4.body()))
ver, nrec, nxt = struct.unpack("<fiI", hd[b"HEDR"])

recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
tmpl = recs[TEMPLATE_STAT]
tsub = dict(sublist(tmpl.body()))


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(tmpl.raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


# Cells of the world: (x, y) -> (CELL rec, its children group)
cells, children = {}, {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "CELL" and any(p.gtype == 1 and struct.unpack("<I", p.label)[0] == WORLD for p in par):
        d = dict(sublist(n.body()))
        if b"XCLC" in d:
            cells[n.fid] = struct.unpack_from("<ii", d[b"XCLC"])
    if isinstance(n, Group) and n.gtype == 6:
        children[struct.unpack("<I", n.label)[0]] = n
by_xy = {xy: fid for fid, xy in cells.items()}

# Terrain: rewrite the heights of each cell the grading changed.
changed = 0
for fid, (cx, cy) in cells.items():
    r0 = (cell_y1 - cy) * 32 + 32            # the cell's south row in the north-up heightmap
    c0 = (cx - cell_x0) * 32
    rows = r0 - np.arange(33)
    g = graded[rows][:, c0:c0 + 33]
    if np.array_equal(g, orig[rows][:, c0:c0 + 33]):
        continue
    temp = [k for k in children[fid].kids if isinstance(k, Group) and k.gtype == 9][0]
    land = [k for k in temp.kids if isinstance(k, Rec) and k.type == "LAND"][0]
    q = np.round(g * step / 8).astype(np.int64)      # VHGT counts in 8s
    de = np.zeros((33, 33), np.int64)
    de[0, 0] = 0
    de[1:, 0] = q[1:, 0] - q[:-1, 0]
    de[:, 1:] = q[:, 1:] - q[:, :-1]
    assert np.abs(de).max() < 128
    subs_ = []
    for t, v in sublist(land.body()):
        if t == b"VHGT":
            v = struct.pack("<f", float(q[0, 0])) + struct.pack("<1089b", *de.flatten().tolist()) + v[1093:]
        subs_.append((t, v))
    land.set_body(pack_subs(subs_))
    changed += 1

# STATs and their references.
stat_group = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"STAT"][0]
added = 0
for m in paving["models"]:
    bx, by = m["cell"]
    sfid = 0x01000000 | nxt; nxt += 1
    path = m["nif"].replace("\\", "\\").encode() + b"\0"
    edid = f"DevilsHanscom{m['name']}".replace("-", "m").encode() + b"\0"
    b = m["bounds"]
    stat = new_rec("STAT", sfid, [(b"EDID", edid), (b"OBND", struct.pack("<6h", *b)),
                                  (b"MODL", path), (b"MODT", tsub[b"MODT"]), (b"DNAM", tsub[b"DNAM"])])
    stat_group.kids.append(stat)
    rfid = 0x01000000 | nxt; nxt += 1
    x, y, z = m["position"]
    refr = new_rec("REFR", rfid, [(b"NAME", struct.pack("<I", sfid)),
                                  (b"DATA", struct.pack("<6f", x, y, z, 0, 0, 0))])
    cfid = by_xy[(bx, by)]
    grp = children[cfid]
    temp = [k for k in grp.kids if isinstance(k, Group) and k.gtype == 9]
    if not temp:
        hdr = bytearray(grp.hdr)
        struct.pack_into("<i", hdr, 12, 9)
        t = Group(bytes(hdr), [])
        grp.kids.append(t)
        temp = [t]
    temp[0].kids.append(refr)
    added += 2

hd_list = [(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v) for t, v in sublist(tes4.body())]
tes4.set_body(pack_subs(hd_list))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{changed} cells' terrain graded; {len(paving['models'])} STATs and references; next id {nxt:06X}")
