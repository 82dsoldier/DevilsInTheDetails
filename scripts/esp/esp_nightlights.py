"""Night cabin lights: DevilsC130CabinLightNight (red, dim) and five refs (Initially Disabled) at the
day lights' spots; all ten moved to the persistent cell; DayLights/NightLights on the jumpmaster."""
import sys, struct
from esplib import *
import vmadlib
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read(); top = parse(data)
before = count(top)
DAY_LIGH, JM, PERSIST_CELL = 0x010073BD, 0x010073B2, 0x01003E64
DAY_REFS = list(range(0x010073BE, 0x010073C3))
hdr = top[0]; hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)
def new_id():
    global nxt
    f = 0x01000000 | nxt; nxt += 1; return f
found, pgroup = {}, None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and (n.fid in DAY_REFS or n.fid in (DAY_LIGH, JM)): found[n.fid] = (n, sib)
    if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == PERSIST_CELL: pgroup = n
    assert not (isinstance(n, Rec) and n.type == "LIGH" and b"CabinLightNight" in n.body()), "already done"
assert len(found) == 7 and pgroup, (found.keys(), pgroup)
# night LIGH
day, dsib = found[DAY_LIGH]
nid = new_id(); out = []
for t, v in sublist(day.body()):
    if t == b"EDID": v = b"DevilsC130CabinLightNight\0"
    if t == b"DATA":
        v = bytearray(v); struct.pack_into("<I", v, 4, 250); v[8:12] = bytes((255, 28, 18, 0)); v = bytes(v)
    if t == b"FNAM": v = struct.pack("<f", 0.45)
    out.append((t, v))
body = pack_subs(out)
night = Rec(day.raw[:24] + body); struct.pack_into("<I", night.raw, 4, len(body)); struct.pack_into("<I", night.raw, 12, nid)
dsib.insert(dsib.index(day) + 1, night)
# move day refs to the persistent cell, persistent; add night twins, persistent + initially disabled
night_refs = []
for fid in DAY_REFS:
    r, sib = found[fid]; sib.remove(r)
    struct.pack_into("<I", r.raw, 8, r.flags | 0x400); pgroup.kids.append(r)
    nr = Rec(bytes(r.raw)); rid = new_id(); struct.pack_into("<I", nr.raw, 12, rid)
    struct.pack_into("<I", nr.raw, 8, 0x400 | 0x800)
    nr.set_body(pack_subs([(t, struct.pack("<I", nid) if t == b"NAME" else v) for t, v in sublist(r.body())]))
    pgroup.kids.append(nr); night_refs.append(rid)
for n in list(walk(top)):        # drop any group the move emptied
    g = n[0]
    if isinstance(g, Group) and not g.kids: n[1].remove(g); print("dropped empty group")
# script properties
jm, _ = found[JM]
out = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [p for p in s[2] if p[0] not in ("DayLights", "NightLights")]
        s[2] += [["DayLights", 11, 1, vmadlib.obj_array(DAY_REFS)], ["NightLights", 11, 1, vmadlib.obj_array(night_refs)]]
        v = vmadlib.build(ver, fmt, sc, rest)
    out.append((t, v))
jm.set_body(pack_subs(out))
after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
print(f"night LIGH {nid:08X}; night refs {[hex(x) for x in night_refs]}; {before} -> {after}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
