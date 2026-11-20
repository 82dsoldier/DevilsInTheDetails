"""Each door slab's ExitDoor: its doorway's load door out (starboard B88E, port B88F)."""
import sys, struct
from esplib import *
import vmadlib
PAIRS = {0x0100CF6B: 0x0100B88E, 0x0100CF6A: 0x0100B88F}   # slab (was 010073B7 starboard, B8 port) -> exit
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid in PAIRS:
        subs_ = sublist(n.body())
        for k, (t, v) in enumerate(subs_):
            if t == b"VMAD":
                vv, ff, sc, rest = vmadlib.parse(v)
                sc[0][2] = [q for q in sc[0][2] if q[0] != "ExitDoor"] + [["ExitDoor", 1, 1, struct.pack("<HhI", 0, -1, PAIRS[n.fid])]]
                subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
                print(f"{n.fid:08X} -> {PAIRS[n.fid]:08X}", sc[0][0])
        n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
