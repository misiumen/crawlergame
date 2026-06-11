class_name Appearance
extends RefCounted
## Character looks: a handful of choices per slot (Abiotic-Factor style picker),
## rendered procedurally by the player painters — the creator's big preview and
## the in-game board token read the SAME data. Pure data + persistence, no nodes.
##
## An appearance is a plain Dictionary {slot -> option index}; it rides into the
## run on player.flags["appearance"], so the save round-trips it for free.

const SAVE_PATH := "user://appearance.json"

const SKIN := [
	{"label": "Blada",   "col": Color(0.85, 0.72, 0.62)},
	{"label": "Śniada",  "col": Color(0.72, 0.55, 0.40)},
	{"label": "Ciemna",  "col": Color(0.45, 0.32, 0.24)},
	{"label": "Sina",    "col": Color(0.55, 0.62, 0.72)},
	{"label": "Zielona", "col": Color(0.48, 0.62, 0.42)},
]
const HAIR := [
	{"label": "Łysina",  "kind": "bald"},
	{"label": "Krótkie", "kind": "short"},
	{"label": "Irokez",  "kind": "mohawk"},
	{"label": "Długie",  "kind": "long"},
	{"label": "Kucyk",   "kind": "tail"},
]
const HAIR_COL := [
	{"label": "Czarne",  "col": Color(0.12, 0.10, 0.12)},
	{"label": "Blond",   "col": Color(0.85, 0.74, 0.42)},
	{"label": "Rude",    "col": Color(0.72, 0.36, 0.18)},
	{"label": "Siwe",    "col": Color(0.75, 0.78, 0.82)},
	{"label": "Neonowe", "col": Color(0.30, 0.85, 0.95)},
]
const TORSO := [
	{"label": "Szczupły", "w": 0.85},
	{"label": "Średni",   "w": 1.0},
	{"label": "Szeroki",  "w": 1.2},
]
const LEGS := [
	{"label": "Proste",  "w": 0.9},
	{"label": "Masywne", "w": 1.15},
]
const FEET := [
	{"label": "Ciężkie buty", "kind": "boots"},
	{"label": "Trampki",      "kind": "sneakers"},
	{"label": "Sandały",      "kind": "sandals"},
]
## Contestant jumpsuit palette (torso + legs pick from the same set).
const CLOTH_COL := [
	{"label": "Cyjan",     "col": Color(0.23, 0.62, 0.72)},
	{"label": "Pomarańcz", "col": Color(0.85, 0.50, 0.20)},
	{"label": "Zieleń",    "col": Color(0.35, 0.62, 0.38)},
	{"label": "Fiolet",    "col": Color(0.55, 0.35, 0.68)},
	{"label": "Szarość",   "col": Color(0.45, 0.48, 0.55)},
]

const SLOTS := {
	"skin": SKIN, "hair": HAIR, "hair_col": HAIR_COL, "torso": TORSO,
	"torso_col": CLOTH_COL, "legs": LEGS, "legs_col": CLOTH_COL, "feet": FEET,
}
const SLOT_LABELS := {
	"skin": "Skóra", "hair": "Fryzura", "hair_col": "Kolor włosów",
	"torso": "Tułów", "torso_col": "Kolor stroju", "legs": "Nogi",
	"legs_col": "Kolor spodni", "feet": "Stopy",
}
const SLOT_ORDER := ["skin", "hair", "hair_col", "torso", "torso_col", "legs", "legs_col", "feet"]

static func defaults() -> Dictionary:
	var d: Dictionary = {}
	for k in SLOT_ORDER:
		d[k] = 0
	d["name"] = ""
	return d

## Current option dict for a slot (index clamped, so stale saves never crash).
static func opt(ap: Dictionary, slot: String) -> Dictionary:
	var opts: Array = SLOTS.get(slot, [])
	if opts.is_empty():
		return {}
	var i: int = clampi(int(ap.get(slot, 0)), 0, opts.size() - 1)
	return opts[i]

static func col(ap: Dictionary, slot: String) -> Color:
	return opt(ap, slot).get("col", Color.WHITE)

## Step a slot's index by dir (wraps both ways). Returns a NEW dict.
static func cycle(ap: Dictionary, slot: String, dir: int) -> Dictionary:
	var out := ap.duplicate()
	var n: int = (SLOTS.get(slot, []) as Array).size()
	if n > 0:
		out[slot] = posmod(int(ap.get(slot, 0)) + dir, n)
	return out

static func save(ap: Dictionary) -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(ap))

static func load_saved() -> Dictionary:
	var d := defaults()
	if not FileAccess.file_exists(SAVE_PATH):
		return d
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return d
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if parsed is Dictionary:
		for k in SLOT_ORDER:
			if (parsed as Dictionary).has(k):
				d[k] = int(parsed[k])
		d["name"] = str((parsed as Dictionary).get("name", ""))
	return d
