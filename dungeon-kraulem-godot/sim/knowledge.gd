class_name Knowledge
extends RefCounted
## Clues, rumors + facts — ported from pygame systems/knowledge.py + the
## clue/rumor template content. A lightweight, browsable intel log: the bulletin
## board, rival crawlers and salvage feed it; the journal ([J]) shows each entry
## with a reliability read (DCC rumors are often half-true — that's the point).
##
## A journal entry is a plain dict: {key, text, kind, truth, source}.

static func _data(bundle: String, name: String) -> Variant:
	var loop := Engine.get_main_loop()
	if not (loop is SceneTree):
		return null
	var data_node := (loop as SceneTree).root.get_node_or_null("Data")
	if data_node == null or not data_node.has_method("group"):
		return null
	return data_node.call("group", bundle, name)

## A random rumor from any category: {key, text, kind:"rumor", truth, source}.
static func random_rumor(rng: RandomNumberGenerator) -> Dictionary:
	var raw: Variant = _data("rumor_templates", "RUMOR_TEMPLATES")
	if not (raw is Dictionary):
		return {}
	var pool: Array = []
	for cat in raw:
		var lst: Variant = raw[cat]
		if lst is Array:
			pool.append_array(lst)
	if pool.is_empty():
		return {}
	var r: Dictionary = pool[rng.randi_range(0, pool.size() - 1)]
	return {"key": r.get("key", ""), "text": r.get("text", ""), "kind": "rumor",
		"truth": float(r.get("truth", 0.5)), "source": "plotka"}

## A random clue (found on the floor): {key, text, kind:"clue", truth, source}.
static func random_clue(rng: RandomNumberGenerator) -> Dictionary:
	var raw: Variant = _data("clue_templates", "CLUE_TEMPLATES")
	if not (raw is Dictionary) or (raw as Dictionary).is_empty():
		return {}
	var keys: Array = (raw as Dictionary).keys()
	var k: String = keys[rng.randi_range(0, keys.size() - 1)]
	var c: Dictionary = raw[k]
	return {"key": k, "text": c.get("text", ""), "kind": "clue",
		"truth": 0.9, "source": c.get("source", "ślad")}

## How much to trust an entry, as a Polish label + a color hint key.
static func reliability_label(truth: float) -> String:
	if truth >= 0.8:
		return "wiarygodne"
	if truth >= 0.5:
		return "niepewne"
	return "plotka"
