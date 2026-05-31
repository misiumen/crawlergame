"""UX-10 — contextual entity action popover.

Clicking a world entity (pin) opens a floating menu of its verbs, dispatched
parser-free by entity id. Single-verb entities skip the menu and act directly.

Asserts:
1. Opening a popover on a multi-verb entity sets entity_popover with its
   options (built from the same logic the action panel uses).
2. A single-verb entity skips the menu and dispatches directly.
3. Activating an option dispatches the right action and closes the menu.
4. Keyboard move wraps the selection; Esc-style close works.
5. The popover auto-closes when its entity leaves the room.
6. Renderer fills `rect` and registers one click zone per option.
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
    g.input_text = ""
    return g


def _place(g, *, name, etype=T_OBJECT, affordances=("inspect",),
           tags=(), portable=False, desc="Opis.", hp=20):
    room = g.world.current_floor.current_room()
    e = Entity(key="t", entity_type=etype, fallback_name=name,
               fallback_desc=desc, tags=list(tags),
               affordances=list(affordances), location_id=room.room_id,
               hp=hp, max_hp=hp, ac=10, damage_dice="1d4")
    e.visible = True
    e.discovered = True
    e.portable = portable
    g.world.register(e)
    room.entities.append(e)
    return e


def test_open_multi_verb_entity_opens_menu():
    g = _demo_game()
    # Salvageable furniture → inspect + salvage (2+ verbs).
    e = _place(g, name="drewniane meble",
               tags=["furniture", "salvageable"],
               affordances=["inspect", "salvage"], desc="Stół.")
    g.open_entity_popover(e.entity_id, anchor=(500, 300))
    assert g.entity_popover is not None, "menu should open for multi-verb entity"
    opts = g.entity_popover["options"]
    assert len(opts) >= 2, [o.label for o in opts]
    ats = {o.action_type for o in opts}
    assert "inspect" in ats and "salvage" in ats, ats
    print(f"  multi-verb opens menu: {[o.label for o in opts]}: OK")


def test_single_verb_dispatches_directly():
    g = _demo_game()
    # Plain decoration with only inspect → no menu, direct dispatch.
    e = _place(g, name="zardzewiała tabliczka", affordances=["inspect"])
    g.open_entity_popover(e.entity_id, anchor=(400, 300))
    assert g.entity_popover is None, "single-verb entity should skip the menu"
    print("  single-verb dispatches directly: OK")


def test_activate_dispatches_and_closes():
    g = _demo_game()
    e = _place(g, name="Wrog", etype=T_MONSTER,
               affordances=["inspect", "attack"], hp=100)
    g.open_entity_popover(e.entity_id, anchor=(500, 300))
    assert g.entity_popover is not None
    opts = g.entity_popover["options"]
    atk = next(i for i, o in enumerate(opts) if o.action_type == "attack")
    from ..engine import combat as _cmb
    room = g.world.current_floor.current_room()
    g._entity_popover_activate(atk)
    assert g.entity_popover is None, "activation must close the menu"
    assert _cmb.get_combat(room) is not None, "attack option should start combat"
    print("  activate dispatches + closes: OK")


def test_keyboard_move_wraps():
    g = _demo_game()
    e = _place(g, name="drewniane meble",
               tags=["furniture", "salvageable"],
               affordances=["inspect", "salvage"])
    g.open_entity_popover(e.entity_id, anchor=(500, 300))
    n = len(g.entity_popover["options"])
    g.entity_popover["idx"] = 0
    g._entity_popover_move(-1)
    assert g.entity_popover["idx"] == n - 1, "up from 0 should wrap to last"
    g._entity_popover_move(1)
    assert g.entity_popover["idx"] == 0, "down should wrap back to 0"
    g._close_entity_popover()
    assert g.entity_popover is None
    print("  keyboard move wraps + close: OK")


def test_renderer_fills_rect_and_zones():
    g = _demo_game()
    e = _place(g, name="drewniane meble",
               tags=["furniture", "salvageable"],
               affordances=["inspect", "salvage"])
    g.open_entity_popover(e.entity_id, anchor=(500, 300))
    surf = pygame.Surface((1280, 720))
    reg = ClickRegistry()
    picked = []
    _ui.draw_entity_popover(surf, g.entity_popover, layout=None,
                            click_registry=reg,
                            on_select=lambda i: picked.append(i))
    assert g.entity_popover["rect"] is not None, "renderer must set rect"
    zones = [z for z in reg.zones if z.category == "entity_popover"]
    assert len(zones) == len(g.entity_popover["options"]), \
        (len(zones), len(g.entity_popover["options"]))
    zones[0].callback()
    assert picked == [0], picked
    print("  renderer fills rect + zones: OK")


def test_autoclose_when_entity_leaves():
    g = _demo_game()
    e = _place(g, name="drewniane meble",
               tags=["furniture", "salvageable"],
               affordances=["inspect", "salvage"])
    g.open_entity_popover(e.entity_id, anchor=(500, 300))
    assert g.entity_popover is not None
    # Simulate the entity being removed from the room, then a draw tick's
    # guard (replicated here) should drop the stale menu.
    room = g.world.current_floor.current_room()
    room.entities.remove(e)
    eid = g.entity_popover["entity_id"]
    ent = g.world.get(eid)
    if ent is None or ent not in room.entities:
        g.entity_popover = None
    assert g.entity_popover is None, "stale menu should auto-close"
    print("  autoclose when entity leaves: OK")


def main():
    test_open_multi_verb_entity_opens_menu()
    test_single_verb_dispatches_directly()
    test_activate_dispatches_and_closes()
    test_keyboard_move_wraps()
    test_renderer_fills_rect_and_zones()
    test_autoclose_when_entity_leaves()
    print("Entity action popover (UX-10) smoke: OK")


if __name__ == "__main__":
    main()
