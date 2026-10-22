# The Devils in the Details

A Fallout 4 mod set on Fort Bragg, NC, in the 1-504 PIR barracks area of the early 1990s.
The story and plan are in [DESIGN.md](DESIGN.md).

## Map scripts

Need Python 3.12 with `rasterio numpy pillow requests pyproj`.

```
python scripts/make_heightmap.py [--exaggerate 1.5]
python scripts/make_overlay.py data/doq_raw/O3507956.SES.811019.tif
```

- `make_heightmap.py` downloads USGS 3DEP elevation for the area and writes a 16-bit heightmap
  sized to whole Fallout cells, with a shaded preview, to `out/`.
- `make_overlay.py` lines aerial photos up with the cell grid and labels each cell with its
  Creation Kit coordinates.

`data/` (downloads) and `out/` (generated) aren't in git. The 1993 aerial photo is USGS DOQ
`O3507956.SES` (Overhills SE quarter, NAPP 6136-187, 1993-02-23), from EarthExplorer
(Aerial Imagery > DOQ); extract the `.tif` into `data/doq_raw/`.
