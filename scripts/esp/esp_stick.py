"""The stick: 8 Devils paratroopers seated by the doors in the C-130, for DevilsJumpmaster to
stand up on the commands. Adds DevilsC130SeatMarker (FURN), DevilsSitLinkedSeatQuiet (PACK),
DevilsParatrooper (NPC_), 8 seat refs and 8 jumper refs (persistent; jumpers Initially
Disabled), and the jumpmaster's Stick / StickSeats / SeatLink properties."""
import sys, struct, math
from esplib import *
from esmrec import esm_body
import vmadlib
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
JM_NPC, JM, HULL_STAT, PERSIST_CELL = 0x01005CD7, 0x010073B2, 0x01004D99, 0x01003E64
CHAIR, SIT_PACK, STAY_PACK = 0x000AE440, 0x001C4E73, 0x000D4AD3
FACES, LINK = 0x001BF0B6, 0x0005D5E6          # LCharMinutemenFacesMale, LinkCustom01
HX, HY, HZ = 17390.0, -26770.0, 24300.0
ORDER = ("GMST KYWD LCRT AACT TRNS CMPO TXST GLOB DMGT CLAS FACT HDPT EYES RACE SOUN ASPC MGEF "
         "LTEX ENCH SPEL ACTI TACT ARMO BOOK CONT DOOR INGR LIGH MISC STAT SCOL MSTT GRAS TREE "
         "FLOR FURN WEAP AMMO NPC_ PLYR LVLN KEYM ALCH IDLM NOTE PROJ HAZD BNDS TERM LVLI WTHR "
         "CLMT SPGD RFCT REGN NAVI CELL WRLD QUST IDLE PACK CSTY LSCR LVSP ANIO WATR EFSH EXPL "
         "DEBR IMGS IMAD FLST PERK BPTD ADDN AVIF CAMS CPTH VTYP MATT IPCT IPDS ARMA ECZN LCTN "
         "MESG DOBJ DFOB LGTM MUSC FSTP FSTS SMBN SMQN SMEN DLBR MUST DLVW EQUP RELA SCEN ASTP "
         "OTFT ARTO MATO MOVT SNDR SNCT SOPM COLL CLFM REVB PKIN RFGP AMDL LAYR COBJ OMOD MSWP "
         "ZOOM INNR KSSM AECH SCCO AORU SCSN STAG NOCM LENS GDRY OVIS").split()

hdr = top[0]
hb = hdr.body()
assert not hdr.flags & 0x80, "localized plugin"
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


f = {}
pgroup = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid in (JM_NPC, JM, HULL_STAT):
        f[n.fid] = (n, sib)
    if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == PERSIST_CELL:
        pgroup = n
    assert not (isinstance(n, Rec) and b"DevilsParatrooper" in n.raw), "already done"
assert len(f) == 3 and pgroup
VER = bytes(f[HULL_STAT][0].raw[16:24])            # form version etc., as our other records


def make(typ, fid, sl, flags=0):
    body = pack_subs(sl)
    return Rec(typ.encode() + struct.pack("<III", len(body), flags, fid) + VER + body)


def top_group(label):
    groups = [g for g in top if isinstance(g, Group)]
    for g in groups:
        if g.label == label.encode():
            return g
    g = Group(bytes(groups[0].hdr[:8]) + label.encode() + bytes(groups[0].hdr[12:24]), [])
    struct.pack_into("<i", g.hdr, 12, 0)
    after = ORDER[ORDER.index(label) + 1:]
    pos = next((top.index(x) for x in groups if x.label.decode("latin1") in after), len(top))
    top.insert(pos, g)
    return g


# Seat marker furniture: the vanilla folding chair's sit marker, invisible.
_, cb = esm_body("FURN", CHAIR)
seat_base = new_id()
sl = []
for t, v in sublist(cb):
    if t == b"EDID":
        v = b"DevilsC130SeatMarker\0"
    elif t == b"FULL":
        v = b"Troop Seat\0"
    elif t == b"MODL":
        v = b"Markers\\InvisibleGeneric01.nif\0"
    elif t == b"MODT":
        continue
    sl.append((t, v))
top_group("FURN").kids.append(make("FURN", seat_base, sl))

# A quiet sit package: sit in the LinkCustom01 furniture, no hellos or chatter.
_, pb = esm_body("PACK", SIT_PACK)
pack = new_id()
sl = []
for t, v in sublist(pb):
    if t == b"EDID":
        v = b"DevilsSitLinkedSeatQuiet\0"
    if t == b"PKDT":
        v = v[:8] + b"\0\0" + v[10:]
    sl.append((t, v))
top_group("PACK").kids.append(make("PACK", pack, sl))

# The paratrooper: the jumpmaster's uniform, a random Minuteman face (Use Traits).
jm_npc, jsib = f[JM_NPC]
npc = new_id()
sl = []
FACE = {b"HCLF", b"PNAM", b"MSDK", b"MSDV", b"MRSV", b"FMRI", b"FMRS", b"FMIN", b"QNAM"}
for t, v in sublist(jm_npc.body()):
    if t in FACE:
        continue
    if t == b"EDID":
        v = b"DevilsParatrooper\0"
    if t == b"FULL":
        v = b"Paratrooper\0"
    if t == b"ACBS":
        v = v[:14] + struct.pack("<H", 0x0001) + v[16:]
    if t == b"RNAM":
        sl.append((b"TPLT", struct.pack("<I", FACES)))
        sl.append((b"TPTA", struct.pack("<13I", FACES, *[0] * 12)))
    if t == b"PKID":
        sl += [(b"PKID", struct.pack("<I", pack)), (b"PKID", struct.pack("<I", STAY_PACK))]
        continue
    sl.append((t, v))
jsib.append(make("NPC_", npc, sl, jm_npc.flags & ~0x40000))

# Seats and jumpers: two outboard and two centreline seats a side, the nearest the doors.
# Each jumper's reference stands where he'll stand after "stand up": in his side's aisle, in a
# line facing aft, behind room for Nate by the door.
hinge = -c.DEFAULT_LENGTH / 2
db = hinge + c.DOOR_AFT + c.DOOR_W
y0 = db + c.SEAT_AFT_GAP
wall = c.wall_x(c.SEAT_Z) - 0.01
inner = c.CENTER_BACK_W / 2 + c.SEAT_D
aisle = (inner + wall - c.SEAT_D) / 2
LINE = [-5.2, -4.6, -4.0, -3.4]


def heading(dx):                    # facing +X is 90 degrees, -X 270 (clockwise from north)
    return math.pi / 2 if dx > 0 else 3 * math.pi / 2


seats, jumpers = [], []
order = [(outboard, side, k) for outboard in (True, False) for side in (1, -1) for k in (0, 1)]
for outboard, side, k in order:
    sy = y0 + (k + 0.5) * c.SEAT_W
    sx = side * (wall - c.SEAT_D / 2) if outboard else side * (inner - c.SEAT_D / 2)
    face = -side if outboard else side
    sid = new_id()
    seats.append(sid)
    pgroup.kids.append(make("REFR", sid, [
        (b"NAME", struct.pack("<I", seat_base)),
        (b"DATA", struct.pack("<6f", HX + 70 * sx, HY + 70 * sy, HZ, 0, 0, heading(face)))], 0x400))
    spot = LINE[2 * k + (0 if outboard else 1)]
    aid = new_id()
    jumpers.append(aid)
    pgroup.kids.append(make("ACHR", aid, [
        (b"NAME", struct.pack("<I", npc)),
        (b"DATA", struct.pack("<6f", HX + 70 * side * aisle, HY + 70 * spot, HZ + 2, 0, 0, math.pi))],
        0x400 | 0x800))
    print(f"{'outboard' if outboard else 'inboard '} {'stbd' if side > 0 else 'port'} seat {k}: "
          f"seat {sid:08X} at ({sx:+.2f}, {sy:+.2f}) m; jumper {aid:08X} stands at "
          f"({side * aisle:+.2f}, {spot:+.2f})")

jm, _ = f[JM]
props = [["Stick", 11, 1, vmadlib.obj_array(jumpers)],
         ["StickSeats", 11, 1, vmadlib.obj_array(seats)],
         ["SeatLink", 1, 1, struct.pack("<HhI", 0, -1, LINK)]]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        names = {p[0] for p in props}
        s[2] = [p for p in s[2] if p[0] not in names] + props
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"FURN {seat_base:08X}, PACK {pack:08X}, NPC_ {npc:08X}; {before} -> {after}")
