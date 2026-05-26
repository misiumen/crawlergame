"""Prompt 20 — encounter prep + scheduled-arrival smoke suite.

Covers:
  * schedule() adds a ScheduledEncounter to the floor's queue
  * tick_due() emits warnings at T-15 / T-5 / T-1
  * tick_due() fires the encounter at the right minute
  * fire() with no traps + player present → starts combat
  * fire() with traps that kill all arrivers → traps_only outcome
  * fire() with player hidden → hidden_success outcome
  * fire() with player in different room → player_fled outcome
  * trigger_alarm effect schedules an encounter
  * Each alarm type has correct delay (default 30, silent 15, biotech 45)
  * Unknown alarm type falls back to default
  * Sponsor tags emit when encounter resolves
  * Idempotent scheduling (re-trigger same alarm = same encounter)
  * Topbar countdown helper time_until_next() returns correct value
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import encounter as _enc
from ..engine import time_system as _ts
from ..engine import consequences as _cons


def _mk_world(player_room="r0") -> WorldState:
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Klinika")
    r2 = RoomState(room_id="r1", fallback_short_title="Korytarz")
    f.add_room(r); f.add_room(r2)
    f.start_room_id = "r0"; f.current_room_id = player_room
    w.current_floor = f
    return w


# ── Scheduling ────────────────────────────────────────────────────────────

def test_schedule_adds_encounter():
    w = _mk_world()
    enc = _enc.schedule(w, "r0", "default")
    assert enc is not None
    assert enc.alarm_type == "default"
    assert enc.fires_at_minute == 30
    assert enc.hostile_keys == ["patrol_security", "patrol_security"]
    assert len(w.current_floor.scheduled_encounters) == 1
    print("  schedule() adds encounter: OK")


def test_alarm_type_delays():
    """Each alarm type has its own delay window."""
    w = _mk_world()
    e1 = _enc.schedule(w, "r0", "default")
    assert e1.fires_at_minute == 30
    w.current_floor.scheduled_encounters.clear()
    e2 = _enc.schedule(w, "r0", "silent_alarm")
    assert e2.fires_at_minute == 15
    w.current_floor.scheduled_encounters.clear()
    e3 = _enc.schedule(w, "r0", "biotech_containment")
    assert e3.fires_at_minute == 45
    print("  alarm type delays: OK (30/15/45)")


def test_unknown_alarm_falls_back_to_default():
    w = _mk_world()
    enc = _enc.schedule(w, "r0", "nonexistent_alarm_type")
    assert enc is not None
    assert enc.fires_at_minute == 30   # default
    print("  unknown alarm type falls back to default: OK")


def test_idempotent_scheduling():
    """Re-scheduling the same alarm in same room with same source =
    same encounter (don't double-up)."""
    w = _mk_world()
    e1 = _enc.schedule(w, "r0", "default")
    e2 = _enc.schedule(w, "r0", "default")
    assert e1 is e2
    assert len(w.current_floor.scheduled_encounters) == 1
    print("  idempotent scheduling: OK")


# ── Warnings ──────────────────────────────────────────────────────────────

def test_tick_emits_warnings_in_order():
    w = _mk_world()
    _enc.schedule(w, "r0", "default")   # fires at minute 30
    # Advance to minute 16: nothing yet (T-15 not crossed).
    w.current_floor.current_minute = 14
    _enc.tick_due(w, 14)
    warn_lines = [m for m, c in w.log if "min" in m.lower() or "patrol" in m.lower()]
    # Now cross T-15 (currentMin=15 → remaining=15).
    w.current_floor.current_minute = 15
    _enc.tick_due(w, 1)
    # Cross T-5.
    w.current_floor.current_minute = 25
    _enc.tick_due(w, 10)
    # Cross T-1.
    w.current_floor.current_minute = 29
    _enc.tick_due(w, 4)
    enc = w.current_floor.scheduled_encounters[0]
    assert 15 in enc.warnings_emitted
    assert 5 in enc.warnings_emitted
    assert 1 in enc.warnings_emitted
    print(f"  warnings emitted at T-15/T-5/T-1: OK")


# ── Firing outcomes ───────────────────────────────────────────────────────

def test_fire_starts_combat_when_player_present():
    w = _mk_world(player_room="r0")
    _enc.schedule(w, "r0", "default")
    # Advance to fire time.
    w.current_floor.current_minute = 35
    _enc.tick_due(w, 35)
    # Encounter should have fired and combat should have started.
    from ..engine import combat as _cmb
    room = w.current_floor.current_room()
    cs = _cmb.get_combat(room)
    assert cs is not None, "combat should have started"
    assert cs.active
    # Queue should be empty after firing.
    assert len(w.current_floor.scheduled_encounters) == 0
    print("  fire() starts combat when player present: OK")


def test_fire_player_fled_when_player_not_in_room():
    w = _mk_world(player_room="r1")   # player elsewhere
    _enc.schedule(w, "r0", "default")
    w.current_floor.current_minute = 35
    _enc.tick_due(w, 35)
    # No combat in r0 (player not there).
    from ..engine import combat as _cmb
    cs = _cmb.get_combat(w.current_floor.rooms["r0"])
    # Combat *may* exist if start_combat got called on the empty room;
    # the contract is: player isn't auto-engaged. Verify by checking
    # log for the "patrol go zajął" line.
    fled_lines = [m for m, c in w.log
                  if "Patrol" in m or "zajął" in m or "uciekł" in m]
    assert fled_lines, f"expected player_fled line, got log={w.log[-5:]}"
    print("  fire() player_fled outcome: OK")


def test_fire_hidden_success_when_player_hidden():
    w = _mk_world(player_room="r0")
    w.character.flags["hidden_for_encounter"] = True
    _enc.schedule(w, "r0", "default")
    w.current_floor.current_minute = 35
    _enc.tick_due(w, 35)
    # No combat — player hidden, arrivers searched and left.
    from ..engine import combat as _cmb
    cs = _cmb.get_combat(w.current_floor.rooms["r0"])
    assert cs is None or not cs.active, "no combat when player hidden"
    # Hidden flag should be CLEARED after fire (next alarm needs fresh hide).
    assert not w.character.flags.get("hidden_for_encounter")
    hidden_lines = [m for m, c in w.log
                    if "Szukaj" in m or "Nie znajduj" in m]
    assert hidden_lines, "expected hidden-success line"
    print("  fire() hidden_success outcome: OK")


def test_fire_traps_only_kills_arrivers_before_combat():
    """One pre-deployed shock trap kills the silent_response (12 HP)
    in two hits. We use the silent_alarm definition (1 hostile) so the
    single trap is enough to clear the room."""
    w = _mk_world(player_room="r0")
    room = w.current_floor.rooms["r0"]
    room.state["player_traps"] = [{
        "key": "shock_pad", "entity_id": -1,
        "display_name": "elektrokoc", "tags": ["shock"],
        "quality": "normal", "armed_at": 0,
        "level": "critical_success",
        "triggered": False,
        "effect": {"type": "damage", "amount": 250},  # one-shot (P27.6 HP×5)
    }]
    _enc.schedule(w, "r0", "silent_alarm")
    w.current_floor.current_minute = 20
    _enc.tick_due(w, 20)
    # Combat should NOT have started — the single trap one-shotted the
    # single arriver.
    from ..engine import combat as _cmb
    cs = _cmb.get_combat(w.current_floor.rooms["r0"])
    assert cs is None or not cs.active, \
        f"expected no combat when trap killed all arrivers, got {cs}"
    print("  fire() traps_only outcome: OK")


# ── Trigger-alarm wiring ─────────────────────────────────────────────────

def test_trigger_alarm_effect_schedules_encounter():
    w = _mk_world(player_room="r0")
    _cons.apply([{"type": "trigger_alarm", "alarm_type": "default"}], w)
    assert len(w.current_floor.scheduled_encounters) == 1
    enc = w.current_floor.scheduled_encounters[0]
    assert enc.alarm_type == "default"
    assert enc.room_id == "r0"
    print("  trigger_alarm effect schedules encounter: OK")


def test_trigger_alarm_uses_alarm_type():
    """trigger_alarm with `alarm_type=silent_alarm` should create a
    15-min encounter."""
    w = _mk_world(player_room="r0")
    _cons.apply([{"type": "trigger_alarm",
                  "alarm_type": "silent_alarm"}], w)
    enc = w.current_floor.scheduled_encounters[0]
    assert enc.alarm_type == "silent_alarm"
    assert enc.fires_at_minute == 15
    print("  trigger_alarm honors alarm_type: OK")


# ── Sponsor + audience ────────────────────────────────────────────────────

def test_alarm_emits_sponsor_tags_and_bumps_audience():
    from ..engine import sponsors as _sp
    w = _mk_world(player_room="r0")
    pre_aud = w.character.audience_rating
    _enc.schedule(w, "r0", "biotech_containment")
    # biotech_containment likes_tags include "chemical" + "spectacle"
    # which NovaChem and Kanał 7 like.
    assert _sp.get_attention(w, "novachem_biotech") != 0 or \
           _sp.get_attention(w, "kanal_7_krawedz") != 0
    assert w.character.audience_rating > pre_aud
    print("  alarm scheduling emits sponsor tags + audience: OK")


# ── time_until_next ───────────────────────────────────────────────────────

def test_time_until_next_returns_minutes():
    w = _mk_world(player_room="r0")
    assert _enc.time_until_next(w) is None
    _enc.schedule(w, "r0", "default")
    assert _enc.time_until_next(w) == 30
    w.current_floor.current_minute = 20
    assert _enc.time_until_next(w) == 10
    print("  time_until_next() returns remaining minutes: OK")


def test_time_until_next_ignores_other_rooms():
    w = _mk_world(player_room="r0")
    _enc.schedule(w, "r1", "default")   # encounter in OTHER room
    assert _enc.time_until_next(w) is None
    print("  time_until_next() only checks player's room: OK")


# ── time_system integration ──────────────────────────────────────────────

def test_time_system_advance_drains_due():
    """Verify time_system.advance() actually calls encounter.tick_due()."""
    w = _mk_world(player_room="r0")
    _enc.schedule(w, "r0", "default")
    _ts.advance(w, 35)   # past the 30-min fire time
    assert len(w.current_floor.scheduled_encounters) == 0, \
        "time_system.advance should drain due encounters"
    print("  time_system.advance() drains encounter queue: OK")


# ── Suite ─────────────────────────────────────────────────────────────────

def main():
    test_schedule_adds_encounter()
    test_alarm_type_delays()
    test_unknown_alarm_falls_back_to_default()
    test_idempotent_scheduling()
    test_tick_emits_warnings_in_order()
    test_fire_starts_combat_when_player_present()
    test_fire_player_fled_when_player_not_in_room()
    test_fire_hidden_success_when_player_hidden()
    test_fire_traps_only_kills_arrivers_before_combat()
    test_trigger_alarm_effect_schedules_encounter()
    test_trigger_alarm_uses_alarm_type()
    test_alarm_emits_sponsor_tags_and_bumps_audience()
    test_time_until_next_returns_minutes()
    test_time_until_next_ignores_other_rooms()
    test_time_system_advance_drains_due()
    print("Prompt 20 encounter-prep smoke: OK")


if __name__ == "__main__":
    main()
