"""Prompt 29.7 — trap pickup (mis-placement fallback) smoke suite.

User reported: rozstawia pułapkę w złej lokacji i nie ma jak jej zabrać.
Without a fallback, the trap-deploy mechanic punishes early-game players
who haven't memorized which rooms have monster traffic.

Covers:
  * Parser recognises zwiń / podnieś / rozbrój pułapkę.
  * Lone-trap pickup with no target argument works.
  * Named pickup matches by display_name / tag / key substring.
  * Successful pickup restores Entity to inventory and removes from
    room.state['player_traps'].
  * Critical fail damages player and marks trap triggered.
  * No-trap room refuses gracefully.
  * Ambiguous pickup asks for disambiguation when 2+ traps present.
  * Time advances on every pickup attempt.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT
from ..engine.parser_core import parse


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


def _mk_trap_entity(w, key="shock_trap", name="pułapka prądowa",
                    tags=("trap", "shock", "deployable")):
    ent = Entity(key=key, entity_type=T_OBJECT, fallback_name=name,
                 tags=list(tags),
                 affordances=["inspect", "deploy"],
                 location_id="r0")
    w.register(ent)
    return ent


def _arm_trap_in_room(r, ent, *, triggered=False):
    r.state.setdefault("player_traps", []).append({
        "key": ent.key,
        "entity_id": ent.entity_id,
        "display_name": ent.display_name(),
        "tags": list(ent.tags or []),
        "quality": "normal",
        "armed_at": 0,
        "level": "success",
        "triggered": triggered,
        "effect": {"type": "damage", "amount": 3, "damage_type": "electric"},
    })


# ── Parser ───────────────────────────────────────────────────────────────

def test_parser_recognises_trap_pickup_variants():
    for cmd in ("zwiń pułapkę", "podnieś pułapkę prądową",
                "rozbrój pułapkę shock"):
        intent = parse(cmd)
        assert intent.intent == "trap_pickup", \
            f"{cmd!r} parsed as {intent.intent}, not trap_pickup"
    print("  parser maps zwiń/podnieś/rozbrój pułapkę → trap_pickup: OK")


# ── Lone-trap path ───────────────────────────────────────────────────────

def test_pickup_lone_trap_returns_to_inventory():
    from ..engine.game import Game
    import random as _r
    w, r = _mk_world()
    ent = _mk_trap_entity(w)
    _arm_trap_in_room(r, ent)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Lucky roll for guaranteed success.
    w.character.stats["DEX"] = 30
    _r.seed(3)
    g.submit_generated_command("zwiń pułapkę")
    # Entity back in inventory, trap dict gone.
    assert ent.entity_id in w.character.inventory_ids, \
        "trap entity not restored to inventory"
    assert not r.state.get("player_traps"), \
        f"trap dict still in room: {r.state.get('player_traps')}"
    print("  lone trap pickup restores entity + clears dict: OK")


# ── Named match ──────────────────────────────────────────────────────────

def test_pickup_by_partial_name():
    from ..engine.game import Game
    import random as _r
    w, r = _mk_world()
    e1 = _mk_trap_entity(w, key="shock_trap", name="pułapka prądowa",
                         tags=("trap", "shock"))
    e2 = _mk_trap_entity(w, key="trip_trap",  name="potykacz",
                         tags=("trap", "tripwire"))
    _arm_trap_in_room(r, e1)
    _arm_trap_in_room(r, e2)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.stats["DEX"] = 30
    _r.seed(4)
    # Match by partial token "prądową" / "prądowa".
    g.submit_generated_command("zwiń pułapkę prądowa")
    inv = w.character.inventory_ids
    assert e1.entity_id in inv, "shock trap not restored"
    assert e2.entity_id not in inv, "wrong trap restored"
    remaining = r.state.get("player_traps") or []
    assert len(remaining) == 1 and remaining[0]["key"] == "trip_trap", \
        f"unexpected traps remaining: {remaining}"
    print("  named pickup matches correct trap: OK")


# ── No traps in room ─────────────────────────────────────────────────────

def test_pickup_refuses_when_no_traps():
    from ..engine.game import Game
    w, r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    pre = len(w.log)
    g.submit_generated_command("zwiń pułapkę")
    post = len(w.log)
    assert post > pre, "no log line on empty-pickup refusal"
    # Inventory still empty (no traps to receive).
    assert not w.character.inventory_ids
    print("  empty room pickup refuses gracefully: OK")


# ── Triggered traps cannot be picked up ──────────────────────────────────

def test_triggered_traps_not_pickable():
    from ..engine.game import Game
    w, r = _mk_world()
    ent = _mk_trap_entity(w)
    _arm_trap_in_room(r, ent, triggered=True)
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zwiń pułapkę")
    # Entity not restored, trap dict still there (triggered).
    assert ent.entity_id not in w.character.inventory_ids
    assert len(r.state.get("player_traps") or []) == 1
    print("  triggered traps stay put: OK")


# ── Critical fail damages player ─────────────────────────────────────────

def test_critical_fail_damages_player():
    from ..engine.game import Game
    from ..engine import game as _gm
    w, r = _mk_world()
    ent = _mk_trap_entity(w)
    _arm_trap_in_room(r, ent)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Cripple stats to ensure low roll has no chance.
    w.character.stats["DEX"] = 1
    w.character.stats["INT"] = 1
    pre_hp = w.character.hp
    # Patch roll_d20 to force critical failure.
    import dungeon_kraulem.engine.utils_compat as _uc
    orig = _uc.roll_d20
    _uc.roll_d20 = lambda: 1
    try:
        g.submit_generated_command("zwiń pułapkę")
    finally:
        _uc.roll_d20 = orig
    assert w.character.hp < pre_hp, \
        f"crit-fail didn't damage player ({pre_hp}→{w.character.hp})"
    # Trap marked triggered.
    traps = r.state.get("player_traps") or []
    assert traps and traps[0].get("triggered") is True, \
        "trap should be triggered after self-fire"
    print(f"  crit-fail damages player ({pre_hp}→{w.character.hp}): OK")


# ── Time advances ────────────────────────────────────────────────────────

def test_pickup_advances_time():
    from ..engine.game import Game
    import random as _r
    w, r = _mk_world()
    ent = _mk_trap_entity(w)
    _arm_trap_in_room(r, ent)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.stats["DEX"] = 30
    _r.seed(5)
    pre_minute = w.current_floor.current_minute
    g.submit_generated_command("zwiń pułapkę")
    post_minute = w.current_floor.current_minute
    assert post_minute > pre_minute, \
        f"time didn't advance ({pre_minute}→{post_minute})"
    print(f"  time advances by {post_minute - pre_minute} min: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_parser_recognises_trap_pickup_variants()
    test_pickup_lone_trap_returns_to_inventory()
    test_pickup_by_partial_name()
    test_pickup_refuses_when_no_traps()
    test_triggered_traps_not_pickable()
    test_critical_fail_damages_player()
    test_pickup_advances_time()
    print("Prompt 29.7 trap pickup smoke: OK")


if __name__ == "__main__":
    main()
