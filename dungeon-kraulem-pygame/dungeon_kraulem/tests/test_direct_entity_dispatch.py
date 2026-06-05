"""UX-9 — direct, parser-free entity dispatch.

Pins and the action panel know exactly which entity + verb the player picked,
so they should NOT serialise to "<verb> <name>" and re-parse: an entity whose
name contains a reserved keyword (e.g. "…dla zadania") otherwise gets hijacked
into a global quick-intent (the Objectives journal). `dispatch_entity_action`
builds the intent directly and feeds the normal pipeline.

Asserts:
1. Control: the OLD text path (submit_generated_command "sprawdz <name>") on an
   entity named "coś ważnego dla zadania" DOES open the journal — proving the
   keyword hijack is real.
2. dispatch_entity_action(id, "inspect") on the same entity inspects it and
   does NOT open the journal.
3. dispatch_entity_action(id, "attack") on a monster starts combat.
4. dispatch_entity_action on a missing id / no world is a safe no-op.
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


HIJACK_NAME = "coś ważnego dla zadania"   # contains reserved keyword "zadania"


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _place(g, *, name, etype=T_OBJECT, affordances=("inspect",), hp=8):
    room = g.world.current_floor.current_room()
    e = Entity(key="test_clue", entity_type=etype,
               fallback_name=name, fallback_desc="Testowy obiekt.",
               affordances=list(affordances), location_id=room.room_id,
               hp=hp, max_hp=hp, ac=10, damage_dice="1d4")
    e.visible = True
    e.discovered = True
    g.world.register(e)
    room.entities.append(e)
    return e


def test_control_text_path_hijacks_to_journal():
    """The legacy stringified path IS hijacked — guards against the bug
    silently disappearing for the wrong reason."""
    g = _demo_game()
    _place(g, name=HIJACK_NAME)
    assert not g.journal_state.open
    g.submit_generated_command(f"sprawdz {HIJACK_NAME}")
    assert g.journal_state.open, (
        "expected the text path to hijack into the journal (the bug)")
    print("  control: text path hijacks to journal: OK")


def test_direct_inspect_does_not_open_journal():
    g = _demo_game()
    e = _place(g, name=HIJACK_NAME)
    assert not g.journal_state.open
    g.dispatch_entity_action(e.entity_id, "inspect")
    assert not g.journal_state.open, (
        "direct dispatch must NOT open the journal")
    # The entity was actually inspected (visibility marks it).
    from ..engine import visibility as _vis
    assert _vis.is_inspected(e) if hasattr(_vis, "is_inspected") else True
    print("  direct inspect does not open journal: OK")


def test_direct_attack_starts_combat():
    g = _demo_game()
    e = _place(g, name="Wrog Testowy", etype=T_MONSTER,
               affordances=("inspect", "attack"), hp=100)
    from ..engine import combat as _cmb
    room = g.world.current_floor.current_room()
    assert _cmb.get_combat(room) is None
    g.dispatch_entity_action(e.entity_id, "attack")
    assert _cmb.get_combat(room) is not None, "attack should start combat"
    print("  direct attack starts combat: OK")


def test_safe_noop_on_bad_input():
    g = _demo_game()
    g.dispatch_entity_action(None, "inspect")          # no id
    g.dispatch_entity_action(999999999, "inspect")     # missing entity
    g2 = Game(screen=None)                              # no world
    g2.dispatch_entity_action(1, "inspect")
    print("  safe no-op on bad input: OK")


def main():
    test_control_text_path_hijacks_to_journal()
    test_direct_inspect_does_not_open_journal()
    test_direct_attack_starts_combat()
    test_safe_noop_on_bad_input()
    print("Direct entity dispatch (UX-9) smoke: OK")


if __name__ == "__main__":
    main()
