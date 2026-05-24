Implement a memetic / belief seed system for creative social-engineering, rumor, propaganda, logic-corruption, and ideological manipulation plays.

Do not implement this as "player creates a faction" only.
The core concept is broader:
The player may introduce an idea, lie, myth, rumor, false order, taboo, or logic hook into the world. If successful, it can spread, distort, and affect future encounters.

Examples:
- Convince machines that someone stole their hearts.
- Spread a rumor that the boss fears mirrors.
- Issue a fake maintenance order to drones.
- Convince crawlers that a safehouse bathroom is cursed.
- Start a superstition around sponsor cameras.
- Skew two hostile groups against each other.
- Convince a vending machine AI that it is an employee with labor rights.
- Tell meat drones that the kitchen is violating sacred hygiene law.

This system must integrate with:
- revamp/parser_core.py
- revamp/llm_parser.py
- revamp/validation.py
- revamp/resolution.py
- revamp/consequences.py
- revamp/world.py
- revamp/floor.py
- revamp/room.py
- revamp/crawlers.py
- revamp/encounters.py
- revamp/narrator.py
- revamp/procgen.py
- revamp/save_load.py
- revamp/data/rumor_templates.py
- revamp/data/memetic_templates.py if present
- revamp/data/encounter_templates.py

Before implementation:
Respect existing procedural integration work:
- rumor metadata with tags/weight/floor_min
- clue chains
- risk/reward metadata
- known_clues / known_facts
- tag-aware encounter selection

============================================================
1. CREATE memetics.py
============================================================

Create:

revamp/memetics.py

Add dataclasses:

BeliefSeed:
- seed_id
- key
- origin_text
- created_by
- created_floor
- created_time
- source_room_id
- target_tags
- affected_factions
- affected_entity_tags
- affected_crawler_ids
- core_claim
- emotional_hook
- logic_hook
- method
- desired_effect
- spread_channels
- strength
- stability
- distortion
- current_stage
- tags
- risks
- rewards
- effects
- consequences
- known_to_player
- public_visibility
- sponsor_attention
- expires_at_time or duration if relevant

BeliefEffect:
- key
- trigger_context
- target_tags
- chance
- effect_type
- effect_value
- description_key
- fallback_description_pl

Stages:
- seeded
- noticed
- spreading
- distorted
- institutionalized
- backlash
- burned_out

Methods:
- rumor
- lie
- mythic_comparison
- false_order
- religious_framing
- logic_exploit
- identity_attack
- propaganda
- taboo_creation
- sponsor_disinformation
- social_proof
- performance
- forged_evidence

Spread channels:
- crawler_gossip
- machine_radio
- sponsor_replay
- safehouse_rumor
- graffiti
- black_market
- faction_channel
- combat_logs
- terminal_logs
- bathroom_graffiti
- audience_memes

============================================================
2. DATA TEMPLATES
============================================================

Create/update:

revamp/data/memetic_templates.py

It should define:
- memetic method templates
- effect templates
- target compatibility rules
- risk templates
- distortion templates
- spread channel templates

Fields should include:
- key
- tags
- floor_min
- floor_max
- weight
- target_tags
- required_context_tags
- possible_effects
- possible_risks
- possible_rewards
- spread_channels
- default_stat
- base_dc
- stability_mod
- distortion_mod
- audience_mod

Example effect types:
- hesitation
- morale_shift
- target_priority_shift
- patrol_disruption
- faction_suspicion
- rumor_created
- clue_distortion
- encounter_modifier
- dialogue_hook
- sponsor_attention
- machine_logic_loop
- crawler_panic
- safehouse_gossip
- black_market_interest
- hostility_shift
- temporary_alliance_chance
- false_objective

============================================================
3. PARSER AND OLLAMA SUPPORT
============================================================

Update parser_core.py and llm_parser.py so they can recognize intents:

- seed_belief
- spread_rumor
- create_taboo
- issue_false_order
- logic_exploit
- identity_attack
- sow_distrust
- incite_panic
- religious_framing
- sponsor_disinformation
- propaganda
- forge_social_proof

Polish examples:
- "wmów robotom, że ktoś ukradł im serca"
- "rozpuszczam plotkę, że boss boi się luster"
- "mówię dronom, że mają nowy rozkaz od administracji"
- "przekonuję crawlerów, że czarna łazienka jest przeklęta"
- "rozgłaszam, że sponsorzy ukrywają wyjście w automatach"
- "wmawiam kultystom, że ich kapłan sprzedał ich sponsorowi"
- "ogłaszam przez kamerę, że maszyny są ofiarami systemu"

English examples:
- "convince the robots someone stole their hearts"
- "spread a rumor that the boss fears mirrors"
- "issue a fake order to the drones"
- "tell the crawlers the black bathroom is cursed"

Ollama JSON schema extension:
{
  "intent": "seed_belief",
  "method": "mythic_comparison",
  "targets": ["robots"],
  "target_tags": ["machine"],
  "core_claim": "someone stole your hearts",
  "desired_outcome": "confuse enemies and disrupt orders",
  "emotional_hook": "loss and injustice",
  "logic_hook": "if something is missing, recover it",
  "spread_channel": "spoken",
  "suggested_stat": "CHA",
  "risk_level": "high",
  "confidence": 0.86
}

Important:
Ollama may interpret the idea.
Ollama may not decide that the effect succeeds or how far it spreads.

============================================================
4. VALIDATION
============================================================

Update validation.py:
- Validate memetic actions against context.
- Check whether targets exist or whether there is a broadcast/spread channel.
- Check whether the target group can understand or receive the message.
- Check whether player has means to communicate:
  - direct speech
  - camera
  - terminal
  - graffiti
  - rumor source
  - safehouse crowd
  - crawler gossip
- Check whether the claim has a plausible hook:
  - emotional
  - logical
  - social
  - symbolic
  - authority-based
- Choose appropriate stat:
  - CHA: persuasion, performance, social manipulation
  - INT: logic exploit, fake order, technical disinformation
  - WIS: reading fears, myths, vulnerabilities
- Set DC based on:
  - target resistance
  - context
  - absurdity
  - evidence/tools
  - audience/broadcast reach
  - previous related known facts or rumors

Examples:
- Speaking to machines in room: valid if machines can hear/parse speech.
- Writing graffiti in bathroom: valid as rumor seed, low immediate effect.
- Broadcasting through sponsor camera: valid but high risk/sponsor attention.
- Issuing fake order to drones: requires terminal/camera/radio/authority evidence or high DC.

============================================================
5. RESOLUTION
============================================================

Update resolution.py:
- Resolve memetic actions with d20 result tiers.

Critical success:
- strong seed
- immediate target effect
- rumor created
- possible spread channel
- audience/sponsor notice

Success:
- belief seed created
- modest immediate effect
- chance of future spread

Partial success:
- belief seed created but distorted, unstable, or risky
- immediate effect may be weaker
- sponsor/enemy notices

Failure:
- no seed or weak seed
- time/noise/social cost

Critical failure:
- backlash
- target becomes hostile
- sponsor labels player manipulator
- false version spreads against player
- future complication

============================================================
6. CONSEQUENCES AND WORLD MEMORY
============================================================

Update consequences.py and world.py:
- Add world_state.belief_seeds: dict[str, BeliefSeed]
- Add floor_state.active_belief_seeds if useful
- Save/load all belief seeds
- Old saves must load safely

Applying a belief seed may:
- add rumor with tags
- add known fact/clue
- modify future encounter selection weights
- modify machine/crawler/faction behavior
- add audience
- add sponsor_attention
- add class affinity:
  - social
  - deception
  - showmanship
  - tech if logic exploit
  - occult/cult if religious framing
  - survival if panic manipulation

Immediate effects can include:
- enemy hesitation
- confusion
- target priority shift
- skipped action
- encounter de-escalation
- relationship shift
- rumor propagation
- floor alert increase

============================================================
7. PROPAGATION
============================================================

Create simple propagation function:
process_belief_seeds(world_state, floor_state, time_delta)

Called when time passes significantly:
- every few hours
- daily
- entering safehouse
- major broadcast
- floor transition
- relevant encounter generation

For each seed:
- check spread channels
- roll simple spread chance based on strength/stability/distortion
- update stage
- maybe create rumor
- maybe create encounter modifier
- maybe create sponsor/narrator event
- maybe burn out

Use existing rumor metadata:
- generated rumors should have tags/floor_min/weight/reveals_tags where possible.
- Do not bypass rumor system.

============================================================
8. ENCOUNTER INTEGRATION
============================================================

Tag-aware encounter selection should consider belief seeds.

Examples:
If active seed targets machines:
- machine encounters may get hesitation/dialogue/logic loop.
- machine rumors may appear.
- maintenance rooms may reference it.

If active seed targets crawlers:
- safehouse rumors may reference it.
- crawler relationships may shift.
- some NPCs may ask the player about it.

If active seed targets sponsor:
- sponsor attention increases.
- camera events may appear.
- black market interest may rise.

Do not overdo it.
Belief seeds should be occasional modifiers, not total takeover.

============================================================
9. NARRATOR AND LOG
============================================================

Add narrator categories:
- belief_seed_attempt
- belief_seed_success
- belief_seed_partial
- belief_seed_fail
- belief_seed_backlash
- belief_spreads
- belief_distorts
- machine_confusion
- crawler_gossip_shift
- sponsor_notices_propaganda
- absurd_idea_takes_root

Polish-first, darkly funny.

Examples:
- "System odnotował próbę przemocy semantycznej."
- "Maszyny przez chwilę milczą. To nie jest błąd. To gorzej."
- "Plotka otrzymała nogi. Niestety, nie wiadomo czyje."
- "Sponsorzy przypominają, że nieautoryzowana mitologia podlega opodatkowaniu."

============================================================
10. UI / JOURNAL
============================================================

Add optional command:
- idee
- plotki
- wpływy
- wplywy
- beliefs
- rumors

Show known active belief seeds if player knows about them:
- name/core claim
- target group
- stage if known
- last known effect
- uncertainty

Do not reveal hidden spread rolls or exact mechanics.

============================================================
TESTING
============================================================

Run:

python -m py_compile revamp/*.py revamp/data/*.py

Then run:

python main_revamp.py

Manual smoke test:
1. Create a room with machine/robot or crawler targets.
2. Type:
   "wmów robotom, że ktoś ukradł im serca"
3. Verify parser/Ollama returns seed_belief intent.
4. Verify validator rejects action if there are no targets or spread channel.
5. Verify successful roll creates belief seed.
6. Advance time.
7. Verify belief can create rumor or encounter modifier.
8. Save/load.
9. Verify belief seed persists.
10. Verify sponsor/narrator reacts.

Report:
- files changed
- belief seed schema
- supported memetic intents
- how propagation works
- how rumors/encounters use belief seeds
- limitations
