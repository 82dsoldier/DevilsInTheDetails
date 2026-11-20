"""Seat the stick 0.20 m forward (each seat marker moved the way its man faces), so they sit on
the seats' front edges with their mains against the net instead of through it and the wall."""
import sys, struct, math
from esplib import *

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
SEATS = [0x010073D8, 0x010073DA, 0x010073DC, 0x010073DE, 0x010073E0, 0x010073E2, 0x010073E4, 0x010073E6]
FORWARD = float(sys.argv[3]) * 70 if len(sys.argv) > 3 else 0.20 * 70
done = 0
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid in SEATS:
        sl = []
        for t, v in sublist(n.body()):
            if t == b"DATA":
                x, y, z, rx, ry, rz = struct.unpack("<6f", v)
                # Heading clockwise from +Y: facing (sin, cos).
                x2, y2 = x + FORWARD * math.sin(rz), y + FORWARD * math.cos(rz)
                print(f"{n.fid:08X} heading {math.degrees(rz):.0f}: x {x:.1f} -> {x2:.1f}, y {y:.1f} -> {y2:.1f}")
                v = struct.pack("<6f", x2, y2, z, rx, ry, rz)
            sl.append((t, v))
        n.set_body(pack_subs(sl))
        done += 1
assert done == 8, done
open(dst, "wb").write(b"".join(n.bytes() for n in top))
