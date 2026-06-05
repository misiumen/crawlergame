extends SceneTree
## Achievement system tests. Run:
## godot --headless --path . -s res://tests/test_achievements.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _initialize() -> void:
	print("=== achievements tests ===")
	Achievements.reset()

	# --- catalog ---
	_ck(AchievementsCatalog.CATALOG.size() == 48, "catalog has all 48 achievements")
	_ck(Achievements.total() == 48, "total() reports 48")
	_ck(AchievementsCatalog.ORDER.size() == 48, "stable display order covers them all")
	var def: Dictionary = AchievementsCatalog.CATALOG["wszystko_jest_surowcem"]
	_ck(def["name"] == "Wszystko jest surowcem", "Polish name ported verbatim")
	_ck(def["category"] == "salvage", "category preserved")
	_ck(AchievementsCatalog.CATALOG["sponsor_nie_pochwala"]["hidden"] == true, "hidden flag preserved")

	# --- unlock / is_unlocked ---
	_ck(not Achievements.is_unlocked("pierwsza_krew"), "nothing unlocked at the start")
	var d := Achievements.unlock("pierwsza_krew")
	_ck(not d.is_empty() and d["name"] != "" and d["key"] == "pierwsza_krew",
		"a NEW unlock returns the def (for a toast)")
	_ck(Achievements.is_unlocked("pierwsza_krew"), "the achievement is now unlocked")
	_ck(Achievements.unlock("pierwsza_krew").is_empty(), "re-unlocking returns empty (no double toast)")
	_ck(Achievements.unlock("nie_ma_takiego").is_empty(), "an unknown key returns empty, no crash")
	_ck(Achievements.count_unlocked() == 1, "count tracks unlocked achievements")

	# --- persistence to disk ---
	_ck(FileAccess.file_exists(Achievements.SAVE_PATH), "unlocking persists to user://achievements.json")
	var txt := FileAccess.get_file_as_string(Achievements.SAVE_PATH)   # opens+closes, no lingering handle
	_ck(txt.contains("pierwsza_krew"), "the unlocked key is written to disk")

	# --- reset wipes everything ---
	Achievements.reset()
	_ck(not Achievements.is_unlocked("pierwsza_krew"), "reset() clears unlocks")
	_ck(Achievements.count_unlocked() == 0, "reset() zeroes the count")
	_ck(not FileAccess.file_exists(Achievements.SAVE_PATH), "reset() removes the save file")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
