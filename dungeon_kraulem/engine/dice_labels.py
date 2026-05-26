"""Polish-first labels for dice-roll log lines (P24.6 / P24.5-5).

Stat dict KEYS stay English (STR/DEX/CON/INT/WIS/CHA) for save-format
compatibility; only the DISPLAYED labels switch to Polish via these
helpers.

Public API:
    stat_pl(stat_key)         → "SIŁ" / "ZRĘ" / etc.
    level_pl(level_key)       → "sukces" / "porażka" / etc.
    intent_pl(intent_key)     → "[atak]" / "[odzysk]" / etc. (bracketed)
    format_check(intent, stat, raw, mod, total, dc, level, extras)
                              → one-liner ready for self.log(..., LOG_SYSTEM)
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple


STAT_LABELS_PL: Dict[str, str] = {
    "STR": "SIŁ",
    "DEX": "ZRĘ",
    "CON": "KON",
    "INT": "INT",
    "WIS": "MDR",
    "CHA": "CHA",
}


LEVEL_LABELS_PL: Dict[str, str] = {
    "critical_success": "kryt. sukces",
    "success":          "sukces",
    "partial_success":  "częśc. sukces",
    "failure":          "porażka",
    "critical_failure": "kryt. porażka",
    # Combat outcomes (used outside the level→narrator pipeline)
    "hit":              "trafienie",
    "miss":             "pudło",
    "crit":             "kryt",
    "fumble":           "fuks",
}


INTENT_LABELS_PL: Dict[str, str] = {
    "attack":         "atak",
    "salvage":        "odzysk",
    "harvest":        "zbiór",
    "loot":           "łup",
    "break":          "rozbicie",
    "hack":           "włam",
    "lockpick":       "wytrych",
    "force":          "wyłam",
    "use":            "użycie",
    "craft":          "rzemiosło",
    "deploy":         "rozstaw",
    "memetic":        "mem",
    "invoke_belief":  "przywołanie",
    "ucieczka":       "ucieczka",
    "flee":           "ucieczka",
    "normal":         "atak",
    "careful":        "ostrożny atak",
    "heavy":          "ryzykowny atak",
    "butcher_corpse": "patroszenie",
    "eat_corpse":     "spożycie",
    "exploit_weakness": "słab. punkt",
    "use_password":   "hasło",
    "intimidate":     "zastraszanie",
    "bribe":          "przekupstwo",
    "persuade":       "perswazja",
    "talk":           "rozmowa",
    "search":         "przeszukanie",
    "throw_at":       "rzut",
    "push_into":      "wepchnięcie",
    "lure":           "wabik",
    "coat_weapon":    "powłoka",
    "wield":          "dobycie",
    "sheathe":        "schowanie",
}


def stat_pl(stat_key: str) -> str:
    """Return the Polish abbreviation for a stat. Unknown keys pass
    through unchanged so authors see the raw key + investigate."""
    return STAT_LABELS_PL.get(stat_key, stat_key)


def level_pl(level_key: str) -> str:
    return LEVEL_LABELS_PL.get(level_key, level_key)


def intent_pl(intent_key: str) -> str:
    return INTENT_LABELS_PL.get(intent_key, intent_key)


def format_check(intent_key: str,
                 stat_key: str,
                 raw: int,
                 mod: int,
                 total: int,
                 dc: int,
                 level: Optional[str] = None,
                 *,
                 extras: Optional[List[Tuple[str, int]]] = None,
                 prefix: str = "  ") -> str:
    """Build a one-line dice-check log entry in Polish.

    Example:
        format_check("salvage", "STR", 13, 0, 13, 12, "success")
        → "  [odzysk] d20(13) + SIŁ(+0) = 13 vs TT 12 → sukces"

    `extras` adds bonus terms (e.g. [("tła", 1), ("bonus", 2)]) between
    the stat term and the total. Useful for combat to-hit bonuses,
    companion-advantage, etc.
    """
    sgn_mod = f"{mod:+d}"
    extras_str = ""
    if extras:
        parts = [f" + {label}({val:+d})" for label, val in extras]
        extras_str = "".join(parts)
    tail = ""
    if level:
        tail = f" → {level_pl(level)}"
    return (f"{prefix}[{intent_pl(intent_key)}] d20({raw}) + "
            f"{stat_pl(stat_key)}({sgn_mod}){extras_str} = "
            f"{total} vs TT {dc}{tail}")
