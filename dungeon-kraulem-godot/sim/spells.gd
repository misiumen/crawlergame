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

## Max mana scales with INT (incl. the tinkering track) — the INT build's payoff.
static func max_mana_for(p) -> int:
	return 3 + maxi(0, p.stat_mod("INT"))
