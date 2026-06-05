"""Action handlers — extracted from game.py (Phase 0.5 decoupling).

All the _attempt_* player-action resolvers (craft, salvage, break, force,
deploy, coat, consume, rest, memetic, ...). Pulled out of the orchestrator
into a mixin Game inherits, verbatim (self.* still resolves). Plus the small
salvage tag->table helper cluster they alone used. pygame-free game logic.
See docs/GODOT_PORT_PLAN.md Phase 0.5.
"""
from __future__ import annotations
from ..config import (LOG_NORMAL, LOG_SYSTEM, LOG_WARN, LOG_SUCCESS,
                      LOG_SYNDIC, LOG_DANGER)
from ..ui.lang import t
from ..ui import audio
from ..systems.narrator import say as narrate
from .validation import validate
from .resolution import resolve
from .consequences import apply
from .salvage_util import _pick_salvage_table_key
from . import time_system


class ActionHandlersMixin:
    """_attempt_* action resolvers mixed into Game. No own state; uses self.*."""

    def _attempt_wield(self, intent):
        """Equip an inventory item to main or offhand. Two-handed weapons
        refuse if the offhand is occupied. Combat-mode switching costs
        one action; out-of-combat switching is free.
        """
        if not intent.targets:
            self.log(t("feedback_wield_no_target",
                       fallback="Co chcesz dobyć?"), LOG_WARN)
            return
        ch = self.world.character
        item = self._resolve_inventory_item(intent.targets[0])
        if item is None:
            self.log(t("feedback_wield_not_in_inventory",
                       fallback=f"Nie masz „{intent.targets[0]}” w plecaku.",
                       name=intent.targets[0]),
                     LOG_WARN)
            return
        # Determine target hand.
        hand = "main"
        for m in (intent.modifiers or []):
            if isinstance(m, str) and m.startswith("hand:"):
                hand = m.split(":", 1)[1]
        # Two-handed weapons (tagged `two_handed`) require both hands.
        tags = set(item.tags or [])
        two_handed = "two_handed" in tags
        offhand_only = "offhand_only" in tags   # e.g. shield
        if offhand_only and hand == "main":
            hand = "offhand"   # silently promote
        if two_handed and ch.wielded_offhand_id is not None and hand == "main":
            offhand_ent = self.world.get(ch.wielded_offhand_id)
            offhand_name = offhand_ent.display_name() if offhand_ent else "coś"
            self.log(t("feedback_wield_twohand_refuse",
                       fallback=f"„{item.display_name()}” wymaga obu rąk. "
                                f"Najpierw wyłóż „{offhand_name}”.",
                       weapon=item.display_name(), offhand=offhand_name),
                     LOG_WARN)
            return
        # Check the slot isn't already holding this item.
        cur_slot_id = (ch.wielded_main_id if hand == "main"
                       else ch.wielded_offhand_id)
        if cur_slot_id == item.entity_id:
            self.log(t("feedback_wield_already",
                       fallback=f"Już trzymasz „{item.display_name()}”.",
                       name=item.display_name()),
                     LOG_WARN)
            return
        # If item is currently in the OTHER hand, swap.
        if hand == "main" and ch.wielded_offhand_id == item.entity_id:
            ch.wielded_offhand_id = None
        elif hand == "offhand" and ch.wielded_main_id == item.entity_id:
            ch.wielded_main_id = None
        # Set the slot.
        if hand == "main":
            ch.wielded_main_id = item.entity_id
            # Two-handed auto-clears offhand.
            if two_handed:
                ch.wielded_offhand_id = None
        else:
            ch.wielded_offhand_id = item.entity_id
        hand_label = "lewą rękę" if hand == "offhand" else "główną rękę"
        self.log(t("feedback_wield_ok",
                   fallback=f"Dobywasz „{item.display_name()}” w {hand_label}.",
                   name=item.display_name(), hand=hand_label),
                 LOG_SUCCESS)
        # Combat: this consumes the player's action.
        from . import combat as _cmb
        floor = self.world.current_floor
        room = floor.current_room() if floor else None
        cs = _cmb.get_combat(room) if room else None
        if cs is not None:
            self._combat_after_player_action(cs)
    def _attempt_sheathe(self, intent):
        """Put away the currently-wielded main weapon."""
        ch = self.world.character
        # Without explicit target, sheathe main. With target, sheathe
        # whichever hand holds it.
        if intent.targets:
            item = self._resolve_inventory_item(intent.targets[0])
            if item is None:
                self.log(t("feedback_sheathe_not_held",
                           fallback="Nie trzymasz tego."),
                         LOG_WARN)
                return
            if ch.wielded_main_id == item.entity_id:
                ch.wielded_main_id = None
            elif ch.wielded_offhand_id == item.entity_id:
                ch.wielded_offhand_id = None
            else:
                self.log(t("feedback_sheathe_not_held",
                           fallback="Nie trzymasz tego."),
                         LOG_WARN)
                return
            self.log(t("feedback_sheathe_ok",
                       fallback=f"Chowasz „{item.display_name()}”.",
                       name=item.display_name()),
                     LOG_SUCCESS)
        else:
            if ch.wielded_main_id is None:
                self.log(t("feedback_sheathe_empty",
                           fallback="Już nic nie trzymasz."),
                         LOG_WARN)
                return
            ent = self.world.get(ch.wielded_main_id)
            ch.wielded_main_id = None
            if ent is not None:
                self.log(t("feedback_sheathe_ok",
                           fallback=f"Chowasz „{ent.display_name()}”.",
                           name=ent.display_name()),
                         LOG_SUCCESS)
    def _attempt_class_active(self):
        """P27.7 — trigger the character's class active ability. One use
        per floor; per-floor cooldown lives on character.flags."""
        from ..systems import class_features as _cf
        ok, line = _cf.use_active(self.world)
        self.log(line, LOG_SUCCESS if ok else LOG_WARN)

    # P27.9 — food + drink mechanic
    # ─────────────────────────────────────────────────────────────────
    # Items tagged "food" or "consumable" give HP back; specific keys
    # add bonus effects (coffee → wake-up, snack_bar → regen, dirty_bandage
    # → bleeding clear, etc.). The item is removed from inventory on
    # success. Class passive `heal_mul` (medic) doubles the heal amount.
    # Effects are intentionally small so consumables stay tactical
    # rather than replacing safehouse sleep.
    # `verb`: "consume" (eat/drink → "Konsumujesz") or "use" (apply →
    # "Użyłeś"). Defaults to "consume" for food, "use" for everything else.
    _CONSUMABLE_EFFECTS = {
        "snack_bar":      {"heal": 12, "clear": [], "verb": "consume"},
        "coffee":         {"heal": 4,  "clear": ["afraid", "shaken"],
                           "verb": "consume"},
        # A bandage is APPLIED, not eaten — it staunches a wound, so it
        # clears both bleeding and the wounded status it's meant to treat.
        "dirty_bandage":  {"heal": 18, "clear": ["bleeding", "wounded"],
                           "verb": "use"},
        "cracked_mug":    {"heal": 1,  "clear": [], "verb": "consume"},
        "battery":        {"heal": 0,  "buff": "next_tech_plus2",
                           "verb": "use"},
    }
    def _attempt_consume(self, intent):
        """Eat/drink an inventory item. Refuses non-food. P27-UX-15."""
        from ..systems import class_features as _cf
        from . import combat as _cmb
        ch = self.world.character
        # Resolve item by name from inventory.
        target_name = (intent.targets[0] if intent.targets else "").strip().lower()
        if not target_name:
            self.log(t("feedback_consume_what",
                       fallback="Co chcesz skonsumować? Np. `zjedz batonik`."),
                     LOG_WARN)
            return
        def _name_match(needle: str, hay: str) -> bool:
            """Loose Polish-friendly match. Splits hay on whitespace and
            checks each word against the needle as prefix/substring,
            either direction. Handles `batonik` → `baton energetyczny`."""
            n = needle.strip().lower()
            if not n:
                return False
            h = hay.lower()
            if n in h or h in n:
                return True
            for word in h.replace("-", " ").split():
                if word.startswith(n[:4]) or n.startswith(word[:4]):
                    return True
            return False

        chosen = None
        for eid in list(ch.inventory_ids):
            ent = self.world.get(eid)
            if ent is None:
                continue
            nm = (ent.display_name() or ent.key or "")
            ek = (ent.key or "")
            if _name_match(target_name, nm) or _name_match(target_name, ek):
                # Must be food / consumable.
                tags = ent.tags or []
                if "food" in tags or "consumable" in tags or ent.key in self._CONSUMABLE_EFFECTS:
                    chosen = ent
                    break
        if chosen is None:
            self.log(t("feedback_consume_none",
                       fallback="Nie masz nic jadalnego pasującego."),
                     LOG_WARN)
            return
        spec = self._CONSUMABLE_EFFECTS.get(chosen.key, {"heal": 5})
        # Pick the right verb: food/drink is eaten ("Konsumujesz"), a
        # bandage / battery is applied ("Użyłeś"). Default by tag.
        _tags = chosen.tags or []
        _verb = spec.get("verb") or (
            "consume" if ("food" in _tags or "drink" in _tags) else "use")
        _verb_word = "Konsumujesz" if _verb == "consume" else "Użyłeś"
        heal = int(spec.get("heal", 0))
        if heal > 0:
            # P29.62 — Przetrwanie (bezdomny): jedzenie i napoje leczą +50%.
            from . import character as _char
            heal = int(round(heal * _cf.heal_multiplier(ch)
                             * _char.survival_heal_mult(ch)))
            pre = ch.hp
            ch.heal(heal)
            self.log(f"{_verb_word} „{chosen.display_name()}”. "
                     f"+{ch.hp - pre} HP ({ch.hp}/{ch.max_hp}).",
                     LOG_SUCCESS)
        else:
            self.log(f"{_verb_word} „{chosen.display_name()}”.", LOG_NORMAL)
        # Clear listed statuses (route the label through the PL map).
        from . import combat as _cmb_lbl
        for cond in spec.get("clear", []):
            if cond in ch.conditions:
                ch.conditions.remove(cond)
                # Also drop its status-clock so it can't tick back.
                _clk = (ch.flags or {}).get("status_clocks") \
                    if hasattr(ch, "flags") else None
                if isinstance(_clk, dict):
                    _clk.pop(cond, None)
                self.log(f"  Stan „{_cmb_lbl.status_label(cond, 'pl')}” mija.",
                         LOG_SUCCESS)
        # Buff flag (rare).
        buff = spec.get("buff")
        if buff:
            ch.flags[buff] = True
        # Remove item.
        try:
            ch.inventory_ids.remove(chosen.entity_id)
        except ValueError:
            pass
        # Sponsor tag: consumption events feed memetics.
        try:
            from . import sponsors as _sp
            _sp.note_player_tag(self.world, "consume")
        except Exception:
            pass
    def _attempt_rest_short(self):
        """P27.6 — short rest (D&D-style). Restores ~25% max HP,
        costs 20 in-game minutes. Refused if: enemies in room, encounter
        pending in <15 min, already at full HP, or 2 short rests this
        floor used up."""
        from . import time_system as ts
        from . import combat as _cmb
        ch = self.world.character
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        # Enemies present? Refuse.
        if _cmb.alive_hostiles_in(room):
            self.log(t("feedback_rest_enemy",
                       fallback="Wokół ciebie wróg. Odpoczynek niemożliwy."),
                     LOG_WARN)
            return
        # P29.0 — encounter scheduling removed. Rest is only refused
        # for active threat in the current room (any alive hostile with
        # threat_level >= 1 == has noticed you).
        try:
            for ent in (self.world.current_floor.current_room().entities
                        if self.world.current_floor else []):
                if (ent.is_alive() and ent.entity_type == "monster"
                        and int(getattr(ent, "threat_level", 0) or 0) >= 1):
                    self.log(t("feedback_rest_threatened",
                               fallback="Coś cię obserwuje. "
                                        "To nie jest moment na odpoczynek."),
                             LOG_WARN)
                    return
        except Exception:
            pass
        # Already full?
        if ch.hp >= ch.max_hp:
            self.log(t("feedback_rest_full_hp",
                       fallback="Jesteś w pełni sił."),
                     LOG_NORMAL)
            return
        # Per-day cooldown — max 2 short rests per day.
        day_key = f"rests_short_day_{self.world.current_floor.day_number()}"
        used = int(ch.flags.get(day_key, 0))
        if used >= 2:
            self.log(t("feedback_rest_cooldown",
                       fallback="Już dwa razy odpoczywałeś dziś. "
                                "Ciało domaga się dłuższego snu."),
                     LOG_WARN)
            return
        # Heal.
        # P29.53g — rest tickuje 30 min (było 20). Dłużej = bardziej
        # widoczne w zegarze top-baru, lepiej współgra z 14-dniowym
        # deadlinem (1 piętro = ~20k minut, 30 min = 0.15% — wciąż
        # tanio, ale user widzi że coś się stało).
        heal = max(1, ch.max_hp // 4)   # ~25% of max
        # P29.55 — double_rest trait (np. half_dead): mnoży heal ×2.
        try:
            from . import species_effects as _sp_fx
            heal = int(round(heal * _sp_fx.rest_heal_mul(ch)))
        except Exception:
            pass
        ch.heal(heal)
        ch.flags[day_key] = used + 1
        ts.advance(self.world, 30)
        # P29.53g — explicit time feedback w komunikacie.
        from .time_system import format_clock
        msg = (f"Krótki odpoczynek. Odzyskujesz {heal} HP "
               f"({ch.hp}/{ch.max_hp}). Zegar: {format_clock(self.world)} "
               f"(−30 min).")
        self.log(msg, LOG_SUCCESS)
    def _attempt_rest_long(self):
        """P27.6 — long rest. Pełna regeneracja HP + reset most
        short-term statuses, costs 6 in-game hours, tylko w
        `safehouse_subtype`-rooms. Sen poza safehouse triggeruje
        encounter spawn."""
        from . import time_system as ts
        from . import combat as _cmb
        ch = self.world.character
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            return
        if _cmb.alive_hostiles_in(room):
            self.log(t("feedback_sleep_enemy",
                       fallback="Sen w czasie walki kończy się jednoznacznie."),
                     LOG_DANGER)
            return
        if not room.is_safe():
            # P29.0 — unsafe sleep: instead of scheduling a patrol that
            # arrives after sleep, bump the room threat pool hard so
            # any hostile already present wakes up. Player gets a clean
            # narrator line and refusal; if they really want to sleep
            # here, they need to clear the room first.
            try:
                from . import threat as _threat
                lines = _threat.bump(self.world, room, 12,
                                     source="unsafe_sleep")
                for ln in lines:
                    self.log(ln, LOG_WARN)
            except Exception:
                pass
            self.log(t("feedback_sleep_unsafe",
                       fallback="Spróbujesz spać tu? Z otwartymi oczami "
                                "nie zaśniesz, z zamkniętymi cię znajdą."),
                     LOG_WARN)
            return
        # Safehouse sleep — full heal + status reset + day advance.
        ch.hp = ch.max_hp
        # Remove short-term statuses (keep persistent ones like
        # corroded that need explicit cure).
        TRANSIENT = {"shaken","hesitating","prone","stunned","blinded",
                     "afraid","slowed","disarmed","wounded"}
        ch.conditions = [c for c in (ch.conditions or [])
                         if c not in TRANSIENT]
        ts.advance(self.world, 6 * 60)
        self.log(t("feedback_sleep_ok",
                   fallback=f"Śpisz spokojnie. Budzisz się w pełni sił "
                            f"(HP: {ch.hp}/{ch.max_hp}).",
                   hp=ch.hp, max=ch.max_hp), LOG_SUCCESS)
    def _attempt_wear(self, intent):
        """Prompt 25 — equip a wearable from inventory into its slot.

        Auto-detects the slot from the item's `slot:X` tag. Conflicts
        (slot already occupied) automatically unequip the previous
        occupant back to inventory + log the swap.
        """
        from . import equipment as _eq
        if not intent.targets:
            self.log(t("feedback_wear_what",
                       fallback="Co chcesz założyć?"), LOG_WARN)
            return
        item = self._resolve_inventory_item(intent.targets[0])
        # _resolve_inventory_item only searches inventory; for "wear" we
        # also need to consider items already-worn (so "załóż" on
        # something worn is a no-op refusal rather than a "not found").
        if item is None:
            # Worn-pool fallback so refusal message is correct.
            for slot, eid in _eq.iter_worn(self.world.character):
                ent = self.world.get(eid)
                if ent is None:
                    continue
                from .polish_text import polish_match, fold as _fold
                if polish_match(_fold(intent.targets[0]),
                                _fold(ent.display_name())):
                    self.log(t("feedback_already_worn",
                               fallback=f"„{ent.display_name()}” już "
                                        f"masz na sobie."),
                             LOG_WARN)
                    return
            self.log(t("feedback_wear_not_found",
                       fallback=f"Nie masz „{intent.targets[0]}” do założenia.",
                       what=intent.targets[0]), LOG_WARN)
            return
        # Pick a slot from the entity's tags. For wieldable items the
        # player should use `dobądź`; warn here so we don't hijack the
        # wield path.
        slot = _eq.slot_for_entity(item)
        if slot is None:
            self.log(t("feedback_wear_no_slot",
                       fallback=f"„{item.display_name()}” nie jest "
                                f"częścią ekwipunku do założenia.",
                       name=item.display_name()), LOG_WARN)
            return
        sd_check = _eq.SLOT_DEFS.get(slot)
        if sd_check is not None and sd_check.is_wield:
            self.log(t("feedback_wear_use_wield",
                       fallback=f"Do „{item.display_name()}” użyj "
                                f"„dobądź”, nie „załóż”.",
                       name=item.display_name()), LOG_WARN)
            return
        ok, prev_id, reason = _eq.equip(self.world, self.world.character,
                                        item, slot)
        if not ok:
            self.log(reason or "Nie pasuje.", LOG_WARN)
            return
        sd = _eq.SLOT_DEFS[slot]
        prev_name = ""
        if prev_id is not None:
            prev = self.world.get(prev_id)
            if prev is not None:
                prev_name = prev.display_name()
        if prev_name:
            self.log(t("feedback_wear_swapped",
                       fallback=f"Zakładasz „{item.display_name()}” "
                                f"(slot: {sd.label_pl}). Zdejmujesz: "
                                f"„{prev_name}”.",
                       new=item.display_name(), slot=sd.label_pl,
                       old=prev_name), LOG_SUCCESS)
        else:
            self.log(t("feedback_wear_ok",
                       fallback=f"Zakładasz „{item.display_name()}” "
                                f"(slot: {sd.label_pl}).",
                       name=item.display_name(), slot=sd.label_pl),
                     LOG_SUCCESS)
    def _attempt_take_off(self, intent):
        """Prompt 25 — remove a worn item back to inventory. Accepts
        either an item name OR a slot name (`zdejmij hełm`)."""
        from . import equipment as _eq
        from .polish_text import polish_match, fold as _fold
        if not intent.targets:
            # No target — if exactly one slot is occupied, take that off.
            worn = list(_eq.iter_worn(self.world.character))
            if len(worn) == 1:
                slot, _eid = worn[0]
            else:
                self.log(t("feedback_take_off_which",
                           fallback="Zdjąć co? Powiedz, co konkretnie."),
                         LOG_WARN)
                return
        else:
            slot = None
            frag = _fold(intent.targets[0])
            # 1) Match by entity display name.
            for s, eid in _eq.iter_worn(self.world.character):
                ent = self.world.get(eid)
                if ent is None:
                    continue
                if polish_match(frag, _fold(ent.display_name())):
                    slot = s
                    break
            # 2) Match by slot label or short glyph.
            if slot is None:
                for s_key, sd in _eq.SLOT_DEFS.items():
                    if polish_match(frag, _fold(sd.label_pl)):
                        slot = s_key
                        break
            if slot is None:
                self.log(t("feedback_take_off_none",
                           fallback=f"Nie masz nic takiego na sobie."),
                         LOG_WARN)
                return
        ok, freed_id, reason = _eq.unequip(self.world, self.world.character,
                                           slot)
        if not ok:
            self.log(reason or "Slot pusty.", LOG_WARN)
            return
        ent = self.world.get(freed_id) if freed_id is not None else None
        nm = ent.display_name() if ent is not None else "?"
        sd = _eq.SLOT_DEFS[slot]
        self.log(t("feedback_take_off_ok",
                   fallback=f"Zdejmujesz „{nm}” (slot: {sd.label_pl}).",
                   name=nm, slot=sd.label_pl), LOG_SUCCESS)
    def _attempt_coat_weapon(self, intent):
        """Apply a substance material to a weapon, granting status-on-hit.

        Substance compatibility table:
            contaminated_blood / ichor_sample / chem_reagent → poison/acid
            battery_cell                                    → electric (one hit)
            tape + fungal_fiber                             → grip (no status)
        """
        if len(intent.targets) < 2:
            self.log(t("feedback_coat_usage",
                       fallback="Czym? Np. „nasącz nóż jadem”."),
                     LOG_WARN)
            return
        ch = self.world.character
        from ..content import materials as _mat
        weapon = self._resolve_inventory_item(intent.targets[0])
        if weapon is None:
            self.log(t("feedback_coat_no_weapon",
                       fallback=f"Nie masz „{intent.targets[0]}” pod ręką.",
                       name=intent.targets[0]),
                     LOG_WARN)
            return
        if "weapon" not in (weapon.tags or []):
            self.log(t("feedback_coat_not_weapon",
                       fallback=f"„{weapon.display_name()}” to nie broń.",
                       name=weapon.display_name()),
                     LOG_WARN)
            return
        # Resolve substance from materials inventory (player.materials dict).
        sub_name = intent.targets[1].lower().strip()
        from .polish_text import polish_match, fold as _fold
        sub_name_f = _fold(sub_name)
        matched_key = None
        for mkey in (ch.materials or {}):
            mat = _mat.get(mkey)
            if mat is None: continue
            if _fold(mat.name()) == sub_name_f or \
               polish_match(sub_name_f, _fold(mat.name())) or \
               polish_match(sub_name_f, _fold(mkey.replace("_", " "))):
                matched_key = mkey
                break
        if matched_key is None or ch.materials.get(matched_key, 0) <= 0:
            self.log(t("feedback_coat_no_material",
                       fallback=f"Nie masz „{sub_name}” w materiałach.",
                       name=sub_name),
                     LOG_WARN)
            return
        # Resolve coating type from material → damage_type + hits.
        COAT_TABLE = {
            "contaminated_blood": ("poison", 3),
            "ichor_sample":       ("acid",   2),
            "chem_reagent":       ("acid",   2),
            "strange_organ":      ("poison", 2),
            "battery_cell":       ("electric", 1),
            "tape":               ("physical", 5),   # grip aid (no status, +1 to-hit)
            "fungal_fiber":       ("physical", 5),
        }
        if matched_key not in COAT_TABLE:
            self.log(t("feedback_coat_incompatible",
                       fallback=f"„{matched_key}” nie pasuje do broni."),
                     LOG_WARN)
            return
        damage_type, hits = COAT_TABLE[matched_key]
        # Consume one unit of material.
        _mat.consume_materials(ch, {matched_key: 1})
        # Apply coating to weapon state.
        weapon.state = {**(weapon.state or {}),
                        "coating": {
                            "damage_type": damage_type,
                            "hits_remaining": hits,
                            "material": matched_key,
                        }}
        mat_name = _mat.get(matched_key).name() if _mat.get(matched_key) else matched_key
        from . import time_system as _ts
        _ts.advance(self.world, 3)
        self.log(t("feedback_coat_ok",
                   fallback=(f"Pokrywasz „{weapon.display_name()}” substancją "
                             f"„{mat_name}”. {hits} trafień."),
                   weapon=weapon.display_name(),
                   material=mat_name, hits=hits),
                 LOG_SUCCESS)
    def _attempt_salvage(self, intent):
        """Resolve a salvage / strip / harvest action against the current room."""
        from .validation import validate as validate_action
        from .resolution import resolve
        from .consequences import apply
        from . import time_system as ts
        from ..content import materials
        from ..content import content_loader as cl
        from ..systems import risk_reward
        import random

        # Use the validator to pick a target entity (it already supports ambiguity)
        v = validate_action(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations), LOG_NORMAL)
            # P26c: latch disambiguation so the next `oba`/`1`/partial
            # name from the player resolves through the standard path.
            self._stash_disambiguation_on_invalid(v, intent)
            return

        target = v.matched_entities[0] if v.matched_entities else None
        if target is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego szukasz."), LOG_WARN)
            return

        # Prompt 24: salvaging a corpse routes to butcher under the
        # hood — the materials economy is the same but the per-monster
        # table + flavor + tag-bus events come from
        # `content/data/monster_salvage.py`.
        from .entity import T_CORPSE
        if target.entity_type == T_CORPSE:
            self._run_butcher(target); return

        # Gap 3: ownership / theft consequences. If the target was placed inside
        # a safehouse, salvaging it is theft. We don't BLOCK it — the player can
        # absolutely strip the cafe espresso machine — but we make it visible
        # and route the social fallout through the existing consequence engine.
        tstate = target.state or {}
        is_owned = (tstate.get("owned_by") == "safehouse"
                    or tstate.get("theft_sensitive") is True)
        if is_owned:
            ch = self.world.character
            warns = int(ch.flags.get("safehouse_theft_warnings", 0))
            # Narrator: first time vs. escalation.
            narr_key = "safehouse_theft_attempt" if warns == 0 else "safehouse_theft_escalation"
            line = narrate(narr_key) or narrate("safehouse_theft") or \
                t("feedback_safehouse_theft_warn",
                  fallback=f"„{target.display_name()}” należy do kryjówki — patrzą na to.",
                  name=target.display_name())
            self.log(line, LOG_WARN)
            if warns == 0:
                cons_kind = "service_denied"
                ch.flags["safehouse_theft_warnings"] = 1
            elif warns == 1:
                cons_kind = "prices_up"
                ch.flags["safehouse_theft_warnings"] = 2
            else:
                cons_kind = "kicked_out"
                ch.flags["safehouse_theft_warnings"] = warns + 1
            # Sponsor-property branch
            if "sponsor" in (target.tags or []) or "camera" in (target.tags or []):
                spline = narrate("sponsor_property_salvage")
                if spline:
                    self.log(spline, LOG_SYNDIC)
            theft_effects = [
                {"type": "safehouse_consequence", "consequence": cons_kind},
                {"type": "world_flag", "key": "sponsor_attention", "value": True},
            ]
            # social_suspicion through risk_reward keeps relationship math
            # in the shared mapper, not hard-coded here.
            from ..systems import risk_reward
            theft_effects.extend(risk_reward.risk_effects(
                ["social_suspicion", "tracked_by_sponsor"]))
            extra_lines = apply(theft_effects, self.world, time_system=time_system)
            for ln in extra_lines:
                self.log(str(ln), LOG_WARN)

        # Pick a salvage table based on target tags
        table_key = _pick_salvage_table_key(target)
        if table_key is None:
            # P28.6: stamp `no_salvage` so the action bar stops offering
            # `Zdemontuj` on this entity next frame. Same pattern as the
            # `stripped` flag — UI builder reads it and filters the
            # affordance out, ending the spam loop where the player
            # repeatedly clicked Zdemontuj on a terminal that never
            # had a salvage table.
            if target.state is None:
                target.state = {}
            target.state["no_salvage"] = True
            self.log(t("feedback_no_salvage",
                       fallback=f"„{target.display_name()}” nie ma z czego ciągnąć surowców."),
                     LOG_WARN)
            return

        from ..content.data.salvage_tables import SALVAGE_TABLES
        table = SALVAGE_TABLES.get(table_key, {})
        # No infinite farming: refuse if already stripped/depleted
        state = target.state or {}
        if state.get("stripped") or state.get("depleted"):
            self.log(t("feedback_already_stripped",
                       fallback=f"„{target.display_name()}” jest już rozebrane na części."),
                     LOG_WARN)
            return

        # Audit gap 1: respect desired_material as a filter. If the player asked
        # for X but no material in the table mentions X by key or tag, give an
        # immersive rejection instead of dropping unrelated stuff.
        desired = (intent.desired_material or "").strip().lower()
        if desired and len(desired) >= 3:
            from ..content import materials as _mat
            all_drop_keys = list((table.get("drops") or {}).keys()) + list((table.get("rare") or {}).keys())
            def _matches(key):
                if desired in key.lower(): return True
                md = _mat.get(key)
                if md is None: return False
                hay = (md.fallback_name_pl + " " + md.fallback_name_en).lower()
                if desired in hay: return True
                for tg in md.tags:
                    if desired in tg or tg in desired:
                        return True
                return False
            if all_drop_keys and not any(_matches(k) for k in all_drop_keys):
                self.log(t("feedback_no_such_material",
                           fallback=f"Możesz rozebrać „{target.display_name()}”, "
                                    f"ale nie wygląda, żeby dało się z niego pozyskać „{desired}”.",
                           src=target.display_name(), what=desired),
                         LOG_WARN)
                return

        # Run a stat check
        stat = table.get("stat", v.required_checks[0]["stat"] if v.required_checks else "STR")
        dc = int(table.get("dc", 10))
        from .utils_compat import roll_d20
        raw = roll_d20()
        ch = self.world.character
        mod = ch.stat_mod(stat)
        total = raw + mod
        crit = (raw == 20); fumble = (raw == 1)
        if crit:               level = "critical_success"
        elif fumble:           level = "critical_failure"
        elif total >= dc + 5:  level = "critical_success"
        elif total >= dc:      level = "success"
        elif total >= dc - 3:  level = "partial_success"
        else:                  level = "failure"

        from .dice_labels import format_check as _fc
        self.log(_fc(intent.intent, stat, raw, mod, total, dc, level),
                 LOG_SYSTEM)

        # Determine drops by level
        drops = {}
        rare = {}
        if level in ("critical_success", "success", "partial_success"):
            for mat, span in (table.get("drops") or {}).items():
                lo, hi = (span if isinstance(span, list) else [span, span])
                qty = random.randint(int(lo), int(hi))
                # Partial = floor (qty/2); crit = qty + 1
                if level == "partial_success": qty = max(0, qty // 2)
                elif level == "critical_success": qty += 1
                if qty > 0:
                    drops[mat] = qty
            for mat, chance in (table.get("rare") or {}).items():
                if random.random() < float(chance):
                    rare[mat] = 1

        # Apply drops
        if drops or rare:
            materials.add_materials(ch, drops)
            materials.add_materials(ch, rare)
            row = ", ".join(f"{q}x {materials.get(k).name() if materials.get(k) else k}"
                            for k, q in {**drops, **rare}.items())
            self.log(t("feedback_salvage_got",
                       fallback=f"Zebrane: {row}", row=row),
                     LOG_SUCCESS)
            # Narrator hooks. Categorize by intent/target so the line roughly
            # fits what just happened. Each category degrades silently when no
            # locale entry exists.
            ttags = target.tags or []
            if intent.intent == "harvest" or "corpse" in ttags:
                if target.entity_type == "monster" or "monster_remains" in ttags:
                    narr_cat = "monster_harvest"
                elif "crawler" in ttags:
                    narr_cat = "crawler_corpse_looted"
                else:
                    narr_cat = "corpse_harvest"
            elif any(tg in ttags for tg in ("furniture",)):
                narr_cat = "furniture_salvage"
            elif any(tg in ttags for tg in ("bathroom", "fixture", "toilet")):
                narr_cat = "bathroom_salvage"
            elif any(tg in ttags for tg in ("camera", "terminal", "panel",
                                            "machine", "electrical", "vending")):
                narr_cat = "tech_salvage"
            else:
                narr_cat = "salvage_success"
            nline = narrate(narr_cat)
            if nline:
                self.log(nline, LOG_SYNDIC)
            # Rare material narrator line if any "rare" drop appeared
            if rare:
                rline = narrate("rare_material_found")
                if rline:
                    self.log(rline, LOG_SYNDIC)
            # Achievements + counter gates. All best-effort.
            try:
                from ..systems import achievements
                achievements.unlock(ch, "wszystko_jest_surowcem", world=self.world)
                if narr_cat == "furniture_salvage":
                    achievements.unlock(ch, "meble_tez_krwawia", world=self.world)
                if narr_cat in ("corpse_harvest", "monster_harvest",
                                "crawler_corpse_looted"):
                    achievements.unlock(ch, "rozbiorka_zwlok", world=self.world)
                if narr_cat == "tech_salvage":
                    achievements.unlock(ch, "technicznie_to_loot", world=self.world)
                if is_owned and "bathroom" in ttags:
                    achievements.unlock(ch, "kradziez_armatury", world=self.world)
                if is_owned and ("sponsor" in ttags or "camera" in ttags):
                    achievements.unlock(ch, "sponsor_nie_pochwala", world=self.world)
                count_salvage = achievements.bump_counter(ch, "salvage_ops_count", 1)
                if count_salvage == 5:
                    achievements.unlock(ch, "recykling_agresywny", world=self.world)
                if count_salvage == 20:
                    achievements.unlock(ch, "ekonomia_przetrwania", world=self.world)
            except Exception:
                pass

        # Time + noise
        ts.advance(self.world, int(table.get("time_minutes", 15)))
        room = self.world.current_floor.current_room()
        self._bump_threat(int(table.get("noise", 1)),
                          source="salvage", room=room)

        # Mark entity depleted/stripped (no farming)
        target.state = state
        if level in ("critical_success", "success"):
            target.state["stripped"] = True
            target.state["depleted"] = True
        elif level == "partial_success":
            target.state["damaged"] = True
        # Failure leaves entity intact but the player loses time

        # Apply risks through the risk_reward mapper (uses shared consequence engine)
        risks = list(table.get("risks", []))
        if level == "critical_failure":
            risks.extend(["self_damage"])
        risk_effs = risk_reward.risk_effects(risks)
        if risk_effs:
            lines = apply(risk_effs, self.world, time_system=ts)
            for ln in lines: self.log(str(ln), LOG_WARN)

        # Affinity nudge: salvage feeds survival
        ch.affinity["survival"] = ch.affinity.get("survival", 0) + 1

    # ── Prompt 24 — corpse handlers ─────────────────────────────────────
    def _attempt_butcher_corpse(self, intent):
        target = self._resolve_corpse_target(intent)
        if target is None:
            return
        self._run_butcher(target)
    def _attempt_eat_corpse(self, intent):
        from . import corpses as _cp
        from . import time_system as ts
        target = self._resolve_corpse_target(intent)
        if target is None:
            return
        ch = self.world.character
        result = _cp.eat(self.world, target, ch)
        if not result.ok:
            self.log(result.message, LOG_WARN)
            return

        # Flavor.
        if result.hp_delta > 0:
            self.log(t("feedback_eat_corpse_heal",
                       fallback=f"Zjadasz. Trochę lepiej. (+{result.hp_delta} HP)",
                       hp=result.hp_delta), LOG_SUCCESS)
        elif result.hp_delta < 0:
            self.log(t("feedback_eat_corpse_hurt",
                       fallback=f"Zjadasz. Żołądek protestuje. ({result.hp_delta} HP)",
                       hp=result.hp_delta), LOG_WARN)
        else:
            self.log(t("feedback_eat_corpse_neutral",
                       fallback="Zjadasz. Smak ciężko opisać. Posila."),
                     LOG_NORMAL)
        if result.status_applied:
            self.log(t("feedback_eat_status",
                       fallback=f"Łapiesz: {result.status_applied}.",
                       status=result.status_applied), LOG_WARN)

        # Time + tag bus.
        ts.advance(self.world, 5)
        try:
            from . import sponsors as _sp
            if result.audience_tag:
                _sp.note_player_tag(self.world, result.audience_tag, weight=2)
            if result.cannibal_tag:
                _sp.note_player_tag(self.world, result.cannibal_tag, weight=3)
        except Exception:
            pass
    def _attempt_craft(self, intent):
        """Try a known recipe by name, otherwise improvise by category from the player's text."""
        from ..content import crafting
        from ..content import materials
        from ..systems import risk_reward
        from .consequences import apply
        from . import time_system as ts
        from .utils_compat import roll_d20
        import random

        text = (intent.raw_text or "").lower()
        tokens = [tok.strip(",.!?") for tok in text.split()]

        # Pass 1: exact recipe key match
        rec_keys = list(crafting.all_recipes().keys())
        plan = None
        for rk in rec_keys:
            if rk in text:
                plan = crafting.try_known_recipe(self.world.character, rk)
                break

        # Pass 2: name match in Polish
        if plan is None:
            for rk, rv in crafting.all_recipes().items():
                nm = (rv.get("name_pl","") or "").lower()
                if nm and nm in text:
                    plan = crafting.try_known_recipe(self.world.character, rk)
                    break

        # Pass 2b: alias match (Gap 6). Each recipe may declare aliases_pl /
        # aliases_en so "pułapka elektryczna" routes to shock_trap, "nóż" to
        # shiv, etc. We ASCII-fold both sides and match alias stems against
        # input stems so Polish case-endings (pułapka/pułapkę/pułapką) all
        # hit. Longest alias wins to avoid "linka" beating "linka potykająca".
        if plan is None:
            from .affordances import fold as _fold
            folded_text = _fold(text)
            text_stems = [w[:4] for w in folded_text.split() if len(w) >= 3]
            alias_hits = []
            for rk, rv in crafting.all_recipes().items():
                for al in (rv.get("aliases_pl") or []) + (rv.get("aliases_en") or []):
                    if not al: continue
                    af = _fold(al)
                    if af in folded_text:
                        alias_hits.append((len(af) + 10, rk)); continue
                    # Per-word stem match: every word in the alias must have a
                    # matching 4-char-prefix stem in the input.
                    al_words = [w for w in af.split() if len(w) >= 3]
                    if al_words and all(any(s.startswith(w[:4]) or w.startswith(s)
                                            for s in text_stems)
                                         for w in al_words):
                        alias_hits.append((len(af), rk))
            if alias_hits:
                alias_hits.sort(reverse=True)
                plan = crafting.try_known_recipe(self.world.character, alias_hits[0][1])

        # Pass 3: improvise by category keyword
        if plan is None:
            cat_keywords = {
                "trap":        ["pułap","pulap","trap"],
                "weapon":      ["broń","bron","włóczni","wlocz","nóż","noz","spear","weapon","oręż","orez"],
                "distraction": ["dystrak","wabik","bait","decoy","odwrócenie","odwrocenie"],
                "tool":        ["narzęd","narzed","lockpick","wytrych","tool"],
                "disguise":    ["przebran","mund","disguise","badge","plakiet"],
            }
            chosen = None
            for cat, cues in cat_keywords.items():
                if any(c in text for c in cues):
                    chosen = cat; break
            if chosen is None:
                self.log(t("feedback_craft_unknown",
                           fallback="Nie rozumiem co próbujesz zrobić. Spróbuj: pułapka / broń / dystrakcja / narzędzie / przebranie."),
                         LOG_WARN)
                # Narrator commentary on absurd / unparseable craft attempts.
                nline = narrate("absurd_craft_attempt")
                if nline:
                    self.log(nline, LOG_SYNDIC)
                return
            plan = crafting.try_improvise(self.world.character, chosen)

        if not plan["valid"]:
            self.log(plan.get("fallback_message", "—"), LOG_WARN); return

        # Run the stat check
        stat = plan["stat"]; dc = plan["dc"]
        raw = roll_d20()
        mod = self.world.character.stat_mod(stat)
        total = raw + mod
        if   raw == 20:        level = "critical_success"
        elif raw == 1:         level = "critical_failure"
        elif total >= dc + 5:  level = "critical_success"
        elif total >= dc:      level = "success"
        elif total >= dc - 3:  level = "partial_success"
        else:                  level = "failure"
        from .dice_labels import (stat_pl as _spl, level_pl as _lpl)
        self.log(f"  [rzemiosło:{plan['category_label_pl']}] d20({raw}) + "
                 f"{_spl(stat)}({mod:+d}) = {total} vs TT {dc} → {_lpl(level)}",
                 LOG_SYSTEM)

        # Materials: consume on success/partial; half-waste on failure; full loss on crit-fail
        if level in ("critical_success", "success", "partial_success"):
            crafting.consume_for(plan, self.world.character)
        elif level == "failure":
            crafting.waste_for(plan, self.world.character)
        else:   # critical_failure
            crafting.consume_for(plan, self.world.character)

        ts.advance(self.world, plan["time_cost"])

        # Produce result item on success / crit-success / partial.
        # P29.14 — full 4-tier quality (masterwork / good / normal /
        # flawed) flows from the roll level. The crafting module
        # owns the mapping and the resulting Entity carries
        # state["quality"]; combat reads it when wielded.
        result_key = plan.get("result_item")
        if level in ("critical_success", "success", "partial_success") and result_key:
            quality = crafting.quality_for_level(level)
            ent = crafting.make_crafted_entity(
                result_key,
                quality=quality,
                damaged=(level == "partial_success"),
                unstable=(level == "partial_success" and random.random() < 0.4),
            )
            self.world.register(ent)
            self.world.character.inventory_ids.append(ent.entity_id)
            qlabel = crafting.quality_label_pl(quality)
            if qlabel:
                self.log(t("feedback_crafted_item_qual",
                           fallback=f"Wytworzone ({qlabel}): {ent.display_name()}",
                           quality=qlabel,
                           name=ent.display_name()), LOG_SUCCESS)
            else:
                self.log(t("feedback_crafted_item",
                           fallback=f"Wytworzone: {ent.display_name()}",
                           name=ent.display_name()), LOG_SUCCESS)
            # P29.15 — masterwork + branded-recipe achievements.
            try:
                from ..systems import achievements as _ach
                if quality == "masterwork":
                    _ach.unlock(self.world.character, "dzielo_mistrzowskie",
                                world=self.world)
                # Branded if the recipe has requires_sponsor_unlock set.
                from ..content.data.recipe_templates import RECIPES as _R
                rec_def = _R.get(plan.get("recipe_key") or "")
                if rec_def and rec_def.get("requires_sponsor_unlock"):
                    _ach.unlock(self.world.character, "markowy_uczestnik",
                                world=self.world)
            except Exception:
                pass

        # Risks on partial / failure / critical_failure
        if level in ("partial_success", "failure", "critical_failure"):
            risks = list(plan.get("risks", []))
            if level == "critical_failure":
                risks.extend(["self_damage", "unsafe_crafting"])
            effs = risk_reward.risk_effects(risks)
            if effs:
                lines = apply(effs, self.world, time_system=ts)
                for ln in lines: self.log(str(ln), LOG_WARN)

        # Affinity: crafting feeds crafting
        ch = self.world.character
        ch.affinity["crafting"] = ch.affinity.get("crafting", 0) + 1
        if plan["category"] == "trap":
            ch.affinity["trap"] = ch.affinity.get("trap", 0) + 1

        # Narrator hooks for crafting outcomes.
        narr_cat = {
            "critical_success": "craft_success",
            "success":          "craft_success",
            "partial_success":  "craft_partial",
            "failure":          "craft_fail",
            "critical_failure": "craft_critical_fail",
        }.get(level, "")
        if narr_cat:
            nline = narrate(narr_cat)
            if nline:
                self.log(nline, LOG_SYNDIC)
        # Result-flavor narrator (only on a successful build)
        if level in ("success", "critical_success", "partial_success"):
            cat = plan.get("category", "")
            cat_to_narr = {
                "trap":   "improvised_trap_created",
                "weapon": "improvised_weapon_created",
                "tool":   "improvised_tool_created",
            }
            extra = cat_to_narr.get(cat)
            if extra:
                line = narrate(extra)
                if line:
                    self.log(line, LOG_SYNDIC)
            if level == "partial_success":
                line = narrate("unstable_item_created")
                if line:
                    self.log(line, LOG_SYNDIC)

        # Achievements + counters
        try:
            from ..systems import achievements
            if level in ("success", "critical_success"):
                achievements.unlock(ch, "rzemieslnik_z_paniki", world=self.world)
                # Tag-based (improvised) recipe = no explicit recipe_key
                if not plan.get("recipe_key"):
                    achievements.unlock(ch, "przepis_jaki_przepis", world=self.world)
                # Crafting while a hostile is present in the current room
                room_ref = self.world.current_floor.current_room()
                if room_ref and any(
                        e.entity_type in ("monster", "crawler")
                        and getattr(e, "is_alive", lambda: True)()
                        for e in room_ref.entities):
                    achievements.unlock(ch, "inzynieria_odwagi", world=self.world)
                # Organic / corpse-derived crafting
                organic_mats = ("meat_chunk", "bone_fragments", "sinew",
                                "blood_sample", "viscera")
                if any(m in (plan.get("required_materials") or {})
                       for m in organic_mats):
                    achievements.unlock(ch, "obrzydliwe_ale_dziala", world=self.world)
                # Trash-tier material used in major action
                if any(m in (plan.get("required_materials") or {})
                       for m in ("tape", "cloth_strips", "screws")):
                    achievements.unlock(ch, "smiec_wartosciowy", world=self.world)
                # Ten crafted items
                count_craft = achievements.bump_counter(ch, "craft_ops_count", 1)
                if count_craft == 10:
                    achievements.unlock(ch, "zlota_raczka_lochu", world=self.world)
        except Exception:
            pass

    # ── Gap 4: deploy crafted/portable trap or device ────────────────────────
    def _attempt_break(self, intent):
        """Destroy a breakable object. Uses the validator for target
        resolution + affordance check, then a STR d20 vs DC 11 (lower for
        fragile entities). On success the entity's state["broken"] = True,
        the room gains noise, and salvageable entities also drop their
        salvage table contents. Crit fail damages the player.
        """
        from .validation import validate as validate_action
        from .consequences import apply
        from . import time_system as ts
        from ..systems import risk_reward
        from .utils_compat import roll_d20

        v = validate_action(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations), LOG_NORMAL)
            # P26c: latch disambiguation (break path).
            self._stash_disambiguation_on_invalid(v, intent)
            return

        target = v.matched_entities[0] if v.matched_entities else None
        if target is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego szukasz."), LOG_WARN)
            return

        # Already broken / stripped → quick refusal so the player isn't
        # confused by a noise-but-no-result outcome.
        st = target.state or {}
        if st.get("broken") or st.get("destroyed"):
            self.log(t("feedback_already_broken",
                       fallback=f"„{target.display_name()}” jest już rozbite.",
                       name=target.display_name()), LOG_WARN)
            return

        # DC adjustment based on tags.
        tags = set(target.tags or [])
        dc = 11
        if "fragile" in tags:           dc -= 3
        elif "heavy" in tags:           dc += 2
        elif "structural" in tags:      dc += 3
        if "metal" in tags and "thin" not in tags:
            dc += 2
        dc = max(6, dc)

        ch = self.world.character
        raw = roll_d20()
        mod = ch.stat_mod("STR")
        total = raw + mod
        if   raw == 20:       level = "critical_success"
        elif raw == 1:        level = "critical_failure"
        elif total >= dc + 5: level = "critical_success"
        elif total >= dc:     level = "success"
        elif total >= dc - 3: level = "partial_success"
        else:                 level = "failure"
        from .dice_labels import format_check as _fc
        self.log(_fc("break", "STR", raw, mod, total, dc, level),
                 LOG_SYSTEM)

        ts.advance(self.world, 4)
        room = self.world.current_floor.current_room() if self.world.current_floor else None

        if level in ("critical_success", "success"):
            target.state = {**(target.state or {}), "broken": True, "destroyed": True}
            self.log(t("feedback_break_ok",
                       fallback=f"Rozbijasz „{target.display_name()}”.",
                       name=target.display_name()), LOG_SUCCESS)
            self._bump_threat(2 if level == "critical_success" else 3,
                              source="break", room=room)
            # Prompt 22 bug fix: break needs CONSEQUENCES — audience
            # reacts (it's a spectacle), and breaking sponsor property
            # emits the right tags so the sponsor system notices. The
            # tag bus already plumbs these to all 6 sponsors.
            from . import audience as _aud
            from . import sponsors as _sp
            _aud.change_audience(self.world,
                                 2 if level == "critical_success" else 1,
                                 source="break")
            _sp.note_player_tag(self.world, "spectacle", weight=1)
            # Was it sponsor property? Look at tags / state.
            is_sponsor_property = (
                "sponsor" in tags or "sponsor_property" in tags or
                (target.state or {}).get("sponsor_owned")
            )
            if is_sponsor_property:
                _sp.note_player_tag(self.world, "sponsor_property_damage",
                                    weight=2)
                line = narrate("sponsor_files_complaint") or \
                       narrate("sponsor_property_salvage")
                if line:
                    self.log(line, LOG_SYNDIC)
            # Prompt 14: if we broke a synthetic door, unlock the exit it
            # represented so the player can now walk through.
            if target.key == "_synth_door":
                label = (target.state or {}).get("label")
                if room and label and label in room.exits:
                    room.exits[label]["locked"] = False
                    room.exits[label]["fallback_hint"] = "Drzwi rozbite — przejście wolne."
            # Salvageable? Drop materials via the existing salvage path.
            if "salvageable" in tags or "salvage" in (target.affordances or []):
                table_key = _pick_salvage_table_key(target)
                if table_key:
                    from ..content.data.salvage_tables import SALVAGE_TABLES
                    from ..content import materials as _mat
                    table = SALVAGE_TABLES.get(table_key, {})
                    import random as _r
                    drops = {}
                    for matkey, span in (table.get("drops") or {}).items():
                        lo, hi = (span if isinstance(span, list) else [span, span])
                        # Break is brutal — yields half of a clean salvage,
                        # but always at least 1 unit if any range > 0.
                        qty = max(0, _r.randint(int(lo), int(hi)) // 2)
                        if qty <= 0 and hi > 0:
                            qty = 1
                        if qty > 0:
                            drops[matkey] = qty
                    if drops:
                        _mat.add_materials(ch, drops)
                        row = ", ".join(f"{q}x {(_mat.get(k).name() if _mat.get(k) else k)}"
                                        for k, q in drops.items())
                        self.log(t("feedback_break_salvage",
                                   fallback=f"Z resztek wyciągasz: {row}", row=row),
                                 LOG_NORMAL)
                    target.state["stripped"] = True
                    target.state["depleted"] = True
            else:
                # Prompt 22 bug fix: even non-salvageable objects yield
                # debris when broken — at least 1-2 generic scraps based
                # on dominant material tag. Otherwise the player gets
                # zero feedback that anything happened (other than the
                # break-success line).
                from ..content import materials as _mat
                import random as _r
                debris_key = None
                if "glass" in tags or "fragile" in tags:
                    debris_key = "glass_shards"
                elif "plastic" in tags or "synthetic" in tags:
                    debris_key = "plastic_shards"
                elif "wood" in tags:
                    debris_key = "wood_fragments"
                elif "electronic" in tags or "electrical" in tags or \
                     "sponsor" in tags:
                    debris_key = "circuit_board"
                elif "metal" in tags:
                    debris_key = "scrap_metal"
                else:
                    debris_key = "scrap_metal"   # neutral default
                qty = 1 if level == "success" else _r.randint(1, 2)
                if _mat.get(debris_key):
                    _mat.add_materials(ch, {debris_key: qty})
                    mname = _mat.get(debris_key).name()
                    self.log(t("feedback_break_debris",
                               fallback=f"Z odłamków zbierasz: {qty}x {mname}.",
                               qty=qty, name=mname),
                             LOG_NORMAL)
                target.state["stripped"] = True
                target.state["depleted"] = True
        elif level == "partial_success":
            target.state = {**(target.state or {}), "damaged": True}
            self.log(t("feedback_break_partial",
                       fallback=f"„{target.display_name()}” pęka, ale trzyma się jeszcze w jednym kawałku.",
                       name=target.display_name()), LOG_WARN)
            self._bump_threat(1, source="break_partial", room=room)
        elif level == "failure":
            self.log(t("feedback_break_fail",
                       fallback=f"Nie udaje ci się rozbić „{target.display_name()}”. Sprzęt cię wyśmiewa.",
                       name=target.display_name()), LOG_WARN)
            self._bump_threat(1, source="break_fail", room=room)
        else:   # critical_failure
            self.log(t("feedback_break_critfail",
                       fallback=f"Coś trzeszczy — głównie ty. Cios odbija ci się rykoszetem.",
                       name=target.display_name()), LOG_DANGER)
            ch.take_damage(1)
            self._bump_threat(2, source="break_critfail", room=room)
            if self._check_player_dead("break_critfail",
                                       "od rykoszetu własnego rozbijania"):
                return

        # Affinity nudge for environment plays.
        ch.affinity["environment"] = ch.affinity.get("environment", 0) + 1

    # ── P29.39: force / wyłam — locked-exit handler ─────────────────────────
    def _attempt_force(self, intent):
        """„Wyłam X" — siłowe otwarcie zamkniętych drzwi (locked exit).
        Validator (od P29.39) potrafi znaleźć synth_door dla podanego
        labela. Tutaj robimy STR check vs DC 14 i, na sukces,
        odblokowujemy konkretne wyjście (`room.exits[label]["locked"]
        = False`).

        Crit fail → uderzasz w futrynę zamiast w zamek, mała szkoda
        na HP i bump threatu (hałas).
        """
        from .validation import validate as validate_action
        from . import time_system as ts
        from .utils_compat import roll_d20
        from .dice_labels import format_check as _fc

        v = validate_action(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations),
                         LOG_NORMAL)
            self._stash_disambiguation_on_invalid(v, intent)
            return

        target = v.matched_entities[0] if v.matched_entities else None
        if target is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego "
                                "szukasz."), LOG_WARN)
            return

        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            self.log("Nie jesteś nigdzie.", LOG_WARN); return

        # Synth-door dla wyjścia: spróbuj odblokować po labelu.
        is_synth = (target.key == "_synth_door")
        st = target.state or {}
        label = st.get("label") if is_synth else None
        ed = (room.exits.get(label) if label else None)

        # Czy to w ogóle locked? Jeśli nie — nie ma co wyłamywać.
        if is_synth and ed is not None and not ed.get("locked"):
            self.log(t("feedback_force_already_open",
                       fallback=(f'„{label}" — nie zamknięte. '
                                 f'Możesz po prostu wejść.')),
                     LOG_WARN)
            return
        if not is_synth:
            tags = set(target.tags or [])
            if "locked" not in tags:
                self.log(t("feedback_force_not_locked",
                           fallback=(f'„{target.display_name()}" '
                                     f'nie jest zamknięte na klucz '
                                     f'— nic do wyłamywania.')),
                         LOG_WARN)
                return

        # STR check vs DC 14 (base z affordance.force).
        ch = self.world.character
        raw = roll_d20()
        mod = ch.stat_mod("STR")
        total = raw + mod
        dc = 14
        # Lekkie modyfikatory dla synth_door: tagi z exit-template
        # mogą zaostrzyć DC, ale na razie trzymamy bazę 14.
        if   raw == 20:       level = "critical_success"
        elif raw == 1:        level = "critical_failure"
        elif total >= dc + 5: level = "critical_success"
        elif total >= dc:     level = "success"
        elif total >= dc - 3: level = "partial_success"
        else:                 level = "failure"
        self.log(_fc("force", "STR", raw, mod, total, dc, level),
                 LOG_SYSTEM)

        ts.advance(self.world, 10)

        if level in ("critical_success", "success"):
            # Odblokuj exit jeśli mamy label, albo zmień stan entity.
            if label and ed is not None:
                ed["locked"] = False
                ed["fallback_hint"] = "Drzwi wyłamane — przejście wolne."
            if is_synth:
                target.tags = [tt for tt in (target.tags or [])
                               if tt != "locked"]
                target.state = {**st, "locked": False, "forced": True}
            self.log(t("feedback_force_ok",
                       fallback=("Stalowa futryna ustępuje z protestem "
                                 "— przejście wolne.")),
                     LOG_SUCCESS)
            self._bump_threat(
                2 if level == "critical_success" else 3,
                source="force_door", room=room)
            # Spektakl: widownia lubi, kiedy ktoś używa pleców
            # zamiast łomu.
            try:
                from . import audience as _aud
                _aud.change_audience(
                    self.world,
                    2 if level == "critical_success" else 1,
                    source="force")
                from . import sponsors as _sp
                _sp.note_player_tag(self.world, "spectacle", weight=1)
            except Exception:
                pass
        elif level == "partial_success":
            # Pęknięta futryna — locked nadal, ale następna próba
            # ma -2 do DC. Trzymamy na entity, nie na exit, bo
            # exit dict nie ma miejsca na to.
            if is_synth:
                target.state = {**st, "damaged": True}
            self.log(t("feedback_force_partial",
                       fallback="Futryna pęka, ale zamek wciąż "
                                "trzyma. Następnym razem pójdzie "
                                "łatwiej."), LOG_WARN)
            self._bump_threat(2, source="force_partial", room=room)
        elif level == "failure":
            self.log(t("feedback_force_fail",
                       fallback="Naparzasz w futrynę. Boli. Drzwi "
                                "ani drgnęły."), LOG_WARN)
            self._bump_threat(1, source="force_fail", room=room)
        else:   # critical_failure
            self.log(t("feedback_force_critfail",
                       fallback="Plecy strzeliły ci jak suchy patyk. "
                                "Drzwi nawet nie zauważyły."),
                     LOG_DANGER)
            ch.take_damage(2)
            self._bump_threat(3, source="force_critfail", room=room)
            if self._check_player_dead("force_critfail",
                                       "od własnego barku w futrynę"):
                return

        # Affinity: wyłom to brudna mechanika otoczenia.
        ch.affinity["environment"] = ch.affinity.get("environment", 0) + 1

    # ── Prompt 16: mass-action handlers ─────────────────────────────────────
    def _attempt_mass_salvage(self, intent):
        """Dismantle every salvageable visible entity in the room.

        Skips: safehouse-owned (with note), structural, locked exits,
        already-stripped/depleted/destroyed entities, terminals (require
        tool), and creatures.  Accumulates time, noise, materials, and
        social risk via the existing salvage path."""
        from . import time_system as ts
        from ..content import materials as _mat
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        self.log(t("feedback_mass_salvage_intro",
                   fallback="Zaczynasz metodyczną rozbiórkę pomieszczenia."),
                 LOG_SYSTEM)

        salvaged: list[str] = []
        skipped: list[str] = []
        warned_safehouse = False
        total_minutes = 0
        # Snapshot the candidates BEFORE iteration so we don't loop on
        # newly-revealed entities (e.g. a synthesized door we create).
        candidates = [e for e in list(room.visible_entities())
                      if e.entity_type not in ("monster", "crawler", "npc")
                      and e.entity_type != "door"]
        for ent in candidates:
            name = ent.display_name()
            tags = set(ent.tags or [])
            affs = set(ent.affordances or [])
            st = ent.state or {}
            # P26c — appropriate-target gate: never try to "salvage"
            # things that aren't salvageable. Hazards (acid puddle,
            # gas cloud), liquids, and creatures-of-flesh that aren't
            # corpses get skipped silently. Without this gate, mass
            # salvage cheerfully tried to disassemble „kałuża kwasu”
            # and produced absurd materials.
            if ent.entity_type == "hazard" or "hazard" in tags:
                continue
            if "liquid" in tags and not ({"container"} & tags):
                continue
            # Must have a salvage pathway (affordance OR salvageable tag).
            if "salvage" not in affs and "salvageable" not in tags \
                    and "corpse" not in tags \
                    and ent.entity_type != "corpse":
                # Silent skip — not every visible thing is fair game
                # for `zdemontuj wszystko`. Only mention it if it has
                # NO obvious "this could be useful" hint at all.
                continue
            if st.get("stripped") or st.get("depleted") or st.get("destroyed"):
                skipped.append(f"{name}: już rozebrane")
                continue
            if "structural" in tags:
                skipped.append(f"{name}: to część konstrukcji")
                continue
            if ent.entity_type == "terminal" and "salvageable" not in tags:
                skipped.append(f"{name}: wymaga narzędzi")
                continue
            owned_safehouse = (st.get("owned_by") == "safehouse"
                               or st.get("theft_sensitive") is True)
            if owned_safehouse and not warned_safehouse:
                # Surface the social cost once, then continue — the player
                # explicitly chose mass salvage.
                self.log(t("feedback_mass_salvage_safehouse_warn",
                           fallback="Część tych rzeczy należy do kryjówki — będą konsekwencje."),
                         LOG_WARN)
                warned_safehouse = True
            table_key = _pick_salvage_table_key(ent)
            if not table_key and "salvageable" not in tags:
                skipped.append(f"{name}: nie ma z czego ciągnąć surowców")
                continue
            # Reuse the existing salvage path so social/audience/risk
            # consequences flow through the canonical handler.
            self._do_single_salvage(ent, mute_narrator=True)
            mark = ", ".join(self._last_salvage_row) if self._last_salvage_row else ""
            if mark:
                salvaged.append(f"{name}: {mark}")
            else:
                skipped.append(f"{name}: nic użytecznego")
            total_minutes += int(self._last_salvage_minutes or 8)

        # Summary.
        if salvaged:
            self.log(t("feedback_mass_salvage_results_h",
                       fallback="Rozebrano:"), LOG_SUCCESS)
            for row in salvaged:
                self.log(f"  • {row}", LOG_NORMAL)
        if skipped:
            self.log(t("feedback_mass_salvage_skipped_h",
                       fallback="Pominięto:"), LOG_WARN)
            for row in skipped:
                self.log(f"  · {row}", LOG_NORMAL)
        if not salvaged and not skipped:
            self.log(t("feedback_mass_salvage_nothing",
                       fallback="Nie widzisz tu niczego, co da się sensownie rozebrać."),
                     LOG_WARN)
            return
        # Big noise + time on top of per-entity bumps already applied.
        self._bump_threat(min(5, len(salvaged)),
                          source="mass_salvage", room=room)
        self.log(t("feedback_mass_salvage_summary",
                   fallback=f"Czas: ok. {total_minutes} min. Hałas: wysoki.",
                   minutes=total_minutes),
                 LOG_SYSTEM)
        # Prompt 18: mass-salvage is the recycling-cult headline move and
        # also drives audience. Emit the tags + audience bump once per
        # batch (per-item single-salvage already books smaller bumps).
        from . import audience as _aud
        from . import sponsors as _sp
        _aud.change_audience(self.world, 2, source="mass_salvage")
        _sp.note_player_tag(self.world, "mass_salvage", weight=2)
        _sp.note_player_tag(self.world, "salvage", weight=1)
        _sp.maybe_intervene(self.world)
    def _attempt_distract(self):
        """P29.68 — `odwróć uwagę` / `hałasuj`: emituje bodziec HAŁASU.
        Moby reagują WEDŁUG PROFILU (ciekawski rusza ku, płochliwy
        pierzcha, agresywny szarżuje na wabik, obojętny ignoruje). Hałas
        = narzędzie, nie kara. Reakcje zabierają mobowi turę przeciw
        graczowi."""
        from . import systemic as _sys
        from . import combat as _cmb
        from . import time_system as _ts
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."),
                     LOG_WARN)
            return
        self.log(t("feedback_distract_intro",
                   fallback="Robisz raban — łomot, krzyk, cokolwiek ściągnie "
                            "albo odciągnie uwagę."), LOG_SYSTEM)
        hostiles = _cmb.alive_hostiles_in(room)
        if not hostiles:
            self.log("  Cisza. Nikt nie nadstawia ucha.", LOG_NORMAL)
        else:
            for ent in hostiles:
                r = _sys.apply_stimulus(ent, "hałas")
                for ln in r.lines:
                    self.log("  " + ln,
                             LOG_SUCCESS if r.matched else LOG_NORMAL)
        cs = _cmb.get_combat(room)
        if cs is not None:
            cs.last_action = "distract"
            self._combat_after_player_action(cs)
        else:
            try:
                _ts.advance(self.world, 1)
            except Exception:
                pass
    def _attempt_cast(self, intent):
        """P29.67 — `czaruj <szkoła> [w/na cel]`. Czar produkuje sygnał,
        który silnik systemowy rozstrzyga jak fizykę (materia / psyche).
        Mana gating + nauka zaklęć w engine.magic."""
        from . import magic as _magic
        from . import combat as _cmb
        from .validation import _resolve_entities
        ch = self.world.character
        school = _magic.resolve_school(getattr(intent, "tool", None))
        if school is None:
            self.log(t("feedback_cast_unknown_school",
                       fallback="Nie znasz takiego zaklęcia."), LOG_WARN)
            return
        spec = _magic.SPELLS[school]
        name = spec["name"]
        if not _magic.knows(ch, school):
            self.log(t("feedback_cast_not_learned",
                       fallback=f"Nie umiesz rzucić „{name}”. Nie nauczyłeś "
                                f"się tej sztuki."), LOG_WARN)
            return
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        target = None
        if intent.targets and room is not None:
            cands = _resolve_entities(room, intent.targets[0])
            target = cands[0] if cands else None
        if target is None:
            self.log(t("feedback_cast_no_target",
                       fallback=f"Na kogo rzucasz „{name}”? Wskaż cel."),
                     LOG_WARN)
            return
        if _magic.mana(ch) < int(spec["mana"]):
            self.log(t("feedback_cast_no_mana",
                       fallback=f"Za mało many na „{name}” "
                                f"(masz {_magic.mana(ch)}/{int(spec['mana'])})."),
                     LOG_WARN)
            return

        victim_name = target.display_name()
        res = _magic.cast(self.world, school, ch, target)
        for ln in res.lines:
            self.log(ln, LOG_SUCCESS)
        self.log(f"  Mana: {_magic.mana(ch)}/"
                 f"{(ch.flags or {}).get('max_mana', 0)}.", LOG_SYSTEM)
        if not target.is_alive() and getattr(target, "max_hp", 0) > 0:
            self.log(f"„{victim_name}” pada.", LOG_SUCCESS)
            try:
                from . import corpses as _cp
                _cp.transform_to_corpse(self.world, target, killer=ch)
            except Exception:
                pass
        # Tura wroga, jeśli walka aktywna.
        cs = _cmb.get_combat(room) if room is not None else None
        if cs is not None:
            cs.last_action = f"cast:{school}"
            self._combat_after_player_action(cs)
    def _attempt_examine_room(self):
        """P29.64 — `zbadaj pomieszczenie`: zunifikowane odkrycie
        OTOCZENIA. Czytelny przegląd: ISTOTY, ŚRODOWISKO (z właściwościami
        ujawnionymi przez silnik systemowy — gracz dedukuje użycie, nie
        dostaje gotowego przepisu) i WYJŚCIA. To OBSERWACJA, nie loot —
        `przeszukaj` zostaje na przeszukiwanie pojemników."""
        from . import systemic as _sys
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."),
                     LOG_WARN)
            return
        self.log(t("examine_room_header",
                   fallback="Lustrujesz otoczenie — co tu można wykorzystać."),
                 LOG_SYSTEM)
        ents = list(room.visible_entities())
        beings = [e for e in ents
                  if e.entity_type in ("monster", "crawler", "npc")
                  and e.is_alive()]
        env = [e for e in ents
               if e.entity_type not in ("monster", "crawler", "npc")]
        any_section = False
        if beings:
            any_section = True
            self.log("ISTOTY:", LOG_NORMAL)
            for e in beings:
                self.log(f"  • {e.display_name()}", LOG_NORMAL)
        observed: list = []   # (nazwa, [obserwacje]) — dla podszeptu percepcji
        if env:
            any_section = True
            self.log("ŚRODOWISKO:", LOG_NORMAL)
            for e in env:
                obs = _sys.salient_observations(e)
                if obs:
                    observed.append((e.display_name(), obs))
                    self.log(f"  • {e.display_name()} — {'; '.join(obs)}",
                             LOG_SUCCESS)
                else:
                    self.log(f"  • {e.display_name()}", LOG_NORMAL)
        exits = [(lbl, ed) for lbl, ed in (room.exits or {}).items()
                 if not ed.get("hidden")]
        if exits:
            any_section = True
            self.log("WYJŚCIA:", LOG_NORMAL)
            for lbl, ed in exits:
                lock = " (zamknięte)" if ed.get("locked") else ""
                self.log(f"  • {lbl}{lock}", LOG_NORMAL)
        if not any_section:
            self.log("  Pusto. Goła podłoga i twój własny oddech.",
                     LOG_NORMAL)
        # P29.64b — głos bohatera: monolog per origin + podszept percepcji
        # (spostrzegawczy dostaje konkretną wskazówkę; reszta — przeczucie).
        try:
            from . import voice as _voice
            ch = self.world.character
            line = _voice.monologue(ch, "examine")
            if line:
                self.log(f"  „{line}”", LOG_SYSTEM)
            hint = _voice.perception_hint(ch, observed)
            if hint:
                self.log(f"  ({hint})", LOG_SYSTEM)
        except Exception:
            pass
    def _attempt_mass_search(self, intent):
        """Search every visible container/corpse/drawer/shelf in the room."""
        from . import time_system as ts
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        self.log(t("feedback_mass_search_intro",
                   fallback="Przeszukujesz wszystko, co wygląda na warte uwagi."),
                 LOG_SYSTEM)
        searched: list[str] = []
        skipped: list[str] = []
        for ent in list(room.visible_entities()):
            tags = set(ent.tags or [])
            st = ent.state or {}
            if st.get("searched") or st.get("looted"):
                skipped.append(f"{ent.display_name()}: już przeszukane")
                continue
            if not (("container" in tags) or ("corpse" in tags)
                    or ("drawer" in tags) or ("shelf" in tags)
                    or ent.entity_type == "corpse"):
                continue
            st["searched"] = True
            ent.state = st
            # Surface entity name as discovered. Containers without explicit
            # loot tables still count as searched (player learned: nothing).
            searched.append(ent.display_name())
        ts.advance(self.world, max(4, 2 * len(searched)))
        if searched:
            self.log(t("feedback_mass_search_results_h",
                       fallback="Przeszukano:"), LOG_SUCCESS)
            for row in searched:
                self.log(f"  • {row}", LOG_NORMAL)
        if skipped:
            self.log(t("feedback_mass_search_skipped_h",
                       fallback="Pominięto:"), LOG_NORMAL)
            for row in skipped:
                self.log(f"  · {row}", LOG_DIM if hasattr(self, "LOG_DIM") else LOG_NORMAL)
        if not searched and not skipped:
            self.log(t("feedback_mass_search_nothing",
                       fallback="Nie widzisz tu nic, co dałoby się sensownie przeszukać."),
                     LOG_WARN)
    def _attempt_mass_loot(self, intent, mode: str = "take"):
        """Take every portable visible item that isn't owned. `mode`:
            "take"  — generic 'weź wszystko' over loose visible items
            "loot"  — 'ograb wszystko' — same plus container/corpse loot,
                      and warns about safehouse property explicitly."""
        from . import time_system as ts
        ch = self.world.character
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        self.log(t("feedback_mass_loot_intro",
                   fallback="Bierzesz wszystko, co da się unieść."),
                 LOG_SYSTEM)
        taken: list[str] = []
        skipped: list[str] = []
        warned_safehouse = False
        for ent in list(room.visible_entities()):
            tags = set(ent.tags or [])
            st = ent.state or {}
            if not ent.portable:
                if mode == "loot" and ent.entity_type == "corpse" and not st.get("looted"):
                    st["looted"] = True; ent.state = st
                    taken.append(f"{ent.display_name()} (przeszukane)")
                else:
                    if "fixture" in tags or "structural" in tags or \
                       ent.entity_type in ("door","terminal"):
                        skipped.append(f"{ent.display_name()}: nie jest przenośne")
                continue
            owned = (st.get("owned_by") == "safehouse"
                     or st.get("theft_sensitive") is True)
            if owned and not warned_safehouse:
                self.log(t("feedback_mass_loot_safehouse_warn",
                           fallback="Niektóre z tych rzeczy należą do kryjówki — ktoś patrzy."),
                         LOG_WARN)
                warned_safehouse = True
            # Move into inventory.
            try:
                room.remove_entity(ent)
            except Exception:
                pass
            ent.location_id = "inventory:player"
            ch.inventory_ids.append(ent.entity_id)
            taken.append(ent.display_name())
            if owned:
                ch.flags["safehouse_theft_warnings"] = int(
                    ch.flags.get("safehouse_theft_warnings", 0)) + 1
        ts.advance(self.world, max(2, len(taken)))
        if taken:
            self.log(t("feedback_mass_loot_results_h",
                       fallback="Zabrane:"), LOG_SUCCESS)
            for row in taken:
                self.log(f"  • {row}", LOG_NORMAL)
        if skipped:
            self.log(t("feedback_mass_loot_skipped_h",
                       fallback="Pominięto:"), LOG_WARN)
            for row in skipped:
                self.log(f"  · {row}", LOG_NORMAL)
        if not taken and not skipped:
            self.log(t("feedback_mass_loot_nothing",
                       fallback="Nic tu się nie nadaje do zabrania."),
                     LOG_WARN)
    def _attempt_mass_break(self, intent):
        """Smash every visibly fragile / clearly-breakable thing. Safe
        minimal version: only targets entities tagged fragile / glass /
        ceramic / destructible that are NOT structural and NOT owned by
        safehouse / sponsor — owned items get a warning + are skipped to
        keep this safe-minimal."""
        from . import time_system as ts
        from ..content import materials as _mat
        from ..content.data.salvage_tables import SALVAGE_TABLES
        import random as _r
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        self.log(t("feedback_mass_break_intro",
                   fallback="Rozglądasz się, biorąc głęboki oddech. To narobi hałasu."),
                 LOG_SYSTEM)
        ch = self.world.character
        broken: list[str] = []
        skipped: list[str] = []
        for ent in list(room.visible_entities()):
            tags = set(ent.tags or [])
            st = ent.state or {}
            if ent.entity_type in ("monster", "crawler", "npc"):
                continue
            if "structural" in tags:
                skipped.append(f"{ent.display_name()}: część konstrukcji")
                continue
            if st.get("broken") or st.get("destroyed"):
                continue
            if (st.get("owned_by") == "safehouse" or st.get("theft_sensitive")):
                skipped.append(f"{ent.display_name()}: ktoś patrzy")
                continue
            destructive_tags = {"fragile","glass","ceramic","destructible","thin"}
            if not (tags & destructive_tags):
                continue
            st["broken"] = True; st["destroyed"] = True
            ent.state = st
            # Brutal break — partial salvage if a table exists.
            table_key = _pick_salvage_table_key(ent)
            row = []
            if table_key:
                table = SALVAGE_TABLES.get(table_key, {})
                drops = {}
                for matkey, span in (table.get("drops") or {}).items():
                    lo, hi = (span if isinstance(span, list) else [span, span])
                    qty = max(0, _r.randint(int(lo), int(hi)) // 3)
                    if qty > 0:
                        drops[matkey] = qty
                if drops:
                    _mat.add_materials(ch, drops)
                    row = [f"{q}x {(_mat.get(k).name() if _mat.get(k) else k)}"
                           for k, q in drops.items()]
                st["stripped"] = True; st["depleted"] = True
            broken.append(ent.display_name() + (f" ({', '.join(row)})" if row else ""))
        ts.advance(self.world, max(3, 2 * len(broken)))
        self._bump_threat(min(8, 2 * len(broken)),
                          source="mass_break", room=room)
        if broken:
            self.log(t("feedback_mass_break_results_h",
                       fallback="Roztrzaskane:"), LOG_SUCCESS)
            for row in broken:
                self.log(f"  • {row}", LOG_NORMAL)
        if skipped:
            self.log(t("feedback_mass_break_skipped_h",
                       fallback="Pominięto:"), LOG_WARN)
            for row in skipped:
                self.log(f"  · {row}", LOG_NORMAL)
        if not broken and not skipped:
            self.log(t("feedback_mass_break_nothing",
                       fallback="Nie widzisz tu niczego sensownego do rozbicia."),
                     LOG_WARN)
        else:
            self.log(t("feedback_mass_break_summary",
                       fallback="Hałas niesie się dalej, niż zamierzałeś."),
                     LOG_WARN)

    # ── Prompt 17: combat v1 ────────────────────────────────────────────────
    def _attempt_deploy(self, intent):
        """Place a deployable item from inventory into the current room.
        The item must be in the player's inventory and carry the 'trap',
        'deployable', or 'deploy'-affordance marker. On placement it leaves
        the inventory and is stored in room.state['player_traps'] until it
        triggers."""
        from . import time_system as ts
        from .utils_compat import roll_d20

        ch = self.world.character
        room = self.world.current_floor.current_room()
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie ma gdzie tego rozstawić."), LOG_WARN)
            return

        # Resolve target item from inventory using the intent's targets list
        wanted = ""
        if intent.targets:
            wanted = (intent.targets[0] or "").lower()
        item = None
        candidates = []
        for eid in ch.inventory_ids:
            e = self.world.get(eid)
            if e is None: continue
            tags = e.tags or []
            affs = e.affordances or []
            if not ("trap" in tags or "deployable" in tags or "deploy" in affs):
                continue
            candidates.append(e)
        if not candidates:
            self.log(t("feedback_deploy_nothing",
                       fallback="Nie masz nic, co można by rozstawić."), LOG_WARN)
            return
        if wanted:
            from .affordances import fold as _fold
            wf = _fold(wanted)
            for e in candidates:
                nm = _fold(e.display_name())
                if wf in nm or any(wf in (tg or "") for tg in (e.tags or [])):
                    item = e; break
        if item is None and len(candidates) == 1:
            item = candidates[0]
        if item is None:
            self.log(t("feedback_deploy_ambiguous",
                       fallback="Co dokładnie rozstawić? "
                                + ", ".join(c.display_name() for c in candidates[:4])),
                     LOG_WARN)
            return

        # P29.55 — ferromanta (metal_only_traps): odmawia non-metal
        # pułapek. Komunikat z trap_refused_log, item zostaje w EQ.
        try:
            from . import species_effects as _sp_fx
            if _sp_fx.trap_deploy_refused(ch, item):
                self.log(_sp_fx.trap_refused_log(ch), LOG_WARN)
                return
        except Exception:
            pass

        # DEX check, but always at least partial — placing trap is mostly
        # about whether it triggers cleanly, not whether you can place it.
        from .affordances import AFFORDANCE_CATALOG
        aff = AFFORDANCE_CATALOG.get("deploy")
        stat = aff.stat if aff else "DEX"
        dc = aff.base_dc if aff else 11
        # Unstable / damaged items are harder to set
        if (item.state or {}).get("unstable"):
            dc += 3
        if (item.state or {}).get("damaged"):
            dc += 2
        raw = roll_d20()
        mod = ch.stat_mod(stat)
        total = raw + mod
        if   raw == 20:       level = "critical_success"
        elif raw == 1:        level = "critical_failure"
        elif total >= dc + 5: level = "critical_success"
        elif total >= dc:     level = "success"
        elif total >= dc - 3: level = "partial_success"
        else:                 level = "failure"
        from .dice_labels import format_check as _fc
        self.log(_fc("deploy", stat, raw, mod, total, dc, level),
                 LOG_SYSTEM)

        ts.advance(self.world, aff.time_cost if aff else 5)

        if level == "critical_failure":
            # The trap fires in the player's face.
            self.log(t("feedback_deploy_critfail",
                       fallback="Pułapka pali ci się w rękach. Następnym razem czytaj instrukcję."),
                     LOG_DANGER)
            ch.take_damage(2)
            try:
                ch.inventory_ids.remove(item.entity_id)
            except ValueError:
                pass
            nline = narrate("trap_self_trigger")
            if nline: self.log(nline, LOG_SYNDIC)
            try:
                from ..systems import achievements
                achievements.unlock(ch, "samo_sie_rozstawilo", world=self.world)
            except Exception:
                pass
            if self._check_player_dead("trap_self_deploy",
                                       "od własnej pułapki przy rozstawianiu"):
                return
            return
        if level == "failure":
            self.log(t("feedback_deploy_fail",
                       fallback="Pułapka nie chce się ustawić. Coś zgrzyta. Zostawiasz."),
                     LOG_WARN)
            # Item stays in inventory but takes one damage tick.
            item.state["damaged"] = int((item.state or {}).get("damaged", 0)) + 1
            nline = narrate("deploy_trap_fail")
            if nline: self.log(nline, LOG_SYNDIC)
            return

        # Success / partial / critical: trap goes live in this room.
        try:
            ch.inventory_ids.remove(item.entity_id)
        except ValueError:
            pass
        item.location_id = room.room_id
        if not room.state:
            room.state = {}
        traps = room.state.setdefault("player_traps", [])
        trap_record = {
            "key":          item.key,
            "entity_id":    item.entity_id,
            "display_name": item.display_name(),
            "tags":         list(item.tags or []),
            "quality":      (item.state or {}).get("quality", "normal"),
            "armed_at":     self.world.current_floor.current_minute,
            "level":        level,                # crit_success > harder hit
            "triggered":    False,
        }
        # Pre-compute damage payload (used when something walks in).
        # Prompt 21: each trap also carries a `damage_type` so the
        # encounter resolver can route it through engine.damage and
        # apply the matching elemental status (burning / shocked /
        # corroded / poisoned).
        if "shock" in item.key or "shock" in item.tags:
            trap_record["effect"] = {
                "type": "damage", "amount": 4 if level == "critical_success" else 3,
                "damage_type": "electric",
            }
        elif "fire" in item.key or "fire" in item.tags or \
             "incendiary" in item.tags:
            trap_record["effect"] = {
                "type": "damage", "amount": 3 if level == "critical_success" else 2,
                "damage_type": "fire",
            }
        elif "acid" in item.key or "acid" in item.tags:
            trap_record["effect"] = {
                "type": "damage", "amount": 3 if level == "critical_success" else 2,
                "damage_type": "acid",
            }
        elif "poison" in item.key or "poison" in item.tags:
            trap_record["effect"] = {
                "type": "damage", "amount": 2 if level == "critical_success" else 1,
                "damage_type": "poison",
            }
        elif "cold" in item.tags or "frost" in item.key:
            trap_record["effect"] = {
                "type": "damage", "amount": 2 if level == "critical_success" else 1,
                "damage_type": "cold",
            }
        elif "smoke" in item.key:
            trap_record["effect"] = {
                "type": "obscure", "amount": 2,
                "damage_type": "physical",   # smoke doesn't damage
            }
        elif "trip" in item.key or "tripwire" in item.tags:
            trap_record["effect"] = {
                "type": "knockdown", "amount": 1,
                "damage_type": "physical",
            }
        else:
            trap_record["effect"] = {
                "type": "damage",
                "amount": 2 if level != "critical_success" else 4,
                "damage_type": "physical",
            }
        traps.append(trap_record)

        self.log(t("feedback_deploy_ok",
                   fallback=f"Rozstawiasz: {item.display_name()}.",
                   name=item.display_name()), LOG_SUCCESS)
        self._bump_threat(3, source="trap_arm", room=room)
        ch.affinity["trap"] = ch.affinity.get("trap", 0) + 1
        self._bump_run_counter("run_traps_armed", 1)
        # P29.12 — tutorial: trap pickup fallback on first deploy.
        try:
            from . import tutorial as _tut
            _tut.try_show_tip(self.world, "trap_deploy")
        except Exception:
            pass

        # Narrator hook
        nline = narrate("deploy_trap_success") or narrate("deploy_trap")
        if nline:
            self.log(nline, LOG_SYNDIC)
        try:
            from ..systems import achievements
            achievements.unlock(ch, "pulapka_z_niczego", world=self.world)
        except Exception:
            pass

    # ── P29.7: pick up a deployed trap (mis-placement fallback) ──────────────
    def _attempt_trap_pickup(self, intent):
        """Reverse of deploy: remove a player-armed trap from
        room.state['player_traps'] and put the underlying Entity back into
        inventory. Costs 2 minutes and a DEX (or INT, whichever is higher)
        check at TT 10. On critical failure the trap fires in your hands.

        Why this exists: the user kept placing traps in dud rooms; without
        a fallback those items were just lost. Simple test, simple outcome
        — partial/success → trap back in pack, critical fail → ouch."""
        from . import time_system as ts
        from .utils_compat import roll_d20
        from .affordances import fold as _fold

        ch = self.world.character
        room = self.world.current_floor.current_room()
        if room is None:
            self.log(t("feedback_no_room",
                       fallback="Nie ma czego zwijać — nie ma pokoju."), LOG_WARN)
            return
        traps = (room.state or {}).get("player_traps") or []
        # Only un-triggered traps can be picked back up.
        live = [tr for tr in traps if not tr.get("triggered")]
        if not live:
            self.log(t("feedback_trap_pickup_none",
                       fallback="W tym pokoju nie ma twoich rozstawionych pułapek do zwinięcia."),
                     LOG_WARN)
            return

        # Match by name from intent.targets[0] if provided.
        wanted = ""
        if intent.targets:
            wanted = (intent.targets[0] or "").strip().lower()
        trap = None
        if wanted:
            wf = _fold(wanted)
            for tr in live:
                nm = _fold(tr.get("display_name", ""))
                tags = [_fold(t or "") for t in (tr.get("tags") or [])]
                if wf in nm or any(wf in tg for tg in tags) or wf in _fold(tr.get("key", "")):
                    trap = tr; break
        if trap is None and len(live) == 1:
            trap = live[0]
        if trap is None:
            names = ", ".join(tr.get("display_name", tr.get("key", "?")) for tr in live[:4])
            self.log(t("feedback_trap_pickup_ambiguous",
                       fallback=f"Którą pułapkę zwinąć? {names}"), LOG_WARN)
            return

        # Roll: best of DEX or INT, TT 10.
        raw = roll_d20()
        mod_dex = ch.stat_mod("DEX")
        mod_int = ch.stat_mod("INT")
        mod = max(mod_dex, mod_int)
        total = raw + mod
        dc = 10
        if   raw == 20:       level = "critical_success"
        elif raw == 1:        level = "critical_failure"
        elif total >= dc + 5: level = "critical_success"
        elif total >= dc:     level = "success"
        elif total >= dc - 3: level = "partial_success"
        else:                 level = "failure"
        from .dice_labels import format_check as _fc
        stat_label = "DEX" if mod_dex >= mod_int else "INT"
        self.log(_fc("trap_pickup", stat_label, raw, mod, total, dc, level),
                 LOG_SYSTEM)

        # Always costs a beat.
        ts.advance(self.world, 2)

        if level == "critical_failure":
            # Trap fires in your hands.
            payload = trap.get("effect") or {}
            dmg = int(payload.get("amount", 2))
            self.log(t("feedback_trap_pickup_critfail",
                       fallback=f"Próbujesz rozbroić — pułapka odpala ci się w dłoniach. -{dmg} HP.",
                       amount=dmg), LOG_DANGER)
            ch.take_damage(dmg)
            # Mark as triggered so it doesn't keep haunting the room.
            trap["triggered"] = True
            self._bump_threat(2, source="trap_self_disarm", room=room)
            if self._check_player_dead("trap_self_disarm",
                                       "od własnej pułapki przy zwijaniu"):
                return
            return
        if level == "failure":
            self.log(t("feedback_trap_pickup_fail",
                       fallback="Zwijanie nie idzie. Pułapka zostaje na miejscu, ale ją trochę poluzowałeś."),
                     LOG_WARN)
            # Slightly degrade — counts as a "damaged" deploy on re-arm.
            trap["damaged"] = int(trap.get("damaged", 0)) + 1
            return

        # success / partial_success / critical_success → trap goes back.
        eid = trap.get("entity_id")
        ent = self.world.get(eid) if eid else None
        if ent is None:
            # Edge case: entity vanished. Fabricate a no-op restoration:
            # just drop the trap dict so the room is clean.
            try:
                traps.remove(trap)
            except ValueError:
                pass
            self.log(t("feedback_trap_pickup_ghost",
                       fallback="Zwijasz, ale pułapki już tu nie ma — została po niej tylko siatka."),
                     LOG_WARN)
            return
        # Restore to inventory.
        ent.location_id = None
        if ent.entity_id not in ch.inventory_ids:
            ch.inventory_ids.append(ent.entity_id)
        # On partial, slap a damaged tick — represents bent mechanism.
        if level == "partial_success":
            ent.state = ent.state or {}
            ent.state["damaged"] = int((ent.state or {}).get("damaged", 0)) + 1
        try:
            traps.remove(trap)
        except ValueError:
            pass
        self.log(t("feedback_trap_pickup_ok",
                   fallback=f"Zwijasz: {ent.display_name()} — wraca do plecaka.",
                   name=ent.display_name()), LOG_SUCCESS)
        # Narrator hook (best-effort).
        try:
            nline = narrate("trap_pickup_ok")
            if nline: self.log(nline, LOG_SYNDIC)
        except Exception:
            pass

    # ── P29.10: sponsor drop-pod open handler ────────────────────────────
    def _attempt_open_pod(self, intent):
        """Open a sponsor drop-pod entity in the current room. The pod
        carries `pending_item_key` + `pending_sponsor_key` in its
        state. On open: materialize the item into inventory, remove
        the pod from the room, log a DCC-flavored "podpisz odbiór"
        line, and bump audience (a brand promotion just landed on
        camera).

        Multiple pods: if more than one, match by name fragment from
        intent.targets[0] (e.g. "novachem"); else pop the first one.
        """
        ch = self.world.character
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None or not getattr(room, "entities", None):
            self.log(t("feedback_pod_none",
                       fallback="W tym pokoju nie ma pakietu do otwarcia."),
                     LOG_WARN)
            return
        pods = [e for e in room.entities
                if e is not None
                and "sponsor_pod" in (e.tags or [])
                and (e.state or {}).get("pending_item_key")]
        if not pods:
            self.log(t("feedback_pod_none",
                       fallback="Nic tu nie wygląda na pakiet sponsorski."),
                     LOG_WARN)
            return

        # Optional name filter — fold + substring match against
        # display_name + sponsor key.
        wanted = ""
        if intent.targets:
            wanted = (intent.targets[0] or "").strip().lower()
        pod = None
        if wanted:
            from .affordances import fold as _fold
            wf = _fold(wanted)
            for p in pods:
                nm = _fold(p.display_name())
                sk = _fold((p.state or {}).get("pending_sponsor_key", ""))
                if wf in nm or wf in sk:
                    pod = p; break
        if pod is None:
            pod = pods[0]  # lone / first available

        item_key = (pod.state or {}).get("pending_item_key", "")
        sponsor_key = (pod.state or {}).get("pending_sponsor_key", "")

        # Materialize the item.
        new_item = None
        try:
            from ..content.items import make_item
            new_item = make_item(item_key, location_id="inventory:player")
        except Exception as exc:
            self.log(f"(Pakiet pusty — błąd zawartości: {exc})", LOG_WARN)
        if new_item is not None:
            self.world.register(new_item)
            ch.inventory_ids.append(new_item.entity_id)

        # Remove the pod from the room.
        try:
            room.entities.remove(pod)
        except ValueError:
            pass
        # Clear pod state so it can't be re-opened from a stale ref.
        pod.state = {**(pod.state or {}), "pending_item_key": "",
                     "pending_sponsor_key": "", "opened": True}

        # Polish display: sponsor name → friendlier opener line.
        sponsor_label = ""
        try:
            from . import sponsors as _sp
            sdata = _sp.get_sponsor(sponsor_key)
            sponsor_label = _sp._name_pl(sdata)
        except Exception:
            sponsor_label = sponsor_key or "sponsor"
        if new_item is not None:
            self.log(t("feedback_pod_open_ok",
                       fallback=f"Otwierasz pakiet od {sponsor_label}: "
                                f"„{new_item.display_name()}” trafia do plecaka.",
                       sponsor=sponsor_label,
                       item=new_item.display_name()),
                     LOG_SUCCESS)
        else:
            self.log(t("feedback_pod_open_empty",
                       fallback=f"Pakiet od {sponsor_label} okazuje się pusty. "
                                f"Sponsorzy są źli na wszystkich."),
                     LOG_WARN)

        # Audience bump: opening on camera is good TV. Sponsor attention
        # also nudges up (you used their product publicly).
        try:
            from . import audience as _aud
            _aud.change_audience(self.world, 3, source="sponsor_pod_open")
        except Exception:
            pass
        # P29.12 — tutorial: explain drop pods + sponsors on first open.
        try:
            from . import tutorial as _tut
            _tut.try_show_tip(self.world, "drop_pods")
            _tut.try_show_tip(self.world, "sponsors")
        except Exception:
            pass
        # P29.15 — first drop-pod achievement.
        try:
            from ..systems import achievements as _ach
            _ach.unlock(self.world.character, "pakiet_z_sufitu",
                        world=self.world)
        except Exception:
            pass
        # P29.20 — companion chatter on sponsor pod open.
        try:
            from . import companion_voice as _cv
            _cv.maybe_say(self.world, "sponsor_pod_open")
        except Exception:
            pass
        try:
            from . import sponsors as _sp
            if sponsor_key:
                _sp.note_player_tag(self.world,
                                    f"used_{sponsor_key}_gift", weight=1)
        except Exception:
            pass
        try:
            audio.play_sfx("sponsor_chime")
        except Exception:
            pass

    # ── P29.18: vending-machine use handler ──────────────────────────────

    # Pool of absurd vending-machine items. Each: (key, display_name,
    # tags, weight). Drawn weighted; one item per machine use; the
    # machine stamps state["vending_used"]=True so it can't be re-rolled.
    _VENDING_POOL = (
        ("plyn_z_napisem_pij", "Płyn z napisem PIJ",
         ["consumable", "weird", "vending_loot"], 4),
        ("skarpetka_rozgrzewajaca", "Skarpetka rozgrzewająca (używana)",
         ["worn", "weird", "vending_loot", "trinket"], 3),
        ("ostatnia_pigulka", "Ostatnia Pigułka (rocznik nieznany)",
         ["consumable", "medical", "vending_loot"], 3),
        ("zardzewialy_klucz", "Zardzewiały klucz (do czegoś)",
         ["tool", "key", "vending_loot"], 2),
        ("instant_zupa_3_in_1", "Zupa instant 3w1 (smak: niespodzianka)",
         ["consumable", "food", "vending_loot"], 4),
        ("portret_anti_hosta",
         "Portret Konferansjera w drewnianej ramce",
         ["junk", "art", "vending_loot"], 2),
        ("baton_proteinowy_otwarte",
         "Baton proteinowy (rozprutą folią)",
         ["consumable", "food", "vending_loot"], 4),
        ("kostka_lodu_z_napisem",
         "Kostka lodu z grawerem „WSZYSTKO BĘDZIE DOBRZE”",
         ["consumable", "weird", "vending_loot"], 2),
        ("kabel_o_dziwnym_przekroju",
         "Kabel o dziwnym przekroju",
         ["scrap", "wire", "vending_loot"], 3),
    )
    def _attempt_vending_use(self, machine_entity) -> None:
        """Dispense one absurd item from the vending machine.

        Single-use per machine (state["vending_used"] flag). Roll
        weighted-random from _VENDING_POOL. Cost: 1 credit per use
        (the machine is a kiosk, after all). Side effect: small
        audience bump because the item is always memorable, and a
        sponsor tag note for "novachem_biotech" (the brand running
        the machines)."""
        import random as _r
        from .entity import Entity, T_ITEM
        ch = self.world.character
        # Cost.
        if ch.credits < 1:
            self.log(t("feedback_vending_no_credits",
                       fallback="Automat brzęczy, ale nie ma kredytów."),
                     LOG_WARN)
            return
        ch.credits -= 1
        # Pick.
        keys = list(self._VENDING_POOL)
        weights = [w for _k, _n, _t, w in keys]
        key, name, tags, _ = _r.choices(keys, weights=weights, k=1)[0]
        # Materialize.
        item = Entity(
            key=key, entity_type=T_ITEM,
            fallback_name=name,
            fallback_desc="Automat wypluł to z bólem.",
            tags=list(tags) + ["crafted"],
            affordances=["inspect", "use", "loot"],
            location_id="inventory:player",
            portable=True,
            state={"quality": "normal"},
        )
        self.world.register(item)
        ch.inventory_ids.append(item.entity_id)
        # Mark the machine as used.
        machine_entity.state = machine_entity.state or {}
        machine_entity.state["vending_used"] = True
        self.log(t("feedback_vending_dispense",
                   fallback=f"Automat: BRZĘK. Dostajesz: „{name}”. "
                            f"(-1 kr.)",
                   name=name), LOG_SUCCESS)
        # Audience nudge — these items are memorable.
        try:
            from . import audience as _aud
            _aud.change_audience(self.world, 1, source="vending",
                                 emit_log=False)
        except Exception:
            pass
        # Sponsor tag — vendings are NovaChem-branded by default.
        try:
            from . import sponsors as _sp
            _sp.note_player_tag(self.world, "consumable_used", weight=1)
        except Exception:
            pass
        # SFX.
        try:
            audio.play_sfx("sponsor_chime")
        except Exception:
            pass

    # ── P29.19 / P29.27: credit sinks ─────────────────────────────────────
    #
    # The actual handler logic was extracted to engine/handlers/credit_sinks.py
    # in P29.27. The class still exposes _TRAIN_COST / _BRIBE_COST etc. for
    # back-compat with any external readers; the dispatch shims forward
    # to the free functions.

    from .handlers import credit_sinks as _credit_sinks
    _TRAIN_COST    = _credit_sinks.TRAIN_COST
    _BRIBE_COST    = _credit_sinks.BRIBE_COST
    _CALL_POD_COST = _credit_sinks.CALL_POD_COST
    _UPGRADE_COST  = _credit_sinks.UPGRADE_COST
    del _credit_sinks   # keep namespace clean
    def _attempt_train_stat(self, intent) -> None:
        from .handlers import credit_sinks
        return credit_sinks.attempt_train_stat(self, intent)
    def _attempt_bribe_sponsor(self, intent) -> None:
        from .handlers import credit_sinks
        return credit_sinks.attempt_bribe_sponsor(self, intent)
    def _attempt_call_pod(self, intent) -> None:
        from .handlers import credit_sinks
        return credit_sinks.attempt_call_pod(self, intent)
    def _attempt_upgrade_loadout(self, intent) -> None:
        from .handlers import credit_sinks
        return credit_sinks.attempt_upgrade_loadout(self, intent)

    # ── P29.23 / P29.14 / P29.33: inventory handler shims ─────────────────
    # Bodies extracted to engine/handlers/inventory.py in P29.33.
    def _attempt_cook(self, intent) -> None:
        from .handlers import inventory
        return inventory.attempt_cook(self, intent)
    def _attempt_read(self, intent) -> None:
        from .handlers import inventory
        return inventory.attempt_read(self, intent)
    def _attempt_apply_enhancement(self, intent):
        from .handlers import inventory
        return inventory.attempt_apply_enhancement(self, intent)
    def _attempt_experiment(self, intent):
        """P29.56 — emergent crafting via raw material combination."""
        from .handlers import experiment
        return experiment.attempt_experiment(self, intent)
    def _attempt_consult_codex(self, intent):
        """P29.57e — Wiercimajster codex (delegate)."""
        from .handlers import wiercimajster as _wm
        return _wm.attempt_consult_codex(self, intent)
    def _attempt_open_box(self, intent):
        """P29.57b — otwórz skrzynkę (VS-style box reveal)."""
        from .handlers import boxes
        return boxes.attempt_open_box(self, intent)

    # ── Prompt 07: memetic / belief-seed handler ─────────────────────────────
    def _attempt_memetic(self, intent):
        """Plant a belief seed. Validates context (targets, channel,
        plausibility), rolls a stat check, and persists the seed onto the
        world via memetics.register_seed. Effects route through the
        consequence engine for the immediate hit; long-term propagation is
        handled in process_belief_seeds (called from move + safehouse
        entry triggers)."""
        from ..systems import memetics
        from ..systems import risk_reward
        from . import time_system as ts
        from .utils_compat import roll_d20
        import random

        ch = self.world.character
        floor = self.world.current_floor
        room = floor.current_room() if floor else None

        if room is None:
            self.log(t("feedback_no_room",
                       fallback="Nie ma jak komuś tu wmówić czegokolwiek."),
                     LOG_WARN)
            return

        # 1. Method: prefer parser hint, otherwise infer from intent label.
        method = (intent.memetic_method or "").strip()
        if not method:
            method = {
                "seed_belief":       "lie",
                "spread_rumor":      "rumor",
                "create_taboo":      "taboo_creation",
                "issue_false_order": "false_order",
                "logic_exploit":     "logic_exploit",
                "identity_attack":   "identity_attack",
                "sow_distrust":      "social_proof",
                "incite_panic":      "identity_attack",
                "religious_framing": "religious_framing",
                "sponsor_disinformation": "sponsor_disinformation",
                "propaganda":        "propaganda",
                "forge_social_proof":"social_proof",
            }.get(intent.intent, "rumor")

        tmpl = memetics.pick_method_template(method)

        # 2. Core claim: must exist OR the seed has no content.
        claim = (intent.core_claim or "").strip()
        if not claim:
            # Fall back to the raw text as the claim, but warn.
            claim = (intent.raw_text or "").strip()
            if not claim:
                self.log(t("feedback_memetic_no_claim",
                           fallback="Brakuje treści — co konkretnie chcesz wmówić?"),
                         LOG_WARN)
                return

        # 3. Targets / target_tags: try intent.targets, then infer from claim.
        targets = list(intent.targets or [])
        target_tags = list(tmpl.get("target_tags", []))
        # Look at visible entities — if any match a target string, use their tags.
        from .affordances import fold as _fold
        for raw_tgt in targets:
            ftgt = _fold(raw_tgt)
            for e in room.entities:
                if ftgt and (ftgt in _fold(e.display_name())
                             or any(ftgt in (tg or "") for tg in (e.tags or []))):
                    for tg in (e.tags or []):
                        if tg not in target_tags:
                            target_tags.append(tg)
        # Common keyword → tag inference (no entity in room required).
        kw_to_tag = {
            "robot":"machine","drono":"drone","dron":"drone",
            "kult":"cult","crawler":"crawler","crawlerom":"crawler",
            "potwor":"monster","sponsor":"sponsor","sponsorom":"sponsor",
            "maszyn":"machine","kamer":"camera",
            "robots":"machine","drones":"drone","cultists":"cult",
            "monsters":"monster","sponsors":"sponsor","cameras":"camera",
        }
        full = _fold((intent.raw_text or "") + " " + claim)
        for kw, tg in kw_to_tag.items():
            if kw in full and tg not in target_tags:
                target_tags.append(tg)

        # Pull target tags injected via LLM passthrough
        for mod in (intent.modifiers or []):
            if isinstance(mod, str) and mod.startswith("target_tag:"):
                tg = mod.split(":", 1)[1].strip()
                if tg and tg not in target_tags:
                    target_tags.append(tg)

        if not targets and not target_tags:
            self.log(t("feedback_memetic_no_target",
                       fallback="Nikogo tu nie ma, kto by to słyszał lub czytał."),
                     LOG_WARN)
            return

        # 4. Spread channel: prefer parser hint, else method default, else
        # context-derived (room.sensory_tags / entity types).
        channel = (intent.spread_channel or "").strip()
        if not channel:
            tmpl_channels = list(tmpl.get("spread_channels", []))
            channel = tmpl_channels[0] if tmpl_channels else "crawler_gossip"

        # 5. Check that the player actually has a way to communicate.
        # Plausible channels by room context: speech (always), terminal (need
        # one in room), camera (need a 'camera' tag), graffiti (always in
        # bathroom / corridor).
        room_tags = set((room.sensory_tags or [])) | {room.actual_type or ""}
        for e in room.entities:
            room_tags.update(e.tags or [])
        channel_ok = True
        if channel == "machine_radio" or channel == "terminal_logs":
            channel_ok = any(("terminal" in (e.tags or [])
                              or e.entity_type == "terminal")
                             for e in room.entities)
        elif channel == "sponsor_replay":
            channel_ok = ("sponsor" in room_tags or "camera" in room_tags
                          or any("camera" in (e.tags or []) for e in room.entities))
        elif channel == "bathroom_graffiti":
            channel_ok = "bathroom" in room_tags or room.safehouse_subtype == "bathroom"
        elif channel == "safehouse_rumor":
            channel_ok = bool(room.safehouse_subtype)
        if not channel_ok:
            self.log(t("feedback_memetic_no_channel",
                       fallback=f"Nie masz tutaj jak puścić tego dalej kanałem „{channel}”.",
                       channel=channel),
                     LOG_WARN)
            return

        # 6. Stat + DC. Adjust DC by absurdity, audience, prior known facts.
        # Stat selection — method-aware. The template's `default_stat` is a
        # last-resort fallback; `memetics.select_memetic_stat` reconciles the
        # method's natural stat against any Ollama suggestion and any
        # keyword cues in the player's phrasing.
        stat = memetics.select_memetic_stat(method, intent) or \
               tmpl.get("default_stat", "CHA")
        dc = int(tmpl.get("base_dc", 12))
        # Absurdity: very short claim or claim with "robot" + "serca" type
        # mismatches → higher DC.
        if len(claim) < 12:
            dc += 1
        if "sponsor" in target_tags:
            dc += 2
        # Reach: large public_visibility → higher DC
        # known_facts that overlap the claim → lower DC
        kf = (ch.flags or {}).get("known_facts") or []
        if any(isinstance(f, str) and f.lower() in claim.lower() for f in kf):
            dc -= 2
        dc = max(6, dc)

        # 7. Roll.
        raw = roll_d20()
        mod = ch.stat_mod(stat)
        total = raw + mod
        if   raw == 20:        level = "critical_success"
        elif raw == 1:         level = "critical_failure"
        elif total >= dc + 5:  level = "critical_success"
        elif total >= dc:      level = "success"
        elif total >= dc - 3:  level = "partial_success"
        else:                  level = "failure"
        from .dice_labels import (stat_pl as _spl, level_pl as _lpl)
        self.log(f"  [mem:{method}] d20({raw}) + {_spl(stat)}({mod:+d}) = "
                 f"{total} vs TT {dc} → {_lpl(level)}", LOG_SYSTEM)

        # Narrator: attempt line first (always).
        line = narrate("belief_seed_attempt")
        if line:
            self.log(line, LOG_SYNDIC)

        ts.advance(self.world, 8)

        # 8. Build the seed (always, even on partial) and adjust quality.
        strength = 60 if level == "critical_success" else \
                   50 if level == "success" else \
                   35 if level == "partial_success" else \
                   15
        stability = 50 + int(tmpl.get("stability_mod", 0))
        if level == "partial_success":
            stability -= 15
        if level == "critical_failure":
            stability -= 30
        stability = max(0, min(100, stability))
        sponsor_attn = (channel in ("sponsor_replay", "audience_memes")
                        or "sponsor" in target_tags)

        # Build BeliefEffects from method's possible_effects (cap to 3).
        from ..systems.memetics import BeliefEffect, create_seed, register_seed
        try:
            from ..content.data.memetic_templates import EFFECT_TEMPLATES
        except Exception:
            EFFECT_TEMPLATES = {}
        possible = list(tmpl.get("possible_effects", []))[:3]
        effects = []
        for ek in possible:
            meta = EFFECT_TEMPLATES.get(ek, {})
            effects.append(BeliefEffect(
                key=ek, trigger_context="encounter_start",
                target_tags=list(target_tags),
                chance=float(meta.get("chance", 0.5)),
                effect_type=ek, effect_value=meta.get("value"),
                fallback_description_pl=meta.get("fallback_pl", ""),
            ))

        seed = create_seed(
            method=method, core_claim=claim,
            target_tags=target_tags,
            origin_text=intent.raw_text or claim,
            source_room_id=room.room_id,
            created_floor=self.world.floor_number,
            created_time=floor.current_minute if floor else 0,
            strength=strength, stability=stability,
            spread_channels=list(tmpl.get("spread_channels", []) or [channel]),
            desired_effect=intent.desired_outcome or "",
            tags=list(tmpl.get("tags", [])),
            risks=list(tmpl.get("possible_risks", [])),
            effects=effects,
            public_visibility=2 if channel in ("sponsor_replay","audience_memes") else 1,
            sponsor_attention=sponsor_attn,
        )

        # 9. Apply outcome.
        immediate = []
        if level == "critical_failure":
            # Backlash branch: weak/empty seed; sponsor flags player as manipulator.
            seed.current_stage = "backlash"
            seed.strength = max(0, seed.strength - 30)
            self.log(narrate("belief_seed_backlash") or
                     t("feedback_memetic_backlash",
                       fallback="Argument obrócił się przeciw tobie. Ktoś już to powtarza, ale o tobie."),
                     LOG_DANGER)
            immediate.extend(risk_reward.risk_effects(
                ["social_suspicion", "tracked_by_sponsor"]))
        elif level == "failure":
            self.log(narrate("belief_seed_fail") or
                     t("feedback_memetic_fail",
                       fallback="Nikt tego nie kupił. Zostaje ślad, ale ślad jest niewielki."),
                     LOG_WARN)
            seed.strength = max(0, seed.strength - 10)
        elif level == "partial_success":
            self.log(narrate("belief_seed_partial") or
                     t("feedback_memetic_partial",
                       fallback="Coś z tego zostaje, ale w wersji, której nie planowałeś."),
                     LOG_WARN)
            seed.distortion = min(100, seed.distortion + 15)
            immediate.extend(risk_reward.risk_effects(
                tmpl.get("possible_risks", []) or []))
        else:
            # success / critical_success
            line = narrate("belief_seed_success") or \
                t("feedback_memetic_success",
                  fallback="Idea zaszczepiona. Teraz tylko sprawdzić, w czyją głowę wpadnie najdłużej.")
            self.log(line, LOG_SUCCESS)
            # Modest reward effects through the same mapper
            immediate.extend(risk_reward.reward_effects(
                tmpl.get("possible_rewards", []) or []))
            # Prompt 18: belief-seed planting is the Ministerstwo headline.
            immediate.append({"type": "add_audience", "amount": 1,
                              "source": "belief_seed", "tag": "memetic_seed"})
            immediate.append({"type": "sponsor_tag",
                              "tag": "belief_invocation", "weight": 1})
            if level == "critical_success":
                immediate.append({"type": "add_audience", "amount": 1,
                                  "source": "belief_seed_crit"})

        # Persist seed.
        register_seed(self.world, seed)
        # Class affinity nudge by method category.
        aff_for = {
            "logic_exploit":     "tech",
            "false_order":       "tech",
            "religious_framing": "occult",
            "identity_attack":   "social",
            "lie":               "social",
            "rumor":             "social",
            "social_proof":      "social",
            "performance":       "showmanship",
            "propaganda":        "showmanship",
            "sponsor_disinformation":"showmanship",
            "taboo_creation":    "social",
            "forged_evidence":   "tech",
            "mythic_comparison": "occult",
        }.get(method)
        if aff_for and aff_for in ch.affinity:
            ch.affinity[aff_for] = ch.affinity.get(aff_for, 0) + 1

        # Sponsor attention notice
        if sponsor_attn and level in ("success", "critical_success",
                                       "partial_success"):
            line = narrate("sponsor_notices_propaganda")
            if line:
                self.log(line, LOG_SYNDIC)

        # Run immediate effect dicts through the consequence engine.
        if immediate:
            lines = apply(immediate, self.world, time_system=time_system)
            for ln in lines:
                self.log(str(ln), LOG_NORMAL)

        # Ambient: roll one propagation tick right now, weakly — this lets
        # crit_success seeds spawn a rumor immediately.
        if level == "critical_success":
            events = memetics.process_belief_seeds(self.world, 0, trigger="broadcast")
            for ev in events:
                if ev.get("kind") == "rumor":
                    nline = narrate("belief_spreads")
                    if nline: self.log(nline, LOG_SYNDIC)

    # ── Prompt 07b: clue-gated resolution path handlers ─────────────────────
    def _attempt_use_password(self, intent):
        """Use a known password / access code against a panel-like target.
        Validator: must have at least one known password, and ideally one
        whose `opens` overlaps the target's tags."""
        from ..systems import knowledge as _kn
        from . import time_system as ts
        ch = self.world.character
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        _kn.bootstrap(self.world)
        passwords = self.world.known_passwords or {}
        if not passwords:
            self.log(t("feedback_password_unknown",
                       fallback="Nie znasz żadnego hasła, które tu pasuje."),
                     LOG_WARN)
            return
        # Try to match target → password.opens
        target_name = (intent.targets[0] if intent.targets else "").strip().lower()
        match = None
        if target_name and room is not None:
            for e in room.entities:
                ftags = (e.tags or [])
                if target_name in (e.display_name() or "").lower() \
                        or any(target_name in (tg or "") for tg in ftags):
                    for pw in passwords.values():
                        if any(o in ftags for o in (pw.get("opens") or [])):
                            match = (e, pw); break
                    if match: break
        if match is None:
            # Fall back: use the first known password against any door/panel
            for e in (room.entities if room else []):
                if "door" in (e.tags or []) or "panel" in (e.tags or []) \
                        or "terminal" in (e.tags or []):
                    pw = next(iter(passwords.values()))
                    match = (e, pw); break
        if match is None:
            self.log(t("feedback_password_no_target",
                       fallback="Hasło jest, ale nie widzisz tu nic, do czego pasuje."),
                     LOG_WARN)
            return
        ent, pw = match
        # Spending the password marks it used. The door becomes unlocked.
        ent.state = ent.state or {}
        ent.state["unlocked"] = True
        ent.state["opened_by_password"] = pw.get("key")
        if room is not None:
            for label, ed in room.exits.items():
                if ed.get("entity_id") == ent.entity_id:
                    ed["locked"] = False
        pw["used"] = True
        ts.advance(self.world, 3)
        self.log(t("feedback_password_used",
                   fallback=f"Wpisujesz „{pw.get('code_text') or pw.get('label')}”. "
                            f"„{ent.display_name()}” ustępuje.",
                   code=pw.get("code_text") or "", name=ent.display_name()),
                 LOG_SUCCESS)
        nline = narrate("clue_path_used")
        if nline: self.log(nline, LOG_SYNDIC)
    def _attempt_exploit_weakness(self, intent):
        """Apply known boss-weakness clue against a present target.
        Requires a known fact / clue whose tags include 'weakness' AND the
        target name matches."""
        from ..systems import knowledge as _kn
        from .utils_compat import roll_d20
        _kn.bootstrap(self.world)
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return
        # Look for an alive hostile in the room
        target = None
        for e in room.entities:
            if e.entity_type in ("monster", "crawler") and e.is_alive():
                target = e; break
        if target is None:
            self.log(t("feedback_weakness_no_target",
                       fallback="Nikogo tu, na kim mógłbyś wykorzystać znaną słabość."),
                     LOG_WARN)
            return
        # Check we know any weakness-tagged clue
        known_weakness = False
        for c in (self.world.known_clues or {}).values():
            tags = (c.get("tags") or []) + (c.get("reveals_tags") or [])
            if "weakness" in tags or any("weakness" in (tg or "") for tg in tags):
                known_weakness = True; break
        if not known_weakness:
            self.log(t("feedback_weakness_unknown",
                       fallback="Wiesz, że coś go boli, ale nie wiesz co."),
                     LOG_WARN)
            return
        # Roll: WIS + DC 11. On success: -50% HP on the target.
        ch = self.world.character
        raw = roll_d20()
        mod = ch.stat_mod("WIS")
        total = raw + mod
        dc = 11
        if total >= dc:
            dmg = max(2, target.hp // 2)
            target.hp = max(0, target.hp - dmg)
            self.log(t("feedback_weakness_used",
                       fallback=f"Trafiasz tam, gdzie boli. „{target.display_name()}”: -{dmg} HP.",
                       name=target.display_name(), amount=dmg),
                     LOG_SUCCESS)
            nline = narrate("clue_path_used")
            if nline: self.log(nline, LOG_SYNDIC)
        else:
            self.log(t("feedback_weakness_missed",
                       fallback="Wiesz, gdzie powinieneś trafić. Nie trafiasz."),
                     LOG_WARN)
    def _attempt_invoke_belief(self, intent):
        """Invoke a planted belief seed against a present target.

        Three distinct reject reasons, each with its own immersive feedback:
        1. Belief not present here (no seed targets the room's tags).
        2. Targets present but no channel (silent / can't broadcast).
        3. Belief and channel both present but the roll missed.
        """
        from ..systems import knowledge as _kn
        from ..systems import memetics
        from .utils_compat import roll_d20
        room = self.world.current_floor.current_room() if self.world.current_floor else None
        if room is None:
            self.log(t("feedback_no_room", fallback="Nie jesteś nigdzie."), LOG_WARN)
            return

        # Collect tags of present hostiles + non-hostile witnesses.
        tags = set()
        target_ent = None
        for e in room.entities:
            if e.entity_type in ("monster", "crawler", "npc") and e.is_alive():
                tags.update(e.tags or [])
                if target_ent is None:
                    target_ent = e

        if target_ent is None:
            # Reject #2 variant: no audience at all to receive the myth.
            self.log(t("feedback_invoke_no_target",
                       fallback="Nikogo tu nie ma, kogo to mogłoby dotyczyć."),
                     LOG_WARN)
            return

        seed = _kn.matching_belief_for(self.world, tags, min_strength=40)
        if seed is None:
            # Reject #1: belief doesn't reach this audience.
            # Check whether ANY active belief exists at all.
            any_active = bool(memetics.all_active(self.world))
            if any_active:
                self.log(t("feedback_invoke_no_match",
                           fallback="Ten mit jeszcze tu nie dotarł."),
                         LOG_WARN)
            else:
                self.log(t("feedback_invoke_no_seed",
                           fallback="Nie znasz idei, którą można byłoby na nich wywołać."),
                         LOG_WARN)
            return

        # Channel check — the target must be in a position to "hear" symbolic
        # invocation. Machines need a terminal/camera/audio source, or to be
        # explicitly tagged as networked. Crawlers/NPCs only need speech.
        is_machine = any(tg in ("machine","drone","ai","construct")
                         for tg in (target_ent.tags or []))
        has_channel = True
        if is_machine:
            has_channel = any(
                ("terminal" in (e.tags or []) or e.entity_type == "terminal"
                 or "camera" in (e.tags or []) or "radio" in (e.tags or []))
                for e in room.entities
            ) or any(tg in ("networked","ai","drone") for tg in (target_ent.tags or []))
        if not has_channel:
            self.log(t("feedback_invoke_no_channel",
                       fallback="Drony słyszą słowa, ale nie mają powodu, by uznać je za instrukcję."),
                     LOG_WARN)
            return

        # Method-aware stat roll vs DC 10 + distortion/10.
        ch = self.world.character
        raw = roll_d20()
        stat = memetics.select_memetic_stat(seed, intent) or "CHA"
        mod = ch.stat_mod(stat)
        total = raw + mod
        dc = 10 + seed.distortion // 10
        from .dice_labels import stat_pl as _spl
        self.log(f"  [przywołanie] d20({raw}) + {_spl(stat)}({mod:+d}) = "
                 f"{total} vs TT {dc}",
                 LOG_SYSTEM)
        if total >= dc:
            target_ent.conditions = target_ent.conditions or []
            if "hesitating" not in target_ent.conditions:
                target_ent.conditions.append("hesitating")
            target_ent.hp = max(1, target_ent.hp - 1)
            self.log(t("feedback_invoke_ok",
                       fallback=f"Przypominasz „{target_ent.display_name()}”, co krąży o nich. Cel waha się.",
                       name=target_ent.display_name()),
                     LOG_SUCCESS)
            nline = narrate("target_hesitates") or \
                    (narrate("machine_confusion") if is_machine
                     else narrate("crawler_gossip_shift"))
            if nline: self.log(nline, LOG_SYNDIC)
            seed.strength = min(100, seed.strength + 3)
            # Belief use also counts as clue-path-used.
            cl = narrate("clue_path_used")
            if cl: self.log(cl, LOG_SYNDIC)
        else:
            self.log(t("feedback_invoke_miss",
                       fallback="Idea nie chwyciła w odpowiednim momencie."),
                     LOG_WARN)
            # High distortion + missed roll = chance the myth backfires.
            if seed.distortion >= 60:
                back = narrate("belief_backfires")
                if back: self.log(back, LOG_DANGER)
    def _attempt_drop(self, ent) -> None:
        """Wyrzuca item z plecaka do bieżącego pokoju. Equipped /
        wielded items wymagają najpierw take_off / sheathe."""
        ch = self.world.character
        floor = self.world.current_floor
        room = floor.current_room() if floor else None
        if room is None:
            return
        eid = ent.entity_id
        nm = ent.display_name()
        # Zablokuj jeśli item jest aktualnie wielniety lub założony.
        if ch.wielded_main_id == eid or ch.wielded_offhand_id == eid:
            msg = (f"„{nm}” trzymasz w ręku. "
                   f"Najpierw `schowaj` żeby wyjąć z dłoni.")
            self.log(msg, LOG_WARN)
            return
        if eid in (ch.worn_slots or {}).values():
            msg = f"„{nm}” masz na sobie. Najpierw `zdejmij`."
            self.log(msg, LOG_WARN)
            return
        # Czy item w inwentarzu?
        if eid not in ch.inventory_ids:
            self.log("Nie masz tego w plecaku.", LOG_WARN)
            return
        # Przerzuć do pokoju.
        ch.inventory_ids.remove(eid)
        ent.location_id = room.room_id
        room.entities.append(ent)
        msg = f"Wyrzucasz: „{nm}”. Leży teraz na podłodze."
        self.log(msg, LOG_NORMAL)

    # ── P29.53c: Key → unlock door ───────────────────────────────────
    def _attempt_use_key(self, key_ent) -> None:
        """Klucz/keycard w plecaku → odblokowuje najbliższe zamknięte
        wyjście w bieżącym pokoju. Pierwsze zamknięte exit łapie klucz."""
        floor = self.world.current_floor
        if floor is None:
            return
        room = floor.current_room()
        if room is None:
            return
        # Znajdź pierwsze zamknięte (nie ukryte) wyjście.
        locked_label = None
        for label, ed in (room.exits or {}).items():
            if ed.get("locked") and not ed.get("hidden"):
                locked_label = label
                break
        if locked_label is None:
            self.log("Nie ma tu nic, na czym klucz mógłby zadziałać.",
                     LOG_WARN)
            return
        # Odblokuj.
        room.exits[locked_label]["locked"] = False
        key_name = key_ent.display_name() if hasattr(key_ent, "display_name") \
                   else "klucz"
        msg = (f"Przykładasz „{key_name}” do czytnika. Zamek pyka. "
               f"Wyjście „{locked_label}” odblokowane.")
        self.log(msg, LOG_SUCCESS)
        # Niektóre keycard'y są jednorazowe (np. suspicious_keycard).
        # Zostawiamy w plecaku — gracz może uznać że to flavor item.
        # Jeśli kiedyś dodamy multi-use vs single-use distinction,
        # tu jest miejsce żeby je usuwać przez ch.inventory_ids.remove.

    # ── P29.52: Recipe note → learn recipe ───────────────────────────
