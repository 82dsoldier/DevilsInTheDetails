"""The apron under the plane: STAT DevilsC130Tarmac (C130_Tarmac.nif), one persistent reference
under the cabin's origin, and the jumpmaster's Tarmac property (shown on the ground, gone as the
doors close for takeoff)."""
import sys, struct
from esplib import *
import vmadlib

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
JM, DOOR_OPEN_STAT, DOOR_REF = 0x010073B2, 0x010073CC, 0x010073CE
HX, HY, HZ = 17390.0, -26770.0, 24300.0
HALF = 440.0 * 70                      # make_c130_blockout.TARMAC_HALF, in units
DROP = 1.03 * 70

hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


f = {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        f[n.fid] = (n, sib)
        assert b"DevilsC130Tarmac" not in n.raw, "already done"
stat, stat_sib = f[DOOR_OPEN_STAT]
door_ref, ref_sib = f[DOOR_REF]
VER = bytes(stat.raw[16:24])


def make(typ, fid, sl, flags=0):
    body = pack_subs(sl)
    return Rec(typ.encode() + struct.pack("<III", len(body), flags, fid) + VER + body)


base = new_id()
sl = []
for t, v in sublist(stat.body()):
    if t == b"EDID":
        v = b"DevilsC130Tarmac\0"
    elif t == b"OBND":
        h = int(HALF)
        v = struct.pack("<6h", -h, -h, -int(DROP) - 1, h, h, -int(DROP) + 1)
    elif t == b"MODL":
        v = b"DevilsInTheDetails\\Aircraft\\C130_Tarmac.nif\0"
    elif t in (b"MODT", b"FULL"):
        continue
    sl.append((t, v))
stat_sib.append(make("STAT", base, sl, stat.flags & ~0x40000))
ref = new_id()
ref_sib.append(make("REFR", ref, [(b"NAME", struct.pack("<I", base)),
                                  (b"DATA", struct.pack("<6f", HX, HY, HZ, 0, 0, 0))], 0x400))
print(f"STAT {base:08X} DevilsC130Tarmac, REFR {ref:08X}")

jm, _ = f[JM]
props = [["Tarmac", 1, 1, struct.pack("<HhI", 0, -1, ref)]]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] != "Tarmac"] + props
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))

after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
