"""The parked C-130 at Hanscom and boarding it.

  GLOB DevilsBoarded (0), the jumpmaster's new Boarded property
  STAT DevilsC130Exterior, ACTI DevilsC130BoardingDoor (script DevilsBoardPlane)
  REFRs of both on the East Ramp, PARK_OUT m out from the Devils' hangar door, parallel to it
  REFR DevilsC130CabinMarker (an XMarkerHeading, persistent) in the cabin over Sicily

    python esp_board.py in.esp out.esp
"""
import sys, struct, json, math
import numpy as np
from esplib import *
import vmadlib

sys.path.insert(0, "C:/source/repos/BraggMap/scripts")
import shapely
from shapely.geometry import Polygon
from pyproj import Transformer
import make_hanscom_paving as P
import make_hanscom_buildings as B

HANSCOM, JM, NO_RIG = 0x0100A22E, 0x010073B2, 0x01005534
SICILY_PERSIST = 0x01003E64
XMARKER_HEADING = 0x00000034
TEMPLATE_STAT, TEMPLATE_ACTI = 0x01008B42, 0x01005535
CABIN = (-13870.0, -20975.0, 24330.0)
CABIN_FACING = 104.0                 # degrees: aft, toward the doors and the jumpmaster
PARK_OUT = 45.0                      # metres from the hangar's door wall to the fuselage's centre line

src, dst = sys.argv[1:3]
top = parse(open(src, "rb").read())
tes4 = top[0]
ver, nrec, nxt = struct.unpack("<fiI", dict(sublist(tes4.body()))[b"HEDR"])
recs = {n.fid: n for n, *_ in walk(top) if isinstance(n, Rec)}


def new_fid():
    global nxt
    f = 0x01000000 | nxt
    nxt += 1
    return f


def new_rec(typ, fid, subs_, flags=0, like=TEMPLATE_STAT):
    body = pack_subs(subs_)
    hdr = bytearray(recs[like].raw[:24])
    hdr[0:4] = typ.encode()
    struct.pack_into("<III", hdr, 4, len(body), flags, fid)
    return Rec(bytes(hdr) + body)


def top_group(label):
    return [n for n in top if isinstance(n, Group) and n.gtype == 0 and n.label == label][0]


def z(s):
    return s.encode() + b"\0"


# Where: the Devils' hangar's door wall, as make_hanscom_buildings.py builds it.
out = P.out_dir("hanscom")
terrain = P.Terrain(out)
terrain.z = np.fromfile(out / "graded16.raw", dtype="<u2").reshape(terrain.ny, terrain.nx) * terrain.step
meta = json.loads((out / "heightmap.json").read_text())
tu = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
areas = {m: shapely.transform(p, lambda q: np.column_stack(terrain.game(q[:, 0], q[:, 1])))
         for m, p in P.paved_areas(json.loads((out / "osm.json").read_text()), tu).items()}
for el in json.loads((out / "osm_buildings.json").read_text())["elements"]:
    if el.get("tags", {}).get("name") == "Hangar 1715":
        e, n = np.array([tu.transform(p["lon"], p["lat"]) for p in el["geometry"]]).T
        poly = shapely.orient_polygons(Polygon(np.column_stack(terrain.game(e, n))).buffer(0).simplify(0.2 / P.UNIT_M))
i = B.ramp_edge(poly, areas["concrete"])
pts = list(poly.exterior.coords)[:-1]
p0, p1 = pts[i], pts[(i + 1) % len(pts)]
L = math.dist(p0, p1)
ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
outward = (uy, -ux)                                  # right of travel, for a ccw outline
mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
px, py = mx + outward[0] * PARK_OUT / P.UNIT_M, my + outward[1] * PARK_OUT / P.UNIT_M
pz = float(terrain.at(px, py)) + P.OFFSET
nose = (-ux, -uy)                                    # along the wall, toward p0
heading = math.atan2(nose[0], nose[1]) % (2 * math.pi)
on_concrete = shapely.contains_xy(areas["concrete"], px, py)
print(f"parked at {px:.0f}, {py:.0f}, {pz:.0f}, heading {math.degrees(heading):.0f}; on the ramp: {on_concrete}")

# The records.
glob = new_rec("GLOB", new_fid(), [(b"EDID", z("DevilsBoarded")), (b"FLTV", struct.pack("<f", 0))])
top_group(b"GLOB").kids.append(glob)

tsub = dict(sublist(recs[TEMPLATE_STAT].body()))
ext_obnd = struct.pack("<6h", -1414, -1050, 0, 1414, 1050, 820)
stat = new_rec("STAT", new_fid(), [(b"EDID", z("DevilsC130Exterior")), (b"OBND", ext_obnd),
                                   (b"MODL", z("DevilsInTheDetails\\Aircraft\\C130_Exterior.nif")),
                                   (b"MODT", tsub[b"MODT"]), (b"DNAM", tsub[b"DNAM"])])
top_group(b"STAT").kids.append(stat)

marker = new_rec("REFR", new_fid(), [(b"EDID", z("DevilsC130CabinMarker")),
                                     (b"NAME", struct.pack("<I", XMARKER_HEADING)),
                                     (b"DATA", struct.pack("<6f", *CABIN, 0, 0, math.radians(CABIN_FACING)))],
                 flags=0x400)

asub = sublist(recs[TEMPLATE_ACTI].body())
obj = lambda f: struct.pack("<HhI", 0, -1, f)
vmad = vmadlib.build(6, 2, [["DevilsBoardPlane", 0, [["CabinMarker", 1, 1, obj(marker.fid)],
                                                     ["NoRigMessage", 1, 1, obj(NO_RIG)],
                                                     ["Boarded", 1, 1, obj(glob.fid)]]]], b"")
acti_subs = []
for t, v in asub:
    if t == b"EDID":
        v = z("DevilsC130BoardingDoor")
    elif t == b"VMAD":
        v = vmad
    elif t == b"OBND":
        v = struct.pack("<6h", -168, -396, 73, -147, -332, 202)   # the doorway box (make_c130_exterior.py)
    elif t == b"FULL":
        v = z("C-130")
    elif t == b"MODL":
        v = z("DevilsInTheDetails\\Aircraft\\C130_BoardingDoor.nif")
    acti_subs.append((t, v))
    if t == b"FNAM":
        acti_subs.append((b"ATTX", z("Board")))
acti = new_rec("ACTI", new_fid(), acti_subs, like=TEMPLATE_ACTI)
top_group(b"ACTI").kids.append(acti)


def cell_temp(world, xy):
    """The temporary-children group of a world's exterior cell."""
    want = None
    for n, sib, idx, par in walk(top):
        if isinstance(n, Rec) and n.type == "CELL" and any(
                p.gtype == 1 and struct.unpack("<I", p.label)[0] == world for p in par):
            d = dict(sublist(n.body()))
            if b"XCLC" in d and struct.unpack_from("<ii", d[b"XCLC"]) == xy:
                want = n.fid
    for n, *_ in walk(top):
        if isinstance(n, Group) and n.gtype == 9 and struct.unpack("<I", n.label)[0] == want:
            return n
    raise KeyError(xy)


rot = (0.0, 0.0, heading)
temp = cell_temp(HANSCOM, (int(px // 4096), int(py // 4096)))
for base in (stat, acti):
    temp.kids.append(new_rec("REFR", new_fid(), [(b"NAME", struct.pack("<I", base.fid)),
                                                 (b"DATA", struct.pack("<6f", px, py, pz, *rot))]))
persist = [n for n, *_ in walk(top) if isinstance(n, Group) and n.gtype == 8
           and struct.unpack("<I", n.label)[0] == SICILY_PERSIST][0]
persist.kids.append(marker)

# The jumpmaster's Boarded property.
jm = recs[JM]
subs_ = sublist(jm.body())
for k, (t, v) in enumerate(subs_):
    if t == b"VMAD":
        vv, ff, sc, rest = vmadlib.parse(v)
        sc[0][2] = [q for q in sc[0][2] if q[0] != "Boarded"] + [["Boarded", 1, 1, obj(glob.fid)]]
        subs_[k] = (t, vmadlib.build(vv, ff, sc, rest))
jm.set_body(pack_subs(subs_))

added = 7
tes4.set_body(pack_subs([(t, struct.pack("<fiI", ver, nrec + added, nxt) if t == b"HEDR" else v)
                         for t, v in sublist(tes4.body())]))
open(dst, "wb").write(b"".join(n.bytes() for n in top))
print(f"GLOB {glob.fid:08X}, STAT {stat.fid:08X}, ACTI {acti.fid:08X}, cabin marker {marker.fid:08X}")
