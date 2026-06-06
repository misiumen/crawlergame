class_name Memetics
extends RefCounted
## Belief seeds — ported (bounded) from systems/memetics.py. You PLANT a meme into
## the show; it PROPAGATES through stages over the run (seeded → spreading →
## institutionalized → backlash → burned-out), applying an ongoing effect while it
## lives and a downside when it sours. Faithful to the core loop; method flavor
## follows memetic_templates.json. Potency comes from a CHA/INT/WIS check at plant.
##
## A seed is a plain dict: {method, label, age, potency, backlashed}.

const STAGES := ["seeded", "spreading", "institutionalized", "backlash", "burned_out"]

## Plantable methods (a curated subset). effect drives the per-tick mechanic.
const METHODS := [
	{"key": "plotka",     "label": "Plotka", "stat": "CHA",
		"desc": "Powoli rośnie — widownia podchwytuje narrację (+widownia/tik)."},
	{"key": "propaganda", "label": "Propaganda", "stat": "INT",
		"desc": "Demoralizuje wrogów — gdy się zakorzeni, wahają się w walce."},
	{"key": "klamstwo",   "label": "Kłamstwo", "stat": "CHA",
		"desc": "Natychmiastowy rozgłos, ale szybki backlash — przyłapią cię."},
	{"key": "kult",       "label": "Rama religijna", "stat": "WIS",
		"desc": "Wolno, ale przy zakorzenieniu kult przysyła daninę (skrzynka)."},
	{"key": "tabu",       "label": "Tabu", "stat": "WIS",
		"desc": "Przesuwa uwagę sponsorów, gdy wejdzie do obiegu."},
]

static func method_def(key: String) -> Dictionary:
	for m in METHODS:
		if m["key"] == key:
			return m
	return {}

## Stage from age (in propagation ticks).
static func stage_for(age: int) -> String:
	if age <= 1: return "seeded"
	if age <= 4: return "spreading"
	if age <= 7: return "institutionalized"
	if age == 8: return "backlash"
	return "burned_out"

## Plant a seed: a CHA/INT/WIS check sets its potency (1–4). Returns the seed.
static func plant(method_key: String, p, rng: RandomNumberGenerator) -> Dictionary:
	var m := method_def(method_key)
	var roll: int = rng.randi_range(1, 20) + int(p.stat_mod(m.get("stat", "CHA")))
	var potency: int = clampi((roll - 6) / 4, 1, 4)
	return {"method": method_key, "label": m.get("label", method_key),
		"age": 0, "potency": potency, "backlashed": false}
