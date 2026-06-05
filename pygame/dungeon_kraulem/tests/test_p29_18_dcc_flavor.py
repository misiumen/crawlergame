"""Prompt 29.18 — DCC flavor smoke suite.

Audit finding: the show is on but no one's directing it; the same
six no-name sponsors; the dungeon never produces an absurd vendor
item; sponsors at HOT don't antagonize each other. P29.18 adds:
  * engine/show_director.py     — reklama / kamera / ankieta / cut
  * engine/proxy_wars.py        — sponsor-vs-sponsor disinfo events
  * content/data/celebrities.py — named NPC pool for encounters
  * vending machines            — room template + use-handler

Covers (compact across all four systems):
  * show_director.list_events returns 5 entries with the right shape.
  * show_director.maybe_fire NO-OPs when audience is cold.
  * show_director.maybe_fire FIRES under force=True at warming+.
  * show_director respects per-floor cap.
  * proxy_wars NO-OPs when only one sponsor is HOT.
  * proxy_wars FIRES when two sponsors both >= +5.
  * proxy_wars respects per-pair cooldown.
  * celebrities catalog has 6+ entries, all gated by floor_min/max.
  * vending machine use moves an item to inventory and burns credit.
  * vending machine is single-use per machine instance.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT


def _mk_world(audience: int = 30):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=audience)
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── show_director ───────────────────────────────────────────────────────

def test_show_director_catalog_shape():
    from ..engine import show_director as _sd
    events = _sd.list_events()
    assert len(events) == 5
    for e in events:
        assert "id" in e and "weight" in e and "min_band" in e
        assert e["min_band"] in ("warming", "hot", "viral")
    print(f"  show_director catalog: {len(events)} events: OK")


def test_show_director_cold_audience_noop():
    from ..engine import show_director as _sd
    w, _r = _mk_world(audience=2)   # cold band
    fired = _sd.maybe_fire(w, force=True)
    assert fired is None, f"cold audience should NOT fire; got {fired}"
    print("  director silent at cold audience: OK")


def test_show_director_fires_at_warming():
    from ..engine import show_director as _sd
    w, _r = _mk_world(audience=45)
    fired = _sd.maybe_fire(w, force=True)
    assert fired is not None, "warming audience + force should fire"
    # Floor state stamped.
    fs = w.current_floor.state
    assert fs.get("director_event_count") == 1
    print(f"  director fires at warming (event={fired}): OK")


def test_show_director_per_floor_cap():
    from ..engine import show_director as _sd
    w, _r = _mk_world(audience=60)
    fs = w.current_floor.state = {}
    fs["director_event_count"] = 99
    fired = _sd.maybe_fire(w, force=True)
    assert fired is None
    print("  director respects per-floor cap: OK")


def test_show_director_cooldown_between_events():
    from ..engine import show_director as _sd
    w, _r = _mk_world(audience=60)
    # First fire goes through.
    a = _sd.maybe_fire(w, force=True)
    # Second fire immediately after — cooldown should block (0 minutes
    # elapsed < 8 minute minimum).
    b = _sd.maybe_fire(w, force=True)
    assert a is not None
    assert b is None, "second fire within cooldown should noop"
    # Advance the clock past cooldown.
    w.current_floor.current_minute += 10
    c = _sd.maybe_fire(w, force=True)
    assert c is not None
    print("  director cooldown gates repeat fires: OK")


# ── proxy_wars ───────────────────────────────────────────────────────────

def test_proxy_wars_noop_one_hot():
    from ..engine import proxy_wars as _pw
    from ..engine import sponsors as _sp
    w, _r = _mk_world(audience=60)
    _sp.adjust_attention(w, "novachem_biotech", 6)
    pair = _pw.maybe_fire(w)
    assert pair is None
    print("  proxy_wars silent with only one HOT sponsor: OK")


def test_proxy_wars_fires_with_two_hot():
    from ..engine import proxy_wars as _pw
    from ..engine import sponsors as _sp
    w, _r = _mk_world(audience=60)
    _sp.adjust_attention(w, "novachem_biotech", 8)
    _sp.adjust_attention(w, "kanal_7_krawedz", 6)
    pair = _pw.maybe_fire(w)
    assert pair is not None
    aggressor, rival = pair
    # Aggressor was the higher-attention one.
    assert aggressor == "novachem_biotech"
    assert rival == "kanal_7_krawedz"
    # Floor state stamped.
    assert w.current_floor.state.get("proxy_war_event_count") == 1
    print(f"  proxy_war fires: {aggressor} vs {rival}: OK")


def test_proxy_wars_per_pair_cooldown():
    from ..engine import proxy_wars as _pw
    from ..engine import sponsors as _sp
    w, _r = _mk_world(audience=60)
    _sp.adjust_attention(w, "novachem_biotech", 8)
    _sp.adjust_attention(w, "kanal_7_krawedz", 7)
    a = _pw.maybe_fire(w)
    # Re-fire immediately — cooldown should block this pair.
    b = _pw.maybe_fire(w)
    assert a is not None
    assert b is None
    # Advance past cooldown.
    w.current_floor.current_minute += 65
    # Re-pump attention since fire took +1/-1.
    _sp.adjust_attention(w, "novachem_biotech", 5)
    _sp.adjust_attention(w, "kanal_7_krawedz", 5)
    c = _pw.maybe_fire(w)
    assert c is not None, "should re-fire after cooldown elapsed"
    print("  proxy_war per-pair cooldown: OK")


# ── celebrities ─────────────────────────────────────────────────────────

def test_celebrities_catalog_size_and_gating():
    from ..content.data import celebrities as _cel
    keys = _cel.all_celebrity_keys()
    assert len(keys) >= 6, f"expected >= 6 celebrities, got {len(keys)}"
    # Each entry has gating + fan_following.
    for k in keys:
        d = _cel.get(k)
        assert d["floor_min"] >= 1
        assert d["floor_max"] is None or d["floor_max"] >= d["floor_min"]
        assert d["fan_following"], f"{k} missing fan_following"
        assert "celebrity" in (d.get("tags") or [])
    # for_floor filters correctly.
    f3 = [d["key"] for d in _cel.for_floor(3)]
    f15 = [d["key"] for d in _cel.for_floor(15)]
    # Pulkownik Recykling is floor 3-10, must be in f3 not f15.
    assert "pulkownik_recykling" in f3
    assert "pulkownik_recykling" not in f15
    print(f"  {len(keys)} celebrities, gating + filter OK")


# ── vending machine ─────────────────────────────────────────────────────

def test_vending_machine_use_dispenses_item():
    from ..engine.game import Game
    w, r = _mk_world(audience=30)
    g = Game(screen=None); g.world = w; g.state = "play"
    vm = Entity(key="vending_machine", entity_type=T_OBJECT,
                fallback_name="automat sponsorski",
                tags=["machine", "container"],
                affordances=["inspect", "use", "force", "salvage"],
                location_id="r0")
    w.register(vm); r.entities.append(vm)
    pre_inv = len(w.character.inventory_ids)
    pre_cr = w.character.credits
    g.submit_generated_command("użyj automat")
    post_inv = len(w.character.inventory_ids)
    assert post_inv == pre_inv + 1, f"item not added: {pre_inv}→{post_inv}"
    assert w.character.credits == pre_cr - 1, \
        f"credit not spent: {pre_cr}→{w.character.credits}"
    # Last item should carry vending_loot tag.
    new_id = w.character.inventory_ids[-1]
    new_item = w.get(new_id)
    assert "vending_loot" in (new_item.tags or [])
    print(f"  vending dispense: +1 item ({new_item.display_name()}), "
          f"-1 kr: OK")


def test_vending_machine_single_use():
    from ..engine.game import Game
    w, r = _mk_world(audience=30)
    g = Game(screen=None); g.world = w; g.state = "play"
    vm = Entity(key="vending_machine", entity_type=T_OBJECT,
                fallback_name="automat sponsorski",
                tags=["machine"],
                affordances=["inspect", "use"], location_id="r0")
    w.register(vm); r.entities.append(vm)
    g.submit_generated_command("użyj automat")
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("użyj automat")
    # Second use should NOT add another item.
    assert len(w.character.inventory_ids) == pre_inv, \
        "vending should be single-use per machine"
    assert (vm.state or {}).get("vending_used") is True
    print("  vending single-use per machine: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_show_director_catalog_shape()
    test_show_director_cold_audience_noop()
    test_show_director_fires_at_warming()
    test_show_director_per_floor_cap()
    test_show_director_cooldown_between_events()
    test_proxy_wars_noop_one_hot()
    test_proxy_wars_fires_with_two_hot()
    test_proxy_wars_per_pair_cooldown()
    test_celebrities_catalog_size_and_gating()
    test_vending_machine_use_dispenses_item()
    test_vending_machine_single_use()
    print("Prompt 29.18 DCC flavor smoke: OK")


if __name__ == "__main__":
    main()
