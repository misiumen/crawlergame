"""P29.18 — Show producer / director interventions.

The reality-TV layer of the game has audience meters, sponsor
chatter, drop pods — but no one was injecting events FROM the
studio. This module fixes that: random pacing breaks ("REKLAMA!"),
forced spectacle ("rotacja kamery"), audience polls, and unscripted
producer cuts. They fire from time_system.advance via maybe_fire()
and keep the dungeon feeling like a broadcast instead of a quiet
roguelike.

Design constraints:
  * Every event must be NO-OP-safe — no required input, no UI
    state changes that would freeze the game.
  * Audience-band gated: only fire when band >= warming. A cold
    audience means no producer is watching, so no interventions.
  * Per-floor cap: at most 4 director events per floor so they
    don't drown the room descriptions.
  * Cooldown: at least 8 in-game minutes between events to prevent
    spam after a fast burst of actions.

Public API:
    maybe_fire(world) -> Optional[str]
        Try to fire a director event. Returns the event id on
        fire (also logged through world.log_msg), or None.
    list_events() -> list[dict]
        Static catalog of event definitions. Test-friendly.
"""
from __future__ import annotations
import random
from typing import Optional, List, Dict


# Per-floor cap. Lives on world.current_floor.state["director_event_count"]
_MAX_PER_FLOOR = 4

# Minimum minutes between events.
_COOLDOWN_MIN = 8

# Per-call fire probability (rolled inside maybe_fire). Tuned so a
# typical 30-minute floor lap fires 1-3 events.
_FIRE_CHANCE = 0.18


# Event catalog. Each entry:
#   id           — stable str key for logs / tests
#   weight       — relative pick probability
#   min_band     — minimum audience band ("warming" / "hot" / "viral")
#   apply(world) — side-effect function, returns Polish log line
#                  (or "" to skip the log)
def _ev_reklama(world) -> str:
    """REKLAMA! 5-second commercial pause heals 5 HP and bumps
    audience +1 (sponsors got a slot)."""
    ch = world.character
    pre = ch.hp
    ch.heal(5)
    post = ch.hp
    try:
        from . import audience as _aud
        _aud.change_audience(world, 1, source="director_reklama",
                             emit_log=False)
    except Exception:
        pass
    delta = post - pre
    if delta > 0:
        return (f"REKLAMA! Studio puszcza spot sponsora — w międzyczasie "
                f"odzyskujesz {delta} HP. Sponsorzy mile widzą widownię.")
    return ("REKLAMA! Studio puszcza spot sponsora. Twoje HP było już "
            "pełne, ale widownia rośnie i tak.")


def _ev_kamera(world) -> str:
    """Rotacja kamery — sets a one-room "spectacle expected" flag
    on the CHARACTER (so it survives save/load — world.flags is
    not serialized). Audience consumers read
    `character.flags['kamera_glowna']`."""
    ch = world.character
    if ch.flags is None:
        ch.flags = {}
    ch.flags["kamera_glowna"] = True
    return ("ROTACJA KAMERY. Reżyser kieruje główne ujęcie na ciebie. "
            "Następna akcja powinna być widowiskowa.")


def _ev_ankieta(world) -> str:
    """Audience poll — randomly favors one of two flavors and
    bumps that sponsor's attention. Flavor-only event."""
    polls = [
        ("Czy crawler powinien zabijać bossów na czas?",
         "sport_safety", 2),
        ("Czy widzowie wolą walkę czy chemię?",
         "novachem_biotech", 2),
        ("Czy crawler jest jedynym uczciwym uczestnikiem?",
         "stadion_wolnosci", 2),
        ("Czy długi należy spłacać czy unikać?",
         "bractwo_komornika", 1),
        ("Czy stealth to jeszcze sport?",
         "spoldzielnia_mrowek", 1),
    ]
    rng = random.Random(world.current_floor.current_minute)
    question, skey, atti = rng.choice(polls)
    try:
        from . import sponsors as _sp
        _sp.adjust_attention(world, skey, atti)
    except Exception:
        pass
    return (f"ANKIETA: „{question}” Wynik nie ma znaczenia — "
            f"sponsor ({skey}) bierze sobie +{atti} uwagi.")


def _ev_cut(world) -> str:
    """Unscripted producer cut — a brief audio glitch + audience
    -1. Negative event, fires only when audience is HOT+ (the studio
    is tired of you)."""
    try:
        from . import audience as _aud
        _aud.change_audience(world, -1, source="director_cut",
                             emit_log=False)
    except Exception:
        pass
    return ("CIĘCIE: producent wycina twoją kwestię i przechodzi "
            "do reklamy. Widownia traci wątek.")


def _ev_dramatic_zoom(world) -> str:
    """Dramatic zoom — if the player has a wielded weapon, set a
    one-room +1 attack bonus flag on character.flags so combat
    can consume it. Otherwise audience +1 only."""
    ch = world.character
    if ch.flags is None:
        ch.flags = {}
    if ch.wielded_main_id is not None:
        ch.flags["dramatic_zoom_attack"] = 1
        return ("ZBLIŻENIE NA BROŃ. Następny atak w tej rundzie ma "
                "+1 do trafienia — kamera lubi twoją broń.")
    try:
        from . import audience as _aud
        _aud.change_audience(world, 1, source="director_zoom",
                             emit_log=False)
    except Exception:
        pass
    return ("ZBLIŻENIE. Reżyser nie ma na czym zatrzymać oka, "
            "ale widownia kupiła moment refleksji.")


EVENTS: List[Dict] = [
    {"id": "reklama",        "weight": 4, "min_band": "warming",
     "apply": _ev_reklama},
    {"id": "kamera",         "weight": 3, "min_band": "warming",
     "apply": _ev_kamera},
    {"id": "ankieta",        "weight": 2, "min_band": "warming",
     "apply": _ev_ankieta},
    {"id": "cut",            "weight": 2, "min_band": "hot",
     "apply": _ev_cut},
    {"id": "dramatic_zoom",  "weight": 3, "min_band": "warming",
     "apply": _ev_dramatic_zoom},
]


_BAND_ORDER = {"cold": 0, "warming": 1, "hot": 2, "viral": 3}


def list_events() -> List[Dict]:
    """Test helper — non-mutating view of the catalog."""
    return [{k: v for k, v in e.items() if k != "apply"} for e in EVENTS]


def _floor_state(world):
    f = getattr(world, "current_floor", None)
    if f is None:
        return None
    if not hasattr(f, "state") or f.state is None:
        f.state = {}
    return f.state


def maybe_fire(world, *, rng: Optional[random.Random] = None,
               force: bool = False) -> Optional[str]:
    """Roll for a director event. Returns the event id if fired.

    Caller (time_system.advance) invokes this once per tick. Returns
    None on:
      * no world / character / floor
      * audience band below "warming"
      * per-floor cap reached
      * cooldown not elapsed
      * fire-chance roll failed (unless force=True)
    """
    if world is None or world.character is None:
        return None
    f = world.current_floor
    if f is None:
        return None
    fstate = _floor_state(world)
    if fstate is None:
        return None
    # Audience-band gate.
    rating = int(world.character.audience_rating or 0)
    try:
        from . import audience as _aud
        band = _aud.band_for(rating)
    except Exception:
        return None
    if _BAND_ORDER.get(band, 0) < _BAND_ORDER["warming"]:
        return None
    # Per-floor cap.
    fired = int(fstate.get("director_event_count", 0))
    if fired >= _MAX_PER_FLOOR:
        return None
    # Cooldown.
    last_min = int(fstate.get("director_last_minute", -10_000))
    now = int(getattr(f, "current_minute", 0) or 0)
    if (now - last_min) < _COOLDOWN_MIN:
        return None
    # Probability roll (skipped with force).
    # P29.28 — seed RNG with the clock + audience rating so two
    # advance() ticks at the same in-game minute roll the same number
    # (helps debug-replay and stops within-tick double-fire when a
    # caller advances zero minutes twice).
    rng = rng or random.Random(now * 1000 + rating)
    if not force and rng.random() >= _FIRE_CHANCE:
        return None
    # Pick an event respecting min_band.
    eligible = [e for e in EVENTS
                if _BAND_ORDER.get(e["min_band"], 0) <= _BAND_ORDER.get(band, 0)]
    if not eligible:
        return None
    weights = [e["weight"] for e in eligible]
    pick = rng.choices(eligible, weights=weights, k=1)[0]
    # Fire.
    try:
        line = pick["apply"](world)
    except Exception:
        return None
    fstate["director_event_count"] = fired + 1
    fstate["director_last_minute"] = now
    if line and hasattr(world, "log_msg"):
        world.log_msg(line, "syndicate")
    return pick["id"]
