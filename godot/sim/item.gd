class_name GameItem
extends RefCounted
## A crafted or found item in the player's run inventory.
## Distinct from CombatEntity — entities live on the board; items live in the pocket.

const CAT_COATING  := "coating"
const CAT_THROWN   := "thrown"
const CAT_WEAPON   := "weapon"
const CAT_TRAP     := "trap"
const CAT_MEDICAL  := "medical"
const CAT_TOOL     := "tool"
const CAT_SCROLL   := "recipe_scroll"

static var _next_uid: int = 1

var uid: int = 0
var name_pl: String = ""
var category: String = ""
var rarity: String = Rarity.COMMON
var tags: Array = []
var affixes: Array = []          # affix-key strings (e.g. ["krwawy", "ciche"])
var affix_names_pl: Array = []   # Polish display strings for affixes
var charges: int = 1             # 0 = permanent (weapon upgrade, etc.)
var effect: Dictionary = {}      # category-specific runtime data
var origin: String = ""          # crafted / boss / sponsor / widownia / chest / mob
var wadliwy: bool = false        # częściowy craft: capped at 1 charge, reduced effect

func _init(_name: String = "", _cat: String = "", _rarity: String = Rarity.COMMON) -> void:
	uid = _next_uid
	_next_uid += 1
	name_pl = _name
	category = _cat
	rarity = _rarity

func display_name() -> String:
	var n := name_pl
	if wadliwy:
		n = "[wadliwy] " + n
	if not affix_names_pl.is_empty():
		n += " — " + ", ".join(affix_names_pl)
	return n

func rarity_color() -> Color:
	return Rarity.color(rarity)

func short_desc() -> String:
	match category:
		CAT_COATING:  return "powłoka x%d" % charges
		CAT_THROWN:   return "rzut x%d" % charges
		CAT_WEAPON:   return "+%d obr." % effect.get("damage_bonus", 0)
		CAT_MEDICAL:  return "leczenie +%d" % effect.get("heal", 0)
		CAT_TOOL:     return "narzędzie"
		CAT_SCROLL:   return "receptura"
		_:            return category

# ── Serialization (save/load) ─────────────────────────────────────────────────

func to_dict() -> Dictionary:
	return {
		"name_pl": name_pl, "category": category, "rarity": rarity,
		"tags": tags.duplicate(), "affixes": affixes.duplicate(),
		"affix_names_pl": affix_names_pl.duplicate(), "charges": charges,
		"effect": effect.duplicate(), "origin": origin, "wadliwy": wadliwy,
	}

static func from_dict(d: Dictionary) -> GameItem:
	var it := GameItem.new(d.get("name_pl", ""), d.get("category", ""), d.get("rarity", Rarity.COMMON))
	it.tags = (d.get("tags", []) as Array).duplicate()
	it.affixes = (d.get("affixes", []) as Array).duplicate()
	it.affix_names_pl = (d.get("affix_names_pl", []) as Array).duplicate()
	it.charges = int(d.get("charges", 1))
	it.effect = (d.get("effect", {}) as Dictionary).duplicate()
	it.origin = d.get("origin", "")
	it.wadliwy = bool(d.get("wadliwy", false))
	return it
