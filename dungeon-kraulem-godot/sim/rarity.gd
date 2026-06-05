class_name Rarity
extends RefCounted
## Five-tier rarity system. Port of engine/rarity.py.
## Field-based (not tag-based) — rarity: String is the source of truth.

const COMMON    := "common"
const UNCOMMON  := "uncommon"
const RARE      := "rare"
const EPIC      := "epic"
const LEGENDARY := "legendary"

const ALL: Array = ["common", "uncommon", "rare", "epic", "legendary"]

const LABELS_PL: Dictionary = {
	"common":    "pospolity",
	"uncommon":  "niepospolity",
	"rare":      "rzadki",
	"epic":      "epicki",
	"legendary": "legendarny",
}

const BOX_LABELS: Dictionary = {
	"common":    "Skrzynka Brązowa",
	"uncommon":  "Skrzynka Srebrna",
	"rare":      "Skrzynka Złota",
	"epic":      "Skrzynka Platynowa",
	"legendary": "Skrzynka Diamentowa",
}

# Diablo-style colors matching engine/rarity.py RGB values.
const COLORS: Dictionary = {
	"common":    Color(0.78, 0.78, 0.78),
	"uncommon":  Color(0.35, 0.78, 0.35),
	"rare":      Color(0.35, 0.55, 0.94),
	"epic":      Color(0.71, 0.35, 0.86),
	"legendary": Color(0.94, 0.65, 0.24),
}

# [floor_min, {rarity: weight}] — matches engine/rarity.py FLOOR_RARITY_WEIGHTS.
const FLOOR_WEIGHTS: Array = [
	[1,  {"common": 90, "uncommon": 10, "rare": 0,  "epic": 0,  "legendary": 0}],
	[4,  {"common": 65, "uncommon": 25, "rare": 9,  "epic": 1,  "legendary": 0}],
	[8,  {"common": 45, "uncommon": 30, "rare": 18, "epic": 6,  "legendary": 1}],
	[12, {"common": 30, "uncommon": 30, "rare": 25, "epic": 12, "legendary": 3}],
	[16, {"common": 20, "uncommon": 25, "rare": 28, "epic": 20, "legendary": 7}],
]

static func label(rarity: String) -> String:
	return LABELS_PL.get(rarity, rarity)

static func box_label(rarity: String) -> String:
	return BOX_LABELS.get(rarity, "Skrzynka Brązowa")

static func color(rarity: String) -> Color:
	return COLORS.get(rarity, COLORS["common"])

static func order(rarity: String) -> int:
	return ALL.find(rarity)

static func weights_for_floor(floor_num: int) -> Dictionary:
	var best: Dictionary = FLOOR_WEIGHTS[0][1]
	for entry in FLOOR_WEIGHTS:
		if floor_num >= int(entry[0]):
			best = entry[1]
	return best.duplicate()

static func pick_for_floor(rng: RandomNumberGenerator, floor_num: int) -> String:
	var weights := weights_for_floor(floor_num)
	var total := 0
	for k in weights:
		total += int(weights[k])
	if total == 0:
		return COMMON
	var roll := rng.randi_range(0, total - 1)
	var acc := 0
	for k in ALL:
		acc += int(weights.get(k, 0))
		if roll < acc:
			return k
	return COMMON
