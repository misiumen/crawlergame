class_name AudienceState
extends RefCounted
## Player audience rating (0–100) and band transitions.
## Turn-based port of engine/audience.py (1 turn ≈ 5 in-game minutes).

const BAND_COLD    := "cold"
const BAND_WARMING := "warming"
const BAND_HOT     := "hot"
const BAND_VIRAL   := "viral"

const BAND_RANGES: Dictionary = {
	"cold":    [0, 19],
	"warming": [20, 49],
	"hot":     [50, 79],
	"viral":   [80, 100],
}

const BAND_LABELS_PL: Dictionary = {
	"cold":    "ZIMNO",
	"warming": "ROZGRZEWKA",
	"hot":     "GORĄCO",
	"viral":   "VIRAL",
}

# Combat modifiers per band — port of audience.py _BAND_COMBAT_MODS.
const BAND_COMBAT_MODS: Dictionary = {
	"cold":    {"to_hit": -1, "audience_on_kill": 1},
	"warming": {"to_hit":  0, "audience_on_kill": 2},
	"hot":     {"to_hit": +1, "audience_on_kill": 3},
	"viral":   {"to_hit": +2, "audience_on_kill": 5},
}

# Idle decay: grace period = 24 turns (≈2 in-game hours), then -1 per 12 turns.
const IDLE_GRACE_TURNS  := 24
const IDLE_DECAY_TURNS  := 12

var rating: int = 0
var idle_turns: int = 0
var history: Array = []   # recent values for sparkline (up to 32)
var peak: int = 0
var min_rating: int = 0   # a floor on the rating (species "Bez Twarzy" sets this)

func band() -> String:
	var r := clampi(rating, 0, 100)
	for b in BAND_RANGES:
		var br: Array = BAND_RANGES[b]
		if r >= br[0] and r <= br[1]:
			return b
	return BAND_COLD

func band_label() -> String:
	return BAND_LABELS_PL.get(band(), "?")

func combat_mods() -> Dictionary:
	return BAND_COMBAT_MODS.get(band(), BAND_COMBAT_MODS[BAND_COLD]).duplicate()

## Change rating. Returns {crossed, from_band, to_band, direction} or {crossed: false}.
func change(delta: int, _source: String = "") -> Dictionary:
	if delta == 0:
		return {"crossed": false}
	var old_band := band()
	rating = clampi(rating + delta, min_rating, 100)
	if rating > peak:
		peak = rating
	idle_turns = 0
	history.append(rating)
	if history.size() > 32:
		history = history.slice(history.size() - 32)
	var new_band := band()
	if new_band != old_band:
		return {"crossed": true, "from_band": old_band, "to_band": new_band,
				"direction": 1 if delta > 0 else -1}
	return {"crossed": false}

## Advance idle decay. Call once per turn.
func tick(turns: int = 1) -> void:
	idle_turns += turns
	if idle_turns <= IDLE_GRACE_TURNS:
		return
	var over := idle_turns - IDLE_GRACE_TURNS
	var steps := over / IDLE_DECAY_TURNS
	if steps > 0 and rating > min_rating:
		rating = maxi(min_rating, rating - steps)
		idle_turns = IDLE_GRACE_TURNS + (over - steps * IDLE_DECAY_TURNS)
