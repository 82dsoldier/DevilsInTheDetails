"""Set object properties on the jumpmaster: name=fid pairs.
    python esp_jm_props.py in.esp out.esp CabinMarker=0100B883 Hull=010073B9"""
import sys, struct
from esplib import *
import vmadlib
JM = 0x010073B2
src, dst, *pairs = sys.argv[1:]
props = {k: int(v, 16) for k, v in (p.split("=") for p in pairs)}
top = parse(open(src, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid == JM:
        subs_ = sublist(n.body())
        for k, (t, v) in enumerate(subs_):
            if t == b"VMAD":
                vv, ff, sc, rest = vmadlib.parse(v)
                sc[0][2] = [q for q in sc[0][2] if q[0] not in props] + \
                    [[name, 1, 1, struct.pack("<HhI", 0, -1, f)] for name, f in props.items()]
                subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
        n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("set", {k: f"{v:08X}" for k, v in props.items()})
