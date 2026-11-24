"""Hanscom's end of the road from the Commonwealth: a Devils checkpoint, in place of the junk-wall
placeholder esp_edge_door.py put across Langley Road.

  - A chain-link fence across the road and out past both sides, its gate the load door: our own
    DevilsHanscomGate, on vanilla's static (non-opening) pre-war chain-link gate.
  - Outside (toward the map's edge), Jersey barriers staggered across the road, so traffic has
    to weave up to the gate.
  - Inside, a sandbagged position by the road and a guard tower across from it. No guards yet
    (they come with the traffic).

The Hanscom door gets a fresh form ID (a save that used the old one keeps its state on the old
ID, which is gone); the Commonwealth door's destination is pointed at it. The placeholder's junk
walls go. The Commonwealth end keeps its junk walls (the author, 2026-11-24).

    python esp_edge_gate.py in.esp out.esp
"""
import sys, struct, math, mmap
from esplib import *
from landh import load_heights, height_at

ESM = r"C:\Steam\steamapps\common\Fallout 4\Data\Fallout4.esm"
HANSCOM = 0x0100A22E
OLD_DOOR_BASE = "DevilsRoadBarricade"
JUNK_WALLS = {0x000C3895, 0x000C3897, 0x001D15DF, 0x001D15E1}
TEMPLATE = 0x01008B42

GATE_LIKE = 0x0001978F                 # PreWarFenceChainLinkGateStatic01: x -2..372, from its hinge end
GATE_W = 372.0
FENCE = 0x0019C915                     # PreWarFenceChainLink01: x 0..259
FENCE_W = 259.0
# The fence models reach 64 below their origin (the gate 32), for slopes; on this gentle ground
# that buried them, and lifting them 44 floated them (the author, 2026-11-24): halfway.
# The gate is right at 22; the fence still stood a little high there (the author, 2026-11-24).
FENCE_LIFT = 10.0
GATE_LIFT = 22.0
POST = 0x0019C91E                      # PreWarFenceChainLinkPost01
JERSEY = 0x00001E02                    # JerseyBarricade01: x -64..64, z 0..64
SANDBAGS = 0x00045762                  # SandbagWall01 (moveable static): x -111..120
TOWER = 0x001AE17A                     # ShackGuardTower (the workshop tower as a static): z -152..88

# Along the road: the gate's centre at Langley Road's middle, where the placeholder's door was.
CENTRE = (6100.0, -77235.0)
BEARING = 71.3                         # up the road, into the base
# Fence panels each side of the gate (the road is 7 m: 490 units): to the left (north) 4, where
# the perimeter fence (esp_perimeter.py) meets it; to the right (south) 1, to the map edge.
PANELS = {-1: 4, 1: 1}
ARRIVE_IN = 300.0
# (across, along, turn) in the road's frame: across is to the right going in, along is into the
# base (negative: outside the gate).
JERSEYS = [(-200, -350, 0), (-72, -350, 0), (72, -650, 0), (200, -650, 0)]
# Between the road (half-width 245) and the perimeter fence, which runs about 487 to the right.
SANDBAG_WALLS = [(365, 150, 0), (305, 330, 90)]
TOWER_AT = (-520, 260, 0)              # 180 faced it backward (the author, 2026-11-24)

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode()
assert not any(r.type == "DOOR" and edid(r) == "DevilsHanscomGate" for r in recs.values()), "already done"


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


name_of = lambda r: struct.unpack("<I", dict(sublist(r.body()))[b"NAME"])[0]

# The placeholder: the two doors (our barricade base) and Hanscom's junk walls.
old_base = [r for r in recs.values() if r.type == "DOOR" and edid(r) == OLD_DOOR_BASE][0]
hs_g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
hs_pcell = [k for k in hs_g1.kids if isinstance(k, Rec) and k.type == "CELL" and k.flags & 0x400][0]
hs_g6 = [k for k in hs_g1.kids if isinstance(k, Group) and k.gtype == 6 and struct.unpack("<I", k.label)[0] == hs_pcell.fid][0]
hs_g8 = [k for k in hs_g6.kids if isinstance(k, Group) and k.gtype == 8][0]
hs_old = [r for r in hs_g8.kids if isinstance(r, Rec) and r.type == "REFR" and name_of(r) == old_base.fid]
assert len(hs_old) == 1
hs_old = hs_old[0]
cw_ref = [r for r in recs.values() if r.type == "REFR" and name_of(r) == old_base.fid and r is not hs_old]
assert len(cw_ref) == 1
cw_ref = cw_ref[0]
cw_xtel = dict(sublist(cw_ref.body()))[b"XTEL"]
assert struct.unpack_from("<I", cw_xtel)[0] == hs_old.fid
hs_xtel = dict(sublist(hs_old.body()))[b"XTEL"]        # back to the Commonwealth, as it was
gone = [r for r in hs_g8.kids if isinstance(r, Rec) and r.type == "REFR" and name_of(r) in JUNK_WALLS]
assert len(gone) == 4, len(gone)
hs_g8.kids = [k for k in hs_g8.kids if k is not hs_old and not any(k is g for g in gone)]

# The gate base: the static gate's model and MODT, as a door.
esm = open(ESM, "rb")
m = mmap.mmap(esm.fileno(), 0, access=mmap.ACCESS_READ)
i, like = 0, None
while like is None:
    size, = struct.unpack_from("<I", m, i + 4)
    if m[i:i+4] == b"GRUP":
        i += 24 if m[i+8:i+12] == b"STAT" else size
        continue
    if struct.unpack_from("<I", m, i + 12)[0] == GATE_LIKE:
        like = dict(sublist(Rec(m[i:i+24+size]).body()))
    i += 24 + size
gate = new_rec("DOOR", new_fid(), [(b"EDID", b"DevilsHanscomGate\0"), (b"OBND", like[b"OBND"]),
                                   (b"FULL", b"Gate\0"), (b"MODL", like[b"MODL"]), (b"MODT", like[b"MODT"]),
                                   (b"FNAM", b"\x00")])
[n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"DOOR"][0].kids.append(gate)

# The road's frame: a model's own x runs across the road at turn 0 (as the junk walls did).
hs = load_heights(top, HANSCOM)
br = math.radians(BEARING)
across, along = (math.cos(br), -math.sin(br)), (math.sin(br), math.cos(br))
cx, cy = CENTRE


def at(u, v):
    return cx + u * across[0] + v * along[0], cy + u * across[1] + v * along[1]


def ground(u0, u1, v):
    """The lower ground of a piece's two ends (so neither end floats; the other sinks a little)."""
    return min(height_at(hs, *at(u0, v)), height_at(hs, *at(u1, v)))


def ref(base, u, v, z, turn=0.0, flags=0x400, extra=()):
    x, y = at(u, v)
    r = new_rec("REFR", new_fid(), [(b"NAME", struct.pack("<I", base)), *extra,
                                    (b"DATA", struct.pack("<6f", x, y, z, 0, 0, br + math.radians(turn)))], flags)
    hs_g8.kids.append(r)
    return r


# The gate (the door), hinge end on the left.
gx, gy = at(-GATE_W / 2, 0)
gz = ground(-GATE_W / 2, GATE_W / 2, 0) + GATE_LIFT
door = new_rec("REFR", new_fid(), [(b"NAME", struct.pack("<I", gate.fid)), (b"XTEL", hs_xtel),
                                   (b"DATA", struct.pack("<6f", gx, gy, gz, 0, 0, br))], 0x400)
hs_g8.kids.append(door)
added = 1
# Arrival: up the road from the gate, on the ground.
ax, ay = at(0, ARRIVE_IN)
new_xtel = struct.pack("<I3f", door.fid, ax, ay, height_at(hs, ax, ay) + 16) + cw_xtel[16:]
cw_ref.set_body(pack_subs([(t, new_xtel if t == b"XTEL" else v) for t, v in sublist(cw_ref.body())]))

# The fence: panels out from each side of the gate, a post at every joint.
for side in (-1, 1):
    for k in range(PANELS[side]):
        near = GATE_W / 2 + k * FENCE_W
        u0 = near if side > 0 else -(near + FENCE_W)
        ref(FENCE, u0, 0, ground(u0, u0 + FENCE_W, 0) + FENCE_LIFT)
        added += 1
    for k in range(PANELS[side] + 1):
        u = side * (GATE_W / 2 + k * FENCE_W)
        ref(POST, u, 0, height_at(hs, *at(u, 0)) + FENCE_LIFT)
        added += 1
for u, v, t in JERSEYS:
    ref(JERSEY, u, v, ground(u - 64, u + 64, v) - 2, t)
    added += 1
for u, v, t in SANDBAG_WALLS:
    ref(SANDBAGS, u, v, height_at(hs, *at(u, v)), t)
    added += 1
u, v, t = TOWER_AT
ref(TOWER, u, v, ground(u - 150, u + 150, v) + 152, t)
added += 1

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 1 + added - 1 - len(gone), nxt) if t == b"HEDR" else v)
                         for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"gate base {gate.fid:08X}, Hanscom door {door.fid:08X} at {gx:.0f}, {gy:.0f}, {gz:.0f} "
      f"(was {hs_old.fid:08X}); {added} refs added, {len(gone) + 1} removed; arrival {ax:.0f}, {ay:.0f}")
