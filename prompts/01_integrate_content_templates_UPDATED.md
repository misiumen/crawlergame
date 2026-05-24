# 01 — Integrate content templates as procedural pools

You are working on the `revamp/floor-survival-architecture` branch.

Do not rewrite the engine.

Goal:
Integrate content template files as procedural content pools, not fixed-map content.

Important correction:
All content templates must be designed for procedural selection.

Do not assume:
- fixed room order,
- fixed NPC placement,
- fixed safehouse location,
- fixed objective path,
- fixed key placement,
- fixed exit route.

Every template should include metadata useful for generation:
- key
- floor_min
- floor_max
- tags
- weight
- rarity
- required_room_tags
- incompatible_tags
- possible_clues
- possible_rewards
- possible_risks
- possible_resolution_methods

Update or create these files if they exist or are needed:
- revamp/data/encounter_templates.py
- revamp/data/npc_templates.py
- revamp/data/rumor_templates.py
- revamp/data/safehouse_templates.py
- revamp/data/item_templates.py
- revamp/data/failure_templates.py
- revamp/data/floor_objective_templates.py
- revamp/data/procedural_metadata_schema.py
- revamp/data/content_validation.py

Requirements:
1. Preserve any useful existing content.
2. Convert content entries to template-like entries with metadata.
3. Add validation helpers that can detect:
   - duplicate keys,
   - missing metadata,
   - invalid floor ranges,
   - clues pointing to missing template keys if references are explicit,
   - single-solution objective templates,
   - hardcoded room IDs unless marked debug/test.
4. Do not hook everything into the generator yet unless trivial.
5. The purpose of this task is to make content structured and generator-ready.

Add or update docs/CONTENT_BIBLE.md with:
- a short "Procedural Content Rules" subsection,
- instruction that hand-built Floor 1 is only a vertical slice/test harness,
- instruction that production floors use template pools.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Report:
- files changed,
- template pools found/created,
- metadata fields added,
- validation helpers added,
- content still hardcoded and needing later conversion.
