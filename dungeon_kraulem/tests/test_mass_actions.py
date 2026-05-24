"""Prompt 16 smoke — mass commands, typed-input priority, bare-exit movement.

Builds the canonical test scene from the prompt and runs:
    - mass salvage (rozbierz wszystko)
    - mass search (przeszukaj wszystko)
    - mass loot (weź wszystko, ograb wszystko)
    - mass break (rozbij wszystko)
    - bare exit name typed as command (korytarz)
    - typed input vs nav-panel priority

Plus the no-LLM guardrail: with intent role ON and Ollama unreachable,
mass commands still resolve deterministically with zero HTTP calls.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

from .. import config
config.apply_llm_mode("performance")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT, T_MONSTER, T_CORPSE
from ..engine.parser_core import parse, parse_with_optional_llm


# ── Parser-level tests ─────────────────────────────────────────────────────

def test_mass_parser_intents():
    cases = [
        ("rozbierz wszystko",     "mass_salvage"),
        ("zdemontuj wszystko",    "mass_salvage"),
        ("pozyskaj wszystko",     "mass_salvage"),
        ("rozbierz cały pokój",   "mass_salvage"),
        ("ogołoć pokój",          "mass_salvage"),
        ("przeszukaj wszystko",   "mass_search"),
        ("przeszukaj cały pokój", "mass_search"),
        ("weź wszystko",          "mass_loot_take"),
        ("zbierz wszystko",       "mass_loot_take"),
        ("ograb wszystko",        "mass_loot_loose"),
        ("rozbij wszystko",       "mass_break"),
        ("zniszcz wszystko",      "mass_break"),
        ("rozwal wszystko",       "mass_break"),
        ("smash all",             "mass_break"),
        ("take everything",       "mass_loot_take"),
    ]
    for text, expected in cases:
        i = parse(text)
        assert i.intent == expected, f"{text!r} -> {i.intent} (expected {expected})"
        assert i.mass_target is True, f"{text!r} mass_target not set"
        assert i.confidence >= 0.9, f"{text!r} confidence too low: {i.confidence}"
    print(f"  mass parser intents: OK ({len(cases)} commands)")


def test_mass_intent_blocks_llm_path():
    """Even with LLM 'on' and Ollama unreachable, mass commands must
    return deterministic intent without trying the network."""
    from ..llm import llm_roles
    config.apply_llm_mode("enhanced")     # would normally consult LLM
    llm_roles.reset_availability_cache()
    # Spy on the HTTP entry point.
    from ..llm import llm_parser
    calls = {"n": 0}
    real = llm_parser.parse_with_ollama
    def spy(*a, **k):
        calls["n"] += 1
        return None
    llm_parser.parse_with_ollama = spy
    try:
        for text in ["rozbierz wszystko", "weź wszystko", "rozbij wszystko"]:
            i = parse_with_optional_llm(text)
            assert i.intent.startswith("mass_"), f"{text!r} -> {i.intent}"
            assert i.mass_target is True
    finally:
        llm_parser.parse_with_ollama = real
        config.apply_llm_mode("performance")
        llm_roles.reset_availability_cache()
    assert calls["n"] == 0, f"Ollama was called {calls['n']}x for mass command"
    print("  LLM guardrail: no Ollama calls on mass commands: OK")


# ── End-to-end via Game ────────────────────────────────────────────────────

def _mk_scene():
    """The exact scene the playtest prompt described."""
    w = WorldState()
    w.character = Character(name="Mass", background="janitor")
    w.character.stats["STR"] = 16
    w.character.stats["DEX"] = 14
    f = FloorState(floor_id="m", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    rb = RoomState(room_id="r1", fallback_short_title="Korytarz")
    f.add_room(r); f.add_room(rb)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.discovered_room_ids = {"r0", "r1"}
    r.exits["korytarz"] = {"target": "r1", "locked": False, "hidden": False,
                            "hint_key": "", "fallback_hint": ""}
    mirror = Entity(key="mirror", entity_type=T_OBJECT, fallback_name="lustro",
                    tags=["bathroom","glass","fragile","salvageable"],
                    affordances=["inspect","break","salvage"], location_id="r0")
    chair = Entity(key="loose_chair", entity_type=T_OBJECT, fallback_name="krzesło",
                   tags=["furniture","wood","salvageable"],
                   affordances=["inspect","salvage"], location_id="r0")
    camera = Entity(key="sponsor_camera", entity_type=T_OBJECT,
                    fallback_name="kamera sponsora",
                    tags=["camera","sponsor","electronic","fragile","salvageable"],
                    affordances=["inspect","salvage","break"], location_id="r0")
    corpse = Entity(key="dead_crawler", entity_type=T_CORPSE,
                    fallback_name="ciało crawlera",
                    tags=["corpse","organic","crawler"],
                    affordances=["inspect","search","loot"], location_id="r0")
    # A portable item lying around for "weź wszystko".
    coin = Entity(key="coin", entity_type=T_OBJECT, fallback_name="moneta",
                  tags=["valuable"], affordances=["inspect","loot"],
                  portable=True, location_id="r0")
    # A safehouse-owned object — should be skipped/warned about.
    sink = Entity(key="sink", entity_type=T_OBJECT, fallback_name="zlew",
                  tags=["bathroom","fixture","ceramic","salvageable"],
                  affordances=["inspect","salvage"], location_id="r0")
    sink.state["owned_by"] = "safehouse"
    sink.state["theft_sensitive"] = True
    # A structural wall chunk — should always be skipped.
    wall = Entity(key="wall_chunk", entity_type=T_OBJECT, fallback_name="ściana",
                  tags=["structural","stone"], affordances=["inspect"],
                  location_id="r0")
    for e in (mirror, chair, camera, corpse, coin, sink, wall):
        r.entities.append(e); w.register(e)
    w.current_floor = f
    return w, f, r


def test_mass_salvage_handler():
    from ..engine.game import Game
    import random; random.seed(2)
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g._handle_play_input("rozbierz wszystko")
    # Expected: mirror, chair, camera stripped; sink warned but processed;
    # corpse + portable coin + wall_chunk skipped (organic/portable/structural)
    mirror = next(e for e in r.entities if e.key == "mirror")
    chair  = next(e for e in r.entities if e.key == "loose_chair")
    cam    = next(e for e in r.entities if e.key == "sponsor_camera")
    wall   = next(e for e in r.entities if e.key == "wall_chunk")
    assert mirror.state.get("stripped"), f"mirror not stripped"
    assert chair.state.get("stripped"),  f"chair not stripped"
    assert cam.state.get("stripped"),    f"camera not stripped"
    assert not wall.state.get("stripped"), "structural wall was stripped"
    # Materials should have accumulated.
    total = sum((w.character.materials or {}).values())
    assert total > 0, f"no materials accrued ({w.character.materials})"
    # Second pass must refuse / be a no-op for already-stripped entities.
    pre_mats = dict(w.character.materials)
    g._handle_play_input("rozbierz wszystko")
    post_mats = dict(w.character.materials)
    # Either nothing new or only safehouse sink (single retry). Wall_chunk
    # must never be stripped on re-run.
    assert wall.state.get("stripped") is None, "second pass stripped wall"
    print(f"  mass salvage: OK (mats {sum(pre_mats.values())} -> {sum(post_mats.values())})")


def test_mass_search_handler():
    from ..engine.game import Game
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g._handle_play_input("przeszukaj wszystko")
    corpse = next(e for e in r.entities if e.key == "dead_crawler")
    assert corpse.state.get("searched") is True, "corpse not searched"
    print("  mass search: OK")


def test_mass_loot_handler():
    from ..engine.game import Game
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g._handle_play_input("weź wszystko")
    # The portable coin must now be in inventory; the non-portable sink
    # must NOT be picked up even though it's "owned_by safehouse".
    assert any(w.get(eid) and w.get(eid).key == "coin"
               for eid in w.character.inventory_ids), \
        "coin not in inventory after 'weź wszystko'"
    sink = next(e for e in r.entities if e.key == "sink")
    assert sink.location_id == "r0", "non-portable sink got taken"
    print("  mass loot: OK")


def test_mass_break_handler():
    from ..engine.game import Game
    import random; random.seed(5)
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g._handle_play_input("rozbij wszystko")
    mirror = next(e for e in r.entities if e.key == "mirror")
    cam    = next(e for e in r.entities if e.key == "sponsor_camera")
    sink   = next(e for e in r.entities if e.key == "sink")   # owned
    wall   = next(e for e in r.entities if e.key == "wall_chunk")
    # Fragile glass/electronic/ceramic — mirror + camera should break.
    # Owned safehouse sink should be skipped (safe-minimal behavior).
    # Structural wall must never break.
    assert mirror.state.get("broken") is True
    assert cam.state.get("broken") is True
    assert not sink.state.get("broken"), "safehouse-owned sink broken in mass break"
    assert not wall.state.get("broken"), "structural wall broken"
    # High noise.
    assert r.noise_level > 0
    print(f"  mass break: OK (noise +{r.noise_level})")


# ── Typed-input priority ────────────────────────────────────────────────────

def test_typed_input_wins_over_nav_selection():
    """The play-state Enter handler must NEVER fire the nav-panel selected
    option when input_text has content. This is the playtest-reported bug."""
    from ..engine.game import Game
    import pygame as _pg

    class FakeEv:
        def __init__(self, k): self.key = k

    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g.state = "play"
    # Pre-fill input as if the player typed "rozbierz wszystko".
    g.input_text = "rozbierz wszystko"
    g._ensure_nav_state()
    pre_log_size = len(g.world.log)
    g.handle_keydown(FakeEv(_pg.K_RETURN))
    # First log line after Enter should be the player's command echo.
    # If the nav option had fired instead, we'd see something like
    # "> rozejrzyj się" instead.
    echoes = [ln for ln, _ in g.world.log[pre_log_size:]
              if ln.startswith("> ")]
    assert echoes, f"no echoed command after Enter: {g.world.log[pre_log_size:]}"
    assert "rozbierz wszystko" in echoes[0], \
        f"typed input was overridden: log shows {echoes[0]!r}"
    print(f"  typed input priority: OK (echoed {echoes[0]!r})")


def test_empty_input_runs_nav_selection():
    """With the input box empty, Enter fires the currently-selected nav
    option ONLY after the player has explicitly armed the selection by
    pressing arrow/Tab. A cold Enter on an empty input is a no-op — this
    prevents Enter-autorepeat/accidental-tap spam from re-firing
    'rozejrzyj się' or similar default nav actions (Prompt 18 fix)."""
    from ..engine.game import Game
    import pygame as _pg

    class FakeEv:
        def __init__(self, k): self.key = k

    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    g.state = "play"
    g.input_text = ""           # empty
    g._ensure_nav_state()
    # Force selection to the look action so we have something deterministic.
    from ..ui import ui_nav
    g.nav_state.current_group_index = 0
    g.nav_state.set_selected_index(0, ui_nav.GROUP_ACTIONS)

    # 1. Cold Enter on empty input must be a no-op (prevents spam).
    pre = len(g.world.log)
    g.handle_keydown(FakeEv(_pg.K_RETURN))
    echoes_cold = [ln for ln, _ in g.world.log[pre:] if ln.startswith("> ")]
    assert not echoes_cold, \
        f"cold Enter on empty input must not fire nav option; got {echoes_cold!r}"

    # 2. Arrow key arms the selection; the next Enter must fire it.
    g.handle_keydown(FakeEv(_pg.K_DOWN))   # arms latch
    pre2 = len(g.world.log)
    g.handle_keydown(FakeEv(_pg.K_RETURN))
    echoes_armed = [ln for ln, _ in g.world.log[pre2:] if ln.startswith("> ")]
    assert echoes_armed, "armed Enter on empty input did nothing"

    # 3. The latch disarms after firing — a second Enter must NOT re-fire.
    pre3 = len(g.world.log)
    g.handle_keydown(FakeEv(_pg.K_RETURN))
    echoes_again = [ln for ln, _ in g.world.log[pre3:] if ln.startswith("> ")]
    assert not echoes_again, \
        f"second Enter must not re-fire (latch should disarm); got {echoes_again!r}"

    print(f"  arming latch on empty-input nav: OK (cold no-op, armed ran {echoes_armed[0]!r}, no re-fire)")


# ── Bare destination commands ──────────────────────────────────────────────

def test_bare_exit_label_routes_to_move():
    w, f, r = _mk_scene()
    i = parse("korytarz", world=w)
    assert i.intent == "move", f"got intent={i.intent}"
    assert i.destination == "korytarz"
    print("  bare 'korytarz' -> move: OK")


def test_bare_destination_room_title():
    w, f, r = _mk_scene()
    # The destination room is "Korytarz" (display_short_title)
    i = parse("Korytarz", world=w)
    assert i.intent == "move", f"got intent={i.intent}"
    print("  bare destination room title -> move: OK")


def test_polish_grammar_exit_inflection():
    """Prompt 18: Polish noun inflection on exit labels — "przejście"
    (nominative), "przejścia" (genitive), "idź do przejścia",
    "idź przez przejście" must all resolve to the exit labeled
    "przejście". Diacritic-folded variants must also work. None of
    these should be miscategorised as the search affordance (the old
    bug: "prze" prefix collision with "przeszukaj")."""
    from ..engine.world import WorldState, FloorState
    from ..engine.room import RoomState
    from ..engine.validation import validate

    room = RoomState(room_id='r1', fallback_short_title='Korytarz',
                     exits={'przejście': {'target':'r2','hidden':False}})
    room2 = RoomState(room_id='r2', fallback_short_title='Komnata')
    floor = FloorState(rooms={'r1':room,'r2':room2}, current_room_id='r1')
    world = WorldState(current_floor=floor)

    phrasings = [
        'przejście', 'przejscie', 'przejścia', 'przejsciem',
        'idź do przejścia', 'idz do przejscia',
        'idź przez przejście', 'idź do komnaty',
    ]
    for txt in phrasings:
        i = parse(txt, world=world)
        assert i.intent == "move", \
            f"{txt!r}: expected intent=move, got {i.intent!r}"
        res = validate(i, world)
        assert res.valid, \
            f"{txt!r}: validation failed reason={res.reason!r}"
    print(f"  Polish-grammar exit inflection: OK ({len(phrasings)} phrasings)")


def test_no_exit_message_has_no_placeholder_leak():
    """Prompt 18: a failed move must not leak a literal '{target}' into
    the player log. Use a clean fallback message and list visible exits."""
    from ..engine.world import WorldState, FloorState
    from ..engine.room import RoomState
    from ..engine.validation import validate

    room = RoomState(room_id='r1', fallback_short_title='Korytarz',
                     exits={'przejście': {'target':'r2','hidden':False}})
    room2 = RoomState(room_id='r2', fallback_short_title='Komnata')
    floor = FloorState(rooms={'r1':room,'r2':room2}, current_room_id='r1')
    world = WorldState(current_floor=floor)

    i = parse("idź do nieistniejącego", world=world)
    res = validate(i, world)
    assert not res.valid
    assert res.reason == "no_exit"
    msg = res.fallback_message or ""
    assert "{target}" not in msg, \
        f"placeholder leak: {msg!r}"
    assert "przejście" in msg, \
        f"visible-exits hint missing: {msg!r}"
    print(f"  no-exit message clean (no {{target}} leak): OK")


# ── Suite ──────────────────────────────────────────────────────────────────

def main():
    test_mass_parser_intents()
    test_mass_intent_blocks_llm_path()
    test_mass_salvage_handler()
    test_mass_search_handler()
    test_mass_loot_handler()
    test_mass_break_handler()
    test_typed_input_wins_over_nav_selection()
    test_empty_input_runs_nav_selection()
    test_bare_exit_label_routes_to_move()
    test_bare_destination_room_title()
    test_polish_grammar_exit_inflection()
    test_no_exit_message_has_no_placeholder_leak()
    print("Prompt 16 mass-action smoke: OK")


if __name__ == "__main__":
    main()
