"""QoL batch 2: UX-1 (log scroll only on overflow).

UX-3 (fog-masked action panel) was attempted here but DEFERRED/reverted:
display_name() is already visibility-aware in real play and
respect_known_key_on_spawn promotes trivial objects, so a panel-only
override was redundant and broke raw fixtures. The real UX-3 (room
description vs panel parity) lives at the fog layer and stays a backlog
item — so this file now only covers UX-1 plus a sanity check that the
object panel still builds verbs.
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
    g._refresh_layout()
    return g


def test_log_scroll_caps_to_overflow():
    g = _demo_game()
    g.world.log = [("linia", "normal")] * 3        # trivially fits
    assert g._log_max_scroll() == 0, "short log must not scroll"
    g.world.log = [("linia", "normal")] * 500       # definitely overflows
    assert g._log_max_scroll() > 0, "long log must allow scrollback"
    print("  UX-1 scroll caps to overflow: OK")


def test_panel_offers_verbs_for_object():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    e = Entity(key="secret", entity_type=T_OBJECT,
               fallback_name="automat sponsorski", fallback_desc="Opis.",
               tags=["salvageable"], affordances=["inspect", "salvage"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    g.world.register(e); room.entities.append(e)
    labels = [o.label for o in _nav._flat_object_verbs(g.world, room)
              if o.target_id == e.entity_id]
    assert labels, "object should still offer at least inspect"
    print(f"  panel offers verbs for object: {labels}: OK")


def main():
    test_log_scroll_caps_to_overflow()
    test_panel_offers_verbs_for_object()
    print("QoL batch 2 (UX-1) smoke: OK")


if __name__ == "__main__":
    main()
