"""ActionIntent validator. Decides whether an action is possible."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Any

from .affordances import AFFORDANCE_CATALOG, fold
from .entity import Entity
from ..ui.lang import t


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
        # Prompt 03: ambiguous targets get a clarify response instead of a guess.
        candidates = _resolve_entities(room, intent.targets[0])
        if len(candidates) > 1:
            result.valid = False
            result.reason = "ambiguous_target"
            result.message_key = "feedback_ambiguous_target"
            result.fallback_message = (
                f"„{intent.targets[0]}” — może chodzi o jedno z: "
                + ", ".join(c.display_name() for c in candidates[:5])
                + ". Doprecyzuj."
            )
            result.possible_interpretations = [c.display_name() for c in candidates[:5]]
            return result
        matched = candidates[0] if candidates else None
    elif intent.intent in ("inspect","attack","talk","intimidate","bribe","loot",
                           "force","hack","lockpick","open","close","use",
                           "break"):
        # No explicit target — if the room has only one matching entity, use it.
        candidates = [e for e in room.visible_entities() if intent.intent in e.affordances]
        if len(candidates) == 1:
            matched = candidates[0]
        elif len(candidates) > 1:
            result.valid = False
            result.reason = "ambiguous_target"
            result.message_key = "feedback_ambiguous_target"
            result.fallback_message = (
                "Co dokładnie? "
                + ", ".join(c.display_name() for c in candidates[:5])
            )
            result.possible_interpretations = [c.display_name() for c in candidates[:5]]
            return result

    if matched is None and intent.intent in ("inspect","attack","talk","intimidate","bribe",
                                              "force","hack","lockpick","open","close","use",
                                              "push_into","throw_at","lure","loot","break"):
        result.valid = False
        result.reason = "no_target"
        result.message_key = "feedback_no_target"
        result.fallback_message = "Nie widzisz tu tego, czego szukasz."
        result.possible_interpretations = [e.display_name() for e in room.visible_entities()][:6]
        return result

    # Prompt 14: tag-driven affordance fallback. If the intent isn't listed
    # explicitly in the entity's affordances but the entity's tags imply it,
    # accept the action. This is the engine rule "if I can see it I can try
    # to do the sensible thing to it" without hand-editing every template.
    if matched is not None and intent.intent not in matched.affordances and intent.intent != "inspect":
        if not _tag_implies_affordance(matched, intent.intent):
            result.valid = False
            result.reason = "wrong_affordance"
            result.fallback_message = _explain_wrong_affordance(matched, intent.intent)
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
    """Find one visible entity matching the fragment, or None.
    Kept for back-compat; new callers should use _resolve_entities."""
    matches = _resolve_entities(room, fragment)
    return matches[0] if matches else None


def _resolve_entities(room, fragment: str) -> list:
    """Return ALL visible entities matching the fragment (ambiguity-aware).

    Prompt 14: when the player targets "drzwi" / "drzwiom" / "door" /
    "wyjście" and the room has visible exits, synthesize a lightweight
    door entity that represents the closest matching exit. This keeps
    "rozbij drzwi", "wyłam drzwi", "kopnij drzwi" working without
    requiring every template to seed a door entity manually.
    """
    if not fragment or room is None:
        return []
    f = fold(fragment)
    tokens = [t for t in re.split(r"[^a-z0-9]+", f) if len(t) >= 3]
    visible = room.visible_entities()
    matches = []

    # Direct full-name match first — exact match short-circuits to single hit
    for e in visible:
        if fold(e.display_name()) == f or fold(e.key) == f:
            return [e]

    # Token-level prefix match (Polish-friendly). Collect all matches.
    seen_ids = set()
    for e in visible:
        names = [fold(e.key.replace("_", " ")), fold(e.display_name())]
        hit = False
        for n in names:
            if hit: break
            n_tokens = [tt for tt in re.split(r"[^a-z0-9]+", n) if len(tt) >= 3]
            for tok in tokens:
                if hit: break
                stem = tok[:4]
                for nt in n_tokens:
                    if nt.startswith(stem) or tok.startswith(nt[:4]):
                        hit = True; break
        if hit and id(e) not in seen_ids:
            matches.append(e); seen_ids.add(id(e))

    # Door fallback: target words pointing at exits.
    door_words = ("drzwi", "door", "doors", "wyjscie", "wyjście",
                  "exit", "brama", "wejscie", "wejście")
    if not matches and any(w in f for w in door_words):
        synth = _synth_door_entity_for(room)
        if synth is not None:
            matches.append(synth)
    return matches


def _synth_door_entity_for(room):
    """Create a transient door entity that represents the room's most
    salient exit. The entity is attached to room.entities so save/load
    + state mutation work the same way as any other env object. Reuses
    an existing synthesized door if one is already there."""
    if room is None or not getattr(room, "exits", None):
        return None
    # Already synthesized? Reuse so state persists.
    for e in room.entities:
        if e.key == "_synth_door":
            return e
    # Pick the first non-hidden exit — prefer locked over open so destructive
    # interactions feel natural.
    chosen = None
    for label, ed in room.exits.items():
        if ed.get("hidden"):
            continue
        if ed.get("locked"):
            chosen = (label, ed); break
        if chosen is None:
            chosen = (label, ed)
    if chosen is None:
        return None
    label, ed = chosen
    locked = bool(ed.get("locked"))
    tags = ["door", "fixture", "metal", "salvageable"]
    if locked:
        tags.append("locked")
    aff = ["inspect", "force", "lockpick", "break", "open", "close"]
    door = Entity(
        key="_synth_door", entity_type="door",
        fallback_name=f"drzwi ({label})",
        fallback_desc=("Zamknięte drzwi." if locked else "Drzwi pokoju."),
        tags=tags, affordances=aff,
        location_id=room.room_id,
        portable=False,
    )
    door.state = {"label": label, "locked": locked}
    room.entities.append(door)
    return door


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


# ── Prompt 14: tag → affordance fallback ─────────────────────────────────
#
# Each intent lists tag sets that, if present on the entity, are sufficient
# to consider the action plausible. The validator falls back to this map
# when the entity's `affordances` list doesn't already mention the intent.
# Keep the lists narrow — every entry expands what the player can attempt
# universally across templates.
_TAG_AFFORDANCE_FALLBACK = {
    "break":   {"fragile", "glass", "ceramic", "destructible", "salvageable",
                "wood", "thin"},
    "salvage": {"salvageable", "machine", "panel", "electrical", "furniture",
                "fixture"},
    "strip":   {"salvageable", "furniture", "fixture", "corpse"},
    "harvest": {"organic", "corpse", "monster_remains",
                # Player phrasing "pozyskaj X z Y" generalizes beyond organics
                # — it's a synonym for "extract X material from Y source."
                # Anything salvageable accepts the extraction attempt; the
                # salvage handler then routes drops by table.
                "salvageable", "glass", "electrical", "metal"},
    "search":  {"container", "corpse", "drawer", "shelf"},
    "loot":    {"container", "corpse", "drawer", "shelf", "salvageable"},
    "open":    {"container", "door", "drawer"},
    "close":   {"container", "door", "drawer"},
    "force":   {"door", "container", "locked"},
    "hack":    {"terminal", "panel", "machine"},
    "lockpick":{"locked", "door", "container"},
    "use":     {"terminal", "machine", "container"},
    "throw_at":{"throwable", "fragile", "small"},
    "push_into":{"furniture", "heavy", "machine"},
}


def _tag_implies_affordance(entity, intent_key: str) -> bool:
    if entity is None:
        return False
    tags = set(entity.tags or [])
    needed = _TAG_AFFORDANCE_FALLBACK.get(intent_key)
    if not needed:
        return False
    return bool(tags & needed)


def _explain_wrong_affordance(entity, intent_key: str) -> str:
    """Build a useful Polish refusal that tells the player WHY the action
    won't land. Generic enough to cover any template + intent pair."""
    name = entity.display_name() if entity is not None else "?"
    # Indestructible structure (a wall, a sealed floor plate, etc.).
    tags = set(entity.tags or []) if entity is not None else set()
    if intent_key in ("break", "attack") and "structural" in tags:
        return (f"Próbujesz, ale „{name}” jest częścią konstrukcji lochu — "
                f"nie ustąpi pod takimi metodami.")
    if intent_key == "break":
        return f"Możesz w to uderzać, ale „{name}” nie wygląda na coś, co ustąpi bez narzędzi."
    if intent_key == "salvage":
        return f"„{name}” nie ma z czego ciągnąć surowców."
    if intent_key in ("harvest", "strip"):
        return f"„{name}” nie nadaje się do takiego pozyskiwania."
    if intent_key == "hack":
        return f"„{name}” nie reaguje na próby włamu."
    if intent_key in ("force", "lockpick"):
        return f"„{name}” nie wygląda jak coś, co da się sforsować ani otworzyć wytrychem."
    return f"„{name}” nie odpowiada na takie działanie."
