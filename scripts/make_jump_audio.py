"""Stand-in audio for the jumpmaster's commands, and the scene script timed to it.

    python scripts/make_jump_audio.py [--install "<Fallout 4>/Data"]

Until the jumpmaster is recorded for real, Windows text-to-speech (Microsoft David) says the
commands, and the stick's echo is a rough chorus of the same voice at a few pitches. The
commands come in three pieces, because the scene stops twice: for the player's sound-off
choice, and for the red light before the green.

  commands_1   "Ten minutes!" through "Sound off for equipment check!" and the OKs passed up
               the stick; then the player sounds off (a choice)
  commands_2   "Six minutes!" through "Stand in the door!"; then red light, a pause, green light
  commands_3   "GO!"

Writes to out/jump/:
  mod/Sound/FX/DevilsInTheDetails/Jump/commands_N.wav
  mod/Scripts/Source/User/DevilsJumpmaster.psc    the scene script, timings filled in
  tts/                                            the raw text-to-speech lines
"""
import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, out_dir                          # noqa: E402

RATE = 44100
GAP = 1.0           # seconds of quiet after each echo, before the next command
ECHO_GAP = 0.15     # the jumpmaster's line to the stick's echo

# (jumpmaster's command, echoed by the stick?, his hand signal). Until he's animated, the hand
# signal is shown with the line. The signals are from memory of FM 3-21.220; the author checks them.
PIECES = {
    "commands_1": [
        ("Ten minutes!", True, "hands out in front, fingers splayed"),
        ("Get ready!", True, "hands out in front, fingers together, tipped forward"),
        ("Outboard personnel, stand up!", True, "arms out, palms up, raised"),
        ("Inboard personnel, stand up!", True, "arms out, palms up, raised"),
        ("Hook up!", True, "arm overhead, finger crooked like a hook, pumping"),
        ("Check static lines!", True, "arm overhead, finger crooked like a hook, pumping (as Hook up)"),
        ("Check equipment!", True, "fingertips tapping his chest"),
        ("Sound off for equipment check!", True, "hands cupped behind his ears"),
    ],
    "commands_2": [
        ("Six minutes!", True, "six fingers up"),
        ("One minute!", True, "one finger up, the hand not on his static line"),
        ("Thirty seconds!", True, "thumb and forefinger held close together"),
        ("Drop zone coming up! Stand in the door!", False, "points the first jumper into the door"),
    ],
    "commands_3": [
        ("Go!", False, None),
    ],
}
SOUND_OFF = ["OK!", "OK!", "OK!"]   # passed forward up the stick, at the end of commands_1
# What the scene does as the stick echoes a command: a call into DevilsJumpmaster.psc.in.
ACTIONS = {
    "Outboard personnel, stand up!": "StandUp(True)",
    "Inboard personnel, stand up!": "StandUp(False)",
    "Hook up!": "HookUp()",
}
# The hand signals he's animated for (make_jm_signals.py): the jumpmaster's Idle property, played
# as he starts the line; the subtitle then drops the written signal.
SIGNALS = {
    "Ten minutes!": "SignalTenMinutes",
    "Get ready!": "SignalGetReady",
    "Outboard personnel, stand up!": "SignalStandUp",
    "Inboard personnel, stand up!": "SignalStandUp",
    "Hook up!": "SignalHookUp",
    "Check static lines!": "SignalHookUp",     # the same signal
    "Check equipment!": "SignalCheckEquipment",
    "Sound off for equipment check!": "SignalSoundOff",
    "Six minutes!": "SignalSixMinutes",
    "One minute!": "SignalOneMinute",
    "Thirty seconds!": "SignalThirtySeconds",
}
SIGNAL_LONGER = {"SignalSoundOff": 7.0}   # held through the stick's OKs (make_jm_signals.py)
SIGNAL_SECONDS = 3.0    # a signal's length (make_jm_signals.py: 2.8 s): the next command waits for it
SIGNAL_LEAD = 1.0       # his arm is going up (0.5 s, plus the game starting the idle) before he shouts

PS_TTS = r"""
Add-Type -AssemblyName System.Speech
$lines = Get-Content -Raw $args[0] | ConvertFrom-Json
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($l in $lines) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice('Microsoft David Desktop')
  $s.Rate = $l.rate
  $s.Volume = 100
  $s.SetOutputToWaveFile($l.path, $fmt)
  $s.Speak($l.text)
  $s.Dispose()
}
"""


def tts(lines, tts_dir):
    """{key: text} -> {key: float32 samples}, through Windows text-to-speech."""
    tts_dir.mkdir(parents=True, exist_ok=True)
    jobs = [{"text": t, "rate": 1, "path": str(tts_dir / f"{k}.wav")} for k, t in lines.items()]
    (tts_dir / "jobs.json").write_text(json.dumps(jobs))
    (tts_dir / "tts.ps1").write_text(PS_TTS)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(tts_dir / "tts.ps1"), str(tts_dir / "jobs.json")], check=True)
    out = {}
    for k in lines:
        with wave.open(str(tts_dir / f"{k}.wav")) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        nz = np.nonzero(np.abs(a) > 0.01)[0]          # trim the silence TTS leaves around it
        out[k] = a[nz[0]:nz[-1] + 1] if len(nz) else a
    return out


def repitch(a, factor):
    """Resample: higher factor, higher and quicker."""
    n = int(len(a) / factor)
    return np.interp(np.arange(n) * factor, np.arange(len(a)), a).astype(np.float32)


def chorus(a, seed):
    """A handful of jumpers shouting the same words, a little out of step."""
    rng = np.random.default_rng(seed)
    parts = []
    for f in (0.86, 0.93, 0.98, 1.04, 1.10):
        delay = int(rng.uniform(0, 0.09) * RATE)
        parts.append(np.concatenate([np.zeros(delay, np.float32), repitch(a, f) * rng.uniform(0.6, 1)]))
    n = max(len(p) for p in parts)
    mix = sum(np.pad(p, (0, n - len(p))) for p in parts)
    return (mix / np.max(np.abs(mix)) * 0.8).astype(np.float32)


def shout(a):
    """Louder and a little clipped, like a man shouting over four engines."""
    return (np.tanh(a / np.max(np.abs(a)) * 2.2) * 0.9).astype(np.float32)


def silence(sec):
    return np.zeros(int(sec * RATE), np.float32)


def write_wav(path, a):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())


def papyrus_piece(name, cues):
    """A function that plays one piece and shows each line as it's said."""
    lines = [f"Function Play_{name}()",
             f"\tInt id = {name}.Play(Self)"]
    t = 0.0
    for at, text, action in cues:          # (seconds, text or None, Papyrus call or None)
        if at > t:
            lines.append(f"\tUtility.Wait({at - t:.2f})")
            t = at
        if text:
            lines.append(f'\tDebug.Notification("{text}")')
        if action:
            lines.append(f"\t{action}")
    return lines, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    out = out_dir("jump")
    mod = out / "mod"
    texts = {}
    for piece, cmds in PIECES.items():
        for i, (text, _, _) in enumerate(cmds):
            texts[f"{piece}_{i}"] = text
    texts["ok"] = "OK!"
    voice = tts(texts, out / "tts")

    funcs, lengths, files = [], {}, []
    for n, (piece, cmds) in enumerate(PIECES.items()):
        audio, cues = [silence(0.3)], []
        t = 0.3
        for i, (text, echo, signal) in enumerate(cmds):
            line = shout(voice[f"{piece}_{i}"])
            start = t
            if text in SIGNALS:
                sig = SIGNALS[text]
                more = f", {SIGNAL_LONGER[sig]:.1f}" if sig in SIGNAL_LONGER else ""
                cues.append((t, None, f"Signal({sig}{more})"))
                audio.append(silence(SIGNAL_LEAD))
                t += SIGNAL_LEAD
                cues.append((t, f"Jumpmaster: {text}", None))
            else:
                cues.append((t, f"Jumpmaster ({signal}): {text}" if signal else f"Jumpmaster: {text}", None))
            audio.append(line)
            t += len(line) / RATE
            if text in ACTIONS:
                cues.append((t, None, ACTIONS[text]))
            if echo:
                audio.append(silence(ECHO_GAP))
                e = chorus(line, seed=n * 100 + i)
                audio.append(e * 0.7)
                t += ECHO_GAP + len(e) / RATE
            if text in SIGNALS and t < start + SIGNAL_SECONDS:     # his signal finishes first
                audio.append(silence(start + SIGNAL_SECONDS - t))
                t = start + SIGNAL_SECONDS
            if i < len(cmds) - 1 or piece == "commands_1":
                audio.append(silence(GAP))
                t += GAP
        if piece == "commands_1":           # the OKs come forward up the stick
            cues.append((t, "The stick: OK! OK! OK!", None))
            for k, _ in enumerate(SOUND_OFF):
                ok = shout(repitch(voice["ok"], (0.9, 1.0, 1.08)[k % 3])) * (0.45 + 0.15 * k)
                audio += [ok, silence(0.35)]
                t += len(ok) / RATE + 0.35
        audio.append(silence(0.3))
        a = np.concatenate(audio)
        wav = mod / "Sound" / "FX" / "DevilsInTheDetails" / "Jump" / f"{piece}.wav"
        write_wav(wav, a)
        files.append(wav)
        lengths[piece] = len(a) / RATE
        body, last = papyrus_piece(piece, cues)
        body += [f"\tUtility.Wait({max(0.0, lengths[piece] - last):.2f})", "EndFunction", ""]
        funcs += body
        print(f"{wav.relative_to(ROOT)}: {lengths[piece]:.1f} s, {len(cues)} lines")

    template = (ROOT / "scripts" / "papyrus" / "DevilsJumpmaster.psc.in").read_text()
    psc = template.replace("; @PIECES@", "\n".join(funcs).rstrip() + "\n")
    psc_path = mod / "Scripts" / "Source" / "User" / "DevilsJumpmaster.psc"
    psc_path.parent.mkdir(parents=True, exist_ok=True)
    psc_path.write_text(psc, newline="\r\n")
    (ROOT / "scripts" / "papyrus" / "DevilsJumpmaster.psc").write_text(psc, newline="\r\n")
    files.append(psc_path)
    print(f"{psc_path.relative_to(ROOT)} (and scripts/papyrus/DevilsJumpmaster.psc); "
          f"about {sum(lengths.values()):.0f} s of commands, plus the pauses")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
