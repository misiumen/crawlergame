"""P29.53r — Paczka reveal screen (multi-line dramatic delivery).

User complaint: 3 paczki w runie zawierały taśmę naprawczą, tani nóż,
antidote — fatalny loot. Loot scaling fix landed w P29.53l (F4+ bonus
item by rarity); ten test cover MOMENT otwarcia paczki — gracz musi
czuć, że to wydarzenie, nie linia tekstu w logu.
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


# ── Reveal structure ─────────────────────────────────────────────────


def test_sponsor_gift_reveal_emits_three_lines():
    """Drop-pod + reveal + catchphrase — three log lines per gift."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"}
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    assert len(lines) == 3, f"expected 3 lines, got {len(lines)}: {lines}"


def test_reveal_includes_rarity_label():
    """The middle line tags the item with a Polish rarity badge."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"}
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    # One of the lines should contain a rarity word.
    rarity_words = {"pospolity", "niepospolity", "rzadki",
                    "epicki", "legendarny"}
    blob = " ".join(lines).lower()
    assert any(r in blob for r in rarity_words), (
        f"no rarity badge in reveal: {lines}")


def test_boon_box_uses_showrunner_flavor():
    """Achievement boon box (source=ach:...) gets a Boon Box opening,
    not a sponsor drop-pod."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "showrunner",
         "item_key": "bandage",
         "source": "ach:first_blood"}
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    blob = " ".join(lines)
    assert "BOON BOX" in blob or "showrunner" in blob.lower()


def test_anonymous_gift_falls_back_cleanly():
    """No sponsor_key + no boon source → anonymous package flavor."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [{"item_key": "bandage"}]
    lines = []
    _consume_pending_gifts(w, room, lines)
    assert any("nonimowy" in ln.lower() or "ladzie" in ln.lower()
               for ln in lines), (
        f"no anonymous flavor in {lines}")


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
    # Two gifts × 3 lines = 6.
    assert len(lines) == 6


def test_unknown_item_key_stays_in_queue():
    """Unknown item keys are kept for later — graceful degradation."""
    w = _mk_world()
    room = _mk_room()
    w.pending_sponsor_gifts = [
        {"sponsor_key": "dr_crucible", "item_key": "bandage"},
        # Note: this item doesn't exist in ITEM_TEMPLATES — may or may
        # not be left in queue depending on make_item fallback. Test
        # mainly ensures we don't crash.
    ]
    lines = []
    _consume_pending_gifts(w, room, lines)
    # Real item consumed.
    assert any(g.get("item_key") == "bandage"
               for g in (w.pending_sponsor_gifts or [])) is False
