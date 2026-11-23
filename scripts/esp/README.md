# Plugin tools

Python that reads and edits `DevilsInTheDetails.esp` directly, with the Creation Kit closed.
Each tool reads one plugin and writes another (`python esp_x.py in.esp out.esp`); back up first,
then copy the result over the plugin in the game's `Data` folder.

Most of these were run once, to make a change that's now in the plugin, and are kept as the
record of how it was made (DESIGN.md names several). The ones to know:

- **`esp_restore_npcs.py in.esp known_good.esp out.esp`**: run after **every** Creation Kit
  save. The CK rewrites the two paratrooper bases (their race becomes SynthGen2RaceValentine,
  among other recalculations); this puts their whole records back from a plugin from before.
- **`esp_navflat.py in.esp out.esp NAVM_FID FLOOR_Z`**: lays a navmesh's vertices on a floor.
- **`esp_navwrite.py`**: writes the C-130 cabin's navmesh (a flat grid over the whole floor).
- **`esp_paving.py`**: Hanscom's graded terrain, paving and buildings into the plugin, from
  `out/hanscom/` (`make_hanscom_paving.py`, `make_hanscom_buildings.py`).
- **`esp_edge_door.py`**: the road between the Commonwealth and Hanscom, a pair of linked load
  doors (vanilla junk-wall gates): one on the elevated highway north of Lexington, at the map's
  border (overriding the Commonwealth's world record, without its offset tables, and its
  persistent cell), one where Langley Road leaves Hanscom's south edge. Run once.
- **`esp_roads.py`**: Hanscom's streets into the plugin (`out/hanscom/roads.json`), the terrain
  they regraded, and fresh bounds for the regenerated paving and buildings. Safe to run again.

The libraries:

- `esplib.py`: parse a plugin into groups and records, edit subrecords, write it back (group
  sizes recomputed; compressed records handled).
- `vmadlib.py`: script data (VMAD): parse, build, object arrays.
- `esmrec.py`, `esmscan.py`: read records from `Fallout4.esm`.
- `landh.py`: terrain heights from a worldspace's LAND records.

Paths in some tools are the author's (the repo at `C:/source/repos/BraggMap`, the game at
`C:/Steam/steamapps/common/Fallout 4`); change them to yours.
