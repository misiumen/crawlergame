Finalize crafting, salvage, narrator hooks, and achievements before moving to memetics.

Do not implement the memetic system in this prompt.
Do not add unrelated features.
Do not rewrite the whole revamp.

Context:
The current salvage/crafting follow-up is being implemented or has just been implemented. This prompt finishes the crafting layer as a coherent gameplay and lore system.

Required new/updated docs:
- docs/CRAFTING_BIBLE.md
- docs/MEMETICS_BIBLE.md
- docs/CONTENT_BIBLE.md should briefly reference both if it exists.

Writing style:
Avoid repetitive paratactic anaphora. Do not generate long sequences of lines with the same sentence structure. Vary rhythm, sentence length, and syntax. Polish should sound natural, not like translated bullet spam.

============================================================
1. INSTALL / UPDATE BIBLES
============================================================

Add docs/CRAFTING_BIBLE.md from the provided file.
Add docs/MEMETICS_BIBLE.md from the provided file.

If docs/CONTENT_BIBLE.md exists, add a short section:

"Crafting and salvage"
- Crafting is a pillar of survival and lore.
- The player may loot, strip, salvage, harvest, dismantle, craft, improvise, repair, reinforce, and deploy.
- Materials use tags.
- Improvised crafting must validate against actual materials, room context, and risk.
- Safehouse theft, corpse harvesting, sponsor property, and bathroom vandalism require world reactions.
- Narrator and achievements are required feedback for important salvage/crafting actions.

"Memetic actions"
- Memetic actions are belief seeds, rumors, false orders, social manipulation, logic exploits, and symbolic attacks.
- They are not the same as creating factions.
- The parser may interpret intent, but the world model validates context.
- Successful memetic actions should be saved as world state and may return later through rumors, encounters, narrator lines, and clue-enabled resolutions.
- Memetics should be implemented after crafting is stable.

============================================================
2. CRAFTING BIBLE COMPLIANCE AUDIT
============================================================

Inspect:
- revamp/materials.py
- revamp/crafting.py
- revamp/data/salvage_tables.py
- revamp/data/recipe_templates.py
- revamp/data/item_templates.py
- revamp/data/entity_templates.py
- revamp/affordances.py
- revamp/parser_core.py
- revamp/validation.py
- revamp/resolution.py
- revamp/consequences.py
- revamp/character.py
- revamp/inventory.py
- revamp/save_load.py
- revamp/narrator.py
- revamp/ui.py
- revamp/locales/pl.json
- revamp/locales/en.json

Bring implementation in line with docs/CRAFTING_BIBLE.md.

Confirm or implement:
- material tags exist and are used,
- material storage is character.materials or equivalent,
- salvage tables produce materials,
- entities become stripped/depleted/destroyed/harvested,
- safehouse-owned entities are marked and risky,
- recipe aliases work in Polish and English,
- tag-based improvised crafting exists,
- crafted items have quality/flaws where appropriate,
- deployable crafted items can be placed or used,
- save/load persists materials, crafted items, entity states, placed traps, achievements.

============================================================
3. PARSER POLISH PATTERNS
============================================================

Ensure parser handles Polish source-material patterns:

- "pozyskaj kości z drona"
- "wyciągnij przewody z kamery"
- "odzyskaj szkło z ekranu"
- "zdemontuj nogę ze stołu"
- "weź kartę z ciała"
- "wytnij gruczoł z potwora"
- "zbierz części z automatu"

For X z/ze Y:
- source entity = Y
- desired material/part = X
- targets should point to source entity, not the material
- ActionIntent should preserve desired_material or desired_part

Validation must reject impossible extraction with useful feedback:
"Możesz rozebrać drona, ale nie wygląda, żeby dało się z niego pozyskać kości."

============================================================
4. SALVAGE AND ROOM CONTENT INTEGRATION
============================================================

Normal generated rooms must naturally include salvageable content.

Update room pools/templates/generator so rooms can seed:
- furniture,
- cameras,
- fixtures,
- corpses,
- vending machines,
- panels,
- pipes,
- crates,
- cabinets,
- debris,
- medical cabinets,
- kitchen equipment,
- terminals.

Do not make every room a salvage warehouse.
Use weights and rarity.

Safehouse/special contexts:
- safehouse furniture and bathroom fixtures should often be salvageable but owned,
- clinic equipment should be useful but risky to steal,
- merchant shelves should be owned,
- sponsor cameras should have sponsor consequences.

============================================================
5. DEPLOYABLE CRAFTED ITEMS
============================================================

Ensure deploy exists as a real affordance and gameplay path.

Commands:
- "rozstaw pułapkę"
- "ustaw linkę"
- "podłóż shock trap"
- "zamontuj pułapkę przy drzwiach"
- "deploy trap"
- "place tripwire near door"

Deploy validation:
- item exists in inventory,
- item has deployable/trap/placed tags,
- room allows placement,
- safehouse placement is forbidden or consequential,
- optional target location/object can be used.

Deploy resolution:
- success places trap/hazard/entity in room,
- partial creates unstable/noisy/visible trap,
- failure wastes time or damages item,
- critical failure self-triggers.

Minimum integration:
Placed trap can provide a one-time advantage when the player lures or fights a hostile in that room. If a full trap combat loop is too large, store a pending room effect:
room.state["player_traps"] = [...]

Save/load placed traps.

============================================================
6. NARRATOR HOOKS
============================================================

Narrator is mandatory lore feedback.

Add or verify categories:
- salvage_success
- salvage_partial
- salvage_fail
- salvage_critical_fail
- furniture_salvage
- tech_salvage
- bathroom_salvage
- safehouse_theft_attempt
- safehouse_theft_escalation
- sponsor_property_salvage
- corpse_loot
- corpse_strip
- corpse_harvest
- monster_harvest
- crawler_corpse_looted
- disgusting_but_useful
- everything_is_material
- craft_success
- craft_partial
- craft_fail
- craft_critical_fail
- absurd_craft_attempt
- clever_craft
- dangerous_craft
- unstable_item_created
- improvised_weapon_created
- improvised_trap_created
- improvised_tool_created
- repair_success
- reinforce_success
- deploy_trap_success
- deploy_trap_fail
- trap_self_trigger
- rare_material_found
- sponsor_component_found
- anomalous_material_found
- forbidden_material_harvested
- audience_likes_recycling
- audience_disgusted
- sponsor_files_complaint

Add Polish lines with varied structure.
Avoid repetitive openings like:
"System odnotował..."
"System odnotował..."
"System odnotował..."

One or two such lines are fine; repeated parataxis is not.

Add English fallback if required by the localization/narrator architecture.

Trigger narrator on:
- notable salvage,
- first salvage,
- corpse harvesting,
- safehouse theft,
- rare material,
- successful craft,
- partial craft,
- critical craft failure,
- deploy trap,
- trap self-trigger,
- absurd invalid craft attempt.

Do not spam on every tiny material pickup.

============================================================
7. ACHIEVEMENTS
============================================================

If achievements system exists, use it.
If missing, create minimal revamp/achievements.py.

Achievement data:
- key
- name_key
- fallback_name_pl
- fallback_name_en
- description_key
- fallback_description_pl
- fallback_description_en
- category
- hidden
- reward
- unlocked flag stored on character as keys

Add achievements:

- wszystko_jest_surowcem
- meble_tez_krwawia
- recykling_agresywny
- rzemieslnik_z_paniki
- przepis_jaki_przepis
- rozbiorka_zwlok
- technicznie_to_loot
- kradziez_armatury
- sponsor_nie_pochwala
- pulapka_z_niczego
- samo_sie_rozstawilo
- inzynieria_odwagi
- obrzydliwe_ale_dziala
- zlota_raczka_lochu
- ekonomia_przetrwania
- smiec_wartosciowy

Hook achievements to:
- first salvage,
- furniture salvage,
- five objects salvaged,
- crafting under danger,
- successful tag-based improvised craft,
- corpse harvesting,
- morally questionable looting,
- bathroom fixture theft,
- sponsor/safehouse property violation,
- first crafted trap,
- critical failure while deploying trap,
- using crafted item to resolve encounter,
- crafting with organic corpse material,
- ten crafted items,
- twenty salvage operations,
- using trash/common material in major action.

Achievements should be primarily lore/audience feedback. Avoid large numeric rewards.

Save/load:
Unlocked achievements must persist.
Old saves without achievements must load safely.

============================================================
8. UI AND HELP
============================================================

Add or verify commands:
- materiały
- materialy
- materials
- pomoc craftingu
- craft help
- pomoc odzysku
- salvage help
- pomoc pułapek
- trap help
- deploy help
- pomoc rozstawiania

Help should show:
- available materials,
- known recipes,
- deployable items,
- examples of natural Polish commands,
- warning that safehouse property has consequences.

Inventory/character display should show:
- materials,
- crafted item quality/flaws,
- deployable tag,
- placed trap feedback if relevant,
- achievement unlock in log.

============================================================
9. MEMETICS PREPARATION ONLY
============================================================

Do not implement memetics yet.

Create docs/MEMETICS_BIBLE.md so the next prompt can implement it.

If adding references in code, keep them as TODO comments only:
- belief seeds
- rumor propagation
- logic exploits
- false orders
- social contagion

No new memetic mechanics in this prompt.

============================================================
10. TESTING
============================================================

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Then run:
python main_revamp.py

Smoke-test:
1. Start or load game.
2. Salvage furniture.
3. Search/loot a corpse.
4. Try "pozyskaj kości z drona" and confirm parser resolves source correctly or rejects material correctly.
5. Salvage a tech object.
6. Craft item by exact recipe.
7. Craft item by Polish alias.
8. Craft improvised item using material tags.
9. Deploy a trap.
10. Trigger safehouse theft consequence if possible.
11. Confirm narrator fires.
12. Confirm achievement unlocks.
13. Save/load.
14. Confirm materials, crafted items, achievements, entity states, and placed traps persist.

Report:
- docs created/updated,
- crafting compliance fixes,
- parser fixes,
- narrator categories added,
- achievements added,
- deploy behavior,
- save/load updates,
- remaining limitations.
