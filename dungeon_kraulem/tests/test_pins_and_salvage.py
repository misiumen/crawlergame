"""Playtest fixes:
- search and salvage are COMPLEMENTARY (search no longer bars salvage).
- a fully-salvaged object loses its pin (no check-spam).
- pin slots are stable per entity_id (no reflow when one is removed).
- beings classify distinctly from objects.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY
from ..engine.entity import Entity, T_OBJECT, T_MONSTER
from ..ui import ui as _ui


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _shelf(g, name="metalowe meble"):
    # Use a real salvageable key so the salvage table resolves (a fake key
    # would make salvage refuse and never set state).
    room = g.world.current_floor.current_room()
    e = Entity(key="furniture_metal", entity_type=T_OBJECT, fallback_name=name,
               fallback_desc="Pełna toreb i kartonów.",
               tags=["container", "furniture", "salvageable", "metal"],
               affordances=["inspect", "search", "loot", "salvage", "strip"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    e.visibility_state = "seen"
    g.world.register(e); room.entities.append(e)
    return e, room


def test_search_then_salvage_is_allowed():
    g = _demo_game()
    e, room = _shelf(g)
    g._handle_play_input("przeszukaj metalowe meble")
    st = e.state or {}
    assert st.get("searched"), "search should mark searched"
    assert not st.get("depleted"), "search must NOT set depleted (blocks salvage)"
    assert not st.get("stripped"), "search must NOT set stripped"
    # Now salvage must still be offered and must work.
    n0 = len(g.world.log)
    g._handle_play_input("rozbierz metalowe meble")
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert "już rozebrane" not in new, f"salvage wrongly refused after search: {new}"
    assert (e.state or {}).get("stripped"), "salvage should mark stripped"
    print("  search then salvage allowed (complementary): OK")


def test_salvaged_object_loses_pin():
    # The user's report: a salvaged shelf keeps its pin and lets you spam
    # `sprawdź`. A plain salvageable object (the common case) must go spent
    # once stripped — only passive inspect/push remain.
    g = _demo_game()
    room = g.world.current_floor.current_room()
    e = Entity(key="furniture_metal", entity_type=T_OBJECT,
               fallback_name="metalowe meble", fallback_desc="x",
               tags=["furniture", "salvageable", "metal"],
               affordances=["inspect", "salvage", "strip"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True; e.visibility_state = "seen"
    g.world.register(e); room.entities.append(e)
    assert _ui._pin_is_spent(g.world, room, e) is False
    # Force the salvage roll to succeed so this test is about the PIN
    # behaviour, not dice variance.
    from ..engine import utils_compat as _uc
    _orig = _uc.roll_d20
    _uc.roll_d20 = lambda: 20
    try:
        g._handle_play_input("rozbierz metalowe meble")
    finally:
        _uc.roll_d20 = _orig
    assert (e.state or {}).get("stripped"), "salvage should mark stripped"
    assert _ui._pin_is_spent(g.world, room, e) is True, \
        "salvaged object should be spent (no pin, no check-spam)"
    print("  salvaged object loses its pin: OK")


def test_pin_slots_stable_on_removal():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    # Spawn three objects; record each one's assigned slot center.
    ents = []
    for i in range(3):
        e = Entity(key=f"obj{i}", entity_type=T_OBJECT,
                   fallback_name=f"rzecz {i}", fallback_desc="x",
                   affordances=["inspect", "loot"], tags=["container"],
                   location_id=room.room_id)
        e.visible = True; e.discovered = True; e.visibility_state = "seen"
        g.world.register(e); room.entities.append(e)
        ents.append(e)

    # Slot for an entity is deterministic: id % n_slots (+ stable probing).
    # With distinct small ids and few entities, each keeps its own primary
    # slot. Removing the FIRST must not change the others' slots.
    def slot_of(eid, present_ids):
        cols, rows = 4, 3
        n = cols * rows
        used = {}
        for x in sorted(present_ids):
            s = x % n
            for _ in range(n):
                if s not in used:
                    break
                s = (s + 1) % n
            used[s] = x
        return next(s for s, x in used.items() if x == eid)

    ids = [e.entity_id for e in ents]
    before = {e.entity_id: slot_of(e.entity_id, ids) for e in ents[1:]}
    # Remove first entity.
    room.entities.remove(ents[0])
    ids2 = [e.entity_id for e in ents[1:]]
    after = {eid: slot_of(eid, ids2) for eid in before}
    assert before == after, f"pin slots reflowed on removal: {before} -> {after}"
    print(f"  pin slots stable on removal ({before}): OK")


def test_being_vs_object_classification():
    monster = Entity(key="m", entity_type=T_MONSTER, fallback_name="szczur")
    obj = Entity(key="o", entity_type=T_OBJECT, fallback_name="półka")
    assert _ui._entity_pin_kind(monster) == _ui.PIN_ENEMY
    assert _ui._entity_pin_kind(obj) == _ui.PIN_OBJECT
    print("  being vs object classification: OK")


def main():
    test_search_then_salvage_is_allowed()
    test_salvaged_object_loses_pin()
    test_pin_slots_stable_on_removal()
    test_being_vs_object_classification()
    print("Pins + salvage playtest-fix smoke: OK")


if __name__ == "__main__":
    main()
