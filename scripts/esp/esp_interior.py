"""The C-130's cabin into an interior cell, DevilsC130Cabin ("C-130"), and the jump out of it by
load doors.

  - a new interior CELL (lighting as vanilla SlocumsJoeHQOffice, which shows the sky)
  - every reference of the plane in Sicily (within 2,000 units of the hull, above z 20,000, but
    not the jump marker) moved into it, persistent ones to its persistent children, positions
    unchanged; the boarding door's hidden twin with them
  - DOOR DevilsC130JumpExit (script DevilsJumpExit) and two references of it, one in each
    doorway where the jump doors are, Persistent and Initially Disabled, teleporting to the jump
    marker; a hidden door on the ground under the marker, their way back
  - the jumpmaster: JumpExits (the same order as JumpDoors); CabinMarker and Hull gone

    python esp_interior.py in.esp out.esp
"""
import sys, struct
from esplib import *
import vmadlib
from esmrec import esm_body
from landh import load_heights, height_at

SICILY, SICILY_PERSIST = 0x0100293F, 0x01003E64
HULL, JM, JUMP_MARKER, NO_RIG = 0x010073B9, 0x010073B2, 0x010045FE, 0x01005534
HIDDEN_DOOR = 0x001A8458
LIGHTING_FROM = 0x001C9331             # SlocumsJoeHQOffice
JUMP_ACTI = 0x01005535                 # DevilsC130JumpDoor: header, OBND, MODT to copy

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
added = 0


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0, like=JUMP_ACTI):
    global added
    body = pack_subs(subs_)
    hdr = bytearray(recs[like].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    added += 1
    return Rec(bytes(hdr) + body)


def group(like, label, gtype, kids):
    hdr = bytearray(like.hdr)
    hdr[8:12] = label if isinstance(label, bytes) else struct.pack("<i", label)
    struct.pack_into("<i", hdr, 12, gtype)
    return Group(bytes(hdr), kids)


z = lambda s: s.encode() + b"\0"
obj = lambda f: struct.pack("<HhI", 0, -1, f)
any_group = [n for n in top if isinstance(n, Group)][0]

# The interior cell.
_, lb = esm_body("CELL", LIGHTING_FROM)
light = dict(sublist(lb))
cell_fid = new_fid()
cell_subs = [(b"EDID", z("DevilsC130Cabin")), (b"FULL", z("C-130")), (b"DATA", struct.pack("<H", 0x81))]
for t in (b"XCLL", b"LTMP", b"XCLW", b"XCIM", b"XCCM", b"XCAS"):
    if t in light:
        cell_subs.append((t, light[t]))
cell = new_rec("CELL", cell_fid, cell_subs)
persist, temp = group(any_group, cell_fid, 8, []), group(any_group, cell_fid, 9, [])
idx = cell_fid & 0xFFFFFF
sub = group(any_group, (idx // 10) % 10, 3, [cell, group(any_group, cell_fid, 6, [persist, temp])])
blk = group(any_group, idx % 10, 2, [sub])
cell_top = group(any_group, b"CELL", 0, [blk])
wrld_at = [i for i, n in enumerate(top) if isinstance(n, Group) and n.label == b"WRLD"][0]
top.insert(wrld_at, cell_top)

# Move the plane's references in.
hx, hy = struct.unpack_from("<2f", dict(sublist(recs[HULL].body()))[b"DATA"])
moving = []
for n, sib, i, par in walk(top):
    if isinstance(n, Rec) and n.type in ("REFR", "ACHR") and n.fid != JUMP_MARKER and any(
            p.gtype == 1 and struct.unpack("<I", p.label)[0] == SICILY for p in par):
        d = dict(sublist(n.body()))
        if b"DATA" in d:
            x, y, zz = struct.unpack_from("<3f", d[b"DATA"])
            if abs(x - hx) < 2000 and abs(y - hy) < 2000 and zz > 20000:
                moving.append((n, sib, par[-1].gtype == 8))
for n, sib, is_persist in moving:
    sib.remove(n)
    (persist if is_persist else temp).kids.append(n)

# The jump exits and their way back.
acti = dict(sublist(recs[JUMP_ACTI].body()))
vmad = vmadlib.build(6, 2, [["DevilsJumpExit", 0, [["NoRigMessage", 1, 1, obj(NO_RIG)]]]], b"")
exit_base = new_rec("DOOR", new_fid(), [
    (b"EDID", z("DevilsC130JumpExit")), (b"VMAD", vmad), (b"OBND", acti[b"OBND"]),
    (b"FULL", z("Paratroop Door")), (b"MODL", z("DevilsInTheDetails\\Aircraft\\C130_DoorExit.nif")),
    (b"MODT", acti[b"MODT"]), (b"FNAM", b"\x00")])
[n for n in top if isinstance(n, Group) and n.label == b"DOOR"][0].kids.append(exit_base)

jm_vmad = vmadlib.parse(dict(sublist(recs[JM].body()))[b"VMAD"])
jump_doors = [q for q in jm_vmad[2][0][2] if q[0] == "JumpDoors"][0][3]
door_fids = [struct.unpack_from("<I", jump_doors, 4 + 8 * k + 4)[0] for k in range(struct.unpack_from("<I", jump_doors)[0])]
mk = struct.unpack("<6f", dict(sublist(recs[JUMP_MARKER].body()))[b"DATA"][:24])
hs = load_heights(top)
back_fid = new_fid()
exits = []
xtel = lambda f, pos: struct.pack("<I6fII", f, *pos, 0, 0)
for dfid in door_fids:
    data = dict(sublist(recs[dfid].body()))[b"DATA"]
    e = new_rec("REFR", new_fid(), [(b"NAME", struct.pack("<I", exit_base.fid)),
                                    (b"XTEL", xtel(back_fid, mk)), (b"DATA", data)], flags=0x400 | 0x800)
    persist.kids.append(e)
    exits.append(e.fid)
ground = height_at(hs, mk[0], mk[1])
first = dict(sublist(recs[door_fids[0]].body()))[b"DATA"]
back = new_rec("REFR", back_fid, [(b"NAME", struct.pack("<I", HIDDEN_DOOR)),
                                  (b"XTEL", xtel(exits[0], struct.unpack("<6f", first[:24]))),
                                  (b"DATA", struct.pack("<6f", mk[0], mk[1], ground - 300, 0, 0, mk[5]))],
               flags=0x400)
sp = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 8 and struct.unpack("<I", n.label)[0] == SICILY_PERSIST][0]
sp.kids.append(back)

# The jumpmaster.
jm = recs[JM]
subs_ = sublist(jm.body())
for k, (t, v) in enumerate(subs_):
    if t == b"VMAD":
        vv, ff, sc, rest = vmadlib.parse(v)
        sc[0][2] = [q for q in sc[0][2] if q[0] not in ("CabinMarker", "Hull", "JumpExits")] + \
            [["JumpExits", 11, 1, vmadlib.obj_array(exits)]]
        subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
jm.set_body(pack_subs(subs_))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v)
                         for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"cell {cell_fid:08X}: {len(moving)} references moved in "
      f"({sum(1 for *_, p in moving if p)} persistent); exits {[f'{f:08X}' for f in exits]} "
      f"(doors {[f'{f:08X}' for f in door_fids]}); back door {back_fid:08X} at ground {ground:.0f}")
