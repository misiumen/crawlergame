"""ActionIntent validator. Decides whether an action is possible."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Any

from .affordances import AFFORDANCE_CATALOG, fold
from .entity import Entity
from .lang import t


@dataclass
class ValidationResult:
    valid: bool = False
    reason: str = ""                    # short reason key, for logs
    message_key: str = ""               # i18n key for in-game feedback
    fallback_message: str = ""
    matched_entities: List[Entity] = field(default_factory=list)
    matched_destination: Optional[str] = None    # room_id
    matched_tool: Optional[Entity] = None
    matched_affordance_key: str = ""
    possible_interpretations: List[str] = field(default_factory=list)
    required_checks: List = field(default_factory=list)
    time_cost: int = 5
    risks: List[str] = field(default_factory=list)
    can_retry: bool = True
    starts_combat: bool = False
    causes_noise: int = 0

    def message(self) -> str:
        return t(self.message_key, fallback=self.fallback_message) if (self.message_key or self.fallback_message) else ""


def validate(intent, world) -> ValidationResult:
    """Validate an ActionIntent against world state."""
    result = ValidationResult()
    if intent is None or intent.intent in ("", "unknown"):
        result.valid = False
        result.reason = "no_intent"
        result.message_key = "feedback_no_intent"
        result.fallback_message = "Nie rozumiem, co chcesz zrobić."
        return result

    # Quick intents that don't need a target ---------------------------------
    no_target = {"look","search","wait","rest_short","rest_long","check_inventory",
                 "check_character","check_map","ask_rumor","save","help","numeric",
                 "flee"}
    if intent.intent in no_target:
        result.valid = True
        result.matched_affordance_key = intent.intent
        aff = AFFORDANCE_CATALOG.get(intent.intent)
        if aff:
            result.time_cost = aff.time_cost
        return result

    floor = world.current_floor
    room  = floor.current_room() if floor else None
    if room is None:
        result.valid = False
        result.reason = "no_room"
        result.fallback_message = "Nie jesteś nigdzie."
        return result

    # ── Movement validation ─────────────────────────────────────────────────
    if intent.intent == "move":
        target_name = intent.destination or (intent.targets[0] if intent.targets else "")
        target_name_f = fold(target_name)
        # Resolve exit label
        chosen_exit = None
        for label, exit_data in room.exits.items():
            if exit_data.get("hidden") and not _is_secret_revealed(room, label):
                continue
            if fold(label) == target_name_f or target_name_f in fold(label):
                chosen_exit = (label, exit_data); break
            target_room = floor.rooms.get(exit_data.get("target",""))
            if target_room and target_name_f and target_name_f in fold(target_room.display_short_title()):
                chosen_exit = (label, exit_data); break
        if chosen_exit is None:
            result.valid = False
            result.reason = "no_exit"
            result.message_key = "feedback_no_exit"
            result.fallback_message = f"Nie ma takiego wyjścia: „{target_name}”."
            return result
        label, exit_data = chosen_exit
        if exit_data.get("locked"):
            result.valid = False
            result.reason = "locked"
            result.fallback_message = f"„{label}” jest zamknięte."
            return result
        result.valid = True
        result.matched_affordance_key = "move"
        result.matched_destination = exit_data["target"]
        result.time_cost = 10
        return result

    # ── Listen at exit ──────────────────────────────────────────────────────
    if intent.intent == "listen":
        target_name = intent.destination or (intent.targets[0] if intent.targets else "")
        target_name_f = fold(target_name)
        for label, exit_data in room.exits.items():
            if fold(label) == target_name_f or (target_name_f and target_name_f in fold(label)):
                result.valid = True
                result.matched_affordance_key = "listen"
                result.matched_destination = exit_data["target"]
                result.time_cost = 5
                return result
        result.valid = False
        result.reason = "no_exit_to_listen"
        result.fallback_message = "Nie ma tu takiego przejścia, żeby nasłuchiwać."
        return result

    # ── Resolve target entity in room ────────────────────────────────────────
    aff = AFFORDANCE_CATALOG.get(intent.intent)
    if aff is None:
        result.valid = False
        result.reason = "no_affordance"
        result.fallback_message = "To brzmi nieprzekonująco."
        return result

    matched: Optional[Entity] = None
    if intent.targets:
        matched = _resolve_entity(room, intent.targets[0], world=world)
    elif intent.intent in ("inspect","attack","talk","intimidate","bribe","loot",
                           "force","hack","lockpick","open","close","use"):
        # No explicit target — if the room has only one matching entity, use it
        candidates = [e for e in room.visible_entities() if intent.intent in e.affordances]
        if len(candidates) == 1:
            matched = candidates[0]

    if matched is None and intent.intent in ("inspect","attack","talk","intimidate","bribe",
                                              "force","hack","lockpick","open","close","use",
                                              "push_into","throw_at","lure","loot"):
        result.valid = False
        result.reason = "no_target"
        result.message_key = "feedback_no_target"
        result.fallback_message = "Nie widzisz tu tego, czego szukasz."
        result.possible_interpretations = [e.display_name() for e in room.visible_entities()][:6]
        return result

    if matched is not None and intent.intent not in matched.affordances and intent.intent != "inspect":
        # Inspect is always allowed; other affordances must be supported
        result.valid = False
        result.reason = "wrong_affordance"
        result.fallback_message = f"„{matched.display_name()}” nie odpowiada na takie działanie."
        return result

    # Tool requirement ------------------------------------------------------
    if aff.required_tool_tags:
        tool_match = _find_inventory_item_with_tags(world, aff.required_tool_tags)
        if tool_match is None:
            result.valid = False
            result.reason = "no_tool"
            result.fallback_message = "Nie masz odpowiedniego narzędzia."
            return result
        result.matched_tool = tool_match

    # Destination for chain actions (push X into Y) -------------------------
    if intent.destination and intent.intent in ("push_into","throw_at","lure"):
        dest_ent = _resolve_entity(room, intent.destination, world=world)
        if dest_ent is None:
            result.valid = False
            result.reason = "no_destination"
            result.fallback_message = f"Nie widzisz tutaj „{intent.destination}”."
            return result
        # Stash destination on entity-2 by encoding it on the result
        result.matched_entities = [matched, dest_ent] if matched else [dest_ent]
    elif matched is not None:
        result.matched_entities = [matched]

    result.valid = True
    result.matched_affordance_key = intent.intent
    result.time_cost = aff.time_cost
    if aff.stat:
        result.required_checks.append({"stat": aff.stat, "dc": aff.base_dc})
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_entity(room, fragment: str, world=None) -> Optional[Entity]:
    """Find a visible entity in the room whose key/name matches the fragment."""
    if not fragment:
        return None
    f = fold(fragment)
    tokens = [t for t in re.split(r"[^a-z0-9]+", f) if len(t) >= 3]
    visible = room.visible_entities()

    # Direct full-name match first
    for e in visible:
        if fold(e.display_name()) == f or fold(e.key) == f:
            return e

    # Token-level prefix match (Polish-friendly)
    for e in visible:
        names = [fold(e.key.replace("_", " ")), fold(e.display_name())]
        for n in names:
            n_tokens = [tt for tt in re.split(r"[^a-z0-9]+", n) if len(tt) >= 3]
            for tok in tokens:
                stem = tok[:4]
                for nt in n_tokens:
                    if nt.startswith(stem) or tok.startswith(nt[:4]):
                        return e
    return None


def _find_inventory_item_with_tags(world, required_tags) -> Optional[Entity]:
    if not required_tags:
        return None
    for eid in world.character.inventory_ids:
        ent = world.entities.get(eid)
        if ent is None:
            continue
        if any(tag in ent.tags for tag in required_tags):
            return ent
    return None


def _is_secret_revealed(room, label) -> bool:
    return room.searched_depth > 0 or label in room.exits and not room.exits[label].get("hidden", False)
