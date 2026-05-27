"""P29.0 — per-room threat escalation (replaces the old noise → patrol
pipeline).

Loud player actions bump `room.noise_level` (renamed semantically: it
is now a local "threat pool" rather than a noise emitter for global
patrol scheduling). Crossing thresholds escalates all alive hostile
entities in the room through threat levels:

    0 oblivious  — default. enemy doesn't notice you.
    1 wary       — heard something. -1 to player attack (it half-knows).
    2 alert      — watching you. next loud action = combat starts.
    3 enraged    — combat starts NOW + enemy gets a free attack of
                   opportunity before the player's next action.

Hide / sneak actions DROP the pool back down. Time passing decays it
naturally. The dungeon doesn't send patrols. The thing already in the
room is what wakes up.

This is DCC-faithful: the loch is a show stage, not a security state.
Monsters wake when you make noise next to them, period.

Public API:
    bump(world, room, amount, source="")    — add to pool; cross thresholds
    de_escalate(world, room, amount=5)      — reduce pool + step entities down
    decay(world, room, minutes)             — time-based decay; called by time_system
    threat_label(level, lang="pl")          — display label for entity.threat_level
    noise_cost(action_kind)                 — lookup table for per-action cost
"""
from __future__ import annotations
from typing import Optional


# ── Thresholds (per-room noise_level) ────────────────────────────────────
# When the room pool crosses these, ALL alive hostile entities in the room
# step their threat_level up by 1. Latches prevent the same threshold
# from firing multiple times before the player de-escalates.
THRESHOLD_WARY    = 6      # 1-2 loud actions → enemy notices
THRESHOLD_ALERT   = 12     # 3-4 loud actions → enemy stands up
THRESHOLD_ENRAGED = 20     # 5-6 loud actions → enemy attacks
DECAY_PER_MINUTE  = 1      # passive decay


# ── Status name map ──────────────────────────────────────────────────────
_THREAT_LABELS_PL = {
    0: "spokojny",   # oblivious
    1: "wyczulony",  # wary
    2: "czujny",     # alert
    3: "wściekły",   # enraged
}
_THREAT_LABELS_EN = {
    0: "calm", 1: "wary", 2: "alert", 3: "enraged",
}


def threat_label(level: int, lang: str = "pl") -> str:
    """Return a display label for an entity's threat_level."""
    table = _THREAT_LABELS_EN if lang == "en" else _THREAT_LABELS_PL
    return table.get(int(level or 0), table[0])


# ── Per-action noise cost ────────────────────────────────────────────────
# What each loud action adds to room.noise_level. Quiet actions (look,
# inspect, listen, wait) cost 0. Movement is 0 unless encumbered.
_NOISE_COST = {
    # Combat
    "attack_unarmed":  3,
    "attack_weapon":   5,
    "attack_crit":     7,
    "attack_gun":      8,
    "attack_explosive": 10,
    # Crafting / trapping in-room
    "trap_arm":        3,
    "trap_disarm":     2,
    "salvage":         4,
    "break":           6,
    "force":           6,   # wyłam drzwi
    # Movement / interaction
    "loud_use":        3,   # consume electric tool / drill / etc.
    "encumbered_move": 2,
    # Stealth-friendly defaults (used when caller doesn't pass one)
    "default":         2,
}


def noise_cost(kind: str) -> int:
    """Look up the noise cost for an action kind. Unknown keys fall
    back to a small default so a missing entry is loud-ish but not
    catastrophic."""
    return int(_NOISE_COST.get(kind, _NOISE_COST["default"]))


# ── Core ─────────────────────────────────────────────────────────────────

def bump(world, room, amount: int, *,
         source: str = "",
         log_threshold_lines: bool = True) -> list:
    """Add `amount` to `room.noise_level`. If the new level crosses a
    threshold (per-room latch), step every alive hostile entity in the
    room up one threat level. Return a list of player-facing log lines
    that the caller can emit (so threat surfaces in the log naturally).

    `source` is a free-text tag for analytics ("salvage", "force_door",
    "weapon_attack") — never shown to the player.

    `log_threshold_lines=False` suppresses the player-facing lines
    (useful for batch tests or quiet bumps from time-system code).
    """
    if room is None or amount <= 0:
        return []
    pre = int(getattr(room, "noise_level", 0) or 0)
    post = pre + int(amount)
    room.noise_level = post

    # Per-room latches so the same crossing fires once per pool-rise.
    state = getattr(room, "state", None)
    if state is None:
        room.state = {}
        state = room.state

    lines: list = []
    crossings = []
    if pre < THRESHOLD_WARY <= post and not state.get("threat_latch_wary"):
        state["threat_latch_wary"] = True
        crossings.append(1)
    if pre < THRESHOLD_ALERT <= post and not state.get("threat_latch_alert"):
        state["threat_latch_alert"] = True
        crossings.append(2)
    if pre < THRESHOLD_ENRAGED <= post and not state.get("threat_latch_enraged"):
        state["threat_latch_enraged"] = True
        crossings.append(3)

    if not crossings:
        return lines

    # For each crossing, step entities up one level.
    hostiles = _alive_hostiles(room, world)
    for target_level in crossings:
        for ent in hostiles:
            if int(getattr(ent, "threat_level", 0) or 0) < target_level:
                ent.threat_level = target_level
                if log_threshold_lines:
                    lines.append(_escalation_line(ent, target_level))
        # Crossing 3 → start combat with a free attack of opportunity.
        if target_level == 3:
            lines.extend(_trigger_enraged_combat(world, room, hostiles))

    return lines


def de_escalate(world, room, amount: int = 5,
                *, also_step_entities: bool = True) -> list:
    """Hide / sneak / quiet retreat — drop the pool and (optionally)
    step each alive hostile down one threat level. Latches at any
    threshold the new pool is below are cleared so they can fire
    again if the player resumes loud actions.

    Returns log lines for the caller to emit."""
    if room is None:
        return []
    pre = int(getattr(room, "noise_level", 0) or 0)
    if pre <= 0 and not also_step_entities:
        return []
    new = max(0, pre - int(amount))
    room.noise_level = new

    state = getattr(room, "state", None)
    if state is None:
        room.state = {}
        state = room.state
    # Clear latches that the new pool no longer satisfies.
    if new < THRESHOLD_ENRAGED:
        state.pop("threat_latch_enraged", None)
    if new < THRESHOLD_ALERT:
        state.pop("threat_latch_alert", None)
    if new < THRESHOLD_WARY:
        state.pop("threat_latch_wary", None)

    lines: list = []
    if also_step_entities:
        for ent in _alive_hostiles(room, world):
            cur = int(getattr(ent, "threat_level", 0) or 0)
            if cur > 0:
                ent.threat_level = cur - 1
    return lines


def decay(world, room, minutes: int) -> None:
    """Time-based passive decay. Called from time_system.advance().
    1 point per `1/DECAY_PER_MINUTE` minutes elapsed. Quiet so it
    doesn't spam the log."""
    if room is None or minutes <= 0:
        return
    drop = int(minutes) * DECAY_PER_MINUTE
    if drop <= 0:
        return
    de_escalate(world, room, amount=drop, also_step_entities=False)


# ── Internals ────────────────────────────────────────────────────────────

def _alive_hostiles(room, world) -> list:
    """Return entities in `room` that are alive AND would be hostile to
    the player. Currently: any entity with entity_type 'monster' OR
    tagged 'hostile'. Crawlers / NPCs / objects don't escalate."""
    out = []
    for ent in (room.entities or []):
        if not ent.is_alive():
            continue
        if ent.entity_type == "monster" or "hostile" in (ent.tags or []):
            out.append(ent)
    return out


def _escalation_line(ent, new_level: int) -> str:
    """Produce a Polish narrator line for an entity stepping up to
    `new_level`. Goes to the player log via the caller."""
    name = ent.display_name()
    if new_level == 1:
        return f"„{name}” odwraca głowę. Coś usłyszał."
    if new_level == 2:
        return f"„{name}” wstaje. Patrzy w twoją stronę."
    if new_level == 3:
        return f"„{name}” rzuca się na ciebie!"
    return f"„{name}” jest spokojny."


def _trigger_enraged_combat(world, room, hostiles: list) -> list:
    """When at least one hostile crosses into level 3, combat starts
    immediately and the room's enraged hostiles get a free attack of
    opportunity (before the player's next action). Idempotent — if
    combat is already running we just flip a flag.
    """
    lines: list = []
    try:
        from . import combat as _cmb
    except Exception:
        return lines
    cs = _cmb.get_combat(room)
    if cs is None or not getattr(cs, "active", False):
        try:
            cs = _cmb.start_combat(room, world, triggered_by="threat_enraged")
        except Exception:
            return lines
        lines.append("Walka się zaczyna — sprowokowałeś.")
    # Flag the combat with free-attack-first so the next tick lets the
    # enraged hostiles strike before the player picks their action.
    if cs is not None:
        cs.free_attack_pending = True
    return lines
