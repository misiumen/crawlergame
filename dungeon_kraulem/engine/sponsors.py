"""Prompt 18 — Sponsor attention + intervention engine.

Three concerns, kept deliberately small:

1. **Attention tracking** — `character.flags["sponsor_attention"]` is now
   a `dict[sponsor_key, int]` (was a bool). Bumps from likes_tags are
   positive, dislikes_tags negative, clamped to [-20, +20]. The old
   `True` value migrates to `{floor_sponsor: 1}` on load.

2. **Tag routing** — gameplay hooks call `note_player_tag(world, tag,
   weight=1)`. Every sponsor whose `likes_tags` contains `tag` gains
   attention; every sponsor whose `dislikes_tags` contains it loses
   attention. The floor's primary sponsor weight is doubled (you're
   playing their floor; they notice harder).

3. **Interventions** — `maybe_intervene(world)` is called after each
   audience change. When audience band is HOT+ and attention thresholds
   are met, picks gift / hunter / heckle for the most-engaged sponsor,
   respecting per-sponsor cooldowns. Records each fire in
   `world.sponsor_interventions_used` so save round-trips work.

LLM-free. No new pygame surfaces. Polish-first via narrator categories.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import random

from ..content.data.sponsors import (
    SPONSORS, get_sponsor, sponsor_for_floor, all_sponsor_keys,
)
from . import audience as _aud


# Attention clamp.
_ATTENTION_MIN = -20
_ATTENTION_MAX =  20

# Threshold (>=) at which a sponsor's `likes` accumulation makes them
# willing to gift the player. Same magnitude on the negative side gates
# hunter spawns when audience is HOT+.
_GIFT_ATTENTION_THRESHOLD   =  3
_HUNTER_ATTENTION_THRESHOLD = -3

# Intervention kinds.
INT_GIFT   = "gift"
INT_HUNTER = "hunter"
INT_HECKLE = "heckle"


@dataclass
class InterventionRecord:
    """Persisted entry describing a fired intervention. Used for save
    round-trip and for the Journal tab's "recent interventions" list."""
    sponsor_key: str
    kind: str
    fired_at_minute: int
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sponsor_key": self.sponsor_key,
            "kind": self.kind,
            "fired_at_minute": self.fired_at_minute,
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InterventionRecord":
        return cls(
            sponsor_key=str(d.get("sponsor_key") or ""),
            kind=str(d.get("kind") or INT_HECKLE),
            fired_at_minute=int(d.get("fired_at_minute") or 0),
            payload=dict(d.get("payload") or {}),
        )


# ── Attention API ──────────────────────────────────────────────────────────

def _attention_dict(world) -> Dict[str, int]:
    """Return the live attention dict, migrating from the legacy bool if
    needed. Always returns the same object so callers can mutate."""
    char = getattr(world, "character", None)
    if char is None:
        return {}
    flags = getattr(char, "flags", None)
    if flags is None:
        char.flags = {}
        flags = char.flags
    val = flags.get("sponsor_attention")
    if isinstance(val, dict):
        return val
    # Migration: legacy bool. True meant "the floor's sponsor noticed you,
    # mildly negatively". Convert to a tiny negative attention.
    if val is True:
        floor_sponsor = current_floor_sponsor_key(world)
        new = {floor_sponsor: -1} if floor_sponsor else {}
        flags["sponsor_attention"] = new
        return new
    # False / None / missing — start clean.
    flags["sponsor_attention"] = {}
    return flags["sponsor_attention"]


def get_attention(world, sponsor_key: str) -> int:
    d = _attention_dict(world)
    return int(d.get(sponsor_key, 0))


def adjust_attention(world, sponsor_key: str, delta: int) -> int:
    """Adjust a single sponsor's attention by `delta`. Clamps to
    [_ATTENTION_MIN, _ATTENTION_MAX]. Returns the new value."""
    if sponsor_key not in SPONSORS:
        return 0
    d = _attention_dict(world)
    cur = int(d.get(sponsor_key, 0))
    new = max(_ATTENTION_MIN, min(cur + int(delta), _ATTENTION_MAX))
    d[sponsor_key] = new
    return new


def current_floor_sponsor_key(world) -> str:
    """Return the floor's primary sponsor key, or "" if unknown."""
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return ""
    # Prefer an explicit `sponsor_key` if it matches our catalog;
    # otherwise fall back to floor-number rotation.
    sk = getattr(floor, "sponsor_key", "") or ""
    if sk in SPONSORS:
        return sk
    fn = int(getattr(floor, "floor_number", 1) or 1)
    return sponsor_for_floor(fn)


# ── Tag routing ────────────────────────────────────────────────────────────

def note_player_tag(world, tag: str, weight: int = 1) -> None:
    """Notify every sponsor about a tag the player just emitted.

    Each sponsor that lists `tag` in `likes_tags` gains `+weight`
    attention (doubled if they are the floor's primary). Each that lists
    it in `dislikes_tags` loses `-weight`. Sponsors that ignore the tag
    are unchanged.

    Safe to call with `world=None` (silently no-ops) so combat-test
    fixtures don't have to mock the world.
    """
    if world is None or not tag:
        return
    primary = current_floor_sponsor_key(world)
    for skey, sdata in SPONSORS.items():
        bump = 0
        if tag in (sdata.get("likes_tags") or []):
            bump += weight
        if tag in (sdata.get("dislikes_tags") or []):
            bump -= weight
        if bump == 0:
            continue
        if skey == primary:
            bump *= 2
        adjust_attention(world, skey, bump)


# ── Interventions ──────────────────────────────────────────────────────────

def _interventions_list(world) -> List[InterventionRecord]:
    lst = getattr(world, "sponsor_interventions_used", None)
    if lst is None:
        world.sponsor_interventions_used = []
        lst = world.sponsor_interventions_used
    return lst


def _last_intervention_minute(world, sponsor_key: str) -> int:
    """Return the latest minute this sponsor fired an intervention, or
    -1 if it never fired. -1 is necessary (not 0) because minute 0 is a
    legitimate fire time at floor start."""
    last = -1
    for rec in _interventions_list(world):
        if rec.sponsor_key == sponsor_key and rec.fired_at_minute > last:
            last = rec.fired_at_minute
    return last


def _now_minute(world) -> int:
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return 0
    return int(getattr(floor, "current_minute", 0) or 0)


def _cooldown_ok(world, sponsor_key: str) -> bool:
    cd = int(get_sponsor(sponsor_key).get("intervention_cooldown_minutes") or 0)
    if cd <= 0:
        return True
    last = _last_intervention_minute(world, sponsor_key)
    if last < 0:
        return True
    return (_now_minute(world) - last) >= cd


def maybe_intervene(world, rng: Optional[random.Random] = None) -> Optional[InterventionRecord]:
    """Try to fire an intervention from the most-engaged sponsor. Returns
    the record fired, or `None`. Call after audience changes and after
    band crossings.

    Rules:
      - Audience band determines what's allowed:
          * cold: nothing
          * warming: heckle only (if any sponsor has |attention| >= 1)
          * hot: gift (if likes >= +3) or hunter (if dislikes <= -3),
                 fallback heckle
          * viral: same as hot but cooldown halved and heckle suppressed
      - Per-sponsor cooldown gates re-firing.
      - The sponsor with the largest |attention| wins; ties broken by
        floor-primary first, then by sponsor catalog order.
    """
    if world is None or getattr(world, "character", None) is None:
        return None
    rng = rng or random.Random()
    rating = int(world.character.audience_rating or 0)
    band   = _aud.band_for(rating)
    if band == _aud.BAND_COLD:
        return None

    primary = current_floor_sponsor_key(world)
    candidates: List[str] = sorted(
        all_sponsor_keys(),
        key=lambda k: (
            -abs(get_attention(world, k)),
            0 if k == primary else 1,
            list(SPONSORS.keys()).index(k),
        ),
    )

    for skey in candidates:
        att = get_attention(world, skey)
        if abs(att) < 1:
            continue   # sponsor doesn't care yet
        # Cooldown gate (halved at VIRAL).
        cd_mult = 0.5 if band == _aud.BAND_VIRAL else 1.0
        cd = int(get_sponsor(skey).get("intervention_cooldown_minutes") or 0)
        last = _last_intervention_minute(world, skey)
        if last >= 0 and (_now_minute(world) - last) < int(cd * cd_mult):
            continue

        kind: Optional[str] = None
        if band == _aud.BAND_WARMING:
            kind = INT_HECKLE
        else:   # hot or viral
            if att >= _GIFT_ATTENTION_THRESHOLD:
                kind = INT_GIFT
            elif att <= _HUNTER_ATTENTION_THRESHOLD:
                kind = INT_HUNTER
            elif band == _aud.BAND_HOT:
                kind = INT_HECKLE   # warming-like fallback
            # In VIRAL we skip the heckle fallback to keep the band loud.

        if kind is None:
            continue
        rec = _fire_intervention(world, skey, kind, rng)
        if rec is not None:
            return rec
    return None


def _fire_intervention(world, sponsor_key: str, kind: str,
                       rng: random.Random) -> Optional[InterventionRecord]:
    """Execute the intervention's side effects, log it, persist it."""
    sdata = get_sponsor(sponsor_key)
    payload: Dict[str, Any] = {}

    if kind == INT_GIFT:
        pool = list(sdata.get("gift_pool") or [])
        if not pool:
            return None
        item = rng.choice(pool)
        payload["item_key"] = item
        _queue_safehouse_gift(world, sponsor_key, item)
        _log_sponsor_line(world, sponsor_key, f"sponsor_gift_{sponsor_key}",
                          default_pl=f"{_name_pl(sdata)}: paczka czeka w safehouse "
                                     f"({item}).")

    elif kind == INT_HUNTER:
        hkey = str(sdata.get("hunter_key") or "")
        if not hkey:
            return None
        payload["hunter_key"] = hkey
        _queue_hunter_spawn(world, sponsor_key, hkey)
        _log_sponsor_line(world, sponsor_key, f"sponsor_hunter_{sponsor_key}",
                          default_pl=f"{_name_pl(sdata)} zatrudnił ci osobisty problem.")

    elif kind == INT_HECKLE:
        heckle_keys = list(sdata.get("heckle_keys") or [])
        if not heckle_keys:
            return None
        from ..ui.lang import t
        loc_key = rng.choice(heckle_keys)
        line = t(loc_key, fallback="")
        if not line:
            # Static fallback — kept so the engine works even before
            # locales catch up.
            line = f"{_name_pl(sdata)} prycha w eter."
        payload["locale_key"] = loc_key
        if hasattr(world, "log"):
            world.log.append((line, "narrator"))
    else:
        return None

    rec = InterventionRecord(
        sponsor_key=sponsor_key,
        kind=kind,
        fired_at_minute=_now_minute(world),
        payload=payload,
    )
    _interventions_list(world).append(rec)
    return rec


# ── Queue helpers (consumed by safehouse / encounter code later) ───────────

def _queue_safehouse_gift(world, sponsor_key: str, item_key: str) -> None:
    """Stash a pending gift on the world. Safehouse-entry code picks
    pending gifts up and materializes them as room loot. Until the
    safehouse hook reads this, the gift is "in transit" — that's
    intentional, the player should walk to claim it.
    """
    pending = getattr(world, "pending_sponsor_gifts", None)
    if pending is None:
        world.pending_sponsor_gifts = []
        pending = world.pending_sponsor_gifts
    pending.append({"sponsor_key": sponsor_key, "item_key": item_key})


def _queue_hunter_spawn(world, sponsor_key: str, hunter_key: str) -> None:
    """Stash a pending hunter spawn. Combat-encounter setup reads this
    and injects the hunter into the next eligible combat room. Until
    consumed, it sits on `world.pending_sponsor_hunters`.
    """
    pending = getattr(world, "pending_sponsor_hunters", None)
    if pending is None:
        world.pending_sponsor_hunters = []
        pending = world.pending_sponsor_hunters
    pending.append({"sponsor_key": sponsor_key, "hunter_key": hunter_key})


def _log_sponsor_line(world, sponsor_key: str, key: str, *,
                      default_pl: str) -> None:
    from ..ui.lang import t
    line = t(key, fallback=default_pl)
    if hasattr(world, "log"):
        world.log.append((line, "sponsor"))


def _name_pl(sdata: Dict[str, Any]) -> str:
    from ..ui.lang import t
    return t(sdata.get("name_key", ""),
             fallback=sdata.get("name_fallback", "Sponsor"))


# ── Save / load helpers ────────────────────────────────────────────────────

def serialize_interventions(world) -> List[Dict[str, Any]]:
    return [rec.to_dict() for rec in _interventions_list(world)]


def deserialize_interventions(world, raw: List[Dict[str, Any]]) -> None:
    lst = []
    for d in raw or []:
        try:
            lst.append(InterventionRecord.from_dict(d))
        except Exception:
            continue
    world.sponsor_interventions_used = lst


# ── UI helpers ─────────────────────────────────────────────────────────────

def sponsor_mood(world, sponsor_key: str) -> str:
    """Return a one-word mood label for UI rendering. Used by the
    topbar / journal."""
    att = get_attention(world, sponsor_key)
    if att >= 5:   return "zachwycony"
    if att >= 3:   return "życzliwy"
    if att >= 1:   return "uważny"
    if att == 0:   return "obojętny"
    if att >= -2: return "podejrzliwy"
    if att >= -4: return "wkurzony"
    return "wrogi"
