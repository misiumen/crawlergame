"""E2E P29.70 — render smoke awatara gracza (workstream C/1).

Rule 12d: zmiana UI = render smoke. Awatar buduje się z EQ, więc
sprawdzamy że RYSUJE się bez wyjątku dla różnych konfiguracji
(goły / pełne EQ / różne species / bezdomny) i faktycznie maluje
sylwetkę (piksele ≠ tło).
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest
import pygame

from ...ui import avatar as _avatar
from ...engine.character import Character


@pytest.fixture(scope="module")
def _pg():
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    yield


def _drew_something(surf) -> bool:
    """True, jeśli na powierzchni jest cokolwiek poza kolorem tła awatara."""
    bg = _avatar._BG
    w, h = surf.get_size()
    for yy in range(0, h, 3):
        for xx in range(0, w, 3):
            px = surf.get_at((xx, yy))[:3]
            if px != bg and px != (0, 0, 0):
                return True
    return False


def _surf():
    return pygame.Surface((120, 120))


def test_avatar_naked_character_renders(_pg):
    c = Character(name="Goły", background="bezdomny")
    s = _surf()
    _avatar.draw_avatar(s, c, 0, 0, 120, 120)
    assert _drew_something(s)


def test_avatar_full_equipment_renders(_pg):
    c = Character(name="Pancerny", background="soldier")
    c.worn_slots = {"head": 1, "torso": 2, "legs": 3, "back": 4}
    c.wielded_main_id = 5
    c.wielded_offhand_id = 6
    s = _surf()
    _avatar.draw_avatar(s, c, 0, 0, 120, 120)
    assert _drew_something(s)


def test_avatar_varies_with_species_and_origin(_pg):
    # Dwa różne profile nie powinny dać identycznego renderu.
    a = Character(name="A", background="office_worker")
    a.species_key = "baseline_human"
    b = Character(name="B", background="mechanic")
    b.species_key = "synthetic"
    sa, sb = _surf(), _surf()
    _avatar.draw_avatar(sa, a, 0, 0, 120, 120)
    _avatar.draw_avatar(sb, b, 0, 0, 120, 120)
    grid_a = [sa.get_at((xx, yy))[:3]
              for yy in range(0, 120, 6) for xx in range(0, 120, 6)]
    grid_b = [sb.get_at((xx, yy))[:3]
              for yy in range(0, 120, 6) for xx in range(0, 120, 6)]
    assert grid_a != grid_b, "awatary różnych profili identyczne"


def test_avatar_none_character_safe(_pg):
    s = _surf()
    _avatar.draw_avatar(s, None, 0, 0, 120, 120)   # nie rzuca


def test_avatar_low_hp_ring_renders(_pg):
    c = Character(name="Ranny", background="nurse")
    c.hp = 5
    s = _surf()
    _avatar.draw_avatar(s, c, 0, 0, 120, 120)
    assert _drew_something(s)


def test_portrait_helper_delegates(_pg):
    """Sidebar helper deleguje do awatara bez wyjątku."""
    from ...ui import ui as _ui
    c = Character(name="Tester", background="janitor")
    s = pygame.Surface((140, 200))
    _ui._draw_player_portrait_placeholder(s, c, 8, 8, 120, 120)
