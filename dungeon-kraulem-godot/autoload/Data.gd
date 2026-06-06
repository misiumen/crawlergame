extends Node
## Loads every res://data/*.json content bundle at boot and serves it.
## Bundles are produced by tools/export_json.py from the Python content modules.

var bundles: Dictionary = {}   # "entity_templates" -> { "ENV": {...}, "MON": {...}, ... }
var _loaded := false

func _ready() -> void:
	_load_all()

## Explicit manifest of bundles. DirAccess enumeration of res:// returns nothing
## in headless mode (only direct FileAccess by path works), so we can't rely on
## listing — this known set loads in the editor, the exe AND headless.
const MANIFEST := [
	"body_plans", "celebrities", "clue_templates", "encounter_templates",
	"entity_templates", "experimental_recipes", "failure_templates", "floor_archetypes",
	"floor_objective_templates", "item_templates", "memetic_templates", "monster_salvage",
	"npc_templates", "pets", "recipe_templates", "room_pool", "rumor_templates",
	"safehouse_templates", "salvage_tables", "sponsor_voice_lines", "sponsors",
]

func _load_one(key: String) -> void:
	var path := "res://data/" + key + ".json"
	if not FileAccess.file_exists(path):
		return
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if parsed == null:
		push_error("Data: failed to parse " + key + ".json")
	else:
		bundles[key] = parsed

func _load_all() -> void:
	if _loaded:
		return
	_loaded = true
	# Prefer DirAccess (auto-picks up any new bundles in the editor)...
	var dir := DirAccess.open("res://data")
	if dir != null:
		dir.list_dir_begin()
		var fname := dir.get_next()
		while fname != "":
			if not dir.current_is_dir() and fname.ends_with(".json"):
				_load_one(fname.get_basename())
			fname = dir.get_next()
		dir.list_dir_end()
	# ...but if enumeration found nothing (headless), fall back to the manifest.
	if bundles.is_empty():
		for key in MANIFEST:
			_load_one(key)

## Fetch a named group from a bundle, e.g. group("entity_templates", "MON").
func group(bundle: String, name: String) -> Variant:
	if not _loaded:
		_load_all()   # lazy init: _ready() doesn't fire for autoloads under -s tests
	if bundles.has(bundle) and (bundles[bundle] as Dictionary).has(name):
		return bundles[bundle][name]
	return null

func summary() -> String:
	var lines: Array[String] = []
	for k in bundles.keys():
		lines.append("  %s: %d groups" % [k, (bundles[k] as Dictionary).size()])
	return "\n".join(lines)
