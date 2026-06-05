"""UX-2 — room-scan actions (look/listen/search-room) are one-and-done.

Once performed in a room they: (1) refuse cheaply on repeat, and (2)
disappear from the action panel. Per-object search is NOT affected.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY
from ..engine.entity import Entity, T_OBJECT
from ..ui import ui_nav as _nav


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _basic_ids(world, room):
    return {o.option_id for o in _nav._basic_actions(world, room)}


def test_look_exhausts_and_hides():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    assert "act_look" in _basic_ids(g.world, room), "look should start visible"
    g._handle_play_input("rozejrzyj się")
    done = set((room.state or {}).get("actions_done", []))
    assert "look" in done, f"look not recorded: {done}"
    assert "act_look" not in _basic_ids(g.world, room), \
        "look should vanish from panel after use"
    print("  look exhausts + hides from panel: OK")


def test_repeat_look_is_refused():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    g._handle_play_input("rozejrzyj się")
    n_before = len(g.world.log)
    g._handle_play_input("rozejrzyj się")
    # Repeat logs the exhausted-feedback refusal (and returns before the
    # normal resolve pipeline, so no progress is made).
    new_lines = [str(x) for x in g.world.log[n_before:]]
    assert any("Już to zrobiłeś" in l or "exhausted" in l for l in new_lines), \
        f"expected a refusal line, got: {new_lines}"
    # Still exactly one 'look' recorded — not duplicated.
    done = list((room.state or {}).get("actions_done", []))
    assert done.count("look") == 1, done
    print("  repeat look refused: OK")


def test_object_search_not_exhausted():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    e = Entity(key="crate", entity_type=T_OBJECT, fallback_name="skrzynia",
               fallback_desc="Drewniana skrzynia.", tags=["container"],
               affordances=["inspect", "search", "loot"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    g.world.register(e); room.entities.append(e)
    g._handle_play_input("przeszukaj skrzynia")
    done = set((room.state or {}).get("actions_done", []))
    assert "search" not in done, \
        "object search must NOT mark room-search as exhausted"
    print("  object search not exhausted as room-scan: OK")


def test_room_search_exhausts():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    assert "act_search" in _basic_ids(g.world, room)
    g._handle_play_input("przeszukaj pokój")
    assert "search" in set((room.state or {}).get("actions_done", []))
    assert "act_search" not in _basic_ids(g.world, room)
    print("  room search exhausts + hides: OK")


def main():
    test_look_exhausts_and_hides()
    test_repeat_look_is_refused()
    test_object_search_not_exhausted()
    test_room_search_exhausts()
    print("UX-2 exhausted room-scan actions smoke: OK")


if __name__ == "__main__":
    main()
