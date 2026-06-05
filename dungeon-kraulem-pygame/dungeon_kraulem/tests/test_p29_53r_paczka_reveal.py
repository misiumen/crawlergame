"""P29.53r — Sponsor gift / Boon pipeline.

P29.57b refactor: sponsor gifts + achievement boon nie spawnują już
gotowych itemów. Tworzą skrzynki entity w EQ gracza, które gracz
otwiera manualnie w tabie „Skrzynki". Reveal moment przeniesiony do
`handlers/boxes.py::attempt_open_box`.

Te testy zostały zaadaptowane do nowego flow:
* gift queue → skrzynka entity w EQ (1 linia log info)
* reveal odbywa się dopiero przy otwarciu skrzynki
* showrunner → reżyser (P29.57b naming refactor)
"""
from __future__ import annotations

from ..engine.consequences import _consume_pending_gifts
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.room import RoomState


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    return w


def _mk_room() -> RoomState:
    return RoomState(room_id="safe_1")


def _count_boxes(w: WorldState) -> int:
    """Helper — ile skrzynek (tag „box") jest w EQ gracza."""
    n = 0
    for eid in (w.character.inventory_ids or []):
        ent = w.entities.get(eid)
        if ent is None:
            continue
        if "box" in (ent.tags or []):
            n += 1
    return n


def test_sponsor_gift_creates_box_in_inventory():
    """Sponsor gift queue → skrzynka entity w EQ, info log."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"}
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    assert _count_boxes(w) == 1, "skrzynka nie powstała w EQ"
    assert len(lines) == 1, f"oczekiwano 1 linii info, dostałem {lines}"
    assert "skrzynka" in lines[0].lower()


def test_box_carries_sponsor_metadata():
    """Skrzynka entity ma tag „box" + state z box_source/source_name."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"}
    ]
    _consume_pending_gifts(w, room, [])
    box = None
    for eid in (w.character.inventory_ids or []):
        ent = w.entities.get(eid)
        if ent and "box" in (ent.tags or []):
            box = ent
            break
    assert box is not None
    state = box.state or {}
    assert state.get("box_source") == "sponsor"
    assert state.get("box_source_name")
    assert state.get("box_contents")
    assert state["box_contents"][0]["item_key"] == "bandage"


def test_boon_box_uses_rezyser_source():
    """Achievement boon (source=ach:...) → box_source = „rezyser"."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "rezyser",
         "item_key": "bandage",
         "source": "ach:first_blood"}
    ]
    _consume_pending_gifts(w, room, [])
    box = None
    for eid in (w.character.inventory_ids or []):
        ent = w.entities.get(eid)
        if ent and "box" in (ent.tags or []):
            box = ent
            break
    assert box is not None
    assert (box.state or {}).get("box_source") == "rezyser"


def test_queue_drained_after_consume():
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"},
        {"sponsor_key": "dr_crucible", "item_key": "stimpak"},
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    assert w.pending_sponsor_gifts == []
    assert _count_boxes(w) == 2
    assert len(lines) == 2


def test_unknown_item_key_does_not_crash():
    """Defensive — handler nie wybucha na nieznanych item keys."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"},
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    # Bandage consumed, queue empty.
    assert not any(g.get("item_key") == "bandage"
                   for g in (w.pending_sponsor_gifts or []))
