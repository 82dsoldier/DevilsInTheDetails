"""Boarding the parked C-130 by a load door instead of a script move.

  DOOR DevilsC130LoadDoor (script DevilsBoardPlane), replacing the ACTI DevilsC130BoardingDoor
  Hanscom's persistent cell (it had none), with the door's reference in it, where the
    activator's was; teleport to the cabin's aisle
  a hidden door (vanilla InvisibleLoad01Hidden) under the cabin floor over Sicily, persistent,
    linked back: its marker on the ramp by the parked plane's step
  the jumpmaster's CabinMarker property removed (the catch step is gone)

    python esp_loaddoor.py in.esp out.esp
"""
import sys, struct, math
from esplib import *
import vmadlib

HANSCOM, SICILY_PERSIST = 0x0100A22E, 0x01003E64
JM, NO_RIG, BOARDED = 0x010073B2, 0x01005534, 0x0100B881
OLD_ACTI = 0x0100B884
HIDDEN_DOOR = 0x001A8458             # InvisibleLoad01Hidden
CABIN = (-13870.0, -20975.0, 24320.0)
CABIN_FACING = 104.0                 # aft, toward the doors and the jumpmaster
FLOOR_Z = 24312.0
DOOR_LOCAL = (-2.15 - 1.4, -5.2)     # metres, plane frame: on the ramp beside the boarding step
UNIT_M = 0.0142875

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0, like=OLD_ACTI):
    body = pack_subs(subs_)
    hdr = bytearray(recs[like].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


def z(s):
    return s.encode() + b"\0"


obj = lambda f: struct.pack("<HhI", 0, -1, f)

# The door base, from the activator's model and bounds.
acti = dict(sublist(recs[OLD_ACTI].body()))
vmad = vmadlib.build(6, 2, [["DevilsBoardPlane", 0, [["NoRigMessage", 1, 1, obj(NO_RIG)],
                                                     ["Boarded", 1, 1, obj(BOARDED)]]]], b"")
door = new_rec("DOOR", new_fid(), [(b"EDID", z("DevilsC130LoadDoor")), (b"VMAD", vmad),
                                   (b"OBND", acti[b"OBND"]), (b"FULL", z("C-130")),
                                   (b"MODL", acti[b"MODL"]), (b"MODT", acti[b"MODT"]),
                                   (b"FNAM", b"\x00")])
door_group = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"DOOR"]
if door_group:
    door_group[0].kids.append(door)
else:                                # no DOOR group yet: one where the standard order has it
    AFTER = (b"INGR", b"LIGH", b"MISC", b"STAT", b"SCOL", b"MSTT", b"GRAS", b"TREE", b"FLOR",
             b"FURN", b"WEAP", b"AMMO", b"NPC_")
    groups = [n for n in top if isinstance(n, Group) and n.gtype == 0]
    nxt_g = min((top.index(g) for g in groups if g.label in AFTER))
    hdr = bytearray(groups[0].hdr)
    hdr[8:12] = b"DOOR"
    top.insert(nxt_g, Group(bytes(hdr), [door]))

# Out with the activator and its reference (keep where it stood).
old_ref = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "REFR" and struct.unpack("<I", dict(sublist(n.body()))[b"NAME"])[0] == OLD_ACTI:
        old_ref = n
        sib.remove(n)
        break
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid == OLD_ACTI:
        sib.remove(n)
        break
px, py, pz, rx, ry, rz = struct.unpack("<6f", dict(sublist(old_ref.body()))[b"DATA"][:24])

# Hanscom's persistent cell, as Sicily's.
sicily_cell = recs[SICILY_PERSIST]
cell_fid = new_fid()
cell = Rec(bytes(sicily_cell.raw))
struct.pack_into("<I", cell.raw, 12, cell_fid)
wc = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
sic6 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 6 and struct.unpack("<I", n.label)[0] == SICILY_PERSIST][0]
sic8 = [k for k in sic6.kids if isinstance(k, Group) and k.gtype == 8][0]
g8 = Group(bytes(sic8.hdr[:8]) + struct.pack("<I", cell_fid) + bytes(sic8.hdr[12:]), [])
g6 = Group(bytes(sic6.hdr[:8]) + struct.pack("<I", cell_fid) + bytes(sic6.hdr[12:]), [g8])
wc.kids[0:0] = [cell, g6]

# The two doors, linked.
hanscom_ref_fid, cabin_ref_fid = new_fid(), new_fid()
c, s_ = math.cos(rz), math.sin(rz)
lx, ly = DOOR_LOCAL[0] / UNIT_M, DOOR_LOCAL[1] / UNIT_M
out_x, out_y = px + lx * c + ly * s_, py - lx * s_ + ly * c
out_facing = rz - math.pi / 2                       # facing away from the plane's port side
xtel = lambda f, pos, rot: struct.pack("<I6fII", f, *pos, *rot, 0, 0)
hanscom_ref = new_rec("REFR", hanscom_ref_fid, [
    (b"NAME", struct.pack("<I", door.fid)),
    (b"XTEL", xtel(cabin_ref_fid, CABIN, (0, 0, math.radians(CABIN_FACING)))),
    (b"DATA", struct.pack("<6f", px, py, pz, rx, ry, rz))], flags=0x400)
cabin_ref = new_rec("REFR", cabin_ref_fid, [
    (b"NAME", struct.pack("<I", HIDDEN_DOOR)),
    (b"XTEL", xtel(hanscom_ref_fid, (out_x, out_y, pz + 8), (0, 0, out_facing))),
    (b"DATA", struct.pack("<6f", CABIN[0], CABIN[1], FLOOR_Z - 200, 0, 0, math.radians(CABIN_FACING)))],
    flags=0x400)
g8.kids.append(hanscom_ref)
sic8.kids.append(cabin_ref)

# The jumpmaster: no CabinMarker any more.
jm = recs[JM]
subs_ = sublist(jm.body())
for k, (t, v) in enumerate(subs_):
    if t == b"VMAD":
        vv, ff, sc, rest = vmadlib.parse(v)
        sc[0][2] = [q for q in sc[0][2] if q[0] != "CabinMarker"]
        subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
jm.set_body(pack_subs(subs_))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 2, nxt) if t == b"HEDR" else v)
                         for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"DOOR {door.fid:08X}; Hanscom door {hanscom_ref_fid:08X} at {px:.0f}, {py:.0f}, {pz:.0f}; "
      f"cabin door {cabin_ref_fid:08X}; Hanscom persistent cell {cell_fid:08X}; "
      f"back out at {out_x:.0f}, {out_y:.0f}")
