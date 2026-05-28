"""P29.53s — Mid-floor decisions + hidden objectives.

Two intertwined systems:

1. Mid-floor decisions (Wave 4 #O): every ~8 floor-hours of game time,
   a "show beat" fires that presents a tiny binary fork. Each fork has
   immediate consequences (audience / credits / HP / status). Logged
   as a tagged event; player typically can't interact directly with
   the choice — the showrunner picks for them based on current band
   (HOT picks the dramatic option, COLD picks the boring one). This
   keeps the show alive without breaking the parser.

2. Hidden objectives (Wave 4 #P): each floor seeds 1-2 hidden side
   goals on creation. They reveal themselves when the player crosses
   a specific behavioral threshold (e.g. „inspect 5 hazards on this
   floor", „kill a monster while at <25% HP"). Reward = audience +
   small loot queued to safehouse.

Both systems are time-gated and idempotent — calling tick() many
times on the same minute doesn't duplicate.
"""
from __future__ import annotations
import random as _r
from typing import Dict, List, Optional


# ── #O Mid-floor decisions ───────────────────────────────────────────


MID_FLOOR_BEAT_COOLDOWN_MIN = 8 * 60   # one beat every ~8 floor hours
MID_FLOOR_BEAT_CHANCE = 0.05


# Beats with two forks. `forks` are evaluated based on current band:
# HOT/VIRAL → drama (first fork). WARMING/COLD → mundane (second).
# `effect` is applied to character / audience.
MID_FLOOR_BEATS = [
    {"key":"sponsor_call",
     "intro":"Twój komunikator buczy. Sponsor chce wywiad na żywo.",
     "forks": [
        {"label":"Showrunner woli krew — odmawiasz, wraca do walki.",
         "effect":{"audience": 3},
         "tag":"refused_interview"},
        {"label":"Bierzesz wywiad. Sponsor składa kondolencje.",
         "effect":{"audience": -2, "credits": 8},
         "tag":"took_interview"},
     ]},

    {"key":"vending_choice",
     "intro":"Mijasz automat z napisem „TANIEJ DZIŚ”. Coś tam terkocze.",
     "forks": [
        {"label":"Kopiesz automat. Wypada batonik — i alarm.",
         "effect":{"hp": 2, "audience": 2},
         "tag":"kicked_vending"},
        {"label":"Idziesz dalej. Automat zostaje urażony.",
         "effect":{},
         "tag":"ignored_vending"},
     ]},

    {"key":"injured_crawler",
     "intro":"Inny crawler leży i prosi o opatrunek. Patrzy ci w oczy.",
     "forks": [
        {"label":"Mijasz go. Twardo i krótko.",
         "effect":{"audience": -3},
         "tag":"ignored_crawler"},
        {"label":"Dajesz opatrunek. Wzajemna ulga.",
         "effect":{"audience": 4, "credits": -3},
         "tag":"helped_crawler"},
     ]},

    {"key":"camera_swarm",
     "intro":"Stado kamer-dronów otacza cię, czekając na content.",
     "forks": [
        {"label":"Robisz pose. Kliki, ujęcia, plejszing.",
         "effect":{"audience": 5},
         "tag":"posed_for_camera"},
        {"label":"Zasłaniasz twarz, idziesz dalej.",
         "effect":{"audience": -1},
         "tag":"avoided_camera"},
     ]},
]


def _fire_mid_floor_beat(world, rng: _r.Random) -> Optional[dict]:
    from . import audience as _aud
    band = _aud.band_for(int(getattr(world.character,
                                     "audience_rating", 0) or 0))
    beat = rng.choice(MID_FLOOR_BEATS)
    # HOT/VIRAL → fork 0 (drama). WARMING/COLD → fork 1 (mundane).
    fork_idx = 0 if band in (_aud.BAND_HOT, _aud.BAND_VIRAL) else 1
    fork = beat["forks"][fork_idx]
    # Apply effects.
    ch = world.character
    fx = fork.get("effect") or {}
    if "audience" in fx:
        try:
            _aud.change_audience(world, int(fx["audience"]),
                                 source=f"beat:{beat['key']}")
        except Exception:
            pass
    if "hp" in fx and ch is not None:
        try:
            ch.hp = max(0, min(int(ch.max_hp or ch.hp),
                               int(ch.hp) + int(fx["hp"])))
        except Exception:
            pass
    if "credits" in fx and ch is not None:
        try:
            ch.credits = max(0, int(getattr(ch, "credits", 0) or 0)
                             + int(fx["credits"]))
        except Exception:
            pass
    # Tag for sponsor reactions.
    try:
        from . import sponsors as _sp
        _sp.note_player_tag(world, fork.get("tag", "beat"), weight=1)
    except Exception:
        pass
    # Log: intro + selected fork.
    if hasattr(world, "log_msg"):
        try:
            world.log_msg(beat["intro"], "syndicate")
            world.log_msg(f"   → {fork['label']}", "narrator")
        except Exception:
            pass
    return {"beat": beat["key"], "fork": fork.get("tag", "")}


# ── #P Hidden objectives ─────────────────────────────────────────────


# Each:
#   key       — internal id
#   describe  — Polish reveal line (shown when condition met)
#   reward    — dict: audience / item_key
#   condition — callable(character, floor) -> bool

def _objective_inspect_5_hazards(ch, _floor):
    return int((ch.flags or {}).get("floor_hazard_inspects", 0)) >= 5


def _objective_low_hp_kill(ch, _floor):
    return bool((ch.flags or {}).get("floor_low_hp_kill"))


def _objective_no_safehouse(ch, _floor):
    return bool((ch.flags or {}).get("floor_skipped_safehouse"))


def _objective_3_corpses_butchered(ch, _floor):
    return int((ch.flags or {}).get("floor_butchered", 0)) >= 3


HIDDEN_OBJECTIVES = [
    {"key":"hazard_inspector",
     "describe":"Ukryty cel: „Inspekcja Sponsora” odblokowany. "
                "Audytowałeś 5 zagrożeń.",
     "reward":{"audience": 6, "item_key": "stimpak"},
     "condition": _objective_inspect_5_hazards},

    {"key":"clutch_kill",
     "describe":"Ukryty cel: „Spektakl Krwawego Tygodnia”. "
                "Trup z resztką HP w żyłach.",
     "reward":{"audience": 8, "item_key": "adrenaline"},
     "condition": _objective_low_hp_kill},

    {"key":"hardcore_route",
     "describe":"Ukryty cel: „Marsz Bezdomny”. Zszedłeś z piętra "
                "bez wejścia do safehouse.",
     "reward":{"audience": 5, "item_key": "energy_bar"},
     "condition": _objective_no_safehouse},

    {"key":"butcher_squad",
     "describe":"Ukryty cel: „Domowa Wędliniarnia”. Pozyskałeś "
                "mięso z 3 trupów.",
     "reward":{"audience": 4, "item_key": "meat_chunk"},
     "condition": _objective_3_corpses_butchered},
]


def _check_hidden_objectives(world) -> List[str]:
    """Walk hidden objectives. For each newly-qualified one, mark
    completed in flags, queue reward, emit log. Returns the list of
    newly-completed objective keys."""
    if world is None or getattr(world, "character", None) is None:
        return []
    ch = world.character
    if ch.flags is None:
        ch.flags = {}
    completed = set(ch.flags.get("hidden_objectives_done", []) or [])
    floor = getattr(world, "current_floor", None)
    new: List[str] = []
    for obj in HIDDEN_OBJECTIVES:
        if obj["key"] in completed:
            continue
        try:
            if obj["condition"](ch, floor):
                completed.add(obj["key"])
                new.append(obj["key"])
                # Apply reward
                rw = obj.get("reward") or {}
                if "audience" in rw:
                    try:
                        from . import audience as _aud
                        _aud.change_audience(world, int(rw["audience"]),
                                             source=f"hidden:{obj['key']}")
                    except Exception:
                        pass
                if "item_key" in rw:
                    pending = getattr(world, "pending_sponsor_gifts",
                                      None)
                    if pending is None:
                        world.pending_sponsor_gifts = []
                        pending = world.pending_sponsor_gifts
                    pending.append({
                        "sponsor_key": "showrunner",
                        "item_key": rw["item_key"],
                        "source": f"hidden:{obj['key']}",
                    })
                # Reveal line
                if hasattr(world, "log_msg"):
                    try:
                        world.log_msg(obj["describe"], "success")
                    except Exception:
                        pass
        except Exception:
            continue
    if new:
        ch.flags["hidden_objectives_done"] = list(completed)
    return new


# ── Combined tick hook ───────────────────────────────────────────────


def tick(world, rng: Optional[_r.Random] = None) -> dict:
    """Combined hook called from time_system.advance. Returns a small
    dict noting which sub-system actually fired this tick (for tests
    + telemetry).

    Cadence:
      * Beat: random roll, cooldown enforced via flag.
      * Hidden objectives: cheap to check every tick.
    """
    out = {"beat": None, "hidden": []}
    if world is None or getattr(world, "current_floor", None) is None:
        return out
    ch = getattr(world, "character", None)
    if ch is None:
        return out
    if ch.flags is None:
        ch.flags = {}

    # Hidden objectives — cheap, no rng.
    new_hidden = _check_hidden_objectives(world)
    out["hidden"] = new_hidden

    # Mid-floor beat — gated by cooldown + RNG.
    now = int(getattr(world.current_floor, "current_minute", 0) or 0)
    last = int(ch.flags.get("_beat_last_min", -10**6))
    if now - last >= MID_FLOOR_BEAT_COOLDOWN_MIN:
        rng = rng or _r.Random(now * 17 + len(ch.flags))
        if rng.random() <= MID_FLOOR_BEAT_CHANCE:
            ch.flags["_beat_last_min"] = now
            fired = _fire_mid_floor_beat(world, rng)
            out["beat"] = fired
    return out
