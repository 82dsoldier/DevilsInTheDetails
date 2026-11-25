"""Jump school's mock door into the plugin: a STAT for MockDoor.nif (make_mock_door.py) and one
reference of it on Hanscom's East Ramp, in front of jump school, from out/hanscom/mockdoor.json.
The ramp's paving stands PAVING_OFFSET above the terrain; the model goes on the paving, at the
lowest of its corners and centre so no corner of the kerb floats.

    python esp_mock_door.py in.esp out.esp

Run once (it refuses a plugin that already has DevilsMockDoor). The sawdust needs navmesh in the
Creation Kit before Sergeant Airborne can walk on it.
"""
import json
import math
import struct
import sys

from esplib import *
from landh import load_heights, height_at

WORLD = 0x0100A22E                     # DevilsHanscomWorld
TEMPLATE_STAT = 0x01008B42             # DevilsC130DoorFrame: header, MODT and DNAM to copy
INFO = "C:/source/repos/BraggMap/out/hanscom/mockdoor.json"
PAVING_OFFSET = 10.0                   # make_hanscom_paving.py's OFFSET
CELL = 4096.0

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
info = json.load(open(INFO))
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode("latin1")
assert not any(r.type == "STAT" and edid(r) == "DevilsMockDoor" for r in recs.values()), "already done"
tmpl = recs[TEMPLATE_STAT]
tsub = dict(sublist(tmpl.body()))


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(tmpl.raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


# Where: the lowest ground under the kerb's corners and the centre.
x, y = info["position"]
h = math.radians(info["heading"])
b = info["bounds"]
hs = load_heights(top, WORLD)
pts = [(x, y)] + [(x + px * math.cos(h) + py * math.sin(h), y - px * math.sin(h) + py * math.cos(h))
                  for px in (b[0], b[3]) for py in (b[1], b[4])]
zs = [height_at(hs, *p) for p in pts]
z = min(zs) + PAVING_OFFSET

stat = new_rec("STAT", new_fid(), [(b"EDID", b"DevilsMockDoor\0"), (b"OBND", struct.pack("<6h", *b)),
                                   (b"MODL", info["nif"].encode() + b"\0"), (b"MODT", tsub[b"MODT"]),
                                   (b"DNAM", tsub[b"DNAM"])])
[n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"STAT"][0].kids.append(stat)
refr = new_rec("REFR", new_fid(), [(b"NAME", struct.pack("<I", stat.fid)),
                                   (b"DATA", struct.pack("<6f", x, y, z, 0, 0, h))])

# Into its cell's temporary children.
cx, cy = int(x // CELL), int(y // CELL)
cell = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "CELL" and any(
            p.gtype == 1 and struct.unpack("<I", p.label)[0] == WORLD for p in par):
        d = dict(sublist(n.body()))
        if b"XCLC" in d and struct.unpack_from("<ii", d[b"XCLC"]) == (cx, cy):
            cell = n
assert cell, (cx, cy)
grp = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 6
       and struct.unpack("<I", n.label)[0] == cell.fid][0]
temp = [k for k in grp.kids if isinstance(k, Group) and k.gtype == 9]
if not temp:
    hdr = bytearray(grp.hdr)
    struct.pack_into("<i", hdr, 12, 9)
    temp = [Group(bytes(hdr), [])]
    grp.kids.append(temp[0])
temp[0].kids.append(refr)

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 2, nxt) if t == b"HEDR" else v)
                         for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"STAT {stat.fid:08X} DevilsMockDoor, REFR {refr.fid:08X} in cell {cx},{cy} at "
      f"{x:.0f}, {y:.0f}, {z:.0f}, heading {info['heading']:.1f} (ground {min(zs):.0f} to {max(zs):.0f})")
for k, (sx, sy, sz) in info["spots"].items():
    print(f"  {k:<10} {sx:.0f}, {sy:.0f}, {z + sz:.0f}")
