class_name ClassFeatures
extends RefCounted
## Class passives (read at combat sites) + actives (once-per-floor abilities).
## Port of systems/class_features.py. Passives are looked up at use time, not
## pre-baked, so re-classing stays consistent. Actives mutate the sim and return
## event dicts (the board's only effect channel). A few abilities are board-
## adapted from the Python original where the surface differs (noted inline).

# ── Passive registry: class_key -> {bonus_kind: amount} ──────────────────────
const PASSIVES: Dictionary = {
	"bruiser":       {"hp_max": 20, "unarmed_dmg": 2},
	"survivor":      {"hp_max": 10, "ac": 1},
	"saboteur":      {"trap_crit": 2},
	"engineer":      {"crafting": 2},
	"ranger":        {"ranged_hit": 2},
	"medic":         {"heal_mul": 1},
	"occultist":     {"mental_resist": 1},
	"negotiator":    {"social": 2},
	"trickster":     {"stealth_init": 2, "social": 1},
	"demolitionist": {"unarmed_dmg": 1, "trap_crit": 1},
	"showman":       {"audience_mul": 1},
	"scout":         {"stealth_init": 1, "ranged_hit": 1},
}

# ── Active registry: class_key -> {name_pl, desc_pl} ─────────────────────────
const ACTIVES: Dictionary = {
	"bruiser":       {"name_pl": "Brutalna szarża", "desc_pl": "Następny atak zadaje podwójne obrażenia."},
	"survivor":      {"name_pl": "Drugi oddech", "desc_pl": "Leczy 35% maks. HP."},
	"saboteur":      {"name_pl": "Sabotaż", "desc_pl": "Oszałamia najbliższego wroga na rundę."},
	"engineer":      {"name_pl": "Szybka naprawa", "desc_pl": "Leczy 20% HP i usuwa negatywne statusy."},
	"ranger":        {"name_pl": "Precyzyjny strzał", "desc_pl": "Następny atak automatycznie trafia."},
	"medic":         {"name_pl": "Triage", "desc_pl": "Leczy 60% maks. HP i usuwa krwawienie."},
	"occultist":     {"name_pl": "Klątwa", "desc_pl": "Wrogowie w pokoju: -2 do trafienia na 3 rundy."},
	"negotiator":    {"name_pl": "Targi", "desc_pl": "+6 widowni i bonus do następnego krafta."},
	"trickster":     {"name_pl": "Znikanie", "desc_pl": "Wszyscy wrogowie tracą czujność."},
	"demolitionist": {"name_pl": "Wybuch", "desc_pl": "15 obrażeń wszystkim wrogom w pokoju."},
	"showman":       {"name_pl": "Hype", "desc_pl": "+8 widowni natychmiast."},
	"scout":         {"name_pl": "Mapowanie", "desc_pl": "Odsłania wrogów i daje +3 widowni."},
}

# ── Passive lookups ───────────────────────────────────────────────────────────

static func passive_bonus_for(class_key: String, kind: String) -> int:
	if not PASSIVES.has(class_key):
		return 0
	return int((PASSIVES[class_key] as Dictionary).get(kind, 0))

static func passive_bonus(player, kind: String) -> int:
	return passive_bonus_for(player.class_key, kind) if player.class_key != "" else 0

static func heal_multiplier(player) -> float:
	return 1.0 + float(passive_bonus(player, "heal_mul"))

static func audience_multiplier(player) -> float:
	return 1.0 + float(passive_bonus(player, "audience_mul"))

# ── Active availability ───────────────────────────────────────────────────────

## Returns [can_use: bool, reason_pl: String].
static func can_use_active(player, floor_num: int) -> Array:
	if player.class_key == "":
		return [false, "Brak klasy."]
	if player.class_active_used_floor == floor_num:
		return [false, "Umiejętność już użyta na tym piętrze."]
	return [true, ""]

static func active_name(class_key: String) -> String:
	return (ACTIVES[class_key]["name_pl"]) if ACTIVES.has(class_key) else ""

static func active_desc(class_key: String) -> String:
	return (ACTIVES[class_key]["desc_pl"]) if ACTIVES.has(class_key) else ""
