"""Game state machine for the revamp."""
import pygame

from .config import (SCREEN_W, SCREEN_H, FPS, BASE_STATS, LOG_NORMAL, LOG_SYSTEM,
                     LOG_WARN, LOG_SUCCESS, LOG_SYNDIC, LOG_DANGER)
from .lang import t, get_language, set_language
from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .procgen import build_floor_1
from .parser_core import parse_with_optional_llm
from .validation import validate
from .resolution import resolve
from .consequences import apply
from . import time_system, save_load, ui, audio
from .narrator import say as narrate


STATE_TITLE     = "title"
STATE_CREATE    = "create"
STATE_PLAY      = "play"
STATE_DIALOG    = "dialog"
STATE_CLASS_OFFER = "class_offer"
STATE_SPECIES_OFFER = "species_offer"
STATE_VICTORY   = "victory"
STATE_DEFEAT    = "defeat"


_NUMS = {
    pygame.K_1:"1", pygame.K_2:"2", pygame.K_3:"3", pygame.K_4:"4", pygame.K_5:"5",
    pygame.K_6:"6", pygame.K_7:"7", pygame.K_8:"8", pygame.K_9:"9", pygame.K_0:"0",
    pygame.K_KP1:"1", pygame.K_KP2:"2", pygame.K_KP3:"3", pygame.K_KP4:"4", pygame.K_KP5:"5",
    pygame.K_KP6:"6", pygame.K_KP7:"7", pygame.K_KP8:"8", pygame.K_KP9:"9", pygame.K_KP0:"0",
}


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.state = STATE_TITLE
        self.world: WorldState | None = None

        # UI state
        self.input_text = ""
        self.blink = True
        self._blink_t = 0
        self._suppress_textinput = False

        # Character creation sub-state
        self.cc = {"step": "name", "name_input": "", "selected_bg": 0}

        # Class / species offers
        self.offer_candidates = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def log(self, msg, cat=LOG_NORMAL):
        if self.world: self.world.log_msg(msg, cat)

    # ── State transitions ────────────────────────────────────────────────────

    def start_new_game(self, name: str, background: str):
        self.world = WorldState()
        self.world.character.name = name or "Bezimienny"
        self.world.character.background = background
        # Modest stat adjustment based on background
        adj = {
            "office_worker": {"INT":+1},
            "mechanic":      {"INT":+1,"STR":+1},
            "nurse":         {"WIS":+1,"CHA":+1},
            "cook":          {"CON":+1,"DEX":+1},
            "security_guard":{"STR":+1,"CON":+1},
            "courier":       {"DEX":+2},
            "student":       {"INT":+2},
            "streamer":      {"CHA":+2},
            "soldier":       {"STR":+1,"CON":+1},
            "unemployed_hustler":{"CHA":+1,"DEX":+1},
            "janitor":       {"CON":+1,"INT":+1},
            "paramedic":     {"WIS":+1,"INT":+1},
        }.get(background, {})
        for s, b in adj.items():
            self.world.character.stats[s] = self.world.character.stats.get(s, 10) + b

        # Some starting items
        from .items import make_item
        starters = {
            "office_worker": ["dead_phone","plastic_badge"],
            "mechanic":      ["duct_tape","battery"],
            "nurse":         ["dirty_bandage","snack_bar"],
            "cook":          ["cheap_knife","snack_bar"],
            "security_guard":["flashlight","plastic_badge"],
            "courier":       ["dead_phone","snack_bar"],
            "student":       ["dead_phone","snack_bar"],
            "streamer":      ["dead_phone","coffee"],
            "soldier":       ["cheap_knife","flashlight"],
            "unemployed_hustler":["improvised_lockpick","cracked_mug"],
            "janitor":       ["duct_tape","flashlight"],
            "paramedic":     ["dirty_bandage","battery"],
        }.get(background, ["cracked_mug"])
        for k in starters:
            it = make_item(k, location_id="inventory:player")
            self.world.register(it)
            self.world.character.inventory_ids.append(it.entity_id)

        # Build Floor 1
        self.world.current_floor = build_floor_1(self.world)
        self.world.floor_number = 1
        self.log(t("log_floor_open",
                   fallback=f"Witaj na Piętrze 1, {self.world.character.name}.",
                   name=self.world.character.name),
                 LOG_SYNDIC)
        # First-enter description
        room = self.world.current_floor.current_room()
        if room:
            self.log(room.display_first_enter(), LOG_NORMAL)
        self.state = STATE_PLAY

    def submit_input(self):
        text_val = self.input_text.strip()
        self.input_text = ""
        if not text_val: return
        if self.state == STATE_PLAY:
            self.log(f"> {text_val}", LOG_NORMAL)
            self._handle_play_input(text_val)
        elif self.state == STATE_CREATE:
            self._handle_create_input(text_val)

    def _handle_create_input(self, text_val):
        if self.cc.get("step") == "name":
            self.cc["name_input"] = text_val
            self.cc["step"] = "background"
            self._suppress_textinput = True

    def _handle_play_input(self, text_val):
        intent = parse_with_optional_llm(text_val, self.world)
        if intent.intent == "unknown":
            self.log(t("feedback_no_intent",
                       fallback="Nie rozumiem, co chcesz zrobić. Spróbuj inaczej."), LOG_WARN)
            return

        # Numeric quick-pick on safehouse menu
        if intent.intent == "numeric":
            self._safehouse_pick(int(intent.modifiers[0]))
            return

        # Special quick-intents that don't go through validator chain
        if intent.intent == "check_inventory":
            self._show_inventory(); return
        if intent.intent == "check_character":
            self._show_character(); return
        if intent.intent == "check_map":
            self._show_map(); return
        if intent.intent == "help":
            self._show_help(); return
        if intent.intent == "save":
            ok = save_load.save(self.world)
            self.log(t("log_save_done", fallback="Zapisano.") if ok else
                     t("log_save_fail", fallback="Zapis nie powiódł się."), LOG_SUCCESS if ok else LOG_DANGER)
            return
        # Prompt 06 quick intents
        if intent.intent == "check_materials":
            self._show_materials(); return
        if intent.intent == "craft_help":
            self._show_craft_help(); return
        if intent.intent == "salvage_help":
            self._show_salvage_help(); return

        # Crafting intent: route to crafting engine, NOT generic validate/resolve
        if intent.intent == "craft":
            self._attempt_craft(intent); return

        # Salvage / strip / harvest: validate target, then run salvage flow
        if intent.intent in ("salvage", "strip", "harvest"):
            self._attempt_salvage(intent); return

        # Standard pipeline: validate → resolve → apply
        v = validate(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations), LOG_NORMAL)
            return

        r = resolve(v, self.world)
        if r.fallback_description and (v.required_checks or r.level != "success"):
            self.log(r.line(), LOG_SYSTEM)

        lines = apply(r.effects, self.world, time_system=time_system)
        for ln in lines:
            self.log(ln, LOG_NORMAL)

        # Hooks: class offer trigger
        self._maybe_offer_class()
        # Hooks: detect victory (reached exit)
        if self.world.current_floor and self.world.current_floor.current_room_id in self.world.current_floor.exit_room_ids:
            # Need an unlock condition met
            if self.world.current_floor.exits_unlocked:
                self.state = STATE_VICTORY
            else:
                self.log(t("log_at_exit_locked",
                           fallback="Stoisz przed drzwiami wyjścia. Nadal zamknięte."),
                         LOG_WARN)

        # Health check
        if not self.world.character.is_alive():
            self.state = STATE_DEFEAT

    def _safehouse_pick(self, idx: int):
        room = self.world.current_floor.current_room()
        if not room or not room.safehouse_subtype:
            return
        from .safehouses import services, perform
        svc_list = services(room.safehouse_subtype)
        if 1 <= idx <= len(svc_list):
            action_key, _, _ = svc_list[idx-1]
            line = perform(action_key, self.world)
            self.log(line, LOG_SUCCESS)

    # ── Class/species offers ─────────────────────────────────────────────────

    def _maybe_offer_class(self):
        c = self.world.character
        if c.class_key is not None: return
        # Offer condition: at least 5 total affinity points or entered floor 3
        total = sum(c.affinity.values())
        if total >= 5 or self.world.floor_number >= 3:
            from .classes import suggest_classes
            self.offer_candidates = suggest_classes(c, n=3)
            self.state = STATE_CLASS_OFFER
            self.log(narrate("class_offer") or
                     t("log_class_offer", fallback="Syndykat ma dla ciebie propozycję."), LOG_SYNDIC)

    def _accept_class(self, idx: int):
        if not (0 <= idx < len(self.offer_candidates)): return
        from .classes import assign_class
        key = self.offer_candidates[idx]
        if assign_class(self.world, key):
            self.log(t("log_class_picked", fallback=f"Klasa: {key}",
                       name=t(f"class_{key}_n", fallback=key)), LOG_SUCCESS)
        self.state = STATE_PLAY

    # ── Info panels (rendered as log dumps to keep code compact) ────────────

    def _show_inventory(self):
        c = self.world.character
        if not c.inventory_ids:
            self.log(t("ui_inv_empty", fallback="Plecak pusty."), LOG_NORMAL); return
        self.log(t("ui_inv_header", fallback="W plecaku:"), LOG_SYSTEM)
        for eid in c.inventory_ids:
            e = self.world.get(eid)
            if e: self.log(f"  • {e.display_name()}", LOG_NORMAL)

    def _show_character(self):
        c = self.world.character
        self.log(f"{c.name} — {t(f'bg_{c.background}_n', fallback=c.background)}", LOG_SYSTEM)
        for s in BASE_STATS:
            mod = c.stat_mod(s); sign = "+" if mod >= 0 else ""
            self.log(f"  {s}: {c.stats[s]:2d} ({sign}{mod})", LOG_NORMAL)
        if c.class_key:
            self.log(f"  {t('ui_class', fallback='Klasa')}: {t(f'class_{c.class_key}_n', fallback=c.class_key)}", LOG_NORMAL)
        self.log(f"  HP {c.hp}/{c.max_hp}   AC {c.effective_ac()}   {t('ui_credits', fallback='Kr')} {c.credits}", LOG_NORMAL)

    def _show_map(self):
        f = self.world.current_floor
        if not f: return
        self.log(t("ui_map_header", fallback="Znane pokoje:"), LOG_SYSTEM)
        for rid in sorted(f.discovered_room_ids):
            r = f.rooms.get(rid)
            if r:
                mark = "@" if rid == f.current_room_id else "·"
                self.log(f"  {mark} {r.display_short_title()}", LOG_NORMAL)

    def _show_help(self):
        for line in [
            t("help_1", fallback="Polecenia: rozejrzyj się, sprawdź X, przeszukaj, nasłuchuj wyjście,"),
            t("help_2", fallback="           idź do <pokój>, użyj X, zaatakuj X, pogadaj z X,"),
            t("help_3", fallback="           wepchnij X do Y, ukryj się, uciekaj, odpocznij, czekaj,"),
            t("help_4", fallback="           plecak, materiały, postać, mapa, zapisz, pomoc"),
            t("help_5", fallback="           rozbierz X, zdemontuj X, pozyskaj kości z X,"),
            t("help_6", fallback="           zrób pułapkę / broń / dystrakcję / narzędzie / przebranie,"),
            t("help_7", fallback="           pomoc craftingu, pomoc odzyskiwania"),
        ]:
            self.log(line, LOG_SYSTEM)

    # ── Prompt 06: materials / salvage / crafting commands ─────────────────

    def _show_materials(self):
        from . import materials
        rows = materials.inventory_summary(self.world.character)
        if not rows:
            self.log(t("ui_materials_empty", fallback="Materiały: brak."), LOG_NORMAL)
            return
        self.log(t("ui_materials_header", fallback="Materiały:"), LOG_SYSTEM)
        for r in rows:
            self.log(r, LOG_NORMAL)

    def _show_craft_help(self):
        from .crafting import all_recipes, improvised_categories
        self.log(t("ui_craft_help_h", fallback="Crafting:"), LOG_SYSTEM)
        self.log("  Znane przepisy:", LOG_NORMAL)
        for k, v in all_recipes().items():
            self.log(f"    {k}  ({v.get('name_pl','?')})", LOG_NORMAL)
        self.log("  Improwizowane kategorie:", LOG_NORMAL)
        for k, v in improvised_categories().items():
            tagsets = " | ".join("+".join(s) for s in v.get("required_tag_sets", []))
            self.log(f"    {k}  → wymaga {tagsets}", LOG_NORMAL)
        self.log("  Przykłady: 'zrób pułapkę z kabli i baterii', 'skleć broń ze szkła i drewna'.", LOG_DIM if hasattr(self, 'LOG_DIM') else LOG_NORMAL)

    def _show_salvage_help(self):
        self.log(t("ui_salvage_help_h", fallback="Odzyskiwanie surowców:"), LOG_SYSTEM)
        self.log("  rozbierz X        — rozkłada na materiały (czas + hałas)", LOG_NORMAL)
        self.log("  zdemontuj X       — to samo, bardziej technicznie", LOG_NORMAL)
        self.log("  pozyskaj X        — organika z ciał i potworów", LOG_NORMAL)
        self.log("  zerwij X          — odzyskanie obudów / pancerzy", LOG_NORMAL)
        self.log("  ograb / przeszukaj X — przedmioty, nie surowce", LOG_NORMAL)

    def _attempt_salvage(self, intent):
        """Resolve a salvage / strip / harvest action against the current room."""
        from .validation import validate as validate_action
        from .resolution import resolve
        from .consequences import apply
        from . import time_system as ts, materials, content_loader as cl, risk_reward
        import random

        # Use the validator to pick a target entity (it already supports ambiguity)
        v = validate_action(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations), LOG_NORMAL)
            return

        target = v.matched_entities[0] if v.matched_entities else None
        if target is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego szukasz."), LOG_WARN)
            return

        # Pick a salvage table based on target tags
        table_key = _pick_salvage_table_key(target)
        if table_key is None:
            self.log(t("feedback_no_salvage",
                       fallback=f"„{target.display_name()}” nie ma z czego ciągnąć surowców."),
                     LOG_WARN)
            return

        from .data.salvage_tables import SALVAGE_TABLES
        table = SALVAGE_TABLES.get(table_key, {})
        # No infinite farming: refuse if already stripped/depleted
        state = target.state or {}
        if state.get("stripped") or state.get("depleted"):
            self.log(t("feedback_already_stripped",
                       fallback=f"„{target.display_name()}” jest już rozebrane na części."),
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

        self.log(f"  [{intent.intent}] d20({raw}) + {stat}({mod:+d}) = {total} vs DC {dc} → {level}", LOG_SYSTEM)

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

        # Time + noise
        ts.advance(self.world, int(table.get("time_minutes", 15)))
        room = self.world.current_floor.current_room()
        if room: room.noise_level += int(table.get("noise", 1))

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

    def _attempt_craft(self, intent):
        """Try a known recipe by name, otherwise improvise by category from the player's text."""
        from . import crafting, materials, risk_reward
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
                         LOG_WARN); return
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
        self.log(f"  [craft:{plan['category_label_pl']}] d20({raw}) + {stat}({mod:+d}) = {total} vs DC {dc} → {level}", LOG_SYSTEM)

        # Materials: consume on success/partial; half-waste on failure; full loss on crit-fail
        if level in ("critical_success", "success", "partial_success"):
            crafting.consume_for(plan, self.world.character)
        elif level == "failure":
            crafting.waste_for(plan, self.world.character)
        else:   # critical_failure
            crafting.consume_for(plan, self.world.character)

        ts.advance(self.world, plan["time_cost"])

        # Produce result item on success / crit-success / partial
        result_key = plan.get("result_item")
        if level in ("critical_success", "success", "partial_success") and result_key:
            ent = crafting.make_crafted_entity(
                result_key,
                quality="good" if level == "critical_success" else "normal",
                damaged=(level == "partial_success"),
                unstable=(level == "partial_success" and random.random() < 0.4),
            )
            self.world.register(ent)
            self.world.character.inventory_ids.append(ent.entity_id)
            self.log(t("feedback_crafted_item",
                       fallback=f"Wytworzone: {ent.display_name()}",
                       name=ent.display_name()), LOG_SUCCESS)

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

    # ── Event handling ───────────────────────────────────────────────────────

    def handle_keydown(self, ev):
        key = ev.key
        digit = _NUMS.get(key)

        if self.state == STATE_TITLE:
            if digit == "1":
                self.cc = {"step":"name","name_input":"","selected_bg":0}
                self._suppress_textinput = True
                self.input_text = ""
                self.state = STATE_CREATE
                return
            if digit == "2" and save_load.exists():
                w = save_load.load()
                if w is not None:
                    self.world = w
                    self.state = STATE_PLAY
                    self.log(t("log_save_loaded", fallback="Zapis wczytany."), LOG_SUCCESS)
                else:
                    self.log(t("log_save_load_failed",
                               fallback="Zapis uszkodzony."), LOG_DANGER)
                return
            if digit == "4":
                pygame.quit(); raise SystemExit
            if key == pygame.K_l:
                set_language("en" if get_language() == "pl" else "pl")
                self._suppress_textinput = True
            return

        if self.state == STATE_CREATE:
            step = self.cc.get("step")
            if step == "name":
                if key == pygame.K_RETURN:
                    name = self.cc.get("name_input","").strip() or "Bezimienny"
                    self.cc["step"] = "background"
                    self.cc["name_input"] = name
                    self._suppress_textinput = True
                elif key == pygame.K_BACKSPACE:
                    self.cc["name_input"] = self.cc.get("name_input","")[:-1]
                elif key == pygame.K_ESCAPE:
                    self.state = STATE_TITLE
            elif step == "background":
                bgs = ["office_worker","mechanic","nurse","cook","security_guard",
                       "courier","student","streamer","soldier","unemployed_hustler",
                       "janitor","paramedic"]
                if digit is not None:
                    idx = int(digit) - 1
                    if 0 <= idx < len(bgs):
                        self._suppress_textinput = True
                        self.start_new_game(self.cc["name_input"], bgs[idx])
                elif key == pygame.K_ESCAPE or key == pygame.K_BACKSPACE:
                    self.cc["step"] = "name"
            return

        if self.state == STATE_PLAY:
            if key == pygame.K_RETURN:
                self.submit_input()
            elif key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif key == pygame.K_ESCAPE:
                self.input_text = ""
            return

        if self.state == STATE_CLASS_OFFER:
            if digit is not None:
                self._suppress_textinput = True
                self._accept_class(int(digit) - 1)
            return

        if self.state in (STATE_VICTORY, STATE_DEFEAT):
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = STATE_TITLE
                self.world = None
            return

    def handle_textinput(self, ev):
        if self._suppress_textinput:
            self._suppress_textinput = False
            return
        if self.state == STATE_PLAY:
            self.input_text += ev.text
        elif self.state == STATE_CREATE and self.cc.get("step") == "name":
            self.cc["name_input"] = self.cc.get("name_input","") + ev.text

    def update(self, dt):
        self._blink_t += dt
        if self._blink_t > 500:
            self.blink = not self.blink
            self._blink_t = 0
        # Audio routing per state
        try:
            audio.play_music(self._music_key_for_state())
        except Exception:
            pass

    def _music_key_for_state(self):
        return {
            STATE_TITLE: "menu",
            STATE_PLAY: "explore",
            STATE_VICTORY: "victory",
            STATE_DEFEAT: "defeat",
        }.get(self.state, "menu")

    def draw(self):
        s = self.screen
        s.fill((10,12,18))
        if self.state == STATE_TITLE:
            ui.draw_title(s, save_load.exists())
        elif self.state == STATE_CREATE:
            ui.draw_creation(s, self.cc)
        elif self.state == STATE_PLAY:
            ui.draw_topbar(s, self.world)
            ui.draw_room_panel(s, self.world)
            ui.draw_sidebar(s, self.world)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink)
        elif self.state == STATE_CLASS_OFFER:
            ui.draw_topbar(s, self.world)
            ui.draw_room_panel(s, self.world)
            ui.draw_sidebar(s, self.world)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink)
            # Overlay listing the suggested classes
            from .lang import t as tr
            from .classes import CLASS_CATALOG
            lines = [tr("offer_title", fallback="PROPOZYCJA KLASY")]
            for i, key in enumerate(self.offer_candidates, 1):
                lines.append(f"[{i}] {tr(f'class_{key}_n', fallback=key)} — {tr(f'class_{key}_d', fallback='')}")
            lines.append(tr("offer_pick", fallback="Wybierz numerem (1-3)"))
            self._overlay(lines)
        elif self.state == STATE_VICTORY:
            self._end_screen(t("victory_title", fallback="ZEJŚCIE ZALICZONE."), True)
        elif self.state == STATE_DEFEAT:
            self._end_screen(t("defeat_title", fallback="UCZESTNIK ZAKOŃCZONY."), False)
        pygame.display.flip()

    def _overlay(self, lines):
        from .config import PANEL_BG, BORDER, ACCENT, NORMAL_TEXT
        w = SCREEN_W - 200; h = max(160, 40 + len(lines)*22)
        x = (SCREEN_W - w)//2; y = (SCREEN_H - h)//2
        bg = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        bg.fill((0,0,0,160))
        self.screen.blit(bg, (0,0))
        pygame.draw.rect(self.screen, PANEL_BG, (x,y,w,h))
        pygame.draw.rect(self.screen, ACCENT, (x,y,w,h), 2)
        cy = y + 16
        for ln in lines:
            ui.text(self.screen, ln, x + 16, cy, NORMAL_TEXT, 16); cy += 24

    def _end_screen(self, title_str, success: bool):
        self.screen.fill((10,12,18))
        col = (90,210,120) if success else (230,80,80)
        ui.text(self.screen, title_str, SCREEN_W//2 - 200, 200, col, 26, True)
        if self.world:
            c = self.world.character
            ui.text(self.screen, f"{c.name} — D{self.world.current_floor.day_number() if self.world.current_floor else 0}",
                    SCREEN_W//2 - 200, 260, (190,205,220), 16)
        ui.text(self.screen, t("end_press_enter", fallback="[Enter] Powrót do menu"),
                SCREEN_W//2 - 200, SCREEN_H - 80, (90,110,130), 14)
        pygame.display.flip()


# ── Prompt 06: salvage-target -> table-key resolver ────────────────────────

# Maps a few entity tag-sets to salvage table keys. Keep it conservative —
# the templates in revamp/data/salvage_tables.py already enumerate the
# obvious correspondences.
_SALVAGE_TAG_RULES = [
    # (set of tags any of which must match, table_key)
    ({"corpse_humanoid", "crawler"},           "corpse_humanoid"),
    ({"corpse_monster", "monster_remains"},    "corpse_monster"),
    ({"corpse"},                               "corpse_humanoid"),
    ({"sponsor","camera"},                     "sponsor_camera"),
    ({"vending","machine"},                    "vending_machine"),
    ({"bathroom","fixture","ceramic"},         "bathroom_fixture"),
    ({"electrical","panel"},                   "electrical_panel"),
    ({"chemical","acid","hazard"},             "chemical_hazard"),
    ({"furniture","metal"},                    "furniture_metal"),
    ({"furniture","wood"},                     "furniture_wood"),
    ({"metal","scrap","heavy"},                "furniture_metal"),
    ({"wood","handle"},                        "furniture_wood"),
]


def _pick_salvage_table_key(entity):
    """Return a salvage-table key for the entity, or None if not salvageable."""
    if entity is None:
        return None
    # Explicit pointer on the entity wins
    if entity.state and entity.state.get("salvage_table"):
        return entity.state["salvage_table"]
    tags = set(entity.tags or [])
    # Monster-type corpses
    if entity.entity_type == "monster" and not entity.is_alive():
        tags.add("corpse_monster")
    if entity.entity_type == "crawler" and not getattr(entity, "alive", True):
        tags.add("corpse_humanoid")
    for required, table_key in _SALVAGE_TAG_RULES:
        if any(t in tags for t in required):
            return table_key
    return None
