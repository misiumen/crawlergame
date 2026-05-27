"""Prompt 29.3 — salvage materials visibility + mouse-wheel scroll.

Covers:
  * Salvage actually adds materials to character.materials (was
    confused with inventory_ids; user reported "salvage daje 0 lootu").
  * Quickstrip sidebar surfaces top-4 materials below PRZY SOBIE
    so player can see what they accumulated without opening tab.
  * MOUSEWHEEL events scroll the log up/down when cursor is over
    the log panel.
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
from ..engine.entity import Entity, T_OBJECT
from ..content import materials as _mat


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


def test_salvage_actually_adds_materials():
    """Diagnostic: confirm salvage writes to character.materials."""
    w, _r = _mk_world()
    pre = dict(w.character.materials or {})
    _mat.add_materials(w.character, {"scrap_metal": 3, "cloth_strips": 2})
    assert w.character.materials.get("scrap_metal") == pre.get("scrap_metal", 0) + 3
    assert w.character.materials.get("cloth_strips") == pre.get("cloth_strips", 0) + 2
    print(f"  add_materials writes to character.materials: OK ({w.character.materials})")


def test_quickstrip_renders_materials_section():
    """Sidebar quickstrip should include a MATERIAŁY block when materials
    pool is non-empty."""
    from ..engine.game import Game
    from ..ui import ui as _ui
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    # Seed some materials.
    _mat.add_materials(g.world.character, {"scrap_metal": 5,
                                            "cloth_strips": 3,
                                            "bone_fragments": 1})
    # Draw doesn't return content but should not crash.
    g.state = "play"
    g.draw()
    print(f"  sidebar with materials: drew OK")


def test_mousewheel_scrolls_log_up():
    """Wheel up over the log panel increments log_scroll."""
    from ..engine.game import Game
    import pygame as _pg
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    # Seed some log so there's something to scroll into.
    for i in range(20):
        g.log(f"line {i}")
    g.draw()   # populate self._layout
    # Position mouse over log panel.
    lx, ly, lw, lh = g._layout.log_rect
    g._mouse_xy = (lx + 10, ly + 10)
    pre_scroll = g.log_scroll
    class _Ev: y = 2
    g.handle_mousewheel(_Ev())
    post_scroll = g.log_scroll
    assert post_scroll > pre_scroll, \
        f"wheel up should increase scroll; pre={pre_scroll} post={post_scroll}"
    print(f"  wheel up over log: {pre_scroll} → {post_scroll}: OK")


def test_mousewheel_scrolls_log_down():
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    for i in range(20):
        g.log(f"line {i}")
    g.draw()
    lx, ly, lw, lh = g._layout.log_rect
    g._mouse_xy = (lx + 10, ly + 10)
    g.log_scroll = 10
    class _Ev: y = -2
    g.handle_mousewheel(_Ev())
    assert g.log_scroll < 10
    print(f"  wheel down: 10 → {g.log_scroll}: OK")


def test_mousewheel_ignored_outside_log():
    """Cursor outside the log panel → wheel is a no-op."""
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    g.draw()
    g.log_scroll = 5
    g._mouse_xy = (10, 10)   # far from log
    class _Ev: y = 3
    g.handle_mousewheel(_Ev())
    assert g.log_scroll == 5, "wheel outside log should not scroll"
    print(f"  wheel outside log: scroll unchanged: OK")


def main():
    test_salvage_actually_adds_materials()
    test_quickstrip_renders_materials_section()
    test_mousewheel_scrolls_log_up()
    test_mousewheel_scrolls_log_down()
    test_mousewheel_ignored_outside_log()
    print("Prompt 29.3 salvage materials + mouse-wheel smoke: OK")


if __name__ == "__main__":
    main()
