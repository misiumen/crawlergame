extends SceneTree
## Headless sim tests (GUT-lite). Exit code = number of failures.
## Run: godot --headless --path godot -s res://tests/test_sim.gd

var _fails := 0
var _checks := 0

func _check(cond: bool, label: String) -> void:
	_checks += 1
	if cond:
		print("  OK  ", label)
	else:
		_fails += 1
		print("  XX  ", label)

func _initialize() -> void:
	print("=== sim tests ===")

	# --- board from ASCII ---
	var b := Board.from_ascii([
		"#####",
		"#~|.#",
		"#...#",
		"#####",
	])
	_check(b.w == 5 and b.h == 4, "board dims 5x4")
	_check(b.is_wall(Vector2i(0, 0)), "wall at corner")
	_check(b.hazard_at(Vector2i(1, 1)) == "water", "water hazard parsed")
	_check(b.hazard_at(Vector2i(2, 1)) == "wire", "wire hazard parsed")
	_check(b.is_free(Vector2i(3, 1)), "floor cell is free")
	_check(not b.is_free(Vector2i(0, 0)), "wall is not free")

	# --- entity placement + movement + occupancy ---
	var rat := CombatEntity.new(1, "Szczur", 22, 10, ["organic", "quadruped"])
	rat.cell = Vector2i(3, 1)
	b.place(rat.id, rat.cell)
	_check(b.occupant_at(Vector2i(3, 1)) == 1, "occupant placed")
	_check(not b.is_free(Vector2i(3, 1)), "occupied cell not free")
	b.move(rat.cell, Vector2i(3, 2))
	rat.cell = Vector2i(3, 2)
	_check(b.occupant_at(Vector2i(3, 2)) == 1 and b.occupant_at(Vector2i(3, 1)) == -1,
		"move updates occupancy")

	# --- tag-driven systemic properties ---
	_check(rat.has_property("flammable"), "organic implies flammable")
	_check(rat.has_property("bleeds"), "organic implies bleeds")
	var bot := CombatEntity.new(2, "Robot", 30, 14, ["robot"])
	_check(bot.has_property("metal") and bot.has_property("conductive"),
		"robot implies metal + conductive")

	# --- damage + statuses + death ---
	rat.add_status("bleeding", 3)
	_check(rat.has_status("bleeding"), "status applied")
	rat.take_damage(10)
	_check(rat.hp == 12 and rat.is_alive(), "damage applied, still alive")
	rat.tick_statuses()
	_check(int(rat.statuses.get("bleeding", 0)) == 2, "status ticks down")
	rat.take_damage(99)
	_check(not rat.is_alive(), "lethal damage kills")

	# --- adjacency (bump-attack reach) ---
	_check(b.is_adjacent(Vector2i(3, 2), Vector2i(2, 1)), "diagonal adjacency")
	_check(not b.is_adjacent(Vector2i(0, 0), Vector2i(2, 2)), "far cells not adjacent")
	_check(not b.is_adjacent(Vector2i(1, 1), Vector2i(1, 1)), "same cell not adjacent")

	print("=== %d checks, %d failed ===" % [_checks, _fails])
	quit(_fails)
