"""P29.26 — Persistent run history / leaderboard / NewGame+ unlocks.

The audit named this the headline DCC feature. Reality-TV runs are
sequels — each season builds on the last. P29.26 makes that real:

  * Every death and every victory appends a `RunSummary.to_dict()`
    entry to `dungeon_kraulem_runs.json` (next to the save files).
  * The file also holds a small `meta` dict with cumulative counters
    (total_runs, victories, fans_total) + a `unlocks` set for
    NewGame+ flags.
  * A title-screen "Wyniki sezonu" overlay reads the file and shows
    the top entries by audience peak.

This module is import-safe — every read/write is wrapped in
try/except OSError so failures degrade silently to "no history."

Public API:
    record_run(world, *, victory: bool) -> dict | None
        Append the current run's RunSummary to history. Returns the
        appended entry on success, or None.
    history() -> list[dict]
        Load the full history list (latest first), empty on missing
        file.
    leaderboard(n=10, key="audience_peak") -> list[dict]
        Sorted view of `history()`, top-N by `key`.
    meta() -> dict
        Read the cumulative meta block (total_runs, victories,
        fans_total, unlocks).
    unlock(key: str) -> None
        Add a NewGame+ unlock key to meta["unlocks"].
    has_unlock(key: str) -> bool
        Convenience reader.
    reset() -> None
        Test helper — wipe the history file.

File layout:
    {
      "version": 1,
      "meta": {
        "total_runs": int,
        "victories": int,
        "fans_total": int,
        "unlocks": ["new_game_plus", ...]
      },
      "runs": [<RunSummary.to_dict()>, ...]
    }
"""
from __future__ import annotations
import json
import os
from typing import Dict, List, Optional, Any


HISTORY_FILE = "dungeon_kraulem_runs.json"
HISTORY_VERSION = 1


def _empty_payload() -> Dict[str, Any]:
    return {
        "version": HISTORY_VERSION,
        "meta": {
            "total_runs": 0,
            "victories": 0,
            "fans_total": 0,
            "unlocks": [],
        },
        "runs": [],
    }


def _load_raw() -> Dict[str, Any]:
    """Read the history file. Returns empty payload on missing /
    corrupt file."""
    if not os.path.exists(HISTORY_FILE):
        return _empty_payload()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _empty_payload()
    # Defensive normalisation — guarantee every expected field.
    if not isinstance(data, dict):
        return _empty_payload()
    data.setdefault("version", HISTORY_VERSION)
    meta = data.setdefault("meta", {})
    meta.setdefault("total_runs", 0)
    meta.setdefault("victories", 0)
    meta.setdefault("fans_total", 0)
    meta.setdefault("unlocks", [])
    data.setdefault("runs", [])
    return data


def _save_raw(payload: Dict[str, Any]) -> bool:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True
    except (OSError, TypeError):
        return False


# ── Public API ──────────────────────────────────────────────────────────

def record_run(world, *, victory: bool) -> Optional[Dict[str, Any]]:
    """Append the current run's RunSummary to history + bump meta
    counters. Returns the appended entry, or None on failure / no
    world. On victory: stamps the new_game_plus unlock."""
    if world is None or world.character is None:
        return None
    try:
        from . import run_summary as _rs
        rs = _rs.build_run_summary(world)
    except Exception:
        return None
    entry = rs.to_dict()
    entry["victory"] = bool(victory)
    payload = _load_raw()
    payload["runs"].insert(0, entry)   # newest first
    # Cap the file at a reasonable size — keep the most recent 200.
    if len(payload["runs"]) > 200:
        payload["runs"] = payload["runs"][:200]
    # Meta updates.
    meta = payload["meta"]
    meta["total_runs"] = int(meta.get("total_runs", 0)) + 1
    if victory:
        meta["victories"] = int(meta.get("victories", 0)) + 1
    # P29.34 — NG+ removed. Per-run unlock evaluation lives in
    # engine.meta_progression.evaluate_run_for_unlocks. That module
    # writes its findings via run_history.unlock(key) for each
    # qualifying unlock — additive options at character creation,
    # not a "harder mode" flag.
    # fans_total = cumulative sum of audience_peak across runs.
    meta["fans_total"] = int(meta.get("fans_total", 0)) + \
                         int(entry.get("audience_peak", 0))
    if _save_raw(payload):
        return entry
    return None


def history() -> List[Dict[str, Any]]:
    """Return the runs list (newest first), or empty list."""
    return list(_load_raw()["runs"])


def leaderboard(n: int = 10,
                key: str = "audience_peak") -> List[Dict[str, Any]]:
    """Top-N entries by the given field. Defaults to audience_peak."""
    rows = history()
    rows.sort(key=lambda r: int(r.get(key, 0)), reverse=True)
    return rows[:max(0, int(n))]


def meta() -> Dict[str, Any]:
    return dict(_load_raw()["meta"])


def unlock(key: str) -> None:
    if not key:
        return
    payload = _load_raw()
    unlocks = list(payload["meta"].get("unlocks", []) or [])
    if key not in unlocks:
        unlocks.append(key)
        payload["meta"]["unlocks"] = unlocks
        _save_raw(payload)


def has_unlock(key: str) -> bool:
    return key in (_load_raw()["meta"].get("unlocks", []) or [])


def reset() -> None:
    """Wipe the history file. For tests."""
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except OSError:
            pass


# ── P29.57e — Boss codex (persistent między runami) ─────────────────
#
# Wiercimajster trener w safehouse czyta z tego słownika. Każdy boss
# którego gracz spotkał / zabił / któremu uciekł zostaje tu zapisany.
# Klucz = entity.key (stabilny przez templates). Wartość:
#   {
#     "name": "Pyskaty Bandzior",
#     "rank": "miejski",
#     "hp_max": 60, "ac": 14,
#     "vulnerable_to": ["acid", "fire"],
#     "damage_type": "electric",
#     "fates": {"killed": 3, "escaped": 1, "died_elsewhere": 0},
#     "last_seen_floor": 5,
#   }
#
# DCC „next run knowledge" — gracz buduje codex przez sezony.


def _codex_entry_from_entity(ent, floor_num: int) -> Dict[str, Any]:
    """Snapshot relevantnych pól bossa do codexu (Polish-only names)."""
    from . import boss_ranks as _br
    return {
        "name": getattr(ent, "fallback_name", "") or "",
        "rank": _br.rank_from_entity(ent),
        "hp_max": int(getattr(ent, "max_hp", 0) or 0),
        "ac": int(getattr(ent, "ac", 10) or 10),
        "damage_dice": getattr(ent, "damage_dice", "") or "",
        "damage_type": getattr(ent, "damage_type", "") or "",
        "vulnerable_to": list(getattr(ent, "vulnerable_to", None) or []),
        "fates": {"killed": 0, "escaped": 0, "died_elsewhere": 0},
        "last_seen_floor": int(floor_num or 1),
    }


def _record_boss_fate(ent, floor_num: int, fate: str
                      ) -> Optional[Dict[str, Any]]:
    """Wewnętrzne — updateuje codex.boss[key] o nowy fate.
    Stabilne wobec brakującego entity / nieistniejącej rangi."""
    if ent is None:
        return None
    key = getattr(ent, "key", "") or ""
    if not key:
        return None
    payload = _load_raw()
    codex = payload["meta"].setdefault("boss_codex", {})
    entry = codex.get(key) or _codex_entry_from_entity(ent, floor_num)
    fates = entry.setdefault("fates",
                             {"killed": 0, "escaped": 0,
                              "died_elsewhere": 0})
    if fate not in fates:
        fates[fate] = 0
    fates[fate] = int(fates[fate]) + 1
    entry["last_seen_floor"] = int(floor_num or 1)
    # Refresh stats — jeśli boss został rebalansowany w content patch,
    # ostatnia obserwacja wygrywa.
    fresh = _codex_entry_from_entity(ent, floor_num)
    for fld in ("name", "rank", "hp_max", "ac",
                "damage_dice", "damage_type", "vulnerable_to"):
        if fresh.get(fld):
            entry[fld] = fresh[fld]
    codex[key] = entry
    payload["meta"]["boss_codex"] = codex
    if _save_raw(payload):
        return entry
    return None


def record_boss_kill(ent, floor_num: int) -> Optional[Dict[str, Any]]:
    """Player zabił bossa — dorzuca +1 do fates.killed."""
    return _record_boss_fate(ent, floor_num, "killed")


def record_boss_escape(ent, floor_num: int) -> Optional[Dict[str, Any]]:
    """Gracz zszedł piętro bez zabicia bossa (escape przez exit
    unlocked inną drogą) — +1 do fates.escaped."""
    return _record_boss_fate(ent, floor_num, "escaped")


def record_boss_died_elsewhere(ent, floor_num: int
                                ) -> Optional[Dict[str, Any]]:
    """Boss zginął od trapów / hazardów / faction crossfire — +1
    do died_elsewhere. Skrzynka NIE dropuje (DCC canon), ale codex
    notuje."""
    return _record_boss_fate(ent, floor_num, "died_elsewhere")


def boss_codex() -> Dict[str, Dict[str, Any]]:
    """Zwraca pełen codex (key → entry). Pusty dict gdy nikt
    jeszcze nie został zapisany."""
    return dict(_load_raw()["meta"].get("boss_codex", {}) or {})


def boss_codex_entry(boss_key: str) -> Optional[Dict[str, Any]]:
    """Wyszukuje entry po entity key. None gdy nieznany."""
    return boss_codex().get(boss_key)
