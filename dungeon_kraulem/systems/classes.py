"""Dynamic class system — class offered based on play behavior, not at creation."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import random

from ..config import AFFINITY_KINDS
from ..ui.lang import t


@dataclass
class ClassDef:
    key: str
    affinity_weights: Dict[str, int] = field(default_factory=dict)
    starting_feature: str = ""

    def name(self): return t(f"class_{self.key}_n", fallback=self.key)
    def desc(self): return t(f"class_{self.key}_d", fallback="")
    def reason(self): return t(f"class_{self.key}_reason", fallback="")


CLASS_CATALOG = {
    "bruiser":       ClassDef("bruiser",       {"melee":3,"survival":1}),
    "survivor":      ClassDef("survivor",      {"survival":3,"stealth":1}),
    "saboteur":      ClassDef("saboteur",      {"environment":3,"trap":2}),
    "engineer":      ClassDef("engineer",      {"tech":3,"crafting":2,"environment":1}),
    "ranger":        ClassDef("ranger",        {"ranged":3,"survival":1,"trap":1}),
    "medic":         ClassDef("medic",         {"support":3,"survival":1}),
    "occultist":     ClassDef("occultist",     {"magic":2,"betrayal":1,"social":1}),
    "negotiator":    ClassDef("negotiator",    {"diplomacy":3,"social":2}),
    "trickster":     ClassDef("trickster",     {"stealth":2,"social":1,"showmanship":1,"betrayal":1}),
    "demolitionist": ClassDef("demolitionist", {"environment":2,"trap":2,"melee":1}),
    "showman":       ClassDef("showman",       {"showmanship":3,"social":1}),
    "scout":         ClassDef("scout",         {"stealth":2,"survival":2,"ranged":1}),
}


def class_score(character, class_key: str) -> float:
    """P27.6 (P27-MECH-2): random noise reduced to a tie-breaker scale
    (was 0..0.5 which dominates when all real scores are tiny). Now
    just 0..0.01 — only matters for ties between classes that scored
    identically on the player's affinity profile."""
    weights = CLASS_CATALOG[class_key].affinity_weights
    aff = character.affinity or {}
    total = 0.0
    for k, w in weights.items():
        total += aff.get(k, 0) * w
    total += random.uniform(0, 0.01)
    return total


def suggest_classes(character, n: int = 3) -> List[str]:
    """Top-N classes ranked by affinity, with a 20% chance of a wildcard."""
    keys = list(CLASS_CATALOG.keys())
    ranked = sorted(keys, key=lambda k: -class_score(character, k))
    if len(ranked) > n and random.random() < 0.2:
        wildcard = random.choice(ranked[n:])
        ranked = ranked[:n-1] + [wildcard] + ranked[n-1:n]
    return ranked[:n]


def assign_class(world, class_key: str) -> bool:
    if class_key not in CLASS_CATALOG:
        return False
    world.character.class_key = class_key
    world.character.class_offered_at = world.current_floor.current_minute if world.current_floor else 0
    return True
