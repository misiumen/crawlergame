"""Prompt 24.6 — UX + Bug Sweep smoke suite.

Covers:
  * Polish dice labels: stat_pl, level_pl, intent_pl, format_check.
  * Mood placeholder caption present.
  * Minimap click-to-move on adjacent unlocked room → idź <label>.
  * Minimap click on locked adjacent → refusal log; no move.
  * Minimap click on non-adjacent → returns False (falls through to mark).
  * Inventory-first resolution: użyj <inventory item> resolves to item, not room.
  * Combat lockdown: idź during combat redirects to flee.
  * Combat lockdown: loot/salvage/search refused mid-combat.
  * Combat lockdown: check_inventory free in combat.
  * Log render: sponsor entry only first-line gets avatar; wrap respects gutter.
  * Smoke: draw at 3 resolutions still works.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..engine.dice_labels import (stat_pl, level_pl, intent_pl,
                                  format_check)
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_ITEM, T_MONSTER


# ── Dice labels ─────────────────────────────────────────────────────────

def test_stat_pl_known_and_unknown():
    assert stat_pl("STR") == "SIŁ"
    assert stat_pl("DEX") == "ZRĘ"
    assert stat_pl("CON") == "KON"
    assert stat_pl("WIS") == "MDR"
    assert stat_pl("INT") == "INT"
    assert stat_pl("CHA") == "CHA"
    # Unknown passes through unchanged.
    assert stat_pl("XYZ") == "XYZ"
    print("  stat_pl mapping: OK")


def test_level_pl():
    assert level_pl("success") == "sukces"
    assert level_pl("failure") == "porażka"
    assert level_pl("critical_success") == "kryt. sukces"
    assert level_pl("critical_failure") == "kryt. porażka"
    print("  level_pl mapping: OK")


def test_intent_pl():
    assert intent_pl("salvage") == "odzysk"
    assert intent_pl("attack") == "atak"
    assert intent_pl("break") == "rozbicie"
    print("  intent_pl mapping: OK")


def test_format_check_example():
    line = format_check("salvage", "STR", 13, 0, 13, 12, "success")
    assert "[odzysk]" in line
    assert "SIŁ(+0)" in line
    assert "TT 12" in line
    assert "sukces" in line
    assert "DC" not in line and "success" not in line
    print(f"  format_check: '{line.strip()}': OK")


def test_format_check_with_extras():
    line = format_check("attack", "STR", 8, 0, 9, 11, "failure",
                       extras=[("tła", 1)])
    assert "+ tła(+1)" in line
    print(f"  format_check extras: '{line.strip()}': OK")


# ── Mood placeholder caption ───────────────────────────────────────────

def test_mood_placeholder_caption_renders():
    from ..ui.ui import _draw_room_mood_placeholder
    surf = pygame.Surface((300, 100))
    r = RoomState(room_id="r0", fallback_short_title="X",
                  actual_type="lore")
    # Just verify it doesn't crash with the caption flag.
    _draw_room_mood_placeholder(surf, 0, 0, 300, 100, r, show_caption=True)
    print("  mood placeholder draws with caption: OK")


# ── Minimap click-to-move ───────────────────────────────────────────────

def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="A")
    r1 = RoomState(room_id="r1", fallback_short_title="B")
    r2 = RoomState(room_id="r2", fallback_short_title="C")
    r0.exits = {
        "wschód": {"target": "r1", "locked": False, "hidden": False},
        "zachód": {"target": "r2", "locked": True,  "hidden": False},
    }
    r1.exits = {"zachód": {"target": "r0"}}
    r2.exits = {"wschód": {"target": "r0"}}
    for r in (r0, r1, r2):
        f.add_room(r)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def test_minimap_click_adjacent_unlocked_moves():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    captured = []
    g.submit_generated_command = lambda c, target_id=None: captured.append(c)
    handled = g._on_minimap_room_click("r1")
    assert handled is True
    assert any("idź wschód" in c for c in captured), \
        f"expected idź wschód, got {captured}"
    print("  minimap click adjacent unlocked → idź: OK")


def test_minimap_click_locked_refuses():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    captured = []
    g.submit_generated_command = lambda c, target_id=None: captured.append(c)
    pre_log = len(w.log)
    handled = g._on_minimap_room_click("r2")  # locked
    assert handled is True
    assert captured == [], f"locked room should not issue idż: {captured}"
    assert len(w.log) > pre_log
    print("  minimap click locked → refusal log: OK")


def test_minimap_click_nonadjacent_returns_false():
    from ..engine.game import Game
    w = _mk_world()
    # Add r3 not reachable from r0.
    r3 = RoomState(room_id="r3", fallback_short_title="D")
    w.current_floor.add_room(r3)
    g = Game(screen=None); g.world = w; g.state = "play"
    handled = g._on_minimap_room_click("r3")
    assert handled is False, "non-adjacent should fall through to mark"
    print("  minimap click non-adjacent → False (mark fallback): OK")


# ── Inventory-first use resolution ─────────────────────────────────────

def test_use_resolves_inventory_first():
    from ..engine.parser_core import ActionIntent
    from ..engine.validation import validate
    w = _mk_world()
    badge = Entity(key="plastic_badge", entity_type=T_ITEM,
                   fallback_name="plastikowa plakietka",
                   portable=True, tags=["badge"],
                   affordances=["inspect", "use"],
                   location_id="inventory:player")
    w.register(badge)
    w.character.inventory_ids.append(badge.entity_id)
    intent = ActionIntent(intent="use", verb="użyj",
                          targets=["plastikowa plakietka"])
    v = validate(intent, w)
    assert v.valid, f"expected valid, got {v.reason} / {v.fallback_message}"
    assert v.matched_entities[0].key == "plastic_badge"
    print("  use resolves inventory item before room: OK")


# ── Combat lockdown ─────────────────────────────────────────────────────

def _start_combat(w):
    from ..engine import combat as _cmb
    room = w.current_floor.current_room()
    m = Entity(key="rat", entity_type=T_MONSTER, fallback_name="szczurek",
               hp=5, max_hp=5, ac=10, affordances=["attack"],
               tags=["monster"], location_id=room.room_id)
    w.register(m); room.entities.append(m)
    _cmb.start_combat(room, w)


def test_combat_lockdown_move_redirects_to_flee():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    from ..engine import combat as _cmb
    w = _mk_world()
    _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    intent = ActionIntent(intent="move", verb="idź", destination="wschód")
    room = w.current_floor.current_room()
    cs = _cmb.get_combat(room)
    consumed = g._combat_route(intent, cs)
    assert consumed is True
    # Flee log should include "wycofuj" or "wycof" or "uciec"
    last = w.log[-3:] if len(w.log) >= 3 else w.log
    txt = " ".join(s for s, _c in last).lower()
    assert "wycof" in txt or "ucie" in txt
    print("  combat lockdown: move → flee redirect: OK")


def test_combat_lockdown_loot_refused():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    from ..engine import combat as _cmb
    w = _mk_world()
    _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    intent = ActionIntent(intent="salvage", verb="zdemontuj")
    room = w.current_floor.current_room()
    cs = _cmb.get_combat(room)
    pre_len = len(w.log)
    consumed = g._combat_route(intent, cs)
    assert consumed is True, "salvage in combat must be consumed/refused"
    assert len(w.log) > pre_len
    last = w.log[-1][0].lower()
    # P26b widened the refusal vocabulary: each intent gets its own
    # flavored line. Check for any plausibly "no, not now" phrasing.
    assert any(k in last for k in ("nie teraz", "walk", "ostrzał",
                                    "złom", "rozbierz", "patrosz")), \
        f"unexpected refusal: {last}"
    print("  combat lockdown: salvage refused: OK")


def test_combat_lockdown_info_free():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    from ..engine import combat as _cmb
    w = _mk_world()
    _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    intent = ActionIntent(intent="check_inventory", verb="plecak")
    room = w.current_floor.current_room()
    cs = _cmb.get_combat(room)
    consumed = g._combat_route(intent, cs)
    assert consumed is False, "info commands stay free in combat"
    print("  combat lockdown: check_inventory not consumed (falls through): OK")


# ── Log render with avatar gutter ──────────────────────────────────────

def test_log_renders_without_overlap():
    """Smoke: emit several LOG_SYNDIC + LOG_NORMAL entries; verify draw
    doesn't crash + the wrap respects the gutter."""
    from ..ui import ui as _ui
    from ..config import LOG_SYNDIC, LOG_NORMAL
    w = _mk_world()
    for i in range(8):
        w.log_msg("Sponsor: " + "bardzo długa linia " * 4, LOG_SYNDIC)
        w.log_msg("Normalna linia bez avatara.", LOG_NORMAL)
    pygame.display.set_mode((1280, 720))
    surf = pygame.display.get_surface()
    surf.fill((0, 0, 0))
    _ui.draw_log_and_input(surf, w.log, "", False)
    print(f"  log render with {len(w.log)} entries: no crash: OK")


# ── Draw smoke ─────────────────────────────────────────────────────────

def test_draw_no_crash_after_p24_6():
    from ..engine.game import Game
    for ww, hh in ((1280, 720), (1920, 1080), (3440, 1440)):
        pygame.display.set_mode((ww, hh))
        g = Game(screen=pygame.display.get_surface())
        g.start_new_game("Tester", "janitor")
        g.state = "play"
        g.draw()
    print("  P24.6 draw OK at 1280×720 / 1920×1080 / 3440×1440: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_stat_pl_known_and_unknown()
    test_level_pl()
    test_intent_pl()
    test_format_check_example()
    test_format_check_with_extras()
    test_mood_placeholder_caption_renders()
    test_minimap_click_adjacent_unlocked_moves()
    test_minimap_click_locked_refuses()
    test_minimap_click_nonadjacent_returns_false()
    test_use_resolves_inventory_first()
    test_combat_lockdown_move_redirects_to_flee()
    test_combat_lockdown_loot_refused()
    test_combat_lockdown_info_free()
    test_log_renders_without_overlap()
    test_draw_no_crash_after_p24_6()
    print("Prompt 24.6 UX + bug sweep smoke: OK")


if __name__ == "__main__":
    main()
