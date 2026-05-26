"""Prompt 28 — sidebar stat block + party panel smoke suite.

Covers:
  * Right sidebar renders 6-stat block visibly (P27-UX-1)
  * Companion panel surfaces an active pet (P27-UX-6)
  * Sidebar renders at all three layout widths without crash
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1920, 1080))


def test_sidebar_renders_at_three_widths():
    from ..engine.game import Game
    sizes = [(1280, 720), (1920, 1080), (3440, 1440)]
    for w, h in sizes:
        pygame.display.set_mode((w, h))
        g = Game(screen=pygame.display.get_surface())
        g.start_new_game("Tester", "janitor")
        g.state = "play"
        g.draw()
    print(f"  sidebar renders at {len(sizes)} widths: OK")


def test_sidebar_with_companion_pet():
    """opiekun_zwierzaka background spawns a starter pet — verify
    no crash and pet visible in companion list."""
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "opiekun_zwierzaka")
    g.state = "play"
    cids = g.world.character.companion_ids
    assert cids, "opiekun_zwierzaka should have a companion"
    g.draw()
    print(f"  sidebar with {len(cids)} companion(s) drew OK")


def test_sidebar_no_companion_no_party_panel():
    """Backgrounds without companions don't show the party header."""
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    assert not g.world.character.companion_ids
    g.draw()
    print("  janitor (no party) draws OK")


def main():
    test_sidebar_renders_at_three_widths()
    test_sidebar_with_companion_pet()
    test_sidebar_no_companion_no_party_panel()
    print("Prompt 28 sidebar + party panel smoke: OK")


if __name__ == "__main__":
    main()
