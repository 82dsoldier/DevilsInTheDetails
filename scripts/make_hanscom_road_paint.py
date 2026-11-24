"""Hanscom's streets as paint on the terrain: how much of vanilla's asphalt (LAsphalt01) each
terrain point gets, for scripts/esp/esp_road_paint.py.

The streets were meshes on the ground (make_hanscom_paving.py's Road_ models), their edges sunk
into it; where the ground beside a street fell away, the sunk edge stood as a wall with its
texture stretched down it (the author, 2026-11-24). Painted, a street can't stand off the ground.

Same layout as the meshes: make_hanscom_paving.py's streets (OSM, by class, off the field's
paving). Each point is fully asphalt inside a street by more than half a point's spacing, none
outside by more than that, and in between by its distance to the edge, so a street's edge is
a blend about one point (1.8 m) wide.

    python scripts/make_hanscom_road_paint.py

Writes out/hanscom/road_paint.npy: float32, the heightmap's points (north row first), 0 to 1.
"""
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import CELL_UNITS, POINT_UNITS, out_dir                    # noqa: E402
import make_hanscom_paving as hp                                               # noqa: E402


def main():
    out = out_dir(hp.AREA)
    meta = json.loads((out / "heightmap.json").read_text())
    to_utm = Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True)
    terrain = hp.Terrain(out)
    world = box(terrain.x0, terrain.y1 - terrain.cells[1] * CELL_UNITS,
                terrain.x0 + terrain.cells[0] * CELL_UNITS, terrain.y1)
    areas = {}
    for mat, poly in hp.paved_areas(json.loads((out / "osm.json").read_text()), to_utm).items():
        g = shapely.transform(poly, lambda p: np.column_stack(terrain.game(p[:, 0], p[:, 1])))
        areas[mat] = g.intersection(world)
    roads = hp.streets(out, terrain, to_utm, areas, world)
    shapely.prepare(roads)
    xs, ys = np.meshgrid(np.arange(terrain.nx) * POINT_UNITS + terrain.x0,
                         terrain.y1 - np.arange(terrain.ny) * POINT_UNITS)
    near = shapely.dwithin(roads, shapely.points(xs, ys), POINT_UNITS)
    paint = np.zeros(xs.shape, np.float32)
    px, py = xs[near], ys[near]
    inside = shapely.contains_xy(roads, px, py)
    edge = roads.boundary
    d = shapely.distance(edge, shapely.points(px, py))
    signed = np.where(inside, d, -d)
    paint[near] = np.clip(0.5 + signed / POINT_UNITS, 0, 1)
    np.save(out / "road_paint.npy", paint)
    print(f"{(paint > 0).sum()} points painted, {(paint >= 1).sum()} fully; grid {paint.shape}")


if __name__ == "__main__":
    main()
