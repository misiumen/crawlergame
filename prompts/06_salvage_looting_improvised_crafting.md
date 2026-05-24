# Prompt 06 — Complete salvage, looting and improvised crafting

Use this after the procedural content direction is in place.

You are working on the `main` branch of the CRAWL PROTOCOL revamp.

Goal:
Implement a complete DCC-style salvage, looting and improvised crafting system.

The player should be able to:
- search corpses, containers and rooms
- loot portable items
- strip bodies or objects for parts
- harvest monster/crawler remains where context allows
- dismantle furniture, cameras, machines, bathroom fixtures, doors, vending machines and debris
- gain materials
- craft known recipes
- improvise tools, weapons, traps, disguises, distractions and repairs from material tags

Do not rewrite the whole game.
Build on the existing architecture:
- affordances.py
- validation.py
- resolution.py
- consequences.py
- parser_core.py
- character.py
- inventory.py / items.py if present
- entity.py
- room.py
- save_load.py
- ui.py
- data/item_templates.py
- data/entity_templates.py

Also use these new data files if present:
- revamp/data/salvage_tables.py
- revamp/data/recipe_templates.py

## Required new modules

Create:
- revamp/materials.py
- revamp/crafting.py

If needed:
- revamp/data/salvage_tables.py
- revamp/data/recipe_templates.py

## Materials

Add material storage to the character:

character.materials: dict[str, int]

Persist it in save/load.
Old saves without materials must load safely.

Materials must have tags, not just names.

Use materials from `salvage_tables.py` and define MaterialDef in `materials.py`.

## Entity integration

Update entities/templates so common world objects can be searched/looted/salvaged/harvested:
- furniture
- corpses
- monster remains
- crawler corpses
- crates
- lockers
- cameras
- terminals
- vending machines
- bathroom fixtures
- medical cabinets
- electrical panels
- kitchen equipment
- debris

Each salvageable entity needs:
- salvage_table
- salvage_state
- remaining_salvage_uses or depleted flag
- tags
- affordances

No infinite farming.

## Action distinction

Implement separate handling for:

1. search / przeszukaj
   Reveals hidden items/info.

2. loot / lootuj / ograb
   Takes portable items.

3. strip / rozbierz
   Removes clothing/equipment/useful parts.

4. salvage / zdemontuj / odzyskaj części
   Breaks down object into materials.

5. harvest / pozyskaj
   Organic salvage from corpses/monsters.

6. craft / zrób / skonstruuj / improwizuj
   Creates known or improvised item.

## Parser

Update parser aliases for Polish and English:

Polish:
- lootuj, ograb, przeszukaj, rozbierz, rozmontuj, zdemontuj, przerób, odzyskaj, pozyskaj, zbierz części, potnij, rozbij, wyłam, wyrwij, zbuduj, skonstruuj, zrób, zrob, craftuj, skleć, improwizuj, połącz, polacz, napraw, wzmocnij, zrób pułapkę

English:
- loot, strip, search, salvage, harvest, dismantle, disassemble, deconstruct, break down, cut apart, pry open, recover parts, scavenge, craft, improvise, combine, build, repair, reinforce, make trap

Parser should return ActionIntent with:
- intent: search/loot/strip/salvage/harvest/craft/improvise
- targets
- tool
- materials mentioned
- desired_outcome
- confidence

## Validation

Validation must reject:
- salvaging nonexistent objects
- harvesting nonexistent bodies
- crafting without materials
- crafting impossible combinations
- looting private/safehouse property without consequence handling
- repeated salvage on depleted object

Validation should allow:
- tag-based improvised crafting if material tags fit desired outcome

## Crafting

Implement known recipes and tag-based improvised crafting.

Known recipes:
- improvised_bandage
- shiv
- tripwire
- shock_trap
- smoke_bottle
- armor_patch
- bait_bundle

Improvised categories:
- weapon
- trap
- distraction
- armor
- tool
- repair
- chemical
- bait
- disguise
- utility

Quality:
- crude
- unstable
- decent
- clever
- excellent

Quality depends on roll result.

## Fail forward

Critical success:
- better item, less waste, audience/narrator bonus

Success:
- normal item

Partial success:
- item is flawed/unstable/noisy or takes extra time

Failure:
- time/material loss, no item or weak flawed item

Critical failure:
- injury, noise, alarm, shock, fire, chemical splash, sponsor attention

## Consequences

Apply:
- add materials
- consume materials
- add crafted items
- mark entity stripped/depleted/destroyed
- add time
- add noise
- apply risk condition
- adjust NPC/crawler reactions when looting bodies in public
- safehouse property theft consequences
- affinity gains

## UI

Add:
- materials view
- crafting help
- salvage help
- log recent salvage/crafting results
- show depleted/stripped state when inspecting objects

Commands:
- materiały / materialy / materials
- pomoc craftingu / craft help
- pomoc odzyskiwania / salvage help

## Testing

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Smoke-test:
1. loot/search corpse
2. strip/harvest corpse if available
3. salvage furniture
4. salvage tech object
5. try salvaging nonexistent wires and verify rejection
6. craft simple trap/tool
7. save/load and verify materials/crafted items/entity depletion persist

Report changed files and limitations.
