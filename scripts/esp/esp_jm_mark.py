"""DevilsJumpmasterMark: an XMarkerHeading on the jumpmaster's editor spot (at the floor), in the
cabin's persistent children; and his JumpmasterMark property."""
import sys, struct
from esplib import *
import vmadlib
JM, CABIN, XMH, FLOOR_Z = 0x010073B2, 0x0100B88B, 0x00000034, 24301.0
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
jm = recs[JM]
x, y, z, rx, ry, rz = struct.unpack_from("<6f", dict(sublist(jm.body()))[b"DATA"])
fid = 0x01000000 | nxt
body = pack_subs([(b"EDID", b"DevilsJumpmasterMark\0"), (b"NAME", struct.pack("<I", XMH)),
                  (b"DATA", struct.pack("<6f", x, y, FLOOR_Z, 0, 0, rz))])
hdr = bytearray(jm.raw[:24]); hdr[0:4] = b"REFR"
struct.pack_into("<III", hdr, 4, len(body), 0x400, fid)
persist = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == CABIN][0]
persist.kids.append(Rec(bytes(hdr) + body))
subs_ = sublist(jm.body())
for k, (t, v) in enumerate(subs_):
    if t == b"VMAD":
        vv, ff, sc, rest = vmadlib.parse(v)
        sc[0][2] = [q for q in sc[0][2] if q[0] != "JumpmasterMark"] + [["JumpmasterMark", 1, 1, struct.pack("<HhI", 0, -1, fid)]]
        subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
jm.set_body(pack_subs(subs_))
tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 1, nxt + 1) if t == b"HEDR" else v) for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"mark {fid:08X} at {x:.0f}, {y:.0f}, facing {rz:.2f}")
