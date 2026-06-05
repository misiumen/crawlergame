extends SceneTree
## Elemental combat: damage typing, status DoT, corroded AC, thrown + trap items.
## Run: godot --headless --path godot -s res://tests/test_elements.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _has(evs: Array, type: String) -> bool:
	for e in evs:
		if e.get("type") == type:
			return true
	return false

func _sim_with(enemy_tags: Array, hp := 200) -> Array:
	var board := Board.from_ascii(["#####", "#...#", "#####"])
	var p := CombatEntity.new(1, "Ty", 100, 14, []); p.faction = "player"; p.cell = Vector2i(1, 1)
	var e := CombatEntity.new(2, "Cel", hp, 12, enemy_tags); e.faction = "enemy"
	e.cell = Vector2i(2, 1); e.aware = true
	var cs := CombatSim.new(board, {1: p, 2: e}, 1, 5)
	board.place(1, p.cell); board.place(2, e.cell)
	return [cs, p, e]

func _initialize() -> void:
	print("=== elemental combat tests ===")

	# --- damage typing by tag ---
	var r = _sim_with(["organic", "flammable"])
	var cs: CombatSim = r[0]; var e: CombatEntity = r[2]
	_ck(cs.effective_damage(e, 10, CombatSim.DMG_FIRE) == 18, "fire vs flammable: 10 -> 18 (x1.75)")
	var r2 = _sim_with(["construct", "metal"])
	var cs2: CombatSim = r2[0]; var e2: CombatEntity = r2[2]
	_ck(cs2.effective_damage(e2, 10, CombatSim.DMG_ACID) == 16, "acid vs metal: 10 -> 16 (x1.6)")
	_ck(cs2.effective_damage(e2, 10, CombatSim.DMG_ELECTRIC) == 15, "electric vs conductive metal: 10 -> 15")
	var r3 = _sim_with(["slime", "liquid"])   # liquid -> wet
	var cs3: CombatSim = r3[0]; var e3: CombatEntity = r3[2]
	_ck(cs3.effective_damage(e3, 10, CombatSim.DMG_COLD) == 15, "cold vs wet: 10 -> 15 (x1.5)")
	_ck(cs3.effective_damage(e3, 10, CombatSim.DMG_FIRE) == 5, "fire vs wet: 10 -> 5 (x0.5)")

	# --- status DoT ticks (non-flammable target -> flat 3) ---
	var r4 = _sim_with(["humanoid"], 100)
	var cs4: CombatSim = r4[0]; var e4: CombatEntity = r4[2]
	e4.add_status("burning", 3)
	var hp_before := e4.hp
	cs4.player_wait()                       # ends the round -> DoT ticks
	_ck(e4.hp < hp_before, "burning deals damage each round")
	_ck(e4.hp == hp_before - 3, "burning ticks 3 fire damage on a non-flammable target")
	# a flammable target takes MORE from the same burn (the fire multiplier applies)
	var r4b = _sim_with(["organic"], 100)
	var cs4b: CombatSim = r4b[0]; var e4b: CombatEntity = r4b[2]
	e4b.add_status("burning", 3)
	cs4b.player_wait()
	_ck(e4b.hp == 100 - 5, "burning a flammable target hurts more (3 x1.75 -> 5)")

	# --- corroded lowers effective AC ---
	var r5 = _sim_with(["humanoid"], 100)
	var cs5: CombatSim = r5[0]; var e5: CombatEntity = r5[2]
	var ac0 := cs5._eff_ac(e5)
	e5.add_status("corroded", 3)
	_ck(cs5._eff_ac(e5) == ac0 - 2, "corroded reduces effective AC by 2")

	# --- thrown item: hits the nearest enemy with its element + status + hazard ---
	var r6 = _sim_with(["organic", "flammable"], 100)
	var cs6: CombatSim = r6[0]; var e6: CombatEntity = r6[2]
	var firebomb := GameItem.new("Butelka zapalająca", GameItem.CAT_THROWN, Rarity.COMMON)
	firebomb.charges = 2
	firebomb.effect = {"dmg_type": "fire", "base_dmg": 6, "hazard": "fire"}
	cs6.items = [firebomb]
	var hp6 := e6.hp
	var ev := cs6.player_use_item(0)
	_ck(_has(ev, "throw"), "using a thrown item emits a throw event")
	_ck(e6.hp < hp6, "the thrown firebomb damaged the enemy")
	_ck(cs6.board.hazard_at(e6.cell) == "fire", "the firebomb left a fire tile under the target")
	_ck(firebomb.charges == 1, "throwing spent one charge")

	# acid vial applies the corroded status (and 'corrosive' maps to acid damage)
	var r7 = _sim_with(["humanoid"], 100)
	var cs7: CombatSim = r7[0]; var e7: CombatEntity = r7[2]
	var vial := GameItem.new("Fiolka kwasu", GameItem.CAT_THROWN, Rarity.COMMON)
	vial.charges = 1
	vial.effect = {"dmg_type": "corrosive", "base_dmg": 5, "status": "corroded", "status_turns": 3}
	cs7.items = [vial]
	cs7.player_use_item(0)
	_ck(e7.has_status("corroded"), "the acid vial applies corroded")

	# --- a thrown item with no target is not wasted ---
	var board8 := Board.from_ascii(["#####", "#...#", "#####"])
	var p8 := CombatEntity.new(1, "Ty", 100, 14, []); p8.faction = "player"; p8.cell = Vector2i(1, 1)
	var cs8 := CombatSim.new(board8, {1: p8}, 1, 5); board8.place(1, p8.cell)
	var bomb8 := GameItem.new("Granat", GameItem.CAT_THROWN, Rarity.COMMON)
	bomb8.charges = 2; bomb8.effect = {"dmg_type": "electric", "base_dmg": 8}
	cs8.items = [bomb8]
	var ev8 := cs8.player_use_item(0)
	_ck(_has(ev8, "none"), "throwing with no enemy returns a 'none' action")
	_ck(bomb8.charges == 2, "a wasted throw is prevented (charge kept)")

	# --- trap item arms a hazard on an adjacent cell (room with space around you) ---
	var b9 := Board.from_ascii(["#####", "#...#", "#...#", "#####"])
	var p9 := CombatEntity.new(1, "Ty", 100, 14, []); p9.faction = "player"; p9.cell = Vector2i(2, 1)
	var e9 := CombatEntity.new(2, "Cel", 100, 12, ["organic"]); e9.faction = "enemy"; e9.cell = Vector2i(3, 2); e9.aware = true
	var cs9 := CombatSim.new(b9, {1: p9, 2: e9}, 1, 5); b9.place(1, p9.cell); b9.place(2, e9.cell)
	var trap := GameItem.new("Pułapka", GameItem.CAT_TRAP, Rarity.COMMON)
	trap.charges = 1; trap.effect = {"hazard": "wire"}
	cs9.items = [trap]
	var ev9 := cs9.player_use_item(0)
	_ck(_has(ev9, "trap_armed"), "deploying a trap emits trap_armed")
	_ck(p9.run_traps_armed == 1, "trap deployment is tallied")

	# --- stepping onto a fire tile ignites the stepper ---
	var bf := Board.from_ascii(["#####", "#...#", "#####"])
	var pf := CombatEntity.new(1, "Ty", 100, 14, []); pf.faction = "player"; pf.cell = Vector2i(1, 1)
	var ef := CombatEntity.new(2, "Cel", 100, 1, ["organic"]); ef.faction = "enemy"; ef.cell = Vector2i(3, 1); ef.aware = true
	var csf := CombatSim.new(bf, {1: pf, 2: ef}, 1, 5); bf.place(1, pf.cell); bf.place(2, ef.cell)
	bf.set_hazard(Vector2i(2, 1), "fire")
	var evf := csf.player_move(Vector2i.RIGHT)   # step into the fire tile
	_ck(_has(evf, "systemic"), "stepping into fire triggers a systemic event")
	_ck(pf.has_status("burning"), "the fire tile set the player burning")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
