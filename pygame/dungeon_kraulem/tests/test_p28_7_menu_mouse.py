"""Prompt 28.7 — mouse on title menu + character creation smoke.

Covers:
  * Title screen draws with click zones registered for each menu
    item (new_game / load_game / settings / quit + lang toggle).
  * Clicking the "NOWA GRA" zone moves Game into STATE_CREATE.
  * Clicking "WYJDŹ" raises SystemExit (mouse parity with [4]).
  * Character creation `name` step has Dalej + Powrót buttons that
    behave like Enter/Esc.
  * Character creation `background` step has a click zone per
    background row; clicking a non-selected row sets selected_bg,
    clicking the already-selected row commits and enters STATE_PLAY.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))


def test_title_registers_menu_clicks():
    from ..engine.game import Game, STATE_TITLE
    g = Game(screen=pygame.display.get_surface())
    g.state = STATE_TITLE
    g.draw()
    cats = [z.category for z in g.click_registry.zones]
    title_zones = [c for c in cats if c == "title_menu"]
    # 4 menu items + 1 lang toggle = 5, but load_game is suppressed
    # when no save exists. Allow ≥3 (new_game/settings/quit/lang).
    assert len(title_zones) >= 3, \
        f"expected ≥3 title_menu zones; got {cats}"
    print(f"  title menu has {len(title_zones)} click zones: OK")


def test_title_click_new_game_enters_create():
    """P29.9 — NOWA GRA now routes through the slot picker. Clicking
    NOWA GRA lands you on STATE_SLOTS (with mode='new'); picking a
    slot from there takes you to STATE_CREATE."""
    from ..engine.game import Game, STATE_TITLE, STATE_CREATE, STATE_SLOTS
    g = Game(screen=pygame.display.get_surface())
    g.state = STATE_TITLE
    g.draw()
    # Find the new_game tooltip zone — we tagged it by label content.
    target = None
    for z in g.click_registry.zones:
        if z.category == "title_menu" and "NOWA" in (z.tooltip or "").upper():
            target = z
            break
    assert target is not None, "no NOWA GRA click zone"
    target.callback()
    assert g.state == STATE_SLOTS, f"state={g.state} (expected STATE_SLOTS)"
    assert g.slot_picker_mode == "new"
    # Now pick slot 0 — should advance to STATE_CREATE.
    g._slot_picker_pick(0)
    assert g.state == STATE_CREATE, f"state={g.state} (expected STATE_CREATE)"
    print(f"  click NOWA GRA → STATE_SLOTS → pick slot → STATE_CREATE: OK")


def test_create_name_buttons_present():
    """Creation 'name' step exposes 'Dalej' and 'Powrót' buttons."""
    from ..engine.game import Game, STATE_CREATE
    g = Game(screen=pygame.display.get_surface())
    g.cc = {"step": "name", "name_input": "Test", "selected_bg": 0}
    g.state = STATE_CREATE
    g.draw()
    btn_zones = [z for z in g.click_registry.zones if z.category == "create_btn"]
    assert len(btn_zones) >= 2, f"expected ≥2 create_btn zones; got {len(btn_zones)}"
    print(f"  create-name has {len(btn_zones)} button zones: OK")


def test_create_name_dalej_advances_to_background():
    from ..engine.game import Game, STATE_CREATE
    g = Game(screen=pygame.display.get_surface())
    g.cc = {"step": "name", "name_input": "Test", "selected_bg": 0}
    g.state = STATE_CREATE
    g.draw()
    # Trigger the confirm-name button.
    for z in g.click_registry.zones:
        if z.category == "create_btn" and "Dalej" in (z.tooltip or ""):
            z.callback()
            break
    assert g.cc.get("step") == "background", g.cc
    print(f"  Dalej click → step=background: OK")


def test_create_bg_row_clicks_select_then_commit():
    # P29.35 — bg row click commit now routes to the species step, not
    # straight to STATE_PLAY. From species, with no companion unlocks,
    # commit lands in STATE_PLAY.
    from ..engine.game import Game, STATE_CREATE, STATE_PLAY
    from ..engine import run_history as _rh
    _rh.reset()    # make sure no companion is unlocked
    g = Game(screen=pygame.display.get_surface())
    g.cc = {"step": "background", "name_input": "Test",
            "selected_bg": 0, "selected_species": 0,
            "selected_companion": 0}
    g.state = STATE_CREATE
    g.draw()
    bg_rows = [z for z in g.click_registry.zones if z.category == "create_bg_row"]
    assert bg_rows, "no create_bg_row zones"
    # Pick the SECOND row first → selection changes to index 1.
    bg_rows[1].callback()
    assert g.cc.get("selected_bg") == 1, g.cc
    # Re-draw to refresh click zones (selected row index changed).
    g.draw()
    bg_rows2 = [z for z in g.click_registry.zones if z.category == "create_bg_row"]
    # Click the now-selected row → routes to species step.
    bg_rows2[1].callback()
    assert g.cc.get("step") == "species", \
        f"expected step=species, got {g.cc.get('step')}"
    # On species, commit baseline_human → launches (no companion unlocks).
    g.draw()
    sp_rows = [z for z in g.click_registry.zones
               if z.category == "create_species_row"]
    assert sp_rows, "no species rows"
    # baseline_human is the only row, and selected_species defaults to 0,
    # so clicking it commits.
    sp_rows[0].callback()
    assert g.state == STATE_PLAY, f"expected STATE_PLAY, got {g.state}"
    assert g.world is not None and g.world.character.name == "Test"
    _rh.reset()
    print(f"  bg row + species row click commit -> STATE_PLAY: OK")


def main():
    test_title_registers_menu_clicks()
    test_title_click_new_game_enters_create()
    test_create_name_buttons_present()
    test_create_name_dalej_advances_to_background()
    test_create_bg_row_clicks_select_then_commit()
    print("Prompt 28.7 menu + creation mouse smoke: OK")


if __name__ == "__main__":
    main()
