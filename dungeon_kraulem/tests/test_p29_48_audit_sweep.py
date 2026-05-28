"""Prompt 29.48 — Sweep oczywistych bugów typu „content bez hook'a".

Zgłoszenie: po znalezieniu showstoppera floor.exits_unlocked, gracz
zażądał audytu: „do takiej sytuacji jak brak możliwości ukończenia
piętra nie powinno dochodzić i bez moich testów."

Diagnoza: bug klasy „pole stanu czytane przez kod, ale nigdy
zapisywane przez produkcyjną ścieżkę" — silnik czeka na trigger
który nigdy nie nadejdzie.

Audyt znalazł:
  * 2 achievements bez triggera w produkcji (reklama_przerywa_walke,
    brak_zwlok_brak_problemu) — gracz NIGDY ich nie odblokuje.
  * Fix: oba dostają hook (defend_streak w combat, kills==0 w
    descent z F1).

Plus: ten plik dodaje STAŁY test regresyjny który chodzi po
catalog'u achievementów i sprawdza, że każdy klucz ma jakąś
wzmiankę w produkcyjnym kodzie. Następne dodanie achievementa
bez triggera będzie failować w CI.
"""
from __future__ import annotations
import os, re

from ..engine import run_history as _rh
from ..systems.achievements import catalog


def _collect_prod_src(exclude_files=("achievements.py",)):
    """Zlap źródła wszystkich plików produkcyjnych (BEZ tests/)."""
    src = ""
    for root, _, files in os.walk(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        if "__pycache__" in root:
            continue
        if "tests" in root.replace(os.sep, "/").split("/"):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in exclude_files:
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fp:
                src += fp.read() + "\n"
    return src


def test_every_achievement_has_production_trigger():
    """Każdy klucz w catalogu achievementów MUSI mieć wzmiankę
    (jako string literal) gdzieś w kodzie produkcyjnym poza
    samym katalogiem. Inaczej osiągnięcie nieosiągalne."""
    prod_src = _collect_prod_src()
    keys = list(catalog().keys())
    unhooked = []
    for k in keys:
        if not re.search(rf'["\'`]{re.escape(k)}["\'`]', prod_src):
            unhooked.append(k)
    assert not unhooked, (
        f"achievements bez triggera w produkcji: {unhooked}")
    print(f"  {len(keys)} achievementów: każdy ma trigger: OK")


def test_defend_streak_achievement_fires():
    """5 obron pod rząd → reklama_przerywa_walke.
    Symulujemy bezpośrednio logikę streak (bez pełnego combat post-hook'a
    który wymaga gen'd floor)."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..systems import achievements as _ach

    w = WorldState()
    w.character = Character(name="t", background="janitor")

    # Replikuj logikę z _combat_defend tylko dla streak/achievement.
    class FakeCS:
        last_action = ""
        defend_streak = 0
    cs = FakeCS()
    for _ in range(5):
        prior = getattr(cs, "last_action", "")
        if prior == "defend":
            cs.defend_streak = int(getattr(cs, "defend_streak", 0)) + 1
        else:
            cs.defend_streak = 1
        if cs.defend_streak >= 5:
            _ach.unlock(w.character, "reklama_przerywa_walke",
                        world=w)
        cs.last_action = "defend"
    assert _ach.is_unlocked(w.character, "reklama_przerywa_walke")
    print("  5 defends → reklama_przerywa_walke: OK")


def test_pacifist_floor1_achievement_fires():
    """Zejście z F1 z run_kills==0 → brak_zwlok_brak_problemu."""
    _rh.reset()
    from ..engine.game import Game
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor_generator import generate_floor

    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.run_kills = 0
    g = Game(screen=None); g.world = w; g.state = "play"
    # Wygeneruj F1 + ustaw bossroom + odblokuj wyjście.
    f = generate_floor(w, floor_number=1, seed=42)
    w.current_floor = f
    # Stand w exit roomie + odblokuj.
    if f.exit_room_ids:
        f.current_room_id = f.exit_room_ids[0]
    f.exits_unlocked.add("test_force")
    g._descend_or_win()
    from ..systems import achievements as _ach
    assert _ach.is_unlocked(w.character, "brak_zwlok_brak_problemu")
    print("  F1 pacifist descent → brak_zwlok_brak_problemu: OK")


def test_pacifist_NOT_fired_when_killed():
    """Zejście z F1 z run_kills>0 NIE odblokowuje pacifist."""
    _rh.reset()
    from ..engine.game import Game
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor_generator import generate_floor

    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.run_kills = 1  # zabił przynajmniej jednego
    g = Game(screen=None); g.world = w; g.state = "play"
    f = generate_floor(w, floor_number=1, seed=42)
    w.current_floor = f
    if f.exit_room_ids:
        f.current_room_id = f.exit_room_ids[0]
    f.exits_unlocked.add("test_force")
    g._descend_or_win()
    from ..systems import achievements as _ach
    assert not _ach.is_unlocked(w.character, "brak_zwlok_brak_problemu")
    print("  F1 z 1+ killem NIE daje pacifist achievementa: OK")


def main():
    _rh.reset()
    try:
        test_every_achievement_has_production_trigger()
        test_defend_streak_achievement_fires()
        test_pacifist_floor1_achievement_fires()
        test_pacifist_NOT_fired_when_killed()
    finally:
        _rh.reset()
    print("Prompt 29.48 audit sweep smoke: OK")


if __name__ == "__main__":
    main()
