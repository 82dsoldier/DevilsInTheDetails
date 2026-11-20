"""Lay a navmesh's vertices on the floor: python esp_navflat.py in.esp out.esp NAVM_FID FLOOR_Z"""
import sys, struct
from esplib import *
src, dst, fid, floor = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), float(sys.argv[4])
top = parse(open(src, "rb").read())
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid == fid:
        subs_ = []
        for t, v in sublist(n.body()):
            if t == b"NVNM":
                v = bytearray(v)
                cnt = struct.unpack_from("<I", v, 16)[0]
                zs = [struct.unpack_from("<f", v, 20 + 12 * i + 8)[0] for i in range(cnt)]
                print(f"{cnt} vertices, z {min(zs):.0f}-{max(zs):.0f} -> {floor:.0f}")
                for i in range(cnt):
                    struct.pack_into("<f", v, 20 + 12 * i + 8, floor)
                v = bytes(v)
            subs_.append((t, v))
        n.set_body(pack_subs(subs_))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
