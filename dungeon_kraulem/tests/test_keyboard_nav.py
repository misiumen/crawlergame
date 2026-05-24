"""Prompt 08 smoke — keyboard cursor navigation.

Asserts that the option-group builder produces a sensible model without
revealing hidden state, that selection movement wraps correctly, and that
`submit_generated_command` routes through `submit_input` (which records
into command history).

This smoke does NOT exercise pygame event injection — it tests the model
layer directly.

Run: python -m revamp._smoke_keyboard_nav
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT, T_MONSTER
from ..ui import ui_nav


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    # One visible object, one hidden, one hostile, one exit
    junk = Entity(key="broken_table", entity_type=T_OBJECT, fallback_name="stół",
                  tags=["furniture","salvageable"], affordances=["inspect","salvage"],
                  location_id="r0")
    hidden = Entity(key="hidden_thing", entity_type=T_OBJECT, fallback_name="tajemnica",
                    tags=["secret"], affordances=["inspect"], location_id="r0",
                    visible=False, discovered=False)
    bot = Entity(key="bot", entity_type=T_MONSTER, fallback_name="goblin",
                 hp=6, max_hp=6, tags=["monster"], affordances=["attack"],
                 location_id="r0")
    r.entities.extend([junk, hidden, bot])
    for e in r.entities:
        w.register(e)
    r.exits = {"północ": {"target":"r1","locked":False,"hidden":False,
                          "hint_key":"","fallback_hint":""}}
    # Also a hidden exit — must not appear in options.
    r.exits["sekret"] = {"target":"r2","locked":False,"hidden":True,
                          "hint_key":"","fallback_hint":""}
    r2 = RoomState(room_id="r1", fallback_short_title="Inny pokój")
    f.add_room(r); f.add_room(r2)
    f.start_room_id="r0"; f.current_room_id="r0"
    f.discovered_room_ids = {"r0","r1"}
    w.current_floor = f
    return w, r


def test_groups_contain_expected_options():
    w, r = _mk_world()
    state = ui_nav.build_play_options(w)
    assert ui_nav.GROUP_ACTIONS in state.groups
    assert ui_nav.GROUP_EXITS in state.groups
    assert ui_nav.GROUP_OBJECTS in state.groups
    assert ui_nav.GROUP_ENTITIES in state.groups
    # Exits: visible north must appear, hidden 'sekret' must not.
    exit_labels = [o.label for o in state.options_in(ui_nav.GROUP_EXITS)]
    assert any("północ" in l for l in exit_labels), f"missing visible exit: {exit_labels}"
    assert not any("sekret" in l for l in exit_labels), f"hidden exit leaked: {exit_labels}"
    # Objects: visible stół must appear; hidden 'tajemnica' must not.
    obj_labels = [o.label for o in state.options_in(ui_nav.GROUP_OBJECTS)]
    assert any("stół" in l for l in obj_labels), f"missing visible object: {obj_labels}"
    assert not any("tajemnica" in l for l in obj_labels), f"hidden object leaked: {obj_labels}"
    # Salvage option present for salvageable tag.
    assert any("Zdemontuj" in l for l in obj_labels), f"salvage option missing: {obj_labels}"
    # Entities: goblin -> attack option.
    ent_labels = [o.label for o in state.options_in(ui_nav.GROUP_ENTITIES)]
    assert any("Zaatakuj" in l for l in ent_labels), f"attack option missing: {ent_labels}"
    print("  groups contain expected options: OK")


def test_move_and_cycle_wraps():
    w, r = _mk_world()
    state = ui_nav.build_play_options(w)
    g = ui_nav.GROUP_ACTIONS
    n = len(state.options_in(g))
    assert n > 0
    # Move down past end -> wraps to 0
    state.set_selected_index(n - 1, g)
    ui_nav.move_selection(state, +1)
    assert state.selected_index(g) == 0
    # Move up past 0 -> wraps to last
    ui_nav.move_selection(state, -1)
    assert state.selected_index(g) == n - 1
    # Cycle groups
    first_g = state.current_group()
    ui_nav.cycle_group(state, +1)
    assert state.current_group() != first_g
    ui_nav.cycle_group(state, -1)
    assert state.current_group() == first_g
    print("  movement + cycle wrap: OK")


def test_commands_are_plain_polish():
    """Every option's command must be a string that the deterministic
    parser can recognize without nav-specific magic."""
    w, r = _mk_world()
    state = ui_nav.build_play_options(w)
    from ..engine import parser_core
    seen = 0
    for g in state.groups:
        for o in state.options_in(g):
            seen += 1
            assert isinstance(o.command, str) and o.command.strip()
            intent = parser_core.parse(o.command)
            # The parser must accept at least the verb — intent != 'unknown'.
            assert intent.intent != "unknown", \
                f"option {o.option_id!r} -> command {o.command!r} not parsed"
    assert seen > 5
    print(f"  all commands parse: OK ({seen} options)")


def test_submit_generated_command_routes_through_submit_input():
    """Game.submit_generated_command must write into the same path as
    typed text, including command history."""
    from ..engine.game import Game
    g = Game(screen=None)
    g.world = WorldState()
    g.world.character = Character(name="N", background="janitor")
    # Minimal floor so submit_input doesn't crash on missing context.
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    g.world.current_floor = f

    g.state = "play"
    g.submit_generated_command("rozejrzyj się")
    # History should contain the command (route-through proof).
    assert g.cmd_history and g.cmd_history[-1] == "rozejrzyj się"
    print("  submit_generated_command -> cmd_history: OK")


def test_input_mode_default_text():
    from ..engine.game import Game
    g = Game(screen=None)
    assert g.input_mode == "text"
    print("  default input_mode == text: OK")


def main():
    test_groups_contain_expected_options()
    test_move_and_cycle_wraps()
    test_commands_are_plain_polish()
    test_submit_generated_command_routes_through_submit_input()
    test_input_mode_default_text()
    print("Prompt 08 keyboard-nav smoke: OK")


if __name__ == "__main__":
    main()
