extends Node
## Loads every res://data/*.json content bundle at boot and serves it.
## Bundles are produced by tools/export_json.py from the Python content modules.

var bundles: Dictionary = {}   # "entity_templates" -> { "ENV": {...}, "MON": {...}, ... }

func _ready() -> void:
	_load_all()

func _load_all() -> void:
	var dir := DirAccess.open("res://data")
	if dir == null:
		push_error("Data: res://data not found — run tools/export_json.py")
		return
	dir.list_dir_begin()
	var fname := dir.get_next()
	while fname != "":
		if not dir.current_is_dir() and fname.ends_with(".json"):
			var key := fname.get_basename()
			var text := FileAccess.get_file_as_string("res://data/" + fname)
			var parsed: Variant = JSON.parse_string(text)
			if parsed == null:
				push_error("Data: failed to parse " + fname)
			else:
				bundles[key] = parsed
		fname = dir.get_next()
	dir.list_dir_end()

## Fetch a named group from a bundle, e.g. group("entity_templates", "MON").
func group(bundle: String, name: String) -> Variant:
	if bundles.has(bundle) and (bundles[bundle] as Dictionary).has(name):
		return bundles[bundle][name]
	return null

func summary() -> String:
	var lines: Array[String] = []
	for k in bundles.keys():
		lines.append("  %s: %d groups" % [k, (bundles[k] as Dictionary).size()])
	return "\n".join(lines)
