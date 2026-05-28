"""P29.53p — Audience-as-lever combat mods.

The user explicitly rejected "audience as currency" — players don't
spend it. Instead, the CURRENT band dynamically pulls combat outcomes:
HOT/VIRAL = +to-hit + bigger kill bonus, COLD = penalty + minimum
bonus. Tests cover the helper and the per-band shape of the mods.
"""
from __future__ import annotations

from ..engine import audience as _aud
from ..engine.world import WorldState
from ..engine.character import Character


def _mk_world(audience: int) -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.audience_rating = audience
    return w


def test_cold_band_imposes_to_hit_penalty():
    mods = _aud.combat_mods_for_world(_mk_world(10))
    assert mods["band"] == _aud.BAND_COLD
    assert mods["to_hit"] == -1


def test_warming_band_is_neutral():
    mods = _aud.combat_mods_for_world(_mk_world(30))
    assert mods["band"] == _aud.BAND_WARMING
    assert mods["to_hit"] == 0


def test_hot_band_grants_bonus():
    mods = _aud.combat_mods_for_world(_mk_world(60))
    assert mods["band"] == _aud.BAND_HOT
    assert mods["to_hit"] == 1


def test_viral_band_grants_bigger_bonus():
    mods = _aud.combat_mods_for_world(_mk_world(90))
    assert mods["band"] == _aud.BAND_VIRAL
    assert mods["to_hit"] == 2


def test_kill_bonus_scales_with_band():
    """Kill bonus should be smallest in COLD and biggest in VIRAL —
    encourages the player to keep the show going."""
    cold = _aud.combat_mods_for_world(_mk_world(5))["audience_on_kill"]
    viral = _aud.combat_mods_for_world(_mk_world(95))["audience_on_kill"]
    assert viral > cold, (
        f"viral kill bonus ({viral}) should exceed cold ({cold})")
    # Concrete shape: 1 / 2 / 3 / 5
    assert cold == 1
    assert viral == 5


def test_combat_mods_safe_without_character():
    """Defensive — engine must not crash if character/world missing."""
    assert _aud.combat_mods_for_world(None) == {
        "to_hit": 0, "audience_on_kill": 0, "band": _aud.BAND_COLD}
    w = WorldState()
    w.character = None
    assert _aud.combat_mods_for_world(w)["to_hit"] == 0


def test_band_bonuses_dont_swing_too_hard():
    """Mods cap at ±2 to-hit so they shade encounters but don't replace
    skill. Sanity guard against future authoring drift."""
    for rating in (0, 25, 60, 100):
        mods = _aud.combat_mods_for_world(_mk_world(rating))
        assert -2 <= mods["to_hit"] <= 2
