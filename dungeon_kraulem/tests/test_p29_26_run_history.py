"""Prompt 29.26 — Persistent run history + leaderboard + NG+ smoke.

Audit headline finding: no run-history file existed. Death wiped the
slot, nothing persisted. No NewGame+ on victory. Meta-progression
across deaths was impossible.

P29.26 ships engine/run_history.py: every death + victory appends a
RunSummary entry to dungeon_kraulem_runs.json. Meta block tracks
total_runs, victories, fans_total (cumulative audience peaks across
all runs), and a list of unlocked NG+ flags.

Covers:
  * record_run on death appends a non-victory entry + bumps
    total_runs.
  * record_run on victory appends a victory entry, bumps
    victories, AND stamps the new_game_plus unlock.
  * history() returns newest-first.
  * leaderboard() sorts by audience_peak desc.
  * has_unlock("new_game_plus") returns False on fresh start,
    True after a recorded victory.
  * fans_total accumulates audience_peak across runs.
  * Death path in Game integrates with run_history (record_run
    called when _check_player_dead flips state).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import run_history as _rh


def _mk_world(*, audience_peak=10, kills=5, victory_setup=False):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=audience_peak)
    w.character.run_audience_peak = audience_peak
    w.character.run_kills = kills
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── Basic record + read ──────────────────────────────────────────────────

def test_record_run_death_appends_entry():
    _rh.reset()
    w = _mk_world(audience_peak=22, kills=3)
    entry = _rh.record_run(w, victory=False)
    assert entry is not None
    assert entry["victory"] is False
    rows = _rh.history()
    assert len(rows) == 1
    assert rows[0]["audience_peak"] == 22
    m = _rh.meta()
    assert m["total_runs"] == 1
    assert m["victories"] == 0
    assert m["fans_total"] == 22
    _rh.reset()
    print("  record_run death: entry + meta bumped: OK")


def test_record_run_victory_bumps_meta():
    """P29.34 — the old `new_game_plus` auto-stamp is gone. Victory
    just bumps total_runs + victories + fans_total. Meta-progression
    unlocks land via engine.meta_progression.record_unlocks_for_run
    in a separate call, not run_history.record_run itself."""
    _rh.reset()
    w = _mk_world(audience_peak=88, kills=42)
    entry = _rh.record_run(w, victory=True)
    assert entry["victory"] is True
    m = _rh.meta()
    assert m["total_runs"] == 1
    assert m["victories"] == 1
    assert m["fans_total"] == 88
    # P29.34 — NG+ is no longer the model. Meta unlocks fire from
    # a separate evaluator now.
    assert "new_game_plus" not in (m["unlocks"] or [])
    _rh.reset()
    print("  record_run victory: meta bumped, no NG+ flag: OK")


# ── Multiple runs ───────────────────────────────────────────────────────

def test_multiple_runs_accumulate():
    _rh.reset()
    for peak, vic in [(10, False), (20, False), (50, False),
                       (30, True), (15, False)]:
        w = _mk_world(audience_peak=peak)
        _rh.record_run(w, victory=vic)
    rows = _rh.history()
    assert len(rows) == 5
    # Newest first: last recorded is rows[0].
    assert rows[0]["audience_peak"] == 15
    m = _rh.meta()
    assert m["total_runs"] == 5
    assert m["victories"] == 1
    # fans_total = 10+20+50+30+15 = 125
    assert m["fans_total"] == 125
    _rh.reset()
    print(f"  5 runs append in order: OK (fans_total=125)")


# ── Leaderboard ─────────────────────────────────────────────────────────

def test_leaderboard_sorts_by_audience_peak():
    _rh.reset()
    for peak in (5, 80, 30, 90, 10):
        w = _mk_world(audience_peak=peak)
        _rh.record_run(w, victory=False)
    top = _rh.leaderboard(n=3)
    peaks = [r["audience_peak"] for r in top]
    assert peaks == [90, 80, 30], f"expected [90,80,30], got {peaks}"
    _rh.reset()
    print(f"  leaderboard(3) by audience_peak: {peaks}: OK")


# ── Has-unlock semantics ────────────────────────────────────────────────

def test_has_unlock_default_false_then_true():
    _rh.reset()
    assert _rh.has_unlock("new_game_plus") is False
    _rh.unlock("new_game_plus")
    assert _rh.has_unlock("new_game_plus") is True
    # Adding twice is idempotent.
    _rh.unlock("new_game_plus")
    m = _rh.meta()
    assert m["unlocks"].count("new_game_plus") == 1
    _rh.reset()
    print("  has_unlock toggles + idempotent add: OK")


# ── End-to-end via Game._check_player_dead ──────────────────────────────

def test_game_death_records_run():
    from ..engine.game import Game
    _rh.reset()
    w = _mk_world(audience_peak=33)
    g = Game(screen=None); g.world = w; g.state = "play"
    ch = w.character
    # Burn last-stand so the very next 0-HP is real death.
    ch.near_death_used = True
    ch.hp = 0
    g._check_player_dead("test", "test cause")
    rows = _rh.history()
    assert len(rows) == 1, "death should have written one entry"
    assert rows[0]["victory"] is False
    assert rows[0]["audience_peak"] == 33
    _rh.reset()
    print("  Game._check_player_dead writes to run_history: OK")


# ── File-corruption tolerance ───────────────────────────────────────────

def test_corrupt_history_file_returns_empty():
    _rh.reset()
    # Write garbage to the history file.
    with open(_rh.HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("not json {")
    rows = _rh.history()
    assert rows == []
    m = _rh.meta()
    assert m["total_runs"] == 0
    _rh.reset()
    print("  corrupt history file → empty payload (no crash): OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    _rh.reset()
    try:
        test_record_run_death_appends_entry()
        test_record_run_victory_bumps_meta()
        test_multiple_runs_accumulate()
        test_leaderboard_sorts_by_audience_peak()
        test_has_unlock_default_false_then_true()
        test_game_death_records_run()
        test_corrupt_history_file_returns_empty()
    finally:
        _rh.reset()
    print("Prompt 29.26 run history smoke: OK")


if __name__ == "__main__":
    main()
