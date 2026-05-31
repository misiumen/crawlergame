"""UX-3 — action panel respects fog-of-war (no name spoilers).

A genuinely-unknown entity must read as a vague shape in the panel, matching
the room description, instead of leaking its real name. A 'seen' entity shows
its real name. Acting still works because options carry target_id.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.world import WorldState
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT
from ..ui import ui_nav as _nav
from ..engine import visibility as _vis


def _mk():
    w = WorldState()
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0")
    f.add_room(r); f.current_room_id = "r0"
    w.current_floor = f
    return w, r


def _obj(r, w, *, state, name="automat sponsorski"):
    e = Entity(key="susp", entity_type=T_OBJECT, fallback_name=name,
               fallback_desc="Coś tu jest.", tags=["salvageable"],
               affordances=["inspect", "salvage"], location_id=r.room_id)
    e.visible = True; e.discovered = True
    e.visibility_state = state
    r.entities.append(e); w.register(e)
    return e


def test_unknown_object_is_masked_in_panel():
    w, r = _mk()
    e = _obj(r, w, state="unknown")
    assert _vis.is_unknown(e)
    labels = [o.label for o in _nav._flat_object_verbs(w, r)
              if o.target_id == e.entity_id]
    assert labels, "unknown object should still offer verbs"
    assert all("automat sponsorski" not in l for l in labels), \
        f"real name leaked for unknown entity: {labels}"
    print(f"  unknown object masked in panel: {labels}: OK")


def test_seen_object_shows_real_name():
    w, r = _mk()
    e = _obj(r, w, state="seen")
    labels = [o.label for o in _nav._flat_object_verbs(w, r)
              if o.target_id == e.entity_id]
    assert any("automat sponsorski" in l for l in labels), \
        f"seen entity should show its real name: {labels}"
    print(f"  seen object shows real name: {labels}: OK")


def test_options_still_target_by_id():
    w, r = _mk()
    e = _obj(r, w, state="unknown")
    opts = [o for o in _nav._flat_object_verbs(w, r)
            if o.target_id == e.entity_id]
    assert opts and all(o.target_id == e.entity_id for o in opts), \
        "masked options must still carry the real target_id"
    print("  masked options still target by id: OK")


def main():
    test_unknown_object_is_masked_in_panel()
    test_seen_object_shows_real_name()
    test_options_still_target_by_id()
    print("UX-3 panel fog-of-war smoke: OK")


if __name__ == "__main__":
    main()
