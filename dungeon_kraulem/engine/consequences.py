"""Consequence engine — applies ResolutionResult.effects to WorldState."""
from typing import List, Dict, Any

from ..ui.lang import t


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
                            from ..content import content_loader
                            extra = content_loader.safehouse_entry_description(r.safehouse_subtype)
                            if extra:
                                lines.append(extra)
                        except Exception:
                            pass
                    # Prompt 19 audit fix S1: materialize pending sponsor
                    # gifts when the player enters a safehouse. The gifts
                    # were queued by engine.sponsors when the sponsor
                    # decided to send something; we drop them as floor
                    # entities so the player loots them on arrival.
                    if r.safehouse_subtype:
                        try:
                            _consume_pending_gifts(world, r, lines)
                        except Exception as exc:
                            lines.append(
                                f"(Sponsor: paczka się zgubiła w transporcie: {exc})")
                    # Prompt 1: encounter-template intro (combat rooms)
                    if r.encounter_intro_fallback:
                        lines.append(r.encounter_intro_fallback)
                    # Prompt-07b follow-up: consume belief-seed encounter
                    # modifiers for this room. Mods are advisory: at most
                    # one Polish flavor line per entry, and we stash the
                    # mod types onto room.state["belief_mods"] so
                    # validation/resolution can read them later.
                    try:
                        from ..systems import memetics
                        from ..systems import narrator as _narr
                        mods = memetics.encounter_modifiers_for(world, r)
                        if mods:
                            r.state = r.state or {}
                            r.state.setdefault("belief_mods", [])
                            for m in mods:
                                mt = m.get("type")
                                if mt and mt not in r.state["belief_mods"]:
                                    r.state["belief_mods"].append(mt)
                                # Pick a narrator line that matches the
                                # nature of the mod (machine/crawler/sponsor).
                                tags = set(m.get("target_tags") or [])
                                if tags & {"machine","drone","ai","construct"}:
                                    nline = _narr.say("machine_talks_back") or \
                                            _narr.say("machine_confusion")
                                elif tags & {"crawler","npc","cult","civilian"}:
                                    nline = _narr.say("rumor_echo") or \
                                            _narr.say("crawler_gossip_shift")
                                elif tags & {"sponsor","audience"}:
                                    nline = _narr.say("sponsor_mocks_belief") or \
                                            _narr.say("sponsor_notices_propaganda")
                                else:
                                    nline = _narr.say("rumor_echo")
                                fb = m.get("fallback_line")
                                if nline:
                                    lines.append(nline)
                                elif fb:
                                    lines.append(fb)
                            # If we have a high-distortion mod, also flag
                            # the room as a place where the belief may
                            # backfire — useful for resolution logic.
                            for sid in (mods[0].get("seed_id"),):
                                seed = (world.belief_seeds or {}).get(sid)
                                if seed is not None and seed.distortion >= 70:
                                    r.state.setdefault("belief_backfire_seeds", [])
                                    if sid not in r.state["belief_backfire_seeds"]:
                                        r.state["belief_backfire_seeds"].append(sid)
                                    nline = _narr.say("belief_backfires")
                                    if nline:
                                        lines.append(nline)
                    except Exception:
                        pass
                else:
                    # Return visit — short look line
                    lines.append(r.display_look())
                # Prompt 07: safehouse entry — strong propagation trigger.
                if r.safehouse_subtype:
                    try:
                        from ..systems import memetics
                        memetics.process_belief_seeds(world, 0,
                                                      trigger="safehouse_entry")
                    except Exception:
                        pass

        elif kind == "look":
            if room:
                lines.append(room.display_look())
                # Prompt 2: layer a safehouse ambient line on look
                if room.safehouse_subtype:
                    import random as _r
                    try:
                        from ..content import content_loader
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
            else:
                # P27.8 (P27-UX-5) — bare `nasłuchuj` (no target room) now
                # surfaces ambient noise level for the current room AND
                # each adjacent room, using the noise system. Helps the
                # player decide which exit is safest BEFORE walking
                # through a door.
                if room and floor:
                    def _noise_label(n: int) -> str:
                        if n <= 0:   return "cisza"
                        if n < 8:    return "szmery"
                        if n < 20:   return "głosy/kroki"
                        if n < 40:   return "ruch, dudnienie"
                        return "tłum, wrzaski"
                    cur_n = int(getattr(room, "noise_level", 0) or 0)
                    lines.append(t("feedback_listen_self",
                                   fallback=f"Tutaj: {_noise_label(cur_n)} ({cur_n}).",
                                   noise=cur_n))
                    # Walk each exit; show what we can hear behind closed doors.
                    # room.exits is Dict[label, {"target":..., "locked":..., ...}].
                    for label, ed in (room.exits or {}).items():
                        if not isinstance(ed, dict):
                            continue
                        if ed.get("hidden"):
                            continue
                        nb = floor.rooms.get(ed.get("target"))
                        if nb is None:
                            continue
                        n = int(getattr(nb, "noise_level", 0) or 0)
                        nb_name = nb.fallback_short_title or nb.room_id
                        lines.append(f"  → {label} ({nb_name}): {_noise_label(n)} ({n}).")
                else:
                    lines.append(t("feedback_silence",
                                   fallback="Słyszysz tylko własny oddech."))
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
            # Prompt 21: damage_type defaults to physical; routed through
            # engine.damage.apply_damage so resistances + status-on-hit
            # work uniformly with traps and environmental kills.
            damage_type = str(eff.get("damage_type") or "physical")
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                # Gap 4: pre-fire any armed player traps in the room against this
                # hostile before the main damage lands. One trap per damage hit.
                if room is not None and ent.entity_type in ("monster","crawler","npc") \
                        and ent.is_alive():
                    traps = (room.state or {}).get("player_traps") or []
                    untriggered = [tr for tr in traps if not tr.get("triggered")]
                    if untriggered:
                        tr = untriggered[0]
                        tr["triggered"] = True
                        eff_payload = tr.get("effect") or {}
                        bonus = int(eff_payload.get("amount", 2))
                        trap_dtype = str(eff_payload.get("damage_type")
                                         or "physical")
                        from . import damage as _dmg
                        tr_res = _dmg.apply_damage(world, ent, bonus,
                                                   damage_type=trap_dtype,
                                                   source="trap_pre_combat")
                        # Status-only effects still apply (smoke/trip).
                        if eff_payload.get("type") == "knockdown" and \
                           "prone" not in ent.conditions:
                            ent.conditions.append("prone")
                        elif eff_payload.get("type") == "obscure" and \
                             "blinded" not in ent.conditions:
                            ent.conditions.append("blinded")
                        lines.append(t("feedback_trap_fires",
                                       fallback=(f"Pułapka „{tr.get('display_name','?')}” "
                                                 f"odpala: -{tr_res['amount_dealt']} HP "
                                                 f"({_dmg.damage_type_label(trap_dtype)})"),
                                       name=tr.get("display_name","?"),
                                       amount=tr_res["amount_dealt"]))
                # Main damage hit — route through engine.damage so
                # resistance + elemental status apply uniformly.
                from . import damage as _dmg
                res = _dmg.apply_damage(world, ent, amount,
                                        damage_type=damage_type,
                                        source="combat")
                if ent.hp <= 0 and ent.max_hp > 0:
                    lines.append(t("feedback_entity_down", fallback=f"{ent.display_name()} pada.",
                                   name=ent.display_name()))
                else:
                    tag = ""
                    if res.get("immune"):
                        tag = " (odporny)"
                    elif res.get("resisted"):
                        tag = " (osłabione)"
                    elif res.get("vulnerable"):
                        tag = " (podatny!)"
                    lines.append(t("feedback_entity_hit",
                                   fallback=(f"{ent.display_name()}: "
                                             f"-{res['amount_dealt']} HP"
                                             f" ({_dmg.damage_type_label(damage_type)})"
                                             + tag),
                                   name=ent.display_name(),
                                   amount=res["amount_dealt"]))

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
            # P29.0 — route through threat.bump so threshold-crossings
            # escalate any hostile in the room. Was a direct field
            # mutation that bypassed escalation.
            if room:
                try:
                    from . import threat as _threat
                    for ln in _threat.bump(world, room,
                                           int(eff.get("amount", 1)),
                                           source="consequence_add_noise"):
                        lines.append(ln)
                except Exception:
                    room.noise_level += int(eff.get("amount", 1))

        elif kind == "de_escalate_threat":
            # P29.0 — emitted by `hide` / `ukryj się` success. Drops the
            # local threat pool and steps any hostiles down one rank.
            if room:
                try:
                    from . import threat as _threat
                    _threat.de_escalate(world, room,
                                        amount=int(eff.get("amount", 5)))
                except Exception:
                    pass

        elif kind == "add_audience":
            # Prompt 18: route audience writes through the audience module
            # so band crossings, decay reset, and sponsor interventions
            # all fire from one place.
            from . import audience as _aud
            from . import sponsors as _sp
            _aud.change_audience(world, int(eff.get("amount", 0)),
                                 source=str(eff.get("source", "effect")))
            # Tag routing — many "audience" effects also signal a tag the
            # sponsors care about (e.g. spectacle, env_kill). Optional.
            tag = eff.get("tag", "")
            if tag:
                _sp.note_player_tag(world, tag, weight=int(eff.get("weight", 1)))
            _sp.maybe_intervene(world)

        elif kind == "sponsor_attention":
            # Prompt 18: direct attention bump for a specific sponsor.
            # Used by risk_reward and content templates that want to
            # poke one sponsor independent of any tag system.
            from . import sponsors as _sp
            sk = str(eff.get("sponsor_key", "") or "")
            if sk:
                _sp.adjust_attention(world, sk, int(eff.get("amount", 0)))
                _sp.maybe_intervene(world)

        elif kind == "sponsor_tag":
            # Prompt 18: emit a player-action tag to all sponsors.
            # Convenience wrapper around sponsors.note_player_tag().
            from . import sponsors as _sp
            tag = str(eff.get("tag", "") or "")
            if tag:
                _sp.note_player_tag(world, tag,
                                    weight=int(eff.get("weight", 1)))
                _sp.maybe_intervene(world)

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

        elif kind == "log_line":
            # P28.5: explicit narrator line emit from a consequence.
            # `category` is for future content-loader hookup; `fallback`
            # is the literal line used today (no LLM, no template
            # registry yet). Lets resolution.py push feedback text
            # without needing a special slot in the caller's log loop.
            ln = eff.get("fallback") or ""
            if ln:
                lines.append(ln)

        elif kind == "world_flag":
            # Generic world-state flag, used by risks/rewards. Lives on
            # the floor's active_events as well as character.flags so both
            # game and save/load see it. Never overrides existing value
            # unless explicitly set.
            key = eff.get("key")
            value = eff.get("value", True)
            if key:
                world.character.flags[key] = value

        elif kind == "loot":
            eid = eff.get("entity_id")
            ent = _resolve_entity(world, room, eid)
            if ent is not None:
                if ent.portable:
                    # Path A: portable entity (a card, a flask) → pick up
                    if room is not None:
                        room.remove_entity(ent)
                    ent.location_id = f"inventory:player"
                    world.character.inventory_ids.append(ent.entity_id)
                    lines.append(t("feedback_looted",
                                   fallback=f"Zabierasz: {ent.display_name()}.",
                                   name=ent.display_name()))
                else:
                    # Prompt 22 bug fix — Path B: container (skrzynia,
                    # szafa, kupa gruzu). `przeszukaj` yields contents.
                    # Either spawn from `state.loot` if the entity was
                    # authored with one, or roll random scraps based on
                    # tags. Once searched the container is marked
                    # `depleted` so re-searching is a no-op.
                    _loot_container(world, room, ent, lines)
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
            # P29.0 — patrol scheduling REMOVED. "Alarm" effects now
            # just bump the local room threat pool by a chunk + emit a
            # narrator line about commotion. No off-screen patrol
            # spawns. The thing in the room either wakes up here, or
            # it doesn't.
            try:
                from . import threat as _threat
                _threat.bump(world, room, 8,
                             source=str(eff.get("source") or "alarm"))
            except Exception:
                pass
            # Still bump audience — sponsors care about commotion.
            from . import audience as _aud
            _aud.change_audience(world, 2, source="alarm")
            lines.append(t("feedback_commotion",
                           fallback="Hałas niesie się po pokoju."))

        elif kind == "add_journal":
            world.character.journal.setdefault(room.room_id if room else "_", []).append(eff.get("text",""))

        # ── Prompt 03 effect types ──────────────────────────────────────────

        elif kind == "alert_patrol":
            # P29.0 — REMOVED. The "patrol incoming" mechanic is gone.
            # Effects that used to alert_patrol now just bump local
            # threat. Kept here as a no-op to absorb old data without
            # crashing (eff = noop).
            try:
                from . import threat as _threat
                _threat.bump(world, room, 6, source="alert_patrol_legacy")
            except Exception:
                pass

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
                                        fallback="Ceny idą w górę. Patrzą na ciebie zimno."),
                    "service_denied": t("feedback_safe_service_denied",
                                        fallback="Obsługa odmawia. Bez wyjaśnień."),
                }.get(cons, t("feedback_safe_consequence",
                              fallback="Coś w kryjówce się zmienia — nie na lepsze.")))

        elif kind == "gain_rumor":
            cat = eff.get("category")
            try:
                from ..content import content_loader
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
            # Pick a clue not yet placed; respect chain prerequisites
            # (Prompt 06a, gap #6). If a clue's requires_clues aren't all
            # in known_clues and it isn't can_skip_sequence, fall back to
            # a vague hint or drop the reveal entirely.
            try:
                from ..content import content_loader
            except Exception:
                content_loader = None
            ch = world.character
            ch.flags.setdefault("known_clues", [])
            ch.flags.setdefault("known_facts", [])
            picked = None
            if content_loader is not None:
                # Try up to 4 picks looking for a clue whose prereqs are met
                for _ in range(4):
                    cand = content_loader.random_clue()
                    if cand is None: break
                    ck, cd = cand
                    if ck in ch.flags["known_clues"]:
                        continue
                    req = cd.get("requires_clues") or []
                    if cd.get("can_skip_sequence") or all(r in ch.flags["known_clues"] for r in req):
                        picked = cand; break
            if picked is None:
                lines.append(t("feedback_vague_hint",
                               fallback="Zauważasz coś, czego jeszcze nie potrafisz nazwać."))
            else:
                ckey, clue = picked
                if room and ckey not in room.fragments:
                    room.fragments.append(ckey)
                if ckey not in ch.flags["known_clues"]:
                    ch.flags["known_clues"].append(ckey)
                # Prompt 07b follow-up: roll `false_variant_chance` to maybe
                # deliver a distorted version. The store keeps the original
                # key + new effective reliability + a `contaminated` flag so
                # save/load preserves the uncertain state.
                from ..content import content_loader as _cl
                delivery = _cl.roll_clue_delivery(clue)
                used_text = delivery["text"]
                # Reveal_tags follow the canonical clue, regardless of which
                # variant fired — false rumors still teach the tag-shape;
                # they just teach it wrong. The reliability counter records
                # how much to trust it.
                for tag in clue.get("reveals", []) or []:
                    if tag not in ch.flags["known_facts"]:
                        ch.flags["known_facts"].append(tag)
                try:
                    from ..systems import knowledge as _kn
                    entry = dict(clue)
                    entry.setdefault("key", ckey)
                    entry["reliability"] = delivery["reliability"]
                    if delivery["contaminated"]:
                        # Tag for journal display + downstream gating.
                        entry["tags"] = list(entry.get("tags") or []) + ["contaminated"]
                    newly = _kn.add_known_clue(world, entry)
                    if newly:
                        for path in (clue.get("enables_paths") or []):
                            lines.append(t("feedback_path_unlocked",
                                           fallback=f"Odblokowano możliwość: {path}.",
                                           path=path))
                except Exception:
                    pass
                if used_text:
                    lines.append(used_text)
                # If contaminated, hint AT THE FRINGE that the source feels
                # off — never expose the false_variant_chance mechanic.
                if delivery["contaminated"]:
                    lines.append(t("feedback_clue_feels_off",
                                   fallback="Brzmi spójnie, ale coś tu nie pasuje. Lepiej traktować ostrożnie."))

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


# ── Prompt 22 bug fix: container search yields contents ──────────────────

def _loot_container(world, room, container, lines) -> None:
    """Search a non-portable container. Produces:
      - authored items from `container.state['loot']` (list of item_keys)
      - failing that, 1-3 randomly-rolled scraps/materials based on tags
    Marks the container `depleted` after to avoid re-search. Empty
    containers print a deadpan "nothing useful" line so the player at
    least knows the search resolved."""
    state = container.state or {}
    if state.get("depleted") or state.get("stripped"):
        lines.append(t("feedback_container_already_searched",
                       fallback=f"„{container.display_name()}” już jest "
                                f"przeszukane — nic więcej.",
                       name=container.display_name()))
        return

    import random as _r
    yielded = False

    # Authored loot first.
    authored = state.get("loot") or []
    if authored:
        try:
            from ..content.items import make_item
            for item_key in list(authored)[:5]:
                ent = make_item(item_key, location_id=f"inventory:player")
                world.register(ent)
                world.character.inventory_ids.append(ent.entity_id)
                lines.append(t("feedback_container_yielded",
                               fallback=f"W środku: {ent.display_name()}.",
                               name=ent.display_name()))
                yielded = True
            container.state["loot"] = []
        except Exception:
            pass

    # Random scrap drops based on tags (covers procgen containers).
    if not yielded:
        tags = set(container.tags or [])
        drops = {}
        # Pick from material catalog; small quantities.
        candidates = []
        if "supply" in tags or "crate" in tags or "container" in tags:
            candidates = ["scrap_metal", "wire_bundle", "tape", "screws"]
        elif "medical" in tags or "clinic" in tags:
            candidates = ["cloth_strips", "tape"]
        elif "chemical" in tags or "lab" in tags:
            candidates = ["glass_shards", "wire_bundle"]
        else:
            candidates = ["scrap_metal", "cloth_strips"]
        # 1-2 stacks, 1-2 qty each.
        n_kinds = _r.randint(1, 2)
        try:
            from ..content import materials as _mat
            for _ in range(n_kinds):
                if not candidates: break
                k = _r.choice(candidates)
                candidates.remove(k)
                if _mat.get(k) is None: continue
                drops[k] = drops.get(k, 0) + _r.randint(1, 2)
            if drops:
                _mat.add_materials(world.character, drops)
                row = ", ".join(
                    f"{q}x {(_mat.get(k).name() if _mat.get(k) else k)}"
                    for k, q in drops.items())
                lines.append(t("feedback_container_scraps",
                               fallback=f"W środku: {row}.",
                               row=row))
                yielded = True
        except Exception:
            pass

    if not yielded:
        lines.append(t("feedback_container_empty",
                       fallback=f"„{container.display_name()}” — pusto.",
                       name=container.display_name()))
    container.state["depleted"] = True


# ── Prompt 19 audit fix S1: sponsor gift consumer ─────────────────────────

def _consume_pending_gifts(world, room, lines) -> None:
    """Materialize every pending sponsor gift into the current
    safehouse room as a loot item, and log a narrator line per gift.

    The queue lives on `world.pending_sponsor_gifts` (populated by
    `engine.sponsors._queue_safehouse_gift`). Each entry is
    `{"sponsor_key": ..., "item_key": ...}`.
    """
    pending = list(getattr(world, "pending_sponsor_gifts", None) or [])
    if not pending:
        return
    from ..content.items import make_item
    from ..content.data.sponsors import get_sponsor
    from ..ui.lang import t
    delivered: list = []
    leftover: list = []
    for entry in pending:
        item_key = str(entry.get("item_key") or "")
        sponsor_key = str(entry.get("sponsor_key") or "")
        if not item_key:
            continue
        try:
            ent = make_item(item_key, location_id=room.room_id)
            world.register(ent)
            room.entities.append(ent)
            sponsor_name = ""
            if sponsor_key:
                sdata = get_sponsor(sponsor_key)
                sponsor_name = t(sdata.get("name_key", ""),
                                 fallback=sdata.get("name_fallback",
                                                    sponsor_key))
            name = ent.display_name() if hasattr(ent, "display_name") else \
                   getattr(ent, "fallback_name", item_key) or item_key
            if sponsor_name:
                lines.append(t("sponsor_gift_delivered",
                               fallback=f"{sponsor_name} podrzucił ci coś w "
                                        f"safehouse: „{name}”.",
                               sponsor=sponsor_name, item=name))
            else:
                lines.append(f"W kącie safehouse znajdujesz: „{name}”.")
            delivered.append(entry)
        except Exception:
            # Unknown item_key — keep it on the queue so future code can
            # try again (e.g. when the item template is later added).
            leftover.append(entry)
    # Replace queue with only the leftovers.
    world.pending_sponsor_gifts = leftover
