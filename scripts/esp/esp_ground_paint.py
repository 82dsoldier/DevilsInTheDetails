"""Hanscom's ground painted with vanilla's landscape textures (out/hanscom/ground_paint.npz, from
scripts/make_hanscom_ground.py): grass, lawns, weeds, forest floor, marsh, dirt, and the
streets' and parking lots' asphalt. Replaces whatever layers the terrain had (esp_road_paint.py's
asphalt among them: the asphalt is in ground_paint too). Safe to run again.

Per quadrant of each cell's terrain (LAND), as vanilla's are: a base texture (BTXT, the class
with the most ground there), then a layer (ATXT) and its opacities (VTXT) for each other class
present, bottom to top. A layer's opacity is its weight over what the layers above it leave
showing, so each class shows by its weight. At most MAX_LAYERS layers (vanilla goes to 9, mostly
4 to 6); past that, the least of them go to the base. The filler ring's cells get the open
ground's grass as their base, no layers.

    python esp_ground_paint.py in.esp out.esp
"""
import sys, struct, json
import numpy as np
from esplib import *

WORLD = 0x0100A22E
OUT = "C:/source/repos/BraggMap/out/hanscom/"
MAX_LAYERS = 6
MIN_W = 3 / 255                       # a class shows in a quadrant past this anywhere in it

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
meta = json.load(open(OUT + "heightmap.json"))
gp = np.load(OUT + "ground_paint.npz")
ltex, weights = gp["ltex"], gp["weights"].astype(np.float32) / 255
ncls = len(ltex)
asphalt = ncls - 1
cx_n, cy_n = meta["cells"]
cell_x0, cell_y1 = -(cx_n // 2), cy_n - cy_n // 2 - 1
assert weights.shape[1:] == (cy_n * 32 + 1, cx_n * 32 + 1), weights.shape

cells, children = {}, {}
for n, sib, idx, par in walk(top):
    if isinstance(n, Rec) and n.type == "CELL" and any(p.gtype == 1 and struct.unpack("<I", p.label)[0] == WORLD for p in par):
        d = dict(sublist(n.body()))
        if b"XCLC" in d and not n.flags & 0x400:
            cells[n.fid] = struct.unpack_from("<ii", d[b"XCLC"])
    if isinstance(n, Group) and n.gtype == 6:
        children[struct.unpack("<I", n.label)[0]] = n

btxt = lambda tex, q: (b"BTXT", struct.pack("<IBBh", int(tex), q, 0, -1))
painted = ring = layers_total = dropped = 0
most = 0
for fid, (cx, cy) in cells.items():
    lands = [k for t in children.get(fid, Group(bytes(24), [])).kids if isinstance(t, Group) and t.gtype == 9
             for k in t.kids if isinstance(k, Rec) and k.type == "LAND"]
    if not lands:
        continue
    land = lands[0]
    subs_ = [(t, v) for t, v in sublist(land.body()) if t not in (b"BTXT", b"ATXT", b"VTXT")]
    tex = []
    if not (cell_x0 <= cx < cell_x0 + cx_n and cell_y1 - cy_n < cy <= cell_y1):
        tex = [btxt(ltex[0], q) for q in range(4)]          # the filler ring
        ring += 1
    else:
        r0 = (cell_y1 - cy) * 32 + 32
        c0 = (cx - cell_x0) * 32
        w = weights[:, r0 - np.arange(33)][:, :, c0:c0 + 33]          # row 0 = the south edge
        for q in range(4):
            qr, qc = (q >> 1) * 16, (q & 1) * 16
            wq = w[:, qr:qr + 17, qc:qc + 17].reshape(ncls, -1)
            present = [c for c in range(ncls) if wq[c].max() > MIN_W]
            base = max(present, key=lambda c: wq[c].sum())
            lay = [c for c in present if c != base]
            while len(lay) > MAX_LAYERS:                   # the least goes (never the asphalt)
                least = min((c for c in lay if c != asphalt), key=lambda c: wq[c].sum())
                lay.remove(least)
                dropped += 1
            tex.append(btxt(ltex[base], q))
            above = np.zeros(wq.shape[1], np.float32)        # the weight of the layers above
            alphas = {}
            for c in reversed(lay):
                alphas[c] = np.clip(wq[c] / np.maximum(1 - above, 1e-6), 0, 1)
                above += wq[c]
            for k, c in enumerate(lay):
                idx = np.flatnonzero(alphas[c] > MIN_W)
                if not len(idx):
                    continue
                tex.append((b"ATXT", struct.pack("<IBBh", int(ltex[c]), q, 0, k)))
                tex.append((b"VTXT", b"".join(struct.pack("<HHf", int(i), 0, float(alphas[c][i])) for i in idx)))
                layers_total += 1
            most = max(most, len(lay))
        painted += 1
    subs_ = [(t, struct.pack("<I", struct.unpack("<I", v)[0] | 0x4) if t == b"DATA" else v) for t, v in subs_]
    at_ = max(i for i, (t, _) in enumerate(subs_) if t in (b"VNML", b"VHGT", b"VCLR")) + 1
    land.set_body(pack_subs(subs_[:at_] + tex + subs_[at_:]))

open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"{painted} map cells painted ({layers_total} layers, at most {most} in a quadrant, "
      f"{dropped} dropped to the cap); {ring} filler cells given the grass")
