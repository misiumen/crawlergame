"""Dialogue hub-return: after a branch you return to the full tree (the
conversation stays open), and exhausted one-shot topics drop off the menu
until you explicitly leave. Replaces the old "branch then dialogue closes,
re-approach to talk again" flow.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY, STATE_DIALOG
from ..engine import dialogue as _dlg
from ..systems.crawlers import make_random_crawler


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    return g


def _spawn_crawler(g):
    room = g.world.current_floor.current_room()
    c = make_random_crawler(1, room.room_id, disposition="neutral")
    c.visible = True; c.discovered = True
    g.world.register(c); room.entities.append(c)
    return c


def _labels(g):
    node = _dlg.current_node(g.dialogue_state)
    return [o.label for (_i, o) in
            _dlg.available_options(g.world, g.dialogue_state, node)]


def _pick_label(g, needle):
    labels = _labels(g)
    idx = next(i for i, l in enumerate(labels) if needle in l)
    g._pick_dialogue_option(idx)


def test_branch_returns_to_hub():
    g = _demo_game()
    c = _spawn_crawler(g)
    g.dispatch_entity_action(c.entity_id, "talk")
    assert g.state == STATE_DIALOG
    start_id = g.dialogue_state.current_node_id
    n_before = len(_labels(g))
    # Ask an info topic; we should land on its node then be able to return.
    _pick_label(g, "skąd jest")
    assert g.state == STATE_DIALOG, "info branch must NOT close the dialogue"
    # Walk back to the hub.
    _pick_label(g, "Wróć do rozmowy")
    assert g.dialogue_state.current_node_id == start_id, "should be back at hub"
    # The asked topic is now one_shot-consumed → fewer options than before.
    assert len(_labels(g)) < n_before, "exhausted topic should drop off the menu"
    print(f"  branch returns to hub, topic consumed ({n_before} -> {len(_labels(g))}): OK")


def test_leave_option_closes():
    g = _demo_game()
    c = _spawn_crawler(g)
    g.dispatch_entity_action(c.entity_id, "talk")
    _pick_label(g, "Skończ rozmowę")
    assert g.state == STATE_PLAY, "explicit leave should close the dialogue"
    print("  explicit leave closes dialogue: OK")


def test_start_line_quotes_balanced():
    # The start line previously dropped its closing quote.
    tree = _dlg.get_tree("default_crawler")
    txt = tree.node("start").text
    assert txt.count("„") == txt.count("”"), f"unbalanced quotes: {txt}"
    print("  start line quotes balanced: OK")


def main():
    test_branch_returns_to_hub()
    test_leave_option_closes()
    test_start_line_quotes_balanced()
    print("Dialogue hub-return smoke: OK")


if __name__ == "__main__":
    main()
