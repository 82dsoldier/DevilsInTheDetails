"""The jump doors in one piece: out with panels 1-4 (their bases, their references, and from the
jumpmaster's DoorsClosed)."""
import sys, struct
from esplib import *
import vmadlib
JM = 0x010073B2
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
bases = {f for f, n in recs.items() if dict(sublist(n.body())).get(b"EDID", b"").rstrip(b"\0").decode()
         in [f"DevilsC130DoorPanel{k}" for k in range(1, 5)]}
gone = set(bases)
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.type == "REFR" and struct.unpack("<I", dict(sublist(n.body()))[b"NAME"])[0] in bases:
        gone.add(n.fid)
def prune(nodes):
    keep = []
    for n in nodes:
        if isinstance(n, Rec) and n.fid in gone:
            continue
        if isinstance(n, Group):
            n.kids = prune(n.kids)
        keep.append(n)
    return keep
top[:] = prune(top)
jm = recs[JM]
subs_ = sublist(jm.body())
for k, (t, v) in enumerate(subs_):
    if t == b"VMAD":
        vv, ff, sc, rest = vmadlib.parse(v)
        for q in sc[0][2]:
            if q[0] == "DoorsClosed":
                n_ = struct.unpack_from("<I", q[3])[0]
                fids = [struct.unpack_from("<I", q[3], 4 + 8 * i + 4)[0] for i in range(n_)]
                q[3] = vmadlib.obj_array([f for f in fids if f not in gone])
                print("DoorsClosed", n_, "->", len([f for f in fids if f not in gone]))
        subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
jm.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"removed {len(bases)} bases and {len(gone) - len(bases)} references")
