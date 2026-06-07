class_name MetaCatalog
extends RefCounted
## Meta-progression "menu of choices", ported + expanded from the pygame
## engine/meta_progression.py UNLOCK_CATALOG. DCC-faithful: what persists between
## runs is NOT difficulty, it's the pool of SPECIES (races), ORIGINS, START PERKS,
## ITEMS, COMPANIONS and BIOMES you can bring into a fresh run.
##
## Two ways to own an entry:
##   1. CONDITION unlocks — earned at run end (Meta.UNLOCK_CATALOG, the pygame path).
##   2. PRESTIGE purchases — spend achievement prestige points (the new expansion;
##      ties the trophy hunt directly to the run loadout).
##
## Each entry: {kind, label, reward, cost, effect}
##   effect — applied to the fresh-run player/run state by BoardView._apply_loadout:
##     stats {STAT:Δ} · hp Δmax_hp · audience Δrating · sponsor_all Δattention ·
##     bonus_damage Δ · coating {type,charges} · materials {k:n} · items [tmpl_key] ·
##     tags [String] (mechanical: thick_hide/metal/flammable/…) · biome {..routedef}
##
## Hand-authored (Godot-only) so effects + costs stay maintainable; labels/rewards
## follow the pygame source.

const SAVE_PATH := "user://meta_unlocks.json"

const KIND_LABELS := {
	"species":    "GATUNEK",
	"origin":     "POCHODZENIE",
	"start_perk": "ATUT STARTOWY",
	"item":       "PRZEDMIOT",
	"companion":  "TOWARZYSZ",
	"biome":      "BIOM",
}

# Cost in prestige points, by kind (defaults — overridable per entry).
const KIND_COST := {
	"species": 45, "origin": 30, "start_perk": 22, "item": 26, "companion": 34, "biome": 18,
}

const CATALOG: Dictionary = {
	# ── Always-available defaults (cost 0, owned from the start) ──────────────
	"species_bezimienny": {"kind": "species", "label": "Bezimienny", "reward": "Standardowy uczestnik. Bez bonusów, bez wymówek.", "cost": 0, "effect": {}},
	"origin_debiutant":   {"kind": "origin", "label": "Debiutant", "reward": "Pierwszy raz na arenie. Widzowie nie mają oczekiwań.", "cost": 0, "effect": {}},

	# ── Species (races) ──────────────────────────────────────────────────────
	"species_mutant_chemiczny":  {"kind": "species", "label": "Mutant chemiczny", "reward": "+1 KOND (więcej HP), ODPORNOŚĆ NA TRUCIZNĘ, ale podatność na ogień.", "cost": 45, "effect": {"hp": 12, "tags": ["flammable"], "trait": "poison_immune"}},
	"species_grzybica":          {"kind": "species", "label": "Grzybica", "reward": "+1 WIS, regeneracja, i grzybowy zmysł do MAGII (adept; zna Szron i Żrący Strumień).", "cost": 45, "effect": {"stats": {"WIS": 1}, "hp": 8, "trait": "regen", "magic": "adept", "start_spells": ["mroz", "kwas"]}},
	"species_cyborg_recyklingu": {"kind": "species", "label": "Cyborg Recyklingu", "reward": "+1 SIŁ, metalowa kończyna (naprawa złomem). Maszyna — GŁUCHA na magię.", "cost": 45, "effect": {"stats": {"STR": 1}, "tags": ["metal"], "trait": "salvage_heal", "magic": "mundane"}},
	"species_pamietajacy":       {"kind": "species", "label": "Pamiętający", "reward": "+1 SPRYT, pierwszy cios trafia na pewno, i pamięć do ZAKLĘĆ (adept; zna Marę i Płomień).", "cost": 45, "effect": {"stats": {"INT": 1}, "trait": "first_strike", "magic": "adept", "start_spells": ["iluzja", "ogien"]}},
	"species_kolyski_anti_hosta":{"kind": "species", "label": "Kołyska Konferansjera", "reward": "+1 do WSZYSTKICH statystyk i błogosławieństwo MAGII (adept; zna Płomień i Wskrzeszenie).", "cost": 110, "effect": {"stats": {"STR": 1, "DEX": 1, "INT": 1, "WIS": 1, "CHA": 1}, "magic": "adept", "start_spells": ["ogien", "nekromancja"]}},
	"species_stary_uczestnik":   {"kind": "species", "label": "Stary Uczestnik", "reward": "Blizna po poprzednim zwycięzcy: +8 HP i widownia zna twój numer (+5).", "cost": 50, "effect": {"hp": 8, "audience": 5}},
	"species_bez_twarzy":        {"kind": "species", "label": "Bez Twarzy", "reward": "Widownia NIGDY nie spada poniżej 10 (i startuje +12), ale −2 CHA.", "cost": 50, "effect": {"audience": 12, "stats": {"CHA": -2}, "audience_min": 10}},
	"species_ferromanta_meta":   {"kind": "species", "label": "Ferromanta", "reward": "Magnetyczna skóra (+1 SIŁ) i wrodzona MAGIA metalu (adept; zna Magnetar i Iskrę).", "cost": 60, "effect": {"stats": {"STR": 1}, "tags": ["armored"], "magic": "adept", "start_spells": ["ferromancja", "prad"]}},

	# ── Origins ──────────────────────────────────────────────────────────────
	"origin_drugi_cykl":       {"kind": "origin", "label": "Drugi cykl", "reward": "Zaczynasz z widownią +5 i blizną po poprzednim sezonie.", "cost": 30, "effect": {"audience": 5}},
	"origin_sponsorowany":     {"kind": "origin", "label": "Sponsorowany Uczestnik", "reward": "Startujesz z kontraktem — każdy sponsor zaczyna z większą uwagą (+5).", "cost": 35, "effect": {"sponsor_all": 5}},
	"origin_zhanbiony_showman":{"kind": "origin", "label": "Zhańbiony Showman", "reward": "Startujesz z widownią=20, ale sponsorzy patrzą krzywo (−3).", "cost": 40, "effect": {"audience": 20, "sponsor_all": -3}},
	"origin_wieczny_stazysta": {"kind": "origin", "label": "Wieczny Stażysta", "reward": "Startujesz z zapasem złomu ×2 z magazynu (4 złomu).", "cost": 30, "effect": {"materials": {"złom": 4}}},
	"origin_sponsor_reject":   {"kind": "origin", "label": "Niechciane Dziecko Sponsorów", "reward": "Każdy sponsor startuje z uwagą −5, ale desperacja zaostrza refleks (+1 ZRĘ).", "cost": 30, "effect": {"sponsor_all": -5, "stats": {"DEX": 1}}},
	"origin_byly_konferansjer":{"kind": "origin", "label": "Były Konferansjer", "reward": "Konferansjer mówi o tobie ze współczuciem: +8 widowni, +1 CHA.", "cost": 40, "effect": {"audience": 8, "stats": {"CHA": 1}}},
	"origin_dziedzic_k7":      {"kind": "origin", "label": "Dziedzic Kanału 7", "reward": "Wbudowany mikrofon kierunkowy: +10 widowni i markowa czapka.", "cost": 50, "effect": {"audience": 10, "items": ["sponsor_kepi"]}},

	# ── Start perks (passive — all owned perks auto-apply each run) ───────────
	"perk_lapowka_dla_portiera":{"kind": "start_perk", "label": "Łapówka dla portiera", "reward": "Startujesz z dodatkowym złomem w kieszeni (3).", "cost": 18, "effect": {"materials": {"złom": 3}}},
	"perk_insiderskie_info":    {"kind": "start_perk", "label": "Insiderskie info", "reward": "Znasz układ pierwszego piętra — widownia docenia pewność siebie (+3).", "cost": 18, "effect": {"audience": 3}},
	"perk_stara_legitymacja":   {"kind": "start_perk", "label": "Stara legitymacja Syndykatu", "reward": "Stare papiery otwierają drzwi: +1 CHA.", "cost": 22, "effect": {"stats": {"CHA": 1}}},
	"perk_lyzka_cudu":          {"kind": "start_perk", "label": "Łyżka Cudu", "reward": "Jednorazowy „drugi oddech” — startujesz z +12 max HP.", "cost": 26, "effect": {"hp": 12}},
	"perk_rzemieslnik_terminala":{"kind": "start_perk", "label": "Rzemieślnik terminala", "reward": "Startujesz z 2 przewodami i szmatą — gotowy do craftu.", "cost": 22, "effect": {"materials": {"przewód": 2, "szmata": 1}}},
	"perk_okopowy_weteran":     {"kind": "start_perk", "label": "Okopowy weteran", "reward": "Maska filtrująca i kombinezon: gruba skóra (połowa obrażeń fizycznych) +5 HP.", "cost": 40, "effect": {"tags": ["thick_hide"], "hp": 5}},
	"perk_handlarz_pakietow":   {"kind": "start_perk", "label": "Handlarz Pakietów", "reward": "Kontakty w produkcji: widownia startuje wyżej (+2).", "cost": 18, "effect": {"audience": 2}},
	"perk_taneczne_nogi":       {"kind": "start_perk", "label": "Taneczne nogi", "reward": "Lekka stopa na arenie: +1 ZRĘ.", "cost": 22, "effect": {"stats": {"DEX": 1}}},
	"perk_dzikus_z_arena":      {"kind": "start_perk", "label": "Dzikus z areny", "reward": "+10 max HP i +1 SIŁ — goła pięść i czysta wściekłość.", "cost": 30, "effect": {"hp": 10, "stats": {"STR": 1}}},
	"perk_skapy_jak_widz":      {"kind": "start_perk", "label": "Skąpy jak widz", "reward": "Zaskórniaki: startujesz z 5 złomu na czarną godzinę.", "cost": 18, "effect": {"materials": {"złom": 5}}},
	"perk_kolekcjoner":         {"kind": "start_perk", "label": "Kolekcjoner", "reward": "Oko do skarbów — widownia lubi twój gust (+2).", "cost": 18, "effect": {"audience": 2}},

	# ── Items (start with it / it joins the pool) ────────────────────────────
	"item_mikrofon_anty_hosta": {"kind": "item", "label": "Mikrofon Konferansjera", "reward": "Mikrofon kierunkowy: startowa widownia +5.", "cost": 26, "effect": {"audience": 5}},
	"item_obrazek_finalu":      {"kind": "item", "label": "Obrazek Finału", "reward": "Drobiazg, który podnosi spryt o +1.", "cost": 24, "effect": {"stats": {"INT": 1}}},
	"item_skarpetka_pulkownika":{"kind": "item", "label": "Skarpetka Pułkownika Recyklingu", "reward": "Rozgrzewająca skarpeta: +1 do testów (WIS).", "cost": 24, "effect": {"stats": {"WIS": 1}}},
	"item_mosiezny_pierscien_producenta":{"kind": "item", "label": "Mosiężny Pierścień Producenta", "reward": "Wpływy w produkcji: 2 złomu na start.", "cost": 24, "effect": {"materials": {"złom": 2}}},
	"item_stara_czaszka_z_markerem":{"kind": "item", "label": "Stara Czaszka z Markerem", "reward": "Gadająca czaszka — dobra na show. Widownia +2.", "cost": 24, "effect": {"audience": 2}},
	"item_czerwony_telefon_k7": {"kind": "item", "label": "Czerwony Telefon Kanału 7", "reward": "Gorąca linia do sponsorów: każdy startuje z uwagą +2.", "cost": 28, "effect": {"sponsor_all": 2}},
	"item_klucz_do_kantyny":    {"kind": "item", "label": "Klucz do Kantyny Sponsorów", "reward": "Dostęp do zapasów: 3 złomu na start.", "cost": 24, "effect": {"materials": {"złom": 3}}},
	"item_pamiatkowa_lyzka":    {"kind": "item", "label": "Pamiątkowa Łyżka", "reward": "Łyżka do podważania: +1 ZRĘ.", "cost": 24, "effect": {"stats": {"DEX": 1}}},
	"item_apteczka_kompletna":  {"kind": "item", "label": "Apteczka Kompletna", "reward": "Apteczka polowa: startujesz z +10 max HP.", "cost": 26, "effect": {"hp": 10}},

	# ── Companions (flavor + a small edge) ───────────────────────────────────
	"companion_papuga_anty_host":{"kind": "companion", "label": "Papuga Konferansjera", "reward": "Sarkastyczna papuga komentuje walkę — widzowie ją kochają (+3 widowni).", "cost": 34, "effect": {"audience": 3}},
	"companion_suczka_recyklingu":{"kind": "companion", "label": "Suczka Recyklingu", "reward": "Trójnoga sunia znosi ci złom — 2 na start.", "cost": 34, "effect": {"materials": {"złom": 2}}},
	"companion_kot_ministerstwa":{"kind": "companion", "label": "Kot Ministerstwa", "reward": "Kot z legitymacją służbową: +1 WIS.", "cost": 34, "effect": {"stats": {"WIS": 1}}},
	"companion_dron_sponsorski":{"kind": "companion", "label": "Dron Sponsorski", "reward": "Latająca kamera nakręca show: startowa widownia +5.", "cost": 40, "effect": {"audience": 5}},

	# ── Biomes (join the route pool at the stairs) ───────────────────────────
	"biome_oboz_goblinski":     {"kind": "biome", "label": "Obóz Gobliński", "reward": "Palisady i ogniska: tłoczno od wrogów, sporo łupu.", "cost": 18, "effect": {"biome": {"label": "Obóz Gobliński", "blurb": "Palisady, ogniska, hordy. Dużo wrogów i łupu.", "enemy_mul": 1.5, "object_mul": 1.2, "trap_mul": 1.0, "object_tags": ["wood", "furniture", "salvageable"]}}},
	"biome_siec_kanalizacyjna": {"kind": "biome", "label": "Sieć Kanalizacyjna", "reward": "Rury, smród i kałuże: pozycjonowanie i prąd rządzą.", "cost": 18, "effect": {"biome": {"label": "Sieć Kanalizacyjna", "blurb": "Rury i woda — prąd niesie się daleko.", "enemy_mul": 1.0, "object_mul": 1.0, "trap_mul": 1.8, "object_tags": ["electric", "wire", "hazard", "metal"]}}},
	"biome_tunel_karnawalowy":  {"kind": "biome", "label": "Tunel Karnawałowy", "reward": "Luna park po nocy: dziwne obiekty, hojna widownia.", "cost": 18, "effect": {"biome": {"label": "Tunel Karnawałowy", "blurb": "Luna park po zmroku. Show kocha to miejsce.", "enemy_mul": 1.1, "object_mul": 1.4, "trap_mul": 1.2, "object_tags": ["furniture", "fragile", "plastic"]}}},
	"biome_katakumby_faktur":   {"kind": "biome", "label": "Katakumby Spóźnionych Faktur", "reward": "Świece i ołtarze biurokracji. Cicho i bogato.", "cost": 22, "effect": {"biome": {"label": "Katakumby Faktur", "blurb": "Ołtarze papierów. Cicho, ale skarby czekają.", "enemy_mul": 0.7, "object_mul": 1.5, "trap_mul": 1.0, "object_tags": ["furniture", "paper", "salvageable"]}}},
	"biome_farma_klonow":       {"kind": "biome", "label": "Farma Klonów", "reward": "Kapsuły z biopłynem: organiczni wrogowie, sporo mięsa.", "cost": 22, "effect": {"biome": {"label": "Farma Klonów", "blurb": "Kapsuły biopłynu — organiczni wrogowie, dużo łupu.", "enemy_mul": 1.4, "object_mul": 1.1, "trap_mul": 0.9, "object_tags": ["organic", "fragile"]}}},
	"biome_elfia_kolonia":      {"kind": "biome", "label": "Elfia Kolonia", "reward": "Drzewa rosną przez beton: drewno wszędzie, ogień groźny.", "cost": 22, "effect": {"biome": {"label": "Elfia Kolonia", "blurb": "Drewno przez beton. Łatwopalne, ale bogate.", "enemy_mul": 1.0, "object_mul": 1.6, "trap_mul": 1.1, "object_tags": ["wood", "flammable", "furniture"]}}},
	"biome_redakcja_krawedzi":  {"kind": "biome", "label": "Redakcja Krawędzi", "reward": "Biurka i kamery na żywo: elektronika i ostre cięcia.", "cost": 26, "effect": {"biome": {"label": "Redakcja Krawędzi", "blurb": "Kamery na żywo. Elektronika, ryzyko i splendor.", "enemy_mul": 1.2, "object_mul": 1.3, "trap_mul": 1.3, "object_tags": ["electronic", "metal", "electric"]}}},
	"biome_swiatynia_konferansjera":{"kind": "biome", "label": "Świątynia Konferansjera", "reward": "Ołtarze i popiersia gospodarza. Widownia szaleje.", "cost": 26, "effect": {"biome": {"label": "Świątynia Konferansjera", "blurb": "Kult gospodarza. Show kocha każdy twój ruch.", "enemy_mul": 1.1, "object_mul": 1.2, "trap_mul": 1.0, "object_tags": ["furniture", "salvageable"]}}},
	"biome_lawowe_tunele":      {"kind": "biome", "label": "Lawowe Tunele", "reward": "Magma i jaszczury: ekstremalne, ale spektakularne.", "cost": 26, "effect": {"biome": {"label": "Lawowe Tunele", "blurb": "Magma i gady. Brutalne — i spektakularne.", "enemy_mul": 1.5, "object_mul": 0.9, "trap_mul": 1.6, "object_tags": ["hazard", "metal"]}}},
}

const ORDER: Array = [
	"species_bezimienny", "species_mutant_chemiczny", "species_grzybica", "species_cyborg_recyklingu",
	"species_pamietajacy", "species_kolyski_anti_hosta", "species_stary_uczestnik", "species_bez_twarzy", "species_ferromanta_meta",
	"origin_debiutant", "origin_drugi_cykl", "origin_sponsorowany", "origin_zhanbiony_showman", "origin_wieczny_stazysta",
	"origin_sponsor_reject", "origin_byly_konferansjer", "origin_dziedzic_k7",
	"perk_lapowka_dla_portiera", "perk_insiderskie_info", "perk_stara_legitymacja", "perk_lyzka_cudu", "perk_rzemieslnik_terminala",
	"perk_okopowy_weteran", "perk_handlarz_pakietow", "perk_taneczne_nogi", "perk_dzikus_z_arena", "perk_skapy_jak_widz", "perk_kolekcjoner",
	"item_mikrofon_anty_hosta", "item_obrazek_finalu", "item_skarpetka_pulkownika", "item_mosiezny_pierscien_producenta",
	"item_stara_czaszka_z_markerem", "item_czerwony_telefon_k7", "item_klucz_do_kantyny", "item_pamiatkowa_lyzka", "item_apteczka_kompletna",
	"companion_papuga_anty_host", "companion_suczka_recyklingu", "companion_kot_ministerstwa", "companion_dron_sponsorski",
	"biome_oboz_goblinski", "biome_siec_kanalizacyjna", "biome_tunel_karnawalowy", "biome_katakumby_faktur", "biome_farma_klonow",
	"biome_elfia_kolonia", "biome_redakcja_krawedzi", "biome_swiatynia_konferansjera", "biome_lawowe_tunele",
]

# ── Queries ───────────────────────────────────────────────────────────────────

static func def_of(key: String) -> Dictionary:
	return CATALOG.get(key, {})

static func cost_of(key: String) -> int:
	return int(def_of(key).get("cost", KIND_COST.get(def_of(key).get("kind", ""), 30)))

static func kind_of(key: String) -> String:
	return def_of(key).get("kind", "")

static func keys_of_kind(kind: String) -> Array:
	var out: Array = []
	for k in ORDER:
		if kind_of(k) == kind:
			out.append(k)
	return out

# ── Persistence (separate from generated meta.json) ───────────────────────────

static var _state: Dictionary = {}
static var _loaded := false

static func _ensure() -> void:
	if _loaded:
		return
	_loaded = true
	_state = {"purchased": [], "spent": 0, "species": "species_bezimienny", "origin": "origin_debiutant"}
	if FileAccess.file_exists(SAVE_PATH):
		var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
		if f != null:
			var p: Variant = JSON.parse_string(f.get_as_text())
			if p is Dictionary:
				_state["purchased"] = (p.get("purchased", []) as Array).duplicate()
				_state["spent"] = int(p.get("spent", 0))
				_state["species"] = str(p.get("species", "species_bezimienny"))
				_state["origin"] = str(p.get("origin", "origin_debiutant"))

static func _save() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(_state))

# ── Ownership / purchasing ────────────────────────────────────────────────────

## Owned = an always-free default, OR earned by a run condition (Meta), OR bought.
static func is_owned(key: String) -> bool:
	_ensure()
	if not CATALOG.has(key):
		return false
	if cost_of(key) == 0:
		return true
	if key in (_state["purchased"] as Array):
		return true
	return key in (Meta.load_state().get("unlocks", []) as Array)

static func spent() -> int:
	_ensure()
	return int(_state["spent"])

## Prestige points still available to spend (achievement score minus what's spent).
static func available_prestige() -> int:
	return maxi(0, Achievements.points() - spent())

## Buy `key` with prestige if affordable + not already owned. Returns true on buy.
static func try_purchase(key: String) -> bool:
	_ensure()
	if not CATALOG.has(key) or is_owned(key):
		return false
	var c := cost_of(key)
	if c > available_prestige():
		return false
	(_state["purchased"] as Array).append(key)
	_state["spent"] = int(_state["spent"]) + c
	_save()
	return true

# ── Loadout (chosen species + origin for the next run) ────────────────────────

static func loadout() -> Dictionary:
	_ensure()
	var sp := str(_state["species"])
	var og := str(_state["origin"])
	if not is_owned(sp): sp = "species_bezimienny"
	if not is_owned(og): og = "origin_debiutant"
	return {"species": sp, "origin": og}

static func set_species(key: String) -> void:
	_ensure()
	if kind_of(key) == "species" and is_owned(key):
		_state["species"] = key
		_save()

static func set_origin(key: String) -> void:
	_ensure()
	if kind_of(key) == "origin" and is_owned(key):
		_state["origin"] = key
		_save()

## All effects to apply for the next run: the chosen species + origin, plus EVERY
## owned passive (perks, items, companions, biomes). Returned as a list of
## {key, kind, label, effect} so the caller can apply + log them.
static func active_effects() -> Array:
	_ensure()
	var lo := loadout()
	var out: Array = []
	for key in [lo["species"], lo["origin"]]:
		if CATALOG.has(key):
			out.append(_entry(key))
	for key in ORDER:
		var kind := kind_of(key)
		if kind in ["start_perk", "item", "companion", "biome"] and is_owned(key):
			out.append(_entry(key))
	return out

static func _entry(key: String) -> Dictionary:
	var d: Dictionary = CATALOG[key]
	return {"key": key, "kind": d["kind"], "label": d["label"], "effect": d.get("effect", {})}

## Test/reset helper.
static func reset() -> void:
	_state = {"purchased": [], "spent": 0, "species": "species_bezimienny", "origin": "origin_debiutant"}
	_loaded = true
	if FileAccess.file_exists(SAVE_PATH):
		DirAccess.remove_absolute(SAVE_PATH)
