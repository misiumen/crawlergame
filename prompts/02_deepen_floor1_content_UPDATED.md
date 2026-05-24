# 02 — Deepen Floor 1 as a procedural content pool

You are currently deepening Floor 1 content.

Important:
Do not deepen Floor 1 as one fixed handcrafted map.

From now on, treat Floor 1 content as a procedural content pool.

Keep any existing hand-built Floor 1 only as:
- vertical slice,
- test harness,
- debug layout,
- example of how templates can be assembled.

Do not hardcode exact placement.

Goal:
Create a rich Floor 1 content pool that a future generator can combine differently each run.

Add or expand reusable templates:

## Required pools

1. Room templates
Create or expand at least 20 Floor 1-compatible room templates.

Each room template should have:
- key
- title/fallback Polish title
- sensory description fragments
- tags
- danger_level
- safe_level
- possible_objects
- possible_encounters
- possible_rumors
- possible_rewards
- possible_exits_hint
- metadata

2. Safehouse templates
Create or expand at least 8 Floor 1-compatible safehouse templates:
- cafe
- bathroom
- lounge
- clinic
- vending hall
- neutral bar
- crawler corner
- sponsor kiosk

Each safehouse should have:
- services
- possible NPC/crawler roles
- possible rumors
- possible weird events
- exhausted service rules
- metadata

3. Encounter templates
Create or expand at least 15 Floor 1-compatible encounter templates:
- hostile monster,
- neutral crawler,
- wounded crawler,
- crawler vs monster,
- loot conflict,
- blocked path,
- ambush,
- social standoff,
- trap-social situation.

Each encounter must have multiple possible resolution methods where plausible:
- fight,
- flee,
- negotiate,
- bribe,
- help,
- betray,
- use_environment,
- sneak,
- use_item,
- ignore.

4. NPC/crawler templates
Create or expand at least 15 crawler/NPC templates.

Each should define:
- archetype,
- personality,
- what they want,
- what they know,
- what they fear,
- when they help,
- when they betray,
- relationship hooks,
- rumor hooks,
- trade/help/hostility flags.

5. Rumor templates
Create or expand at least 15 Floor 1-compatible rumors.

Rumors should include:
- true clue,
- partial clue,
- false or misleading clue,
- sponsor propaganda,
- crawler gossip,
- safehouse hint,
- objective hint,
- hazard warning.

6. Clue chains
Create at least 8 clue chain templates.

Each clue chain should:
- point toward a possible objective, secret, safehouse, hazard, key, shortcut, or exit route,
- have 2–4 clues,
- tolerate alternate placement,
- not require exact room IDs unless debug-only.

7. Objective variants
Create at least 6 Floor 1 exit/objective variants.

Examples:
- find access code,
- repair lift panel,
- negotiate passage,
- defeat or bypass major obstacle,
- open maintenance hatch,
- collect components,
- activate emergency route.

Each objective must have at least two possible solution paths.

8. Environmental object sets
Create at least 15 object-set templates.

Examples:
- acid hazard setup,
- electrical hazard setup,
- vending machine/social setup,
- bathroom utility setup,
- kitchen grease setup,
- camera/sponsor setup,
- freezer/locked door setup,
- maintenance hatch setup.

## Style requirements

Polish text should be immersive:
- sensory,
- darkly funny,
- corporate cruelty,
- not dry,
- not overlong for UI.

Avoid:
- exact room order,
- exact NPC placement,
- exact key placement,
- single-solution objective,
- revealing room type before discovery.

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Report:
- how many templates were added per category,
- any remaining fixed-map assumptions,
- what generator support is still needed.
