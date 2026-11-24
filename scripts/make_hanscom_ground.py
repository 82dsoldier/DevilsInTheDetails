"""Hanscom's ground cover: how much of each vanilla landscape texture every terrain point gets,
for scripts/esp/esp_ground_paint.py. The streets themselves are raised meshes
(make_hanscom_roads.py); the paint gives them gravel shoulders.

The cover is OpenStreetMap's (© OpenStreetMap contributors, ODbL) land use and natural areas,
fetched once into out/hanscom/osm_landcover.json; ground OSM says nothing about is dead wild
grass, broken up by patches of grassy dirt (smooth noise, the same every run). Each class is
rasterized at a quarter of the points' spacing and averaged to the points, then softened over
about a point, so its edges blend. Classes cover the ones below them in CLASSES' order (a
wood's edge over the grass, a parking lot over all), so the weights at a point add up to 1.

    python scripts/make_hanscom_ground.py [--refetch]

Writes out/hanscom/ground_paint.npz: `names`, `ltex` (form IDs) and `weights` (classes x the
heightmap's points, north row first, 0 to 255).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import requests
import shapely
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import POINT_UNITS, out_dir                                  # noqa: E402
import make_hanscom_paving as hp                                                 # noqa: E402

# Bottom to top: (name, vanilla LTEX, OSM tags it covers ("key=value", or "key=*")).
CLASSES = [
    ("wildgrass", 0x01D1D3, []),                                  # LDriedGrass01: the rest
    ("dirtgrass", 0x04417F, []),                                  # LDirtGravel01Grass: noise patches
    ("lawn", 0x06E61A, ["landuse=grass", "leisure=park", "leisure=pitch", "leisure=garden",
                        "leisure=playground", "landuse=recreation_ground", "landuse=cemetery",
                        "landuse=religious", "landuse=allotments", "landuse=residential"]),   # LDriedGrass03
    ("weeds", 0x022B63, ["landuse=meadow", "natural=grassland", "natural=heath", "natural=scrub",
                         "landuse=farmland", "landuse=animal_keeping"]),                      # LDriedGrass02Weeds
    ("forest", 0x03343C, ["natural=wood", "landuse=forest", "natural=tree_row"]),             # LForestFloor01
    ("wetland", 0x118017, ["natural=wetland", "natural=water"]),                              # LMarshMudFloor01Grass
    ("dirt", 0x021336, ["landuse=industrial", "landuse=commercial", "landuse=retail",
                        "landuse=construction", "landuse=brownfield", "landuse=landfill",
                        "railway=*", "natural=sand", "natural=bare_rock", "leisure=track"]),  # LDirtGravel01
    ("asphalt", 0x021C68, ["amenity=parking"]),                   # LAsphalt01
]
SHOULDER = 1             # points (1.8 m) of gravel past a street's edge
LINE_W = {"natural=tree_row": 8.0, "railway=*": 5.0}             # metres, for lines
PATCH_SIGMA = 6.0        # points: the dirt patches' size
PATCH_SHARE = 0.18       # about this much of the open ground
SOFT = 0.8               # points: the edges' softening
SUPER = 4
SEED = 1715


def fetch(path):
    s, w, n, e = hp.OSM_BBOX
    parts = "".join(f'way["{k}"]({s},{w},{n},{e});relation["{k}"]({s},{w},{n},{e});'
                    for k in ("landuse", "natural", "leisure"))
    q = (f'[out:json][timeout:120];({parts}way["amenity"="parking"]({s},{w},{n},{e});'
         f'way["railway"]({s},{w},{n},{e}););out geom tags;')
    r = requests.post(hp.OVERPASS, data={"data": q}, headers={"User-Agent": "map-tool/1.0"}, timeout=240)
    r.raise_for_status()
    path.write_text(r.text)


def tag_class(tags):
    for i, (_, _, keys) in enumerate(CLASSES):
        for k in keys:
            key, val = k.split("=")
            if key in tags and (val == "*" or tags[key] == val):
                return i, k
    return None, None


def shapes(osm, to_utm):
    """{class index: geometry in UTM metres}."""
    out = {}
    for el in osm["elements"]:
        ci, key = tag_class(el.get("tags", {}))
        if ci is None:
            continue
        if el["type"] == "way" and el.get("geometry"):
            pts = [to_utm.transform(p["lon"], p["lat"]) for p in el["geometry"]]
            if len(pts) < 2:
                continue
            if key in LINE_W:
                g = LineString(pts).buffer(LINE_W[key] / 2)
            elif len(pts) >= 4 and pts[0] == pts[-1]:
                g = Polygon(pts).buffer(0)
            else:
                continue
        elif el["type"] == "relation":
            rings = {"outer": [], "inner": []}
            for m in el.get("members", []):
                if m.get("geometry") and m.get("role") in rings:
                    rings[m["role"]].append(LineString([to_utm.transform(p["lon"], p["lat"]) for p in m["geometry"]]))
            outer = unary_union(list(polygonize(unary_union(rings["outer"])))) if rings["outer"] else None
            if outer is None or outer.is_empty:
                continue
            inner = unary_union(list(polygonize(unary_union(rings["inner"])))) if rings["inner"] else None
            g = outer.difference(inner) if inner is not None and not inner.is_empty else outer
        else:
            continue
        out.setdefault(ci, []).append(g)
    return {ci: unary_union(gs) for ci, gs in out.items()}


def rasterize(geom, terrain):
    """Coverage (0 to 1) of each terrain point by `geom` (game units)."""
    px = POINT_UNITS / SUPER
    W, H = terrain.nx * SUPER, terrain.ny * SUPER
    img = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(img)
    ox, oy = terrain.x0 - POINT_UNITS / 2, terrain.y1 + POINT_UNITS / 2
    to_px = lambda c: [((x - ox) / px, (oy - y) / px) for x, y in c]
    for p in getattr(geom, "geoms", [geom]):
        if p.is_empty or p.geom_type != "Polygon":
            continue
        dr.polygon(to_px(p.exterior.coords), fill=255)
        for h in p.interiors:
            dr.polygon(to_px(h.coords), fill=0)
    a = np.asarray(img, np.float32) / 255
    return a.reshape(terrain.ny, SUPER, terrain.nx, SUPER).mean(axis=(1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true", help="download the land cover again")
    args = ap.parse_args()
    out = out_dir(hp.AREA)
    path = out / "osm_landcover.json"
    if args.refetch or not path.exists():
        print("Fetching the land cover from OpenStreetMap...")
        fetch(path)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = hp.Terrain(out)
    game = lambda g: shapely.transform(g, lambda p: np.column_stack(terrain.game(p[:, 0], p[:, 1])))

    cover = np.zeros((len(CLASSES), terrain.ny, terrain.nx), np.float32)
    for ci, g in shapes(json.loads(path.read_text()), to_utm).items():
        cover[ci] = ndimage.gaussian_filter(rasterize(game(g), terrain), SOFT)
    # The dirt patches: smooth noise, its top PATCH_SHARE, with soft edges.
    noise = ndimage.gaussian_filter(np.random.default_rng(SEED).standard_normal((terrain.ny, terrain.nx)), PATCH_SIGMA)
    t = np.quantile(noise, 1 - PATCH_SHARE)
    cover[1] = np.clip((noise - t) / (noise.std() * 0.5), 0, 1)
    # The streets are raised meshes now (make_hanscom_roads.py): under and along them, gravel, a
    # shoulder SHOULDER points past each edge, so a street stands out from the grass.
    street = np.load(out / "road_paint.npy")
    shoulder = ndimage.maximum_filter(street, size=2 * SHOULDER + 1)
    cover[6] = np.maximum(cover[6], shoulder)

    # Each class covers those below it: its weight is its cover less what's on top of it.
    weights = np.zeros_like(cover)
    left = np.ones((terrain.ny, terrain.nx), np.float32)
    for ci in range(len(CLASSES) - 1, 0, -1):
        weights[ci] = np.clip(cover[ci], 0, 1) * left
        left -= weights[ci]
    weights[0] = left
    np.savez_compressed(out / "ground_paint.npz", names=np.array([c[0] for c in CLASSES]),
                        ltex=np.array([c[1] for c in CLASSES], np.uint32),
                        weights=np.round(weights * 255).astype(np.uint8))
    for (name, _, _), w in zip(CLASSES, weights):
        print(f"  {name:10s} {w.mean() * 100:5.1f}% of the ground")


if __name__ == "__main__":
    main()
