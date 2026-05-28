"""P29.53o — Floor objective picker respects floor_min/floor_max.

User complaint: F1 had find_keycard objective but the keycards didn't
unlock doors (now P29.53c fixed the unlock). The remaining ask: F1
should not even draw the keycard objective — it should be boss-driven
via the new pool_intake_boss (P29.46) + bypass_warden.
"""
from __future__ import annotations
import random

from ..content.data.floor_objective_templates import FLOOR_OBJECTIVE_TEMPLATES


def test_find_keycard_starts_at_floor_2():
    """F1 should not draw the keycard objective at all."""
    obj = FLOOR_OBJECTIVE_TEMPLATES["find_keycard"]
    assert obj["floor_min"] >= 2, (
        "find_keycard must be locked out of F1 per user feedback")


def test_bypass_warden_available_on_floor_1():
    """The boss-driven objective must be a valid F1 candidate."""
    obj = FLOOR_OBJECTIVE_TEMPLATES["bypass_warden"]
    assert obj.get("floor_min", 1) <= 1 <= obj.get("floor_max", 99)


def test_pick_objective_respects_bounds_on_floor_1():
    """Calling the picker for F1 over many seeds must never produce a
    keycard objective."""
    from ..engine.floor_generator import _pick_objective
    from ..engine.floor import FloorState
    # All archetypes that previously prefer find_keycard — pick one to
    # force preferred_objectives full of keycard. With bounds enforced,
    # F1 must still skip it.
    arch = {"preferred_objectives": ["find_keycard", "bypass_warden"]}
    for seed in range(40):
        f = FloorState(floor_id="floor_1", floor_number=1)
        rng = random.Random(seed)
        _pick_objective(f, arch, rng)
        assert f.objective_key != "find_keycard", (
            f"seed={seed}: F1 got find_keycard despite floor_min=2")


def test_pick_objective_allows_keycard_on_floor_2():
    """F2 SHOULD still be able to roll keycard (it's the intended floor
    for the mechanic)."""
    from ..engine.floor_generator import _pick_objective
    from ..engine.floor import FloorState
    arch = {"preferred_objectives": ["find_keycard"]}
    f = FloorState(floor_id="floor_2", floor_number=2)
    rng = random.Random(0)
    _pick_objective(f, arch, rng)
    assert f.objective_key == "find_keycard"


def test_pick_objective_falls_back_to_bypass_warden_when_empty():
    """If preferred_objectives is empty/out-of-bounds, fall back to
    bypass_warden so the floor always has a clearable exit."""
    from ..engine.floor_generator import _pick_objective
    from ..engine.floor import FloorState
    arch = {"preferred_objectives": ["find_keycard"]}  # blocked on F1
    f = FloorState(floor_id="floor_1", floor_number=1)
    rng = random.Random(0)
    _pick_objective(f, arch, rng)
    # F1 + only-keycard preferred → fall through to any-in-bounds. Must
    # pick SOMETHING and that something must be valid for F1.
    assert f.objective_key, "picker left objective empty on F1"
    picked = FLOOR_OBJECTIVE_TEMPLATES[f.objective_key]
    assert picked.get("floor_min", 1) <= 1 <= picked.get("floor_max", 99)
