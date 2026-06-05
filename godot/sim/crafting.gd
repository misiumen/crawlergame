class_name Crafting
extends RefCounted
## Tag-based tinkering. No fixed recipes: combine tagged materials, infer a
## function, roll d20 + INT vs DC. What works once goes in the recipe book.

# ── Material → tag definitions ───────────────────────────────────────────────
const MATERIAL_TAGS: Dictionary = {
	"przewód":  ["conductive", "electric"],
	"złom":     ["metal", "edge"],
	"kwas":     ["chem", "corrosive"],
	"szmata":   ["binding", "soft"],
	"butelka":  ["container", "fragile"],
	"bateria":  ["electric", "power"],
	"rurka":    ["metal", "haft"],
	"drewno":   ["flammable", "haft", "soft"],
	"plastik":  ["container", "light"],
}

# ── Grammar rules ────────────────────────────────────────────────────────────
# Ordered most-specific first. Match = all required tags present in combined set.
const TAG_GRAMMAR: Array = [
	{
		"required":      ["metal", "edge", "binding"],
		"category":      "weapon",
		"name_pl":       "Nóż ze złomu",
		"desc_fuzzy":    "Prowizoryczna broń sieczna. Tnie, ale nieładnie.",
		"dominant":      "metal",
		"base_charges":  0,
		"effect":        {"damage_bonus": 3},
	},
	{
		"required":      ["metal", "haft"],
		"category":      "weapon",
		"name_pl":       "Prowizoryczny buzdygan",
		"desc_fuzzy":    "Broń obuchowa na drzewcu. Powolna, ale wali.",
		"dominant":      "metal",
		"base_charges":  0,
		"effect":        {"damage_bonus": 4},
	},
	{
		"required":      ["electric", "container"],
		"category":      "thrown",
		"name_pl":       "Granat prądowy",
		"desc_fuzzy":    "Coś, co razi prądem na odległość. Ładunek? Granat? Nie masz pewności.",
		"dominant":      "electric",
		"base_charges":  2,
		"effect":        {"dmg_type": "electric", "base_dmg": 8},
	},
	{
		"required":      ["electric", "binding"],
		"category":      "coating",
		"name_pl":       "Powłoka prądowa",
		"desc_fuzzy":    "Powłoka przewodząca na ostrze. Trzy uderzenia.",
		"dominant":      "electric",
		"base_charges":  3,
		"effect":        {"coating": "electric"},
	},
	{
		"required":      ["corrosive", "container"],
		"category":      "thrown",
		"name_pl":       "Fiolka kwasu",
		"desc_fuzzy":    "Żrąca ciecz zamknięta pod ciśnieniem. Rozbryzg na kontakcie.",
		"dominant":      "corrosive",
		"base_charges":  2,
		"effect":        {"dmg_type": "corrosive", "base_dmg": 5, "status": "corroded", "status_turns": 3},
	},
	{
		"required":      ["chem", "binding"],
		"category":      "coating",
		"name_pl":       "Powłoka trująca",
		"desc_fuzzy":    "Trucizna na ostrze. Trzy dawki.",
		"dominant":      "chem",
		"base_charges":  3,
		"effect":        {"coating": "poison"},
	},
	{
		"required":      ["flammable", "container"],
		"category":      "thrown",
		"name_pl":       "Butelka zapalająca",
		"desc_fuzzy":    "Łatwopalna mieszanina w szkle. Klasyk rozpaczy.",
		"dominant":      "flammable",
		"base_charges":  2,
		"effect":        {"dmg_type": "fire", "base_dmg": 6, "hazard": "fire"},
	},
	{
		"required":      ["power", "conductive"],
		"category":      "tool",
		"name_pl":       "Ogniwo",
		"desc_fuzzy":    "Akumulator. Zasila powłoki elektryczne — doładowuje je.",
		"dominant":      "power",
		"base_charges":  1,
		"effect":        {"recharge_coating": 2},
	},
	{
		"required":      ["binding", "soft"],
		"category":      "medical",
		"name_pl":       "Bandaż",
		"desc_fuzzy":    "Opatrunek. Tamuje krew, podnosi na duchu.",
		"dominant":      "soft",
		"base_charges":  1,
		"effect":        {"heal": 8},
	},
]

# ── Backfire pools by dominant tag ───────────────────────────────────────────
const BACKFIRE_POOLS: Dictionary = {
	"electric": [
		{"type": "damage",    "dmg": 3, "dmg_type": "electric", "status": "shocked", "turns": 1,
		 "desc": "Iskra — porażenie ciebie!"},
		{"type": "coating_lost",
		 "desc": "Spięcie — twoja powłoka przepada."},
		{"type": "alert_enemies", "radius": 4,
		 "desc": "EMP — wybudzasz wszystkich w zasięgu 4."},
	],
	"corrosive": [
		{"type": "damage",    "dmg": 2, "dmg_type": "physical", "status": "corroded", "turns": 2,
		 "desc": "Kwas na twarz — żre!"},
		{"type": "max_hp_loss", "amount": 1,
		 "desc": "Trwałe -1 HP max."},
	],
	"flammable": [
		{"type": "status",    "status": "burning", "turns": 2,
		 "desc": "Twoje odzienie płonie!"},
		{"type": "hazard_tile", "hazard": "fire",
		 "desc": "Podpala kafelek pod tobą."},
	],
	"power": [
		{"type": "int_xp_loss", "amount": 5,
		 "desc": "Rozładowanie — tracisz 5 INT XP."},
	],
	"chem": [
		{"type": "damage",    "dmg": 1, "dmg_type": "physical", "status": "poisoned", "turns": 2,
		 "desc": "Próbka trucizny na palce."},
	],
	"soft":    [{"type": "materials_lost", "desc": "Tracisz materiały."}],
	"metal":   [{"type": "materials_lost", "desc": "Tracisz materiały."}],
	"unknown": [{"type": "materials_lost", "desc": "Tracisz materiały."}],
}

# ── Affix pools ───────────────────────────────────────────────────────────────
const AFFIX_POOLS: Dictionary = {
	"electric":  ["podwojny_ladunek", "razenie_obszarowe"],
	"edge":      ["krwawy"],
	"container": ["natrysk"],
	"binding":   ["ciche"],
	"fragile":   ["niestabilny"],
	"metal":     ["wzmocniony"],
	"corrosive": ["natrawiajacy"],
	"power":     ["doladowany"],
}

const AFFIX_NAMES: Dictionary = {
	"podwojny_ladunek":  "podwójny ładunek",
	"razenie_obszarowe": "+teren rażenia",
	"krwawy":            "krwawy",
	"natrysk":           "natrysk",
	"ciche":             "ciche",
	"niestabilny":       "niestabilny",
	"wzmocniony":        "wzmocniony",
	"natrawiajacy":      "natrawiający",
	"doladowany":        "doładowany",
}

const AFFIX_EFFECTS: Dictionary = {
	"podwojny_ladunek":  {"charges_bonus": 3},
	"razenie_obszarowe": {"aoe": true},
	"krwawy":            {"damage_when_hurt_bonus": 3},
	"natrysk":           {"coat_tile": true},
	"ciche":             {"silent": true},
	"niestabilny":       {"random_charges": true},
	"wzmocniony":        {"damage_bonus": 2},
	"natrawiajacy":      {"extra_status_turns": 2},
	"doladowany":        {"charges_bonus": 2},
}

const NAME_FRAGMENTS: Dictionary = {
	"electric":  ["Piorun", "Iskra", "Wolta", "Błysk"],
	"corrosive": ["Żrący", "Kwas", "Ząb"],
	"flammable": ["Żar", "Płomień", "Lont"],
	"metal":     ["Ząb", "Kolec", "Żelazo"],
	"power":     ["Rdzeń", "Ogniwo", "Ładunek"],
	"soft":      ["Szew", "Węzeł"],
	"chem":      ["Jad", "Esencja"],
	"unknown":   ["Wynalazek", "Twór", "Coś"],
}

# ── Core helpers ──────────────────────────────────────────────────────────────

static func material_tags(mat_name: String) -> Array:
	return MATERIAL_TAGS.get(mat_name, []).duplicate()

static func combined_tags(mat_names: Array) -> Array:
	var out: Array = []
	for name in mat_names:
		for tag in material_tags(name):
			if tag not in out:
				out.append(tag)
	return out

static func match_rule(tags: Array) -> Variant:
	var best: Variant = null
	var best_count := 0
	for rule in TAG_GRAMMAR:
		var req: Array = rule["required"]
		var all_match := true
		for r in req:
			if r not in tags:
				all_match = false
				break
		if all_match and req.size() > best_count:
			best = rule
			best_count = req.size()
	return best

static func compute_dc(mat_names: Array, discovered: Array) -> int:
	var tags := combined_tags(mat_names)
	var rule: Variant = match_rule(tags)
	var dc := 12 if rule != null else 16
	dc += maxi(0, mat_names.size() - 2)
	if "power" in tags or "fragile" in tags:
		dc += 2
	if "fragile" in tags and "electric" in tags:
		dc += 3
	if "binding" in tags:
		dc -= 2
	if _tag_set_known(tags, discovered):
		dc -= 2
	return clampi(dc, 6, 18)

static func _tag_set_known(tags: Array, discovered: Array) -> bool:
	var sorted_tags := tags.duplicate()
	sorted_tags.sort()
	for entry in discovered:
		var known: Array = (entry["tags"] as Array).duplicate()
		known.sort()
		if known == sorted_tags:
			return true
	return false

static func _dominant_tag(tags: Array, rule: Variant) -> String:
	if rule != null:
		return (rule as Dictionary).get("dominant", "unknown")
	for t in ["electric", "flammable", "corrosive", "power", "chem"]:
		if t in tags:
			return t
	return "unknown"

static func _risk_label(dominant: String) -> String:
	match dominant:
		"electric":  return "iskra? spięcie? EMP?"
		"corrosive": return "kwas? żrące ryzyko?"
		"flammable": return "ogień? pożar?"
		"power":     return "rozładowanie?"
		"chem":      return "trucizna?"
		_:           return "tracisz materiały"

# ── Preview (no mutation) ─────────────────────────────────────────────────────

static func preview(mat_names: Array, discovered: Array) -> Dictionary:
	if mat_names.is_empty():
		return {}
	var tags := combined_tags(mat_names)
	var rule: Variant = match_rule(tags)
	var dc := compute_dc(mat_names, discovered)
	var dominant := _dominant_tag(tags, rule)
	var stability_pct := clampi(100 - (dc - 6) * 5, 5, 95)
	var known := _tag_set_known(tags, discovered)
	return {
		"tags": tags,
		"rule": rule,
		"dc": dc,
		"dominant": dominant,
		"fuzzy_desc": (rule as Dictionary)["desc_fuzzy"] if rule else "Nie masz pojęcia, co z tego wyjdzie.",
		"stability_pct": stability_pct,
		"risk_label": _risk_label(dominant),
		"known": known,
		"tiers": [
			["krytyk",    "unikat + afiks"],
			["sukces",    "działa"],
			["częściowy", "1 użycie, wadliwy"],
			["porażka",   "tracisz materiały"],
			["backfire",  _risk_label(dominant)],
		],
	}

# ── Attempt (mutates: spends materials, records discovery) ────────────────────

static func attempt(mat_names: Array, materials: Dictionary, discovered: Array,
		rng: RandomNumberGenerator, int_mod: int) -> Dictionary:
	var tags := combined_tags(mat_names)
	var rule: Variant = match_rule(tags)
	var dc := compute_dc(mat_names, discovered)
	var dominant := _dominant_tag(tags, rule)
	var roll := rng.randi_range(1, 20) + int_mod
	var margin := roll - dc

	var outcome: String
	if   margin >= 5:  outcome = "krytyk"
	elif margin >= 0:  outcome = "sukces"
	elif margin >= -4: outcome = "czesciowy"
	elif margin >= -8: outcome = "porazka"
	else:              outcome = "backfire"

	var xp_gain := 0
	match outcome:
		"krytyk":              xp_gain = 5
		"sukces":              xp_gain = 3
		"czesciowy", "porazka": xp_gain = 1
		"backfire":            xp_gain = 1

	# Spend one of each material used.
	for mat in mat_names:
		var count: int = int(materials.get(mat, 0))
		if count <= 1: materials.erase(mat)
		else:          materials[mat] = count - 1

	var result := {
		"outcome": outcome, "roll": roll, "dc": dc, "margin": margin,
		"item": null, "backfire": null, "int_xp_gained": xp_gain, "events": [],
	}

	if outcome in ["krytyk", "sukces", "czesciowy"] and rule != null:
		var item := _build_item(rule as Dictionary, outcome, margin, tags, rng, discovered)
		result["item"] = item
		if outcome in ["krytyk", "sukces"]:
			_record_discovery(tags, (rule as Dictionary)["name_pl"], discovered)

	if outcome == "backfire":
		var pool: Array = BACKFIRE_POOLS.get(dominant, BACKFIRE_POOLS["unknown"])
		result["backfire"] = pool[rng.randi_range(0, pool.size() - 1)].duplicate()

	result["events"].append({
		"type": "craft_attempt", "outcome": outcome,
		"roll": roll, "dc": dc,
		"item_name": (result["item"] as GameItem).display_name() if result["item"] else "",
	})
	return result

# ── Item construction ─────────────────────────────────────────────────────────

static func _build_item(rule: Dictionary, outcome: String, margin: int,
		tags: Array, rng: RandomNumberGenerator, discovered: Array) -> GameItem:
	var dominant: String = rule.get("dominant", "unknown")
	var wadliwy := outcome == "czesciowy"
	var item_name: String = rule["name_pl"]
	var rarity_str := Rarity.COMMON
	var affixes: Array = []
	var affix_names: Array = []

	if outcome == "krytyk":
		if margin >= 10:
			rarity_str = Rarity.RARE
			affixes = _pick_affixes(tags, 2, rng)
			item_name = _generate_name(dominant, rng)
		else:
			rarity_str = Rarity.UNCOMMON
			affixes = _pick_affixes(tags, 1, rng)
		# Known recipe bumps rarity one tier further.
		if _tag_set_known(tags, discovered):
			var idx := Rarity.order(rarity_str)
			if idx >= 0 and idx + 1 < Rarity.ALL.size():
				rarity_str = Rarity.ALL[idx + 1]

	for a in affixes:
		affix_names.append(AFFIX_NAMES.get(a, a))

	var item := GameItem.new(item_name, rule["category"], rarity_str)
	item.affixes = affixes
	item.affix_names_pl = affix_names
	item.tags = tags.duplicate()
	item.origin = "crafted"
	item.wadliwy = wadliwy

	var base_charges: int = rule.get("base_charges", 1)
	if wadliwy:
		item.charges = 1
	elif base_charges == 0:
		item.charges = 0
	else:
		item.charges = base_charges
		for akey in affixes:
			var fx: Dictionary = AFFIX_EFFECTS.get(akey, {})
			if fx.has("charges_bonus") and item.charges > 0:
				item.charges += int(fx["charges_bonus"])
			if fx.get("random_charges", false):
				item.charges = rng.randi_range(1, 5)

	item.effect = rule.get("effect", {}).duplicate()
	for akey in affixes:
		var fx: Dictionary = AFFIX_EFFECTS.get(akey, {})
		for fkey in fx:
			if fkey not in ["charges_bonus", "random_charges"]:
				item.effect[fkey] = fx[fkey]

	return item

static func _pick_affixes(tags: Array, count: int, rng: RandomNumberGenerator) -> Array:
	var candidates: Array = []
	for tag in tags:
		for a in (AFFIX_POOLS.get(tag, []) as Array):
			if a not in candidates:
				candidates.append(a)
	if candidates.is_empty():
		return []
	# Shuffle in-place via Fisher-Yates.
	for i in range(candidates.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp = candidates[i]; candidates[i] = candidates[j]; candidates[j] = tmp
	return candidates.slice(0, mini(count, candidates.size()))

static func _generate_name(dominant: String, rng: RandomNumberGenerator) -> String:
	var frags: Array = NAME_FRAGMENTS.get(dominant, NAME_FRAGMENTS["unknown"])
	return frags[rng.randi_range(0, frags.size() - 1)]

static func _record_discovery(tags: Array, name: String, discovered: Array) -> void:
	var sorted_tags := tags.duplicate()
	sorted_tags.sort()
	for entry in discovered:
		var known: Array = (entry["tags"] as Array).duplicate()
		known.sort()
		if known == sorted_tags:
			entry["times"] = int(entry.get("times", 0)) + 1
			return
	discovered.append({"tags": sorted_tags, "name": name, "times": 1})
