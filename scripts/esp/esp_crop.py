"""Hanscom cropped to the first act (the author, 2026-11-24: a true-scale world, 3 by 2.2 km, is
too big to walk; a Skyrim mod like that got frustrating fast).

Kept: the act's cells (PLAY: the parked C-130, the hangar, the recruiting station, jump school,
the derelicts and the DRMO), which the perimeter fence will close, and MARGIN cells of the real
Hanscom round them, outside the fence, as scenery. Every other cell goes, with everything in it
(terrain, references, navmesh); then the bases nothing places any more (Hanscom's own STATs),
and the removed navmeshes' entries in the navmesh index (NAVI). The navmesh left needs
finalizing again in the Creation Kit: its edges to the removed cells point nowhere.

Run on a plugin from before esp_edge_door.py (the doors, ring, gate, perimeter and paint are
built for the cropped map after it):

    python esp_crop.py in.esp out.esp
"""
import sys, struct
from esplib import *

HANSCOM = 0x0100A22E
PLAY = (-1, 12, -11, -5)                 # cells x0, x1, y0, y1 (inclusive): the fenced map
MARGIN = 3
KEEP = (PLAY[0] - MARGIN, PLAY[1] + MARGIN, PLAY[2] - MARGIN, PLAY[3] + MARGIN)
CELL = 4096.0

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
# New records after the crop start past every ID the uncropped builds used (up to 011600), so a
# save from one of them can't lay its state on a different record with the same ID.
nxt = max(nxt, 0x011600)
g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
inside = lambda cx, cy: KEEP[0] <= cx <= KEEP[1] and KEEP[2] <= cy <= KEEP[3]

removed_nodes = 0
gone_navm = set()
cells_gone = 0
for block in [k for k in g1.kids if isinstance(k, Group) and k.gtype == 4]:
    for sub in [k for k in block.kids if isinstance(k, Group) and k.gtype == 5]:
        keep, drop_next = [], False
        for k in sub.kids:
            if isinstance(k, Rec) and k.type == "CELL":
                cx, cy = struct.unpack_from("<ii", dict(sublist(k.body()))[b"XCLC"])
                drop_next = not inside(cx, cy)
                if drop_next:
                    removed_nodes += 1
                    cells_gone += 1
                    continue
            elif isinstance(k, Group) and k.gtype == 6 and drop_next:
                removed_nodes += count([k])
                gone_navm |= {n.fid for n, *_ in walk([k]) if isinstance(n, Rec) and n.type == "NAVM"}
                drop_next = False
                continue
            keep.append(k)
        sub.kids[:] = keep
    empty = [s for s in block.kids if isinstance(s, Group) and not s.kids]
    removed_nodes += len(empty)
    block.kids[:] = [s for s in block.kids if not (isinstance(s, Group) and not s.kids)]
empty = [b for b in g1.kids if isinstance(b, Group) and b.gtype == 4 and not b.kids]
removed_nodes += len(empty)
g1.kids[:] = [b for b in g1.kids if not (isinstance(b, Group) and b.gtype == 4 and not b.kids)]

# Persistent references outside what's kept (none expected: the C-130's door is on the ramp).
pcell = [k for k in g1.kids if isinstance(k, Rec) and k.type == "CELL" and k.flags & 0x400][0]
for n, *_ in walk(g1.kids):
    if isinstance(n, Rec) and n.type in ("REFR", "ACHR"):
        x, y = struct.unpack_from("<2f", dict(sublist(n.body()))[b"DATA"])
        assert inside(int(x // CELL), int(y // CELL)), f"{n.fid:08X} at {x:.0f}, {y:.0f} is outside what's kept"

# Hanscom's own bases that nothing places any more.
placed = {struct.unpack("<I", dict(sublist(n.body()))[b"NAME"])[0]
          for n, *_ in walk(top) if isinstance(n, Rec) and n.type in ("REFR", "ACHR")}
stat_group = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"STAT"][0]
unused = [s for s in stat_group.kids if isinstance(s, Rec) and s.fid not in placed and dict(sublist(s.body()))
          .get(b"MODL", b"").rstrip(b"\0").decode().lower().startswith("devilsinthedetails\\hanscom\\")]
stat_group.kids[:] = [s for s in stat_group.kids if not any(s is u for u in unused)]
removed_nodes += len(unused)

# The navmesh index: the removed navmeshes' entries.
navi = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"NAVI"][0].kids[0]
ns = sublist(navi.body())
kept = [(t, v) for t, v in ns if not (t == b"NVMI" and struct.unpack_from("<I", v)[0] in gone_navm)]
navi.set_body(pack_subs(kept))

# The world's bounds (esp_edge_ring.py widens them again for its ring).
wrld = [n for n, *_ in walk(top) if isinstance(n, Rec) and n.fid == HANSCOM][0]
nam0 = struct.pack("<2f", KEEP[0] * CELL, KEEP[2] * CELL)
nam9 = struct.pack("<2f", (KEEP[1] + 1) * CELL, (KEEP[3] + 1) * CELL)
wrld.set_body(pack_subs([(t, nam0 if t == b"NAM0" else nam9 if t == b"NAM9" else v) for t, v in sublist(wrld.body())]))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec - removed_nodes, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"kept cells x {KEEP[0]}..{KEEP[1]}, y {KEEP[2]}..{KEEP[3]} (fenced: x {PLAY[0]}..{PLAY[1]}, y {PLAY[2]}..{PLAY[3]}); "
      f"{cells_gone} cells gone, {len(gone_navm)} navmeshes, {len(ns) - len(kept)} index entries, "
      f"{len(unused)} unused STATs")
