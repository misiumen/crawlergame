"""CRAWL PROTOCOL - Safehouse subtypes.

Each floor has exactly one safehouse, layered on top of the existing
checkpoint room. Subtypes never repeat on consecutive floors.

Subtypes (6, so 5-floor runs always have variety):
  cafe       - Buy small consumables. Audience boost.
  bathroom   - Stealth bonus refresh. Lore graffiti.
  lounge     - Audience-rating bump and a temporary CHA buff.
  clinic     - Paid healing per HP point.
  kiosk      - Information/intel (preview next floor type / boss tag).
  faction    - Faction-flavored hall (Step 12 polish).

Each subtype offers 2-3 interactions. Resolved by free text or numeric key.
"""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from lang import tr


SUBTYPES = ("cafe", "bathroom", "lounge", "clinic", "kiosk", "faction")


def pick_safehouse_for_floor(floor_num: int, previous_subtype: Optional[str] = None) -> str:
    """Return a subtype, never matching previous_subtype."""
    pool = [s for s in SUBTYPES if s != previous_subtype]
    # Bias by floor (clinic more common deeper)
    weights = []
    for s in pool:
        w = 10
        if s == "clinic" and floor_num >= 3:
            w = 14
        if s == "kiosk" and floor_num <= 2:
            w = 12
        weights.append(w)
    return random.choices(pool, weights=weights, k=1)[0]


def assign_subtype_to_checkpoint(room, floor_num: int, previous_subtype: Optional[str] = None):
    """Mutate a checkpoint Room to carry a safehouse subtype."""
    if room.room_type != "checkpoint":
        return
    sub = pick_safehouse_for_floor(floor_num, previous_subtype)
    room.safehouse_subtype = sub


# ── Interaction logic ─────────────────────────────────────────────────────────

def list_interactions(subtype: str) -> List[tuple]:
    """Return [(key, label_translation_key, price)] for the subtype's services."""
    return {
        "cafe": [
            ("buy_coffee",    "safe_cafe_coffee",   20),
            ("buy_meal",      "safe_cafe_meal",     40),
            ("audience_chat", "safe_cafe_chat",      0),
        ],
        "bathroom": [
            ("wash",          "safe_bath_wash",      0),
            ("read_graffiti", "safe_bath_graffiti",  0),
            ("hide_a_while",  "safe_bath_hide",      0),
        ],
        "lounge": [
            ("drink",         "safe_lounge_drink",  30),
            ("schmooze",      "safe_lounge_chat",    0),
        ],
        "clinic": [
            ("heal_10",       "safe_clinic_h10",    30),
            ("heal_full",     "safe_clinic_full",   90),
            ("cure_cond",     "safe_clinic_cure",   40),
        ],
        "kiosk": [
            ("buy_intel",     "safe_kiosk_intel",   25),
            ("buy_map",       "safe_kiosk_map",     35),
        ],
        "faction": [
            ("trade",         "safe_faction_trade",  0),
            ("intel",         "safe_faction_intel",  0),
        ],
    }.get(subtype, [])


def perform(action_key: str, player, room) -> str:
    """Execute a safehouse action. Returns a localized result line."""
    if action_key == "buy_coffee":
        if player.credits < 20:
            return tr("dialog_too_poor")
        player.credits -= 20
        player.heal(5)
        player.add_audience(3)
        return tr("safe_cafe_coffee_result")
    if action_key == "buy_meal":
        if player.credits < 40:
            return tr("dialog_too_poor")
        player.credits -= 40
        player.heal(12)
        return tr("safe_cafe_meal_result")
    if action_key == "audience_chat":
        player.add_audience(6)
        return tr("safe_cafe_chat_result")
    if action_key == "wash":
        player.heal(4)
        return tr("safe_bath_wash_result")
    if action_key == "read_graffiti":
        from procgen import random_lore
        return random_lore()
    if action_key == "hide_a_while":
        player.heal(8)
        return tr("safe_bath_hide_result")
    if action_key == "drink":
        if player.credits < 30:
            return tr("dialog_too_poor")
        player.credits -= 30
        player.add_audience(10)
        return tr("safe_lounge_drink_result")
    if action_key == "schmooze":
        player.add_audience(5)
        return tr("safe_lounge_chat_result")
    if action_key == "heal_10":
        if player.credits < 30:
            return tr("dialog_too_poor")
        player.credits -= 30
        player.heal(10)
        return tr("safe_clinic_h10_result")
    if action_key == "heal_full":
        if player.credits < 90:
            return tr("dialog_too_poor")
        player.credits -= 90
        player.hp = player.max_hp
        return tr("safe_clinic_full_result")
    if action_key == "cure_cond":
        if player.credits < 40:
            return tr("dialog_too_poor")
        player.credits -= 40
        player.conditions = []
        return tr("safe_clinic_cure_result")
    if action_key == "buy_intel":
        if player.credits < 25:
            return tr("dialog_too_poor")
        player.credits -= 25
        return tr("safe_kiosk_intel_result")
    if action_key == "buy_map":
        if player.credits < 35:
            return tr("dialog_too_poor")
        player.credits -= 35
        return tr("safe_kiosk_map_result")
    if action_key == "trade":
        player.credits += 20
        return tr("safe_faction_trade_result")
    if action_key == "intel":
        return tr("safe_faction_intel_result")
    return tr("dialog_end")
