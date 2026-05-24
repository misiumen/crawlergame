# 04 — Content QA audit for procedural replayability

Do not add major features.
Audit and fix content structure.

Goal:
Verify content supports procedural generation, replayability, and improvisational RPG play.

Inspect:
- docs/CONTENT_BIBLE.md
- revamp/data/*.py
- revamp/procgen.py
- revamp/floor.py
- revamp/room.py
- revamp/game.py
- revamp/validation.py
- revamp/resolution.py
- revamp/consequences.py
- revamp/parser_core.py

## Check for fixed-map assumptions

Find and report:
- hardcoded room IDs,
- hardcoded NPC placement,
- hardcoded exit path,
- single-solution objectives,
- content that only works in one exact room,
- clues that refer to locations that may not exist,
- safehouses assumed to always be in the same place,
- boss/objective dependencies without fallback,
- required key behind its own lock,
- room type revealed before discovery,
- impossible clue chains,
- objective variants with only one resolution,
- templates without metadata,
- templates with no tags,
- templates with no possible risks/rewards,
- templates with no resolution methods.

Convert obvious issues into template-friendly structures when safe.

## Validate template quality

Each major template should have:
- key,
- metadata,
- tags,
- floor range,
- rarity/weight,
- risks,
- rewards,
- possible clues,
- possible resolution methods.

## Validate generated floors if generator exists

Generate at least 5 Floor 1 seeds.

For each:
- validate graph reachability,
- validate safehouse reachability,
- validate objective solvability,
- validate backtracking,
- validate hidden room types,
- validate clue chain,
- validate at least 2 solution paths,
- validate save/load if practical.

## Polish writing quality audit

Check:
- no dry placeholder text in visible content,
- Polish text sounds natural,
- descriptions do not reveal mechanics too directly,
- narrator lines are brief and in tone,
- parser feedback is useful and immersive.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Report:
1. fixed-map assumptions found,
2. template quality issues,
3. generator validation issues,
4. Polish writing issues,
5. fixes made,
6. remaining recommended work.
