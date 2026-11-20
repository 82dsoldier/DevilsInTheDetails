"""The jump doors in five panels that slide round the track: ACTI DevilsC130DoorClosed becomes
DevilsC130DoorPanel0 (C130_DoorPanel0.nif), four more ACTIs for panels 1-4, each with the
DevilsC130DoorPanel script (Panel = k); four more refs on each door where the closed one is;
the jumpmaster's DoorsClosed lists all ten; bounds for the panels (over their whole travel) and
the open door."""
import sys, struct, math
from esplib import *
import vmadlib
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
JM, OPEN_STAT, CLOSED_ACTI = 0x010073B2, 0x010073CC, 0x010073CD
U = 1 / c.UNIT_M

hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


f, closed_refs = {}, []
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec):
        f[n.fid] = (n, sib)
        assert b"DevilsC130DoorPanel" not in n.raw, "already done"
        if n.raw[:4] == b"REFR" and dict(sublist(n.body())).get(b"NAME") == struct.pack("<I", CLOSED_ACTI):
            closed_refs.append((n, sib))
assert len(closed_refs) == 2, closed_refs

segs, keys, _ = c.door_segments(c.DEFAULT_LENGTH)


def bounds(verts):
    lo = [int(math.floor(min(v[i] for v in verts) * U)) - 1 for i in range(3)]
    hi = [int(math.ceil(max(v[i] for v in verts) * U)) + 1 for i in range(3)]
    return struct.pack("<6h", *lo, *hi)


def swept(parts, ks):
    out = []
    for dx, dz, deg in ks:
        co, si = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        for _, _, m in parts.values():
            out += [(x * co - z * si + dx, y, x * si + z * co + dz) for x, y, z in m.verts]
    return out


def script_vmad(k):
    return vmadlib.build(6, 2, [["DevilsC130DoorPanel", 0, [["Panel", 3, 1, struct.pack("<i", k)]]]], b"")


acti, acti_sib = f[CLOSED_ACTI]
VER = bytes(acti.raw[16:24])
bases = []
for k in range(5):
    sl = [(b"EDID", f"DevilsC130DoorPanel{k}\0".encode()),
          (b"VMAD", script_vmad(k)),
          (b"OBND", bounds(swept(segs[k], keys[k]))),
          (b"MODL", f"DevilsInTheDetails\\Aircraft\\C130_DoorPanel{k}.nif\0".encode())]
    body = pack_subs(sl)
    if k == 0:
        acti.set_body(body)
        bases.append(CLOSED_ACTI)
    else:
        fid = new_id()
        acti_sib.append(Rec(b"ACTI" + struct.pack("<III", len(body), acti.flags & ~0x40000, fid) + VER + body))
        bases.append(fid)
    print(f"ACTI {bases[-1]:08X} DevilsC130DoorPanel{k}")

panels = []
for ref, sib in closed_refs:
    panels.append(ref.fid)
    for k in range(1, 5):
        sl = [(t, struct.pack("<I", bases[k]) if t == b"NAME" else v) for t, v in sublist(ref.body())]
        body = pack_subs(sl)
        fid = new_id()
        sib.append(Rec(b"REFR" + struct.pack("<III", len(body), ref.flags & ~0x40000, fid) + bytes(ref.raw[16:24]) + body))
        panels.append(fid)
print("panels", " ".join(f"{p:08X}" for p in panels))

st, _ = f[OPEN_STAT]
op = c.door_open_parts(c.DEFAULT_LENGTH)
st.set_body(pack_subs([(t, bounds([v for _, _, m in op.values() for v in m.verts]) if t == b"OBND" else v)
                       for t, v in sublist(st.body())]))

jm, _ = f[JM]
sl = []
for t, v in sublist(jm.body()):
    if t == b"VMAD":
        ver, fmt, sc, rest = vmadlib.parse(v)
        (s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
        s[2] = [q for q in s[2] if q[0] not in ("DoorsClosed", "DoorRaise")] + \
            [["DoorsClosed", 11, 1, vmadlib.obj_array(panels)]]
        v = vmadlib.build(ver, fmt, sc, rest)
    sl.append((t, v))
jm.set_body(pack_subs(sl))

after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
