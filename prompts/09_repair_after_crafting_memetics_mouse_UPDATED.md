Review and repair the implementation after salvage/crafting, memetics, and mouse UI changes.

Do not add major new features.

Run:

python -m py_compile revamp/*.py revamp/data/*.py

Then run:

python main_revamp.py

Fix the project until it starts and the core loop works.

============================================================
CHECK PROCEDURAL INTEGRATION REGRESSIONS
============================================================

Verify:
- risk/reward metadata still maps to consequences
- safehouse possible_clue_sources still work
- objective.required_tags validation still works
- rumor tags/weight/floor_min metadata still works
- clue chain ordering still works
- known_clues / known_facts save/load still works
- item damaged state persists and has gameplay impact

============================================================
CHECK SALVAGE / CRAFTING
============================================================

Fix:
- missing imports
- broken material save/load
- old saves lacking materials
- salvageable entities not persisting stripped/depleted state
- parser not recognizing Polish salvage/crafting commands
- validation allowing nonexistent materials
- validation allowing salvaging nonexistent objects
- crafting consuming materials but not producing item
- crafting producing item without consuming materials
- crafted items not serializing
- damaged/unstable crafted items not being handled
- safehouse salvage not causing consequences
- UI not showing materials
- crashes when entity has no salvage_table
- infinite salvage farming

Smoke test:
- loot corpse
- salvage furniture
- salvage tech object
- craft simple trap/tool
- save/load
- verify state persists

============================================================
CHECK MEMETIC SYSTEM
============================================================

Fix:
- Ollama JSON not mapping to seed_belief intent
- parser not recognizing Polish memetic commands
- validator allowing belief seed with no target/channel
- belief seed not saving/loading
- belief propagation crashing
- rumor creation bypassing rumor metadata
- encounter selection ignoring active belief seeds
- belief effects applying too often
- belief effects revealing hidden mechanics
- sponsor/narrator spam

Smoke test:
- with machine/crawler target, attempt belief seed
- without target/channel, verify rejection
- successful roll creates belief seed
- time passage processes seed
- save/load preserves seed

============================================================
CHECK MOUSE UI
============================================================

Fix:
- click targets not cleared/rebuilt per frame
- wrong commands submitted by buttons
- mouse actions bypass parser/validator
- hidden objects shown as clickable
- disabled buttons still clickable
- right-click/context menu crashes
- text input broken after mouse changes
- typed commands no longer work
- save/load buttons not working
- scroll/log clicks interfering with actions

Smoke test:
- click look
- click exit
- click visible object inspect
- click salvage action if available
- click materials
- typed commands still work

============================================================
FINAL REPORT
============================================================

Report:
1. What was broken.
2. What was fixed.
3. Which systems are now working.
4. Remaining limitations.
5. Exact run command.
