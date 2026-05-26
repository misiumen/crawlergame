"""P27.7 — class features (passive + active).

Each class in CLASS_CATALOG (systems/classes.py) gets one passive bonus
that the engine queries via `passive_bonus(char, kind)` and one active
ability triggered by the `umiejętność` verb. Actives share a per-floor
cooldown stored on `character.flags["class_active_used_on_floor"]`.

Design notes
------------
* Passives are read at query time — they don't mutate stats. That way
  classes can be assigned mid-floor without re-stating the character.
* Actives mutate world state (heal, status, etc.) and stamp the active
  cooldown flag. They refuse if already used this floor.
* Both passives and actives are exposed through a single registry so a
  future UI button or skill-tree screen can iterate them.
"""
from __future__ import annotations
from typing import Dict, Tuple, Optional


# ── Passive table ────────────────────────────────────────────────────────
# kind names are sniffed at the engine call sites. Values are additive.
#
# Currently sniffed:
#   "hp_max"        — added to base max_hp after stats roll
#   "ac"            — added to effective_ac
#   "unarmed_dmg"   — extra damage when fighting unarmed
#   "ranged_hit"    — to-hit bonus on ranged attacks
#   "crafting"      — to-hit bonus on craft / repair rolls
#   "heal_mul"      — multiplier on bandage / consumable heal
#   "audience_mul"  — multiplier on audience_rating gains
#   "stealth_init"  — extra noise dampening
#   "social"        — to-hit on negotiate / persuade rolls
#   "trap_crit"     — extra crit chance on traps
#   "mental_resist" — flat resist to mental statuses
CLASS_PASSIVES: Dict[str, Dict[str, int]] = {
    "bruiser":       {"hp_max": 20, "unarmed_dmg": 2},
    "survivor":      {"hp_max": 10, "ac": 1},
    "saboteur":      {"trap_crit": 2},
    "engineer":      {"crafting": 2},
    "ranger":        {"ranged_hit": 2},
    "medic":         {"heal_mul": 1},          # +100% bandage heal
    "occultist":     {"mental_resist": 1},
    "negotiator":    {"social": 2},
    "trickster":     {"stealth_init": 2, "social": 1},
    "demolitionist": {"unarmed_dmg": 1, "trap_crit": 1},
    "showman":       {"audience_mul": 1},      # ×2 audience gain
    "scout":         {"stealth_init": 1, "ranged_hit": 1},
}


# ── Active table ─────────────────────────────────────────────────────────
# Each entry: (name_pl, desc_pl, handler_key)
CLASS_ACTIVES: Dict[str, Tuple[str, str, str]] = {
    "bruiser":       ("Brutalna szarża",   "Następny atak zadaje podwójne obrażenia.", "buff_next_attack_x2"),
    "survivor":      ("Drugi oddech",      "Leczy 35% maks. HP.",                       "heal_pct_35"),
    "saboteur":      ("Sabotaż",           "Rozkłada darmową pułapkę „shock_pad”.",     "place_trap_shock"),
    "engineer":      ("Szybka naprawa",    "Naprawia jedną złamaną strefę u sojusznika lub u ciebie.", "repair_one_zone"),
    "ranger":        ("Precyzyjny strzał", "Następny atak dystansowy automatycznie trafia.", "buff_next_ranged_hit"),
    "medic":         ("Triage",            "Leczy 60% maks. HP i usuwa „bleeding”.",    "heal_pct_60_clear_bleed"),
    "occultist":     ("Klątwa",            "Wrogowie w pokoju dostają -2 do ataku na 3 rundy.", "curse_room_atk_minus2"),
    "negotiator":    ("Targi",             "+5 do następnego rzutu społecznego.",       "buff_next_social"),
    "trickster":     ("Znikanie",          "Stajesz się ukryty dla najbliższego spotkania.", "set_hidden_for_encounter"),
    "demolitionist": ("Wybuch",            "AoE 15 obrażeń wszystkim wrogom w pokoju.", "aoe_dmg_15"),
    "showman":       ("Hype",              "+8 audience teraz, +2 do następnego stand-upu.", "audience_bump_8"),
    "scout":         ("Mapowanie",         "Odsłania wszystkie pokoje na bieżącym piętrze.", "reveal_floor"),
}


# ── Public API ───────────────────────────────────────────────────────────

def passive_bonus(character, kind: str) -> int:
    """Return the additive passive bonus from the character's current
    class for the given kind. 0 if no class or kind not registered."""
    key = getattr(character, "class_key", None)
    if not key:
        return 0
    return CLASS_PASSIVES.get(key, {}).get(kind, 0)


def heal_multiplier(character) -> float:
    """Convenience: heal_mul passive returns +N (where N is fractional
    bonus). Engine multiplies amount by (1 + N)."""
    return 1.0 + float(passive_bonus(character, "heal_mul"))


def audience_multiplier(character) -> float:
    return 1.0 + float(passive_bonus(character, "audience_mul"))


def can_use_active(world) -> Tuple[bool, str]:
    """Did we use our class active on the current floor already?"""
    ch = world.character
    if not getattr(ch, "class_key", None):
        return False, "Nie masz jeszcze klasy."
    fnum = getattr(world.current_floor, "floor_number", None) if world.current_floor else None
    used = ch.flags.get("class_active_used_on_floor")
    if used is not None and used == fnum:
        return False, "Już użyłeś tej umiejętności na tym piętrze."
    return True, ""


def use_active(world) -> Tuple[bool, str]:
    """Trigger the character's class active. Returns (ok, log_line)."""
    ok, reason = can_use_active(world)
    if not ok:
        return False, reason
    ch = world.character
    spec = CLASS_ACTIVES.get(ch.class_key)
    if not spec:
        return False, "Twoja klasa nie ma aktywnej umiejętności."
    name, desc, handler = spec
    line = _dispatch(world, handler, name)
    if not line:
        return False, "Nic się nie wydarzyło."
    # Stamp cooldown.
    fnum = getattr(world.current_floor, "floor_number", None) if world.current_floor else None
    ch.flags["class_active_used_on_floor"] = fnum
    return True, line


def active_label(character) -> Optional[str]:
    key = getattr(character, "class_key", None)
    if not key:
        return None
    spec = CLASS_ACTIVES.get(key)
    return spec[0] if spec else None


def active_description(character) -> Optional[str]:
    key = getattr(character, "class_key", None)
    if not key:
        return None
    spec = CLASS_ACTIVES.get(key)
    return spec[1] if spec else None


# ── Handlers ─────────────────────────────────────────────────────────────

def _dispatch(world, key: str, name: str) -> str:
    """Run an active handler and return the log line, or empty on no-op."""
    fn = _HANDLERS.get(key)
    if fn is None:
        return ""
    return fn(world, name) or ""


def _h_buff_next_attack_x2(world, name):
    world.character.flags["class_buff_next_attack_x2"] = True
    return f"„{name}” — następny atak zada podwójne obrażenia."


def _h_heal_pct_35(world, name):
    ch = world.character
    pre = ch.hp
    amount = max(1, int(ch.max_hp * 0.35))
    ch.heal(amount)
    return f"„{name}” — leczysz się o {ch.hp - pre} HP ({ch.hp}/{ch.max_hp})."


def _h_heal_pct_60_clear_bleed(world, name):
    ch = world.character
    pre = ch.hp
    amount = max(1, int(ch.max_hp * 0.60))
    ch.heal(amount)
    cleared = False
    if "bleeding" in ch.conditions:
        ch.conditions = [c for c in ch.conditions if c != "bleeding"]
        cleared = True
    msg = f"„{name}” — leczysz {ch.hp - pre} HP ({ch.hp}/{ch.max_hp})."
    if cleared:
        msg += " Krwawienie ustaje."
    return msg


def _h_place_trap_shock(world, name):
    room = world.current_floor.current_room() if world.current_floor else None
    if room is None:
        return ""
    traps = room.state.setdefault("player_traps", [])
    traps.append({
        "key": "shock_pad", "entity_id": -1,
        "display_name": "elektrokoc", "tags": ["shock"],
        "quality": "normal", "armed_at": world.current_floor.current_minute,
        "level": "success", "triggered": False,
        "effect": {"type": "damage", "amount": 25},
    })
    return f"„{name}” — rozkładasz elektrokoc na progu."


def _h_repair_one_zone(world, name):
    ch = world.character
    # Try to clear ONE of the player's broken-zone statuses.
    for cond in ("disarmed", "slowed", "stunned"):
        if cond in ch.conditions:
            ch.conditions = [c for c in ch.conditions if c != cond]
            return f"„{name}” — usuwasz stan {cond}."
    return f"„{name}” — nie ma nic do naprawienia."


def _h_buff_next_ranged_hit(world, name):
    world.character.flags["class_buff_next_ranged_auto_hit"] = True
    return f"„{name}” — następny strzał trafi automatycznie."


def _h_curse_room_atk_minus2(world, name):
    room = world.current_floor.current_room() if world.current_floor else None
    if room is None:
        return ""
    from ..engine import combat as _cmb
    cursed = 0
    for ent in room.entities:
        if getattr(ent, "entity_type", "") == "monster" and ent.is_alive():
            _cmb.add_status(ent, "cursed_atk_m2", 3)
            cursed += 1
    return f"„{name}” — klątwa dotyka {cursed} wrog{'a' if cursed == 1 else 'ów'}."


def _h_buff_next_social(world, name):
    world.character.flags["class_buff_next_social_plus5"] = True
    return f"„{name}” — następny rzut społeczny dostanie +5."


def _h_set_hidden_for_encounter(world, name):
    world.character.flags["hidden_for_encounter"] = True
    return f"„{name}” — znikasz w cieniu. Następne spotkanie cię nie znajdzie."


def _h_aoe_dmg_15(world, name):
    room = world.current_floor.current_room() if world.current_floor else None
    if room is None:
        return ""
    hit = 0
    for ent in list(room.entities):
        if getattr(ent, "entity_type", "") == "monster" and ent.is_alive():
            ent.take_damage(15)
            hit += 1
    return f"„{name}” — eksplozja rani {hit} wrog{'a' if hit == 1 else 'ów'} po 15 HP."


def _h_audience_bump_8(world, name):
    world.character.audience_rating += 8
    world.character.flags["class_buff_next_standup_plus2"] = True
    return f"„{name}” — viewerów przybywa (+8 audience)."


def _h_reveal_floor(world, name):
    f = world.current_floor
    if f is None:
        return ""
    revealed = 0
    for r in f.rooms.values():
        if not r.state.get("explored"):
            r.state["explored"] = True
            revealed += 1
    return f"„{name}” — mapujesz piętro. Odsłonięto {revealed} pokoi."


_HANDLERS = {
    "buff_next_attack_x2":         _h_buff_next_attack_x2,
    "heal_pct_35":                 _h_heal_pct_35,
    "heal_pct_60_clear_bleed":     _h_heal_pct_60_clear_bleed,
    "place_trap_shock":            _h_place_trap_shock,
    "repair_one_zone":             _h_repair_one_zone,
    "buff_next_ranged_hit":        _h_buff_next_ranged_hit,
    "curse_room_atk_minus2":       _h_curse_room_atk_minus2,
    "buff_next_social":            _h_buff_next_social,
    "set_hidden_for_encounter":    _h_set_hidden_for_encounter,
    "aoe_dmg_15":                  _h_aoe_dmg_15,
    "audience_bump_8":             _h_audience_bump_8,
    "reveal_floor":                _h_reveal_floor,
}
