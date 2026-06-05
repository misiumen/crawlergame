"""Prompt 26b — Combat Stakes Layer smoke suite.

Covers:
  * Noise decay over time (out of combat)
  * Noise propagation to adjacent rooms
  * Noise threshold triggers patrol_routine encounter
  * High noise threshold triggers patrol_responder encounter
  * Latches prevent re-spawning until noise drops back down
  * Combat lockdown whitelist: refuses loot/salvage/butcher with refusal log
  * Combat lockdown allows wield/coat/use_item to fall through
  * Combat lockdown move → flee with check
  * Floor collapse threshold crossings emit drama lines
  * Floor collapse at 0 sets `floor.state["collapsed"]`; Game flips to DEFEAT
  * Faction AI: rival faction monsters may target each other (probabilistic)
  * Cross-faction targeting still consumes attacker's turn + audience bump
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import random as _r

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..config import MINUTES_PER_DAY
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import combat as _cmb
from ..engine import time_system as _ts
# P29.0 — noise / encounter modules REMOVED; their tests live in
# test_p29_threat.py against the new threat-escalation system.


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    a = RoomState(room_id="a", fallback_short_title="A")
    b = RoomState(room_id="b", fallback_short_title="B")
    c = RoomState(room_id="c", fallback_short_title="C")
    a.exits = {
        "wschód": {"target": "b", "locked": False, "hidden": False},
    }
    b.exits = {
        "zachód": {"target": "a", "locked": False, "hidden": False},
        "wschód": {"target": "c", "locked": False, "hidden": False},
    }
    c.exits = {"zachód": {"target": "b", "locked": False, "hidden": False}}
    for r in (a, b, c):
        f.add_room(r)
    f.start_room_id = "a"; f.current_room_id = "a"
    w.current_floor = f
    return w


# P29.0 — noise→patrol mechanics REMOVED. Their replacement tests
# live in test_p29_threat.py against engine/threat.py.


# ── Combat lockdown whitelist ─────────────────────────────────────────

def _start_combat(w):
    room = w.current_floor.current_room()
    m = Entity(key="rat", entity_type=T_MONSTER, fallback_name="szczurek",
               hp=5, max_hp=5, ac=10, affordances=["attack"],
               tags=["monster"], location_id=room.room_id)
    w.register(m); room.entities.append(m)
    _cmb.start_combat(room, w)


def test_lockdown_refuses_loot():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    w = _mk_world(); _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    cs = _cmb.get_combat(w.current_floor.current_room())
    pre = len(w.log)
    consumed = g._combat_route(ActionIntent(intent="loot", verb="podnieś"), cs)
    assert consumed is True
    assert len(w.log) > pre
    last = w.log[-1][0].lower()
    assert "walk" in last or "nie teraz" in last or "patrosz" in last
    print("  lockdown refuses loot: OK")


def test_lockdown_allows_wield_fallthrough():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    w = _mk_world(); _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    cs = _cmb.get_combat(w.current_floor.current_room())
    consumed = g._combat_route(ActionIntent(intent="wield", verb="dobądź"), cs)
    assert consumed is False, "wield must fall through for normal handler"
    print("  lockdown allows wield fall-through: OK")


def test_lockdown_allows_use_fallthrough():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    w = _mk_world(); _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    cs = _cmb.get_combat(w.current_floor.current_room())
    consumed = g._combat_route(ActionIntent(intent="use", verb="użyj"), cs)
    assert consumed is False
    print("  lockdown allows use fall-through: OK")


def test_lockdown_move_routes_to_flee():
    from ..engine.game import Game
    from ..engine.parser_core import ActionIntent
    w = _mk_world(); _start_combat(w)
    g = Game(screen=None); g.world = w; g.state = "play"
    cs = _cmb.get_combat(w.current_floor.current_room())
    intent = ActionIntent(intent="move", verb="idź", destination="wschód")
    consumed = g._combat_route(intent, cs)
    assert consumed is True
    # P27.6: symmetric enemy attack log widened tail; scan a bigger window.
    last_lines = " ".join(s for s, _c in w.log[-8:]).lower()
    assert "wycof" in last_lines or "ucie" in last_lines
    print("  lockdown move → flee redirect: OK")


# ── Floor collapse dramatics ──────────────────────────────────────────

def test_collapse_threshold_lines_fire():
    w = _mk_world()
    f = w.current_floor
    f.deadline_minute = f.current_minute + 65  # 1h 5min remaining
    pre_log = len(w.log)
    _ts.advance(w, 6)
    after_log_text = " ".join(s for s, _ in w.log[pre_log:]).lower()
    # 1h threshold should have fired.
    assert "godzin" in after_log_text or "1h" in after_log_text or "termin" in after_log_text
    print("  1h deadline warning emits on cross: OK")


def test_collapse_at_zero_marks_floor():
    w = _mk_world()
    f = w.current_floor
    f.deadline_minute = f.current_minute + 5
    _ts.advance(w, 10)   # cross zero
    assert (f.state or {}).get("collapsed"), \
        "deadline=0 must mark floor.state['collapsed']"
    print("  deadline=0 → floor.state.collapsed: OK")


def test_game_state_flips_to_defeat_on_collapse():
    from ..engine.game import Game
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    f = g.world.current_floor
    f.deadline_minute = f.current_minute + 3
    _ts.advance(g.world, 5)
    g.update(0)
    assert g.state == "defeat"
    print("  Game state → defeat on collapse: OK")


def test_fresh_game_ticks_without_crashing():
    """Regression for d3693aa: P26b added a Game.update() poll that read
    `f.state["collapsed"]`, but FloorState never had a `state` attribute
    defined — only RoomState did. Every update() tick after
    start_new_game raised AttributeError, crashing the game on the first
    frame. The earlier P26b tests only exercised update() AFTER
    _trigger_floor_collapse had lazily created `f.state`, so they missed
    this entirely.

    Covers all backgrounds because the bug was background-agnostic; we
    just iterate through a couple to make the class of bug ("game can
    run for N frames after fresh start") testable for any future
    Game.update() regression.
    """
    from ..engine.game import Game
    from ..engine.character import BACKGROUNDS
    pygame.display.set_mode((1280, 720))
    for bg in ("janitor", "opiekun_zwierzaka", "office_worker"):
        assert bg in BACKGROUNDS, f"test fixture stale: {bg} not in BACKGROUNDS"
        g = Game(screen=pygame.display.get_surface())
        g.start_new_game("Tester", bg)
        g.state = "play"
        # Tick + draw a few frames — this is what crashed before.
        for _ in range(5):
            g.update(16)
            g.draw()
    print("  fresh game ticks without crashing (3 backgrounds × 5 frames): OK")


# ── Faction AI ────────────────────────────────────────────────────────

def test_faction_tags_extract():
    e = Entity(key="x", entity_type=T_MONSTER, fallback_name="x",
               hp=5, max_hp=5, ac=10, location_id="r",
               tags=["monster", "faction:novachem", "humanoid"])
    facs = _cmb._faction_tags(e)
    assert facs == {"novachem"}
    print("  _faction_tags extracts faction keys: OK")


def test_rival_target_picked_when_factions_differ():
    """With seeded randomness, a rival from a different faction can
    be chosen as target."""
    w = _mk_world()
    room = w.current_floor.current_room()
    a = Entity(key="a", entity_type=T_MONSTER, fallback_name="A",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster", "faction:novachem"],
               location_id=room.room_id, damage_dice="1d4")
    b = Entity(key="b", entity_type=T_MONSTER, fallback_name="B",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster", "faction:liga"],
               location_id=room.room_id, damage_dice="1d4")
    w.register(a); w.register(b)
    room.entities.append(a); room.entities.append(b)
    _cmb.start_combat(room, w)
    cs = _cmb.get_combat(room)
    # Force seeded RNG to hit the retarget path.
    import random as _rnd
    _rnd.seed(1)
    saw_rival = False
    for _ in range(30):
        action = _cmb.choose_enemy_action(w, cs, a)
        if action.target_id == b.entity_id:
            saw_rival = True
            break
    assert saw_rival, "expected at least one rival retarget over 30 rolls"
    print("  rival faction retarget fires: OK")


def test_same_faction_no_retarget():
    w = _mk_world()
    room = w.current_floor.current_room()
    a = Entity(key="a", entity_type=T_MONSTER, fallback_name="A",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster", "faction:liga"],
               location_id=room.room_id, damage_dice="1d4")
    b = Entity(key="b", entity_type=T_MONSTER, fallback_name="B",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster", "faction:liga"],
               location_id=room.room_id, damage_dice="1d4")
    w.register(a); w.register(b)
    room.entities.append(a); room.entities.append(b)
    _cmb.start_combat(room, w)
    cs = _cmb.get_combat(room)
    import random as _rnd
    _rnd.seed(1)
    for _ in range(30):
        action = _cmb.choose_enemy_action(w, cs, a)
        assert action.target_id is None, "same-faction must not retarget"
    print("  same-faction no retarget: OK")


def test_no_faction_tag_no_retarget():
    w = _mk_world()
    room = w.current_floor.current_room()
    a = Entity(key="a", entity_type=T_MONSTER, fallback_name="A",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster"],
               location_id=room.room_id, damage_dice="1d4")
    b = Entity(key="b", entity_type=T_MONSTER, fallback_name="B",
               hp=10, max_hp=10, ac=10, affordances=["attack"],
               tags=["monster", "faction:liga"],
               location_id=room.room_id, damage_dice="1d4")
    w.register(a); w.register(b)
    room.entities.append(a); room.entities.append(b)
    _cmb.start_combat(room, w)
    cs = _cmb.get_combat(room)
    import random as _rnd
    _rnd.seed(1)
    for _ in range(20):
        action = _cmb.choose_enemy_action(w, cs, a)
        assert action.target_id is None, "no faction tag must not retarget"
    print("  no-faction never retargets: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    # P29.0 — patrol/noise tests removed. See test_p29_threat.py for
    # the replacement (threat escalation in-room).
    test_lockdown_refuses_loot()
    test_lockdown_allows_wield_fallthrough()
    test_lockdown_allows_use_fallthrough()
    test_lockdown_move_routes_to_flee()
    test_collapse_threshold_lines_fire()
    test_collapse_at_zero_marks_floor()
    test_game_state_flips_to_defeat_on_collapse()
    test_fresh_game_ticks_without_crashing()
    test_faction_tags_extract()
    test_rival_target_picked_when_factions_differ()
    test_same_faction_no_retarget()
    test_no_faction_tag_no_retarget()
    print("Prompt 26b combat stakes layer smoke: OK")


if __name__ == "__main__":
    main()
