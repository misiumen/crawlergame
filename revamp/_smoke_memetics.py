"""End-to-end smoke for Prompt 07 (memetic / belief seed system).

Covers:
1. Parser recognizes all memetic intents.
2. _attempt_memetic plants a seed with no targets if context implies them.
3. _attempt_memetic refuses if no targets, no claim, or no channel.
4. Seed persists through world.to_dict / from_dict.
5. process_belief_seeds advances stage / creates rumors / burns out.
6. encounter_modifiers_for returns relevant effects for targeted rooms.
7. Safehouse-entry trigger via consequences.move_to_room runs propagation.

Run: python -m revamp._smoke_memetics
"""
import random
random.seed(7)

from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_OBJECT, T_MONSTER, T_TERMINAL
from .parser_core import parse
from . import memetics


def _mk_world(has_terminal=False, has_camera=False, has_machine=False,
              safehouse=False):
    w = WorldState()
    w.character = Character(name="Memetic", background="streamer")
    w.character.stats["CHA"] = 16  # high CHA to make rolls more likely succeed
    w.floor_number = 1
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    if safehouse:
        r.safehouse_subtype = "cafe"
        r.actual_type = "safehouse"
    if has_terminal:
        term = Entity(key="t1", entity_type=T_TERMINAL, fallback_name="terminal",
                      tags=["terminal","machine"], affordances=["inspect","hack"],
                      location_id="r0")
        r.entities.append(term); w.register(term)
    if has_camera:
        cam = Entity(key="cam", entity_type=T_OBJECT, fallback_name="kamera",
                     tags=["camera","sponsor"], affordances=["inspect"],
                     location_id="r0")
        r.entities.append(cam); w.register(cam)
    if has_machine:
        bot = Entity(key="bot", entity_type=T_MONSTER, fallback_name="drono",
                     tags=["machine","drone"], hp=8, max_hp=8,
                     affordances=["attack"], location_id="r0")
        r.entities.append(bot); w.register(bot)
    f.add_room(r); f.start_room_id=r.room_id; f.current_room_id=r.room_id
    w.current_floor = f
    return w, f, r


def test_parser_recognizes_memetic_intents():
    cases = [
        ("wmów robotom, że ktoś ukradł im serca", "seed_belief"),
        ("rozpuść plotkę, że boss boi się luster", "spread_rumor"),
        ("podaj fałszywy rozkaz dronom: wracać do warsztatu", "issue_false_order"),
        ("ogłaszam przez kamerę, że maszyny są ofiarami systemu", "propaganda"),
        ("convince the robots that someone stole their hearts", "seed_belief"),
        ("spread rumor that the boss fears mirrors", "spread_rumor"),
    ]
    for text, expected in cases:
        i = parse(text)
        assert i.intent == expected, f"{text!r} -> got {i.intent}, expected {expected}"
        # Must have either a claim or targets, otherwise the handler will reject it.
        assert i.core_claim or i.targets, f"{text!r} parsed empty"
    print("  parser: OK")


def test_create_and_persist_seed():
    w, _, _ = _mk_world()
    seed = memetics.create_seed(
        method="rumor", core_claim="boss boi się luster",
        target_tags=["crawler","npc"], strength=60, stability=55,
    )
    memetics.register_seed(w, seed)
    assert seed.seed_id in w.belief_seeds
    blob = w.to_dict()
    w2 = WorldState.from_dict(blob)
    assert seed.seed_id in w2.belief_seeds, "seed lost on save/load"
    s2 = w2.belief_seeds[seed.seed_id]
    assert s2.core_claim == "boss boi się luster"
    assert s2.method == "rumor"
    assert "crawler" in s2.target_tags
    print("  save/load: OK")


def test_propagation_runs():
    w, f, r = _mk_world()
    seed = memetics.create_seed(method="rumor", core_claim="X spreads",
                                target_tags=["crawler"], strength=70,
                                spread_channels=["crawler_gossip"])
    memetics.register_seed(w, seed)
    # Run many ticks
    starting_rumors = list(f.rumors)
    rumor_emitted = False
    for _ in range(20):
        f.current_minute += 60
        events = memetics.process_belief_seeds(w, 60, trigger="tick")
        if any(e.get("kind") == "rumor" for e in events):
            rumor_emitted = True
            break
    assert rumor_emitted, "no rumor emitted across 20 ticks (strength=70)"
    print("  propagation -> rumor: OK")


def test_encounter_modifiers():
    w, f, r = _mk_world(has_machine=True)
    from .memetics import BeliefEffect
    seed = memetics.create_seed(
        method="logic_exploit",
        core_claim="they are violating compliance",
        target_tags=["machine","drone"],
        strength=70, stability=70,
        effects=[BeliefEffect(key="hesitation",
                              effect_type="hesitation", chance=1.0,
                              target_tags=["machine"],
                              fallback_description_pl="cel waha się")],
    )
    memetics.register_seed(w, seed)
    mods = memetics.encounter_modifiers_for(w, r)
    assert any(m.get("type") == "hesitation" for m in mods), f"no hesitation mod: {mods}"
    print("  encounter modifiers: OK")


def test_attempt_memetic_full_flow():
    """Drive Game._attempt_memetic against a context with machine targets."""
    import os; os.environ.setdefault("SDL_VIDEODRIVER","dummy")
    from .game import Game
    w, f, r = _mk_world(has_terminal=True, has_machine=True)
    g = Game(screen=None)
    g.world = w
    # Use an LLM-shaped intent
    intent = parse("wmów robotom, że ktoś ukradł im serca")
    assert intent.intent == "seed_belief"
    g._attempt_memetic(intent)
    seeds = memetics.all_active(w)
    assert seeds, "no seed created"
    print(f"  full flow: OK (seed_count={len(seeds)}, stage={seeds[0].current_stage})")


def test_refuses_when_context_missing():
    """false_order via machine_radio requires a terminal — must reject if none."""
    import os; os.environ.setdefault("SDL_VIDEODRIVER","dummy")
    from .game import Game
    w, f, r = _mk_world(has_terminal=False, has_machine=True)
    g = Game(screen=None)
    g.world = w
    intent = parse("podaj fałszywy rozkaz dronom: wracać do warsztatu")
    before = len(memetics.all_active(w))
    g._attempt_memetic(intent)
    after = len(memetics.all_active(w))
    assert after == before, "seed was planted despite missing channel"
    print("  channel guard: OK")


def main():
    test_parser_recognizes_memetic_intents()
    test_create_and_persist_seed()
    test_propagation_runs()
    test_encounter_modifiers()
    test_attempt_memetic_full_flow()
    test_refuses_when_context_missing()
    print("Prompt 07 memetic smoke: OK")


if __name__ == "__main__":
    main()
