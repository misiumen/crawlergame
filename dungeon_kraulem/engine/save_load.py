"""Dungeon Kraulem save/load.

Persistent state lives in `dungeon_kraulem_save.json`. The previous file
name (`revamp_save.json`) is auto-migrated on first load so saves made
before the package rename keep working.
"""
import json
import os

from .world import WorldState

SAVE_FILE = "dungeon_kraulem_save.json"
LEGACY_SAVE_FILE = "revamp_save.json"
SAVE_VERSION = 1


def _resolve_save_path() -> str:
    """Return the path we should READ from. Prefer the new name; fall
    back to the legacy file if only that exists. Writes always use the
    new name."""
    if os.path.exists(SAVE_FILE):
        return SAVE_FILE
    if os.path.exists(LEGACY_SAVE_FILE):
        return LEGACY_SAVE_FILE
    return SAVE_FILE


def save(world: WorldState) -> bool:
    data = world.to_dict()
    data["version"] = SAVE_VERSION
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except (OSError, TypeError):
        return False


def load() -> WorldState | None:
    path = _resolve_save_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("version") != SAVE_VERSION:
        return None
    try:
        return WorldState.from_dict(data)
    except Exception:
        return None


def exists() -> bool:
    return os.path.exists(SAVE_FILE) or os.path.exists(LEGACY_SAVE_FILE)


def delete():
    for p in (SAVE_FILE, LEGACY_SAVE_FILE):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
