class_name Highlights
extends RefCounted
## Highlight reel, ported from pygame systems/highlight_reel.py. Standout moments
## are recorded during a run (big hits, kills, clutch survivals, level-ups); the
## results screen surfaces the top few by `value`. Stored on the player flags so
## it persists in the save.

const MAX_ENTRIES := 16   # cap kept on the reel
const TOP_N := 3          # how many surface in the montage

## Append a moment to a reel array (mutates + returns it), trimmed to the best ones.
static func add(reel: Array, kind: String, line: String, value: int = 1) -> Array:
	if line == "":
		return reel
	reel.append({"kind": kind, "line": line, "value": value})
	if reel.size() > MAX_ENTRIES:
		reel.sort_custom(func(a, b): return int(a["value"]) > int(b["value"]))
		reel.resize(MAX_ENTRIES)
	return reel

## The top-n most impressive lines, highest value first.
static func top(reel: Array, n: int = TOP_N) -> Array:
	var copy := reel.duplicate()
	copy.sort_custom(func(a, b): return int(a["value"]) > int(b["value"]))
	var out: Array = []
	for i in mini(n, copy.size()):
		out.append(copy[i]["line"])
	return out
