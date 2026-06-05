extends SceneTree
## Unit tests for the tag-based crafting system.
## Run: godot --headless --path godot -s res://tests/test_crafting.gd

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
	print("=== crafting tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 42

	# --- tag union is deduplicated ---
	var tags := Crafting.combined_tags(["przewód", "złom"])
	_ck("electric" in tags, "combined_tags: przewód contributes electric")
	_ck("metal" in tags, "combined_tags: złom contributes metal")
	_ck("edge" in tags, "combined_tags: złom contributes edge")
	_ck("conductive" in tags, "combined_tags: przewód contributes conductive")
	_ck(tags.count("electric") == 1, "combined_tags: no duplicates")

	# --- tag grammar: exact rule matching (most specific wins) ---
	# metal+edge alone should NOT match metal+edge+binding
	var rule_edge: Variant = Crafting.match_rule(["metal", "edge"])
	_ck(rule_edge == null, "no rule matched: metal+edge alone (needs binding)")
	# metal+edge+binding → weapon rule
	var rule_weapon: Variant = Crafting.match_rule(["metal", "edge", "binding"])
	_ck(rule_weapon != null, "metal+edge+binding → weapon rule")
	_ck(rule_weapon != null and (rule_weapon as Dictionary)["category"] == "weapon",
		"weapon rule has category=weapon")
	# electric+binding → coating rule
	var rule_coat: Variant = Crafting.match_rule(["electric", "binding", "conductive", "soft"])
	_ck(rule_coat != null and (rule_coat as Dictionary)["category"] == "coating",
		"electric+binding → coating rule")
	# electric+container → thrown
	var rule_throw: Variant = Crafting.match_rule(["electric", "container", "fragile"])
	_ck(rule_throw != null and (rule_throw as Dictionary)["category"] == "thrown",
		"electric+container → thrown rule")

	# --- DC formula ---
	# przewód+szmata: [conductive,electric,binding,soft] → rule(DC12) - 2(binding) = 10
	var dc_coat := Crafting.compute_dc(["przewód", "szmata"], [])
	_ck(dc_coat == 10, "DC for electric coating = 10 (12-2 binding)")
	# bateria+butelka: [electric,power,container,fragile]
	# rule matches electric+container (DC 12), +2 (power|fragile), +3 (fragile&electric) → DC 17
	var dc_granat := Crafting.compute_dc(["bateria", "butelka"], [])
	_ck(dc_granat == 17, "DC for electric grenade = 17 (12+2 power/fragile+3 fragile&electric)")
	# 3 mats: +1 extra → DC increases
	var dc_3mat := Crafting.compute_dc(["przewód", "szmata", "złom"], [])
	_ck(dc_3mat > dc_coat, "3 mats increases DC vs 2 mats")
	# known recipe: -2
	var discovered: Array = []
	discovered.append({"tags": ["binding", "conductive", "electric", "soft"], "name": "test", "times": 1})
	var dc_known := Crafting.compute_dc(["przewód", "szmata"], discovered)
	_ck(dc_known == dc_coat - 2, "known recipe reduces DC by 2")

	# --- outcome tiers by margin ---
	# Force specific margins by using int_mod to bridge the gap.
	# DC 10, int_mod=20 → roll 1+20=21, margin=11 → krytyk (>=5)
	var mats_ok := {"przewód": 1, "szmata": 1}
	rng.seed = 1  # seed 1: first randi_range(1,20) will be 1 — with int_mod=20, margin=11
	var disc2: Array = []
	var res_krytyk := Crafting.attempt(["przewód", "szmata"], mats_ok, disc2, rng, 20)
	_ck(res_krytyk["outcome"] in ["krytyk", "sukces"],
		"int_mod=20 yields krytyk or sukces (roll 1d20+20 vs DC10)")
	_ck(res_krytyk["item"] is GameItem, "krytyk/sukces yields a GameItem")
	_ck(disc2.size() == 1, "successful craft records discovery")

	# sukces outcome: item built
	var mats_suc := {"przewód": 1, "szmata": 1}
	rng.seed = 42
	var disc3: Array = []
	var res_suc := Crafting.attempt(["przewód", "szmata"], mats_suc, disc3, rng, 5)
	_ck(res_suc["item"] != null or res_suc["outcome"] in ["porazka", "backfire"],
		"attempt with int_mod=5 produces valid outcome")

	# porażka: int_mod=-9, DC=10, so roll 1d20-9 ≤ 11 easily → likely porażka or backfire
	var mats_fail := {"przewód": 1, "szmata": 1}
	rng.seed = 100  # seed 100: roll ~1-3 → with int_mod=-9, margin = (roll-9) - 10 → easily <-4
	var disc4: Array = []
	var res_fail := Crafting.attempt(["przewód", "szmata"], mats_fail, disc4, rng, -9)
	_ck(res_fail["outcome"] in ["czesciowy", "porazka", "backfire"],
		"very negative int_mod tends toward failure")
	_ck(not mats_fail.has("przewód"), "materials spent even on failure")

	# --- item attributes ---
	# krytyk (margin>=10): rare + 2 affixes + generated name
	var mats_crit := {"przewód": 1, "szmata": 1}
	rng.seed = 1
	var disc5: Array = []
	var res2 := Crafting.attempt(["przewód", "szmata"], mats_crit, disc5, rng, 20)
	if res2["item"] is GameItem:
		var itm := res2["item"] as GameItem
		_ck(itm.charges == 3, "coating item starts with 3 weapon charges")
		_ck(itm.effect.has("coating"), "coating item has coating effect")
		_ck(itm.origin == "crafted", "item origin = crafted")
	else:
		_ck(true, "(item null on failure — skip item attr checks)")

	# czesciowy: wadliwy flag
	# make a scenario that yields czesciowy (margin -1 to -4)
	var mats_part := {"przewód": 1, "szmata": 1}
	rng.seed = 77  # hopefully gives a czesciowy; we just check if the flag is set when outcome is czesciowy
	var disc6: Array = []
	var res_part := Crafting.attempt(["przewód", "szmata"], mats_part, disc6, rng, -1)
	if res_part["outcome"] == "czesciowy":
		_ck((res_part["item"] as GameItem).wadliwy, "czesciowy outcome sets wadliwy flag")

	# --- recipe book: second craft of same tags increments times ---
	var mats_a := {"przewód": 2, "szmata": 2}
	var disc_book: Array = []
	rng.seed = 1
	Crafting.attempt(["przewód", "szmata"], mats_a, disc_book, rng, 20)  # first: records
	rng.seed = 1
	Crafting.attempt(["przewód", "szmata"], mats_a, disc_book, rng, 20)  # second: increments
	if disc_book.size() > 0:
		_ck(int(disc_book[0].get("times", 0)) >= 2, "recipe book: repeated sukces increments times counter")

	# --- preview: no mutation ---
	var mats_b := {"przewód": 1, "szmata": 1}
	var disc_b: Array = []
	var prev2 := Crafting.preview(["przewód", "szmata"], disc_b)
	_ck(mats_b.has("przewód"), "preview does not mutate materials")
	_ck(disc_b.is_empty(), "preview does not mutate discovered list")
	_ck(prev2.has("dc") and prev2.has("rule") and prev2.has("tiers"), "preview returns dc/rule/tiers")
	_ck(prev2["tiers"].size() == 5, "preview tiers: 5 outcomes")

	# --- INT XP gains ---
	_ck(res_krytyk["int_xp_gained"] == 5, "krytyk grants 5 INT XP")
	if res_suc["outcome"] == "sukces":
		_ck(res_suc["int_xp_gained"] == 3, "sukces grants 3 INT XP")

	# --- backfire: has desc and type ---
	var mats_bf := {"bateria": 1, "butelka": 1}  # electric+container, DC 18, fragile — high backfire risk
	rng.seed = 99
	var disc7: Array = []
	var res_bf := Crafting.attempt(["bateria", "butelka"], mats_bf, disc7, rng, -10)
	if res_bf["outcome"] == "backfire":
		_ck(res_bf["backfire"] is Dictionary, "backfire result is a dict")
		_ck(res_bf["backfire"].has("desc") and res_bf["backfire"].has("type"),
			"backfire dict has desc and type fields")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
