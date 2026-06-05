extends Node
## Phase 0 smoke test: confirms content JSON loads and the tag inference works.
## Replaced by the real title/board scenes in Phase 1.

func _ready() -> void:
	print("=== Dungeon Kraulem (Godot) — Phase 0 boot ===")
	print("Content bundles loaded:")
	print(Data.summary())

	# tag-inference smoke test
	var props := Tags.properties_for(["robot", "fragile"])
	print("tag inference: robot+fragile -> ", props.keys())

	# data access smoke test
	var mon: Variant = Data.group("entity_templates", "MON")
	if mon != null:
		print("entity_templates.MON: %d monsters" % (mon as Dictionary).size())

	# seeded RNG smoke test
	Rng.reseed(1234)
	print("rng roll 2d6+1: ", Rng.roll(2, 6, 1))

	print("Phase 0 scaffold OK.")
	if DisplayServer.get_name() == "headless":
		get_tree().quit.call_deferred()
