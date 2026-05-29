"""P29.65 — współdzielony roller kości (JEDNO źródło dla gracza i mobów).

Obsługuje 'NdS', 'NdS+B', 'NdS-B' oraz gołą liczbę 'N'. Odporny na śmieci:
przy niesparsowalnym wejściu zwraca część stałą (lub 0).

Tło: parsowanie kości żyło wcześniej w DWÓCH miejscach, każde popsute inaczej:
  * game._roll_dice_spec — dzielił tylko po '+', więc 'NdS-B' cicho zerowało;
  * combat._enemy_attack_damage — dzielił po 'd' i robił int(sides) na '8+13',
    co rzucało wyjątek i fallbackowało do 1d4 → KAŻDY skalowany mob bił jak 1d4.
Ta rozbieżność rozmontowała balans walki. Teraz oba tory wołają `roll_spec`.
"""
from __future__ import annotations
import re as _re

_DICE_RE = _re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def _parse(spec):
    """Zwraca (n, sides, bonus) albo None gdy to nie kość.
    Goła liczba 'N' → (0, 0, N) (sygnał: brak kości, sama stała)."""
    if spec is None:
        return None
    s = str(spec).strip().lower().replace(" ", "")
    if not s:
        return None
    if s.lstrip("+-").isdigit():
        return (0, 0, int(s))
    m = _DICE_RE.match(s)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def roll_spec(spec, rng) -> int:
    """Rzuca 'NdS±B' / 'N'. Niesparsowalne → 0. Wynik nie schodzi poniżej 0
    (callerzy zwykle nakładają własne max(1, ...) na finalne obrażenia)."""
    parsed = _parse(spec)
    if parsed is None:
        return 0
    n, sides, bonus = parsed
    if n <= 0 or sides <= 0:
        return max(0, bonus)
    total = sum(rng.randint(1, sides) for _ in range(n)) + bonus
    return max(0, total)


def avg_spec(spec) -> float:
    """Średnia wartość rzutu — do symulacji balansu, strojenia i testów
    monotoniczności (np. „broń wg rarity rośnie", „pięść najsłabsza")."""
    parsed = _parse(spec)
    if parsed is None:
        return 0.0
    n, sides, bonus = parsed
    if n <= 0 or sides <= 0:
        return float(max(0, bonus))
    return n * (sides + 1) / 2.0 + bonus
