"""Prompt 29.11 — Floors 7-18 procedural content smoke suite.

Audit finding: room_pool had zero floor_min >= 7 templates and the
generator silently fell back to "Pomieszczenie (boss)" stubs past
floor 6. New content: 4 thematic bands (UNDERGROUND / FUNGAL_BLOOM /
MACHINE_CHURCH / HELLFLOOR) with 2-3 rooms + 1 boss each, plus 12
new monster keys spanning floors 7-18.

Covers:
  * Every new monster template loads + has scaled HP/damage.
  * Boss roster includes the four new floor bosses.
  * Room pool exposes deep-floor templates at the right floor bands.
  * generate_floor(floor_number=N) for N in {7,9,12,15,18} produces
    a non-stub floor with rooms drawn from the right templates.
  * Final floor 18 includes the final boss room template.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data.entity_templates import MON
from ..content.data.room_pool import ROOM_POOL


# ── Monster templates load ───────────────────────────────────────────────

def test_new_deep_floor_monsters_exist():
    new_keys = [
        "kanal_widmo", "mokry_kolega", "boss_burmistrz_kanalow",
        "kwiat_padliny", "zarodnikowiec", "boss_matka_zarodników",
        "kantor_pamieci", "diakon_korpo", "boss_proboszcz_korpo",
        "windykator_ostateczny", "anti_host_lite",
        "boss_prezes_syndykatu",
    ]
    missing = [k for k in new_keys if k not in MON]
    assert not missing, f"missing monster templates: {missing}"
    print(f"  {len(new_keys)} new deep-floor monsters in MON: OK")


def test_final_boss_has_endgame_stats():
    prezes = MON["boss_prezes_syndykatu"]
    # Post _apply_balance_scale: HP × 5, damage_dice mutated.
    assert prezes["hp"] >= 400, f"final boss HP too low: {prezes['hp']}"
    assert "final_boss" in (prezes.get("tags") or [])
    assert prezes.get("floor_min") == 18 and prezes.get("floor_max") == 18
    print(f"  final boss stats: HP={prezes['hp']}, AC={prezes['ac']}: OK")


def test_floor_min_max_bands():
    """Each deep-floor monster should be tagged with the band it
    inhabits — not a hard test, but a tripwire for accidentally
    mis-banded entries."""
    bands = {
        "kanal_widmo":            (7, 9),
        "kwiat_padliny":          (10, 12),
        "kantor_pamieci":         (13, 15),
        "windykator_ostateczny":  (16, 18),
    }
    for key, (lo, hi) in bands.items():
        m = MON[key]
        assert m.get("floor_min") == lo, f"{key} floor_min: {m.get('floor_min')}"
        assert m.get("floor_max") == hi, f"{key} floor_max: {m.get('floor_max')}"
    print("  band gating consistent: OK")


# ── Room pool ────────────────────────────────────────────────────────────

def test_room_pool_covers_floors_7_to_18():
    """For each band, at least one room template with role=filler
    and one with role=boss must exist at the boss-tier floor."""
    bands = [(7, 9, "boss_burmistrz_kanalow"),
             (10, 12, "boss_matka_zarodników"),
             (13, 15, "boss_proboszcz_korpo"),
             (16, 18, "boss_prezes_syndykatu")]
    for lo, hi, boss_key in bands:
        # Filler rooms in band.
        fillers = [t for t in ROOM_POOL
                   if t.get("role") in ("filler", "danger")
                   and (t.get("floor_min") or 1) <= hi
                   and (t.get("floor_max") or 99) >= lo
                   and (t.get("floor_min") or 1) >= lo]
        assert fillers, f"no filler/danger templates for floors {lo}-{hi}"
        # Boss room at top of band.
        bosses = [t for t in ROOM_POOL
                  if t.get("role") == "boss"
                  and (t.get("floor_min") or 1) <= hi
                  and (t.get("floor_max") or 99) >= hi
                  and boss_key in (t.get("entity_seed_pools") or {}).get("mon", [])]
        assert bosses, f"no boss room for floor {hi} with key={boss_key}"
    print("  4 bands each have filler + boss rooms: OK")


def test_final_floor_18_has_final_boss_room():
    finals = [t for t in ROOM_POOL
              if t.get("floor_min") == 18 and t.get("role") == "boss"]
    assert finals, "no floor 18 boss room template"
    assert any("boss_prezes_syndykatu" in (t.get("entity_seed_pools") or {})
                                          .get("mon", []) for t in finals)
    print("  floor 18 has Prezes boss room: OK")


# ── Generator end-to-end ────────────────────────────────────────────────

def test_generate_floor_deep_returns_non_stub():
    """Deep floors must build without crashing AND produce real rooms
    (not the 'fallback' / stub template). The actual mob mix is
    weighted-random so we don't pin specific keys — we just assert
    the pipeline runs and yields something with content."""
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="Test")
    for fnum in (7, 9, 12, 15, 18):
        floor = generate_floor(w, floor_number=fnum, seed=100 + fnum)
        assert floor is not None, f"floor {fnum} build failed"
        rooms = list(getattr(floor, "rooms", {}).values()) if hasattr(floor, "rooms") else []
        if not rooms:
            rooms = [floor.current_room()] if hasattr(floor, "current_room") else []
        assert len(rooms) >= 1, f"floor {fnum} has no rooms"
        # No room template_id should be a 'fallback_<role>' (means
        # the picker returned None and the generator stubbed in
        # something to avoid a crash — that's the regression we
        # explicitly want to catch).
        stub_rooms = [r for r in rooms
                      if (getattr(r, "template_id", "") or "")
                      .startswith("fallback_")]
        assert not stub_rooms, \
            f"floor {fnum} has stub rooms: " \
            f"{[r.template_id for r in stub_rooms]}"
    print("  generate_floor(7-18) produces non-stub floors: OK")


def test_pick_template_gates_floor_max():
    """Floor-3 / floor-5 themed rooms must NOT be picked for floor 10+.
    Verify the picker filter by checking what comes back for several
    floor numbers."""
    from ..engine import floor_generator as _fg
    import random as _r
    # Pick 100 times for floor 12; nothing should have floor_max < 12.
    rng = _r.Random(7)
    for _ in range(100):
        t = _fg._pick_template_for_role("filler", rng, used=[], floor_num=12)
        if t is None:
            continue
        fmax = t.get("floor_max")
        assert fmax is None or fmax >= 12, \
            f"leaked: {t['template_id']} (floor_max={fmax}) on floor 12"
    print("  _pick_template_for_role respects floor_max: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_new_deep_floor_monsters_exist()
    test_final_boss_has_endgame_stats()
    test_floor_min_max_bands()
    test_room_pool_covers_floors_7_to_18()
    test_final_floor_18_has_final_boss_room()
    test_generate_floor_deep_returns_non_stub()
    test_pick_template_gates_floor_max()
    print("Prompt 29.11 deep-floor content smoke: OK")


if __name__ == "__main__":
    main()
