# Procedural Content Addendum

Use this addendum alongside `docs/CONTENT_BIBLE.md`.

## Core correction

Floor content must be built as reusable procedural content, not as one canonical fixed map.

The hand-built Floor 1 may exist only as:
- a vertical slice,
- a debugging harness,
- a smoke-test layout,
- a reference example.

The production game should generate floors from controlled templates.

## Design rule

Do not write content that depends on exact placement unless it is explicitly marked as a test-only handcrafted layout.

Prefer content that can be selected by:

```python
generate_floor(floor_number=1, seed=...)
```

## Every content template should include metadata

Recommended metadata:

```python
{
    "key": "...",
    "floor_min": 1,
    "floor_max": 3,
    "tags": [...],
    "weight": 1.0,
    "rarity": "common|uncommon|rare|setpiece",
    "required_room_tags": [...],
    "incompatible_tags": [...],
    "possible_clues": [...],
    "possible_rewards": [...],
    "possible_risks": [...],
    "possible_resolution_methods": [...]
}
```

## Floor generation guarantees

A generated floor should guarantee structure, not exact content.

Floor 1 should guarantee:
- a start room,
- 12–20 total rooms,
- at least one safehouse or neutral anchor,
- at least one bathroom/cafe/lounge/clinic-like location,
- multiple danger rooms,
- multiple non-combat opportunities,
- at least one locked or blocked area,
- at least one secret or hidden feature,
- at least one major obstacle,
- at least one floor exit objective,
- at least two possible solution paths toward progress,
- backtracking,
- hidden room types before discovery,
- clues and rumors that help the player plan.

## Information design

Information is content.

The generator should place:
- true clues,
- partial clues,
- unreliable rumors,
- environmental hints,
- NPC knowledge,
- map hints,
- safehouse gossip,
- sponsor propaganda that may conceal useful information.

## Avoid

Avoid:
- hardcoded room IDs in content templates,
- one fixed NPC placement,
- one fixed item needed for progress,
- clues pointing to content that may not exist,
- single-solution objectives,
- revealing room type before discovery,
- linear-only routes,
- fixed safehouse position,
- fixed boss path.

## Preferred structure

Good content is modular:

- room template,
- object set,
- encounter template,
- clue chain,
- NPC/crawler template,
- safehouse template,
- objective variant,
- reward table,
- consequence table.

The generator combines these into a playable floor.
