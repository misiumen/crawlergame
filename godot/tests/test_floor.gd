extends SceneTree
## Headless floor tests: room transitions carry the player + inventory; the
## stairs descend. Run: godot --headless --path godot -s res://tests/test_floor.gd

var _f := 0
var _n := 0
func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c: _f += 1

func _initialize() -> void:
	print("=== floor tests ===")
	var fl := Floor.new(Encounters.floor())
	_ck(fl.current == 0 and fl.current_name() == "Magazyn", "starts in room 0 (Magazyn)")
	_ck(fl.sim.player().cell == Vector2i(2, 3), "player at start cell")
	_ck(fl.rooms.size() == 2, "floor has two rooms")

	fl.inv["złom"] = 5                                   # shared run inventory
	_ck(fl.sim.materials.get("złom", 0) == 5, "inv is shared with the active room sim")

	# walk east to the door (9,3) and step through
	for i in 7:
		fl.sim.player_move(Vector2i.RIGHT)
	_ck(fl.sim.player().cell == Vector2i(9, 3), "reached the east door")
	var r = fl.try_transition()
	_ck(r != null and r.get("name") == "Hala", "transition into Hala")
	_ck(fl.current == 1 and fl.sim.player().cell == Vector2i(2, 3), "entered Hala at the entry cell")
	_ck(fl.sim.materials.get("złom", 0) == 5, "materials persist across rooms")
	_ck(fl.sim.entities.has(2) and not (fl.sim.entities[2] as CombatEntity).aware,
		"rat present and asleep in Hala")

	# stairs descend
	fl.player.cell = Vector2i(11, 6)
	var d = fl.try_transition()
	_ck(d != null and d.get("descend", false) and fl.descended, "stairs trigger descend")

	# going back: from Hala's west door (1,3) -> Magazyn at (8,3)
	fl.player.cell = Vector2i(1, 3)
	var b = fl.try_transition()
	_ck(b != null and b.get("name") == "Magazyn" and fl.sim.player().cell == Vector2i(8, 3),
		"back door returns to Magazyn at the right cell")
	# the table we never dismantled is still there (room state persists)
	_ck(fl.sim.entities.has(3), "room state persists (furniture still present)")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
