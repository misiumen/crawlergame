"""Prompt 27.9 — consume + content smoke suite.

Covers:
  * `skonsumuj batonik` heals + removes item
  * `zjedz X` / `wypij X` / `eat X` / `drink X` all route to consume
  * Coffee clears `afraid` status
  * Dirty bandage clears `bleeding`
  * Medic heal_multiplier doubles consume heal
  * Non-food item refused
  * Item not in inventory refused gracefully
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import parser_core as _pc
from ..content.items import make_item
from ..systems import classes as _cls


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Klinika")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def _give(w, key):
    it = make_item(key, location_id="inventory:player")
    w.register(it)
    w.character.inventory_ids.append(it.entity_id)
    return it


# ── Parser routing ───────────────────────────────────────────────────────

def test_parser_routes_consume_synonyms():
    for verb in ("skonsumuj", "zjedz", "wypij", "eat", "drink"):
        i = _pc.parse(f"{verb} batonik", world=None)
        assert i.intent == "consume", f"{verb}: got {i.intent}"
        assert i.targets and "baton" in i.targets[0]
    print("  parser: skonsumuj/zjedz/wypij/eat/drink → consume: OK")


# ── Snack bar ────────────────────────────────────────────────────────────

def test_snack_bar_heals_and_removes():
    from ..engine.game import Game
    w = _mk_world()
    _give(w, "snack_bar")
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.hp = 50
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("zjedz batonik")
    assert w.character.hp > 50, f"hp should increase: {w.character.hp}"
    assert len(w.character.inventory_ids) < pre_inv, "snack should be consumed"
    print(f"  snack_bar: hp 50→{w.character.hp}, item removed: OK")


# ── Coffee ───────────────────────────────────────────────────────────────

def test_coffee_clears_afraid():
    from ..engine.game import Game
    w = _mk_world()
    _give(w, "coffee")
    w.character.conditions.append("afraid")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("wypij coffee")
    assert "afraid" not in w.character.conditions, "afraid should clear"
    print("  coffee clears afraid: OK")


# ── Bandage ──────────────────────────────────────────────────────────────

def test_bandage_clears_bleeding():
    from ..engine.game import Game
    w = _mk_world()
    _give(w, "dirty_bandage")
    w.character.conditions.append("bleeding")
    w.character.hp = 60
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("skonsumuj bandaż")
    assert "bleeding" not in w.character.conditions
    assert w.character.hp > 60
    print(f"  dirty_bandage clears bleeding + heals: OK ({w.character.hp})")


# ── Class multiplier ─────────────────────────────────────────────────────

def test_medic_doubles_consume_heal():
    from ..engine.game import Game
    w = _mk_world()
    _cls.assign_class(w, "medic")  # heal_mul = 1 → ×2
    _give(w, "snack_bar")
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.hp = 50
    g.submit_generated_command("zjedz batonik")
    gained = w.character.hp - 50
    # snack_bar base 12 × 2 = 24 (with possible cap clamp).
    assert gained >= 20, f"medic should heal ≥20 from snack; got {gained}"
    print(f"  medic ×2 heal from snack: +{gained} HP: OK")


# ── Refusals ─────────────────────────────────────────────────────────────

def test_non_food_refused():
    from ..engine.game import Game
    w = _mk_world()
    _give(w, "duct_tape")   # not food
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("zjedz taśmę")
    assert len(w.character.inventory_ids) == pre_inv, "duct_tape should not be consumed"
    txt = "\n".join(s for s, _ in w.log[-3:]).lower()
    assert "jadalne" in txt or "nie masz" in txt
    print("  non-food refused: OK")


def test_missing_item_refused():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zjedz pierogi")
    txt = "\n".join(s for s, _ in w.log[-3:]).lower()
    assert "nie masz" in txt or "jadalne" in txt
    print("  missing item refused: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_parser_routes_consume_synonyms()
    test_snack_bar_heals_and_removes()
    test_coffee_clears_afraid()
    test_bandage_clears_bleeding()
    test_medic_doubles_consume_heal()
    test_non_food_refused()
    test_missing_item_refused()
    print("Prompt 27.9 consume + content smoke: OK")


if __name__ == "__main__":
    main()
