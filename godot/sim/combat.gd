class_name CombatSim
extends RefCounted
## Tile-based combat resolution. Pure logic: methods mutate sim state and RETURN
## arrays of event dicts. Presentation turns events into animations; the sim
## never touches a node.

const DMG_PHYSICAL := "physical"
const DMG_ELECTRIC := "electric"

var board: Board
var entities: Dictionary = {}
var player_id: int = 0
var round_num: int = 1
var side: String = "player"
var over: bool = false
var outcome: String = ""

var materials: Dictionary = {}      # run materials, shared ref from Floor
var items: Array = []               # GameItem list, shared ref from Floor
var discovered_recipes: Array = []  # recipe book, shared ref from Floor
var _audience: AudienceState        # may be null in headless unit tests
var _sponsors: SponsorState         # may be null in headless unit tests
var aim_zone: String = ""           # presentation sets this to aim the next player hit
var _curse_to_hit: int = 0          # occultist Curse: +AC vs enemies while active
var _curse_rounds: int = 0          # rounds the curse lasts

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

func player() -> CombatEntity:
	return entities[player_id]

func enemies_alive() -> Array:
	var out: Array = []
	for id in entities:
		var e: CombatEntity = entities[id]
		if e.faction == "enemy" and e.is_alive():
			out.append(e)
	return out

# ── Damage model ──────────────────────────────────────────────────────────────

func effective_damage(target: CombatEntity, base: int, dmg_type: String) -> int:
	var dmg: int = base
	if dmg_type == DMG_PHYSICAL and target.has_property("thick_hide"):
		dmg = int(dmg / 2.0)
	if dmg_type == DMG_ELECTRIC and target.has_property("shock_weak"):
		dmg = dmg * 2
	return maxi(1, dmg)

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
	if occ != -1 and occ != player_id:
		var t: CombatEntity = entities[occ]
		if t.faction == "object":
			return [{"type": "blocked", "reason": "object", "id": t.id}]
		evs += _player_attack(t)
	elif board.is_free(dest):
		board.move(p.cell, dest)
		p.cell = dest
		evs.append({"type": "move", "id": player_id, "to": dest})
		evs += _on_enter_cell(p)
	else:
		return [{"type": "blocked"}]
	evs += _after_player_action()
	return evs

func _player_attack(target: CombatEntity) -> Array:
	target.aware = true
	# Aiming a small zone (head/limb) is harder to land but hits where you want.
	var zone: String = aim_zone
	var hit_bonus: int = 3
	if zone != "" and target.body != null:
		hit_bonus += target.body.to_hit_mod_for(zone)
	var evs: Array = [{"type": "attack", "attacker": player_id, "target": target.id,
		"aim": zone}]
	var p: CombatEntity = player()
	_add_affinity("melee", 1)
	# Ranger's precise shot (active) forces the hit to land.
	var autohit: bool = p.next_attack_autohit
	if autohit:
		p.next_attack_autohit = false
	if autohit or _roll_hit(hit_bonus, target.ac):
		var base: int = rng.randi_range(1, 6) + 2 + p.bonus_damage
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
		GameItem.CAT_TOOL:
			if item.effect.has("recharge_coating") and p.coating != "":
				p.coating_charges += int(item.effect["recharge_coating"])
				evs.append({"type": "coating_recharged",
							"charges": p.coating_charges})
	# Consume or keep.
	if item.charges == 0:
		pass   # permanent upgrade — stays in items list
	elif item.charges <= 1:
		items.remove_at(item_idx)
	else:
		item.charges -= 1
	evs += _after_player_action(1)
	return evs

# ── Class active ability ──────────────────────────────────────────────────────

## Fire the player's emergent-class active (once per floor). Returns events; the
## ability counts as the player's action, so the enemy turn follows.
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
	evs += _after_player_action(7)
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
	evs += _update_awareness(noise_radius)
	side = "enemies"
	evs += _enemy_turn()
	if not over:
		evs += _check_end()
	side = "player"
	round_num += 1
	return evs

func _update_awareness(noise_radius: int) -> Array:
	var evs: Array = []
	var p: CombatEntity = player()
	var reach: int = maxi(SIGHT, noise_radius)
	for e in enemies_alive():
		if e.aware:
			continue
		var d: Vector2i = (e.cell - p.cell).abs()
		if maxi(d.x, d.y) <= reach:
			e.aware = true
			evs.append({"type": "notice", "id": e.id})
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
		if board.is_adjacent(e.cell, p.cell):
			evs.append({"type": "attack", "attacker": e.id, "target": player_id})
			# A disarmed (broken-arm) enemy swings weaker.
			var atk_bonus: int = 0 if e.has_status("disarmed") else 2
			# Survivor's passive + occultist's Curse make the player harder to hit.
			var pac: int = p.ac + ClassFeatures.passive_bonus(p, "ac") + _curse_to_hit
			if _roll_hit(atk_bonus, pac):
				var base: int = rng.randi_range(1, 4) + 1
				if e.has_status("disarmed"):
					base = maxi(1, base - 2)
				evs += _apply_damage(p, base, DMG_PHYSICAL)
			else:
				evs.append({"type": "miss", "attacker": e.id, "target": player_id})
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
	for id in entities:
		(entities[id] as CombatEntity).tick_statuses()
	return evs

func _step_toward(frm: Vector2i, to: Vector2i) -> Vector2i:
	return frm + Vector2i(signi(to.x - frm.x), signi(to.y - frm.y))

func _check_end() -> Array:
	if not player().is_alive():
		over = true; outcome = "lose"
		return [{"type": "combat_end", "outcome": "lose"}]
	if enemies_alive().is_empty():
		over = true; outcome = "win"
		return [{"type": "combat_end", "outcome": "win"}]
	return []
