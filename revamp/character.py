"""Character model — modest stats, no fantasy class at start."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .config import BASE_STATS, AFFINITY_KINDS


@dataclass
class Character:
    name: str = ""
    background: str = "unemployed_hustler"
    pronoun: str = ""              # optional, free text

    stats: Dict[str, int] = field(default_factory=lambda: {s: 10 for s in BASE_STATS})

    # Combat shell
    max_hp: int = 14
    hp: int = 14
    base_ac: int = 10
    conditions: List[str] = field(default_factory=list)

    # Class is dynamic — earned by play behavior
    class_key: Optional[str] = None
    class_offered_at: Optional[int] = None     # in-game minute when offered

    # Species set on Floor 3
    species_key: str = "baseline_human"
    species_picked_at_floor: Optional[int] = None

    # Affinity scores driving the class offer
    affinity: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in AFFINITY_KINDS})

    # Inventory: list of Entity dicts (Entities with entity_type=T_ITEM, location_id="inventory:<owner>")
    inventory_ids: List[int] = field(default_factory=list)
    credits: int = 25

    # Materials inventory (Prompt 06): qty-only, dict[material_key] -> int.
    # Items crafted FROM materials become Entities in inventory_ids above.
    materials: Dict[str, int] = field(default_factory=dict)

    # Audience rating (sponsor-facing)
    audience_rating: int = 0

    # Achievements
    unlocked_achievements: List[str] = field(default_factory=list)

    # Journal: dict room_id -> [notes]
    journal: Dict[str, List[str]] = field(default_factory=dict)

    # Relationships with crawlers: id -> int (positive: friendly; negative: hostile)
    relationships: Dict[str, int] = field(default_factory=dict)

    # Misc flags
    flags: Dict[str, Any] = field(default_factory=dict)

    # ── Derived ──────────────────────────────────────────────────────────────

    def stat_mod(self, stat: str) -> int:
        v = self.stats.get(stat, 10)
        return (v - 10) // 2

    def effective_ac(self) -> int:
        return self.base_ac + self.stat_mod("DEX")

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, n: int):
        self.hp = max(0, self.hp - n)

    def heal(self, n: int):
        self.hp = min(self.max_hp, self.hp + n)

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "name": self.name, "background": self.background, "pronoun": self.pronoun,
            "stats": dict(self.stats),
            "max_hp": self.max_hp, "hp": self.hp,
            "base_ac": self.base_ac, "conditions": list(self.conditions),
            "class_key": self.class_key, "class_offered_at": self.class_offered_at,
            "species_key": self.species_key,
            "species_picked_at_floor": self.species_picked_at_floor,
            "affinity": dict(self.affinity),
            "inventory_ids": list(self.inventory_ids),
            "materials": dict(self.materials),
            "credits": self.credits, "audience_rating": self.audience_rating,
            "unlocked_achievements": list(self.unlocked_achievements),
            "journal": {k: list(v) for k, v in self.journal.items()},
            "relationships": dict(self.relationships),
            "flags": dict(self.flags),
        }

    @classmethod
    def from_dict(cls, d):
        c = cls()
        for k in ("name","background","pronoun","max_hp","hp","base_ac",
                  "class_key","class_offered_at","species_key",
                  "species_picked_at_floor","credits","audience_rating"):
            setattr(c, k, d.get(k, getattr(c, k)))
        c.stats = dict(d.get("stats", c.stats))
        c.conditions = list(d.get("conditions", []))
        c.affinity = {**c.affinity, **d.get("affinity", {})}
        c.inventory_ids = list(d.get("inventory_ids", []))
        c.materials = dict(d.get("materials", {}))
        c.unlocked_achievements = list(d.get("unlocked_achievements", []))
        c.journal = {k: list(v) for k, v in d.get("journal", {}).items()}
        c.relationships = dict(d.get("relationships", {}))
        c.flags = dict(d.get("flags", {}))
        return c
