# 02b — Integrate procedural Floor 1 generator

Use this after Floor 1 has been redirected into procedural template pools.

Do not create a fixed Floor 1 map.

Goal:
Replace or supplement the hand-built Floor 1 with a procedural generator:

generate_floor(floor_number=1, seed=None)

The generator must create a playable persistent floor using template pools.

## Required generated Floor 1 guarantees

A generated Floor 1 must have:
- 12–20 rooms,
- start room,
- at least 1 safehouse,
- at least 1 cafe/bathroom/lounge/clinic-style neutral location,
- 2–4 monster or hostile encounters,
- 2–4 crawler/NPC encounters,
- at least 1 locked or blocked area,
- at least 1 secret or hidden area,
- at least 1 major obstacle,
- at least 1 exit condition,
- at least 2 possible ways to progress toward the exit,
- backtracking,
- hidden room types,
- room hints instead of revealed room types,
- at least 2 useful clue sources,
- at least 1 false or partial rumor.

## Use template metadata

Select content using:
- tags,
- weight,
- rarity,
- floor_min/floor_max,
- required_room_tags,
- incompatible_tags,
- possible_clues,
- possible_rewards,
- possible_risks,
- possible_resolution_methods.

## Generation steps

Implement or update generator steps:

1. choose floor archetype
2. choose floor theme
3. generate connected graph
4. place start room
5. place required safehouse
6. place objective structure
7. place locked/blocked areas
8. place clue chain
9. place encounters
10. place crawlers/NPCs
11. place environmental objects
12. place loot and rumors
13. validate floor

## Floor archetypes

Add at least these archetypes:
- survival_sprawl
- maintenance_maze
- safehouse_spokes
- trap_infrastructure
- crawler_conflict
- locked_route
- secret_detour

Each archetype should influence:
- graph shape,
- safehouse count,
- encounter density,
- hazard density,
- clue density,
- backtracking density,
- secret chance.

## validate_floor(floor_state)

Add or update validation:

- start exists,
- exit/objective exists,
- all required rooms are reachable,
- safehouse is reachable,
- backtracking exists,
- objective has at least 2 solution paths,
- no clue points to missing content,
- no required key is placed behind its own lock,
- no boss/major obstacle appears immediately after start unless explicitly intended,
- room type is hidden until discovery,
- generated graph is not a pure linear chain unless archetype allows it,
- safehouse is not always in same graph position,
- at least one meaningful non-combat path exists.

## Debug option

Keep existing hand-built Floor 1 as optional debug mode if useful:

USE_HANDMADE_FLOOR_1 = False by default.

If debug flag is True, old vertical slice can load.

## Testing

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Then generate Floor 1 with at least 5 different seeds.

For each seed report:
- room count,
- archetype,
- theme,
- safehouse count,
- objective variant,
- major obstacle,
- whether validation passed,
- summary of solution paths.

Manual smoke-test:
- launch game,
- start new game,
- enter generated floor,
- move between rooms,
- backtrack,
- discover unknown room,
- find safehouse,
- save/load.

Report:
- generator changes,
- validation rules,
- example generated floor summaries for 3 seeds,
- known limitations.
