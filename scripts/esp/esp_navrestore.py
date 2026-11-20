"""Bring back the cabin's navmesh (0x0100C029, deleted in the CK) from the save before, with its
place in the navmesh index (NAVI) and the doors' links to it (XNDP), and lay it on the floor:
the CK's floated 16-40 units above it, so a MoveTo onto a mark lifted each man and dropped him
again, twice a second (the hold), and the hooks rode under the cable."""
import sys, struct
from esplib import *
NAVM, CABIN_CELL, FLOOR_Z = 0x0100C029, 0x0100B88B, 24301.0
src, had, dst = sys.argv[1:4]
top = parse(open(src, "rb").read())
old = {n.fid: n for n, *_ in walk(parse(open(had, "rb").read())) if isinstance(n, Rec)}
nav = Rec(bytes(old[NAVM].raw))
subs_ = []
for t, v in sublist(nav.body()):
    if t == b"NVNM":
        v = bytearray(v)
        for i in range(struct.unpack_from("<I", v, 16)[0]):
            struct.pack_into("<f", v, 20 + 12 * i + 8, FLOOR_Z)
        v = bytes(v)
    subs_.append((t, v))
nav.set_body(pack_subs(subs_))
temp = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 9 and struct.unpack("<I", n.label)[0] == CABIN_CELL][0]
temp.kids.append(nav)
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.type == "NAVI":
        n.raw = bytearray(old[n.fid].raw)
    if isinstance(n, Rec) and n.type == "REFR" and n.fid in old:
        o = dict(sublist(old[n.fid].body()))
        if b"XNDP" in o and b"XNDP" not in dict(sublist(n.body())):
            n.set_body(old[n.fid].body())
            print("door link back:", hex(n.fid))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("navmesh restored, flat at", FLOOR_Z)
