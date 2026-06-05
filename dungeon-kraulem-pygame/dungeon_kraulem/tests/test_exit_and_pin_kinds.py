"""Four pin kinds (enemy / npc / object / exit) + exits-as-pins.

Exits are now interactive pins on the illustration, visually distinct
(door-shaped, amber) from the circular entity pins, which are colour-coded
by kind.

Asserts:
1. _entity_pin_kind classifies monster→enemy, npc/neutral-crawler→npc,
   hostile crawler→enemy, object/hazard→object.
2. Each kind has its own colour.
3. _draw_exit_pins registers one clickable zone per VISIBLE exit (hidden
   exits excluded); clicking issues idź/wyłam for that exit.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY
from ..engine.entity import Entity, T_OBJECT, T_MONSTER
from ..ui import ui as _ui
from ..ui.click_registry import ClickRegistry


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    return g


def _ent(etype, **kw):
    e = Entity(key="t", entity_type=etype, fallback_name="x")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def test_pin_kind_classifier():
    assert _ui._entity_pin_kind(_ent(T_MONSTER)) == _ui.PIN_ENEMY
    assert _ui._entity_pin_kind(_ent("npc")) == _ui.PIN_NPC
    assert _ui._entity_pin_kind(_ent("crawler")) == _ui.PIN_NPC
    assert _ui._entity_pin_kind(_ent("crawler", disposition="hostile")) == _ui.PIN_ENEMY
    assert _ui._entity_pin_kind(_ent(T_OBJECT)) == _ui.PIN_OBJECT
    assert _ui._entity_pin_kind(_ent("hazard")) == _ui.PIN_OBJECT
    print("  pin-kind classifier: OK")


def test_four_distinct_colors():
    cols = {_ui.PIN_ENEMY, _ui.PIN_NPC, _ui.PIN_OBJECT, _ui.PIN_EXIT}
    rgbs = {_ui._PIN_COLORS[k] for k in cols}
    assert len(rgbs) == 4, "all four pin kinds must have distinct colours"
    print("  four distinct pin colours: OK")


def test_exit_pins_clickable():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    room.exits = {
        "wschód": {"target": "r_x", "locked": False},
        "kierownictwo": {"target": "r_k", "locked": True},
        "sekret": {"target": "r_s", "hidden": True},
    }
    surf = pygame.Surface((1280, 720))
    reg = ClickRegistry()
    issued = []
    _ui._draw_exit_pins(surf, g.world, room, (640, 40, 620, 520), 64, None,
                        click_registry=reg,
                        command_cb=lambda c, target_id=None: issued.append(c),
                        mxy=None)
    zones = [z for z in reg.zones if z.category == "room_exit_pin"]
    assert len(zones) == 2, f"hidden exit must not pin: got {len(zones)}"
    # Fire all and check both an open (idź) and a locked (wyłam) command.
    for z in zones:
        z.callback()
    assert any(c.startswith("idź wschód") for c in issued), issued
    assert any(c.startswith("wyłam kierownictwo") for c in issued), issued
    print(f"  exit pins clickable (idź/wyłam): {issued}: OK")


def test_no_exits_no_crash():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    room.exits = {}
    surf = pygame.Surface((1280, 720))
    reg = ClickRegistry()
    _ui._draw_exit_pins(surf, g.world, room, (640, 40, 620, 520), 64, None,
                        click_registry=reg, command_cb=lambda *a, **k: None)
    assert not [z for z in reg.zones if z.category == "room_exit_pin"]
    print("  no exits → no crash: OK")


def main():
    test_pin_kind_classifier()
    test_four_distinct_colors()
    test_exit_pins_clickable()
    test_no_exits_no_crash()
    print("Pin kinds + exit pins smoke: OK")


if __name__ == "__main__":
    main()
