# 03 — Improvisation and fail-forward, context-driven

Do not add fixed-map assumptions.

Goal:
Improve improvisation resolution and fail-forward outcomes using room/entity/context tags.

Failure and partial success templates must be context-driven.

They should use:
- current room tags,
- visible entities,
- object tags,
- encounter type,
- safehouse status,
- danger level,
- noise level,
- relationship state,
- available exits,
- current floor objective.

Do not refer to fixed room IDs unless the content is explicitly debug/test-only.

## Good examples

- If room has tag "mechanical", failure may trigger sparks, noise, jammed mechanism, or maintenance alert.
- If room has tag "safehouse", social failure may affect reputation or service access.
- If room has visible crawler, failure may change relationship.
- If room has hazard tag "acid", partial success may splash acid or corrode an item.
- If room has sponsor camera, clever success may boost audience.
- If player uses Polish/English ambiguous command, parser should ask clarification instead of guessing.

## Bad examples

- "In room_chemical_lab, always trigger acid splash."
- "Crawler Marek always appears in bathroom_01."
- "Failure always deals 1d6 damage."
- "The code is always in the freezer."

## Required work

Update failure/partial success systems and templates to support:

Result levels:
- critical_success
- success
- partial_success
- failure
- critical_failure

Add context-driven effects:
- time cost,
- noise,
- relationship shift,
- audience shift,
- object state change,
- item damage/loss,
- condition,
- reveal clue,
- alert patrol,
- block/unblock route,
- safehouse consequence,
- rumor gained,
- class affinity shift.

Add at least 30 fail-forward templates:
- 5 mechanical,
- 5 social,
- 5 stealth,
- 5 environmental,
- 5 safehouse,
- 5 combat/escape.

Add at least 20 partial success templates.

Parser/validator behavior:
- impossible action returns immersive feedback,
- ambiguous action asks for clarification,
- valid improvised action receives a fair check,
- engine changes world state based on result.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Report:
- templates added,
- systems changed,
- examples of 5 action outcomes,
- remaining limitations.
