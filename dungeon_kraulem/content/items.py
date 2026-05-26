"""Item templates and helpers."""
from ..engine.entity import Entity, T_ITEM


# Each item template: key -> dict of kwargs for Entity construction
ITEM_TEMPLATES = {
    "cracked_mug":     dict(tags=["mug","throwable","fragile"], portable=True,
                            affordances=["inspect","throw_at","loot"]),
    "duct_tape":       dict(tags=["adhesive","craft_material"], portable=True,
                            affordances=["inspect","use","loot"]),
    "cheap_knife":     dict(tags=["weapon","melee","sharp"], portable=True,
                            affordances=["inspect","attack","loot"]),
    "dead_phone":      dict(tags=["electronics","junk"], portable=True,
                            affordances=["inspect","loot"]),
    "snack_bar":       dict(tags=["food","consumable"], portable=True,
                            affordances=["inspect","use","loot"]),
    "plastic_badge":   dict(tags=["badge","disguise"], portable=True,
                            affordances=["inspect","loot","use"]),
    "dirty_bandage":   dict(tags=["medical","consumable"], portable=True,
                            affordances=["inspect","use","loot"]),
    "flashlight":      dict(tags=["light","tool"], portable=True,
                            affordances=["inspect","use","loot"]),
    "broken_camera_lens": dict(tags=["junk","glass"], portable=True,
                            affordances=["inspect","loot"]),
    "battery":         dict(tags=["electronics","craft_material"], portable=True,
                            affordances=["inspect","loot","use"]),
    "coffee":          dict(tags=["food","consumable"], portable=True,
                            affordances=["inspect","use","loot"]),
    "suspicious_keycard": dict(tags=["keycard","key"], portable=True,
                            affordances=["inspect","loot","use"]),
    "lockpick_set":    dict(tags=["lockpick","tool"], portable=True,
                            affordances=["inspect","loot","use"]),
    "improvised_lockpick": dict(tags=["lockpick","tool","junk"], portable=True,
                            affordances=["inspect","loot","use"]),
    # P24.5 — map drops. Use-handler reveals adjacent unexplored rooms;
    # floor map reveals every room on the current floor.
    "map_fragment":    dict(tags=["map","paper","sponsor_loot"], portable=True,
                            affordances=["inspect","use","loot"]),
    "floor_map":       dict(tags=["map","paper","sponsor_loot","rare"], portable=True,
                            affordances=["inspect","use","loot"]),
    # Misc trophies referenced by monster_salvage tables (P24).
    "warden_baton":     dict(tags=["weapon","melee","electric"], portable=True,
                            affordances=["inspect","attack","loot"]),
    "cleaver_handle":   dict(tags=["weapon","melee","sharp","junk"], portable=True,
                            affordances=["inspect","attack","loot"]),
    "planszetka_inspektora": dict(tags=["paper","sponsor_loot","data"], portable=True,
                            affordances=["inspect","loot","use"]),
    "notes_windykatora": dict(tags=["paper","sponsor_loot","data"], portable=True,
                            affordances=["inspect","loot","use"]),

    # ── P25 — wearables. Each tagged with exactly ONE `slot:X`. The
    # `equip_state` field below is folded into `Entity.state` by
    # `make_item` so equipment.slot_ac_bonus / aggregated_resists
    # read the right values.
    # HEAD (slot:head)
    "helm_konstrukcyjny": dict(tags=["slot:head","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1}),
    "czapka_uszanka":     dict(tags=["slot:head","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["cold"]}),
    "maska_filtrujaca":   dict(tags=["slot:head","filter"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["poison"]}),
    "sponsor_kepi":       dict(tags=["slot:head","sponsor","badge"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),

    # TORSO (slot:torso)
    "kamizelka_taktyczna": dict(tags=["slot:torso","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 2,
                                         "equip_resists":["physical"]}),
    "fartuch_laboratoryjny": dict(tags=["slot:torso","cloth","sponsor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["acid"]}),
    "kurtka_skorzana":    dict(tags=["slot:torso","leather"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1}),
    "kombinezon_hazmat":  dict(tags=["slot:torso","hazmat"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["acid","poison"],
                                         "on_equip_status":["encumbered"]}),

    # LEGS (slot:legs)
    "spodnie_robocze":    dict(tags=["slot:legs","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "buty_taktyczne":     dict(tags=["slot:legs","boots","armor"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"ac_bonus": 1}),
    "kalosze":            dict(tags=["slot:legs","rubber","insulator"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={"equip_resists":["electric"]}),

    # ACCESSORY (slot:accessory)
    "odznaka_zawodnika":  dict(tags=["slot:accessory","sponsor","badge"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "zegarek_sponsora":   dict(tags=["slot:accessory","sponsor","timepiece"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "amulet_szczescia":   dict(tags=["slot:accessory","occult"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "opaska_imienna":     dict(tags=["slot:accessory","cloth"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),

    # BACK (slot:back)
    "plecak_taktyczny":   dict(tags=["slot:back","gear"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "pas_narzedziowy":    dict(tags=["slot:back","gear","craft_material"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
    "kabura_skorzana":    dict(tags=["slot:back","leather","gear"], portable=True,
                            affordances=["inspect","loot","wear"],
                            equip_state={}),
}


def make_item(key: str, location_id: str = "") -> Entity:
    """Build an item Entity. Prefers content/data/item_templates.py for
    richer fallback name/description/tags/affordances; falls back to the
    legacy ITEM_TEMPLATES dict above if no content entry exists."""
    proto = ITEM_TEMPLATES.get(key, {})

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
    return ent
