"""Hanscom's streets into the plugin: a STAT and a reference per street model (out/hanscom/
roads.json, from make_hanscom_paving.py), the terrain (VHGT) of every cell whose heights differ
from graded16.raw, and the bounds (OBND) of the paving and building STATs already in, as their
regenerated models have them; street models no longer in roads.json are removed, with their
references. Safe to run again: models already in are only updated.

    python esp_roads.py in.esp out.esp
"""
import sys, struct, json
import numpy as np
from esplib import *

WORLD = 0x0100A22E
OUT = "C:/source/repos/BraggMap/out/hanscom/"
ROUNDING = 1.05                 # VHGT counts (8 units): the plugin vs the heightmap, unmoved
TEMPLATE_STAT = 0x01008B42      # DevilsC130DoorFrame: header, MODT and DNAM to copy
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
meta = json.load(open(OUT + "heightmap.json"))
nx, ny = meta["points"]
step = meta["game_units_per_pixel_step"]
graded = np.fromfile(OUT + "graded16.raw", dtype="<u2").reshape(ny, nx).astype(np.int64)
roads = json.load(open(OUT + "roads.json"))["models"]
others = json.load(open(OUT + "paving.json"))["models"] + json.load(open(OUT + "buildings.json"))["models"]
cx_n, cy_n = meta["cells"]
cell_x0, cell_y1 = -(cx_n // 2), cy_n - cy_n // 2 - 1

tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
tmpl = recs[TEMPLATE_STAT]
tsub = dict(sublist(tmpl.body()))


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(tmpl.raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


cells, children = {}, {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "CELL" and any(p.gtype == 1 and struct.unpack("<I", p.label)[0] == WORLD for p in par):
        d = dict(sublist(n.body()))
        if b"XCLC" in d:
            cells[n.fid] = struct.unpack_from("<ii", d[b"XCLC"])
    if isinstance(n, Group) and n.gtype == 6:
        children[struct.unpack("<I", n.label)[0]] = n
by_xy = {xy: fid for fid, xy in cells.items()}


def temp_group(cfid):
    grp = children[cfid]
    temp = [k for k in grp.kids if isinstance(k, Group) and k.gtype == 9]
    if temp:
        return temp[0]
    hdr = bytearray(grp.hdr)
    struct.pack_into("<i", hdr, 12, 9)
    t = Group(bytes(hdr), [])
    grp.kids.append(t)
    return t


# Terrain: each cell whose heights (in VHGT's 8-unit counts) aren't graded16's.
changed = 0
for fid, (cx, cy) in cells.items():
    if fid not in children:
        continue
    r0 = (cell_y1 - cy) * 32 + 32            # the cell's south row in the north-up heightmap
    c0 = (cx - cell_x0) * 32
    rows = r0 - np.arange(33)
    exact = graded[rows][:, c0:c0 + 33] * step / 8
    lands = [k for t in children[fid].kids if isinstance(t, Group) and t.gtype == 9
             for k in t.kids if isinstance(k, Rec) and k.type == "LAND"]
    if not lands:
        continue
    land = lands[0]
    v = dict(sublist(land.body()))[b"VHGT"]
    de0 = np.array(struct.unpack_from("<1089b", v, 4), np.int64).reshape(33, 33)
    cur = np.cumsum(de0, axis=1) + np.cumsum(de0[:, 0])[:, None] - de0[:, 0][:, None] + struct.unpack_from("<f", v)[0]
    # Points within rounding of the heightmap (its step isn't a whole count) keep their heights,
    # so only the ground the streets moved changes and cell edges still meet their neighbours.
    moved = np.abs(cur - exact) > ROUNDING
    if not moved.any():
        continue
    q = np.where(moved, np.round(exact), np.round(cur)).astype(np.int64)
    de = np.zeros((33, 33), np.int64)
    de[1:, 0] = q[1:, 0] - q[:-1, 0]
    de[:, 1:] = q[:, 1:] - q[:, :-1]
    assert np.abs(de).max() < 128
    subs_ = [(t, struct.pack("<f", float(q[0, 0])) + struct.pack("<1089b", *de.flatten().tolist()) + v[1093:]
              if t == b"VHGT" else v) for t, v in sublist(land.body())]
    land.set_body(pack_subs(subs_))
    changed += 1

# STATs by model path.
stat_group = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"STAT"][0]
by_model = {}
for n in stat_group.kids:
    if isinstance(n, Rec):
        d = dict(sublist(n.body()))
        if b"MODL" in d:
            by_model[d[b"MODL"].rstrip(b"\0").decode().lower()] = n


def set_bounds(stat, b):
    subs_ = [(t, struct.pack("<6h", *b) if t == b"OBND" else v) for t, v in sublist(stat.body())]
    stat.set_body(pack_subs(subs_))


bounds = 0
for m in others:
    s = by_model.get(m["nif"].lower())
    if s is not None and dict(sublist(s.body()))[b"OBND"] != struct.pack("<6h", *m["bounds"]):
        set_bounds(s, m["bounds"])
        bounds += 1

# Street models no longer in roads.json (the layout changed): their STATs and references go.
wanted = {m["nif"].lower() for m in roads}
gone = {s.fid for path, s in by_model.items()
        if path.startswith("devilsinthedetails\\hanscom\\road_") and path not in wanted}
removed = 0
for n in [n for n, *_ in walk(top) if isinstance(n, Group)]:
    keep = [k for k in n.kids if not (isinstance(k, Rec) and (
        k.fid in gone or (k.type == "REFR" and struct.unpack("<I", dict(sublist(k.body()))[b"NAME"])[0] in gone)))]
    removed += len(n.kids) - len(keep)
    n.kids[:] = keep
for path in [p for p, s in by_model.items() if s.fid in gone]:
    del by_model[path]

added = updated = 0
for m in roads:
    s = by_model.get(m["nif"].lower())
    if s is not None:
        set_bounds(s, m["bounds"])
        updated += 1
        continue
    sfid = 0x01000000 | nxt; nxt += 1
    edid = f"DevilsHanscom{m['name']}".replace("-", "m").encode() + b"\0"
    stat_group.kids.append(new_rec("STAT", sfid, [
        (b"EDID", edid), (b"OBND", struct.pack("<6h", *m["bounds"])), (b"MODL", m["nif"].encode() + b"\0"),
        (b"MODT", tsub[b"MODT"]), (b"DNAM", tsub[b"DNAM"])]))
    rfid = 0x01000000 | nxt; nxt += 1
    temp_group(by_xy[tuple(m["cell"])]).kids.append(new_rec("REFR", rfid, [
        (b"NAME", struct.pack("<I", sfid)), (b"DATA", struct.pack("<6f", *m["position"], 0, 0, 0))]))
    added += 1

hd = [(t, struct.pack("<fiI", ver, nrec + 2 * added - removed, nxt) if t == b"HEDR" else v) for t, v in sublist(tes4.body())]
tes4.set_body(pack_subs(hd))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{changed} cells' terrain rewritten; {added} street models added ({updated} already in); "
      f"{removed // 2} gone ({removed} records); {bounds} paving/building bounds refreshed; next id {nxt:06X}")
