"""CRAWL PROTOCOL - Achievement system (Step 3, bilingual).

Achievements have stable ASCII keys; names/descriptions live in
locales/pl.json and locales/en.json via tr().

Saves store only a list of unlocked keys (Character.unlocked_achievements),
so this module can grow new entries without breaking old saves.

Usage:
    from achievements import unlock, is_unlocked, catalog_keys
    unlock(player, "first_blood", log_callback=game.msg)
"""
from dataclasses import dataclass
from typing import Optional, Callable, List

from lang import tr


@dataclass
class Achievement:
    key: str                  # stable ASCII id; never displayed
    reward_type: str = "none" # none | xp | credits
    reward_value: int = 0

    @property
    def name(self) -> str:
        return tr(f"achievement_{self.key}_n")

    @property
    def description(self) -> str:
        return tr(f"achievement_{self.key}_d")


# Catalog keyed by stable id. Localized strings live in JSON.
ACHIEVEMENT_CATALOG = {
    "first_blood":      Achievement("first_blood",      "xp", 25),
    "floor_1":          Achievement("floor_1",          "xp", 100),
    "still_standing":   Achievement("still_standing",   "xp", 150),
    "hybrid":           Achievement("hybrid",           "xp", 75),
    "env_kill":         Achievement("env_kill",         "credits", 40),
    "safehouse":        Achievement("safehouse",        "xp", 30),
    "crawler_friend":   Achievement("crawler_friend",   "credits", 50),
    "crawler_enemy":    Achievement("crawler_enemy",    "xp", 60),
    "race_picked":      Achievement("race_picked",      "xp", 50),
}


def catalog_keys() -> List[str]:
    return list(ACHIEVEMENT_CATALOG.keys())


def is_unlocked(player, key: str) -> bool:
    return key in getattr(player, "unlocked_achievements", [])


def unlock(player, key: str, log_callback: Optional[Callable] = None) -> bool:
    """
    Mark an achievement as unlocked on the player. Applies reward and logs
    via the callback (typically Game.msg). Returns True if newly unlocked.
    """
    if not hasattr(player, "unlocked_achievements"):
        return False
    if key in player.unlocked_achievements:
        return False
    ach = ACHIEVEMENT_CATALOG.get(key)
    if ach is None:
        return False

    player.unlocked_achievements.append(key)

    # Apply reward
    if ach.reward_type == "xp" and ach.reward_value:
        try:
            player.add_xp(ach.reward_value)
        except Exception:
            pass
    elif ach.reward_type == "credits" and ach.reward_value:
        player.credits = getattr(player, "credits", 0) + ach.reward_value

    if log_callback:
        line = tr("achievement_unlocked", name=ach.name)
        try:
            log_callback(line, "success")
        except TypeError:
            # callback may have a different signature
            log_callback(line)

    return True
