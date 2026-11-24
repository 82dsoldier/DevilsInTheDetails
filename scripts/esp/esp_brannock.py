"""SSG Dale Brannock, the Devils' recruiting sergeant at Hanscom (the author, 2026-11-24): an
ex-drill sergeant stuck behind a recruiting table, who hates it and recruits by insulting you
until you want to prove him wrong.

  - His base (DevilsBrannock) is the paratroopers' (DevilsParatrooperOutboard) with its own name,
    essential and unique, his face and voice from one vanilla Minutemen face (FACE, template,
    Use Traits only, so the face is the same every time), and vanilla's stay-at-editor-location
    package in place of the jump's.
  - His outfit (DevilsBrannockOutfit): the vanilla post-war fatigues. The maroon beret with the
    1-504 flash and the subdued jump wings over his left pocket come next (worn models).
  - He stands just outside the recruiting station's big doorway (the Hanscom Aero Club's, on
    its ramp side), facing the ramp, where the recruits will line up. A persistent reference in
    Hanscom's persistent cell.

Add his base to esp_restore_npcs.py's BASES: the CK rewrites templated NPCs' race on save.

    python esp_brannock.py in.esp out.esp
"""
import sys, struct, math
from esplib import *
from landh import load_heights, height_at

HANSCOM = 0x0100A22E
PARATROOPER = 0x010073D7
TEMPLATE = 0x01008B42
FACE = 0x001BF0B0                     # EncMinutemenFaceM03: MaleRough voice
STAY = 0x00003641                     # DefaultStayAtEditorLocation
FATIGUES = 0x0019CBB3                 # ClothesFatiguesPostWar
# The doorway's middle, and out of it (make_hanscom_buildings.py's opening on the ramp side).
DOORWAY = (27691.0, -21108.0)
OUT = (0.144, 0.990)
STAND_OUT = 300.0

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0")
assert not any(edid(r) == b"DevilsBrannock" for r in recs.values()), "already done"


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

outfit = new_rec("OTFT", new_fid(), [(b"EDID", b"DevilsBrannockOutfit\0"), (b"INAM", struct.pack("<I", FATIGUES))])
group(b"OTFT").kids.append(outfit)

subs_ = []
for t, v in sublist(recs[PARATROOPER].body()):
    if t == b"EDID":
        v = b"DevilsBrannock\0"
    elif t == b"FULL":
        v = b"SSG Brannock\0"
    elif t == b"TPLT":
        v = struct.pack("<I", FACE)
    elif t == b"TPTA":
        v = struct.pack("<I", FACE) + v[4:]
    elif t == b"ACBS":
        flags = struct.unpack_from("<I", v)[0] | 0x02 | 0x20          # essential, unique
        v = struct.pack("<I", flags) + v[4:]
    elif t == b"DOFT":
        v = struct.pack("<I", outfit.fid)
    elif t == b"PKID":
        if any(t2 == b"PKID" for t2, _ in subs_):
            continue                                                    # one package: his post
        v = struct.pack("<I", STAY)
    subs_.append((t, v))
npc = new_rec("NPC_", new_fid(), subs_)
group(b"NPC_").kids.append(npc)

# His spot: out of the doorway onto the ramp, facing out of it.
hs = load_heights(top, HANSCOM)
x, y = DOORWAY[0] + STAND_OUT * OUT[0], DOORWAY[1] + STAND_OUT * OUT[1]
z = height_at(hs, x, y) + 16
facing = math.atan2(OUT[0], OUT[1])
g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
pcell = [k for k in g1.kids if isinstance(k, Rec) and k.type == "CELL" and k.flags & 0x400][0]
g6 = [k for k in g1.kids if isinstance(k, Group) and k.gtype == 6 and struct.unpack("<I", k.label)[0] == pcell.fid][0]
g8 = [k for k in g6.kids if isinstance(k, Group) and k.gtype == 8][0]
ref = new_rec("ACHR", new_fid(), [(b"NAME", struct.pack("<I", npc.fid)),
                                  (b"DATA", struct.pack("<6f", x, y, z, 0, 0, facing))], flags=0x400)
g8.kids.append(ref)

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 3, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"DevilsBrannock {npc.fid:08X} (outfit {outfit.fid:08X}) at {x:.0f}, {y:.0f}, {z:.0f} "
      f"facing {math.degrees(facing):.0f}; reference {ref.fid:08X}")
