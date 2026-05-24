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
            t("help_4", fallback="           plecak, postać, mapa, zapisz, pomoc"),
        ]:
            self.log(line, LOG_SYSTEM)

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
