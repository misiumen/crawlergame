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
	_ck(p.hp >= 100, "positioning kill: player took no counter-damage (level-up may heal past 100)")

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
	var ee: Dictionary = enc["entities"]
	_ck(ee.size() >= 2 and ee[1].faction == "player" and ee[2].faction == "enemy",
		"intake has player + rat (+ objects)")
	_ck(not (ee[2] as CombatEntity).aware, "intake rat starts asleep")
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

	# --- awareness: a sleeping enemy stays idle until it notices you ---
	var ba := Board.from_ascii(["##########", "#........#", "##########"])
	var pa := CombatEntity.new(1, "Ty", 100, 14, []); pa.faction = "player"; pa.cell = Vector2i(1, 1)
	var ea := CombatEntity.new(2, "Wrog", 20, 10, []); ea.faction = "enemy"; ea.cell = Vector2i(8, 1); ea.aware = false
	var csa := CombatSim.new(ba, {1: pa, 2: ea}, 1, 5); ba.place(1, pa.cell); ba.place(2, ea.cell)
	csa.player_wait()
	_ck(not ea.aware and ea.cell == Vector2i(8, 1), "distant sleeping enemy stays idle")
	var g := 0
	while not ea.aware and g < 10:
		csa.player_move(Vector2i.RIGHT); g += 1
	_ck(ea.aware, "enemy wakes when player comes within sight")

	# --- dismantle the world into materials; objects block movement, not attacks ---
	var bs := Board.from_ascii(["#####", "#...#", "#####"])
	var ps := CombatEntity.new(1, "Ty", 100, 14, []); ps.faction = "player"; ps.cell = Vector2i(1, 1)
	var obj := CombatEntity.new(3, "Stol", 6, 5, ["furniture", "wood", "salvageable"])
	obj.faction = "object"; obj.affordances = ["salvage"]; obj.cell = Vector2i(2, 1)
	var css := CombatSim.new(bs, {1: ps, 3: obj}, 1, 2); bs.place(1, ps.cell); bs.place(3, obj.cell)
	var evb := css.player_move(Vector2i.RIGHT)
	_ck(_has_event(evb, "blocked") and ps.cell == Vector2i(1, 1), "moving into an object is blocked, not an attack")
	var evi := css.player_interact()
	_ck(_has_event(evi, "salvage"), "dismantle emits a salvage event")
	_ck(css.materials.size() > 0, "dismantling yields materials")
	_ck(not obj.is_alive(), "dismantled object is removed")

	# --- crafting (bench API): electric+binding tags -> electric coating -> attacks bypass thick hide ---
	# przewód=[conductive,electric] + szmata=[binding,soft] → matches rule electric+binding → DC 10
	# int_xp=50 → int_mod=10, min roll=11, always sukces or krytyk — deterministic on this seed.
	var bc := Board.from_ascii(["####", "#..#", "####"])
	var pc := CombatEntity.new(1, "Ty", 100, 14, []); pc.faction = "player"; pc.cell = Vector2i(1, 1)
	var rc := CombatEntity.new(2, "Szczur", 200, 1, ["organic", "thick_hide", "shock_weak"])
	rc.faction = "enemy"; rc.cell = Vector2i(2, 1); rc.aware = true     # ac 1 = always hit, 200 HP = no early kill
	var csc := CombatSim.new(bc, {1: pc, 2: rc}, 1, 11); bc.place(1, pc.cell); bc.place(2, rc.cell)
	pc.int_xp = 50  # int_mod = 10, guarantees sukces on DC 10
	csc.materials = {"przewód": 1, "szmata": 1}
	var prev := csc.bench_preview(["przewód", "szmata"])
	_ck(prev.get("rule") != null, "bench preview matches electric+binding rule")
	_ck(prev.get("dc") == 10, "bench DC = 10 (12 base - 2 binding bonus)")
	var evc := csc.bench_attempt(["przewód", "szmata"])
	_ck(_has_event(evc, "craft_attempt"), "bench_attempt emits craft_attempt event")
	_ck(csc.items.size() == 1, "crafted item added to items list")
	_ck((csc.items[0] as GameItem).category == "coating", "crafted item is a coating")
	_ck(not csc.materials.has("szmata"), "bench_attempt spent the szmata material")
	var evuse := csc.player_use_item(0)
	_ck(_has_event(evuse, "coating_applied"), "player_use_item applies coating to weapon")
	_ck(pc.coating == "electric", "electric coating wired to player weapon")
	_ck(pc.coating_charges == 3, "coating grants 3 hit charges")
	var eva := csc.player_move(Vector2i.RIGHT)                          # coated bump-attack
	_ck(_has_event(eva, "damage", "dmg_type", "electric"), "coated attack deals electric (bypasses thick hide)")
	_ck(pc.coating_charges == 2, "one coating charge consumed on hit")
	var evf := csc.bench_attempt(["przewód", "szmata"])
	_ck(_has_event(evf, "craft_fail"), "bench_attempt without materials fails gracefully")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
