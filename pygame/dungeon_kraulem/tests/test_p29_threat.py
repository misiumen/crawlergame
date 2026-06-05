"""Prompt 29.0 — per-room threat escalation (replaces noise → patrol).

Covers:
  * bump increases room.noise_level
  * crossing THRESHOLD_WARY/ALERT/ENRAGED steps hostile entities up
    one threat_level (oblivious=0 → wary=1 → alert=2 → enraged=3)
  * latches prevent re-firing the same threshold inside one rise
  * crossing ENRAGED starts combat with free_attack_pending=True
  * de_escalate drops the pool AND steps entities down one rank
  * decay reduces pool by DECAY_PER_MINUTE * minutes (latch clears
    when pool falls below threshold)
  * threat_level + room.noise_level survive save/load round-trip
  * non-hostile entities never escalate
  * combat's free_attack_pending triggers an enemy turn on next
    player input
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER, T_OBJECT
from ..engine import threat as _threat
from ..engine import combat as _cmb


def _mk_world(monster_hp: int = 60):
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    m = Entity(key="thug", entity_type=T_MONSTER,
               fallback_name="Bandzior", hp=monster_hp, max_hp=monster_hp,
               ac=11, affordances=["attack"],
               tags=["monster", "humanoid"], location_id="r0")
    w.register(m); r.entities.append(m)
    return w, r, m


# ── Core bump + escalation ───────────────────────────────────────────────

def test_bump_increases_pool():
    w, r, _m = _mk_world()
    assert r.noise_level == 0
    _threat.bump(w, r, 3, source="test")
    assert r.noise_level == 3
    _threat.bump(w, r, 2, source="test")
    assert r.noise_level == 5
    print("  bump increments noise_level: OK")


def test_crossing_wary_threshold_escalates_monster():
    w, r, m = _mk_world()
    assert m.threat_level == 0
    _threat.bump(w, r, _threat.THRESHOLD_WARY + 1, source="test")
    assert m.threat_level == 1, m.threat_level
    print(f"  crossing WARY → threat_level=1: OK")


def test_crossing_alert_threshold_steps_up_again():
    w, r, m = _mk_world()
    _threat.bump(w, r, _threat.THRESHOLD_ALERT + 1, source="test")
    # Both WARY and ALERT thresholds crossed in one bump → level=2.
    assert m.threat_level == 2, m.threat_level
    print(f"  crossing ALERT in one bump → threat_level=2: OK")


def test_crossing_enraged_starts_combat_with_free_attack():
    w, r, m = _mk_world()
    _threat.bump(w, r, _threat.THRESHOLD_ENRAGED + 5, source="test")
    assert m.threat_level == 3
    cs = _cmb.get_combat(r)
    assert cs is not None and cs.active, "combat should be active"
    assert cs.free_attack_pending is True
    print(f"  crossing ENRAGED → combat + free_attack_pending: OK")


def test_latch_prevents_double_escalation_within_same_rise():
    """Bumping twice across the same threshold only escalates once."""
    w, r, m = _mk_world()
    _threat.bump(w, r, _threat.THRESHOLD_WARY + 1, source="test")
    assert m.threat_level == 1
    # Drop entity threat_level manually to simulate a separate concern
    # (e.g. hide steps it down) but keep pool above WARY — no re-escalation
    # because latch is set.
    m.threat_level = 0
    _threat.bump(w, r, 1, source="test")
    assert m.threat_level == 0, \
        f"latch should suppress re-escalation; got {m.threat_level}"
    print("  WARY latch prevents double escalation: OK")


# ── De-escalation ────────────────────────────────────────────────────────

def test_de_escalate_drops_pool_and_steps_entities_down():
    w, r, m = _mk_world()
    _threat.bump(w, r, _threat.THRESHOLD_ALERT + 1, source="test")
    assert m.threat_level == 2 and r.noise_level >= _threat.THRESHOLD_ALERT
    _threat.de_escalate(w, r, amount=20)
    assert m.threat_level == 1, f"expected step-down, got {m.threat_level}"
    assert r.noise_level == 0
    # Latches should be cleared since pool is now below thresholds.
    assert "threat_latch_alert" not in (r.state or {})
    assert "threat_latch_wary" not in (r.state or {})
    print(f"  de-escalate drops pool + steps entity down: OK")


# ── Decay ────────────────────────────────────────────────────────────────

def test_decay_reduces_pool_over_time():
    w, r, _m = _mk_world()
    r.noise_level = 15
    r.state["threat_latch_wary"] = True
    r.state["threat_latch_alert"] = True
    _threat.decay(w, r, 10)
    assert r.noise_level == 5, r.noise_level
    # 5 < THRESHOLD_ALERT(12), latch_alert clears.
    assert "threat_latch_alert" not in r.state
    # 5 < THRESHOLD_WARY(6), latch_wary also clears.
    assert "threat_latch_wary" not in r.state, r.state
    print(f"  decay 10min: 15→5, all latches clear: OK")


# ── Non-hostile entities don't escalate ──────────────────────────────────

def test_non_monster_entities_dont_escalate():
    w, r, _m = _mk_world()
    chair = Entity(key="chair", entity_type=T_OBJECT,
                   fallback_name="krzesło", location_id="r0",
                   tags=["furniture"])
    w.register(chair); r.entities.append(chair)
    _threat.bump(w, r, _threat.THRESHOLD_ENRAGED + 5, source="test")
    assert chair.threat_level == 0, \
        f"furniture should never escalate; got {chair.threat_level}"
    print("  object entities don't escalate: OK")


# ── Save/load round-trip ────────────────────────────────────────────────

def test_entity_threat_level_save_load():
    w, _r, m = _mk_world()
    m.threat_level = 2
    d = m.to_dict()
    m2 = Entity.from_dict(d)
    assert m2.threat_level == 2
    print("  Entity.threat_level save/load OK")


def test_room_noise_level_save_load():
    w, r, _m = _mk_world()
    r.noise_level = 15
    d = r.to_dict()
    r2 = RoomState.from_dict(d)
    assert r2.noise_level == 15
    print("  RoomState.noise_level save/load OK")


# ── Status label ─────────────────────────────────────────────────────────

def test_threat_labels_are_polish():
    assert _threat.threat_label(0) == "spokojny"
    assert _threat.threat_label(1) == "wyczulony"
    assert _threat.threat_label(2) == "czujny"
    assert _threat.threat_label(3) == "wściekły"
    assert _threat.threat_label(99) == "spokojny"   # fallback
    print("  threat labels PL: OK")


# ── Integration: free attack fires on next player input ──────────────────

def test_free_attack_fires_before_next_player_command():
    from ..engine.game import Game
    w, r, m = _mk_world(monster_hp=80)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Bump into enraged so combat starts with free_attack_pending=True.
    for ln in _threat.bump(w, r, _threat.THRESHOLD_ENRAGED + 5, source="test"):
        g.log(ln)
    cs = _cmb.get_combat(r)
    assert cs is not None and cs.free_attack_pending is True
    pre_hp = w.character.hp
    # Now player issues any non-trivial command; enemy turn should fire
    # FIRST, then the command runs. Use `czekaj` so we don't get a
    # second enemy turn from the player's attack.
    g.submit_generated_command("czekaj")
    # Either the enemy hit the player, or rolled and missed — either
    # way the free_attack_pending flag must be consumed.
    assert cs.free_attack_pending is False, "free_attack_pending should clear"
    print(f"  free attack consumed (HP {pre_hp}→{w.character.hp}): OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_bump_increases_pool()
    test_crossing_wary_threshold_escalates_monster()
    test_crossing_alert_threshold_steps_up_again()
    test_crossing_enraged_starts_combat_with_free_attack()
    test_latch_prevents_double_escalation_within_same_rise()
    test_de_escalate_drops_pool_and_steps_entities_down()
    test_decay_reduces_pool_over_time()
    test_non_monster_entities_dont_escalate()
    test_entity_threat_level_save_load()
    test_room_noise_level_save_load()
    test_threat_labels_are_polish()
    test_free_attack_fires_before_next_player_command()
    print("Prompt 29.0 threat-escalation smoke: OK")


if __name__ == "__main__":
    main()
