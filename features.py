"""CRAWL PROTOCOL v2 - Class feature definitions."""
import copy
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Feature:
    name: str
    description: str
    effect_type: str       # damage_bonus, heal, condition, extra_attack, etc.
    effect_value: str      # dice string or integer or keyword
    cooldown_max: int = 0  # 0 = at-will, >0 = uses per rest
    cooldown_cur: int = 0
    tags: List[str] = field(default_factory=list)  # class keys it belongs to

    def is_available(self):
        return self.cooldown_max == 0 or self.cooldown_cur < self.cooldown_max

    def use(self):
        if self.cooldown_max > 0:
            self.cooldown_cur += 1

    def tick_cooldown(self):
        pass

    def restore(self):
        self.cooldown_cur = 0

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "effect_type": self.effect_type,
            "effect_value": self.effect_value,
            "cooldown_max": self.cooldown_max,
            "cooldown_cur": self.cooldown_cur,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            description=d["description"],
            effect_type=d["effect_type"],
            effect_value=d["effect_value"],
            cooldown_max=d.get("cooldown_max", 0),
            cooldown_cur=d.get("cooldown_cur", 0),
            tags=d.get("tags", []),
        )


# ── Feature catalog ────────────────────────────────────────────────────────────
# effect_type keys used in combat.py:
#   damage_bonus  - add effect_value dice to attack damage
#   heal          - restore HP (effect_value dice or int)
#   condition     - inflict condition on enemy (effect_value = condition name)
#   extra_attack  - make extra attack (effect_value = damage dice)
#   shield        - grant temporary AC (effect_value = AC amount, duration)
#   aoe           - hit all enemies (effect_value = dice)
#   summon        - create ally
#   utility       - non-combat or context-sensitive

FEATURE_CATALOG = {
    # Warrior
    "power_strike": Feature(
        "Power Strike", "Deal an extra 1d8 on next attack.",
        "damage_bonus", "1d8", cooldown_max=2, tags=["warrior"]),
    "second_wind": Feature(
        "Second Wind", "Recover 1d10+level HP.",
        "heal", "1d10", cooldown_max=1, tags=["warrior"]),
    "cleave": Feature(
        "Cleave", "Attack hits all adjacent enemies for half damage.",
        "aoe", "1d6", cooldown_max=2, tags=["warrior"]),
    "rally": Feature(
        "Rally", "Grant +2 AC for 3 rounds.",
        "shield", "2", cooldown_max=1, tags=["warrior"]),
    "war_cry": Feature(
        "War Cry", "Intimidate - enemy has -2 to attack for 2 rounds.",
        "condition", "weakened", cooldown_max=2, tags=["warrior"]),

    # Rogue
    "sneak_attack": Feature(
        "Sneak Attack", "Extra 2d6 damage when enemy is unaware or flanked.",
        "damage_bonus", "2d6", cooldown_max=0, tags=["rogue"]),
    "evasion": Feature(
        "Evasion", "Avoid all damage on successful DEX save.",
        "shield", "evasion", cooldown_max=1, tags=["rogue"]),
    "smoke_dash": Feature(
        "Smoke Dash", "Escape combat without a check.",
        "utility", "free_flee", cooldown_max=1, tags=["rogue"]),
    "expose": Feature(
        "Expose Weakness", "Target takes +1d4 from all sources for 2 rounds.",
        "condition", "exposed", cooldown_max=2, tags=["rogue"]),
    "cheap_shot": Feature(
        "Cheap Shot", "Stun enemy for 1 round (CON save DC 14).",
        "condition", "stunned", cooldown_max=2, tags=["rogue"]),

    # Ranger
    "aimed_shot": Feature(
        "Aimed Shot", "Extra 1d10 ranged damage.",
        "damage_bonus", "1d10", cooldown_max=2, tags=["ranger"]),
    "hunters_mark": Feature(
        "Hunter's Mark", "Mark target; +1d6 on all attacks vs them.",
        "condition", "marked", cooldown_max=2, tags=["ranger"]),
    "trap_mastery": Feature(
        "Trap Mastery", "+5 to disarm trap checks.",
        "utility", "trap_bonus_5", cooldown_max=0, tags=["ranger"]),
    "volley": Feature(
        "Volley", "Hit all enemies for 1d6 ranged damage.",
        "aoe", "1d6", cooldown_max=2, tags=["ranger"]),
    "camouflage": Feature(
        "Camouflage", "Avoid one combat encounter per floor.",
        "utility", "skip_encounter", cooldown_max=1, tags=["ranger"]),

    # Mage
    "fireball": Feature(
        "Fireball", "2d8 fire damage to all enemies.",
        "aoe", "2d8", cooldown_max=2, tags=["mage"]),
    "magic_missile": Feature(
        "Magic Missile", "1d4+1 force damage, always hits.",
        "damage_bonus", "1d4", cooldown_max=0, tags=["mage"]),
    "arcane_shield": Feature(
        "Arcane Shield", "+4 AC for 2 rounds.",
        "shield", "4", cooldown_max=2, tags=["mage"]),
    "slow": Feature(
        "Slow", "Enemy has -3 to initiative and attack for 2 rounds.",
        "condition", "slowed", cooldown_max=2, tags=["mage"]),
    "telekinesis": Feature(
        "Telekinesis", "Free skill check with INT on any physical action.",
        "utility", "int_assist", cooldown_max=1, tags=["mage"]),

    # Cleric
    "divine_smite": Feature(
        "Divine Smite", "Extra 2d8 radiant damage.",
        "damage_bonus", "2d8", cooldown_max=2, tags=["cleric"]),
    "heal_prayer": Feature(
        "Healing Prayer", "Restore 2d8+level HP.",
        "heal", "2d8", cooldown_max=2, tags=["cleric"]),
    "holy_ward": Feature(
        "Holy Ward", "+3 AC and immune to conditions for 2 rounds.",
        "shield", "3", cooldown_max=1, tags=["cleric"]),
    "turn_enemy": Feature(
        "Turn Enemy", "Undead/demon enemy flees for 1 round.",
        "condition", "fleeing", cooldown_max=2, tags=["cleric"]),
    "mass_heal": Feature(
        "Mass Heal", "Restore 1d6 HP (can use outside combat).",
        "heal", "1d6", cooldown_max=3, tags=["cleric"]),

    # Warlock
    "eldritch_blast": Feature(
        "Eldritch Blast", "1d10 force damage, always available.",
        "damage_bonus", "1d10", cooldown_max=0, tags=["warlock"]),
    "hex": Feature(
        "Hex", "Target takes extra 1d6 necrotic per round for 3 rounds.",
        "condition", "hexed", cooldown_max=2, tags=["warlock"]),
    "dark_pact": Feature(
        "Dark Pact", "Trade 5 HP for 3d8 damage.",
        "damage_bonus", "3d8", cooldown_max=1, tags=["warlock"]),
    "shadow_step": Feature(
        "Shadow Step", "Teleport behind enemy; +2d6 sneak damage.",
        "damage_bonus", "2d6", cooldown_max=2, tags=["warlock"]),
    "life_drain": Feature(
        "Life Drain", "Deal 1d8 necrotic, heal for half.",
        "damage_bonus", "1d8", cooldown_max=2, tags=["warlock"]),

    # Engineer
    "deploy_turret": Feature(
        "Deploy Turret", "Turret fires 1d6 each enemy turn for 3 rounds.",
        "summon", "turret_1d6_3", cooldown_max=1, tags=["engineer"]),
    "emp_pulse": Feature(
        "EMP Pulse", "Stun mechanical enemies 2 rounds; 1d6 to all.",
        "aoe", "1d6", cooldown_max=2, tags=["engineer"]),
    "shield_drone": Feature(
        "Shield Drone", "+3 AC for 3 rounds.",
        "shield", "3", cooldown_max=2, tags=["engineer"]),
    "overclock": Feature(
        "Overclock", "Take 2 attacks this round.",
        "extra_attack", "weapon", cooldown_max=2, tags=["engineer"]),
    "jury_rig": Feature(
        "Jury-Rig", "Craft a one-use item from scrap (heal 1d6 or +1d4 damage).",
        "utility", "craft_item", cooldown_max=2, tags=["engineer"]),

    # Psion
    "mind_blast": Feature(
        "Mind Blast", "2d6 psychic damage, INT save DC 13 or stunned.",
        "damage_bonus", "2d6", cooldown_max=2, tags=["psion"]),
    "telekinetic_throw": Feature(
        "Telekinetic Throw", "1d8 damage + enemy loses next action.",
        "damage_bonus", "1d8", cooldown_max=2, tags=["psion"]),
    "precognition": Feature(
        "Precognition", "+4 AC until next turn.",
        "shield", "4", cooldown_max=2, tags=["psion"]),
    "psychic_link": Feature(
        "Psychic Link", "Know enemy's max HP, AC, and resistances.",
        "utility", "enemy_scan", cooldown_max=0, tags=["psion"]),
    "dominate": Feature(
        "Dominate", "Enemy skips turn (WIS save DC 15).",
        "condition", "dominated", cooldown_max=1, tags=["psion"]),

    # Hybrid / specialization extras
    "battlemage_surge": Feature(
        "Battlemage Surge", "Use spell slot to power melee strike: +3d6.",
        "damage_bonus", "3d6", cooldown_max=2, tags=["warrior", "mage"]),
    "saboteur_bomb": Feature(
        "Saboteur Bomb", "Plant explosive: 3d8 AoE next round.",
        "aoe", "3d8", cooldown_max=1, tags=["rogue", "engineer"]),
    "heretic_nova": Feature(
        "Heretic Nova", "Radiant+necrotic burst: 2d10 to all.",
        "aoe", "2d10", cooldown_max=1, tags=["cleric", "warlock"]),
    "seer_volley": Feature(
        "Seer Volley", "Three arrows with Hunter's Mark bonus each.",
        "extra_attack", "1d6", cooldown_max=2, tags=["ranger", "psion"]),
    "guardian_stance": Feature(
        "Guardian Stance", "+5 AC and allies take 50% reduced damage.",
        "shield", "5", cooldown_max=1, tags=["warrior", "cleric"]),
    "inventor_field": Feature(
        "Inventor Field", "Turret + Arcane Shield simultaneously.",
        "utility", "combo_field", cooldown_max=1, tags=["mage", "engineer"]),
}


def get_feature(name):
    f = FEATURE_CATALOG.get(name)
    return copy.deepcopy(f) if f else None


def features_for_class(class_key, count=3):
    """Return `count` fresh Feature copies for a class key."""
    pool = [copy.deepcopy(f) for f in FEATURE_CATALOG.values()
            if class_key in (f.tags or [])]
    import random
    random.shuffle(pool)
    return pool[:count]


def feature_to_dict(f):
    return f.to_dict()


def feature_from_dict(d):
    return Feature.from_dict(d)
