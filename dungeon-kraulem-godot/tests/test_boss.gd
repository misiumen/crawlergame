extends SceneTree
## Boss-finale tests. Run:
## godot --headless --path godot -s res://tests/test_boss.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _content() -> Dictionary:
	return {
		"MON": {
			"szczur":  {"fallback_name": "Szczur", "tags": ["monster", "organic"], "floor_min": 1, "floor_max": 99},
			"prezes":  {"fallback_name": "Prezes Syndykatu", "tags": ["monster", "boss", "humanoid"], "floor_min": 1, "floor_max": 99},
		},
		"ENV": {"stol": {"fallback_name": "Stół", "tags": ["furniture", "wood"], "affordances": ["salvage"]}},
		"MOB_COMBAT_STATS": {"szczur": [22, "1d6+1", 2, 12], "prezes": [120, "2d8+4", 6, 15]},
	}

func _boss_of(data: Dictionary) -> CombatEntity:
	for room in data["rooms"]:
		for id in room["entities"]:
			var e: CombatEntity = room["entities"][id]
			if e.faction == "enemy" and ("boss" in e.tags or e.monster_key == "prezes"):
				return e
	return null

func _initialize() -> void:
	print("=== boss finale tests ===")
	var content := _content()

	# --- a boss floor is a single arena with a boss ---
	var data := FloorGen.generate(6, 42, content, {}, true)
	_ck((data["rooms"] as Array).size() == 1, "boss floor is a single arena room")
	var room: Dictionary = data["rooms"][0]
	_ck(room.get("boss", false), "the room is flagged as a boss room")
	var boss := _boss_of(data)
	_ck(boss != null, "the arena contains a boss")
	_ck(boss != null and boss.aware, "the boss starts awake")
	# boss is beefed up: 120 base * 1.4 (* depth scaling) -> well above 120
	_ck(boss != null and boss.max_hp > 120, "the boss has boosted HP")
	_ck(boss != null and boss.dmg_dice == "2d8+4", "the boss uses its content damage dice")

	# --- the exit is gated until the room is cleared ---
	var ex: Dictionary = room["exits"][room["door"]]
	_ck(ex.get("descend", false) and ex.get("requires_clear", false),
		"the boss-arena exit descends but requires clearing")

	# --- try_transition is blocked while the boss lives, opens once it's dead ---
	var fl = Floor.new(data)
	fl.player.cell = room["door"]                 # stand on the stair
	var r1 = fl.try_transition()
	_ck(r1 != null and r1.get("blocked", "") == "boss", "stairs are blocked while the boss lives")
	# kill everything in the room
	for id in fl.sim.entities:
		var e: CombatEntity = fl.sim.entities[id]
		if e.faction == "enemy":
			e.alive = false; e.hp = 0
	var r2 = fl.try_transition()
	_ck(r2 != null and r2.get("descend", false), "stairs open (victory) once the arena is cleared")

	# --- non-boss floors never gate their exit ---
	var normal := FloorGen.generate(3, 42, content, {}, false)
	var nlast: Dictionary = normal["rooms"][normal["rooms"].size() - 1]
	_ck(not (nlast["exits"][nlast["door"]] as Dictionary).get("requires_clear", false),
		"normal floors descend freely (no clear gate)")

	# --- bosses do NOT leak into normal rooms ---
	var leaked := false
	for fnum in [1, 2, 3, 4, 5]:
		var nd := FloorGen.generate(fnum, fnum * 9, content, {}, false)
		if _boss_of(nd) != null:
			leaked = true
	_ck(not leaked, "the boss never spawns on a normal floor")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
