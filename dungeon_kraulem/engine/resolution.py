"""Resolution engine — rolls dice for validated actions."""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any

from ..ui.lang import t
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
    from .dice_labels import format_check as _fc
    result.fallback_description = _fc(
        aff_key, stat, raw, mod, total, dc, level,
        extras=[("tła", bonus)],
        prefix="",
    )
    # Prompt 3: pick a context-aware fail-forward template; both narrative
    # line AND additional effects come from it.
    if level in (PARTIAL, FAILURE, CRIT_FAILURE):
        outcome = _context_outcome(level, aff_key, validation_result, world)
        if outcome:
            txt = outcome.get("text")
            if txt:
                result.fallback_description += "\n  " + txt
            # Pull template effects in alongside the affordance-driven ones
            for eff in (outcome.get("effects") or []):
                result.effects.append(dict(eff))
            # P27.5 (P27-UX-19): removed the leaked [template=X] debug
            # tag from player-facing log. The internal key is still
            # available on `outcome["key"]` for tests/analytics; we just
            # don't append it to the displayed description anymore.

    # Affordance-driven effects (combat damage, hack-state change, etc.)
    result.effects.extend(_effects_for_level(level, aff_key, validation_result, world))
    return result


# ── Context builder for fail-forward picker (Prompt 03) ─────────────────────

def _context_outcome(level: str, aff_key: str, validation_result, world):
    """Build a context dict from world/room/entity/intent and ask the picker
    for an outcome template. Always safe — returns None on any failure."""
    try:
        from ..content import content_loader
    except Exception:
        return None

    ctx = _build_context(aff_key, validation_result, world)
    return content_loader.pick_fail_outcome(
        level if level != CRIT_FAILURE else "critical_failure",
        ctx,
    )


def _build_context(aff_key: str, validation_result, world) -> dict:
    floor = getattr(world, "current_floor", None)
    room  = floor.current_room() if floor else None

    room_tags = []
    visible_crawler = False
    visible_sponsor_cam = False
    entity_tags = []
    entity_types = []
    if room is not None:
        room_tags = list(getattr(room, "sensory_tags", []) or [])
        if room.actual_type:
            room_tags.append(room.actual_type)
        if room.safehouse_subtype:
            room_tags.extend(["safehouse", room.safehouse_subtype])
        for e in getattr(room, "entities", []) or []:
            entity_types.append(getattr(e, "entity_type", ""))
            entity_tags.extend(getattr(e, "tags", []) or [])
            etype = getattr(e, "entity_type", "")
            if etype == "crawler":
                visible_crawler = True
            if "camera" in (getattr(e, "tags", []) or []) or e.key == "sponsor_camera":
                visible_sponsor_cam = True

    # Target-specific tags
    targets = validation_result.matched_entities or []
    for t in targets:
        entity_tags.extend(getattr(t, "tags", []) or [])
        entity_types.append(getattr(t, "entity_type", ""))

    # Player tools
    tools = []
    try:
        for eid in world.character.inventory_ids:
            ent = world.entities.get(eid)
            if ent:
                tools.extend(getattr(ent, "tags", []) or [])
    except Exception:
        pass

    # Intent category (rough bucket)
    category = _affordance_category(aff_key)

    return {
        "room_tags": room_tags,
        "entity_tags": entity_tags,
        "entity_types": entity_types,
        "encounter_type": getattr(room, "encounter_key", "") if room else "",
        "safehouse_subtype": getattr(room, "safehouse_subtype", None) if room else None,
        "noise_level": getattr(room, "noise_level", 0) if room else 0,
        "available_exits": len(getattr(room, "exits", {})) if room else 0,
        "visible_crawler": visible_crawler,
        "visible_sponsor_cam": visible_sponsor_cam,
        "floor_objective": getattr(floor, "objective_key", "") if floor else "",
        "affordance_key": aff_key,
        "intent_category": category,
        "tools": tools,
    }


def _affordance_category(aff_key: str) -> str:
    table = {
        "attack": "combat", "shoot": "combat",
        "flee":   "combat_escape",
        "talk":   "social", "intimidate": "social", "bribe": "social",
        "sneak":  "stealth", "hide": "stealth",
        "hack":   "mechanical", "force": "mechanical", "lockpick": "mechanical",
        "repair": "mechanical", "use": "mechanical",
        "push_into": "environment", "throw_at": "environment", "lure": "environment",
        "rest_short": "safehouse", "rest_long": "safehouse",
        "look": "general", "inspect": "general", "search": "general",
        "listen": "general", "wait": "general",
        "perform": "social", "loot": "general", "craft": "mechanical",
    }
    return table.get(aff_key, "general")


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
            # Prompt 18: combat spectacle hooks. Crit hits feed audience
            # + the Sport / Kanał 7 / NovaChem sponsor tag system.
            if level == CRIT_SUCCESS:
                effects.append({"type":"add_audience","amount":3,
                                "source":"crit_hit","tag":"crit_hit"})
                effects.append({"type":"sponsor_tag","tag":"crit_success","weight":1})
            else:
                effects.append({"type":"add_audience","amount":1,
                                "source":"heavy_hit","tag":"heavy_attack_hit"})
        elif aff_key == "shoot" and primary is not None:
            dmg = random.randint(4, 10) + world.character.stat_mod("DEX")
            if level == CRIT_SUCCESS: dmg *= 2
            effects.append({"type":"damage_entity","entity_id":primary.entity_id,"amount":dmg})
            effects.append({"type":"add_noise","amount":5})
            effects.append({"type":"add_affinity","kind":"ranged","amount":1})
            if level == CRIT_SUCCESS:
                effects.append({"type":"add_audience","amount":3,
                                "source":"crit_hit","tag":"crit_hit"})
                effects.append({"type":"sponsor_tag","tag":"crit_success","weight":1})
            else:
                effects.append({"type":"add_audience","amount":1,
                                "source":"heavy_hit","tag":"heavy_attack_hit"})
        elif aff_key in ("push_into","throw_at","lure") and destination is not None:
            dmg = random.randint(6, 12)
            # Prompt 21: env-kill carries the destination's damage_type
            # (e.g. acid_pool -> acid + corroded; future env types just
            # set their damage_type field to plug in).
            env_dmg_type = getattr(destination, "damage_type",
                                   None) or "physical"
            effects.append({"type":"damage_entity",
                            "entity_id":primary.entity_id,
                            "amount":dmg,
                            "damage_type":env_dmg_type})
            effects.append({"type":"add_affinity","kind":"environment","amount":2})
            # Prompt 18: environment kills are the marquee sponsor moment.
            # Bump audience AND emit env_kill tag for Sport/Kanał 7.
            effects.append({"type":"add_audience",
                            "amount": aff.audience_effect if aff else 5,
                            "source":"env_kill","tag":"env_kill"})
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
            # Prompt 18: lockpicking is a Czarny Rynek love / Ministerstwo hate.
            effects.append({"type":"sponsor_tag","tag":"lockpicking","weight":1})
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
            # Prompt 20: if a scheduled encounter is incoming in this room,
            # a successful hide marks the player concealed so the arriver
            # search resolves narratively instead of starting combat.
            effects.append({"type":"world_flag",
                            "key":"hidden_for_encounter","value":True})
            effects.append({"type":"sponsor_tag","tag":"hide","weight":1})
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
