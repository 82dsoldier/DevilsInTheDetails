"""Hanscom's perimeter: a chain-link fence the whole way round, just inside the map's edge, and a
border region at the edge, so the gate on the road in is the only way in or out.

  - The fence runs INSET in from the edge, panel after panel along the ground (each at the
    lower ground of its two ends, lifted as the checkpoint's are), a post at every joint.
  - It meets the checkpoint's fence (esp_edge_gate.py, run first), which stands on its south
    line, at both of its ends.
  - Where it crosses a street, junk walls instead of the fence: the Devils closed every
    road in but one.
  - Here and there (PATCH_EVERY, at random but the same every run) a panel is down and patched:
    a junk wall.
  - The breach (BREACH): a stretch with no fence at all, where raiders come through (the
    settlement quest closes it with 10 junk items; the author, 2026-11-24). Posts stand at its
    ends.
  - A guard tower inside each corner.
  - DevilsHanscomBorder: a border region (record flag 0x40, like vanilla's Border) round the
    map's edge, so the breach doesn't let the player walk off the map.

The pieces are ordinary (temporary) references in the cells they stand in.

    python esp_perimeter.py in.esp out.esp
"""
import sys, struct, math, random
import numpy as np
from esplib import *
from landh import load_heights, height_at

HANSCOM = 0x0100A22E
TEMPLATE = 0x01008B42
CELL = 4096.0
# The fenced map (esp_crop.py's PLAY): cells x -1..12, y -11..-5. Outside it, the real Hanscom's
# cells kept as scenery, and the filler ring.
X_MIN, X_MAX, Y_MIN, Y_MAX = -1 * CELL, 13 * CELL, -11 * CELL, -4 * CELL
PAINT_X0, PAINT_Y1 = -25 * CELL, 19 * CELL    # road_paint.npy's grid: the whole of the old map
INSET = 128.0
FENCE, FENCE_W, POST = 0x0019C915, 259.0, 0x0019C91E
FENCE_LIFT = 10.0                       # as esp_edge_gate.py's
JUNK_WALLS = [0x000C3895, 0x000C3897, 0x001D15DF, 0x001D15E1]   # about 280 long, centred
TOWER, TOWER_Z = 0x001AE17A, 152.0      # its origin sits 152 above its base
TOWER_IN = 500.0                        # from the corner, each way
PATCH_EVERY = 25                        # about one panel in this many is a patch
ROAD = 0.25                             # asphalt at a panel's middle (0 to 1) that makes it a road
SEED = 1715
# The border region's polygon is the map's edge, but what the game goes by is each cell's list of
# its regions (XCLR, which the Creation Kit fills in): a cell inside the border lists it, as
# vanilla's do (cell 0,0 lists Border). With only the polygon, no cell was inside, and the
# Commonwealth door sent the player back to itself (tested 2026-11-24). So every map cell lists
# it; the filler ring's cells don't, and are outside.
BORDER_OUT = 0.0
# The checkpoint (esp_edge_gate.py): its fence's ends, on the line across the road at the gate.
GATE_CENTRE, GATE_BEARING, GATE_W = (15820.0, -44928.0), 9.3, 372.0
ARM_LEFT, ARM_RIGHT = 1, 1              # its panels each side
# The breach: on the south side, below the DRMO, this stretch of x.
BREACH = (26000.0, 26800.0)
OUT = "C:/source/repos/BraggMap/out/hanscom/"

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
assert not any(r.type == "REGN" for r in recs.values()), "already done"
paint = np.load(OUT + "road_paint.npy")
hs = load_heights(top, HANSCOM)


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0):
    body = pack_subs(subs_)
    hdr = bytearray(recs[TEMPLATE].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


# Hanscom's cells and their children, for each piece's temporary group.
g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
by_xy, children = {}, {}
for n, *_ in walk(g1.kids):
    if isinstance(n, Rec) and n.type == "CELL" and not n.flags & 0x400:
        by_xy[struct.unpack_from("<ii", dict(sublist(n.body()))[b"XCLC"])] = n.fid
    if isinstance(n, Group) and n.gtype == 6:
        children[struct.unpack("<I", n.label)[0]] = n


def temp_group(cfid):
    grp = children[cfid]
    temp = [k for k in grp.kids if isinstance(k, Group) and k.gtype == 9]
    if temp:
        return temp[0]
    hdr = bytearray(grp.hdr)
    struct.pack_into("<i", hdr, 12, 9)
    t = Group(bytes(hdr), [])
    grp.kids.append(t)
    return t


added = 0


def place(base, x, y, z, rz):
    global added
    cell = by_xy[(int(math.floor(x / CELL)), int(math.floor(y / CELL)))]
    temp_group(cell).kids.append(new_rec("REFR", new_fid(), [
        (b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", x, y, z, 0, 0, rz))]))
    added += 1


def asphalt(x, y):
    r, c = int(round((PAINT_Y1 - y) / 128)), int(round((x - PAINT_X0) / 128))
    return float(paint[r, c]) if 0 <= r < paint.shape[0] and 0 <= c < paint.shape[1] else 0.0


# The checkpoint's arm ends.
gb = math.radians(GATE_BEARING)
across = (math.cos(gb), -math.sin(gb))
arm = lambda u: (GATE_CENTRE[0] + u * across[0], GATE_CENTRE[1] + u * across[1])
left_end = arm(-(GATE_W / 2 + ARM_LEFT * FENCE_W))
right_end = arm(GATE_W / 2 + ARM_RIGHT * FENCE_W)
x0, x1, y0, y1 = X_MIN + INSET, X_MAX - INSET, Y_MIN + INSET, Y_MAX - INSET
# From the checkpoint's right (east) end round to its left: east along the south side, up the
# east, along the north, down the west, east along the south to the gate.
path = [right_end, (x1, y0), (x1, y1), (x0, y1), (x0, y0), left_end]

def euler(d):
    """(rx, ry, rz) that turn a model's own x along the unit vector d, its z as near up as can be.
    The game's rotation, found from vanilla's fence panels on slopes (each tilted one's far end
    meets the next one's origin): world = Rx(-rx) Ry(-ry) Rz(-rz) local, standard right-handed."""
    up = np.array([0.0, 0.0, 1.0])
    z = up - d * (up @ d)
    z /= np.linalg.norm(z)
    m = np.column_stack([d, np.cross(z, d), z])
    a, b, c = math.atan2(-m[1, 2], m[2, 2]), math.asin(max(-1.0, min(1.0, m[0, 2]))), math.atan2(-m[0, 1], m[0, 0])
    return -a, -b, -c


def span(px, py, dx, dy):
    """How far along the ground a panel from (px, py) reaches: its length is along the slope."""
    h, hp = FENCE_W, height_at(hs, px, py)
    for _ in range(3):
        dz = height_at(hs, px + h * dx, py + h * dy) - hp
        h = math.sqrt(max(FENCE_W ** 2 - dz * dz, (FENCE_W / 2) ** 2))
    return h


def place_rot(base, x, y, z, rot):
    global added
    cell = by_xy[(int(math.floor(x / CELL)), int(math.floor(y / CELL)))]
    temp_group(cell).kids.append(new_rec("REFR", new_fid(), [
        (b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", x, y, z, *rot))]))
    added += 1


rng = random.Random(SEED)
counts = {"fence": 0, "road": 0, "patch": 0, "breach": 0, "tilted": 0}
worst = 0.0
in_breach = False
for (ax, ay), (bx, by) in zip(path, path[1:]):
    L = math.hypot(bx - ax, by - ay)
    dx, dy = (bx - ax) / L, (by - ay) / L
    rz = math.atan2(-dy, dx)                 # a model's own x along the segment
    # Panel starts, each where the last one ends along the ground; the last one overlaps the one
    # before it, to end at b.
    starts, s = [], 0.0
    while True:
        h = span(ax + s * dx, ay + s * dy, dx, dy)
        if s + h >= L:
            back = L - FENCE_W
            for _ in range(3):
                back = L - span(ax + back * dx, ay + back * dy, dx, dy)
            starts.append((max(back, 0.0), L - max(back, 0.0)))
            break
        starts.append((s, h))
        s += h
    for k, (s, h) in enumerate(starts):
        px, py = ax + s * dx, ay + s * dy
        qx, qy = px + h * dx, py + h * dy
        mx, my = (px + qx) / 2, (py + qy) / 2
        hp, hq = height_at(hs, px, py), height_at(hs, qx, qy)
        z = min(hp, hq)
        if abs(my - y0) < 200 and BREACH[0] <= mx <= BREACH[1]:
            if not in_breach:                    # the post the fence ends on, at the breach's edge
                place(POST, px, py, hp + FENCE_LIFT, 0.0)
            in_breach = True
            counts["breach"] += 1
            continue
        in_breach = False
        # Closed roads and patches are junk walls: Jersey barriers and sandbags (tried first) are
        # waist high, and anyone could hop them (the author, 2026-11-24).
        if max(asphalt(px, py), asphalt(mx, my), asphalt(qx, qy)) > ROAD:
            place(rng.choice(JUNK_WALLS), mx, my, z, rz + math.pi * rng.randrange(2))
            counts["road"] += 1
        elif rng.randrange(PATCH_EVERY) == 0:
            place(rng.choice(JUNK_WALLS), mx, my, z, rz + math.pi * rng.randrange(2))
            counts["patch"] += 1
        else:
            d = np.array([qx - px, qy - py, hq - hp])
            place_rot(FENCE, px, py, hp + FENCE_LIFT, euler(d / np.linalg.norm(d)))
            worst = max(worst, abs(hp - hq))
            counts["fence"] += 1
            counts["tilted"] += abs(hq - hp) > 0.09 * h          # over about 5 degrees
        place(POST, px, py, hp + FENCE_LIFT, 0.0)
    place(POST, bx, by, height_at(hs, bx, by) + FENCE_LIFT, 0.0)

# A guard tower inside each corner, its back to the base (a guess at its front: the checkpoint's,
# turned the way the author settled on, has its local y up the road, into the base).
for cx, cy in [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]:
    ix, iy = math.copysign(1, -cx), math.copysign(1, -cy)        # inward
    tx, ty = cx + ix * TOWER_IN, cy + iy * TOWER_IN
    place(TOWER, tx, ty, min(height_at(hs, tx + a, ty + b) for a in (-150, 150) for b in (-150, 150)) + TOWER_Z,
          math.atan2(ix, iy))

# The border region, at the map's edge.
vanilla_rclr = b"\x62\x73\x73\x00"           # vanilla Border's colour
regn = new_rec("REGN", new_fid(), [
    (b"EDID", b"DevilsHanscomBorder\0"), (b"RCLR", vanilla_rclr), (b"WNAM", struct.pack("<I", HANSCOM)),
    (b"RPLI", struct.pack("<I", 0)),
    (b"RPLD", struct.pack("<8f", X_MIN - BORDER_OUT, Y_MIN - BORDER_OUT, X_MIN - BORDER_OUT, Y_MAX + BORDER_OUT,
                          X_MAX + BORDER_OUT, Y_MAX + BORDER_OUT, X_MAX + BORDER_OUT, Y_MIN - BORDER_OUT))], flags=0x40)
inside = 0
for n, *_ in walk(g1.kids):
    if isinstance(n, Rec) and n.type == "CELL" and not n.flags & 0x400:
        sub = sublist(n.body())
        cx, cy = struct.unpack_from("<ii", dict(sub)[b"XCLC"])
        if not (X_MIN <= cx * CELL < X_MAX and Y_MIN <= cy * CELL < Y_MAX):
            continue
        regions = dict(sub).get(b"XCLR", b"")
        sub = [(t, v) for t, v in sub if t != b"XCLR"]
        at_ = max(i for i, (t, _) in enumerate(sub) if t in (b"XCLC", b"MHDT", b"LTMP", b"XCLW")) + 1
        sub.insert(at_, (b"XCLR", regions + struct.pack("<I", regn.fid)))
        n.set_body(pack_subs(sub))
        inside += 1
navi = [i for i, n in enumerate(top) if isinstance(n, Group) and n.gtype == 0 and n.label == b"NAVI"][0]
ghdr = bytearray(top[navi].hdr)
ghdr[8:12] = b"REGN"
top.insert(navi, Group(bytes(ghdr), [regn]))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added + 2, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{added} references: {counts}; steepest panel {worst:.0f} units end to end; "
      f"border {regn.fid:08X} ({inside} cells inside); next id {nxt:06X}")
