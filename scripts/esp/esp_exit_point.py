"""Move the jump marker, and the jump exits' teleport, onto the old cabin's navmesh floating over
cell -4, -6 (0x01009A8B): a load door sets the player on the navmesh under its marker, and on
that patch, with nothing solid under it, he falls; at the old marker, just off its edge, he was
set on the ground."""
import sys, struct
from esplib import *
JUMP_MARKER, EXITS = 0x010045FE, (0x0100B88E, 0x0100B88F)
POINT = (-13700.0, -21015.0, 24320.0)      # the clear floor between the old doors, on the patch
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid in (JUMP_MARKER,) + EXITS:
        subs_ = []
        for t, v in sublist(n.body()):
            if n.fid == JUMP_MARKER and t == b"DATA":
                rot = struct.unpack_from("<3f", v, 12)
                v = struct.pack("<6f", *POINT, *rot) + v[24:]
                print("jump marker moved, facing", round(rot[2], 3))
            if n.fid in EXITS and t == b"XTEL":
                f, x, y, z_, rx, ry, rz, fl, ti = struct.unpack("<I6fII", v)
                v = struct.pack("<I6fII", f, *POINT, rx, ry, rz, fl, ti)
            subs_.append((t, v))
        n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
