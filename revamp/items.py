"""Item templates and helpers."""
from .entity import Entity, T_ITEM


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
}


def make_item(key: str, location_id: str = "") -> Entity:
    proto = ITEM_TEMPLATES.get(key, {})
    return Entity(
        key=key, entity_type=T_ITEM,
        name_key=f"item_{key}_n", fallback_name=key.replace("_"," "),
        desc_key=f"item_{key}_d", fallback_desc="",
        location_id=location_id, portable=True,
        tags=list(proto.get("tags", [])),
        affordances=list(proto.get("affordances", ["inspect","loot"])),
    )
