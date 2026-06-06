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

	# --- catalog: generated + hand-authored merge ---
	_ck(AchievementsCatalog.CATALOG.size() == 48, "generated catalog has all 48 achievements")
	_ck(Achievements.total() == AchievementsCatalog.CATALOG.size() + AchievementsExtra.EXTRA.size(),
		"total() merges generated + hand-authored catalogs")
	_ck(Achievements.order().size() == Achievements.total(), "merged display order covers every achievement")
	var def: Dictionary = AchievementsCatalog.CATALOG["wszystko_jest_surowcem"]
	_ck(def["name"] == "Wszystko jest surowcem", "Polish name ported verbatim")
	_ck(def["category"] == "salvage", "category preserved")
	_ck(AchievementsCatalog.CATALOG["sponsor_nie_pochwala"]["hidden"] == true, "hidden flag preserved")

	# --- tiers + prestige points ---
	_ck(Achievements.tier_of("aw_poziom_15") == "platinum", "hand-authored tier is read back")
	_ck(Achievements.tier_of("wszystko_jest_surowcem") in ["bronze", "silver"], "generated entries get a default tier")
	_ck(Achievements.TIER_POINTS["platinum"] == 12, "platinum is worth the most points")
	_ck(Achievements.points() == 0, "no points before anything is unlocked")

	# --- unlock / is_unlocked ---
	_ck(not Achievements.is_unlocked("pierwsza_krew"), "nothing unlocked at the start")
	var d := Achievements.unlock("pierwsza_krew")
	_ck(not d.is_empty() and d["name"] != "" and d["key"] == "pierwsza_krew",
		"a NEW unlock returns the def (for a toast)")
	_ck(Achievements.is_unlocked("pierwsza_krew"), "the achievement is now unlocked")
	_ck(Achievements.unlock("pierwsza_krew").is_empty(), "re-unlocking returns empty (no double toast)")
	_ck(Achievements.unlock("nie_ma_takiego").is_empty(), "an unknown key returns empty, no crash")
	_ck(Achievements.count_unlocked() == 1, "count tracks unlocked achievements")

	# --- lifetime progress goals ---
	_ck(Achievements.progress("kill_10") == [0, 10], "a progress achievement starts at 0/goal")
	_ck(Achievements.bump("kills", 9).is_empty(), "below the goal, bump unlocks nothing")
	_ck(Achievements.stat("kills") == 9, "lifetime counter accumulates")
	_ck(Achievements.progress("kill_10") == [9, 10], "progress reflects the counter")
	var crossed := Achievements.bump("kills", 5)   # 9 + 5 = 14 >= 10
	_ck(crossed.size() == 1 and crossed[0]["key"] == "kill_10", "hitting the goal auto-unlocks + returns the def")
	_ck(Achievements.is_unlocked("kill_10"), "the goal achievement is now unlocked")
	_ck(Achievements.progress("kill_10") == [10, 10], "progress caps at the goal once earned")
	_ck(Achievements.points() >= Achievements.TIER_POINTS[Achievements.tier_of("kill_10")],
		"unlocking adds its tier's points to the prestige score")

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
