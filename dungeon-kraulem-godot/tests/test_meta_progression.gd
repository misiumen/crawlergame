extends SceneTree
## Meta-progression: prestige purchases, loadout selection, ownership, effects,
## and biome registration into the route pool.
## Run: godot --headless --path . -s res://tests/test_meta_progression.gd

var _f := 0
var _n := 0
func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c: _f += 1

func _initialize() -> void:
	print("=== meta-progression tests ===")
	MetaCatalog.reset()
	Achievements.reset()

	# --- defaults are owned for free; paid entries are not ---
	_ck(MetaCatalog.is_owned("species_bezimienny"), "the default species is always owned")
	_ck(MetaCatalog.is_owned("origin_debiutant"), "the default origin is always owned")
	_ck(not MetaCatalog.is_owned("species_pamietajacy"), "a paid species is locked until bought")
	_ck(MetaCatalog.cost_of("species_pamietajacy") == 45, "species cost reads through")
	_ck(MetaCatalog.kind_of("species_pamietajacy") == "species", "kind reads through")
	_ck(MetaCatalog.keys_of_kind("biome").size() == 9, "all nine biomes are catalogued")

	# --- prestige economy ---
	_ck(MetaCatalog.available_prestige() == 0, "no prestige before any achievements")
	_ck(not MetaCatalog.try_purchase("species_pamietajacy"), "cannot buy while broke")
	for k in ["kill_250", "aw_poziom_20", "win_pacifist", "win_lowlevel"]:   # 4 platinums = 48 pts
		Achievements.unlock(k)
	_ck(Achievements.points() == 48, "platinum unlocks bank prestige points")
	_ck(MetaCatalog.available_prestige() == 48, "available prestige = points − spent")
	_ck(MetaCatalog.try_purchase("species_pamietajacy"), "afford → purchase succeeds")
	_ck(MetaCatalog.is_owned("species_pamietajacy"), "the purchase is now owned")
	_ck(MetaCatalog.available_prestige() == 3, "buying spends the cost (48 − 45)")
	_ck(not MetaCatalog.try_purchase("species_pamietajacy"), "no double-buying")
	_ck(not MetaCatalog.try_purchase("perk_lyzka_cudu"), "cannot afford a 26-pt perk with 3 left")

	# --- loadout selection only accepts owned entries ---
	MetaCatalog.set_species("species_pamietajacy")
	_ck(MetaCatalog.loadout()["species"] == "species_pamietajacy", "selecting an owned species sticks")
	MetaCatalog.set_species("species_grzybica")        # not owned
	_ck(MetaCatalog.loadout()["species"] == "species_pamietajacy", "selecting an UNowned species is ignored")

	# --- active effects feed the run ---
	var effects := MetaCatalog.active_effects()
	var has_species := false
	var has_default_origin := false
	for e in effects:
		if e["key"] == "species_pamietajacy" and int((e["effect"] as Dictionary).get("stats", {}).get("INT", 0)) == 1:
			has_species = true
		if e["key"] == "origin_debiutant":
			has_default_origin = true
	_ck(has_species, "the chosen species' effect is in the active set")
	_ck(has_default_origin, "the default origin is always active")

	# --- biomes register into the route pool ---
	Routes.clear_extra()
	_ck(not Routes.all_biomes().has("biome_test"), "route pool starts with only built-ins")
	Routes.register("biome_test", {"label": "Test", "blurb": "x", "enemy_mul": 1.0})
	_ck(Routes.all_biomes().has("biome_test"), "a registered biome joins the pool")
	_ck(Routes.label_of("biome_test") == "Test", "registered biome label resolves")
	_ck(Routes.mods_for("biome_test")["biome_key"] == "biome_test", "registered biome yields mods")
	Routes.clear_extra()
	_ck(not Routes.all_biomes().has("biome_test"), "clearing drops meta biomes")

	# --- persistence + reset ---
	_ck(FileAccess.file_exists(MetaCatalog.SAVE_PATH), "purchases persist to disk")
	MetaCatalog.reset()
	_ck(not MetaCatalog.is_owned("species_pamietajacy"), "reset wipes purchases")
	_ck(not FileAccess.file_exists(MetaCatalog.SAVE_PATH), "reset removes the file")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
