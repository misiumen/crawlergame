extends SceneTree
## Headless combat-sim tests. Run: godot --headless --path godot -s res://tests/test_combat.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _has_event(evs: Array, type: String, key := "", val = null) -> bool:
	for e in evs:
		if e.get("type") == type and (key == "" or e.get(key) == val):
			return true
	return false

func _initialize() -> void:
	print("=== combat tests ===")

	# --- the core design proof: damage gradient is deterministic ---
	var rat := CombatEntity.new(2, "Szczur", 22, 13,
		["organic", "quadruped", "thick_hide", "shock_weak"])
	var cs := CombatSim.new(Board.new(3, 3), {2: rat}, 1, 1)
	_ck(cs.effective_damage(rat, 8, CombatSim.DMG_PHYSICAL) == 4, "thick hide halves physical (8->4)")
	_ck(cs.effective_damage(rat, 8, CombatSim.DMG_ELECTRIC) == 16, "shock weakness doubles electric (8->16)")
	# => per equal base, the clever (electric) kill hits 4x harder than brute.

	# --- shove onto water+wire triggers a shock that bypasses thick hide ---
	var b := Board.from_ascii(["#####", "#~|.#", "#####"])   # water (1,1), wire (2,1)
	var p := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"])
	p.faction = "player"; p.cell = Vector2i(3, 1)
	var r2 := CombatEntity.new(2, "Szczur", 22, 13, ["organic", "thick_hide", "shock_weak"])
	r2.faction = "enemy"; r2.cell = Vector2i(2, 1)
	var cs2 := CombatSim.new(b, {1: p, 2: r2}, 1, 7)
	b.place(1, p.cell); b.place(2, r2.cell)
	var rhp0 := r2.hp
	var evs := cs2.player_shove(Vector2i.LEFT)               # (2,1) -> (1,1) water by the wire
	_ck(r2.cell == Vector2i(1, 1), "rat shoved onto the water tile")
	_ck(_has_event(evs, "systemic", "element", "electric"), "water+wire triggers electric shock")
	_ck(r2.hp < rhp0, "shock damaged the rat")
	_ck(p.hp == 100, "positioning kill: player took no counter-damage")

	# --- enemy turn: an adjacent enemy attacks; a distant one steps closer ---
	var b2 := Board.from_ascii(["######", "#....#", "######"])
	var p2 := CombatEntity.new(1, "Ty", 100, 14, []); p2.faction = "player"; p2.cell = Vector2i(1, 1)
	var e2 := CombatEntity.new(2, "Wrog", 20, 10, []); e2.faction = "enemy"; e2.cell = Vector2i(4, 1)
	var cs3 := CombatSim.new(b2, {1: p2, 2: e2}, 1, 5); b2.place(1, p2.cell); b2.place(2, e2.cell)
	var evs2 := cs3.player_wait()
	_ck(_has_event(evs2, "move", "id", 2), "distant enemy steps toward player")
	_ck(e2.cell.x < 4, "enemy actually moved closer")

	# --- win condition: kill the only enemy ---
	var b3 := Board.from_ascii(["####", "#..#", "####"])     # (1,1),(2,1) floor
	var p3 := CombatEntity.new(1, "Ty", 100, 14, []); p3.faction = "player"; p3.cell = Vector2i(2, 1)
	var r3 := CombatEntity.new(2, "Szczur", 3, 10, ["organic"]); r3.faction = "enemy"; r3.cell = Vector2i(1, 1)
	var cs4 := CombatSim.new(b3, {1: p3, 2: r3}, 1, 3); b3.place(1, p3.cell); b3.place(2, r3.cell)
	var guard := 0
	while not cs4.over and guard < 50:
		cs4.player_move(Vector2i.LEFT)
		guard += 1
	_ck(cs4.outcome == "win", "killing the only enemy wins")

	# --- encounter factory builds and is internally consistent ---
	var enc := Encounters.intake()
	var eb: Board = enc["board"]
	_ck(enc.has("board") and enc.has("entities") and enc.has("player_id"), "intake encounter builds")
	_ck((enc["entities"] as Dictionary).size() == 2, "intake has player + rat")
	# a water tile in the intake is adjacent to the wire (the trap is real)
	var trap_ok := false
	for y in eb.h:
		for x in eb.w:
			var c := Vector2i(x, y)
			if eb.hazard_at(c) == "water":
				for dy in range(-1, 2):
					for dx in range(-1, 2):
						if eb.hazard_at(c + Vector2i(dx, dy)) == "wire":
							trap_ok = true
	_ck(trap_ok, "intake has a water tile adjacent to the wire (live trap)")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
