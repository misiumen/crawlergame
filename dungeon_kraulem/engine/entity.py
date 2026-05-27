"""Entity model — everything interactable in the world."""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import itertools

_eid_counter = itertools.count(1)


def _next_eid() -> int:
    return next(_eid_counter)


# Entity type constants
T_PLAYER  = "player"
T_CRAWLER = "crawler"
T_MONSTER = "monster"
T_NPC     = "npc"
T_OBJECT  = "object"
T_HAZARD  = "hazard"
T_DOOR    = "door"
T_CONTAINER = "container"
T_TERMINAL  = "terminal"
T_CORPSE  = "corpse"
T_ITEM    = "item"
T_FEATURE = "environmental_feature"
T_SERVICE = "safehouse_service"
T_EXIT    = "exit"
T_COMPANION = "companion"   # Prompt 19 — pets / crawler allies / drones


@dataclass
class Entity:
    entity_id: int = field(default_factory=_next_eid)
    key: str = ""                           # stable id like "acid_pool", "goblin_butcher"
    entity_type: str = T_OBJECT
    name_key: str = ""                      # i18n key, e.g. "ent_acid_pool_n"
    fallback_name: str = ""
    desc_key: str = ""                      # i18n key, e.g. "ent_acid_pool_d"
    fallback_desc: str = ""
    tags: List[str] = field(default_factory=list)
    location_id: str = ""                   # room_id or "inventory:<owner_id>"
    visible: bool = True                    # immediately visible on enter
    discovered: bool = True                 # has player learned of it
    interactable: bool = True
    portable: bool = False
    state: Dict[str, Any] = field(default_factory=dict)   # arbitrary runtime state
    affordances: List[str] = field(default_factory=list)  # affordance keys

    # Combat / NPC fields used by relevant subtypes
    hp: int = 0
    max_hp: int = 0
    ac: int = 10
    damage_dice: str = "1d4"
    damage_type: str = "physical"   # Prompt 21: what kind of damage this entity deals on attack
    attack_bonus: int = 0
    conditions: List[str] = field(default_factory=list)
    # Prompt 21: resistance / vulnerability / immunity to typed damage.
    # Each is a list of damage_type keys (see engine.damage.DAMAGE_TYPES).
    # `resists` halves incoming damage; `vulnerable_to` doubles it;
    # `immune_to` reduces to zero.
    resists: List[str] = field(default_factory=list)
    vulnerable_to: List[str] = field(default_factory=list)
    immune_to: List[str] = field(default_factory=list)

    # Prompt 26a — per-zone HP for body-aware combat. dict zone_key →
    # {hp, max_hp, broken}. Empty by default; lazy-initialized by
    # `content.data.body_plans.init_body_parts` on first body-aware
    # combat read so old saves and non-creature entities don't pay.
    body_parts: Dict[str, Any] = field(default_factory=dict)

    # P29.0 — local threat escalation (replaces noise → patrol pipeline).
    # Hostiles in the same room rise through threat levels as the player
    # makes loud actions: 0=oblivious, 1=wary, 2=alert, 3=enraged.
    # Crossing into 3 starts combat with a free attack of opportunity
    # for the enemy. Stealth/hide and time bring it back down.
    threat_level: int = 0

    def is_alive(self) -> bool:
        return self.hp > 0 if self.max_hp > 0 else True

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def to_dict(self):
        return {
            "entity_id": self.entity_id, "key": self.key,
            "entity_type": self.entity_type,
            "name_key": self.name_key, "fallback_name": self.fallback_name,
            "desc_key": self.desc_key, "fallback_desc": self.fallback_desc,
            "tags": list(self.tags), "location_id": self.location_id,
            "visible": self.visible, "discovered": self.discovered,
            "interactable": self.interactable, "portable": self.portable,
            "state": dict(self.state), "affordances": list(self.affordances),
            "hp": self.hp, "max_hp": self.max_hp, "ac": self.ac,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "attack_bonus": self.attack_bonus,
            "conditions": list(self.conditions),
            "resists": list(self.resists),
            "vulnerable_to": list(self.vulnerable_to),
            "immune_to": list(self.immune_to),
            "body_parts": {k: dict(v) for k, v in (self.body_parts or {}).items()},
            "threat_level": int(self.threat_level or 0),
        }

    @classmethod
    def from_dict(cls, d):
        e = cls()
        e.entity_id = d.get("entity_id", _next_eid())
        e.key = d.get("key", "")
        e.entity_type = d.get("entity_type", T_OBJECT)
        e.name_key = d.get("name_key", "")
        e.fallback_name = d.get("fallback_name", "")
        e.desc_key = d.get("desc_key", "")
        e.fallback_desc = d.get("fallback_desc", "")
        e.tags = list(d.get("tags", []))
        e.location_id = d.get("location_id", "")
        e.visible = d.get("visible", True)
        e.discovered = d.get("discovered", True)
        e.interactable = d.get("interactable", True)
        e.portable = d.get("portable", False)
        e.state = dict(d.get("state", {}))
        e.affordances = list(d.get("affordances", []))
        e.hp = d.get("hp", 0)
        e.max_hp = d.get("max_hp", 0)
        e.ac = d.get("ac", 10)
        e.damage_dice = d.get("damage_dice", "1d4")
        e.damage_type = d.get("damage_type", "physical")
        e.attack_bonus = d.get("attack_bonus", 0)
        e.conditions = list(d.get("conditions", []))
        e.resists       = list(d.get("resists", []))
        e.vulnerable_to = list(d.get("vulnerable_to", []))
        e.immune_to     = list(d.get("immune_to", []))
        bp = d.get("body_parts") or {}
        e.body_parts = {k: dict(v) for k, v in bp.items()}
        e.threat_level = int(d.get("threat_level", 0) or 0)
        return e

    def display_name(self):
        from ..ui.lang import t
        return t(self.name_key, fallback=self.fallback_name or self.key)

    def display_desc(self):
        from ..ui.lang import t
        return t(self.desc_key, fallback=self.fallback_desc or "")
