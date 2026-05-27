"""Prompt 18 — Audience rating bands + decay + change API.

The audience number lives on `Character.audience_rating` and was already
saved/loaded by the character serializer. Until this module landed, it
was a quiet counter that nothing read.

This module:
  - Defines four named bands (`cold`, `warming`, `hot`, `viral`) with
    clamp range [0, 100].
  - Provides `change_audience(world, delta, source="")` — the single
    write path that callers should use instead of touching
    `world.character.audience_rating` directly. It clamps, logs, and
    emits a band-crossing event when needed.
  - Provides `tick_decay(world, minutes_elapsed)` — boredom decay called
    by the time-advance code each in-game minute step.
  - Provides `band_for(rating)` / `band_label(band)` for UI rendering.

LLM-free, deterministic. Side-effects routed via narrator categories
that already exist in `systems.narrator` (the categories were declared
in Prompt 06c — they just had no triggers).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# ── Bands ──────────────────────────────────────────────────────────────────

BAND_COLD    = "cold"      # 0-19 — sponsor looking elsewhere
BAND_WARMING = "warming"   # 20-49 — audience starting to notice
BAND_HOT     = "hot"       # 50-79 — sponsor engaged, gifts possible
BAND_VIRAL   = "viral"     # 80-100 — channel-wide spotlight

BANDS = (BAND_COLD, BAND_WARMING, BAND_HOT, BAND_VIRAL)

# (lower_inclusive, upper_inclusive)
_BAND_RANGES = {
    BAND_COLD:    (0, 19),
    BAND_WARMING: (20, 49),
    BAND_HOT:     (50, 79),
    BAND_VIRAL:   (80, 100),
}

# Locale-key fallbacks for band labels in the UI.
_BAND_LABEL_FALLBACK = {
    BAND_COLD:    "ZIMNO",
    BAND_WARMING: "ROZGRZEWKA",
    BAND_HOT:     "GORĄCO",
    BAND_VIRAL:   "VIRAL",
}

# Tag emitted to sponsor-attention bumps when the player enters VIRAL.
TAG_VIRAL_BAND = "audience_high_band"


# Sustained-idle decay parameters.
# After this many minutes with no audience-changing event, lose −1 per
# `_IDLE_DECAY_MINUTES_PER_TICK` minutes. Safehouse rest tick is handled
# separately (steeper decay) by the rest-time code.
_IDLE_DECAY_GRACE_MINUTES   = 120   # 2 in-game hours
_IDLE_DECAY_MINUTES_PER_TICK = 60   # then −1 per hour
_AUDIENCE_MIN = 0
_AUDIENCE_MAX = 100


@dataclass
class BandCrossing:
    """Returned by `change_audience` when the band changed as a result."""
    from_band: str
    to_band: str
    direction: int   # +1 = rising, -1 = falling


# ── Public API ─────────────────────────────────────────────────────────────

def band_for(rating: int) -> str:
    """Return the band name for a raw rating value."""
    r = max(_AUDIENCE_MIN, min(int(rating), _AUDIENCE_MAX))
    for band, (lo, hi) in _BAND_RANGES.items():
        if lo <= r <= hi:
            return band
    return BAND_COLD


def band_label(band: str) -> str:
    """Return the localized display label for a band."""
    from ..ui.lang import t
    key = f"audience_band_{band}"
    return t(key, fallback=_BAND_LABEL_FALLBACK.get(band, band.upper()))


def band_range(band: str) -> Tuple[int, int]:
    """Return (lo, hi) inclusive range for a band, or (0,0) for unknown."""
    return _BAND_RANGES.get(band, (0, 0))


def change_audience(world, delta: int, source: str = "",
                    emit_log: bool = True) -> Optional[BandCrossing]:
    """Single-point write for audience_rating. Clamps to [0,100], records
    the change for idle-decay reset, and emits a band-crossing event +
    narrator line if the band changed.

    Returns the BandCrossing if a band boundary was crossed; otherwise
    `None`. Callers that need the new band can use `band_for(...)`.

    `source` is a free-text tag used for the optional log entry and (in
    the future) for analytics — pass something like `"crit_hit"` or
    `"safehouse_rest"`. It's NOT used to gate logic.
    """
    if world is None or getattr(world, "character", None) is None:
        return None
    if not isinstance(delta, int):
        delta = int(delta)
    if delta == 0:
        return None

    char = world.character
    # P27.7 — showman passive multiplies positive audience gains.
    if delta > 0:
        try:
            from ..systems import class_features as _cf
            mul = _cf.audience_multiplier(char)
            if mul != 1.0:
                delta = max(1, int(round(delta * mul)))
        except Exception:
            pass
    before = max(_AUDIENCE_MIN, min(int(char.audience_rating or 0), _AUDIENCE_MAX))
    after = max(_AUDIENCE_MIN, min(before + delta, _AUDIENCE_MAX))
    char.audience_rating = after

    # Reset the idle-decay counter — something interesting happened.
    setattr(world, "audience_idle_minutes", 0)

    # P27 — viewer-count HUD sparkline: track recent audience values so
    # the top bar can render a tiny trend graph. Bounded to 32 entries.
    history = getattr(world, "audience_history", None)
    if history is None:
        world.audience_history = []
        history = world.audience_history
    history.append(after)
    if len(history) > 32:
        del history[:-32]

    if emit_log and hasattr(world, "log"):
        sign = "+" if delta > 0 else ""
        # P28.8: route through log_msg so the P28.6 dedupe collapses
        # repeated "Widownia +2" entries into "Widownia +2 (×N)". This
        # was THE source of the visible bleed bug — direct .append
        # bypassed dedupe and the entries piled up adjacent to each
        # other in the log.
        if hasattr(world, "log_msg"):
            world.log_msg(f"Widownia {sign}{delta}", "system")
        else:
            world.log.append((f"Widownia {sign}{delta}", "system"))

    if after == before:
        return None

    band_before = band_for(before)
    band_after  = band_for(after)
    if band_before == band_after:
        return None

    crossing = BandCrossing(
        from_band=band_before,
        to_band=band_after,
        direction=1 if after > before else -1,
    )
    _emit_band_crossing(world, crossing)
    return crossing


def tick_decay(world, minutes_elapsed: int) -> None:
    """Apply idle-time decay. Called by the time-advance code each time
    an action consumes minutes. After 2 in-game hours of no audience
    change, the rating drops by 1 per subsequent in-game hour.

    Safe to call when current_floor / character are missing — does
    nothing in that case.
    """
    if world is None or getattr(world, "character", None) is None:
        return
    if not isinstance(minutes_elapsed, int) or minutes_elapsed <= 0:
        return

    idle = int(getattr(world, "audience_idle_minutes", 0) or 0)
    idle += minutes_elapsed
    rating = int(world.character.audience_rating or 0)

    # Grace period — no decay yet.
    if idle < _IDLE_DECAY_GRACE_MINUTES:
        setattr(world, "audience_idle_minutes", idle)
        return

    # Past grace: every additional `_IDLE_DECAY_MINUTES_PER_TICK` minutes
    # subtracts 1. Track the remainder in `audience_idle_minutes`.
    over = idle - _IDLE_DECAY_GRACE_MINUTES
    decay_steps = over // _IDLE_DECAY_MINUTES_PER_TICK
    if decay_steps > 0 and rating > _AUDIENCE_MIN:
        change_audience(world, -int(decay_steps), source="boredom",
                        emit_log=False)
        # Consume the steps from the accumulator.
        setattr(world, "audience_idle_minutes",
                _IDLE_DECAY_GRACE_MINUTES +
                (over - decay_steps * _IDLE_DECAY_MINUTES_PER_TICK))
    else:
        setattr(world, "audience_idle_minutes", idle)


def safehouse_rest_decay(world, hours: int) -> None:
    """Steeper decay applied when the player rests in a safehouse. The
    audience gets bored quickly when the show stops.

    −2 per in-game hour of rest. Called by the rest handler in `game.py`
    after the rest's time-cost has been booked.
    """
    if world is None or hours <= 0:
        return
    change_audience(world, -2 * int(hours), source="safehouse_rest")


# ── Internal ───────────────────────────────────────────────────────────────

def _emit_band_crossing(world, crossing: BandCrossing) -> None:
    """Log a narrator line for the band crossing and, when reaching VIRAL,
    bump all sponsor `audience_high_band` attention paths through the
    sponsor engine (lazily imported to avoid a cycle)."""
    from ..systems import narrator
    if crossing.direction > 0:
        # Rising: pick the "interest growing" narrator pool.
        line = narrator.say("audience_rise", band=band_label(crossing.to_band))
    else:
        line = narrator.say("audience_drop", band=band_label(crossing.to_band))
    if line and hasattr(world, "log"):
        # P28.8: route through log_msg for dedupe consistency.
        if hasattr(world, "log_msg"):
            world.log_msg(line, "narrator")
        else:
            world.log.append((line, "narrator"))

    # Hand-off to sponsor engine: a VIRAL crossing is itself a "spectacle"
    # signal that several sponsors care about.
    if crossing.to_band == BAND_VIRAL and crossing.direction > 0:
        try:
            from . import sponsors as _sp
            _sp.note_player_tag(world, TAG_VIRAL_BAND, weight=1)
        except Exception:
            # Engine must work even if the sponsor module fails to import
            # (e.g. tests stubbing out the world). Audience itself stays.
            pass
