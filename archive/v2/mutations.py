"""Mutation system for CRAWL PROTOCOL."""
import random
from dataclasses import dataclass


@dataclass
class Mutation:
    name: str
    description: str
    category: str           # physical mental arcane technological corruptive
    positive_effect: str
    negative_effect: str
    rarity: str             # common uncommon rare
    # Gameplay modifiers (applied to character stats)
    hp_bonus: int = 0
    dex_penalty: int = 0
    init_bonus: int = 0
    init_penalty: int = 0
    melee_dmg_bonus: int = 0
    damage_reduction: int = 0     # chance-based in combat
    attack_bonus: int = 0
    attack_penalty: int = 0
    ac_bonus: int = 0
    ac_penalty: int = 0
    detect_bonus: int = 0
    heal_on_kill: bool = False
    damage_burst_used: bool = False   # for Black Vein Surge (once per rest)


MUTATION_CATALOG = [
    Mutation(
        "Reinforced Bones",
        "Your skeleton has calcified beyond normal limits.",
        "physical",
        "+10 max HP",
        "-1 DEX",
        "uncommon",
        hp_bonus=10, dex_penalty=1,
    ),
    Mutation(
        "Clawed Hands",
        "Your fingernails have become retractable bone claws.",
        "physical",
        "+2 melee damage",
        "Penalty to delicate trap disarm checks",
        "common",
        melee_dmg_bonus=2,
    ),
    Mutation(
        "Reactive Skin",
        "Your skin hardens instinctively under impact.",
        "physical",
        "Chance to reduce incoming damage by 2",
        "Vulnerability to anomaly effects",
        "uncommon",
        damage_reduction=2,
    ),
    Mutation(
        "Danger Sense",
        "A preternatural awareness of incoming violence.",
        "mental",
        "+2 initiative and +2 trap detection",
        "Occasional false warning",
        "common",
        init_bonus=2, detect_bonus=2,
    ),
    Mutation(
        "Split Focus",
        "Your mind tracks multiple threats simultaneously.",
        "mental",
        "+2 to perception and skill checks",
        "Chance to lose temporary buffs",
        "common",
        detect_bonus=2,
    ),
    Mutation(
        "Predatory Calm",
        "You become eerily relaxed when nearly dead.",
        "mental",
        "+3 attack when HP below 30%",
        "-1 to peaceful event outcomes",
        "uncommon",
        # handled specially in combat
    ),
    Mutation(
        "Unstable Spellblood",
        "Raw magic leaks through your veins.",
        "arcane",
        "+2 magic damage",
        "10% chance to take 1d4 damage when using magic features",
        "uncommon",
        attack_bonus=2,  # applied to magic attacks
    ),
    Mutation(
        "Curse Mark",
        "A sigil burned into your flesh by something ancient.",
        "corruptive",
        "Enemies sometimes suffer -1 to attacks",
        "Merchants charge 10% more",
        "rare",
    ),
    Mutation(
        "Spectral Limb",
        "One of your arms phases partially out of reality.",
        "arcane",
        "+1 attack and can interact with incorporeal objects",
        "10% chance to attract anomalies",
        "rare",
        attack_bonus=1,
    ),
    Mutation(
        "Cybernetic Eye",
        "A salvaged optical implant now occupies your left eye socket.",
        "technological",
        "+2 attack accuracy and inspection",
        "Vulnerable to static traps (+2 damage from static)",
        "uncommon",
        attack_bonus=2,
    ),
    Mutation(
        "Embedded Toolarm",
        "Micro-tools have fused with your forearm bones.",
        "technological",
        "+3 engineering/trap checks",
        "-1 CHA (you clank when you move)",
        "uncommon",
        detect_bonus=3,
    ),
    Mutation(
        "Reactive Plating",
        "Sub-dermal metal plates have grown under your skin.",
        "technological",
        "+2 AC",
        "-2 initiative",
        "uncommon",
        ac_bonus=2, init_penalty=2,
    ),
    Mutation(
        "Hunger Node",
        "A secondary digestive organ that processes violence.",
        "physical",
        "Heal 2 HP after each kill",
        "Short rests occasionally fail",
        "uncommon",
        heal_on_kill=True,
    ),
    Mutation(
        "Echo Parasite",
        "A psychic entity nesting in your auditory cortex.",
        "mental",
        "Occasional useful dungeon warning",
        "Occasional misleading warning",
        "rare",
    ),
    Mutation(
        "Black Vein Surge",
        "Dark ichor pulses through your veins once per rest.",
        "corruptive",
        "Once per rest: deal 3d6 bonus damage on one attack",
        "Take 1d6 damage after using the surge",
        "rare",
    ),
]


def get_random_mutation(category=None, rarity=None):
    pool = list(MUTATION_CATALOG)
    if category:
        pool = [m for m in pool if m.category == category] or pool
    if rarity:
        pool = [m for m in pool if m.rarity == rarity] or pool
    return random.choice(pool) if pool else None


def apply_mutation(mutation, character):
    """Apply mutation stat effects to a character. Returns True if applied."""
    # Check for duplicates
    for m in character.mutations:
        if m.name == mutation.name:
            print(f"  You already have: {mutation.name}")
            return False

    character.mutations.append(mutation)

    # Apply stat changes
    if mutation.hp_bonus:
        character.max_hp += mutation.hp_bonus
        character.hp = min(character.hp + mutation.hp_bonus, character.max_hp)
        print(f"  Max HP +{mutation.hp_bonus}")
    if mutation.dex_penalty:
        character.abilities["DEX"] = max(6, character.abilities["DEX"] - mutation.dex_penalty)
        print(f"  DEX -{mutation.dex_penalty}")
    if mutation.ac_bonus:
        character.base_ac += mutation.ac_bonus
        character.ac = character.base_ac
        print(f"  AC +{mutation.ac_bonus}")
    if mutation.ac_penalty:
        character.base_ac = max(8, character.base_ac - mutation.ac_penalty)
        character.ac = character.base_ac
        print(f"  AC -{mutation.ac_penalty}")

    from narrator import get_narrator
    get_narrator().say("mutation_gain")
    return True


def mutation_to_dict(m):
    return {
        "name": m.name,
        "category": m.category,
        "rarity": m.rarity,
        "damage_burst_used": m.damage_burst_used,
    }


def mutation_from_dict(d):
    name = d.get("name", "")
    for m in MUTATION_CATALOG:
        if m.name == name:
            import copy
            mut = copy.deepcopy(m)
            mut.damage_burst_used = d.get("damage_burst_used", False)
            return mut
    return None
