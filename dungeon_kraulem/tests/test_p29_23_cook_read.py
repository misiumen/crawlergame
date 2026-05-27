"""Prompt 29.23 — Cooking + reading verbs smoke suite.

Audit finding: natural Polish verbs `gotuj` and `czytaj` didn't
parse. The Kucharz background gave a knife with no cookable path;
lore-tagged items had nowhere to surface their text.

Covers:
  * parser routes gotuj/piecz/smaż/cook → cook intent.
  * parser routes czytaj/przeczytaj/read → read intent.
  * cook with raw meat + wood produces a cooked_meat entity in
    inventory.
  * cook without meat refuses cleanly.
  * cook without wood refuses cleanly.
  * cook critical-failure damages player.
  * read on a lore-tagged item surfaces fallback_desc.
  * read on a non-lore item refuses politely.
  * read with no target refuses with syntax hint.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_ITEM, T_OBJECT
from ..engine.parser_core import parse


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="cook")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Parser ──────────────────────────────────────────────────────────────

def test_parser_cook_variants():
    for cmd in ("gotuj mięso", "piecz", "smaż mięso", "cook"):
        i = parse(cmd)
        assert i.intent == "cook", f"{cmd!r} → {i.intent}"
    print("  parser: gotuj/piecz/smaż/cook → cook intent: OK")


def test_parser_read_variants():
    for cmd in ("czytaj notatkę", "przeczytaj plakat", "read"):
        i = parse(cmd)
        assert i.intent == "read", f"{cmd!r} → {i.intent}"
    print("  parser: czytaj/przeczytaj/read → read intent: OK")


# ── Cook ────────────────────────────────────────────────────────────────

def test_cook_produces_cooked_meat():
    from ..engine.game import Game
    import random as _r
    w, _r2 = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    # Stash materials.
    w.character.materials = {"meat_chunk": 2, "wood_fragments": 2}
    w.character.stats["WIS"] = 15  # high WIS → bias toward success
    _r.seed(3)
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("gotuj")
    post_inv = len(w.character.inventory_ids)
    assert post_inv == pre_inv + 1, \
        f"cooked_meat not added: {pre_inv}→{post_inv}"
    # Item should be tagged food.
    new = w.get(w.character.inventory_ids[-1])
    assert new.key == "cooked_meat"
    assert "food" in (new.tags or [])
    # Materials consumed.
    assert w.character.materials["meat_chunk"] == 1
    assert w.character.materials["wood_fragments"] == 1
    print(f"  gotuj → {new.display_name()} in inventory, "
          f"materials -1 each: OK")


def test_cook_no_meat_refuses():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.materials = {"wood_fragments": 3}
    pre = len(w.character.inventory_ids)
    g.submit_generated_command("gotuj")
    post = len(w.character.inventory_ids)
    assert pre == post, "no meat → no item produced"
    # Materials NOT consumed.
    assert w.character.materials["wood_fragments"] == 3
    print("  gotuj without meat: refuses, no consumption: OK")


def test_cook_no_wood_refuses():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.materials = {"meat_chunk": 2}
    pre = len(w.character.inventory_ids)
    g.submit_generated_command("gotuj")
    post = len(w.character.inventory_ids)
    assert pre == post
    # Meat NOT consumed when wood is missing.
    assert w.character.materials["meat_chunk"] == 2
    print("  gotuj without wood: refuses, no consumption: OK")


def test_cook_critical_fail_damages_player():
    from ..engine.game import Game
    import dungeon_kraulem.engine.utils_compat as _uc
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.materials = {"meat_chunk": 1, "wood_fragments": 1}
    w.character.stats["WIS"] = 1  # awful
    pre_hp = w.character.hp
    # Force critical failure via roll_d20 = 1.
    orig = _uc.roll_d20
    _uc.roll_d20 = lambda: 1
    try:
        g.submit_generated_command("gotuj")
    finally:
        _uc.roll_d20 = orig
    assert w.character.hp < pre_hp, \
        f"crit-fail should damage; HP {pre_hp}→{w.character.hp}"
    # Materials still consumed (you wasted them).
    assert w.character.materials["meat_chunk"] == 0
    print(f"  gotuj crit-fail damages player ({pre_hp}→{w.character.hp}): OK")


# ── Read ────────────────────────────────────────────────────────────────

def test_read_surfaces_lore_text():
    from ..engine.game import Game
    w, r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    note = Entity(
        key="syndic_memo", entity_type=T_ITEM,
        fallback_name="notatka syndykatu",
        fallback_desc="Wewnętrzna instrukcja: nie czytać poza protokołem.",
        tags=["lore", "readable", "paper"],
        affordances=["inspect", "use"],
        location_id="inventory:player",
        portable=True,
    )
    w.register(note); w.character.inventory_ids.append(note.entity_id)
    pre = len(w.log)
    g.submit_generated_command("czytaj notatka")
    post = w.log[-1][0] if isinstance(w.log[-1], tuple) else str(w.log[-1])
    assert "Wewnętrzna" in post or "notatka syndykatu" in post, \
        f"lore text not surfaced: {post}"
    print(f"  czytaj surfaces lore: OK")


def test_read_non_lore_item_refuses():
    from ..engine.game import Game
    w, r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    # An item with no lore/readable/paper tag.
    rock = Entity(
        key="rock", entity_type=T_OBJECT,
        fallback_name="kamień",
        tags=["heavy"],
        affordances=["inspect"], location_id="r0",
    )
    w.register(rock); r.entities.append(rock)
    pre = len(w.log)
    g.submit_generated_command("czytaj kamień")
    text = w.log[-1][0] if isinstance(w.log[-1], tuple) else str(w.log[-1])
    assert "nic" in text.lower() or "nie ma" in text.lower(), \
        f"unreadable refusal missing: {text}"
    print("  czytaj on non-lore: refuses politely: OK")


def test_read_no_target_refuses():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("czytaj")
    last = w.log[-1][0] if isinstance(w.log[-1], tuple) else str(w.log[-1])
    assert "Co" in last or "spróbuj" in last.lower(), \
        f"no-target hint missing: {last}"
    print("  czytaj without target: hints syntax: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_parser_cook_variants()
    test_parser_read_variants()
    test_cook_produces_cooked_meat()
    test_cook_no_meat_refuses()
    test_cook_no_wood_refuses()
    test_cook_critical_fail_damages_player()
    test_read_surfaces_lore_text()
    test_read_non_lore_item_refuses()
    test_read_no_target_refuses()
    print("Prompt 29.23 cook + read smoke: OK")


if __name__ == "__main__":
    main()
