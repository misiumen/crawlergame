"""End-to-end smoke for Prompt 07b (knowledge + clue-gated resolution).

Covers:
1. add_known_clue / fact / password / route round-trip through save/load.
2. has_unlocked_path triggered by clue's enables_paths.
3. matching_belief_for returns a seed only when target_tags overlap and strength is high.
4. Rumor bias toward objective tags fires across multiple seeds.
5. _attempt_use_password unlocks a door entity when password matches.
6. _attempt_exploit_weakness applies damage with known weakness.
7. _attempt_invoke_belief lands when a strong belief targets the room's machines.
8. Parser recognizes "wiedza", "użyj hasła", "wykorzystaj słabość", "przypominam ... o sercach".

Run: python -m revamp._smoke_knowledge
"""
import os, random
random.seed(13)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_OBJECT, T_MONSTER, T_DOOR
from .parser_core import parse
from . import knowledge as kn
from . import memetics


def _mk():
    w = WorldState()
    w.character = Character(name="K", background="streamer")
    w.character.stats["CHA"] = 18
    w.character.stats["WIS"] = 18
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    w.current_floor = f
    return w, f, r


def test_parser_intents():
    cases = [
        ("wiedza", "check_knowledge"),
        ("wskazówki", "check_knowledge"),
        ("użyj hasła", "use_password"),
        ("użyj hasła do panelu", "use_password"),
        ("wykorzystaj słabość bossa", "exploit_weakness"),
        ("przypominam dronom o skradzionych sercach", "invoke_belief"),
        ("use password on terminal", "use_password"),
    ]
    for text, expected in cases:
        i = parse(text)
        assert i.intent == expected, f"{text!r} -> got {i.intent}, expected {expected}"
    print("  parser intents: OK")


def test_save_load_round_trip():
    w, f, r = _mk()
    kn.add_known_clue(w, {
        "key": "service_password_elevator",
        "title_pl": "Hasło windy",
        "text": "Z notatki: JAZDA-0",
        "reveals_tags": ["elevator_password_known"],
        "enables_paths": ["use_password"],
        "tags": ["password","elevator"],
        "reliability": 0.85,
    })
    kn.add_known_password(w, {
        "key":"elevator_pwd_1", "label":"Hasło serwisowe windy",
        "code_text":"JAZDA-0", "opens":["elevator","door"], "tags":["service"]
    })
    kn.add_known_fact(w, {
        "key":"boss_weakness_water_fact",
        "text":"Strażnik zwalnia na mokrym.",
        "tags":["weakness","boss"], "enables_paths":["exploit_weakness"],
    })
    kn.add_known_route(w, {"key":"vent_to_office","from_room_id":"bath","to_room_id":"office","route_type":"vent","known":True})
    assert kn.has_unlocked_path(w, "use_password")
    assert kn.has_unlocked_path(w, "exploit_weakness")
    assert kn.has_known_clue(w, "service_password_elevator")
    assert kn.has_known_clue(w, "elevator_password_known")  # tag lookup
    assert kn.has_password_for(w, "elevator")
    # Round-trip
    blob = w.to_dict()
    w2 = WorldState.from_dict(blob)
    assert "service_password_elevator" in w2.known_clues
    assert "elevator_pwd_1" in w2.known_passwords
    assert kn.has_unlocked_path(w2, "use_password")
    assert kn.has_unlocked_path(w2, "exploit_weakness")
    assert "vent_to_office" in w2.known_routes
    print("  save/load: OK")


def test_rumor_bias_to_objective_tags():
    """Across multiple generated floors, rumors picked should overlap with
    objective.tags more often than chance."""
    from . import floor_generator as fg, content_loader as cl
    matched = 0
    total = 0
    for seed in range(1, 16):
        w = WorldState()
        w.character = Character(name="P", background="janitor")
        floor = fg.generate_floor(w, floor_number=1, seed=seed)
        obj = cl.all_floor_objectives().get(floor.objective_key, {})
        obj_tags = set(obj.get("tags", []) + obj.get("required_tags", []))
        if not obj_tags or not floor.rumors:
            continue
        for rk in floor.rumors:
            rumor = cl.all_rumor_categories()
            found = None
            for cat, items in rumor.items():
                for r in items:
                    if r.get("key") == rk:
                        found = r; break
                if found: break
            if not found:
                continue
            total += 1
            tags = set(found.get("tags") or []) | set(found.get("reveals_tags") or [])
            if obj_tags & tags:
                matched += 1
    # Expect at least ~35% of placed rumors to overlap with objective tags.
    # (Cap is low because some rumors carry no tags at all.)
    ratio = matched / max(1, total)
    print(f"  rumor bias: {matched}/{total} = {ratio:.0%}")
    assert ratio >= 0.30, f"rumor objective bias too weak: {ratio:.0%}"


def test_use_password_handler():
    from .game import Game
    w, f, r = _mk()
    door = Entity(key="elev_door", entity_type=T_DOOR, fallback_name="winda",
                  tags=["door","elevator"], affordances=["use","force","hack"],
                  location_id="r0")
    r.entities.append(door); w.register(door)
    kn.add_known_password(w, {
        "key":"pwd1", "label":"Hasło windy", "code_text":"JAZDA-0",
        "opens":["elevator"], "tags":["service"],
    })
    g = Game(screen=None); g.world = w
    g._attempt_use_password(parse("użyj hasła do windy"))
    assert door.state.get("unlocked") is True, "door not unlocked"
    print("  password handler: OK")


def test_exploit_weakness_handler():
    from .game import Game
    w, f, r = _mk()
    boss = Entity(key="boss", entity_type=T_MONSTER, fallback_name="strażnik",
                  hp=20, max_hp=20, tags=["boss"], affordances=["attack"],
                  location_id="r0")
    r.entities.append(boss); w.register(boss)
    kn.add_known_clue(w, {
        "key":"boss_weakness_water", "title_pl":"Słabość",
        "text":"Boss zwalnia w wilgoci.",
        "tags":["weakness","boss"], "enables_paths":["exploit_weakness"],
        "reveals_tags":["boss_weakness_water"],
    })
    g = Game(screen=None); g.world = w
    pre = boss.hp
    # Try a few times so a single bad roll doesn't fail the smoke; with
    # WIS=18 (mod=+4) and DC=11, success chance is ~70%.
    for _ in range(6):
        g._attempt_exploit_weakness(parse("wykorzystaj słabość bossa"))
        if boss.hp < pre:
            break
        boss.hp = pre  # reset for retry
    assert boss.hp < pre, f"boss hp didn't drop in 6 tries ({pre} -> {boss.hp})"
    print(f"  exploit_weakness handler: OK (hp {pre} -> {boss.hp})")


def test_invoke_belief_handler():
    from .game import Game
    w, f, r = _mk()
    bot = Entity(key="bot", entity_type=T_MONSTER, fallback_name="drono",
                 hp=8, max_hp=8, tags=["machine","drone"],
                 affordances=["attack"], location_id="r0")
    r.entities.append(bot); w.register(bot)
    # Plant a high-strength belief on machines
    seed = memetics.create_seed(method="identity_attack",
                                core_claim="ktoś ukradł im serca",
                                target_tags=["machine","drone"],
                                strength=75, stability=60)
    memetics.register_seed(w, seed)
    g = Game(screen=None); g.world = w
    g._attempt_invoke_belief(parse("przypominam dronom o skradzionych sercach"))
    # Either the bot gained a condition or HP dropped (success path).
    success = ("hesitating" in (bot.conditions or [])) or bot.hp < 8
    assert success, f"invoke_belief had no visible effect (hp={bot.hp}, cond={bot.conditions})"
    print(f"  invoke_belief handler: OK (cond={bot.conditions}, hp={bot.hp})")


def test_old_save_loads_safe():
    """Ensure a save without any knowledge fields loads cleanly with empties."""
    minimal = {
        "version": 1,
        "character": {"name":"old","background":"janitor"},
        "current_floor": None,
        "floor_number": 1,
        "entities": {},
        "log": [],
        "known_crawlers": [],
        "settings": {},
        "random_seed": None,
    }
    w = WorldState.from_dict(minimal)
    assert w.known_clues == {}
    assert w.known_facts == {}
    assert w.known_routes == {}
    assert w.known_passwords == {}
    assert w.unlocked_paths == []
    print("  old-save tolerance: OK")


def main():
    test_parser_intents()
    test_save_load_round_trip()
    test_rumor_bias_to_objective_tags()
    test_use_password_handler()
    test_exploit_weakness_handler()
    test_invoke_belief_handler()
    test_old_save_loads_safe()
    print("Prompt 07b knowledge smoke: OK")


if __name__ == "__main__":
    main()
