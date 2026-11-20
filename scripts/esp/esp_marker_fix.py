"""Move the boarding door's arrival point to the clear floor between the paratroop doors (it was
on the centre line of seats, and a jumper in power armor doesn't fit there, so the game set him
on the DZ), and name the cabin's cell "C-130" (a load door shows where it leads)."""
import sys, struct, math
from esplib import *
HANSCOM_DOOR, CABIN_DOOR, MARKER = 0x0100B889, 0x0100B88A, 0x0100B883
PLANE_CELL = (-4, -6)
SICILY = 0x0100293F
ARRIVE = (-13700.0, -21015.0, 24322.0)       # between the doors, aft of the seats
FACING = math.radians(104.0)                 # aft
src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
for n, sib, idx, par in walk(top):
    if not isinstance(n, Rec):
        continue
    if n.fid == HANSCOM_DOOR:
        subs_ = []
        for t, v in sublist(n.body()):
            if t == b"XTEL":
                f, *_r, fl, ti = struct.unpack("<I6fII", v)
                v = struct.pack("<I6fII", f, *ARRIVE, 0, 0, FACING, fl, ti)
            subs_.append((t, v))
        n.set_body(pack_subs(subs_))
    elif n.fid in (CABIN_DOOR, MARKER):
        subs_ = []
        for t, v in sublist(n.body()):
            if t == b"DATA":
                z = ARRIVE[2] - 200 if n.fid == CABIN_DOOR else ARRIVE[2]
                v = struct.pack("<6f", ARRIVE[0], ARRIVE[1], z, 0, 0, FACING) + v[24:]
            subs_.append((t, v))
        n.set_body(pack_subs(subs_))
    elif n.type == "CELL" and any(p.gtype == 1 and struct.unpack("<I", p.label)[0] == SICILY for p in par):
        d = sublist(n.body())
        dd = dict(d)
        if b"XCLC" in dd and struct.unpack_from("<ii", dd[b"XCLC"]) == PLANE_CELL:
            d = [(t, v) for t, v in d if t != b"FULL"]
            i = [t for t, v in d].index(b"EDID") + 1 if b"EDID" in dd else 0
            d.insert(i, (b"FULL", b"C-130\0"))
            n.set_body(pack_subs(d))
            print("named cell", hex(n.fid))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("arrival", ARRIVE)
