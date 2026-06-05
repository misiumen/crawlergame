# Dungeon Kraulem → Godot: Rework & Port Plan

> Status: KIERUNEK USTALONY. This is the build bible for porting the game to
> Godot 4 and reworking it from a text/menu "PowerPoint" into a board-first,
> embodied tactical roguelike. Rationale in English (internal doc); ALL
> player-facing text stays Polish.
>
> Companion mockups (the UI spec): `_mockup_ideal.png` (combat),
> `_combat_screen.png` (dedicated combat screen), `_combat_body.png` (embodied
> combat), `_sys_1..9_*.png` (every reworked system).

---

## 0. The strategy in one paragraph

The simulation is excellent; the presentation is the problem. So we **keep the
brain, throw away the face.** The ~15–20k lines of *rules* (systemic engine,
combat, crafting, memetics, floor-gen) get rewritten in GDScript against a
clear spec — the existing Python version stays alive as a *reference oracle* to
verify the port matches. The ~25k lines of *content* (entities, rooms, recipes,
dialogue, body-plans — all already declarative tag-data) are **extracted to
JSON** and loaded at runtime; no rewrite, just serialization. The UI layer
(`ui.py`, `ui_nav.py`, parser-as-primary) is **deleted** and rebuilt as Godot
scenes around a spatial board. The single unifying change: the game gains a
**body and a space** — an embodied `@` on tiles where the systemic depth becomes
physical, and combat becomes the spine via reactive, breakable bodies.

---

## 1. Target game (what we're building)

A board-first, turn-based tactical roguelike (DCC/litRPG soul) where:

- You **move** an embodied character through tile rooms (no parser as primary input; ~8 hotkeys).
- The world is a **resource** — dismantle furniture/corpses/fixtures into materials (Dysmantle).
- **Crafting** turns materials (by tag) into concrete tools/weapons/coatings (Dead Island).
- **Combat is the spine**: a dedicated tactical-arena screen with **embodied, breakable bodies** that burn/bleed/corrode/sever, where positioning + environment + your built-up kit resolve the encounter. Brute force works but is slow and costly (the "in-between" bite).
- The deep systems are **visible and physical**: fire spreads tile-to-tile, you push enemies into hazards, a consequence-preview shows the systemic chain before you commit (Into the Breach perfect-information).
- The **DCC layer** (sponsors, audience, memetics, emergent classes, meta-progression) sits on top of a core that is finally fun to touch.

Two modes: **Explore** (calm, lean) and **Combat** (wipe to a focused arena).

---

## 2. Architecture — the clean split

Four layers, strictly separated. This separation is the whole point; it's what
makes the port tractable and keeps the renderer swappable.

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION  (Godot scenes/nodes — NEW, replaces ui.py) │
│  board, tokens, combat arena, panels, FX, body rigs       │
├─────────────────────────────────────────────────────────┤
│  SIM CORE  (GDScript — ported from Python rules)          │
│  systemic, combat, crafting, memetics, floor-gen, classes │
│  pure logic, no rendering, deterministic, unit-tested     │
├─────────────────────────────────────────────────────────┤
│  CONTENT DATA  (JSON — extracted from Python data/)       │
│  entities, rooms, recipes, salvage, statuses, body-plans  │
├─────────────────────────────────────────────────────────┤
│  LOCALIZATION  (PO/CSV — all player-facing Polish)        │
└─────────────────────────────────────────────────────────┘
```

Rule: **the sim core never imports a Godot node.** It takes data in, returns
state/events out. The presentation observes the sim and draws it. This is what
lets us test the rules headlessly and swap renderers later.

---

## 3. What ports how

| Current (Python) | Disposition | Notes |
|---|---|---|
| `engine/systemic.py` | **Rewrite → GDScript** | Crown jewel. Rules match on tags; port the resolver + tag inference (lines 75–128) first. |
| `engine/combat.py` | **Rewrite → GDScript** | Replace abstract `engaged/at_range` bands with **real tile positions**. |
| `content/crafting.py` | **Rewrite → GDScript** | Dual-path tag matching. |
| `systems/memetics.py`, `meta_progression.py`, `systems/classes.py`, `engine/consequences.py` | **Rewrite → GDScript** | Phase 5; well-specified. |
| `engine/floor_generator.py` + validation | **Rewrite → GDScript** | Preserve seeding/determinism + validation retry loop. |
| `content/data/*.py` (entities, rooms, recipes, salvage, body_plans, dialogues, sponsors, memetic/rumor templates…) | **Extract → JSON** | Already declarative dicts. Mechanical. |
| `ui/locales/*` | **Convert → Godot localization** (PO/CSV) | Honor Polish-only. |
| `ui/ui.py`, `ui/ui_nav.py`, `ui/journal.py`, `ui/layout.py`, `engine/parser_core.py` | **DELETE / rebuild** | This is the PowerPoint. The parser may survive as an optional power-user search box, never the default. |
| `tests/test_*.py` | **Port → GUT** (Godot Unit Test) + keep Python as oracle | Preserve the safety net. |
| save/load (pickle round-trip) | **Redesign** | New JSON save schema; don't port pickle. |
| `DungeonKraulem.exe` / PyInstaller | **Replace** | Godot one-click export. |

---

## 4. Godot project structure

```
res://
  data/                  # extracted JSON (entities.json, rooms.json, recipes.json, ...)
  sim/                   # SIM CORE — pure GDScript, no nodes
    tags.gd              # tag/property inference (systemic.py:75-128)
    systemic.gd          # elemental rule resolver
    combat.gd            # tile-based combat state + resolution
    crafting.gd
    floorgen.gd
    memetics.gd  classes.gd  consequences.gd
    rng.gd               # seeded RNG (determinism)
  autoload/              # singletons
    Game.gd              # run state, mode (explore/combat), save/load
    Data.gd              # loads + serves JSON content
    Events.gd            # signal bus (sim → presentation)
  scenes/
    Board.tscn           # the tile board (explore + combat arena share it)
    Token.tscn           # an actor on the board (procedural body rig)
    CombatScreen.tscn     # dedicated combat UI
    ExploreHUD.tscn
    panels/  (EnemyBody, PlayerCard, ActionBar, Log, Craft, Gear, Map, Dialogue, Memetics, RunSummary)
    fx/      (Fire, Blood, Acid, Shock, Impact, Floater)
  body/                  # procedural body system
    BodyRig.gd  parts/  damage_overlays/
  tests/                 # GUT tests mirroring tests/test_*.py
```

Autoloads `Game`, `Data`, `Events` are the spine. Presentation nodes listen to
`Events` signals (e.g. `damage_dealt`, `status_applied`, `limb_severed`) and
animate; they never compute rules.

---

## 5. Content-as-data pipeline

**One-time + repeatable extraction.** Write a small Python script
(`tools/export_json.py`) that imports the existing `content/data/*.py` modules
and dumps each dict to `res://data/*.json`. Because the data is already plain
dicts of tags/affordances/pools, this is near-mechanical. Re-run it whenever
content changes during the transition.

**Validated empirically (Phase 0 ran it):** 21 files / ~1,000+ entries exported
cleanly to `godot/data/`. Only **two** module-level structures are *not* pure
data and must be ported as GDScript instead: `floor_biomes.FLOOR_BIOMES` and
`meta_progression.UNLOCK_CATALOG` (the unlock **eval closures** — lambdas that
inspect post-run world state). So "extract to JSON" is true for the bulk;
data-with-logic is a small, known exception set, ported as code.

Example — an entity stays almost identical, just serialized:

```json
// data/entities.json (env)
"exposed_wiring": {
  "fallback_name": "obnażone przewody",
  "fallback_desc": "Pęk kabli wyrwanych ze ściany. Iskrzy.",
  "tags": ["electric","spark","wire","craft_material","hazardous"],
  "affordances": ["inspect","use","throw_at","craft","push_into"]
}
```

Rooms (`room_pool.py`) keep their template-with-pools shape; `floorgen.gd`
instantiates them exactly as the Python generator does. `body_plans.py` becomes
the backbone of the procedural body rig (§8) — fortunate that it already exists.

**Decision:** load JSON at runtime (editable, fast iteration) rather than baking
into Godot `Resource` binaries. Revisit only if load time becomes a problem.

---

## 6. The rule port + the oracle strategy

Port order follows the vertical slice (§7), not the file list. For each module:

1. Read the Python + its tests as the spec.
2. Reimplement in GDScript as pure functions on data.
3. **Oracle check (corrected after pressure test):** keep the Python game
   runnable as a regression oracle — but check **pure transforms with explicit
   inputs**, not whole seeded runs. Python and GDScript use different RNG
   algorithms, so identical seeds will NOT produce identical sequences; you
   cannot diff a generated floor byte-for-byte. What you *can* diff: "tags X +
   element Y → status Z", "this attack with these mods → this damage", "these
   materials + this category → this recipe match." For generation, assert
   structural/statistical properties (reachability, exit count, role mix), not
   equality.
4. Port the corresponding tests to GUT so the GDScript stays locked.

Determinism within Godot (reproducible runs) uses one seeded RNG (`sim/rng.gd`,
all randomness routed through it) — but it mirrors the Python *intent*, not the
Python *sequence*.

---

## 7. Phases & milestones

Each phase ends with something **runnable**. Sizes are relative (S/M/L/XL), not dates.

### Phase 0 — Foundations (M)
- Godot 4 project + repo structure (§4); GDScript chosen over C#.
- `tools/export_json.py` → first JSON dumps (entities, statuses, a few rooms).
- `sim/tags.gd` (tag inference) + `sim/rng.gd`.
- `Data` autoload loads JSON; a smoke test renders one room of tiles.
- GUT installed; first ported test green.

### Phase 0.5 — Decouple the rules IN PYTHON first (M) ★ NEW, from the pressure test
*Why: an audit of `game.py` found ~3,350 lines (33%) of genuine game rules
living inside the orchestrator — combat math, action handlers, lifecycle —
**not** in the dedicated rule modules. They're pygame-free (good) but tangled
into input/flow (bad). Porting that tangle straight to GDScript would mean
untangling a 10k-line file in an unfamiliar language.*

Refactor **in the running Python game** (tests stay green the whole time):
- ✅ **DONE** — Combat resolution (`_combat_attack`, `_apply_enemy_action`,
  `_run_enemy_turn`, `_tick_systemic_on`, dodge/flee/lure/use-environment,
  `_try_systemic_chain`, 13 methods / ~1.3k lines) → `engine/combat_rules.py`
  as `CombatRulesMixin`. Commit `0e8bc0c`. 133/133 green.
- ✅ **DONE** — All 42 `_attempt_*` action handlers (~3.1k lines) →
  `engine/action_handlers.py` as `ActionHandlersMixin`; shared salvage helper →
  neutral `engine/salvage_util.py`. Commit `c971f79`. 133/133 green.
- ⏸ **Run lifecycle — intentionally NOT pre-extracted.** Recon showed
  `_descend_or_win`, `_check_player_dead`, the offer/levelup methods all reference
  the module-level `STATE_*` flow constants (and some use `pygame`/`ui.`). They
  are fused to the state machine — they ARE the flow/orchestrator layer, not pure
  rules. Extracting them would mean relocating the whole `STATE_*` family across
  `game.py` for little gain, since this layer is **rewritten as Godot `Game.gd`
  flow** (Phase 1+), not ported as a clean module. Leave in `game.py`.
- ⏳ Optional later: turn `_try_systemic_chain` (currently a `self`-method in
  `combat_rules.py`) into a pure function in `systemic.py` — minor, defer.

**Outcome:** `game.py` 10,183 → **5,732 lines**. The pure game-rule mass the
audit flagged (combat + actions, ~4.4k lines) is now in standalone, pygame-free,
test-locked modules — exactly the per-module translation units the GDScript port
needs. The remainder of `game.py` is genuinely flow + UI + input, which the port
re-authors rather than translates. The oracle is now real for these modules
(clean function boundaries to diff). Phase 0.5 is complete.

### Phase 1 — Vertical slice: the "thinking encounter" (L) ★ the proof
*Maps to `_mockup_ideal.png` / `_combat_screen.png`.*
- `Board.tscn` + `Token.tscn`: embodied `@`, arrow/WSAD movement, bump-to-attack, fog/LOS.
- `combat.gd`: turn order, attack resolution, ~4 statuses — **tile positions, not bands.**
- Port the systemic rules needed for one combo: `electric + water`, `push_into_hazard`, fire-as-DoT.
- One enemy: physical-resistant + electric-weak, telegraphed. A puddle + sparking wire.
- **Consequence preview** drawn on the board.
- First juice: `Tween` moves, hit flash, damage floater, screen shake.
- **Definition of done = §11.** Do not proceed until the single encounter is fun with arrow keys.

✅ **BUILT & VERIFIED (headless).** `sim/board.gd` + `sim/entity.gd` (tiles, tags),
`sim/combat.gd` (bump-attack, tag damage-gradient, water+wire trap, enemy AI,
win/lose), `sim/encounters.gd` (the intake setup), `scenes/BoardView.gd` (one-key
movement, gliding tokens, hit-flash, damage floaters, shake, consequence preview,
enemy intent telegraph). 36 GDScript checks green (`test_sim`/`test_combat`/
`test_view`) + main scene boots clean. Run: `Godot --path godot`. **Remaining: the
§11 fun-gate is subjective — needs a human play session (can't be judged headless).**

### Phase 2 — Exploration + world-as-resource (L) ✅ DONE
*Maps to `_sys_1_explore.png`, `_sys_2_salvage.png`, `_sys_4_gear.png`.*
- ✅ Multi-room floor (`sim/floor.gd`): storage + hall, doors/exits, minimap, room
  transitions; player + run inventory + per-room state persist across rooms.
- ✅ Affordance interaction: dismantle objects ([E]) → materials; objects block movement.
- ✅ Enemy **awareness** (sleeping/noise/sight) → a real explore→engage beat.
- ✅ Crafting ([Z] warsztat): materials → electric weapon coating / damage upgrade
  (pulled forward from Phase 3 to close the salvage→power loop).
- ✅ Narration **DZIENNIK** log + materials/weapon/objective HUD (the readability fix).
- ⏸ **Deferred:** procedural `floorgen.gd` from room JSON — the floor is hand-authored
  for now; porting the full Python `floor_generator` is a later content-phase task.
  The exploration *experience* (rooms, doors, scavenge→craft→fight→descend) is complete.

**Verified:** 66 GDScript checks green (`test_sim`/`combat`/`view`/`floor`); main scene
+ exported exe boot clean.

### Phase 3 — Crafting + power compounding (M) ✅ DONE
*Maps to `_sys_3_craft.png`.*
- ✅ `crafting.gd` — **tag-grammar crafting, no fixed recipes**: combine tagged
  materials, infer a function, roll k20+INT vs DC, 5 outcome tiers (krytyk/
  sukces/częściowy/porażka/backfire), per-dominant backfire pools, affix + name
  generation, discovered-recipe book. Plus `rarity.gd` (5 tiers), `item.gd`,
  `box.gd` (lootboxes).
- ✅ Craft screen ([I] warsztat): 6 bench slots, combined-tag preview, DC readout,
  fuzzy prediction, stability/risk bars, outcome-tier list, recipe book; items +
  boxes tabs.
- ✅ Coatings/upgrades applied in combat; crafted items used by index; all drop
  pipelines produce unopened boxes the player opens.
- ✅ **Bonus (pulled in):** full sponsor + audience + lootbox systems ported from
  the Python engine (`sponsors.gd`, `audience.gd`) — 11 sponsors, attention
  routing by gameplay tags, gift thresholds, COLD/WARMING/HOT/VIRAL bands with
  combat mods. HUD strip + signals.

### Phase 4 — Embodiment upgrade: reactive bodies (L) ✅ DONE (sim + readout)
*Maps to `_combat_body.png`. The combat-as-spine payoff.*
- ✅ `sim/body.gd` — `BodyState` from `body_plans.json`: per-part hp + wounds +
  severity, layered on the canonical hp/death model. Located hits, part damage
  multipliers, wound typing (burn/shock/corrode/freeze/bleed/sever), limb
  severing, maims, butcher yields. Plus the **full `tags.gd` inference port**
  (the systemic foundation, previously a stub).
- ✅ Damage applied per-part by zone × element; `combat.gd` emits body_hit/maim/
  sever events; wound floaters + glyphs + per-part hit flash.
- ✅ Body-zone targeting ([T] cycles the aimed zone) + persistent wounds change
  behavior (broken leg → can't chase, head → stunned, arm → weaker).
- ✅ Large **body-readout panel** (parts colored by severity, HP pips, wound
  glyphs, aim highlight). Grid-token wound tinting = TODO polish.
- ⏸ **Deferred (visual rig):** the procedural part-shape rig with anchor points +
  AI-seeded art (`BodyRig.gd` proper) is the remaining presentation polish; the
  *systemic* embodiment (located breakable bodies driving combat) is complete and
  test-locked (40 GUT checks).

### Phase 5 — The DCC soul (XL, can parallelize) ✅ CORE DONE
*Maps to `_sys_5..9`.*
- ✅ `classes.gd` + `class_features.gd` — emergent classes: every action bumps a
  playstyle affinity; when one dominates, the Syndicate offers a 3-candidate
  class with a passive + a once-per-floor active. 12 classes, full combat wiring.
- ✅ `narrator.gd` — konferansjer commentary, generated faithfully from the Python
  locale (24 board categories: kills/env-kill/salvage/craft/audience/offer).
- ✅ `run_summary.gd` + `meta.gd` — end-of-run results screen (tallies, sponsors,
  anti-host death lines) + meta-progression: 20 board-evaluable unlocks from
  `UNLOCK_CATALOG` (closures ported as a condition spec), persisted to
  `user://meta.json` across runs. [Enter] starts a fresh run.
- ✅ sponsors/audience HUD already landed in Phase 3.
- ⏸ **Deferred to Phase 6 (need world surfaces the board doesn't have yet):**
  `memetics.gd` (needs free-text seeding + rooms-with-terminals/safehouses +
  in-game-minutes), dialogue trees (need NPCs on the board), floor-map/route
  gambling (needs the procedural multi-floor run). The faithful Python specs are
  captured; these layer on once Phase 6 builds their surfaces.
- The DCC *loop* is complete: scavenge→craft→fight→your-style-becomes-a-class→the
  host narrates it→the run ends with a recap that unlocks options for next time.

### Phase 6 — Procedural floors + content + ship polish (XL) ✅ CORE DONE
- ✅ **Procedural floor generation** (`sim/floorgen.gd`) — board-native rewrite of
  `floor_generator.py`: seeded determinism, a validation retry loop (entry→door
  reachability past placed objects, guaranteed descent), role-mixed rooms,
  difficulty scaling with depth.
- ✅ **Content from templates** — enemies from `entity_templates.MON` +
  `MOB_COMBAT_STATS` (hp/dice/to-hit/AC, floor-range gated, bosses excluded),
  objects from `ENV`; `sim/dice.gd` rolls content damage strings.
- ✅ **Multi-floor descent** — carries the whole run forward (player/class/kit/
  recipes/audience/sponsors); active recharges per floor; a breather heals 15%
  between floors; `FINAL_FLOOR` wins; depth in HUD; meta floor-unlocks fire.
- ✅ **Route gambling** (`sim/routes.gd`) — at the stairs you pick one of a few
  biomes; each biases enemy/object/trap counts AND which objects spawn (thematic
  floors). Persisted in the save and reproduced deterministically.
- ✅ **Save / load** (`sim/save.gd`) — per-floor checkpoint: store seed + depth +
  biome + carried run-state (no room layout — floors regenerate deterministically).
  Resume on boot, autosave on descent, clear on run-end. (`Meta` persists unlocks.)
- ✅ **NPC dialogue** (`sim/dialogue.gd`) — talkable NPCs on the floor; single-
  exchange nodes with audience/sponsor/material/flavor effects (board distillation
  of `dialogue.py`).
- ✅ **Elemental combat** (`sim/combat.gd`) — fire/acid/cold typed by tags (matter
  rules made real), status DoT (burning/poisoned/corroded) + corroded-AC, and
  **usable thrown/trap items** (the crafting→combat loop was broken: grenades you
  couldn't throw). Fire tiles ignite the stepper.
- ✅ **Boss finale** (`sim/floorgen.gd`) — `FINAL_FLOOR` is a gated boss arena;
  bosses/minibosses (previously excluded everywhere) finally appear; the exit only
  opens once the arena is cleared.
- ✅ **Title screen + web export config** — front-end (continue / new run / unlock
  count); `export_presets.cfg` Web preset + `build-web.bat` (you install the Web
  templates once, then one-click).
- ✅ **Fix exposed by procgen:** clearing a room no longer locks the player out of
  moving — only death is terminal (`_check_end` reworked).
- **Genuinely needs YOU (not code):**
  - **Memetics** — needs a free-text input surface + in-game-minute propagation;
    doesn't fit the hotkey board. Faithful spec captured; a design call.
  - **Audio / art assets** — music/SFX/sprites; the immediate-mode board has juice
    (tweens, flash, shake, floaters, fire tiles) but no authored audio/art.
  - **Web export run** — the preset + script ship; needs the Web export templates
    installed in your Godot to actually produce the build.
  - **Balance / playtest feel** — subjective; needs a human at the keyboard.
  - **Full dialogue trees** (multi-node + skill checks) — the single-exchange
    version ships; trees are a clean extension.

**Test coverage at end of Phase 6: 380 GUT checks across 15 suites** (sim, combat,
crafting, body, classes, narrator, meta, floorgen, routes, save, dialogue,
elements, boss, floor, view). Game boots clean; one-click exe builds.

---

## 8. The embodiment / body system (detail)

The thing that makes combat the spine. **Layered, not monolithic.**

- **Body-plans** (`body_plans.py`): *confirmed it exists and ports clean as JSON* — but it is **zone + damage logic** (head/torso/limb hit-mods, damage multipliers, maim statuses, butcher yields), NOT visual rig data. It gives you the *zones to map onto* a rig. The **visual rig itself** (part shapes, anchor points, art) is **new authoring** in Godot: quadruped, humanoid, blob, drone (the plans already group monsters this way), each a small set of part nodes at anchor points, with `body_plans` zones bound to them.
- **Tag-driven skin:** palette + decorations from the monster's tags. A rat and a guard reuse rigs; tags differentiate them. → 141 monsters from a bounded part kit, not 141 sprites.
- **Damage = generic operations on a part**, driven by *which zone* (combat already knows) × *what kind* (from tags):
  - sever → hide part + stump cap + spawn gore chunk; break → rotate/bent variant
  - burn → fire particle layer; bleed → blood decal + drips; corrode → green-pit decal + dissolve shader
- **Shared FX library** reused across every body. Art budget = body-plans + skins + FX, not monsters × states.
- **Art pipeline:** prototype with primitive shapes (as in `_combat_body.png`); later seed the part library with AI-generated pieces, composed procedurally. Renderer swap only — sim/data unchanged.

---

## 9. Keeping the soul

- **Polish-only player-facing text** stays law. All strings live in Godot
  localization (PO/CSV) converted from `ui/locales`. Internal/code in English.
- Narrator, sponsor voice lines, audience reactions, memetic rumor rendering —
  port the content as data; the konferansjer commentary is part of the juice,
  surfaced in the combat/explore log and on kills.
- Meta-progression unlocks preserve the DCC "each run grows the option pool."

---

## 10. Risks & key decisions

| Risk / decision | Call |
|---|---|
| GDScript vs C# | **GDScript** — Python-like, fits the team, simplest path. |
| Rewriting rules is the real cost | Mitigate with the **Python oracle** + ported GUT tests; port in slice order, not all at once. |
| Data extraction drift during transition | Re-runnable `export_json.py`; freeze content edits to Python until Phase 6, then migrate fully. |
| Determinism / seeded runs | Single `rng.gd`, mirror Python seeds, diff floor-gen against oracle. |
| Save format | New JSON schema; accept old saves are dropped (pre-1.0). |
| Scope creep (Phase 5 is huge) | Phases 1–4 are the *game*; 5 is the *soul*. Ship-playable after 4; layer 5 on. |
| Art | Procedural rigs first; AI-seeded parts later. Never block gameplay on art. |
| **game.py is 33% embedded rules, not a clean orchestrator** | Addressed by **Phase 0.5** (decouple in Python before porting). This is the single biggest correction from the pressure test. |
| **Realistic scope** | Audit estimate: ~3–4.5 months for a 1:1 functional port by one dev (UI rebuild ~3–4wk, flow ~2–3wk, rules ~4–6wk, content/glue + integration ~4–5wk). **Ship-playable target = end of Phase 4**; Phase 5 (the DCC soul) layers on after and can be paced/trimmed. |

---

## 11. Definition of done — the vertical slice (Phase 1 gate)

The whole project pivots on this one test. The slice is DONE — and the
direction PROVEN — when, with **only the arrow keys / a handful of hotkeys**:

1. Moving and bumping to attack feels responsive (tweened, with impact).
2. The enemy's intent + danger are readable **on the board** before you act.
3. The clever kill (lure/shove enemy onto the puddle → trigger the wire → shock)
   is **faster and cheaper** than brute-force bumping, and the game shows the
   chain via the consequence preview.
4. Brute force still **works** (walk up, bump it down) — just slower and costlier.
5. A neutral observer says the single encounter is *tense and satisfying*.

If yes → green-light Phases 2+. If no → iterate the slice; do not build outward
on an unproven loop.

---

## 12. Parallel-track strategy

Don't break the Python game. Keep it runnable through Phase 5 as (a) the
reference oracle for rule parity, (b) a place to keep iterating content, and
(c) a fallback. The Godot build becomes primary once it reaches feature parity
with the current playable scope (end of Phase 4). Cut over fully at Phase 6.
