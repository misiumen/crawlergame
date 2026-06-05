"""Prompt 29.10 — mid-floor sponsor drop-pods smoke suite.

Audit finding: existing sponsor gifts queued silently for the next
safehouse — sterile, anti-DCC. Now when a sponsor crosses a gift
threshold, the gift materializes as a branded loot pod in the
player's current room. The safehouse path is the fallback when no
room is available (e.g. between floors).

Covers:
  * deliver_sponsor_gift returns "pod" when a room is set, spawns a
    sponsor_pod entity in that room with the right state.
  * deliver_sponsor_gift falls back to "safehouse" when no room.
  * Parser recognises otwórz / rozbij / zgarnij pakiet.
  * _attempt_open_pod materializes the item into inventory and
    removes the pod from the room.
  * Open bumps audience + emits a positive log line.
  * Opening with no pods refuses gracefully.
  * Multi-pod room with name hint picks the right one.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.parser_core import parse
from ..engine import sponsors as _sp


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=10)
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Parser ───────────────────────────────────────────────────────────────

def test_parser_recognises_pod_open_variants():
    for cmd in ("otwórz pakiet", "rozbij pakiet", "zgarnij pakiet",
                "otwórz pakiet novachem"):
        intent = parse(cmd)
        assert intent.intent == "open_pod", \
            f"{cmd!r} parsed as {intent.intent}, not open_pod"
    intent = parse("otwórz pakiet novachem")
    assert intent.targets == ["novachem"]
    print("  parser: otwórz / rozbij / zgarnij pakiet → open_pod: OK")


# ── deliver_sponsor_gift routes to pod when room available ────────────────

def test_deliver_gift_spawns_pod_in_current_room():
    w, r = _mk_world()
    mode = _sp.deliver_sponsor_gift(w, "nova_chem", "stimpak")
    assert mode == "pod", f"expected pod, got {mode}"
    # Pod entity should be in room.entities and have sponsor_pod tag.
    pods = [e for e in r.entities if "sponsor_pod" in (e.tags or [])]
    assert len(pods) == 1, f"expected 1 pod, got {len(pods)}"
    pod = pods[0]
    assert pod.state["pending_item_key"] == "stimpak"
    assert pod.state["pending_sponsor_key"] == "nova_chem"
    assert "open_pod" in (pod.affordances or [])
    print(f"  deliver_sponsor_gift → pod in current room: OK ({pod.display_name()})")


def test_deliver_gift_falls_back_to_safehouse_without_room():
    w = WorldState()
    w.character = Character(name="X")
    # No current_floor → no room → must fall back to safehouse queue.
    mode = _sp.deliver_sponsor_gift(w, "nova_chem", "stimpak")
    assert mode == "safehouse", f"expected safehouse fallback, got {mode}"
    pending = getattr(w, "pending_sponsor_gifts", None) or []
    assert len(pending) == 1
    print("  deliver_sponsor_gift falls back to safehouse when no room: OK")


# ── Open pod handler ─────────────────────────────────────────────────────

def test_open_pod_moves_item_to_inventory():
    from ..engine.game import Game
    w, r = _mk_world()
    _sp.deliver_sponsor_gift(w, "nova_chem", "stimpak")
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("otwórz pakiet")
    post_inv = len(w.character.inventory_ids)
    assert post_inv == pre_inv + 1, \
        f"item not added: {pre_inv}→{post_inv}"
    # Pod removed from room.
    pods = [e for e in r.entities if "sponsor_pod" in (e.tags or [])
            and (e.state or {}).get("pending_item_key")]
    assert not pods, "active pod should be gone from room"
    print(f"  otwórz pakiet → item in inventory, pod removed: OK")


def test_open_pod_bumps_audience():
    from ..engine.game import Game
    w, r = _mk_world()
    _sp.deliver_sponsor_gift(w, "nova_chem", "stimpak")
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_aud = w.character.audience_rating
    g.submit_generated_command("otwórz pakiet")
    post_aud = w.character.audience_rating
    assert post_aud > pre_aud, \
        f"audience didn't bump: {pre_aud}→{post_aud}"
    print(f"  otwórz pakiet bumps audience ({pre_aud}→{post_aud}): OK")


def test_open_pod_refuses_when_no_pods():
    from ..engine.game import Game
    w, r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    pre = len(w.log)
    g.submit_generated_command("otwórz pakiet")
    post = len(w.log)
    assert post > pre, "no log line on empty-pod refusal"
    print("  empty-room open pakiet refuses: OK")


def test_open_pod_picks_by_name_when_multiple():
    from ..engine.game import Game
    w, r = _mk_world()
    _sp.deliver_sponsor_gift(w, "nova_chem", "stimpak")
    _sp.deliver_sponsor_gift(w, "czarny_rynek", "dirty_bandage")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("otwórz pakiet czarny_rynek")
    # nova_chem pod should still be there; czarny_rynek pod should be gone.
    remaining = [e for e in r.entities if "sponsor_pod" in (e.tags or [])
                 and (e.state or {}).get("pending_item_key")]
    assert len(remaining) == 1
    assert remaining[0].state["pending_sponsor_key"] == "nova_chem"
    print("  multi-pod room: name hint picks correct pod: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_parser_recognises_pod_open_variants()
    test_deliver_gift_spawns_pod_in_current_room()
    test_deliver_gift_falls_back_to_safehouse_without_room()
    test_open_pod_moves_item_to_inventory()
    test_open_pod_bumps_audience()
    test_open_pod_refuses_when_no_pods()
    test_open_pod_picks_by_name_when_multiple()
    print("Prompt 29.10 sponsor drop-pods smoke: OK")


if __name__ == "__main__":
    main()
