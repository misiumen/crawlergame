"""Species / race transformation offered on first entry to Floor 3."""
from dataclasses import dataclass
from typing import Dict
from .lang import t


@dataclass
class Species:
    key: str
    stat_bonus: Dict[str, int]
    hp_bonus: int = 0
    drawback_tag: str = ""
    passive: str = ""

    def name(self): return t(f"species_{self.key}_n", fallback=self.key)
    def desc(self): return t(f"species_{self.key}_d", fallback="")
    def drawback(self): return t(f"species_{self.key}_drawback", fallback="")


SPECIES_CATALOG = {
    "baseline_human":   Species("baseline_human",   {}, 0, "", "ordinary"),
    "enhanced_human":   Species("enhanced_human",   {"DEX":1,"CON":1}, 4, "biopsy_audits", "all_stats"),
    "tunnelborn":       Species("tunnelborn",       {"WIS":2}, 6, "sun_sensitive", "low_light_vision"),
    "scrapkin":         Species("scrapkin",         {"CON":2}, 8, "scary_to_npcs", "metal_skin"),
    "glassblood":       Species("glassblood",       {"INT":2,"DEX":1}, -4, "fragile", "see_through_walls"),
    "void_touched":     Species("void_touched",     {"INT":3}, 0, "audience_disturbed", "telepathy"),
    "fungal_host":      Species("fungal_host",      {"CON":2}, 6, "spore_signature", "regen"),
    "chimera":          Species("chimera",          {"STR":2,"DEX":1}, 8, "appearance_horror", "extra_limb"),
    "synthetic":        Species("synthetic",        {"INT":2,"DEX":1}, 4, "no_taste_no_smell", "poison_immune"),
    "half_dead":        Species("half_dead",        {"CON":1}, 4, "scares_animals", "necrotic_resist"),
}


def apply_species(world, species_key: str) -> bool:
    sp = SPECIES_CATALOG.get(species_key)
    if sp is None:
        return False
    ch = world.character
    ch.species_key = sp.key
    ch.species_picked_at_floor = world.floor_number
    for stat, bonus in sp.stat_bonus.items():
        ch.stats[stat] = ch.stats.get(stat, 10) + bonus
    if sp.hp_bonus:
        ch.max_hp += sp.hp_bonus
        ch.hp = min(ch.max_hp, ch.hp + max(0, sp.hp_bonus))
    return True
