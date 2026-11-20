"""Shift the plane (and with it the jump marker and the stick's landings) so the whole of it is
in one cell, (-4, -6): it straddled the border with (-4, -5), and the CK's navmesh, made a cell at
a time, covered only half the cabin floor. Every plane reference, the jump marker and the landing
markers move by the same amount; the landings are set back on the ground."""
import sys, struct
from esplib import *
import vmadlib
from landh import load_heights, height_at

src, dst, dy = sys.argv[1], sys.argv[2], float(sys.argv[3])
top = parse(open(src, "rb").read())
JM, HULL, JUMP_MARKER = 0x010073B2, 0x010073B9, 0x010045FE
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}


def data(rec):
    return list(struct.unpack("<6f", dict(sublist(rec.body()))[b"DATA"][:24]))


def set_data(rec, v):
    rec.set_body(pack_subs([(t, struct.pack("<6f", *v) + b[24:]) if t == b"DATA" else (t, b)
                            for t, b in sublist(rec.body())]))


ox, oy, oz = data(recs[HULL])[:3]
plane = []
for fid, rec in recs.items():
    if bytes(rec.raw[:4]) in (b"REFR", b"ACHR") and fid != JUMP_MARKER:
        d = dict(sublist(rec.body()))
        if b"DATA" in d:
            x, y, z = struct.unpack("<3f", d[b"DATA"][:12])
            if abs(x - ox) < 2000 and abs(y - oy) < 2000 and z > 20000:
                plane.append(fid)
for fid in plane + [JUMP_MARKER]:
    v = data(recs[fid])
    v[1] += dy
    set_data(recs[fid], v)
ver, fmt, sc, rest = vmadlib.parse(dict(sublist(recs[JM].body()))[b"VMAD"])
(land,) = [q for q in sc[0][2] if q[0] == "StickLandings"]
hs = load_heights(top)
for k in range(struct.unpack_from("<I", land[3])[0]):
    fid = struct.unpack_from("<I", land[3], 4 + 8 * k + 4)[0]
    v = data(recs[fid])
    v[1] += dy
    v[2] = height_at(hs, v[0], v[1]) + 8.0
    set_data(recs[fid], v)
print(f"{len(plane)} plane references, the jump marker and 8 landings moved {dy:+.0f} in y; "
      f"plane origin now {ox:.0f} {oy + dy:.0f}, cell {int(ox // 4096)}, {int((oy + dy) // 4096)}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
