# Dungeon Kraulem

A galactic reality-TV dungeon crawler (Dungeon Crawler Carl–inspired). This repo
holds **two games** plus the shared design history that connects them:

```
godot/    ← THE GODOT 4 REFACTOR  (the current/new game)
pygame/   ← THE OLD PYGAME GAME    (the original Python build it was ported from)
docs/     ← design docs + UI-spec mockups (shared lineage)
tools/    ← bridge generators: read pygame content, emit godot/sim/*.gd
```

## godot/ — the refactor (active)
A board-first tactical roguelike rebuilt in Godot 4: tile combat with breakable
bodies, tag-driven crafting, sponsors/audience, emergent classes, a konferansjer
narrator, procedural multi-floor descent with route gambling, save/load, full
dialogue trees, and a boss finale. Pure-logic sim core (no nodes) with ~400
headless GUT checks.

- Play: open `godot/project.godot` in Godot 4.6+, or run `godot/builds/DungeonKraulem.exe`.
- Details: `godot/README.md`. Plan + status: `docs/GODOT_PORT_PLAN.md`.

## pygame/ — the original (reference)
The original Python/pygame game (`pygame/dungeon_kraulem/`). Kept as the reference
oracle the port was checked against, and as a place the content (entities, rooms,
recipes, dialogues, narrator lines) still lives in authored form.

- Play: `pygame/PLAY.bat` (or `pygame/DEBUG.bat` for a console).
- Tests: `cd pygame && python _run.py`  (set `SDL_VIDEODRIVER=dummy` headless).
- Build exe: `pygame/build_exe.bat`.

## docs/ and tools/
- `docs/` — design bibles (combat, crafting, memetics, content) + the Godot port
  plan; `docs/mockups/` holds the UI-spec frames.
- `tools/` — the faithful-port bridge: `gen_narrator.py`, `gen_runsummary.py`,
  `gen_meta.py`, `gen_dialogues.py` read from `pygame/dungeon_kraulem/…` and write
  the corresponding `godot/sim/*.gd`. Re-run after changing the pygame content.

> All player-facing text is Polish by design; code and docs are English.
