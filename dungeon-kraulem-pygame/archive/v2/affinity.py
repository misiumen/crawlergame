"""CRAWL PROTOCOL - Affinity tracking and class suggestion (Step 11).

Affinity is built per kill method (env, melee, ranged, stealth, ...).
When the player earns a class via Class Box (or hits level 3 unclassed),
we suggest the top-3 classes weighted by how the player has been playing.

Each ClassDef has an `affinity_weights` dict (added in classes.py).
"""
from typing import List, Dict


KIND_MELEE   = "melee"
KIND_RANGED  = "ranged"
KIND_STEALTH = "stealth"
KIND_MAGIC   = "magic"
KIND_TECH    = "tech"
KIND_TRAP    = "trap"
KIND_ENV     = "env"
KIND_SUPPORT = "support"
KIND_SOCIAL  = "social"

KINDS = (KIND_MELEE, KIND_RANGED, KIND_STEALTH, KIND_MAGIC,
         KIND_TECH, KIND_TRAP, KIND_ENV, KIND_SUPPORT, KIND_SOCIAL)


# Default affinity weights per class key (used until classes.py defines its own).
DEFAULT_CLASS_AFFINITY: Dict[str, Dict[str, int]] = {
    "warrior":  {"melee":3, "support":1},
    "rogue":    {"stealth":3, "trap":2},
    "ranger":   {"ranged":3, "trap":1, "env":1},
    "mage":     {"magic":3, "env":1},
    "cleric":   {"support":3, "melee":1},
    "warlock":  {"magic":3, "social":1},
    "engineer": {"tech":3, "trap":2, "env":1},
    "psion":    {"magic":2, "social":2, "stealth":1},
}


def record_kill(player, kind: str, weight: int = 1):
    if not hasattr(player, "affinity"):
        return
    player.affinity[kind] = player.affinity.get(kind, 0) + weight
    if hasattr(player, "kill_method_history"):
        player.kill_method_history.append(kind)
        player.kill_method_history = player.kill_method_history[-50:]


def record_action(player, kind: str, weight: int = 1):
    """Like record_kill but for non-lethal actions (talk, sneak past, strip)."""
    record_kill(player, kind, weight)


def class_score(player, class_key: str) -> float:
    weights = DEFAULT_CLASS_AFFINITY.get(class_key, {})
    aff = getattr(player, "affinity", {}) or {}
    total = 0.0
    for kind, w in weights.items():
        total += aff.get(kind, 0) * w
    # Tiny noise so ties resolve unpredictably
    import random
    total += random.uniform(0, 0.5)
    return total


def suggest_classes(player, n: int = 3, available_keys=None) -> List[str]:
    """Return top-N class keys ranked by player's affinity score."""
    keys = list(available_keys) if available_keys else list(DEFAULT_CLASS_AFFINITY.keys())
    scored = sorted(keys, key=lambda k: -class_score(player, k))
    # 20% wildcard slot: insert a random non-top class at position 2 sometimes
    import random
    if len(scored) > n and random.random() < 0.2:
        tail = scored[n:]
        wildcard = random.choice(tail) if tail else None
        if wildcard:
            scored = scored[:n-1] + [wildcard] + scored[n-1:n]
    return scored[:n]
