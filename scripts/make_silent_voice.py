"""Silent stand-in voice files for the plugin's dialogue (out/voice/lines*.json, from
scripts/esp/esp_recruit_dialogue.py and esp_jumpschool.py): Fallout 4 wants a voice file behind every line, or its
subtitle flashes past. Each is near-silence as long as the line takes to read, WORDS_PER_SEC,
never under MIN_SEC, in the game's own format (.fuz: the audio as xWMA, no lip sync).

    python scripts/make_silent_voice.py [--install "<Fallout 4>/Data"]

Needs the Creation Kit's xWMAEncode ("<Fallout 4>/Tools/Audio/xwmaencode.exe"). Writes
out/voice/mod/Sound/Voice/DevilsInTheDetails.esp/<voice type>/<line's ID>_<response>.fuz, and
installs those and the quest's SEQ file. Real recordings replace them later, same names.
"""
import argparse
import json
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import out_dir                                # noqa: E402

GAME = Path(r"C:\Steam\steamapps\common\Fallout 4")
XWMA = GAME / "Tools" / "Audio" / "xwmaencode.exe"
RATE = 44100
WORDS_PER_SEC = 2.6
MIN_SEC = 1.8
PLUGIN = "DevilsInTheDetails.esp"


def fuz(seconds, tmp):
    """A .fuz of near-silence (a hiss far under hearing: xWMA won't take pure zeros)."""
    n = int(seconds * RATE)
    a = (np.random.default_rng(1).normal(0, 1.5, n)).astype("<i2")
    wav, xwm = tmp / "line.wav", tmp / "line.xwm"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(a.tobytes())
    subprocess.run([str(XWMA), str(wav), str(xwm)], check=True, capture_output=True)
    return b"FUZE" + struct.pack("<II", 1, 0) + xwm.read_bytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    out = out_dir("voice")
    # lines.json (Brannock's, esp_recruit_dialogue.py) and any lines_*.json (esp_jumpschool.py, ...)
    spec = {"voice_types": {}, "lines": []}
    for f in sorted(out.glob("lines*.json")):
        part = json.loads(f.read_text())
        spec["voice_types"].update(part["voice_types"])
        spec["lines"] += part["lines"]
    mod = out / "mod"
    tmp = out / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    files = []
    for line in spec["lines"]:
        secs = max(MIN_SEC, len(line["text"].split()) / WORDS_PER_SEC + 0.6)
        data = fuz(secs, tmp)
        for vt in spec["voice_types"][line["voice"]]:
            f = mod / "Sound" / "Voice" / PLUGIN / vt / f"{line['fid']:08X}_{line['n']}.fuz"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            files.append(f)
    seq = mod / "SEQ" / "DevilsInTheDetails.seq"
    if seq.exists():
        files.append(seq)
    print(f"{len(files)} files ({len(spec['lines'])} lines)")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        print(f"  installed under {data}")


if __name__ == "__main__":
    main()
