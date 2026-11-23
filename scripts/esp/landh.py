"""Terrain height in DevilsSicilyWorld from the plugin's LAND records (VHGT)."""
import struct
from esplib import *

SICILY = 0x0100293F


def load_heights(top, world_fid=SICILY):
    """{(cx, cy): 33x33 heights in game units} for a world's cells (Sicily's by default)."""
    SICILY = world_fid
    cells, out = {}, {}
    def visit(nodes, world, cell):
        for n in nodes:
            if isinstance(n, Rec):
                if bytes(n.raw[:4]) == b"WRLD":
                    world = n.fid
                elif bytes(n.raw[:4]) == b"CELL" and world == SICILY:
                    d = dict(sublist(n.body()))
                    if b"XCLC" in d:
                        cells[n.fid] = struct.unpack_from("<ii", d[b"XCLC"])
                elif bytes(n.raw[:4]) == b"LAND" and world == SICILY and cell in cells:
                    d = dict(sublist(n.body()))
                    v = d.get(b"VHGT")
                    if v:
                        off = struct.unpack_from("<f", v)[0]
                        deltas = struct.unpack_from("<1089b", v, 4)
                        h, row = [[0.0] * 33 for _ in range(33)], off
                        for r in range(33):
                            row += deltas[r * 33]
                            acc = row
                            h[r][0] = acc * 8
                            for c in range(1, 33):
                                acc += deltas[r * 33 + c]
                                h[r][c] = acc * 8
                        out[cells[cell]] = h
            else:
                gtype = struct.unpack_from("<i", n.hdr, 12)[0]
                label = struct.unpack_from("<I", n.hdr, 8)[0]
                w = label if gtype == 1 else world
                c = label if gtype in (6, 8, 9) else cell
                visit(n.kids, w, c)
    visit(top, None, None)
    return out


def height_at(hs, x, y):
    cx, cy = int(x // 4096), int(y // 4096)
    h = hs[(cx, cy)]
    fx, fy = (x - cx * 4096) / 128, (y - cy * 4096) / 128
    c, r = min(int(fx), 31), min(int(fy), 31)
    tx, ty = fx - c, fy - r
    return (h[r][c] * (1 - tx) * (1 - ty) + h[r][c + 1] * tx * (1 - ty)
            + h[r + 1][c] * (1 - tx) * ty + h[r + 1][c + 1] * tx * ty)


if __name__ == "__main__":
    top = parse(open(r"C:\Steam\steamapps\common\Fallout 4\Data\DevilsInTheDetails.esp", "rb").read())
    hs = load_heights(top)
    print(len(hs), "cells; ground at the jump marker:", round(height_at(hs, -13650, -20430)), "(DESIGN: 2967)")
