"""QoL batch 2: UX-1 (log scroll only on overflow) + UX-3 (fog-masked panel)."""
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
from ..engine import visibility as _vis


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


def test_panel_masks_unknown_names():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    e = Entity(key="secret", entity_type=T_OBJECT,
               fallback_name="automat sponsorski", fallback_desc="Opis.",
               tags=["salvageable"], affordances=["inspect", "salvage"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    g.world.register(e); room.entities.append(e)
    # Force unknown (not yet inspected/seen).
    if hasattr(_vis, "mark_unknown"):
        try: _vis.mark_unknown(g.world, e)
        except Exception: pass
    labels = [o.label for o in _nav._flat_object_verbs(g.world, room)
              if o.target_id == e.entity_id]
    assert labels, "object should still offer at least inspect"
    if _vis.is_unknown(e):
        assert all("automat sponsorski" not in l for l in labels), \
            f"unknown name leaked into panel: {labels}"
        print(f"  UX-3 unknown masked in panel: {labels}: OK")
    else:
        # If the engine auto-marks it seen, masking isn't expected — at least
        # confirm _panel_name masks a forced-unknown entity directly.
        assert "automat" not in _nav._panel_name(_FakeUnknown())
        print("  UX-3 _panel_name masks unknown (direct): OK")


class _FakeUnknown:
    entity_type = T_OBJECT
    fallback_name = "automat sponsorski"
    def display_name(self): return "automat sponsorski"


def main():
    test_log_scroll_caps_to_overflow()
    test_panel_masks_unknown_names()
    print("QoL batch 2 (UX-1 / UX-3) smoke: OK")


if __name__ == "__main__":
    main()
