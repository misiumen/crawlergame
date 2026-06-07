class_name Safehouse
extends RefCounted
## Safehouses — the between-fights breather rooms, ported from pygame
## systems/safehouses.py. The original used credits; this run has no credit
## economy, so SCRAP (złom) is the currency — which closes the loop: salvage →
## złom → heal / buy materials / sell loot / sponsor packages.
##
## Four subtypes (one spawns per floor). Services are data; BoardView applies the
## effects (it has the player HP, materials and inventory).

const SUBTYPES := {
	"klinika":        {"name": "Klinika polowa", "blurb": "Zszyją cię. Tanio nie znaczy bezboleśnie."},
	"czarny_rynek":   {"name": "Czarny rynek", "blurb": "Kup materiały, opchnij łup. Nikt nie pyta skąd."},
	"kiosk_sponsora": {"name": "Kiosk sponsora", "blurb": "Reklama, paczki, raporty. Wszystko na sprzedaż."},
	"tablica":        {"name": "Tablica ogłoszeń", "blurb": "Plotki z areny. Czasem przydatne."},
}
const ORDER := ["klinika", "czarny_rynek", "kiosk_sponsora", "tablica"]

## Materials the black market sells (convert spare złom into craft stock).
const BUY_MATS := [
	{"mat": "przewód", "price": 3}, {"mat": "szmata", "price": 2},
	{"mat": "bateria", "price": 4}, {"mat": "plastik", "price": 2},
	{"mat": "rurka", "price": 3},
]

## What a found/crafted item fetches when you sell it, by rarity.
const SELL_BY_RARITY := {"common": 3, "uncommon": 5, "rare": 8, "epic": 12, "legendary": 18}

## Fixed-service rows per subtype: {action, label, cost(złom)[, hp/aud]}.
## (Black-market buy/sell rows are built dynamically by the presentation, since
## the sell list depends on what you're carrying.)
const SERVICES := {
	"klinika": [
		{"action": "heal_small", "label": "Opatrunek (+12 HP)", "cost": 6},
		{"action": "heal_full", "label": "Pełne leczenie (100% HP)", "cost": 20},
	],
	"kiosk_sponsora": [
		{"action": "ad", "label": "Reklama sponsora (+6 widowni)", "cost": 4},
		{"action": "box", "label": "Paczka sponsora (skrzynka)", "cost": 18},
		{"action": "scroll", "label": "Zwój zaklęć (naucz się zaklęcia)", "cost": 14},
	],
	"tablica": [
		{"action": "read", "label": "Przeczytaj ogłoszenia (za darmo)", "cost": 0},
	],
}

## Deterministic per-floor subtype so a reloaded floor shows the same safehouse.
static func subtype_for(depth: int) -> String:
	return ORDER[(depth - 1) % ORDER.size()]

static func name_of(subtype: String) -> String:
	return SUBTYPES.get(subtype, {}).get("name", subtype)

static func blurb_of(subtype: String) -> String:
	return SUBTYPES.get(subtype, {}).get("blurb", "")

static func services(subtype: String) -> Array:
	return SERVICES.get(subtype, [])

static func sell_price(rarity: String) -> int:
	return int(SELL_BY_RARITY.get(rarity, 2))
