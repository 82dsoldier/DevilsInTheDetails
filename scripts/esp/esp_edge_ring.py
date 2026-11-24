"""A ring of filler terrain around Hanscom, so the map doesn't end in a gap.

Past a world's last cell the game draws nothing in the loaded cells (sky shows through) and only
then, further out, the world's flat default land. So: RING cells of terrain all round, their
heights carried straight out from the map's edge and eased (smoothstep) down or up to the
world's default land height at the ring's outer edge, where the flat default takes over. No
textures (the default ground, like the rest of Hanscom so far), normals left to the game (zeros,
as the CK's import left them). The world's bounds grow to take the ring in.

    python esp_edge_ring.py in.esp out.esp
"""
import sys, struct
import numpy as np
from esplib import *

HANSCOM = 0x0100A22E
RING = 3

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
world = recs[HANSCOM]
wsub = sublist(world.body())
default_land = struct.unpack("<2f", dict(wsub)[b"DNAM"])[0]
g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]

# Every cell's heights, in VHGT counts (8 units), and a cell to copy records and groups from.
heights, sample = {}, None
for n, sib, idx, par in walk(g1.kids):
    if isinstance(n, Rec) and n.type == "CELL" and not n.flags & 0x400:
        xy = struct.unpack_from("<ii", dict(sublist(n.body()))[b"XCLC"])
        kids = sib[idx + 1]
        land = [r for g in kids.kids if isinstance(g, Group) for r in g.kids if isinstance(r, Rec) and r.type == "LAND"]
        if not land:
            continue
        v = dict(sublist(land[0].body()))[b"VHGT"]
        de = np.array(struct.unpack_from("<1089b", v, 4), np.int64).reshape(33, 33)
        heights[xy] = np.cumsum(de, 1) + np.cumsum(de[:, 0])[:, None] - de[:, 0][:, None] + struct.unpack_from("<f", v)[0]
        if sample is None:
            sample = (n, kids, [g for g in kids.kids if isinstance(g, Group) and g.gtype == 9][0], land[0], v, par)
xs = [x for x, y in heights]
ys = [y for x, y in heights]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
assert len(heights) == (x1 - x0 + 1) * (y1 - y0 + 1), "the map isn't a full rectangle of cells"

# One grid of points over the map and the ring (row 0 = the south edge, as VHGT's rows go).
W, H = (x1 - x0 + 1 + 2 * RING) * 32 + 1, (y1 - y0 + 1 + 2 * RING) * 32 + 1
grid = np.zeros((H, W))
for (cx, cy), h in heights.items():
    r, c = (cy - y0 + RING) * 32, (cx - x0 + RING) * 32
    grid[r:r + 33, c:c + 33] = h
lo, hi = RING * 32, RING * 32 + (y1 - y0 + 1) * 32          # the map's rows lo..hi, inclusive
clo, chi = RING * 32, RING * 32 + (x1 - x0 + 1) * 32
rr, cc = np.mgrid[0:H, 0:W]
er, ec = np.clip(rr, lo, hi), np.clip(cc, clo, chi)          # the nearest point on the map
edge = grid[er, ec]
d = np.hypot(rr - er, cc - ec) / (RING * 32)                 # 0 at the map's edge, 1 at the ring's
t = np.clip(d, 0, 1)
t = t * t * (3 - 2 * t)
target = default_land / 8
ring = np.round(edge * (1 - t) + target * t).astype(np.int64)
inside = (rr >= lo) & (rr <= hi) & (cc >= clo) & (cc <= chi)
assert np.array_equal(ring[inside], grid[inside].astype(np.int64)), "the map's heights aren't whole counts"

cell0, kids0, temp0, land0, v0, par0 = sample
block0, sub0 = par0[-2], par0[-1]                            # the sample cell's block and sub-block
blocks = {struct.unpack("<hh", g.label): g for g in g1.kids if isinstance(g, Group) and g.gtype == 4}


def subblock(cx, cy):
    bkey = (cy >> 5, cx >> 5)
    if bkey not in blocks:
        blocks[bkey] = Group(bytes(block0.hdr[:8]) + struct.pack("<hh", *bkey) + bytes(block0.hdr[12:]), [])
        g1.kids.append(blocks[bkey])
    b = blocks[bkey]
    skey = (cy >> 3, cx >> 3)
    for s in b.kids:
        if isinstance(s, Group) and struct.unpack("<hh", s.label) == skey:
            return s
    s = Group(bytes(sub0.hdr[:8]) + struct.pack("<hh", *skey) + bytes(sub0.hdr[12:]), [])
    b.kids.append(s)
    return s


def with_fid(rec, fid):
    r = Rec(bytes(rec.raw))
    struct.pack_into("<I", r.raw, 12, fid)
    return r


added = 0
for cy in range(y0 - RING, y1 + RING + 1):
    for cx in range(x0 - RING, x1 + RING + 1):
        if (cx, cy) in heights:
            continue
        r, c = (cy - y0 + RING) * 32, (cx - x0 + RING) * 32
        q = ring[r:r + 33, c:c + 33]
        de = np.zeros((33, 33), np.int64)
        de[1:, 0] = q[1:, 0] - q[:-1, 0]
        de[:, 1:] = q[:, 1:] - q[:, :-1]
        assert np.abs(de).max() < 128
        cfid = 0x01000000 | nxt; nxt += 1
        lfid = 0x01000000 | nxt; nxt += 1
        cell = with_fid(cell0, cfid)
        cell.set_body(pack_subs([(t_, v[:0] + struct.pack("<ii", cx, cy) + v[8:] if t_ == b"XCLC" else v)
                                 for t_, v in sublist(cell0.body())]))
        land = with_fid(land0, lfid)
        land.set_body(pack_subs([(b"DATA", dict(sublist(land0.body()))[b"DATA"]),
                                 (b"VNML", bytes(3267)),
                                 (b"VHGT", struct.pack("<f", float(q[0, 0])) + struct.pack("<1089b", *de.flatten().tolist()) + v0[1093:])]))
        temp = Group(bytes(temp0.hdr[:8]) + struct.pack("<I", cfid) + bytes(temp0.hdr[12:]), [land])
        kids = Group(bytes(kids0.hdr[:8]) + struct.pack("<I", cfid) + bytes(kids0.hdr[12:]), [temp])
        subblock(cx, cy).kids += [cell, kids]
        added += 1

# The world's bounds take the ring in.
nam0 = struct.pack("<2f", (x0 - RING) * 4096.0, (y0 - RING) * 4096.0)
nam9 = struct.pack("<2f", (x1 + RING + 1) * 4096.0, (y1 + RING + 1) * 4096.0)
world.set_body(pack_subs([(t_, nam0 if t_ == b"NAM0" else nam9 if t_ == b"NAM9" else v) for t_, v in wsub]))

tes4.set_body(pack_subs([(t_, struct.pack("<fiI", ver, nrec + 2 * added, nxt) if t_ == b"HEDR" else v) for t_, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{added} ring cells (x {x0 - RING}..{x1 + RING}, y {y0 - RING}..{y1 + RING}), easing to {default_land:.0f}; next id {nxt:06X}")
