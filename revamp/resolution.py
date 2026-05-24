"""Resolution engine — rolls dice for validated actions."""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .lang import t
from .affordances import AFFORDANCE_CATALOG


# Result levels
CRIT_SUCCESS = "critical_success"
SUCCESS      = "success"
PARTIAL      = "partial_success"
FAILURE      = "failure"
CRIT_FAILURE = "critical_failure"


@dataclass
class ResolutionResult:
    level: str = SUCCESS
    raw_roll: int = 0
    total: int = 0
    dc: int = 0
    description_key: str = ""
    fallback_description: str = ""
    effects: List[Dict[str, Any]] = field(default_factory=list)

    def line(self) -> str:
        return t(self.description_key, fallback=self.fallback_description) if (self.description_key or self.fallback_description) else ""


def resolve(validation_result, world) -> ResolutionResult:
    """Resolve a validated action and return its mechanical result."""
    if not validation_result.valid:
        # Validator should already have explained why
        return ResolutionResult(level=FAILURE,
                                fallback_description=validation_result.message())

    aff_key = validation_result.matched_affordance_key
    aff = AFFORDANCE_CATALOG.get(aff_key)

    # No-roll actions ----------------------------------------------------------
    if not validation_result.required_checks:
        return ResolutionResult(level=SUCCESS, effects=_no_roll_effects(aff_key, validation_result))

    # Run the first required check (most actions have just one)
    check = validation_result.required_checks[0]
    stat = check.get("stat", "STR")
    dc   = check.get("dc", 10)
    raw  = random.randint(1, 20)
    mod  = world.character.stat_mod(stat)
    bonus = _background_bonus(world.character, aff_key)
    total = raw + mod + bonus

    crit_success = raw == 20
    crit_failure = raw == 1

    if crit_success:
        level = CRIT_SUCCESS
    elif crit_failure:
        level = CRIT_FAILURE
    elif total >= dc + 5:
        level = CRIT_SUCCESS if total >= dc + 8 else SUCCESS
    elif total >= dc:
        level = SUCCESS
    elif total >= dc - 3:
        level = PARTIAL
    else:
        level = FAILURE

    result = ResolutionResult(level=level, raw_roll=raw, total=total, dc=dc)
    result.fallback_description = (
        f"[{aff_key}] d20({raw}) + {stat}({mod:+d}) + tła({bonus:+d}) = {total} vs DC {dc} → {level}"
    )
    result.effects = _effects_for_level(level, aff_key, validation_result, world)
    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _background_bonus(character, aff_key: str) -> int:
    """Tiny situational bonus based on background."""
    bg = character.background
    table = {
        "soldier":      {"attack":1,"intimidate":1,"shoot":1},
        "mechanic":     {"hack":1,"repair":2,"craft":1,"force":1},
        "nurse":        {"talk":1,"use":1},
        "cook":         {"craft":1,"intimidate":1,"talk":1},
        "security_guard":{"attack":1,"intimidate":1,"force":1},
        "courier":      {"sneak":1,"flee":1,"search":1},
        "student":      {"hack":1,"inspect":1,"search":1},
        "streamer":     {"perform":2,"talk":1,"bribe":1},
        "unemployed_hustler":{"bribe":1,"lockpick":1,"talk":1},
        "janitor":      {"craft":1,"search":1,"use":1,"force":1},
        "paramedic":    {"use":1,"talk":1,"search":1},
        "office_worker":{"hack":1,"talk":1,"inspect":1},
    }
    return table.get(bg, {}).get(aff_key, 0)


def _no_roll_effects(aff_key: str, validation):
    """Effects that don't require a roll (look, search, move, talk-open)."""
    effects = []
    if aff_key == "move" and validation.matched_destination:
        effects.append({"type": "move_to_room", "room_id": validation.matched_destination,
                        "time_cost": 10})
    elif aff_key == "look":
        effects.append({"type": "look", "time_cost": 1})
    elif aff_key == "search":
        effects.append({"type": "search", "time_cost": 30})
    elif aff_key == "wait":
        effects.append({"type": "wait", "time_cost": 15})
    elif aff_key == "rest_short":
        effects.append({"type": "rest", "minutes": 60})
    elif aff_key == "rest_long":
        effects.append({"type": "rest", "minutes": 360})
    elif aff_key == "listen":
        effects.append({"type": "listen", "room_id": validation.matched_destination,
                        "time_cost": 5})
    elif aff_key == "loot":
        if validation.matched_entities:
            effects.append({"type": "loot", "entity_id": validation.matched_entities[0].entity_id,
                            "time_cost": 2})
    elif aff_key == "open":
        if validation.matched_entities:
            effects.append({"type": "open", "entity_id": validation.matched_entities[0].entity_id,
                            "time_cost": 2})
    elif aff_key == "flee":
        effects.append({"type": "flee", "time_cost": 3})
    return effects


def _effects_for_level(level, aff_key, validation, world):
    """Convert resolution level + affordance into world-state effects."""
    effects = []
    aff = AFFORDANCE_CATALOG.get(aff_key)
    targets = validation.matched_entities
    destination = validation.matched_entities[1] if len(targets) > 1 else None
    primary = targets[0] if targets else None

    if level in (CRIT_SUCCESS, SUCCESS):
        # Affordance-specific success outcomes
        if aff_key == "attack" and primary is not None:
            dmg = random.randint(3, 8) + world.character.stat_mod("STR")
            if level == CRIT_SUCCESS: dmg *= 2
            effects.append({"type":"damage_entity","entity_id":primary.entity_id,"amount":dmg})
            effects.append({"type":"add_noise","amount":3})
            effects.append({"type":"add_affinity","kind":"melee","amount":1})
        elif aff_key == "shoot" and primary is not None:
            dmg = random.randint(4, 10) + world.character.stat_mod("DEX")
            if level == CRIT_SUCCESS: dmg *= 2
            effects.append({"type":"damage_entity","entity_id":primary.entity_id,"amount":dmg})
            effects.append({"type":"add_noise","amount":5})
            effects.append({"type":"add_affinity","kind":"ranged","amount":1})
        elif aff_key in ("push_into","throw_at","lure") and destination is not None:
            dmg = random.randint(6, 12)
            effects.append({"type":"damage_entity","entity_id":primary.entity_id,"amount":dmg})
            effects.append({"type":"add_affinity","kind":"environment","amount":2})
            effects.append({"type":"add_audience","amount":aff.audience_effect if aff else 5})
        elif aff_key == "hack" and primary is not None:
            effects.append({"type":"change_object_state","entity_id":primary.entity_id,
                            "state_update":{"hacked":True}})
            effects.append({"type":"add_affinity","kind":"tech","amount":2})
        elif aff_key == "force" and primary is not None:
            effects.append({"type":"change_object_state","entity_id":primary.entity_id,
                            "state_update":{"broken_open":True}})
            effects.append({"type":"add_noise","amount":4})
        elif aff_key == "lockpick" and primary is not None:
            effects.append({"type":"change_object_state","entity_id":primary.entity_id,
                            "state_update":{"unlocked":True}})
            effects.append({"type":"add_affinity","kind":"stealth","amount":1})
        elif aff_key == "talk" and primary is not None:
            effects.append({"type":"change_relationship","entity_id":primary.entity_id,"amount":1})
            effects.append({"type":"add_affinity","kind":"diplomacy","amount":1})
        elif aff_key == "intimidate" and primary is not None:
            effects.append({"type":"add_condition","entity_id":primary.entity_id,
                            "condition":"shaken"})
            effects.append({"type":"add_affinity","kind":"showmanship","amount":1})
        elif aff_key == "bribe" and primary is not None:
            effects.append({"type":"change_relationship","entity_id":primary.entity_id,"amount":2})
            effects.append({"type":"spend_credits","amount":20})
        elif aff_key == "sneak":
            effects.append({"type":"add_condition","entity_id":world.character_id_hint(),
                            "condition":"sneaking"} if hasattr(world,"character_id_hint") else
                            {"type":"add_affinity","kind":"stealth","amount":1})
        elif aff_key == "hide":
            effects.append({"type":"add_affinity","kind":"stealth","amount":1})
        elif aff_key == "craft":
            effects.append({"type":"add_affinity","kind":"crafting","amount":1})
        elif aff_key == "repair":
            effects.append({"type":"add_affinity","kind":"tech","amount":1})
        elif aff_key == "perform":
            effects.append({"type":"add_audience","amount":15})
            effects.append({"type":"add_affinity","kind":"showmanship","amount":2})

    elif level == PARTIAL:
        # Partial: still affects state but with a cost or twist
        if primary is not None and aff_key in ("attack","shoot","push_into","throw_at"):
            effects.append({"type":"damage_entity","entity_id":primary.entity_id,
                            "amount":random.randint(1,4)})
            effects.append({"type":"add_noise","amount":2})
            effects.append({"type":"add_condition","entity_id":-1,"condition":"prone"})
        elif aff_key == "hack" and primary is not None:
            effects.append({"type":"change_object_state","entity_id":primary.entity_id,
                            "state_update":{"hacked":True}})
            effects.append({"type":"trigger_alarm","amount":1})

    elif level in (FAILURE, CRIT_FAILURE):
        # Fail consequences
        if aff_key == "attack" and primary is not None:
            effects.append({"type":"add_noise","amount":2})
        elif aff_key in ("force","hack","lockpick"):
            effects.append({"type":"trigger_alarm","amount":1 if level==CRIT_FAILURE else 0})
        if level == CRIT_FAILURE:
            effects.append({"type":"damage_self","amount":random.randint(1,3)})

    return effects
