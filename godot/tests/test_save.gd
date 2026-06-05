extends SceneTree
## Save/load round-trip tests. Run:
## godot --headless --path godot -s res://tests/test_save.gd

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

func _initialize() -> void:
	print("=== save/load tests ===")
	Save.clear()
	var content := _content()

	# --- no save initially ---
	_ck(not Save.has_save(), "no save exists at the start")

	# --- build a run, dress it up, write a checkpoint ---
	var data := FloorGen.generate(3, 12345, content)
	var floor = Floor.new(data)
	floor.player.hp = 47
	floor.player.max_hp = 120
	floor.player.class_key = "bruiser"
	floor.player.affinity = {"melee": 11, "tech": 2}
	floor.player.int_xp = 25
	floor.player.bonus_damage = 3
	floor.player.run_kills = 6
	floor.player.coating = "electric"
	floor.player.coating_charges = 2
	floor.inv = {"złom": 4, "przewód": 1}
	floor.discovered_recipes = [{"tags": ["binding", "electric"], "name": "Powłoka prądowa", "times": 2}]
	floor.audience.rating = 58
	floor.audience.peak = 73
	floor.sponsors.attention = {"novachem_biotech": 8}
	var an_item := GameItem.new("Fiolka kwasu", GameItem.CAT_THROWN, Rarity.RARE)
	an_item.charges = 2
	an_item.effect = {"dmg_type": "corrosive", "base_dmg": 5}
	an_item.affix_names_pl = ["natrysk"]
	floor.items = [an_item]
	floor.class_offered = true

	Save.write(floor, 12345)
	_ck(Save.has_save(), "write creates a save file")

	# --- read it back ---
	var sd := Save.read()
	_ck(int(sd["seed"]) == 12345, "save round-trips the seed")
	_ck(int(sd["depth"]) == 3, "save round-trips the depth")
	_ck(sd["player"]["class_key"] == "bruiser", "save round-trips the class")

	# --- rebuild the floor from the save ---
	var fl2 = Save.rebuild_floor(sd, content)
	_ck(fl2 != null, "rebuild_floor returns a Floor")
	_ck(fl2.depth == 3, "rebuilt floor is at the saved depth")
	var p2 = fl2.player
	_ck(p2.hp == 47 and p2.max_hp == 120, "player HP restored")
	_ck(p2.class_key == "bruiser", "player class restored")
	_ck(int(p2.affinity.get("melee", 0)) == 11, "player affinity restored")
	_ck(p2.int_xp == 25, "player INT restored")
	_ck(p2.bonus_damage == 3, "player weapon bonus restored")
	_ck(p2.run_kills == 6, "run kills restored")
	_ck(p2.coating == "electric" and p2.coating_charges == 2, "weapon coating restored")
	_ck(int(fl2.inv.get("złom", 0)) == 4, "materials restored")
	_ck(fl2.discovered_recipes.size() == 1, "recipe book restored")
	_ck(fl2.audience.rating == 58 and fl2.audience.peak == 73, "audience restored")
	_ck(int(fl2.sponsors.get_attention("novachem_biotech")) == 8, "sponsor attention restored")
	_ck(fl2.items.size() == 1, "items restored")
	_ck((fl2.items[0] as GameItem).rarity == Rarity.RARE, "item rarity restored")
	_ck((fl2.items[0] as GameItem).charges == 2, "item charges restored")
	_ck(fl2.class_offered, "class_offered flag restored")

	# --- determinism: the rebuilt floor matches a fresh generate of (seed, depth) ---
	var fresh := FloorGen.generate(3, 12345, content)
	_ck((fresh["rooms"] as Array).size() == fl2.rooms.size(),
		"rebuilt floor layout matches a fresh generate (same seed+depth)")

	# --- clear ---
	Save.clear()
	_ck(not Save.has_save(), "clear removes the save")
	_ck(Save.rebuild_floor({}, content) == null, "rebuild of an empty save is null")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
