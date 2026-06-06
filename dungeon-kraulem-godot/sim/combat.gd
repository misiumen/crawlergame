class_name CombatSim
extends RefCounted
## Tile-based combat resolution. Pure logic: methods mutate sim state and RETURN
## arrays of event dicts. Presentation turns events into animations; the sim
## never touches a node.

const DMG_PHYSICAL := "physical"
const DMG_ELECTRIC := "electric"
const DMG_FIRE := "fire"
const DMG_ACID := "acid"
const DMG_COLD := "cold"

var board: Board
var entities: Dictionary = {}
var player_id: int = 0
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

## Effective AC, reduced while the target is corroded (armor eaten away).
func _eff_ac(target: CombatEntity) -> int:
	return target.ac + target.armor_bonus() - (2 if target.has_status("corroded") else 0)

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
		evs += _player_attack(t)
		noise = 3   # a melee swing is heard by nearby enemies (but not the whole floor)
	elif board.is_free(dest):
		board.move(p.cell, dest)
		p.cell = dest
		evs.append({"type": "move", "id": player_id, "to": dest})
		evs += _on_enter_cell(p)
	else:
		return [{"type": "blocked"}]
	evs += _after_player_action(noise)
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
	# Ranger's precise shot (active) forces the hit to land.
	var autohit: bool = p.next_attack_autohit
	if autohit:
		p.next_attack_autohit = false
	if autohit or _roll_hit(hit_bonus, _eff_ac(target)):
		var base: int = rng.randi_range(1, 6) + 2 + p.bonus_damage + p.stat_mod("STR")  # muscle hits harder
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
	if board.is_free(land):
		board.move(target.cell, land)
		target.cell = land
		evs.append({"type": "move", "id": target.id, "to": land})
		evs += _on_enter_cell(target)
	else:
		evs += _apply_damage(target, 2, DMG_PHYSICAL)
	evs += _after_player_action()
	return evs

func player_wait() -> Array:
	if over or side != "player":
		return []
	var evs: Array = [{"type": "wait"}]
	evs += _after_player_action()
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

func _after_player_action(noise_radius: int = 0) -> Array:
	if _curse_rounds > 0:
		_curse_rounds -= 1
		if _curse_rounds <= 0:
			_curse_to_hit = 0
	var evs: Array = _check_end()
	if over:
		return evs
	evs += _ally_turn()          # your pet acts on your side, first
	if not over:
		evs += _check_end()
	evs += _update_awareness(noise_radius)
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
	side = "player"
	round_num += 1
	return evs

## Grant the player XP for any enemy that has died since we last looked (covers
## both melee kills and damage-over-time deaths). Level-ups bump max HP + heal a
## little and bank a skill point; the presentation narrates it and hands out loot.
func _award_kill_xp() -> Array:
	var evs: Array = []
	for id in entities:
		var e: CombatEntity = entities[id]
		if e.faction != "enemy" or e.is_alive() or _xp_done.has(id):
			continue
		_xp_done[id] = true
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
			if near != null and rng.randf() < 0.22:
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
	var evs: Array = []
	var p: CombatEntity = player()
	for e in enemies_alive():
		if not e.aware:
			continue
		# A shocked or head-stunned enemy loses its turn entirely.
		if e.has_status("shocked") or e.has_status("stunned"):
			var why: String = "stunned" if e.has_status("stunned") else "shocked"
			evs.append({"type": "skip", "id": e.id, "reason": why})
			continue
		# Talked-down minds: a charmed enemy won't attack YOU. If it was incited it
		# turns on its own kind; otherwise it just stands down, confused.
		if e.has_status("charmed"):
			if e.flags.get("incited", false):
				evs += _incited_turn(e)
			else:
				evs.append({"type": "skip", "id": e.id, "reason": "charmed"})
			continue
		# Target the player if adjacent; otherwise swat your pet if IT is adjacent
		# (the "protect the mascot" tension — the companion can be downed).
		var victim: CombatEntity = null
		if board.is_adjacent(e.cell, p.cell):
			victim = p
		else:
			for a in allies_alive():
				if board.is_adjacent(e.cell, a.cell):
					victim = a; break
		if victim != null:
			evs.append({"type": "attack", "attacker": e.id, "target": victim.id})
			# A disarmed (broken-arm) enemy swings weaker.
			var atk_bonus: int = 0 if e.has_status("disarmed") else 2
			# Survivor's passive + occultist's Curse make the PLAYER harder to hit.
			var vac: int = _eff_ac(victim)
			if victim == p:
				vac += ClassFeatures.passive_bonus(p, "ac") + _curse_to_hit
			# Content-driven enemies carry their own to-hit; fall back to the default.
			var eatk: int = (e.to_hit if e.dmg_dice != "" else atk_bonus)
			if e.has_status("disarmed"):
				eatk -= 2
			if _roll_hit(eatk, vac):
				var base: int = Dice.roll(e.dmg_dice, rng) if e.dmg_dice != "" else rng.randi_range(1, 4) + 1
				if e.has_status("disarmed"):
					base = maxi(1, base - 2)
				evs += _apply_damage(victim, base, DMG_PHYSICAL)
				if victim != p and not victim.is_alive():
					evs.append({"type": "ally_down", "id": victim.id, "name": victim.name_pl})
			else:
				evs.append({"type": "miss", "attacker": e.id, "target": victim.id})
		elif not e.can_move():
			# Locomotion destroyed — it can't close the gap, only thrash in place.
			evs.append({"type": "skip", "id": e.id, "reason": "crippled"})
		elif e.is_hobbled() or e.has_status("slowed"):
			# One broken leg: it can't chase at speed — kite it.
			evs.append({"type": "skip", "id": e.id, "reason": "hobbled"})
		else:
			var step: Vector2i = _step_toward(e.cell, p.cell)
			if step != e.cell and board.is_free(step):
				board.move(e.cell, step)
				e.cell = step
				evs.append({"type": "move", "id": e.id, "to": step})
				evs += _on_enter_cell(e)
		if not p.is_alive():
			break
	evs += _tick_dots()
	for id in entities:
		(entities[id] as CombatEntity).tick_statuses()
	return evs

## An incited enemy attacks its own kind: it goes for the nearest OTHER enemy
## (or any crawler), closing in or striking — you turned the room on itself.
func _incited_turn(e: CombatEntity) -> Array:
	var evs: Array = []
	var tgt: CombatEntity = null
	var best := 1 << 30
	for id in entities:
		var o: CombatEntity = entities[id]
		if o.id == e.id or not o.is_alive():
			continue
		if o.faction != "enemy" and o.faction != "crawler":
			continue
		var d: int = maxi(absi(o.cell.x - e.cell.x), absi(o.cell.y - e.cell.y))
		if d < best:
			best = d; tgt = o
	if tgt == null:
		evs.append({"type": "skip", "id": e.id, "reason": "charmed"})
		return evs
	if board.is_adjacent(e.cell, tgt.cell):
		tgt.aware = true
		evs.append({"type": "attack", "attacker": e.id, "target": tgt.id, "ally": true})
		if _roll_hit(e.to_hit if e.dmg_dice != "" else 2, _eff_ac(tgt)):
			var base: int = Dice.roll(e.dmg_dice, rng) if e.dmg_dice != "" else rng.randi_range(1, 4) + 1
			evs += _apply_damage(tgt, base, DMG_PHYSICAL)
		else:
			evs.append({"type": "miss", "attacker": e.id, "target": tgt.id})
	else:
		var step := _step_toward(e.cell, tgt.cell)
		if step != e.cell and board.is_free(step):
			board.move(e.cell, step); e.cell = step
			evs.append({"type": "move", "id": e.id, "to": step})
	return evs

## Apply damage-over-time from lingering statuses (burning/poisoned/corroded) to
## every living entity, then return the events. Runs once per round.
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
