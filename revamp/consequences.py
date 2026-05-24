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
                r = floor.rooms[target]
                # Detect first-ever visit BEFORE we mutate state
                first_visit = not r.visited
                floor.current_room_id = target
                r.visited = True
                floor.discovered_room_ids.add(target)
                floor.known_room_ids.add(target)
                if time_system:
                    time_system.advance(world, eff.get("time_cost", 10))
                r.last_visited_minute = floor.current_minute

                if first_visit:
                    lines.append(r.display_first_enter())
                    # Prompt 1: layer a safehouse template entry-description
                    if r.safehouse_subtype:
                        try:
                            from . import content_loader
                            extra = content_loader.safehouse_entry_description(r.safehouse_subtype)
                            if extra:
                                lines.append(extra)
                        except Exception:
                            pass
                    # Prompt 1: encounter-template intro (combat rooms)
                    if r.encounter_intro_fallback:
                        lines.append(r.encounter_intro_fallback)
                else:
                    # Return visit — short look line
                    lines.append(r.display_look())

        elif kind == "look":
            if room:
                lines.append(room.display_look())
                # Prompt 2: layer a safehouse ambient line on look
                if room.safehouse_subtype:
                    import random as _r
                    try:
                        from . import content_loader
                        ambient = content_loader.safehouse_ambient_line(room.safehouse_subtype)
                        if ambient and _r.random() < 0.7:
                            lines.append(ambient)
                    except Exception:
                        pass
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

        # ── Prompt 03 effect types ──────────────────────────────────────────

        elif kind == "alert_patrol":
            if floor:
                floor.floor_alert_level = min(10, floor.floor_alert_level + 2)
                # Stash a one-shot "patrol_inbound" event
                floor.active_events.append({
                    "minute": floor.current_minute,
                    "kind":   "patrol_inbound",
                    "args":   {"source_room": room.room_id if room else ""},
                })
            lines.append(t("feedback_patrol_alerted",
                           fallback="Patrol odebrał sygnał. Idą tu."))

        elif kind == "block_route":
            if room and room.exits:
                # Pick a random non-already-locked exit and lock it
                import random as _r
                candidates = [(lbl, ed) for lbl, ed in room.exits.items()
                              if not ed.get("locked")]
                if candidates:
                    lbl, ed = _r.choice(candidates)
                    ed["locked"] = True
                    ed["fallback_hint"] = "Zawalone albo zaryglowane. Nie tędy."
                    lines.append(t("feedback_route_blocked",
                                   fallback=f"Droga '{lbl}' jest teraz zablokowana.",
                                   exit=lbl))

        elif kind == "unblock_route":
            if room and room.exits:
                locked = [(lbl, ed) for lbl, ed in room.exits.items() if ed.get("locked")]
                if locked:
                    import random as _r
                    lbl, ed = _r.choice(locked)
                    ed["locked"] = False
                    lines.append(t("feedback_route_unblocked",
                                   fallback=f"Droga '{lbl}' otwiera się.",
                                   exit=lbl))

        elif kind == "safehouse_consequence":
            cons = eff.get("consequence", "")
            if room and room.safehouse_subtype:
                room.state = getattr(room, "state", {}) or {}
                # Stash a flag in the room's fragments (visible on Look) and on the
                # floor state for later service modifiers
                marker = f"safehouse:{cons}"
                if marker not in room.fragments:
                    room.fragments.append(marker)
                lines.append({
                    "kicked_out":     t("feedback_safe_kicked_out",
                                        fallback="Wypraszają cię. Dyskretnie. Definitywnie."),
                    "prices_up":      t("feedback_safe_prices_up",
                                        fallback="Cennik się przegrupował. Na twoją niekorzyść."),
                    "service_denied": t("feedback_safe_service_denied",
                                        fallback="Obsługa odmawia. Bez wyjaśnień."),
                }.get(cons, t("feedback_safe_consequence",
                              fallback="Coś w safehouse zmienia się — nie na lepsze.")))

        elif kind == "gain_rumor":
            cat = eff.get("category")
            try:
                from . import content_loader
                rumor = content_loader.random_rumor(category=cat)
            except Exception:
                rumor = None
            if rumor:
                rkey = rumor.get("key")
                if floor and rkey and rkey not in floor.rumors:
                    floor.rumors.append(rkey)
                text = rumor.get("text", "")
                if text:
                    lines.append(text)

        elif kind == "reveal_clue":
            # Pick any clue not yet placed in the current room
            try:
                from . import content_loader
                picked = content_loader.random_clue()
            except Exception:
                picked = None
            if picked and room:
                ckey, clue = picked
                if ckey not in room.fragments:
                    room.fragments.append(ckey)
                # Reveal tags on the character's known facts
                ch = world.character
                ch.flags.setdefault("known_clues", [])
                ch.flags.setdefault("known_facts", [])
                if ckey not in ch.flags["known_clues"]:
                    ch.flags["known_clues"].append(ckey)
                for tag in clue.get("reveals", []) or []:
                    if tag not in ch.flags["known_facts"]:
                        ch.flags["known_facts"].append(tag)
                line = clue.get("text", "")
                if line:
                    lines.append(line)

        elif kind == "class_affinity_shift":
            kind_id = eff.get("kind")
            amt = int(eff.get("amount", 1))
            if kind_id and kind_id in world.character.affinity:
                world.character.affinity[kind_id] += amt

        elif kind == "item_damage":
            # Degrade a random inventory item whose tag matches `tag` (or any with "*").
            tag = eff.get("tag", "*")
            import random as _r
            candidates = []
            for eid in world.character.inventory_ids:
                ent = world.entities.get(eid)
                if ent is None:
                    continue
                if tag == "*" or tag in (ent.tags or []):
                    candidates.append(ent)
            if candidates:
                victim = _r.choice(candidates)
                # We don't have a condition field on Entity yet; flag via state.
                victim.state["damaged"] = victim.state.get("damaged", 0) + 1
                lines.append(t("feedback_item_damaged",
                               fallback=f"{victim.display_name()}: uszkodzone.",
                               name=victim.display_name()))

    return lines


def _resolve_entity(world, room, entity_id):
    if entity_id is None or entity_id == -1:
        return None
    if room is not None:
        for e in room.entities:
            if e.entity_id == entity_id:
                return e
    return world.entities.get(entity_id)
