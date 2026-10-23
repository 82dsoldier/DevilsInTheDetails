"""Download 3DEP elevation for the area and turn it into a Fallout 4 heightmap.

    python scripts/make_heightmap.py                     # true scale, no exaggeration
    python scripts/make_heightmap.py --exaggerate 2      # hills twice as tall
    python scripts/make_heightmap.py --dds-size 832x1216 # if the Creation Kit asks for another size

The area is the four corners in AREA (lat, lon), plus MARGIN_M on every side,
squared off to north and rounded out to whole Fallout cells.

Fallout 4 scale: 128 game units = 6 ft, so one unit is 0.0142875 m. A cell is
4096 units (58.52 m) with 33 x 33 height points (one every 128 units, 1.8288 m);
neighbouring cells share their edge points, so N cells need N*32 + 1 points.

Writes to out/:
  dem_utm.tif          the downloaded elevation, metres, UTM 17N, 1 m pixels
  heightmap16.png      16-bit grayscale, one pixel per height point, north up
  heightmap16.raw      the same, little-endian 16-bit, no header
  heightmap.dds        for the Fallout 4 Creation Kit's importer: one channel of 32-bit float
                       (DXGI R32_FLOAT), 0 at the lowest point and 1 at the highest, north up
  heightmap.json       how pixel values map to metres and game units, and the cell grid
  preview.png          shaded relief with the area's outline, for checking by eye
"""
import argparse
import json
import math
import struct
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from pyproj import Transformer
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# The corners as given: degrees, minutes, seconds (N, W).
AREA_DMS = [
    ((35, 8, 20.44), (79, 2, 14.69)),
    ((35, 8, 28.71), (79, 1, 38.60)),
    ((35, 8, 5.81), (79, 1, 26.89)),
    ((35, 7, 28.13), (79, 1, 48.33)),
]
MARGIN_M = 150                 # extra ground around the area, so its edges aren't the world's edges
UNIT_M = 0.0142875             # one Fallout 4 game unit in metres
CELL_UNITS = 4096
POINT_UNITS = 128
CELL_M = CELL_UNITS * UNIT_M   # 58.5216
POINT_M = POINT_UNITS * UNIT_M # 1.8288
UTM = "EPSG:32617"             # UTM zone 17N: metres, fits North Carolina
EXPORT_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"


def dms(d, m, s):
    return d + m / 60 + s / 3600


def corners_utm():
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    return [to_utm.transform(-dms(*lon), dms(*lat)) for lat, lon in AREA_DMS]


def download_dem(bounds, path):
    """3DEP's best available elevation (1 m lidar here) for the bounds, in UTM, 1 m pixels."""
    minx, miny, maxx, maxy = bounds
    width, height = int(round(maxx - minx)), int(round(maxy - miny))
    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}", "bboxSR": 32617, "imageSR": 32617,
        "size": f"{width},{height}", "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation", "noData": -9999, "f": "image",
    }
    r = requests.get(EXPORT_URL, params=params, timeout=300)
    r.raise_for_status()
    if not r.content.startswith((b"II*\x00", b"MM\x00*")):
        raise SystemExit(f"3DEP didn't return a GeoTIFF: {r.content[:300]!r}")
    path.write_bytes(r.content)


def write_dds_r32f(path, data):
    """A DDS with the DX10 header holding one channel of 32-bit float (DXGI_FORMAT_R32_FLOAT),
    the format the Fallout 4 Creation Kit's heightmap importer reads. No mipmaps."""
    h, w = data.shape
    header = struct.pack(
        "<4s7I44s8I5I",
        b"DDS ", 124,
        0x1 | 0x2 | 0x4 | 0x8 | 0x1000,   # caps, height, width, pitch, pixel format
        h, w, w * 4, 0, 1, bytes(44),
        32, 0x4, int.from_bytes(b"DX10", "little"), 0, 0, 0, 0, 0,   # pixel format: FourCC DX10
        0x1000, 0, 0, 0, 0,               # caps: texture
    )
    dx10 = struct.pack("<5I", 41, 3, 0, 1, 0)   # R32_FLOAT, 2D texture, array size 1
    with open(path, "wb") as f:
        f.write(header + dx10)
        f.write(np.ascontiguousarray(data, dtype="<f4").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exaggerate", type=float, default=1.0, help="vertical scale (1 = true)")
    ap.add_argument("--redownload", action="store_true")
    ap.add_argument("--dds-size", help="WxH for heightmap.dds, if the Creation Kit wants a size "
                    "other than one pixel per height point")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    pts = corners_utm()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    # Whole cells, centred on the area plus margin.
    w_m = max(xs) - min(xs) + 2 * MARGIN_M
    h_m = max(ys) - min(ys) + 2 * MARGIN_M
    cells_x, cells_y = math.ceil(w_m / CELL_M), math.ceil(h_m / CELL_M)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    west = cx - cells_x * CELL_M / 2
    north = cy + cells_y * CELL_M / 2
    nx, ny = cells_x * 32 + 1, cells_y * 32 + 1

    # Download a little beyond the grid so resampling has data at the edges.
    pad = 10
    dl_bounds = (math.floor(west - pad), math.floor(north - cells_y * CELL_M - pad),
                 math.ceil(west + cells_x * CELL_M + pad), math.ceil(north + pad))
    dem_path = OUT / "dem_utm.tif"
    if args.redownload or not dem_path.exists():
        print("Downloading 3DEP elevation...")
        download_dem(dl_bounds, dem_path)

    # Resample onto the height-point grid. Points sit on cell corners, so the
    # first point is at (west, north) exactly: grid pixels are centred there.
    grid = np.full((ny, nx), np.nan, dtype=np.float32)
    grid_transform = from_origin(west - POINT_M / 2, north + POINT_M / 2, POINT_M, POINT_M)
    with rasterio.open(dem_path) as src:
        src_res = src.res
        reproject(
            source=rasterio.band(src, 1), destination=grid,
            dst_transform=grid_transform, dst_crs=UTM, src_nodata=-9999, dst_nodata=np.nan,
            resampling=Resampling.average,   # averages the 1 m lidar under each 1.83 m point
        )
    missing = int(np.isnan(grid).sum())
    if missing:
        print(f"Warning: {missing} points had no elevation; filled with the lowest value.")
        grid = np.where(np.isnan(grid), np.nanmin(grid), grid)

    base = float(grid.min())
    rel_m = (grid - base) * args.exaggerate          # metres above the lowest point
    rel_units = rel_m / UNIT_M
    top_units = float(rel_units.max())
    scale = 65535 / top_units if top_units > 0 else 1
    h16 = np.round(rel_units * scale).astype(np.uint16)

    Image.fromarray(h16).save(OUT / "heightmap16.png")
    h16.astype("<u2").tofile(OUT / "heightmap16.raw")

    norm = (rel_units / top_units if top_units > 0 else rel_units).astype(np.float32)
    dds_size = (nx, ny)
    if args.dds_size:
        dds_size = tuple(int(v) for v in args.dds_size.lower().split("x"))
        norm = np.asarray(Image.fromarray(norm, mode="F").resize(dds_size, Image.BILINEAR))
    write_dds_r32f(OUT / "heightmap.dds", norm)

    meta = {
        "cells": [cells_x, cells_y],
        "points": [nx, ny],
        "point_spacing_m": POINT_M,
        "cell_size_m": CELL_M,
        "utm_crs": UTM,
        "north_west_corner_utm": [west, north],
        "lowest_elevation_m": base,
        "highest_elevation_m": float(grid.max()),
        "relief_m": float(grid.max()) - base,
        "exaggeration": args.exaggerate,
        "height_range_game_units": top_units,
        "game_units_per_pixel_step": 1 / scale,
        "pixel_to_game_units": "units = pixel * game_units_per_pixel_step, above the lowest point",
        "dds_size": list(dds_size),
        "ck_import_min_height": 0,
        "ck_import_max_height": round(top_units),
        "source_resolution_m": list(src_res),
    }
    (OUT / "heightmap.json").write_text(json.dumps(meta, indent=2))

    # Shaded relief preview (light from the north-west), with the area outlined.
    dzdy, dzdx = np.gradient(rel_m, POINT_M)
    slope = np.arctan(np.hypot(dzdx, dzdy) * 3)    # exaggerated for the picture only
    aspect = np.arctan2(-dzdx, dzdy)
    az, alt = math.radians(315), math.radians(45)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    tint = (rel_m - rel_m.min()) / max(np.ptp(rel_m), 1e-6)
    rgb = np.stack([
        (0.35 + 0.45 * tint) * 255, (0.55 + 0.25 * tint) * 255, (0.35 + 0.1 * tint) * 255,
    ], axis=-1) * np.clip(shade, 0, 1)[..., None]
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)
    outline = [((x - west) / POINT_M, (north - y) / POINT_M) for x, y in pts]
    draw.polygon(outline, outline=(255, 60, 60))
    for i in range(1, cells_x):
        draw.line([(i * 32, 0), (i * 32, ny)], fill=(0, 0, 0, 40))
    for j in range(1, cells_y):
        draw.line([(0, j * 32), (nx, j * 32)], fill=(0, 0, 0, 40))
    img.save(OUT / "preview.png")

    print(f"{cells_x} x {cells_y} cells ({cells_x * CELL_M:.0f} x {cells_y * CELL_M:.0f} m), "
          f"{nx} x {ny} height points")
    print(f"Elevation {base:.1f} to {grid.max():.1f} m (relief {grid.max() - base:.1f} m), "
          f"exaggeration {args.exaggerate}: {top_units:.0f} game units top to bottom")
    print(f"heightmap.dds is {dds_size[0]} x {dds_size[1]}; in the Creation Kit's import, "
          f"min height 0, max height {top_units:.0f}")


if __name__ == "__main__":
    main()
