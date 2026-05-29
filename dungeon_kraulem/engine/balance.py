"""P29.65 — czysta funkcja skalowania bojowego wg głębokości piętra.

Bazowe staty mobów żyją autorsko w `MOB_COMBAT_STATS` (entity_templates.py) na
skali wczesnej gry. Ta funkcja dorzuca ŁAGODNY bonus za każde piętro PONIŻEJ
piętra „domowego" moba (floor_min) — żeby ten sam szablon pojawiający się głębiej
był nieco groźniejszy. Kluczowe: mob na swoim piętrze (lub gdy piętro domowe jest
nieznane) = BEZ zmian, więc nie podwajamy autorskiego balansu. To NIE jest ślepy
mnożnik P27.6 — to przejrzysta krzywa głębokości wołana przez buildery przy spawnie.
"""
from __future__ import annotations
from .dice import _parse

_HP_PER_FLOOR = 0.06      # +6% max HP na piętro głębokości
_DMG_BONUS_EVERY = 3      # +1 do stałej obrażeń co 3 piętra głębokości
_MAX_DEPTH = 12           # cap, by reuse na bardzo głębokim piętrze nie eksplodował


def _home_floor_from_tags(ent):
    """Piętro domowe z taga „floor_min:N". Zwraca int albo None (nieznane)."""
    for t in (getattr(ent, "tags", None) or []):
        s = str(t)
        if s.startswith("floor_min:"):
            try:
                return max(1, int(s.split(":", 1)[1]))
            except ValueError:
                return None
    return None


def _bump_dice_bonus(spec, extra):
    """Dokłada `extra` do stałej części „NdS+B". No-op dla gołej liczby/śmieci."""
    parsed = _parse(spec)
    if parsed is None or extra <= 0:
        return spec
    n, sides, bonus = parsed
    if n <= 0 or sides <= 0:
        return spec
    return f"{n}d{sides}+{bonus + extra}"


def scale_for_floor(ent, floor, home_floor=None):
    """Mutuje encję bojową wg głębokości względem jej piętra domowego.

    `home_floor` jawnie z buildera (np. `proto.get("floor_min")`); gdy None —
    próbuje taga „floor_min:N"; gdy nadal nieznane → BEZ skalowania (bezpiecznie).
    No-op też dla nie-potworów (brak max_hp). Zwraca `ent` dla wygody."""
    if ent is None or not getattr(ent, "max_hp", 0):
        return ent
    try:
        floor = int(floor or 1)
    except (TypeError, ValueError):
        return ent
    if home_floor is None:
        home_floor = _home_floor_from_tags(ent)
    if home_floor is None:
        return ent
    try:
        home = max(1, int(home_floor))
    except (TypeError, ValueError):
        return ent
    depth = min(_MAX_DEPTH, max(0, floor - home))
    if depth <= 0:
        return ent
    ratio = (ent.hp / ent.max_hp) if ent.max_hp else 1.0
    ent.max_hp = int(round(ent.max_hp * (1 + _HP_PER_FLOOR * depth)))
    ent.hp = max(1, int(round(ent.max_hp * ratio)))
    extra = depth // _DMG_BONUS_EVERY
    if extra:
        ent.damage_dice = _bump_dice_bonus(ent.damage_dice, extra)
    return ent
