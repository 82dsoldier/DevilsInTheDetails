"""Turn the cabin (the interior DevilsC130Cabin) to point north, about the hull's origin: every
reference in it, and the teleports that land in it. The door panels' tilt up the wall is about
the world's north-south axis (SetAngle), right only while the plane points north; at 284 degrees
they came in diagonally. Its navmesh is left to be made again in the CK."""
import sys, struct, math
from esplib import *
CABIN, HULL = 0x0100B88B, 0x010073B9
INTO = (0x0100B889, 0x0100B88D)          # teleports landing in the cabin: Hanscom's door, the DZ's
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
hx, hy, hz, _, _, h = struct.unpack_from("<6f", dict(sublist(recs[HULL].body()))[b"DATA"])
c, s = math.cos(h), math.sin(h)


def turn(x, y, rz):
    dx, dy = x - hx, y - hy
    return hx + dx * c - dy * s, hy + dx * s + dy * c, (rz - h) % (2 * math.pi)


def edit(n, fn):
    n.set_body(pack_subs([(t, fn(t, v)) for t, v in sublist(n.body())]))


moved = 0
for n, sib, i, par in walk(top):
    if isinstance(n, Rec) and n.type in ("REFR", "ACHR") and any(
            p.gtype in (8, 9) and struct.unpack("<I", p.label)[0] == CABIN for p in par):
        def fn(t, v):
            if t != b"DATA":
                return v
            x, y, z, rx, ry, rz = struct.unpack_from("<6f", v)
            x, y, rz = turn(x, y, rz)
            return struct.pack("<6f", x, y, z, rx, ry, rz) + v[24:]
        edit(n, fn)
        moved += 1
for f in INTO:
    def fn(t, v):
        if t != b"XTEL":
            return v
        d, x, y, z, rx, ry, rz, fl, ti = struct.unpack("<I6fII", v)
        x, y, rz = turn(x, y, rz)
        return struct.pack("<I6fII", d, x, y, z, rx, ry, rz, fl, ti)
    edit(recs[f], fn)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{moved} references turned {math.degrees(-h) % 360:.0f} degrees about {hx:.0f}, {hy:.0f}; hull now heading 0")
