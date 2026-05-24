"""Gap 8 (audit 06): save/load round-trip smoke test for the salvage/craft/deploy
pipeline. Run as `python -m revamp._smoke_audit_06`.

Asserts:
  - Materials inventory survives save/load.
  - Crafted item with damaged state survives save/load.
  - Deployed trap on a room survives save/load.
  - Safehouse-owned entity flags (owned_by / theft_sensitive) survive save/load.
  - Safehouse theft warning counter survives save/load.

Never touches the on-disk save file (revamp_save.json) — works in-memory via
to_dict / from_dict directly.
"""
from ..content import materials as _mat
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT, T_ITEM
from ..content.crafting import make_crafted_entity


def main():
    w = WorldState()
    w.character = Character(name="Audit", background="janitor")
    w.floor_number = 1

    # 1) Materials
    _mat.add_materials(w.character, {"wire_bundle": 3, "scrap_metal": 2})

    # 2) Floor + room with a safehouse-owned entity
    f = FloorState(floor_id="audit_floor", floor_number=1)
    cafe = RoomState(room_id="audit_cafe", fallback_short_title="Cafe Audit")
    cafe.actual_type = "safehouse"
    cafe.safehouse_subtype = "cafe"
    coffee = Entity(key="coffee_machine", entity_type=T_OBJECT,
                    fallback_name="ekspres", tags=["furniture","machine"],
                    affordances=["inspect","salvage"], location_id=cafe.room_id)
    coffee.state["owned_by"] = "safehouse"
    coffee.state["theft_sensitive"] = True
    cafe.entities.append(coffee)
    w.register(coffee)
    f.add_room(cafe)
    f.start_room_id = cafe.room_id
    f.current_room_id = cafe.room_id
    w.current_floor = f

    # 3) Crafted item, damaged
    item = make_crafted_entity("shock_trap", quality="normal", damaged=True)
    w.register(item)
    w.character.inventory_ids.append(item.entity_id)

    # 4) Deployed trap in room state
    cafe.state["player_traps"] = [{
        "key": "tripwire_trap", "entity_id": -1,
        "display_name": "linka", "tags": ["trap","trip"],
        "armed_at": 0, "level": "success", "triggered": False,
        "effect": {"type": "knockdown", "amount": 1},
    }]

    # 5) Theft warning counter
    w.character.flags["safehouse_theft_warnings"] = 2

    # Round-trip
    blob = w.to_dict()
    w2 = WorldState.from_dict(blob)

    ch = w2.character
    assert ch.materials.get("wire_bundle") == 3, f"materials lost: {ch.materials}"
    assert ch.materials.get("scrap_metal") == 2
    assert ch.flags.get("safehouse_theft_warnings") == 2, "theft warnings lost"

    f2 = w2.current_floor
    cafe2 = f2.rooms["audit_cafe"]
    coffee2 = next(e for e in cafe2.entities if e.key == "coffee_machine")
    assert coffee2.state.get("owned_by") == "safehouse", "ownership lost"
    assert coffee2.state.get("theft_sensitive") is True, "theft_sensitive lost"

    assert "player_traps" in cafe2.state, "room state lost"
    assert cafe2.state["player_traps"][0]["key"] == "tripwire_trap"
    assert cafe2.state["player_traps"][0]["effect"]["type"] == "knockdown"

    # Crafted item still in inventory, still damaged
    inv_items = [w2.get(eid) for eid in ch.inventory_ids]
    crafted = next(e for e in inv_items if e is not None and e.key == "shock_trap")
    assert crafted.state.get("damaged"), "crafted damage flag lost"

    print("Gap 8 save/load smoke: OK")


if __name__ == "__main__":
    main()
