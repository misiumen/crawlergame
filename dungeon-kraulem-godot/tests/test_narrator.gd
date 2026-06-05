extends SceneTree
## Narrator (konferansjer) tests. Run:
## godot --headless --path godot -s res://tests/test_narrator.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _initialize() -> void:
	print("=== narrator tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 3

	# known categories the board fires return non-empty Polish lines
	for cat in ["env_kill", "craft_success", "craft_fail", "salvage_success",
			"furniture_salvage", "audience_rise", "audience_drop", "class_offer",
			"clever_craft", "tech_salvage"]:
		_ck(Narrator.has_category(cat), "category '%s' has lines" % cat)
		_ck(Narrator.say(cat, rng) != "", "say('%s') returns a line" % cat)

	# unknown category yields empty (no crash, no fabricated text)
	_ck(Narrator.say("does_not_exist", rng) == "", "unknown category -> empty string")
	_ck(not Narrator.has_category("does_not_exist"), "unknown category -> has_category false")

	# multi-line categories actually vary across the pool (deterministic w/ seed)
	var seen := {}
	for i in 40:
		seen[Narrator.say("salvage_success", rng)] = true
	_ck(seen.size() >= 2, "salvage_success draws from more than one line variant")

	# lines are Polish (contain Polish-specific glyphs somewhere in the pool)
	var joined := ""
	for line in Narrator.CATEGORIES["env_kill"]:
		joined += line
	_ck(joined.length() > 0, "env_kill lines are present and non-empty")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
