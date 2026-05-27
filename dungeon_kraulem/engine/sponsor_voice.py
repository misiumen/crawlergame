"""Sponsor voice bus — proactive sponsor chatter (Prompt 27).

When a tag-bus event of significance fires (`note_player_tag` with
weight >= 2), this module rolls to surface a Polish quip from the
floor's primary sponsor (or another high-attention sponsor) into the
player's log. Surfaced as LOG_SYNDIC entries, which already display the
avatar gutter (P24.5).

Why this matters: pre-P27 sponsors were mechanically present but
narratively invisible. Audience moved, attention adjusted, hunters
maybe spawned — but the sponsor never *spoke*. The voice bus is what
sells the "you're on TV and the network execs are watching" feeling.

Public API:
    maybe_speak(world, tag, weight)         — call after note_player_tag
                                              when something dramatic
                                              happened. Sponsors might
                                              chime in.

Authoring:
    Voice lines live in `content/data/sponsor_voice_lines.py`. Each
    sponsor has a dict keyed by tag, with a list of one-liner Polish
    quips. The bus picks one at random per fire. New tags fall back
    silently (no quip = no chatter).
"""
from __future__ import annotations
import random as _r
from typing import Optional


# Cooldown — same sponsor won't speak again until N in-game minutes
# pass. Keeps banter from spamming during a 10-round combat.
COOLDOWN_MINUTES = 5

# Per-sponsor probability of chiming in when their library has a line
# for the tag. Primary floor sponsor speaks more often.
PROB_PRIMARY = 0.50
PROB_OTHER   = 0.15


def maybe_speak(world, tag: str, weight: int = 1,
                *, rng: Optional[_r.Random] = None) -> None:
    """Roll for a sponsor to chime in about the player's recent action.

    Args:
        world: WorldState
        tag:   the tag-bus event that just fired (e.g. "kill_lethal",
               "butchered_corpse", "crossfire")
        weight: how dramatic the event was; only weight >= 2 events
                trigger voice-bus rolls (so a single audience-bump
                doesn't trigger banter)

    Safe-noop when:
      - world or tag is None
      - sponsor lines module isn't loadable
      - no sponsor has a line for this tag
    """
    if world is None or not tag or weight < 2:
        return
    try:
        from ..content.data.sponsor_voice_lines import VOICE_LINES
        from . import sponsors as _sp
    except Exception:
        return
    rng = rng or _r.Random()
    primary = _sp.current_floor_sponsor_key(world)
    now_min = _now_minute(world)
    speakers = _candidate_speakers(world, tag, primary)
    for sponsor_key in speakers:
        lines = VOICE_LINES.get(sponsor_key, {}).get(tag)
        if not lines:
            continue
        # Cooldown gate.
        last_min = _last_voice_minute(world, sponsor_key)
        if (now_min - last_min) < COOLDOWN_MINUTES:
            continue
        # Probability gate.
        p = PROB_PRIMARY if sponsor_key == primary else PROB_OTHER
        if rng.random() > p:
            continue
        # Pick a line + emit it.
        line = rng.choice(lines)
        sponsor_name = _sp.SPONSORS.get(sponsor_key, {}).get(
            "name_fallback", sponsor_key)
        formatted = f"{sponsor_name}: „{line}”"
        try:
            world.log_msg(formatted, "syndicate")
        except Exception:
            pass
        # P27 — chime before sponsor speaks. Silent until assets/sfx/
        # sponsor_chime.ogg drops.
        try:
            from ..ui import audio as _audio
            _audio.play_sfx("sponsor_chime")
        except Exception:
            pass
        _stamp_voice_minute(world, sponsor_key, now_min)
        # Only one sponsor per event — first roll that fires wins.
        return


def _candidate_speakers(world, tag: str, primary: str) -> list:
    """Sponsors who MIGHT speak about this tag.

    P29.2: primary may be "" (no sponsor has attention yet). In that
    case ANY sponsor whose likes/dislikes match the tag is a
    candidate — early-game sponsors should still be able to speak
    once before anyone's locked in primary. After a primary
    emerges, they go first and other sponsors only chime in if they
    have meaningful attention.
    """
    from . import sponsors as _sp
    out = []
    if primary and primary in _sp.SPONSORS:
        out.append(primary)
    # Find tag-matching sponsors. Threshold depends on whether we
    # already have a primary: 3+ attention if yes (gating noise),
    # any tag-match if no (early-game open mic).
    attention = getattr(world, "sponsor_attention", {})
    if not isinstance(attention, dict):
        # fallback if stored on character flags instead
        char = getattr(world, "character", None)
        if char and isinstance(getattr(char, "flags", None), dict):
            attention = char.flags.get("sponsor_attention") or {}
        else:
            attention = {}
    early_game = (primary == "")
    for skey, sdata in _sp.SPONSORS.items():
        if skey == primary:
            continue
        if (tag not in (sdata.get("likes_tags") or [])
                and tag not in (sdata.get("dislikes_tags") or [])):
            continue
        if not early_game:
            if abs(int(attention.get(skey, 0) or 0)) < 3:
                continue
        out.append(skey)
    return out


def _now_minute(world) -> int:
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return 0
    return int(getattr(floor, "current_minute", 0) or 0)


def _last_voice_minute(world, sponsor_key: str) -> int:
    book = getattr(world, "sponsor_voice_last", None)
    if not book:
        return -COOLDOWN_MINUTES - 1
    return int(book.get(sponsor_key, -COOLDOWN_MINUTES - 1))


def _stamp_voice_minute(world, sponsor_key: str, minute: int) -> None:
    book = getattr(world, "sponsor_voice_last", None)
    if book is None:
        world.sponsor_voice_last = {}
        book = world.sponsor_voice_last
    book[sponsor_key] = int(minute)
