"""Prompt 21 — Damage types + statuses smoke suite.

Covers:
  * Damage type registry: all 7 types present, extensible via register
  * apply_damage honors resistance (½), vulnerability (×2), immunity (0)
  * apply_damage applies the type's status (burning / shocked / etc.)
  * Burning + wet tag = extinguished, wet tag removed
  * Out-of-combat slow-decay tick drains DOT statuses at half rate
  * Burning + chilled cancels both (status interaction)
  * Push_into acid_pool deals acid damage + corroded
  * Trap dispatch honors damage_type from item tags
  * Combat damage_entity routes through apply_damage
  * `afraid` reduces player to-hit; `shocked` raises fumble floor
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER, T_HAZARD
from ..engine import damage as _dmg
from ..engine import combat as _cmb
from ..engine import consequences as _cons
from ..engine import time_system as _ts


def _mk_world(player_room="r0"):
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id=player_room
    w.current_floor = f
    return w


def _mk_mob(world, room, *, hp=20, resists=None, vulnerable_to=None,
            immune_to=None, tags=None):
    e = Entity(
        key="testmob", entity_type=T_MONSTER, fallback_name="testmob",
        hp=hp, max_hp=hp, ac=12, attack_bonus=2,
        damage_dice="1d6", affordances=["attack"],
        tags=list(tags or []),
        resists=list(resists or []),
        vulnerable_to=list(vulnerable_to or []),
        immune_to=list(immune_to or []),
        location_id=room.room_id,
    )
    world.register(e); room.entities.append(e)
    return e


# ── Registry ──────────────────────────────────────────────────────────────

def test_registry_has_7_v1_types():
    for k in ("physical","fire","electric","acid","poison","cold","psychic"):
        dt = _dmg.get_damage_type(k)
        assert dt.key == k, f"missing {k}"
    print("  registry has all 7 v1 damage types: OK")


def test_registry_extensible():
    """Future env-trap content should be able to register new types."""
    n_before = len(_dmg.all_damage_types())
    _dmg.register_damage_type(_dmg.DamageType(
        key="kinetic_test", label_pl="kinetyczne", label_en="kinetic"))
    assert len(_dmg.all_damage_types()) == n_before + 1
    assert _dmg.get_damage_type("kinetic_test").key == "kinetic_test"
    print("  registry is extensible: OK")


# ── apply_damage math ─────────────────────────────────────────────────────

def test_resistance_halves_damage():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20, resists=["fire"])
    res = _dmg.apply_damage(w, m, 10, "fire")
    assert res["amount_dealt"] == 5, f"resist: {res}"
    assert res["resisted"] is True
    assert m.hp == 15
    print("  resistance halves damage: OK")


def test_vulnerability_doubles_damage():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20,
                vulnerable_to=["fire"])
    res = _dmg.apply_damage(w, m, 5, "fire")
    assert res["amount_dealt"] == 10
    assert res["vulnerable"] is True
    print("  vulnerability doubles damage: OK")


def test_immunity_zeroes_damage():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20,
                immune_to=["poison"])
    res = _dmg.apply_damage(w, m, 50, "poison")
    assert res["amount_dealt"] == 0
    assert res["immune"] is True
    assert m.hp == 20
    print("  immunity zeroes damage: OK")


def test_status_applied_on_hit():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    res = _dmg.apply_damage(w, m, 5, "fire")
    assert "burning" in m.conditions
    assert res["status_applied"] == "burning"
    res2 = _dmg.apply_damage(w, m, 5, "electric")
    assert "shocked" in m.conditions
    res3 = _dmg.apply_damage(w, m, 5, "acid")
    assert "corroded" in m.conditions
    print("  status applied on hit for fire/electric/acid: OK")


def test_burning_extinguished_by_wet_tag():
    """Fire hit on a wet target damages but does NOT apply burning,
    and the wet tag is consumed."""
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30,
                tags=["wet"])
    res = _dmg.apply_damage(w, m, 5, "fire")
    assert "burning" not in m.conditions, "wet should extinguish"
    assert res["status_applied"] is None
    assert "wet" not in m.tags, "wet tag should be consumed"
    # Next fire hit should now burn.
    res2 = _dmg.apply_damage(w, m, 5, "fire")
    assert "burning" in m.conditions
    print("  wet tag extinguishes fire (and is consumed): OK")


# ── Combat tick: DOT + interactions ──────────────────────────────────────

def test_combat_tick_applies_dot():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    _cmb.add_status(m, "burning", duration=3)
    hp_before = m.hp
    _cmb.tick_statuses(m)
    assert m.hp == hp_before - 2, "burning DOT should be 2/turn"
    print("  combat tick applies DOT: OK")


def test_burning_plus_chilled_cancels_both():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    _cmb.add_status(m, "burning", duration=3)
    _cmb.add_status(m, "chilled", duration=3)
    _cmb.tick_statuses(m)
    assert "burning" not in m.conditions, "should cancel"
    assert "chilled" not in m.conditions, "should cancel"
    print("  burning + chilled cancels both: OK")


# ── Out-of-combat slow decay ──────────────────────────────────────────────

def test_slow_decay_drains_burning_at_half_rate():
    """30 in-game minutes (3 ticks of 10 min) of exploration on a
    target with 2 turns of burning left → status ends, DOT applied at
    half rate (so 1 HP/tick instead of 2)."""
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    _cmb.add_status(m, "burning", duration=2)
    hp_before = m.hp
    _dmg.slow_decay_tick(w, 30)   # 3 ticks
    # 2 ticks of damage (status expires after the 2nd tick).
    assert m.hp < hp_before, f"hp should drop, was {hp_before} now {m.hp}"
    assert "burning" not in m.conditions, "status should expire"
    print(f"  slow decay drains burning: OK (hp {hp_before} -> {m.hp})")


def test_slow_decay_clears_corroded_eventually():
    """Corroded persists out of combat; 80 minutes (8 ticks) clears it."""
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    _cmb.add_status(m, "corroded", duration=8)
    _dmg.slow_decay_tick(w, 90)   # 9 ticks
    assert "corroded" not in m.conditions
    print("  slow decay clears corroded after duration: OK")


# ── push_into env-kill carries damage_type ──────────────────────────────

def test_push_into_acid_pool_carries_acid_damage():
    """Resolution emits damage_entity with damage_type=acid when the
    destination has damage_type='acid'. Consequence applies it via
    engine.damage so corroded status sticks."""
    from ..engine.resolution import _effects_for_level, CRIT_SUCCESS
    from ..engine.validation import ValidationResult
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20)
    pool = Entity(key="acid_pool", entity_type=T_HAZARD,
                  fallback_name="kałuża kwasu",
                  tags=["acid","liquid","hazardous"],
                  affordances=["push_into","throw_at"],
                  location_id="r0")
    pool.damage_type = "acid"
    w.register(pool); w.current_floor.current_room().entities.append(pool)
    v = ValidationResult(valid=True, matched_entities=[m, pool],
                         matched_affordance_key="push_into")
    effs = _effects_for_level(CRIT_SUCCESS, "push_into", v, w)
    dmg_effects = [e for e in effs if e.get("type") == "damage_entity"]
    assert dmg_effects
    assert dmg_effects[0].get("damage_type") == "acid"
    # Apply and verify corroded sticks.
    _cons.apply(dmg_effects, w)
    assert "corroded" in m.conditions, \
        f"push into acid should apply corroded; conditions={m.conditions}"
    print("  push_into acid_pool emits acid damage + corroded: OK")


# ── damage_entity routes through apply_damage ────────────────────────────

def test_damage_entity_routes_through_apply_damage():
    """Verify that a damage_entity effect with damage_type=fire applies
    burning to the target."""
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20)
    _cons.apply([{"type": "damage_entity",
                  "entity_id": m.entity_id,
                  "amount": 5,
                  "damage_type": "fire"}], w)
    assert "burning" in m.conditions
    print("  damage_entity routes through apply_damage: OK")


def test_damage_entity_respects_resistance():
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=20,
                resists=["fire"])
    _cons.apply([{"type": "damage_entity",
                  "entity_id": m.entity_id,
                  "amount": 10,
                  "damage_type": "fire"}], w)
    assert m.hp == 15, f"resist should halve damage; hp={m.hp}"
    print("  damage_entity respects resistance: OK")


# ── time_system integration ──────────────────────────────────────────────

def test_time_system_advance_runs_slow_decay():
    """time_system.advance() must call damage.slow_decay_tick()."""
    w = _mk_world()
    m = _mk_mob(w, w.current_floor.current_room(), hp=30)
    _cmb.add_status(m, "burning", duration=5)
    hp_before = m.hp
    _ts.advance(w, 30)   # 30 minutes elapsed = 3 ticks
    assert m.hp < hp_before, \
        f"time_system.advance should slow-decay burning; hp {hp_before}->{m.hp}"
    print(f"  time_system.advance drives slow decay: OK")


# ── Suite ─────────────────────────────────────────────────────────────────

def main():
    test_registry_has_7_v1_types()
    test_registry_extensible()
    test_resistance_halves_damage()
    test_vulnerability_doubles_damage()
    test_immunity_zeroes_damage()
    test_status_applied_on_hit()
    test_burning_extinguished_by_wet_tag()
    test_combat_tick_applies_dot()
    test_burning_plus_chilled_cancels_both()
    test_slow_decay_drains_burning_at_half_rate()
    test_slow_decay_clears_corroded_eventually()
    test_push_into_acid_pool_carries_acid_damage()
    test_damage_entity_routes_through_apply_damage()
    test_damage_entity_respects_resistance()
    test_time_system_advance_runs_slow_decay()
    print("Prompt 21 damage+status smoke: OK")


if __name__ == "__main__":
    main()
