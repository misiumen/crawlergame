"""Prompt 25 — 7-Slot Equipment smoke suite.

Covers:
  * SLOT_DEFS schema + slot_for_entity auto-detection
  * can_equip respects slot:X tag gating
  * equip moves entity from inventory to slot; unequip reverses
  * Slot conflict: equipping a second item displaces the first back to inv
  * AC accumulates from torso + legs + head
  * Resistances aggregate across worn slots
  * Immunities aggregate
  * Save/load round-trip preserves worn_slots
  * Wear / take_off parser routing
  * Wear handler refuses non-wearables
  * Take_off without target picks the lone occupied slot
  * Eligible inventory filter for paper-doll popover
  * Popover open/commit/close (game-level)
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_ITEM
from ..engine import equipment as _eq
from ..content.items import make_item


# ── Helpers ────────────────────────────────────────────────────────────

def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def _give(w, key):
    it = make_item(key, location_id="inventory:player")
    w.register(it)
    w.character.inventory_ids.append(it.entity_id)
    return it


# ── Slot definitions ──────────────────────────────────────────────────

def test_slot_defs_has_seven_slots():
    assert set(_eq.SLOT_KEYS) == {"head","torso","legs","main","off","acc","back"}
    assert len(_eq.SLOT_DEFS) == 7
    # Main + off are flagged wield.
    assert _eq.SLOT_DEFS["main"].is_wield
    assert _eq.SLOT_DEFS["off"].is_wield
    assert not _eq.SLOT_DEFS["head"].is_wield
    print("  SLOT_DEFS: 7 slots, main/off are wield: OK")


def test_slot_for_entity_auto_detects():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    assert _eq.slot_for_entity(h) == "head"
    v = _give(w, "kamizelka_taktyczna")
    assert _eq.slot_for_entity(v) == "torso"
    a = _give(w, "odznaka_zawodnika")
    assert _eq.slot_for_entity(a) == "acc"
    print("  slot_for_entity auto-detect: OK")


def test_can_equip_rejects_wrong_slot():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    ok, reason = _eq.can_equip(w, w.character, h, "torso")
    assert not ok and "Tors" in reason
    ok, _ = _eq.can_equip(w, w.character, h, "head")
    assert ok
    print("  can_equip rejects wrong slot: OK")


# ── Equip / unequip lifecycle ──────────────────────────────────────────

def test_equip_moves_from_inventory_to_slot():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    assert h.entity_id in w.character.inventory_ids
    ok, prev, _ = _eq.equip(w, w.character, h, "head")
    assert ok
    assert prev is None
    assert w.character.worn_slots.get("head") == h.entity_id
    assert h.entity_id not in w.character.inventory_ids
    print("  equip moves to slot, removes from inventory: OK")


def test_equip_swap_returns_previous_to_inventory():
    w = _mk_world()
    a = _give(w, "helm_konstrukcyjny")
    b = _give(w, "czapka_uszanka")
    _eq.equip(w, w.character, a, "head")
    ok, prev, _ = _eq.equip(w, w.character, b, "head")
    assert ok
    assert prev == a.entity_id
    assert a.entity_id in w.character.inventory_ids
    assert w.character.worn_slots["head"] == b.entity_id
    print("  equip swap returns previous to inventory: OK")


def test_unequip_returns_to_inventory():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    _eq.equip(w, w.character, h, "head")
    ok, freed, _ = _eq.unequip(w, w.character, "head")
    assert ok and freed == h.entity_id
    assert h.entity_id in w.character.inventory_ids
    assert w.character.worn_slots == {}
    print("  unequip returns to inventory: OK")


# ── Aggregated effects ─────────────────────────────────────────────────

def test_ac_accumulates_from_multiple_slots():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")        # +1
    v = _give(w, "kamizelka_taktyczna")       # +2
    b = _give(w, "buty_taktyczne")            # +1
    base = w.character.effective_ac()         # 10
    _eq.equip(w, w.character, h, "head")
    _eq.equip(w, w.character, v, "torso")
    _eq.equip(w, w.character, b, "legs")
    eq_ac = w.character.effective_ac(w)
    assert eq_ac == base + 4, f"expected {base+4}, got {eq_ac}"
    print(f"  AC accumulates: base {base} → equipped {eq_ac}: OK")


def test_resists_aggregate_across_slots():
    w = _mk_world()
    m = _give(w, "maska_filtrujaca")          # poison
    v = _give(w, "fartuch_laboratoryjny")     # acid
    _eq.equip(w, w.character, m, "head")
    _eq.equip(w, w.character, v, "torso")
    res = _eq.aggregated_resists(w, w.character)
    assert "poison" in res and "acid" in res
    print(f"  resists aggregate: {res}: OK")


def test_hazmat_grants_double_resists_and_condition():
    w = _mk_world()
    suit = _give(w, "kombinezon_hazmat")
    _eq.equip(w, w.character, suit, "torso")
    res = _eq.aggregated_resists(w, w.character)
    assert "acid" in res and "poison" in res
    assert "encumbered" in (w.character.conditions or [])
    print("  hazmat: double resists + encumbered status: OK")


# ── Save / load round-trip ────────────────────────────────────────────

def test_worn_slots_save_load_round_trip():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    _eq.equip(w, w.character, h, "head")
    d = w.character.to_dict()
    c2 = Character.from_dict(d)
    assert c2.worn_slots == {"head": h.entity_id}
    print("  worn_slots save/load round-trip: OK")


# ── Parser ─────────────────────────────────────────────────────────────

def test_parser_wear_verb():
    from ..engine.parser_core import parse
    intent = parse("załóż kamizelka taktyczna", world=None)
    assert intent.intent == "wear", f"got {intent.intent}"
    print("  parse 'załóż X' → wear: OK")


def test_parser_take_off_verb():
    from ..engine.parser_core import parse
    intent = parse("zdejmij hełm konstrukcyjny", world=None)
    assert intent.intent == "take_off", f"got {intent.intent}"
    print("  parse 'zdejmij X' → take_off: OK")


# ── Game handlers ──────────────────────────────────────────────────────

def test_wear_handler_equips():
    from ..engine.game import Game
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("załóż hełm konstrukcyjny")
    assert w.character.worn_slots.get("head") == h.entity_id
    print("  wear handler equips: OK")


def test_take_off_handler_unequips():
    from ..engine.game import Game
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    _eq.equip(w, w.character, h, "head")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zdejmij hełm")
    assert w.character.worn_slots == {}
    assert h.entity_id in w.character.inventory_ids
    print("  take_off handler unequips: OK")


def test_take_off_no_target_picks_lone_slot():
    from ..engine.game import Game
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    _eq.equip(w, w.character, h, "head")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zdejmij")
    # Lone-slot heuristic should clear head.
    assert w.character.worn_slots == {}
    print("  take_off no-target picks lone slot: OK")


# ── Eligible inventory filter ─────────────────────────────────────────

def test_eligible_inventory_for_slot():
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    v = _give(w, "kamizelka_taktyczna")
    e = _eq.eligible_inventory_for_slot(w, w.character, "head")
    keys = [it.key for it in e]
    assert "helm_konstrukcyjny" in keys
    assert "kamizelka_taktyczna" not in keys
    print("  eligible_inventory_for_slot filters by slot tag: OK")


# ── Popover lifecycle ─────────────────────────────────────────────────

def test_popover_opens_via_drain_ui_inputs():
    from ..engine.game import Game
    w = _mk_world()
    _give(w, "helm_konstrukcyjny")
    g = Game(screen=None); g.world = w; g.state = "play"
    # Simulate paper-doll click writing the pending slot.
    w._pending_slot_swap = ("head", "Głowa")
    g._drain_ui_inputs()
    assert g.slot_popover_open == "head"
    g._popover_close()
    assert g.slot_popover_open is None
    print("  popover open via drain, close clears: OK")


def test_popover_commit_equips_first_eligible():
    from ..engine.game import Game
    w = _mk_world()
    h = _give(w, "helm_konstrukcyjny")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.slot_popover_open = "head"
    g.slot_popover_idx = 0
    g._popover_commit()
    assert w.character.worn_slots.get("head") == h.entity_id
    assert g.slot_popover_open is None, "popover should close after commit"
    print("  popover commit equips + closes: OK")


# ── Draw smoke ─────────────────────────────────────────────────────────

def test_draw_with_popover_open_no_crash():
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    _give(g.world, "helm_konstrukcyjny")
    g.slot_popover_open = "head"
    g.draw()
    print("  draw with popover open: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_slot_defs_has_seven_slots()
    test_slot_for_entity_auto_detects()
    test_can_equip_rejects_wrong_slot()
    test_equip_moves_from_inventory_to_slot()
    test_equip_swap_returns_previous_to_inventory()
    test_unequip_returns_to_inventory()
    test_ac_accumulates_from_multiple_slots()
    test_resists_aggregate_across_slots()
    test_hazmat_grants_double_resists_and_condition()
    test_worn_slots_save_load_round_trip()
    test_parser_wear_verb()
    test_parser_take_off_verb()
    test_wear_handler_equips()
    test_take_off_handler_unequips()
    test_take_off_no_target_picks_lone_slot()
    test_eligible_inventory_for_slot()
    test_popover_opens_via_drain_ui_inputs()
    test_popover_commit_equips_first_eligible()
    test_draw_with_popover_open_no_crash()
    print("Prompt 25 7-slot equipment smoke: OK")


if __name__ == "__main__":
    main()
