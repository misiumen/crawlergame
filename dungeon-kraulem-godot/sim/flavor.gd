class_name Flavor
extends RefCounted
## Thin flavor-content layer: surfaces two Polish content bundles that otherwise
## shipped unused — failure_templates (procedural craft-failure lines) and
## celebrities (named star cameos). These are pure flavor (no new material/economy
## vocabulary), so they wire cleanly into the existing systems.

static func _data(bundle: String, name: String) -> Variant:
	var loop := Engine.get_main_loop()
	if not (loop is SceneTree):
		return null
	var dn = (loop as SceneTree).root.get_node_or_null("Data")
	if dn == null or not dn.has_method("group"):
		return null
	return dn.call("group", bundle, name)

## A procedural failure line for a craft outcome level ("partial" / "failure" /
## "critical_failure"), or "" if none. Pulled from failure_templates.json.
static func fail_line(level: String, rng: RandomNumberGenerator) -> String:
	var raw: Variant = _data("failure_templates", "FAIL_TEMPLATES")
	if not (raw is Array):
		return ""
	var pool: Array = []
	for t in raw:
		if t is Dictionary and t.get("level", "") == level and not t.has("requires"):
			pool.append(t.get("text", ""))
	if pool.is_empty():
		return ""
	return pool[rng.randi_range(0, pool.size() - 1)]

## A celebrity valid for this depth: {name, intro}, or {} if none. From celebrities.json.
static func celebrity_for(depth: int, rng: RandomNumberGenerator) -> Dictionary:
	var raw: Variant = _data("celebrities", "CELEBRITIES")
	if not (raw is Dictionary):
		return {}
	var pool: Array = []
	for k in raw:
		var c: Dictionary = raw[k]
		if depth >= int(c.get("floor_min", 1)) and depth <= int(c.get("floor_max", 99)):
			pool.append(c)
	if pool.is_empty():
		return {}
	var pick: Dictionary = pool[rng.randi_range(0, pool.size() - 1)]
	return {"name": pick.get("fallback_name", "?"), "intro": pick.get("fallback_intro", "")}
