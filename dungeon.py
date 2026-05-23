"""CRAWL PROTOCOL v2 - DAG floor generator."""
import random
import math
from rooms import (Room, ROOM_COMBAT, ROOM_TRAP, ROOM_TREASURE, ROOM_REST,
                   ROOM_MERCHANT, ROOM_LORE, ROOM_MUTATION, ROOM_CHECKPOINT,
                   ROOM_BOSS, ROOM_START, random_trap, random_mutation,
                   MUTATION_CATALOG)
from monsters import get_encounter, get_floor_boss
from items import open_box, floor_loot_tier
from procgen import random_floor_theme, syndicate_comment, random_factions


# ── Floor layout constants ─────────────────────────────────────────────────────

_ROOM_COUNTS = {1: 12, 2: 14, 3: 16, 4: 18, 5: 20}

# Room type distribution weights (excluding start, checkpoint, boss which are fixed)
_TYPE_WEIGHTS = [
    (ROOM_COMBAT,   40),
    (ROOM_TRAP,     15),
    (ROOM_TREASURE, 10),
    (ROOM_REST,      8),
    (ROOM_MERCHANT,  7),
    (ROOM_LORE,      8),
    (ROOM_MUTATION,  7),
]


def _weighted_pick(table):
    total = sum(w for _, w in table)
    r = random.uniform(0, total)
    acc = 0
    for item, w in table:
        acc += w
        if r <= acc:
            return item
    return table[-1][0]


# ── DAG layout algorithm ───────────────────────────────────────────────────────

def _dag_layout(room_count, map_w, map_h, margin=40):
    """
    Generate (x, y) positions for room_count nodes in a DAG.
    Layered top→bottom layout: start at top, boss at bottom.
    Returns list of (x, y) tuples indexed by node_id.
    """
    # Divide rooms into layers
    layers = []
    remaining = room_count - 2  # exclude start (0) and boss (last)
    layer_sizes = []

    # First layer after start: 2-3 rooms
    while remaining > 0:
        size = min(random.randint(2, 4), remaining)
        layer_sizes.append(size)
        remaining -= size

    # Nodes: index 0 = start, 1..N-2 = middle, N-1 = boss
    total_layers = len(layer_sizes) + 2  # +2 for start and boss layers
    positions = []

    # Start node
    positions.append((map_w // 2, margin))

    # Middle layers
    y_step = (map_h - 2 * margin) / (total_layers - 1)
    for layer_idx, size in enumerate(layer_sizes):
        y = margin + y_step * (layer_idx + 1)
        if size == 1:
            xs = [map_w // 2]
        else:
            xs = [int(map_w * (i + 1) / (size + 1)) for i in range(size)]
        for x in xs:
            positions.append((int(x), int(y)))

    # Boss node
    positions.append((map_w // 2, map_h - margin))

    return positions, layer_sizes


def _build_dag_connections(layer_sizes, total_rooms):
    """
    Build adjacency list: each node connects forward to 1-2 nodes in next layer.
    Returns dict: node_id -> list of next node_ids.
    Also returns reverse: node_id -> list of previous node_ids.
    """
    connections = {i: [] for i in range(total_rooms)}

    # Node index tracking
    layer_starts = [0]  # node 0 is start
    cur = 1
    for size in layer_sizes:
        layer_starts.append(cur)
        cur += size
    layer_starts.append(cur)  # boss node

    layers_all = [[0]]  # start layer
    cur = 1
    for size in layer_sizes:
        layers_all.append(list(range(cur, cur + size)))
        cur += size
    layers_all.append([cur])  # boss layer

    # Connect each layer to next
    for li in range(len(layers_all) - 1):
        current_layer = layers_all[li]
        next_layer = layers_all[li + 1]
        # Ensure every node in next_layer has at least one incoming connection
        connected_next = set()
        for node in current_layer:
            # Connect to 1-2 nodes in next layer
            count = min(len(next_layer), random.randint(1, 2))
            targets = random.sample(next_layer, count)
            for t in targets:
                if t not in connections[node]:
                    connections[node].append(t)
                connected_next.add(t)
        # Ensure all next_layer nodes reachable
        for n in next_layer:
            if n not in connected_next:
                src = random.choice(current_layer)
                if n not in connections[src]:
                    connections[src].append(n)

    return connections


# ── Floor generation ───────────────────────────────────────────────────────────

class Floor:
    def __init__(self, floor_num):
        self.floor_num = floor_num
        theme_name, theme_desc = random_floor_theme(floor_num)
        self.theme_name = theme_name
        self.theme_desc = theme_desc
        self.rooms: dict = {}           # node_id -> Room
        self.connections: dict = {}     # node_id -> [node_ids]
        self.start_id: int = 0
        self.boss_id: int = 0
        self.checkpoint_id: int = -1
        self.current_id: int = 0
        self.factions = random_factions(2)
        self._generate(floor_num)

    def _generate(self, floor_num):
        room_count = _ROOM_COUNTS.get(floor_num, 12)
        from config import MAP_W, MAP_H
        map_w = MAP_W - 20
        map_h = MAP_H - 20

        positions, layer_sizes = _dag_layout(room_count, map_w, map_h)
        self.connections = _build_dag_connections(layer_sizes, room_count)

        # Assign room types
        boss_id = room_count - 1
        self.start_id = 0
        self.boss_id = boss_id

        # Pick a mid-point for checkpoint
        mid = room_count // 2
        checkpoint_candidates = list(range(mid - 1, mid + 2))
        checkpoint_id = random.choice([c for c in checkpoint_candidates if 0 < c < boss_id])
        self.checkpoint_id = checkpoint_id

        for i in range(room_count):
            if i == 0:
                rtype = ROOM_START
            elif i == boss_id:
                rtype = ROOM_BOSS
            elif i == checkpoint_id:
                rtype = ROOM_CHECKPOINT
            else:
                rtype = _weighted_pick(_TYPE_WEIGHTS)

            r = Room(rtype, floor_num=floor_num)
            r.node_id = i
            r.x, r.y = positions[i]
            r.connections = list(self.connections.get(i, []))
            self._populate_room(r, floor_num)
            self.rooms[i] = r

        # Start room always cleared/visited
        self.rooms[0].cleared = True
        self.rooms[0].visited = True
        self.current_id = 0

    def _populate_room(self, room, floor_num):
        rtype = room.room_type
        tier = floor_loot_tier(floor_num)

        if rtype == ROOM_COMBAT:
            room.enemies = get_encounter(floor_num)

        elif rtype == ROOM_TRAP:
            room.trap = random_trap()

        elif rtype == ROOM_TREASURE:
            room.loot_tier = tier

        elif rtype == ROOM_LORE:
            from procgen import random_lore
            room.lore_text = random_lore()

        elif rtype == ROOM_MUTATION:
            pool = random.sample(MUTATION_CATALOG, min(3, len(MUTATION_CATALOG)))
            room.mutation_pool = [dict(m) for m in pool]

        elif rtype == ROOM_MERCHANT:
            room.shop_stock = self._generate_shop(floor_num)

        elif rtype == ROOM_CHECKPOINT:
            room.faction = random.choice(self.factions) if self.factions else None

        elif rtype == ROOM_BOSS:
            room.enemies = [get_floor_boss(floor_num)]
            room.is_boss_room = True
            room.loot_tier = ["Gold", "Gold", "Platinum", "Platinum", "Titanium"][min(floor_num - 1, 4)]

    def _generate_shop(self, floor_num):
        from items import (WEAPON_CATALOG, ARMOR_CATALOG,
                           CONSUMABLE_CATALOG, TRINKET_CATALOG)
        import copy
        stock = []
        # 2-3 items from appropriate tier
        tier_idx = min(floor_num - 1, 4)
        tiers = ["Copper", "Silver", "Gold", "Platinum", "Titanium"]
        allowed_tiers = tiers[:tier_idx + 1]

        for catalog in (WEAPON_CATALOG, ARMOR_CATALOG, CONSUMABLE_CATALOG, TRINKET_CATALOG):
            pool = [v for v in catalog.values() if v.tier in allowed_tiers]
            if pool:
                item = copy.deepcopy(random.choice(pool))
                price = _item_price(item, floor_num)
                stock.append((item, price))

        return stock

    def current_room(self):
        return self.rooms.get(self.current_id)

    def navigate_to(self, node_id):
        """Move to node_id if it's connected from current. Returns True on success."""
        if node_id in self.connections.get(self.current_id, []):
            self.current_id = node_id
            return True
        return False

    def reachable_from_current(self):
        """Return list of node_ids reachable from current position."""
        return list(self.connections.get(self.current_id, []))

    def to_dict(self):
        return {
            "floor_num": self.floor_num,
            "theme_name": self.theme_name,
            "theme_desc": self.theme_desc,
            "rooms": {str(k): v.to_dict() for k, v in self.rooms.items()},
            "connections": {str(k): v for k, v in self.connections.items()},
            "start_id": self.start_id,
            "boss_id": self.boss_id,
            "checkpoint_id": self.checkpoint_id,
            "current_id": self.current_id,
        }

    @classmethod
    def from_dict(cls, d):
        f = cls.__new__(cls)
        f.floor_num = d["floor_num"]
        f.theme_name = d["theme_name"]
        f.theme_desc = d["theme_desc"]
        f.rooms = {int(k): Room.from_dict(v) for k, v in d["rooms"].items()}
        f.connections = {int(k): v for k, v in d["connections"].items()}
        f.start_id = d["start_id"]
        f.boss_id = d["boss_id"]
        f.checkpoint_id = d["checkpoint_id"]
        f.current_id = d["current_id"]
        f.factions = []
        # Repopulate dynamic data (enemies, traps) that can't be serialized easily
        for room in f.rooms.values():
            if not room.cleared:
                f._populate_room(room, f.floor_num)
        return f



def _item_price(item, floor_num):
    from items import Weapon, Armor, Consumable, Trinket
    tier_mult = {"Copper": 1, "Silver": 2, "Gold": 4, "Platinum": 8, "Titanium": 15}
    base = 30
    if isinstance(item, Weapon):
        base = 60
    elif isinstance(item, Armor):
        base = 50
    elif isinstance(item, Consumable):
        base = 25
    elif isinstance(item, Trinket):
        base = 80
    mult = tier_mult.get(item.tier, 1)
    return int(base * mult * (1 + 0.1 * floor_num))
