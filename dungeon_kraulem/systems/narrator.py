"""Narrator — sarcastic Syndicate broadcast voice.

The static line table below is the canonical source. When the narrator
LLM role is enabled and reachable, `say()` may ask the model to rephrase
the chosen static line for a fresher delivery — but the static line is
always available as the fallback and the LLM never introduces new
mechanical content.
"""
import random
from ..ui.lang import t


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
    """Pick a random localized narrator line for a category.

    If the narrator LLM role is enabled and its model is installed, the
    chosen static line is passed to the model as a "rephrase this in the
    same tone, one short sentence" prompt. The model output is validated
    (length, no English leakage when running in PL) and replaces the
    static line. On ANY failure, the static line is returned unchanged.
    """
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
        chosen = chosen.format(**fmt)
    except (KeyError, IndexError):
        pass

    # Prompt 13: optional LLM rephrase. Only fires for "atmospheric"
    # categories — narrator hooks that benefit from variety. Mechanical
    # markers (e.g. "deadline", "first_floor_open") stay static so we
    # don't accidentally drift important wording.
    if category in _LLM_REPHRASE_CATEGORIES:
        chosen = _maybe_rephrase(chosen, category)
    return chosen


# Categories worth rephrasing. Anything not in this set stays purely
# static. Keep the list conservative — every category here costs one
# LLM round-trip when the narrator role is on.
_LLM_REPHRASE_CATEGORIES = frozenset((
    "salvage_success", "furniture_salvage", "tech_salvage", "bathroom_salvage",
    "corpse_harvest", "monster_harvest", "rare_material_found",
    "craft_success", "craft_partial", "craft_fail", "craft_critical_fail",
    "absurd_craft_attempt", "clever_craft", "dangerous_craft",
    "unstable_item_created", "deploy_trap_success", "trap_self_trigger",
    "belief_seed_success", "belief_seed_backlash", "belief_spreads",
    "machine_confusion", "machine_talks_back", "rumor_echo",
    "sponsor_notices_propaganda", "sponsor_mocks_belief", "audience_disgusted",
    "audience_likes_recycling", "absurd_idea_takes_root",
))


def _maybe_rephrase(line: str, category: str) -> str:
    """Run a guarded rephrase through the narrator role. Falls back to
    the input line on any error."""
    if not line:
        return line
    try:
        from ..llm import llm_roles
        if not llm_roles.is_role_available(llm_roles.ROLE_NARRATOR):
            return line
        prompt = (
            "Jesteś narratorem sarkastycznej, korporacyjnej transmisji w "
            "dungeon crawlerze. Przepisz poniższe zdanie jednym krótkim "
            "polskim zdaniem, zachowując ten sam ton i sens. Bez nawiasów, "
            "bez wyjaśnień, bez angielskich słów. Zwróć tylko nową wersję.\n\n"
            f"Zdanie: {line}\n"
            f"Kategoria (kontekst): {category}\n"
            "Nowa wersja:"
        )

        def _validate(text: str) -> bool:
            if not text or len(text) > 220:
                return False
            # Reject obvious English leakage. The model is allowed to use
            # technical loanwords but should not produce whole English
            # phrases.
            lowered = text.lower()
            english_tells = (" the ", " and ", " of ", " with ", "you ", " is ")
            for tell in english_tells:
                if tell in f" {lowered} ":
                    return False
            return True

        return llm_roles.enrich_text(
            role=llm_roles.ROLE_NARRATOR,
            prompt=prompt, fallback=line,
            validator=_validate,
        )
    except Exception:
        return line
