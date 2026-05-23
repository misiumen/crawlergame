"""CRAWL PROTOCOL v2 - Character model."""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from utils import ability_modifier, proficiency_bonus, parse_dice, clamp, d20
from config import (BASE_STATS, POINT_BUY_BUDGET, STAT_COST,
                    XP_THRESHOLDS, LEVEL_CAP)
from items import (Weapon, Armor, Consumable, Trinket,
                   item_to_dict, item_from_dict,
                   get_starting_weapon, get_starting_armor)
from features import Feature, feature_to_dict, feature_from_dict


# ── Background definitions ─────────────────────────────────────────────────────

BACKGROUNDS = {
    "Soldier": {
        "desc": "Military background. +2 STR, +1 CON. Start with Combat Knife.",
        "stat_bonus": {"STR": 2, "CON": 1},
        "perk": "soldier_training",   # +1 proficiency bonus in combat
        "perk_desc": "+1 to all attack rolls.",
    },
    "Nurse": {
        "desc": "Medical professional. +2 WIS, +1 INT. Start with Medkit.",
        "stat_bonus": {"WIS": 2, "INT": 1},
        "perk": "field_medic",
        "perk_desc": "Healing items restore +5 HP.",
    },
    "Electrician": {
        "desc": "Practical technician. +2 INT, +1 DEX. Traps easier to disarm.",
        "stat_bonus": {"INT": 2, "DEX": 1},
        "perk": "wire_sense",
        "perk_desc": "+3 to trap disarm checks.",
    },
    "Hacker": {
        "desc": "Digital infiltrator. +2 INT, +1 DEX. Bypass some locks.",
        "stat_bonus": {"INT": 2, "DEX": 1},
        "perk": "system_access",
        "perk_desc": "Can attempt to disable electronic traps without a roll.",
    },
    "Chef": {
        "desc": "Culinary combat. +1 CON, +1 WIS. Consumables last longer.",
        "stat_bonus": {"CON": 1, "WIS": 1},
        "perk": "prep_work",
        "perk_desc": "Consumables give +3 bonus to their effect.",
    },
    "Athlete": {
        "desc": "Physical peak. +2 STR, +2 DEX. Better flee checks.",
        "stat_bonus": {"STR": 2, "DEX": 2},
        "perk": "peak_condition",
        "perk_desc": "+2 to DEX checks and flee rolls.",
    },
    "Scavenger": {
        "desc": "Survivor instinct. +1 all stats. Better loot detection.",
        "stat_bonus": {"STR": 1, "DEX": 1, "CON": 1, "INT": 1, "WIS": 1, "CHA": 1},
        "perk": "eagle_eye",
        "perk_desc": "Find extra loot in cleared rooms.",
    },
    "Preacher": {
        "desc": "Faithful and resilient. +2 CHA, +2 WIS. Rally morale.",
        "stat_bonus": {"CHA": 2, "WIS": 2},
        "perk": "sermon",
        "perk_desc": "+2 to saves vs fear/mental effects.",
    },
    "Academic": {
        "desc": "Analytical mind. +3 INT. Identify items and traps passively.",
        "stat_bonus": {"INT": 3},
        "perk": "studied",
        "perk_desc": "See enemy stats without using a skill.",
    },
    "Drifter": {
        "desc": "No fixed ties. +1 DEX, +1 CHA. Adapt quickly.",
        "stat_bonus": {"DEX": 1, "CHA": 1},
        "perk": "adaptable",
        "perk_desc": "Once per floor, reroll any single check.",
    },
}

# ── Class definitions ──────────────────────────────────────────────────────────

CLASSES = {
    "warrior": {
        "name": "Warrior",
        "primary": ["STR", "CON"],
        "hit_die": "1d10",
        "base_ac": 12,
        "desc": "Frontline fighter. High HP, heavy weapons.",
        "starting_features": ["power_strike", "second_wind", "rally"],
    },
    "rogue": {
        "name": "Rogue",
        "primary": ["DEX", "INT"],
        "hit_die": "1d8",
        "base_ac": 13,
        "desc": "Precise and deceptive. Sneak attacks and evasion.",
        "starting_features": ["sneak_attack", "evasion", "smoke_dash"],
    },
    "ranger": {
        "name": "Ranger",
        "primary": ["DEX", "WIS"],
        "hit_die": "1d8",
        "base_ac": 13,
        "desc": "Ranged specialist. Traps and tracking.",
        "starting_features": ["aimed_shot", "hunters_mark", "trap_mastery"],
    },
    "mage": {
        "name": "Mage",
        "primary": ["INT", "WIS"],
        "hit_die": "1d6",
        "base_ac": 11,
        "desc": "Arcane power. Spells and shields.",
        "starting_features": ["fireball", "magic_missile", "arcane_shield"],
    },
    "cleric": {
        "name": "Cleric",
        "primary": ["WIS", "CON"],
        "hit_die": "1d8",
        "base_ac": 13,
        "desc": "Holy warrior. Healing and divine damage.",
        "starting_features": ["divine_smite", "heal_prayer", "holy_ward"],
    },
    "warlock": {
        "name": "Warlock",
        "primary": ["CHA", "INT"],
        "hit_die": "1d8",
        "base_ac": 12,
        "desc": "Pact magic. Dark power at a price.",
        "starting_features": ["eldritch_blast", "hex", "dark_pact"],
    },
    "engineer": {
        "name": "Engineer",
        "primary": ["INT", "DEX"],
        "hit_die": "1d8",
        "base_ac": 13,
        "desc": "Tech specialist. Turrets and gadgets.",
        "starting_features": ["deploy_turret", "emp_pulse", "shield_drone"],
    },
    "psion": {
        "name": "Psion",
        "primary": ["INT", "WIS"],
        "hit_die": "1d6",
        "base_ac": 12,
        "desc": "Mental power. Psychic damage and control.",
        "starting_features": ["mind_blast", "telekinetic_throw", "precognition"],
    },
}


# ── Character class ────────────────────────────────────────────────────────────

class Character:
    def __init__(self):
        self.name: str = "Unnamed"
        self.background: str = "Drifter"
        self.background_perk: str = "adaptable"

        # Ability scores
        self.stats: Dict[str, int] = {s: 10 for s in BASE_STATS}

        # Class (earned via Class Box)
        self.class_key: Optional[str] = None
        self.class_name: str = "Unclassified"
        self.secondary_class: Optional[str] = None
        self.hybrid_class: Optional[str] = None
        self.specialization: Optional[str] = None

        # Level / XP
        self.level: int = 1
        self.xp: int = 0

        # HP
        self.max_hp: int = 10
        self.hp: int = 10

        # AC
        self.base_ac: int = 10
        self.ac: int = 10

        # Equipment
        self.weapon: Optional[Weapon] = None
        self.armor: Optional[Armor] = None
        self.trinket: Optional[Trinket] = None
        self.inventory: List[Any] = []

        # Features
        self.features: List[Feature] = []

        # Economy
        self.credits: int = 50

        # Audience
        self.audience_rating: int = 0

        # Dungeon state
        self.current_floor: int = 1
        self.current_room_index: int = 0
        self.rooms_cleared: int = 0

        # Conditions (combat)
        self.conditions: List[str] = []
        self.temp_ac_bonus: int = 0
        self.temp_stat_bonus: Dict[str, int] = {}
        self.temp_rounds: int = 0

        # Mutations
        self.mutations: List[Dict] = []

        # Achievements
        self.unlocked_achievements: List[str] = []

        # Flags
        self.class_box_choices: List[str] = []  # pending class choice

    # ── Derived stats ──────────────────────────────────────────────────────────

    def stat_mod(self, stat):
        base = self.stats.get(stat, 10)
        bonus = self.temp_stat_bonus.get(stat, 0)
        return ability_modifier(base + bonus)

    def prof(self):
        return proficiency_bonus(self.level)

    def effective_ac(self):
        armor_bonus = self.armor.ac_bonus if self.armor else 0
        return self.base_ac + armor_bonus + self.stat_mod("DEX") + self.temp_ac_bonus

    def xp_to_next(self):
        next_lvl = self.level + 1
        if next_lvl > LEVEL_CAP:
            return 9999
        return XP_THRESHOLDS.get(next_lvl, 9999)

    def attack_stat(self):
        if self.weapon and self.weapon.stat == "DEX":
            return "DEX"
        return "STR"

    def attack_roll(self):
        raw = d20()
        total = raw + self.stat_mod(self.attack_stat()) + self.prof()
        return raw, total

    def damage_roll(self):
        dice = self.weapon.damage_dice if self.weapon else "1d4"
        base = parse_dice(dice) + self.stat_mod(self.attack_stat())
        if self.weapon and self.weapon.bonus:
            base += self.weapon.bonus
        return max(1, base)

    def is_alive(self):
        return self.hp > 0

    # ── Modification ──────────────────────────────────────────────────────────

    def initialize(self):
        """Compute max HP and AC from stats/class after creation."""
        hit_die = "1d10"
        if self.class_key and self.class_key in CLASSES:
            hit_die = CLASSES[self.class_key]["hit_die"]
            self.base_ac = CLASSES[self.class_key]["base_ac"]
        con_mod = self.stat_mod("CON")
        self.max_hp = parse_dice(hit_die) + con_mod + 4  # generous base
        self.max_hp = max(8, self.max_hp)
        self.hp = self.max_hp
        self.ac = self.effective_ac()

    def assign_class(self, class_key):
        if class_key not in CLASSES:
            return
        self.class_key = class_key
        cls = CLASSES[class_key]
        self.class_name = cls["name"]
        self.base_ac = cls["base_ac"]
        from features import get_feature
        for fname in cls["starting_features"]:
            feat = get_feature(fname)
            if feat and feat.name not in [f.name for f in self.features]:
                self.features.append(feat)
        # Recalc HP with class hit die
        hit_die = cls["hit_die"]
        con_mod = self.stat_mod("CON")
        new_max = parse_dice(hit_die) + con_mod + 4
        gain = max(0, new_max - self.max_hp)
        self.max_hp = max(self.max_hp, new_max)
        self.hp = min(self.max_hp, self.hp + gain)

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def add_xp(self, amount):
        self.xp += amount
        while self.level < LEVEL_CAP and self.xp >= self.xp_to_next():
            self._level_up()

    def _level_up(self):
        self.level += 1
        hit_die = "1d10"
        if self.class_key and self.class_key in CLASSES:
            hit_die = CLASSES[self.class_key]["hit_die"]
        con_mod = self.stat_mod("CON")
        hp_gain = parse_dice(hit_die) + con_mod
        hp_gain = max(1, hp_gain)
        self.max_hp += hp_gain
        self.hp = min(self.max_hp, self.hp + hp_gain)
        return True

    def short_rest(self):
        hit_die = "1d10"
        if self.class_key and self.class_key in CLASSES:
            hit_die = CLASSES[self.class_key]["hit_die"]
        heal_amount = parse_dice(hit_die) + self.stat_mod("CON")
        heal_amount = max(1, heal_amount)
        self.heal(heal_amount)
        for f in self.features:
            f.restore()
        return heal_amount

    def reset_combat_temps(self):
        self.conditions = []
        self.temp_ac_bonus = 0
        self.temp_stat_bonus = {}
        self.temp_rounds = 0

    def use_consumable(self, item):
        """Apply a consumable effect. Returns description string."""
        if not isinstance(item, Consumable):
            return "Not a consumable."
        effect = item.effect
        bonus = 3 if self.background_perk == "prep_work" else 0

        if effect.startswith("heal_"):
            if effect == "heal_full":
                self.heal(self.max_hp)
                return f"Fully restored HP."
            amount = int(effect.split("_")[1]) + bonus
            self.heal(amount)
            return f"Restored {amount} HP."
        elif effect == "cure_poison":
            self.conditions = [c for c in self.conditions if c != "poisoned"]
            return "Cured poison."
        elif effect.startswith("temp_str_"):
            amt = int(effect.split("_")[2])
            self.temp_stat_bonus["STR"] = amt
            self.temp_rounds = 3
            return f"+{amt} STR for 3 rounds."
        elif effect.startswith("temp_int_"):
            amt = int(effect.split("_")[2])
            self.temp_stat_bonus["INT"] = amt
            self.temp_rounds = 3
            return f"+{amt} INT for 3 rounds."
        elif effect == "berserk":
            self.temp_stat_bonus["STR"] = 6
            self.temp_rounds = 4
            return "+6 STR berserk mode for 4 rounds."
        elif effect == "blind_enemy":
            return "smoke_flask"  # combat handles this
        elif effect.startswith("acid_"):
            return effect  # combat handles direct damage
        return f"Used {item.name}."

    def equip_weapon(self, weapon):
        if self.weapon:
            self.inventory.append(self.weapon)
        self.weapon = weapon

    def equip_armor(self, armor):
        if self.armor:
            self.inventory.append(self.armor)
        self.armor = armor

    def equip_trinket(self, trinket):
        if self.trinket:
            self.inventory.append(self.trinket)
        self.trinket = trinket

    def add_to_inventory(self, item):
        self.inventory.append(item)

    def remove_from_inventory(self, item):
        if item in self.inventory:
            self.inventory.remove(item)

    def add_mutation(self, mutation_dict):
        self.mutations.append(mutation_dict)
        for stat, val in mutation_dict.get("stat_bonus", {}).items():
            self.stats[stat] = self.stats.get(stat, 10) + val
        hp_bonus = mutation_dict.get("hp_bonus", 0)
        if hp_bonus:
            self.max_hp += hp_bonus
            self.hp += hp_bonus

    def add_audience(self, amount):
        self.audience_rating = max(0, self.audience_rating + amount)

    # ── Serialisation ──────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "name": self.name,
            "background": self.background,
            "background_perk": self.background_perk,
            "stats": dict(self.stats),
            "class_key": self.class_key,
            "class_name": self.class_name,
            "secondary_class": self.secondary_class,
            "hybrid_class": self.hybrid_class,
            "specialization": self.specialization,
            "level": self.level,
            "xp": self.xp,
            "max_hp": self.max_hp,
            "hp": self.hp,
            "base_ac": self.base_ac,
            "weapon": item_to_dict(self.weapon),
            "armor": item_to_dict(self.armor),
            "trinket": item_to_dict(self.trinket),
            "inventory": [item_to_dict(i) for i in self.inventory],
            "features": [feature_to_dict(f) for f in self.features],
            "credits": self.credits,
            "audience_rating": self.audience_rating,
            "current_floor": self.current_floor,
            "current_room_index": self.current_room_index,
            "rooms_cleared": self.rooms_cleared,
            "mutations": list(self.mutations),
            "unlocked_achievements": list(self.unlocked_achievements),
            "conditions": list(self.conditions),
        }

    @classmethod
    def from_dict(cls, d):
        c = cls()
        c.name = d["name"]
        c.background = d.get("background", "Drifter")
        c.background_perk = d.get("background_perk", "adaptable")
        c.stats = d.get("stats", {s: 10 for s in BASE_STATS})
        c.class_key = d.get("class_key")
        c.class_name = d.get("class_name", "Unclassified")
        c.secondary_class = d.get("secondary_class")
        c.hybrid_class = d.get("hybrid_class")
        c.specialization = d.get("specialization")
        c.level = d.get("level", 1)
        c.xp = d.get("xp", 0)
        c.max_hp = d.get("max_hp", 10)
        c.hp = d.get("hp", c.max_hp)
        c.base_ac = d.get("base_ac", 10)
        c.weapon = item_from_dict(d.get("weapon"))
        c.armor = item_from_dict(d.get("armor"))
        c.trinket = item_from_dict(d.get("trinket"))
        c.inventory = [item_from_dict(i) for i in d.get("inventory", []) if i]
        c.features = [feature_from_dict(f) for f in d.get("features", [])]
        c.credits = d.get("credits", 50)
        c.audience_rating = d.get("audience_rating", 0)
        c.current_floor = d.get("current_floor", 1)
        c.current_room_index = d.get("current_room_index", 0)
        c.rooms_cleared = d.get("rooms_cleared", 0)
        c.mutations = d.get("mutations", [])
        c.unlocked_achievements = d.get("unlocked_achievements", [])
        c.conditions = d.get("conditions", [])
        return c

    # ── Display helpers ────────────────────────────────────────────────────────

    def stat_block_lines(self):
        lines = []
        for s in BASE_STATS:
            val = self.stats.get(s, 10)
            mod = ability_modifier(val)
            sign = "+" if mod >= 0 else ""
            lines.append(f"{s}: {val:2d} ({sign}{mod})")
        return lines

    def gear_lines(self):
        lines = []
        lines.append(f"Weapon : {self.weapon.display() if self.weapon else 'None'}")
        lines.append(f"Armor  : {self.armor.display() if self.armor else 'None'}")
        lines.append(f"Trinket: {self.trinket.display() if self.trinket else 'None'}")
        return lines

    def feature_lines(self):
        if not self.features:
            return ["(no features)"]
        return [f"{f.name} - {f.description}" for f in self.features]


# ── Character creation (called from game.py state machine) ────────────────────

def create_character_data(name, background_key, stat_allocations):
    """
    Create a Character from creation screen data.
    stat_allocations: dict {stat: score} after point-buy.
    Returns Character instance.
    """
    c = Character()
    c.name = name
    c.background = background_key
    bg = BACKGROUNDS.get(background_key, BACKGROUNDS["Drifter"])
    c.background_perk = bg["perk"]

    c.stats = dict(stat_allocations)
    for stat, bonus in bg.get("stat_bonus", {}).items():
        c.stats[stat] = c.stats.get(stat, 10) + bonus

    c.weapon = get_starting_weapon()
    c.armor = get_starting_armor()
    c.credits = 50

    c.max_hp = 8 + ability_modifier(c.stats.get("CON", 10)) + 2
    c.max_hp = max(8, c.max_hp)
    c.hp = c.max_hp
    c.base_ac = 10

    return c


def apply_backstory_gear(character, backstory):
    """
    Replace character's starting gear with backstory-specific items.
    backstory is a dict from procgen.get_backstory().
    """
    import copy
    from items import BACKSTORY_GEAR, Weapon, Armor, Consumable, Trinket

    gear_keys = backstory.get("gear_keys", [])
    credits_mod = backstory.get("credits_mod", 0)

    character.weapon = None
    character.armor = None
    # Don't wipe trinket slot yet — assign from gear

    for key in gear_keys:
        item = BACKSTORY_GEAR.get(key)
        if item is None:
            # Fall back to standard catalogs
            from items import WEAPON_CATALOG, ARMOR_CATALOG, CONSUMABLE_CATALOG, TRINKET_CATALOG
            item = (WEAPON_CATALOG.get(key) or ARMOR_CATALOG.get(key) or
                    CONSUMABLE_CATALOG.get(key) or TRINKET_CATALOG.get(key))
        if item is None:
            continue
        item = copy.deepcopy(item)
        if isinstance(item, Weapon) and character.weapon is None:
            character.weapon = item
        elif isinstance(item, Armor) and character.armor is None:
            character.armor = item
        elif isinstance(item, Trinket) and character.trinket is None:
            character.trinket = item
        elif isinstance(item, Consumable):
            character.inventory.append(item)
        else:
            # Extra weapon/armor/trinket goes to inventory
            character.inventory.append(item)

    # Fallback: ensure a weapon and armor exist
    if character.weapon is None:
        character.weapon = get_starting_weapon()
    if character.armor is None:
        character.armor = get_starting_armor()

    character.credits = max(10, 50 + credits_mod)


def randomize_character():
    """
    Build a fully random character: random name, background, and stats via 4d6-drop-lowest.
    Returns (character, backstory_dict).
    """
    import random
    from procgen import random_name, get_backstory

    # Random name
    name = random_name()

    # Random background
    bg_key = random.choice(list(BACKGROUNDS.keys()))
    bg = BACKGROUNDS[bg_key]

    # Stats: 4d6 drop lowest for each of the 6 stats
    def roll_stat():
        rolls = [random.randint(1, 6) for _ in range(4)]
        return sum(sorted(rolls)[1:])  # drop lowest

    base_stats = {s: roll_stat() for s in BASE_STATS}

    # Apply background bonuses
    final_stats = dict(base_stats)
    for stat, bonus in bg.get("stat_bonus", {}).items():
        final_stats[stat] = final_stats.get(stat, 10) + bonus

    c = Character()
    c.name = name
    c.background = bg_key
    c.background_perk = bg["perk"]
    c.stats = final_stats
    c.credits = 50
    c.max_hp = 8 + ability_modifier(c.stats.get("CON", 10)) + 2
    c.max_hp = max(8, c.max_hp)
    c.hp = c.max_hp
    c.base_ac = 10
    c.weapon = get_starting_weapon()
    c.armor = get_starting_armor()

    # Get backstory and apply flavor gear
    backstory = get_backstory(bg_key)
    apply_backstory_gear(c, backstory)

    return c, backstory
