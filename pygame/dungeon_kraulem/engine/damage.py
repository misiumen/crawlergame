"""Prompt 21 — Damage type registry + apply_damage + status pipeline.

The engine had only `damage_dice` (an amount) and a handful of statuses
that weren't connected to anything elemental. This module adds the
missing axis: **what KIND of damage was that?**

Design constraints (from the design conversation):

1. **Extensible registry, not enum.** Future prompts can add `kinetic`,
   `crush`, `magnetic`, etc. without touching engine code — they just
   call `register_damage_type(...)` from content data.

2. **Statuses persist out of combat, decay at half rate.** A burning
   player who flees combat keeps burning for a while at half tick.

3. **Resistance / vulnerability / immunity** all live as lists on
   Entity (added in Prompt 21). Resistance halves damage; vulnerability
   doubles it; immunity zeroes it. Immunity wins over vulnerability if
   both are listed (paranoid content).

4. **Status apply is opportunistic, not forced.** Some damage types
   *can* apply a status but only when the hit lands AND the target
   isn't immune. Caller can opt out with `apply_status=False`.

`Entity.damage_type` (default "physical") is the kind THIS entity
deals when it attacks. The same registry covers both incoming and
outgoing damage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Status interaction (small table) ──────────────────────────────────────
# Status keys are the same strings used by combat.add_status / has_status
# / target.conditions. New statuses added by Prompt 21 are listed here
# so the duration system has a single source of truth.

STATUS_DURATIONS_TURNS: Dict[str, int] = {
    # Existing statuses (durations were inline in callers; now centralized).
    "prone":            1,
    "stunned":          2,
    "blinded":          2,
    "bleeding":         5,
    "behind_cover":     2,
    "afraid":           3,
    "shocked":          2,
    "wounded":          3,
    # Prompt 21 — new statuses.
    "burning":          3,    # DOT, can spread via flammable tag
    "corroded":         8,    # AC reduction; persists ACROSS combat
    "poisoned":         5,    # DOT, cured by antidote item
    "chilled":          3,    # halves DEX-derived stats
}

# Statuses that persist between combats (do not auto-clear when combat
# ends; out-of-combat decay tick reduces them). Everything else clears.
STATUS_PERSISTS_OUT_OF_COMBAT = frozenset({
    "burning", "bleeding", "poisoned", "corroded", "wounded",
})

# DOT statuses — drain HP per tick. Mapping: status -> damage per turn.
STATUS_DOT_PER_TURN: Dict[str, int] = {
    "burning":   2,
    "bleeding":  1,
    "poisoned":  1,
}


# ── Damage type registry ──────────────────────────────────────────────────

@dataclass
class DamageType:
    key: str
    label_pl: str
    label_en: str
    applies_status: Optional[str] = None     # status to add on hit
    status_duration_turns: int = 0           # 0 = use STATUS_DURATIONS default
    ignites_tags: List[str] = field(default_factory=list)
    extinguished_by_tags: List[str] = field(default_factory=list)
    audience_tag: str = ""                   # sponsor tag emitted on hit


_REGISTRY: Dict[str, DamageType] = {}


def register_damage_type(dt: DamageType) -> DamageType:
    """Add or override a damage type. Content code can call this at
    import time to extend the registry — engine code doesn't need to
    change for new types."""
    _REGISTRY[dt.key] = dt
    return dt


def get_damage_type(key: str) -> DamageType:
    """Return the damage type entry, or the physical default for unknown
    keys. Never raises."""
    return _REGISTRY.get(key) or _REGISTRY["physical"]


def all_damage_types() -> List[str]:
    return list(_REGISTRY.keys())


# ── Seed the seven v1 types ───────────────────────────────────────────────

register_damage_type(DamageType(
    key="physical", label_pl="fizyczne", label_en="physical",
    applies_status=None,
    audience_tag="",
))
register_damage_type(DamageType(
    key="fire", label_pl="ogień", label_en="fire",
    applies_status="burning",
    status_duration_turns=3,
    ignites_tags=["flammable","wood","paper","oil","cloth","alcohol"],
    extinguished_by_tags=["wet","water","ice"],
    audience_tag="spectacle",
))
register_damage_type(DamageType(
    key="electric", label_pl="elektryczne", label_en="electric",
    applies_status="shocked",
    status_duration_turns=2,
    audience_tag="spectacle",
))
register_damage_type(DamageType(
    key="acid", label_pl="żrące", label_en="acid",
    applies_status="corroded",
    status_duration_turns=8,
    audience_tag="chemical",
))
register_damage_type(DamageType(
    key="poison", label_pl="toksyczne", label_en="poison",
    applies_status="poisoned",
    status_duration_turns=5,
    audience_tag="chemical",
))
register_damage_type(DamageType(
    key="cold", label_pl="zimno", label_en="cold",
    applies_status="chilled",
    status_duration_turns=3,
    audience_tag="",
))
register_damage_type(DamageType(
    key="psychic", label_pl="psychiczne", label_en="psychic",
    applies_status="afraid",
    status_duration_turns=3,
    audience_tag="",
))


# ── apply_damage ──────────────────────────────────────────────────────────

def apply_damage(world, target, amount: int,
                 damage_type: str = "physical",
                 *,
                 source: str = "",
                 apply_status: bool = True) -> Dict[str, Any]:
    """Deal `amount` of `damage_type` damage to `target`. Returns a dict
    with what actually happened — caller can log details:

        {"amount_dealt": int,
         "damage_type": str,
         "resisted": bool,
         "vulnerable": bool,
         "immune": bool,
         "status_applied": Optional[str]}

    Honors target.immune_to / .resists / .vulnerable_to. Applies the
    damage type's status (if any and `apply_status`). Handles the
    fire-extinguishes-via-wet interaction:
      - If target has any `extinguished_by_tags` (e.g. "wet"), the
        burning status is suppressed AND the wet tag is removed (the
        fire dried them off).
    """
    if target is None or amount <= 0:
        return {"amount_dealt": 0, "damage_type": damage_type,
                "resisted": False, "vulnerable": False,
                "immune": False, "status_applied": None}

    dt = get_damage_type(damage_type)
    immune = damage_type in (getattr(target, "immune_to", []) or [])
    if immune:
        return {"amount_dealt": 0, "damage_type": damage_type,
                "resisted": False, "vulnerable": False,
                "immune": True, "status_applied": None}

    resisted = damage_type in (getattr(target, "resists", []) or [])
    vulnerable = damage_type in (getattr(target, "vulnerable_to", []) or [])

    final = int(amount)
    if resisted and not vulnerable:
        final = max(1, final // 2)
    elif vulnerable and not resisted:
        final = final * 2
    # Both flags set → no-op (cancels). Content authoring error guard.

    # HP write.
    if hasattr(target, "hp"):
        target.hp = max(0, target.hp - final)

    # Status application.
    status_applied = None
    if apply_status and dt.applies_status and target.is_alive():
        # Check extinguish interactions for fire.
        extinguished = False
        if dt.extinguished_by_tags:
            target_tags = list(getattr(target, "tags", []) or [])
            for tag in dt.extinguished_by_tags:
                if tag in target_tags:
                    extinguished = True
                    # Burn off the wet tag — next fire hit will stick.
                    target.tags = [x for x in target_tags if x != tag]
                    break
        if not extinguished:
            duration = dt.status_duration_turns or \
                       STATUS_DURATIONS_TURNS.get(dt.applies_status, 2)
            _apply_status_via_combat(target, dt.applies_status, duration)
            status_applied = dt.applies_status

    # Sponsor tag for spectacle / chemical / etc.
    if dt.audience_tag and world is not None:
        try:
            from . import sponsors as _sp
            _sp.note_player_tag(world, dt.audience_tag, weight=1)
        except Exception:
            pass

    return {"amount_dealt": final, "damage_type": damage_type,
            "resisted": resisted and not vulnerable,
            "vulnerable": vulnerable and not resisted,
            "immune": False,
            "status_applied": status_applied}


def _apply_status_via_combat(target, status_key: str, duration: int) -> None:
    """Set the status both on `target.conditions` (the inert list used
    by tag checks) and on the combat clock store (used by tick_statuses).
    Lazily imported to avoid a hard dependency cycle with combat.py."""
    try:
        from . import combat as _cmb
        _cmb.add_status(target, status_key, duration)
    except Exception:
        # Fall back to manual addition if combat module isn't loadable.
        if hasattr(target, "conditions") and status_key not in target.conditions:
            target.conditions.append(status_key)


# ── Out-of-combat slow decay ──────────────────────────────────────────────

# Each "tick" out-of-combat is N in-game minutes. Default 10 → after
# 30 minutes of exploration, a 3-turn burning status will have ticked
# its 3 times.
SLOW_DECAY_MINUTES_PER_TICK = 10

# Outside combat, DOT damage halves to avoid murder by stroll.
_OUT_OF_COMBAT_DOT_HALF = 2


def slow_decay_tick(world, minutes_elapsed: int) -> None:
    """Called by time_system.advance() each in-game minute step. Walks
    every entity with status clocks, ticks any PERSISTS_OUT_OF_COMBAT
    status that's still active, and applies DOT damage at half rate.

    Idempotent and safe to call frequently — only does real work when
    the floor's clock has crossed another SLOW_DECAY_MINUTES_PER_TICK
    boundary since the last call.
    """
    if world is None or getattr(world, "current_floor", None) is None:
        return
    if minutes_elapsed <= 0:
        return
    floor = world.current_floor

    # Accumulator on the floor — keeps decay independent of combat ticks.
    acc = int(getattr(floor, "_status_decay_accumulator", 0) or 0)
    acc += int(minutes_elapsed)
    ticks = acc // SLOW_DECAY_MINUTES_PER_TICK
    floor._status_decay_accumulator = acc - ticks * SLOW_DECAY_MINUTES_PER_TICK
    if ticks <= 0:
        return

    # Don't slow-decay while combat is active in the player's room —
    # combat's own tick_statuses handles that pace.
    try:
        from . import combat as _cmb
        room = floor.current_room()
        if room is not None and _cmb.get_combat(room) is not None:
            return
    except Exception:
        pass

    # Tick player + every entity in the world's known registry. Cheap
    # since most won't have status clocks.
    targets: List[Any] = []
    char = getattr(world, "character", None)
    if char is not None:
        targets.append(char)
    for ent in (getattr(world, "entities", {}) or {}).values():
        if getattr(ent, "conditions", None):
            targets.append(ent)

    for tgt in targets:
        for _ in range(ticks):
            _apply_out_of_combat_status_tick(tgt)


def _apply_out_of_combat_status_tick(target) -> None:
    """Run one out-of-combat tick on `target`. Drains a turn from each
    persisting status; applies half-rate DOT damage; removes statuses
    whose clock hits zero."""
    if target is None:
        return
    # Statuses can be on entity.conditions (list) and in the combat
    # clock dict. We use combat's tick_statuses with a custom DOT
    # damage map (half rate).
    try:
        from . import combat as _cmb
        clocks = _cmb._clocks_for(target) or {}
    except Exception:
        clocks = (getattr(target, "state", {}) or {}).get("status_clocks", {})

    if not clocks:
        return
    persist_keys = [k for k in clocks
                    if k in STATUS_PERSISTS_OUT_OF_COMBAT]
    if not persist_keys:
        return

    for k in persist_keys:
        # Half-rate DOT: 2 per turn becomes 1 per out-of-combat tick.
        dot = STATUS_DOT_PER_TURN.get(k, 0)
        if dot > 0 and hasattr(target, "hp") and target.is_alive():
            half = max(1, dot // _OUT_OF_COMBAT_DOT_HALF) if dot >= 2 else 0
            if half > 0:
                target.hp = max(0, target.hp - half)
        clocks[k] = clocks.get(k, 0) - 1
        if clocks[k] <= 0:
            clocks.pop(k, None)
            if hasattr(target, "conditions") and k in target.conditions:
                target.conditions.remove(k)


# ── Helpers for content / UI ──────────────────────────────────────────────

def damage_type_label(key: str, lang: str = "pl") -> str:
    """Localized label for a damage type. Falls back to the key."""
    dt = get_damage_type(key)
    if lang == "en":
        return dt.label_en or key
    return dt.label_pl or key
