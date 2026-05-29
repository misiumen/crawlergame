"""E2E P29.71 — pipeline ilustracji (workstream C/2).

User wybrał: „pipeline + Ty generujesz art". Dowodzimy że SLOTY +
loader + łańcuch fallbacków działają i gra renderuje się bez grafik
(fallback proceduralny), a wrzucony PNG byłby użyty.
"""
from __future__ import annotations
import os
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest
import pygame

from ...ui import art as _art
from ...ui import assets as _assets
from ...engine.entity import Entity, T_MONSTER


@pytest.fixture(scope="module")
def _pg():
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    yield


def _room(biome="", rtype="combat"):
    r = types.SimpleNamespace()
    r.biome = biome
    r.actual_type = rtype
    r.entities = []
    return r


# ── Łańcuchy kluczy ─────────────────────────────────────────────────


def test_room_bg_key_chain_order():
    # P29.74 — wszystko per biom (bg_<biome>_<typ> → bg_<biome>), bez
    # biome-agnostycznych bg_room_<typ>/bg_default (bleed między biomami).
    keys = _art.room_bg_keys(_room(biome="zoo_korporacyjne", rtype="boss"))
    assert keys == ["bg_zoo_korporacyjne_boss", "bg_zoo_korporacyjne"]


def test_room_bg_key_chain_no_biome():
    # Brak biomu → brak kluczy → gradient (żadnego wspólnego bg_default).
    assert _art.room_bg_keys(_room(biome="", rtype="combat")) == []


def test_enemy_archetype_from_tags():
    def mob(*tags):
        return Entity(key="m", entity_type=T_MONSTER, fallback_name="m",
                      tags=list(tags))
    assert _art.enemy_archetype(mob("monster", "robot")) == "robot"
    assert _art.enemy_archetype(mob("monster", "beast")) == "beast"
    assert _art.enemy_archetype(mob("monster", "humanoid")) == "humanoid"
    assert _art.enemy_archetype(mob("monster")) == "humanoid"   # domyślnie


def test_enemy_art_keys_chain():
    e = Entity(key="intake_warden", entity_type=T_MONSTER,
               fallback_name="W", tags=["monster", "humanoid"])
    # Bez biomu: mob → archetyp neutralny.
    assert _art.enemy_art_keys(e) == ["wrog_intake_warden", "wrog_humanoid"]
    # Z biomem (P29.75 — BIOME-FIRST): prefiks krótkiego członu biomu z
    # przodu, potem warianty archetypu. Pierwszy istniejący plik wygrywa.
    assert _art.enemy_art_keys(e, "intake_industrial") == [
        "wrog_intake_intake_warden", "wrog_intake_warden",
        "wrog_intake_humanoid_industrial", "wrog_intake_humanoid",
        "wrog_humanoid_intake_industrial", "wrog_humanoid"]


def test_enemy_art_keys_biome_first_matches_user_files():
    # Pliki usera dla Sortowni: wrog_intake_<mob>. Łańcuch MUSI je trafić
    # PRZED neutralnym fallbackiem archetypu.
    def mob(key, *tags):
        return Entity(key=key, entity_type=T_MONSTER, fallback_name=key,
                      tags=["monster", *tags])
    for key in ("tunnel_runt", "freezer_carver", "biotech_inspector"):
        keys = _art.enemy_art_keys(mob(key, "humanoid"), "intake_industrial")
        assert keys[0] == f"wrog_intake_{key}"


# ── Loader: None gdy brak pliku ─────────────────────────────────────


def test_load_image_none_when_missing(_pg):
    assert _assets.load_image("nieistnieje_xyz_123", 32, 32) is None
    assert _assets.has_image("nieistnieje_xyz_123") is False


# ── Fallback renderuje się bez grafik (gra nie pęka) ────────────────


def test_room_background_fallback_renders(_pg, monkeypatch):
    # Wymuś BRAK plików (izolacja od grafik wrzuconych na dysk, np.
    # bg_default.png), żeby przetestować ścieżkę gradientu.
    monkeypatch.setattr(_art._assets, "load_image", lambda *a, **k: None)
    surf = pygame.Surface((200, 120))
    used_real = _art.draw_room_background(surf, _room(biome="bar_skurczybyk"),
                                          (0, 0, 200, 120))
    assert used_real is False           # brak PNG → fallback gradient
    # Gradient: górny i dolny piksel różne.
    assert surf.get_at((5, 2))[:3] != surf.get_at((5, 117))[:3]


def test_enemy_portrait_fallback_renders(_pg, monkeypatch):
    monkeypatch.setattr(_art._assets, "load_image", lambda *a, **k: None)
    surf = pygame.Surface((80, 80))
    e = Entity(key="x", entity_type=T_MONSTER, fallback_name="x",
               tags=["monster", "robot"])
    used_real = _art.draw_enemy_portrait(surf, e, (0, 0, 80, 80))
    assert used_real is False
    # Coś narysowane (nie czysto czarne tło).
    drew = any(surf.get_at((xx, yy))[:3] not in ((0, 0, 0), (20, 22, 28))
               for yy in range(0, 80, 5) for xx in range(0, 80, 5))
    assert drew


def test_room_background_none_safe(_pg):
    surf = pygame.Surface((50, 50))
    assert _art.draw_room_background(surf, None, (0, 0, 50, 50)) is False
