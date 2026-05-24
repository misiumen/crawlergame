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
    attack_bonus: int = 0
    conditions: List[str] = field(default_factory=list)

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
            "damage_dice": self.damage_dice, "attack_bonus": self.attack_bonus,
            "conditions": list(self.conditions),
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
        e.attack_bonus = d.get("attack_bonus", 0)
        e.conditions = list(d.get("conditions", []))
        return e

    def display_name(self):
        from .lang import t
        return t(self.name_key, fallback=self.fallback_name or self.key)

    def display_desc(self):
        from .lang import t
        return t(self.desc_key, fallback=self.fallback_desc or "")
