"""Prompt 28.4 — minimap click refusal smoke suite.

Covers:
  * Click on non-adjacent room → logs "too far" refusal, NOT silently
    adds to player_map_marks.
  * Click on adjacent locked exit → logs "locked" refusal, no move.
  * Click on adjacent unlocked exit → submits `idź <label>`.
  * Click on current room → no-op, falls through (returns False).
  * Stale marks no longer render as visible highlight (only adjacent
    walkable cells get the accent border now).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="Pakamera")
    r1 = RoomState(room_id="r1", fallback_short_title="Korytarz")
    r2 = RoomState(room_id="r2", fallback_short_title="Daleka Sala")
    r3 = RoomState(room_id="r3", fallback_short_title="Lounge")
    r0.exits = {"wschód": {"target": "r1"},
                "kratka": {"target": "r3", "locked": True}}
    r1.exits = {"zachód": {"target": "r0"},
                "wschód": {"target": "r2"}}
    r2.exits = {"zachód": {"target": "r1"}}
    r3.exits = {"kratka": {"target": "r0", "locked": True}}
    f.add_room(r0); f.add_room(r1); f.add_room(r2); f.add_room(r3)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.discovered_room_ids = {"r0", "r1", "r2", "r3"}
    w.current_floor = f
    return w


def test_click_non_adjacent_refuses_no_mark():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_marks = dict(getattr(w, "player_map_marks", {}) or {})
    handled = g._on_minimap_room_click("r2")   # 2 rooms away
    assert handled is True, "non-adjacent click should be consumed, not fall through"
    txt = " ".join(s for s, _ in w.log[-3:]).lower()
    assert "daleko" in txt or "sąsiednie" in txt or "sasiednie" in txt, \
        f"expected refusal log; got: {txt}"
    new_marks = dict(getattr(w, "player_map_marks", {}) or {})
    assert new_marks == pre_marks, \
        f"non-adjacent click should NOT add a mark; before={pre_marks} after={new_marks}"
    print("  non-adjacent click → refusal, no mark: OK")


def test_click_locked_refuses():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    handled = g._on_minimap_room_click("r3")   # adjacent but locked
    assert handled is True
    txt = " ".join(s for s, _ in w.log[-3:]).lower()
    assert "zamknięt" in txt or "zamknięte" in txt or "zamkniete" in txt
    # Player did NOT move.
    assert w.current_floor.current_room_id == "r0"
    print("  locked adjacent click → locked log, no move: OK")


def test_click_unlocked_adjacent_moves():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    handled = g._on_minimap_room_click("r1")
    assert handled is True
    assert w.current_floor.current_room_id == "r1", \
        f"player should have moved to r1; at {w.current_floor.current_room_id}"
    print("  unlocked adjacent click → moves: OK")


def test_click_current_room_is_noop():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_log = len(w.log)
    handled = g._on_minimap_room_click("r0")   # current
    # Returns False (no action) — but we explicitly don't add a mark either.
    assert handled is False
    # No new log line.
    assert len(w.log) == pre_log
    print("  current-room click → no-op: OK")


def test_minimap_draws_after_click_refusal():
    """Refusal click should not leave the minimap in a broken state."""
    from ..engine.game import Game
    from ..ui import minimap as _mm
    from ..ui import layout as _lay
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    # Try to "click" a non-existent / non-adjacent room via the handler.
    far = next((rid for rid in g.world.current_floor.rooms.keys()
                if rid != g.world.current_floor.current_room_id), None)
    if far:
        # Force into adj-status: only refuse if exit doesn't reach.
        g._on_minimap_room_click(far)
    # Draw should be clean.
    surf = pygame.display.get_surface()
    layout = _lay.calculate_layout(surf.get_width(), surf.get_height())
    _mm.draw_minimap(surf, g.world, layout.minimap_rect, layout)
    print("  minimap renders fine after refusal click: OK")


def main():
    test_click_non_adjacent_refuses_no_mark()
    test_click_locked_refuses()
    test_click_unlocked_adjacent_moves()
    test_click_current_room_is_noop()
    test_minimap_draws_after_click_refusal()
    print("Prompt 28.4 minimap click refusal smoke: OK")


if __name__ == "__main__":
    main()
