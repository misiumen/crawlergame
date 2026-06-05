"""P29.53m — Graduated VATS body damage.

Damaged/crippled limbs should affect combat even before broken, not
just at HP=0. Severity tiers: intact ≥75%, damaged 25-75%,
crippled 1-25%, broken 0. User complaint: "złamałem tors szczura
kompletnie, nie zmieniło to nic w jego zachowaniu".
"""
from __future__ import annotations

from ..content.data import body_plans as _bp
from ..engine.entity import Entity, T_MONSTER


def _mk_monster(hp: int = 20, max_hp: int = 20) -> Entity:
    e = Entity(key="goblin", entity_type=T_MONSTER, fallback_name="goblin",
               hp=hp, max_hp=max_hp,
               tags=["monster", "humanoid"],
               damage_dice="1d6", attack_bonus=2)
    _bp.init_body_parts(e)
    return e


# ── severity classifier ──────────────────────────────────────────────


def test_severity_classifier_tiers():
    intact = {"hp": 10, "max_hp": 10, "broken": False}
    just_damaged = {"hp": 6, "max_hp": 10, "broken": False}
    crippled = {"hp": 2, "max_hp": 10, "broken": False}
    dead = {"hp": 0, "max_hp": 10, "broken": True}
    assert _bp.part_severity(intact) == _bp.SEVERITY_INTACT
    assert _bp.part_severity(just_damaged) == _bp.SEVERITY_DAMAGED
    assert _bp.part_severity(crippled) == _bp.SEVERITY_CRIPPLED
    assert _bp.part_severity(dead) == _bp.SEVERITY_BROKEN


def test_severity_75_percent_is_intact():
    """Boundary: 75% exactly = intact (not damaged)."""
    p = {"hp": 75, "max_hp": 100, "broken": False}
    assert _bp.part_severity(p) == _bp.SEVERITY_INTACT


def test_severity_at_25_percent_is_damaged():
    """Boundary: 25% exactly = damaged (not crippled)."""
    p = {"hp": 25, "max_hp": 100, "broken": False}
    assert _bp.part_severity(p) == _bp.SEVERITY_DAMAGED


# ── combat mods ──────────────────────────────────────────────────────


def test_intact_body_has_no_combat_mods():
    e = _mk_monster()
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 0
    assert mods["attack_to_hit_delta"] == 0
    assert mods["speed_delta"] == 0


def test_damaged_arm_subtracts_damage_but_not_to_hit():
    e = _mk_monster()
    arm = e.body_parts["l_arm"]
    arm["hp"] = int(arm["max_hp"] * 0.5)   # damaged tier
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 1
    assert mods["attack_to_hit_delta"] == 0


def test_crippled_arm_subtracts_more():
    e = _mk_monster()
    arm = e.body_parts["l_arm"]
    arm["hp"] = 1   # crippled (1/zone_max < 25%)
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 2
    assert mods["attack_to_hit_delta"] == 1


def test_broken_arm_does_not_double_dip():
    """Broken parts are handled by STATUS_DISARMED — not via mods.
    body_combat_mods MUST skip broken to avoid stacking penalties."""
    e = _mk_monster()
    arm = e.body_parts["l_arm"]
    arm["hp"] = 0
    arm["broken"] = True
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 0
    assert mods["attack_to_hit_delta"] == 0


def test_crippled_leg_does_not_subtract_damage():
    """Leg damage hits speed/to-hit only, not damage roll."""
    e = _mk_monster()
    leg = e.body_parts["l_leg"]
    leg["hp"] = 1
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 0
    assert mods["attack_to_hit_delta"] == 1
    assert mods["speed_delta"] == 2


def test_damaged_head_subtracts_to_hit():
    e = _mk_monster()
    head = e.body_parts["head"]
    head["hp"] = int(head["max_hp"] * 0.5)
    mods = _bp.body_combat_mods(e)
    assert mods["attack_to_hit_delta"] == 1


def test_multiple_damaged_zones_stack():
    e = _mk_monster()
    e.body_parts["l_arm"]["hp"] = 1   # crippled arm
    e.body_parts["r_arm"]["hp"] = int(e.body_parts["r_arm"]["max_hp"] * 0.5)
    # crippled L-arm: +2 dmg, +1 to-hit
    # damaged R-arm: +1 dmg
    mods = _bp.body_combat_mods(e)
    assert mods["attack_dmg_delta"] == 3
    assert mods["attack_to_hit_delta"] == 1


# ── integration: enemy damage rolls drop with damaged arms ────────────


def test_enemy_attack_damage_drops_with_crippled_arm():
    """End-to-end: a goblin with a crippled arm rolls less damage on
    average than an intact one. Seed RNG for determinism."""
    import random
    intact = _mk_monster()
    busted = _mk_monster()
    arm = busted.body_parts["l_arm"]
    arm["hp"] = 1   # crippled, -2 dmg

    from ..engine.combat import _enemy_attack_damage
    # Sample many rolls; assert mean damage is lower for the busted one.
    random.seed(7)
    intact_total = sum(_enemy_attack_damage(intact) for _ in range(200))
    random.seed(7)
    busted_total = sum(_enemy_attack_damage(busted) for _ in range(200))
    assert busted_total < intact_total, (
        f"crippled arm should reduce dmg over 200 rolls; "
        f"intact={intact_total} busted={busted_total}")
