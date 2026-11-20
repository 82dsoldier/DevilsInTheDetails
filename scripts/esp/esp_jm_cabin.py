"""The jumpmaster's CabinMarker property: DevilsC130CabinMarker (0100B883)."""
import sys, struct
from esplib import *
import vmadlib
JM, MARKER = 0x010073B2, 0x0100B883
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid == JM:
        subs_ = sublist(n.body())
        for k, (t, v) in enumerate(subs_):
            if t == b"VMAD":
                vv, ff, sc, rest = vmadlib.parse(v)
                sc[0][2] = [q for q in sc[0][2] if q[0] != "CabinMarker"] + \
                    [["CabinMarker", 1, 1, struct.pack("<HhI", 0, -1, MARKER)]]
                subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
        n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("CabinMarker set")
