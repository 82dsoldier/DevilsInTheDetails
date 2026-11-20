"""Sound records for the C-130 engines (2D stereo, the loops looping) and the jumpmaster's properties."""
import sys, struct
from esplib import *
import vmadlib
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read(); top = parse(data)
before = count(top)
TEMPLATE, JM, SOM_STEREO = 0x01005CD9, 0x010073B2, 0x0007EDCA
SOUNDS = [("EnginesIdle", "DevilsC130EnginesIdle", "engines_idle", True),
          ("EnginesTakeoff", "DevilsC130EnginesTakeoff", "engines_takeoff", False),
          ("EnginesCruise", "DevilsC130EnginesCruise", "engines_cruise", True)]
hdr = top[0]; hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)
tmpl = jm = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid == TEMPLATE: tmpl, tsib = n, sib
    if isinstance(n, Rec) and n.fid == JM: jm = n
    assert not (isinstance(n, Rec) and n.type == "SNDR" and b"DevilsC130Engines" in n.body()), "already done"
props = []
for prop, edid, wav, loop in SOUNDS:
    fid = 0x01000000 | nxt; nxt += 1
    out = []
    for t, v in sublist(tmpl.body()):
        if t == b"EDID": v = edid.encode() + b"\0"
        if t == b"ANAM": v = f"data\Sound\FX\DevilsInTheDetails\C130\{wav}.wav".encode() + b"\0"
        if t == b"ONAM": v = struct.pack("<I", SOM_STEREO)
        if t == b"LNAM": v = bytes((0, 0x08 if loop else 0, 0, 0))
        out.append((t, v))
    body = pack_subs(out)
    r = Rec(tmpl.raw[:24] + body); struct.pack_into("<I", r.raw, 4, len(body)); struct.pack_into("<I", r.raw, 12, fid)
    tsib.append(r)
    props.append([prop, 1, 1, struct.pack("<HhI", 0, -1, fid)])
    print(f"SNDR {fid:08X} {edid}")
out = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [p for p in s[2] if p[0] not in {x[0] for x in props}] + props
        v = vmadlib.build(ver, fmt, sc, rest)
    out.append((t, v))
jm.set_body(pack_subs(out))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(before, "->", after)
