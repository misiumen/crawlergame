"""Prompt 27.7 — class features + starter loadouts smoke suite.

Covers:
  * class_features.passive_bonus returns 0 with no class
  * Each class registered in CLASS_PASSIVES + CLASS_ACTIVES
  * assign_class applies hp_max passive and undoes prior on reassign
  * survivor passive: AC +1 reflected in effective_ac
  * showman passive: audience_multiplier doubles positive gains
  * medic passive: heal_multiplier returns 2.0
  * use_active heals (survivor), once per floor (cooldown)
  * use_active without class returns refusal
  * Each starter background gets at least 1 pre-equipped item
  * Parser routes 'umiejętność' to class_active intent
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character, BACKGROUNDS
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..systems import class_features as _cf
from ..systems import classes as _cls
from ..engine import audience as _aud
from ..engine import parser_core as _pc


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Klinika")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── Passive bonuses ──────────────────────────────────────────────────────

def test_passive_zero_without_class():
    w = _mk_world()
    assert _cf.passive_bonus(w.character, "hp_max") == 0
    assert _cf.passive_bonus(w.character, "ac") == 0
    print("  passive_bonus 0 without class: OK")


def test_every_class_has_passive_and_active():
    missing = []
    for key in _cls.CLASS_CATALOG.keys():
        if key not in _cf.CLASS_PASSIVES:
            missing.append(f"passive:{key}")
        if key not in _cf.CLASS_ACTIVES:
            missing.append(f"active:{key}")
    assert not missing, f"missing class entries: {missing}"
    print(f"  every class has passive + active: {len(_cls.CLASS_CATALOG)} classes OK")


def test_assign_class_applies_hp_max():
    w = _mk_world()
    pre_max = w.character.max_hp
    ok = _cls.assign_class(w, "bruiser")  # hp_max +20
    assert ok
    assert w.character.max_hp == pre_max + 20
    assert w.character.class_key == "bruiser"
    print(f"  bruiser hp_max {pre_max}→{w.character.max_hp}: OK")


def test_reassign_class_undoes_prior_hp_max():
    w = _mk_world()
    pre_max = w.character.max_hp
    _cls.assign_class(w, "bruiser")    # +20
    _cls.assign_class(w, "ranger")     # ranger has no hp_max → back to baseline
    assert w.character.max_hp == pre_max, \
        f"expected baseline {pre_max}, got {w.character.max_hp}"
    print(f"  reassign undoes prior hp_max bump: OK ({w.character.max_hp})")


def test_survivor_ac_passive_reflected():
    w = _mk_world()
    pre_ac = w.character.effective_ac()
    _cls.assign_class(w, "survivor")
    post_ac = w.character.effective_ac()
    assert post_ac == pre_ac + 1, f"AC: pre={pre_ac} post={post_ac}"
    print(f"  survivor AC {pre_ac}→{post_ac}: OK")


def test_showman_audience_multiplier():
    w = _mk_world()
    _cls.assign_class(w, "showman")
    pre = w.character.audience_rating
    _aud.change_audience(w, 4, source="test", emit_log=False)
    delta = w.character.audience_rating - pre
    assert delta >= 8, f"showman should ≥2× a +4 bump; got {delta}"
    print(f"  showman 2× audience: +4 → +{delta}: OK")


def test_medic_heal_multiplier():
    w = _mk_world()
    _cls.assign_class(w, "medic")
    mul = _cf.heal_multiplier(w.character)
    assert mul >= 2.0
    print(f"  medic heal multiplier: ×{mul}: OK")


# ── Active abilities ─────────────────────────────────────────────────────

def test_active_requires_class():
    w = _mk_world()
    ok, line = _cf.use_active(w)
    assert not ok
    print(f"  active without class refused: {line}: OK")


def test_active_heals_then_cooldown():
    w = _mk_world()
    _cls.assign_class(w, "survivor")
    w.character.hp = 30
    ok, line = _cf.use_active(w)
    assert ok, line
    assert w.character.hp > 30
    # Second use same floor → refused.
    ok2, line2 = _cf.use_active(w)
    assert not ok2
    print(f"  survivor active heal + cooldown: {line}: OK")


def test_active_resets_per_floor():
    w = _mk_world()
    _cls.assign_class(w, "survivor")
    _cf.use_active(w)
    # Advance to a new floor.
    f2 = FloorState(floor_id="f2", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="A")
    f2.add_room(r); f2.start_room_id = "r0"; f2.current_room_id = "r0"
    w.current_floor = f2
    w.character.hp = 20
    ok, _ = _cf.use_active(w)
    assert ok, "active should reset on new floor"
    print("  active resets per floor: OK")


# ── Starter loadouts ─────────────────────────────────────────────────────

def test_every_background_pre_equipped():
    """Each background creates at least one item in a slot or wield
    after start_new_game."""
    from ..engine.game import Game
    fails = []
    for bg in BACKGROUNDS:
        g = Game(screen=None)
        g.start_new_game("Test", bg)
        ch = g.world.character
        equipped = (bool(ch.worn_slots)
                    or ch.wielded_main_id is not None
                    or ch.wielded_offhand_id is not None)
        if not equipped:
            fails.append(bg)
    assert not fails, f"backgrounds without starter loadout: {fails}"
    print(f"  all {len(BACKGROUNDS)} backgrounds pre-equipped: OK")


def test_security_guard_specific_loadout():
    from ..engine.game import Game
    g = Game(screen=None)
    g.start_new_game("Test", "security_guard")
    ch = g.world.character
    assert "torso" in ch.worn_slots, "security_guard should wear kamizelka"
    assert "legs" in ch.worn_slots, "security_guard should wear boots"
    assert ch.wielded_main_id is not None, "security_guard should wield flashlight"
    print(f"  security_guard: torso+legs+main wielded: OK")


# ── Parser ───────────────────────────────────────────────────────────────

def test_parser_routes_umiejetnosc():
    intent = _pc.parse("umiejętność", world=None)
    assert intent.intent == "class_active", f"got {intent.intent}"
    print(f"  parser: 'umiejętność' → class_active: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_passive_zero_without_class()
    test_every_class_has_passive_and_active()
    test_assign_class_applies_hp_max()
    test_reassign_class_undoes_prior_hp_max()
    test_survivor_ac_passive_reflected()
    test_showman_audience_multiplier()
    test_medic_heal_multiplier()
    test_active_requires_class()
    test_active_heals_then_cooldown()
    test_active_resets_per_floor()
    test_every_background_pre_equipped()
    test_security_guard_specific_loadout()
    test_parser_routes_umiejetnosc()
    print("Prompt 27.7 class features + starter loadouts smoke: OK")


if __name__ == "__main__":
    main()
