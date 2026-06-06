class_name Achievements
extends RefCounted
## Persistent achievement unlocks — a DCC staple (a huge list to chase, with
## snarky flavor). Two catalogs feed in: AchievementsCatalog (generated from the
## pygame source) and AchievementsExtra (hand-authored Godot-only, tiered, some
## with lifetime progress goals). Both unlocked keys AND lifetime counters persist
## to user://achievements.json. Unlocking returns the def so the UI can pop a
## Vampire-Survivors-style toast.

const SAVE_PATH := "user://achievements.json"

## Tier → prestige point value (a Vampire-Survivors-ish "achievement score").
const TIER_POINTS := {"bronze": 1, "silver": 3, "gold": 6, "platinum": 12}

static var _unlocked: Dictionary = {}   # key -> true (in-process cache)
static var _stats: Dictionary = {}      # lifetime counter -> int
static var _loaded := false
static var _merged: Dictionary = {}     # cached merged catalog
static var _order: Array = []           # cached merged display order

# ── Merged catalog (generated + hand-authored) ────────────────────────────────

static func catalog() -> Dictionary:
	if _merged.is_empty():
		for k in AchievementsCatalog.CATALOG:
			_merged[k] = AchievementsCatalog.CATALOG[k]
		for k in AchievementsExtra.EXTRA:
			_merged[k] = AchievementsExtra.EXTRA[k]
	return _merged

static func order() -> Array:
	if _order.is_empty():
		_order = AchievementsCatalog.ORDER + AchievementsExtra.EXTRA_ORDER
	return _order

static func def_of(key: String) -> Dictionary:
	var c := catalog()
	return c.get(key, {})

## A tier for every achievement: explicit on hand-authored ones, derived for the
## generated set (hidden ones read as the rarer "silver", the rest "bronze").
static func tier_of(key: String) -> String:
	var d := def_of(key)
	if d.has("tier"):
		return d["tier"]
	return "silver" if d.get("hidden", false) else "bronze"

# ── Persistence ───────────────────────────────────────────────────────────────

static func _ensure() -> void:
	if _loaded:
		return
	_loaded = true
	if FileAccess.file_exists(SAVE_PATH):
		var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
		if f != null:
			var parsed: Variant = JSON.parse_string(f.get_as_text())
			if parsed is Array:                       # legacy format: a bare key list
				for k in parsed:
					_unlocked[k] = true
			elif parsed is Dictionary:
				for k in parsed.get("unlocked", []):
					_unlocked[k] = true
				var st: Variant = parsed.get("stats", {})
				if st is Dictionary:
					for k in st:
						_stats[k] = int(st[k])

static func _save() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"unlocked": _unlocked.keys(), "stats": _stats}))

# ── Unlock / query ────────────────────────────────────────────────────────────

static func is_unlocked(key: String) -> bool:
	_ensure()
	return _unlocked.has(key)

## Unlock `key`. Returns the def {key,name,desc,category,hidden,tier} if it was
## NEWLY unlocked (so the caller can toast it), or {} if unknown / already had.
static func unlock(key: String) -> Dictionary:
	_ensure()
	if not catalog().has(key) or _unlocked.has(key):
		return {}
	_unlocked[key] = true
	_save()
	var d: Dictionary = (catalog()[key] as Dictionary).duplicate()
	d["key"] = key
	d["tier"] = tier_of(key)
	return d

# ── Lifetime progress counters ────────────────────────────────────────────────

## Add `amount` to a lifetime counter and auto-unlock any progress achievement
## whose goal it just reached. Returns the list of newly-unlocked defs (toast 'em).
static func bump(stat_key: String, amount: int = 1) -> Array:
	_ensure()
	if amount == 0:
		return []
	_stats[stat_key] = int(_stats.get(stat_key, 0)) + amount
	var fresh: Array = []
	for key in catalog():
		var d: Dictionary = catalog()[key]
		if d.get("stat", "") == stat_key and not _unlocked.has(key):
			if int(_stats[stat_key]) >= int(d.get("goal", 1 << 30)):
				var got := unlock(key)
				if not got.is_empty():
					fresh.append(got)
	_save()
	return fresh

static func stat(stat_key: String) -> int:
	_ensure()
	return int(_stats.get(stat_key, 0))

## For a progress achievement, [current, goal] (current capped at goal); else [].
static func progress(key: String) -> Array:
	var d := def_of(key)
	if not d.has("stat"):
		return []
	var goal := int(d.get("goal", 0))
	return [mini(stat(d["stat"]), goal), goal]

# ── Aggregates ────────────────────────────────────────────────────────────────

static func count_unlocked() -> int:
	_ensure()
	var n := 0
	for k in _unlocked:
		if catalog().has(k):
			n += 1
	return n

static func total() -> int:
	return catalog().size()

## Prestige score: sum of tier points across everything unlocked.
static func points() -> int:
	_ensure()
	var p := 0
	for k in _unlocked:
		if catalog().has(k):
			p += int(TIER_POINTS.get(tier_of(k), 1))
	return p

static func points_total() -> int:
	var p := 0
	for k in catalog():
		p += int(TIER_POINTS.get(tier_of(k), 1))
	return p

static func has_any() -> bool:
	_ensure()
	return not _unlocked.is_empty()

## Reset everything (test helper / "wipe achievements").
static func reset() -> void:
	_unlocked.clear()
	_stats.clear()
	_loaded = true
	if FileAccess.file_exists(SAVE_PATH):
		DirAccess.remove_absolute(SAVE_PATH)
