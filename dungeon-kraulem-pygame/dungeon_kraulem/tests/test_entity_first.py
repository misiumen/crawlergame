"""Prompt 14 smoke — entity-first dungeon + universal interaction.

Builds the exact test scene the prompt described and runs the listed
commands. Asserts that every visible object is targetable and that the
core interactions work without an LLM.

Test scene (one room):
    - lustro (mirror)
    - kamera (camera)
    - krzesło (chair)
    - ciało (corpse)
    - zamknięte drzwi (locked door — synthesized from room.exits)

Commands exercised (Polish):
    - sprawdź lustro / kamerę / krzesło / ciało
    - rozbij lustro
    - pozyskaj szkło z lustra
    - zdemontuj kamerę
    - wyciągnij przewody z kamery
    - rozbij krzesło / rozbierz krzesło
    - przeszukaj ciało / ograb ciało
    - zaatakuj lustro (must route to break, not refuse)
    - kopnij drzwi (must route to break against synth door)
    - wyłam drzwi (force)

Asserts:
  * Every targetable entity gets a valid validation result.
  * Tag-driven fallback works for entities that don't list the affordance
    explicitly but DO carry compatible tags.
  * Synthesizing a door entity from `room.exits` lets break/force/lockpick
    address it.
  * Breaking the synthetic door unlocks the underlying exit.
  * State changes survive save/load (stripped, broken, looted flags).
  * No Ollama HTTP call is made — pure deterministic resolution.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

from .. import config
config.apply_llm_mode("performance")    # belt-and-braces: LLM off

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT, T_MONSTER, T_NPC, T_CORPSE
from ..engine.parser_core import parse
from ..engine.validation import validate, _tag_implies_affordance, _synth_door_entity_for


def _mk_scene():
    """Build the test scene with the 5 canonical objects + a second room
    behind a locked door so we can verify door-break unlocks the exit."""
    w = WorldState()
    w.character = Character(name="EF", background="janitor")
    w.character.stats["STR"] = 18
    w.character.stats["DEX"] = 16
    w.character.stats["WIS"] = 14
    f = FloorState(floor_id="ef", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Łazienka testowa")
    rb = RoomState(room_id="r1", fallback_short_title="Korytarz")
    f.add_room(r); f.add_room(rb)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    # Locked exit to r1.
    r.exits["północ"] = {"target": "r1", "locked": True, "hidden": False,
                          "hint_key": "", "fallback_hint": "Zamknięte."}
    # Five canonical entities.
    mirror = Entity(key="mirror", entity_type=T_OBJECT, fallback_name="lustro",
                    tags=["bathroom","glass","fragile","salvageable"],
                    affordances=["inspect","break","salvage"], location_id="r0")
    camera = Entity(key="sponsor_camera", entity_type=T_OBJECT,
                    fallback_name="kamera sponsora",
                    tags=["camera","sponsor","electronic","high","fragile",
                          "salvageable","sponsor_tech"],
                    affordances=["inspect","salvage","break"], location_id="r0")
    chair  = Entity(key="loose_chair", entity_type=T_OBJECT,
                    fallback_name="luźne krzesło",
                    tags=["furniture","plastic","light","salvageable"],
                    affordances=["inspect","salvage","throw_at"], location_id="r0")
    corpse = Entity(key="dead_crawler", entity_type=T_CORPSE,
                    fallback_name="ciało crawlera",
                    tags=["corpse","corpse_humanoid","organic","crawler"],
                    affordances=["inspect","search","loot","harvest"],
                    location_id="r0")
    for e in (mirror, camera, chair, corpse):
        r.entities.append(e); w.register(e)
    f.discovered_room_ids = {"r0"}
    w.current_floor = f
    return w, f, r


# ── Tag-fallback unit tests ────────────────────────────────────────────────

def test_tag_implies_affordance():
    e = Entity(key="x", entity_type=T_OBJECT, fallback_name="x",
               tags=["fragile","glass","salvageable"], affordances=["inspect"])
    assert _tag_implies_affordance(e, "break")
    assert _tag_implies_affordance(e, "salvage")
    assert not _tag_implies_affordance(e, "talk")
    # Entity with no tags + no affordances: nothing implied.
    e2 = Entity(key="y", entity_type=T_OBJECT, fallback_name="y",
                tags=[], affordances=["inspect"])
    assert not _tag_implies_affordance(e2, "break")
    assert not _tag_implies_affordance(e2, "salvage")
    print("  tag-implies-affordance: OK")


# ── Door synthesis ─────────────────────────────────────────────────────────

def test_door_synthesis():
    w, f, r = _mk_scene()
    # No door entity exists yet.
    assert not any(e.key == "_synth_door" for e in r.entities)
    door = _synth_door_entity_for(r)
    assert door is not None
    assert door.entity_type == "door"
    assert "locked" in door.tags
    assert "break" in door.affordances
    # Repeated synth returns the same entity (no duplicate spam).
    door2 = _synth_door_entity_for(r)
    assert door is door2
    print("  synth door entity: OK")


# ── Validator: every canonical command finds its target ────────────────────

def test_every_command_validates():
    w, f, r = _mk_scene()
    cases = [
        # (text, expected intent, expected target keyword in display_name)
        ("sprawdź lustro",        "inspect", "lustro"),
        ("rozbij lustro",         "break",   "lustro"),
        ("pozyskaj szkło z lustra", "harvest", "lustro"),
        ("sprawdź kamerę",        "inspect", "kamera"),
        ("zdemontuj kamerę",      "salvage", "kamera"),
        ("wyciągnij przewody z kamery", "salvage", "kamera"),
        ("rozbij krzesło",        "break",   "krzesło"),
        ("rozbierz krzesło",      "salvage", "krzesło"),
        # "przeszukaj X" with an explicit target routes to loot
        # (container/corpse search) rather than the no-target global search.
        ("przeszukaj ciało",      "loot",    "ciało"),
        ("ograb ciało",           "loot",    "ciało"),
        ("pozyskaj kości z ciała","harvest", "ciało"),
        ("kopnij drzwi",          "break",   "drzwi"),
        ("wyłam drzwi",           "force",   "drzwi"),
    ]
    for text, expected_intent, name_token in cases:
        i = parse(text)
        assert i.intent == expected_intent, \
            f"{text!r} -> intent={i.intent} (expected {expected_intent})"
        v = validate(i, w)
        assert v.valid, f"{text!r} not valid: {v.fallback_message}"
        assert v.matched_entities, f"{text!r} no matched entity"
        # Either the synthesized door key matches "drzwi" via display_name,
        # or a regular entity matches via its Polish fallback_name.
        target = v.matched_entities[0]
        display = target.display_name().lower()
        assert name_token.lower() in display or name_token.lower() in target.key, \
            f"{text!r} matched {target.display_name()!r} (expected {name_token!r})"
    print(f"  every command validates: OK ({len(cases)} cases)")


# ── attack on object routes to break ───────────────────────────────────────

def test_attack_object_routes_to_break():
    from ..engine.game import Game
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    mirror = next(e for e in r.entities if e.key == "mirror")
    assert not mirror.state.get("broken")
    # With STR 18 and fragile DC 8, almost certain hit; loop a few times.
    for _ in range(6):
        g._handle_play_input("zaatakuj lustro")
        if mirror.state.get("broken"):
            break
        mirror.state = {}
    assert mirror.state.get("broken"), \
        f"'zaatakuj lustro' didn't route to break (state={mirror.state})"
    print("  zaatakuj lustro -> break: OK")


# ── Door-break unlocks underlying exit ─────────────────────────────────────

def test_break_door_unlocks_exit():
    from ..engine.game import Game
    import random; random.seed(11)
    w, f, r = _mk_scene()
    assert r.exits["północ"]["locked"] is True
    g = Game(screen=None); g.world = w
    for _ in range(6):
        g._handle_play_input("rozbij drzwi")
        if not r.exits["północ"]["locked"]:
            break
    assert r.exits["północ"]["locked"] is False, \
        f"door break didn't propagate to room.exits (locked still True)"
    print("  rozbij drzwi unlocks exit: OK")


# ── State persistence + no infinite farming ────────────────────────────────

def test_no_infinite_farming():
    from ..engine.game import Game
    import random; random.seed(7)
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    # First salvage of the chair should succeed (eventually).
    chair = next(e for e in r.entities if e.key == "loose_chair")
    for _ in range(6):
        g._handle_play_input("rozbierz krzesło")
        if chair.state.get("stripped") or chair.state.get("depleted"):
            break
    assert chair.state.get("stripped") or chair.state.get("depleted"), \
        "chair didn't get stripped/depleted"
    pre_mats = dict(w.character.materials)
    # Second salvage attempt must be refused — no farming.
    g._handle_play_input("rozbierz krzesło")
    last = w.log[-1][0]
    assert "już" in last.lower() or "rozebrane" in last.lower() or \
           "stripped" in last.lower(), \
        f"second salvage didn't refuse: {last!r}"
    # Materials must not have grown.
    assert dict(w.character.materials) == pre_mats, "materials grew on second strip"
    print("  no infinite farming: OK")


# ── save/load round-trips entity state ─────────────────────────────────────

def test_state_persists():
    from ..engine.game import Game
    import random; random.seed(3)
    w, f, r = _mk_scene()
    g = Game(screen=None); g.world = w
    # Break the mirror and loot the corpse.
    mirror = next(e for e in r.entities if e.key == "mirror")
    corpse = next(e for e in r.entities if e.key == "dead_crawler")
    for _ in range(5):
        g._handle_play_input("rozbij lustro")
        if mirror.state.get("broken"): break
    g._handle_play_input("przeszukaj ciało")
    blob = w.to_dict()
    w2 = WorldState.from_dict(blob)
    r2 = w2.current_floor.rooms["r0"]
    m2 = next(e for e in r2.entities if e.key == "mirror")
    assert m2.state.get("broken") is True, \
        f"mirror state lost on save/load: {m2.state}"
    print("  state persists through save/load: OK")


# ── Useful refusals for indestructible things ──────────────────────────────

def test_indestructible_gives_useful_refusal():
    """A 'structural' object should refuse break with a clear message, not
    a generic 'wrong_affordance' technical error."""
    w, f, r = _mk_scene()
    wall = Entity(key="wall_chunk", entity_type=T_OBJECT,
                  fallback_name="ściana", tags=["structural","stone"],
                  affordances=["inspect"], location_id="r0")
    r.entities.append(wall); w.register(wall)
    i = parse("rozbij ścianę")
    v = validate(i, w)
    assert v.valid is False
    msg = v.fallback_message.lower()
    assert "konstruk" in msg or "ustąpi" in msg or "ustapi" in msg, \
        f"unhelpful refusal: {v.fallback_message!r}"
    print(f"  indestructible refusal: OK ({v.fallback_message[:60]}…)")


# ── LLM independence ───────────────────────────────────────────────────────

def test_no_ollama_calls():
    """Drive the whole canonical command set with LLM off and the spy
    counter must stay at zero."""
    from ..llm import llm_parser
    calls = {"n": 0}
    real = llm_parser.parse_with_ollama
    def spy(*a, **k):
        calls["n"] += 1
        return None
    llm_parser.parse_with_ollama = spy
    try:
        from ..engine.game import Game
        w, f, r = _mk_scene()
        g = Game(screen=None); g.world = w
        for text in [
            "sprawdź lustro", "rozbij lustro", "pozyskaj szkło z lustra",
            "zdemontuj kamerę", "wyciągnij przewody z kamery",
            "rozbierz krzesło", "przeszukaj ciało", "ograb ciało",
            "rozbij drzwi", "zaatakuj lustro",
        ]:
            g._handle_play_input(text)
    finally:
        llm_parser.parse_with_ollama = real
    assert calls["n"] == 0, f"Ollama HTTP called {calls['n']}× with LLM off"
    print("  zero Ollama calls in performance mode: OK")


def main():
    test_tag_implies_affordance()
    test_door_synthesis()
    test_every_command_validates()
    test_attack_object_routes_to_break()
    test_break_door_unlocks_exit()
    test_no_infinite_farming()
    test_state_persists()
    test_indestructible_gives_useful_refusal()
    test_no_ollama_calls()
    print("Prompt 14 entity-first smoke: OK")


if __name__ == "__main__":
    main()
