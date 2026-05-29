"""E2E P29.62 — origin „bezdomny" (underdog challenge + Przetrwanie).

User-approved spec (2026-05-29):
  „brakuje mi origin który ma być wyzwaniem. zróbmy dodatkowy origin
  bezdomny. ma słabsze statystyki bazowe od każdego. zaczyna z losowym
  statustem na siebie nałożonym, bleed/poison cokolwiek. jego dodatkową
  umiejętnością powinien być survival, czyli jedzenie i napoje leczą go
  bardziej."

Pokrywa (Rule 12b):
  * rejestracja origin + NAJSŁABSZE staty ze wszystkich
  * 0 kredytów, brak broni startowej, losowy negatywny status na starcie
  * Przetrwanie: jedzenie/picie +50% (pełna ścieżka _attempt_consume)
  * twardy żołądek: je niejadalne/zepsute zwłoki bez kary statusu
  * +1 do plonu z patroszenia (szperacz)
  * render smoke kreatora postaci (Rule 12d) — lista 14 origin NIE
    wchodzi w bleed z podpowiedzią na dole ekranu.
"""
from __future__ import annotations
import os
import pytest

# Headless pygame PRZED importami pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine.game import Game
from ...engine import character as _char
from ...engine.character import BACKGROUNDS, Character
from ...engine import corpses as _corpses
from ...engine.entity import Entity, T_CORPSE
from ...engine.parser_core import ActionIntent
from ...content.data.monster_salvage import template_for

_AILMENTS = {"bleeding", "poisoned", "wounded"}


def _new_game(bg: str) -> Game:
    g = Game(screen=None)
    g.start_new_game("Tester", bg)
    return g


def _corpse(original_key: str) -> Entity:
    """Minimalne zwłoki gotowe do eat() — tyle stanu, ile czyta eat()."""
    e = Entity(key=original_key, entity_type=T_CORPSE,
               fallback_name="ciało")
    e.state = {"original_key": original_key, "eaten_uses": 0, "dead": True}
    return e


# ── Rejestracja + staty ─────────────────────────────────────────────


def test_bezdomny_registered_in_backgrounds():
    assert "bezdomny" in BACKGROUNDS


def test_bezdomny_has_weakest_stats_of_all():
    """„słabsze statystyki bazowe OD KAŻDEGO" — suma statów bezdomnego
    musi być ściśle najniższa spośród wszystkich origin."""
    sums = {}
    g = Game(screen=None)
    for bg in BACKGROUNDS:
        g.start_new_game("T", bg)
        sums[bg] = sum(g.world.character.stats.values())
    others = [v for k, v in sums.items() if k != "bezdomny"]
    assert sums["bezdomny"] < min(others), (
        f"bezdomny={sums['bezdomny']} nie jest najsłabszy: {sums}")


# ── Underdog: 0 kredytów, bez broni, losowy status ──────────────────


def test_bezdomny_zero_credits_and_unarmed():
    c = _new_game("bezdomny").world.character
    assert c.credits == 0, "bezdomny ma startować bez grosza"
    assert c.wielded_main_id is None, "bezdomny nie ma broni startowej"


def test_bezdomny_starts_with_random_ailment():
    """Zawsze JEDEN z trzech statusów, nigdy bez."""
    seen = set()
    for _ in range(12):
        c = _new_game("bezdomny").world.character
        ail = [x for x in c.conditions if x in _AILMENTS]
        assert ail, f"bezdomny bez startowej dolegliwości: {c.conditions}"
        seen.update(ail)
    assert seen <= _AILMENTS, f"nieoczekiwany status: {seen - _AILMENTS}"


def test_non_bezdomny_starts_healthy():
    c = _new_game("soldier").world.character
    assert not [x for x in c.conditions if x in _AILMENTS]


# ── Helpery Przetrwania (derived z background — save-safe) ──────────


def test_survival_helpers_only_for_bezdomny():
    bez = Character(name="b", background="bezdomny")
    off = Character(name="o", background="office_worker")
    assert _char.survival_heal_mult(bez) == 1.5
    assert _char.survival_heal_mult(off) == 1.0
    assert _char.has_tough_stomach(bez) is True
    assert _char.has_tough_stomach(off) is False
    assert _char.salvage_bonus(bez) == 1
    assert _char.salvage_bonus(off) == 0


# ── Przetrwanie: jedzenie/picie +50% (pełna ścieżka konsumpcji) ─────


def _eat_snack(bg: str, start_hp: int = 40) -> int:
    """Start gry, dorzuć baton, zjedz przez _attempt_consume, zwróć
    przyrost HP."""
    from ...content.items import make_item
    g = _new_game(bg)
    c = g.world.character
    snack = make_item("snack_bar", location_id="inventory:player")
    g.world.register(snack)
    c.inventory_ids.append(snack.entity_id)
    c.hp = start_hp
    pre = c.hp
    g._attempt_consume(ActionIntent(verb="zjedz", targets=["baton"]))
    return c.hp - pre


def test_food_heals_50pct_more_for_bezdomny():
    # snack_bar heal=12; bezdomny *1.5 = 18, office_worker = 12.
    assert _eat_snack("office_worker") == 12
    assert _eat_snack("bezdomny") == 18


# ── Twardy żołądek: niejadalne / zepsute bez kary ───────────────────


def test_tough_stomach_eats_inedible_corpse():
    """Niejadalne zwłoki: bezdomny zjada (i coś z tego ma), zwykły
    człowiek odmawia."""
    c_bez = Character(name="b", background="bezdomny")
    c_off = Character(name="o", background="office_worker")

    r_off = _corpses.eat(None, _corpse("nieznany_trup"), c_off)
    assert r_off.ok is False, "zwykły człowiek powinien odmówić"

    r_bez = _corpses.eat(None, _corpse("nieznany_trup"), c_bez)
    assert r_bez.ok is True, "twardy żołądek powinien przełknąć"
    assert r_bez.status_applied is None
    assert r_bez.hp_delta > 0, "z niejadalnego trupa ma być choć kęs kalorii"


def test_tough_stomach_suppresses_spoiled_status():
    """freezer_carver: normalnie -4 HP + status 'sick'. Bezdomny: bez
    statusu, bez utraty HP."""
    c_off = Character(name="o", background="office_worker")
    c_bez = Character(name="b", background="bezdomny")

    r_off = _corpses.eat(None, _corpse("freezer_carver"), c_off)
    assert r_off.ok is True
    assert r_off.status_applied == "sick"
    assert r_off.hp_delta < 0

    r_bez = _corpses.eat(None, _corpse("freezer_carver"), c_bez)
    assert r_bez.ok is True
    assert r_bez.status_applied is None, "twardy żołądek znosi 'sick'"
    assert r_bez.hp_delta >= 0, "twardy żołądek nie traci HP na zepsutym"


def test_survival_boosts_edible_corpse_heal():
    """tunnel_runt jadalny +2 HP → bezdomny dostaje więcej niż zwykły."""
    c_off = Character(name="o", background="office_worker")
    c_bez = Character(name="b", background="bezdomny")
    r_off = _corpses.eat(None, _corpse("tunnel_runt"), c_off)
    r_bez = _corpses.eat(None, _corpse("tunnel_runt"), c_bez)
    assert r_off.hp_delta == 2
    assert r_bez.hp_delta > r_off.hp_delta, "Przetrwanie ma wzmocnić +2"


# ── Szperacz: +1 do plonu z patroszenia ─────────────────────────────


def test_scavenger_salvage_bonus():
    """Przy IDENTYCZNYM rzucie kości bezdomny wyciąga +1 z każdej
    pozycji tabeli salvage."""
    import random as _r
    spec = template_for("tunnel_runt").get("salvage") or {}
    n_entries = len(spec)
    assert n_entries > 0

    c_off = Character(name="o", background="office_worker")
    c_bez = Character(name="b", background="bezdomny")
    _corpses.butcher(None, _corpse("tunnel_runt"), c_off,
                     rng=_r.Random(42))
    _corpses.butcher(None, _corpse("tunnel_runt"), c_bez,
                     rng=_r.Random(42))
    off_total = sum((c_off.materials or {}).values())
    bez_total = sum((c_bez.materials or {}).values())
    assert bez_total == off_total + n_entries, (
        f"szperacz +1/pozycję: off={off_total} bez={bez_total} "
        f"entries={n_entries}")


# ── Render smoke (Rule 12d): kreator z 14 origin nie robi bleed ─────


@pytest.fixture(scope="module")
def _pygame_headless():
    import pygame
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    yield
    # Bez pygame.quit() — inne moduły testowe dzielą stan pygame.


def test_creation_background_step_renders(_pygame_headless):
    """draw_creation na kroku 'background' z zaznaczonym bezdomnym
    renderuje się bez wyjątku (catch crashy layoutu)."""
    import pygame
    from ...ui import ui as _ui
    surf = pygame.Surface((1280, 720))
    bez_idx = list(BACKGROUNDS).index("bezdomny")
    _ui.draw_creation(surf, {"step": "background", "selected_bg": bez_idx})


def test_creation_bg_list_fits_above_bottom_hint(_pygame_headless):
    """Lista origin (14 baz) MUSI zmieścić się powyżej podpowiedzi na
    dole (sh-40). Zagęszczenie do 36px/wiersz (cy=132) trzyma to z
    zapasem — sentinel przeciw nawrotom bleedu przy dorzucaniu origin.
    Stałe mirrorują ui.py (wzorzec jak test_log_render_bleed)."""
    sh = 720
    cy_start = 132
    row_h = 20 + 16            # name += 20, desc += 16
    n = len(BACKGROUNDS)
    last_desc_baseline = cy_start + (n - 1) * row_h + 20
    bottom_hint_y = sh - 40
    assert last_desc_baseline < bottom_hint_y - 8, (
        f"bleed: ostatni wiersz origin na y={last_desc_baseline}, "
        f"podpowiedź na y={bottom_hint_y}. Lista za długa.")
