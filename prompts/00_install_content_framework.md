# Prompt 0 — Install content framework

You are working on the `revamp/floor-survival-architecture` branch of CRAWL PROTOCOL.

Goal:
Add a content framework without changing core gameplay yet.

Create/merge these files if they do not exist:
- docs/CONTENT_BIBLE.md
- revamp/data/encounter_templates.py
- revamp/data/npc_templates.py
- revamp/data/rumor_templates.py
- revamp/data/safehouse_templates.py
- revamp/data/item_templates.py
- revamp/data/failure_templates.py
- revamp/data/floor_objective_templates.py
- revamp/data/content_validation.py

Rules:
- Do not rewrite the engine.
- Do not change game loop yet.
- Keep templates data-driven.
- Internal keys in English.
- Player-facing fallback text mostly Polish.
- Keep all files importable.

After adding files, run:
python -m py_compile revamp/*.py revamp/data/*.py

Report:
- files created
- any import/syntax problems
- next integration steps
