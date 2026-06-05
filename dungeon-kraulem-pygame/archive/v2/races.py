"""CRAWL PROTOCOL - Race / species choice (Step 10).

Picked when the player first enters Floor 3. Five flavors of "what is left
of you after two floors of broadcast." Each gives a stat profile, a small
passive, and a bonus HP pool.

Localized name/desc keys in pl.json/en.json under `race_<key>_n` / `_d`
and `race_<key>_p` (passive description).
"""
from dataclasses import dataclass, field
from typing import Dict, List
from lang import tr


@dataclass
class Race:
    key: str
    stat_bonus: Dict[str, int] = field(default_factory=dict)
    hp_bonus: int = 0
    passive: str = ""           # short id for runtime logic
    granted_feature_key: str = None   # optional feature key

    @property
    def name(self) -> str:
        return tr(f"race_{self.key}_n")

    @property
    def description(self) -> str:
        return tr(f"race_{self.key}_d")

    @property
    def passive_description(self) -> str:
        return tr(f"race_{self.key}_p")


RACE_CATALOG = {
    "human": Race("human",
                  stat_bonus={"STR":1, "DEX":1, "CON":1, "INT":1, "WIS":1, "CHA":1},
                  hp_bonus=4,
                  passive="adaptive"),
    "mutant": Race("mutant",
                   stat_bonus={"CON":3, "STR":1},
                   hp_bonus=12,
                   passive="extra_mutation_slot"),
    "synthetic": Race("synthetic",
                      stat_bonus={"INT":3, "DEX":1},
                      hp_bonus=6,
                      passive="immune_poison"),
    "psionic": Race("psionic",
                    stat_bonus={"INT":2, "WIS":2},
                    hp_bonus=4,
                    passive="enemy_scan"),
    "altered": Race("altered",
                    stat_bonus={"CON":2, "CHA":2},
                    hp_bonus=8,
                    passive="env_immune"),
}


def apply_race(player, race_key: str):
    """Apply a race choice to the player. Idempotent on the same race."""
    race = RACE_CATALOG.get(race_key)
    if race is None or player.race == race_key:
        return False
    player.race = race_key
    player.race_picked_at_floor = player.current_floor
    for stat, bonus in race.stat_bonus.items():
        player.stats[stat] = player.stats.get(stat, 10) + bonus
    if race.hp_bonus:
        player.max_hp += race.hp_bonus
        player.hp += race.hp_bonus
    return True
