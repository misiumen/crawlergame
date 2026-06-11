extends SceneTree
## Procedural floor generation + dice tests. Run:
## godot --headless --path godot -s res://tests/test_floorgen.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _path_exists(board: Board, frm: Vector2i, to: Vector2i, ents: Dictionary) -> bool:
	return FloorGen._path_exists(board, frm, to, ents)

# A small synthetic content bundle (no Data autoload needed).
func _content() -> Dictionary:
	return {
		"MON": {
			"szczur":  {"fallback_name": "Szczur", "tags": ["monster", "small", "organic"], "floor_min": 1, "floor_max": 4},
			"karaluch":{"fallback_name": "Karaluch", "tags": ["monster", "small", "robactwo"], "floor_min": 1, "floor_max": 99},
			"golem":   {"fallback_name": "Golem", "tags": ["monster", "construct", "metal", "floor_min:5"]},
			"boss_x":  {"fallback_name": "Boss", "tags": ["monster", "boss"], "floor_min": 1, "floor_max": 99},
		},
		"ENV": {
			"stol":   {"fallback_name": "Stół", "tags": ["furniture", "wood", "salvageable"], "affordances": ["inspect", "salvage"]},
			"szafka": {"fallback_name": "Szafka", "tags": ["furniture", "metal", "electric"], "affordances": ["inspect", "salvage"]},
		},
		"MOB_COMBAT_STATS": {
			"szczur":  [22, "1d6+1", 2, 12],
			"karaluch":[14, "1d4", 1, 11],
			"golem":   [60, "1d10+2", 4, 15],
			"boss_x":  [150, "2d8+4", 6, 16],
		},
	}

func _initialize() -> void:
	print("=== floorgen / dice tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 1

	# --- dice ---
	_ck(Dice.parse("2d6+3") == {"count": 2, "sides": 6, "bonus": 3}, "parse 2d6+3")
	_ck(Dice.parse("1d8") == {"count": 1, "sides": 8, "bonus": 0}, "parse 1d8 (no bonus)")
	_ck(Dice.parse("garbage").is_empty(), "parse rejects garbage")
	_ck(abs(Dice.average("2d6") - 7.0) < 0.001, "average 2d6 = 7")
	_ck(abs(Dice.average("1d6+2") - 5.5) < 0.001, "average 1d6+2 = 5.5")
	var lo := 999; var hi := -999
	for i in 400:
		var r := Dice.roll("1d6+2", rng)
		lo = mini(lo, r); hi = maxi(hi, r)
	_ck(lo == 3 and hi == 8, "1d6+2 rolls span [3,8]")
	_ck(Dice.roll("bad", rng) == 1, "bad dice notation rolls 1, not a crash")

	# --- generation: shape matches Encounters.floor() ---
	var content := _content()
	var data := FloorGen.generate(1, 42, content)
	_ck(data.has("rooms") and data.has("player") and data.has("start_cell"),
		"generate returns the Floor data shape")
	_ck((data["rooms"] as Array).size() == 1, "a floor is ONE continuous board now")
	var cont_b: Board = data["rooms"][0]["board"]
	var carved := 0
	for cy in cont_b.h:
		for cx in cont_b.w:
			if not cont_b.is_wall(Vector2i(cx, cy)):
				carved += 1
	_ck(carved > 150, "chambers are carved out of the rock (real floor area)")
	_ck(bool((data["rooms"][0]["exits"].values()[0] as Dictionary).get("guarded", false)),
		"the stairs are guarded")
	_ck(data["player"].faction == "player", "data carries a player")
	var fl = Floor.new(data)
	_ck(fl.sim != null, "Floor consumes generated data and builds a sim")

	# --- determinism: same seed + floor -> identical structure ---
	var a := FloorGen.generate(3, 777, content)
	var b := FloorGen.generate(3, 777, content)
	_ck((a["rooms"] as Array).size() == (b["rooms"] as Array).size(),
		"same seed -> same room count")
	var a0: Board = a["rooms"][0]["board"]
	var b0: Board = b["rooms"][0]["board"]
	_ck(a0.w == b0.w and a0.h == b0.h, "same seed -> identical room dimensions")
	_ck(a["rooms"][0]["entry"] == b["rooms"][0]["entry"], "same seed -> identical entry")
	var c := FloorGen.generate(3, 778, content)
	_ck(a0.w != (c["rooms"][0]["board"] as Board).w or a["rooms"].size() != c["rooms"].size()
		or a["rooms"][0]["entry"] != c["rooms"][0]["entry"],
		"a different seed produces a different layout")

	# --- every room is reachable entry->door past its objects ---
	var all_reachable := true
	for room in data["rooms"]:
		if not _path_exists(room["board"], room["entry"], room["door"], room["entities"]):
			all_reachable = false
	_ck(all_reachable, "validation guarantees entry->door is walkable in every room")

	# --- the last room descends; earlier rooms link forward ---
	var rooms: Array = data["rooms"]
	var last: Dictionary = rooms[rooms.size() - 1]
	_ck(last["exits"][last["door"]].get("descend", false), "the last room's door descends")
	if rooms.size() >= 2:
		var first: Dictionary = rooms[0]
		_ck(first["exits"][first["door"]].get("to", -1) == 1, "room 0 links forward to room 1")

	# --- enemies come from content, scaled by depth, carry combat stats ---
	var deep := FloorGen.generate(5, 9, content)
	var found_enemy := false
	var found_golem := false
	for room in deep["rooms"]:
		for id in room["entities"]:
			var e: CombatEntity = room["entities"][id]
			if e.faction == "enemy":
				found_enemy = true
				_ck(e.dmg_dice != "", "a generated enemy carries damage dice")
				if e.monster_key == "golem":
					found_golem = true
	_ck(found_enemy, "deeper floors spawn enemies")
	_ck(found_golem, "floor-5 pool includes the floor_min:5 golem")

	# --- bosses are excluded from normal rooms ---
	var saw_boss := false
	for fnum in [1, 3, 5]:
		var fd := FloorGen.generate(fnum, fnum * 13, content)
		for room in fd["rooms"]:
			for id in room["entities"]:
				if (room["entities"][id] as CombatEntity).monster_key == "boss_x":
					saw_boss = true
	_ck(not saw_boss, "bosses/minibosses never populate normal rooms")

	# --- depth scaling: same mob is tougher deeper ---
	var f1 := FloorGen.generate(1, 5, content)
	var f6 := FloorGen.generate(6, 5, content)
	var hp1 := _first_enemy_hp(f1, "szczur")
	var hp6 := _first_enemy_hp(f6, "szczur")
	if hp1 > 0 and hp6 > 0:
		_ck(hp6 > hp1, "the same mob has more HP on a deeper floor")

	# --- no-content fallback still produces a valid floor ---
	var fb := FloorGen.generate(1, 1, {})
	_ck((fb["rooms"] as Array).size() == 1, "empty content -> fallback floor still generates")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)

func _first_enemy_hp(data: Dictionary, key: String) -> int:
	for room in data["rooms"]:
		for id in room["entities"]:
			var e: CombatEntity = room["entities"][id]
			if e.faction == "enemy" and e.monster_key == key:
				return e.max_hp
	return -1
