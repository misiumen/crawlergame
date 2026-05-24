# 07b — Knowledge, Clues, Rumors, and Resolution Integration

Use this prompt after:

1. `06c_finish_crafting_bible_narrator_achievements.md`
2. `07_memetic_belief_seed_system_UPDATED.md`

Run it before mouse-only UI work.

---

You are working on the `main` branch of the CRAWL PROTOCOL revamp.

Do not add unrelated features.
Do not rewrite the whole game.

## Goal

Integrate knowledge, rumors, clues, facts, passwords, weaknesses, routes, and memetic beliefs into encounter and objective resolution.

Information should matter mechanically.

If the player learns something useful, the game should be able to unlock new options later.

Examples:

- learning a service password unlocks `use_password`
- learning a boss weakness unlocks `exploit_weakness`
- learning about a maintenance route unlocks `take_secret_route`
- learning a machine protocol unlocks `logic_exploit`
- spreading a strong belief seed among machines unlocks `invoke_belief` or `identity_attack`
- learning a faction dispute unlocks `sow_distrust`
- learning a door maintenance cycle unlocks `wait_for_cycle`
- learning where the control panel is unlocks `disable_panel` or `repair_panel`

The system should support tabletop-like play: observation, rumors, social manipulation, memetic ideas, and clue chains should open solutions that were not available before.

---

## Files to inspect

Inspect existing code before changing anything:

- `revamp/world.py`
- `revamp/floor.py`
- `revamp/room.py`
- `revamp/character.py`
- `revamp/game.py`
- `revamp/parser_core.py`
- `revamp/validation.py`
- `revamp/resolution.py`
- `revamp/consequences.py`
- `revamp/encounters.py`
- `revamp/procgen.py`
- `revamp/content_loader.py`
- `revamp/memetics.py` if it exists
- `revamp/narrator.py`
- `revamp/save_load.py`
- `revamp/data/rumor_templates.py`
- `revamp/data/clue_templates.py` if it exists
- `revamp/data/encounter_templates.py`
- `revamp/data/floor_objective_templates.py`
- `revamp/data/memetic_templates.py` if it exists
- `docs/CONTENT_BIBLE.md`
- `docs/MEMETICS_BIBLE.md` if it exists

---

## Design rule

Do not make information cosmetic.

A rumor, clue, known fact, password, discovered route, observed weakness, or memetic belief should be able to do at least one of these:

- reveal a hidden room or route
- reduce DC
- unlock a new resolution method
- make an impossible action possible
- change NPC/crawler reaction
- modify encounter behavior
- change objective state
- add a new parser-recognized option
- create a narrator/audience/sponsor reaction

Do not make every clue perfectly true.

Rumors may be:

- true
- false
- biased
- outdated
- partial
- sponsor-manipulated
- crawler-misunderstood

But even false rumors should be useful as worldbuilding or risk.

---

## 1. Knowledge model

Create or update a lightweight knowledge model.

Preferred location:

- `revamp/knowledge.py`

If an equivalent module already exists, extend it instead.

Add dataclasses or simple dictionaries for:

### KnownClue

Fields:

- `key`
- `title`
- `description`
- `tags`
- `source`
- `reliability`
- `floor_number`
- `created_time`
- `reveals_tags`
- `enables_paths`
- `related_room_ids`
- `related_entity_ids`
- `related_objective_keys`
- `used`

### KnownFact

Fields:

- `key`
- `text`
- `tags`
- `source`
- `confidence`
- `floor_number`
- `created_time`
- `enables_paths`

### KnownRoute

Fields:

- `key`
- `from_room_id`
- `to_room_id`
- `route_type`
- `known`
- `locked`
- `requirements`
- `source`

### KnownPassword / AccessCode

Fields:

- `key`
- `label`
- `code_text`
- `tags`
- `opens`
- `source`
- `used`

If keeping this simpler is safer, implement as serializable dicts but keep the same conceptual fields.

---

## 2. Store knowledge in world/character

Add safe storage for knowledge.

Preferred:

`WorldState` stores world-level knowledge:

- `known_clues: dict[str, dict]`
- `known_facts: dict[str, dict]`
- `known_routes: dict[str, dict]`
- `known_passwords: dict[str, dict]`

`Character` may store personal knowledge if that is more consistent with the existing save structure.

Either approach is fine, but it must:

- serialize to save file
- load safely from old saves
- avoid duplicate clue spam
- support checking by tag/key/path

Add helper functions:

- `add_known_clue(world, clue)`
- `add_known_fact(world, fact)`
- `has_known_clue(world, key_or_tag)`
- `has_known_fact(world, key_or_tag)`
- `has_unlocked_path(world, path_key)`
- `get_known_tags(world)`
- `get_enabled_resolution_paths(world)`

---

## 3. Rumor selection should use objective tags

Problem:

Rumors can exist, but selection may not be biased toward current floor objectives.

Goal:

When generating or seeding rumors, prefer rumors connected to current floor objective tags, while still allowing noise and false leads.

If current objective tags include:

- `power`
- `cable`
- `control_panel`
- `boss`
- `safehouse`
- `machine`
- `crawler`
- `keycard`
- `maintenance`
- `chemical`
- `bathroom`
- `camera`
- `sponsor`
- `exit`
- `secret_route`
- `locked_door`

then prefer rumor templates whose:

- `tags`
- `reveals_tags`
- `objective_tags`
- `related_tags`

match those concepts.

Do not make all rumors useful.

Suggested distribution:

- 50 percent relevant or partially relevant
- 25 percent atmospheric/noisy
- 15 percent misleading/biased
- 10 percent rare/very useful

If this exact distribution is inconvenient, implement similar behavior.

---

## 4. Clue templates

If `revamp/data/clue_templates.py` does not exist, create it.

Add reusable clue templates with fields:

- `key`
- `title_pl`
- `title_en`
- `text_pl`
- `text_en`
- `tags`
- `reveals_tags`
- `enables_paths`
- `floor_min`
- `floor_max`
- `weight`
- `reliability`
- `possible_sources`
- `related_objective_tags`
- `false_variant_chance`

Add at least 20 clue templates.

Include clues for:

- service passwords
- machine protocols
- boss weaknesses
- hidden routes
- safehouse rules
- maintenance cycles
- keycard locations
- power reroutes
- camera blind spots
- faction disputes
- crawler rumors
- sponsor manipulation
- bathroom oddities
- chemical hazards
- salvage/crafting opportunities
- memetic belief propagation

Clues should be written in Polish first with English fallback.

Avoid repetitive anaphora and flat parataxis in writing. Vary sentence structure.

---

## 5. Learn clue/fact through actions

Hook knowledge into existing actions.

Knowledge can be gained from:

- inspecting objects
- searching rooms
- listening at doors
- talking to NPC/crawler
- reading terminal
- reading bulletin board
- safehouse rumors
- examining corpses
- hacking machines
- observing patrols
- using a camera/sponsor terminal
- memetic success/failure
- crafting/salvage discoveries

When a clue is learned:

- add to known_clues/known_facts
- log it clearly
- optionally trigger narrator
- optionally update journal
- mark clue as learned so it does not spam repeatedly

Log examples:

- `Nowa informacja: znasz hasło serwisowe do windy.`
- `Nowa możliwość: panel można wyłączyć przez obejście zasilania.`
- `Ta plotka brzmi podejrzanie, ale pasuje do śladów przy drzwiach.`
- `Zauważasz rytm patroli. To nie jest bezpieczeństwo, to rozkład jazdy.`

---

## 6. Clue-enabled resolution paths

Update encounter/objective resolution so knowledge can unlock new options.

When an encounter or objective has possible resolutions, allow additional options if the player has relevant clues/facts/routes/passwords/beliefs.

Examples:

### Door / elevator / locked exit

Without clue:

- force
- hack
- search for key

With known password:

- use_password

With known maintenance cycle:

- wait_for_cycle

With known cable route:

- reroute_power

### Machine enemies

Without memetic belief:

- fight
- sneak
- hack

With strong matching belief seed:

- invoke_belief
- logic_exploit
- identity_attack

### Boss

Without weakness:

- fight
- flee
- use_environment

With known weakness:

- exploit_weakness
- lure_to_specific_object
- use_specific_material

### Faction/social conflict

Without clue:

- negotiate
- intimidate
- bribe

With known faction dispute:

- sow_distrust
- reveal_secret
- blackmail

### Secret route

Without route clue:

- not visible

With route clue:

- inspect specific object
- open hidden route
- use crawlspace

---

## 7. Validator integration

Update `validation.py` so clue-gated paths are checked properly.

Rules:

- If a resolution requires a known clue/fact/path, validation must check it.
- If missing, the option should not appear in suggested actions or should fail with immersive feedback.
- If present, validation should allow the action and may reduce DC.
- If clue is unreliable, keep some risk.

Examples:

If player says:

`używam hasła serwisowego`

but no password known:

`Nie znasz żadnego hasła, które pasuje do tego panelu.`

If password known:

`valid = true`, resolution path `use_password`.

If player says:

`przypominam dronom o skradzionych sercach`

but no matching belief seed exists:

`valid = false` or high DC generic social action.

If matching belief seed exists and target has `machine` tag:

`valid = true`, resolution path `invoke_belief`.

---

## 8. Memetic integration

If `revamp/memetics.py` or belief seeds exist, integrate them.

A belief seed should be able to unlock special social/logic resolution paths when:

- belief strength is high enough
- target tags match
- context allows communication or symbolic invocation
- player knows or created the belief

Example:

Belief seed:

- key: `stolen_hearts_machines`
- target_tags: `machine`, `drone`, `construct`
- strength: 3
- enables_paths: `invoke_stolen_heart_myth`, `identity_attack`, `logic_confusion`

Against machine enemy:

- unlock `invoke_belief`
- CHA or INT check
- effects: hesitation, morale shift, target priority change, alarm, or confusion

Do not let memetics become magic without context.

It needs:

- audience
- communication channel
- symbol
- prior exposure
- vulnerability tag
- machine/social/cult/faction susceptibility

At least one must apply.

---

## 9. UI and command help

Update UI/help enough so the player can see known information.

Commands:

- `wiedza`
- `informacje`
- `plotki`
- `wskazówki`
- `clues`
- `rumors`
- `facts`

Show concise categories:

- Known clues
- Known facts
- Passwords/access codes
- Known routes
- Active memetic ideas, if any

Do not clutter the main UI.

When a clue unlocks a path, the log should mention it.

Suggested phrasing:

- `Odblokowano możliwość: użycie hasła serwisowego.`
- `Ta informacja może pomóc przy maszynach.`
- `Masz teraz konkretny powód, żeby wrócić do zamkniętych drzwi.`

---

## 10. Content and writing

Add or update Polish text for clues and clue-related feedback.

Style requirements:

- Polish first.
- Natural, immersive language.
- Avoid repetitive anaphora.
- Avoid flat parataxis chains.
- Keep log messages readable.
- Clues should feel like information gathered from a dangerous place, not tutorial popups.

Bad:

`Masz clue. Możesz iść do drzwi. Możesz użyć hasła.`

Better:

`Z poszarpanej notatki wynika, że panel windy przyjmuje krótkie hasła serwisowe. Jedno z nich ktoś dopisał tłustym markerem: JAZDA-0.`

---

## 11. Save / load

Persist:

- known_clues
- known_facts
- known_routes
- known_passwords
- used clues if tracked
- memetic belief links if relevant
- objective path unlocks if stored explicitly

Old saves must load safely.

No crash if fields are missing.

---

## 12. Testing

Run:

```bash
python -m py_compile revamp/*.py revamp/data/*.py
```

Then run:

```bash
python main_revamp.py
```

Smoke-test:

1. Generate or start Floor 1.
2. Learn a clue from search/inspect/talk/rumor.
3. Confirm it appears under `wiedza` or equivalent.
4. Confirm save/load preserves it.
5. Confirm a clue can unlock or validate a resolution path.
6. Confirm a missing clue blocks that path with clear feedback.
7. If memetics exist, create or use a matching belief seed.
8. Confirm belief seed can unlock an option only in a matching context.
9. Confirm rumors are biased toward objective tags in at least one generated floor.

Report:

- files changed
- knowledge storage model
- clue templates added
- rumor selection changes
- examples of clue-gated resolution paths
- memetic integration points
- remaining limitations
