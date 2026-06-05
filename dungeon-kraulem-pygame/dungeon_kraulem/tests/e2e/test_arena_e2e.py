"""E2E dla P29.60 Arena testowa — combat-only sandbox.

User: 'wydzielić wersję gry gdzie BĘDZIE TYLKO WALKA.'

MVP scope (ten plik):
- 1 wariant 'duel_1v1' (1 mob, fixed default loadout)
- Arena world setup
- Combat dispatch przez Game
- Win detection (mob dead → state → ARENA_MENU)
- Loss detection (player dead → state → ARENA_MENU)

Rule 12b — testy capturują full flow user-facing.
"""
from __future__ import annotations
import os

# Headless pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import arena as _arena
from ...engine.game import (
    Game, STATE_PLAY, STATE_ARENA_MENU, STATE_ARENA_PLAY,
)


# ── Arena variants catalog ──────────────────────────────────────────


def test_variants_in_catalog():
    """P29.75c — 5 wariantów (doszedł miniboss_sortownia: trójka Sortowni
    = duel_1v1/miniboss_sortownia/boss_fight + triple_threat/trap_room)."""
    keys = {v.key for v in _arena.all_variants()}
    assert keys == {"duel_1v1", "miniboss_sortownia", "boss_fight",
                    "triple_threat", "trap_room"}


def test_all_variants_enabled():
    """Wszystkie warianty enabled."""
    enabled = {v.key for v in _arena.all_variants() if v.enabled}
    assert enabled == {"duel_1v1", "miniboss_sortownia", "boss_fight",
                       "triple_threat", "trap_room"}


def test_variant_labels_are_polish():
    """Labels Polish-only."""
    BAD = (" the ", "duel", "fight", "boss room", "trap room")
    for v in _arena.all_variants():
        low = v.label_pl.lower() + " " + v.description_pl.lower()
        for bad in BAD:
            assert bad not in low, (
                f"variant {v.key} ma angielski {bad!r}: {v.label_pl}")


# ── build_arena_world ───────────────────────────────────────────────


def test_build_arena_world_for_duel_spawns_mob():
    """P29.75c — duel_1v1 → wróg Sortowni: Rzeźnik z Zamrażarki."""
    w, floor = _arena.build_arena_world("duel_1v1")
    room = floor.rooms["arena_room"]
    mob_names = [e.fallback_name for e in room.entities]
    assert "Rzeźnik z Zamrażarki" in mob_names


def test_build_arena_world_marks_arena_flag():
    """Arena world ma flag żeby Game wiedział że to test mode."""
    w, _f = _arena.build_arena_world("duel_1v1")
    assert w.flags.get("arena_mode") is True
    assert w.flags.get("arena_variant") == "duel_1v1"


def test_build_arena_unknown_variant_raises():
    import pytest
    with pytest.raises(ValueError):
        _arena.build_arena_world("nieistniejący")


def test_triple_threat_spawns_3_mobs_different_factions():
    """triple_threat: 3 moby — szczur (beast), kapitan (liga), rzeźnik."""
    w, floor = _arena.build_arena_world("triple_threat")
    room = floor.rooms["arena_room"]
    assert len(room.entities) >= 3
    names = [e.fallback_name for e in room.entities]
    assert any("Szczurek" in n for n in names)
    assert any("Kapitan" in n for n in names)


def test_boss_fight_spawns_boss():
    """boss_fight: spawnuje Strażnika Bramy (intake floor boss)."""
    w, floor = _arena.build_arena_world("boss_fight")
    room = floor.rooms["arena_room"]
    names = [e.fallback_name for e in room.entities]
    assert any("Strażnik" in n for n in names)


def test_trap_room_spawns_traps_and_mob():
    """trap_room: mob + 3 hazards (kałuża kwasu, zwarcie, rura pary)."""
    from ...engine.entity import T_HAZARD, T_MONSTER
    w, floor = _arena.build_arena_world("trap_room")
    room = floor.rooms["arena_room"]
    mobs = [e for e in room.entities if e.entity_type == T_MONSTER]
    traps = [e for e in room.entities if e.entity_type == T_HAZARD]
    assert len(mobs) >= 1, "trap_room: brak moba"
    assert len(traps) >= 2, f"trap_room: za mało pułapek ({len(traps)})"


def test_arena_is_won_after_killing_all_mobs():
    w, floor = _arena.build_arena_world("duel_1v1")
    room = floor.rooms["arena_room"]
    assert _arena.arena_is_won(w) is False
    for e in room.entities:
        e.hp = 0
    assert _arena.arena_is_won(w) is True


def test_arena_is_lost_after_player_dies():
    w, _f = _arena.build_arena_world("duel_1v1")
    assert _arena.arena_is_lost(w) is False
    w.character.hp = 0
    assert _arena.arena_is_lost(w) is True


# ── Game integration ────────────────────────────────────────────────


def test_game_start_arena_variant_transitions_to_arena_play():
    """Game.start_arena_variant('duel_1v1') → STATE_ARENA_PLAY,
    world set, mob obecny."""
    game = Game(screen=None)
    ok = game.start_arena_variant("duel_1v1")
    assert ok is True
    assert game.state == STATE_ARENA_PLAY
    assert game.world is not None
    assert game.world.flags.get("arena_mode") is True

    room = game.world.current_floor.current_room()
    # P29.75c — duel_1v1 spawnuje moba Sortowni (wróg = Rzeźnik z Zamrażarki).
    from ...engine.entity import T_MONSTER
    assert any(e.entity_type == T_MONSTER for e in room.entities)


def test_game_start_unknown_variant_returns_false():
    """Unknown variant key — error, not crash."""
    game = Game(screen=None)
    ok_setup = game.start_arena_variant("duel_1v1")
    assert ok_setup

    ok = game.start_arena_variant("nieistniejacy_xyz")
    assert ok is False


def test_game_open_arena_menu_resets_world_to_none():
    game = Game(screen=None)
    game.start_arena_variant("duel_1v1")
    assert game.world is not None

    game.open_arena_menu()
    assert game.state == STATE_ARENA_MENU
    assert game.world is None


# ── E2E: arena win/loss routes back to menu ─────────────────────────


def test_player_killing_mob_in_arena_returns_to_menu():
    """Symuluj kill mob → check_arena_end → state ARENA_MENU."""
    game = Game(screen=None)
    game.start_arena_variant("duel_1v1")
    assert game.state == STATE_ARENA_PLAY

    # Kill mob bezpośrednio (skip combat roll)
    room = game.world.current_floor.current_room()
    for e in room.entities:
        e.hp = 0

    # _check_arena_end normally called from _handle_play_input
    # post-dispatch. Wywołujemy bezpośrednio dla testu.
    game._check_arena_end()
    assert game.state == STATE_ARENA_MENU


def test_player_dying_in_arena_returns_to_menu():
    game = Game(screen=None)
    game.start_arena_variant("duel_1v1")
    assert game.state == STATE_ARENA_PLAY

    game.world.character.hp = 0
    game._check_arena_end()
    assert game.state == STATE_ARENA_MENU


# ── E2E z HeadlessSession-style flow ────────────────────────────────


def test_arena_player_can_attack_szczurek_via_command():
    """Real flow: start arena, wpisz 'zaatakuj szczurek', powinno
    odpalić combat (nawet jeśli nie zabija od razu)."""
    game = Game(screen=None)
    game.start_arena_variant("duel_1v1")

    pre_logs = len(game.world.log)
    game.input_text = "zaatakuj szczurek"
    game.submit_input()

    new_logs = [t for t, _ in game.world.log[pre_logs:]]
    joined = "\n".join(new_logs)

    # Should have triggered SOMETHING — combat start, attack roll
    # Albo state przeszedł w ARENA_MENU (jednokeł kill)
    assert (len(new_logs) > 0 and (
        "atak" in joined.lower() or
        "walka" in joined.lower() or
        game.state == STATE_ARENA_MENU
    )), (
        f"komenda nie wywołała żadnego combat-y log/state change.\n"
        f"State: {game.state}, logs: {new_logs!r}")


# ── E2E: Title → arena menu → loadout → arena ─────────────────────


def test_title_to_arena_menu_via_callback():
    """Symuluje click 'Arena testowa' z title menu."""
    from ...engine.game import STATE_TITLE
    game = Game(screen=None)
    assert game.state == STATE_TITLE

    game._title_action("arena_menu")
    assert game.state == STATE_ARENA_MENU


def test_arena_menu_pick_variant_opens_loadout():
    """Wybór wariantu z arena menu otwiera loadout picker."""
    from ...engine.game import STATE_ARENA_LOADOUT
    game = Game(screen=None)
    game.open_arena_menu()

    game._arena_pick_variant("duel_1v1")
    assert game.state == STATE_ARENA_LOADOUT
    assert game._pending_arena_variant == "duel_1v1"
    assert game.arena_loadout_step == "weapon"


def test_arena_loadout_full_flow_starts_arena():
    """Pełna ścieżka: arena menu → wybór wariantu → weapon →
    class → STATE_ARENA_PLAY."""
    from ...engine.game import (
        STATE_ARENA_LOADOUT, ARENA_WEAPONS, ARENA_CLASSES,
    )
    game = Game(screen=None)
    game.open_arena_menu()
    game._arena_pick_variant("duel_1v1")
    assert game.state == STATE_ARENA_LOADOUT

    # Step 1: wybór broni
    game._arena_loadout_pick("weapon", ARENA_WEAPONS[0][0])
    assert game.arena_loadout_step == "class"
    assert game.arena_loadout.get("weapon") == ARENA_WEAPONS[0][0]

    # Step 2: wybór klasy → start arena
    game._arena_loadout_pick("class", ARENA_CLASSES[0][0])
    assert game.state == STATE_ARENA_PLAY
    assert game.world is not None
    # Weapon zapisany w flags
    assert (game.world.character.flags.get("arena_starting_weapon")
            == ARENA_WEAPONS[0][0])


def test_arena_back_to_title_from_menu():
    """Z arena menu Esc → STATE_TITLE."""
    from ...engine.game import STATE_TITLE
    game = Game(screen=None)
    game.open_arena_menu()
    game._arena_back_to_title()
    assert game.state == STATE_TITLE


def test_arena_back_to_menu_from_loadout():
    """Z arena loadout Esc → STATE_ARENA_MENU."""
    game = Game(screen=None)
    game.open_arena_menu()
    game._arena_pick_variant("duel_1v1")
    game._arena_back_to_menu()
    assert game.state == STATE_ARENA_MENU
    assert game._pending_arena_variant is None


def test_all_variants_have_polish_loadout_content():
    """Loadout pickers Polish-only. Reguła 1 (Polish-only) + Reguła 8
    (calques). Włącza English stat names (STR/DEX/CON/WIS) — w polskiej
    grze MUSI być SIŁ/ZRĘ/KON/MDR. Plus stage'owane angielskie:
    'damage', 'hack', 'stats', 'rifle'."""
    from ...engine.game import ARENA_WEAPONS, ARENA_CLASSES
    BAD = (" the ", " your ", "weapon", "class", "rifle",
           # P29.60 hotfix: stat names w PL
           " str", " dex", " con", " wis",
           # P29.60 hotfix: angielskie technical terms
           "damage", "hack", " stats")
    for key, label, desc in ARENA_WEAPONS + ARENA_CLASSES:
        text = (" " + label + " " + desc + " ").lower()
        for bad in BAD:
            assert bad not in text, (
                f"loadout {key} ma angielski {bad!r}: "
                f"{label} / {desc}")


# ── Render smoke tests — Rule 12d gap close ──────────────────────────
#
# User natknął się na crash gry przy wejściu do arena menu — moje E2E
# testowały LOGIKĘ (state transitions, world setup) ale NIE renderingu
# (draw_arena_menu wołało nieistniejący kwarg). Te smoke testy wołają
# faktyczne `Game.draw()` żeby wyłapać API mismatch.


def _render_smoke(setup_callback):
    """Helper: tworzy headless Game z screen, woła setup_callback,
    potem draw(). Zwraca True jeśli draw nie crashuje."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    screen = pygame.display.set_mode((1280, 800))
    g = Game(screen=screen)
    setup_callback(g)
    g.draw()  # raises if anything wrong z render path
    return True


def test_render_state_arena_menu_doesnt_crash():
    """`Game.draw()` w STATE_ARENA_MENU musi nie crashować — user-facing
    flow z title menu '[3] ARENA TESTOWA'."""
    _render_smoke(lambda g: g.open_arena_menu())


def test_render_state_arena_loadout_doesnt_crash():
    """`Game.draw()` w STATE_ARENA_LOADOUT po wybraniu wariantu."""
    def _setup(g):
        g.open_arena_menu()
        g._arena_pick_variant("duel_1v1")
    _render_smoke(_setup)


def test_render_state_arena_play_doesnt_crash():
    """`Game.draw()` w STATE_ARENA_PLAY — reuses STATE_PLAY rendering."""
    _render_smoke(lambda g: g.start_arena_variant("duel_1v1"))


def test_render_all_4_variants_in_arena_play():
    """Każdy z 4 wariantów renderuje się bez crasha w STATE_ARENA_PLAY."""
    for variant_key in ("duel_1v1", "triple_threat",
                         "boss_fight", "trap_room"):
        _render_smoke(
            lambda g, vk=variant_key: g.start_arena_variant(vk))
