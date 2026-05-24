# Prompt 09 — Repair after crafting/memetics/mouse integration

Do not add new features.

Fix the project so it runs after the salvage/crafting, memetics and mouse-only changes.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Then run:
python main_revamp.py

Fix:
- missing imports
- missing dataclass fields
- old saves without materials/active_beliefs crashing
- entity without salvage_table crashing
- parser intents not mapped
- validation allows nonexistent target/material
- crafting consumes materials incorrectly
- crafted item cannot serialize
- depleted objects reset after save/load
- memetic belief not serializing
- belief evolution crashes when no active floor
- UI button rect crashes
- mouse click duplicates game logic
- mouse-only buttons not using parser pipeline
- safehouse property salvage has no consequence
- Ollama unavailable causes crash
- text input broken after mouse UI changes

Smoke-test:
1. launch game
2. start new game
3. move/look/search
4. click at least one mouse button
5. type a command
6. salvage one object if present
7. craft one simple item if possible
8. seed one belief if valid target exists
9. save/load
10. verify no crash

Report exact fixes and remaining limitations.
