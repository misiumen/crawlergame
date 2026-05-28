"""P29.58 — Progressive floor sizing (F1 intake → F18 brutalne).

Pokrywa:
* floor_size_for_floor: krzywa per piętro, monotonicznie niemalejąca
* Generator faktycznie produkuje pokoje w docelowym zakresie
* F1 intake (~20) i F18 wielkie (~85-120) na rzeczywistych
  generacjach
* Boss count skaluje się z floor_size (max(2, rooms//5))
* Performance sanity: F18 generuje się w <3s
* No regression: generator nadal walidownalny dla wielu seedów
"""
from __future__ import annotations
import random
import time

from ..engine import floor_sizing as _fs
from ..engine import floor_generator as _fg
from ..engine import boss_ranks as _br
from ..engine.world import WorldState
from ..engine.character import Character


def _new_world():
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    return w


# ── floor_sizing module ────────────────────────────────────────────


def test_floor_size_f1_is_intake_sized():
    mn, mx = _fs.floor_size_for_floor(1)
    assert 15 <= mn <= 25, f"F1 min za daleko: {mn}"
    assert 18 <= mx <= 30, f"F1 max za daleko: {mx}"
    assert mn <= mx


def test_floor_size_f18_is_brutal():
    mn, mx = _fs.floor_size_for_floor(18)
    assert mn >= 70, f"F18 min za mały: {mn}"
    assert mx >= 100, f"F18 max za mały: {mx}"
    assert mx <= 150  # sanity upper bound


def test_floor_size_monotonic_non_decreasing():
    """F(n+1) min/max >= F(n) min/max. Krzywa nie cofa się."""
    prev_mn = prev_mx = 0
    for fn in range(1, 19):
        mn, mx = _fs.floor_size_for_floor(fn)
        assert mn >= prev_mn, f"F{fn} min={mn} < prev {prev_mn}"
        assert mx >= prev_mx, f"F{fn} max={mx} < prev {prev_mx}"
        prev_mn, prev_mx = mn, mx


def test_floor_size_out_of_range_caps_to_top():
    """Powyżej F18 — używamy top bandu, nie crashujemy."""
    mn, mx = _fs.floor_size_for_floor(99)
    top_mn, top_mx = _fs.floor_size_for_floor(18)
    assert (mn, mx) == (top_mn, top_mx)


def test_floor_size_below_one_treats_as_one():
    assert _fs.floor_size_for_floor(0) == _fs.floor_size_for_floor(1)
    assert _fs.floor_size_for_floor(-5) == _fs.floor_size_for_floor(1)


# ── Generator integration ──────────────────────────────────────────


def test_f1_actual_room_count_in_band():
    """F1 generacja produkuje pokoi w zakresie F1 sizing."""
    mn, mx = _fs.floor_size_for_floor(1)
    # Z różnymi seedami sprawdzamy że ramy są dotrzymane (arch_scale
    # może dać 0.85-1.0, więc dolna granica luźniejsza).
    for seed in (1, 7, 42, 99):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=1, seed=seed)
        n = len(f.rooms)
        assert int(mn * 0.7) <= n <= int(mx * 1.1), (
            f"F1 seed={seed} ma {n} pokoi, expected ~{mn}-{mx}")


def test_f18_actual_room_count_in_band():
    """F18 generacja produkuje wiele pokoi (>60)."""
    for seed in (1, 7, 42):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=18, seed=seed)
        n = len(f.rooms)
        assert n >= 60, f"F18 seed={seed} za mało pokoi: {n}"
        # Górny luźny cap z marginesem
        assert n <= 150


def test_boss_count_scales_with_floor_depth():
    """Im głębsze piętro, tym więcej bossów (przez większy rooms count
    i boss_count_for_floor formula). F1 < F18."""
    f1_bosses = []
    f18_bosses = []
    for seed in (1, 7, 42):
        w = _new_world()
        f1 = _fg.generate_floor(w, floor_number=1, seed=seed)
        f1_bosses.append(_br.boss_count_for_floor(len(f1.rooms)))
        w2 = _new_world()
        f18 = _fg.generate_floor(w2, floor_number=18, seed=seed)
        f18_bosses.append(_br.boss_count_for_floor(len(f18.rooms)))
    avg_f1 = sum(f1_bosses) / len(f1_bosses)
    avg_f18 = sum(f18_bosses) / len(f18_bosses)
    assert avg_f18 > avg_f1 * 3, (
        f"F18 boss count nie skaluje się: F1 avg {avg_f1}, "
        f"F18 avg {avg_f18}")


def test_generation_validates_clean_at_deep_floors():
    """F18 musi mieć floor.start + exit + safehouse, jak na każdym
    piętrze. Walidator nie powinien rzucać błędów."""
    for seed in (1, 13, 77):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=18, seed=seed)
        assert f.start_room_id
        assert f.exit_room_ids
        # Co najmniej 1 safehouse
        safes = [r for r in f.rooms.values()
                 if r.safehouse_subtype]
        assert safes, f"F18 seed={seed} brak safehouse"


# ── Performance sanity ─────────────────────────────────────────────


def test_f18_generation_under_three_seconds():
    """F18 (~100 rooms) musi się generować w <3s na typowej maszynie.
    Jeśli zaczyna pęcznieć — czas na profilowanie."""
    w = _new_world()
    t0 = time.perf_counter()
    _fg.generate_floor(w, floor_number=18, seed=12345)
    elapsed = time.perf_counter() - t0
    assert elapsed < 3.0, f"F18 gen za długo: {elapsed:.2f}s"


def test_f1_generation_fast():
    """F1 (~20 rooms) musi być szybkie — <0.5s."""
    w = _new_world()
    t0 = time.perf_counter()
    _fg.generate_floor(w, floor_number=1, seed=1)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"F1 gen za długo: {elapsed:.2f}s"
