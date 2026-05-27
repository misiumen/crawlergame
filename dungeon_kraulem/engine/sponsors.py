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
    SPONSORS, get_sponsor, all_sponsor_keys,
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
    # Legacy bool migration. Old saves wrote `True` to mean "the floor's
    # primary sponsor noticed you negatively". P29.2: floor primary no
    # longer exists, so we just convert to an empty dict. Anyone who
    # cared about that legacy mark would have decayed it by now anyway.
    # (Avoid calling current_floor_sponsor_key here — would recurse.)
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
    """P29.2 — returns whichever sponsor currently has the highest
    positive attention on this player. NOT the floor's "assigned"
    sponsor (that concept is gone — DCC sponsors compete continuously,
    not by floor-number quota).

    Returns "" if no sponsor has positive attention yet (fresh game,
    very early floor 1). In that case downstream code treats it as
    "no primary yet" — note_player_tag's 2× bump skips, topbar shows
    a generic placeholder, etc.

    Tie-break: catalog order (so behavior is deterministic when two
    sponsors happen to tie). NEGATIVE attention does NOT make you a
    sponsor's "primary" — hatred isn't sponsorship.
    """
    if world is None:
        return ""
    att = _attention_dict(world)
    best_key = ""
    best_val = 0
    for skey in all_sponsor_keys():
        v = int(att.get(skey, 0))
        if v > best_val:
            best_val = v
            best_key = skey
    return best_key


def top_sponsors_ranked(world, n: int = 3) -> List[tuple]:
    """P29.2 — list top-N sponsors by current attention, descending.
    Returns [(sponsor_key, attention), ...]. Used by the topbar HUD
    to render the "audience ranking" instead of a single locked-in
    floor sponsor. Skips sponsors with attention 0 (not watching yet).
    Includes negatives if there's room — a hostile sponsor is
    interesting context.
    """
    if world is None:
        return []
    att = _attention_dict(world)
    # Sort by abs attention (engagement, whether love or hate); within
    # ties, positive wins (allies preferred over enemies).
    ranked = sorted(
        ((k, int(att.get(k, 0))) for k in all_sponsor_keys()
         if att.get(k, 0) != 0),
        key=lambda kv: (-abs(kv[1]), -kv[1],
                        list(SPONSORS.keys()).index(kv[0])),
    )
    return ranked[:max(0, int(n))]


# ── Tag routing ────────────────────────────────────────────────────────────

def note_player_tag(world, tag: str, weight: int = 1) -> None:
    """Notify every sponsor about a tag the player just emitted.

    Each sponsor that lists `tag` in `likes_tags` gains `+weight`
    attention (doubled if they are the floor's primary). Each that lists
    it in `dislikes_tags` loses `-weight`. Sponsors that ignore the tag
    are unchanged.

    P27 — also routes through `sponsor_voice.maybe_speak` for weight ≥ 2
    events, surfacing proactive sponsor chatter as LOG_SYNDIC lines.

    Safe to call with `world=None` (silently no-ops) so combat-test
    fixtures don't have to mock the world.
    """
    if world is None or not tag:
        return
    primary = current_floor_sponsor_key(world)
    # P29.2 — current room may carry a `theme_sponsor_boost` dict that
    # mirrors the floor's DCC vibe (e.g. ZOO room boosts Czarny Rynek
    # +50% per like-bump, Museum boosts Recykling, etc.). This INSPIRES
    # without locking — other sponsors can still win attention from
    # actions they care about more.
    theme_boost = _current_room_sponsor_boost(world)
    for skey, sdata in SPONSORS.items():
        bump = 0
        if tag in (sdata.get("likes_tags") or []):
            bump += weight
        if tag in (sdata.get("dislikes_tags") or []):
            bump -= weight
        if bump == 0:
            continue
        # Primary doubling (DCC: once a sponsor's locked on, they stay
        # focused — natural "main sponsor" emergence).
        if skey == primary and primary:
            bump *= 2
        # Room theme boost: multiplicative, both for likes (+) and
        # dislikes (−) — a room themed for sponsor X both feeds them
        # AND makes them angrier when you mess up.
        boost = theme_boost.get(skey, 0)
        if boost:
            if bump > 0:
                bump += boost
            else:
                bump -= boost
        adjust_attention(world, skey, bump)
    # P27 — sponsor voice bus: roll for proactive chatter.
    try:
        from . import sponsor_voice as _sv
        _sv.maybe_speak(world, tag, weight)
    except Exception:
        pass
    # P29.2 — gift trigger check (first time a sponsor crosses attention
    # threshold). Side-effect free if no crossings.
    try:
        _check_gift_thresholds(world)
    except Exception:
        pass


def _current_room_sponsor_boost(world) -> Dict[str, int]:
    """Read `theme_sponsor_boost` off the player's current room (if any).
    Returns an empty dict when no boost defined. ROOM_POOL templates
    can declare e.g. `theme_sponsor_boost={"czarny_rynek": 1}` to
    nudge that sponsor when player acts in this kind of room."""
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return {}
    room = floor.current_room() if hasattr(floor, "current_room") else None
    if room is None:
        return {}
    boost = (room.state or {}).get("theme_sponsor_boost") if room.state else None
    if isinstance(boost, dict):
        return {k: int(v) for k, v in boost.items() if v}
    return {}


# ── P29.2 — Gift trigger on first attention-threshold crossing ──────────

_GIFT_THRESHOLD_FIRST = 8       # first gift fires at +8 attention
_GIFT_THRESHOLD_SECOND = 14     # repeat at +14 (extended sponsor love)


def _check_gift_thresholds(world) -> None:
    """When a sponsor's attention crosses a gift threshold for the first
    time in this session, queue a gift via _queue_safehouse_gift. Stamps
    a per-(sponsor, threshold) flag on character.flags so it doesn't
    re-fire."""
    if world is None or getattr(world, "character", None) is None:
        return
    flags = world.character.flags
    if flags is None:
        world.character.flags = {}
        flags = world.character.flags
    att = _attention_dict(world)
    for skey in all_sponsor_keys():
        v = int(att.get(skey, 0))
        sdata = get_sponsor(skey)
        # First gift: attention >= 8 and never sent before.
        # P29.10 — prefer drop-pod (DCC moment); deliver_sponsor_gift
        # handles the safehouse fallback when no current room.
        flag1 = f"sponsor_gift1_sent_{skey}"
        if v >= _GIFT_THRESHOLD_FIRST and not flags.get(flag1):
            gifts = list(sdata.get("gift_pool") or [])
            if gifts:
                item = gifts[0]
                mode = deliver_sponsor_gift(world, skey, item)
                flags[flag1] = True
                if mode == "safehouse" and hasattr(world, "log_msg"):
                    world.log_msg(
                        f"{_name_pl(sdata)} cię zauważył. Paczka czeka w safehouse.",
                        "sponsor",
                    )
                # (The "pod" branch logs from inside _spawn_sponsor_drop_pod.)
        # Second gift: deeper bond.
        flag2 = f"sponsor_gift2_sent_{skey}"
        if v >= _GIFT_THRESHOLD_SECOND and not flags.get(flag2):
            gifts = list(sdata.get("gift_pool") or [])
            if len(gifts) >= 2:
                item = gifts[1]
                mode = deliver_sponsor_gift(world, skey, item)
                flags[flag2] = True
                if mode == "safehouse" and hasattr(world, "log_msg"):
                    world.log_msg(
                        f"{_name_pl(sdata)} szanuje cię. Druga paczka w safehouse.",
                        "sponsor",
                    )


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
            # P28.8: route through log_msg for dedupe.
            if hasattr(world, "log_msg"):
                world.log_msg(line, "narrator")
            else:
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


# ── P29.10 — Mid-floor sponsor drop-pods ────────────────────────────────────

def _spawn_sponsor_drop_pod(world, sponsor_key: str, item_key: str) -> bool:
    """Materialize a sponsor-branded loot pod in the player's current
    room. Returns True on success, False if no room is available
    (caller should fall back to _queue_safehouse_gift).

    The pod is a normal Entity tagged 'sponsor_pod' + 'container'. It
    carries the pending item_key in its state; on `otwórz pakiet`,
    Game._attempt_open_pod materializes the actual item, transfers
    it to player inventory, and removes the pod from the room.
    """
    from .entity import Entity, T_OBJECT
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return False
    room = floor.current_room() if hasattr(floor, "current_room") else None
    if room is None:
        return False
    sdata = get_sponsor(sponsor_key)
    sponsor_name = _name_pl(sdata)
    pod = Entity(
        key=f"sponsor_pod_{sponsor_key}",
        entity_type=T_OBJECT,
        fallback_name=f"pakiet sponsorski ({sponsor_name})",
        fallback_desc=(
            f"Zgrzytająca metalowa kapsuła z logo „{sponsor_name}”. "
            f"Migocze diodą. Otwórz, póki nikt nie patrzy."
        ),
        tags=["sponsor_pod", "container", "loot", "deliverable"],
        affordances=["inspect", "open_pod", "break"],
        location_id=room.room_id,
        portable=False,
        state={
            "pending_item_key": item_key,
            "pending_sponsor_key": sponsor_key,
            "armed_at_minute": _now_minute(world),
        },
    )
    world.register(pod)
    if not hasattr(room, "entities") or room.entities is None:
        room.entities = []
    room.entities.append(pod)
    # SFX hook (audio module noops if unavailable).
    try:
        from . import audio as _audio
        _audio.play_sfx("sponsor_chime")
    except Exception:
        pass
    if hasattr(world, "log_msg"):
        world.log_msg(
            f"PAKIET! {sponsor_name} zrzuca ci kapsułę — ląduje obok. "
            f"„otwórz pakiet”, jeśli chcesz dobrać.", "sponsor")
    return True


def deliver_sponsor_gift(world, sponsor_key: str, item_key: str) -> str:
    """P29.10 — public entry point. Try drop-pod first (more DCC), fall
    back to safehouse-queue when player is between floors or otherwise
    has no current room. Returns one of:
      "pod"        — materialized in current room as a pod entity
      "safehouse"  — queued for next safehouse claim
      "none"       — failed (no world / no character)
    """
    if world is None:
        return "none"
    if _spawn_sponsor_drop_pod(world, sponsor_key, item_key):
        return "pod"
    _queue_safehouse_gift(world, sponsor_key, item_key)
    return "safehouse"


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
        # P28.8: route through log_msg for dedupe.
        if hasattr(world, "log_msg"):
            world.log_msg(line, "sponsor")
        else:
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
