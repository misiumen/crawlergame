"""CRAWL PROTOCOL - Save and load system (v3, migrating from v2).

v3 changes:
  - Added Character fields: race, race_features, affinity, language_pref,
    known_npcs, relationships, materials, known_recipes, race_picked_at_floor.
  - Added Room fields: env_objects, npcs, safehouse_subtype, resolution_modes,
    inspected.
  - unlocked_achievements is now a list of stable keys (not English names).

Migration policy:
  - v3 saves are loaded directly.
  - v2 saves are migrated in memory on load (defaults filled in) and saved back
    as v3 on the next save_game() call.
  - Older / unknown versions are rejected.
"""
import json
import os

SAVE_FILE = "savegame.json"
SAVE_VERSION = 3
LEGACY_VERSIONS = (2,)


def save_game(player, floor=None):
    """Write game state to JSON. floor is a Floor instance (optional)."""
    data = {
        "version": SAVE_VERSION,
        "player": player.to_dict(),
        "floor": floor.to_dict() if floor else None,
    }
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except (OSError, TypeError):
        return False


def load_game():
    """Load game state. Returns (player, floor_dict) or (None, None)."""
    if not os.path.exists(SAVE_FILE):
        return None, None
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version")
        if version == SAVE_VERSION:
            pass  # OK as-is
        elif version in LEGACY_VERSIONS:
            data = _migrate(data, from_version=version)
        else:
            return None, None
        from character import Character
        player = Character.from_dict(data["player"])
        floor_data = data.get("floor")
        return player, floor_data
    except (OSError, json.JSONDecodeError, KeyError):
        return None, None


def delete_save():
    if os.path.exists(SAVE_FILE):
        try:
            os.remove(SAVE_FILE)
        except OSError:
            pass


def save_exists():
    return os.path.exists(SAVE_FILE)


# ── Migration ─────────────────────────────────────────────────────────────────

def _migrate(data: dict, from_version: int) -> dict:
    """Migrate save data in-place between versions. Returns same dict."""
    if from_version == 2:
        _migrate_v2_to_v3(data)
    data["version"] = SAVE_VERSION
    return data


def _migrate_v2_to_v3(data: dict):
    player = data.get("player", {}) or {}
    player.setdefault("race", None)
    player.setdefault("race_features", [])
    player.setdefault("race_picked_at_floor", None)
    player.setdefault("language_pref", "pl")
    player.setdefault("known_npcs", [])
    player.setdefault("relationships", {})
    player.setdefault("materials", {})
    player.setdefault("known_recipes", [])
    player.setdefault("affinity", {
        "melee": 0, "ranged": 0, "stealth": 0, "magic": 0,
        "tech": 0, "trap": 0, "env": 0, "support": 0, "social": 0,
    })
    player.setdefault("kill_method_history", [])

    # Achievements: v2 stored English names ("First Blood"). Map known
    # names to v3 stable keys; drop unknowns.
    name_to_key = {
        "First Blood": "first_blood",
        "Floor One Survivor": "floor_1",
        "Still Standing": "still_standing",
        "Hybrid Theory": "hybrid",
    }
    old_list = player.get("unlocked_achievements") or []
    migrated = []
    for entry in old_list:
        if not isinstance(entry, str):
            continue
        if entry in name_to_key:
            migrated.append(name_to_key[entry])
        elif "_" in entry and entry.islower():
            # Already a stable key
            migrated.append(entry)
    player["unlocked_achievements"] = migrated

    data["player"] = player

    # Floor migration: add empty env_objects / npcs / resolution_modes
    floor = data.get("floor")
    if isinstance(floor, dict):
        rooms = floor.get("rooms", {}) or {}
        for _, room in rooms.items():
            if not isinstance(room, dict):
                continue
            room.setdefault("env_objects", [])
            room.setdefault("npcs", [])
            room.setdefault("safehouse_subtype", None)
            room.setdefault("resolution_modes", ["combat"])
            room.setdefault("inspected", False)
