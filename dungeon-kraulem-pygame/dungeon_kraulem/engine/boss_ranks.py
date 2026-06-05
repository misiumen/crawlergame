"""P29.57c — System rang bossów (6-tier DCC canon).

DCC chapter 28: "Bossy z okolicy, dzielnicowe, miejskie, prowincjonalne,
krajowe i całego poziomu." Każde piętro ma X bossów z różnych rang,
zawsze 1× boss piętra (= boss całego poziomu) jako main objective.

Per Etap C:
- Każdy boss-entity nosi tag `boss_rank:<rank>` (np. `boss_rank:miejski`)
- Generator wybiera bossy po rank (placement w `floor_generator.py`)
- Drop on kill: każdy rank ma swój Boss Box tier (Etap D handler)

Rangi (od najsłabszej do najsilniejszej):
1. lokalny      → Skrzynka Brązowa
2. dzielnicowy  → Skrzynka Srebrna
3. miejski      → Skrzynka Złota
4. regionalny   → Skrzynka Platynowa
5. krajowy      → Skrzynka Diamentowa
6. boss_pietra  → Skrzynka Niebiańska

Boss piętra rank — zawsze obecny na każdym piętrze (Q-fin-2, 2026-05-28).
HP/dmg skaluje z głębokością, rank reward zawsze cap.
"""
from __future__ import annotations
from typing import Dict, List


# ── Constants ────────────────────────────────────────────────────────


RANK_LOKALNY     = "lokalny"
RANK_DZIELNICOWY = "dzielnicowy"
RANK_MIEJSKI     = "miejski"
RANK_REGIONALNY  = "regionalny"
RANK_KRAJOWY     = "krajowy"
RANK_BOSS_PIETRA = "boss_pietra"

ALL_RANKS = (RANK_LOKALNY, RANK_DZIELNICOWY, RANK_MIEJSKI,
             RANK_REGIONALNY, RANK_KRAJOWY, RANK_BOSS_PIETRA)

MINI_RANKS = (RANK_LOKALNY, RANK_DZIELNICOWY, RANK_MIEJSKI,
              RANK_REGIONALNY, RANK_KRAJOWY)


# ── Display labels (Polish) ──────────────────────────────────────────


_RANK_LABEL_PL: Dict[str, str] = {
    RANK_LOKALNY:     "lokalny",
    RANK_DZIELNICOWY: "dzielnicowy",
    RANK_MIEJSKI:     "miejski",
    RANK_REGIONALNY:  "regionalny",
    RANK_KRAJOWY:     "krajowy",
    RANK_BOSS_PIETRA: "boss piętra",
}


def rank_label_pl(rank: str) -> str:
    return _RANK_LABEL_PL.get(rank, rank)


# ── Order / comparisons ─────────────────────────────────────────────


_RANK_ORDER: Dict[str, int] = {r: i for i, r in enumerate(ALL_RANKS)}


def rank_order(rank: str) -> int:
    """0..5 — wyższe = silniejsze."""
    return _RANK_ORDER.get(rank, 0)


def is_boss_pietra(rank: str) -> bool:
    """True iff rank to boss piętra (single per floor, main objective).
    Exit unlock zależy od TEJ rangi."""
    return rank == RANK_BOSS_PIETRA


# ── Rarity mapping (Boss Box per rank) ──────────────────────────────


_RANK_TO_BOX_RARITY: Dict[str, str] = {
    RANK_LOKALNY:     "common",      # Brązowa
    RANK_DZIELNICOWY: "uncommon",    # Srebrna
    RANK_MIEJSKI:     "rare",        # Złota
    RANK_REGIONALNY:  "epic",        # Platynowa
    RANK_KRAJOWY:     "epic",        # Diamentowa (epic+, intermediate)
    RANK_BOSS_PIETRA: "legendary",   # Niebiańska
}


def box_rarity_for_rank(rank: str) -> str:
    """Mapowanie rang → rarity Boss Box'a. Używane przez Etap D drop
    logic."""
    return _RANK_TO_BOX_RARITY.get(rank, "common")


# 6 distinct Polish tier labels per rank (Diamentowa ≠ Platynowa ≠
# Niebiańska, mimo że rarity może się powielić — krajowy i regionalny
# obie mapują na epic items, ale skrzynki są inne).
_RANK_TO_BOX_TIER_LABEL: Dict[str, str] = {
    RANK_LOKALNY:     "Skrzynka Brązowa",
    RANK_DZIELNICOWY: "Skrzynka Srebrna",
    RANK_MIEJSKI:     "Skrzynka Złota",
    RANK_REGIONALNY:  "Skrzynka Platynowa",
    RANK_KRAJOWY:     "Skrzynka Diamentowa",
    RANK_BOSS_PIETRA: "Skrzynka Niebiańska",
}


def box_tier_label_for_rank(rank: str) -> str:
    """Polski label tier'u skrzyni per rank. 6 unikalnych nazw —
    używane przez make_box(tier_label=...) bo standardowe rarity
    label'e mają tylko 5 pozycji."""
    return _RANK_TO_BOX_TIER_LABEL.get(rank, "Skrzynka Brązowa")


# ── Audience bonus per kill rank (baseline TODO TUNE) ────────────────


_RANK_AUDIENCE_BONUS: Dict[str, int] = {
    RANK_LOKALNY:     5,    # TODO TUNE
    RANK_DZIELNICOWY: 10,
    RANK_MIEJSKI:     20,
    RANK_REGIONALNY:  35,
    RANK_KRAJOWY:     60,
    RANK_BOSS_PIETRA: 100,
}


def audience_bonus_for_kill(rank: str) -> int:
    """Wielkość bonusa widowni po zabiciu bossa tej rangi.
    Używane przez Etap D w hook'u kill path."""
    return _RANK_AUDIENCE_BONUS.get(rank, 0)


# ── Tag helpers ──────────────────────────────────────────────────────


_RANK_TAG_PREFIX = "boss_rank:"


def rank_tag(rank: str) -> str:
    """Zwraca tag identyfikujący rank bossa, np. „boss_rank:miejski"."""
    return f"{_RANK_TAG_PREFIX}{rank}"


def rank_from_entity(entity) -> str:
    """Wyciąga rank z tagów entity. Zwraca pusty string jeśli brak.
    Boss-entity powinien mieć dokładnie 1 tag boss_rank:."""
    if entity is None:
        return ""
    for tag in (entity.tags or []):
        if isinstance(tag, str) and tag.startswith(_RANK_TAG_PREFIX):
            return tag[len(_RANK_TAG_PREFIX):]
    return ""


def is_boss_entity(entity) -> bool:
    """True iff entity ma jakikolwiek boss_rank tag."""
    return bool(rank_from_entity(entity))


# ── Boss count formula per floor size ───────────────────────────────


def boss_count_for_floor(n_rooms: int) -> int:
    """Per-floor total boss count: max(2, rooms // 5).

    Skalowanie: 15 rooms → 3 bossy, 50 rooms → 10 bossy, 100 rooms → 20.
    Zawsze minimum 2 (boss piętra + 1 mini). Działa zarówno na obecnych
    małych piętrach jak i na przyszłych dużych (Etap F, P29.58).
    """
    return max(2, int(n_rooms) // 5)


def mini_boss_count_for_floor(n_rooms: int) -> int:
    """Total - 1 (boss piętra always)."""
    return max(1, boss_count_for_floor(n_rooms) - 1)
