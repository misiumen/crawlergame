# Prompt 3 — Improvisation and fail-forward content pass

Improve how the revamp handles improvised player actions.

Do not add new major systems.
Use existing parser, validator, affordances, resolution, consequences, and templates.

Goals:
- More actions should produce interesting partial results.
- Failure should often change the situation, not just say "no".
- Impossible actions should get immersive Polish feedback.
- The game should suggest plausible nearby alternatives when an action is impossible.

Tasks:
1. Use failure_templates.py in resolution/consequences.
2. Add feedback for:
   - no target,
   - target exists but not reachable,
   - wrong tool,
   - hidden object not discovered,
   - action forbidden in safehouse,
   - no matching environmental object.
3. When possible, suggest valid visible affordances:
   Example: no acid here, but there is a loose shelf or wet floor.
4. Add narrator reactions for:
   - creative action,
   - stupid action,
   - partial success,
   - environmental setup,
   - failed social gambit,
   - successful avoidance.
5. Ensure Ollama/parser intent is still validated by real world state.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Manual tests:
- "wepchnij goblina do kwasu" in room without acid
- "rzucam kubkiem w kamerę" with and without mug/camera
- "próbuję przekupić crawlera" with crawler present
- "używam łazienki" outside safehouse/bathroom
