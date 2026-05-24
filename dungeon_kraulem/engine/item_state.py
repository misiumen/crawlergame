"""Item condition helpers (Prompt 06a, gap #7).

Items in the revamp engine are `Entity` instances whose `state` dict can
carry condition flags. This module standardises how those flags are read,
written, and surfaced to the player.

Schema applied opportunistically to entity.state:
  damaged          : bool       -- single-bit flag for narrative effects
  damage_count     : int        -- how many times damaged (informational)
  durability       : int|None   -- remaining hits; None = not tracked
  max_durability   : int|None
  unstable         : bool       -- damaged AND can produce extra failure

Mechanical effects (small, never instant-kill):
  weapon  damaged  -> -1 to_hit modifier and damage penalty 1
  tool    damaged  -> -1 to skill check
  armor   damaged  -> -1 AC bonus
  consumable damaged -> 50% chance of safe use, 50% chance of dud

Lookups are tolerant: missing fields default to "not damaged".
"""
from typing import Optional


# ── Predicates ────────────────────────────────────────────────────────────────

def is_item_damaged(item) -> bool:
    """True if the item carries any damaged-ness."""
    if item is None:
        return False
    state = getattr(item, "state", None) or {}
    if state.get("damaged"):
        return True
    dur = state.get("durability")
    if dur is not None and dur <= 0:
        return True
    return False


def is_item_unstable(item) -> bool:
    state = getattr(item, "state", None) or {}
    return bool(state.get("unstable"))


# ── Mutation ─────────────────────────────────────────────────────────────────

def damage_item(item, amount: int = 1) -> bool:
    """Apply `amount` points of damage. Returns True if the item became
    newly damaged this call."""
    if item is None:
        return False
    item.state = getattr(item, "state", None) or {}
    was_damaged = is_item_damaged(item)
    item.state["damage_count"] = int(item.state.get("damage_count", 0)) + amount
    # Hard durability decrement
    dur = item.state.get("durability")
    if dur is not None:
        item.state["durability"] = max(0, int(dur) - amount)
    # Damaged flag latches after first hit
    if not item.state.get("damaged"):
        item.state["damaged"] = True
    # Two hits -> unstable
    if item.state["damage_count"] >= 2:
        item.state["unstable"] = True
    return not was_damaged


def repair_item(item, amount: int = 1) -> bool:
    """Repair `amount` points. Returns True if the item is now usable again."""
    if item is None:
        return False
    item.state = getattr(item, "state", None) or {}
    if "durability" in item.state and item.state["durability"] is not None:
        item.state["durability"] = min(
            int(item.state.get("max_durability", 99)),
            int(item.state["durability"]) + amount,
        )
    item.state["damage_count"] = max(0, int(item.state.get("damage_count", 0)) - amount)
    if item.state["damage_count"] <= 0:
        item.state["damaged"] = False
        item.state["unstable"] = False
    return not is_item_damaged(item)


# ── Display + modifiers ──────────────────────────────────────────────────────

def describe_item_condition(item) -> str:
    """One-line Polish summary of the item's wear."""
    if item is None or not is_item_damaged(item):
        return ""
    state = item.state
    if state.get("unstable"):
        return "(uszkodzone, niestabilne)"
    return "(uszkodzone)"


def attack_modifier(weapon) -> int:
    """Penalty to attack rolls when the weapon is damaged."""
    if not is_item_damaged(weapon):
        return 0
    return -2 if is_item_unstable(weapon) else -1


def damage_modifier(weapon) -> int:
    """Penalty to damage rolls when the weapon is damaged."""
    if not is_item_damaged(weapon):
        return 0
    return -2 if is_item_unstable(weapon) else -1


def skill_modifier(tool) -> int:
    """Penalty to skill checks when the tool is damaged."""
    if not is_item_damaged(tool):
        return 0
    return -2 if is_item_unstable(tool) else -1


def ac_modifier(armor) -> int:
    """Penalty to AC when the armor is damaged."""
    if not is_item_damaged(armor):
        return 0
    return -1


def consumable_safe(consumable) -> bool:
    """Return True if a damaged consumable can be used safely this time
    (50/50 if damaged, always True if intact)."""
    if not is_item_damaged(consumable):
        return True
    import random
    return random.random() >= 0.5
