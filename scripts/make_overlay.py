"""Line up aerial photos with the heightmap's cell grid, for placing buildings.

    python scripts/make_overlay.py data/doq_raw/O3507956.SES.811019.tif [more.tif ...]

Run make_heightmap.py first (this reads out/heightmap.json for the grid).
Several photos are combined, the first one listed winning where they overlap.

Writes to out/:
  aerial_grid.tif     the photo(s) on the heightmap's area, 1 m pixels, georeferenced (UTM 17N)
  aerial_grid.png     the same with the cell grid, cell numbers and the area outline drawn on
  cells.json          what the cell numbers mean
Cell numbers: cell (0, 0) is the one just south-east of the grid's centre; x grows
east and y grows north, as in the Creation Kit.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_heightmap import corners_utm, OUT, UTM   # noqa: E402

PX_M = 1.0   # output pixel size


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    meta = json.loads((OUT / "heightmap.json").read_text())
    cells_x, cells_y = meta["cells"]
    cell_m = meta["cell_size_m"]
    west, north = meta["north_west_corner_utm"]
    w = int(round(cells_x * cell_m / PX_M))
    h = int(round(cells_y * cell_m / PX_M))
    transform = from_origin(west, north, PX_M, PX_M)

    mosaic = np.zeros((h, w), dtype=np.uint8)
    have = np.zeros((h, w), dtype=bool)
    for path in sys.argv[1:]:
        img = np.zeros((h, w), dtype=np.uint8)
        with rasterio.open(path) as src:
            reproject(source=rasterio.band(src, 1), destination=img, dst_transform=transform,
                      dst_crs=UTM, src_nodata=None, dst_nodata=0, resampling=Resampling.bilinear,
                      init_dest_nodata=True)
            # Where the photo actually covers (0 can also be real black, so use its footprint).
            cover = np.zeros((h, w), dtype=np.uint8)
            reproject(source=np.ones((src.height, src.width), dtype=np.uint8), destination=cover,
                      src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                      dst_crs=UTM, dst_nodata=0, resampling=Resampling.nearest)
        take = (cover > 0) & ~have
        mosaic[take] = img[take]
        have |= take

    with rasterio.open(OUT / "aerial_grid.tif", "w", driver="GTiff", width=w, height=h, count=1,
                       dtype="uint8", crs=UTM, transform=transform, nodata=None) as dst:
        dst.write(mosaic, 1)

    rgb = np.stack([mosaic] * 3, axis=-1)
    rgb[~have] = (90, 70, 110)          # no photo here
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    x0, y_top = -(cells_x // 2), cells_y // 2 - 1
    for i in range(cells_x + 1):
        x = i * cell_m / PX_M
        draw.line([(x, 0), (x, h)], fill=(255, 220, 0), width=1)
    for j in range(cells_y + 1):
        y = j * cell_m / PX_M
        draw.line([(0, y), (w, y)], fill=(255, 220, 0), width=1)
    for i in range(cells_x):
        for j in range(cells_y):
            draw.text((i * cell_m / PX_M + 3, j * cell_m / PX_M + 2), f"{x0 + i},{y_top - j}",
                      fill=(255, 220, 0), font=font)
    outline = [((x - west) / PX_M, (north - y) / PX_M) for x, y in corners_utm()]
    draw.polygon(outline, outline=(255, 50, 50), width=3)
    img.save(OUT / "aerial_grid.png")

    (OUT / "cells.json").write_text(json.dumps({
        "cells": [cells_x, cells_y],
        "x_range": [x0, x0 + cells_x - 1],
        "y_range": [y_top - cells_y + 1, y_top],
        "cell_size_m": cell_m,
        "north_west_corner_utm": [west, north],
        "note": "cell (x, y) covers UTM east west + (x - x_min) * cell_size_m, "
                "north edge at north - (y_max - y) * cell_size_m",
        "photos": sys.argv[1:],
        "coverage_percent": round(100 * have.mean(), 1),
    }, indent=2))
    print(f"{w} x {h} px, {100 * have.mean():.1f}% covered by photos; "
          f"cells x {x0}..{x0 + cells_x - 1}, y {y_top - cells_y + 1}..{y_top}")


if __name__ == "__main__":
    main()
