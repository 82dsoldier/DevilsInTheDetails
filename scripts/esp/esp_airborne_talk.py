"""Sergeant Airborne's talk as a conversation, as Brannock's is (the author, 2026-11-27: "never
could talk to him"). His greetings were bare lines, with no scene after them: the game shows those
only with general subtitles on, and their voice files are silent, so talking to him showed
nothing (and the first one still moved the quest on when it ended).

Now his greetings start a scene with a player-dialogue action, so they come up in dialogue, with
the dialogue camera and dialogue subtitles. It lives in its own quest, DevilsJumpSchoolTalk
(start-game enabled, no name, alias 0 = him), not in "All the Way": an alias added to a quest
that's already running stays empty in saves made after it started, and a scene needs its actor's
alias filled. "All the Way" keeps its stages and objectives; his greetings still set them.

  Greetings (moved from DevilsRecruiting's greeting topic):
    not signed      "You're not one of mine..." (no scene: nothing to say to a stranger)
    taking him on   "You're Brannock's latest?..." (sets stage 15), then the scene
    door waiting    "That door's not going to jump itself...", then the scene
    through it      "Tower's next, recruit...", then the scene
  DevilsAirborneTalk: I'm ready / What do I do? / Why a mock door? / Later. The two questions
  loop back to the choices.

Writes the quest's SEQ entry beside DevilsRecruiting's (out/voice/mod/SEQ/DevilsInTheDetails.seq)
and the new lines' silent voice list (out/voice/lines_airborne_talk.json).

    python esp_airborne_talk.py in.esp out.esp
"""
import json, struct, sys
from pathlib import Path
from esplib import *

TEMPLATE = 0x01008B42
NEUTRAL, IRRITATED = 0x000D755D, 0x000C8670
GET_IS_ID, GET_IS_ALIAS_REF = 72, 566
PRIORITY = 60
VOICE = Path("C:/source/repos/BraggMap/out/voice/lines_airborne_talk.json")
SEQ = Path("C:/source/repos/BraggMap/out/voice/mod/SEQ/DevilsInTheDetails.seq")

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode("latin1")
by_edid = {edid(r): r for r in recs.values()}
assert "DevilsJumpSchoolTalk" not in by_edid, "already done"
recruiting = by_edid["DevilsRecruiting"]
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


def new_group(label, gtype):
    global added
    hdr = bytearray(24)
    hdr[0:4] = b"GRUP"
    hdr[8:12] = label if isinstance(label, bytes) else struct.pack("<I", label)
    struct.pack_into("<i", hdr, 12, gtype)
    added += 1
    return Group(bytes(hdr), [])


def ctda(func, p1=0, value=1.0, op=0x00):
    return (b"CTDA", struct.pack("<B3xfHHIIIIi", op, value, func, 0, p1, 0, 0, 0, -1))


def trda(emotion, n):
    return (b"TRDA", struct.pack("<II", emotion, n) + bytes.fromhex("00010000ffffffffffffffff"))


lines = []


def info(responses, emotion, voice, conds=(), prompt=None, scene=None):
    fid = new_fid()
    s = [(b"ENAM", struct.pack("<HH", 0, 0))]
    for n, text in enumerate(responses, 1):
        s += [trda(emotion, n), (b"NAM1", z(text)), (b"NAM2", b"\0"), (b"NAM3", b"\0"), (b"NAM4", b"\0")]
        lines.append({"fid": fid & 0xFFFFFF, "n": n, "text": text, "voice": voice})
    s += list(conds)
    if prompt:
        s.append((b"RNAM", z(prompt)))
    if scene:
        s += [(b"TSCE", fid4(scene)), (b"NAM0", z("Loop 1"))]
    else:
        s.append((b"NAM0", b"\0"))
    s.append((b"INAM", fid4(1)))
    return new_rec("INFO", fid, s)


quest_fid = new_fid()
children = new_group(quest_fid, 10)


def topic(infos):
    fid = new_fid()
    dial = new_rec("DIAL", fid, [(b"PNAM", struct.pack("<f", 50.0)), (b"QNAM", fid4(quest_fid)),
                                 (b"DATA", bytes.fromhex("00021000")), (b"SNAM", b"SCEN"),
                                 (b"TIFC", struct.pack("<I", len(infos)))])
    g = new_group(fid, 7)
    g.kids = list(infos)
    children.kids += [dial, g]
    return fid


def scene(fid, name, choices):
    """As esp_recruit_dialogue.py's: one phase, the speaker (alias 0), one player-dialogue action."""
    t = lambda k, i: fid4(choices[k][i]) if k in choices else fid4(0)
    s = [(b"EDID", z(name)), (b"FNAM", fid4(0x24)), (b"HNAM", b""), (b"NAM0", z("Loop 1")), (b"NEXT", b""),
         (b"NEXT", b""), (b"WNAM", fid4(0x1DB)), (b"HNAM", b""), (b"ALID", fid4(0)), (b"LNAM", fid4(0)),
         (b"DNAM", fid4(0x0A)), (b"ANAM", struct.pack("<H", 3)), (b"NAM0", b"\0"), (b"ALID", fid4(0)),
         (b"INAM", fid4(1)), (b"FNAM", fid4(0x228000)), (b"SNAM", fid4(0)), (b"ENAM", fid4(0)),
         (b"PTOP", t("pos", 0)), (b"NTOP", t("neg", 0)), (b"NETO", t("neu", 0)), (b"QTOP", t("que", 0)),
         (b"NPOT", t("pos", 1)), (b"NNGT", t("neg", 1)), (b"NNUT", t("neu", 1)), (b"NQUT", t("que", 1)),
         (b"DTGT", fid4(0)), (b"ANAM", b""), (b"PNAM", fid4(quest_fid)), (b"INAM", fid4(1)),
         (b"VNAM", struct.pack("<4I", 3, 3, 3, 3)), (b"XNAM", fid4(0))]
    children.kids.append(new_rec("SCEN", fid, s))


# The scene.
talk = new_fid()
him = [ctda(GET_IS_ALIAS_REF, 0, 1.0)]
P = "player"
pos = topic([info(["I'm ready."], NEUTRAL, P, prompt="I'm ready.")])
pos_a = topic([info(["Then why are you still talking to me? Rig on, up the steps, into my door."], IRRITATED,
                    "airborne", him)])
neu = topic([info(["What do I do?"], NEUTRAL, P, prompt="What do I do?")])
neu_a = topic([info(["When I say \"Stand in the door,\" you stand in my door. When I say \"GO,\" you go. Hard exit, "
                     "chin on your chest, hands on your reserve, and you count. Four thousand. Out loud."],
                    IRRITATED, "airborne", him, scene=talk)])
que = topic([info(["Why a mock door?"], NEUTRAL, P, prompt="Why a mock door?")])
que_a = topic([info(["Because the first time you see an open door at twelve hundred feet, I want your feet to "
                     "already know what to do. Your brain's going to be no use at all."], IRRITATED, "airborne",
                    him, scene=talk)])
neg = topic([info(["Later."], NEUTRAL, P, prompt="Later.")])
neg_a = topic([info(["Later's what they carve on your headstone, recruit."], IRRITATED, "airborne", him)])
scene(talk, "DevilsAirborneTalk", {"pos": (pos, pos_a), "neu": (neu, neu_a), "que": (que, que_a),
                                   "neg": (neg, neg_a)})

# His greetings: out of DevilsRecruiting's greeting topic, into a greeting topic of this quest,
# the three after Nate signs now starting the scene.
rchildren = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 10
             and struct.unpack("<I", n.label)[0] == recruiting.fid][0]
rgree = [k for k in rchildren.kids if isinstance(k, Rec) and k.type == "DIAL"
         and dict(sublist(k.body())).get(b"SNAM") == b"GREE"][0]
rinfos = [k for k in rchildren.kids if isinstance(k, Group) and k.gtype == 7
          and struct.unpack("<I", k.label)[0] == rgree.fid][0]
is_his = ctda(GET_IS_ID, AIRBORNE, 1.0)[1]
mine = [r for r in rinfos.kids if is_his in [v for t, v in sublist(r.body()) if t == b"CTDA"]]
assert len(mine) == 4, len(mine)
rinfos.kids = [r for r in rinfos.kids if r not in mine]
rgree.set_body(pack_subs([(t, struct.pack("<I", len(rinfos.kids)) if t == b"TIFC" else v)
                          for t, v in sublist(rgree.body())]))
for r in mine:
    s = sublist(r.body())
    first = dict(s).get(b"NAM1", b"")
    if not first.startswith(b"You're not one of mine"):
        s = [x for x in s if x[0] != b"NAM0"]
        at = [i for i, (t, _) in enumerate(s) if t == b"INAM"][0]
        s = s[:at] + [(b"TSCE", fid4(talk)), (b"NAM0", z("Loop 1"))] + s[at:]
    r.set_body(pack_subs(s))
gree_fid = new_fid()
gree = new_rec("DIAL", gree_fid, [(b"PNAM", struct.pack("<f", 50.0)), (b"QNAM", fid4(quest_fid)),
                                  (b"DATA", bytes.fromhex("00077400")), (b"SNAM", b"GREE"),
                                  (b"TIFC", struct.pack("<I", len(mine)))])
ggroup = new_group(gree_fid, 7)
ggroup.kids = mine
children.kids += [gree, ggroup]

# The quest: as DevilsRecruiting's header (start-game enabled), no name, him as alias 0.
rd = dict(sublist(recruiting.body()))
quest = new_rec("QUST", quest_fid, [
    (b"EDID", z("DevilsJumpSchoolTalk")),
    (b"DNAM", rd[b"DNAM"]), (b"FLTR", z("DevilsInTheDetails\\")), (b"NEXT", b""),
    (b"ANAM", fid4(1)),
    (b"ALST", fid4(0)), (b"ALID", z("SergeantAirborne")), (b"FNAM", fid4(0x200)), (b"ALUA", fid4(AIRBORNE)),
    (b"VTCK", fid4(0)), (b"ALED", b""),
])
qtop = [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"QUST"][0]
qtop.kids += [quest, children]

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
VOICE.write_text(json.dumps({"voice_types": {"airborne": ["MaleRough"],
                                             "player": ["PlayerVoiceMale01", "PlayerVoiceFemale01"]},
                             "lines": lines}, indent=1))
SEQ.parent.mkdir(parents=True, exist_ok=True)
SEQ.write_bytes(struct.pack("<II", recruiting.fid, quest_fid))
print(f"DevilsJumpSchoolTalk {quest_fid:08X}, scene {talk:08X}, greetings moved: {len(mine)}; "
      f"{len(lines)} new lines; {added} records and groups")
