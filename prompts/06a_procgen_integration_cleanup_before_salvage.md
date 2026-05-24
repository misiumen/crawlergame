You are working on the existing CRAWL PROTOCOL revamp branch.

Do not add salvage, crafting, memetics, or mouse-only UI yet.

First close the open procedural-generator/content integration gaps found by the previous audit.

Relevant files to inspect:
- revamp/procgen.py
- revamp/floor.py
- revamp/room.py
- revamp/world.py
- revamp/character.py
- revamp/validation.py
- revamp/resolution.py
- revamp/consequences.py
- revamp/save_load.py
- revamp/content_loader.py
- revamp/data/room_pool.py
- revamp/data/clue_templates.py
- revamp/data/floor_objective_templates.py
- revamp/data/safehouse_templates.py
- revamp/data/encounter_templates.py
- revamp/data/rumor_templates.py if present
- revamp/data/item_templates.py

Goal:
Make the procedural/content framework ready for salvage, crafting, and memetic systems.

============================================================
1. WIRE RISKS / REWARDS INTO RESOLUTION AND CONSEQUENCES
============================================================

Current issue:
Template metadata documents risks/rewards, but the resolver/consequence layer does not consistently consult them.

Implement:
- A common helper to convert content metadata risks/rewards into mechanical or narrative effects.
- ResolutionResult or Consequence application should be able to receive risk/reward metadata from:
  - room templates
  - encounter templates
  - objective templates
  - clue templates
  - safehouse templates
  - future salvage/crafting/memetic templates

Risk examples:
- tracked_by_sponsor
- black_market_interest
- makes_noise
- attracts_patrol
- damages_item
- increases_alert
- social_suspicion
- unsafe_crafting
- disease_risk
- chemical_exposure

Reward examples:
- audience_awareness
- clue_gain
- material_gain
- relationship_gain
- safehouse_discount
- rumor_gain
- class_affinity_gain
- hidden_exit_hint

Do not overbuild. Implement a simple, data-driven mapper:
risk/reward key -> small effect/log/narrator hook.

Examples:
- tracked_by_sponsor -> audience +1, sponsor attention flag/log
- black_market_interest -> add world flag or rumor hook
- makes_noise -> room noise +1 or floor alert +1
- damages_item -> set item.state["damaged"] = True where applicable
- audience_awareness -> audience +1
- clue_gain -> add known clue if provided
- material_gain -> future hook; do not implement materials here unless already present

============================================================
2. SAFEHOUSE possible_clue_sources
============================================================

Current issue:
safehouse `possible_clue_sources` is documented metadata, but clue placement uses hardcoded room_type -> actual_type mapping.

Implement:
- If safehouse templates include `possible_clue_sources`, the clue placer should read them.
- Safehouse subtypes should influence clue placement.
- Example:
  - cafe may produce crawler gossip / overheard conversation
  - bathroom may produce graffiti / mirror warning / discarded badge
  - clinic may produce medical records / wounded crawler testimony
  - black_market may produce paid rumors / illegal map fragments
  - bulletin_board may produce explicit job or clue hooks

Do not force every safehouse to have a clue.
Use weights and objective relevance.

============================================================
3. TAG-AWARE ENCOUNTER SELECTION
============================================================

Current issue:
The generator places one encounter intro in a combat room without using objective/crawler/floor tags enough.

Implement:
- Encounter selection should filter and weight by tags:
  - floor theme tags
  - room tags
  - objective tags
  - required_tags from objective
  - crawler/NPC tags if present
  - safehouse/social/danger context
- The selected encounters should reinforce the floor goal.

Example:
If objective is `repair_elevator` with required tags `power`, `cable`, `control_panel`:
- favor encounters involving maintenance drones, broken panels, scavenger crawlers, locked service rooms, electrical hazards.
- do not randomly select unrelated cult encounter unless tags overlap or weight still allows rare variety.

Add fallback:
If no exact tag match exists, choose a general encounter but log/debug why.

============================================================
4. VALIDATE objective.required_tags
============================================================

Current issue:
Objectives may declare required_tags such as ["power", "cable", "control_panel"], but validate_floor does not confirm those tags exist somewhere on the generated floor.

Implement:
- validate_floor must check objective.required_tags.
- Required tags may be satisfied by:
  - room tags
  - entity/object tags
  - clue tags
  - safehouse service tags
  - encounter tags
  - item/loot tags if placed
- If a required tag is missing, generator should repair the floor by placing a compatible room/entity/clue, or reject/regenerate the floor.

Do not let the game generate an impossible floor.

============================================================
5. RUMOR METADATA
============================================================

Current issue:
Rumors are flat per-category and have `reveals_tags`, but lack tags/weight/floor_min metadata.

Implement or update rumor templates so each rumor has:
- key
- category
- text_key or fallback text
- tags
- reveals_tags
- weight
- floor_min
- floor_max
- reliability
- source_types
- objective_tags if relevant
- false_or_partial flag if useful

Rumor selection should use:
- current floor number
- floor theme
- safehouse/NPC source type
- active objective tags
- known/unrevealed clues

Do not break existing rumors. Provide migration/defaults.

============================================================
6. CLUE CHAINS AS REAL SEQUENCES
============================================================

Current issue:
`unlocks_chain` exists in clue templates, but the engine does not enforce ordering.

Implement:
- Clue chains should have sequence/order.
- A clue can require prior clue key or stage.
- The player should not receive step 3 before step 1 unless the clue is marked `can_skip_sequence`.
- `Character.flags["known_clues"]` or equivalent should track known clue keys.
- `known_facts` should track facts revealed by clues.
- Clue placement can place later clues physically, but discovery should either:
  - hide them until prerequisites are met, or
  - convert them into vague/partial clue until prerequisite exists.

Keep it simple but real.

============================================================
7. item_damage AND state["damaged"] MUST MATTER
============================================================

Current issue:
Prompt 03 effects set item damage/damaged flags, but nothing consumes them.

Implement:
- Items may have state dict with:
  - damaged: bool
  - durability: int or None
  - max_durability: int or None
  - unstable: bool
- Damaged items should have a small mechanical penalty where appropriate:
  - weapon: lower reliability / damage penalty / chance to break
  - tool: lower check bonus or failure chance
  - armor: reduced protection
  - consumable: may be unsafe if damaged
- Repair affordance or future crafting should be able to clear damaged state.
- If inventory system is too simple, implement minimal helper functions:
  - is_item_damaged(item)
  - damage_item(item, amount=1)
  - repair_item(item, amount=1)
  - describe_item_condition(item)

Do not overcomplicate item durability yet.

============================================================
8. SAVE FORMAT RE-VERIFY
============================================================

Current issue:
Save format must be re-verified against new `Character.flags["known_clues"]` and `known_facts`.

Implement:
- Save/load must preserve:
  - known_clues
  - known_facts
  - clue chain state
  - damaged item state
  - floor objective state
  - rumors/facts if stored
- Old saves without these fields must load safely.

Add a simple round-trip save/load test path if test framework exists, or a debug helper.

============================================================
TESTING
============================================================

Run:

python -m py_compile revamp/*.py revamp/data/*.py

Then run:

python main_revamp.py

Manual smoke tests:
1. Generate Floor 1 with several seeds if a seed option exists.
2. Verify objective.required_tags are present or floor is repaired.
3. Verify a safehouse can provide clue source based on subtype.
4. Verify clues do not reveal later chain steps too early.
5. Verify damaged item state persists through save/load.
6. Verify a risk/reward metadata key produces some effect or log.
7. Verify rumors can be selected with tags/floor metadata.

Report:
- files changed
- which integration gaps were fixed
- any gaps intentionally left for the salvage/crafting/memetics prompts
