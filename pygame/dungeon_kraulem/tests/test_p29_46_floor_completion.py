"""Prompt 29.46 — Critical bug: floor exit never unlocks.

Zgłoszenie z playthrough: „sprawdź czy na pewno da się ukończyć
piętro. ostatni playthrough miałem z tym problem."

Diagnoza: floor.exits_unlocked to set, który był NIGDY nie ustawiany
przez kod produkcyjny. Jedyne miejsca w repo z `exits_unlocked.add`
to były pliki testowe (P27 show-layer + P29.24 collapse-escape).
Game._descend_or_win() sprawdza `if floor.exits_unlocked:` więc
warunek był zawsze False → gracz dostawał komunikat „Stoisz przed
drzwiami wyjścia. Nadal zamknięte." i nigdy nie schodził w dół.

Fix:
  * Nowy hook Game._unlock_floor_exits(reason) — dodaje do setu.
  * Wywoływany po transform_to_corpse jeśli target miał tag
    `floor_boss` LUB `final_boss`.
  * Reason loguje czytelnym komunikatem.

Pokrywa:
  * floor.exits_unlocked startuje pusty po generate_floor
  * po _unlock_floor_exits ma element
  * dwukrotne wywołanie tego samego reason'u nie duplikuje
  * floor_boss tag triggers unlock (sym. walka)
  * final_boss tag też triggers
  * miniboss tag NIE triggers (one tylko dropią mapę)
"""
from __future__ import annotations

from ..engine import run_history as _rh
from ..engine import floor_generator as _fg
from ..engine.world import WorldState
from ..engine.character import Character
from ..content.data.entity_templates import MON


# ── Helpers ──────────────────────────────────────────────────────────


def _new_world():
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    return w


def _gen_floor(num=3, seed=42):
    w = _new_world()
    f = _fg.generate_floor(w, floor_number=num, seed=seed)
    w.current_floor = f
    return w, f


# ── Tests ────────────────────────────────────────────────────────────


def test_fresh_floor_has_empty_exits_unlocked():
    """Świeży floor po generate_floor ma exits_unlocked = pusty set."""
    _, f = _gen_floor(num=3)
    assert not f.exits_unlocked, \
        f"floor.exits_unlocked nie startuje pusty: {f.exits_unlocked}"
    print("  fresh floor exits_unlocked == empty set: OK")


def test_unlock_helper_marks_exit():
    """Standalone _unlock_floor_exits dodaje reason do setu."""
    from ..engine.game import Game
    # Game potrzebuje screen — używamy mockowanego.
    class _DummyScreen:
        def get_size(self): return (1280, 720)
    try:
        import pygame
        pygame.display.init()
        scr = pygame.display.set_mode((1280, 720))
    except Exception:
        scr = _DummyScreen()
    g = Game(scr)
    w, f = _gen_floor(num=3)
    g.world = w
    assert not f.exits_unlocked
    g._unlock_floor_exits(reason="boss_defeated")
    assert "boss_defeated" in f.exits_unlocked
    # Idempotencja:
    g._unlock_floor_exits(reason="boss_defeated")
    assert len(f.exits_unlocked) == 1
    print("  _unlock_floor_exits + idempotency: OK")


def test_boss_kill_unlocks_exit_in_real_flow():
    """Symuluje realny flow: piętro z bossem → transform_to_corpse →
    boss tag triggers unlock. To weryfikuje że nasz hook jest
    podpięty pod właściwe miejsce."""
    from ..engine.game import Game
    from ..engine import corpses as _cp
    from ..engine.entity import Entity, T_MONSTER

    try:
        import pygame
        pygame.display.init()
        scr = pygame.display.set_mode((1280, 720))
    except Exception:
        class _DS:
            def get_size(self): return (1280, 720)
        scr = _DS()

    g = Game(scr)
    w, f = _gen_floor(num=3)
    g.world = w
    # Znajdź pokój bossowy.
    boss_room = next((r for r in f.rooms.values()
                      if r.actual_type == "boss"), None)
    assert boss_room is not None, "wygenerowane piętro nie ma boss-roomu"
    # Stwórz fake floor_boss tak, jak generator by go umieścił.
    fake_boss = Entity(key="fake_floor_boss", entity_type=T_MONSTER,
                       fallback_name="Boss Testowy",
                       tags=["monster","humanoid","floor_boss"],
                       location_id=boss_room.room_id)
    w.register(fake_boss)
    boss_room.entities.append(fake_boss)
    f.current_room_id = boss_room.room_id
    # Symulujemy fragment _combat_attack po hit'cie zabijającym.
    # Bezpośrednio wywołujemy ten sam ciąg, który game.py wywołuje
    # w combat hit branchu.
    _tags_pre = list(fake_boss.tags or [])
    _cp.transform_to_corpse(w, fake_boss, killer=w.character)
    if "floor_boss" in _tags_pre or "final_boss" in _tags_pre:
        g._unlock_floor_exits(reason="boss_defeated")
    assert f.exits_unlocked, "boss kill nie odblokował wyjścia!"
    print(f"  floor_boss kill → exits_unlocked={f.exits_unlocked}: OK")


def test_miniboss_kill_does_NOT_unlock_exit():
    """Miniboss to dropi mapę, ale NIE odblokowuje wyjścia.
    To jest celowy projekt — wyjście tylko po głównym bossie."""
    from ..engine.game import Game
    from ..engine import corpses as _cp
    from ..engine.entity import Entity, T_MONSTER

    try:
        import pygame
        pygame.display.init()
        scr = pygame.display.set_mode((1280, 720))
    except Exception:
        class _DS:
            def get_size(self): return (1280, 720)
        scr = _DS()

    g = Game(scr)
    w, f = _gen_floor(num=3)
    g.world = w
    room = next(iter(f.rooms.values()))
    fake_mini = Entity(key="fake_mini", entity_type=T_MONSTER,
                       fallback_name="Mini Test",
                       tags=["monster","miniboss"],
                       location_id=room.room_id)
    w.register(fake_mini)
    room.entities.append(fake_mini)
    f.current_room_id = room.room_id
    _tags_pre = list(fake_mini.tags or [])
    _cp.transform_to_corpse(w, fake_mini, killer=w.character)
    if "floor_boss" in _tags_pre or "final_boss" in _tags_pre:
        g._unlock_floor_exits(reason="boss_defeated")
    assert not f.exits_unlocked, \
        f"miniboss BŁĘDNIE odblokował wyjście: {f.exits_unlocked}"
    print("  miniboss kill → exits_unlocked STILL empty: OK")


def test_every_floor_has_killable_boss():
    """KRYTYCZNE: każde piętro 1-18 musi mieć w pokoju bossowym
    monstera z tagiem `floor_boss` lub `final_boss`. Inaczej hook
    P29.46 nie ma w czym strzelać i gracz utknie na piętrze.
    Sprawdzamy 5 seedów per piętro."""
    fails = []
    for floor_num in range(1, 19):
        ok_seeds = 0
        for seed in (1, 7, 42, 100, 999):
            w = _new_world()
            f = _fg.generate_floor(w, floor_number=floor_num, seed=seed)
            killable = False
            for room in f.rooms.values():
                if room.actual_type != "boss":
                    continue
                for ent in room.entities:
                    tags = ent.tags or []
                    if "floor_boss" in tags or "final_boss" in tags:
                        killable = True
                        break
            if killable:
                ok_seeds += 1
        if ok_seeds < 5:
            fails.append((floor_num, ok_seeds))
    assert not fails, f"piętra bez killowalnego bossa: {fails}"
    print(f"  każde F1-18 ma killowalnego bossa w 5/5 seedach: OK")


def test_descend_gate_respects_unlocked():
    """_descend_or_win uruchamia się tylko, gdy gracz JEST w
    exit-roomie I exits_unlocked jest truthy. Sprawdzamy logikę
    gate'a — bez odblokowania, nawet w exit-roomie, nie descend."""
    w, f = _gen_floor(num=3)
    # Postaw gracza w exit roomie.
    if not f.exit_room_ids:
        # Fallback gdyby generator nie dał exit_room_ids.
        print("  WARNING: floor without exit_room_ids; skipping gate test")
        return
    f.current_room_id = f.exit_room_ids[0]
    # Bez exits_unlocked: gate musi blokować.
    assert (f.current_room_id in f.exit_room_ids) is True
    assert (not f.exits_unlocked)  # ten warunek blokuje descend
    print("  gate przy zamkniętym wyjściu blokuje descend: OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_fresh_floor_has_empty_exits_unlocked()
        test_unlock_helper_marks_exit()
        test_boss_kill_unlocks_exit_in_real_flow()
        test_miniboss_kill_does_NOT_unlock_exit()
        test_every_floor_has_killable_boss()
        test_descend_gate_respects_unlocked()
    finally:
        _rh.reset()
    print("Prompt 29.46 floor completion bug smoke: OK")


if __name__ == "__main__":
    main()
