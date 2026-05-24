"""Narrator — sarcastic Syndicate broadcast voice."""
import random
from .lang import t


CATEGORIES = (
    "impossible_action", "clever_action", "env_kill", "cowardice", "hiding",
    "betrayal", "helping_crawler", "bathroom_use", "coffee_use",
    "class_offer", "species_offer", "time_warning", "deadline",
    "audience_rise", "audience_drop", "crit_success", "crit_failure",
    "return_safehouse_wounded", "stupid_attempt", "repeated_pattern",
    "first_floor_open", "rest_taken",
    # Prompt 06c: salvage / craft / deploy categories.
    "salvage_success", "salvage_partial", "salvage_fail",
    "salvage_critical_fail", "furniture_salvage", "tech_salvage",
    "bathroom_salvage", "safehouse_theft_attempt",
    "safehouse_theft_escalation", "sponsor_property_salvage",
    "corpse_loot", "corpse_strip", "corpse_harvest", "monster_harvest",
    "crawler_corpse_looted", "disgusting_but_useful",
    "everything_is_material", "craft_success", "craft_partial",
    "craft_fail", "craft_critical_fail", "absurd_craft_attempt",
    "clever_craft", "dangerous_craft", "unstable_item_created",
    "improvised_weapon_created", "improvised_trap_created",
    "improvised_tool_created", "repair_success", "reinforce_success",
    "deploy_trap_success", "deploy_trap_fail", "trap_self_trigger",
    "rare_material_found", "sponsor_component_found",
    "anomalous_material_found", "forbidden_material_harvested",
    "audience_likes_recycling", "audience_disgusted",
    "sponsor_files_complaint",
    # Prompt 07: memetic / belief-seed categories.
    "belief_seed_attempt", "belief_seed_success", "belief_seed_partial",
    "belief_seed_fail", "belief_seed_backlash", "belief_spreads",
    "belief_distorts", "machine_confusion", "crawler_gossip_shift",
    "sponsor_notices_propaganda", "absurd_idea_takes_root",
    # Prompt 07b — knowledge / clue-gated actions
    "clue_path_used", "false_lead_followed", "rumor_revealed_useful",
    # Prompt 07b follow-up — belief-driven encounter reactions
    "machine_talks_back", "rumor_echo", "belief_backfires",
    "sponsor_mocks_belief", "crawler_mentions_distorted_belief",
    "target_hesitates", "target_reinterprets_order", "target_demands_proof",
)


def say(category: str, **fmt) -> str:
    """Pick a random localized narrator line for a category."""
    # Find up to 6 variants per category. Keys are like narrator_{cat}_1..6
    candidates = []
    for i in range(1, 7):
        key = f"narrator_{category}_{i}"
        line = t(key, fallback="")
        if line:
            candidates.append(line)
    if not candidates:
        return ""
    chosen = random.choice(candidates)
    try:
        return chosen.format(**fmt)
    except (KeyError, IndexError):
        return chosen
