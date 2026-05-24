"""Character class definitions for CRAWL PROTOCOL."""
from dataclasses import dataclass, field
from typing import List
from features import get_feature


@dataclass
class ClassDef:
    name: str
    role: str
    primary_abilities: List[str]
    base_hp: int            # base HP at level 1 (before CON mod)
    hp_per_level: int       # base HP gain per level (before CON mod)
    starting_ac: int
    starting_weapon: str
    feature_names: List[str]
    specialization_feature: str


# Default score array (assigned by class priority)
_DEFAULT_ARRAY = [16, 14, 13, 12, 10, 8]
_ALL_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


CLASS_DEFS = {
    "warrior": ClassDef(
        name="Warrior",
        role="Durable melee fighter",
        primary_abilities=["STR", "CON"],
        base_hp=14,
        hp_per_level=8,
        starting_ac=15,
        starting_weapon="Rusted Blade",
        feature_names=["Power Attack", "Guard", "Second Wind"],
        specialization_feature="Weapon Master",
    ),
    "rogue": ClassDef(
        name="Rogue",
        role="Evasive precision attacker",
        primary_abilities=["DEX", "INT"],
        base_hp=10,
        hp_per_level=6,
        starting_ac=14,
        starting_weapon="Survival Knife",
        feature_names=["Sneak Attack", "Dodge", "Quick Hands"],
        specialization_feature="Shadow Step",
    ),
    "ranger": ClassDef(
        name="Ranger",
        role="Ranged combat and survival",
        primary_abilities=["DEX", "WIS"],
        base_hp=11,
        hp_per_level=7,
        starting_ac=14,
        starting_weapon="Crude Bow",
        feature_names=["Aimed Shot", "Track", "Field Medicine"],
        specialization_feature="Hunter's Mark",
    ),
    "mage": ClassDef(
        name="Mage",
        role="Offensive and utility caster",
        primary_abilities=["INT"],
        base_hp=7,
        hp_per_level=4,
        starting_ac=11,
        starting_weapon="Arcane Rod",
        feature_names=["Arcane Bolt", "Shield", "Detect Anomaly"],
        specialization_feature="Arcane Mastery",
    ),
    "cleric": ClassDef(
        name="Cleric",
        role="Support, healing, defense",
        primary_abilities=["WIS"],
        base_hp=10,
        hp_per_level=6,
        starting_ac=14,
        starting_weapon="Shock Baton",
        feature_names=["Heal", "Bless", "Smite"],
        specialization_feature="Divine Grace",
    ),
    "warlock": ClassDef(
        name="Warlock",
        role="Risky charisma caster",
        primary_abilities=["CHA", "CON"],
        base_hp=9,
        hp_per_level=5,
        starting_ac=12,
        starting_weapon="Arcane Rod",
        feature_names=["Eldritch Bolt", "Hex", "Dark Bargain"],
        specialization_feature="Pact of Torment",
    ),
    "engineer": ClassDef(
        name="Engineer",
        role="Gadgets, traps, repairs",
        primary_abilities=["INT", "DEX"],
        base_hp=10,
        hp_per_level=6,
        starting_ac=13,
        starting_weapon="Spark Pistol",
        feature_names=["Deploy Trap", "Repair", "Overcharge"],
        specialization_feature="Master Tinker",
    ),
    "psion": ClassDef(
        name="Psion",
        role="Mental powers, control, perception",
        primary_abilities=["WIS", "INT"],
        base_hp=8,
        hp_per_level=5,
        starting_ac=12,
        starting_weapon="Glass Dagger",
        feature_names=["Mind Spike", "Push", "Read Intent"],
        specialization_feature="Mind Fortress",
    ),
}


def auto_assign_abilities(class_key):
    """
    Assign the default score array to a class, giving the highest scores
    to primary abilities first.
    """
    cls = CLASS_DEFS.get(class_key.lower())
    if not cls:
        return {s: 10 for s in _ALL_STATS}

    remaining_scores = list(_DEFAULT_ARRAY)
    assignments = {}

    # Assign highest scores to primary abilities
    for ability in cls.primary_abilities:
        if remaining_scores:
            assignments[ability] = remaining_scores.pop(0)

    # Fill remaining in order STR DEX CON INT WIS CHA, skipping already assigned
    for stat in _ALL_STATS:
        if stat not in assignments and remaining_scores:
            assignments[stat] = remaining_scores.pop(0)

    # Any leftover
    for stat in _ALL_STATS:
        if stat not in assignments:
            assignments[stat] = 8

    return assignments


def get_class(class_key):
    return CLASS_DEFS.get(class_key.lower())


def get_class_features(class_key):
    """Return fresh Feature objects for a class."""
    cls = CLASS_DEFS.get(class_key.lower())
    if not cls:
        return []
    return [f for f in (get_feature(n) for n in cls.feature_names) if f]


def display_classes():
    print("\n" + "=" * 60)
    print("  AVAILABLE CLASSES")
    print("=" * 60)
    keys = list(CLASS_DEFS.keys())
    for i, key in enumerate(keys, 1):
        cls = CLASS_DEFS[key]
        print(f"\n  [{i}] {cls.name}")
        print(f"      Role: {cls.role}")
        print(f"      Primary: {', '.join(cls.primary_abilities)}")
        print(f"      Starting HP: {cls.base_hp} + CON mod")
        print(f"      Starting AC: {cls.starting_ac}")
    print()
