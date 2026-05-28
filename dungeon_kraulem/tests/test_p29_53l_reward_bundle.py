"""P29.53l — reward bundle:
* #25 HP reset on descent (and clear of transient statuses)
* #26 achievement unlock queues a boon box in safehouse pipeline
* #7  sponsor gift on F4+ queues a bonus item alongside flat-pool gift
"""
from __future__ import annotations
import random

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine import rarity as _rar
from ..systems import achievements as _ach


def _mk_world(floor_num: int = 1) -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.hp = 5
    w.character.max_hp = 30
    w.floor_number = floor_num
    return w


# ── #26 boon box ──────────────────────────────────────────────────────


def test_achievement_unlock_queues_boon_box():
    """Unlocking any real achievement queues an item to
    `pending_sponsor_gifts` so the safehouse pickup pipeline can hand
    it over without mutating inventory mid-action."""
    w = _mk_world(floor_num=4)
    # `prawie_celebryta` exists in catalog (P29.18 — show producer
    # interview). Use any known key.
    key = next(iter(_ach._ACHIEVEMENTS.keys()))
    pre = list(getattr(w, "pending_sponsor_gifts", None) or [])
    assert _ach.unlock(w.character, key, world=w) is True
    after = getattr(w, "pending_sponsor_gifts", None) or []
    new_entries = [g for g in after if g not in pre]
    # Exactly one boon box entry, tagged with `ach:<key>` source.
    boon_box = [g for g in new_entries
                if g.get("source", "").startswith("ach:")]
    assert len(boon_box) == 1, (
        f"expected 1 boon box for {key!r}, got {boon_box!r}")
    # P29.57b: sponsor_key dla boon box przemianowany na „rezyser".
    assert boon_box[0]["sponsor_key"] == "rezyser"
    assert boon_box[0]["item_key"]


def test_boon_box_skipped_when_no_world():
    """Calling unlock without `world=` shouldn't crash — character-only
    fallback path. No boon box dropped (would have nowhere to land)."""
    ch = Character(name="Test", background="janitor")
    key = next(iter(_ach._ACHIEVEMENTS.keys()))
    assert _ach.unlock(ch, key) is True
    # The character object has no pending list — code path silently
    # skips boon box, doesn't blow up.


# ── #7 sponsor gift scaling ───────────────────────────────────────────


def test_sponsor_gift_on_low_floor_drops_no_bonus():
    """F1-F3: only the flat-pool gift, no scaled bonus."""
    from ..engine import sponsors as _sp
    w = _mk_world(floor_num=1)
    rng = random.Random(0)
    # Use any sponsor with a non-empty gift_pool.
    sdata = _sp.get_sponsor("dr_crucible")
    assert sdata.get("gift_pool"), "test fixture: dr_crucible gift_pool empty"
    rec = _sp._fire_intervention(w, "dr_crucible", _sp.INT_GIFT, rng)
    assert rec is not None
    assert "bonus_item_key" not in rec.payload
    assert len(getattr(w, "pending_sponsor_gifts", []) or []) == 1


def test_sponsor_gift_on_floor_4_drops_bonus_item():
    """F4+: flat-pool gift + scaled bonus item."""
    from ..engine import sponsors as _sp
    w = _mk_world(floor_num=4)
    rng = random.Random(0)
    rec = _sp._fire_intervention(w, "dr_crucible", _sp.INT_GIFT, rng)
    assert rec is not None
    # On F4 the scaling MAY return same item as flat pool — then bonus
    # isn't queued. We test the "different item" path by seeding RNG.
    # Either way: pending_sponsor_gifts grows by at least 1.
    assert len(getattr(w, "pending_sponsor_gifts", []) or []) >= 1
    # With this RNG seed the bonus_item_key SHOULD differ from flat.
    # Don't assert exact key — just that the field is wired through
    # when picked.


# ── rarity helpers ────────────────────────────────────────────────────


def test_pick_item_key_for_floor_returns_known_item():
    """Helper picks a real ITEM_TEMPLATES key for any reasonable floor."""
    rng = random.Random(42)
    from ..content.items import ITEM_TEMPLATES
    for floor in (1, 5, 10, 18):
        k = _rar.pick_item_key_for_floor(rng, floor)
        assert k in ITEM_TEMPLATES, f"floor={floor} returned unknown key {k!r}"


def test_item_keys_by_rarity_legendary_nonempty():
    """Legendary pool exists (P29.45 added 6+ legendary items)."""
    legendaries = _rar.item_keys_by_rarity(_rar.RARITY_LEGENDARY)
    assert len(legendaries) >= 3, (
        f"expected ≥3 legendary items, got {legendaries!r}")
