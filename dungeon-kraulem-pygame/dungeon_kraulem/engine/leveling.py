"""P29.76 — System XP + poziomów (DCC-faithful).

DCC (gwiazda polarna): System przyznaje XP za pokonanych, a awans daje +max HP,
punkt atrybutu (gracz rozdaje sam) ORAZ loot box. Ten moduł to jedno źródło:
krzywa XP, XP-za-zabójstwo wg tieru, `award_xp` (obsługa wielu awansów naraz)
i aplikacja nagród. Picker rozdawania punktów + UI żyją w game.py/ui.py (Etap B);
loot box reuse'uje system Skrzynek (engine/handlers/boxes.py).

Decyzje usera (P29.76): awans = +max HP + punkt statu do rozdania + losowa
skrzynka; XP z zabójstw wg tieru (normal/miniboss/boss) + bonus za bossa.
Liczby oznaczone `# TODO TUNE` dostrajane symulacją przejścia pięter.
"""
from __future__ import annotations
import random as _random
from typing import Dict, List


# ── Krzywa XP ───────────────────────────────────────────────────────
def xp_to_reach(level: int) -> int:
    """Kumulatywny próg XP, by OSIĄGNĄĆ dany poziom (L1 = 0). Kwadratowa:
    L2=100, L3=300, L4=600, L5=1000, L10=4500...  # TODO TUNE."""
    if level <= 1:
        return 0
    return 50 * (level - 1) * level


def level_for_xp(xp: int) -> int:
    lvl = 1
    while lvl < 99 and xp >= xp_to_reach(lvl + 1):
        lvl += 1
    return lvl


def xp_into_level(xp: int):
    """(xp zdobyte w obrębie bieżącego poziomu, xp potrzebne do następnego)
    — pod pasek XP w UI."""
    lvl = level_for_xp(xp)
    cur = xp_to_reach(lvl)
    nxt = xp_to_reach(lvl + 1)
    return (max(0, xp - cur), max(1, nxt - cur))


# ── XP za zabójstwo wg tieru ────────────────────────────────────────
_BASE_XP = 20  # normalny mob na F1  # TODO TUNE


def _tier_mult_from_tags(tags) -> float:
    tags = set(tags or [])
    if "floor_boss" in tags or "final_boss" in tags:
        return 10.0
    if "miniboss" in tags or any(str(t).startswith("boss_rank:") for t in tags):
        return 4.0
    return 1.0


def xp_for_kill_tags(tags, floor: int = 1) -> int:
    """Wariant przyjmujący SUROWE tagi — używany w hooku zabójstwa, gdzie
    encja może być już przetworzona w trupa (tagi pre-death w `_tags_pre`)."""
    floor = max(1, int(floor or 1))
    return int(round(_BASE_XP * _tier_mult_from_tags(tags)
                     * (1.0 + 0.10 * (floor - 1))))


def xp_for_kill(entity, floor: int = 1) -> int:
    """XP za zabicie `entity` na danym piętrze: baza × mnożnik tieru ×
    skalowanie piętrem (+10%/piętro)."""
    return xp_for_kill_tags(getattr(entity, "tags", None) or [], floor)


# ── Loot box per poziom ─────────────────────────────────────────────
def box_rarity_for_level(level: int) -> str:
    """Pasmo rarity skrzynki-awansu (Brązowa→Diamentowa).  # TODO TUNE."""
    if level >= 13:
        return "legendary"
    if level >= 10:
        return "epic"
    if level >= 7:
        return "rare"
    if level >= 4:
        return "uncommon"
    return "common"


def roll_levelup_box_contents(rng, level: int, floor: int = 1) -> List[Dict]:
    """Treść skrzynki-awansu: 1-3 itemy (skalowane poziomem) + kredyty.
    Reuse pickera rarity z engine/rarity.py.  # TODO TUNE."""
    contents: List[Dict] = []
    try:
        from .rarity import pick_item_key_for_floor
        n_items = 1 + (1 if level >= 7 else 0) + (1 if level >= 13 else 0)
        for _ in range(n_items):
            contents.append(
                {"item_key": pick_item_key_for_floor(rng, floor), "qty": 1})
    except Exception:
        pass
    contents.append({"item_key": "credits", "qty": 10 + 8 * int(level)})
    return contents


# ── Aplikacja awansu ────────────────────────────────────────────────
def hp_gain_for(character) -> int:
    """Przyrost max HP na poziom: 6 + mod CON (min 4). CON nareszcie ma
    znaczenie (dotąd max_hp było stałe 100).  # TODO TUNE."""
    con_mod = character.stat_mod("CON") if hasattr(character, "stat_mod") else 0
    return max(4, 6 + int(con_mod))


def apply_level_up(world, new_level: int, *, rng=None) -> None:
    """Nadaje nagrody za pojedynczy awans: +max HP (+heal), +1 punkt statu
    do rozdania, loot box, log „AWANS!". Defensywne — nigdy nie wywala gry."""
    ch = getattr(world, "character", None)
    if ch is None:
        return
    rng = rng or _random.Random()
    # +max HP + heal-on-level (DCC).
    gain = hp_gain_for(ch)
    ch.max_hp = int(ch.max_hp) + gain
    ch.hp = min(ch.max_hp, int(ch.hp) + gain)
    # +1 nierozdany punkt atrybutu (rozdaje gracz — picker Etap B).
    ch.unspent_stat_points = int(getattr(ch, "unspent_stat_points", 0) or 0) + 1
    # Loot box (system Skrzynek — ląduje w EQ, otwierane manualnie).
    try:
        from .handlers import boxes as _boxes
        floor = int(getattr(getattr(world, "current_floor", None),
                            "floor_number", 1) or 1)
        _boxes.make_box(
            world, source="level_up", source_name=f"Poziom {new_level}",
            contents=roll_levelup_box_contents(rng, new_level, floor),
            rarity=box_rarity_for_level(new_level))
    except Exception:
        pass
    # Log (głos Systemu, zielony).
    try:
        world.log_msg(
            f"AWANS! Poziom {new_level}. +{gain} max HP, punkt atrybutu do "
            f"rozdania, skrzynka czeka w tabie Skrzynki.", "success")
    except Exception:
        pass


def pre_level(world, target_level: int) -> None:
    """Ustawia postać na dany poziom BEZ log-spamu „AWANS" — do testbedów
    (np. start areny). Kumulatywne +max HP, +punkty do rozdania, ustawia
    `level`, i daje JEDNĄ skrzynkę demonstracyjną (do przetestowania reveala).
    Nie służy balansowi — daje dostęp do mechanik progresji od ręki."""
    ch = getattr(world, "character", None)
    lvl = int(target_level or 1)
    if ch is None or lvl <= 1:
        return
    gain = sum(hp_gain_for(ch) for _ in range(lvl - 1))
    ch.max_hp = int(ch.max_hp) + gain
    ch.hp = ch.max_hp
    ch.level = lvl
    ch.unspent_stat_points = int(getattr(ch, "unspent_stat_points", 0) or 0) + (lvl - 1)
    try:
        from .handlers import boxes as _boxes
        # Use an UNSEEDED rng — seeding with `lvl` made the arena testbed
        # box deterministic, so the same level always rolled the identical
        # reward (the "cleaver handle every time" bug). The box should be a
        # fresh roll each run.
        _boxes.make_box(
            world, source="level_up", source_name="Trening areny",
            contents=roll_levelup_box_contents(_random.Random(), lvl, 1),
            rarity=box_rarity_for_level(lvl))
    except Exception:
        pass


def award_xp(world, amount: int, *, reason: str = "kill", rng=None) -> List[int]:
    """Dolicza XP graczowi; obsługuje WIELE awansów naraz (np. boss daje
    duży skok). Zwraca listę nowo osiągniętych poziomów (pusta gdy brak)."""
    ch = getattr(world, "character", None)
    if world is None or ch is None or int(amount) <= 0:
        return []
    old_level = int(getattr(ch, "level", 1) or 1)
    ch.xp = int(getattr(ch, "xp", 0) or 0) + int(amount)
    new_level = level_for_xp(ch.xp)
    gained: List[int] = []
    if new_level > old_level:
        for lvl in range(old_level + 1, new_level + 1):
            ch.level = lvl
            apply_level_up(world, lvl, rng=rng)
            gained.append(lvl)
    return gained
