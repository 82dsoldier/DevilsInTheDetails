"""Sergeant Airborne, jump school's instructor at the mock door (the author, 2026-11-27): a
black hat, nobody's name, loud and deadpan.

  - The black hat (DevilsBlackHat, "Black Hat", slot 30 as the vanilla caps; its addon
    AADevilsBlackHat) from make_black_hat.py's BlackHat.nif, built as esp_uniform.py builds the
    beret, from the jump kit's armor.
  - His outfit (DevilsAirborneOutfit): the post-war fatigues, the black hat, and the subdued
    jump wings Brannock wears on his chest (DevilsJumpWings).
  - His base (DevilsSergeantAirborne, "Sergeant Airborne") is a copy of SSG Brannock's (the
    paratrooper's, essential and unique, staying at his editor location), with another vanilla
    Minutemen face (FACE, MaleRough voice like Brannock's, a different man) and the outfit.
  - He stands in the sawdust out from the mock door's doorway and a little forward of it,
    facing the door, where he can watch a man stand in it (STAND_*, from out/hanscom/mockdoor.json).
    A persistent reference in Hanscom's persistent cell.

Add his base to esp_restore_npcs.py's BASES: the CK rewrites templated NPCs' race on save.

    python esp_airborne.py in.esp out.esp
"""
import json, math, struct, sys
from esplib import *

HANSCOM = 0x0100A22E
KIT_ARMO, KIT_ARMA = 0x01007407, 0x01007406
TEMPLATE = 0x01008B42
FACE = 0x001BF0B3                     # EncMinutemenFaceM06: MaleRough voice
FATIGUES = 0x0019CBB3                 # ClothesFatiguesPostWar
HAT_MODEL = r"DevilsInTheDetails\Uniform\BlackHat.nif"
INFO = "C:/source/repos/BraggMap/out/hanscom/mockdoor.json"
STAND_OUT = 150.0                     # units past the landing spot, out from the door
STAND_FWD = 130.0                     # and toward the fuselage's forward end (out of the way)

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode("latin1")
by_edid = {edid(r): r for r in recs.values()}
assert "DevilsSergeantAirborne" not in by_edid, "already done"


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(recs[TEMPLATE].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


group = lambda label: [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == label][0]

# The hat.
bod2 = struct.pack("<I", 1 << (30 - 30))
arma_fid, hat_fid = new_fid(), new_fid()
arma = [(t, b"AADevilsBlackHat\0" if t == b"EDID" else bod2 if t == b"BOD2" else
         HAT_MODEL.encode() + b"\0" if t in (b"MOD2", b"MOD3") else v) for t, v in sublist(recs[KIT_ARMA].body())]
armo = [(t, b"DevilsBlackHat\0" if t == b"EDID" else b"Black Hat\0" if t == b"FULL" else bod2 if t == b"BOD2" else
         struct.pack("<I", arma_fid) if t == b"MODL" else v) for t, v in sublist(recs[KIT_ARMO].body())]
group(b"ARMA").kids.append(new_rec("ARMA", arma_fid, arma))
group(b"ARMO").kids.append(new_rec("ARMO", hat_fid, armo))

# The outfit.
wings = by_edid["DevilsJumpWings"].fid
outfit = new_rec("OTFT", new_fid(), [(b"EDID", b"DevilsAirborneOutfit\0"),
                                     (b"INAM", struct.pack("<3I", FATIGUES, hat_fid, wings))])
group(b"OTFT").kids.append(outfit)

# The man: Brannock's base with his own name, face and outfit.
subs_ = []
for t, v in sublist(by_edid["DevilsBrannock"].body()):
    if t == b"EDID":
        v = b"DevilsSergeantAirborne\0"
    elif t == b"FULL":
        v = b"Sergeant Airborne\0"
    elif t == b"TPLT":
        v = struct.pack("<I", FACE)
    elif t == b"TPTA":
        v = struct.pack("<I", FACE) + v[4:]
    elif t == b"DOFT":
        v = struct.pack("<I", outfit.fid)
    subs_.append((t, v))
npc = new_rec("NPC_", new_fid(), subs_)
group(b"NPC_").kids.append(npc)

# His spot: past the landing spot, out from the door, a little forward, facing the door.
info = json.load(open(INFO))
sp = info["spots"]
dx, dy, _ = sp["door_sill"]
lx, ly, lz = sp["landing"]
ux, uy = lx - dx, ly - dy
ln = math.hypot(ux, uy)
ux, uy = ux / ln, uy / ln
h = math.radians(info["heading"])
fx, fy = -math.cos(h), math.sin(h)            # the model's -x (forward) in the world
x = lx + ux * STAND_OUT + fx * STAND_FWD
y = ly + uy * STAND_OUT + fy * STAND_FWD
# The model's origin z: esp_mock_door.py put it on the paving; the spots are heights above it.
door = [r for r in recs.values() if r.type == "REFR" and
        struct.unpack("<I", dict(sublist(r.body()))[b"NAME"])[0] == by_edid["DevilsMockDoor"].fid][0]
oz = struct.unpack_from("<f", dict(sublist(door.body()))[b"DATA"], 8)[0]
z = oz + lz + 8
facing = math.atan2(dx - x, dy - y)
g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
pcell = [k for k in g1.kids if isinstance(k, Rec) and k.type == "CELL" and k.flags & 0x400][0]
g6 = [k for k in g1.kids if isinstance(k, Group) and k.gtype == 6 and struct.unpack("<I", k.label)[0] == pcell.fid][0]
g8 = [k for k in g6.kids if isinstance(k, Group) and k.gtype == 8][0]
ref = new_rec("ACHR", new_fid(), [(b"NAME", struct.pack("<I", npc.fid)),
                                  (b"DATA", struct.pack("<6f", x, y, z, 0, 0, facing))], flags=0x400)
g8.kids.append(ref)

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 5, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"hat {hat_fid:08X} (addon {arma_fid:08X}), outfit {outfit.fid:08X}, "
      f"DevilsSergeantAirborne {npc.fid:08X} at {x:.0f}, {y:.0f}, {z:.0f} facing "
      f"{math.degrees(facing):.0f}; reference {ref.fid:08X}")
