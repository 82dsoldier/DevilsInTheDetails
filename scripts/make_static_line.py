"""The stick's static lines, as something they wear: a hooked-up static line skinned to the man,
so it goes where he goes. The hook rides his root bone (it moves only when he moves or turns), so
it stays on the cable as he shifts and looks about; the strap blends from it to his chest.

    python scripts/make_static_line.py [--install "<Fallout 4>/Data"]

The shape is make_c130_blockout.static_line_parts (the snap hook on the anchor cable ahead of
him, the yellow webbing down over his inboard shoulder to the top of his main), in his own frame,
fitted to the vanilla male body in fatigues. Two models: R over the right shoulder (the
starboard men: facing aft, their inboard shoulder is the right) and L over the left (port).
The textures are the cabin's (make_c130_blockout.py writes them). worn.py does the skinning.

Writes out/c130/mod/Meshes/DevilsInTheDetails/Aircraft/C130_StaticLineR.nif and ...L.nif. The
plugin's armor (DevilsStaticLineRight/Left, body slot 56) points at them; the jumpmaster's script
gives each man his on "Hook up!".
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_c130_blockout as c                                    # noqa: E402
import worn                                                       # noqa: E402
from make_heightmap import out_dir                                # noqa: E402

# The hook rides the root, so it stays on the cable while he shifts his weight and looks about;
# the strap runs from the root (near the hook) to the chest (by his shoulder), blended between.
ROOT_FROM, CHEST_FROM = 2.05, 1.68      # metres up the strap's front: all root above, all chest below


def strap_weights(v):
    if v[1] < 0.05:                                      # over his shoulder and down his back
        return {"Chest": 1.0}
    t = min(1.0, max(0.0, (v[2] - CHEST_FROM) / (ROOT_FROM - CHEST_FROM)))
    w = t * t * (3 - 2 * t)
    return {"Root": w, "Chest": 1.0 - w}


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
    for mirror, name in ((False, "C130_StaticLineR"), (True, "C130_StaticLineL")):
        path = mesh_dir / f"{name}.nif"
        shapes = {sn: (mat, m, strap_weights if sn == "static_line" else worn.rigid("Root"))
                  for sn, (mat, _, m) in c.static_line_parts(mirror).items()}
        worn.write_worn(path, name, shapes, tex, pyn, c.MATERIALS)
        files.append(path)
        print(f"{path}: worn, the hook on Root, the strap Root to Chest")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
