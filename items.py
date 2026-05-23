"""CRAWL PROTOCOL v2 - Items and tiered box system."""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ── Item base classes ──────────────────────────────────────────────────────────

@dataclass
class Weapon:
    name: str
    damage_dice: str       # e.g. "1d8"
    stat: str              # STR or DEX
    two_handed: bool = False
    bonus: int = 0
    description: str = ""
    tier: str = "Copper"

    def display(self):
        h = "2H" if self.two_handed else "1H"
        b = f" +{self.bonus}" if self.bonus else ""
        return f"{self.name} [{self.damage_dice}{b} {self.stat} {h}]"


@dataclass
class Armor:
    name: str
    ac_bonus: int
    stat_req: Optional[str] = None
    description: str = ""
    tier: str = "Copper"

    def display(self):
        return f"{self.name} [AC+{self.ac_bonus}]"


@dataclass
class Consumable:
    name: str
    effect: str            # "heal_X", "cure_poison", "temp_str_X", etc.
    value: int = 0
    description: str = ""
    tier: str = "Copper"
    quantity: int = 1

    def display(self):
        return f"{self.name} (x{self.quantity})"


@dataclass
class Trinket:
    name: str
    passive: str           # short effect key
    value: int = 0
    description: str = ""
    tier: str = "Copper"

    def display(self):
        return f"{self.name} [passive: {self.passive}]"


# ── Catalogs ───────────────────────────────────────────────────────────────────

WEAPON_CATALOG: Dict[str, Weapon] = {
    "shiv":          Weapon("Shiv",           "1d4",  "DEX", description="Crude but effective."),
    "baton":         Weapon("Baton",          "1d6",  "STR", description="Standard-issue riot control."),
    "combat_knife":  Weapon("Combat Knife",   "1d6",  "DEX", description="Military surplus."),
    "pipe":          Weapon("Iron Pipe",      "1d8",  "STR", two_handed=True, description="Heavy and satisfying."),
    "energy_pistol": Weapon("Energy Pistol",  "1d8",  "DEX", tier="Silver", description="Syndicate-branded sidearm."),
    "shock_baton":   Weapon("Shock Baton",    "1d8",  "STR", tier="Silver", description="Stuns on a natural 18+."),
    "plasma_blade":  Weapon("Plasma Blade",   "1d10", "STR", tier="Gold",   description="Edge holds indefinitely."),
    "arc_rifle":     Weapon("Arc Rifle",      "2d6",  "DEX", two_handed=True, tier="Gold", description="Crowd-pleasing firepower."),
    "void_edge":     Weapon("Void Edge",      "2d8",  "STR", tier="Platinum", description="Cuts through most things."),
    "syndicate_arm": Weapon("Syndicate Arm",  "2d10", "STR", tier="Titanium", bonus=2, description="Sponsor-provided. There are conditions."),
}

ARMOR_CATALOG: Dict[str, Armor] = {
    "scrap_vest":    Armor("Scrap Vest",       1, description="Improvised protection."),
    "leather_coat":  Armor("Leather Coat",     2, description="Better than nothing."),
    "mesh_armor":    Armor("Mesh Armor",       3, tier="Silver", description="Syndicate-standard light armor."),
    "combat_suit":   Armor("Combat Suit",      4, tier="Silver", description="Protocol-issue."),
    "reinforced":    Armor("Reinforced Vest",  5, stat_req="STR", tier="Gold", description="Heavy. Worth it."),
    "exo_shell":     Armor("Exo Shell",        6, stat_req="STR", tier="Gold", description="Experimental."),
    "void_plate":    Armor("Void Plate",       8, stat_req="STR", tier="Titanium", description="They don't make this anymore."),
}

CONSUMABLE_CATALOG: Dict[str, Consumable] = {
    "stim_patch":    Consumable("Stim Patch",   "heal_15",      description="Fast-acting. Tastes awful."),
    "medkit":        Consumable("Medkit",        "heal_30",      tier="Silver", description="Proper field kit."),
    "antidote":      Consumable("Antidote",      "cure_poison",  description="Neutralizes most toxins."),
    "adrenaline":    Consumable("Adrenaline",    "temp_str_4",   tier="Silver", description="+4 STR for 3 rounds."),
    "focus_serum":   Consumable("Focus Serum",   "temp_int_4",   tier="Silver", description="+4 INT for 3 rounds."),
    "rage_dose":     Consumable("Rage Dose",     "berserk",      tier="Gold",   description="Strength at a cost."),
    "full_restore":  Consumable("Full Restore",  "heal_full",    tier="Platinum", description="Syndicate-grade medical."),
    "smoke_flask":   Consumable("Smoke Flask",   "blind_enemy",  description="Useful for fleeing."),
    "acid_flask":    Consumable("Acid Flask",    "acid_3d6",     tier="Silver", description="Throw at enemy."),
}

TRINKET_CATALOG: Dict[str, Trinket] = {
    "rabbit_foot":   Trinket("Rabbit Foot",     "lucky_1",     description="+1 to saving throws."),
    "syndicate_pin": Trinket("Syndicate Pin",   "rating_bonus",description="+5 audience rating per floor."),
    "dogtags":       Trinket("Dog Tags",        "resist_fear", description="You've seen worse."),
    "lucky_chip":    Trinket("Lucky Chip",      "reroll_1_per_floor", tier="Silver", description="One reroll per floor."),
    "whisper_coin":  Trinket("Whisper Coin",    "merchant_10", tier="Gold", description="10% discount at merchants."),
    "void_shard":    Trinket("Void Shard",      "bonus_xp_10", tier="Gold", description="+10% XP from kills."),
}

# ── Backstory starting gear catalog ───────────────────────────────────────────
# Flavor items tied to origin stories. Keyed by the gear_keys in procgen.BACKSTORIES.

BACKSTORY_GEAR: Dict[str, Any] = {
    # Weapons
    "chefs_knife":   Weapon("Chef's Knife",    "1d6",  "DEX", description="Holds an edge. You made sure of it."),
    "scalpel_knife": Weapon("Scalpel",         "1d4",  "DEX", description="Surgical. Precise. Unnerving."),
    "shiv":          Weapon("Shiv",            "1d4",  "DEX", description="Crude but effective."),
    # Armor
    "patient_gown":  Armor("Patient Gown",     0, description="Provides no protection. The audience finds it charming."),
    "pilgrim_robe":  Armor("Pilgrim's Robe",   1, description="Heavy cloth. More comforting than useful."),
    "apron_vest":    Armor("Apron",            1, description="Thick canvas. Better than nothing. Smells like garlic."),
    "work_belt":     Armor("Work Belt",        1, description="Tool loops. A couple of them have things in them."),
    "training_gear": Armor("Training Gear",    1, description="Compression wear. Breathable. Not designed for this."),
    "riot_remnants": Armor("Riot Vest (damaged)", 2, description="Something got through the ceramic. Still better than nothing."),
    "worn_jacket":   Armor("Worn Jacket",      1, description="Found it in a bin three cities ago. Kept it."),
    # Consumables
    "field_rations": Consumable("Field Rations",   "heal_8",   description="Expired two months ago. Still fine probably."),
    "emergency_rations": Consumable("Emergency Rations", "heal_10", description="Emergency only. This qualifies."),
    "worn_medkit":   Consumable("Worn Medkit",     "heal_20",  description="Half the supplies are gone. Half isn't nothing."),
    "stim_patch":    Consumable("Stim Patch",      "heal_15",  description="Fast-acting. Tastes awful."),
    "antidote":      Consumable("Antidote",        "cure_poison", description="Neutralizes most toxins."),
    "smoke_flask":   Consumable("Smoke Flask",     "blind_enemy", description="Useful for fleeing."),
    "surgical_tape": Consumable("Surgical Tape",   "heal_6",   description="Not really a medical item. Used as one anyway."),
    "sports_tape":   Consumable("Sports Tape",     "heal_6",   description="For joint support. Or wounds. Either works."),
    # Trinkets
    "dog_tags_item": Trinket("Dog Tags",        "resist_fear", description="Name, rank, blood type. Two of three still apply."),
    "hospital_id":   Trinket("Hospital ID",     "known_face",  description="Opens some doors. Closes others."),
    "burner_phone":  Trinket("Burner Phone",    "bonus_xp_10", description="Dead battery. The contacts list is encrypted. Still useful somehow."),
    "cracked_tablet": Trinket("Cracked Tablet", "enemy_scan",  description="Pulls Syndicate public records. Mostly."),
    "wire_cutters":  Trinket("Wire Cutters",    "trap_bonus_5",description="+5 to trap disarm checks."),
    "worn_scripture":Trinket("Worn Scripture",  "resist_fear", description="The cover is gone. The words are still there."),
    "field_notebook":Trinket("Field Notes",     "enemy_scan",  description="Annotated. Some of it is even accurate."),
    "reading_glasses":Trinket("Reading Glasses","enemy_scan",  description="Prescription is wrong. You squint a lot."),
    "scavenger_pack":Trinket("Scavenger Pack",  "eagle_eye",   description="Jury-rigged. Finds things other people miss."),
    "mystery_note":  Trinket("Mystery Note",    "lucky_1",     description="'Good luck - you're going to need it.' You kept it."),
    "rabbit_foot":   Trinket("Rabbit Foot",     "lucky_1",     description="+1 to saving throws."),
}


# ── Box system ─────────────────────────────────────────────────────────────────

_BOX_TABLES = {
    "Copper": {
        "weapons":     ["shiv", "baton", "combat_knife"],
        "armors":      ["scrap_vest", "leather_coat"],
        "consumables": ["stim_patch", "antidote", "smoke_flask"],
        "trinkets":    ["rabbit_foot", "dogtags"],
        "credits":     (20, 60),
    },
    "Silver": {
        "weapons":     ["baton", "combat_knife", "pipe", "energy_pistol", "shock_baton"],
        "armors":      ["leather_coat", "mesh_armor", "combat_suit"],
        "consumables": ["medkit", "adrenaline", "focus_serum", "acid_flask"],
        "trinkets":    ["syndicate_pin", "lucky_chip"],
        "credits":     (60, 150),
    },
    "Gold": {
        "weapons":     ["energy_pistol", "plasma_blade", "arc_rifle"],
        "armors":      ["combat_suit", "reinforced", "exo_shell"],
        "consumables": ["rage_dose", "medkit", "focus_serum"],
        "trinkets":    ["whisper_coin", "void_shard", "lucky_chip"],
        "credits":     (150, 350),
    },
    "Platinum": {
        "weapons":     ["plasma_blade", "arc_rifle", "void_edge"],
        "armors":      ["reinforced", "exo_shell"],
        "consumables": ["full_restore", "rage_dose"],
        "trinkets":    ["whisper_coin", "void_shard"],
        "credits":     (300, 700),
    },
    "Titanium": {
        "weapons":     ["void_edge", "syndicate_arm"],
        "armors":      ["void_plate"],
        "consumables": ["full_restore"],
        "trinkets":    ["void_shard"],
        "credits":     (600, 1500),
    },
}

# Probability weights: [weapon, armor, consumable, trinket, credits, nothing]
_BOX_WEIGHTS = {
    "Copper":   [20, 15, 30, 10, 20, 5],
    "Silver":   [25, 20, 25, 15, 12, 3],
    "Gold":     [25, 20, 20, 20, 15, 0],
    "Platinum": [30, 25, 20, 20, 5, 0],
    "Titanium": [35, 30, 20, 15, 0, 0],
}


def open_box(tier="Copper"):
    """Open a loot box and return a list of items/tuples."""
    table = _BOX_TABLES.get(tier, _BOX_TABLES["Copper"])
    weights = _BOX_WEIGHTS.get(tier, _BOX_WEIGHTS["Copper"])
    categories = ["weapon", "armor", "consumable", "trinket", "credits", "nothing"]

    results = []
    # Primary drop
    cat = _weighted_choice(categories, weights)
    item = _resolve_drop(cat, table)
    if item is not None:
        results.append(item)

    # Bonus roll on Gold+
    tier_order = ["Copper", "Silver", "Gold", "Platinum", "Titanium"]
    tier_idx = tier_order.index(tier) if tier in tier_order else 0
    if tier_idx >= 2 and random.random() < 0.4:
        cat2 = _weighted_choice(categories, weights)
        item2 = _resolve_drop(cat2, table)
        if item2 is not None:
            results.append(item2)

    return results


def _weighted_choice(options, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0
    for opt, w in zip(options, weights):
        acc += w
        if r <= acc:
            return opt
    return options[-1]


def _resolve_drop(category, table):
    if category == "weapon":
        key = random.choice(table["weapons"])
        import copy
        return copy.deepcopy(WEAPON_CATALOG[key])
    elif category == "armor":
        key = random.choice(table["armors"])
        import copy
        return copy.deepcopy(ARMOR_CATALOG[key])
    elif category == "consumable":
        key = random.choice(table["consumables"])
        import copy
        return copy.deepcopy(CONSUMABLE_CATALOG[key])
    elif category == "trinket":
        key = random.choice(table["trinkets"])
        import copy
        return copy.deepcopy(TRINKET_CATALOG[key])
    elif category == "credits":
        lo, hi = table["credits"]
        return ("credits", random.randint(lo, hi))
    return None


def open_class_box(available_classes):
    """Returns 3 random class keys from available_classes list."""
    pool = list(available_classes)
    random.shuffle(pool)
    return pool[:3]


def open_skill_box(character_class_key):
    """Returns 2 skill-style feature names relevant to the class."""
    from features import FEATURE_CATALOG
    relevant = [k for k, f in FEATURE_CATALOG.items()
                if character_class_key and character_class_key.lower() in (f.tags or [])]
    all_feats = list(FEATURE_CATALOG.keys())
    if len(relevant) < 2:
        relevant = all_feats
    random.shuffle(relevant)
    return relevant[:2]


def floor_loot_tier(floor_num):
    tiers = ["Copper", "Copper", "Silver", "Silver", "Gold",
             "Gold", "Platinum", "Platinum", "Titanium", "Titanium"]
    idx = min(floor_num - 1, len(tiers) - 1)
    return tiers[idx]


# ── Serialisation ──────────────────────────────────────────────────────────────

def item_to_dict(item):
    if item is None:
        return None
    d = {"_type": item.__class__.__name__}
    d.update(item.__dict__)
    return d


def item_from_dict(d):
    if d is None:
        return None
    t = d.get("_type")
    data = {k: v for k, v in d.items() if k != "_type"}
    if t == "Weapon":
        return Weapon(**data)
    if t == "Armor":
        return Armor(**data)
    if t == "Consumable":
        return Consumable(**data)
    if t == "Trinket":
        return Trinket(**data)
    return None


def get_starting_weapon(class_key=None):
    import copy
    if class_key in ("rogue", "ranger"):
        return copy.deepcopy(WEAPON_CATALOG["combat_knife"])
    return copy.deepcopy(WEAPON_CATALOG["baton"])


def get_starting_armor(class_key=None):
    import copy
    return copy.deepcopy(ARMOR_CATALOG["scrap_vest"])
