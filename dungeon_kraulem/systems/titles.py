"""P29.53s — Player titles (DCC reality-TV flavor).

Titles are short Polish honorifics earned by behavioral patterns,
distinct from achievements (which are one-shot unlocks). A title is a
rolling label that the player can wear — surfaces in UI top-bar /
victory screen / sponsor commentary lines.

Mechanic: every title is a rule `(predicate) -> title_key`. On any
tick or significant event, `recompute(world)` walks all rules,
adds qualifying titles to `character.flags["titles"]`. Removal is
optional — once earned, the title is sticky for the run (showrunner
remembers).
"""
from __future__ import annotations
from typing import Dict, List


# ── Catalog ──────────────────────────────────────────────────────────


# Each entry:
#   key       — internal id (also stored in flags["titles"])
#   label_pl  — display label in Polish (Dinniman tone)
#   describe  — short qualification line for tooltips / unlock log
#   rule      — callable(character) -> bool

def _kills_geq(n: int):
    return lambda ch: int(getattr(ch, "run_kills", 0) or 0) >= n


def _peak_audience_geq(n: int):
    return lambda ch: int(getattr(ch, "run_audience_peak", 0) or 0) >= n


def _floor_geq(n: int):
    return lambda ch: int(getattr(ch, "run_max_floor_reached", 1) or 1) >= n


def _flag_geq(key: str, n: int):
    return lambda ch: int((ch.flags or {}).get(key, 0)) >= n


def _flag_truthy(key: str):
    return lambda ch: bool((ch.flags or {}).get(key))


TITLES: List[Dict] = [
    {"key":"rzeznik",       "label_pl":"Rzeźnik",
     "describe":"50 zabójstw w tym runie.",
     "rule": _kills_geq(50)},
    {"key":"pacyfista",     "label_pl":"Pacyfista",
     "describe":"Zszedłeś z F1 bez ani jednego trupa.",
     "rule": lambda ch: bool((ch.flags or {})
                             .get("descended_pacifist", False))},
    {"key":"gwiazdor",      "label_pl":"Gwiazdor Kanału",
     "describe":"Twoja widownia osiągnęła VIRAL band.",
     "rule": _peak_audience_geq(80)},
    {"key":"medyk_polowy",  "label_pl":"Medyk Polowy",
     "describe":"20 wykorzystanych opatrunków / chemii.",
     "rule": _flag_geq("run_consumables_used", 20)},
    {"key":"klepacz_drzwi", "label_pl":"Klepacz Drzwi",
     "describe":"Wyłamałeś co najmniej 5 zamków.",
     "rule": _flag_geq("run_locks_broken", 5)},
    {"key":"saper",         "label_pl":"Saper",
     "describe":"30 rozstawionych pułapek.",
     "rule": lambda ch: int(getattr(ch, "run_traps_armed", 0) or 0) >= 30},
    {"key":"piwniczak",     "label_pl":"Piwniczak",
     "describe":"Dotarłeś do F10. Wpierdoliłeś się głęboko.",
     "rule": _floor_geq(10)},
    {"key":"finalista",     "label_pl":"Finalista Sezonu",
     "describe":"Skończyłeś sezon (F18). Showrunner cię pamięta.",
     "rule": _floor_geq(18)},
    {"key":"rzeznik_pieciu","label_pl":"Rzeźnik Piątego",
     "describe":"Zabicie minibossa na F5 lub niżej.",
     "rule": _flag_truthy("miniboss_killed_f5_plus")},
    {"key":"speedrunner",   "label_pl":"Speedrunner",
     "describe":"Zszedłeś z piętra w mniej niż 6 godzin gry.",
     "rule": _flag_truthy("descended_under_6h")},
]


def all_titles() -> List[Dict]:
    return list(TITLES)


def label_of(key: str) -> str:
    for t in TITLES:
        if t["key"] == key:
            return t["label_pl"]
    return key


# ── Runtime ──────────────────────────────────────────────────────────


def current_titles(character) -> List[str]:
    """Return list of title_keys the character currently has."""
    if character is None or character.flags is None:
        return []
    return list(character.flags.get("titles", []) or [])


def recompute(world) -> List[str]:
    """Re-evaluate every title rule. Append newly-qualified titles to
    `character.flags["titles"]`. Returns the list of NEWLY added title
    keys this call (for log lines)."""
    if world is None or getattr(world, "character", None) is None:
        return []
    ch = world.character
    if ch.flags is None:
        ch.flags = {}
    have = set(ch.flags.get("titles", []) or [])
    new_keys: List[str] = []
    for t in TITLES:
        if t["key"] in have:
            continue
        try:
            if t["rule"](ch):
                have.add(t["key"])
                new_keys.append(t["key"])
        except Exception:
            continue
    if new_keys:
        ch.flags["titles"] = list(have)
        # Log narrator lines for new titles.
        if hasattr(world, "log_msg"):
            for k in new_keys:
                lbl = label_of(k)
                try:
                    world.log_msg(
                        f"Showrunner przyznaje tytuł: „{lbl}”.",
                        "syndicate")
                except Exception:
                    pass
    return new_keys
