"""P29.58 — Progressive floor size: F1 tutorial → F18 100+ rooms.

Wcześniej (P29 baseline): archetype.min_rooms/max_rooms decydowały —
zawsze 12-20 pokoi niezależnie od piętra. To było daleko od DCC canon:
„Loch jest gigantyczny. Każde piętro głębsze = więcej pokoi, więcej
możliwości się zgubić, więcej miejsc na rzeczy."

Q-fin-3 (user 2026-05-28): docelowo 80-120 pokoi na deep floors,
PROGRESYWNIE — F1 jako intake mniejsze (krzywa nauki), F18 brutalne.

Curve dobrane tak, że:
  * F1     → 18-22  (intake, gracz uczy się sterowania)
  * F2-3   → 22-30  (rozszerzenie)
  * F4-6   → 30-45  (pierwsze duże piętra)
  * F7-10  → 45-65
  * F11-14 → 65-85
  * F15-18 → 85-120 (finałowe sektory)

Boss formula `max(2, rooms // 5)` (P29.57c) skaluje się razem:
  * F1   ≈ 20 rooms → ≈ 4 bossy
  * F10  ≈ 55 rooms → 11 bossy
  * F18  ≈ 100 rooms → 20 bossy
Per user Q-fin (2026-05-28): bez floor cap'u, 20 bossów to feature.
"""
from __future__ import annotations
from typing import Tuple


# (min, max) per piętro. Krzywa progresywna, skok progresji per band.
# Krzywa nie-liniowa, bo dynamika tutoriale → fight-finałowe.
_FLOOR_SIZE_BANDS: Tuple[Tuple[int, int, int, int], ...] = (
    # (floor_lo, floor_hi, min_rooms, max_rooms)
    (1,  1,   18,  22),
    (2,  3,   22,  30),
    (4,  6,   30,  45),
    (7,  10,  45,  65),
    (11, 14,  65,  85),
    (15, 18,  85, 120),
)


def floor_size_for_floor(floor_num: int) -> Tuple[int, int]:
    """Zwraca (min_rooms, max_rooms) dla piętra. Default fallback dla
    piętrów poza zakresem 1-18: jak F18 (cap). Generator losuje
    `random.randint(min, max)` z tego."""
    n = int(floor_num or 1)
    if n < 1:
        n = 1
    for lo, hi, rmin, rmax in _FLOOR_SIZE_BANDS:
        if lo <= n <= hi:
            return (rmin, rmax)
    # > F18 → top band cap
    return _FLOOR_SIZE_BANDS[-1][2:]
