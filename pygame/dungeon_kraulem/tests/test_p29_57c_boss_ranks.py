"""P29.57c — Boss rank system + multi-boss per piętro placement.

Pokrywa:
* boss_ranks module — labels / order / box rarity / audience bonus / tags
* Formula: max(2, rooms // 5) total, mini = total - 1 (≥1)
* Floor boss zawsze dostaje tag `boss_rank:boss_pietra`
* Mini bossy dostają LOSOWĄ rangę z MINI_RANKS (no floor cap)
* Per piętro: dokładnie 1 boss_pietra + ≥1 mini z mieszanych rang
* Exit unlock zależy od TYLKO boss_pietra rangi (przez floor_boss tag,
  juz pokryte P29.57a)
"""
from __future__ import annotations
import random

from ..engine import boss_ranks as _br
from ..engine import floor_generator as _fg
from ..engine.world import WorldState
from ..engine.character import Character


# ── Module API ───────────────────────────────────────────────────────


def test_all_ranks_have_labels_pl():
    """Wszystkie 6 rang ma polski label."""
    for rank in _br.ALL_RANKS:
        label = _br.rank_label_pl(rank)
        assert label, f"brak labela dla rangi {rank}"
        # Polish-only sanity: no english common words
        for bad in ("rank", "tier", "city", "local"):
            assert bad not in label.lower(), (
                f'angielskie słowo {bad!r} w label rangi {rank}: {label!r}')


def test_rank_order_strictly_increasing():
    """0..5, boss piętra najwyższa."""
    orders = [_br.rank_order(r) for r in _br.ALL_RANKS]
    assert orders == list(range(len(_br.ALL_RANKS)))
    assert _br.rank_order(_br.RANK_BOSS_PIETRA) > \
        _br.rank_order(_br.RANK_KRAJOWY)


def test_box_rarity_mapping_per_rank():
    """Mapowanie rang → rarity skrzynki (Etap D drop logic)."""
    assert _br.box_rarity_for_rank(_br.RANK_LOKALNY)     == "common"
    assert _br.box_rarity_for_rank(_br.RANK_DZIELNICOWY) == "uncommon"
    assert _br.box_rarity_for_rank(_br.RANK_MIEJSKI)     == "rare"
    assert _br.box_rarity_for_rank(_br.RANK_REGIONALNY)  == "epic"
    assert _br.box_rarity_for_rank(_br.RANK_KRAJOWY)     == "epic"
    assert _br.box_rarity_for_rank(_br.RANK_BOSS_PIETRA) == "legendary"


def test_audience_bonus_strictly_increasing():
    """Im wyższa ranga, tym większy bonus widowni."""
    bonuses = [_br.audience_bonus_for_kill(r) for r in _br.ALL_RANKS]
    assert bonuses == sorted(bonuses)
    assert bonuses[0] > 0
    assert _br.audience_bonus_for_kill(_br.RANK_BOSS_PIETRA) >= 100


def test_rank_tag_helper_roundtrip():
    """rank_tag → rank_from_entity zwraca to samo."""
    class _Stub:
        tags = [_br.rank_tag(_br.RANK_MIEJSKI), "monster"]

    assert _br.rank_from_entity(_Stub()) == _br.RANK_MIEJSKI
    assert _br.is_boss_entity(_Stub()) is True


def test_no_rank_tag_returns_empty():
    class _Stub:
        tags = ["monster", "humanoid"]

    assert _br.rank_from_entity(_Stub()) == ""
    assert _br.is_boss_entity(_Stub()) is False


def test_is_boss_pietra_only_for_boss_pietra():
    assert _br.is_boss_pietra(_br.RANK_BOSS_PIETRA) is True
    for r in _br.MINI_RANKS:
        assert _br.is_boss_pietra(r) is False


# ── Boss count formula ──────────────────────────────────────────────


def test_boss_count_scales_with_rooms():
    """max(2, rooms // 5). Działa na obecnych 12-20 i przyszłych 80-120."""
    assert _br.boss_count_for_floor(0)   == 2   # floor
    assert _br.boss_count_for_floor(5)   == 2
    assert _br.boss_count_for_floor(10)  == 2
    assert _br.boss_count_for_floor(15)  == 3
    assert _br.boss_count_for_floor(20)  == 4
    assert _br.boss_count_for_floor(50)  == 10
    assert _br.boss_count_for_floor(100) == 20
    assert _br.boss_count_for_floor(120) == 24


def test_mini_count_is_total_minus_one():
    for rooms in (5, 12, 20, 50, 100):
        assert _br.mini_boss_count_for_floor(rooms) == \
            _br.boss_count_for_floor(rooms) - 1


def test_mini_count_floor_at_one():
    """Min 1 mini boss zawsze, nawet jeśli total = 2."""
    assert _br.mini_boss_count_for_floor(5) >= 1
    assert _br.mini_boss_count_for_floor(0) >= 1


# ── Floor generator integration ──────────────────────────────────────


def _new_world():
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    return w


def _bosses_by_rank(floor):
    """Mapuje rank → lista (room_id, entity_key) na piętrze."""
    out = {}
    for room in floor.rooms.values():
        for ent in room.entities:
            r = _br.rank_from_entity(ent)
            if r:
                out.setdefault(r, []).append((room.room_id, ent.key))
    return out


def test_floor_boss_tagged_boss_pietra():
    """Każde piętro ma DOKŁADNIE 1 entity z rangą `boss_pietra`."""
    for seed in (1, 2, 7, 42, 99):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=1, seed=seed)
        per_rank = _bosses_by_rank(f)
        bps = per_rank.get(_br.RANK_BOSS_PIETRA, [])
        assert len(bps) == 1, (
            f"F1 seed={seed} nie ma dokładnie 1 bossa piętra: {bps}")


def test_each_floor_has_at_least_one_miniboss():
    """P29.57c: F1-2 NIE są już intake-only — min 1 mini boss."""
    for fnum in (1, 2, 3):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=fnum, seed=42)
        per_rank = _bosses_by_rank(f)
        mini_count = sum(len(v) for r, v in per_rank.items()
                         if r in _br.MINI_RANKS)
        assert mini_count >= 1, (
            f"F{fnum} bez mini bossa: ranks={list(per_rank.keys())}")


def test_mini_bossy_drawn_from_mini_ranks():
    """Mini bossy mają rangi z MINI_RANKS (nigdy boss_pietra)."""
    for seed in (1, 11, 222):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=5, seed=seed)
        per_rank = _bosses_by_rank(f)
        # Drop bossa piętra z analizy
        for r in per_rank:
            if r == _br.RANK_BOSS_PIETRA:
                continue
            assert r in _br.MINI_RANKS, (
                f"mini boss z rangi spoza MINI_RANKS: {r}")


def test_mini_ranks_can_mix_on_same_floor():
    """Per design: rang losowany OSOBNO per boss. W 5 seedach
    powinniśmy zobaczyć ≥2 różne rangi mini-bossów (statystyka)."""
    seen_ranks = set()
    for seed in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=5, seed=seed)
        per_rank = _bosses_by_rank(f)
        for r in per_rank:
            if r in _br.MINI_RANKS:
                seen_ranks.add(r)
    assert len(seen_ranks) >= 2, (
        f"mini boss rang nie waria w 10 seedach (Q-fin-1 bez cap): "
        f"{seen_ranks}")


def test_no_floor_cap_on_mini_ranks():
    """Q-fin-1: F1 może dostać LOSOWĄ rangę mini bossa, nie tylko
    lokalną. Przy >=10 seedach na F1 powinniśmy zobaczyć ≥2 różne
    rangi."""
    seen_on_f1 = set()
    for seed in range(1, 21):
        w = _new_world()
        f = _fg.generate_floor(w, floor_number=1, seed=seed)
        per_rank = _bosses_by_rank(f)
        for r in per_rank:
            if r in _br.MINI_RANKS:
                seen_on_f1.add(r)
    assert len(seen_on_f1) >= 2, (
        f"F1 dostaje tylko 1 rangę mini (cap'owane?): {seen_on_f1}")
