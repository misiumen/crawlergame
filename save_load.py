"""CRAWL PROTOCOL v2 - Save and load system."""
import json
import os

SAVE_FILE = "savegame.json"
SAVE_VERSION = 2


def save_game(player, floor=None):
    """Write game state to JSON. floor is a Floor instance (optional)."""
    from character import Character
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
    """Load game state from JSON. Returns (player, floor_dict) or (None, None)."""
    if not os.path.exists(SAVE_FILE):
        return None, None
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != SAVE_VERSION:
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
