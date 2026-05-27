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
        unlocks = list(meta.get("unlocks", []) or [])
        if "new_game_plus" not in unlocks:
            unlocks.append("new_game_plus")
        meta["unlocks"] = unlocks
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
