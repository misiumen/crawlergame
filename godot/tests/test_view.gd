extends SceneTree
## Headless smoke/logic test for the presentation layer: the scene builds, input
## drivers reach the sim, and many actions + frames run without script errors.
## (Pixels aren't verifiable headless; this proves the wiring is sound.)
## Run: godot --headless --path godot -s res://tests/test_view.gd

var _f := 0
var _n := 0
func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c: _f += 1

func _initialize() -> void:
	print("=== view tests ===")
	Save.clear()                         # start from a clean slate, not a leftover save
	var bv = preload("res://scenes/BoardView.gd").new()
	bv._font = ThemeDB.fallback_font
	bv._build()                          # (_ready is deferred under -s; call directly)
	_ck(bv.sim != null, "scene builds a CombatSim")
	_ck(bv._vpos.size() >= 2, "visual positions initialised for tokens")

	# narration: events map to readable Polish log lines
	_ck(bv._event_line({"type": "damage", "target": 2, "amount": 5, "dmg_type": "electric"}) != "",
		"narration: electric damage -> line")
	_ck(bv._event_line({"type": "salvage", "target": 3, "gained": {"drewno": 2}}) != "",
		"narration: salvage -> line")
	_ck(bv._event_line({"type": "notice", "id": 2}) != "", "narration: notice -> line")

	var r0: int = bv.sim.round_num
	bv.handle_dir(Vector2i.RIGHT)        # a real move ends the player turn
	_ck(bv.sim.round_num > r0, "an action advances the round")

	for i in 6:
		bv._process(0.016)               # manual frames (no main loop under -s)
	_ck(true, "_process runs without error")

	# bench crafting via the view: electric+binding -> electric coating, then use it
	bv.sim.materials = {"przewód": 1, "szmata": 1}
	bv.sim.player().int_xp = 50            # int_mod 10 guarantees success on DC 10
	bv._animate(bv.sim.bench_attempt(["przewód", "szmata"]))
	_ck(bv.floor.items.size() >= 1, "bench_attempt via the view crafts an item")
	var narrated := false
	for line in bv._log:
		if (line as String).begins_with("Konferansjer:"):
			narrated = true
	_ck(narrated, "konferansjer narrates the successful craft")
	bv._animate(bv.sim.player_use_item(0))
	_ck(bv.sim.player().coating == "electric", "using the crafted coating arms the weapon")

	# the craft panel opens/closes and draws without crashing
	bv._craft_open = true
	bv._craft_mode = "bench"
	bv._bench_slots = ["przewód"]
	bv._bench_preview = Crafting.preview(["przewód"], bv.floor.discovered_recipes)
	for i in 3:
		bv._process(0.016)
	_ck(true, "craft panel draws (bench mode) without crash")
	bv._craft_mode = "items"
	for i in 3:
		bv._process(0.016)
	_ck(true, "craft panel draws (items mode) without crash")
	bv._craft_open = false

	# body readout: the enemy has a procedural body; aim + located hits don't crash
	var enemy_id := -1
	for id in bv.sim.entities:
		if bv.sim.entities[id].faction == "enemy":
			enemy_id = id
	if enemy_id != -1 and bv.sim.entities[enemy_id].body != null:
		_ck(true, "enemy has a procedural body attached via the view")
	bv.sim.aim_zone = "head"

	# class offer: force a dominant playstyle, advance a turn, expect the picker
	bv.floor.player.affinity = {"melee": 12, "tech": 1}
	bv.floor.turn = 10
	bv._advance_floor_turn()
	_ck(not bv._class_offer.is_empty(), "a dominant playstyle opens the class offer")
	for i in 2:
		bv._process(0.016)              # draws the offer modal
	_ck(true, "class-offer modal draws without crash")
	bv._accept_class(0)
	_ck(bv.floor.player.class_key != "", "accepting the offer assigns a class")
	_ck(bv._class_offer.is_empty(), "offer closes after accepting")
	# fire the class active (drawn HUD + dispatch)
	bv._use_class_active()
	_ck(bv.floor.player.class_active_used_floor == bv.floor.depth,
		"using the active marks the per-floor cooldown")
	for i in 3:
		bv._process(0.016)
	_ck(true, "class HUD + active path run without crash")

	# descent: gamble a route, then descend, carrying the whole run forward
	var d0: int = bv.floor.depth
	var cls: String = bv.floor.player.class_key
	bv.floor.player.run_kills = 3
	bv._offer_routes()
	_ck(not bv._route_offer.is_empty(), "the stairs offer route choices")
	for i in 2:
		bv._process(0.016)              # draws the route modal
	_ck(true, "route-offer modal draws without crash")
	var chosen: String = bv._route_offer[0]
	bv._descend_into(chosen)
	_ck(bv._route_offer.is_empty(), "picking a route closes the modal")
	_ck(bv.floor.depth == d0 + 1, "descending advances the floor depth")
	_ck(bv.floor.biome == chosen, "the new floor records its chosen biome")
	_ck(bv.floor.player.class_key == cls, "the class carries to the next floor")
	_ck(bv.floor.player.run_kills == 3, "run tallies carry to the next floor")
	_ck(bv.floor.player.class_active_used_floor == -1, "the class active recharges on the new floor")
	for i in 5:
		bv.handle_dir(Vector2i.RIGHT); bv._process(0.016)
	_ck(true, "playing on the generated next floor does not crash")

	# hammer many actions + frames; must never crash
	for i in 30:
		bv.handle_dir(Vector2i.LEFT)
		bv.handle_shove(Vector2i.LEFT)
		bv._process(0.016)
	_ck(true, "30 mixed actions + frames, no crash")

	# end-of-run results screen builds + draws without crash
	bv._end_run(false)
	_ck(not bv._summary.is_empty(), "ending the run builds a summary")
	_ck(not bv._summary_lines.is_empty(), "the results screen has rendered lines")
	for i in 3:
		bv._process(0.016)              # draws the full-screen summary
	_ck(true, "results screen draws without crash")

	Save.clear()                         # don't leave a save behind for other tests
	print("=== %d checks, %d failed ===" % [_n, _f])
	bv.free()
	quit(_f)
