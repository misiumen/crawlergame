"""P29.53s — Per-biome gimmicks (Wave 4 #U).

Each enabled FloorBiome gets one short, distinctive mechanical quirk
that fires periodically while the player is on a floor of that
biome. The quirks are intentionally light — they punctuate the biome
identity without overriding combat or the main objective.

Mechanic: every ~45 floor-minutes, `tick(world)` picks the player's
current biome and calls its gimmick handler. Each handler logs ~1
flavorful line and applies a tiny mechanical effect (small audience
bump, small status, small free credits etc).

The dispatch is purely table-driven — adding a new biome only needs
a new entry here.
"""
from __future__ import annotations
import random as _r
from typing import Callable, Dict, Optional


GIMMICK_COOLDOWN_MIN = 45


# ── Gimmick handlers ─────────────────────────────────────────────────
#
# Each handler signature: (world) -> Optional[str]
# Returns the log line emitted (or None when skipped).


def _gimmick_okopy_frontowe(world) -> Optional[str]:
    """Trenches: artyleria z poza pola walki — losowe HP -1, czasem
    znajdziesz brzęczący granat (1 credit-shrap = 1 kr)."""
    rng = _r.Random(int(getattr(world.current_floor,
                                "current_minute", 0) or 0))
    ch = world.character
    if rng.random() < 0.5:
        ch.hp = max(1, int(ch.hp) - 1)
        return ("Daleki wybuch wstrząsa stropem. Spada gruz. "
                "(−1 HP. Mat. opatrunkowy: opatrz.)")
    else:
        ch.credits = max(0, int(getattr(ch, "credits", 0) or 0) + 1)
        return ("Znajdujesz odłamek z dziwną grawerką: „1KR”. "
                "(+1 kredyt.)")


def _gimmick_zoo_korporacyjne(world) -> Optional[str]:
    """Zoo: zwierzaki sponsora kibicują pojedynkom (+widownia)."""
    try:
        from . import audience as _aud
        _aud.change_audience(world, 2, source="biome:zoo_korporacyjne")
    except Exception:
        return None
    return ("Klatki w korytarzu wybuchają piskiem zachwytu. "
            "Maskotki sponsora kibicują. (+2 widowni.)")


def _gimmick_muzeum_spektakli(world) -> Optional[str]:
    """Muzeum: showrunner recytuje archiwalne fragmenty z głośnika."""
    rng = _r.Random(int(getattr(world.current_floor,
                                "current_minute", 0) or 0) + 7)
    snippets = [
        "Sezon 2: „Crawler 17 jadł kamień. Kamień nie reagował.”",
        "Sezon 4: „Maskotka roku — koza, ponownie.”",
        "Sezon 1, finał: „Showrunner odmówił komentarza.”",
        "Sezon 9: „Nikt nie zgaduje, czemu ten sezon się nie liczy.”",
    ]
    return f"Z głośnika: {rng.choice(snippets)}"


def _gimmick_bar_skurczybyk(world) -> Optional[str]:
    """Bar: bezalkoholowa wódka regeneruje 2 HP raz na cooldown."""
    ch = world.character
    if int(ch.hp) >= int(ch.max_hp or ch.hp):
        return None
    healed = min(2, int(ch.max_hp or ch.hp) - int(ch.hp))
    ch.hp += healed
    return (f"Barman „Skurczybyk” podsuwa szot. Niby bezalkoholowa. "
            f"(+{healed} HP, nie pytaj o licencję.)")


def _gimmick_neighborhood(world) -> Optional[str]:
    """Osiedle: NPC krzyczą z balkonów (+1 widowni)."""
    try:
        from . import audience as _aud
        _aud.change_audience(world, 1, source="biome:neighborhood")
    except Exception:
        return None
    return ("Z balkonu piętro wyżej ktoś krzyczy: „NIE GAŚ ŚWIATŁA, "
            "OGLĄDAM!”. (+1 widowni.)")


# ── Dispatch ─────────────────────────────────────────────────────────


BIOME_GIMMICKS: Dict[str, Callable] = {
    "okopy_frontowe":    _gimmick_okopy_frontowe,
    "zoo_korporacyjne":  _gimmick_zoo_korporacyjne,
    "muzeum_spektakli":  _gimmick_muzeum_spektakli,
    "bar_skurczybyk":    _gimmick_bar_skurczybyk,
    "neighborhood":      _gimmick_neighborhood,
}


def tick(world) -> Optional[str]:
    """Fire the active biome's gimmick if cooldown is up. Return the
    emitted log line, or None."""
    if world is None or getattr(world, "current_floor", None) is None:
        return None
    ch = getattr(world, "character", None)
    if ch is None:
        return None
    if ch.flags is None:
        ch.flags = {}
    now = int(getattr(world.current_floor, "current_minute", 0) or 0)
    last = int(ch.flags.get("_gimmick_last_min", -10**6))
    if now - last < GIMMICK_COOLDOWN_MIN:
        return None
    biome = getattr(world.current_floor, "biome_key", "") or ""
    handler = BIOME_GIMMICKS.get(biome)
    if handler is None:
        return None
    try:
        line = handler(world)
    except Exception:
        return None
    if line and hasattr(world, "log_msg"):
        try:
            world.log_msg(line, "narrator")
        except Exception:
            pass
    ch.flags["_gimmick_last_min"] = now
    return line
