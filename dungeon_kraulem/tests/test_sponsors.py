"""Prompt 18 — sponsor / audience v1 smoke suite.

Covers:
  * Audience band lookup and clamping
  * Band crossings emit narrator lines
  * Idle decay after grace period
  * Sponsor attention dict accumulates via likes/dislikes tags
  * Floor primary sponsor receives 2× attention
  * Intervention cooldown gates re-firing
  * Gift / hunter / heckle dispatch
  * Save round-trip preserves attention + interventions
  * Legacy `flags["sponsor_attention"] = True` migrates to dict
  * Each catalog sponsor has at least one like + one dislike tag
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import random
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import audience as _aud
from ..engine import sponsors as _sp
from ..content.data.sponsors import (
    SPONSORS, SPONSOR_NOVACHEM, SPONSOR_SPORT, SPONSOR_CZARNY_RYNEK,
    SPONSOR_MINISTERSTWO, SPONSOR_RECYKLING, SPONSOR_KANAL_7,
    get_sponsor,
)


def _mk_world(floor_num: int = 1, sponsor_key: str = SPONSOR_NOVACHEM) -> WorldState:
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id=f"f{floor_num}", floor_number=floor_num)
    f.sponsor_key = sponsor_key
    f.current_minute = 0
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── Audience band model ───────────────────────────────────────────────────

def test_band_for_clamps_and_buckets():
    assert _aud.band_for(-50) == _aud.BAND_COLD
    assert _aud.band_for(0)   == _aud.BAND_COLD
    assert _aud.band_for(19)  == _aud.BAND_COLD
    assert _aud.band_for(20)  == _aud.BAND_WARMING
    assert _aud.band_for(49)  == _aud.BAND_WARMING
    assert _aud.band_for(50)  == _aud.BAND_HOT
    assert _aud.band_for(79)  == _aud.BAND_HOT
    assert _aud.band_for(80)  == _aud.BAND_VIRAL
    assert _aud.band_for(100) == _aud.BAND_VIRAL
    assert _aud.band_for(500) == _aud.BAND_VIRAL
    print("  band_for clamps + buckets: OK")


def test_change_audience_clamps():
    w = _mk_world()
    w.character.audience_rating = 95
    _aud.change_audience(w, 50)
    assert w.character.audience_rating == 100, \
        f"upper clamp failed: {w.character.audience_rating}"
    _aud.change_audience(w, -500)
    assert w.character.audience_rating == 0, \
        f"lower clamp failed: {w.character.audience_rating}"
    print("  change_audience clamps to [0,100]: OK")


def test_change_audience_emits_band_crossing():
    w = _mk_world()
    w.character.audience_rating = 18
    crossing = _aud.change_audience(w, +5)   # 18 -> 23, COLD -> WARMING
    assert crossing is not None, "expected band crossing"
    assert crossing.from_band == _aud.BAND_COLD
    assert crossing.to_band == _aud.BAND_WARMING
    assert crossing.direction == 1
    # Same-band change must NOT emit a crossing.
    crossing2 = _aud.change_audience(w, +1)
    assert crossing2 is None
    print("  band crossing emitted on boundary cross: OK")


def test_idle_decay_after_grace_period():
    w = _mk_world()
    w.character.audience_rating = 40
    # Inside grace (under 120 minutes) -> no decay.
    _aud.tick_decay(w, 60)
    _aud.tick_decay(w, 30)
    assert w.character.audience_rating == 40, \
        f"decayed too early: {w.character.audience_rating}"
    # Past grace by 120 minutes (60+30=90, +120 = 210 total, over=90 -> 1 step).
    _aud.tick_decay(w, 120)
    assert w.character.audience_rating < 40, \
        f"expected decay, got {w.character.audience_rating}"
    print(f"  idle decay after grace: OK (now {w.character.audience_rating})")


# ── Sponsor attention ────────────────────────────────────────────────────

def test_attention_starts_empty_and_dict_typed():
    w = _mk_world()
    d = _sp._attention_dict(w)
    assert isinstance(d, dict), f"attention not dict: {type(d)}"
    assert d == {}, f"attention not empty: {d}"
    print("  attention starts as empty dict: OK")


def test_note_player_tag_routes_to_correct_sponsors():
    """P29.2: no more 'floor primary' lock. Primary doubling only
    applies once a sponsor has positive attention (emergent primary).
    Pre-seed Sport with attention so it counts as primary, then
    verify the 2× bump fires."""
    w = _mk_world(sponsor_key=SPONSOR_SPORT)
    _sp.adjust_attention(w, SPONSOR_SPORT, 3)  # make Sport primary by force
    # `crit_hit` is in Sport.likes_tags and Kanał 7 likes "crit_success" not
    # "crit_hit", so only Sport gains here. Primary => double weight.
    pre = _sp.get_attention(w, SPONSOR_SPORT)
    _sp.note_player_tag(w, "crit_hit", weight=1)
    delta = _sp.get_attention(w, SPONSOR_SPORT) - pre
    assert delta == 2, \
        f"Sport (primary) should gain +2 from crit_hit, got " \
        f"{_sp.get_attention(w, SPONSOR_SPORT)} (delta {delta})"
    # Other sponsors that don't list crit_hit shouldn't move.
    assert _sp.get_attention(w, SPONSOR_NOVACHEM) == 0
    print("  tag routing + primary doubling: OK")


def test_note_player_tag_likes_and_dislikes():
    """P29.2: pre-seed NovaChem positive so they're emergent primary."""
    w = _mk_world(sponsor_key=SPONSOR_NOVACHEM)
    _sp.adjust_attention(w, SPONSOR_NOVACHEM, 3)
    pre = {k: _sp.get_attention(w, k) for k in
           (SPONSOR_CZARNY_RYNEK, SPONSOR_NOVACHEM, SPONSOR_MINISTERSTWO)}
    # 'theft' is liked by Czarny Rynek, disliked by NovaChem (primary) +
    # Ministerstwo.
    _sp.note_player_tag(w, "theft", weight=1)
    assert _sp.get_attention(w, SPONSOR_CZARNY_RYNEK) == pre[SPONSOR_CZARNY_RYNEK] + 1
    assert _sp.get_attention(w, SPONSOR_NOVACHEM) == pre[SPONSOR_NOVACHEM] - 2   # primary -> 2x
    assert _sp.get_attention(w, SPONSOR_MINISTERSTWO) == pre[SPONSOR_MINISTERSTWO] - 1
    print("  likes/dislikes route opposite directions: OK")


def test_attention_clamps():
    w = _mk_world()
    for _ in range(200):
        _sp.adjust_attention(w, SPONSOR_NOVACHEM, +5)
    assert _sp.get_attention(w, SPONSOR_NOVACHEM) == 20, \
        f"upper clamp: {_sp.get_attention(w, SPONSOR_NOVACHEM)}"
    for _ in range(200):
        _sp.adjust_attention(w, SPONSOR_NOVACHEM, -5)
    assert _sp.get_attention(w, SPONSOR_NOVACHEM) == -20, \
        f"lower clamp: {_sp.get_attention(w, SPONSOR_NOVACHEM)}"
    print("  attention clamps to [-20,+20]: OK")


# ── Interventions ────────────────────────────────────────────────────────

def test_no_intervention_below_warming():
    w = _mk_world()
    w.character.audience_rating = 10   # cold
    _sp.adjust_attention(w, SPONSOR_NOVACHEM, +5)
    rec = _sp.maybe_intervene(w, rng=random.Random(1))
    assert rec is None, f"cold band must not intervene, got {rec}"
    print("  no intervention in COLD band: OK")


def test_gift_fires_when_hot_and_liked():
    w = _mk_world()
    w.character.audience_rating = 60   # hot
    _sp.adjust_attention(w, SPONSOR_NOVACHEM, +5)
    rec = _sp.maybe_intervene(w, rng=random.Random(1))
    assert rec is not None, "expected an intervention to fire"
    assert rec.kind == _sp.INT_GIFT, f"expected gift, got {rec.kind}"
    assert rec.sponsor_key == SPONSOR_NOVACHEM
    # Gift queued for safehouse.
    assert getattr(w, "pending_sponsor_gifts", None), \
        "gift should be queued for safehouse"
    print(f"  HOT + liked -> gift fires: OK ({rec.payload.get('item_key')})")


def test_hunter_fires_when_hot_and_disliked():
    w = _mk_world()
    w.character.audience_rating = 70   # hot
    _sp.adjust_attention(w, SPONSOR_SPORT, -5)
    rec = _sp.maybe_intervene(w, rng=random.Random(2))
    assert rec is not None and rec.kind == _sp.INT_HUNTER, \
        f"expected hunter, got {rec}"
    assert getattr(w, "pending_sponsor_hunters", None)
    print(f"  HOT + disliked -> hunter fires: OK")


def test_cooldown_blocks_repeat_interventions():
    w = _mk_world()
    w.character.audience_rating = 60
    _sp.adjust_attention(w, SPONSOR_NOVACHEM, +5)
    r1 = _sp.maybe_intervene(w, rng=random.Random(1))
    assert r1 is not None
    # Same-minute follow-up must be blocked.
    r2 = _sp.maybe_intervene(w, rng=random.Random(1))
    assert r2 is None, f"cooldown should block repeat; got {r2}"
    # Advance time past the cooldown.
    w.current_floor.current_minute += SPONSORS[SPONSOR_NOVACHEM][
        "intervention_cooldown_minutes"] + 1
    r3 = _sp.maybe_intervene(w, rng=random.Random(1))
    assert r3 is not None, "after cooldown, should fire again"
    print("  per-sponsor cooldown gates repeats: OK")


# ── Save / load + migration ───────────────────────────────────────────────

def test_save_round_trip_preserves_state():
    w = _mk_world()
    w.character.audience_rating = 62
    _sp.adjust_attention(w, SPONSOR_NOVACHEM, +5)
    _sp.adjust_attention(w, SPONSOR_SPORT, -3)
    rec = _sp.maybe_intervene(w, rng=random.Random(3))
    assert rec is not None
    d = w.to_dict()
    w2 = WorldState.from_dict(d)
    assert w2.character.audience_rating == 62
    assert _sp.get_attention(w2, SPONSOR_NOVACHEM) == 5
    assert _sp.get_attention(w2, SPONSOR_SPORT) == -3
    assert len(w2.sponsor_interventions_used) == 1
    assert w2.sponsor_interventions_used[0].sponsor_key == rec.sponsor_key
    print("  save round-trip preserves audience + attention + interventions: OK")


def test_legacy_bool_sponsor_attention_migrates():
    """Old saves wrote `flags['sponsor_attention'] = True`. New code
    expects a dict. The migration fires the first time
    `_attention_dict(world)` is read.

    P29.2: with no primary sponsor (zero attention everywhere), the
    legacy `True` migrates to an empty dict rather than a primary
    marker — there's no longer a 'floor primary' to assign to.
    """
    w = _mk_world(sponsor_key=SPONSOR_NOVACHEM)
    w.character.flags["sponsor_attention"] = True
    d = w.to_dict()
    w2 = WorldState.from_dict(d)
    # Trigger migration via read.
    val = _sp._attention_dict(w2)
    assert isinstance(val, dict), f"migration failed: {type(val)} ({val!r})"
    # No primary sponsor yet → empty dict (cleanest start). Legacy
    # bool no longer carries the "primary noticed you" semantic since
    # there is no primary lock anymore.
    assert val == {} or val.get(SPONSOR_NOVACHEM) == -1, \
        f"unexpected legacy migration: {val}"
    print(f"  legacy bool sponsor_attention migrates: {val}: OK")


# ── Catalog hygiene ───────────────────────────────────────────────────────

def test_each_sponsor_has_likes_and_dislikes():
    """Every catalog sponsor must offer at least one like + one dislike
    tag, otherwise the tag-routing engine has nothing to do for them."""
    for skey, sdata in SPONSORS.items():
        likes = sdata.get("likes_tags") or []
        disl  = sdata.get("dislikes_tags") or []
        assert likes, f"{skey}: no likes_tags"
        assert disl,  f"{skey}: no dislikes_tags"
        assert sdata.get("gift_pool"),  f"{skey}: no gift_pool"
        assert sdata.get("hunter_key"), f"{skey}: no hunter_key"
        assert sdata.get("heckle_keys"), f"{skey}: no heckle_keys"
    print(f"  catalog hygiene: OK ({len(SPONSORS)} sponsors)")


# P29.2 — floor rotation tests REMOVED. Sponsors no longer get
# assigned per floor; they compete continuously via attention.
# See test_p29_2_sponsors.py for the replacement smoke suite.


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_band_for_clamps_and_buckets()
    test_change_audience_clamps()
    test_change_audience_emits_band_crossing()
    test_idle_decay_after_grace_period()
    test_attention_starts_empty_and_dict_typed()
    test_note_player_tag_routes_to_correct_sponsors()
    test_note_player_tag_likes_and_dislikes()
    test_attention_clamps()
    test_no_intervention_below_warming()
    test_gift_fires_when_hot_and_liked()
    test_hunter_fires_when_hot_and_disliked()
    test_cooldown_blocks_repeat_interventions()
    test_save_round_trip_preserves_state()
    test_legacy_bool_sponsor_attention_migrates()
    test_each_sponsor_has_likes_and_dislikes()
    # P29.2 — floor rotation tests removed (sponsors compete now).
    print("Prompt 18 sponsor/audience smoke: OK")


if __name__ == "__main__":
    main()
