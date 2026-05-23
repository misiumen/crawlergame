"""Achievement system for CRAWL PROTOCOL."""
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Achievement:
    name: str
    description: str
    unlocked: bool = False
    reward_type: str = "none"   # none, xp, credits, mutation_chance
    reward_value: int = 0


ACHIEVEMENT_CATALOG = {
    "First Blood": Achievement(
        "First Blood",
        "Kill your first enemy.",
        reward_type="xp", reward_value=25
    ),
    "Barely Breathing": Achievement(
        "Barely Breathing",
        "Survive combat with 1 HP remaining.",
        reward_type="xp", reward_value=50
    ),
    "Trap Enthusiast": Achievement(
        "Trap Enthusiast",
        "Trigger 3 traps. Intentionally or otherwise.",
        reward_type="xp", reward_value=30
    ),
    "Critical Problem": Achievement(
        "Critical Problem",
        "Land a critical hit.",
        reward_type="xp", reward_value=20
    ),
    "Natural Disaster": Achievement(
        "Natural Disaster",
        "Roll a natural 1 in combat.",
        reward_type="none", reward_value=0
    ),
    "Boss Breaker": Achievement(
        "Boss Breaker",
        "Defeat a floor boss.",
        reward_type="xp", reward_value=100
    ),
    "Mutation Accepted": Achievement(
        "Mutation Accepted",
        "Gain your first mutation.",
        reward_type="xp", reward_value=40
    ),
    "Questionable Snack": Achievement(
        "Questionable Snack",
        "Use a Mystery Ration.",
        reward_type="none", reward_value=0
    ),
    "Wrong Lever": Achievement(
        "Wrong Lever",
        "Trigger a trap while trying to disarm it.",
        reward_type="xp", reward_value=15
    ),
    "Unfair Trade": Achievement(
        "Unfair Trade",
        "Spend 50 or more credits at a merchant.",
        reward_type="xp", reward_value=30
    ),
    "Still Standing": Achievement(
        "Still Standing",
        "Reach floor 2.",
        reward_type="xp", reward_value=75
    ),
    "Floor One Survivor": Achievement(
        "Floor One Survivor",
        "Clear floor 1 completely.",
        reward_type="credits", reward_value=25
    ),
    "Collector": Achievement(
        "Collector",
        "Carry 5 or more items in inventory.",
        reward_type="xp", reward_value=20
    ),
    "Cowardice Is Strategy": Achievement(
        "Cowardice Is Strategy",
        "Successfully flee from combat.",
        reward_type="xp", reward_value=15
    ),
    "Overkill": Achievement(
        "Overkill",
        "Deal 20+ damage in a single hit.",
        reward_type="xp", reward_value=50
    ),
    "Hybrid Theory": Achievement(
        "Hybrid Theory",
        "Unlock a hybrid class.",
        reward_type="xp", reward_value=75
    ),
    "Disarmed": Achievement(
        "Disarmed",
        "Successfully disarm a trap.",
        reward_type="xp", reward_value=25
    ),
    "Merchant of Death": Achievement(
        "Merchant of Death",
        "Buy 3 items from merchants.",
        reward_type="credits", reward_value=15
    ),
}


class AchievementManager:
    def __init__(self):
        self.achievements = {k: Achievement(v.name, v.description,
                                            v.unlocked, v.reward_type, v.reward_value)
                             for k, v in ACHIEVEMENT_CATALOG.items()}
        self.counters = {
            "traps_triggered": 0,
            "merchant_buys": 0,
            "credits_spent": 0,
        }

    def unlock(self, name):
        """Unlock an achievement. Returns (reward_type, reward_value) or None if already unlocked."""
        ach = self.achievements.get(name)
        if ach and not ach.unlocked:
            ach.unlocked = True
            from narrator import get_narrator
            n = get_narrator()
            print(f"\n  [ACHIEVEMENT] {name}: {ach.description}")
            n.say("achievement")
            return ach.reward_type, ach.reward_value
        return None

    def is_unlocked(self, name):
        ach = self.achievements.get(name)
        return ach.unlocked if ach else False

    def check_inventory(self, inventory):
        if len(inventory) >= 5:
            self.unlock("Collector")

    def check_credits_spent(self, amount):
        self.counters["credits_spent"] += amount
        if self.counters["credits_spent"] >= 50:
            self.unlock("Unfair Trade")

    def check_merchant_buy(self):
        self.counters["merchant_buys"] += 1
        if self.counters["merchant_buys"] >= 3:
            self.unlock("Merchant of Death")

    def check_trap_trigger(self):
        self.counters["traps_triggered"] += 1
        if self.counters["traps_triggered"] >= 3:
            self.unlock("Trap Enthusiast")

    def to_dict(self):
        return {
            "achievements": {k: v.unlocked for k, v in self.achievements.items()},
            "counters": dict(self.counters),
        }

    @classmethod
    def from_dict(cls, data):
        mgr = cls()
        for name, unlocked in data.get("achievements", {}).items():
            if name in mgr.achievements:
                mgr.achievements[name].unlocked = unlocked
        mgr.counters.update(data.get("counters", {}))
        return mgr
