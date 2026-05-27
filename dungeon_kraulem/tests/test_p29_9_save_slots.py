"""Prompt 29.9 — three-slot save system smoke suite.

Audit finding: a single save file meant New Game overwrote everything,
and P29.8 permadeath wiped that single file. Three slots make
permadeath shippable: lose slot 0, keep tinkering on slots 1 + 2.

Covers:
  * save_to_slot / load_from_slot round-trip per slot.
  * exists_slot / delete_slot scoped per slot.
  * Active slot pointer governs the back-compat save()/load() API.
  * peek_slot returns a non-rehydrated preview dict.
  * Legacy single-file save migrates into slot 0 on first read.
  * delete() (post-death wipe) hits ACTIVE slot only — other slots
    untouched.
  * Empty slot peek returns None.
"""
from __future__ import annotations
import os, json, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine import save_load
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world(name="Igor", floor=2, audience=12, hp=50, hp_max=100):
    w = WorldState()
    w.character = Character(name=name, background="janitor",
                            max_hp=hp_max, hp=hp, audience_rating=audience)
    f = FloorState(floor_id="f1", floor_number=floor)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def _wipe_all():
    # Defensive: also pin active slot back to 0 so subsequent tests
    # start from a known state.
    save_load.set_active_slot(0)
    save_load.delete_all()


# ── Per-slot round-trip ───────────────────────────────────────────────────

def test_save_to_slot_round_trip():
    _wipe_all()
    w0 = _mk_world(name="Slot0", floor=1, audience=3)
    w1 = _mk_world(name="Slot1", floor=5, audience=27)
    assert save_load.save_to_slot(w0, 0) is True
    assert save_load.save_to_slot(w1, 1) is True
    assert save_load.exists_slot(0)
    assert save_load.exists_slot(1)
    assert not save_load.exists_slot(2)
    r0 = save_load.load_from_slot(0)
    r1 = save_load.load_from_slot(1)
    assert r0.character.name == "Slot0"
    assert r1.character.name == "Slot1"
    assert r1.current_floor.floor_number == 5
    print("  save_to_slot / load_from_slot round-trip: OK")


# ── Active slot pointer ───────────────────────────────────────────────────

def test_active_slot_routes_back_compat_api():
    _wipe_all()
    save_load.set_active_slot(2)
    w = _mk_world(name="ActiveSlot", floor=3)
    save_load.save(w)   # back-compat API → writes slot 2
    assert save_load.exists_slot(2)
    assert not save_load.exists_slot(0)
    r = save_load.load()  # back-compat → reads slot 2
    assert r is not None and r.character.name == "ActiveSlot"
    print("  set_active_slot routes save()/load() to right slot: OK")


# ── peek_slot ────────────────────────────────────────────────────────────

def test_peek_slot_returns_preview():
    _wipe_all()
    w = _mk_world(name="Peek", floor=7, audience=42, hp=80, hp_max=100)
    save_load.save_to_slot(w, 1)
    p0 = save_load.peek_slot(0)
    p1 = save_load.peek_slot(1)
    assert p0 is None
    assert p1 is not None
    assert p1["name"] == "Peek"
    assert p1["floor"] == 7
    assert p1["audience"] == 42
    assert p1["hp"] == 80 and p1["hp_max"] == 100
    assert p1["dead"] is False
    print(f"  peek_slot: OK ({p1['name']} @ floor {p1['floor']})")


def test_peek_dead_character_flagged():
    _wipe_all()
    w = _mk_world(name="Dead", hp=0)
    save_load.save_to_slot(w, 0)
    p = save_load.peek_slot(0)
    assert p["dead"] is True
    print("  peek_slot.dead=True when HP<=0: OK")


# ── delete() (post-death wipe) is scoped to active slot ─────────────────

def test_delete_only_wipes_active_slot():
    _wipe_all()
    w0 = _mk_world(name="Survives", floor=1)
    w1 = _mk_world(name="Survives2", floor=2)
    w2 = _mk_world(name="Wiped", floor=8)
    save_load.save_to_slot(w0, 0)
    save_load.save_to_slot(w1, 1)
    save_load.save_to_slot(w2, 2)
    save_load.set_active_slot(2)
    save_load.delete()   # back-compat delete — should hit slot 2 only
    assert save_load.exists_slot(0)
    assert save_load.exists_slot(1)
    assert not save_load.exists_slot(2)
    print("  delete() scoped to active slot (P29.8 death wipe safe): OK")


# ── list_slots ───────────────────────────────────────────────────────────

def test_list_slots_returns_three_entries():
    _wipe_all()
    w = _mk_world(name="One")
    save_load.save_to_slot(w, 1)
    listed = save_load.list_slots()
    assert len(listed) == 3
    assert listed[0] is None
    assert listed[1]["name"] == "One"
    assert listed[2] is None
    print("  list_slots returns 3 entries (None for empty): OK")


# ── Legacy migration ─────────────────────────────────────────────────────

def test_legacy_save_migrates_to_slot_0():
    _wipe_all()
    # Write a legacy single-file save manually.
    w = _mk_world(name="LegacyHero", floor=3)
    data = w.to_dict()
    data["version"] = save_load.SAVE_VERSION
    legacy = save_load.LEGACY_SAVE_FILE_NEW
    with open(legacy, "w", encoding="utf-8") as f:
        json.dump(data, f)
    assert os.path.exists(legacy)
    # First peek/load triggers migration.
    p = save_load.peek_slot(0)
    assert p is not None and p["name"] == "LegacyHero"
    assert not os.path.exists(legacy), "legacy file should be removed after migration"
    assert save_load.exists_slot(0)
    print("  legacy single-file save migrates to slot 0: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    _wipe_all()
    try:
        test_save_to_slot_round_trip()
        test_active_slot_routes_back_compat_api()
        test_peek_slot_returns_preview()
        test_peek_dead_character_flagged()
        test_delete_only_wipes_active_slot()
        test_list_slots_returns_three_entries()
        test_legacy_save_migrates_to_slot_0()
    finally:
        _wipe_all()
    print("Prompt 29.9 save-slots smoke: OK")


if __name__ == "__main__":
    main()
