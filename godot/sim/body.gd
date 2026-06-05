class_name BodyState
extends RefCounted
## Procedural breakable body. Built from a body-plan (data/body_plans.json) and
## an entity's total HP. Tracks PER-PART hp + wound types + severity, layered
## ON TOP of the entity's canonical hp/death model — the entity still dies when
## entity.hp <= 0 (so existing combat/win-lose stays intact); the body adds
## located wounds, maims (broken leg -> can't flee), and butcher yields.
##
## Sim-only: no nodes. Presentation reads parts[] to draw the rig + overlays.

const SEV_INTACT := "intact"
const SEV_DAMAGED := "damaged"
const SEV_CRIPPLED := "crippled"
const SEV_BROKEN := "broken"

const SEVERITY_PL := {
	"intact":   "sprawne",
	"damaged":  "uszkodzone",
	"crippled": "okaleczone",
	"broken":   "złamane",
}

# Wound types (drive presentation overlays + butcher flavor).
const W_BURN := "burn"
const W_BLEED := "bleed"
const W_CORRODE := "corrode"
const W_SHOCK := "shock"
const W_FREEZE := "freeze"
const W_SEVER := "sever"

const WOUND_PL := {
	"burn":    "oparzenie",
	"bleed":   "krwawienie",
	"corrode": "korozja",
	"shock":   "poparzenie prądem",
	"freeze":  "odmrożenie",
	"sever":   "amputacja",
}

# Core parts that cannot be severed (losing them = death, not amputation).
const VITAL_PARTS := ["torso", "body", "mass"]
# Locomotion parts whose loss costs mobility (broken -> can't flee/charge).
const LOCOMOTION_PARTS := ["l_leg", "r_leg", "propulsion", "tail"]

var plan_key: String = ""
var parts: Dictionary = {}   # part_key -> part dict (see _make_part)
var order: Array = []        # part keys sorted by display_order

# ── Construction ──────────────────────────────────────────────────────────────

## Build from an explicit plan definition (testable, no autoload needed).
## plan_def is the {part_key: {hp_frac, to_hit_mod, ...}} dict from body_plans.
func _init(_plan_key: String, plan_def: Dictionary, total_hp: int) -> void:
	plan_key = _plan_key
	var keyed: Array = []
	for pkey in plan_def:
		var pd: Dictionary = plan_def[pkey]
		var part := _make_part(pkey, pd, total_hp)
		parts[pkey] = part
		keyed.append(pkey)
	keyed.sort_custom(func(a, b):
		return int(parts[a]["display_order"]) < int(parts[b]["display_order"]))
	order = keyed

func _make_part(pkey: String, pd: Dictionary, total_hp: int) -> Dictionary:
	var maxhp: int = maxi(1, int(round(float(pd.get("hp_frac", 0.5)) * total_hp)))
	return {
		"key":         pkey,
		"label_pl":    pd.get("label_pl", pkey),
		"max_hp":      maxhp,
		"hp":          maxhp,
		"to_hit_mod":  int(pd.get("to_hit_mod", 0)),
		"damage_mul":  float(pd.get("damage_mul", 1.0)),
		"maim_status": pd.get("maim_status"),       # may be null
		"display_order": int(pd.get("display_order", 99)),
		"wounds":      {},                          # wound_type -> true
		"severity":    SEV_INTACT,
		"severed":     false,
		"vital":       pkey in VITAL_PARTS,
		"butcher_intact": pd.get("butcher_intact_bonus", []),
		"butcher_broken": pd.get("butcher_broken_bonus", []),
	}

## Resolve which plan a creature uses, from its tags / monster key, against the
## body_plans bundle. Mirrors Python: PLANS_BY_MONSTER_KEY first, then PLAN_BY_TAG.
static func plan_key_for(tags: Array, monster_key: String, bundle: Dictionary) -> String:
	var by_key: Dictionary = bundle.get("PLANS_BY_MONSTER_KEY", {})
	if monster_key != "" and by_key.has(monster_key):
		return by_key[monster_key]
	var by_tag: Array = bundle.get("PLAN_BY_TAG", [])
	for pair in by_tag:
		if (pair as Array)[0] in tags:
			return (pair as Array)[1]
	return "humanoid"

## Convenience: build a body for an entity from the Data autoload bundle.
## Returns null if no plan data is available (headless tests pass a def directly).
static func from_bundle(tags: Array, monster_key: String, total_hp: int,
		bundle: Dictionary) -> BodyState:
	var plans: Dictionary = bundle.get("PLANS", {})
	if plans.is_empty():
		return null
	var pkey := plan_key_for(tags, monster_key, bundle)
	if not plans.has(pkey):
		return null
	return BodyState.new(pkey, plans[pkey], total_hp)

# ── Damage application ────────────────────────────────────────────────────────

## Classify a wound from the damage type (+ whether the target bleeds, + heavy).
static func wound_for(dmg_type: String, target_bleeds: bool, heavy: bool) -> String:
	match dmg_type:
		"electric": return W_SHOCK
		"fire":     return W_BURN
		"acid":     return W_CORRODE
		"cold":     return W_FREEZE
		_:
			if heavy:          return W_SEVER
			if target_bleeds:  return W_BLEED
			return ""

## Choose a hit zone. If aimed_zone is a valid part key, use it; else weight by
## part size (hp_frac via max_hp) so the torso is hit most often.
func pick_zone(rng: RandomNumberGenerator, aimed_zone: String = "") -> String:
	if aimed_zone != "" and parts.has(aimed_zone) and not parts[aimed_zone]["severed"]:
		return aimed_zone
	var pool: Array = []
	var weights: Array = []
	var total := 0
	for pkey in order:
		var p: Dictionary = parts[pkey]
		if p["severed"]:
			continue
		var w: int = maxi(1, int(p["max_hp"]))
		pool.append(pkey); weights.append(w); total += w
	if pool.is_empty():
		return ""
	var roll := rng.randi_range(1, total)
	var acc := 0
	for i in pool.size():
		acc += int(weights[i])
		if roll <= acc:
			return pool[i]
	return pool[-1]

## Apply a located hit. Returns a result dict describing the wound + any newly
## triggered maim. Does NOT touch entity.hp — the caller's _apply_damage owns the
## canonical life pool; this only tracks the part for wounds/maims/butcher.
func apply_hit(zone: String, amount: int, dmg_type: String,
		target_bleeds: bool, heavy: bool) -> Dictionary:
	if not parts.has(zone):
		return {}
	var p: Dictionary = parts[zone]
	var was_broken: bool = p["severity"] == SEV_BROKEN
	p["hp"] = maxi(0, int(p["hp"]) - amount)
	var wound := wound_for(dmg_type, target_bleeds, heavy)
	if wound != "":
		p["wounds"][wound] = true
	_recompute_severity(p)
	var newly_broken: bool = (p["severity"] == SEV_BROKEN) and not was_broken
	# Sever a non-vital limb when it newly breaks from a heavy/edge blow.
	var did_sever := false
	if newly_broken and not p["vital"] and heavy:
		p["severed"] = true
		p["wounds"][W_SEVER] = true
		did_sever = true
	var maim = p["maim_status"] if newly_broken else null
	return {
		"zone":         zone,
		"label_pl":     p["label_pl"],
		"wound":        wound,
		"severity":     p["severity"],
		"newly_broken": newly_broken,
		"severed":      did_sever,
		"maim_status":  maim,
		"damage_mul":   p["damage_mul"],
	}

func _recompute_severity(p: Dictionary) -> void:
	var frac := float(p["hp"]) / float(maxi(1, int(p["max_hp"])))
	if   p["hp"] <= 0:    p["severity"] = SEV_BROKEN
	elif frac <= 0.5:     p["severity"] = SEV_CRIPPLED
	elif frac < 1.0:      p["severity"] = SEV_DAMAGED
	else:                 p["severity"] = SEV_INTACT

# ── Queries (behavior + presentation) ─────────────────────────────────────────

func part(zone: String) -> Dictionary:
	return parts.get(zone, {})

func severity_of(zone: String) -> String:
	return parts[zone]["severity"] if parts.has(zone) else SEV_INTACT

func damage_mul_for(zone: String) -> float:
	return float(parts[zone]["damage_mul"]) if parts.has(zone) else 1.0

func to_hit_mod_for(zone: String) -> int:
	return int(parts[zone]["to_hit_mod"]) if parts.has(zone) else 0

## All maim statuses currently active (from broken parts that carry one).
func active_maims() -> Array:
	var out: Array = []
	for pkey in order:
		var p: Dictionary = parts[pkey]
		if p["severity"] == SEV_BROKEN and p["maim_status"] != null:
			if p["maim_status"] not in out:
				out.append(p["maim_status"])
	return out

## Mobility gone? A broken locomotion part means no fleeing / no charging.
func can_move() -> bool:
	var locomotors: Array = []
	for pkey in order:
		if pkey in LOCOMOTION_PARTS:
			locomotors.append(pkey)
	if locomotors.is_empty():
		return true   # blobs/drones-without-legs always "move"
	# Quadruped/biped: if EVERY locomotion part is broken, it can't move.
	for pkey in locomotors:
		if parts[pkey]["severity"] != SEV_BROKEN:
			return true
	return false

## Slowed if any single locomotion part is broken (mirrors maim "slowed").
func is_hobbled() -> bool:
	for pkey in order:
		if pkey in LOCOMOTION_PARTS and parts[pkey]["severity"] == SEV_BROKEN:
			return true
	return false

## Butcher yields: intact parts give their intact bonus, broken give the broken.
func butcher_yields() -> Dictionary:
	var out: Dictionary = {}
	for pkey in order:
		var p: Dictionary = parts[pkey]
		var table: Array = p["butcher_broken"] if p["severity"] == SEV_BROKEN else p["butcher_intact"]
		for entry in table:
			var k: String = (entry as Array)[0]
			var n: int = int((entry as Array)[1])
			out[k] = int(out.get(k, 0)) + n
	return out

## Compact status line for the combat readout (Polish).
func summary_line() -> String:
	var hurt: Array = []
	for pkey in order:
		var p: Dictionary = parts[pkey]
		if p["severity"] != SEV_INTACT:
			var tag: String = SEVERITY_PL.get(p["severity"], p["severity"])
			hurt.append("%s: %s" % [p["label_pl"], tag])
	return ", ".join(hurt) if not hurt.is_empty() else "bez obrażeń"
