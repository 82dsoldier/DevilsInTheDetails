"""Undo the stand furniture (they never got up: a sit package on a second piece of furniture
left them in their seats). The 8 marks stay, as plain vanilla XMarkerHeadings; the stand
packages and DevilsC130StandMarker go."""
import sys, struct
from esplib import *

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
FURN, PACKS = 0x010073FB, {0x01007404, 0x01007405}
STANDS = set(range(0x010073FC, 0x01007404))
NPCS = {0x010073D7, 0x010073EB}
XMARKER_HEADING = 0x00000034
hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)

removed, marks = 0, 0
for n, sib, idx, par in list(walk(top)):
    if not isinstance(n, Rec):
        continue
    if n.fid == FURN or n.fid in PACKS:
        assert n.fid != FURN or b"DevilsC130StandMarker" in n.raw
        sib.remove(n)
        removed += 1
    elif n.fid in STANDS:
        n.set_body(pack_subs([(t, struct.pack("<I", XMARKER_HEADING) if t == b"NAME" else v)
                              for t, v in sublist(n.body())]))
        marks += 1
    elif n.fid in NPCS:
        sl = list(sublist(n.body()))
        keep = [(t, v) for t, v in sl if not (t == b"PKID" and struct.unpack("<I", v)[0] in PACKS)]
        assert len(keep) == len(sl) - 1
        n.set_body(pack_subs(keep))
assert removed == 3 and marks == 8, (removed, marks)
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"removed {removed}, {marks} marks now XMarkerHeading; {before} -> {after}")

# The jumpmaster no longer has StandLink.
import vmadlib
top = parse(open(dst, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid == 0x010073B2:
        sl = []
        for t, v in sublist(n.body()):
            if t == b"VMAD":
                ver, fmt, sc, rest = vmadlib.parse(v)
                (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
                s[2] = [q for q in s[2] if q[0] != "StandLink"]
                print("props:", [q[0] for q in s[2]])
                v = vmadlib.build(ver, fmt, sc, rest)
            sl.append((t, v))
        n.set_body(pack_subs(sl))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
