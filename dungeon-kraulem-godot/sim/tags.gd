class_name Tags
extends RefCounted
## Tag -> implied-property inference. This is the FOUNDATION of the systemic
## engine: rules match on PROPERTIES, not object ids, so one rule written once
## works on anything carrying the right tag (the whole ~141-entry bestiary
## reacts to the engine without per-entry hand-tagging).
##
## Full port of dungeon_kraulem/engine/systemic.py (lines 47-128):
##   _TAG_INFERENCE + _PROP_ALIASES  -> IMPLIED
##   _ELEMENT_TAG_SOURCE             -> ELEMENT_SOURCE
##   _IMPACT_TAGS                    -> IMPACT_TAGS
##   _DAMAGE_TO_ELEMENT             -> DAMAGE_TO_ELEMENT
##
## The Python source names properties in Polish (łatwopalne, przewodzące…); the
## Godot combat layer already speaks English (DMG_ELECTRIC, has_property
## ("conductive")). The player never sees EITHER — these are internal property
## tags. So the vocabulary here is English for consistency with combat.gd, and
## the Polish element display names (for log lines) live in ELEMENT_LABELS_PL.
##
## Mappings are deliberately NARROW (matches the Python intent: "tylko
## jednoznaczne materiały" — only unambiguous materials), so the world does NOT
## become "everything burns / everything conducts".

# ── Elements (internal English; PL only for the player-facing log) ───────────
const EL_FIRE := "fire"
const EL_ELECTRIC := "electric"
const EL_ACID := "acid"
const EL_COLD := "cold"
const EL_IMPACT := "impact"

const ELEMENT_LABELS_PL := {
	"fire":     "ogień",
	"electric": "prąd",
	"acid":     "kwas",
	"cold":     "mróz",
	"impact":   "uderzenie",
}

## damage_type (combat) -> matter element (systemic). "physical" maps to nothing
## (ordinary damage, no matter interaction).
const DAMAGE_TO_ELEMENT := {
	"fire":     "fire",
	"electric": "electric",
	"acid":     "acid",
	"cold":     "cold",
}

# ── Tag -> implied matter properties (the inference table) ────────────────────
const IMPLIED := {
	# metal  (acid -> corrosion)
	"armored":    ["metal"],
	"machine":    ["metal", "conductive"],
	"mechanical": ["metal"],
	"robot":      ["metal", "conductive"],
	"drone":      ["metal", "conductive"],
	"construct":  ["metal"],
	"scrap":      ["metal"],
	"terminal":   ["metal", "conductive"],
	"metal":      ["conductive"],            # alias: metal conducts
	# conductive  (electric -> shock)
	"electronic": ["conductive"],
	"electrical": ["conductive"],
	"electric":   ["conductive"],
	"wire":       ["conductive"],
	"spark":      ["conductive"],
	# flammable  (fire -> blaze)
	"wood":       ["flammable"],
	"wooden":     ["flammable"],
	"furniture":  ["flammable"],
	"fungal":     ["flammable"],
	"gas":        ["flammable"],
	"plastic":    ["flammable"],
	"paper":      ["flammable"],
	"cloth":      ["flammable"],
	"fabric":     ["flammable"],
	"oil":        ["flammable"],
	"grease":     ["flammable"],
	# fragile  (impact -> shatter)
	"ceramic":    ["fragile"],
	"glass":      ["fragile"],
	# wet  (cold -> freeze; standing liquid also conducts)
	"liquid":     ["wet"],
	"water":      ["wet", "conductive"],
	"slime":      ["wet"],
	# organic / body-system extension (Godot-specific; drives bleed overlays)
	"organic":    ["flammable", "bleeds"],
	"flesh":      ["bleeds"],
	"beast":      ["bleeds"],
}

# ── Element SOURCE tags (active energy: a hazard or a soaked/charged item) ────
## A passive "wire"/"metal" is NOT a source — it only conducts. These tags make
## the entity itself an emitter of the element.
const ELEMENT_SOURCE := {
	"electric":   "electric",
	"electrical": "electric",
	"spark":      "electric",
	"fire":       "fire",
	"flame":      "fire",
	"burning":    "fire",
	"acid":       "acid",
	"caustic":    "acid",
	"frost":      "cold",
	"ice":        "cold",
	"cold":       "cold",
	"cryo":       "cold",
}

# ── Impact (blunt) weapon/source tags ────────────────────────────────────────
const IMPACT_TAGS := ["blunt", "heavy", "obuch", "ciezkie", "uderzenie"]

# ── Matter rules: (source element, target property) -> effect ────────────────
## The 5 rules of matter. The systemic resolver matches a source's element
## against a target's properties. Effect carries the status, immediate damage,
## AC delta, and a lingering profile (DoT/turns/stun/slow). Player log lines are
## Polish. (combat.gd currently hardcodes the water+wire path; this table is the
## data a future systemic.gd resolver consumes.)
const MATTER_RULES := [
	{
		"element": "fire", "prop": "flammable", "effect": "pożar", "status": "płonie",
		"damage": 4, "ac_delta": 0, "linger": {"dot": 3, "turns": 3},
		"log": "{cel} staje w płomieniach. Ogień szuka, czego się chwycić dalej.",
	},
	{
		"element": "electric", "prop": "conductive", "effect": "porażenie", "status": "porażony",
		"damage": 5, "ac_delta": 0, "linger": {"dot": 2, "turns": 2, "stun": 0.5},
		"log": "Prąd przeskakuje przez {cel}. Iskry, zapach spalenizny.",
	},
	{
		"element": "acid", "prop": "metal", "effect": "korozja", "status": "skorodowany",
		"damage": 0, "ac_delta": -2, "linger": {"dot": 0, "turns": 0},
		"log": "Kwas wgryza się w metal: {cel}. Coś syczy i mięknie.",
	},
	{
		"element": "cold", "prop": "wet", "effect": "zamrożenie", "status": "zamrożony",
		"damage": 0, "ac_delta": 0, "linger": {"dot": 0, "turns": 2, "slow": true, "stun": 0.4},
		"log": "Wilgoć na {cel} zamarza w sekundę. Ruch zamiera.",
	},
	{
		"element": "impact", "prop": "fragile", "effect": "roztrzaskanie", "status": "roztrzaskany",
		"damage": 8, "ac_delta": 0, "linger": {"dot": 0, "turns": 0},
		"log": "{cel} pęka z trzaskiem. Odłamki rozsypują się po podłodze.",
	},
]

# ── Inference API ─────────────────────────────────────────────────────────────

## Returns a set-like Dictionary {property: true} for an entity's tags: every
## raw tag is its own property, plus everything it implies.
static func properties_for(tags: Array) -> Dictionary:
	var props := {}
	for t in tags:
		props[t] = true
		if IMPLIED.has(t):
			for p in IMPLIED[t]:
				props[p] = true
	return props

static func has_property(tags: Array, prop: String) -> bool:
	return properties_for(tags).has(prop)

## If any tag makes the entity an active source of an element, return that
## element (e.g. "electric"); otherwise "".
static func element_source(tags: Array) -> String:
	for t in tags:
		if ELEMENT_SOURCE.has(t):
			return ELEMENT_SOURCE[t]
	return ""

## True if any tag marks the source as a blunt/impact attack.
static func is_impact(tags: Array) -> bool:
	for t in tags:
		if t in IMPACT_TAGS:
			return true
	return false

## Map a combat damage_type to its matter element ("" for physical/unknown).
static func element_for_damage(dmg_type: String) -> String:
	return DAMAGE_TO_ELEMENT.get(dmg_type, "")

## Polish display label for an element (for the player log).
static func element_label(element: String) -> String:
	return ELEMENT_LABELS_PL.get(element, element)

## Find the matter rule for (source element x target tags), or null. The first
## rule whose element matches AND whose required property the target carries.
static func match_matter_rule(element: String, target_tags: Array) -> Variant:
	var props := properties_for(target_tags)
	for rule in MATTER_RULES:
		if rule["element"] == element and props.has(rule["prop"]):
			return rule
	return null
