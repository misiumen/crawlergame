"""Other crawlers as named, persistent NPCs."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random

from .entity import Entity, T_CRAWLER
from .lang import t


PERSONALITIES = ("paranoid","friendly","arrogant","desperate","professional",
                 "comic_relief","broken","opportunist","honorable","cowardly",
                 "zealot","celebrity","conspiracy_theorist","silent_killer")

STATUSES = ("healthy","wounded","poisoned","terrified","celebrating","mourning",
            "hiding","shopping","cleaning_up","arguing","sleeping",
            "being_interviewed","fighting_monster","looting","trapped")

DISPOSITIONS = ("hostile","friendly","neutral","ignoring")


@dataclass
class Crawler(Entity):
    """Specialized Entity — one of the other contestants."""
    alias: str = ""
    personality: str = "professional"
    status: str = "healthy"
    disposition: str = "neutral"
    can_be_attacked: bool = True
    can_be_helped: bool = True
    can_trade: bool = False
    alive: bool = True
    known_to_player: bool = False
    last_seen_room: str = ""
    last_seen_minute: int = -1

    def to_dict(self):
        d = super().to_dict()
        d.update({
            "alias": self.alias, "personality": self.personality, "status": self.status,
            "disposition": self.disposition,
            "can_be_attacked": self.can_be_attacked, "can_be_helped": self.can_be_helped,
            "can_trade": self.can_trade, "alive": self.alive,
            "known_to_player": self.known_to_player,
            "last_seen_room": self.last_seen_room,
            "last_seen_minute": self.last_seen_minute,
        })
        return d

    @classmethod
    def from_dict(cls, d):
        c = super().from_dict(d)
        # Re-populate crawler-specific fields
        c.alias = d.get("alias", "")
        c.personality = d.get("personality", "professional")
        c.status = d.get("status", "healthy")
        c.disposition = d.get("disposition", "neutral")
        c.can_be_attacked = d.get("can_be_attacked", True)
        c.can_be_helped = d.get("can_be_helped", True)
        c.can_trade = d.get("can_trade", False)
        c.alive = d.get("alive", True)
        c.known_to_player = d.get("known_to_player", False)
        c.last_seen_room = d.get("last_seen_room", "")
        c.last_seen_minute = d.get("last_seen_minute", -1)
        return c


_FIRST = ["Arek","Voss","Kael","Mira","Toran","Lyss","Daven","Sable",
          "Oryn","Cress","Falke","Nira","Brek","Cade","Holt","Sera"]
_LAST = ["Vance","Thresh","Cole","Maren","Tyde","Crane","Solis","Vex",
         "Harrow","Cross","Weld","Fenn","Kade","Morrow","Volke","Hess"]


def make_random_crawler(floor_num: int, room_id: str, disposition: Optional[str] = None) -> Crawler:
    name = f"{random.choice(_FIRST)} {random.choice(_LAST)}"
    archetype = random.choice(["vet","scavenger","preacher","runner","medic"])
    dispo = disposition or _pick_disposition(floor_num)
    personality = random.choice(PERSONALITIES)
    hp = 10 + floor_num * 4 + random.randint(0, 4)
    c = Crawler(
        key=f"crawler_{archetype}_{name.split()[0].lower()}",
        entity_type=T_CRAWLER,
        name_key="", fallback_name=name,
        desc_key="", fallback_desc=f"{archetype}, {personality}",
        tags=[archetype, personality],
        location_id=room_id,
        hp=hp, max_hp=hp, ac=11 + floor_num // 2,
        attack_bonus=2 + floor_num // 2, damage_dice="1d6",
        affordances=["inspect","talk","intimidate","bribe","attack","loot"],
        alias=archetype, personality=personality,
        disposition=dispo,
        last_seen_room=room_id,
    )
    if dispo == "hostile":
        c.status = "fighting_monster" if random.random() < 0.3 else "healthy"
    elif dispo == "ignoring":
        c.interactable = False
    return c


def _pick_disposition(floor_num: int) -> str:
    # Hostile grows on deeper floors
    weights = {
        1: [15, 40, 30, 15],
        2: [20, 38, 27, 15],
        3: [25, 35, 25, 15],
        4: [32, 30, 23, 15],
        5: [40, 25, 20, 15],
    }.get(floor_num, [25, 35, 25, 15])
    return random.choices(DISPOSITIONS, weights=weights, k=1)[0]
