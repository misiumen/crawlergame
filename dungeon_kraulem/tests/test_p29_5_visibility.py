"""Prompt 29.5 — fog-of-war / scout layer smoke suite.

Covers:
  * Entity.visibility_state defaults to "unknown" + save/load.
  * mark_seen / mark_inspected transitions.
  * shape_for_unknown returns Polish vague labels from tags.
  * display_name_for_player gates name by state.
  * `sprawdź X` handler walks unknown → seen → inspected.
  * `sprawdź` costs 1 turn + bumps threat (mechanical cost).
  * Combat hit auto-promotes target to inspected.
  * known_entity_keys persists cross-floor; new spawns of known key
    arrive as seen instead of unknown.
  * world.known_entity_keys save/load round-trip.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER, T_OBJECT
from ..engine import visibility as _vis


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


def _add_monster(w, r, key="thug", hp=80):
    m = Entity(key=key, entity_type=T_MONSTER,
               fallback_name="Bandzior", hp=hp, max_hp=hp, ac=11,
               affordances=["attack"], tags=["monster", "humanoid"],
               location_id="r0")
    w.register(m); r.entities.append(m)
    return m


# ── Field defaults + save/load ───────────────────────────────────────────

def test_entity_default_visibility_unknown():
    e = Entity(key="x", entity_type=T_MONSTER, fallback_name="x")
    assert e.visibility_state == "unknown"
    print("  Entity default visibility_state='unknown': OK")


def test_visibility_save_load_round_trip():
    e = Entity(key="x", entity_type=T_MONSTER, fallback_name="x")
    e.visibility_state = "inspected"
    d = e.to_dict()
    e2 = Entity.from_dict(d)
    assert e2.visibility_state == "inspected"
    print("  visibility_state save/load round-trip: OK")


# ── Transitions ──────────────────────────────────────────────────────────

def test_mark_seen_promotes_unknown_only():
    w, r = _mk_world()
    m = _add_monster(w, r)
    assert _vis.is_unknown(m)
    assert _vis.mark_seen(m) is True
    assert _vis.get_state(m) == _vis.STATE_SEEN
    # Calling again is a no-op (already seen).
    assert _vis.mark_seen(m) is False
    print("  mark_seen unknown→seen, no-op on seen: OK")


def test_mark_inspected_promotes_and_remembers_key():
    w, r = _mk_world()
    m = _add_monster(w, r, key="thug")
    _vis.mark_inspected(w, m)
    assert _vis.get_state(m) == _vis.STATE_INSPECTED
    assert "thug" in w.known_entity_keys
    print("  mark_inspected sets state + records key: OK")


def test_shape_for_unknown_uses_tags():
    e_h = Entity(key="x", entity_type=T_MONSTER, tags=["monster", "humanoid"])
    assert _vis.shape_for_unknown(e_h) == "postać"
    e_b = Entity(key="y", entity_type=T_MONSTER, tags=["monster", "beast"])
    assert _vis.shape_for_unknown(e_b) == "zwierzę"
    e_m = Entity(key="z", entity_type=T_MONSTER, tags=["monster", "machine"])
    assert _vis.shape_for_unknown(e_m) == "urządzenie"
    print("  shape_for_unknown maps tags → PL: OK")


def test_display_name_gated_by_state():
    e = Entity(key="x", entity_type=T_MONSTER,
               fallback_name="Bandzior", tags=["monster", "humanoid"])
    # unknown
    assert _vis.display_name_for_player(e) == "postać"
    e.visibility_state = "seen"
    assert "Bandzior" in _vis.display_name_for_player(e)
    print("  display_name gated by state: OK")


# ── sprawdź handler ──────────────────────────────────────────────────────

def test_sprawdz_walks_state_machine():
    """P29.47 — dwustopniowy state machine został spłaszczony do
    jednego kroku. Pierwsza sprawdź daje pełną kartę od razu
    (unknown → inspected). Druga już tylko re-printuje."""
    from ..engine.game import Game
    w, r = _mk_world()
    m = _add_monster(w, r, key="thug", hp=80)
    g = Game(screen=None); g.world = w; g.state = "play"
    m.fallback_name = "Bandzior"
    # Single sprawdź: unknown → inspected (pełna karta od razu).
    g.submit_generated_command("sprawdź Bandzior")
    assert _vis.get_state(m) == _vis.STATE_INSPECTED, \
        f"sprawdź powinno od razu dać inspected; got {_vis.get_state(m)}"
    # Druga sprawdź: nadal inspected, no change.
    g.submit_generated_command("sprawdź Bandzior")
    assert _vis.get_state(m) == _vis.STATE_INSPECTED
    print("  sprawdź unknown→inspected w jednym kroku: OK")


def test_sprawdz_costs_a_turn():
    from ..engine.game import Game
    w, r = _mk_world()
    m = _add_monster(w, r, key="thug")
    m.fallback_name = "Bandzior"
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_minute = w.current_floor.current_minute
    g.submit_generated_command("sprawdź Bandzior")
    post_minute = w.current_floor.current_minute
    assert post_minute > pre_minute, \
        f"sprawdź should advance time; {pre_minute}→{post_minute}"
    print(f"  sprawdź advances time by {post_minute - pre_minute} min: OK")


# ── Combat hit auto-inspect ──────────────────────────────────────────────

def test_combat_hit_promotes_to_inspected():
    """Landing a hit reveals full stats (combat math leaks them)."""
    from ..engine.game import Game
    from ..engine import combat as _cmb
    import random as _r
    w, r = _mk_world()
    m = _add_monster(w, r, key="thug", hp=200)
    m.fallback_name = "Bandzior"
    g = Game(screen=None); g.world = w; g.state = "play"
    _cmb.start_combat(r, w)
    cs = _cmb.get_combat(r)
    cs.selected_target_id = m.entity_id
    # Force STR high for reliable hit.
    w.character.stats["STR"] = 30
    _r.seed(7)
    pre_state = _vis.get_state(m)
    # Try a few attacks; the first successful hit should promote.
    for _ in range(6):
        g.submit_generated_command("zaatakuj")
        if _vis.get_state(m) == _vis.STATE_INSPECTED:
            break
    assert _vis.get_state(m) == _vis.STATE_INSPECTED, \
        f"combat hit should promote; pre={pre_state} post={_vis.get_state(m)}"
    print(f"  combat hit auto-inspects target: OK")


# ── known_entity_keys cross-spawn ────────────────────────────────────────

def test_known_key_persists_to_new_spawn():
    """After inspecting an entity with key=K, a NEW spawn with the
    same key arrives as `seen`, not `unknown`."""
    w, r = _mk_world()
    m = _add_monster(w, r, key="thug")
    _vis.mark_inspected(w, m)
    # Now spawn a fresh entity with same key.
    m2 = Entity(key="thug", entity_type=T_MONSTER,
                fallback_name="Bandzior 2",
                tags=["monster", "humanoid"], location_id="r0")
    _vis.respect_known_key_on_spawn(w, m2)
    assert _vis.get_state(m2) == _vis.STATE_SEEN, \
        f"new spawn of known key should be seen; got {_vis.get_state(m2)}"
    print("  known_entity_keys → next spawn starts as 'seen': OK")


def test_known_entity_keys_save_load():
    w, _r = _mk_world()
    w.known_entity_keys = ["thug", "tunnel_runt"]
    d = w.to_dict()
    w2 = WorldState.from_dict(d)
    assert "thug" in w2.known_entity_keys
    assert "tunnel_runt" in w2.known_entity_keys
    print("  known_entity_keys save/load: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_entity_default_visibility_unknown()
    test_visibility_save_load_round_trip()
    test_mark_seen_promotes_unknown_only()
    test_mark_inspected_promotes_and_remembers_key()
    test_shape_for_unknown_uses_tags()
    test_display_name_gated_by_state()
    test_sprawdz_walks_state_machine()
    test_sprawdz_costs_a_turn()
    test_combat_hit_promotes_to_inspected()
    test_known_key_persists_to_new_spawn()
    test_known_entity_keys_save_load()
    print("Prompt 29.5 visibility / fog-of-war smoke: OK")


if __name__ == "__main__":
    main()
