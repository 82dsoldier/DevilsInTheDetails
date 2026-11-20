"""Jump doors that close for takeoff: DevilsC130DoorOpen/Closed statics, a ref of each on each
door (persistent; the closed ones Initially Disabled), the hydraulics/door/wind sounds, and the
jumpmaster's properties for them."""
import sys, struct
from esplib import *
import vmadlib
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read(); top = parse(data)
before = count(top)
HULL_STAT, DOORS, JM, PERSIST_CELL = 0x01004D99, (0x010073B7, 0x010073B8), 0x010073B2, 0x01003E64
SND_TEMPLATE, SOM_STEREO = 0x01005CD9, 0x0007EDCA
hdr = top[0]; hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)
def new_id():
    global nxt
    f = 0x01000000 | nxt; nxt += 1; return f
def clone(rec, fid, subs_):
    body = pack_subs(subs_)
    r = Rec(rec.raw[:24] + body); struct.pack_into("<I", r.raw, 4, len(body)); struct.pack_into("<I", r.raw, 12, fid)
    return r
f = {}; pgroup = None
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.fid in (HULL_STAT, JM, SND_TEMPLATE) + DOORS: f[n.fid] = (n, sib)
    if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == PERSIST_CELL: pgroup = n
    assert not (isinstance(n, Rec) and b"DevilsC130DoorClosed" in n.raw), "already done"
assert len(f) == 5 and pgroup

# statics
hull, hsib = f[HULL_STAT]
stats = {}
for closed, edid, nif, full in ((False, "DevilsC130DoorOpen", "C130_DoorOpen", "Jump Door"),
                                (True, "DevilsC130DoorClosed", "C130_DoorClosed", "Jump Door")):
    parts, _ = c.door_panel_parts(c.DEFAULT_LENGTH, closed)
    vs = [v for _, _, m in parts.values() for v in m.verts]
    lo = [int(min(v[i] for v in vs) * 70) - 1 for i in range(3)]
    hi = [int(max(v[i] for v in vs) * 70) + 1 for i in range(3)]
    fid = new_id(); stats[closed] = fid
    sl = []
    for t, v in sublist(hull.body()):
        if t == b"EDID": v = edid.encode() + b"\0"
        if t == b"OBND": v = struct.pack("<6h", *lo, *hi)
        if t == b"MODL": v = f"DevilsInTheDetails\Aircraft\{nif}.nif".encode() + b"\0"
        if t == b"FULL": v = full.encode() + b"\0"
        sl.append((t, v))
    hsib.append(clone(hull, fid, sl))
    print(f"STAT {fid:08X} {edid} bounds {lo} {hi}")

# refs on each door, where the activators are
refs = {False: [], True: []}
for door in DOORS:
    d, _ = f[door]
    pos = dict(sublist(d.body()))[b"DATA"]
    for closed in (False, True):
        rid = new_id(); refs[closed].append(rid)
        body = pack_subs([(b"NAME", struct.pack("<I", stats[closed])), (b"DATA", pos)])
        r = Rec(b"REFR" + struct.pack("<III", len(body), 0x400 | (0x800 if closed else 0), rid) + bytes(d.raw[16:24]) + body)
        pgroup.kids.append(r)
        print(f"REFR {rid:08X} {'closed' if closed else 'open'} at {struct.unpack('<3f', pos[:12])}")

# sounds
tmpl, tsib = f[SND_TEMPLATE]
props = []
for prop, edid, wav, loop in (("Hydraulics", "DevilsC130Hydraulics", "hydraulics", False),
                              ("DoorOpenSound", "DevilsC130DoorOpenSound", "door_open", False),
                              ("EnginesCruiseDoors", "DevilsC130EnginesCruiseDoors", "engines_cruise_doors", True)):
    fid = new_id(); sl = []
    for t, v in sublist(tmpl.body()):
        if t == b"EDID": v = edid.encode() + b"\0"
        if t == b"ANAM": v = ("data\Sound\FX\DevilsInTheDetails\C130\\" + wav + ".wav").encode() + b"\0"
        if t == b"ONAM": v = struct.pack("<I", SOM_STEREO)
        if t == b"LNAM": v = bytes((0, 0x08 if loop else 0, 0, 0))
        sl.append((t, v))
    tsib.append(clone(tmpl, fid, sl))
    props.append([prop, 1, 1, struct.pack("<HhI", 0, -1, fid)])
    print(f"SNDR {fid:08X} {edid}")
props += [["DoorsOpen", 11, 1, vmadlib.obj_array(refs[False])], ["DoorsClosed", 11, 1, vmadlib.obj_array(refs[True])]]

jm, _ = f[JM]
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
print(before, "->", after)
