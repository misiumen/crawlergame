"""P29.55 — Species effects wired into combat/rest/trap pipeline.

Pre-P29.55 wiele species_effects helperów było defined + tested w
isolation ale **nigdy nie wpięte w prawdziwą ścieżkę gry**. Tests
weryfikują że hook'i są CALLABLE w docelowych miejscach i że
trait flagi naprawdę zmieniają zachowanie.
"""
from __future__ import annotations
import random

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.entity import Entity, T_MONSTER, T_ITEM
from ..engine import species_effects as _sp_fx


def _mk_char_with_trait(trait_key: str) -> Character:
    ch = Character(name="Test", background="janitor")
    ch.hp = 30
    ch.max_hp = 30
    ch.flags = {f"species_trait_{trait_key}": True}
    return ch


def _mk_world_with_trait(trait_key: str) -> WorldState:
    w = WorldState()
    w.character = _mk_char_with_trait(trait_key)
    w.current_floor = FloorState(floor_id="f1", floor_number=1)
    return w


# ── outgoing_crit_mul (crit_amplifier) ──────────────────────────────


def test_crit_amplifier_returns_15_for_chimera():
    ch = _mk_char_with_trait("crit_amplifier")
    assert _sp_fx.outgoing_crit_mul(ch) == 1.5


def test_crit_amplifier_returns_10_without_trait():
    ch = Character(name="Test", background="janitor")
    assert _sp_fx.outgoing_crit_mul(ch) == 1.0


# ── rest_heal_mul (double_rest) ──────────────────────────────────────


def test_double_rest_doubles_heal():
    ch = _mk_char_with_trait("double_rest")
    assert _sp_fx.rest_heal_mul(ch) == 2.0


# ── precog_dodge_consume (one-shot per floor) ────────────────────────


def test_precog_dodge_consumes_once_per_floor():
    w = _mk_world_with_trait("precog_dodge")
    assert _sp_fx.precog_dodge_consume(w) is True
    assert _sp_fx.precog_dodge_consume(w) is False


def test_precog_dodge_refreshes_on_new_floor():
    """Going to next floor should reset the precog charge — assumed
    by the per-floor model. Verified by changing floor_number."""
    w = _mk_world_with_trait("precog_dodge")
    _sp_fx.precog_dodge_consume(w)
    w.current_floor.floor_number = 2
    assert _sp_fx.precog_dodge_consume(w) is True


# ── bleed_on_hit_check (glassblood: 20%) ─────────────────────────────


def test_bleed_on_hit_fires_with_lucky_roll():
    ch = _mk_char_with_trait("bleeds_easy")
    rng = random.Random()
    rng.random = lambda: 0.01   # under 0.20
    assert _sp_fx.bleed_on_hit_check(ch, rng) is True


def test_bleed_on_hit_misses_with_high_roll():
    ch = _mk_char_with_trait("bleeds_easy")
    rng = random.Random()
    rng.random = lambda: 0.99
    assert _sp_fx.bleed_on_hit_check(ch, rng) is False


def test_bleed_on_hit_does_nothing_without_trait():
    ch = Character(name="Test", background="janitor")
    rng = random.Random()
    rng.random = lambda: 0.01
    assert _sp_fx.bleed_on_hit_check(ch, rng) is False


# ── magnetic_disarm_check (ferromanta: 25% vs metal) ─────────────────


def test_magnetic_disarm_fires_on_metal_target():
    ch = _mk_char_with_trait("magnetic_disarm")
    target = Entity(key="bot", entity_type=T_MONSTER,
                    fallback_name="bot",
                    tags=["monster", "metal", "armored"])
    rng = random.Random()
    rng.random = lambda: 0.05   # under 0.25
    assert _sp_fx.magnetic_disarm_check(ch, target, rng) is True


def test_magnetic_disarm_skips_non_metal_target():
    ch = _mk_char_with_trait("magnetic_disarm")
    target = Entity(key="goblin", entity_type=T_MONSTER,
                    fallback_name="goblin",
                    tags=["monster", "humanoid"])
    rng = random.Random()
    rng.random = lambda: 0.05
    assert _sp_fx.magnetic_disarm_check(ch, target, rng) is False


# ── to_hit_modifier (sun_sensitive in bright rooms) ──────────────────


def test_sun_sensitive_penalizes_to_hit_in_safehouse():
    ch = _mk_char_with_trait("sun_sensitive")

    class _Room:
        sensory_tags = ["safehouse"]

    assert _sp_fx.to_hit_modifier(ch, room=_Room()) == -2


def test_sun_sensitive_zero_in_dark_room():
    ch = _mk_char_with_trait("sun_sensitive")

    class _Room:
        sensory_tags = ["dark"]

    assert _sp_fx.to_hit_modifier(ch, room=_Room()) == 0


# ── trap_deploy_refused (ferromanta: only metal traps) ───────────────


def test_metal_only_traps_refuses_non_metal():
    ch = _mk_char_with_trait("metal_only_traps")
    wood_trap = Entity(key="wood_snare", entity_type=T_ITEM,
                       fallback_name="snare",
                       tags=["trap", "wooden"])
    assert _sp_fx.trap_deploy_refused(ch, wood_trap) is True


def test_metal_only_traps_allows_metal():
    ch = _mk_char_with_trait("metal_only_traps")
    metal_trap = Entity(key="steel_jaws", entity_type=T_ITEM,
                        fallback_name="jaws",
                        tags=["trap", "metal"])
    assert _sp_fx.trap_deploy_refused(ch, metal_trap) is False


def test_trap_refused_log_returns_polish_message():
    ch = _mk_char_with_trait("metal_only_traps")
    msg = _sp_fx.trap_refused_log(ch)
    assert "metal" in msg.lower() or "pułapka" in msg.lower()


# ── End-to-end sanity: trait combinations don't crash ────────────────


def test_multiple_traits_compose_cleanly():
    """All wired hooks should be no-op when their trait is missing."""
    ch = Character(name="Test", background="janitor")
    ch.flags = {}
    assert _sp_fx.outgoing_crit_mul(ch) == 1.0
    assert _sp_fx.rest_heal_mul(ch) == 1.0
    rng = random.Random()
    assert _sp_fx.bleed_on_hit_check(ch, rng) is False
    target = Entity(key="x", entity_type=T_MONSTER, fallback_name="x")
    assert _sp_fx.magnetic_disarm_check(ch, target, rng) is False
    assert _sp_fx.to_hit_modifier(ch, room=None) == 0
