"""The jumpmaster's hand signals: IDLE DevilsJMSignalHookUp, a dynamic idle cloned from the vanilla
BOS_Salute (dyn_Activation through RaiderRootBehavior), its animation our own JM_HookUp.hkx;
the jumpmaster's SignalHookUp property."""
import sys, struct
from esplib import *
from esmrec import esm_body
import vmadlib

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
JM, HULL_STAT = 0x010073B2, 0x01004D99
BOS_SALUTE = 0x0019E2C8
SIGNALS = [tuple(a.split(",")) for a in sys.argv[3:]]   # edid,property,animation
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
for n, *_ in walk(top):
    if isinstance(n, Rec):
        if n.fid in (JM, HULL_STAT):
            found[n.fid] = n
        assert not any((e + chr(0)).encode() in n.raw for e, _, _ in SIGNALS), "already done"
VER = bytes(found[HULL_STAT].raw[16:24])


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


_, salute = esm_body("IDLE", BOS_SALUTE)
props = []
for edid, prop, anim in SIGNALS:
    sl = []
    for t, v in sublist(salute):
        if t == b"EDID":
            v = edid.encode() + b"\0"
        elif t == b"GNAM":
            v = f"Actors\\Character\\Animations\\DevilsInTheDetails\\{anim}.hkx".encode() + b"\0"
        sl.append((t, v))
    fid = new_id()
    body = pack_subs(sl)
    top_group("IDLE").kids.append(Rec(b"IDLE" + struct.pack("<III", len(body), 0, fid) + VER + body))
    props.append([prop, 1, 1, struct.pack("<HhI", 0, -1, fid)])
    print(f"IDLE {fid:08X} {edid} -> {anim}.hkx")

jm = found[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        names = {q[0] for q in props}
        s[2] = [q for q in s[2] if q[0] not in names] + props
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))

after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
