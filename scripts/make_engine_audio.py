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
  engines_cruise_doors.wav  loop: in flight with the jump doors open, the wind roaring in
  hydraulics.wav        one piece, HYD_LEN s: the pump closing the ramp and doors before
                        takeoff; the doors shut at HYD_CLOSED
  door_open.wav         one piece, DOOR_LEN s: the loadmaster opening a jump door (it
                        slides from DOOR_SLIDE to DOOR_UP)

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
# The hydraulics closing the ramp and doors: the locks clunk home at HYD_CLOSED.
HYD_CLOSED, HYD_LEN = 9.0, 10.5
# A jump door opening: unlatched at 0.1 s, sliding up its tracks from DOOR_SLIDE to DOOR_UP
# (where it bangs to a stop), the wind coming in; DOOR_LEN long. The scene slides the door to match.
DOOR_SLIDE, DOOR_UP, DOOR_LEN = 0.4, 3.2, 4.5


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


def band_shape(lo, hi):
    return lambda f: ((f > lo) & (f < hi)) / np.sqrt(np.maximum(f, 1))


def clunk(n, at, freq, gain, seed, decay=0.12):
    """A metal clunk at `at` s: a decaying low thud and a short bright crack."""
    t = np.arange(n) / RATE - at
    on = t >= 0
    thud = np.sin(2 * np.pi * freq * t) * np.exp(-t / decay)
    crack = noise(n, seed, band_shape(800, 5000)) * np.exp(-t / 0.02)
    return np.where(on, gain * (thud + 0.5 * crack), 0)


def hydraulics():
    """The hydraulic pump closing the ramp and doors before takeoff: an electric motor whine that
    spins up, labours while the ramp moves, the locks clunk home at HYD_CLOSED, and spins down."""
    n = int(HYD_LEN * RATE)
    t = np.arange(n) / RATE
    run = smooth(t, 0, 0.8) * (1 - smooth(t, HYD_CLOSED + 0.3, HYD_LEN - 0.2))
    load = smooth(t, 1.2, 2.0) * (1 - smooth(t, HYD_CLOSED - 0.4, HYD_CLOSED))
    f = 410 * (0.4 + 0.6 * run) * (1 - 0.04 * load + 0.006 * np.sin(2 * np.pi * 0.7 * t))
    phase = 2 * np.pi * np.cumsum(f) / RATE
    whine = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.3 * np.sin(3 * phase)
             + 0.25 * np.sin(4.5 * phase) + 0.12 * np.sin(9 * phase))
    hiss = noise(n, 31, band_shape(1500, 6000)) * 0.15 * load
    a = 0.06 * run * (whine * (0.8 + 0.2 * load)) + 0.06 * hiss
    a += clunk(n, HYD_CLOSED - 0.15, 70, 0.22, 32, 0.18) + clunk(n, HYD_CLOSED, 110, 0.14, 33)
    return np.stack([a, a], 1)


def wind(n, periodic_len=None):
    """Wind roaring past the open doors, with some buffeting; stereo, the doors either side."""
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for ch in range(2):
        rush = noise(n, 41 + ch, lambda f: np.where(f > 40, 1 / np.sqrt(np.maximum(f, 1)), 0)
                     / (1 + (f / 1800) ** 2))
        buffet = noise(n, 43 + ch, rumble_shape)
        flutter = 1 + 0.25 * np.sin(2 * np.pi * (round(0.37 * LOOP_LEN) / LOOP_LEN) * t + ch)
        out[:, ch] = 0.07 * rush * flutter + 0.05 * buffet
    return out


def door_open():
    """The loadmaster opening a jump door: unlatch, the door rattling up its tracks, a bang as it
    stops at the top, and the wind coming in."""
    n = int(DOOR_LEN * RATE)
    t = np.arange(n) / RATE
    a = clunk(n, 0.1, 140, 0.18, 51, 0.06)
    slide = (smooth(t, DOOR_SLIDE - 0.05, DOOR_SLIDE + 0.1) * (1 - smooth(t, DOOR_UP - 0.1, DOOR_UP)))
    clicks = np.sin(2 * np.pi * 11 * t) ** 8                     # the rollers over the track joints
    a = a + noise(n, 52, band_shape(300, 3000)) * 0.08 * slide * (0.5 + clicks)
    a = a + clunk(n, DOOR_UP, 90, 0.25, 53, 0.15)
    a = np.stack([a, a], 1)
    return a + wind(n) * smooth(t, DOOR_SLIDE, DOOR_LEN - 0.3)[:, None]


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
    idle, takeoff, cruise = idle * scale, takeoff * scale, cruise * scale
    cruise_doors = cruise + wind(cruise.shape[0])
    files = []
    for name, a in (("engines_idle", idle), ("engines_takeoff", takeoff), ("engines_cruise", cruise),
                    ("engines_cruise_doors", cruise_doors), ("hydraulics", hydraulics()),
                    ("door_open", door_open())):
        p = sound_dir / f"{name}.wav"
        write_wav(p, a)
        files.append(p)
        rms = 20 * np.log10(np.sqrt(np.mean(a ** 2)))
        print(f"{p.relative_to(ROOT)}: {len(a) / RATE:.0f} s, {rms:.1f} dB RMS, peak {np.abs(a).max():.2f}")
    # The loops must match end to start.
    for name, a in (("idle", idle), ("cruise", cruise), ("cruise_doors", cruise_doors)):
        jump = np.abs(a[0] - a[-1]).max()
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
