"""Prompt 29.24 — Floor-collapse escape-at-exit smoke suite.

Audit finding: the floor deadline timer was unstoppable. When it
hit 0, _trigger_floor_collapse marked the floor as collapsed and
the player died regardless of where they were standing. The comment
in time_system.py:148 said "could land in P31" — never did.

Fix: if the player is in the boss room (with exits_unlocked) or a
room tagged "exit" at the moment of collapse, descent fires instead.

Covers:
  * _trigger_floor_collapse with no exit context kills normally.
  * _trigger_floor_collapse in exit-tagged room sets the descend
    flag, NOT the collapsed flag.
  * _trigger_floor_collapse in boss room WITH exits_unlocked also
    sets descend flag.
  * boss room WITHOUT exits_unlocked still kills (you didn't earn
    the descent yet).
  * Game.update consumes the descend flag and calls _descend_or_win.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world(*, room_type="combat", room_tags=None,
              exits_unlocked=False):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala",
                  actual_type=room_type)
    if room_tags:
        r.sensory_tags = list(room_tags)
    f.add_room(r)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.exits_unlocked = exits_unlocked
    w.current_floor = f
    return w, r


# ── Collapse without exit context kills ──────────────────────────────────

def test_collapse_in_combat_room_kills():
    from ..engine.time_system import _trigger_floor_collapse
    w, _r = _mk_world(room_type="combat")
    _trigger_floor_collapse(w)
    assert w.current_floor.state.get("collapsed") is True
    assert not w.current_floor.state.get("collapse_descend_requested")
    print("  collapse in normal room → collapsed=True (kill): OK")


# ── Collapse in exit room → descend flag ─────────────────────────────────

def test_collapse_at_exit_room_flags_descend():
    from ..engine.time_system import _trigger_floor_collapse
    w, _r = _mk_world(room_type="social", room_tags=["exit"],
                      exits_unlocked=True)
    _trigger_floor_collapse(w)
    assert w.current_floor.state.get("collapse_descend_requested") is True
    assert not w.current_floor.state.get("collapsed")
    print("  collapse at exit-tagged room → descend flag set: OK")


def test_collapse_at_boss_unlocked_flags_descend():
    from ..engine.time_system import _trigger_floor_collapse
    w, _r = _mk_world(room_type="boss", exits_unlocked=True)
    _trigger_floor_collapse(w)
    assert w.current_floor.state.get("collapse_descend_requested") is True
    assert not w.current_floor.state.get("collapsed")
    print("  collapse in boss room + exits_unlocked → descend: OK")


def test_collapse_at_boss_locked_still_kills():
    from ..engine.time_system import _trigger_floor_collapse
    w, _r = _mk_world(room_type="boss", exits_unlocked=False)
    _trigger_floor_collapse(w)
    # exits_unlocked=False means player didn't earn the descent yet.
    assert w.current_floor.state.get("collapsed") is True
    assert not w.current_floor.state.get("collapse_descend_requested")
    print("  boss room without exits_unlocked → still kill: OK")


# ── Game.update consumes descend flag ────────────────────────────────────

def test_game_update_consumes_descend_flag():
    """When time_system marks descend_requested, Game.update should
    invoke _descend_or_win on the next tick (we don't run the full
    descent path here — too expensive — just verify the flag clears
    and the death path doesn't fire)."""
    from ..engine.game import Game
    w, _r = _mk_world(room_type="boss", exits_unlocked=True)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Stub _descend_or_win to a no-op so we don't need a real
    # next floor.
    calls = {"n": 0}
    def stub(): calls["n"] += 1
    g._descend_or_win = stub
    # Pre-set the descend flag (as time_system would have done).
    w.current_floor.state["collapse_descend_requested"] = True
    g.update(0.016)   # one ~60fps tick
    # Flag must be cleared.
    assert w.current_floor.state.get("collapse_descend_requested") is False
    # _descend_or_win called exactly once.
    assert calls["n"] == 1
    # State not flipped to defeat.
    assert g.state == "play"
    print(f"  Game.update consumed descend flag + called _descend_or_win: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_collapse_in_combat_room_kills()
    test_collapse_at_exit_room_flags_descend()
    test_collapse_at_boss_unlocked_flags_descend()
    test_collapse_at_boss_locked_still_kills()
    test_game_update_consumes_descend_flag()
    print("Prompt 29.24 collapse-escape smoke: OK")


if __name__ == "__main__":
    main()
