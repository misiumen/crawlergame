Implement a DCC-style salvage, looting, harvesting, and improvised crafting system in the revamp branch.

Before implementing this prompt, assume the procedural integration cleanup has either been completed or is in progress. Do not bypass existing risk/reward metadata, clue chains, item damage, or save/load conventions.

Do not rewrite the whole game.

Build on:
- revamp/entity.py
- revamp/affordances.py
- revamp/validation.py
- revamp/resolution.py
- revamp/consequences.py
- revamp/parser_core.py
- revamp/inventory.py
- revamp/items.py
- revamp/character.py
- revamp/room.py
- revamp/floor.py
- revamp/game.py
- revamp/save_load.py
- revamp/narrator.py
- revamp/data/item_templates.py
- revamp/data/entity_templates.py
- revamp/data/salvage_tables.py if present
- revamp/data/recipe_templates.py if present

Goal:
The player should be able to loot, strip, salvage, harvest, break down, and repurpose many objects in the world.

This supports:
- improvised tools
- improvised traps
- improvised weapons
- distractions
- repairs
- clues
- alternative encounter solutions
- environmental problem-solving

The intended feel:
"Almost everything in the dungeon can become a resource, but doing so costs time, creates risk, and changes the world."

============================================================
1. USE EXISTING RISK / REWARD PIPELINE
============================================================

Salvage/crafting actions must use the same risk/reward metadata handling created in the procedural integration pass.

Examples:
- makes_noise -> add room noise / floor alert
- tracked_by_sponsor -> audience/sponsor attention
- damages_item -> item.state["damaged"] = True
- chemical_exposure -> damage/condition risk
- social_suspicion -> NPC/crawler reaction
- clue_gain -> known clue or known fact
- material_gain -> add materials

Do not implement a separate incompatible risk system.

============================================================
2. MATERIAL SYSTEM
============================================================

Create/update:

revamp/materials.py

Add MaterialDef:
- key
- name_key
- fallback_name_pl
- fallback_name_en
- tags
- rarity
- description_key
- fallback_description_pl
- value
- weight if inventory weight exists, otherwise ignore

Core materials:

Common:
- scrap_metal
- wood_fragments
- plastic_shards
- cloth_strips
- glass_shards
- wire_bundle
- screws
- tape
- rubber_strip
- ceramic_fragments
- leather_scraps

Organic:
- bone_fragments
- monster_hide
- sinew
- meat_chunk
- tooth
- claw
- strange_organ
- fungal_fiber
- ichor_sample
- contaminated_blood

Technical:
- battery_cell
- circuit_board
- camera_lens
- sensor_module
- copper_coil
- insulated_wire
- broken_screen
- motor_unit
- pressure_valve
- data_chip

Chemical:
- cleaning_fluid
- acid_residue
- oil_canister
- disinfectant
- flammable_gel
- coolant
- powdered_reagent
- medical_alcohol

Rare/weird:
- sponsor_chip
- anomaly_dust
- void_residue
- mutation_sample
- black_glass
- crawler_badge
- contract_scrap
- audience_token

Character/inventory:
- Add character.materials: dict[str, int]
- Save/load materials.
- Old saves without materials must load safely.

UI:
- Show materials via commands:
  - materiały
  - materialy
  - materials

============================================================
3. SALVAGE TABLES
============================================================

Create/update:

revamp/data/salvage_tables.py

Each salvageable entity type should define:
- key
- display/fallback labels if needed
- material drops
- quantity ranges
- rare drop chances
- required tool tags
- stat
- dc
- time_cost
- noise
- risks
- rewards
- depletes_entity
- state_change

Tables to include:
- furniture_wood
- furniture_metal
- corpse_humanoid
- corpse_crawler
- corpse_monster
- sponsor_camera
- vending_machine
- bathroom_fixture
- medical_cabinet
- electrical_panel
- kitchen_equipment
- chemical_hazard
- terminal_console
- broken_door
- ventilation_grate
- floor_debris
- broken_robot
- trap_remains

Important:
- Salvage tables should include tags so the generator can place them contextually.
- Salvage rewards can include clues/facts when appropriate.
  Example: corpse_crawler may yield crawler_badge and clue/fact.
- Salvage risks must be fed into the shared consequence system.

============================================================
4. ENTITY TEMPLATE INTEGRATION
============================================================

Update entity templates so many objects can be salvaged.

Examples:
- tables
- chairs
- shelves
- cabinets
- lockers
- crates
- corpses
- crawler corpses
- monster corpses
- cameras
- terminals
- vending machines
- bathroom stalls
- sinks
- mirrors
- toilets
- pipes
- vents
- loose grates
- doors
- broken machines
- floor debris
- kitchen counters
- medical cabinets

Each relevant entity should have:
- salvage_table key
- salvage_state
- intact / damaged / stripped / depleted state
- tags
- actions / affordances

No infinite farming.
Once salvaged, an entity should become:
- stripped
- depleted
- damaged
- destroyed
or should have reduced remaining salvage.

Save/load must persist entity state.

============================================================
5. LOOTING VS SALVAGING
============================================================

Separate actions:

1. search / przeszukaj
- reveals/finds obvious or hidden items
- costs moderate time
- may reveal clues

2. loot / ograb / lootuj
- takes portable items from corpse/container
- costs little/moderate time
- may affect reputation if witnesses exist

3. strip / rozbierz
- removes equipment/clothing/useful parts
- costs more time
- may create materials
- may be socially punished

4. salvage / zdemontuj / odzyskaj części
- breaks down object into materials
- costs time
- may require tools
- creates noise
- can destroy object
- may trigger hazard

5. harvest / pozyskaj
- organic salvage from corpses/monsters
- may require blade/tool
- can produce organic materials
- may cause disease/disgust/narrator/social consequences

============================================================
6. IMPROVISED CRAFTING SYSTEM
============================================================

Create/update:

revamp/crafting.py
revamp/data/recipe_templates.py

Two crafting modes:

A. Known recipes
Specific recipes with required materials.

B. Improvised crafting
Player writes:
- "zrób pułapkę z kabli i baterii"
- "skleć włócznię ze stołowej nogi i szkła"
- "zrób wabik z mięsa i telefonu"
- "owijam nóż taśmą i szkłem"
- "robię granat z butli gazowej i zapalniczki"

Parser extracts:
- desired crafted object
- materials/tools mentioned
- category: trap, weapon, distraction, repair, armor, consumable, key/tool, bait, disguise

Validator checks:
- player has materials
- materials have suitable tags
- room/context allows crafting
- required tool exists if needed
- time is available
- action is not absurdly impossible

Resolution:
- usually INT or DEX
- DC based on complexity/material quality
- result level:
  - critical_success
  - success
  - partial_success
  - failure
  - critical_failure

Known recipe examples:
- improvised_bandage
- shiv
- glass_spear
- noise_maker
- shock_trap
- tripwire
- smoke_bottle
- fire_bottle
- lockpick
- armor_patch
- insulated_gloves
- acid_vial
- bait_bundle
- reinforced_club
- camera_decoy
- crude_battery_pack
- chemical_flash
- bone_spike_trap
- crawler_disguise_piece

Recipe fields:
- key
- name_key
- fallback_name_pl
- fallback_description_pl
- required_materials
- required_tags
- required_tools
- result_item
- result_effect
- time_cost
- stat
- dc
- risks
- rewards
- failure_risk
- partial_success_result
- category
- tags

If exact recipe not found:
Use tag-based improvised crafting:
- wire/binding + sharp -> cutting tripwire / improvised trap
- wire/electrical + battery -> shock device / electrical trap
- glass/sharp + wood/handle -> crude spear / shiv
- organic/meat + scent -> bait
- cloth + alcohol + flammable -> fire bottle
- tape + armor/cloth/metal -> armor patch
- camera_lens + electronics -> decoy/sensor gadget

============================================================
7. FAIL-FORWARD CRAFTING
============================================================

Crafting is not binary.

Critical success:
- item created
- better quality
- less material waste
- possible audience/narrator bonus

Success:
- item created normally

Partial success:
- item created but flawed
- extra time
- noisy
- unstable
- damaged
- reduced durability
- consumes extra materials

Failure:
- no item or flawed item
- some material loss
- time passes

Critical failure:
- injury
- noise/alarm
- fire/shock/chemical splash
- cursed/unstable item
- sponsor camera notices

Use item state:
- item.state["damaged"]
- item.state["unstable"]
- item.state["quality"]
- item.state["durability"]

Damaged/unstable items must matter through existing item_damage logic.

============================================================
8. RESULT ITEMS
============================================================

Crafted items must be usable.

If full unique implementation is too large, use generic templates:
- improvised_weapon
- improvised_trap
- improvised_distraction
- improvised_tool
- improvised_armor_patch
- improvised_bait
- improvised_disguise

Each should have:
- tags
- quality
- state
- duration/uses if relevant
- effect when used

Examples:
- improvised_trap: can be deployed in current room
- improvised_distraction: thrown/noise/lure/flee assist
- improvised_tool: bonus to one check type
- improvised_bait: lure monsters
- improvised_disguise: social/sneak bonus

Save/load crafted items.

============================================================
9. PARSER INTEGRATION
============================================================

Update parser_core.py for:
- "przeszukuję ciało"
- "ograbiam ciało"
- "rozbieram ciało z ubrań"
- "pozyskuję kości z potwora"
- "zdemontuj kamerę"
- "rozbij stół i weź nogę"
- "zbierz przewody"
- "przerób meble na barykadę"
- "zrób pułapkę z kabli"
- "craftuję lockpick z drutu"
- "skleć włócznię ze szkła i kija"
- "użyj resztek mięsa jako przynęty"

English:
- search body
- loot corpse
- strip corpse
- harvest monster
- salvage camera
- dismantle table
- recover wires
- craft trap from wires
- make lockpick from wire
- build spear from glass and stick
- use meat as bait

ActionIntent fields should support:
- intent: loot/search/salvage/harvest/craft/improvise
- targets
- tool
- materials mentioned
- desired_outcome
- confidence

Ollama may help parse complex crafting commands, but validator must check materials.

============================================================
10. VALIDATION
============================================================

Update validation.py:
- reject salvaging things not present
- reject harvesting corpses not present
- reject crafting without materials
- reject impossible material combinations
- allow tag-based improvised crafting
- warn if action is dangerous
- check safehouse/social restrictions
- check tool requirements
- check time cost

Examples:
"rozbieram krzesło" + room has chair -> valid.
"zbieram przewody" + no electrical/wire source -> invalid with immersive message.
"zrób granat z kubka i mięsa" -> invalid or very high absurdity unless explosive/chemical/electrical tags exist.

============================================================
11. CONSEQUENCES
============================================================

Update consequences.py:
- add materials
- remove materials
- add crafted item
- mark entity depleted/stripped/destroyed
- add time
- add noise
- apply injury/hazard on failure
- apply social consequences for looting bodies in front of witnesses
- apply safehouse consequences for stealing/salvaging property
- add audience/narrator response
- add known facts/clues if salvage reveals them

============================================================
12. SAFEHOUSE AND SOCIAL CONSEQUENCES
============================================================

Context matters.

Allowed:
- abandoned rooms
- battlefield corpses
- monster remains
- broken furniture
- dungeon debris

Risky:
- crawler corpses in front of witnesses
- safehouse property
- sponsor cameras
- medical equipment in clinic
- bathroom fixtures
- merchant shelves

Safehouse theft/salvage can cause:
- warning
- fine
- ejection
- relationship loss
- sponsor attention
- hostility
- achievement/narrator line

============================================================
13. ACHIEVEMENTS / AFFINITY / NARRATOR
============================================================

Achievements if system exists:
- Wszystko Jest Surowcem
- Meble Też Krwawią
- Recykling Agresywny
- Rzemieślnik Z Paniki
- Niebezpiecznie Kreatywny
- Rozbiórka Zwłok
- Przepis? Jaki Przepis?
- Złota Rączka Lochu

Affinity:
- salvage: survival +1, crafting +1
- corpse harvesting: survival +1, occult/corruptive if relevant
- tech salvage: tech +1
- trap crafting: trap +2
- improvised weapon: melee/survival +1
- disguise crafting: social/deception +1

Narrator categories:
- salvage_success
- salvage_fail
- corpse_loot
- corpse_harvest
- furniture_salvage
- safehouse_theft
- crafting_success
- crafting_partial
- crafting_fail
- crafting_critical_fail
- absurd_improvisation
- dangerous_but_valid
- invalid_crafting_materials

Polish-first, sarcastic, corporate, darkly funny.

============================================================
14. UI
============================================================

Update UI so player can see:
- materials
- recent salvage results
- crafted item results
- entity stripped/depleted status
- simple crafting help

Commands:
- materiały / materialy / materials
- craft help / pomoc craftingu
- salvage help / pomoc odzyskiwania

Do not overcrowd UI.

============================================================
TESTING
============================================================

Run:

python -m py_compile revamp/*.py revamp/data/*.py

Then run:

python main_revamp.py

Manual smoke test:
1. Start game.
2. Find a room with furniture or corpse.
3. Use "przeszukaj ciało".
4. Use "ograb ciało".
5. Use "pozyskaj kości z ciała" if corpse supports it.
6. Use "rozbierz krzesło".
7. Confirm materials are added.
8. Try to salvage nonexistent wires and confirm rejection.
9. Craft simple item:
   "zrób pułapkę z kabli"
   or "zrób prowizoryczną broń ze szkła i drewna"
10. Confirm materials are consumed.
11. Confirm crafted item appears.
12. Save/load.
13. Confirm materials and crafted items persist.
14. Try stealing/salvaging safehouse property and confirm contextual consequence.

Report:
- files changed
- materials added
- salvage tables added
- recipes added
- how improvised crafting works
- how item damage/degradation is used
- limitations
