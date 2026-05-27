"""P29.18 — Sponsor proxy-war events.

When two sponsors both go HOT (attention >= +5) at the same time, the
audience expects them to fight each other publicly. This module
detects that condition during sponsor attention adjustments and
fires a one-time antagonistic event:

  * a "disinformation" log line in their voice
  * a sponsor_voice chatter line attacking the rival
  * each sponsor's attention shifts slightly: +1 to the aggressor,
    -1 to the rival they accuse

Limits:
  * Per-pair cooldown of 60 in-game minutes (one event per pair).
  * Per-floor cap of 2 proxy-war events.
  * Pair is the alphabetically-sorted (key_a, key_b) — order-independent.

Public API:
    maybe_fire(world) -> Optional[tuple[str, str]]
        Returns the (aggressor, rival) pair on fire, or None.
"""
from __future__ import annotations
import random
from typing import Optional, Tuple


# P29.28 — pre-tune: events were test-only fire in practice.
#   HOT threshold +5 → +4 (one floor of normal play often hits this)
#   per-pair cooldown 60 → 45 min (still prevents spam)
#   per-floor cap 2 → 4 (let the show actually happen)
_HOT_THRESHOLD = 4
_PER_PAIR_COOLDOWN = 45
_PER_FLOOR_CAP = 4


# Pool of disinformation lines, picked at fire time. Keys substitute
# {aggressor} / {rival} with sponsor PL display names.
_DISINFO_LINES = (
    "{aggressor}: „Słyszeliście, co {rival} robił w zeszłym sezonie? "
    "Materiał wyszedł na jaw.”",
    "{aggressor} zwołuje konferencję w studio: „Działalność {rival} "
    "wymaga niezależnej kontroli.”",
    "{aggressor} ogłasza: „Sponsoring {rival} został zawieszony do "
    "wyjaśnienia.” (Wyjaśnienie nie nastąpi.)",
    "{aggressor} wykupuje pasmo reklamowe specjalnie po to, żeby "
    "skrytykować {rival}.",
    "Na ekranach studio leci nagranie {rival}, dziwnie zmontowane. "
    "Logo {aggressor} w prawym górnym rogu.",
)


def _attention_dict(world) -> dict:
    """Return the current attention dict without mutating it."""
    try:
        from . import sponsors as _sp
        return dict(_sp._attention_dict(world))
    except Exception:
        return {}


def _sponsor_name(skey: str) -> str:
    try:
        from . import sponsors as _sp
        sdata = _sp.get_sponsor(skey)
        return _sp._name_pl(sdata)
    except Exception:
        return skey


def _floor_state(world):
    f = getattr(world, "current_floor", None)
    if f is None:
        return None
    if not hasattr(f, "state") or f.state is None:
        f.state = {}
    return f.state


def _now_minute(world) -> int:
    f = getattr(world, "current_floor", None)
    if f is None:
        return 0
    return int(getattr(f, "current_minute", 0) or 0)


def _pair_key(a: str, b: str) -> str:
    return f"proxy_war_pair_{min(a, b)}__{max(a, b)}"


def maybe_fire(world, *, rng: Optional[random.Random] = None
              ) -> Optional[Tuple[str, str]]:
    """Try to fire a proxy-war event. Called from sponsors.adjust_attention
    after attention changes, OR from time_system on a cooldown tick.
    Idempotent: enforces per-pair cooldown + per-floor cap.
    """
    if world is None or getattr(world, "character", None) is None:
        return None
    fstate = _floor_state(world)
    if fstate is None:
        return None
    # Per-floor cap.
    fired = int(fstate.get("proxy_war_event_count", 0))
    if fired >= _PER_FLOOR_CAP:
        return None
    # Find pairs at HOT.
    att = _attention_dict(world)
    hot = sorted(
        [k for k, v in att.items() if int(v) >= _HOT_THRESHOLD],
        key=lambda k: int(att[k]),
        reverse=True,
    )
    if len(hot) < 2:
        return None
    # Pick top two; alphabetize for the cooldown key.
    rng = rng or random.Random(_now_minute(world))
    aggressor = hot[0]
    rival = hot[1]
    key = _pair_key(aggressor, rival)
    last_min = int(fstate.get(key, -10_000))
    now = _now_minute(world)
    if (now - last_min) < _PER_PAIR_COOLDOWN:
        return None
    # Fire.
    line = rng.choice(_DISINFO_LINES).format(
        aggressor=_sponsor_name(aggressor),
        rival=_sponsor_name(rival),
    )
    if hasattr(world, "log_msg"):
        world.log_msg(line, "sponsor")
    # Attention shift: +1 aggressor, -1 rival.
    try:
        from . import sponsors as _sp
        _sp.adjust_attention(world, aggressor, 1)
        _sp.adjust_attention(world, rival, -1)
    except Exception:
        pass
    fstate[key] = now
    fstate["proxy_war_event_count"] = fired + 1
    return (aggressor, rival)
