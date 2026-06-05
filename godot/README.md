# Dungeon Kraulem — Godot 4 refactor

Board-first tactical roguelike (DCC/litRPG soul). The **new game** — a rework +
port of the old pygame game (now in `../pygame/`). Full plan + status:
`../docs/GODOT_PORT_PLAN.md`. UI spec frames: `../docs/mockups/`.

## Run it
- **Play:** open `project.godot` in Godot 4.6+, or run the built exe
  `builds/DungeonKraulem.exe` (rebuild with `build.bat`).
- **Tests (headless):** `godot --headless --path . -s res://tests/test_<name>.gd`.
  Suites: sim, combat, crafting, body, classes, narrator, meta, floorgen, routes,
  save, dialogue, elements, boss, floor, view.

## Structure
```
project.godot          autoloads + window config
data/                  content JSON (generated from ../pygame — do not hand-edit)
autoload/  Events.gd   signal bus (sim -> presentation)
           Data.gd     loads data/*.json
           Game.gd / rng.gd
sim/                   THE SIM CORE — pure logic, no nodes, GUT-tested:
           board, entity, tags, combat, crafting, rarity, item, box,
           audience, sponsors, classes, class_features, narrator,
           run_summary, meta, dice, floorgen, routes, save, body, floor,
           dialogue (+ dialogue_trees, dialogue_trees_extra)
scenes/    BoardView.gd the playable board (input, draw, animation)
tests/                 headless GUT-style suites
```

## Regenerate content from the pygame source
Some `sim/*.gd` are GENERATED from the Python game (faithful ports of its content)
by the bridge generators in `../tools/`:
```
python ../tools/gen_narrator.py      # -> sim/narrator.gd
python ../tools/gen_runsummary.py    # -> sim/run_summary.gd
python ../tools/gen_meta.py          # -> sim/meta.gd
python ../tools/gen_dialogues.py     # -> sim/dialogue_trees.gd
```
The content JSON in `data/` comes from the pygame export pipeline:
```
cd ../pygame && python -m dungeon_kraulem.tools.export_json
```

## Hard rule
The **sim core never imports a node.** It takes data in, returns event dicts /
emits `Events` signals out. That keeps the rules headlessly testable and the
renderer swappable.

## Status
Phases 0–6 complete (vertical slice → exploration → crafting → bodies → DCC soul
→ procedural floors/descent/save/routes/dialogue). See `../docs/GODOT_PORT_PLAN.md`.
