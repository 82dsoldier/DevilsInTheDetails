"""SSG Brannock's pitch (DESIGN.md, "His pitch"): a short exchange, nothing given away until Nate
signs, then anything. Built as vanilla builds a small conversation (modelled on MS02Donny):

  DevilsRecruiting (QUST)  start-game enabled; alias 0 "Brannock" (his unique base)
    Greeting (GREE)        before he's signed: one of two, at random, then the Before scene;
                           after: "Back again... sir?" / "Corporal. What do you need?", then After
    DevilsRecruitBefore    one player-dialogue action: sign up / what is this place / who are you
                           / never mind. The two questions loop back to the choices; signing up
                           goes on to the Prior scene.
    DevilsRecruitPrior     "I was an officer." / "Enlisted." His answer sets DevilsNateRank
                           (vanilla's DefaultTopicInfoSetGlobal on the line's end): 1 officer,
                           2 enlisted (a corporal). 0 is not signed.
    DevilsRecruitAfter     what happens now / where are we going / what's the catch / that's all.

Every line is silent for now: scripts/make_silent_voice.py writes a quiet voice file for each,
as long as the line takes to read (out/voice/lines.json, from here), so the subtitles stay up.
Also writes the start-game quest's SEQ file (Data\\SEQ\\DevilsInTheDetails.seq), which a
start-game-enabled quest with dialogue needs.

    python esp_recruit_dialogue.py in.esp out.esp
"""
import sys, struct, json
from pathlib import Path
from esplib import *

TEMPLATE = 0x01008B42
SET_GLOBAL = "DefaultTopicInfoSetGlobal"
NEUTRAL, IRRITATED, AMUSED = 0x000D755D, 0x000C8670, 0x000FA84D
GET_IS_ID, GET_GLOBAL, GET_IS_ALIAS_REF = 72, 74, 566
PRIORITY = 60
OUT = Path("C:/source/repos/BraggMap/out/voice")
SEQ = Path("C:/source/repos/BraggMap/out/voice/mod/SEQ/DevilsInTheDetails.seq")

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
th = sublist(tes4.body())
ver, nrec, nxt = struct.unpack("<fiI", dict(th)[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}
edid = lambda r: dict(sublist(r.body())).get(b"EDID", b"").rstrip(b"\0").decode()
by_edid = {edid(r): r for r in recs.values()}
assert "DevilsRecruiting" not in by_edid, "already done"
BRANNOCK = by_edid["DevilsBrannock"].fid
added = 0


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


z = lambda s: s.encode("cp1252") + b"\0"
fid4 = lambda f: struct.pack("<I", f)


def ctda(func, p1=0, value=1.0, op=0x00):
    """A condition: function(p1) == value (op: 0x00 ==, 0x20 !=, ...), on the subject."""
    return (b"CTDA", struct.pack("<B3xfHHIIIIi", op, value, func, 0, p1, 0, 0, 0, -1))


def trda(emotion, n):
    return (b"TRDA", struct.pack("<II", emotion, n) + bytes.fromhex("00010000ffffffffffffffff"))


lines = []          # for the silent voice files


def info(responses, emotion, voice, conds=(), prompt=None, scene=None, flags=0, vmad=None):
    """A line: its responses (one or more), its conditions, the player's prompt, the scene it
    starts (at its phase "Loop 1")."""
    fid = new_fid()
    s = []
    if vmad:
        s.append((b"VMAD", vmad))
    s.append((b"ENAM", struct.pack("<HH", flags, 0)))
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


def set_global(glob, value):
    """VMAD: vanilla's DefaultTopicInfoSetGlobal, the global set to value when the line ends."""
    def ws(t): t = t.encode(); return struct.pack("<H", len(t)) + t
    props = (ws("SetGlobalOnEnd") + struct.pack("<BB", 1, 1) + struct.pack("<HhI", 0, -1, glob)
             + ws("OnEndValue") + struct.pack("<BB", 4, 1) + struct.pack("<f", value))
    return struct.pack("<hhH", 6, 2, 1) + ws(SET_GLOBAL) + b"\x00" + struct.pack("<H", 2) + props


quest_fid = new_fid()
children = new_group(quest_fid, 10)


def topic(kind, infos):
    """A topic (DIAL) in the quest and its lines: kind "scene" (a player choice or the answer to
    one) or "greeting"."""
    fid = new_fid()
    data, snam = (bytes.fromhex("00021000"), b"SCEN") if kind == "scene" else (bytes.fromhex("00077400"), b"GREE")
    dial = new_rec("DIAL", fid, [(b"PNAM", struct.pack("<f", 50.0)), (b"QNAM", fid4(quest_fid)), (b"DATA", data),
                                 (b"SNAM", snam), (b"TIFC", struct.pack("<I", len(infos)))])
    g = new_group(fid, 7)
    g.kids = list(infos)
    children.kids += [dial, g]
    return fid


def scene(fid, name, choices):
    """A scene: one phase ("Loop 1"), Brannock (alias 0), and one player-dialogue action:
    choices = {slot: (player topic, his answer)}, slots "pos", "neg", "neu", "que"."""
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


# The global: 0 not signed, 1 officer, 2 enlisted (a corporal).
rank = new_rec("GLOB", new_fid(), [(b"EDID", z("DevilsNateRank")), (b"FNAM", b"f"), (b"FLTV", struct.pack("<f", 0.0))])
[n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == b"GLOB"][0].kids.append(rank)
before_scn, prior_scn, after_scn = new_fid(), new_fid(), new_fid()
him = [ctda(GET_IS_ALIAS_REF, 0, 1.0)]
P = "player"

# Before he's signed.
pos = topic("scene", [info(["I want to sign up."], NEUTRAL, P, prompt="I want to sign up.")])
pos_a = topic("scene", [info(["Course you do. Everybody does, till the first jump. Prior service?"], IRRITATED,
                             "brannock", him, scene=prior_scn)])
neu = topic("scene", [info(["What is this place?"], NEUTRAL, P, prompt="What is this place?")])
neu_a = topic("scene", [info(["Recruiting station. I recruit. You station. Simple."], IRRITATED, "brannock", him,
                             scene=before_scn)])
que = topic("scene", [info(["Who are you people?"], NEUTRAL, P, prompt="Who are you people?")])
que_a = topic("scene", [info(["The people standing between this field and every raider east of Concord. "
                              "Sign, and you'll find out the rest."], IRRITATED, "brannock", him, scene=before_scn)])
neg = topic("scene", [info(["Never mind."], NEUTRAL, P, prompt="Never mind.")])
neg_a = topic("scene", [info(["Then get out of my line."], IRRITATED, "brannock", him)])
scene(before_scn, "DevilsRecruitBefore", {"pos": (pos, pos_a), "neu": (neu, neu_a), "que": (que, que_a),
                                          "neg": (neg, neg_a)})

# Prior service: officer or enlisted, the player's choice.
off = topic("scene", [info(["I was an officer."], NEUTRAL, P, prompt="I was an officer.")])
off_a = topic("scene", [info(["An officer. Course you were. Two hundred years on ice and you still expect a salute.",
                              "Welcome to the Devils... sir."], AMUSED, "brannock", him,
                             vmad=set_global(rank.fid, 1.0))])
enl = topic("scene", [info(["Enlisted."], NEUTRAL, P, prompt="Enlisted.")])
enl_a = topic("scene", [info(["Then you know which end of the rifle goes bang. Prior service don't start at "
                              "private. You'll come in as a corporal. Don't make me regret it."], IRRITATED,
                             "brannock", him, vmad=set_global(rank.fid, 2.0))])
scene(prior_scn, "DevilsRecruitPrior", {"pos": (off, off_a), "neu": (enl, enl_a)})

# After: anything.
a_pos = topic("scene", [info(["So what happens now?"], NEUTRAL, P, prompt="So what happens now?")])
a_pos_a = topic("scene", [info(["Now you learn to fall out of an airplane. Jump school's two doors down. Mock door "
                                "first, then the bird."], IRRITATED, "brannock", him, scene=after_scn)])
a_neu = topic("scene", [info(["Where are we going?"], NEUTRAL, P, prompt="Where are we going?")])
a_neu_a = topic("scene", [info(["Bragg. North Carolina. Home of the Airborne. Where else?"], IRRITATED, "brannock",
                               him, scene=after_scn)])
a_que = topic("scene", [info(["What's the catch?"], NEUTRAL, P, prompt="What's the catch?")])
a_que_a = topic("scene", [info(["The catch is the bird's grounded and every raider on the road knows when the "
                                "caravans run. Welcome to the Devils."], IRRITATED, "brannock", him,
                               scene=after_scn)])
a_neg = topic("scene", [info(["That's all."], NEUTRAL, P, prompt="That's all.")])
a_neg_a = topic("scene", [info(["Then get out of my line."], IRRITATED, "brannock", him)])
scene(after_scn, "DevilsRecruitAfter", {"pos": (a_pos, a_pos_a), "neu": (a_neu, a_neu_a), "que": (a_que, a_que_a),
                                        "neg": (a_neg, a_neg_a)})

# The greeting: which scene depends on DevilsNateRank.
me = ctda(GET_IS_ID, BRANNOCK, 1.0)
rank_is = lambda v: ctda(GET_GLOBAL, rank.fid, v)
topic("greeting", [
    info(["Line's right there. You gonna stand in it, or just admire it?"], IRRITATED, "brannock",
         [me, rank_is(0.0)], scene=before_scn, flags=0x02),
    info(["You lost, or you here to waste my time?"], IRRITATED, "brannock", [me, rank_is(0.0)],
         scene=before_scn, flags=0x02),
    info(["Back again... sir?"], AMUSED, "brannock", [me, rank_is(1.0)], scene=after_scn),
    info(["Corporal. What do you need?"], IRRITATED, "brannock", [me, rank_is(2.0)], scene=after_scn),
])

# The quest: start-game enabled, priority over the generic hellos, Brannock as alias 0.
quest = new_rec("QUST", quest_fid, [
    (b"EDID", z("DevilsRecruiting")),
    (b"DNAM", struct.pack("<HBB", 0x0111, PRIORITY, 0x80) + bytes.fromhex("0000000006000000")),
    (b"FLTR", z("DevilsInTheDetails\\")), (b"NEXT", b""),
    (b"ANAM", fid4(1)),
    (b"ALST", fid4(0)), (b"ALID", z("Brannock")), (b"FNAM", fid4(0x200)), (b"ALUA", fid4(BRANNOCK)),
    (b"VTCK", fid4(0)), (b"ALED", b""),
])
qgroup = new_group(b"QUST", 0)
qgroup.kids = [quest, children]
wrld_at = [i for i, n in enumerate(top) if isinstance(n, Group) and n.gtype == 0 and n.label == b"WRLD"][0]
assert not any(isinstance(n, Group) and n.gtype == 0 and n.label == b"QUST" for n in top)
top.insert(wrld_at + 1, qgroup)

tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v) for t, v in th]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "lines.json").write_text(json.dumps({"voice_types": {"brannock": ["MaleRough"],
                                                            "player": ["PlayerVoiceMale01", "PlayerVoiceFemale01"]},
                                            "lines": lines}, indent=1))
SEQ.parent.mkdir(parents=True, exist_ok=True)
SEQ.write_bytes(struct.pack("<I", quest_fid))
print(f"DevilsRecruiting {quest_fid:08X}, DevilsNateRank {rank.fid:08X}; {len(lines)} lines; scenes "
      f"{before_scn:08X} {prior_scn:08X} {after_scn:08X}; {added} records and groups")
