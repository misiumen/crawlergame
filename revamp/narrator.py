"""Narrator — sarcastic Syndicate broadcast voice."""
import random
from .lang import t


CATEGORIES = (
    "impossible_action", "clever_action", "env_kill", "cowardice", "hiding",
    "betrayal", "helping_crawler", "bathroom_use", "coffee_use",
    "class_offer", "species_offer", "time_warning", "deadline",
    "audience_rise", "audience_drop", "crit_success", "crit_failure",
    "return_safehouse_wounded", "stupid_attempt", "repeated_pattern",
    "first_floor_open", "rest_taken",
)


def say(category: str, **fmt) -> str:
    """Pick a random localized narrator line for a category."""
    # Find up to 6 variants per category. Keys are like narrator_{cat}_1..6
    candidates = []
    for i in range(1, 7):
        key = f"narrator_{category}_{i}"
        line = t(key, fallback="")
        if line:
            candidates.append(line)
    if not candidates:
        return ""
    chosen = random.choice(candidates)
    try:
        return chosen.format(**fmt)
    except (KeyError, IndexError):
        return chosen
