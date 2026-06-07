class_name Spells
extends RefCounted
## Castable spells, ported from pygame engine/magic.py. They REUSE the elemental
## damage + status engine (fire/electric/acid/cold each hit their tag multipliers),
## so a spell is "ranged systemic damage". Design echo of the source: "mag potężny
## ale kruchy + limit many" — powerful but mana-limited, and mana scales with INT.
##
## Spell: {name, mana, hp_cost, kind, dmg_type, status, desc}
##   kind: "element" (damage + matching status) · "push" (telekinetic shove) ·
##         "drain" (damage + self-heal) · "void" (big damage, self-recoil) ·
##         "illusion" (enemy loses its next turn + forgets you) · "mend" (self-heal)

const SPELLS := {
	"ogien":      {"name": "Płomień", "mana": 2, "kind": "element", "dmg_type": "fire", "status": "burning", "desc": "Ognisty pocisk — pali łatwopalnych."},
	"prad":       {"name": "Iskra", "mana": 2, "kind": "element", "dmg_type": "electric", "status": "shocked", "desc": "Łuk prądu — rażący metal i mokrych."},
	"kwas":       {"name": "Żrący Strumień", "mana": 2, "kind": "element", "dmg_type": "acid", "status": "corroded", "desc": "Kwas — zżera metal i pancerz."},
	"mroz":       {"name": "Szron", "mana": 2, "kind": "element", "dmg_type": "cold", "status": "slowed", "desc": "Mróz — spowalnia i kruszy mokrych."},
	"telekineza": {"name": "Pchnięcie", "mana": 3, "kind": "push", "desc": "Telekinetyczny odrzut — wepchnij wroga (np. w prąd)."},
	"iluzja":     {"name": "Mara", "mana": 3, "kind": "illusion", "desc": "Złuda — wróg traci turę i gubi twój trop."},
	"ferromancja":{"name": "Magnetar", "mana": 3, "kind": "element", "dmg_type": "acid", "status": "corroded", "desc": "Ferromancja — rwie metal na strzępy."},
	"krew":       {"name": "Krwawa Danina", "mana": 0, "hp_cost": 6, "kind": "drain", "dmg_type": "physical", "desc": "Oddajesz 6 HP, by zadać cios i wyssać życie."},
	"pustka":     {"name": "Pustka", "mana": 3, "kind": "void", "dmg_type": "cold", "desc": "Czysta nicość — ogromne obrażenia, ale odrzut rani ciebie."},
	"nekromancja":{"name": "Wskrzeszenie", "mana": 4, "kind": "mend", "desc": "Zszywasz własne ciało mocą — duże leczenie."},
}

const ORDER := ["ogien", "prad", "kwas", "mroz", "telekineza", "iluzja", "ferromancja", "krew", "pustka", "nekromancja"]

static func def_of(key: String) -> Dictionary:
	return SPELLS.get(key, {})

## ── Knowing + learning ────────────────────────────────────────────────────────
## You don't start knowing spells unless your race is magically adept; the rest is
## learned from scrolls. Mundane (tech/construct) races can't learn magic at all.
## Known keys live in player flags["known_spells"].

static func known(p) -> Array:
	return p.flags.get("known_spells", [])

static func is_known(p, key: String) -> bool:
	return key in known(p)

static func can_learn(p) -> bool:
	return p.magic_affinity != "mundane"

## Teach a spell. Returns true if newly learned (false if mundane / already known).
static func learn(p, key: String) -> bool:
	if not SPELLS.has(key) or not can_learn(p) or is_known(p, key):
		return false
	var lst: Array = p.flags.get("known_spells", [])
	lst.append(key)
	p.flags["known_spells"] = lst
	return true

## A spell this player doesn't know yet (for a random scroll), or "" if none left.
static func random_unknown(p, rng: RandomNumberGenerator) -> String:
	var pool: Array = []
	for k in ORDER:
		if not is_known(p, k):
			pool.append(k)
	if pool.is_empty():
		return ""
	return pool[rng.randi_range(0, pool.size() - 1)]

## Max mana scales with INT and your race's magic affinity (the caster payoff —
## adepts run hot, mundane races barely flicker).
static func max_mana_for(p) -> int:
	var bonus := 0
	match p.magic_affinity:
		"adept":   bonus = 3
		"mundane": bonus = -2
	return maxi(0, 3 + maxi(0, p.stat_mod("INT")) + bonus)
