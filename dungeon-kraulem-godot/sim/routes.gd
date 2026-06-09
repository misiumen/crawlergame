class_name Routes
extends RefCounted
## Route gambling between floors (the DCC floor-map beat). Before each descent you
## pick one of a few routes; each is a "biome" that biases the procedural floor
## (more enemies / more salvage / more traps / quieter). Flavor labels echo the
## Python floor_archetypes. A route is identified by a key so it can be persisted
## in the save and reproduced deterministically (the mods derive from the key).

## key -> {label, blurb, enemy_mul, object_mul, trap_mul, object_tags}.
## object_tags biases WHICH objects spawn (thematic floors), not just how many.
const BIOMES: Dictionary = {
	"sortownia": {
		"label": "Rozległa Sortownia",
		"blurb": "Dużo złomu do rozbiórki, umiarkowane ryzyko.",
		"enemy_mul": 1.0, "object_mul": 1.6, "trap_mul": 1.0,
		"object_tags": ["furniture", "salvageable", "wood"],
	},
	"konflikt": {
		"label": "Strefa Konfliktu Zawodników",
		"blurb": "Więcej wrogów — i więcej łupu z trupów.",
		"enemy_mul": 1.6, "object_mul": 1.0, "trap_mul": 1.0,
		"object_tags": [],
	},
	"pulapki": {
		"label": "Sektor Pułapek Sponsora",
		"blurb": "Prąd i kałuże wszędzie. Pozycjonowanie wygrywa.",
		"enemy_mul": 0.8, "object_mul": 0.8, "trap_mul": 2.2,
		"object_tags": ["electric", "electrical", "wire", "electronic", "hazard"],
	},
	"zamknieta": {
		"label": "Trasa Zamknięta",
		"blurb": "Cicho. Mało wrogów, ale i chudo z zasobami.",
		"enemy_mul": 0.4, "object_mul": 0.7, "trap_mul": 0.6,
		"object_tags": [],
	},
	"serwis": {
		"label": "Sieć Korytarzy Serwisowych",
		"blurb": "Ciasno i technicznie. Sporo elektroniki na złom.",
		"enemy_mul": 1.1, "object_mul": 1.3, "trap_mul": 1.4,
		"object_tags": ["electronic", "metal", "electric", "fragile"],
	},
	"skrot": {
		"label": "Skrót, którego nie ma na mapie",
		"blurb": "Nikt nie wie, co tam jest. Hazard.",
		"enemy_mul": 1.3, "object_mul": 1.3, "trap_mul": 1.3,
		"object_tags": [],
	},
	# Show-floor biomes from the pygame floor catalog (each carries an achievement).
	"okopy_frontowe": {
		"label": "Frontowe Okopy",
		"blurb": "Artyleria gdzieś nad sufitem. Gruz, błoto i propaganda.",
		"enemy_mul": 1.4, "object_mul": 0.9, "trap_mul": 1.4,
		"object_tags": ["metal", "hazard"],
	},
	"zoo_korporacyjne": {
		"label": "Zoo Korporacyjne",
		"blurb": "Klatki, wybiegi i sponsorskie pawie. Zwierzyna kibicuje.",
		"enemy_mul": 1.3, "object_mul": 1.1, "trap_mul": 0.8,
		"object_tags": ["organic", "fragile"],
	},
	"muzeum_spektakli": {
		"label": "Muzeum Spektakli",
		"blurb": "Eksponaty z poprzednich sezonów. Kurator nie pyta.",
		"enemy_mul": 0.9, "object_mul": 1.5, "trap_mul": 1.1,
		"object_tags": ["furniture", "fragile", "salvageable"],
	},
	"bar_skurczybyk": {
		"label": "Bar U Skurczybyka",
		"blurb": "Neon, kleista podłoga i wieczór karaoke. Mikrofon czeka.",
		"enemy_mul": 1.0, "object_mul": 1.2, "trap_mul": 0.9,
		"object_tags": ["furniture", "wood"],
	},
}

## Meta-progression biomes (unlocked via the catalog) register here so they join
## the route pool for the run. Cleared + repopulated when a loadout is applied.
static var _extra: Dictionary = {}

static func register(key: String, def: Dictionary) -> void:
	_extra[key] = def

static func clear_extra() -> void:
	_extra.clear()

## All currently-offerable biomes (built-in + meta-unlocked).
static func all_biomes() -> Dictionary:
	if _extra.is_empty():
		return BIOMES
	var m := BIOMES.duplicate(true)
	for k in _extra:
		m[k] = _extra[k]
	return m

## Offer n distinct routes (keys), chosen without replacement.
static func offer(rng: RandomNumberGenerator, n: int = 3) -> Array:
	var keys: Array = all_biomes().keys()
	# Fisher–Yates shuffle (seeded), then take n.
	for i in range(keys.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = keys[i]; keys[i] = keys[j]; keys[j] = t
	return keys.slice(0, mini(n, keys.size()))

## The generation modifiers for a biome key (with the key + label folded in so
## FloorGen can stamp the floor name). Unknown key -> neutral mods.
static func mods_for(key: String) -> Dictionary:
	var b: Dictionary = all_biomes().get(key, {})
	return {
		"biome_key": key,
		"label": b.get("label", ""),
		"enemy_mul": float(b.get("enemy_mul", 1.0)),
		"object_mul": float(b.get("object_mul", 1.0)),
		"trap_mul": float(b.get("trap_mul", 1.0)),
		"object_tags": (b.get("object_tags", []) as Array).duplicate(),
	}

static func label_of(key: String) -> String:
	return all_biomes().get(key, {}).get("label", key)

static func blurb_of(key: String) -> String:
	return all_biomes().get(key, {}).get("blurb", "")
