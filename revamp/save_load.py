"""Revamp save/load. Uses its own file, separate from v2 saves."""
import json
import os

from .world import WorldState

SAVE_FILE = "revamp_save.json"
SAVE_VERSION = 1


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
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
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
    return os.path.exists(SAVE_FILE)


def delete():
    if os.path.exists(SAVE_FILE):
        try:
            os.remove(SAVE_FILE)
        except OSError:
            pass
