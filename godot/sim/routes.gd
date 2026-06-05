class_name Routes
extends RefCounted
## Route gambling between floors (the DCC floor-map beat). Before each descent you
## pick one of a few routes; each is a "biome" that biases the procedural floor
## (more enemies / more salvage / more traps / quieter). Flavor labels echo the
## Python floor_archetypes. A route is identified by a key so it can be persisted
## in the save and reproduced deterministically (the mods derive from the key).

## key -> {label, blurb, enemy_mul, object_mul, trap_mul}
const BIOMES: Dictionary = {
	"sortownia": {
		"label": "Rozległa Sortownia",
		"blurb": "Dużo złomu do rozbiórki, umiarkowane ryzyko.",
		"enemy_mul": 1.0, "object_mul": 1.6, "trap_mul": 1.0,
	},
	"konflikt": {
		"label": "Strefa Konfliktu Zawodników",
		"blurb": "Więcej wrogów — i więcej łupu z trupów.",
		"enemy_mul": 1.6, "object_mul": 1.0, "trap_mul": 1.0,
	},
	"pulapki": {
		"label": "Sektor Pułapek Sponsora",
		"blurb": "Prąd i kałuże wszędzie. Pozycjonowanie wygrywa.",
		"enemy_mul": 0.8, "object_mul": 0.8, "trap_mul": 2.2,
	},
	"zamknieta": {
		"label": "Trasa Zamknięta",
		"blurb": "Cicho. Mało wrogów, ale i chudo z zasobami.",
		"enemy_mul": 0.4, "object_mul": 0.7, "trap_mul": 0.6,
	},
	"serwis": {
		"label": "Sieć Korytarzy Serwisowych",
		"blurb": "Ciasno i technicznie. Sporo elektroniki na złom.",
		"enemy_mul": 1.1, "object_mul": 1.3, "trap_mul": 1.4,
	},
	"skrot": {
		"label": "Skrót, którego nie ma na mapie",
		"blurb": "Nikt nie wie, co tam jest. Hazard.",
		"enemy_mul": 1.3, "object_mul": 1.3, "trap_mul": 1.3,
	},
}

## Offer n distinct routes (keys), chosen without replacement.
static func offer(rng: RandomNumberGenerator, n: int = 3) -> Array:
	var keys: Array = BIOMES.keys()
	# Fisher–Yates shuffle (seeded), then take n.
	for i in range(keys.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = keys[i]; keys[i] = keys[j]; keys[j] = t
	return keys.slice(0, mini(n, keys.size()))

## The generation modifiers for a biome key (with the key + label folded in so
## FloorGen can stamp the floor name). Unknown key -> neutral mods.
static func mods_for(key: String) -> Dictionary:
	var b: Dictionary = BIOMES.get(key, {})
	return {
		"biome_key": key,
		"label": b.get("label", ""),
		"enemy_mul": float(b.get("enemy_mul", 1.0)),
		"object_mul": float(b.get("object_mul", 1.0)),
		"trap_mul": float(b.get("trap_mul", 1.0)),
	}

static func label_of(key: String) -> String:
	return BIOMES.get(key, {}).get("label", key)

static func blurb_of(key: String) -> String:
	return BIOMES.get(key, {}).get("blurb", "")
