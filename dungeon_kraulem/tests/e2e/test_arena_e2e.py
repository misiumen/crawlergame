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


def test_4_variants_in_catalog():
    """Wszystkie 4 warianty są zarejestrowane."""
    keys = {v.key for v in _arena.all_variants()}
    assert keys == {"duel_1v1", "triple_threat",
                    "boss_fight", "trap_room"}


def test_only_duel_1v1_enabled_for_mvp():
    """MVP: tylko 1 wariant gotowy do gry. Reszta 'wkrótce'."""
    enabled = {v.key for v in _arena.all_variants() if v.enabled}
    assert enabled == {"duel_1v1"}, (
        f"MVP scope: tylko duel_1v1 enabled, got {enabled}")


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
    """duel_1v1 → world ma room z Tunelowy Szczurek."""
    w, floor = _arena.build_arena_world("duel_1v1")
    room = floor.rooms["arena_room"]
    mob_names = [e.fallback_name for e in room.entities]
    assert "Tunelowy Szczurek" in mob_names


def test_build_arena_world_marks_arena_flag():
    """Arena world ma flag żeby Game wiedział że to test mode."""
    w, _f = _arena.build_arena_world("duel_1v1")
    assert w.flags.get("arena_mode") is True
    assert w.flags.get("arena_variant") == "duel_1v1"


def test_build_arena_disabled_variant_raises():
    """Disabled variant — explicit error."""
    import pytest
    with pytest.raises(ValueError):
        _arena.build_arena_world("boss_fight")  # disabled w MVP


def test_build_arena_unknown_variant_raises():
    import pytest
    with pytest.raises(ValueError):
        _arena.build_arena_world("nieistniejący")


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
    assert any("Szczurek" in e.fallback_name
               for e in room.entities)


def test_game_start_disabled_variant_logs_and_returns_false():
    game = Game(screen=None)
    # Najpierw musi istnieć world żeby log_msg działało
    ok_setup = game.start_arena_variant("duel_1v1")
    assert ok_setup

    # Teraz disabled variant
    ok = game.start_arena_variant("boss_fight")
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
