class_name CombatSim
extends RefCounted
## Tile-based combat resolution. Pure logic: methods mutate sim state and RETURN
## arrays of event dicts. Presentation turns events into animations; the sim
## never touches a node.

const DMG_PHYSICAL := "physical"
const DMG_ELECTRIC := "electric"
const DMG_FIRE := "fire"
const DMG_ACID := "acid"
const DMG_EXPLOSION := "explosion"
const DMG_CRUSH := "crush"
const DMG_COLD := "cold"

var board: Board
var entities: Dictionary = {}
var player_id: int = 0
var player_ap: int = 2           # action points this round (move/hit 1, aimed 2)
var player_ap_max: int = 2
var round_completed := false     # set when the enemy phase just ran (view: tick the floor)
var lure: Dictionary = {}        # thrown decoy: {"cell": Vector2i, "turns": int}
var bombs: Array = []            # placed charges: [{cell: Vector2i, timer: int}]
var round_num: int = 1
var side: String = "player"
var over: bool = false       # terminally over (player dead) — blocks input
var cleared: bool = false    # this room's enemies are all down (exploration continues)
var outcome: String = ""
var _had_enemies: bool = false

var materials: Dictionary = {}      # run materials, shared ref from Floor
var items: Array = []               # GameItem list, shared ref from Floor
var discovered_recipes: Array = []  # recipe book, shared ref from Floor
var _audience: AudienceState        # may be null in headless unit tests
var _sponsors: SponsorState         # may be null in headless unit tests
var aim_zone: String = ""           # presentation sets this to aim the next player hit
var _curse_to_hit: int = 0          # occultist Curse: +AC vs enemies while active
var _curse_rounds: int = 0          # rounds the curse lasts
var _xp_done: Dictionary = {}       # enemy ids we've already granted kill-XP for

var rng := RandomNumberGenerator.new()

const DIRS8 := [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN,
	Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]
const SIGHT := 4

func _init(_board: Board, _entities: Dictionary, _player_id: int,
		seed_value: int = 0, _materials: Dictionary = {},
		_items: Array = [], _discovered: Array = [],
		_audience_ref = null, _sponsors_ref = null) -> void:
	board = _board
	entities = _entities
	player_id = _player_id
	materials = _materials
	items = _items
	discovered_recipes = _discovered
	_audience = _audience_ref
	_sponsors = _sponsors_ref
	rng.seed = seed_value
	_had_enemies = not enemies_alive().is_empty()

func player() -> CombatEntity:
	return entities[player_id]

func enemies_alive() -> Array:
	var out: Array = []
	for id in entities:
		var e: CombatEntity = entities[id]
		if e.faction == "enemy" and e.is_alive():
			out.append(e)
	return out

func allies_alive() -> Array:
	var out: Array = []
	for id in entities:
		var e: CombatEntity = entities[id]
		if e.faction == "ally" and e.is_alive():
			out.append(e)
	return out

# ── Damage model ──────────────────────────────────────────────────────────────

func effective_damage(target: CombatEntity, base: int, dmg_type: String) -> int:
	var dmg: float = float(base)
	# Physical: thick hide tanks it.
	if dmg_type == DMG_PHYSICAL and target.has_property("thick_hide"):
		dmg *= 0.5
	# Electric: explicit shock-weakness, or conductive matter conducts it.
	if dmg_type == DMG_ELECTRIC:
		if target.has_property("shock_weak"): dmg *= 2.0
		elif target.has_property("conductive"): dmg *= 1.5
	# Fire: flammable matter (organic/wood/cloth/...) burns hotter; wet resists.
	if dmg_type == DMG_FIRE:
		if target.has_property("flammable"): dmg *= 1.75
		if target.has_property("wet"): dmg *= 0.5
	# Acid: eats metal.
	if dmg_type == DMG_ACID and target.has_property("metal"):
		dmg *= 1.6
	# Cold: brittle once wet/frozen; fire creatures resist.
	if dmg_type == DMG_COLD:
		if target.has_property("wet"): dmg *= 1.5
		if target.has_property("flammable"): dmg *= 0.75
	return maxi(1, int(round(dmg)))

## Status effects shorthand: which DoT a status deals per turn, by type.
const STATUS_DOT := {"burning": [3, "fire"], "poisoned": [2, "physical"], "corroded": [1, "acid"]}

## Effective AC, reduced while the target is corroded (armor eaten away) and
## raised while a humanoid holds its guard (break it with a shove).
## Tactical readability: the player's % chance to land a hit on `target`
## (d20 + bonus vs effective AC, honoring the aimed zone). 5..95 clamp.
func hit_chance(target: CombatEntity) -> int:
	var hb: int = 3 + player().stat_mod("DEX")
	if aim_zone != "" and target.body != null:
		hb += target.body.to_hit_mod_for(aim_zone)
	return clampi((21 - (_eff_ac(target) - hb)) * 5, 5, 95)

func _eff_ac(target: CombatEntity) -> int:
	return target.ac + target.armor_bonus() \
		+ (3 if target.has_status("guard") else 0) \
		- (2 if target.has_status("corroded") else 0)

## Apply damage. If the target carries a procedural body, the blow is LOCATED:
## a zone is chosen (or the aimed one used), the part's damage multiplier scales
## the hit, and a wound/maim/sever is recorded — emitted as a `body_hit` event.
## Flat-HP actors (player, objects) keep the simple path, so older tests hold.
func _apply_damage(target: CombatEntity, base: int, dmg_type: String,
		zone := "", heavy := false) -> Array:
	var dmg: int = effective_damage(target, base, dmg_type)
	var evs: Array = []
	var hit: Dictionary = {}
	if target.body != null:
		if zone == "":
			zone = target.body.pick_zone(rng, "")
		dmg = maxi(1, int(round(dmg * target.body.damage_mul_for(zone))))
		hit = target.body.apply_hit(zone, dmg, dmg_type,
				target.has_property("bleeds"), heavy)
	target.take_damage(dmg)
	evs.append({"type": "damage", "target": target.id, "amount": dmg,
		"dmg_type": dmg_type, "zone": zone})
	if not hit.is_empty():
		evs.append({"type": "body_hit", "target": target.id, "zone": hit["zone"],
			"label": hit["label_pl"], "wound": hit.get("wound", ""),
			"severity": hit["severity"], "severed": hit.get("severed", false),
			"maim": hit.get("maim_status")})
		if hit.get("maim_status") != null and target.is_alive():
			target.add_status(hit["maim_status"], 3)
			evs.append({"type": "maim", "target": target.id,
				"status": hit["maim_status"], "label": hit["label_pl"],
				"severed": hit.get("severed", false)})
	if not target.is_alive():
		board.clear(target.cell)
		evs.append({"type": "death", "target": target.id})
		if target.faction == "enemy":
			evs += _style_credit(target, dmg_type)
	return evs

## The audience pays for INVENTION: the first kill by a new method this run
## triples the take; an enemy that never laid eyes on you is a spectacle.
const METHOD_PL := {
	"physical": "OSTRZE", "fire": "OGIEŃ", "electric": "PRĄD", "acid": "KWAS",
	"explosion": "EKSPLOZJA", "crush": "ZGNIECENIE", "poison": "TRUCIZNA",
	"cold": "MRÓZ",
}

func _style_credit(target: CombatEntity, dmg_type: String) -> Array:
	var evs: Array = []
	var p: CombatEntity = player()
	var methods: Dictionary = p.flags.get("kill_methods", {})
	var seen_before: bool = methods.has(dmg_type)
	methods[dmg_type] = int(methods.get(dmg_type, 0)) + 1
	p.flags["kill_methods"] = methods
	if not seen_before:
		evs.append({"type": "novel_kill", "method": METHOD_PL.get(dmg_type, dmg_type)})
		evs += _change_audience(6, "novel_kill")
	if not bool(target.flags.get("seen_player", false)):
		evs.append({"type": "unseen_kill", "name": target.name_pl})
		evs += _change_audience(5, "unseen_kill")
		_add_affinity("environment", 1)
	return evs

func _roll_hit(bonus: int, ac: int) -> bool:
	var mods := _audience.combat_mods() if _audience else {"to_hit": 0}
	return (rng.randi_range(1, 20) + bonus + int(mods.get("to_hit", 0))) >= ac

# ── Player actions ────────────────────────────────────────────────────────────

func player_move(dir: Vector2i) -> Array:
	if over or side != "player":
		return []
	var p: CombatEntity = player()
	var dest: Vector2i = p.cell + dir
	var occ: int = board.occupant_at(dest)
	var evs: Array = []
	var noise: int = 0
	var act_cost: int = 1
	if occ != -1 and occ != player_id:
		var t: CombatEntity = entities[occ]
		if t.faction == "object":
			return [{"type": "blocked", "reason": "object", "id": t.id}]
		if t.faction == "npc":
			return [{"type": "talk", "npc_id": t.id}]   # bump an NPC = talk to it
		if t.faction == "safehouse":
			return [{"type": "safehouse", "id": t.id}]  # bump a safehouse = use it
		if t.faction == "crawler":
			return [{"type": "crawler", "id": t.id}]    # bump a rival crawler = parley
		if t.faction == "ally":
			return [{"type": "blocked", "reason": "ally"}]   # don't swing at your own pet
		if aim_zone != "":
			act_cost = 2   # a called shot eats the whole round's focus
		evs += _player_attack(t)
		noise = 3   # a melee swing is heard by nearby enemies (but not the whole floor)
	elif board.is_free(dest):
		board.move(p.cell, dest)
		p.cell = dest
		evs.append({"type": "move", "id": player_id, "to": dest})
		evs += _on_enter_cell(p)
	else:
		return [{"type": "blocked"}]
	evs += _after_player_action(noise, act_cost)
	return evs

func _player_attack(target: CombatEntity) -> Array:
	var was_unaware: bool = not target.aware   # for the stealth-kill achievement
	target.aware = true
	# Aiming a small zone (head/limb) is harder to land but hits where you want.
	var zone: String = aim_zone
	var hit_bonus: int = 3 + player().stat_mod("DEX")   # agility sharpens your aim
	if zone != "" and target.body != null:
		hit_bonus += target.body.to_hit_mod_for(zone)
	var evs: Array = [{"type": "attack", "attacker": player_id, "target": target.id,
		"aim": zone, "target_unaware": was_unaware}]
	var p: CombatEntity = player()
	_add_affinity("melee", 1)
	# A spectre lets bare steel pass straight through — elements and coatings bite.
	if target.body_kind() == "spectral" and p.coating == "" and rng.randf() < 0.35:
		evs.append({"type": "phase", "id": target.id, "name": target.name_pl})
		aim_zone = ""
		evs += _after_player_action(1)
		return evs
	# Ranger's precise shot (active) forces the hit to land.
	var autohit: bool = p.next_attack_autohit
	if autohit:
		p.next_attack_autohit = false
	if autohit or _roll_hit(hit_bonus, _eff_ac(target)):
		var base: int = rng.randi_range(1, 6) + 2 + p.bonus_damage + p.stat_mod("STR")  # muscle hits harder
		if was_unaware:
			# Sneak strike: pillars + line of sight pay off. +50% before multipliers.
			base += maxi(2, base / 2)
			evs.append({"type": "sneak", "target": target.id})
		base += ClassFeatures.passive_bonus(p, "unarmed_dmg")   # bruiser/demoman fists
		if p.next_attack_mult > 1:                               # bruiser charge (active)
			base *= p.next_attack_mult
			p.next_attack_mult = 1
		var dtype: String = DMG_PHYSICAL
		if p.coating == "electric" and p.coating_charges > 0:
			dtype = DMG_ELECTRIC
			p.coating_charges -= 1
			if p.coating_charges <= 0:
				p.coating = ""
		elif p.coating == "poison" and p.coating_charges > 0:
			p.coating_charges -= 1
			if p.coating_charges <= 0:
				p.coating = ""
		# A strong physical cut can sever a limb.
		var heavy: bool = dtype == DMG_PHYSICAL and base >= 9
		evs += _apply_damage(target, base, dtype, zone, heavy)
		aim_zone = ""   # the aim is spent on this swing
		# A surviving humanoid raises its guard (+3 AC). Trading bumps stops
		# working — break the stance with a shove, or aim past it.
		if target.is_alive() and target.faction == "enemy" \
				and target.body_kind() == "humanoid" and not target.has_status("guard"):
			target.add_status("guard", 3)   # a 3-round stance; shove to break it early
			evs.append({"type": "guard", "id": target.id, "name": target.name_pl})
		# Spectacle tags for dead enemies.
		if not target.is_alive():
			p.run_kills += 1
			evs += _note_tag("kill_lethal")
			evs += _note_tag("combat")
			var mods := _audience.combat_mods() if _audience else {"audience_on_kill": 1}
			evs += _change_audience(int(mods.get("audience_on_kill", 1)), "kill")
			if dtype == DMG_ELECTRIC:
				evs += _note_tag("env_kill")
				_add_affinity("environment", 1)
		if dtype == DMG_ELECTRIC or dtype == DMG_PHYSICAL and base >= 8:
			evs += _note_tag("crit_hit")
	else:
		evs.append({"type": "miss", "attacker": player_id, "target": target.id})
	return evs

func player_shove(dir: Vector2i) -> Array:
	if over or side != "player":
		return []
	var p: CombatEntity = player()
	var adj: Vector2i = p.cell + dir
	var occ: int = board.occupant_at(adj)
	if occ == -1 or occ == player_id:
		return [{"type": "none", "action": "shove"}]
	var target: CombatEntity = entities[occ]
	var land: Vector2i = adj + dir
	var evs: Array = [{"type": "shove", "target": target.id, "dir": dir}]
	if target.faction == "object":
		# furniture is a weapon: free cell -> it slides; an enemy -> CRUSHED
		# under it; a wall -> it shatters where it stands.
		var locc: int = board.occupant_at(land)
		if board.is_free(land):
			board.move(target.cell, land)
			target.cell = land
			evs.append({"type": "move", "id": target.id, "to": land})
		elif locc != -1 and entities.has(locc) and entities[locc].faction == "enemy":
			var victim: CombatEntity = entities[locc]
			evs += _apply_damage(victim, 5, DMG_CRUSH)
			if victim.is_alive():
				victim.add_status("stunned", 1)
				victim.intent = {}
				evs.append({"type": "slam", "id": victim.id, "name": victim.name_pl})
			target.hp = 0; target.alive = false
			board.clear(target.cell)
			evs.append({"type": "obj_break", "id": target.id, "name": target.name_pl})
		else:
			target.hp = 0; target.alive = false
			board.clear(target.cell)
			evs.append({"type": "obj_break", "id": target.id, "name": target.name_pl})
		_add_affinity("environment", 1)
		evs += _after_player_action(3)
		return evs
	if target.has_status("guard"):
		target.statuses.erase("guard")   # a shove breaks the stance
		evs.append({"type": "guard_break", "id": target.id})
	if board.is_free(land):
		board.move(target.cell, land)
		target.cell = land
		evs.append({"type": "move", "id": target.id, "to": land})
		evs += _on_enter_cell(target)
	else:
		# Slammed into a wall (or another body): hurt, STUNNED, intent cancelled.
		evs += _apply_damage(target, 2, DMG_PHYSICAL)
		if target.is_alive():
			target.add_status("stunned", 1)
			target.intent = {}
			evs.append({"type": "slam", "id": target.id, "name": target.name_pl})
		var owall: int = board.occupant_at(land)
		if owall != -1 and owall != player_id and entities.has(owall):
			var bystander: CombatEntity = entities[owall]
			if bystander.faction != "object":
				evs += _apply_damage(bystander, 2, DMG_PHYSICAL)
	evs += _after_player_action()
	return evs

func player_wait() -> Array:
	if over or side != "player":
		return []
	var evs: Array = [{"type": "wait"}]
	evs += _after_player_action(0, 99)   # end the round outright
	return evs

## Throw a crafted thing at a cell (range 4, needs line of sight). 1 AP.
## "acid": auto-hits the cell + splashes neighbours. "lure": enemies retarget.
func player_throw(kind: String, cell: Vector2i) -> Array:
	if over or side != "player":
		return []
	var p: CombatEntity = player()
	var d: Vector2i = (cell - p.cell).abs()
	if maxi(d.x, d.y) > 4 or not board.has_los(p.cell, cell):
		return [{"type": "none", "action": "throw"}]
	var evs: Array = [{"type": "throw", "kind": kind, "cell": cell}]
	match kind:
		"acid":
			var occ: int = board.occupant_at(cell)
			if occ != -1 and occ != player_id and entities.has(occ):
				var t: CombatEntity = entities[occ]
				evs += _apply_damage(t, rng.randi_range(3, 8), DMG_ACID)
				if t.is_alive():
					t.add_status("corroded", 2)
			for dd in DIRS8:
				var occ2: int = board.occupant_at(cell + dd)
				if occ2 != -1 and occ2 != player_id and entities.has(occ2):
					var t2: CombatEntity = entities[occ2]
					if t2.faction != "object":
						evs += _apply_damage(t2, 2, DMG_ACID)
			_add_affinity("environment", 1)
		"lure":
			lure = {"cell": cell, "turns": 2}
			evs.append({"type": "lure_set", "cell": cell})
			# the decoy SCREAMS where it lands — ears near IT wake up (they heard
			# a noise, they did not see you; ZAOCZNE stays on the table)
			for le in enemies_alive():
				var ld: Vector2i = (le.cell - cell).abs()
				if maxi(ld.x, ld.y) <= 6 and not le.aware:
					le.aware = true
					evs.append({"type": "notice", "id": le.id})
	evs += _after_player_action(5)   # throwing is noisy — that can be the point
	return evs

## Plant a charge on your own or an adjacent free cell. Fuse: 5 rounds.
func player_place_bomb(cell: Vector2i) -> Array:
	if over or side != "player":
		return []
	var p: CombatEntity = player()
	var d: Vector2i = (cell - p.cell).abs()
	if maxi(d.x, d.y) > 1 or board.is_wall(cell) \
			or (board.occupant_at(cell) != -1 and board.occupant_at(cell) != player_id):
		return [{"type": "none", "action": "bomb"}]
	bombs.append({"cell": cell, "timer": 5})
	var evs: Array = [{"type": "bomb_placed", "cell": cell}]
	evs += _after_player_action(1)
	return evs

## Detonation: damage by ring, INNER walls crumble, objects die, gas pockets
## sympathize, other charges chain — and the bang pulls every ear to the crater.
func _explode(cell: Vector2i, radius: int, chain: Array) -> Array:
	var evs: Array = [{"type": "explosion", "cell": cell, "radius": radius}]
	chain.append(cell)
	for dy in range(-radius, radius + 1):
		for dx in range(-radius, radius + 1):
			var c: Vector2i = cell + Vector2i(dx, dy)
			if not board.in_bounds(c):
				continue
			var ring: int = maxi(absi(dx), absi(dy))
			if board.is_wall(c) and c.x > 0 and c.y > 0 and c.x < board.w - 1 and c.y < board.h - 1:
				board.set_wall(c, false)
				evs.append({"type": "wall_break", "cell": c})
			var occ: int = board.occupant_at(c)
			if occ != -1 and occ != -2 and entities.has(occ):
				var t: CombatEntity = entities[occ]
				if t.faction == "object":
					t.hp = 0; t.alive = false
					board.clear(c)
					evs.append({"type": "death", "target": t.id})
				elif t.is_alive():
					evs += _apply_damage(t, maxi(4, 14 - 4 * ring), DMG_EXPLOSION)
			if board.hazard_at(c) == "gas" and ring > 0:
				board.set_hazard(c, "")
				evs += _explode(c, 1, chain)
	# secondary fires near the crater
	for _i in 2:
		var fc: Vector2i = cell + Vector2i(rng.randi_range(-1, 1), rng.randi_range(-1, 1))
		if board.in_bounds(fc) and not board.is_wall(fc) and board.hazard_at(fc) == "":
			board.set_hazard(fc, "fire")
	# chain other charges caught in the blast
	for b in bombs.duplicate():
		var bc: Vector2i = b["cell"]
		if bc in chain:
			continue
		if maxi(absi(bc.x - cell.x), absi(bc.y - cell.y)) <= radius:
			bombs.erase(b)
			evs += _explode(bc, 2, chain)
	# the bang: wake everything nearby and pull it to the crater
	for e in enemies_alive():
		var dd: Vector2i = (e.cell - cell).abs()
		if maxi(dd.x, dd.y) <= 12:
			e.aware = true
	lure = {"cell": cell, "turns": 1}
	return evs

func _tick_bombs() -> Array:
	var evs: Array = []
	for b in bombs.duplicate():
		b["timer"] = int(b["timer"]) - 1
		evs.append({"type": "bomb_tick", "cell": b["cell"], "timer": b["timer"]})
		if int(b["timer"]) <= 0:
			bombs.erase(b)
			evs += _explode(b["cell"], 2, [])
	return evs

## The world breathes once per round: fire spreads to flammable matter, gas
## kisses flame, anyone STANDING in a fire keeps burning.
func _environment_round() -> Array:
	var evs: Array = []
	var fires: Array = []
	for c in board.hazards:
		if str(board.hazards[c]) == "fire":
			fires.append(c)
	for fc in fires:
		for d in DIRS8:
			var n: Vector2i = (fc as Vector2i) + d
			if not board.in_bounds(n):
				continue
			if board.hazard_at(n) == "gas":
				board.set_hazard(n, "")
				evs += _explode(n, 1, [])
				continue
			var occ: int = board.occupant_at(n)
			if occ != -1 and entities.has(occ):
				var t: CombatEntity = entities[occ]
				if t.faction == "object" and (t.tags.has("flammable") or t.tags.has("wood")) \
						and rng.randf() < 0.35:
					t.hp = 0; t.alive = false
					board.clear(n)
					board.set_hazard(n, "fire")
					evs.append({"type": "ignite", "cell": n, "name": t.name_pl})
	for id in entities.keys():
		var e: CombatEntity = entities[id]
		if e.is_alive() and e.faction != "object" and board.hazard_at(e.cell) == "fire":
			evs += _apply_damage(e, 2, DMG_FIRE)
	return evs

func player_interact() -> Array:
	if over or side != "player":
		return []
	# An adjacent NPC takes priority — talk to it.
	for d in DIRS8:
		var occ: int = board.occupant_at(player().cell + d)
		if occ != -1 and occ != player_id and entities[occ].faction == "npc":
			return [{"type": "talk", "npc_id": occ}]
	for d in DIRS8:
		var occ: int = board.occupant_at(player().cell + d)
		if occ != -1 and occ != player_id:
			var t: CombatEntity = entities[occ]
			if t.faction == "object" and "salvage" in t.affordances:
				return _salvage(t)
	return [{"type": "none", "action": "salvage"}]

# ── Bench crafting (replaces old craftables/craft) ────────────────────────────

## Preview the bench without mutating anything. Returns preview dict from Crafting.
func bench_preview(slot_names: Array) -> Dictionary:
	if slot_names.is_empty():
		return {}
	return Crafting.preview(slot_names, discovered_recipes)

## Attempt a craft. Spends materials, creates item, awards INT XP, applies backfire.
func bench_attempt(slot_names: Array) -> Array:
	if over or side != "player":
		return []
	if slot_names.is_empty():
		return [{"type": "none", "action": "craft"}]
	# Check all materials are available.
	var counts: Dictionary = {}
	for mat in slot_names:
		counts[mat] = int(counts.get(mat, 0)) + 1
	for mat in counts:
		if int(materials.get(mat, 0)) < int(counts[mat]):
			return [{"type": "craft_fail", "reason": "brak materiałów: " + mat}]

	var p := player()
	# Engineer's crafting passive sweetens the roll alongside INT.
	var craft_mod := p.int_mod() + ClassFeatures.passive_bonus(p, "crafting")
	var result := Crafting.attempt(slot_names, materials, discovered_recipes,
			rng, craft_mod)
	p.int_xp += int(result.get("int_xp_gained", 0))
	_add_affinity("crafting", 2 if result.get("outcome") in ["krytyk", "sukces"] else 1)

	var item: Variant = result.get("item")
	if item is GameItem:
		items.append(item)

	var evs: Array = result.get("events", []).duplicate()

	var bf: Variant = result.get("backfire")
	if bf is Dictionary:
		evs.append_array(_apply_backfire(bf))

	var outcome: String = result["outcome"]
	var aud_delta := 1
	if outcome == "krytyk":
		aud_delta = 5
		evs.append_array(_note_tag("clever_craft"))
	elif outcome == "sukces":
		aud_delta = 2
		evs.append_array(_note_tag("crafting"))
	elif outcome == "backfire":
		aud_delta = 3   # audience loves when things explode
	evs.append_array(_change_audience(aud_delta, "craft"))
	evs += _after_player_action(1)
	return evs

func _apply_backfire(bf: Dictionary) -> Array:
	var evs: Array = []
	var p := player()
	var desc: String = bf.get("desc", "")
	evs.append({"type": "backfire_desc", "desc": desc})
	match bf.get("type"):
		"damage":
			var dtype := DMG_ELECTRIC if bf.get("dmg_type") == "electric" else DMG_PHYSICAL
			evs += _apply_damage(p, int(bf.get("dmg", 2)), dtype)
			if bf.has("status"):
				p.add_status(bf["status"], int(bf.get("turns", 1)))
				evs.append({"type": "status", "target": player_id,
							"status": bf["status"], "turns": bf.get("turns", 1)})
		"coating_lost":
			p.coating = ""
			p.coating_charges = 0
		"alert_enemies":
			evs += _update_awareness(int(bf.get("radius", 4)))
		"max_hp_loss":
			p.max_hp = maxi(1, p.max_hp - int(bf.get("amount", 1)))
		"int_xp_loss":
			p.int_xp = maxi(0, p.int_xp - int(bf.get("amount", 5)))
		"status":
			p.add_status(bf["status"], int(bf.get("turns", 2)))
		# "materials_lost" already handled by Crafting.attempt spending them
	return evs

## Use item at index `item_idx` in the items array.
func player_use_item(item_idx: int) -> Array:
	if over or side != "player":
		return []
	if item_idx < 0 or item_idx >= items.size():
		return [{"type": "none", "action": "use_item"}]
	var item := items[item_idx] as GameItem
	var p := player()
	# A thrown weapon needs something to throw at — don't waste it on an empty room.
	if item.category == GameItem.CAT_THROWN and enemies_alive().is_empty():
		return [{"type": "none", "action": "throw"}]
	var evs: Array = [{"type": "item_used", "uid": item.uid, "name": item.name_pl,
		"category": item.category, "rarity": item.rarity}]
	match item.category:
		GameItem.CAT_COATING:
			p.coating = item.effect.get("coating", "")
			p.coating_charges = item.charges
			evs.append({"type": "coating_applied", "coating": p.coating,
						"charges": p.coating_charges})
		GameItem.CAT_MEDICAL:
			var heal_amount: int = int(round(int(item.effect.get("heal", 8))
					* ClassFeatures.heal_multiplier(p)))   # medic doubles healing
			var actual := mini(heal_amount, p.max_hp - p.hp)
			p.hp = mini(p.max_hp, p.hp + heal_amount)
			evs.append({"type": "heal", "target": player_id, "amount": actual})
			_add_affinity("support", 1)
		GameItem.CAT_WEAPON:
			p.bonus_damage += int(item.effect.get("damage_bonus", 0))
			evs.append({"type": "weapon_upgrade",
						"bonus": item.effect.get("damage_bonus", 0)})
		GameItem.CAT_ARMOR:
			# Equip into its slot; the previously worn piece (if any) returns to the
			# pocket. Worn armor adds to AC via CombatEntity.armor_bonus().
			var slot: String = item.effect.get("slot", "body")
			var prev = p.equipment.get(slot, null)
			p.equipment[slot] = item
			items.remove_at(item_idx)
			if prev != null:
				items.append(prev)
			evs.append({"type": "armor_equipped", "slot": slot,
						"ac_bonus": item.effect.get("ac_bonus", 1), "name": item.name_pl})
			evs += _after_player_action(0)
			return evs
		GameItem.CAT_SCROLL:
			# A recipe scroll teaches a recipe permanently (DCC loves found schematics).
			var rec: Dictionary = item.effect if not item.effect.is_empty() else {"name": item.name_pl, "tags": item.tags}
			var known := false
			for r in discovered_recipes:
				if (r as Dictionary).get("name", "") == rec.get("name", ""):
					known = true
			if not known:
				discovered_recipes.append(rec)
			evs.append({"type": "recipe_learned", "name": rec.get("name", item.name_pl), "known": known})
		GameItem.CAT_SPELL:
			# A spell scroll teaches a spell — if your race can grasp magic at all.
			if not Spells.can_learn(p):
				evs.append({"type": "spell_learned", "name": "", "fizzle": true})
			else:
				var skey: String = item.effect.get("spell", "")
				if skey == "" or Spells.is_known(p, skey):
					skey = Spells.random_unknown(p, rng)
				if skey != "" and Spells.learn(p, skey):
					evs.append({"type": "spell_learned", "name": Spells.def_of(skey).get("name", skey)})
				else:
					evs.append({"type": "spell_learned", "name": "", "fizzle": true})
		GameItem.CAT_TOOL:
			if item.effect.has("recharge_coating") and p.coating != "":
				p.coating_charges += int(item.effect["recharge_coating"])
				evs.append({"type": "coating_recharged",
							"charges": p.coating_charges})
		GameItem.CAT_THROWN:
			evs += _throw_item(item)
		GameItem.CAT_TRAP:
			evs += _deploy_trap(item)
	# Consume or keep.
	if item.charges == 0:
		pass   # permanent upgrade — stays in items list
	elif item.charges <= 1:
		items.remove_at(item_idx)
	else:
		item.charges -= 1
	evs += _after_player_action(1)
	return evs

# ── Thrown weapons + traps ────────────────────────────────────────────────────

## Hurl a thrown item at the nearest enemy: element damage (+ a splash if the
## item rolled an AoE affix), an optional lingering status, and an optional hazard
## tile left under the target (e.g. fire). Spectacle the audience loves.
func _throw_item(item: GameItem) -> Array:
	var evs: Array = []
	var fx: Dictionary = item.effect
	var dmg_type: String = fx.get("dmg_type", DMG_PHYSICAL)
	if dmg_type == "corrosive": dmg_type = DMG_ACID   # crafting's name -> damage model's
	var base: int = int(fx.get("base_dmg", 5))
	var target := _nearest_enemy()
	if target == null:
		return evs
	evs.append({"type": "throw", "name": item.name_pl, "target": target.id,
		"dmg_type": dmg_type})
	var hits: Array = [target]
	if fx.get("aoe", false):
		for e in enemies_alive():
			if e != target and board.is_adjacent(e.cell, target.cell):
				hits.append(e)
	for h in hits:
		evs += _apply_damage(h, base, dmg_type)
		if fx.has("status") and h.is_alive():
			h.add_status(fx["status"], int(fx.get("status_turns", 2)))
			evs.append({"type": "status", "target": h.id, "status": fx["status"],
				"turns": int(fx.get("status_turns", 2))})
	# A hazard tile under the impact (fire pool, gas...).
	if fx.has("hazard") and board.in_bounds(target.cell):
		board.set_hazard(target.cell, fx["hazard"])
		evs.append({"type": "hazard_placed", "cell": target.cell, "kind": fx["hazard"]})
	evs += _note_tag("clever_action")
	evs += _change_audience(2, "throw")
	_add_affinity("ranged", 1)
	return evs

## Arm a trap on a free adjacent cell (a hazard the next stepper triggers).
func _deploy_trap(item: GameItem) -> Array:
	var evs: Array = []
	var kind: String = item.effect.get("hazard", "wire")
	var p := player()
	for d in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var c: Vector2i = p.cell + d
		if board.is_free(c) and board.hazard_at(c) == "":
			board.set_hazard(c, kind)
			p.run_traps_armed += 1
			_add_affinity("trap", 1)
			evs.append({"type": "trap_armed", "cell": c, "kind": kind})
			return evs
	evs.append({"type": "none", "action": "trap"})
	return evs

# ── Class active ability ──────────────────────────────────────────────────────

## Fire the player's emergent-class active (once per floor). Returns events; the
## ability counts as the player's action, so the enemy turn follows.
## Fire the pet's signature ability (per-floor cooldown, free action like a class
## active). Each companion has ONE, ported from the pygame ability kit.
func use_companion_ability(floor_num: int) -> Array:
	if over or side != "player":
		return []
	var comp: CombatEntity = null
	for id in entities:
		if entities[id].faction == "ally" and entities[id].is_alive():
			comp = entities[id]; break
	if comp == null:
		return [{"type": "companion_blocked", "reason": "Brak towarzysza."}]
	if int(comp.flags.get("ability_floor", -1)) == floor_num:
		return [{"type": "companion_blocked", "reason": "Umiejętność towarzysza już użyta na tym piętrze."}]
	comp.flags["ability_floor"] = floor_num
	var evs: Array = [{"type": "companion_ability", "key": comp.monster_key, "name": comp.name_pl}]
	match comp.monster_key:
		"companion_suczka_recyklingu":          # find_scrap: sniffs out a pile of scrap
			var amt := 4 + floor_num * 2
			materials["złom"] = int(materials.get("złom", 0)) + amt
			evs.append({"type": "scrap_found", "amount": amt})
		"companion_dron_sponsorski":            # scout: marks the nearest foe (next hit lands)
			player().next_attack_autohit = true
			var f := _nearest_enemy_to(player().cell)
			evs += _change_audience(2, "pet_scout")
			evs.append({"type": "marked", "id": (f.id if f != null else -1)})
		"companion_kot_ministerstwa":           # distract: an enemy loses its next turn
			var foe := _nearest_enemy_to(comp.cell)
			if foe != null:
				foe.add_status("stunned", 1)
				evs.append({"type": "distract", "id": foe.id, "name": foe.name_pl})
		"companion_papuga_anty_host":           # morale_boost: works the crowd hard
			evs += _change_audience(8, "pet_morale")
			evs.append({"type": "buff", "label": "+8 widowni (papuga rozgrzewa tłum)"})
		_:
			evs += _change_audience(3, "pet")
	return evs

## Cast a spell at the nearest enemy (ranged systemic damage), reusing the
## element engine. Costs mana (and sometimes HP); scales with INT. Takes a turn.
func cast_spell(key: String) -> Array:
	if over or side != "player":
		return []
	var sp := Spells.def_of(key)
	if sp.is_empty():
		return [{"type": "none", "action": "cast"}]
	var p := player()
	if not Spells.is_known(p, key):
		return [{"type": "cast_blocked", "reason": "Nie znasz tego zaklęcia."}]
	var cost: int = int(sp.get("mana", 0))
	var hp_cost: int = int(sp.get("hp_cost", 0))
	if p.mana < cost:
		return [{"type": "cast_blocked", "reason": "Za mało many."}]
	if hp_cost > 0 and p.hp <= hp_cost:
		return [{"type": "cast_blocked", "reason": "Za mało HP na tę krew."}]
	var kind: String = sp.get("kind", "element")
	# Self-only spell (mend) needs no target; everything else wants an enemy.
	var foe := _nearest_enemy_to(p.cell)
	if kind != "mend" and foe == null:
		return [{"type": "none", "action": "cast"}]
	p.mana -= cost
	if hp_cost > 0:
		p.hp = maxi(1, p.hp - hp_cost)
	var evs: Array = [{"type": "spell_cast", "key": key, "name": sp.get("name", key)}]
	var pow: int = 4 + rng.randi_range(0, 3) + p.stat_mod("INT")   # INT drives spellpower
	_add_affinity("tech", 1)
	match kind:
		"element":
			evs += _apply_damage(foe, pow, sp.get("dmg_type", DMG_PHYSICAL))
			if foe.is_alive() and sp.has("status"):
				foe.add_status(sp["status"], 2)
				evs.append({"type": "status", "target": foe.id, "status": sp["status"], "turns": 2})
		"push":
			var dir: Vector2i = Vector2i(signi(foe.cell.x - p.cell.x), signi(foe.cell.y - p.cell.y))
			if dir == Vector2i.ZERO:
				dir = Vector2i.RIGHT
			var dest: Vector2i = foe.cell + dir
			if board.is_free(dest):
				board.move(foe.cell, dest); foe.cell = dest
				evs.append({"type": "move", "id": foe.id, "to": dest})
				evs += _on_enter_cell(foe)        # a shove into a hazard still triggers it
		"drain":
			evs += _apply_damage(foe, pow + 3, DMG_PHYSICAL)
			evs += _heal_player(int(round(pow * 0.6)), "Krwawa danina")
		"void":
			evs += _apply_damage(foe, pow + 6, sp.get("dmg_type", DMG_COLD))
			var recoil := rng.randi_range(1, 4)
			p.hp = maxi(1, p.hp - recoil)
			evs.append({"type": "damage", "target": player_id, "amount": recoil, "dmg_type": "void"})
		"illusion":
			foe.add_status("stunned", 1)
			foe.aware = false
			evs.append({"type": "status", "target": foe.id, "status": "stunned", "turns": 1})
		"mend":
			evs += _heal_player(int(round(p.max_hp * 0.45)), "Wskrzeszenie")
	evs += _change_audience(2, "spell")
	evs += _after_player_action(2)   # casting is loud
	return evs

## Refill mana to max (call on each new floor) and recompute the INT-scaled cap.
func refill_mana() -> void:
	var p := player()
	p.max_mana = Spells.max_mana_for(p)
	p.mana = p.max_mana

## Nearest living enemy to a cell (Chebyshev), or null if none.
func _nearest_enemy_to(c: Vector2i) -> CombatEntity:
	var best: CombatEntity = null
	var bd := 1 << 30
	for e in enemies_alive():
		var d: int = maxi(absi(e.cell.x - c.x), absi(e.cell.y - c.y))
		if d < bd:
			bd = d; best = e
	return best

func use_class_active(floor_num: int) -> Array:
	if over or side != "player":
		return []
	var p := player()
	var gate := ClassFeatures.can_use_active(p, floor_num)
	if not bool(gate[0]):
		return [{"type": "class_active_blocked", "reason": gate[1]}]
	var name_pl := ClassFeatures.active_name(p.class_key)
	var evs: Array = [{"type": "class_active", "class_key": p.class_key, "name": name_pl}]
	match p.class_key:
		"bruiser":
			p.next_attack_mult = 2
			evs.append({"type": "buff", "label": "Następny cios x2"})
		"ranger":
			p.next_attack_autohit = true
			evs.append({"type": "buff", "label": "Następny atak trafia na pewno"})
		"survivor":
			evs += _heal_player(int(round(p.max_hp * 0.35)), "Drugi oddech")
		"medic":
			p.statuses.erase("bleeding")
			evs += _heal_player(int(round(p.max_hp * 0.60)), "Triage")
		"engineer":
			for s in ["disarmed", "slowed", "stunned", "shocked", "poisoned", "burning"]:
				p.statuses.erase(s)
			evs += _heal_player(int(round(p.max_hp * 0.20)), "Szybka naprawa")
		"showman":
			evs += _change_audience(8, "hype")
			evs.append({"type": "buff", "label": "+8 widowni"})
		"negotiator":
			evs += _change_audience(6, "targi")
			p.next_attack_mult = maxi(p.next_attack_mult, 1)
			_add_affinity("diplomacy", 1)
			evs.append({"type": "buff", "label": "+6 widowni, układy nabite"})
		"scout":
			for e in enemies_alive():
				e.aware = false
			evs += _change_audience(3, "scout")
			evs.append({"type": "buff", "label": "Teren rozpoznany"})
		"trickster":
			for e in enemies_alive():
				e.aware = false
			evs.append({"type": "buff", "label": "Znikasz z pola widzenia"})
		"occultist":
			_curse_to_hit = 2
			_curse_rounds = 3
			evs.append({"type": "buff", "label": "Klątwa: wrogowie -2 do trafienia (3 rundy)"})
		"saboteur":
			var tgt := _nearest_enemy()
			if tgt != null:
				tgt.add_status("stunned", 1)
				evs.append({"type": "status", "target": tgt.id, "status": "stunned", "turns": 1})
				evs.append({"type": "buff", "label": "Sabotaż: %s oszołomiony" % tgt.name_pl})
		"demolitionist":
			for e in enemies_alive():
				evs += _apply_damage(e, 15, DMG_PHYSICAL)
			evs.append({"type": "buff", "label": "Wybuch: 15 obrażeń wszystkim"})
	p.class_active_used_floor = floor_num
	evs += _after_player_action(2)
	return evs

func _heal_player(amount: int, _label: String) -> Array:
	var p := player()
	var actual := mini(amount, p.max_hp - p.hp)
	p.hp = mini(p.max_hp, p.hp + amount)
	return [{"type": "heal", "target": player_id, "amount": actual}]

func _nearest_enemy() -> CombatEntity:
	var p := player()
	var best: CombatEntity = null
	var best_d := 1 << 30
	for e in enemies_alive():
		var d: int = maxi(absi(e.cell.x - p.cell.x), absi(e.cell.y - p.cell.y))
		if d < best_d:
			best_d = d; best = e
	return best

# ── Salvage ───────────────────────────────────────────────────────────────────

func _salvage(obj: CombatEntity) -> Array:
	var gained: Dictionary = {}
	for tag in obj.tags:
		match tag:
			"wood":           _gain(gained, "drewno", rng.randi_range(1, 3))
			"metal":          _gain(gained, "złom", rng.randi_range(1, 2))
			"cloth", "fabric":_gain(gained, "szmata", 1)
			"electric", "wire":_gain(gained, "przewód", 1)
			"plastic":        _gain(gained, "plastik", 1)
	if gained.is_empty():
		_gain(gained, "złom", 1)
	for k in gained:
		materials[k] = int(materials.get(k, 0)) + gained[k]
	board.clear(obj.cell)
	obj.alive = false
	var evs: Array = [{"type": "salvage", "target": obj.id, "gained": gained}]
	evs += _note_tag("salvage")
	evs += _change_audience(1, "salvage")
	player().run_corpses_salvaged += 1
	_add_affinity("tech", 1)
	if "wood" in obj.tags or "furniture" in obj.tags:
		_add_affinity("environment", 1)
	# "Cyborg Recyklingu" feeds scrap into itself — salvage patches you up.
	var pl := player()
	if pl.species_trait == "salvage_heal" and pl.is_alive() and pl.hp < pl.max_hp:
		var got := mini(3, pl.max_hp - pl.hp)
		pl.hp += got
		evs.append({"type": "heal", "target": player_id, "amount": got})
	evs += _grant_xp(5)   # everything is a resource — including XP
	evs += _after_player_action(7)
	return evs

## Bank XP from a non-kill source and emit the xp / level_up events (mirrors the
## per-level rewards in _award_kill_xp).
func _grant_xp(amount: int) -> Array:
	var p := player()
	var lv := p.gain_xp(amount)
	var evs: Array = [{"type": "xp", "amount": amount, "level": p.level,
		"xp": p.xp, "to_next": p.xp_to_next()}]
	for _i in lv:
		p.max_hp += 5
		p.hp = mini(p.max_hp, p.hp + 5)
		p.skill_points += 1
	if lv > 0:
		evs.append({"type": "level_up", "level": p.level, "levels": lv,
			"skill_points": p.skill_points, "max_hp": p.max_hp})
	return evs

func _gain(d: Dictionary, key: String, n: int) -> void:
	d[key] = int(d.get(key, 0)) + n

# ── Systemic ──────────────────────────────────────────────────────────────────

func _on_enter_cell(e: CombatEntity) -> Array:
	var evs: Array = []
	if board.hazard_at(e.cell) == "water" and _adjacent_live_wire(e.cell):
		var base: int = rng.randi_range(3, 18)
		evs.append({"type": "systemic", "element": "electric",
					"target": e.id, "via": "water+wire"})
		evs += _apply_damage(e, base, DMG_ELECTRIC)
		if e.is_alive():
			e.add_status("shocked", 1)
			evs.append({"type": "status", "target": e.id,
						"status": "shocked", "turns": 1})
		# Environmental kill is spectacular.
		if not e.is_alive() and e.faction == "enemy":
			player().run_kills += 1
			evs += _note_tag("env_kill")
			evs += _change_audience(5, "env_kill")
			if e.id != player_id:
				_add_affinity("environment", 2)
	# Fire tile: ignites whoever steps in (flammable matter burns harder).
	elif board.hazard_at(e.cell) == "fire":
		evs.append({"type": "systemic", "element": "fire", "target": e.id, "via": "fire_tile"})
		evs += _apply_damage(e, rng.randi_range(3, 7), DMG_FIRE)
		if e.is_alive():
			e.add_status("burning", 2)
			evs.append({"type": "status", "target": e.id, "status": "burning", "turns": 2})
		elif e.faction == "enemy":
			player().run_kills += 1
			evs += _note_tag("env_kill")
			evs += _change_audience(4, "env_kill")
	return evs

func would_shock_at(c: Vector2i) -> bool:
	return board.hazard_at(c) == "water" and _adjacent_live_wire(c)

func _adjacent_live_wire(c: Vector2i) -> bool:
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			if dx == 0 and dy == 0:
				continue
			if board.hazard_at(c + Vector2i(dx, dy)) == "wire":
				return true
	return false

# ── Audience + sponsor helpers ────────────────────────────────────────────────

func _note_tag(tag: String, weight: int = 1) -> Array:
	if _sponsors == null:
		return []
	return _sponsors.note_tag(tag, weight)

func _add_affinity(kind: String, amount: int = 1) -> void:
	player().add_affinity(kind, amount)

func _change_audience(delta: int, source: String = "") -> Array:
	if _audience == null:
		return []
	# Showman doubles audience gains.
	if delta > 0:
		delta = int(round(delta * ClassFeatures.audience_multiplier(player())))
	var crossing := _audience.change(delta, source)
	var evs: Array = [{"type": "audience_change", "delta": delta,
		"rating": _audience.rating, "band": _audience.band(),
		"crossed": crossing.get("crossed", false)}]
	if crossing.get("crossed", false):
		evs.append({"type": "audience_band_crossed",
			"from_band": crossing["from_band"],
			"to_band": crossing["to_band"],
			"direction": crossing["direction"]})
	return evs

# ── Turn flow ─────────────────────────────────────────────────────────────────

func _after_player_action(noise_radius: int = 0, cost: int = 1) -> Array:
	round_completed = false
	_round_noise = maxi(_round_noise, noise_radius)
	player_ap -= cost
	var evs: Array = _check_end()
	if over:
		return evs
	evs += _award_kill_xp()
	if player_ap > 0:
		# Round still open: awareness updates now (noise carries), enemies wait.
		evs += _update_awareness(_round_noise)
		return evs
	# ── Round closes: allies act, awareness, enemies EXECUTE then DECLARE ─────
	if _curse_rounds > 0:
		_curse_rounds -= 1
		if _curse_rounds <= 0:
			_curse_to_hit = 0
	evs += _ally_turn()          # your pet acts on your side, first
	if not over:
		evs += _check_end()
	evs += _update_awareness(_round_noise)
	_round_noise = 0
	side = "enemies"
	evs += _enemy_turn()
	if not over:
		evs += _check_end()
	evs += _award_kill_xp()
	# "Grzybica" slow regeneration: heal a little each round if you took the trait.
	var pl := player()
	if pl.species_trait == "regen" and pl.is_alive() and pl.hp < pl.max_hp:
		pl.hp = mini(pl.max_hp, pl.hp + 1)
		evs.append({"type": "heal", "target": player_id, "amount": 1})
	if pl.mana < pl.max_mana:               # slow mana regen between casts
		pl.mana += 1
	evs += _tick_bombs()
	evs += _environment_round()
	if not over:
		evs += _check_end()
	evs += _award_kill_xp()
	side = "player"
	round_num += 1
	player_ap = player_ap_max
	round_completed = true
	evs.append({"type": "round_end"})
	if not lure.is_empty():
		lure["turns"] = int(lure["turns"]) - 1
		if int(lure["turns"]) <= 0:
			lure = {}
			evs.append({"type": "lure_end"})
	return evs

var _round_noise: int = 0

## Grant the player XP for any enemy that has died since we last looked (covers
## both melee kills and damage-over-time deaths). Level-ups bump max HP + heal a
## little and bank a skill point; the presentation narrates it and hands out loot.
func _award_kill_xp() -> Array:
	var evs: Array = []
	for id in entities:
		var e: CombatEntity = entities[id]
		# The paid-out marker lives ON THE ENTITY, not on the sim: each room change
		# builds a fresh CombatSim over the same persistent entities, so a sim-local
		# ledger let you farm XP from old corpses by pacing between sectors.
		if e.faction != "enemy" or e.is_alive() or e.flags.get("xp_granted", false):
			continue
		e.flags["xp_granted"] = true
		var amt: int = 4 + e.max_hp + (12 if e.tags.has("boss") else 0)
		evs += _grant_xp(amt)
	return evs

## An idle enemy wakes when it can SEE you (within SIGHT and unobstructed line of
## sight — walls block) or HEAR a commotion (within noise_radius, which carries
## around corners). This stops a whole room — or enemies behind walls — from
## piling on the moment you poke one rat across the floor.
func _update_awareness(noise_radius: int) -> Array:
	var evs: Array = []
	var p: CombatEntity = player()
	for e in enemies_alive():
		if e.aware:
			continue
		var d: Vector2i = (e.cell - p.cell).abs()
		var cheby: int = maxi(d.x, d.y)
		var sees: bool = cheby <= SIGHT and board.has_los(e.cell, p.cell)
		var hears: bool = noise_radius > 0 and cheby <= noise_radius
		if sees:
			e.flags["seen_player"] = true
		if sees or hears:
			e.aware = true
			evs.append({"type": "notice", "id": e.id})
	return evs

## Your pet ally's turn: attack an adjacent enemy, else close on the nearest one;
## with no enemies in the room it trots back toward you. A loyal mascot, not a
## second protagonist — modest dice, and enemies leave it alone (it never dies on
## the board; it just respawns each floor from your loadout).
func _ally_turn() -> Array:
	var evs: Array = []
	var p: CombatEntity = player()
	for a in allies_alive():
		var foes := enemies_alive()
		# A convert (zealot) may spread the faith to an adjacent enemy on its own —
		# this is how a crusade chains through a room without you lifting a finger.
		if a.tags.has("faith"):
			var near: CombatEntity = null
			for e in foes:
				if board.is_adjacent(a.cell, e.cell):
					near = e; break
			var chain_p := 0.35 if player().origin_trait == "preacher" else 0.22
			if near != null and rng.randf() < chain_p:
				convert_enemy(near)
				evs.append({"type": "convert", "id": near.id, "name": near.name_pl, "chained": true})
				continue
		if foes.is_empty():
			# follow the player (don't crowd — stop when already adjacent)
			if not board.is_adjacent(a.cell, p.cell):
				var step := _step_toward(a.cell, p.cell)
				if step != a.cell and board.is_free(step):
					board.move(a.cell, step); a.cell = step
					evs.append({"type": "move", "id": a.id, "to": step})
			continue
		# target the nearest enemy
		var tgt: CombatEntity = null
		var best := 1 << 30
		for e in foes:
			var d: int = maxi(absi(e.cell.x - a.cell.x), absi(e.cell.y - a.cell.y))
			if d < best:
				best = d; tgt = e
		if tgt == null:
			continue
		if board.is_adjacent(a.cell, tgt.cell):
			evs += _ally_attack(a, tgt)
		else:
			var step2 := _step_toward(a.cell, tgt.cell)
			if step2 != a.cell and board.is_free(step2):
				board.move(a.cell, step2); a.cell = step2
				evs.append({"type": "move", "id": a.id, "to": step2})
	return evs

## Flip an enemy onto your side (a convert). It keeps its combat profile but now
## fights with the ally AI and carries the faith (so it can chain-convert others).
func convert_enemy(e: CombatEntity) -> void:
	e.faction = "ally"
	if not e.tags.has("faith"): e.tags.append("faith")
	if not e.tags.has("convert"): e.tags.append("convert")
	e.aware = true
	e.statuses.erase("charmed")
	e.flags.erase("incited")
	if e.dmg_dice == "": e.dmg_dice = "1d4"
	if e.to_hit == 0: e.to_hit = 2

## An ally swing: rolls to hit, deals its dmg_dice, and — flavor — its kills still
## thrill the crowd. Awareness wakes the victim (the pet is loud).
func _ally_attack(a: CombatEntity, target: CombatEntity) -> Array:
	target.aware = true
	var evs: Array = [{"type": "attack", "attacker": a.id, "target": target.id, "ally": true}]
	if _roll_hit(a.to_hit, _eff_ac(target)):
		var base: int = Dice.roll(a.dmg_dice, rng) if a.dmg_dice != "" else rng.randi_range(1, 4) + 1
		evs += _apply_damage(target, base, DMG_PHYSICAL)
		if not target.is_alive():
			evs += _change_audience(1, "ally_kill")
	else:
		evs.append({"type": "miss", "attacker": a.id, "target": target.id})
	return evs

func _enemy_turn() -> Array:
	# Phase 1 — EXECUTE: every declared intent goes off, aimed at a CELL, and
	# hits WHATEVER stands there (friendly fire is real). You dodge a declared
	# strike by not being in the cell — or by parking something else in it.
	var evs: Array = []
	var p: CombatEntity = player()
	for e in enemies_alive():
		if e.intent.is_empty():
			continue
		var it: Dictionary = e.intent
		e.intent = {}
		if e.has_status("stunned") or e.has_status("shocked"):
			evs.append({"type": "skip", "id": e.id, "reason": "stunned"})
			continue
		if e.has_status("charmed") and not e.flags.get("incited", false):
			evs.append({"type": "skip", "id": e.id, "reason": "charmed"})
			continue
		var cell: Vector2i = it.get("cell", e.cell)
		match str(it.get("kind", "")):
			"strike":
				evs += _execute_hit(e, cell, false)
			"zap":
				if board.has_los(e.cell, cell):
					evs.append({"type": "attack", "attacker": e.id, "target": -1, "ranged": true})
					evs += _execute_hit(e, cell, true)
				else:
					evs.append({"type": "fizzle", "id": e.id})
			"pounce":
				if board.is_free(cell):
					board.move(e.cell, cell); e.cell = cell
					evs.append({"type": "pounce", "id": e.id, "name": e.name_pl})
					evs.append({"type": "move", "id": e.id, "to": cell})
					evs += _on_enter_cell(e)
				else:
					var occ: int = board.occupant_at(cell)
					if occ != -1 and entities.has(occ):
						evs.append({"type": "pounce", "id": e.id, "name": e.name_pl})
						evs += _execute_hit(e, cell, false)
		if not p.is_alive():
			break
	# Phase 2 — DECLARE: move now, telegraph the next blow (drawn on the board).
	if p.is_alive():
		for e in enemies_alive():
			if not e.aware:
				continue
			if e.has_status("stunned") or e.has_status("shocked"):
				continue
			if e.has_status("charmed") and not e.flags.get("incited", false):
				continue
			evs += _declare_intent(e)
	evs += _tick_dots()
	for id in entities:
		(entities[id] as CombatEntity).tick_statuses()
	return evs

## A declared hit lands automatically on whatever occupies the cell now.
func _execute_hit(e: CombatEntity, cell: Vector2i, ranged: bool) -> Array:
	var evs: Array = []
	var occ: int = board.occupant_at(cell)
	if occ == -1 or occ == e.id or not entities.has(occ):
		evs.append({"type": "whiff", "id": e.id, "cell": cell})
		return evs
	var victim: CombatEntity = entities[occ]
	if victim.faction == "object":
		evs.append({"type": "whiff", "id": e.id, "cell": cell})
		return evs
	var base: int
	if ranged:
		base = rng.randi_range(2, 5)
	else:
		base = Dice.roll(e.dmg_dice, rng) if e.dmg_dice != "" else rng.randi_range(1, 4) + 1
		if e.has_status("disarmed"):
			base = maxi(1, base - 2)
		if e.flags.get("enraged", false):
			base += 2
		if e.body_kind() == "bug":
			var pack := 0
			for o in enemies_alive():
				if o.id != e.id and o.body_kind() == "bug" and board.is_adjacent(o.cell, victim.cell):
					pack += 1
			base += mini(pack, 2)
	evs.append({"type": "attack", "attacker": e.id, "target": victim.id, "ranged": ranged})
	evs += _apply_damage(victim, base, DMG_ELECTRIC if ranged else DMG_PHYSICAL)
	if victim.faction == "enemy" and not victim.is_alive():
		# an enemy walked into a colleague's declared blow — the crowd LOVES it
		evs += _note_tag("env_kill")
		evs += _change_audience(4, "friendly_fire")
	if victim.faction == "ally" and not victim.is_alive():
		evs.append({"type": "ally_down", "id": victim.id, "name": victim.name_pl})
	return evs

## Move toward the prey, then telegraph next round's action (cell-targeted).
func _declare_intent(e: CombatEntity) -> Array:
	var evs: Array = []
	var p: CombatEntity = player()
	var kind: String = e.body_kind()
	# elites enrage the moment they bleed below half
	if kind == "elite" and e.hp * 2 < e.max_hp and not e.flags.get("enraged", false):
		e.flags["enraged"] = true
		evs.append({"type": "enrage", "id": e.id, "name": e.name_pl})
	# the prey: the lure if one is out, an incited target, else you (or your pet)
	var prey_cell: Vector2i = p.cell
	if not lure.is_empty():
		prey_cell = lure["cell"]
	elif e.flags.get("incited", false):
		var best: CombatEntity = null
		var bd := 999
		for o in enemies_alive():
			if o.id == e.id:
				continue
			var dd: Vector2i = (o.cell - e.cell).abs()
			var ch: int = maxi(dd.x, dd.y)
			if ch < bd:
				bd = ch; best = o
		if best != null:
			prey_cell = best.cell
	var pd: int = maxi(absi(prey_cell.x - e.cell.x), absi(prey_cell.y - e.cell.y))
	# Mech: keeps range, telegraphs a zap on your CURRENT cell.
	if kind == "mech" and e.can_move() and not e.is_hobbled():
		if pd <= 1:
			var back: Vector2i = e.cell + Vector2i(signi(e.cell.x - prey_cell.x), signi(e.cell.y - prey_cell.y))
			if board.is_free(back):
				board.move(e.cell, back); e.cell = back
				evs.append({"type": "move", "id": e.id, "to": back})
				evs += _on_enter_cell(e)
				pd = maxi(absi(prey_cell.x - e.cell.x), absi(prey_cell.y - e.cell.y))
		if pd >= 2 and pd <= 3 and board.has_los(e.cell, prey_cell):
			e.intent = {"kind": "zap", "cell": prey_cell}
			return evs
	# Beast: telegraphs a two-tile pounce along its lane.
	if kind == "beast" and pd == 2 and e.can_move() and not e.is_hobbled():
		var dvec: Vector2i = prey_cell - e.cell
		if dvec.x == 0 or dvec.y == 0 or absi(dvec.x) == absi(dvec.y):
			e.intent = {"kind": "pounce", "cell": prey_cell}
			return evs
	# Everyone else: close in (movement happens NOW), then telegraph a strike.
	if board.is_adjacent(e.cell, prey_cell):
		e.intent = {"kind": "strike", "cell": prey_cell}
		return evs
	# pet adjacent? swat it instead
	for a in allies_alive():
		if board.is_adjacent(e.cell, a.cell):
			e.intent = {"kind": "strike", "cell": a.cell}
			return evs
	if not e.can_move():
		evs.append({"type": "skip", "id": e.id, "reason": "crippled"})
		return evs
	if e.is_hobbled() or e.has_status("slowed"):
		evs.append({"type": "skip", "id": e.id, "reason": "hobbled"})
		return evs
	var step: Vector2i = _step_toward(e.cell, prey_cell)
	if step != e.cell and board.is_free(step):
		board.move(e.cell, step)
		e.cell = step
		evs.append({"type": "move", "id": e.id, "to": step})
		evs += _on_enter_cell(e)
	if e.is_alive() and board.is_adjacent(e.cell, prey_cell):
		e.intent = {"kind": "strike", "cell": prey_cell}
	return evs

func _tick_dots() -> Array:
	var evs: Array = []
	for id in entities.keys():
		var e: CombatEntity = entities[id]
		if not e.is_alive():
			continue
		for status in STATUS_DOT:
			if e.has_status(status):
				var spec: Array = STATUS_DOT[status]
				evs.append({"type": "status_tick", "target": e.id, "status": status,
					"amount": spec[0]})
				evs += _apply_damage(e, int(spec[0]), str(spec[1]))
				if not e.is_alive():
					break
	return evs

func _step_toward(frm: Vector2i, to: Vector2i) -> Vector2i:
	return frm + Vector2i(signi(to.x - frm.x), signi(to.y - frm.y))

func _check_end() -> Array:
	# Only DEATH terminally ends play. Clearing a room's enemies does NOT lock the
	# player out — you still walk to the exit and descend. The "win" event fires
	# once, when the last enemy of a room that HAD enemies falls.
	if not player().is_alive():
		over = true; outcome = "lose"
		return [{"type": "combat_end", "outcome": "lose"}]
	if _had_enemies and not cleared and enemies_alive().is_empty():
		cleared = true; outcome = "win"
		return [{"type": "combat_end", "outcome": "win"}]
	return []
