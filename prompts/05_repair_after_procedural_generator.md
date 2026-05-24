# 05 — Repair after procedural generator/content changes

Use this if the generator/content changes break the game.

Do not add new features.

Fix the project so it runs again.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Then run:
python main_revamp.py

Fix:
- syntax errors,
- missing imports,
- circular imports,
- broken template imports,
- missing metadata fields,
- generator crashes,
- validate_floor false positives,
- save/load errors,
- UI crashes from missing room fields,
- parser/validator crashes from missing entities,
- old hand-built Floor 1 debug mode crashes,
- generated floor missing start/safehouse/exit,
- clues pointing to missing content,
- impossible objective dependency.

Preserve:
- procedural content pool direction,
- template metadata,
- hand-built Floor 1 only as debug/test mode,
- hidden room type design,
- backtracking,
- save/load compatibility for revamp saves where possible.

Report:
- what broke,
- what was fixed,
- what remains fragile,
- exact command to run the game.
