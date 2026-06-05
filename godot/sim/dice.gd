class_name Dice
extends RefCounted
## Tiny dice-notation roller, e.g. "1d6+2", "2d4", "1d8-1". Used for content-
## driven enemy damage (MOB_COMBAT_STATS carry strings like "2d6+4").

## Roll a dice string with the given RNG. Returns at least 1. Bad input -> 1.
static func roll(notation: String, rng: RandomNumberGenerator) -> int:
	var spec := parse(notation)
	if spec.is_empty():
		return 1
	var total: int = int(spec["bonus"])
	for i in int(spec["count"]):
		total += rng.randi_range(1, int(spec["sides"]))
	return maxi(1, total)

## Average value of a dice string (for previews/scaling), or 1 on bad input.
static func average(notation: String) -> float:
	var spec := parse(notation)
	if spec.is_empty():
		return 1.0
	return float(spec["count"]) * (float(spec["sides"]) + 1.0) / 2.0 + float(spec["bonus"])

## Parse "NdM+K" -> {count, sides, bonus}, or {} if it doesn't match.
static func parse(notation: String) -> Dictionary:
	var n := notation.strip_edges().to_lower().replace(" ", "")
	var re := RegEx.new()
	re.compile("^(\\d+)d(\\d+)([+-]\\d+)?$")
	var m := re.search(n)
	if m == null:
		return {}
	return {
		"count": int(m.get_string(1)),
		"sides": int(m.get_string(2)),
		"bonus": int(m.get_string(3)) if m.get_string(3) != "" else 0,
	}
