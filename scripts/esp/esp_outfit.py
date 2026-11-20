"""Fix the jump references in DevilsInTheDetails.esp: move the starboard door from cell
(4,-71) to (4,-7) with Y corrected, delete the stray red light, drop the emptied cell."""
import struct, zlib, sys

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
DOOR, LIGHT = 0x010073B7, 0x01006479
DOOR_Y = -28653.0


class Group:
    def __init__(self, hdr, kids):
        self.hdr, self.kids = bytearray(hdr), kids

    @property
    def gtype(self): return struct.unpack_from("<i", self.hdr, 12)[0]
    @property
    def label(self): return bytes(self.hdr[8:12])

    def bytes(self):
        body = b"".join(k.bytes() for k in self.kids)
        struct.pack_into("<I", self.hdr, 4, 24 + len(body))
        return bytes(self.hdr) + body


class Rec:
    def __init__(self, raw): self.raw = bytearray(raw)
    @property
    def type(self): return self.raw[:4].decode("latin1")
    @property
    def fid(self): return struct.unpack_from("<I", self.raw, 12)[0]
    @property
    def flags(self): return struct.unpack_from("<I", self.raw, 8)[0]
    def body(self):
        b = bytes(self.raw[24:])
        return zlib.decompress(b[4:]) if self.flags & 0x40000 else b
    def bytes(self): return bytes(self.raw)


def parse(i, end):
    out = []
    while i < end:
        size = struct.unpack_from("<I", data, i + 4)[0]
        if data[i:i+4] == b"GRUP":
            out.append(Group(data[i:i+24], parse(i + 24, i + size))); i += size
        else:
            out.append(Rec(data[i:i + 24 + size])); i += 24 + size
    return out


def subs(b):
    i, out = 0, []
    while i < len(b):
        t, n = b[i:i+4], struct.unpack_from("<H", b, i + 4)[0]
        out.append((t, i + 6, n)); i += 6 + n
    return out


def count(nodes):
    return sum(1 + (count(n.kids) if isinstance(n, Group) else 0) for n in nodes)


top = parse(0, len(data))
before = count(top)
assert data == b"".join(n.bytes() for n in top), "round trip failed"


def walk(nodes, parents=()):
    for idx, n in enumerate(nodes):
        yield n, nodes, idx, parents
        if isinstance(n, Group):
            yield from walk(n.kids, parents + (n,))


def cell_xy(rec):
    for t, o, n in subs(rec.body()):
        if t == b"XCLC":
            return struct.unpack_from("<ii", rec.body(), o)
    return None

NPC = 0x01005CD7
ITEMS = [0x0019CBB3, 0x0019CBB1]          # ClothesFatiguesPostWar, Armor_Army_Helmet_postwar
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
new_fid = 0x01000000 | nxt
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid == NPC:
        npc = n
assert not any(isinstance(n, Rec) and n.type == "OTFT" and b"DevilsJumpmasterOutfit" in n.body()
               for n, *_ in walk(top)), "outfit already there"

edid = b"DevilsJumpmasterOutfit\0"
inam = struct.pack(f"<{len(ITEMS)}I", *ITEMS)
rb = b"EDID" + struct.pack("<H", len(edid)) + edid + b"INAM" + struct.pack("<H", len(inam)) + inam
raw = bytearray(b"OTFT" + struct.pack("<III", len(rb), 0, new_fid) + bytes(npc.raw[16:24]) + rb)
outfit = Rec(raw)

groups = [n for n in top if isinstance(n, Group)]
existing = [g for g in groups if g.label == b"OTFT"]
if existing:
    existing[0].kids.append(outfit)
else:
    g = Group(bytes(groups[0].hdr[:8]) + b"OTFT" + bytes(groups[0].hdr[12:24]), [outfit])
    struct.pack_into("<i", g.hdr, 12, 0)
    after = ORDER[ORDER.index("OTFT") + 1:]
    pos = next((top.index(x) for x in groups if x.label.decode("latin1") in after), len(top))
    top.insert(pos, g)

# Point the jumpmaster's default outfit at it.
b = npc.body()
out = b""
for t, o2, ln in subs(b):
    v = b[o2:o2+ln]
    if t == b"DOFT":
        print("DOFT", v.hex(), "->", hex(new_fid)); v = struct.pack("<I", new_fid)
    out += t + struct.pack("<H", len(v)) + v
packed = struct.pack("<I", len(out)) + zlib.compress(out) if npc.flags & 0x40000 else out
npc.raw = bytearray(npc.raw[:24]) + packed
struct.pack_into("<I", npc.raw, 4, len(packed))

after_n = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + (after_n - before), nxt + 1)
print(f"new outfit {new_fid:08X}; records+groups {before} -> {after_n}; next id {nxt:x} -> {nxt + 1:x}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
