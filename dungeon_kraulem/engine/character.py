"""Character model — modest stats, no fantasy class at start."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from ..config import BASE_STATS, AFFINITY_KINDS


# Prompt 19 audit fix S2: single source of truth for the playable
# backgrounds. Imported by engine.game (stat-adjust + starter-items)
# and ui.ui (creation render). Order is the order shown to the player.
BACKGROUNDS = (
    "office_worker", "mechanic", "nurse", "cook", "security_guard",
    "courier", "student", "streamer", "soldier", "unemployed_hustler",
    "janitor", "paramedic",
    "opiekun_zwierzaka",   # Prompt 19
)


@dataclass
class Character:
    name: str = ""
    background: str = "unemployed_hustler"
    pronoun: str = ""              # optional, free text

    stats: Dict[str, int] = field(default_factory=lambda: {s: 10 for s in BASE_STATS})

    # Combat shell — P27.6 balance pass: HP scaled ×7 (14→100) so
    # individual hits feel like meaningful chunks rather than instant
    # death, and the player sees real numbers move.
    max_hp: int = 100
    hp: int = 100
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
    # NOTE: BACKGROUNDS is the single source of truth for the
    # character-creation list. game.py and ui.py both import it.

    # Prompt 23 — wield slots. Both fields hold the entity_id of an
    # inventory item being held in that hand, or None for empty.
    # `wielded_main_id` is the primary weapon used for attack damage.
    # `wielded_offhand_id` is the off-hand: shield (+AC), torch
    # (light), second knife (extra attack at -2), chembottle (ready),
    # etc. Two-handed weapons lock the off-hand slot.
    wielded_main_id: Optional[int] = None
    wielded_offhand_id: Optional[int] = None

    # Prompt 25 — 5 non-wield equipment slots. dict slot_key →
    # entity_id. Main/off keep their dedicated fields above so the P23
    # wield path is unchanged.
    worn_slots: Dict[str, int] = field(default_factory=dict)

    # Prompt 19 — companion ids the player currently owns. Companions
    # themselves live on world.companions; this list just references
    # them by id so save/load can rehydrate the relationship.
    companion_ids: List[int] = field(default_factory=list)

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

    def effective_ac(self, world=None) -> int:
        """Base AC + DEX mod + any worn-slot AC bonuses. P25: accepts an
        optional `world` so the AC can include armor / shield bonuses
        without callers needing a separate function. When world is None
        (legacy callers), only base + DEX is returned — matches pre-P25
        behavior so saves and snapshots stay consistent."""
        ac = self.base_ac + self.stat_mod("DEX")
        if world is not None:
            try:
                from . import equipment as _eq
                ac += _eq.total_ac_bonus(world, self)
            except Exception:
                pass
        # P27.7 — class passive (e.g. survivor +1 AC).
        try:
            from ..systems import class_features as _cf
            ac += _cf.passive_bonus(self, "ac")
        except Exception:
            pass
        return ac

    def offhand_ac_bonus(self, world) -> int:
        """Prompt 23: +2 if the offhand entity is a shield (has `shield`
        tag). 0 otherwise. Lazy lookup avoids storing a world ref on
        the character itself."""
        if self.wielded_offhand_id is None or world is None:
            return 0
        ent = world.get(self.wielded_offhand_id)
        if ent is None:
            return 0
        if "shield" in (ent.tags or []):
            return 2
        return 0

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
            "companion_ids": list(self.companion_ids),
            "wielded_main_id": self.wielded_main_id,
            "wielded_offhand_id": self.wielded_offhand_id,
            "worn_slots": dict(self.worn_slots),
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
        c.companion_ids = list(d.get("companion_ids", []))   # Prompt 19
        c.wielded_main_id    = d.get("wielded_main_id")       # Prompt 23
        c.wielded_offhand_id = d.get("wielded_offhand_id")    # Prompt 23
        # Prompt 25 — worn_slots; coerce values to int (json deserializes
        # dict KEYS as strings already; we want VALUE ints).
        ws = d.get("worn_slots") or {}
        c.worn_slots = {k: int(v) for k, v in ws.items()}
        c.materials = dict(d.get("materials", {}))
        c.unlocked_achievements = list(d.get("unlocked_achievements", []))
        c.journal = {k: list(v) for k, v in d.get("journal", {}).items()}
        c.relationships = dict(d.get("relationships", {}))
        c.flags = dict(d.get("flags", {}))
        return c
