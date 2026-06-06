class_name Crawlers
extends RefCounted
## Rival contestants — other crawlers on the show, ported from pygame
## systems/crawlers.py + the CRAWLER_ARCHETYPES content. They roam a floor as
## neutral NPCs you can TALK to (audience/relationship), ROB (a DEX gamble — win
## and they flee minus their scrap, lose and they turn hostile), or just leave.
## A provoked crawler becomes a real enemy on the board.

const FIRST := ["Arek", "Voss", "Kael", "Mira", "Toran", "Lyss", "Daven", "Sable", "Renn", "Kira"]
const LAST := ["Vance", "Thresh", "Cole", "Maren", "Tyde", "Crane", "Solis", "Vex", "Korda", "Brak"]

## Archetype catalog from data/npc_templates.json (via the Data autoload).
static func _archetypes() -> Dictionary:
	var loop := Engine.get_main_loop()
	if not (loop is SceneTree):
		return {}
	var data_node := (loop as SceneTree).root.get_node_or_null("Data")
	if data_node == null or not data_node.has_method("group"):
		return {}
	var raw: Variant = data_node.call("group", "npc_templates", "CRAWLER_ARCHETYPES")
	return raw if raw is Dictionary else {}

## Build a crawler descriptor for a floor. Deterministic from the given rng.
## Returns {name, archetype, personality, disposition, carried{mat:qty}}.
static func make(depth: int, rng: RandomNumberGenerator) -> Dictionary:
	var arch := _archetypes()
	var akey := ""
	var personality := "professional"
	if not arch.is_empty():
		var keys: Array = arch.keys()
		akey = keys[rng.randi_range(0, keys.size() - 1)]
		var a: Dictionary = arch[akey]
		personality = a.get("personality", personality)
		var pool: Variant = a.get("fallback_name_pool", [])
		if pool is Array and not (pool as Array).is_empty():
			var nm: String = pool[rng.randi_range(0, (pool as Array).size() - 1)]
			return _finish({"name": nm, "archetype": akey, "personality": personality}, depth, rng)
	var name := "%s %s" % [FIRST[rng.randi_range(0, FIRST.size() - 1)], LAST[rng.randi_range(0, LAST.size() - 1)]]
	return _finish({"name": name, "archetype": akey, "personality": personality}, depth, rng)

static func _finish(d: Dictionary, depth: int, rng: RandomNumberGenerator) -> Dictionary:
	# Disposition skews more hostile the deeper you are.
	var roll := rng.randi_range(0, 99)
	var hostile_chance := 15 + depth * 6
	d["disposition"] = "hostile" if roll < hostile_chance else "neutral"
	# What they're carrying (you can rob it).
	var mats := ["złom", "przewód", "szmata", "bateria", "plastik"]
	d["carried"] = {
		"złom": rng.randi_range(2, 4 + depth),
		mats[rng.randi_range(1, mats.size() - 1)]: rng.randi_range(1, 2),
	}
	return d

## Combat stats for a crawler that turns hostile, scaled by depth.
static func combat_stats(depth: int) -> Dictionary:
	return {"hp": 14 + depth * 4, "ac": 12, "to_hit": 3, "dice": "1d6+%d" % (1 + depth / 2)}
