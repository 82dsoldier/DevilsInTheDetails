"""Replace the cabin's navmesh (0x0100CF5C) with one written here: a flat grid over the whole
cabin floor, wall to wall and from the doors' aft edge to the cargo pallets, on the floor.

The CK's covered only a strip down the middle of the aft half and floated above the floor, and
the game sets actors on the navmesh whenever it places them (MoveTo, SetPosition and load alike):
the jumpmaster's mark and the outboard men's were off it, so every hold put them somewhere else
and they hopped and drifted (tested 2026-11-20).

NVNM layout (version 15), as parsed from the CK's: header (version, magic, parent world 0, parent
cell), vertices, triangles of 21 bytes (3 vertex indices, 3 neighbour triangles or -1, a height,
a byte, flags (0x0800 found?, 0x0400 a door's), cover flags), edge links, door triangles (triangle,
0xE48B73F3, door ref), cover, cover map, waypoints, then the lookup grid (one cell here).

    python esp_navwrite.py in.esp out.esp
"""
import sys, struct
from esplib import *

NAVM = 0x0100CF5C
X0, X1 = -14262.0, -14062.0          # the floor between the walls (the hull's origin x -14162)
Y0, Y1 = -21420.0, -20880.0          # the doors' aft edge to the pallets
Z = 24301.0
NX, NY = 4, 10
DOORS = (0x0100B88A, 0x0100B88E, 0x0100B88F)   # the boarding door's twin, the two jump exits
DOOR_CRC = 0xE48B73F3

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
nav = recs[NAVM]
old = dict(sublist(nav.body()))[b"NVNM"]
header = old[:16]

verts = [(X0 + (X1 - X0) * i / NX, Y0 + (Y1 - Y0) * j / NY, Z) for j in range(NY + 1) for i in range(NX + 1)]
vid = lambda i, j: j * (NX + 1) + i
tris = []
for j in range(NY):
    for i in range(NX):
        a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
        tris += [(a, b, c), (a, c, d)]                     # counter-clockwise from above
edges = {}
for t, (a, b, c) in enumerate(tris):
    for e, (p, q) in enumerate(((a, b), (b, c), (c, a))):
        edges.setdefault(frozenset((p, q)), []).append((t, e))
nbr = [[-1, -1, -1] for _ in tris]
for pairs in edges.values():
    if len(pairs) == 2:
        (t1, e1), (t2, e2) = pairs
        nbr[t1][e1], nbr[t2][e2] = t2, t1


def centroid(t):
    return [sum(verts[k][n] for k in tris[t]) / 3 for n in range(2)]


door_tri = {}
for f in DOORS:
    x, y = struct.unpack_from("<2f", dict(sublist(recs[f].body()))[b"DATA"])
    door_tri[f] = min(range(len(tris)), key=lambda t: (centroid(t)[0] - x) ** 2 + (centroid(t)[1] - y) ** 2)

out = bytearray(header)
out += struct.pack("<I", len(verts)) + b"".join(struct.pack("<3f", *v) for v in verts)
out += struct.pack("<I", len(tris))
for t, (a, b, c) in enumerate(tris):
    flags = 0x0800 | (0x0400 if t in door_tri.values() else 0)
    out += struct.pack("<3H3hfBHH", a, b, c, *nbr[t], 170.0, 0, flags, 0)
out += struct.pack("<I", 0)                                    # edge links
out += struct.pack("<I", len(DOORS)) + b"".join(struct.pack("<hII", door_tri[f], DOOR_CRC, f) for f in DOORS)
out += struct.pack("<I", 0) + struct.pack("<I", 0) + struct.pack("<I", 0)   # cover, cover map, waypoints
out += struct.pack("<Iff", 1, X1 - X0, Y1 - Y0)
out += struct.pack("<3f", X0, Y0, Z) + struct.pack("<3f", X1, Y1, 3.4028234663852886e38)
out += struct.pack("<I", len(tris)) + struct.pack(f"<{len(tris)}h", *range(len(tris)))

nav.set_body(pack_subs([(t, bytes(out) if t == b"NVNM" else v) for t, v in sublist(nav.body())]))
for f in DOORS:
    n = recs[f]
    subs_ = [(t, v) for t, v in sublist(n.body()) if t != b"XNDP"]
    i = [t for t, v in subs_].index(b"DATA")
    subs_.insert(i, (b"XNDP", struct.pack("<IHH", NAVM, door_tri[f], 0)))
    n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{len(verts)} vertices, {len(tris)} triangles over x {X0:.0f}..{X1:.0f}, y {Y0:.0f}..{Y1:.0f} at z {Z:.0f}; "
      f"doors on triangles {[door_tri[f] for f in DOORS]}")
