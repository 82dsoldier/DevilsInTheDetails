"""Jump school's mock door, working (DESIGN.md, "Jump school's mock door"; the author,
2026-11-27): Sergeant Airborne takes Nate on, and Nate goes out the mock door in his rig.

  - The doorway's activator, DevilsMockDoorExit ("Mock Door", prompt "Step Out"), its model
    MockDoorExit.nif (make_mock_door.py: an invisible slab across the doorway, in the mock
    door's frame), its script DevilsMockDoor: "Stand in the door!", "GO!", out onto the sawdust,
    the critique. One reference, placed exactly as the mock door is.
  - Where Nate comes down: an XMarkerHeading on the sawdust 1.5 m out from the doorway,
    facing out (DevilsMockDoorLanding), persistent, for the script.
  - The quest, DevilsRecruiting ("All the Way"), goes on: Sergeant Airborne as alias 2; stage
    15, "Reported to jump school", with objective 15 "Go out the mock door" (its marker on
    him); stage 20, "Out the mock door", with objective 20 "Report to the 34-foot tower" (no
    marker: the tower isn't built yet).
  - His greetings, in the quest's greeting topic beside Brannock's, by the quest's stage:
    before Nate signs, after (taking him on: DevilsTopicStage sets stage 15, completes
    objective 10 and shows 15), while the door waits, and once Nate is through it.

Silent voice files for the new lines: out/voice/lines_jumpschool.json, for make_silent_voice.py.

    python esp_jumpschool.py in.esp out.esp
"""
import json, math, struct, sys
from pathlib import Path
from esplib import *

TEMPLATE = 0x01008B42
HANSCOM = 0x0100A22E
JUMP_DOOR_ACTI = 0x01005535            # DevilsC130JumpDoor: MODT and PNAM to copy
XMARKER_HEADING = 0x00000034
INFO = "C:/source/repos/BraggMap/out/hanscom/mockdoor.json"
VOICE = Path("C:/source/repos/BraggMap/out/voice/lines_jumpschool.json")
IRRITATED = 0x000C8670
GET_IS_ID, GET_STAGE_DONE, GET_IS_ALIAS_REF = 72, 59, 566
LOG_15 = ("Sergeant Airborne runs jump school's mock door, out in the sawdust on the ramp. Nobody gets "
          "on the bird without going out his door first, in a rig.")
OBJ_15 = "Go out the mock door"
LOG_20 = ("I went out Sergeant Airborne's mock door. He wasn't impressed, but he passed me. The 34-foot "
          "tower is next.")
OBJ_20 = "Report to the 34-foot tower"

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode("latin1")
by_edid = {edid(r): r for r in recs.values()}
assert "DevilsMockDoorExit" not in by_edid, "already done"
quest = by_edid["DevilsRecruiting"]
AIRBORNE = by_edid["DevilsSergeantAirborne"].fid
added = 0
z = lambda s: s.encode("cp1252") + b"\0"
fid4 = lambda f: struct.pack("<I", f)


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0):
    global added
    body = pack_subs(subs_)
    hdr = bytearray(recs[TEMPLATE].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    added += 1
    return Rec(bytes(hdr) + body)


def ws(t):
    t = t.encode()
    return struct.pack("<H", len(t)) + t


def prop_obj(name, fid):
    return ws(name) + struct.pack("<BB", 1, 1) + struct.pack("<HhI", 0, -1, fid)


def prop_int(name, v):
    return ws(name) + struct.pack("<BB", 3, 1) + struct.pack("<i", v)


def vmad(script, props):
    return struct.pack("<hhH", 6, 2, 1) + ws(script) + b"\x00" + struct.pack("<H", len(props)) + b"".join(props)


def ctda(func, p1=0, value=1.0, p2=0, op=0x00):
    """A condition: function(p1, p2) == value (op 0x00 ==), on the subject."""
    return (b"CTDA", struct.pack("<B3xfHHIIIIi", op, value, func, 0, p1, p2, 0, 0, -1))


def trda(emotion, n):
    return (b"TRDA", struct.pack("<II", emotion, n) + bytes.fromhex("00010000ffffffffffffffff"))


# --- Where -----------------------------------------------------------------------------------
info = json.load(open(INFO))
mock = [r for r in recs.values() if r.type == "REFR" and
        struct.unpack("<I", dict(sublist(r.body()))[b"NAME"])[0] == by_edid["DevilsMockDoor"].fid][0]
mock_data = dict(sublist(mock.body()))[b"DATA"]
oz = struct.unpack_from("<f", mock_data, 8)[0]
dx, dy, _ = info["spots"]["door_sill"]
lx, ly, lz = info["spots"]["landing"]
out_heading = math.atan2(lx - dx, ly - dy)

g1 = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 1 and struct.unpack("<I", n.label)[0] == HANSCOM][0]
pcell = [k for k in g1.kids if isinstance(k, Rec) and k.type == "CELL" and k.flags & 0x400][0]
g6 = [k for k in g1.kids if isinstance(k, Group) and k.gtype == 6 and struct.unpack("<I", k.label)[0] == pcell.fid][0]
g8 = [k for k in g6.kids if isinstance(k, Group) and k.gtype == 8][0]
landing = new_rec("REFR", new_fid(), [(b"EDID", z("DevilsMockDoorLanding")), (b"NAME", fid4(XMARKER_HEADING)),
                                      (b"DATA", struct.pack("<6f", lx, ly, oz + lz + 4, 0, 0, out_heading))], 0x400)
g8.kids.append(landing)

# --- The doorway's activator ------------------------------------------------------------------
jd = dict(sublist(recs[JUMP_DOOR_ACTI].body()))
acti = new_rec("ACTI", new_fid(), [
    (b"EDID", z("DevilsMockDoorExit")),
    (b"VMAD", vmad("DevilsMockDoor", [prop_obj("LandingMarker", landing.fid), prop_obj("MyQuest", quest.fid)])),
    (b"OBND", struct.pack("<6h", *info["exit_bounds"])), (b"FULL", z("Mock Door")),
    (b"MODL", z(info["exit_nif"])), (b"MODT", jd[b"MODT"]), (b"PNAM", jd[b"PNAM"]),
    (b"ATTX", z("Step Out")), (b"FNAM", b"\x00\x00")])
[n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"ACTI"][0].kids.append(acti)
exit_ref = new_rec("REFR", new_fid(), [(b"NAME", fid4(acti.fid)), (b"DATA", mock_data)])
mock_group = [g for n, sib, idx, par in walk(top) if n is mock for g in [par[-1]]][0]
mock_group.kids.append(exit_ref)

# --- The quest's new stages, objectives and alias ---------------------------------------------
subs_ = sublist(quest.body())
types = [t for t, _ in subs_]
after_stage = max(i for i, t in enumerate(types) if t == b"CNAM") + 1
stages = [(b"INDX", struct.pack("<HBB", 15, 0, 0)), (b"QSDT", b"\x00"), (b"NAM2", z("Reported to jump school")),
          (b"CNAM", z(LOG_15)),
          (b"INDX", struct.pack("<HBB", 20, 0, 0)), (b"QSDT", b"\x00"), (b"NAM2", z("Out the mock door")),
          (b"CNAM", z(LOG_20))]
subs_ = subs_[:after_stage] + stages + subs_[after_stage:]
types = [t for t, _ in subs_]
after_obj = max(i for i, t in enumerate(types) if t == b"QSTA") + 1
objs = [(b"QOBJ", struct.pack("<H", 15)), (b"FNAM", fid4(0)), (b"NNAM", z(OBJ_15)), (b"QSTA", struct.pack("<iII", 2, 0, 0)),
        (b"QOBJ", struct.pack("<H", 20)), (b"FNAM", fid4(0)), (b"NNAM", z(OBJ_20))]
subs_ = subs_[:after_obj] + objs + subs_[after_obj:]
subs_ = [(t, fid4(3) if t == b"ANAM" else v) for t, v in subs_]
subs_ += [(b"ALST", fid4(2)), (b"ALID", z("SergeantAirborne")), (b"FNAM", fid4(0x200)), (b"ALUA", fid4(AIRBORNE)),
          (b"VTCK", fid4(0)), (b"ALED", b"")]
quest.set_body(pack_subs(subs_))

# --- His greetings -----------------------------------------------------------------------------
lines = []


def greeting(responses, conds, script=None):
    fid = new_fid()
    s = []
    if script:
        s.append((b"VMAD", script))
    s.append((b"ENAM", struct.pack("<HH", 0, 0)))
    for n, text in enumerate(responses, 1):
        s += [trda(IRRITATED, n), (b"NAM1", z(text)), (b"NAM2", b"\0"), (b"NAM3", b"\0"), (b"NAM4", b"\0")]
        lines.append({"fid": fid & 0xFFFFFF, "n": n, "text": text, "voice": "airborne"})
    s += list(conds) + [(b"NAM0", b"\0"), (b"INAM", fid4(1))]
    return new_rec("INFO", fid, s)


me = ctda(GET_IS_ID, AIRBORNE, 1.0)
done = lambda stage, v: ctda(GET_STAGE_DONE, quest.fid, v, stage)
take_on = vmad("DevilsTopicStage", [prop_obj("MyQuest", quest.fid), prop_int("StageToSet", 15),
                                    prop_int("ObjectiveToComplete", 10), prop_int("ObjectiveToShow", 15)])
infos = [
    greeting(["You're not one of mine. Brannock's line is two doors down."], [me, done(10, 0.0)]),
    greeting(["You're Brannock's latest? He sends me the best the wasteland has to offer. God help us all.",
              "Get in your rig, get up those steps and into my door. Move like you've got somewhere to be."],
             [me, done(10, 1.0), done(15, 0.0)], take_on),
    greeting(["That door's not going to jump itself, recruit. Rig on, up the steps, and into my door."],
             [me, done(15, 1.0), done(20, 0.0)]),
    greeting(["Tower's next, recruit. My door's open if you want to go again."], [me, done(20, 1.0)]),
]
qchildren = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 10
             and struct.unpack("<I", n.label)[0] == quest.fid][0]
gree = [k for k in qchildren.kids if isinstance(k, Rec) and k.type == "DIAL"
        and dict(sublist(k.body())).get(b"SNAM") == b"GREE"]
assert len(gree) == 1, len(gree)
gree = gree[0]
ginfos = [k for k in qchildren.kids if isinstance(k, Group) and k.gtype == 7
          and struct.unpack("<I", k.label)[0] == gree.fid][0]
ginfos.kids += infos
gree.set_body(pack_subs([(t, struct.pack("<I", len(ginfos.kids)) if t == b"TIFC" else v)
                         for t, v in sublist(gree.body())]))

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
VOICE.write_text(json.dumps({"voice_types": {"airborne": ["MaleRough"]}, "lines": lines}, indent=1))
print(f"activator {acti.fid:08X} (ref {exit_ref.fid:08X}), landing {landing.fid:08X} at {lx:.0f}, {ly:.0f}, "
      f"{oz + lz + 4:.0f}; quest {quest.fid:08X}: stages 15, 20, objectives 15, 20, alias 2; "
      f"{len(infos)} greetings ({len(lines)} lines)")
