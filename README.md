# The Devils in the Details

A Fallout 4 mod set on Fort Bragg, NC, in the 1-504 PIR barracks area of the early 1990s.
The story and plan are in [DESIGN.md](DESIGN.md).

## Map scripts

Need Python 3.12 with `rasterio numpy pillow requests pyproj`.

```
python scripts/make_heightmap.py [--area bragg_blvd] [--exaggerate 1.5]
python scripts/make_overlay.py [--area bragg_blvd] data/doq_raw/O3507956.SES.811019.tif
```

```
python scripts/make_photo_overlay.py [--area bragg_blvd] [--install "<Fallout 4>/Data"]
```

`make_photo_overlay.py` drapes the 1993 photo over the terrain as a reference mesh for the
Creation Kit. It needs [PyNifly](https://github.com/BadDogSkyrim/PyNifly) (the `io_scene_nifly`
release zip) unpacked to `data/tools/io_scene_nifly`; it runs without Blender.

`--area` picks the worldspace (`barracks`, the default, `bragg_blvd` or `sicily`); each one's files go to `out/<area>/`.

- `make_heightmap.py` downloads USGS 3DEP elevation for the area and writes a 16-bit heightmap
  sized to whole Fallout cells, with a shaded preview, to `out/<area>/`. It also writes
  `heightmap.dds` (32-bit float, one channel) for the Creation Kit's heightmap import, and prints
  the min and max heights to enter there.
- `make_overlay.py` lines aerial photos up with the cell grid and labels each cell with its
  Creation Kit coordinates.

`data/` (downloads) and `out/` (generated) aren't in git. The 1993 aerial photo is USGS DOQ
`O3507956.SES` (Overhills SE quarter, NAPP 6136-187, 1993-02-23), from EarthExplorer
(Aerial Imagery > DOQ); extract the `.tif` into `data/doq_raw/`.

## License

- **Code** (scripts, Papyrus, xEdit scripts and other tools): [MIT](LICENSE).
- **Art and writing** (models, textures, sounds, the story, dialogue and design notes):
  [Creative Commons Attribution-NonCommercial-ShareAlike 4.0](LICENSE-ART.txt) (CC BY-NC-SA 4.0).
  You may use and change it, with credit, not for profit, and you must share your changes under
  the same license.

Fallout 4 and its assets belong to Bethesda Softworks. This repository contains only original
work; the mod uses the game's own files rather than copying them.
