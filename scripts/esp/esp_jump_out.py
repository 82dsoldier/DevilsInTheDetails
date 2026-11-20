"""Nate steps out of the plane for real (the game sets a teleported actor down on the navmesh,
so the jump marker no longer works with the DZ navmeshed). The plane, every reference of it, is
turned to heading 284 (the jump run west-northwest, as the landing was laid out; the starboard
door opens north-northeast) and moved so that a man stepping out of the starboard door comes down where the jump
marker is; its four cell-bound references go to the cell under it. A STAT DevilsC130DoorFrame (the
doorway with nothing in it) at each door, Initially Disabled, for the green light; the
jumpmaster's JumpDoors and DoorFrames. The stick's landing markers re-placed along the new run."""
import sys, struct, math
from esplib import *
import vmadlib
from landh import load_heights, height_at

src, dst = sys.argv[1], sys.argv[2]
top = parse(open(src, "rb").read())
before = count(top)
SICILY, JM, HULL_REF = 0x0100293F, 0x010073B2, 0x010073B9
JUMP_MARKER, JUMP_DOOR_ACTI, OPEN_STAT = 0x010045FE, 0x01005535, 0x010073CC
JUMP_DOORS = (0x010073B7, 0x010073B8)          # starboard, port
OLD_O = (17390.0, -26770.0, 24300.0)
H = math.radians(284.0)
EXIT = (180.0, -483.0)                          # where a man stepping out the starboard door comes down, in the plane's frame
M = 1 / 0.014287
hdr = top[0]
hb = hdr.body()
(o,) = [o for t, o, n in subs(hb) if t == b"HEDR"]
num, nxt = struct.unpack_from("<iI", hb, o + 4)


def new_id():
    global nxt
    fid = 0x01000000 | nxt
    nxt += 1
    return fid


def rot(x, y, a):
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


recs, cells, cellgroups = {}, {}, {}
def visit(nodes, world, cell):
    for n in nodes:
        if isinstance(n, Rec):
            recs[n.fid] = (n, nodes)
            assert b"DevilsC130DoorFrame" not in n.raw, "already done"
            if bytes(n.raw[:4]) == b"CELL" and world == SICILY:
                d = dict(sublist(n.body()))
                if b"XCLC" in d:
                    cells[struct.unpack_from("<ii", d[b"XCLC"])] = n.fid
        else:
            gt = struct.unpack_from("<i", n.hdr, 12)[0]
            lb = struct.unpack_from("<I", n.hdr, 8)[0]
            if gt in (6, 8, 9):
                cellgroups[(lb, gt)] = n
            visit(n.kids, lb if gt == 1 else world, lb if gt in (6, 8, 9) else cell)
visit(top, None, None)

mk = dict(sublist(recs[JUMP_MARKER][0].body()))
lx, ly = struct.unpack("<2f", mk[b"DATA"][:8])
ex, ey = rot(*EXIT, H)
O = (lx - ex, ly - ey, OLD_O[2])
print(f"plane origin {O[0]:.0f} {O[1]:.0f} {O[2]:.0f}, heading 284")


def data_of(rec):
    return struct.unpack("<6f", dict(sublist(rec.body()))[b"DATA"][:24])


def set_data(rec, vals):
    rec.set_body(pack_subs([(t, struct.pack("<6f", *vals) + v[24:]) if t == b"DATA" else (t, v)
                            for t, v in sublist(rec.body())]))


# Every plane reference: in the Sicily world, at flight height, near the old origin.
plane = []
for fid, (rec, sib) in recs.items():
    if bytes(rec.raw[:4]) in (b"REFR", b"ACHR") and fid != JUMP_MARKER:
        d = dict(sublist(rec.body()))
        if b"DATA" not in d:
            continue
        x, y, z = struct.unpack("<3f", d[b"DATA"][:12])
        if abs(x - OLD_O[0]) < 3000 and abs(y - OLD_O[1]) < 3000 and z > 20000:
            plane.append(fid)
for fid in plane:
    rec, _ = recs[fid]
    x, y, z, rx, ry, rz = data_of(rec)
    wx, wy = rot(x - OLD_O[0], y - OLD_O[1], H)
    set_data(rec, (O[0] + wx, O[1] + wy, z, rx, ry, (rz + H) % (2 * math.pi)))
print(len(plane), "references moved")

# The cell-bound ones into the cell under the plane.
cx, cy = int(O[0] // 4096), int(O[1] // 4096)
new_cell = cells[(cx, cy)]
temp = cellgroups.get((new_cell, 9))
assert temp is not None, "no temporary group in the new cell"
moved = 0
for fid in plane:
    rec, sib = recs[fid]
    if any(sib is g.kids for (lb, gt), g in cellgroups.items() if gt == 9 and lb != new_cell):
        sib.remove(rec)
        temp.kids.append(rec)
        moved += 1
print(f"{moved} references into cell {cx}, {cy}")

# The open doorway.
op, op_sib = recs[OPEN_STAT]
acti = dict(sublist(recs[JUMP_DOOR_ACTI][0].body()))
sid = new_id()
sb = pack_subs([(b"EDID", b"DevilsC130DoorFrame" + bytes(1)), (b"OBND", acti[b"OBND"]),
                (b"MODL", b"DevilsInTheDetails\Aircraft\C130_DoorFrame.nif" + bytes(1))])
op_sib.append(Rec(b"STAT" + struct.pack("<III", len(sb), 0, sid) + bytes(op.raw[16:24]) + sb))
print(f"STAT {sid:08X} DevilsC130DoorFrame")
persist_sib = recs[0x010073CE][1]               # with the open doors, in the persistent cell
frames = []
for door in JUMP_DOORS:
    rec, _ = recs[door]
    body = pack_subs([(b"NAME", struct.pack("<I", sid)), (b"DATA", dict(sublist(rec.body()))[b"DATA"])])
    fid = new_id()
    persist_sib.append(Rec(b"REFR" + struct.pack("<III", len(body), 0x400 | 0x800, fid) + bytes(rec.raw[16:24]) + body))
    frames.append(fid)
print("frames", " ".join(f"{f:08X}" for f in frames))

# The stick's landing markers, along the new run: behind is back up the run, the port men to the
# plane's left.
jm, _ = recs[JM]
ver, fmt, sc, rest = vmadlib.parse(dict(sublist(jm.body()))[b"VMAD"])
(s,) = [s for s in sc if s[0] == "DevilsJumpmaster"]
(land,) = [q for q in s[2] if q[0] == "StickLandings"]
land_ids = [struct.unpack_from("<I", land[3], 4 + 8 * k + 4)[0] for k in range(struct.unpack_from("<I", land[3])[0])]
hs = load_heights(top)
back = (-math.sin(H), -math.cos(H))
left = (-math.cos(H), math.sin(H))
places = {0: (65, 0), 4: (130, 0), 1: (195, 0), 5: (260, 0), 2: (35, 25), 6: (100, 25), 3: (165, 25), 7: (230, 25)}
for i, fid in enumerate(land_ids):
    b_m, l_m = places[i]
    x = lx + (back[0] * b_m + left[0] * l_m) * M
    y = ly + (back[1] * b_m + left[1] * l_m) * M
    set_data(recs[fid][0], (x, y, height_at(hs, x, y) + 8.0, 0.0, 0.0, H))
    print(f"  landing {i}: {x:8.0f} {y:8.0f}")
s[2] = [q for q in s[2] if q[0] not in ("JumpDoors", "DoorFrames")] + \
    [["JumpDoors", 11, 1, vmadlib.obj_array(list(JUMP_DOORS))], ["DoorFrames", 11, 1, vmadlib.obj_array(frames)]]
jm.set_body(pack_subs([(t, vmadlib.build(ver, fmt, sc, rest)) if t == b"VMAD" else (t, v) for t, v in sublist(jm.body())]))

after = count(top)
struct.pack_into("<iI", hdr.raw, 24 + o + 4, num + after - before, nxt)
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{before} -> {after}")
