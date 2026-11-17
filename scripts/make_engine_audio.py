"""Stand-in engine sound for the C-130 cabin: four Allison T56 turboprops, heard from inside.

    python scripts/make_engine_audio.py [--install "<Fallout 4>/Data"]

Made from scratch (no recordings): each propeller is a tone at its blade-passing rate (4 blades
at 1,020 rpm, 68 Hz) with harmonics, the four slightly out of sync so they beat against each
other, the C-130's throb; a faint turbine whine; and a low roar of noise that grows with power.
The T56 turns at a constant speed in flight, so takeoff is mostly the blades biting (power), with
the rpm coming up from ground idle first.

  engines_idle.wav      loop: ground idle, boarding and taxiing
  engines_takeoff.wav   one piece, TAKEOFF_LEN s: idle, run-up against the brakes, the roll,
                        liftoff, the climb, settling to cruise power. Starts like the idle loop
                        and ends like the cruise loop, so the scene crossfades between them.
  engines_cruise.wav    loop: in flight

The loops are seamless: every tone fits a whole number of cycles in LOOP_LEN, and the noise is
made periodic. The jumpmaster's script (DevilsJumpmaster.psc.in) plays them; its takeoff
timings follow the constants below.

Writes to out/engines/mod/Sound/FX/DevilsInTheDetails/C130/.
"""
import argparse
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import ROOT, out_dir                          # noqa: E402

RATE = 44100
LOOP_LEN = 24.0
BLADE_HZ = 4 * 1020 / 60            # blade-passing rate at 100% rpm
IDLE_RPM = 0.72                     # low-speed ground idle
DETUNE = (0.0, 0.0045, -0.003, 0.0075)   # each prop a little off the others: the throb
PAN = (-0.8, -0.3, 0.3, 0.8)        # engines 1-4, port to starboard
HARMONICS = (1.0, 0.55, 0.35, 0.22, 0.14, 0.09, 0.06, 0.04)
WHINE_HZ = 3100.0                   # turbine whine at 100% (faint, through the hull)
IDLE_POWER, CRUISE_POWER = 0.25, 0.8
PEAK = 0.5                          # the loudest moment (full power on the roll), full scale 1

# The takeoff piece, seconds from its start.
RUNUP, BRAKES_OFF, LIFTOFF, CLIMBED, TAKEOFF_LEN = 4.0, 14.0, 38.0, 53.0, 56.0


def smooth(t, a, b):
    x = np.clip((t - a) / (b - a), 0, 1)
    return x * x * (3 - 2 * x)


def noise(n, seed, shape):
    """Noise n samples long with spectrum `shape(freqs)`; periodic over n."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1 / RATE)
    spec = (rng.normal(size=f.size) + 1j * rng.normal(size=f.size)) * shape(f)
    spec[0] = 0
    a = np.fft.irfft(spec, n)
    return a / np.sqrt(np.mean(a ** 2))


def roar_shape(f):
    return np.where(f > 15, 1 / np.sqrt(np.maximum(f, 1)), 0) / (1 + (f / 450) ** 2)


def rumble_shape(f):
    return np.exp(-((f - 35) / 20) ** 2)


def engines(t, rpm, power, periodic):
    """Stereo (n, 2) for rpm and power curves (arrays like t). periodic: constant rpm, and every
    frequency rounded to fit LOOP_LEN."""
    n = t.size
    out = np.zeros((n, 2))
    rng = np.random.default_rng(7)
    for k, (d, pan) in enumerate(zip(DETUNE, PAN)):
        f = BLADE_HZ * rpm * (1 + d)
        shaft = f / 4
        if periodic:
            step = 4 / LOOP_LEN                        # the shaft rate (f/4) must fit too
            f = np.round(f / step) * step
            shaft = f / 4
            phase = 2 * np.pi * f * t
            sphase = 2 * np.pi * shaft * t
        else:
            phase = 2 * np.pi * np.cumsum(f) / RATE
            sphase = phase / 4
        amp = 0.25 + 0.75 * power
        tone = sum(h * np.sin(i * phase + rng.uniform(0, 2 * np.pi))
                   for i, h in enumerate(HARMONICS, 1))
        tone *= 1 + 0.12 * np.sin(sphase + rng.uniform(0, 2 * np.pi))   # a little prop imbalance
        whine_f = WHINE_HZ * rpm * (1 + 3 * d)
        if periodic:
            whine_f = np.round(whine_f * LOOP_LEN) / LOOP_LEN
            wphase = 2 * np.pi * whine_f * t
        else:
            wphase = 2 * np.pi * np.cumsum(whine_f) / RATE
        sig = 0.16 * amp * tone + 0.012 * rpm * np.sin(wphase)
        out[:, 0] += sig * np.sqrt((1 - pan) / 2)
        out[:, 1] += sig * np.sqrt((1 + pan) / 2)
    roar_amp = (0.15 + 0.85 * power ** 1.5) * 0.35
    common = noise(n, 11, roar_shape)
    for ch in range(2):
        out[:, ch] += roar_amp * (0.7 * common + 0.3 * noise(n, 12 + ch, roar_shape))
    return out


def takeoff_curves(t):
    rpm = IDLE_RPM + (1 - IDLE_RPM) * smooth(t, RUNUP, BRAKES_OFF - 2)
    power = (IDLE_POWER + (0.6 - IDLE_POWER) * smooth(t, RUNUP, BRAKES_OFF - 2)
             + 0.4 * smooth(t, BRAKES_OFF - 1, BRAKES_OFF + 3)
             - (1 - CRUISE_POWER) * smooth(t, CLIMBED - 6, CLIMBED))
    return rpm, power


def write_wav(path, a):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    mod = out_dir("engines") / "mod"
    sound_dir = mod / "Sound" / "FX" / "DevilsInTheDetails" / "C130"

    t_loop = np.arange(int(LOOP_LEN * RATE)) / RATE
    ones = np.ones_like(t_loop)
    idle = engines(t_loop, IDLE_RPM * ones, IDLE_POWER * ones, True)
    cruise = engines(t_loop, ones, CRUISE_POWER * ones, True)

    t = np.arange(int(TAKEOFF_LEN * RATE)) / RATE
    rpm, power = takeoff_curves(t)
    takeoff = engines(t, rpm, power, False)
    # Runway rumble on the roll, growing with speed, gone at liftoff.
    roll = smooth(t, BRAKES_OFF, LIFTOFF - 4) * (1 - smooth(t, LIFTOFF - 0.5, LIFTOFF + 0.5))
    rumble = noise(t.size, 21, rumble_shape) * 0.25 * roll
    takeoff += rumble[:, None]

    scale = PEAK / np.abs(takeoff).max()
    files = []
    for name, a in (("engines_idle", idle), ("engines_takeoff", takeoff), ("engines_cruise", cruise)):
        a = a * scale
        p = sound_dir / f"{name}.wav"
        write_wav(p, a)
        files.append(p)
        rms = 20 * np.log10(np.sqrt(np.mean(a ** 2)))
        print(f"{p.relative_to(ROOT)}: {len(a) / RATE:.0f} s, {rms:.1f} dB RMS, peak {np.abs(a).max():.2f}")
    # The loops must match end to start.
    for name, a in (("idle", idle), ("cruise", cruise)):
        jump = np.abs(a[0] - a[-1]).max() * scale
        print(f"  {name} loop seam: {jump:.4f}")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
