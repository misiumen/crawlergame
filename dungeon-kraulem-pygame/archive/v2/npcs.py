"""CRAWL PROTOCOL - Other crawlers as NPCs.

Crawlers are named contestants encountered mid-floor in rooms that
aren't currently in active combat. Each Crawler has:

  - disposition: hostile | friendly | neutral | ignoring
  - archetype  : storyline-style flavor (vet / scavenger / preacher / runner)
  - inventory  : optional loot if killed
  - dialog tree: keyed by archetype+disposition (delivered via dialog.py)

Hostile crawlers convert into Monster instances when combat starts and
remain dead-once-killed (named NPCs, not respawns).

Spawn frequency by floor (deeper floors more dangerous):
  Floor 1: hostile 15% / friendly 40% / neutral 30% / ignoring 15%
  Floor 5: hostile 40% / friendly 25% / neutral 20% / ignoring 15%
"""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from lang import tr


DISPOSITIONS = ("hostile", "friendly", "neutral", "ignoring")
ARCHETYPES   = ("vet", "scavenger", "preacher", "runner", "medic", "engineer_npc")


@dataclass
class Crawler:
    id: str                          # unique room-id (e.g. "f1n4_vet_voss")
    name: str
    archetype: str
    disposition: str
    floor_spawned: int
    is_dead: bool = False
    looted: bool = False
    dialog_state: str = "start"
    inventory: List[Dict] = field(default_factory=list)
    # cached combat stats if hostile
    hp: int = 0
    max_hp: int = 0
    ac: int = 11
    attack_bonus: int = 3
    damage_dice: str = "1d6"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "archetype": self.archetype,
            "disposition": self.disposition, "floor_spawned": self.floor_spawned,
            "is_dead": self.is_dead, "looted": self.looted,
            "dialog_state": self.dialog_state,
            "inventory": list(self.inventory),
            "hp": self.hp, "max_hp": self.max_hp, "ac": self.ac,
            "attack_bonus": self.attack_bonus, "damage_dice": self.damage_dice,
        }

    @classmethod
    def from_dict(cls, d):
        c = cls(id=d["id"], name=d["name"], archetype=d["archetype"],
                disposition=d["disposition"], floor_spawned=d.get("floor_spawned",1))
        c.is_dead       = d.get("is_dead", False)
        c.looted        = d.get("looted", False)
        c.dialog_state  = d.get("dialog_state","start")
        c.inventory     = list(d.get("inventory", []))
        c.hp = d.get("hp", 12); c.max_hp = d.get("max_hp", c.hp)
        c.ac = d.get("ac", 11); c.attack_bonus = d.get("attack_bonus", 3)
        c.damage_dice = d.get("damage_dice", "1d6")
        return c


# ── Spawn ─────────────────────────────────────────────────────────────────────

_DISPO_WEIGHTS_BY_FLOOR = {
    1: {"hostile": 15, "friendly": 40, "neutral": 30, "ignoring": 15},
    2: {"hostile": 20, "friendly": 38, "neutral": 27, "ignoring": 15},
    3: {"hostile": 25, "friendly": 35, "neutral": 25, "ignoring": 15},
    4: {"hostile": 32, "friendly": 30, "neutral": 23, "ignoring": 15},
    5: {"hostile": 40, "friendly": 25, "neutral": 20, "ignoring": 15},
}

# Hostile-allowed room types: non-checkpoint, non-start, non-active-combat.
_NPC_OK_ROOMS = {"rest", "treasure", "lore", "merchant", "mutation",
                 "trap", "checkpoint"}


def _pick_disposition(floor_num: int) -> str:
    w = _DISPO_WEIGHTS_BY_FLOOR.get(floor_num, _DISPO_WEIGHTS_BY_FLOOR[1])
    keys = list(w.keys())
    weights = list(w.values())
    return random.choices(keys, weights=weights, k=1)[0]


def _stats_for(archetype: str, floor: int):
    base_hp = 10 + floor * 4
    ac = 11 + floor // 2
    atk = 3 + floor // 2
    dmg = ["1d6", "1d6+1", "1d8", "1d8+1", "2d6"][min(floor-1, 4)]
    hp = base_hp + {"vet": 6, "engineer_npc": 2, "scavenger": 4,
                    "medic": 0, "preacher": 2, "runner": 0}.get(archetype, 0)
    return hp, ac, atk, dmg


def populate_npc(room, floor_num: int, spawn_rate: float = 0.18):
    """
    Maybe place a Crawler in `room`. Mutates room.npcs.
    No-op for room types not on the safe list.
    """
    if room.room_type not in _NPC_OK_ROOMS:
        return
    if room.npcs:
        return  # already populated
    if random.random() >= spawn_rate:
        return

    from procgen import random_name
    archetype = random.choice(ARCHETYPES)
    dispo = _pick_disposition(floor_num)
    name = random_name()
    nid = f"f{floor_num}_r{room.node_id}_{archetype}_{name.split()[0].lower()}"

    c = Crawler(id=nid, name=name, archetype=archetype,
                disposition=dispo, floor_spawned=floor_num)
    if dispo == "hostile":
        c.hp, c.ac, c.attack_bonus, c.damage_dice = _stats_for(archetype, floor_num)
        c.max_hp = c.hp
        # Loot from prior contestants — a flavor item or two
        c.inventory = [{"type": "credits", "value": random.randint(30, 80)}]
    room.npcs.append(c)


def to_monster(crawler: "Crawler"):
    """Convert a hostile crawler into a Monster instance for combat."""
    from monsters import Monster
    m = Monster(name=crawler.name, hp=crawler.hp, ac=crawler.ac,
                attack_bonus=crawler.attack_bonus, damage_dice=crawler.damage_dice,
                xp=40 + 15 * crawler.floor_spawned, cr_drop=0,
                tags=["crawler"], description=f"{crawler.archetype} ({crawler.disposition})")
    m.is_crawler = True
    m.crawler_ref = crawler
    return m


def find_npc(room, text: str) -> Optional[Crawler]:
    """Match free-text against an NPC name in the room."""
    if not text or not room or not room.npcs:
        return None
    from environment import _fold  # reuse the ASCII fold helper
    norm = _fold(text)
    for c in room.npcs:
        if _fold(c.name) in norm or any(part in norm for part in _fold(c.name).split()):
            return c
    return None
