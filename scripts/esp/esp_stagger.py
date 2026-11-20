"""Stagger the stick: outboard jumpers in outboard seats 1 and 4 (from the doors), inboard on
the centerline between seats 2-3 and 5-6 (the markers are invisible); each stands straight out from his seat into the aisle, so the line
runs outboard 1, inboard 1, outboard 2, inboard 2, 0.78 m (1.5 seats) apart, so their
collision bodies clear each other, and no one crosses anyone."""
import sys, struct, math
from esplib import *
sys.path.insert(0, r"C:\source\repos\BraggMap\scripts")
import make_c130_blockout as c

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
top = parse(data)
HX, HY, HZ = 17390.0, -26770.0, 24300.0
# (seat ref, jumper ref) in esp_stick.py's order: outboard stbd 0,1; port 0,1; inboard stbd 0,1; port 0,1
PAIRS = [(0x010073D8, 0x010073D9), (0x010073DA, 0x010073DB), (0x010073DC, 0x010073DD),
         (0x010073DE, 0x010073DF), (0x010073E0, 0x010073E1), (0x010073E2, 0x010073E3),
         (0x010073E4, 0x010073E5), (0x010073E6, 0x010073E7)]
hinge = -c.DEFAULT_LENGTH / 2
db = hinge + c.DOOR_AFT + c.DOOR_W
y0 = db + c.SEAT_AFT_GAP
wall = c.wall_x(c.SEAT_Z) - 0.01
inner = c.CENTER_BACK_W / 2 + c.SEAT_D
aisle = (inner + wall - c.SEAT_D) / 2
FIRST, GAP = -5.28, 0.6        # the first jumper's place in line, by outboard seat 1; spacing

recs = {}
for n, *_ in walk(top):
    if isinstance(n, Rec):
        recs[n.fid] = n


def set_pos(fid, x, y, z, rz):
    r = recs[fid]
    sl = [(t, struct.pack("<6f", x, y, z, 0, 0, rz) if t == b"DATA" else v) for t, v in sublist(r.body())]
    r.set_body(pack_subs(sl))


order = [(outboard, side, k) for outboard in (True, False) for side in (1, -1) for k in (0, 1)]
for (outboard, side, k), (seat, jumper) in zip(order, PAIRS):
    seat_no = 3 * k + (0 if outboard else 1.5)          # seats from the doors: O 0, 3; I 1.5, 4.5
    sy = y0 + (seat_no + 0.5) * c.SEAT_W
    sx = side * (wall - c.SEAT_D / 2) if outboard else side * (inner - c.SEAT_D / 2)
    face = -side if outboard else side
    set_pos(seat, HX + 70 * sx, HY + 70 * sy, HZ, math.pi / 2 if face > 0 else 3 * math.pi / 2)
    ly = sy                                              # straight out from his seat
    set_pos(jumper, HX + 70 * side * aisle, HY + 70 * ly, HZ + 2, math.pi)
    print(f"{'outboard' if outboard else 'inboard '} {'stbd' if side > 0 else 'port'} #{k + 1}: "
          f"seat {seat_no + 1} at y {sy:+.2f} m, stands at y {ly:+.2f} m")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
