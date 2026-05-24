"""Consequence engine — applies ResolutionResult.effects to WorldState."""
from typing import List, Dict, Any

from .lang import t


def apply(effects: List[Dict[str, Any]], world, time_system=None) -> List[str]:
    """Apply each effect and return list of log lines (already localized)."""
    lines: List[str] = []
    floor = world.current_floor
    room  = floor.current_room() if floor else None

    for eff in effects:
        kind = eff.get("type", "")
        if kind == "move_to_room":
            target = eff["room_id"]
            if floor and target in floor.rooms:
                floor.current_room_id = target
                floor.rooms[target].visited = True
                floor.discovered_room_ids.add(target)
                floor.known_room_ids.add(target)
                floor.rooms[target].last_visited_minute = floor.current_minute
                if time_system:
                    time_system.advance(world, eff.get("time_cost", 10))
                # First-enter line
                r = floor.rooms[target]
                if r.last_visited_minute == floor.current_minute:
                    lines.append(r.display_first_enter())

        elif kind == "look":
            if room:
                lines.append(room.display_look())
            if time_system:
                time_system.advance(world, eff.get("time_cost", 1))

        elif kind == "search":
            if room:
                room.searched_depth += 1
                lines.append(room.display_search() or
                             t("feedback_nothing_found", fallback="Nic ciekawego."))
            if time_system:
                time_system.advance(world, eff.get("time_cost", 30))

        elif kind == "listen":
            target = eff.get("room_id")
            target_room = floor.rooms.get(target) if floor else None
            if target_room is not None:
                target_room.scouted = True
                floor.known_room_ids.add(target)
                hint = target_room.display_public_hint()
                if not hint:
                    hint = t("feedback_silence", fallback="Słyszysz tylko własny oddech.")
                lines.append(hint)
            if time_system:
                time_system.advance(world, eff.get("time_cost", 5))

        elif kind == "wait":
            if time_system:
                time_system.advance(world, eff.get("time_cost", 15))
            lines.append(t("feedback_waited", fallback="Czekasz. Coś gdzieś tyka."))

        elif kind == "rest":
            mins = eff.get("minutes", 60)
            heal = max(1, mins // 30)
            world.character.heal(heal)
            if time_system:
                time_system.advance(world, mins)
            lines.append(t("feedback_rested", fallback=f"Odpoczynek: +{heal} HP."))

        elif kind == "damage_entity":
            eid = eff.get("entity_id"); amount = int(eff.get("amount", 0))
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                ent.hp = max(0, ent.hp - amount)
                if ent.hp <= 0 and ent.max_hp > 0:
                    lines.append(t("feedback_entity_down", fallback=f"{ent.display_name()} pada.",
                                   name=ent.display_name()))
                else:
                    lines.append(t("feedback_entity_hit",
                                   fallback=f"{ent.display_name()}: -{amount} HP.",
                                   name=ent.display_name(), amount=amount))

        elif kind == "damage_self":
            world.character.take_damage(int(eff.get("amount", 0)))
            lines.append(t("feedback_self_hurt", fallback="Coś poszło nie tak. Boli.",
                           amount=eff.get("amount",0)))

        elif kind == "heal_entity":
            eid = eff.get("entity_id"); amount = int(eff.get("amount", 0))
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                ent.hp = min(ent.max_hp, ent.hp + amount)

        elif kind == "add_condition":
            eid = eff.get("entity_id"); cond = eff.get("condition","")
            ent = _resolve_entity(world, room, eid)
            if ent is not None and cond not in ent.conditions:
                ent.conditions.append(cond)

        elif kind == "change_object_state":
            eid = eff.get("entity_id"); update = eff.get("state_update", {})
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                ent.state.update(update)
                # Doors specifically: opening / unlocking propagates to room.exits
                if "unlocked" in update and room is not None:
                    for label, ed in room.exits.items():
                        if ed.get("entity_id") == ent.entity_id:
                            ed["locked"] = False

        elif kind == "add_noise":
            if room:
                room.noise_level += int(eff.get("amount", 1))

        elif kind == "add_audience":
            world.character.audience_rating += int(eff.get("amount", 0))

        elif kind == "add_affinity":
            kind_id = eff.get("kind"); amt = int(eff.get("amount", 1))
            if kind_id and kind_id in world.character.affinity:
                world.character.affinity[kind_id] += amt

        elif kind == "change_relationship":
            eid = eff.get("entity_id"); amt = int(eff.get("amount", 0))
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                key = ent.key or str(ent.entity_id)
                world.character.relationships[key] = world.character.relationships.get(key, 0) + amt

        elif kind == "spend_credits":
            amt = int(eff.get("amount", 0))
            world.character.credits = max(0, world.character.credits - amt)

        elif kind == "add_credits":
            world.character.credits += int(eff.get("amount", 0))

        elif kind == "loot":
            eid = eff.get("entity_id")
            ent = _resolve_entity(world, room, eid)
            if ent is not None and ent.portable:
                if room is not None:
                    room.remove_entity(ent)
                ent.location_id = f"inventory:player"
                world.character.inventory_ids.append(ent.entity_id)
                lines.append(t("feedback_looted",
                               fallback=f"Zabierasz: {ent.display_name()}.",
                               name=ent.display_name()))
            if time_system:
                time_system.advance(world, eff.get("time_cost", 2))

        elif kind == "open":
            eid = eff.get("entity_id")
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                ent.state["open"] = True
                lines.append(t("feedback_opened",
                               fallback=f"Otwierasz: {ent.display_name()}.",
                               name=ent.display_name()))

        elif kind == "flee":
            if time_system:
                time_system.advance(world, eff.get("time_cost", 3))
            lines.append(t("feedback_fled", fallback="Wycofujesz się."))

        elif kind == "reveal_entity":
            eid = eff.get("entity_id")
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                ent.discovered = True; ent.visible = True

        elif kind == "trigger_alarm":
            world.character.audience_rating += 2
            if floor:
                floor.floor_alert_level = min(10, floor.floor_alert_level + 1 + eff.get("amount", 0))
            lines.append(t("feedback_alarm", fallback="Gdzieś brzęczy alarm."))

        elif kind == "add_journal":
            world.character.journal.setdefault(room.room_id if room else "_", []).append(eff.get("text",""))

    return lines


def _resolve_entity(world, room, entity_id):
    if entity_id is None or entity_id == -1:
        return None
    if room is not None:
        for e in room.entities:
            if e.entity_id == entity_id:
                return e
    return world.entities.get(entity_id)
