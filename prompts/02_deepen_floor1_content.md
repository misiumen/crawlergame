# Prompt 2 — Deepen Floor 1 content

Use the new content bible and templates to deepen Floor 1.

Do not rewrite the engine.

Goals:
- Floor 1 should feel like a persistent place, not a route.
- Add more sensory Polish descriptions.
- Hide room types from the player.
- Add rumors that reveal partial information.
- Add at least 3 ways to make progress toward the exit.
- Add at least 5 meaningful non-combat solutions.
- Add crawler/social content that can be ignored, helped, attacked, or traded with depending on context.

Tasks:
1. Expand Floor 1 to 15-20 rooms if not already.
2. Ensure at least:
   - 1 cafe or bathroom safehouse,
   - 1 black-market or kiosk-like safe room,
   - 2 crawler encounters,
   - 2 monster encounters avoidable by non-combat,
   - 1 locked or blocked route,
   - 1 secret/hidden route,
   - 1 major exit objective.
3. Add room hints instead of visible room types.
4. Make `look` useful and cheap/free.
5. Make `search` cost time and reveal more.
6. Add at least 20 new Polish ambient lines.
7. Add at least 10 rumors with truth values.

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Report:
- new rooms/content
- exit paths
- non-combat solutions
- known limitations
