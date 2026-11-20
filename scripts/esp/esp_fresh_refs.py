"""New form IDs for the cabin's seats, open doors, doorway frames and door slabs. A save keeps
every persistent reference where it last was, and the test saves had these over Sicily, from
before the cabin became an interior: the game drew them there, not in the cabin, and statics
and furniture can't be moved by script. Fresh IDs no save has seen. Only the jumpmaster's
properties pointed at them."""
import sys, struct
from esplib import *
JM = 0x010073B2
OLD = [0x010073D8, 0x010073DA, 0x010073DC, 0x010073DE, 0x010073E0, 0x010073E2, 0x010073E4, 0x010073E6,
       0x010073CE, 0x010073D0, 0x01008B43, 0x01008B44, 0x010073B7, 0x010073B8]
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
remap = {}
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid in OLD:
        new = 0x01000000 | nxt
        nxt += 1
        remap[n.fid] = new
        struct.pack_into("<I", n.raw, 12, new)
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid == JM:
        subs_ = []
        for t, v in sublist(n.body()):
            if t == b"VMAD":
                for o, nw in remap.items():
                    v = v.replace(struct.pack("<I", o), struct.pack("<I", nw))
            subs_.append((t, v))
        n.set_body(pack_subs(subs_))
tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec, nxt) if t == b"HEDR" else v) for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(len(remap), "references renumbered:", ", ".join(f"{o:08X}->{n:08X}" for o, n in remap.items()))
