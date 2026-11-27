"""Worn models: things a man wears (his static line, his parachutes and rucksack), skinned to the
vanilla skeleton so they go where he goes.

Shapes are built in his own frame (metres, his feet at the origin, facing +Y, his right +X),
fitted to the vanilla male body in fatigues in its bind pose. Each vertex is weighted to one or
more bones; write_worn makes the nif.

The bind poses are from the vanilla skeleton (Meshes\\Actors\\Character\\CharacterAssets\\
skeleton.nif) and match the vanilla FatiguesM.nif, kept here as constants so the build needs no
game archives. Skin space is the actor's space (game units) moved by G2S_T; each bone's
skin-to-bone (translation, rotation) takes skin space to the bone's.
"""
from make_heightmap import UNIT_M

G2S_T = (0.00020388176199048758, 0.8818080425262451, -120.84370422363281)
_I = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
BONES = {
    # At his feet, facing as he does: it moves only when he moves or turns, not as he breathes,
    # shifts his weight or looks about.
    "Root": (tuple(-t for t in G2S_T), _I),
    "Pelvis": ((51.9324, -0.88187, 0.00025),
               ((0.0, 0.0, 1.0), (-1e-06, 1.0, -0.0), (-1.0, -1e-06, 0.0))),
    "SPINE1": ((47.66992950439453, -6.771327018737793, 0.00020669560763053596),
               ((-2.384185791015625e-07, 0.1225384771823883, 0.9924637675285339),
                (1.1585652828216553e-06, 0.9924637675285339, -0.1225384771823883),
                (-1.0, 1.1138617992401123e-06, -3.5762786865234375e-07))),
    "SPINE2": ((39.54899597167969, 0.13759994506835938, 0.00021451013162732124),
               ((-2.384185791015625e-07, -0.05266787111759186, 0.998612105846405),
                (-5.383044481277466e-07, 0.998612105846405, 0.05266787111759186),
                (-1.0, -5.252659320831299e-07, -2.384185791015625e-07))),
    "Chest": ((29.590248107910156, -0.40610456466674805, 0.00022265555162448436),
              ((1.1920928955078125e-07, -0.03431236743927002, 0.9994111657142639),
               (-2.4586915969848633e-07, 0.9994111657142639, 0.03431236743927002),
               (-1.0, -2.514570951461792e-07, 5.960464477539063e-08))),
    # The thighs: his left is -X.
    # The head (from the vanilla military cap, Clothes\Ronnie\MCap.nif, skinned to it alone).
    "HEAD": ((0.0003204345703125, -3.814697265625e-05, 2.920367114711553e-05),
             ((4.172325134277344e-07, 0.0649806559085846, 0.9978865385055542),
              (2.9802322387695312e-08, 0.9978865385055542, -0.0649806559085846),
              (-1.0, 5.587935447692871e-08, 4.172325134277344e-07))),
    "LLeg_Thigh": ((-52.27887, -2.76568, -0.88223),
                   ((-0.127248, -0.038602, -0.991119), (-0.289087, 0.957303, -0.00017),
                    (0.948808, 0.286498, -0.132974))),
    "RLeg_Thigh": ((-52.30026, -2.48862, 0.06424),
                   ((0.113885, -0.029031, -0.99307), (0.289361, 0.957206, 0.005201),
                    (0.950421, -0.287948, 0.117412))),
}

# The torso's bones by height (metres), each centred on its stretch of the spine: a vertex is
# shared between the two it lies between, so the kit bends with him.
TORSO = [("Pelvis", 0.90), ("SPINE1", 1.08), ("SPINE2", 1.24), ("Chest", 1.42)]


def torso_weights(v):
    """A vertex on his torso (metres, his frame): its weights among the spine's bones."""
    z = v[2]
    if z <= TORSO[0][1]:
        return {TORSO[0][0]: 1.0}
    for (a, za), (b, zb) in zip(TORSO, TORSO[1:]):
        if z <= zb:
            t = (z - za) / (zb - za)
            return {a: 1.0 - t, b: t}
    return {TORSO[-1][0]: 1.0}


def rigid(bone):
    return lambda v: {bone: 1.0}


def _xf(TransformBuf, t, r):
    b = TransformBuf()
    b.store(t, r, (1, 1, 1))             # returns None: keep the buffer
    return b


def write_worn(path, name, shapes, tex, pyn, materials, prefix="c130_"):
    """shapes: {shape name: (material, Mesh, weights)}, weights(vertex in metres) -> {bone: w}.
    materials: the cabin's MATERIALS table (for double-sided), or one like it. Textures are
    named <prefix><material>{,_n,_s}.dds under tex."""
    NifFile, NiShapeBuf, PynBufferTypes, TransformBuf, SF1, SF2 = pyn
    nif = NifFile()
    nif.initialize("FO4", str(path), root_type="NiNode", root_name=name)
    g2s = _xf(TransformBuf, G2S_T, _I)
    for shape_name, (mat, m, weights) in shapes.items():
        if not m.tris:
            continue
        verts = [tuple(v[i] / UNIT_M + G2S_T[i] for i in range(3)) for v in m.verts]
        per_bone = {}
        for i, v in enumerate(m.verts):
            for bone, w in weights(v).items():
                if w > 1e-4:
                    per_bone.setdefault(bone, []).append((i, w))
        props = NiShapeBuf()
        props.bufType = PynBufferTypes.BSTriShapeBufType
        shape = nif.createShapeFromData(shape_name, verts, m.tris, m.uvs, m.norms, props=props,
                                        parent=nif.rootNode)
        shape.skin()
        shape.set_global_to_skin(g2s)
        # Every bone first: adding one resets the skin-to-bone of those already set.
        for bone in per_bone:
            t, r = BONES[bone]
            rt = [[r[j][i] for j in range(3)] for i in range(3)]
            # The bone node itself, in the actor's space: skin-to-bone inverted, less the G2S shift.
            node = _xf(TransformBuf, [-sum(rt[i][j] * t[j] for j in range(3)) - G2S_T[i]
                                      for i in range(3)], rt)
            shape.add_bone(bone, node)
        for bone, w in per_bone.items():
            shape.set_skin_to_bone_xform(bone, _xf(TransformBuf, *BONES[bone]))
            shape.setShapeWeights(bone, w)
        shape.shader._checked_for_materials = True
        shape.shader._materials = None
        sp = shape.shader.properties
        sp.bufType = PynBufferTypes.BSLightingShaderPropertyBufType
        sp.shaderflags1_set(SF1.SKINNED)
        if materials[mat][1].get("double_sided"):
            sp.shaderflags2_set(SF2.DOUBLE_SIDED)
        sp.Spec_Str, sp.Glossiness = 1.0, 1.0
        shape.set_texture("Diffuse", f"{tex}\\{prefix}{mat}.dds")
        shape.set_texture("Normal", f"{tex}\\{prefix}{mat}_n.dds")
        shape.set_texture("Specular", f"{tex}\\{prefix}{mat}_s.dds")
        shape.save_shader_attributes()
        if materials[mat][1].get("alpha"):          # cut out by the diffuse's alpha (a pin's shape)
            shape.has_alpha_property = True
            shape.alpha_property.properties.flags = 4844          # alpha test
            shape.alpha_property.properties.threshold = 128
            shape.save_alpha_property()
    nif.save()


def load_pyn():
    from make_photo_overlay import load_pynifly
    NifFile, NiShapeBuf, PynBufferTypes, _ = load_pynifly()
    from pyn.structs import TransformBuf
    from pyn.nifconstants import ShaderFlags1FO4, ShaderFlags2FO4
    return NifFile, NiShapeBuf, PynBufferTypes, TransformBuf, ShaderFlags1FO4, ShaderFlags2FO4
