"""CRAWL PROTOCOL - Environmental objects in rooms.

Each room can contain 0..N EnvObjects: loose wiring, water pools, fuel
drums, machinery, shelves, etc. Objects have:

  - combine_tags: short tags used to detect lethal pairings (electric+liquid,
    flammable+spark, acid+fire, gas+spark).
  - strip_yield: materials granted when the player strips the object for
    crafting.
  - combat_effect: damage / condition applied when used directly in combat.
  - hidden: true objects only appear after a successful Look check.

Localized name/description keys live in pl.json / en.json under
`env_<key>_n` and `env_<key>_d`.
"""
import copy
import random
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from lang import tr


# ── EnvObject ─────────────────────────────────────────────────────────────────

@dataclass
class EnvObject:
    key: str
    material_tags: List[str] = field(default_factory=list)
    combine_tags: List[str] = field(default_factory=list)
    combat_effect: Optional[Dict] = None    # {"damage":"3d6","condition":"burning"}
    strip_yield: Dict[str, int] = field(default_factory=dict)
    consumed: bool = False
    stripped: bool = False
    hidden: bool = False
    detect_dc: int = 12

    @property
    def name(self) -> str:
        return tr(f"env_{self.key}_n")

    @property
    def description(self) -> str:
        return tr(f"env_{self.key}_d")

    def display(self) -> str:
        flags = []
        if self.consumed:
            flags.append("X")
        if self.stripped:
            flags.append("-")
        flag_s = f" [{'/'.join(flags)}]" if flags else ""
        return f"{self.name}{flag_s}"

    def to_dict(self):
        return {
            "key": self.key,
            "material_tags": list(self.material_tags),
            "combine_tags": list(self.combine_tags),
            "combat_effect": dict(self.combat_effect) if self.combat_effect else None,
            "strip_yield": dict(self.strip_yield),
            "consumed": self.consumed,
            "stripped": self.stripped,
            "hidden": self.hidden,
            "detect_dc": self.detect_dc,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            key=d["key"],
            material_tags=list(d.get("material_tags", [])),
            combine_tags=list(d.get("combine_tags", [])),
            combat_effect=dict(d["combat_effect"]) if d.get("combat_effect") else None,
            strip_yield=dict(d.get("strip_yield", {})),
            consumed=d.get("consumed", False),
            stripped=d.get("stripped", False),
            hidden=d.get("hidden", False),
            detect_dc=d.get("detect_dc", 12),
        )


# ── Catalog ───────────────────────────────────────────────────────────────────
# Tags reference: electric, liquid, flammable, gas, spark, acid, heavy, fragile

ENV_CATALOG: Dict[str, EnvObject] = {
    "loose_cables":  EnvObject("loose_cables",  ["wire","scrap_metal"], ["electric","spark"],
                                combat_effect={"damage":"1d6","condition":"stunned"},
                                strip_yield={"wire":2}),
    "water_pool":    EnvObject("water_pool",    ["water"], ["liquid"],
                                combat_effect=None,  # only useful in combos
                                strip_yield={}),
    "fuel_drum":     EnvObject("fuel_drum",     ["fuel","scrap_metal"], ["flammable","liquid"],
                                combat_effect={"damage":"2d6"},
                                strip_yield={"fuel":1,"scrap_metal":1}),
    "gas_vent":      EnvObject("gas_vent",      ["chem"], ["gas","flammable"],
                                combat_effect={"damage":"1d4","condition":"poisoned"},
                                strip_yield={"chem":1}),
    "acid_barrel":   EnvObject("acid_barrel",   ["chem","scrap_metal"], ["acid","liquid"],
                                combat_effect={"damage":"2d6","condition":"burning"},
                                strip_yield={"chem":2,"scrap_metal":1}),
    "heavy_shelf":   EnvObject("heavy_shelf",   ["scrap_metal","glass"], ["heavy","fragile"],
                                combat_effect={"damage":"2d8"},
                                strip_yield={"scrap_metal":2,"glass":1}),
    "broken_terminal": EnvObject("broken_terminal", ["wire","glass","scrap_metal"], ["electric","spark"],
                                combat_effect=None,
                                strip_yield={"wire":1,"glass":1,"scrap_metal":1}),
    "exposed_wire":  EnvObject("exposed_wire",  ["wire"], ["electric","spark"],
                                combat_effect={"damage":"1d8","condition":"stunned"},
                                strip_yield={"wire":1}),
    "steam_pipe":    EnvObject("steam_pipe",    ["scrap_metal"], ["heavy","gas"],
                                combat_effect={"damage":"1d10","condition":"burning"},
                                strip_yield={"scrap_metal":2}),
    "loose_grate":   EnvObject("loose_grate",   ["scrap_metal"], ["heavy"],
                                combat_effect={"damage":"1d6"},
                                strip_yield={"scrap_metal":1}),
    "fire_extinguisher": EnvObject("fire_extinguisher", ["chem","scrap_metal"], ["chemical","cold"],
                                combat_effect={"damage":"1d4","condition":"blinded"},
                                strip_yield={"chem":1,"scrap_metal":1}),
    "shattered_glass": EnvObject("shattered_glass", ["glass"], ["fragile"],
                                combat_effect={"damage":"1d4"},
                                strip_yield={"glass":2},
                                hidden=True, detect_dc=10),
    "hanging_lamp":  EnvObject("hanging_lamp",  ["glass","wire"], ["fragile","spark"],
                                combat_effect={"damage":"1d6","condition":"blinded"},
                                strip_yield={"glass":1,"wire":1}),
    "rusted_locker": EnvObject("rusted_locker", ["scrap_metal"], ["heavy"],
                                combat_effect=None,
                                strip_yield={"scrap_metal":2}),
    "ammo_crate":    EnvObject("ammo_crate",    ["powder","scrap_metal"], ["flammable","spark"],
                                combat_effect={"damage":"3d6"},
                                strip_yield={"powder":2,"scrap_metal":1},
                                hidden=True, detect_dc=14),
}


# ── Lethal combos (frozenset of tags -> effect) ───────────────────────────────

COMBO_TABLE = {
    frozenset({"electric","liquid"}): {"damage":"4d6","condition":"stunned","aoe":True,"label_key":"combo_shock"},
    frozenset({"acid","fire"}):       {"damage":"3d8","condition":"burning","aoe":True,"label_key":"combo_burn"},
    frozenset({"flammable","spark"}): {"damage":"2d6","condition":"burning","aoe":False,"label_key":"combo_ignite"},
    frozenset({"gas","spark"}):       {"damage":"5d6","condition":"burning","aoe":True,"label_key":"combo_explode"},
    frozenset({"heavy","fragile"}):   {"damage":"3d6","condition":None,"aoe":False,"label_key":"combo_crush"},
}


# ── Per-floor / per-room-type spawn tables ────────────────────────────────────

# Each room type maps to a list of (env_key, weight). Weights are relative.
ROOM_TYPE_ENV_POOL = {
    "combat":   [("loose_cables",3),("water_pool",2),("heavy_shelf",2),("fuel_drum",1),
                 ("gas_vent",1),("exposed_wire",2),("steam_pipe",2),("loose_grate",2),
                 ("hanging_lamp",2),("shattered_glass",1),("rusted_locker",1),
                 ("broken_terminal",1),("ammo_crate",1)],
    "trap":     [("gas_vent",2),("exposed_wire",2),("steam_pipe",1)],
    "treasure": [("rusted_locker",3),("broken_terminal",1),("loose_cables",1),
                 ("shattered_glass",1)],
    "rest":     [("rusted_locker",2),("broken_terminal",1)],
    "merchant": [("rusted_locker",2),("broken_terminal",1)],
    "lore":     [("broken_terminal",3),("shattered_glass",1)],
    "mutation": [("acid_barrel",2),("gas_vent",2),("fuel_drum",1)],
    "checkpoint":[("rusted_locker",2),("broken_terminal",1),("fire_extinguisher",1)],
    "boss":     [("loose_cables",3),("steam_pipe",2),("acid_barrel",1),("heavy_shelf",1),
                 ("fuel_drum",2),("hanging_lamp",1)],
    "start":    [],
}


def populate_environment(room, floor_num: int = 1):
    """
    Generate 0-3 EnvObjects for a room based on its type.
    Deeper floors lean more dangerous (more flammable/electric).
    """
    pool = ROOM_TYPE_ENV_POOL.get(room.room_type, [])
    if not pool:
        return

    # How many objects to spawn
    if room.room_type in ("combat", "boss"):
        count = random.choices([1,2,3,0], weights=[40,30,15,15])[0]
    elif room.room_type in ("trap","mutation","treasure"):
        count = random.choices([0,1,2], weights=[40,45,15])[0]
    else:
        count = random.choices([0,1,2], weights=[60,30,10])[0]
    if count == 0:
        return

    keys = [k for k, _ in pool]
    weights = [w for _, w in pool]

    chosen = []
    for _ in range(count):
        if not keys:
            break
        key = random.choices(keys, weights=weights, k=1)[0]
        chosen.append(key)
        # Allow duplicates but slightly drop weight to spread variety
        idx = keys.index(key)
        weights[idx] = max(1, weights[idx] - 1)

    for k in chosen:
        proto = ENV_CATALOG.get(k)
        if proto:
            room.env_objects.append(copy.deepcopy(proto))


# ── Resolution helpers ────────────────────────────────────────────────────────

# ASCII-fold Polish diacritics so "kabli" matches "kable" and "szafkę" matches "szafka"
_PL_FOLD = str.maketrans({
    "ą":"a", "ć":"c", "ę":"e", "ł":"l", "ń":"n",
    "ó":"o", "ś":"s", "ź":"z", "ż":"z",
    "Ą":"a", "Ć":"c", "Ę":"e", "Ł":"l", "Ń":"n",
    "Ó":"o", "Ś":"s", "Ź":"z", "Ż":"z",
})

# Polish stop-words and short verbs we never want to use as object cues.
_STOP_TOKENS = {
    "use","with","on","at","the","a","an","to","for","in","into","my","his","her","this","that",
    "uzyj","użyj","wez","weź","rzuc","rzuć","polacz","połącz","kombinuj","wrzuc","wrzuć",
    "do","na","w","z","i","oraz","sie","się","go","ja","ją","wroga","wroga.",
    "zerwij","zlap","złap","atakuj","uderz",
}


def _fold(s: str) -> str:
    return s.lower().translate(_PL_FOLD)


def find_object(room, text: str) -> Optional[EnvObject]:
    """Match a free-text fragment against env objects in the room.

    Strategy: ASCII-fold (Polish diacritics → ASCII), tokenize the input,
    drop stop-words, and accept any token whose 4+ char prefix appears
    in any haystack token's prefix as well (handles Polish case endings).
    """
    if not text:
        return None
    norm = _fold(text).strip()
    if not norm:
        return None

    raw_tokens = [t for t in re.split(r"[^a-z0-9]+", norm) if len(t) >= 3]
    tokens = [t for t in raw_tokens if t not in _STOP_TOKENS]
    if not tokens:
        return None

    visible = [o for o in room.env_objects
               if not (o.hidden and not room.inspected) and not o.consumed]
    for obj in visible:
        haystacks = [
            _fold(obj.key.replace("_", " ")),
            _fold(obj.name),
        ]
        hay_tokens = []
        for h in haystacks:
            hay_tokens.extend(re.split(r"[^a-z0-9]+", h))
        hay_tokens = [t for t in hay_tokens if len(t) >= 3]
        for t in tokens:
            stem = t[:4]
            for ht in hay_tokens:
                if ht.startswith(stem) or t.startswith(ht[:4]):
                    return obj
    return None


def available_combo(room) -> Optional[tuple]:
    """If two visible non-consumed objects share complementary combine tags,
    return (objA, objB, effect_dict). Otherwise None."""
    visible = [o for o in room.env_objects
               if not (o.hidden and not room.inspected) and not o.consumed]
    n = len(visible)
    for i in range(n):
        for j in range(i + 1, n):
            tags = set(visible[i].combine_tags) | set(visible[j].combine_tags)
            for combo_set, effect in COMBO_TABLE.items():
                if combo_set.issubset(tags):
                    return visible[i], visible[j], effect
    return None


def reveal_hidden(room, perception_roll: int):
    """Inspecting the room. Reveals hidden objects whose detect_dc <= roll."""
    room.inspected = True
    revealed = []
    for obj in room.env_objects:
        if obj.hidden and obj.detect_dc <= perception_roll:
            obj.hidden = False
            revealed.append(obj)
    return revealed
