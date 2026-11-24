"""SSG Brannock's beret and jump wings into the plugin (models from scripts/make_uniform.py): an
armor and its addon for each, made from the jump kit's (DevilsJumpKit) with their own model,
name and body slot, and both added to his outfit (DevilsBrannockOutfit).

  DevilsBeret      "Maroon Beret", slot 30 (hair top, as the vanilla caps), Uniform\\Beret.nif
  DevilsJumpWings  "Jump Wings", slot 55, Uniform\\Wings.nif

    python esp_uniform.py in.esp out.esp
"""
import sys, struct
from esplib import *

KIT_ARMO, KIT_ARMA = 0x01007407, 0x01007406
TEMPLATE = 0x01008B42
PIECES = [("DevilsBeret", "Maroon Beret", 30, r"DevilsInTheDetails\Uniform\Beret.nif"),
          ("DevilsJumpWings", "Jump Wings", 55, r"DevilsInTheDetails\Uniform\Wings.nif")]

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode()
by_edid = {edid(r): r for r in recs.values()}
assert "DevilsBeret" not in by_edid, "already done"


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


group = lambda label: [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == label][0]
added = []
for name, full, slot, model in PIECES:
    bod2 = struct.pack("<I", 1 << (slot - 30))
    arma_fid, armo_fid = new_fid(), new_fid()
    arma = []
    for t, v in sublist(recs[KIT_ARMA].body()):
        if t == b"EDID":
            v = f"AA{name}\0".encode()
        elif t == b"BOD2":
            v = bod2
        elif t in (b"MOD2", b"MOD3"):
            v = model.encode() + b"\0"
        arma.append((t, v))
    armo = []
    for t, v in sublist(recs[KIT_ARMO].body()):
        if t == b"EDID":
            v = f"{name}\0".encode()
        elif t == b"FULL":
            v = f"{full}\0".encode()
        elif t == b"BOD2":
            v = bod2
        elif t == b"MODL":
            v = struct.pack("<I", arma_fid)
        armo.append((t, v))
    group(b"ARMA").kids.append(new_rec("ARMA", arma_fid, arma))
    group(b"ARMO").kids.append(new_rec("ARMO", armo_fid, armo))
    added.append(armo_fid)

outfit = by_edid["DevilsBrannockOutfit"]
outfit.set_body(pack_subs([(t, v + b"".join(struct.pack("<I", f) for f in added) if t == b"INAM" else v)
                           for t, v in sublist(outfit.body())]))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + 2 * len(PIECES), nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print("added", ", ".join(f"{f:08X}" for f in added), "to", f"{outfit.fid:08X}")
