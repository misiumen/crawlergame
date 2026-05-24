# Prompt 1 — Integrate content templates into generation

You are working on the revamp branch.

Goal:
Start using the new content templates in the existing revamp systems.

Inspect first:
- revamp/procgen.py
- revamp/floor.py
- revamp/room.py
- revamp/entity.py
- revamp/encounters.py
- revamp/safehouses.py
- revamp/crawlers.py
- revamp/items.py
- revamp/narrator.py
- revamp/data/*.py

Tasks:
1. Add loader/helper functions in procgen.py or a new content_loader.py.
2. Use `encounter_templates.py` when creating room encounters.
3. Use `npc_templates.py` when generating crawler/NPC personalities.
4. Use `safehouse_templates.py` when generating safehouse rooms.
5. Use `rumor_templates.py` when generating rumors.
6. Use `item_templates.py` for problem-solving items.
7. Use `floor_objective_templates.py` to generate at least one Floor 1 exit objective.
8. Use `failure_templates.py` in resolution/narration for partial/failure outcomes.

Important:
- Do not attempt to integrate every template perfectly.
- Integrate enough for Floor 1 vertical slice.
- Preserve existing data structures where possible.
- No crashes if content key is missing.
- Avoid circular imports.

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Report:
- which templates are now used
- what remains static
- next content gaps
