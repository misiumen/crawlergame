class_name FloorGen
extends RefCounted
## Procedural floor generation, board-native. A board rewrite (not a literal port)
## of engine/floor_generator.py: it preserves the spirit — seeded determinism,
## content pulled from templates, role-mixed rooms, and a validation retry loop
## (reachability + a guaranteed descent) — adapted to the tile-room model the
## Godot port uses (rooms = boards + doors). Difficulty scales with depth.
##
## generate() returns the SAME dict shape as Encounters.floor(), so Floor.new()
## consumes it unchanged: {rooms, player, inv, start, start_cell, hint}.

const MIN_W := 9
const MAX_W := 15
const MIN_H := 7
const MAX_H := 9

# Fallback content if the caller passes nothing (keeps headless tests trivial).
const FALLBACK_MON := {
	"szczur": {"fallback_name": "Szczur", "tags": ["monster", "small", "organic", "beast"],
		"stats": [22, "1d6+1", 2, 12]},
}
const FALLBACK_ENV := {
	"stol": {"fallback_name": "Stół", "tags": ["furniture", "wood", "salvageable"],
		"affordances": ["inspect", "salvage"]},
}

# ── Entry point ───────────────────────────────────────────────────────────────

## Build floor `floor_num` (1-based) from `seed`. `content` is the entity bundle
## {"MON": {...}, "ENV": {...}, "MOB_COMBAT_STATS": {...}} (pass {} for fallback).
## `mods` is an optional route-biome bias {enemy_mul, object_mul, trap_mul,
## biome_key, label} — Routes.mods_for(key).
static func generate(floor_num: int, seed_value: int, content: Dictionary = {},
		mods: Dictionary = {}) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value + floor_num * 100003
	var mon: Dictionary = content.get("MON", FALLBACK_MON)
	var env: Dictionary = content.get("ENV", FALLBACK_ENV)
	var stats: Dictionary = content.get("MOB_COMBAT_STATS", {})

	var room_count: int = clampi(2 + (floor_num - 1) / 2, 2, 4)
	var next_id := {"v": 2}   # 1 = player; entities count up from 2

	var rooms: Array = []
	for i in room_count:
		rooms.append(_gen_room(rng, floor_num, i, room_count, mon, env, stats, next_id, mods))
	_link_rooms(rooms)

	var player := CombatEntity.new(1, "Bezimienny", 100, 14, ["humanoid"])
	player.faction = "player"

	var biome_label: String = mods.get("label", "")
	var hint := "Piętro %d. Przejdź pokoje (+), zejdź po schodach (>). Rozbieraj, kuj, walcz." % floor_num
	if biome_label != "":
		hint = "Piętro %d — %s. Schodź po schodach (>)." % [floor_num, biome_label]

	return {
		"rooms": rooms,
		"player": player,
		"inv": {},
		"start": 0,
		"start_cell": rooms[0]["entry"],
		"floor_num": floor_num,
		"biome": mods.get("biome_key", ""),
		"hint": hint,
	}

# ── Room generation ───────────────────────────────────────────────────────────

static func _gen_room(rng: RandomNumberGenerator, floor_num: int, idx: int, total: int,
		mon: Dictionary, env: Dictionary, stats: Dictionary, next_id: Dictionary,
		mods: Dictionary = {}) -> Dictionary:
	var enemy_mul: float = float(mods.get("enemy_mul", 1.0))
	var object_mul: float = float(mods.get("object_mul", 1.0))
	var trap_mul: float = float(mods.get("trap_mul", 1.0))
	var pref_tags: Array = mods.get("object_tags", [])
	var w: int = rng.randi_range(MIN_W, MAX_W)
	var h: int = rng.randi_range(MIN_H, MAX_H)
	var board := Board.new(w, h)
	# Wall border, floor interior.
	for x in w:
		board.set_wall(Vector2i(x, 0)); board.set_wall(Vector2i(x, h - 1))
	for y in h:
		board.set_wall(Vector2i(0, y)); board.set_wall(Vector2i(w - 1, y))

	var entry := Vector2i(1, h / 2)
	var door := Vector2i(w - 2, h / 2)          # east doorway (interior, near wall)
	var is_last := idx == total - 1

	# A conductive trap appears more often deeper (and per the route's trap bias).
	if rng.randf() < minf((0.3 + floor_num * 0.08) * trap_mul, 0.95):
		_place_trap(board, rng, entry, door)

	var entities: Dictionary = {}
	# Objects to dismantle (1..3).
	# Bias object selection toward the biome's preferred tags (thematic floors).
	var obj_keys: Array = _biased_object_keys(env, pref_tags)
	var n_obj := maxi(0, int(round(rng.randi_range(1, 3) * object_mul)))
	for _i in n_obj:
		if obj_keys.is_empty():
			break
		var cell := _free_interior(board, rng, entry, door)
		if cell == Vector2i(-1, -1):
			break
		var ekey: String = obj_keys[rng.randi_range(0, obj_keys.size() - 1)]
		var obj := _make_object(ekey, env[ekey], next_id["v"])
		obj.cell = cell
		board.place(obj.id, cell)
		entities[obj.id] = obj
		next_id["v"] += 1

	# Enemies (deeper floors = more, harder). Room 0 a touch lighter.
	var eligible := _eligible_mobs(mon, floor_num, false)
	var n_enemy: int = clampi(int(round((floor_num / 2 + idx) * enemy_mul)), 0, 4)
	if idx == 0:
		n_enemy = maxi(0, n_enemy - 1)
	for _i in n_enemy:
		if eligible.is_empty():
			break
		var cell := _free_interior(board, rng, entry, door)
		if cell == Vector2i(-1, -1):
			break
		var mkey: String = eligible[rng.randi_range(0, eligible.size() - 1)]
		var foe := _make_mob(mkey, mon[mkey], stats.get(mkey), next_id["v"], floor_num)
		foe.cell = cell
		# Distant foes start asleep — preserves the explore->engage beat.
		foe.aware = false
		board.place(foe.id, cell)
		entities[foe.id] = foe
		next_id["v"] += 1

	# Validate: entry must reach the door with objects in place. Free up the path
	# by removing any object that blocks it (enemies are passable for the check).
	_ensure_reachable(board, entry, door, entities)

	return {
		"name": "Sektor %d" % (idx + 1),
		"board": board,
		"entities": entities,
		"entry": entry,
		"door": door,
		"is_last": is_last,
		"exits": {},   # filled by _link_rooms
	}

static func _link_rooms(rooms: Array) -> void:
	for i in rooms.size():
		var room: Dictionary = rooms[i]
		if room["is_last"]:
			room["exits"][room["door"]] = {"descend": true}
		else:
			var nxt: Dictionary = rooms[i + 1]
			room["exits"][room["door"]] = {"to": i + 1, "at": nxt["entry"]}
			# back-door from the next room's entry to here (step west onto entry).
			nxt["exits"][Vector2i(0, nxt["entry"].y) + Vector2i(1, 0)] = {"to": i, "at": room["door"]}

# ── Content -> entities ───────────────────────────────────────────────────────

static func _make_object(key: String, tmpl: Dictionary, id: int) -> CombatEntity:
	var tags: Array = (tmpl.get("tags", []) as Array).duplicate()
	var obj := CombatEntity.new(id, tmpl.get("fallback_name", key), 6, 5, tags)
	obj.faction = "object"
	obj.monster_key = key
	var aff: Array = tmpl.get("affordances", ["inspect", "salvage"])
	obj.affordances = aff.duplicate()
	if "salvage" not in obj.affordances:
		obj.affordances.append("salvage")
	return obj

static func _make_mob(key: String, tmpl: Dictionary, stat: Variant, id: int, floor_num: int) -> CombatEntity:
	var tags: Array = (tmpl.get("tags", []) as Array).duplicate()
	var hp := 20; var ac := 12; var dice := "1d6"; var th := 2
	if stat is Array and (stat as Array).size() >= 4:
		hp = int(stat[0]); dice = str(stat[1]); th = int(stat[2]); ac = int(stat[3])
	# Depth scaling: +10% HP per floor beyond 1 (gentle).
	hp = int(round(hp * (1.0 + 0.10 * maxi(0, floor_num - 1))))
	var foe := CombatEntity.new(id, tmpl.get("fallback_name", key), hp, ac, tags)
	foe.faction = "enemy"
	foe.monster_key = key
	foe.dmg_dice = dice
	foe.to_hit = th
	foe.affordances = ["inspect", "attack"]
	return foe

## Mob keys eligible for this floor: honor floor_min/floor_max (and floor_min:N
## tags), exclude bosses/minibosses from normal rooms.
static func _eligible_mobs(mon: Dictionary, floor_num: int, allow_boss: bool) -> Array:
	var out: Array = []
	for key in mon:
		var t: Dictionary = mon[key]
		var tags: Array = t.get("tags", [])
		if not allow_boss and ("boss" in tags or "miniboss" in tags or key.begins_with("boss_")
				or key.begins_with("miniboss_")):
			continue
		var fmin: int = int(t.get("floor_min", _tag_floor_min(tags)))
		var fmax: int = int(t.get("floor_max", 99))
		if floor_num >= fmin and floor_num <= fmax:
			out.append(key)
	if out.is_empty():   # never strand the generator
		out = mon.keys()
	return out

static func _tag_floor_min(tags: Array) -> int:
	for t in tags:
		if (t as String).begins_with("floor_min:"):
			return int((t as String).substr(10))
	return 1

## A pick-list of ENV keys weighted toward `pref_tags`: a key whose tags overlap
## the preferred set is added an extra time (so it's likelier without excluding
## the rest). Empty pref -> every key once.
static func _biased_object_keys(env: Dictionary, pref_tags: Array) -> Array:
	var out: Array = []
	for key in env:
		out.append(key)
		if pref_tags.is_empty():
			continue
		var tags: Array = env[key].get("tags", [])
		for pt in pref_tags:
			if pt in tags:
				out.append(key); out.append(key)   # ×3 total -> strong bias
				break
	return out

# ── Layout helpers ────────────────────────────────────────────────────────────

## A trap: two water tiles + an adjacent live wire, kept clear of the entry/door
## row so it never seals the corridor.
static func _place_trap(board: Board, rng: RandomNumberGenerator, entry: Vector2i, door: Vector2i) -> void:
	var corridor_y: int = entry.y
	var ty := corridor_y
	# pick a row that isn't the corridor row
	for _try in 6:
		var cand := rng.randi_range(1, board.h - 2)
		if cand != corridor_y:
			ty = cand; break
	if ty == corridor_y:
		return
	var tx := rng.randi_range(2, maxi(2, board.w - 4))
	board.set_hazard(Vector2i(tx, ty), "water")
	board.set_hazard(Vector2i(tx + 1, ty), "water")
	board.set_hazard(Vector2i(tx + 1, ty - 1), "wire")

## A free interior cell not on entry/door and not on the straight corridor row
## between them (so placement can't trivially wall off the path). (-1,-1) if none.
static func _free_interior(board: Board, rng: RandomNumberGenerator, entry: Vector2i, door: Vector2i) -> Vector2i:
	for _try in 40:
		var c := Vector2i(rng.randi_range(1, board.w - 2), rng.randi_range(1, board.h - 2))
		if c == entry or c == door:
			continue
		if c.y == entry.y and c.x >= entry.x and c.x <= door.x:
			continue   # keep the direct corridor row clear
		if board.is_free(c) and board.hazard_at(c) == "":
			return c
	return Vector2i(-1, -1)

## BFS from entry to door treating walls + objects as blocking (enemies passable).
## If unreachable, remove blocking objects one by one until a path exists.
static func _ensure_reachable(board: Board, entry: Vector2i, door: Vector2i, entities: Dictionary) -> void:
	for _guard in 12:
		if _path_exists(board, entry, door, entities):
			return
		# Remove the object nearest the corridor and retry.
		var victim := -1
		for id in entities:
			var e: CombatEntity = entities[id]
			if e.faction == "object":
				victim = id; break
		if victim == -1:
			return
		board.clear(entities[victim].cell)
		entities.erase(victim)

static func _path_exists(board: Board, frm: Vector2i, to: Vector2i, entities: Dictionary) -> bool:
	var blocked: Dictionary = {}
	for id in entities:
		var e: CombatEntity = entities[id]
		if e.faction == "object":
			blocked[e.cell] = true
	var seen: Dictionary = {frm: true}
	var queue: Array = [frm]
	while not queue.is_empty():
		var cur: Vector2i = queue.pop_front()
		if cur == to:
			return true
		for d in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var n: Vector2i = cur + d
			if seen.has(n) or not board.in_bounds(n) or board.is_wall(n) or blocked.has(n):
				continue
			seen[n] = true
			queue.append(n)
	return false
