"""E2E P29.73 — biomy losowe od F1 + bez powtórki dwa piętra z rzędu.

User: „piętra miały być losowe... F1 i F2 ten sam biom? nie taki był plan".
Naprawa: Tier-1 biomy dostępne od piętra 1 (floor_min=1) → szeroka pula
od startu; generator nie pozwala na ten sam biom dwa piętra z rzędu.
"""
from __future__ import annotations
import os
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...content.data.floor_biomes import available_biomes
from ...engine.world import WorldState
from ...engine.floor_generator import generate_floor


# ── Różnorodność od piętra 1 ────────────────────────────────────────


def test_tier1_biomes_available_from_floor1():
    keys = {b.key for b in available_biomes(1)}
    assert len(keys) > 1, f"F1 ma tylko {keys} — brak różnorodności"
    # Tier-1 biomy muszą być dostępne już na F1 (nie tylko intake).
    assert "zoo_korporacyjne" in keys
    assert "bar_skurczybyk" in keys
    assert "intake_industrial" in keys


def test_floor2_not_locked_to_single_biome():
    assert len({b.key for b in available_biomes(2)}) > 1


def test_deep_biomes_stay_late():
    # Grzybica (floor_min=10) NIE powinna być dostępna na F1.
    assert "grzybica_bloom" not in {b.key for b in available_biomes(1)}


# ── Bez tego samego biomu dwa piętra z rzędu ────────────────────────


def test_no_consecutive_biome_repeat():
    prev = "zoo_korporacyjne"
    for seed in range(16):
        w = WorldState()
        # Symuluj piętro, które gracz opuszcza (generator czyta jego biom).
        w.current_floor = types.SimpleNamespace(biome_key=prev)
        f = generate_floor(w, floor_number=2, seed=seed)
        assert f.biome_key != prev, \
            f"seed {seed}: powtórzony biom z rzędu ({prev})"


def test_first_floor_has_no_previous_constraint():
    # Brak poprzedniego piętra → guard nie wyrzuca wyjątku, biom się losuje.
    w = WorldState()
    w.current_floor = None
    f = generate_floor(w, floor_number=1, seed=3)
    assert f.biome_key  # jakiś biom przypisany (pula F1 niepusta)
