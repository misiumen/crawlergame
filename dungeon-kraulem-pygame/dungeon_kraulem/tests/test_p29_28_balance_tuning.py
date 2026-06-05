"""Prompt 29.28 — Balance tuning smoke suite.

Audit findings:
  * Sponsor pod first gift at +8 attention → most runs never saw
    a pod. Lowered to +5.
  * Proxy-war HOT threshold +5 + per-pair 60min cooldown +
    per-floor cap 2 → events fired only in tests. Lowered to +4
    HOT, 45min cooldown, cap 4.
  * Sponsor hunter cooldown was 24h game-time. A 30-min lap
    never saw one. Now 2h (120 min).
  * Threat thresholds 6/12/20 hit alert in 2 player actions. Now
    8/16/26 — ~30% more headroom matches audit's tuning ask.
  * show_director RNG was unseeded; within-tick double-fire was
    possible. Now seeded by `(now_min * 1000 + audience)`.

Each numeric pin gets a contract test so a future un-tune is loud.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


# ── Constant pins ───────────────────────────────────────────────────────

def test_sponsor_pod_thresholds_lowered():
    from ..engine import sponsors as _sp
    assert _sp._GIFT_THRESHOLD_FIRST == 5, \
        f"first gift threshold should be 5, got {_sp._GIFT_THRESHOLD_FIRST}"
    assert _sp._GIFT_THRESHOLD_SECOND == 10, \
        f"second gift should be 10, got {_sp._GIFT_THRESHOLD_SECOND}"
    print(f"  pod thresholds: first=5, second=10: OK")


def test_proxy_war_thresholds_lowered():
    from ..engine import proxy_wars as _pw
    assert _pw._HOT_THRESHOLD == 4
    assert _pw._PER_PAIR_COOLDOWN == 45
    assert _pw._PER_FLOOR_CAP == 4
    print(f"  proxy-war: HOT=4, cooldown=45, cap=4: OK")


def test_sponsor_hunter_cooldown_lowered():
    from ..content.data.sponsors import SPONSORS
    over_24h = [k for k, v in SPONSORS.items()
                if int(v.get("intervention_cooldown_minutes", 0)) > 360]
    assert not over_24h, \
        f"these sponsors still on >6h cooldown: {over_24h}"
    # And all 11 should be at 120 minutes now.
    not_120 = [k for k, v in SPONSORS.items()
               if int(v.get("intervention_cooldown_minutes", 0)) != 120]
    assert not not_120, \
        f"sponsors not at 120-min cooldown: {not_120}"
    print(f"  all 11 sponsor hunter cooldowns at 120 min: OK")


def test_threat_thresholds_widened():
    from ..engine import threat as _th
    assert _th.THRESHOLD_WARY == 8
    assert _th.THRESHOLD_ALERT == 16
    assert _th.THRESHOLD_ENRAGED == 26
    assert _th.DECAY_PER_MINUTE == 1
    print(f"  threat thresholds: WARY=8, ALERT=16, ENRAGED=26: OK")


# ── Behavior smoke checks ──────────────────────────────────────────────

def test_proxy_war_fires_at_4_not_5():
    """Verify the new threshold is honored end-to-end."""
    from ..engine import proxy_wars as _pw
    from ..engine import sponsors as _sp
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor import FloorState
    from ..engine.room import RoomState
    w = WorldState()
    w.character = Character(name="Test", audience_rating=60)
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="x")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    w.current_floor = f
    # Boost to exactly +4 each — old code would've refused.
    _sp.adjust_attention(w, "novachem_biotech", 4)
    _sp.adjust_attention(w, "kanal_7_krawedz", 4)
    pair = _pw.maybe_fire(w)
    assert pair is not None, "+4/+4 should fire under P29.28"
    print("  proxy_war fires at HOT=+4 (was +5): OK")


def test_sponsor_pod_fires_at_5_attention():
    """When attention crosses the new +5 threshold, _check_gift_thresholds
    should fire the first gift."""
    from ..engine import sponsors as _sp
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor import FloorState
    from ..engine.room import RoomState
    w = WorldState()
    w.character = Character(name="Test")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="x")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    w.current_floor = f
    # Force attention to exactly +5 for NovaChem.
    w.character.flags = {"sponsor_attention": {"novachem_biotech": 5}}
    _sp._check_gift_thresholds(w)
    pods = [e for e in r.entities if "sponsor_pod" in (e.tags or [])]
    assert pods, "+5 attention should produce a pod under P29.28"
    print("  pod fires at attention=+5 (was +8): OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_sponsor_pod_thresholds_lowered()
    test_proxy_war_thresholds_lowered()
    test_sponsor_hunter_cooldown_lowered()
    test_threat_thresholds_widened()
    test_proxy_war_fires_at_4_not_5()
    test_sponsor_pod_fires_at_5_attention()
    print("Prompt 29.28 balance tuning smoke: OK")


if __name__ == "__main__":
    main()
