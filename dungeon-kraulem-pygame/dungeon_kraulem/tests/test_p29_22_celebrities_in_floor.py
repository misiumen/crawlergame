"""Prompt 29.22 — Celebrity placement smoke suite.

Audit finding: content/data/celebrities.py shipped 6 named NPCs but
floor_generator.py never read the catalog. Pure content rot. P29.22
hooks _place_celebrity into generate_floor at 25% per-floor chance,
and consequences.py emits the intro + side effects on first room
entry.

Covers:
  * _place_celebrity injects an entity tagged "celebrity" with
    state["celebrity_intro_pending"]=True when an eligible celeb
    exists.
  * Already-met celebrities (character.flags["celeb_met_<key>"]
    set) are NOT re-placed.
  * _fire_celebrity_intros runs once: stamps the flag, clears the
    pending state, bumps audience, adjusts sponsor attention.
  * Picker respects floor_min/floor_max gates from the catalog.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=10)
    return w


def _mk_floor_with_rooms(n_rooms=3, floor_num=5):
    f = FloorState(floor_id="f1", floor_number=floor_num)
    for i in range(n_rooms):
        r = RoomState(room_id=f"r{i}",
                      fallback_short_title=f"Pokój {i}",
                      actual_type="social")
        f.add_room(r)
    f.start_room_id = "r0"
    f.current_room_id = "r0"
    return f


# ── Placement ────────────────────────────────────────────────────────────

def test_place_celebrity_injects_entity():
    from ..engine.floor_generator import _place_celebrity
    import random as _r
    w = _mk_world()
    w.current_floor = _mk_floor_with_rooms(floor_num=5)
    rng = _r.Random(42)
    _place_celebrity(w.current_floor, rng, world=w)
    # At floor 5 eligible: Pulkownik Recykling (3-10), Bóstwo Pamięci
    # (5-14), Biegacz Tora (2-8). One of them should land in a non-
    # start room.
    placed = []
    for room in w.current_floor.rooms.values():
        for ent in room.entities:
            if "celebrity" in (ent.tags or []):
                placed.append(ent)
    assert len(placed) == 1, \
        f"expected exactly 1 celebrity, got {len(placed)}"
    ent = placed[0]
    assert (ent.state or {}).get("celebrity_intro_pending") is True
    assert ent.location_id != "r0", "celebrity should NOT be in start room"
    print(f"  _place_celebrity placed {ent.fallback_name} in "
          f"{ent.location_id}: OK")


def test_already_met_celebrity_not_replaced():
    from ..engine.floor_generator import _place_celebrity
    import random as _r
    w = _mk_world()
    # Pre-mark every floor-5-eligible celeb as met.
    w.character.flags = {
        f"celeb_met_{k}": True
        for k in ("pulkownik_recykling", "bostwo_pamieci",
                  "biegacz_tora", "mrok_kanal7")
    }
    w.current_floor = _mk_floor_with_rooms(floor_num=5)
    rng = _r.Random(1)
    _place_celebrity(w.current_floor, rng, world=w)
    placed = [e for r in w.current_floor.rooms.values()
              for e in r.entities if "celebrity" in (e.tags or [])]
    assert len(placed) == 0, \
        f"all eligible celebs already met — none should place: got {placed}"
    print("  already-met celebrities not re-placed: OK")


def test_placement_respects_floor_gates():
    """At floor 17 only Doktor Polimer (10-16) is OUT of range;
    Bankier Serca (6-14) is also out; mrok_kanal7 (4-12) out;
    nothing eligible. Picker should silently no-op."""
    from ..engine.floor_generator import _place_celebrity
    import random as _r
    w = _mk_world()
    w.current_floor = _mk_floor_with_rooms(floor_num=17)
    rng = _r.Random(2)
    _place_celebrity(w.current_floor, rng, world=w)
    placed = [e for r in w.current_floor.rooms.values()
              for e in r.entities if "celebrity" in (e.tags or [])]
    # All celebs have floor_max <= 16, so floor 17 should have none.
    assert len(placed) == 0, \
        f"no celeb eligible for floor 17 but got: {placed}"
    print("  floor-gate filter rejects out-of-range floors: OK")


# ── First-encounter side effects ────────────────────────────────────────

def test_fire_celebrity_intros_runs_once():
    """When player enters a room containing a pending celebrity,
    _fire_celebrity_intros should: emit the intro line, bump
    audience by notoriety_boost, adjust fan_following sponsor +2,
    stamp the met-flag, clear pending."""
    from ..engine.consequences import _fire_celebrity_intros
    from ..engine.entity import Entity, T_NPC
    from ..engine import sponsors as _sp
    w = _mk_world()
    w.current_floor = _mk_floor_with_rooms()
    room = w.current_floor.rooms["r0"]
    # Synthesize a celebrity entity.
    pre_aud = w.character.audience_rating
    pre_att = _sp.get_attention(w, "kult_recyklingu")
    ent = Entity(
        key="pulkownik_recykling",
        entity_type=T_NPC,
        fallback_name="Pułkownik Recykling",
        tags=["celebrity", "recykling"],
        location_id="r0",
        state={
            "celebrity_intro_pending": True,
            "celebrity_data": {
                "fan_following": "kult_recyklingu",
                "notoriety_boost": 5,
                "intro": "Pułkownik Recykling salutuje.",
            },
        },
    )
    w.register(ent)
    room.entities.append(ent)
    lines = []
    _fire_celebrity_intros(w, room, lines)
    # Intro line emitted.
    assert any("Recykling" in ln for ln in lines), \
        f"intro line missing: {lines}"
    # Audience bumped by 5.
    assert w.character.audience_rating == pre_aud + 5
    # Sponsor attention bumped by 2.
    assert _sp.get_attention(w, "kult_recyklingu") == pre_att + 2
    # Flag stamped.
    assert w.character.flags.get("celeb_met_pulkownik_recykling") is True
    # Pending cleared.
    assert ent.state["celebrity_intro_pending"] is False
    print(f"  first-encounter side effects fire once: OK "
          f"(audience +{w.character.audience_rating - pre_aud}, "
          f"sponsor +2)")


def test_fire_celebrity_intros_idempotent_after_first():
    """Second call to _fire_celebrity_intros for the same room should
    be a no-op (the pending flag is cleared)."""
    from ..engine.consequences import _fire_celebrity_intros
    from ..engine.entity import Entity, T_NPC
    w = _mk_world()
    w.current_floor = _mk_floor_with_rooms()
    room = w.current_floor.rooms["r0"]
    ent = Entity(
        key="biegacz_tora", entity_type=T_NPC,
        fallback_name="Biegacz Tora",
        tags=["celebrity"], location_id="r0",
        state={"celebrity_intro_pending": True,
               "celebrity_data": {"fan_following": "",
                                  "notoriety_boost": 4, "intro": "Biegnie."}},
    )
    w.register(ent); room.entities.append(ent)
    lines1 = []
    _fire_celebrity_intros(w, room, lines1)
    lines2 = []
    _fire_celebrity_intros(w, room, lines2)
    assert lines1 and not lines2, \
        f"second call should emit nothing; got lines2={lines2}"
    print("  second-call idempotent (no double intro): OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_place_celebrity_injects_entity()
    test_already_met_celebrity_not_replaced()
    test_placement_respects_floor_gates()
    test_fire_celebrity_intros_runs_once()
    test_fire_celebrity_intros_idempotent_after_first()
    print("Prompt 29.22 celebrities in floor smoke: OK")


if __name__ == "__main__":
    main()
