# Dungeon Kraulem — Godot port (Phase 0 scaffold)

Board-first tactical roguelike. Port of the pygame game in `../dungeon_kraulem`.
Full plan: `../docs/GODOT_PORT_PLAN.md`. UI spec: the `../_mockup_*.png` / `../_sys_*.png` frames.

## Structure
```
project.godot         autoloads + window config
data/                 content JSON (generated — do not hand-edit)
autoload/  Events.gd  signal bus (sim -> presentation)
           Data.gd    loads data/*.json
           Game.gd    run state + mode (explore/combat)
           rng.gd     single seeded RNG
sim/       tags.gd    tag->property inference (systemic foundation)
                      (combat.gd, systemic.gd, crafting.gd, floorgen.gd ... land here in Phases 1-5)
scenes/    Boot.tscn  Phase 0 smoke test (data load + tag inference)
```

## Regenerate content data
From the repo root (where `dungeon_kraulem/` lives):
```
python -m dungeon_kraulem.tools.export_json
```
Writes `godot/data/*.json`. Two structures need a code port, not JSON:
`floor_biomes.FLOOR_BIOMES` and `meta_progression.UNLOCK_CATALOG` (eval closures).

## Hard rule
The **sim core never imports a node.** It takes data in, emits `Events` signals out.
That keeps rules headlessly testable (GUT) and the renderer swappable.

## Status
Phase 0 foundations only. Next: Phase 0.5 (decouple embedded rules in the Python
source) then Phase 1 vertical slice (one tile-combat encounter). See the plan.
