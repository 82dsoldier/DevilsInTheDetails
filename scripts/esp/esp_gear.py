"""The ruck and weapons case, seated and standing (DevilsJumpGearSeated / ...Standing, slot 58).
From: the jump kit (main, reserve, harness, ruck, weapons case), worn: DevilsJumpKit (ARMO) and its
AA (ARMA), body slot 57, from the vanilla army helmet's records; the jumpmaster's JumpKit.
Adapted from: Worn static lines: out go the per-man STATs and their 8 refs (statics don't move once loaded);
in come DevilsStaticLineRight/Left (ARMO) with their AA (ARMA), body slot 56, from the vanilla
army helmet's records; the jumpmaster's StickLines becomes StaticLineRight / StaticLineLeft."""
import sys, struct
from esplib import *
from esmrec import esm_body
import vmadlib

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
before = count(top)
JM, HULL_STAT = 0x010073B2, 0x01004D99
HELMET_ARMO, HELMET_ARMA = 0x0019CBB1, 0x0019CBB2
SLOT_56 = 1 << (58 - 30)   # slot 58
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
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


found = {}
for n, sib, idx, par in list(walk(top)):
    if isinstance(n, Rec) and n.fid in (JM, HULL_STAT):
        found[n.fid] = n
    assert not (isinstance(n, Rec) and b"DevilsJumpGearSeated" in n.raw), "already done"
VER = bytes(found[HULL_STAT].raw[16:24])
def make(typ, fid, sl):
    body = pack_subs(sl)
    return Rec(typ.encode() + struct.pack("<III", len(body), 0, fid) + VER + body)


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


_, arma_b = esm_body("ARMA", HELMET_ARMA)
_, armo_b = esm_body("ARMO", HELMET_ARMO)
items = {}
for side, nif in (("Seated", "C130_JumpGearSeated"), ("Standing", "C130_JumpGearStanding")):
    model = f"DevilsInTheDetails\\Aircraft\\{nif}.nif".encode() + b"\0"
    aa = new_id()
    sl = []
    for t, v in sublist(arma_b):
        if t == b"EDID":
            v = f"AADevilsJumpGear{side}".encode() + b"\0"
        elif t == b"BOD2":
            v = struct.pack("<I", SLOT_56)
        elif t in (b"MOD2", b"MOD3"):
            v = model
        elif t in (b"MO2T", b"MO3T", b"MO2S", b"MO3S"):
            continue
        sl.append((t, v))
    top_group("ARMA").kids.append(make("ARMA", aa, sl))
    arm = new_id()
    items[side] = arm
    sl = []
    for t, v in sublist(armo_b):
        if t == b"EDID":
            v = f"DevilsJumpGear{side}".encode() + b"\0"
        elif t == b"FULL":
            v = b"Static Line\0"
        elif t == b"BOD2":
            v = struct.pack("<I", SLOT_56)
        elif t == b"MODL":
            v = struct.pack("<I", aa)
        elif t == b"DATA":
            v = struct.pack("<Iff", 0, 0.0, 0.0)[:len(v)]
        elif t == b"FNAM":
            v = bytes(len(v))
        elif t in (b"PTRN", b"MOD2", b"MO2T", b"MO2S", b"KSIZ", b"KWDA", b"DESC"):
            continue
        sl.append((t, v))
    top_group("ARMO").kids.append(make("ARMO", arm, sl))
    print(f"ARMO {arm:08X} DevilsJumpGear{side}, ARMA {aa:08X}")

jm = found[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] not in ("GearSeated", "GearStanding")]
        s[2] += [["Gear" + k, 1, 1, struct.pack("<HhI", 0, -1, items[k])] for k in ("Seated", "Standing")]
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))

# Drop any group left empty.
def prune(nodes):
    for n in list(nodes):
        if isinstance(n, Group):
            prune(n.kids)
            if not n.kids:
                nodes.remove(n)
prune(top)
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
