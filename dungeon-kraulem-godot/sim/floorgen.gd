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

const MIN_W := 10
const MAX_W := 16
const MIN_H := 8
const MAX_H := 10

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
		mods: Dictionary = {}, is_boss: bool = false) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value + floor_num * 100003
	var mon: Dictionary = content.get("MON", FALLBACK_MON)
	var env: Dictionary = content.get("ENV", FALLBACK_ENV)
	var stats: Dictionary = content.get("MOB_COMBAT_STATS", {})

	var next_id := {"v": 2}   # 1 = player; entities count up from 2
	var rooms: Array = []

	if is_boss:
		# A single arena, one boss, the exit (= victory) gated until it falls.
		rooms.append(_gen_boss_room(rng, floor_num, mon, env, stats, next_id, mods))
	else:
		# S2: ONE continuous board — chambers carved from solid rock, joined by
		# door gaps. Space is real: lure things between chambers, blow holes in
		# the inner walls, refuse to walk into the guard's lair at all.
		rooms.append(_gen_continuous(rng, floor_num, mon, env, stats, next_id, mods))

	var player := CombatEntity.new(1, "Bezimienny", 100, 14, ["humanoid"])
	player.faction = "player"

	var biome_label: String = mods.get("label", "")
	var hint := "Piętro %d. Przejdź pokoje (+), zejdź po schodach (>). Rozbieraj, kuj, walcz." % floor_num
	if biome_label != "":
		hint = "Piętro %d — %s. Schodź po schodach (>)." % [floor_num, biome_label]

	# Collapse timer (the book's rule: deeper floors grant more days; the
	# countdown only matters while you dawdle). One "day" = 30 turns.
	var days: int = 4 + floor_num
	return {
		"rooms": rooms,
		"player": player,
		"inv": {},
		"start": 0,
		"start_cell": rooms[0]["entry"],
		"floor_num": floor_num,
		"biome": mods.get("biome_key", ""),
		"hint": hint,
		"time_days": days,
		"time_limit": days * 30,
	}

# ── Continuous-floor generation (S2) ─────────────────────────────────────────

const SLOT_W := 11
const SLOT_H := 9

## One big board: a random walk over a 3x2 macro-grid picks 4-5 path chambers
## (entry first, stairs last) plus up to 2 branch loot-chambers. Everything not
## carved stays solid wall; walls off the outer border are bomb-destructible.
static func _gen_continuous(rng: RandomNumberGenerator, floor_num: int,
		mon: Dictionary, env: Dictionary, stats: Dictionary, next_id: Dictionary,
		mods: Dictionary) -> Dictionary:
	var enemy_mul: float = float(mods.get("enemy_mul", 1.0))
	var object_mul: float = float(mods.get("object_mul", 1.0))
	var pref_tags: Array = mods.get("object_tags", [])
	var W: int = 3 * SLOT_W + 1
	var H: int = 2 * SLOT_H + 1
	var board := Board.new(W, H)
	for y in H:
		for x in W:
			board.set_wall(Vector2i(x, y))
	# macro path: a walk over slots (sx 0..2, sy 0..1)
	var path: Array = []
	var cur := Vector2i(0, rng.randi_range(0, 1))
	path.append(cur)
	var want: int = 4 + (1 if floor_num >= 3 else 0)
	while path.size() < want:
		var opts: Array = []
		for d in [Vector2i(1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = cur + d
			if n.x >= 0 and n.x < 3 and n.y >= 0 and n.y < 2 and not (n in path):
				opts.append(n)
		if opts.is_empty():
			break
		cur = opts[rng.randi_range(0, opts.size() - 1)]
		path.append(cur)
	# branches: loot chambers hanging off the path (not off the last slot)
	var branches: Array = []
	for i in range(path.size() - 1):
		if branches.size() >= 2:
			break
		for d in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0)]:
			var n2: Vector2i = (path[i] as Vector2i) + d
			if n2.x >= 0 and n2.x < 3 and n2.y >= 0 and n2.y < 2 					and not (n2 in path) and not (n2 in branches):
				branches.append(n2)
				break
	# carve chamber interiors (with a little size jitter)
	var chambers: Array = []   # [{slot, rect}]
	for sl in path + branches:
		var ox: int = (sl as Vector2i).x * SLOT_W
		var oy: int = (sl as Vector2i).y * SLOT_H
		var inx: int = rng.randi_range(0, 1)
		var iny: int = rng.randi_range(0, 1)
		var r := Rect2i(ox + 1 + inx, oy + 1 + iny, SLOT_W - 1 - inx * 2, SLOT_H - 1 - iny * 2)
		for y in range(r.position.y, r.position.y + r.size.y):
			for x in range(r.position.x, r.position.x + r.size.x):
				board.set_wall(Vector2i(x, y), false)
		chambers.append({"slot": sl, "rect": r})
	# door gaps between every connected slot pair
	var carved: Array = path + branches
	for ci in chambers.size():
		var a: Vector2i = chambers[ci]["slot"]
		for d in [Vector2i(1, 0), Vector2i(0, 1)]:
			var b2: Vector2i = a + d
			if not (b2 in carved):
				continue
			# is the pair actually linked (consecutive on path, or branch-parent)?
			var linked := false
			for i in range(path.size() - 1):
				if (path[i] == a and path[i + 1] == b2) or (path[i] == b2 and path[i + 1] == a):
					linked = true
			if (a in branches) or (b2 in branches):
				linked = true
			if not linked:
				continue
			if d.x == 1:
				var gx: int = (a.x + 1) * SLOT_W
				var gy: int = a.y * SLOT_H + SLOT_H / 2 + rng.randi_range(-1, 1)
				board.set_wall(Vector2i(gx, gy), false)
				board.set_wall(Vector2i(gx - 1, gy), false)
				board.set_wall(Vector2i(gx + 1, gy), false)
			else:
				var gy2: int = maxi(a.y, b2.y) * SLOT_H
				var gx2: int = a.x * SLOT_W + SLOT_W / 2 + rng.randi_range(-1, 1)
				board.set_wall(Vector2i(gx2, gy2), false)
				board.set_wall(Vector2i(gx2, gy2 - 1), false)
				board.set_wall(Vector2i(gx2, gy2 + 1), false)
	var first_r: Rect2i = chambers[0]["rect"]
	var last_r: Rect2i = chambers[path.size() - 1]["rect"]
	var entry := Vector2i(first_r.position.x + 1, first_r.position.y + first_r.size.y / 2)
	var stairs := Vector2i(last_r.position.x + last_r.size.x / 2,
		last_r.position.y + last_r.size.y / 2)
	# ── populate ──────────────────────────────────────────────────────────────
	var entities: Dictionary = {}
	var eligible := _biased_mob_keys(mon,
		_eligible_mobs(mon, floor_num, false), mods.get("mob_tags", []))
	var obj_keys: Array = _biased_object_keys(env, pref_tags)
	var hz: String = str(mods.get("hazard_kind", ""))
	for ci in chambers.size():
		var r: Rect2i = chambers[ci]["rect"]
		var is_first: bool = ci == 0
		var is_stairs: bool = ci == path.size() - 1
		var is_branch: bool = ci >= path.size()
		# pillars: cover inside the chamber
		for _i in rng.randi_range(1, 2):
			var pc := Vector2i(rng.randi_range(r.position.x + 2, r.position.x + r.size.x - 3),
				rng.randi_range(r.position.y + 2, r.position.y + r.size.y - 3))
			if pc != entry and pc != stairs:
				board.set_wall(pc)
		# objects (branch chambers are the loot stashes)
		var n_obj: int = int(round(rng.randi_range(1, 2) * object_mul)) + (3 if is_branch else 0)
		for _i in n_obj:
			var oc := _free_in_rect(board, rng, r, entry, stairs)
			if oc == Vector2i(-1, -1) or obj_keys.is_empty():
				break
			var ekey: String = obj_keys[rng.randi_range(0, obj_keys.size() - 1)]
			var obj := _make_object(ekey, env[ekey], next_id["v"])
			obj.cell = oc
			board.place(obj.id, oc)
			entities[obj.id] = obj
			next_id["v"] += 1
		# hazard pools
		if hz != "" and not is_first:
			for _i in rng.randi_range(1, 2):
				var hc := _free_in_rect(board, rng, r, entry, stairs)
				if hc != Vector2i(-1, -1):
					board.set_hazard(hc, hz)
		# enemies: none in the entry chamber, a pack elsewhere
		var n_en: int = 0 if is_first else clampi(int(round((1 + floor_num / 2) * enemy_mul)), 1, 3)
		if is_branch:
			n_en = 1
		for _i in n_en:
			var ec := _free_in_rect(board, rng, r, entry, stairs)
			if ec == Vector2i(-1, -1) or eligible.is_empty():
				break
			var mkey: String = eligible[rng.randi_range(0, eligible.size() - 1)]
			var foe := _make_mob(mkey, mon[mkey], stats.get(mkey), next_id["v"], floor_num)
			foe.cell = ec
			foe.aware = false
			board.place(foe.id, ec)
			entities[foe.id] = foe
			next_id["v"] += 1
		# the stairs chamber breeds the GUARD: its strongest dweller goes Alfa
		if is_stairs:
			var best: CombatEntity = null
			for id in entities:
				var e: CombatEntity = entities[id]
				if e.faction == "enemy" and r.has_point(e.cell) 						and (best == null or e.max_hp > best.max_hp):
					best = e
			if best != null:
				best.max_hp = int(best.max_hp * 1.6)
				best.hp = best.max_hp
				best.to_hit += 1
				if not best.tags.has("miniboss"):
					best.tags.append("miniboss")
				best.name_pl = "Alfa: " + best.name_pl
	# an NPC somewhere mid-path (~40%)
	if rng.randf() < 0.4 and path.size() > 2:
		var midr: Rect2i = chambers[path.size() / 2]["rect"]
		var nc := _free_in_rect(board, rng, midr, entry, stairs)
		if nc != Vector2i(-1, -1):
			var npc := CombatEntity.new(next_id["v"], "", 1, 10, ["npc", "non_combat"])
			npc.faction = "npc"
			npc.affordances = ["talk"]
			npc.dialogue_tree_key = Dialogue.random_tree_key(rng)
			npc.name_pl = Dialogue.tree_speaker(npc.dialogue_tree_key)
			npc.cell = nc
			board.place(npc.id, nc)
			entities[npc.id] = npc
			next_id["v"] += 1
	# Repair pass: if a random object plugged a door gap, clear the path.
	_ensure_reachable(board, entry, stairs, entities)
	return {
		"name": str(mods.get("label", "Sektor")),
		"board": board,
		"entities": entities,
		"entry": entry,
		"door": stairs,
		"is_last": true,
		"exits": {stairs: {"descend": true, "guarded": true}},
	}

## A free cell inside a chamber rect, off the entry/stairs. (-1,-1) if none.
static func _free_in_rect(board: Board, rng: RandomNumberGenerator, r: Rect2i,
		entry: Vector2i, stairs: Vector2i) -> Vector2i:
	for _try in 30:
		var c := Vector2i(rng.randi_range(r.position.x, r.position.x + r.size.x - 1),
			rng.randi_range(r.position.y, r.position.y + r.size.y - 1))
		if c != entry and c != stairs and board.is_free(c):
			return c
	return Vector2i(-1, -1)

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

	# Interior pillars: cover that breaks line of sight — you can scout, regroup,
	# or sneak past. The corridor row (entry.y) stays clear, so the room is always
	# passable and _ensure_reachable keeps its guarantee.
	for _i in rng.randi_range(2, 4):
		var pc := Vector2i(rng.randi_range(2, w - 3), rng.randi_range(2, h - 3))
		if pc.y != entry.y and pc != entry and pc != door:
			board.set_wall(pc)

	# A conductive trap appears more often deeper (and per the route's trap bias).
	if rng.randf() < minf((0.3 + floor_num * 0.08) * trap_mul, 0.95):
		_place_trap(board, rng, entry, door)

	# Biome hazard pools (fire craters, flooded gratings): real cells you can
	# bait — or SHOVE — enemies into. Never on the corridor row.
	var hz: String = str(mods.get("hazard_kind", ""))
	if hz != "":
		for _i in rng.randi_range(1, 2) + floor_num / 3:
			var hc := Vector2i(rng.randi_range(2, w - 3), rng.randi_range(2, h - 3))
			if hc.y != entry.y and hc != entry and hc != door and board.hazard_at(hc) == "":
				board.set_hazard(hc, hz)

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
	# The biome's mob_tags triple the weight of on-theme monsters (distinct rosters).
	var eligible := _biased_mob_keys(mon,
		_eligible_mobs(mon, floor_num, false), mods.get("mob_tags", []))
	var n_enemy: int = clampi(int(round((floor_num / 2 + idx) * enemy_mul)), 0, 4)
	if idx == 0:
		n_enemy = maxi(0, n_enemy - 1)
	for _i in n_enemy:
		if eligible.is_empty():
			break
		var cell := _free_interior(board, rng, entry, door)
		if cell == Vector2i(-1, -1):
			break
		# Keep spawns away from the doorway — you get a beat to read the room
		# before anything can reach you.
		for _retry in 6:
			if absi(cell.x - entry.x) + absi(cell.y - entry.y) >= 5:
				break
			var c2 := _free_interior(board, rng, entry, door)
			if c2 != Vector2i(-1, -1):
				cell = c2
		var mkey: String = eligible[rng.randi_range(0, eligible.size() - 1)]
		var foe := _make_mob(mkey, mon[mkey], stats.get(mkey), next_id["v"], floor_num)
		foe.cell = cell
		# Distant foes start asleep — preserves the explore->engage beat.
		foe.aware = false
		board.place(foe.id, cell)
		entities[foe.id] = foe
		next_id["v"] += 1

	# Occasionally a non-combat NPC to talk to (not in the first room, ~30%).
	if idx > 0 and rng.randf() < 0.3:
		var cell := _free_interior(board, rng, entry, door)
		if cell != Vector2i(-1, -1):
			var npc := CombatEntity.new(next_id["v"], "", 1, 10, ["npc", "non_combat"])
			npc.faction = "npc"
			npc.affordances = ["talk"]
			npc.dialogue_tree_key = Dialogue.random_tree_key(rng)
			npc.name_pl = Dialogue.tree_speaker(npc.dialogue_tree_key)
			npc.cell = cell
			board.place(npc.id, cell)
			entities[npc.id] = npc
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

## Weight eligible mobs toward the biome's preferred tags (3x). A biome with no
## mob_tags — or no matching monsters — degrades gracefully to the flat pool.
static func _biased_mob_keys(mon: Dictionary, eligible: Array, mob_tags: Array) -> Array:
	if mob_tags.is_empty():
		return eligible
	var out: Array = []
	for key in eligible:
		out.append(key)
		var tags: Array = (mon[key] as Dictionary).get("tags", [])
		for t in mob_tags:
			if t in tags:
				out.append(key)
				out.append(key)
				break
	return out

static func _tag_floor_min(tags: Array) -> int:
	for t in tags:
		if (t as String).begins_with("floor_min:"):
			return int((t as String).substr(10))
	return 1

## Choose a boss for the finale: prefer a 'boss', then a 'miniboss', then anything.
static func _pick_boss(mon: Dictionary, floor_num: int, rng: RandomNumberGenerator) -> String:
	var bosses: Array = []
	var minis: Array = []
	for key in mon:
		var tags: Array = mon[key].get("tags", [])
		if "boss" in tags or key.begins_with("boss_"):
			bosses.append(key)
		elif "miniboss" in tags or key.begins_with("miniboss_"):
			minis.append(key)
	if not bosses.is_empty():
		return bosses[rng.randi_range(0, bosses.size() - 1)]
	if not minis.is_empty():
		return minis[rng.randi_range(0, minis.size() - 1)]
	var any: Array = mon.keys()
	return any[rng.randi_range(0, any.size() - 1)] if not any.is_empty() else "szczur"

## The finale arena: one beefed-up boss (+ a couple of minions), and an exit that
## only opens — i.e. only counts as victory — once the room is cleared.
static func _gen_boss_room(rng: RandomNumberGenerator, floor_num: int,
		mon: Dictionary, env: Dictionary, stats: Dictionary, next_id: Dictionary,
		mods: Dictionary) -> Dictionary:
	var w := rng.randi_range(13, 15)
	var h := 9
	var board := Board.new(w, h)
	for x in w:
		board.set_wall(Vector2i(x, 0)); board.set_wall(Vector2i(x, h - 1))
	for y in h:
		board.set_wall(Vector2i(0, y)); board.set_wall(Vector2i(w - 1, y))
	var entry := Vector2i(1, h / 2)
	var door := Vector2i(w - 2, h / 2)
	var entities: Dictionary = {}

	# The boss — extra HP, awake, centre stage.
	var bkey := _pick_boss(mon, floor_num, rng)
	var boss := _make_mob(bkey, mon[bkey], stats.get(bkey), next_id["v"], floor_num)
	boss.max_hp = int(round(boss.max_hp * 1.4))
	boss.hp = boss.max_hp
	boss.aware = true
	boss.cell = Vector2i(w / 2 + 1, h / 2)
	board.place(boss.id, boss.cell)
	entities[boss.id] = boss
	next_id["v"] += 1

	# A couple of normal minions flanking.
	var eligible := _eligible_mobs(mon, floor_num, false)
	for _i in 2:
		if eligible.is_empty():
			break
		var cell := _free_interior(board, rng, entry, door)
		if cell == Vector2i(-1, -1):
			break
		var mkey: String = eligible[rng.randi_range(0, eligible.size() - 1)]
		var foe := _make_mob(mkey, mon[mkey], stats.get(mkey), next_id["v"], floor_num)
		foe.aware = true
		foe.cell = cell
		board.place(foe.id, cell)
		entities[foe.id] = foe
		next_id["v"] += 1

	return {
		"name": "ARENA — %s" % boss.name_pl,
		"board": board,
		"entities": entities,
		"entry": entry,
		"door": door,
		"is_last": true,
		"exits": {door: {"descend": true, "requires_clear": true}},
		"boss": true,
	}

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
