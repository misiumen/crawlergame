"""7-Slot Equipment system (Prompt 25).

Slots:
    head     — hełmy, czapki, maski            (tag: slot:head)
    torso    — kamizelki, kombinezony           (tag: slot:torso)
    legs     — spodnie, buty                    (tag: slot:legs)
    main     — broń w głównej ręce              (P23 wield)
    off      — tarcza / pomocnicza              (P23 wield)
    acc      — odznaka, amulet, zegarek         (tag: slot:accessory)
    back     — plecak, kabura, pas              (tag: slot:back)

Worn items live on `character.worn_slots: dict[slot_key, entity_id]`.
Main/off keep their existing fields (`wielded_main_id`,
`wielded_offhand_id`) so the P23 wield handler doesn't need rewriting —
this module treats them as virtual slots and reads/writes through the
old fields.

API:
    SLOT_DEFS: ordered dict of slot definitions
    SLOT_KEYS: tuple of slot keys
    slot_for_entity(entity) → Optional[str]   (auto-detect from tags)
    can_equip(world, character, entity, slot) → (bool, reason)
    equip(world, character, entity, slot)     → (ok, prev_unequipped_id, reason)
    unequip(world, character, slot)           → (ok, freed_id, reason)
    equipped(character, slot) → Optional[entity_id]
    equipped_entity(world, character, slot)   → Optional[Entity]
    iter_worn(character)                       → iter[(slot, entity_id)]
    slot_ac_bonus(world, character, slot)      → int
    total_ac_bonus(world, character)           → int
    aggregated_resists(world, character)       → set[damage_type]
    aggregated_immunities(world, character)    → set[damage_type]
    aggregated_vulnerabilities(world, character) → set[damage_type]

Item-template extensions (P25):
    tags include exactly ONE `slot:X` for wearables (X = head/torso/legs/accessory/back).
    Optional state fields (set at template build time):
        ac_bonus:        int  — flat addition to character AC
        equip_resists:   list[str] — damage_types resisted while worn
        equip_immune_to: list[str]
        equip_vulnerable_to: list[str]
        on_equip_status: list[str] — conditions added (e.g. "encumbered")
        on_unequip_status: list[str] — conditions removed
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterable


# ── Slot definitions ──────────────────────────────────────────────────

# Stable ASCII slot keys. Display labels via dice_labels / locales.
SLOT_HEAD   = "head"
SLOT_TORSO  = "torso"
SLOT_LEGS   = "legs"
SLOT_MAIN   = "main"
SLOT_OFF    = "off"
SLOT_ACC    = "acc"
SLOT_BACK   = "back"

# Render-order tuple (matches the paper-doll grid layout).
SLOT_KEYS: Tuple[str, ...] = (
    SLOT_HEAD, SLOT_TORSO, SLOT_LEGS,
    SLOT_MAIN, SLOT_OFF,
    SLOT_ACC, SLOT_BACK,
)


@dataclass
class SlotDef:
    key: str
    label_pl: str          # display label
    short_glyph: str       # paper-doll letter
    required_tags: List[str]   # entity must have AT LEAST ONE of these
    is_wield: bool = False     # main/off use the P23 wield fields

    def accepts(self, entity) -> bool:
        if entity is None:
            return False
        tags = set(getattr(entity, "tags", []) or [])
        if self.is_wield:
            # Wield slots gate by `weapon` tag for main; `shield` or
            # `offhand_only` or `one_handed` for off. We delegate the
            # finer gating to the existing P23 wield handler.
            return "weapon" in tags or "shield" in tags
        return any(t in tags for t in self.required_tags)


SLOT_DEFS: Dict[str, SlotDef] = {
    SLOT_HEAD:  SlotDef(SLOT_HEAD,  "Głowa",        "H", ["slot:head"]),
    SLOT_TORSO: SlotDef(SLOT_TORSO, "Tors",         "T", ["slot:torso"]),
    SLOT_LEGS:  SlotDef(SLOT_LEGS,  "Nogi",         "L", ["slot:legs"]),
    SLOT_MAIN:  SlotDef(SLOT_MAIN,  "Główna ręka",  "M", ["weapon"], is_wield=True),
    SLOT_OFF:   SlotDef(SLOT_OFF,   "Pomocnicza",   "O", ["weapon", "shield"], is_wield=True),
    SLOT_ACC:   SlotDef(SLOT_ACC,   "Akcesorium",   "A", ["slot:accessory"]),
    SLOT_BACK:  SlotDef(SLOT_BACK,  "Plecy",        "B", ["slot:back"]),
}


def is_wearable(entity) -> bool:
    """True iff the entity carries any slot:* tag (i.e. it can land in
    one of the 5 non-wield slots). Wield gates separately."""
    if entity is None:
        return False
    return any(t.startswith("slot:")
               for t in (getattr(entity, "tags", []) or []))


def slot_for_entity(entity) -> Optional[str]:
    """Auto-detect which slot an entity targets. Returns the first
    matching slot key, or None if no slot:* tag is present. Falls back
    to wield slots only if the entity has no slot:* tag AND has the
    `weapon` tag (callers usually go through P23 wield in that case).
    """
    if entity is None:
        return None
    tags = list(getattr(entity, "tags", []) or [])
    # Tag suffix → slot_key. `slot:accessory` is shortened to `acc`
    # for the slot key (keeps paper-doll glyph compact) but the human-
    # readable tag uses the full word.
    TAG_TO_SLOT = {
        "head": SLOT_HEAD,
        "torso": SLOT_TORSO,
        "legs": SLOT_LEGS,
        "accessory": SLOT_ACC,
        "acc": SLOT_ACC,
        "back": SLOT_BACK,
        "main": SLOT_MAIN,
        "off": SLOT_OFF,
    }
    for t in tags:
        if not t.startswith("slot:"):
            continue
        suffix = t.split(":", 1)[1]
        slot = TAG_TO_SLOT.get(suffix)
        if slot is not None and slot in SLOT_DEFS:
            return slot
    # Fallback: if it's a weapon and has no slot:* tag, suggest main hand.
    if "weapon" in tags:
        return SLOT_MAIN
    return None


# ── Equip / unequip / read ────────────────────────────────────────────

def _get_worn_slots(character) -> Dict[str, int]:
    """Return the character's worn_slots dict, creating if missing."""
    if not hasattr(character, "worn_slots") or character.worn_slots is None:
        character.worn_slots = {}
    return character.worn_slots


def equipped(character, slot: str) -> Optional[int]:
    """Return the entity_id worn in the given slot, or None."""
    if character is None or slot not in SLOT_DEFS:
        return None
    sd = SLOT_DEFS[slot]
    if sd.is_wield:
        if slot == SLOT_MAIN:
            return getattr(character, "wielded_main_id", None)
        return getattr(character, "wielded_offhand_id", None)
    return _get_worn_slots(character).get(slot)


def equipped_entity(world, character, slot: str):
    eid = equipped(character, slot)
    if eid is None or world is None:
        return None
    return world.get(eid)


def iter_worn(character) -> Iterable[Tuple[str, int]]:
    """Walk all 7 slots, yielding (slot_key, entity_id) for each
    occupied one."""
    for slot in SLOT_KEYS:
        eid = equipped(character, slot)
        if eid is not None:
            yield (slot, eid)


def can_equip(world, character, entity, slot: str) -> Tuple[bool, str]:
    """Validate whether `entity` can be placed in `slot`. Returns
    (ok, reason). Reason is "" on success, otherwise a Polish refusal
    string."""
    if entity is None:
        return False, "Brak przedmiotu."
    if slot not in SLOT_DEFS:
        return False, f"Slot „{slot}” nie istnieje."
    sd = SLOT_DEFS[slot]
    if sd.is_wield:
        # Delegate to P23 wield rules — main is any weapon, off must be
        # one_handed / shield / offhand_only.
        return True, ""
    if not sd.accepts(entity):
        return False, f"„{entity.display_name()}” nie pasuje do slotu „{sd.label_pl}”."
    # Entity must be in the player's inventory (or already in the slot
    # — re-equipping is a no-op).
    if character is not None:
        cur = equipped(character, slot)
        if cur == entity.entity_id:
            return True, ""
        inv = list(getattr(character, "inventory_ids", []) or [])
        if entity.entity_id not in inv:
            return False, "Tego nie masz przy sobie."
    return True, ""


def equip(world, character, entity, slot: str) -> Tuple[bool, Optional[int], str]:
    """Move `entity` into `slot`, displacing any current occupant back
    to inventory. Returns (ok, prev_unequipped_id, reason).

    For main/off slots, sets the existing P23 fields and lets the
    standard wield path keep working.
    """
    ok, reason = can_equip(world, character, entity, slot)
    if not ok:
        return False, None, reason
    sd = SLOT_DEFS[slot]
    prev_id = equipped(character, slot)
    # If something else is in the slot, unequip it first.
    if prev_id is not None and prev_id != entity.entity_id:
        _set_slot(character, slot, None)
        _return_to_inventory(character, prev_id)
    _set_slot(character, slot, entity.entity_id)
    # Wear items move out of the inventory_ids list — they're worn, not
    # carried. (Wield uses the same convention via P23.) Remove without
    # raising if absent (re-equip case).
    try:
        character.inventory_ids.remove(entity.entity_id)
    except (ValueError, AttributeError):
        pass
    # Hooks: on_equip_status conditions, equip-time effects (future
    # encumbrance, etc.).
    _apply_equip_hooks(world, character, entity, equip=True)
    return True, prev_id, ""


def unequip(world, character, slot: str) -> Tuple[bool, Optional[int], str]:
    """Remove the item from `slot` back to inventory. Returns
    (ok, freed_id, reason)."""
    eid = equipped(character, slot)
    if eid is None:
        return False, None, "Slot pusty."
    ent = world.get(eid) if world is not None else None
    _set_slot(character, slot, None)
    _return_to_inventory(character, eid)
    if ent is not None:
        _apply_equip_hooks(world, character, ent, equip=False)
    return True, eid, ""


def _set_slot(character, slot: str, eid: Optional[int]) -> None:
    sd = SLOT_DEFS[slot]
    if sd.is_wield:
        if slot == SLOT_MAIN:
            character.wielded_main_id = eid
        else:
            character.wielded_offhand_id = eid
    else:
        worn = _get_worn_slots(character)
        if eid is None:
            worn.pop(slot, None)
        else:
            worn[slot] = int(eid)


def _return_to_inventory(character, eid: int) -> None:
    """Push an entity back into inventory_ids if not already there."""
    if not hasattr(character, "inventory_ids") or character.inventory_ids is None:
        character.inventory_ids = []
    if eid not in character.inventory_ids:
        character.inventory_ids.append(int(eid))


def _apply_equip_hooks(world, character, entity, *, equip: bool) -> None:
    """Apply on_equip / on_unequip status side-effects, if the entity
    declares them in its state."""
    if entity is None or entity.state is None:
        return
    if equip:
        for status in (entity.state.get("on_equip_status") or []):
            if hasattr(character, "conditions"):
                if character.conditions is None:
                    character.conditions = []
                if status not in character.conditions:
                    character.conditions.append(status)
    else:
        for status in (entity.state.get("on_equip_status") or []):
            if hasattr(character, "conditions") and character.conditions:
                if status in character.conditions:
                    character.conditions.remove(status)


# ── Aggregated effects ────────────────────────────────────────────────

def slot_ac_bonus(world, character, slot: str) -> int:
    """Return the AC bonus contributed by the item currently in `slot`.
    Reads `ac_bonus` from the entity's `state` dict."""
    ent = equipped_entity(world, character, slot)
    if ent is None or ent.state is None:
        return 0
    try:
        return int(ent.state.get("ac_bonus", 0) or 0)
    except (TypeError, ValueError):
        return 0


def total_ac_bonus(world, character) -> int:
    """Sum AC bonuses across every worn slot (incl. main/off — a shield
    in off naturally pairs here; main weapons rarely contribute AC but
    the addition is safe because most have ac_bonus=0)."""
    total = 0
    for slot in SLOT_KEYS:
        total += slot_ac_bonus(world, character, slot)
    return total


def _aggregate_state_list(world, character, key: str) -> List[str]:
    out: List[str] = []
    for slot in SLOT_KEYS:
        ent = equipped_entity(world, character, slot)
        if ent is None or ent.state is None:
            continue
        vals = ent.state.get(key) or []
        for v in vals:
            if v not in out:
                out.append(v)
    return out


def aggregated_resists(world, character) -> List[str]:
    return _aggregate_state_list(world, character, "equip_resists")


def aggregated_immunities(world, character) -> List[str]:
    return _aggregate_state_list(world, character, "equip_immune_to")


def aggregated_vulnerabilities(world, character) -> List[str]:
    return _aggregate_state_list(world, character, "equip_vulnerable_to")


# ── Inventory popover support ─────────────────────────────────────────

def eligible_inventory_for_slot(world, character, slot: str) -> List:
    """Return a list of inventory entities that could be equipped in
    `slot`. Used by the paper-doll click popover."""
    if world is None or character is None or slot not in SLOT_DEFS:
        return []
    sd = SLOT_DEFS[slot]
    out = []
    inv = list(getattr(character, "inventory_ids", []) or [])
    for eid in inv:
        ent = world.get(eid)
        if ent is None:
            continue
        if sd.is_wield:
            # Wield popover offers any item with the right wield-class
            # tag. Two-handed weapons are eligible for main only.
            tags = set(ent.tags or [])
            if slot == SLOT_MAIN:
                if "weapon" in tags:
                    out.append(ent)
            else:
                if "shield" in tags or "offhand_only" in tags or \
                   ("weapon" in tags and "one_handed" in tags):
                    out.append(ent)
        else:
            if sd.accepts(ent):
                out.append(ent)
    return out
