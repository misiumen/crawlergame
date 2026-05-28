"""Item templates and helpers.

P29.43 — Dodane pole `rarity` (common/uncommon/rare/epic/legendary).
Domyślnie `common`. Powiązane: engine/rarity.py. Niektóre itemy mają
też tagi biomów (zoo/forge/trenches/...) — generator lootu w
biomowym piętrze będzie preferował items pasujące do biomu LUB
neutralne (bez biome tagu).

P29.43-sweep — `_ITEM_ALIASES` dict mapuje fantomowe item keys ze
starszych konfiguracji (sponsor gift_pools: bandage, stimpak,
antidote, ammo_box, lockpick, …) na istniejące templaty w
ITEM_TEMPLATES. Bez tego mappingu drop pody dostawały make_item
z pustym proto → gołe entity bez tagów + bez affordance „use".
Alias zachowuje display_name canonical template'u (czyli „dirty
bandage" zamiast surowego „bandage" jako placeholder).
"""
from ..engine.entity import Entity, T_ITEM


# ── P29.43-sweep: aliases dla starszych keys w gift_pools ────────────
# Klucz → canonical key w ITEM_TEMPLATES. make_item używa aliasu
# do lookup'u proto, ale entity zachowuje canonical key (bo i tak
# żaden inny kod nie używa „bandage" jako stable id).
_ITEM_ALIASES = {
    # Medical / consumable
    "bandage":             "dirty_bandage",
    "stimpak":             "dirty_bandage",
    "antidote":            "dirty_bandage",
    "adrenaline":          "coffee",
    "premium_painkiller":  "dirty_bandage",
    "authorized_stim":     "dirty_bandage",
    "rampage_stim":        "coffee",
    "stim_wytrzymalosci":  "coffee",
    "fungal_pill":         "dirty_bandage",
    "morale_brew":         "coffee",
    "polymer_balm":        "dirty_bandage",
    "ration_pack":         "snack_bar",
    "chem_reagent":        "battery",
    # Weapons / armor
    "weapon_part":         "cleaver_handle",
    "kevlar_scrap":        "duct_tape",
    "branded_armor":       "kamizelka_taktyczna",
    "debt_collector_baton": "warden_baton",
    "improvised_spear":    "cheap_knife",
    "improvised_club":     "cleaver_handle",
    "liga_helmet":         "helm_konstrukcyjny",
    "weapon_poison_coat":  "battery",   # placeholder — broń/skrzynka chem
    # Tools / utility
    "lockpick":            "lockpick_set",
    "jury_tool":           "improvised_lockpick",
    "smoke_bottle":        "cracked_mug",
    "fan_throwable":       "cracked_mug",
    "camera_drone":        "broken_camera_lens",
    "ammo_box":            "battery",
    "rope_bundle":         "duct_tape",
    "megafon_propaganda":  "dead_phone",
    # Paper / data
    "cash_voucher":        "planszetka_inspektora",
    "forged_id":           "plastic_badge",
    "propaganda_zine":     "notes_windykatora",
    "blank_iou_pad":       "notes_windykatora",
    "fence_loot":          "broken_camera_lens",
    "scrap_bundle":        "duct_tape",
    # Occult / unique
    "blessed_amulet":      "amulet_szczescia",
}


def _resolve_template_key(key: str) -> str:
    """Resolve alias do canonical key z ITEM_TEMPLATES. Brak aliasu —
    zwraca oryginalny key. Used by make_item."""
    return _ITEM_ALIASES.get(key, key)


# Each item template: key -> dict of kwargs for Entity construction.
# Pola opcjonalne:
#   rarity:  common|uncommon|rare|epic|legendary  (default: common)
#   tags:    może zawierać tagi biomów (forge, trenches, zoo, ...)
ITEM_TEMPLATES = {
    "cracked_mug":     dict(tags=["mug","throwable","fragile"], portable=True,
                            affordances=["inspect","throw_at","loot"],
                            rarity="common"),
    "duct_tape":       dict(tags=["adhesive","craft_material"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="common"),
    "cheap_knife":     dict(tags=["weapon","melee","sharp"], portable=True,
                            affordances=["inspect","attack","loot"],
                            rarity="uncommon"),
    "dead_phone":      dict(tags=["electronics","junk"], portable=True,
                            affordances=["inspect","loot"],
                            rarity="common"),
    "snack_bar":       dict(tags=["food","consumable"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="common"),
    # P29.59 — credits_pile był spawnowany przez room_pool jako
    # entity_seed, ale brak template'u → display fallback do
    # 'credits pile' (English). Polski fallback_name w
    # content/data/item_templates.py.
    "credits_pile":    dict(tags=["currency","loot"], portable=True,
                            affordances=["inspect","pick_up","loot"],
                            rarity="common"),
    "plastic_badge":   dict(tags=["badge","disguise"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="common"),
    "dirty_bandage":   dict(tags=["medical","consumable"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="common"),
    "flashlight":      dict(tags=["light","tool"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="uncommon"),
    "broken_camera_lens": dict(tags=["junk","glass"], portable=True,
                            affordances=["inspect","loot"],
                            rarity="common"),
    "battery":         dict(tags=["electronics","craft_material"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="common"),
    "coffee":          dict(tags=["food","consumable"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="common"),
    "suspicious_keycard": dict(tags=["keycard","key"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="uncommon"),
    "lockpick_set":    dict(tags=["lockpick","tool"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="uncommon"),
    "improvised_lockpick": dict(tags=["lockpick","tool","junk"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="common"),
    # P24.5 — map drops. Use-handler reveals adjacent unexplored rooms;
    # floor map reveals every room on the current floor.
    "map_fragment":    dict(tags=["map","paper","sponsor_loot"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="uncommon"),
    "floor_map":       dict(tags=["map","paper","sponsor_loot"], portable=True,
                            affordances=["inspect","use","loot"],
                            rarity="rare"),
    # Misc trophies referenced by monster_salvage tables (P24).
    "warden_baton":     dict(tags=["weapon","melee","electric"], portable=True,
                            affordances=["inspect","attack","loot"],
                            rarity="uncommon"),
    "cleaver_handle":   dict(tags=["weapon","melee","sharp","junk"], portable=True,
                            affordances=["inspect","attack","loot"],
                            rarity="common"),
    "planszetka_inspektora": dict(tags=["paper","sponsor_loot","data"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="uncommon"),
    "notes_windykatora": dict(tags=["paper","sponsor_loot","data"], portable=True,
                            affordances=["inspect","loot","use"],
                            rarity="uncommon"),

    # ── P25 — wearables. Each tagged with exactly ONE `slot:X`. The
    # `equip_state` field below is folded into `Entity.state` by
    # `make_item` so equipment.slot_ac_bonus / aggregated_resists
    # read the right values.
    # HEAD (slot:head)
    "helm_konstrukcyjny": dict(tags=["slot:head","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1},
                            rarity="uncommon"),
    "czapka_uszanka":     dict(tags=["slot:head","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["cold"]},
                            rarity="common"),
    "maska_filtrujaca":   dict(tags=["slot:head","filter","trenches"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["poison"]},
                            rarity="rare"),
    "sponsor_kepi":       dict(tags=["slot:head","sponsor","badge"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="common"),

    # TORSO (slot:torso)
    "kamizelka_taktyczna": dict(tags=["slot:torso","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 2,
                                         "equip_resists":["physical"]},
                            rarity="rare"),
    "fartuch_laboratoryjny": dict(tags=["slot:torso","cloth","sponsor","clone_farm"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["acid"]},
                            rarity="uncommon"),
    "kurtka_skorzana":    dict(tags=["slot:torso","leather"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1},
                            rarity="uncommon"),
    "kombinezon_hazmat":  dict(tags=["slot:torso","hazmat","reactor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["acid","poison"],
                                         "on_equip_status":["encumbered"]},
                            rarity="epic"),

    # LEGS (slot:legs)
    "spodnie_robocze":    dict(tags=["slot:legs","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="common"),
    "buty_taktyczne":     dict(tags=["slot:legs","boots","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1},
                            rarity="uncommon"),
    "kalosze":            dict(tags=["slot:legs","rubber","insulator","sewers"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["electric"]},
                            rarity="uncommon"),

    # ACCESSORY (slot:accessory)
    "odznaka_zawodnika":  dict(tags=["slot:accessory","sponsor","badge"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="common"),
    "zegarek_sponsora":   dict(tags=["slot:accessory","sponsor","timepiece"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="uncommon"),
    "amulet_szczescia":   dict(tags=["slot:accessory","occult","museum"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="rare"),
    "opaska_imienna":     dict(tags=["slot:accessory","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="common"),

    # BACK (slot:back)
    "plecak_taktyczny":   dict(tags=["slot:back","gear"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="uncommon"),
    "pas_narzedziowy":    dict(tags=["slot:back","gear","craft_material","forge"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="uncommon"),
    "kabura_skorzana":    dict(tags=["slot:back","leather","gear"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={},
                            rarity="common"),

    # ── P29.52 — Recipe notes. Każdy ma state.recipe_key wskazujący
    # przepis do nauczenia przy `użyj`. Discovery system: gracz znajduje
    # je w pokojach typu workshop / library, dostaje od sponsora lub
    # kupuje na czarnym rynku.
    "recipe_note_shock_trap": dict(
        tags=["paper","recipe","tech"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "shock_trap"},
        rarity="uncommon"),
    "recipe_note_smoke_bottle": dict(
        tags=["paper","recipe","chemistry"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "smoke_bottle"},
        rarity="uncommon"),
    "recipe_note_fire_trap": dict(
        tags=["paper","recipe","fire"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "fire_trap_recipe"},
        rarity="rare"),
    "recipe_note_morale_brew": dict(
        tags=["paper","recipe","cooking"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "morale_brew"},
        rarity="common"),
    "recipe_note_acid_flask": dict(
        tags=["paper","recipe","chemistry"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "acid_flask_recipe"},
        rarity="rare"),
    "recipe_note_poison_dart": dict(
        tags=["paper","recipe","chemistry"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "poison_dart_recipe"},
        rarity="rare"),
    "recipe_note_garrote": dict(
        tags=["paper","recipe","stealth"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "improvised_garrote"},
        rarity="uncommon"),
    "recipe_note_taser": dict(
        tags=["paper","recipe","tech"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "improvised_taser"},
        rarity="uncommon"),
    "recipe_note_chembottle": dict(
        tags=["paper","recipe","chemistry"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "improvised_chembottle"},
        rarity="uncommon"),
    "recipe_note_silencer": dict(
        tags=["paper","recipe","tech"], portable=True,
        affordances=["inspect","loot","use","read"],
        equip_state={"recipe_key": "weapon_silencer"},
        rarity="rare"),

    # ── P29.45 — Wysokie rarity. Epic-y (5) drop'ują się z bossów F9+
    # i są lepsze niż wcześniejsze rzadkie. Legendary (6) są z final-
    # bossów i miniboss-trifekt — przeznaczone jako run-defining loot.

    # EPIC (slot:head)
    "monoklokular_kuratora": dict(
        tags=["slot:head","optic","museum","occult"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"perception_bonus": 2,
                     "equip_resists":["psychic"]},
        rarity="epic"),
    "kombinezon_strażaka_korpo": dict(
        tags=["slot:torso","hazmat","sponsor","fire"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"ac_bonus": 1,
                     "equip_resists":["fire","acid"]},
        rarity="epic"),
    "buty_z_blachy_okopowej": dict(
        tags=["slot:legs","armor","trenches"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"ac_bonus": 2,
                     "on_equip_status":["loud_step"]},
        rarity="epic"),
    "lornetka_zwiadowcza": dict(
        tags=["slot:accessory","optic","scout"], portable=True,
        affordances=["inspect","loot","wear","use"],
        equip_state={"perception_bonus": 1,
                     "scout_range_bonus": 1},
        rarity="epic"),
    "miecz_okopowy_oficera": dict(
        tags=["weapon","melee","sharp","trenches"], portable=True,
        affordances=["inspect","attack","loot"],
        equip_state={"weapon_dice": "1d10+2",
                     "vs_tag_bonus": {"humanoid": 1}},
        rarity="epic"),

    # LEGENDARY — run-defining. Każdy ma wyraźny trade-off
    # (DCC: niczego potężnego nie da się dostać za darmo).
    "krawat_konferansjera": dict(
        tags=["slot:accessory","sponsor","cursed"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"stat_bonus": {"all": 1},
                     "audience_offset": -3,
                     "konferansjer_hostile": True},
        rarity="legendary"),
    "stara_mapa_borant": dict(
        tags=["map","paper","sponsor_loot","artifact"], portable=True,
        affordances=["inspect","use","loot"],
        equip_state={"map_reveal_scope": "floor_plus_adjacent"},
        rarity="legendary"),
    "mlot_kowalski_polorka": dict(
        tags=["weapon","melee","blunt","forge","oversized"], portable=True,
        affordances=["inspect","attack","loot","break"],
        equip_state={"weapon_dice": "2d8+3",
                     "breaks_doors": True,
                     "on_equip_status":["encumbered"]},
        rarity="legendary"),
    "amulet_widza_pierwszego": dict(
        tags=["slot:accessory","occult","artifact"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"low_audience_bonus": 5,
                     "applies_below_audience": 10},
        rarity="legendary"),
    "garnitur_zarzadu": dict(
        tags=["slot:torso","sponsor","disguise","syndicate"], portable=True,
        affordances=["inspect","loot","wear"],
        equip_state={"npc_treat_as_elite": True,
                     "monster_initiative_penalty": 1,
                     "audience_offset": -1},
        rarity="legendary"),
    "plaszcz_kartograf_dluznika": dict(
        tags=["slot:back","cloth","artifact","map"], portable=True,
        affordances=["inspect","loot","wear","use"],
        equip_state={"reveal_on_floor_enter": True,
                     "audience_offset": 1},
        rarity="legendary"),
}


def make_item(key: str, location_id: str = "") -> Entity:
    """Build an item Entity. Prefers content/data/item_templates.py for
    richer fallback name/description/tags/affordances; falls back to the
    legacy ITEM_TEMPLATES dict above if no content entry exists.

    P29.43-sweep — gdy `key` nie ma w ITEM_TEMPLATES, sprawdzamy alias
    (np. „bandage" → „dirty_bandage"). Bez tego sponsor drop pody
    wystawiały gołe entity bez tagów / affordances.
    """
    proto = ITEM_TEMPLATES.get(key, {})
    if not proto:
        canonical = _resolve_template_key(key)
        if canonical != key:
            proto = ITEM_TEMPLATES.get(canonical, {})
            # Użyj canonical key w dalszej części (display_name z tabeli).
            key = canonical

    # Pull richer fallback content if available (Prompt 1)
    fb_name = key.replace("_", " ")
    fb_desc = ""
    tags = list(proto.get("tags", []))
    aff  = list(proto.get("affordances", ["inspect", "loot"]))
    try:
        from . import content_loader
        c_tmpl = content_loader.item_template(key)
    except Exception:
        c_tmpl = None
    if c_tmpl:
        fb_name = c_tmpl.get("fallback_name") or fb_name
        fb_desc = c_tmpl.get("fallback_description") or fb_desc
        # Merge tags / affordances from content layer without duplicates
        for t in c_tmpl.get("tags", []):
            if t not in tags:
                tags.append(t)
        for a in c_tmpl.get("affordances", []):
            if a not in aff:
                aff.append(a)

    ent = Entity(
        key=key, entity_type=T_ITEM,
        name_key=f"item_{key}_n", fallback_name=fb_name,
        desc_key=f"item_{key}_d", fallback_desc=fb_desc,
        location_id=location_id, portable=True,
        tags=tags,
        affordances=aff,
    )
    # P25: fold the wearable's equip_state (ac_bonus, resists, hooks)
    # into Entity.state so equipment.py reads it directly without
    # needing a parallel template lookup.
    equip_state = proto.get("equip_state")
    if equip_state:
        ent.state = dict(equip_state)
    # P29.43 — zapisujemy rarity na state, żeby UI mógł kolorować bez
    # template lookup (i żeby save/load to przeniosło). Default common.
    rarity = proto.get("rarity", "common")
    if ent.state is None:
        ent.state = {}
    ent.state.setdefault("rarity", rarity)
    return ent
