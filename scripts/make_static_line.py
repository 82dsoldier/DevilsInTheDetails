"""The stick's static lines, as something they wear: a hooked-up static line skinned to the man,
so it goes where he goes. The hook rides his root bone (it moves only when he moves or turns), so
it stays on the cable as he shifts and looks about; the strap blends from it to his chest.

    python scripts/make_static_line.py [--install "<Fallout 4>/Data"]

The shape is make_c130_blockout.static_line_parts (the snap hook on the anchor cable ahead of
him, the yellow webbing down over his inboard shoulder and down his back), in his own frame,
fitted to the vanilla male body in fatigues. Two models: R over the right shoulder (the
starboard men: facing aft, their inboard shoulder is the right) and L over the left (port).
The textures are the cabin's (make_c130_blockout.py writes them).

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
from make_heightmap import UNIT_M, out_dir                        # noqa: E402
from make_photo_overlay import load_pynifly                       # noqa: E402

# The bones' bind poses, from the vanilla Meshes\Armor\ArmyFatigues\FatiguesM.nif (so the
# build needs no game archives): skin space is the actor's space (feet at the origin, game units)
# moved by G2S_T, and CHEST_S2B takes skin space to the bone's.
BONE = "Chest"
ROOT = "Root"        # at his feet, facing as he does; it moves only when he moves or turns
G2S_T = (0.00020388176199048758, 0.8818080425262451, -120.84370422363281)
CHEST_S2B_T = (29.590248107910156, -0.40610456466674805, 0.00022265555162448436)
CHEST_S2B_R = ((1.1920928955078125e-07, -0.03431236743927002, 0.9994111657142639),
               (-2.4586915969848633e-07, 0.9994111657142639, 0.03431236743927002),
               (-1.0, -2.514570951461792e-07, 5.960464477539063e-08))
# The hook rides the root, so it stays on the cable while he shifts his weight and looks about;
# the strap runs from the root (near the hook) to the chest (by his shoulder), blended between.
ROOT_FROM, CHEST_FROM = 2.05, 1.68      # metres up the strap's front: all root above, all chest below


def root_weight(part, v):
    """How much of a vertex (metres, his frame) rides the root rather than the chest."""
    if part != "static_line":
        return 1.0                                       # the hook and its gate
    if v[1] < 0.05:                                      # over his shoulder and down his back
        return 0.0
    t = min(1.0, max(0.0, (v[2] - CHEST_FROM) / (ROOT_FROM - CHEST_FROM)))
    return t * t * (3 - 2 * t)


def write_worn(path, name, parts, tex, pyn):
    NifFile, NiShapeBuf, PynBufferTypes, TransformBuf, SF1, SF2 = pyn
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="NiNode", root_name=name)
    def xf(t, r):
        b = TransformBuf()
        b.store(t, r, (1, 1, 1))
        return b

    g2s = xf(G2S_T, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    s2b = xf(CHEST_S2B_T, CHEST_S2B_R)
    # The bone node itself, in the actor's space: the inverse of skin-to-bone, less the G2S shift.
    rt = [[CHEST_S2B_R[j][i] for j in range(3)] for i in range(3)]
    node = xf([-sum(rt[i][j] * CHEST_S2B_T[j] for j in range(3)) - G2S_T[i] for i in range(3)], rt)
    root_s2b = xf([-t for t in G2S_T], ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    root_node = xf((0, 0, 0), ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    for shape_name, (mat, _, m) in parts.items():
        if not m.tris:
            continue
        verts = [tuple(v[i] / UNIT_M + G2S_T[i] for i in range(3)) for v in m.verts]
        wr = [root_weight(shape_name, v) for v in m.verts]
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        shape = nif.createShapeFromData(shape_name, verts, m.tris, m.uvs, m.norms, props=props,
                                        parent=nif.rootNode)
        shape.skin()
        shape.set_global_to_skin(g2s)
        bones = [(bone, bnode, bs2b, weights) for bone, bnode, bs2b, weights in (
                 (BONE, node, s2b, [(i, 1.0 - w) for i, w in enumerate(wr) if w < 1.0]),
                 (ROOT, root_node, root_s2b, [(i, w) for i, w in enumerate(wr) if w > 0.0]))
                 if weights]
        # All the bones first: adding one resets the skin-to-bone of those already set.
        for bone, bnode, _, _ in bones:
            shape.add_bone(bone, bnode)
        for bone, _, bs2b, weights in bones:
            shape.set_skin_to_bone_xform(bone, bs2b)
            shape.setShapeWeights(bone, weights)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        sp = shape.shader.properties
        sp.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        sp.shaderflags1_set(SF1.SKINNED)
        if c.MATERIALS[mat][1].get("double_sided"):
            sp.shaderflags2_set(SF2.DOUBLE_SIDED)
        sp.Spec_Str, sp.Glossiness = 1.0, 1.0
        shape.set_texture("Diffuse", f"{tex}\\c130_{mat}.dds")
        shape.set_texture("Normal", f"{tex}\\c130_{mat}_n.dds")
        shape.set_texture("Specular", f"{tex}\\c130_{mat}_s.dds")
        shape.save_shader_attributes()
    nif.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", help="the game's Data folder, to copy the files into")
    args = ap.parse_args()
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.structs import TransformBuf
    from pyn.nifconstants import ShaderFlags1FO4, ShaderFlags2FO4
    pyn = (NifFile, NiShapeBuf, PynBufferTypes, TransformBuf, ShaderFlags1FO4, ShaderFlags2FO4)

    mod = out_dir("c130") / "mod"
    mesh_dir = mod / "Meshes" / c.MOD_PATH
    mesh_dir.mkdir(parents=True, exist_ok=True)
    tex = "textures\\" + c.MOD_PATH.replace("/", "\\")
    files = []
    for mirror, name in ((False, "C130_StaticLineR"), (True, "C130_StaticLineL")):
        path = mesh_dir / f"{name}.nif"
        write_worn(path, name, c.static_line_parts(mirror), tex, pyn)
        files.append(path)
        print(f"{path}: worn, bound to {BONE} and {ROOT}")
    if args.install:
        data = Path(args.install)
        for f in files:
            dest = data / f.relative_to(mod)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print(f"  installed {dest}")


if __name__ == "__main__":
    main()
