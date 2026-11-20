"""Where the stick comes down: eight XMarkerHeadings on Sicily DZ behind Nate's landing spot,
along the jump run, about 65 m apart (the author: a realistic spread), each door's men in their
own line; the jumpmaster's StickLandings property, in Stick's order."""
import sys, struct, math
from esplib import *
import vmadlib
from landh import load_heights, height_at

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
JM, JUMP_MARKER, XMH = 0x010073B2, 0x010045FE, 0x00000034
M = 1 / 0.014287                     # game units a metre
hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)

found = {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        found[n.fid] = (n, sib)
        assert b"StickLandings" not in n.raw, "already done"
mark, msib = found[JUMP_MARKER]
d = dict(sublist(mark.body()))
mx, my, mz, _, _, mh = struct.unpack("<6f", d[b"DATA"][:24])
hs = load_heights(top)
fx, fy = math.sin(mh), math.cos(mh)          # his facing, the jump run's direction
lx, ly = -fy, fx                              # his left: the port door's side
# Stick's order: outboard starboard 1, 2; outboard port 1, 2; inboard starboard 1, 2; inboard port 1, 2.
# Out of each door: outboard 1, inboard 1, outboard 2, inboard 2. Nate is first out starboard; the
# port men land in a line 25 m to the left, half a step behind, so none comes down where he looks.
order = {"stbd": [0, 4, 1, 5], "port": [2, 6, 3, 7]}
places = [None] * 8
for k, i in enumerate(order["stbd"]):
    places[i] = (65.0 * (k + 1), 0.0)
for k, i in enumerate(order["port"]):
    places[i] = (35.0 + 65.0 * k, 25.0)
refs = []
for i, (back, left) in enumerate(places):
    x = mx - fx * back * M + lx * left * M
    y = my - fy * back * M + ly * left * M
    z = height_at(hs, x, y) + 8.0
    fid = 0x01000000 | nxt
    nxt += 1
    body = pack_subs([(b"NAME", struct.pack("<I", XMH)), (b"DATA", struct.pack("<6f", x, y, z, 0.0, 0.0, mh))])
    msib.append(Rec(b"REFR" + struct.pack("<III", len(body), 0x400, fid) + bytes(mark.raw[16:24]) + body))
    refs.append(fid)
    print(f"{i}: {fid:08X} {back:5.0f} m back, {left:2.0f} m left: {x:8.0f} {y:8.0f} {z:6.0f}")

jm, _ = found[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] != "StickLandings"] + [["StickLandings", 11, 1, vmadlib.obj_array(refs)]]
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
