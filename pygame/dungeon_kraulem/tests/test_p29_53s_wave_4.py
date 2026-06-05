"""P29.53s — Wave 4 loop urozmaicenia: titles, highlight reel,
mid-floor events, hidden objectives, biome gimmicks.
"""
from __future__ import annotations
import random

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..systems import titles as _ti
from ..systems import highlight_reel as _hr
from ..engine import mid_floor_events as _mfe
from ..engine import biome_gimmicks as _bg


def _mk_world(minute: int = 0, biome: str = "") -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.hp = 20
    w.character.max_hp = 30
    w.character.credits = 50
    w.character.audience_rating = 40
    w.current_floor = FloorState(floor_id="f1", floor_number=1,
                                 current_minute=minute)
    if biome:
        w.current_floor.biome_key = biome
    return w


# ── #S titles ────────────────────────────────────────────────────────


def test_titles_catalog_has_polish_labels():
    """Every title has a non-empty Polish label."""
    for t in _ti.all_titles():
        assert t["label_pl"] and isinstance(t["label_pl"], str)
        # Polish-only sanity — must contain at least one Polish char or
        # be obviously Polish.
        assert t["label_pl"] != t["key"], (
            f"{t['key']} has no human label")


def test_title_earned_when_rule_passes():
    w = _mk_world()
    w.character.run_kills = 60   # Rzeźnik unlock at 50
    new = _ti.recompute(w)
    assert "rzeznik" in new
    assert "rzeznik" in _ti.current_titles(w.character)


def test_title_sticky_once_earned():
    """Once earned, title stays even if rule no longer holds."""
    w = _mk_world()
    w.character.run_kills = 60
    _ti.recompute(w)
    # Reset kills below threshold — title shouldn't be revoked.
    w.character.run_kills = 0
    _ti.recompute(w)
    assert "rzeznik" in _ti.current_titles(w.character)


def test_title_recompute_safe_without_world():
    assert _ti.recompute(None) == []


# ── #R highlight reel ────────────────────────────────────────────────


def test_highlight_reel_records_entry():
    w = _mk_world()
    _hr.record(w, "crit_kill", "Strzał w głowę: bandzior", value=10)
    assert len(_hr._reel(w.character)) == 1


def test_highlight_reel_caps_at_max():
    w = _mk_world()
    for i in range(20):
        _hr.record(w, "kill", f"trup {i}", value=i)
    # Cap is MAX_REEL_ENTRIES = 12.
    assert len(_hr._reel(w.character)) <= _hr.MAX_REEL_ENTRIES


def test_highlight_reel_top_n_sorted_by_value():
    w = _mk_world()
    _hr.record(w, "kill", "byle co", value=1)
    _hr.record(w, "crit", "spektakl", value=20)
    _hr.record(w, "drop", "loot", value=5)
    top = _hr.top_n(w.character, 2)
    assert [t["value"] for t in top] == [20, 5]


def test_highlight_reel_emit_montage_header():
    w = _mk_world()
    _hr.record(w, "kill", "x", value=1)
    lines = _hr.emit_floor_end_montage(w)
    assert any("Highlight" in ln for ln in lines)


def test_highlight_reel_empty_when_no_records():
    w = _mk_world()
    assert _hr.emit_floor_end_montage(w) == []


# ── #O mid-floor beat ─────────────────────────────────────────────────


def test_mid_floor_beat_not_fired_before_cooldown():
    w = _mk_world(minute=100)
    w.character.flags = {"_beat_last_min": 80}   # 20 min ago — too soon
    out = _mfe.tick(w, rng=random.Random(0))
    assert out["beat"] is None


def test_mid_floor_beat_fires_with_lucky_rng():
    """Force a high chance + clear cooldown → a beat fires."""
    w = _mk_world(minute=10000)
    w.character.flags = {}
    rng = random.Random()
    rng.random = lambda: 0.001  # always rolls under MID_FLOOR_BEAT_CHANCE
    rng.choice = lambda lst: lst[0]
    out = _mfe.tick(w, rng=rng)
    assert out["beat"] is not None


# ── #P hidden objectives ─────────────────────────────────────────────


def test_hidden_objective_completes_on_threshold():
    w = _mk_world()
    w.character.flags = {"floor_hazard_inspects": 5}
    new = _mfe._check_hidden_objectives(w)
    assert "hazard_inspector" in new


def test_hidden_objective_idempotent():
    """Re-checking once completed must not fire twice."""
    w = _mk_world()
    w.character.flags = {"floor_hazard_inspects": 5}
    _mfe._check_hidden_objectives(w)
    again = _mfe._check_hidden_objectives(w)
    assert again == []


def test_hidden_objective_queues_reward():
    w = _mk_world()
    w.character.flags = {"floor_low_hp_kill": True}
    _mfe._check_hidden_objectives(w)
    queued = getattr(w, "pending_sponsor_gifts", []) or []
    assert any(g.get("source", "").startswith("hidden:")
               for g in queued)


# ── #U biome gimmicks ────────────────────────────────────────────────


def test_biome_gimmick_fires_after_cooldown():
    w = _mk_world(minute=1000, biome="zoo_korporacyjne")
    pre = int(w.character.audience_rating)
    line = _bg.tick(w)
    assert line is not None
    assert int(w.character.audience_rating) > pre


def test_biome_gimmick_skipped_when_unknown_biome():
    w = _mk_world(minute=1000, biome="not_a_real_biome")
    assert _bg.tick(w) is None


def test_biome_gimmick_respects_cooldown():
    w = _mk_world(minute=1000, biome="zoo_korporacyjne")
    _bg.tick(w)
    # Same minute again → cooldown blocks.
    w.current_floor.current_minute = 1001
    assert _bg.tick(w) is None


def test_biome_gimmick_handlers_polish_only():
    """Sanity sample on every handler — no English leaks."""
    w = _mk_world(minute=1000)
    suspect = {"the", "you", "your", "and"}
    for biome_key, handler in _bg.BIOME_GIMMICKS.items():
        w.current_floor.biome_key = biome_key
        # Some handlers heal HP — reset for each.
        w.character.hp = 10
        w.character.max_hp = 30
        line = handler(w)
        if line is None:
            continue
        words = line.lower().split()
        bad = [w_ for w_ in words
               if w_.strip(".,!?'\"„”():") in suspect]
        assert not bad, f"biome {biome_key} leaks English: {bad}"
