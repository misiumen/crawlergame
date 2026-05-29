"""E2E dla P29.61 vertical slice — systemowa interakcja w arenie.

Pierwsza systemowa interakcja widoczna END-TO-END w grze: w arenie
trap_room gracz wpycha szczura w pęknięty hazard → silnik reguł
odpala efekt.

trap_room spawnuje: Tunelowy Szczurek (tag flammable→łatwopalne) +
kałuża kwasu (acid) + zwarcie kablowe (electric) + pęknięta rura
pary (fire). Czyli:
  • wepchnij szczura w rurę pary → ogień+łatwopalne → POŻAR (synergia)
  • wepchnij szczura w kwas → brak synergii (szczur nie metal) →
    bazowe obrażenia środowiskowe

Rule 12b/12d — capturuje observed behaviour + integrację z grą.
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import systemic as _sys
from ...engine import combat as _cmb
from ...engine.game import Game, STATE_ARENA_PLAY
from ...engine.parser_core import ActionIntent


def _start_trap_arena():
    game = Game(screen=None)
    ok = game.start_arena_variant("trap_room")
    assert ok and game.state == STATE_ARENA_PLAY
    room = game.world.current_floor.current_room()
    return game, room


def _find(room, needle):
    for e in room.entities:
        if needle.lower() in e.fallback_name.lower() or needle in e.key:
            return e
    return None


# ── Synergia: ogień + łatwopalne → pożar ────────────────────────────


def test_push_rat_into_steam_pipe_ignites():
    game, room = _start_trap_arena()
    rat = _find(room, "Szczur")
    pipe = _find(room, "rura pary")
    assert rat is not None, "brak szczura w trap_room"
    assert pipe is not None, "brak rury pary w trap_room"

    cs = _cmb.start_combat(room, game.world, triggered_by="test")

    intent = ActionIntent(intent="push_into", verb="wepchnij",
                          targets=[rat.fallback_name])
    intent.destination = "rura pary"

    pre_hp = rat.hp
    ok = game._try_systemic_chain(intent, cs)

    assert ok is True, "systemic chain nie zadziałał"
    assert _sys.has_systemic_status(rat, "płonie"), \
        "szczur (łatwopalny) powinien się zapalić od rury (ogień)"
    assert rat.hp < pre_hp, "pożar powinien zadać obrażenia"
    joined = "\n".join(t for t, _ in game.world.log)
    assert "płomien" in joined.lower(), \
        f"log nie pokazuje zapłonu:\n{joined}"


# ── Bazowe obrażenia: brak synergii ale hazard parzy ───────────────


def test_push_rat_into_acid_base_damage():
    game, room = _start_trap_arena()
    rat = _find(room, "Szczur")
    acid = _find(room, "kwas")
    assert rat and acid

    cs = _cmb.start_combat(room, game.world, triggered_by="test")
    intent = ActionIntent(intent="push_into", verb="wepchnij",
                          targets=[rat.fallback_name])
    intent.destination = "kałuża kwasu"

    pre_hp = rat.hp
    ok = game._try_systemic_chain(intent, cs)

    # Szczur nie jest metalem → brak synergii korozji, ale kwas
    # i tak parzy (bazowe obrażenia środowiskowe).
    assert ok is True
    assert rat.hp < pre_hp, "kwas powinien zadać bazowe obrażenia"


# ── Parser produkuje poprawny intent dla łańcucha ──────────────────


def test_parser_push_into_chain_sets_destination():
    from ...engine.parser_core import parse_with_optional_llm
    intent = parse_with_optional_llm(
        "wepchnij szczura w kałużę kwasu")
    assert intent.intent in ("push_into", "lure"), (
        f"oczekiwano push_into, got {intent.intent}")
    assert intent.targets, "brak obiektu (szczur)"
    assert getattr(intent, "destination", None), "brak destination"
    assert "kwas" in intent.destination.lower()


# ── No-match graceful: wepchnij w coś bez elementu ─────────────────


def test_push_into_nonelement_no_systemic():
    """Wepchnięcie szczura w zwykły obiekt bez elementu → systemic
    nie łapie, fall-through do starej logiki (brak crasha)."""
    game, room = _start_trap_arena()
    rat = _find(room, "Szczur")
    cs = _cmb.start_combat(room, game.world, triggered_by="test")
    intent = ActionIntent(intent="push_into", verb="wepchnij",
                          targets=[rat.fallback_name])
    intent.destination = "nieistniejący obiekt xyz"
    ok = game._try_systemic_chain(intent, cs)
    assert ok is False, "brak celu/źródła → systemic nie powinien łapać"


# ── Render smoke nadal OK po wpięciu ───────────────────────────────


def test_arena_play_still_renders_after_systemic_wire():
    import pygame
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    screen = pygame.display.set_mode((1280, 800))
    game = Game(screen=screen)
    game.start_arena_variant("trap_room")
    game.draw()  # nie crashuje
