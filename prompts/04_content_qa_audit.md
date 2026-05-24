# Prompt 4 — Content QA and consistency audit

Audit the revamp content.

Do not add new features unless needed for fixes.

Check:
1. Are player-visible strings Polish-first?
2. Are internal keys stable English identifiers?
3. Do room descriptions avoid revealing room type too early?
4. Does Floor 1 support backtracking?
5. Can the player make progress without winning every fight?
6. Are there at least 3 exit/progress paths?
7. Are safehouses useful but not overpowered?
8. Do crawler encounters have at least 2-3 contextual resolutions?
9. Are rumors connected to real rooms/objectives?
10. Does save/load preserve room state, time, known info, and active objectives?

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Produce a report:
- content strengths
- weak spots
- broken links/templates
- missing localization keys
- priority fixes
