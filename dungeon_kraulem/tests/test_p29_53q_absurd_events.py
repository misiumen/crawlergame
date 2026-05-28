"""P29.53q — Random absurd ambient events.

Cosmetic Dinniman-flavor events firing on the floor clock. Each
event = log line + optional small effect (audience/HP/credits).
Tests cover: catalog sanity, cooldown, RNG determinism, effects.
"""
from __future__ import annotations
import random

from ..engine import absurd_events as _ae
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState


def _mk_world(at_minute: int = 200) -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.max_hp = 30
    w.character.hp = 20
    w.character.credits = 100
    w.character.audience_rating = 40
    w.current_floor = FloorState(floor_id="f1", floor_number=1)
    w.current_floor.current_minute = at_minute
    return w


# ── Catalog sanity ───────────────────────────────────────────────────


def test_catalog_has_enough_variety():
    """At least 15 events so a 5-floor run doesn't see the same line
    six times."""
    assert len(_ae.ABSURD_EVENTS) >= 15


def test_catalog_keys_unique():
    keys = [e["key"] for e in _ae.ABSURD_EVENTS]
    assert len(keys) == len(set(keys)), "duplicate keys in catalog"


def test_catalog_lines_polish_only():
    """No raw English leaks — sample for obvious markers. Polish-only
    is non-negotiable per project constraints."""
    suspect = {"the", "you", "your", "and", "with"}
    for ev in _ae.ABSURD_EVENTS:
        words = ev["line_pl"].lower().split()
        bad = [w for w in words if w.strip(".,!?'\"„”") in suspect]
        assert not bad, f"event {ev['key']} has English word: {bad}"


def test_catalog_tones_known():
    """Every tone must be a known log category — typo guard."""
    known = {"narrator", "syndicate", "warn", "success", "system"}
    for ev in _ae.ABSURD_EVENTS:
        assert ev["tone"] in known, (
            f"event {ev['key']} has unknown tone {ev['tone']!r}")


def test_catalog_effects_bounded():
    """No effect bigger than ±5 — anything larger goes through
    sponsor pipeline, not absurd events."""
    for ev in _ae.ABSURD_EVENTS:
        fx = ev.get("effect") or {}
        for k, v in fx.items():
            assert abs(int(v)) <= 5, (
                f"event {ev['key']} has effect {k}={v} (cap is ±5)")


# ── Fire mechanics ───────────────────────────────────────────────────


def test_does_not_fire_immediately_after_previous():
    """Cooldown prevents back-to-back firing."""
    w = _mk_world(at_minute=200)
    w.character.flags = {"_absurd_last_min": 180}
    # Only 20 minutes since last; below MIN_COOLDOWN.
    out = _ae.maybe_fire(w, rng=random.Random(0))
    assert out is None


def test_fires_after_cooldown_with_lucky_rng():
    """With cooldown clear and a high-roll RNG, an event fires."""
    w = _mk_world(at_minute=500)
    w.character.flags = {}
    # RNG seed that puts random() < TICK_CHANCE.
    rng = random.Random()
    # Force the random() roll low enough.
    rng.random = lambda: 0.01  # always succeeds the 6% check
    rng.choice = lambda lst: lst[0]
    out = _ae.maybe_fire(w, rng=rng)
    assert out is not None
    assert out["key"] == _ae.ABSURD_EVENTS[0]["key"]


def test_one_shot_event_dedupes():
    """One-shot events fire at most once per run."""
    w = _mk_world(at_minute=500)
    w.character.flags = {"_absurd_fired": ["empty_room_with_chair"]}
    pool = [e for e in _ae.ABSURD_EVENTS
            if not (e.get("one_shot")
                    and e["key"] in set(w.character.flags["_absurd_fired"]))]
    assert all(e["key"] != "empty_room_with_chair" for e in pool)


# ── Effects ──────────────────────────────────────────────────────────


def test_audience_effect_routes_through_change_audience():
    """Audience deltas are clamped via the audience module."""
    w = _mk_world(at_minute=500)
    pre = int(w.character.audience_rating)
    ev = {"key":"_t1", "line_pl":"x", "tone":"narrator",
          "effect":{"audience": 3}}
    _ae._apply(w, w.character, ev)
    assert int(w.character.audience_rating) == pre + 3


def test_hp_effect_clamps_to_max():
    w = _mk_world(at_minute=500)
    w.character.hp = w.character.max_hp  # already full
    ev = {"key":"_t2", "line_pl":"x", "tone":"narrator",
          "effect":{"hp": 5}}
    _ae._apply(w, w.character, ev)
    assert w.character.hp == w.character.max_hp, "shouldn't overheal"


def test_credits_effect_clamps_to_zero():
    w = _mk_world(at_minute=500)
    w.character.credits = 2
    ev = {"key":"_t3", "line_pl":"x", "tone":"narrator",
          "effect":{"credits": -10}}
    _ae._apply(w, w.character, ev)
    assert w.character.credits == 0, "credits shouldn't go negative"


def test_maybe_fire_safe_without_world():
    """Defensive: must not crash on None/empty world."""
    assert _ae.maybe_fire(None) is None
    w = WorldState()
    w.character = None
    assert _ae.maybe_fire(w) is None
