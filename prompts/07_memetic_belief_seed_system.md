# Prompt 07 — Memetic belief-seed system

Implement a system for creative social-engineering plays that can persist and spread.

This is NOT a faction-creation system.
It is a system for ideas, rumors, symbolic claims, logic traps, misinformation and identity attacks.

Examples of supported play:
- convince machines that someone stole their hearts
- make goblins believe cameras steal names
- spread a rumor that a boss fears mirrors
- issue a false order to drones
- convince crawlers that a bathroom is sacred or unsafe
- sow distrust between enemy groups

## Required modules

Create:
- revamp/memetics.py

Use:
- revamp/data/memetic_templates.py if present

Integrate with:
- parser_core.py
- llm_parser.py
- validation.py
- resolution.py
- consequences.py
- world.py
- floor.py
- crawlers.py
- encounters.py
- safehouses.py
- narrator.py
- procgen.py
- save_load.py
- ui.py

## Data model

Create BeliefSeed dataclass:
- belief_id
- origin_text
- created_by
- created_floor
- created_time
- target_tags
- affected_entity_ids
- affected_factions
- core_claim
- emotional_hook
- logic_hook
- spread_channels
- strength
- stability
- distortion
- stage
- effects
- consequences
- last_evolved_time

Stages:
- seeded
- spreading
- distorted
- weaponized
- burned_out

Effects:
- hesitation
- target_priority_shift
- morale_shift
- rumor_hook
- sponsor_attention
- logic_corruption
- panic

Add to WorldState or FloorState:
- active_beliefs: dict[str, BeliefSeed]

Persist in save/load.
Old saves must load safely.

## Parser intents

Add intents:
- seed_belief
- spread_rumor
- false_order
- identity_attack
- sow_distrust
- incite_panic
- sponsor_disinformation
- create_taboo

Polish examples:
- wmów im że...
- przekonuję roboty że...
- rozpuszczam plotkę że...
- podaję fałszywy rozkaz...
- skłócam ich...
- mówię maszynom że ktoś ukradł im...
- ogłaszam że to miejsce jest przeklęte...

English examples:
- convince them that...
- make the machines believe...
- spread a rumor that...
- issue a false order...
- turn them against...
- tell the drones someone stole...

Ollama may help parse these, but cannot apply effects.

## Validation

Check:
- are there targets that can hear/receive the idea?
- are targets sentient, semi-sentient, machine-logical, social, superstitious, bureaucratic, etc.?
- is there a communication channel?
- is the claim plausible enough for the target type?
- is this safehouse/social/combat/broadcast context?
- does it need CHA, INT or WIS?
- risk level

If no valid audience/channel exists, reject with immersive feedback.

## Resolution

Use d20-style check.

Common stats:
- CHA: persuasion, performance, manipulation
- INT: logic exploit, fake order, technical/social engineering
- WIS: reading weakness, mythic/framing insight

Result levels:
- critical_success
- success
- partial_success
- failure
- critical_failure

Critical success:
- immediate effect + persistent belief with high strength

Success:
- immediate effect + persistent belief with moderate strength

Partial:
- belief forms but distorted, weaker, risky

Failure:
- no belief, maybe suspicion

Critical failure:
- targets become hostile / sponsor notices / player marked as manipulator

## Consequences

Immediate effects may include:
- enemy hesitation
- lost turn
- morale penalty
- target priority shift
- social confusion
- alarm
- audience change
- relationship change

Persistent effects:
- add belief seed
- add rumor
- modify future encounters with matching target tags
- generate safehouse gossip
- generate sponsor/narrator commentary
- create later event hook
- possibly distort the belief over time

## Evolution

Add function:
evolve_beliefs(world, minutes_passed)

Called when time passes.

Beliefs may:
- spread
- distort
- burn out
- become stronger due to audience/sponsor replay
- affect future rooms/encounters
- appear in rumors

Keep evolution simple initially:
- once every 6 hours or day
- roll based on strength/stability/distortion

## UI

Add commands:
- idee / beliefs / plotki aktywne
- "co ludzie mówią?" / "rumors"

Display known active belief effects only if the player has reason to know.

## Narrator

Add categories:
- belief_seeded
- belief_failed
- belief_spread
- belief_distorted
- logic_corruption
- sponsor_noticed_belief
- rumor_returns
- enemy_hesitates_from_belief

Polish-first, darkly funny.

## Testing

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Smoke-test:
1. enter room with machine/creature/crawler
2. use a belief-seeding command
3. validate context
4. resolve check
5. confirm belief stored on success/partial
6. pass time
7. confirm belief can produce rumor or encounter modifier
8. save/load and verify belief persists

Report files changed and limitations.
