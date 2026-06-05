"""P29.65 Etap D — game-juice walki (Bug #25 „jak Excel").

SFX już działał; brakowało warstwy WIZUALNEJ. Tu pilnujemy, że:
  * _spawn_combat_fx dokłada pływającą liczbę + błysk + (opcjonalnie) shake
    na world.combat_fx,
  * update(dt) wygasza efekty (floatery znikają po ttl, flash/shake maleją),
  * draw_combat_arena renderuje arenę Z aktywnymi efektami bez wyjątku
    (render-smoke na realnym set_mode).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from ..engine import arena, combat
from ..engine.game import Game
from ..ui import ui


def _arena(vk="duel_1v1"):
    res = arena.build_arena_world(vk)
    return res[0] if isinstance(res, tuple) else res


def test_spawn_and_decay():
    w = _arena()
    g = Game(screen=None)
    g.world = w
    g.state = "play"
    g._spawn_combat_fx("player", "-12", (255, 90, 90), big=True, shake=7.0)
    fx = w.combat_fx
    assert len(fx["floaters"]) == 1
    assert "player" in fx["flash"] and fx["shake"] == 7.0
    # 100 ms: shake gaśnie, flash maleje, floater wciąż żyje.
    g.update(100)
    assert fx["shake"] == 0.0
    assert fx["flash"].get("player", 0) < 240
    assert fx["floaters"] and fx["floaters"][0]["age"] >= 100
    # Po przekroczeniu ttl floater znika.
    g.update(1000)
    assert not fx["floaters"], "floater powinien wygasnąć po ttl"
    print("  spawn + decay (floater/flash/shake) OK")


def test_floater_cap():
    w = _arena()
    g = Game(screen=None); g.world = w; g.state = "play"
    for i in range(40):
        g._spawn_combat_fx("player", f"-{i}", (255, 255, 255))
    assert len(w.combat_fx["floaters"]) <= 24, "lista floaterów musi mieć cap"
    print("  floater cap (<=24) OK")


def test_arena_renders_with_fx():
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    screen = pygame.display.set_mode((1280, 800))
    w = _arena("triple_threat")
    room = w.current_floor.current_room()
    cs = combat.start_combat(room, w)
    # Zasiej efekty: błysk + pływające liczby na wrogu i graczu + shake.
    mob_eid = cs.participants[0]
    w.combat_fx = {
        "floaters": [
            {"anchor": mob_eid, "text": "-18", "color": (255, 210, 70),
             "age": 100.0, "ttl": 950.0, "big": True},
            {"anchor": "player", "text": "-9", "color": (255, 90, 90),
             "age": 300.0, "ttl": 950.0, "big": False},
        ],
        "flash": {mob_eid: 200.0, "player": 120.0},
        "shake": 130.0,
    }
    # Render-smoke: nie może rzucić.
    ui.draw_combat_arena(screen, w, cs)
    pygame.display.flip()
    print("  draw_combat_arena z aktywnym game-juice: render OK")


def main():
    test_spawn_and_decay()
    test_floater_cap()
    test_arena_renders_with_fx()
    print("P29.65 Etap D combat juice: OK")


if __name__ == "__main__":
    main()
