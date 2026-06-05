"""CRAWL PROTOCOL v2 - Room types for Pygame dungeon."""
import random
from utils import d20, parse_dice
from procgen import random_room_name, random_lore, syndicate_comment


# Room type constants
ROOM_COMBAT    = "combat"
ROOM_TRAP      = "trap"
ROOM_TREASURE  = "treasure"
ROOM_REST      = "rest"
ROOM_MERCHANT  = "merchant"
ROOM_LORE      = "lore"
ROOM_MUTATION  = "mutation"
ROOM_CHECKPOINT= "checkpoint"
ROOM_BOSS      = "boss"
ROOM_START     = "start"

# Symbol used on mini-map
ROOM_SYMBOLS = {
    ROOM_COMBAT:     "E",
    ROOM_TRAP:       "T",
    ROOM_TREASURE:   "$",
    ROOM_REST:       "R",
    ROOM_MERCHANT:   "M",
    ROOM_LORE:       "?",
    ROOM_MUTATION:   "~",
    ROOM_CHECKPOINT: "C",
    ROOM_BOSS:       "B",
    ROOM_START:      "S",
}

# Colors on map (references config keys)
ROOM_COLORS = {
    ROOM_COMBAT:     "DANGER",
    ROOM_TRAP:       "WARN",
    ROOM_TREASURE:   "GOLD_COLOR",
    ROOM_REST:       "SUCCESS",
    ROOM_MERCHANT:   "ACCENT",
    ROOM_LORE:       "DIM_TEXT",
    ROOM_MUTATION:   "ACCENT2",
    ROOM_CHECKPOINT: "NODE_SAFE",
    ROOM_BOSS:       "NODE_BOSS",
    ROOM_START:      "NORMAL_TEXT",
}


class Room:
    """Data holder for a single dungeon room."""

    def __init__(self, room_type, name=None, floor_num=1):
        self.room_type = room_type
        self.name = name or random_room_name()
        self.floor_num = floor_num
        self.cleared = False
        self.visited = False
        # Positional data set by dungeon.py DAG layout
        self.node_id = 0
        self.x = 0
        self.y = 0
        # Connected rooms (node IDs)
        self.connections: list = []
        # Payload — set by dungeon.py generator
        self.enemies = []          # list of Monster (for combat rooms)
        self.trap = None           # Trap dict (for trap rooms)
        self.loot_tier = "Copper"  # for treasure rooms
        self.lore_text = ""        # for lore rooms
        self.mutation_pool = []    # for mutation rooms
        self.shop_stock = []       # for merchant rooms
        self.faction = None        # for checkpoint rooms
        self.is_boss_room = False  # flag

        # ── v3 additions ────────────────────────────────────────────────────
        self.env_objects: list = []       # list of EnvObject dicts/instances
        self.npcs: list = []              # list of Crawler dicts/instances
        self.safehouse_subtype: str = None
        self.resolution_modes: list = ["combat"]   # combat | social | stealth | skill
        self.inspected: bool = False
        # Loose lore-fragments visible only after first Look on hidden objects
        self.fragments_revealed: list = []

    def symbol(self):
        if self.cleared:
            return ROOM_SYMBOLS[self.room_type].lower()
        return ROOM_SYMBOLS[self.room_type]

    def color_key(self):
        return ROOM_COLORS.get(self.room_type, "NORMAL_TEXT")

    def description(self):
        from lang import tr
        key_map = {
            ROOM_COMBAT:     "v2_room_combat_desc",
            ROOM_TRAP:       "v2_room_trap_desc",
            ROOM_TREASURE:   "v2_room_treasure_desc",
            ROOM_REST:       "v2_room_rest_desc",
            ROOM_MERCHANT:   "v2_room_merchant_desc",
            ROOM_LORE:       "v2_room_lore_desc",
            ROOM_MUTATION:   "v2_room_mutation_desc",
            ROOM_CHECKPOINT: "v2_room_checkpoint_desc",
            ROOM_BOSS:       "v2_room_boss_desc",
            ROOM_START:      "v2_room_start_desc",
        }
        k = key_map.get(self.room_type)
        if k:
            return tr(k, fallback="Unknown room.")
        base = {
            ROOM_COMBAT:     "Hostiles detected. Engage or be eliminated.",
            ROOM_TRAP:       "Environmental hazard. Proceed with caution.",
            ROOM_TREASURE:   "Loot cache. The Protocol approves of salvage.",
            ROOM_REST:       "Temporary reprieve. The cameras are respectful.",
            ROOM_MERCHANT:   "A vendor. Somehow. The Syndicate takes its cut.",
            ROOM_LORE:       "Data fragment. Someone was here before you.",
            ROOM_MUTATION:   "Anomalous readings. Exposure risk.",
            ROOM_CHECKPOINT: "Safe zone. Faction presence detected.",
            ROOM_BOSS:       "High-value threat. Audience interest: maximum.",
            ROOM_START:      "Entry point. There is no going back.",
        }
        return base.get(self.room_type, "Unknown room type.")

    def to_dict(self):
        return {
            "room_type": self.room_type,
            "name": self.name,
            "floor_num": self.floor_num,
            "cleared": self.cleared,
            "visited": self.visited,
            "node_id": self.node_id,
            "x": self.x,
            "y": self.y,
            "connections": list(self.connections),
            "loot_tier": self.loot_tier,
            "lore_text": self.lore_text,
            "is_boss_room": self.is_boss_room,
            # v3 additions
            "env_objects": [_serialize_env(o) for o in self.env_objects],
            "npcs": [_serialize_npc(n) for n in self.npcs],
            "safehouse_subtype": self.safehouse_subtype,
            "resolution_modes": list(self.resolution_modes),
            "inspected": self.inspected,
            "fragments_revealed": list(self.fragments_revealed),
        }

    @classmethod
    def from_dict(cls, d):
        r = cls(d["room_type"], d.get("name"), d.get("floor_num", 1))
        r.cleared = d.get("cleared", False)
        r.visited = d.get("visited", False)
        r.node_id = d.get("node_id", 0)
        r.x = d.get("x", 0)
        r.y = d.get("y", 0)
        r.connections = d.get("connections", [])
        r.loot_tier = d.get("loot_tier", "Copper")
        r.lore_text = d.get("lore_text", "")
        r.is_boss_room = d.get("is_boss_room", False)
        r.env_objects = [_deserialize_env(o) for o in d.get("env_objects", [])]
        r.npcs = [_deserialize_npc(n) for n in d.get("npcs", [])]
        r.safehouse_subtype = d.get("safehouse_subtype")
        r.resolution_modes = list(d.get("resolution_modes") or ["combat"])
        r.inspected = d.get("inspected", False)
        r.fragments_revealed = list(d.get("fragments_revealed", []))
        return r


# ── EnvObject / Crawler (de)serialization helpers ──────────────────────────
# These bounce through dataclasses defined in environment.py / npcs.py.
# Import is deferred to avoid circular dependency at module load.

def _serialize_env(o):
    if hasattr(o, "to_dict"):
        return o.to_dict()
    return o if isinstance(o, dict) else None


def _deserialize_env(d):
    if not isinstance(d, dict):
        return None
    try:
        from environment import EnvObject
        return EnvObject.from_dict(d)
    except Exception:
        return d  # leave as raw dict if module not loadable


def _serialize_npc(n):
    if hasattr(n, "to_dict"):
        return n.to_dict()
    return n if isinstance(n, dict) else None


def _deserialize_npc(d):
    if not isinstance(d, dict):
        return None
    try:
        from npcs import Crawler
        return Crawler.from_dict(d)
    except Exception:
        return d


# ── Trap definitions ───────────────────────────────────────────────────────────

TRAP_CATALOG = [
    {"name": "Pressure Plate",    "damage": "2d6", "detect_dc": 12, "disarm_dc": 13, "stat": "DEX", "desc": "Classic. Effective. Popular with sadists."},
    {"name": "Laser Grid",        "damage": "3d4", "detect_dc": 14, "disarm_dc": 15, "stat": "INT", "desc": "Cuts in ways you prefer not to think about."},
    {"name": "Acid Sprayer",      "damage": "2d6", "detect_dc": 13, "disarm_dc": 14, "stat": "DEX", "desc": "Repurposed industrial equipment."},
    {"name": "Shock Plate",       "damage": "2d4", "detect_dc": 11, "disarm_dc": 12, "stat": "DEX", "desc": "Old maintenance tech. Still functional."},
    {"name": "Gas Vent",          "damage": "1d6", "detect_dc": 13, "disarm_dc": 15, "stat": "CON", "desc": "Hallucinogenic or toxic. Unclear which is worse.", "effect": "poisoned"},
    {"name": "Collapsing Floor",  "damage": "3d6", "detect_dc": 15, "disarm_dc": 16, "stat": "WIS", "desc": "You fell. The audience loved it."},
    {"name": "Noise Trap",        "damage": "0",   "detect_dc": 10, "disarm_dc": 11, "stat": "DEX", "desc": "Alerts enemies. Sometimes worse than damage.", "effect": "spawn_enemy"},
    {"name": "Proximity Mine",    "damage": "4d4", "detect_dc": 14, "disarm_dc": 16, "stat": "INT", "desc": "High yield. Low subtlety."},
    {"name": "Spike Wall",        "damage": "2d8", "detect_dc": 12, "disarm_dc": 14, "stat": "STR", "desc": "The floor pushed back."},
    {"name": "Syndicate Camera",  "damage": "0",   "detect_dc": 8,  "disarm_dc": 18, "stat": "INT", "desc": "Non-lethal. Just very embarrassing.", "effect": "audience_minus"},
]


def random_trap():
    return dict(random.choice(TRAP_CATALOG))


# ── Mutation definitions ───────────────────────────────────────────────────────

MUTATION_CATALOG = [
    {"name": "Subdermal Plating",  "stat_bonus": {"CON": 2},          "hp_bonus": 5,  "desc": "+2 CON, +5 max HP. Heavy."},
    {"name": "Reactive Tendons",   "stat_bonus": {"DEX": 2},                          "desc": "+2 DEX. You move wrong but fast."},
    {"name": "Cortex Spike",       "stat_bonus": {"INT": 2},                          "desc": "+2 INT. Your headaches have headaches."},
    {"name": "Adrenal Override",   "stat_bonus": {"STR": 2},                          "desc": "+2 STR. Calm is now a memory."},
    {"name": "Acid Secretion",     "stat_bonus": {},                                  "desc": "Melee attacks inflict 'burning' on hit.", "passive": "acid_touch"},
    {"name": "Echo Location",      "stat_bonus": {"WIS": 2},                          "desc": "+2 WIS. Detect traps passively."},
    {"name": "Void Sight",         "stat_bonus": {},                                  "desc": "See invisible entities. Ratings +5.", "passive": "void_sight"},
    {"name": "Regeneration",       "stat_bonus": {},           "hp_bonus": 10,        "desc": "Recover 2 HP per room. +10 max HP.", "passive": "regen_2"},
    {"name": "Broadcast Affinity", "stat_bonus": {"CHA": 3},                          "desc": "+3 CHA. The audience LOVES you."},
    {"name": "Bone Blades",        "stat_bonus": {"STR": 1},                          "desc": "+1 STR. Unarmed attacks deal 1d6.", "passive": "bone_blades"},
    {"name": "Signal Immunity",    "stat_bonus": {},                                  "desc": "Immune to mental/psychic conditions.", "passive": "signal_immune"},
    {"name": "Exoskeletal Crust",  "stat_bonus": {"CON": 1},          "hp_bonus": 3,  "desc": "+1 CON, +3 HP, +1 AC.", "passive": "extra_ac_1"},
    {"name": "Neural Overdrive",   "stat_bonus": {"INT": 1, "DEX": 1},                "desc": "+1 INT, +1 DEX. Occasional blackouts."},
    {"name": "Pheromone Glands",   "stat_bonus": {"CHA": 2},                          "desc": "+2 CHA. Some enemies hesitate."},
    {"name": "Gravity Resistance", "stat_bonus": {"STR": 1, "CON": 1},                "desc": "+1 STR, +1 CON. Falls hurt less."},
]


def random_mutation():
    return dict(random.choice(MUTATION_CATALOG))
