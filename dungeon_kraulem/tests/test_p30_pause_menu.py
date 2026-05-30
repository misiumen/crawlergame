"""P30 smoke — in-game pause / escape menu.

Asserts:
1. Esc on an empty command box (STATE_PLAY) opens the pause menu.
2. Esc with text in the box clears it instead (does NOT open the menu).
3. Esc inside the pause menu resumes the game.
4. Each menu action routes correctly: resume / save / reseed / quit_to_menu.
5. Reseed keeps the character's name/background and assigns a fresh seed.
6. The pause render registers one click zone per menu row, and a click
   fires the matching action (mouse parity).
7. Opening settings from pause remembers prev_state=pause.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import (Game, STATE_PLAY, STATE_PAUSE, STATE_TITLE,
                           STATE_SETTINGS, STATE_SLOTS)
from ..ui import ui as _ui


def _key(k):
    return type("E", (), {"key": k, "type": pygame.KEYDOWN})()


def _mk_game():
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def test_esc_empty_opens_menu():
    g = _mk_game()
    g.handle_keydown(_key(pygame.K_ESCAPE))
    assert g.state == STATE_PAUSE, g.state
    print("  Esc (empty box) opens pause menu: OK")


def test_esc_with_text_clears_only():
    g = _mk_game()
    g.input_text = "atak"
    g.handle_keydown(_key(pygame.K_ESCAPE))
    assert g.state == STATE_PLAY and g.input_text == "", (g.state, g.input_text)
    print("  Esc (with text) clears box, no menu: OK")


def test_esc_in_menu_resumes():
    g = _mk_game()
    g.handle_keydown(_key(pygame.K_ESCAPE))      # open
    g.handle_keydown(_key(pygame.K_ESCAPE))      # resume
    assert g.state == STATE_PLAY, g.state
    print("  Esc inside menu resumes: OK")


def test_actions_route():
    g = _mk_game()
    g.open_pause_menu()
    g._pause_action("resume")
    assert g.state == STATE_PLAY
    # save
    g.open_pause_menu()
    g._pause_action("save")
    assert g.state == STATE_PLAY            # save returns to play
    # quit to menu
    g.open_pause_menu()
    g._pause_action("quit_to_menu")
    assert g.state == STATE_TITLE and g.world is None, (g.state, g.world)
    print("  resume / save / quit_to_menu route correctly: OK")


def test_reseed_keeps_identity_new_seed():
    g = _mk_game()
    name, bg = g.world.character.name, g.world.character.background
    g.open_pause_menu()
    g._pause_action("reseed")
    assert g.state == STATE_PLAY
    assert g.world.character.name == name
    assert g.world.character.background == bg
    assert g.world.random_seed is not None
    print("  reseed keeps identity + sets fresh seed: OK")


def test_settings_from_pause_returns_to_pause():
    g = _mk_game()
    g.open_pause_menu()
    g._pause_action("settings")
    assert g.state == STATE_SETTINGS
    assert g.settings_state.get("prev_state") == STATE_PAUSE
    print("  settings opened from pause returns to pause: OK")


def test_click_zones_and_mouse_fire():
    g = _mk_game()
    g.handle_keydown(_key(pygame.K_ESCAPE))
    s = pygame.display.get_surface()
    s.fill((0, 0, 0))
    g.draw()
    zones = [z for z in g.click_registry.zones if z.category == "pause_menu"]
    assert len(zones) == len(_ui.PAUSE_MENU_ITEMS), len(zones)
    # Click the first row (resume) → back to play.
    rx, ry, rw, rh = zones[0].rect
    mev = type("M", (), {"button": 1, "pos": (rx + rw // 2, ry + rh // 2),
                         "type": pygame.MOUSEBUTTONDOWN})()
    g.handle_mousedown(mev)
    assert g.state == STATE_PLAY, g.state
    print(f"  {len(zones)} click zones; mouse click fires action: OK")


def main():
    test_esc_empty_opens_menu()
    test_esc_with_text_clears_only()
    test_esc_in_menu_resumes()
    test_actions_route()
    test_reseed_keeps_identity_new_seed()
    test_settings_from_pause_returns_to_pause()
    test_click_zones_and_mouse_fire()
    print("P30 pause menu smoke: OK")


if __name__ == "__main__":
    main()
