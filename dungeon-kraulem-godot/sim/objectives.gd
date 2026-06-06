class_name Objectives
extends RefCounted
## Per-floor side-goal (ported concept from pygame floor_objective_templates): each
## floor rolls ONE tracked objective tied to a behaviour the player already does.
## Hitting the target pays out audience + XP (the show rewards a good segment).
## Unlike the old inert "Cel:" hint, this has real progress + a completion payoff.
##
## An objective instance is a plain dict: {key, label, target, progress, done,
## reward_audience, reward_xp}. Tracking + payout live in BoardView.

const DEFS: Array = [
	{"key": "salvage", "label": "Rozbierz %d obiektów na żywej antenie", "target": 3, "audience": 8, "xp": 15},
	{"key": "kill",    "label": "Pokonaj %d przeciwników", "target": 4, "audience": 10, "xp": 20},
	{"key": "box",     "label": "Otwórz skrzynkę dla widowni", "target": 1, "audience": 6, "xp": 12},
	{"key": "craft",   "label": "Stwórz coś w warsztacie", "target": 1, "audience": 8, "xp": 15},
	{"key": "scrap",   "label": "Uzbieraj %d sztuk złomu", "target": 6, "audience": 6, "xp": 12},
]

## Roll a fresh objective for a floor (deterministic from depth + the run rng).
static func pick(depth: int, rng: RandomNumberGenerator) -> Dictionary:
	var d: Dictionary = DEFS[rng.randi_range(0, DEFS.size() - 1)]
	# Scale a couple of targets gently with depth so deep floors stay meaningful.
	var target := int(d["target"])
	if d["key"] == "kill":
		target += depth / 3
	elif d["key"] == "scrap":
		target += depth
	return {
		"key": d["key"], "label": d["label"], "target": target, "progress": 0,
		"done": false, "reward_audience": int(d["audience"]), "reward_xp": int(d["xp"]) + depth * 2,
	}

## Human-readable line for the HUD, e.g. "Rozbierz 3 obiektów… (1/3)".
static func describe(obj: Dictionary) -> String:
	if obj.is_empty():
		return ""
	var lab: String = obj["label"]
	if lab.contains("%d"):
		lab = lab % int(obj["target"])
	if bool(obj.get("done", false)):
		return "✓ " + lab
	return "%s  (%d/%d)" % [lab, int(obj["progress"]), int(obj["target"])]

## How much `event_key` advances `obj` this tick (0 if unrelated).
static func advance_for(obj: Dictionary, event_key: String, amount: int = 1) -> int:
	if obj.is_empty() or bool(obj.get("done", false)):
		return 0
	return amount if obj.get("key", "") == event_key else 0
