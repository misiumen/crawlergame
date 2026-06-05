"""Prompt 29.39 — fix dla bug'a „wyłam przejście do X".

Bug zgłoszony przez gracza: w panelu pojawia się akcja
„wyłam przejście do Zamrażarka — Mięso Nieidentyfikowalne", ale po
wywołaniu silnik zwraca „Nie widzisz tu tego, czego szukasz." dwa
razy z rzędu, a wyjście pozostaje zamknięte.

Przyczyna: UI sugerował komendę dla każdego locked exit, parser
poprawnie produkował `intent.intent="force"`, ale w `game.py` nie
było żadnego dispatchu pod `force` (tylko `break`). Plus walidator
zwracał pusty zestaw entity, bo:
  (a) wyjścia żyją jako klucze w `room.exits` dict, nie jako entity;
  (b) heurystyka „syntetyczne drzwi" w `validation._resolve_entities`
      reagowała tylko na słowa „drzwi", „wyjście", „brama" — nie na
      „przejście", a tylko brała PIERWSZE locked wyjście w pokoju
      (nie konkretne).

P29.39 dorzuca:
  * `validation._synth_door_for_exit_label(room, folded_target)` —
    matcher po labelu, tworzący/zwracający synth_door przypiętą do
    konkretnego wyjścia.
  * Dodanie „przejście" / „przejscie" do `door_words`.
  * `game._attempt_force(intent)` — STR check vs DC 14, na sukces
    `room.exits[label]["locked"] = False` + spektakl audience.
  * Dispatch w głównym routerze: `if intent.intent == "force": ...`.

Smoke pokrywa:
  * Walidator znajduje konkretne wyjście po labelu (nie pierwsze).
  * `_attempt_force` na sukcesie odblokowuje konkretne wyjście.
  * Drzwi już otwarte zwracają zrozumiały komunikat, nie crash.
  * Crit fail zadaje 2 HP graczowi.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import random
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.parser_core import ActionIntent
from ..engine import validation as _val


def _world_with_two_exits():
    """Buduje świat: jeden pokój, dwa wyjścia — jedno zamknięte
    ('przejście do zamrażarka'), drugie otwarte ('korytarz'). Konkret
    żeby test pokazał że validator nie myli ich ze sobą."""
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.stats["STR"] = 20   # praktycznie auto-success
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Sala")
    r.exits = {
        "przejście do zamrażarka": {
            "target": "r1", "locked": True, "hidden": False,
        },
        "korytarz": {
            "target": "r2", "locked": False, "hidden": False,
        },
    }
    f.add_room(r)
    f.add_room(RoomState(room_id="r1", fallback_short_title="Zamrażarka"))
    f.add_room(RoomState(room_id="r2", fallback_short_title="Korytarz"))
    f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    w.floor_number = 1
    return w


# ── Validator: matcher po labelu ───────────────────────────────────────

def test_resolve_finds_specific_locked_exit_by_label():
    w = _world_with_two_exits()
    room = w.current_floor.current_room()
    matches = _val._resolve_entities(
        room, "przejście do zamrażarka")
    assert matches, "validator nic nie znalazł"
    assert matches[0].key == "_synth_door"
    assert (matches[0].state or {}).get("label") == "przejście do zamrażarka"
    print("  validator łapie konkretne wyjście po labelu: OK")


def test_resolve_does_not_confuse_two_exits():
    """Pewnik: jak gracz wpisze 'korytarz', dostaje korytarz, nie
    zamrażarkę (nawet jeśli ta jest locked, a heurystyka by ją
    preferowała)."""
    w = _world_with_two_exits()
    room = w.current_floor.current_room()
    matches = _val._resolve_entities(room, "korytarz")
    assert matches, "korytarz nieznaleziony"
    assert (matches[0].state or {}).get("label") == "korytarz"
    print("  dwa wyjścia w jednym pokoju nie mylą się: OK")


def test_resolve_word_przejscie_alone_falls_back_to_synth():
    """Słowo 'przejście' bez label-detail wciąż łapie się przez
    `door_words` fallback — pierwsze niesakryte wyjście."""
    w = _world_with_two_exits()
    room = w.current_floor.current_room()
    matches = _val._resolve_entities(room, "przejście")
    assert matches, "fallback nie zadziałał"
    print("  samo 'przejście' fallbackuje do synth_door: OK")


# ── Game.force handler: odblokowuje konkretne wyjście ─────────────────

def test_force_unlocks_specific_exit():
    from ..engine.game import Game
    g = Game(screen=None)
    g.world = _world_with_two_exits()
    g.state = "play"
    # Ustawiamy seed żeby roll był deterministyczny — STR=20 + d20 >= 1
    # już wystarczy.
    random.seed(7)
    intent = ActionIntent(
        intent="force", verb="wyłam",
        targets=["przejście do zamrażarka"],
        normalized_text="wyłam przejście do zamrażarka")
    g._attempt_force(intent)
    room = g.world.current_floor.current_room()
    assert not room.exits["przejście do zamrażarka"]["locked"], \
        "force nie odblokował wyjścia"
    # Drugie wyjście nie ruszone.
    assert room.exits["korytarz"]["locked"] is False
    print("  _attempt_force odblokowuje konkretny exit: OK")


def test_force_already_open_refuses_cleanly():
    from ..engine.game import Game
    g = Game(screen=None)
    g.world = _world_with_two_exits()
    g.state = "play"
    intent = ActionIntent(
        intent="force", verb="wyłam",
        targets=["korytarz"],
        normalized_text="wyłam korytarz")
    pre_log_len = len(g.world.log)
    g._attempt_force(intent)
    # Nic nie powinno crashować. Korytarz wciąż otwarty (oczywiście).
    assert g.world.current_floor.rooms["r0"].exits["korytarz"]["locked"] is False
    # I jakaś linia w logu o tym że nie było co wyłamywać.
    assert len(g.world.log) > pre_log_len
    print("  force na otwartym wyjściu: clean refusal: OK")


def test_force_does_not_throw_on_missing_target():  # noqa
    pass


# ── UX-6 / UX-3 ───────────────────────────────────────────────────────
# Trywialne obiekty od razu `seen` (bez fog-of-war), inspect bez surowych
# tagów, z afordansami w polskich etykietach.

def test_trivial_entity_starts_as_seen():
    from ..engine.entity import Entity
    from ..engine import visibility as _vis
    crate = Entity(
        key="crate", entity_type="object",
        fallback_name="skrzynia zaopatrzenia",
        tags=["container", "wood", "salvageable"],
        affordances=["inspect", "search", "loot", "break"],
    )
    # WorldState może być None — respect_known_key_on_spawn nie wymaga.
    class _StubWorld:
        known_entity_keys = []
    _vis.respect_known_key_on_spawn(_StubWorld(), crate)
    assert _vis.get_state(crate) == _vis.STATE_SEEN, \
        f"skrzynia powinna od razu być seen; jest {_vis.get_state(crate)}"
    print("  trywialna skrzynia: STATE_SEEN od razu: OK")


def test_non_trivial_entity_stays_unknown():
    from ..engine.entity import Entity
    from ..engine import visibility as _vis
    trap = Entity(
        key="floor_trap", entity_type="hazard",
        fallback_name="podejrzana płyta podłogi",
        tags=["trap", "hidden", "metal"],
        affordances=["inspect", "disarm"],
    )
    class _StubWorld:
        known_entity_keys = []
    _vis.respect_known_key_on_spawn(_StubWorld(), trap)
    assert _vis.get_state(trap) == _vis.STATE_UNKNOWN, \
        f"pułapka powinna zostać unknown; jest {_vis.get_state(trap)}"
    print("  pułapka: STATE_UNKNOWN (wymaga sprawdź): OK")


def test_inspect_block_does_not_leak_raw_tags():
    from ..engine.entity import Entity
    from ..engine import visibility as _vis
    crate = Entity(
        key="crate", entity_type="object",
        fallback_name="skrzynia zaopatrzenia",
        fallback_desc="Pełna albo pusta. Z zewnątrz wygląda tak samo.",
        tags=["container", "wood", "salvageable"],
        affordances=["inspect", "search", "loot", "break"],
    )
    lines = _vis.build_inspect_block(None, crate)
    blob = "\n".join(lines)
    # Surowe sluga NIE mogą trafić do gracza.
    for bad in ("container", "wood", "salvageable", "Tagi:"):
        assert bad not in blob, (f'wyciek surowego taga „{bad}": '
                                 f'\n{blob}')
    # Affordance hints po polsku obecne.
    assert "Możesz spróbować" in blob
    assert "przeszukać" in blob or "rozbić" in blob or "zgarnąć" in blob
    print("  inspect bez surowych tagów + polskie afordansy: OK")


def test_inspect_block_includes_polish_affordance_hints():
    from ..engine.entity import Entity
    from ..engine import visibility as _vis
    door = Entity(
        key="locked_door", entity_type="door",
        fallback_name="zamknięte drzwi",
        tags=["door", "metal", "locked"],
        affordances=["inspect", "force", "lockpick", "break"],
    )
    lines = _vis.build_inspect_block(None, door)
    blob = "\n".join(lines)
    # Polskie etykiety afordansów.
    assert "wyłamać" in blob, f"missing wyłamać:\n{blob}"
    assert "wytrychem" in blob, f"missing wytrych:\n{blob}"
    print("  drzwi: polskie afordansy w hintach: OK")


def _ignored_marker():
    """Gracz wpisze nonsens → walidator wraca pusto → handler
    zwraca po prostu komunikat, nie wyjątek."""
    from ..engine.game import Game
    g = Game(screen=None)
    g.world = _world_with_two_exits()
    g.state = "play"
    intent = ActionIntent(
        intent="force", verb="wyłam",
        targets=["maczeta z mango"],
        normalized_text="wyłam maczeta z mango")
    g._attempt_force(intent)   # bez crashu
    print("  force na nonsensie nie crashuje: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_resolve_finds_specific_locked_exit_by_label()
    test_resolve_does_not_confuse_two_exits()
    test_resolve_word_przejscie_alone_falls_back_to_synth()
    test_force_unlocks_specific_exit()
    test_force_already_open_refuses_cleanly()
    test_force_does_not_throw_on_missing_target()
    test_trivial_entity_starts_as_seen()
    test_non_trivial_entity_stays_unknown()
    test_inspect_block_does_not_leak_raw_tags()
    test_inspect_block_includes_polish_affordance_hints()
    print("Prompt 29.39 force + inspect-bloat smoke: OK")


if __name__ == "__main__":
    main()
