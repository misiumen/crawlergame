"""Noise propagation + decay + aggro (Prompt 26b).

The world has noise levels stored per-room (`room.noise_level`).
Pre-P26b: noise was incremented by various actions but never decayed
and never triggered anything — playtester correctly reported it as
inert.

P26b wires three behaviours:

  1. **Decay** — out of combat, noise drops by `DECAY_OUT_OF_COMBAT`
     per minute of time advancement (floored at 0). In combat it
     decays more slowly (`DECAY_IN_COMBAT`) so the player can't
     no-op-away a noise spike.

  2. **Propagation** — high-noise rooms bleed `PROPAGATION_FRACTION`
     of their noise to adjacent (non-hidden, non-locked) rooms each
     tick. This means a fight in the kitchen makes the corridor next
     door noticeably louder, which feeds into encounter pacing.

  3. **Threshold-triggered encounters** — when a room's noise crosses
     `PATROL_THRESHOLD`, schedule a patrol encounter via the existing
     `engine.encounter` module. A second patrol fires at
     `PATROL_THRESHOLD_HIGH`. Latches per room so the same noise
     bracket only spawns once per visit.

Public API:
    tick_noise(world, minutes)
    add_noise(world, room, amount, *, source="action")
    register_noise_taxonomy(world)   — author hook for content-specific
                                        per-source modifiers (no-op v1)

Hooks for future prompts:
  * `room.state["noise_log"]` tracks recent noise events for the player
    journal (P27 viewer mechanics consume this).
  * The "investigator" responder spawn is deferred to content/data —
    we just request the spawn here; encounter.py decides what hostile
    keys actually arrive.
"""
from __future__ import annotations
from typing import Optional


# Tuning knobs — small enough that one or two actions never trigger
# patrols, but a 4-turn combat in a small room reliably does.
DECAY_OUT_OF_COMBAT = 2     # per minute of time advance
DECAY_IN_COMBAT     = 1     # per minute (combat ticks one minute / round)
PROPAGATION_FRACTION = 0.25 # 25% of source room's noise bleeds to each adjacent
PROPAGATION_DECAY_FLOOR = 4 # don't propagate below this; tiny noises stay local
PATROL_THRESHOLD       = 12
PATROL_THRESHOLD_HIGH  = 20


# Per-room latch keys (live on room.state) to avoid re-triggering the
# same patrol while noise stays high.
LATCH_LOW  = "noise_patrol_lo_fired"
LATCH_HIGH = "noise_patrol_hi_fired"


def tick_noise(world, minutes_elapsed: int) -> None:
    """Called once per time-advance. Handles decay, propagation, and
    threshold-triggered encounter scheduling.

    Safe-noop when no floor / no rooms / minutes <= 0."""
    if world is None or minutes_elapsed <= 0:
        return
    floor = getattr(world, "current_floor", None)
    if floor is None or not getattr(floor, "rooms", None):
        return

    # Detect combat in any room — affects the decay rate. (We tick all
    # rooms with the same rate based on whether the PLAYER's current
    # room is in combat. Better than nothing; granular per-room combat
    # decay would need a per-room combat lookup each tick.)
    in_combat = False
    try:
        from . import combat as _cmb
        cur = floor.rooms.get(floor.current_room_id)
        if cur is not None:
            cs = _cmb.get_combat(cur)
            in_combat = bool(cs and cs.active)
    except Exception:
        pass
    decay = (DECAY_IN_COMBAT if in_combat else DECAY_OUT_OF_COMBAT) * minutes_elapsed

    # Two-pass propagation: first read all current noise levels (so
    # propagation uses the snapshot, not a running total), then write
    # decayed-plus-incoming back.
    snapshot = {rid: int(getattr(r, "noise_level", 0) or 0)
                for rid, r in floor.rooms.items()}
    incoming: dict = {rid: 0.0 for rid in floor.rooms}
    for rid, r in floor.rooms.items():
        src_noise = snapshot[rid]
        if src_noise <= PROPAGATION_DECAY_FLOOR:
            continue
        for label, ed in (r.exits or {}).items():
            tgt = ed.get("target", "")
            if not tgt or tgt not in floor.rooms:
                continue
            # Locked + hidden doors muffle noise; closed cardinal doors
            # propagate normally (this is a dungeon, not a soundproof
            # corporate office).
            if ed.get("hidden"):
                continue
            mult = 0.5 if ed.get("locked") else 1.0
            incoming[tgt] += src_noise * PROPAGATION_FRACTION * mult

    # Apply decay + incoming, threshold-check, schedule encounters.
    for rid, r in floor.rooms.items():
        new_level = max(0, snapshot[rid] - decay + int(round(incoming[rid])))
        # Pull state for latch flags.
        st = getattr(r, "state", None)
        if st is None:
            r.state = {}
            st = r.state
        # Reset latches once noise drops well below threshold.
        if new_level < PATROL_THRESHOLD * 0.5:
            st.pop(LATCH_LOW, None)
            st.pop(LATCH_HIGH, None)
        r.noise_level = new_level
        # Threshold-trigger patrol schedule.
        if new_level >= PATROL_THRESHOLD_HIGH and not st.get(LATCH_HIGH):
            st[LATCH_HIGH] = True
            _schedule_noise_patrol(world, r, urgency="high")
        elif new_level >= PATROL_THRESHOLD and not st.get(LATCH_LOW):
            st[LATCH_LOW] = True
            _schedule_noise_patrol(world, r, urgency="low")


def _schedule_noise_patrol(world, room, *, urgency: str) -> None:
    """Hand off to the existing encounter scheduler. Urgency picks the
    alarm type — high noise = faster ETA via a more aggressive alarm.

    The encounter module already idempotently dedups schedules from the
    same `source`, so a sustained-noise room won't keep spawning
    duplicate patrols.
    """
    alarm_type = "patrol_responder" if urgency == "high" else "patrol_routine"
    source = f"noise:{urgency}"
    try:
        from . import encounter as _enc
        _enc.schedule(world, room.room_id,
                      alarm_type=alarm_type,
                      source=source)
    except Exception:
        # Defensive fallback: surface a log line so the player still
        # sees the signal even if the alarm definitions aren't in place.
        from ..ui.lang import t
        eta = 6 if urgency == "high" else 15
        msg = t("noise_patrol_warning",
                fallback=f"Hałas zdradza twoją pozycję — patrol w drodze (~{eta} min).",
                eta=eta)
        try:
            world.log_msg(msg, "warn")
        except Exception:
            pass


def add_noise(world, room, amount: int, *, source: str = "action") -> None:
    """Convenience wrapper: bump a room's noise and record the source.
    Used as a single chokepoint so future telemetry / sponsor reactions
    can hook in. Today it just adds the value and logs the source in
    `room.state["noise_log"]` for journal display."""
    if room is None or amount <= 0:
        return
    room.noise_level = int(getattr(room, "noise_level", 0) or 0) + int(amount)
    st = getattr(room, "state", None)
    if st is None:
        room.state = {}
        st = room.state
    log = st.setdefault("noise_log", [])
    log.append((source, int(amount)))
    # Trim to last 8 entries — journal display only needs recent.
    if len(log) > 8:
        st["noise_log"] = log[-8:]
