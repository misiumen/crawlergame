class_name Achievements
extends RefCounted
## Persistent achievement unlocks — a DCC staple (a big list to chase, with snarky
## flavor). Catalog lives in AchievementsCatalog; unlocked keys persist to
## user://achievements.json across runs. Unlocking returns the def so the UI can
## pop a Vampire-Survivors-style toast.

const SAVE_PATH := "user://achievements.json"

static var _unlocked: Dictionary = {}   # key -> true (in-process cache)
static var _loaded := false

static func _ensure() -> void:
	if _loaded:
		return
	_loaded = true
	if FileAccess.file_exists(SAVE_PATH):
		var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
		if f != null:
			var parsed: Variant = JSON.parse_string(f.get_as_text())
			if parsed is Array:
				for k in parsed:
					_unlocked[k] = true

static func _save() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(_unlocked.keys()))

static func is_unlocked(key: String) -> bool:
	_ensure()
	return _unlocked.has(key)

## Unlock `key`. Returns the achievement def {key,name,desc,category,hidden} if it
## was NEWLY unlocked (so the caller can toast it), or {} if unknown / already had.
static func unlock(key: String) -> Dictionary:
	_ensure()
	if not AchievementsCatalog.CATALOG.has(key) or _unlocked.has(key):
		return {}
	_unlocked[key] = true
	_save()
	var d: Dictionary = (AchievementsCatalog.CATALOG[key] as Dictionary).duplicate()
	d["key"] = key
	return d

static func count_unlocked() -> int:
	_ensure()
	var n := 0
	for k in _unlocked:
		if AchievementsCatalog.CATALOG.has(k):
			n += 1
	return n

static func total() -> int:
	return AchievementsCatalog.CATALOG.size()

static func has_any() -> bool:
	_ensure()
	return not _unlocked.is_empty()

## Reset everything (test helper / "wipe achievements").
static func reset() -> void:
	_unlocked.clear()
	_loaded = true
	if FileAccess.file_exists(SAVE_PATH):
		DirAccess.remove_absolute(SAVE_PATH)
