# The Devils in the Details

Design notes for a Fallout 4 mod set on Fort Bragg, NC, in the 1-504 PIR barracks area as it was in the early 1990s.
Started 2026-10-22. Nothing here is final.

## Story

### The premise

Two hundred years after the bombs, the soldiers at Fort Bragg are still there. The garrison's last
order was to **hold the post until relieved**. Nobody came. The descendants kept the order, along with
drill, rank and the regulations, which by now are close to a religion.

They protect the Sandhills from the **raiders and super mutants who attack regularly**. In return
they take a **tithe**: food, water and recruits. Whether that's protection or a racket depends on who
you ask.

**The question the mod asks:** the settlers hate the soldiers, but would they survive without them?

### The soldiers ("the Devils")

- Descendants of the pre-war garrison. Locals call them the **Devils**, after the 504th's WWII
  nickname, "Devils in Baggy Pants", half in fear and half in respect.
- Disciplined, well armed, short of people. Every year they need more food and more recruits
  to hold the line.
- They honestly believe they're the only thing between the settlers and death. They may be
  right.
- They need: someone to show both a decent officer and a hard one. A **reform-minded officer**
  who thinks the tithe has become extortion; a **hardliner** who thinks the settlers owe them
  everything.

### The settlers

- Survivors from Fayetteville and the farms around it (exact home still to decide: Fayetteville,
  the farms, or the old family housing on post).
- They resent the tithe, which keeps growing; conscription, which takes their children; and the
  curfew and checkpoints.
- They're also raided constantly, and the soldiers are what stops the worst of it. Some know it.
- They need: a **moderate leader** who wants a fairer deal, and a **hard core** who wants the
  soldiers gone whatever the cost.

### Raiders and super mutants

Not a side to choose: a constant pressure. Regular attacks on the farms and the post are what make
the soldiers necessary, and what make the player's choice cost something. Whatever the ending,
the raids continue: whoever is left has to deal with them.

### The player's hook

**Nate is a pre-war Army veteran: the only living person with valid 2077 military credentials.**

- Something on the post still recognizes an active-duty ID: the **armory**, a sealed bunker, or
  the automated defenses (to decide). Suddenly both sides need the player.
- Unlocking it for the soldiers makes them unstoppable. Giving it to the settlers flips the
  balance. Or the player can destroy it.
- **Why go to North Carolina:** a military radio signal or a recall order addressed to Nate's
  service number, picked up in Boston.

### Story shape

1. **Arrival.** Both sides are neutral. Small jobs for each; learn how they see things.
   Witness a raid, and see what the soldiers do (and what they charge for it).
2. **Rising tension.** Something forces the issue: a tithe raid on a farm, an ambush on a patrol,
   a missing recruit.
3. **The choice.** Help one side; **the other becomes hostile**.
4. **The ending.** The armory decides who wins, or how it ends.
5. **Optional third path.** Speech checks bring the reform officer and the moderate settler leader
   together for a negotiated peace: a fairer tithe, volunteers instead of conscription.

### Consequences to show

- **Side with the soldiers:** the settlers are safe from raids and live under the Devils for good.
  Hardliner or reformer in charge changes how that feels.
- **Side with the settlers:** they're free, and the raids get worse. Can they hold? Maybe the
  player has to help them build defenses, or maybe some farms are lost.
- **Negotiated peace:** the raids continue, but now the two sides face them together.

### Open questions

- Should the soldiers lean sympathetic, threatening, or truly balanced? (Leaning: balanced, with
  the raids making the soldiers' case for them.)
- Is the hook tied to Nate's past, or is the player a stranger passing through?
- Where do the settlers live?
- What exactly is locked behind the credentials?
- How does the player travel between Boston and Bragg (vertibird, train, boat, a long walk)?

## Scope (to keep it finishable)

- One post area (the map below) plus one settler settlement.
- Two key interiors: the headquarters building and the company barracks. Every other barracks
  has a locked or sealed door.
- Four or five quests.
- More can be added later.

## Building it

### Factions

- **New factions; never edit the Gunners faction.** Copy the Gunners' NPC templates, outfits and
  leveled lists into new records, for the soldiers and the settlers.
- Both start **neutral to the player**. A script on the quest stage where the player picks a side
  makes the other faction an enemy (like the Brotherhood and Institute split in vanilla).
- Restyle the soldiers toward early-90s battle dress: woodland camouflage, the old helmet,
  parachute badges.

### The map

- Area: the 1-504 barracks area as outlined, about 1.2 x 1.9 km, plus 150 m margin:
  **26 x 38 cells** (x -13 to 12, y -19 to 18), true scale.
- Terrain: USGS 3DEP 1 m lidar, 70 to 128 m elevation (57 m of relief).
  `scripts/make_heightmap.py` makes the 16-bit heightmap (`--exaggerate` for taller hills).
- Layout: USGS DOQ from **NAPP photo of 1993-02-23**, 1 m, in `data/doq_raw/`.
  `scripts/make_overlay.py` lines it up with the cell grid; `out/aerial_grid.png` shows each cell's
  Creation Kit coordinates.
- Still to do: find a heightmap importer that works with Fallout 4 and make the script write its
  format.

### Buildings

- **Exterior:** a NIF shell (walls and roof, simple box collision), reused for every identical
  barracks. Split large buildings into a few pieces for occlusion and precombines. A simple LOD
  version for distance (xLODGen).
- **Interior:** a load door (teleport) to a separate interior cell, built from modular kit pieces.
  Room bounds and portals in the Creation Kit are only for occlusion inside big interiors; they don't
  load anything.
- Textures through `.bgsm` material files.
- Tools: **PyNifly** for Blender (version 28.1.0 or later fixed Fallout 4 collision export; re-export
  anything made with earlier versions). Look for the old barracks NIF on the other drives.
