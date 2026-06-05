class_name CombatSim
extends RefCounted
## Tile-based combat resolution — the spatial heir to combat_rules.py.
##
## Pure logic: methods mutate sim state and RETURN an array of event dicts
## ({"type":"damage"/"move"/"systemic"/"death"/...}). The presentation layer
## turns events into animations/FX/signals; the sim never touches a node, so it
## stays fully headless-testable.

const DMG_PHYSICAL := "physical"
const DMG_ELECTRIC := "electric"

var board: Board
var entities: Dictionary = {}     # id -> CombatEntity
var player_id: int = 0
var round_num: int = 1
var side: String = "player"
var over: bool = false
var outcome: String = ""          # "" | "win" | "lose"
var materials: Dictionary = {}    # run inventory: "drewno" -> count
var rng := RandomNumberGenerator.new()

const DIRS8 := [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN,
	Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]
const SIGHT := 4                  # an enemy notices you within this many tiles

func _init(_board: Board, _entities: Dictionary, _player_id: int, seed_value: int = 0) -> void:
	board = _board
	entities = _entities
	player_id = _player_id
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

# ---- damage model (pure, deterministic; tags drive resist/weakness) ----
func effective_damage(target: CombatEntity, base: int, dmg_type: String) -> int:
	var dmg: int = base
	if dmg_type == DMG_PHYSICAL and target.has_property("thick_hide"):
		dmg = int(dmg / 2.0)               # thick hide shrugs off blades -> brute is slow
	if dmg_type == DMG_ELECTRIC and target.has_property("shock_weak"):
		dmg = dmg * 2                       # conducts -> the exploitable weakness
	return maxi(1, dmg)

func _apply_damage(target: CombatEntity, base: int, dmg_type: String, zone := "") -> Array:
	var dmg: int = effective_damage(target, base, dmg_type)
	target.take_damage(dmg)
	var evs: Array = [{"type": "damage", "target": target.id, "amount": dmg,
		"dmg_type": dmg_type, "zone": zone}]
	if not target.is_alive():
		board.clear(target.cell)
		evs.append({"type": "death", "target": target.id})
	return evs

func _roll_hit(bonus: int, ac: int) -> bool:
	return (rng.randi_range(1, 20) + bonus) >= ac

# ---- player actions: return events; a real action ends the player turn ----
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
			return [{"type": "blocked", "reason": "object", "id": t.id}]   # use [E] to dismantle
		evs += _player_attack(t)                      # bump = attack
	elif board.is_free(dest):
		board.move(p.cell, dest)
		p.cell = dest
		evs.append({"type": "move", "id": player_id, "to": dest})
		evs += _on_enter_cell(p)
	else:
		return [{"type": "blocked"}]                   # wall/edge: not a turn
	evs += _after_player_action()
	return evs

func _player_attack(target: CombatEntity) -> Array:
	target.aware = true                                # striking it certainly alerts it
	var evs: Array = [{"type": "attack", "attacker": player_id, "target": target.id}]
	if _roll_hit(3, target.ac):
		var base: int = rng.randi_range(1, 6) + 2      # knife 1d6+2 (physical)
		evs += _apply_damage(target, base, DMG_PHYSICAL)
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
		return [{"type": "blocked"}]
	var target: CombatEntity = entities[occ]
	var land: Vector2i = adj + dir
	var evs: Array = [{"type": "shove", "target": target.id, "dir": dir}]
	if board.is_free(land):
		board.move(target.cell, land)
		target.cell = land
		evs.append({"type": "move", "id": target.id, "to": land})
		evs += _on_enter_cell(target)
	else:
		evs += _apply_damage(target, 2, DMG_PHYSICAL)  # shoved into a wall
	evs += _after_player_action()
	return evs

func player_wait() -> Array:
	if over or side != "player":
		return []
	var evs: Array = [{"type": "wait"}]
	evs += _after_player_action()
	return evs

## Dismantle the first adjacent object into materials (Dysmantle). Loud.
func player_interact() -> Array:
	if over or side != "player":
		return []
	for d in DIRS8:
		var occ: int = board.occupant_at(player().cell + d)
		if occ != -1 and occ != player_id:
			var t: CombatEntity = entities[occ]
			if t.faction == "object" and "salvage" in t.affordances:
				return _salvage(t)
	return [{"type": "none"}]                          # nothing to dismantle: not a turn

func _salvage(obj: CombatEntity) -> Array:
	var gained: Dictionary = {}
	for tag in obj.tags:
		match tag:
			"wood": _gain(gained, "drewno", rng.randi_range(1, 3))
			"metal": _gain(gained, "złom", rng.randi_range(1, 2))
			"cloth", "fabric": _gain(gained, "szmata", 1)
			"electric", "wire": _gain(gained, "przewód", 1)
			"plastic": _gain(gained, "plastik", 1)
	if gained.is_empty():
		_gain(gained, "złom", 1)
	for k in gained:
		materials[k] = int(materials.get(k, 0)) + gained[k]
	board.clear(obj.cell)
	obj.alive = false
	var evs: Array = [{"type": "salvage", "target": obj.id, "gained": gained}]
	evs += _after_player_action(7)                     # dismantling is noisy
	return evs

func _gain(d: Dictionary, key: String, n: int) -> void:
	d[key] = int(d.get(key, 0)) + n

# ---- systemic: entering a cell can trigger environmental reactions ----
func _on_enter_cell(e: CombatEntity) -> Array:
	var evs: Array = []
	if board.hazard_at(e.cell) == "water" and _adjacent_live_wire(e.cell):
		var base: int = rng.randi_range(3, 18)         # ~3d6, electric
		evs.append({"type": "systemic", "element": "electric", "target": e.id, "via": "water+wire"})
		evs += _apply_damage(e, base, DMG_ELECTRIC)
		if e.is_alive():
			e.add_status("shocked", 1)
			evs.append({"type": "status", "target": e.id, "status": "shocked", "turns": 1})
	return evs

## Public: would an entity standing on cell `c` get shocked? (used by the
## presentation layer to draw the consequence preview before you commit).
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

# ---- turn flow ----
func _after_player_action(noise_radius: int = 0) -> Array:
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

## Idle enemies wake when you come within sight, or when noise reaches them.
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
			continue                                   # still idle / hasn't noticed you
		if e.has_status("shocked"):
			evs.append({"type": "skip", "id": e.id, "reason": "shocked"})
			continue
		if board.is_adjacent(e.cell, p.cell):
			evs.append({"type": "attack", "attacker": e.id, "target": player_id})
			if _roll_hit(2, p.ac):
				var base: int = rng.randi_range(1, 4) + 1
				evs += _apply_damage(p, base, DMG_PHYSICAL)
			else:
				evs.append({"type": "miss", "attacker": e.id, "target": player_id})
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
		over = true
		outcome = "lose"
		return [{"type": "combat_end", "outcome": "lose"}]
	if enemies_alive().is_empty():
		over = true
		outcome = "win"
		return [{"type": "combat_end", "outcome": "win"}]
	return []
