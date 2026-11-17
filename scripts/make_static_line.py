"""The static lines, as something they wear: a hooked-up static line skinned to the man, so it
goes where he goes. The hook rides his root bone (it moves only when he moves or turns), so it
stays on the cable as he shifts and looks about; the strap blends from it to his chest.

    python scripts/make_static_line.py [--install "<Fallout 4>/Data"]

The shape is make_c130_blockout.static_line_parts (the snap hook on the anchor cable ahead of
him, the yellow webbing down over his shoulder nearest it and over the top of his main), in his
own frame, fitted to the vanilla male body in fatigues. The textures are the cabin's
(make_c130_blockout.py writes them). worn.py does the skinning.

  C130_StaticLineR / L   the stick: R over the right shoulder (the starboard men: facing aft,
                         their inboard shoulder), L over the left (port)
  C130_StaticLineJM      the jumpmaster, hooked up before he starts the commands (the author):
                         he stands aft of the starboard door on the ramp, facing forward, the
                         cable to his left and, the ramp rising under him, nearer his head

The plugin's armor (DevilsStaticLineRight / Left / JM, body slot 56) points at them; the
jumpmaster's script puts them on.
"""
import argparse
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_c130_blockout as c                                    # noqa: E402
import worn                                                       # noqa: E402
from make_heightmap import out_dir                                # noqa: E402

# The jumpmaster's reference (DevilsInTheDetails.esp, 010073B2), in metres from the hull's
# origin: facing forward (+Y, heading 0), so his right is +X. The ramp under him rises aft of the
# hinge at RAMP_ANGLE, so he stands that much higher than the cabin floor.
JM_X, JM_Y = 1.214, -7.857
JM_FLOOR = max(0.0, (-c.DEFAULT_LENGTH / 2 - JM_Y) * math.tan(math.radians(c.RAMP_ANGLE)))
JM_CABLE = (c.CABLE_X - JM_X, c.CABLE_Z - JM_FLOOR)              # to his right (so left), up

CHEST_FROM = 1.68          # metres up the strap's front: all chest below (by his shoulder)


def strap_weights(cable_z):
    """The hook rides the root, so it stays on the cable while he shifts and looks about; the
    strap blends from root (near the hook) to chest (by his shoulder)."""
    root_from = cable_z - 0.20

    def weights(v):
        if v[1] < 0.05:                                  # over his shoulder and on to his main
            return {"Chest": 1.0}
        t = min(1.0, max(0.0, (v[2] - CHEST_FROM) / (root_from - CHEST_FROM)))
        w = t * t * (3 - 2 * t)
        return {"Root": w, "Chest": 1.0 - w}
    return weights


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    pyn = worn.load_pyn()
    mod = out_dir("c130") / "mod"
    mesh_dir = mod / "Meshes" / c.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex = "textures\\" + c.MOD_PATH.replace("/", "\\")
    files = []
    lines = (("C130_StaticLineR", False, None, c.CABLE_Z), ("C130_StaticLineL", True, None, c.CABLE_Z),
             ("C130_StaticLineJM", False, JM_CABLE, JM_CABLE[1]))
    for name, mirror, cable, cz in lines:
        path = mesh_dir / f"{name}.nif"
        shapes = {sn: (mat, m, strap_weights(cz) if sn == "static_line" else worn.rigid("Root"))
                  for sn, (mat, _, m) in c.static_line_parts(mirror, cable).items()}
        worn.write_worn(path, name, shapes, tex, pyn, c.MATERIALS)
        files.append(path)
        print(f"{path}: the hook on Root, the strap Root to Chest")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
