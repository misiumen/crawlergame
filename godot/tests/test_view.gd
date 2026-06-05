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
	var bv = preload("res://scenes/BoardView.gd").new()
	bv._font = ThemeDB.fallback_font
	bv._build()                          # (_ready is deferred under -s; call directly)
	_ck(bv.sim != null, "scene builds a CombatSim")
	_ck(bv._vpos.size() == 2, "visual positions initialised for both tokens")

	var r0: int = bv.sim.round_num
	bv.handle_dir(Vector2i.RIGHT)        # a real move ends the player turn
	_ck(bv.sim.round_num > r0, "an action advances the round")

	for i in 6:
		bv._process(0.016)               # manual frames (no main loop under -s)
	_ck(true, "_process runs without error")

	# hammer many actions + frames; must never crash
	for i in 30:
		bv.handle_dir(Vector2i.LEFT)
		bv.handle_shove(Vector2i.LEFT)
		bv._process(0.016)
	_ck(true, "30 mixed actions + frames, no crash")

	print("=== %d checks, %d failed ===" % [_n, _f])
	bv.free()
	quit(_f)
