extends SceneTree
## Route-gamble + biome generation tests. Run:
## godot --headless --path godot -s res://tests/test_routes.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _content() -> Dictionary:
	return {
		"MON": {"szczur": {"fallback_name": "Szczur", "tags": ["monster", "organic"], "floor_min": 1, "floor_max": 99}},
		"ENV": {"stol": {"fallback_name": "Stół", "tags": ["furniture", "wood"], "affordances": ["salvage"]}},
		"MOB_COMBAT_STATS": {"szczur": [22, "1d6+1", 2, 12]},
	}

func _count(data: Dictionary, faction: String) -> int:
	var n := 0
	for room in data["rooms"]:
		for id in room["entities"]:
			if (room["entities"][id] as CombatEntity).faction == faction:
				n += 1
	return n

func _initialize() -> void:
	print("=== routes tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 4

	# --- offer returns distinct keys ---
	var offer := Routes.offer(rng, 3)
	_ck(offer.size() == 3, "offer returns 3 routes")
	_ck(offer[0] != offer[1] and offer[1] != offer[2] and offer[0] != offer[2],
		"offered routes are distinct")
	for k in offer:
		_ck(Routes.BIOMES.has(k), "offered key '%s' is a real biome" % k)

	# --- mods derive from key + are neutral for unknown ---
	var m := Routes.mods_for("konflikt")
	_ck(m["biome_key"] == "konflikt", "mods carry the biome key")
	_ck(float(m["enemy_mul"]) > 1.0, "konflikt biases toward more enemies")
	var mu := Routes.mods_for("nope")
	_ck(abs(float(mu["enemy_mul"]) - 1.0) < 0.001, "unknown biome -> neutral mods")

	# --- biome actually biases generation (same seed, different biome) ---
	var content := _content()
	var konflikt := FloorGen.generate(4, 555, content, Routes.mods_for("konflikt"))
	var zamknieta := FloorGen.generate(4, 555, content, Routes.mods_for("zamknieta"))
	var e_konflikt := _count(konflikt, "enemy")
	var e_zamknieta := _count(zamknieta, "enemy")
	_ck(e_konflikt >= e_zamknieta,
		"a conflict route has at least as many enemies as a quiet route (same seed)")
	# the quiet route should usually have strictly fewer; allow equality only at floors
	# where both clamp to the same small count — assert across a couple of floors.
	var konflikt_total := 0; var zamkn_total := 0
	for fnum in [3, 4, 5]:
		konflikt_total += _count(FloorGen.generate(fnum, 88, content, Routes.mods_for("konflikt")), "enemy")
		zamkn_total += _count(FloorGen.generate(fnum, 88, content, Routes.mods_for("zamknieta")), "enemy")
	_ck(konflikt_total > zamkn_total, "across floors, conflict spawns more enemies than the quiet route")

	# --- the floor records its biome ---
	_ck(konflikt["biome"] == "konflikt", "generated floor stamps its biome key")
	var fl = Floor.new(konflikt)
	_ck(fl.biome == "konflikt", "Floor exposes the biome")

	# --- traps route biases trap placement (count water/wire hazards) ---
	var pulapki_haz := _hazards(FloorGen.generate(4, 7, content, Routes.mods_for("pulapki")))
	var zamkn_haz := _hazards(FloorGen.generate(4, 7, content, Routes.mods_for("zamknieta")))
	_ck(pulapki_haz >= zamkn_haz, "the trap route places at least as many hazards as the quiet one")

	# --- determinism: same seed+biome -> identical enemy count ---
	var a := _count(FloorGen.generate(4, 999, content, Routes.mods_for("serwis")), "enemy")
	var b := _count(FloorGen.generate(4, 999, content, Routes.mods_for("serwis")), "enemy")
	_ck(a == b, "same seed + biome is deterministic")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)

func _hazards(data: Dictionary) -> int:
	var n := 0
	for room in data["rooms"]:
		var board: Board = room["board"]
		n += board.hazards.size()
	return n
