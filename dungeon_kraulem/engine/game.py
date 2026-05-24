"""Game state machine for the revamp."""
import pygame

from ..config import (SCREEN_W, SCREEN_H, FPS, BASE_STATS, LOG_NORMAL, LOG_SYSTEM,
                     LOG_WARN, LOG_SUCCESS, LOG_SYNDIC, LOG_DANGER)
from ..ui.lang import t, get_language, set_language
from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .procgen import build_floor_1
from .parser_core import parse_with_optional_llm
from .validation import validate
from .resolution import resolve
from .consequences import apply
from . import time_system
from . import save_load
from ..ui import ui
from ..ui import audio
from ..systems.narrator import say as narrate


STATE_TITLE     = "title"
STATE_CREATE    = "create"
STATE_PLAY      = "play"
STATE_DIALOG    = "dialog"
STATE_CLASS_OFFER = "class_offer"
STATE_SPECIES_OFFER = "species_offer"
STATE_VICTORY   = "victory"
STATE_DEFEAT    = "defeat"
STATE_SETTINGS  = "settings"   # Prompt 11: simple settings popup from title


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

        # Prompt 09: cached layout (rebuilt on resolution changes).
        self._layout = None
        self._refresh_layout()

        # Prompt 10: tabbed journal overlay.
        from ..ui import journal as _journal
        self.journal_state = _journal.JournalState()

        # Prompt 08: keyboard cursor navigation.
        # input_mode: "text" (default — typing goes to input_text and arrows
        # are inert) or "nav" (typing is suppressed except letters that
        # match hotkeys; arrows move selection; Enter activates option).
        self.input_mode = "text"
        self.nav_state = None         # built lazily per frame in draw()
        # Title-menu cursor index for arrow-key navigation.
        self.title_idx = 0
        # Command history (lightweight) — Up/Down in text mode walks it.
        self.cmd_history: list[str] = []
        self.cmd_history_idx = -1     # -1 = "current draft (not in history)"

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
        from ..content.items import make_item
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
        # Prompt 12: a short, in-character nudge that points at the core
        # loop without becoming a tutorial wall. One line. Localized.
        self.log(t("log_first_room_hint",
                   fallback="(Wskazówka: 'rozejrzyj się', 'przeszukaj', "
                            "'rozbij' albo 'rozbierz' coś — z resztek można "
                            "potem 'zrób' przedmiot. Spróbuj 'pomoc'.)"),
                 LOG_SYSTEM)
        self.state = STATE_PLAY

    def submit_input(self):
        text_val = self.input_text.strip()
        self.input_text = ""
        if not text_val: return
        if self.state == STATE_PLAY:
            # Record to lightweight command history for Up/Down recall.
            if not self.cmd_history or self.cmd_history[-1] != text_val:
                self.cmd_history.append(text_val)
                # Keep history bounded.
                if len(self.cmd_history) > 50:
                    self.cmd_history = self.cmd_history[-50:]
            self.cmd_history_idx = -1
            self.log(f"> {text_val}", LOG_NORMAL)
            self._handle_play_input(text_val)
        elif self.state == STATE_CREATE:
            self._handle_create_input(text_val)

    # ── Prompt 09: resolution / layout management ────────────────────────

    def _refresh_layout(self):
        from ..ui import layout as _L
        if self.screen is None:
            from ..config import DEFAULT_RESOLUTION
            w, h = DEFAULT_RESOLUTION
        else:
            w, h = self.screen.get_size()
        self._layout = _L.calculate_layout(w, h)

    def set_resolution(self, w: int, h: int, fullscreen: bool | None = None) -> bool:
        """Apply a new resolution + optional fullscreen toggle. Persists
        the choice via `settings.save_settings`. Returns True on success."""
        from ..ui import settings as _settings
        from ..config import SUPPORTED_RESOLUTIONS
        if (w, h) not in [tuple(p) for p in SUPPORTED_RESOLUTIONS]:
            self.log(t("feedback_resolution_unsupported",
                       fallback="Ta rozdzielczość nie jest obsługiwana."),
                     LOG_WARN)
            return False
        flags = 0
        if fullscreen is None:
            fullscreen = _settings.load_settings().get("fullscreen", False)
        if fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((w, h), flags)
        except pygame.error:
            self.log(t("feedback_resolution_fail",
                       fallback="Nie udało się zmienić rozdzielczości."),
                     LOG_DANGER)
            return False
        _settings.set_resolution(w, h)
        _settings.set_fullscreen(bool(fullscreen))
        self._refresh_layout()
        self.log(t("feedback_resolution_set",
                   fallback=f"Rozdzielczość ustawiona na {w}x{h}.",
                   w=w, h=h), LOG_SUCCESS)
        return True

    def toggle_fullscreen(self, enabled: bool) -> bool:
        from ..ui import settings as _settings
        s = _settings.load_settings()
        w, h = s["resolution_width"], s["resolution_height"]
        ok = self.set_resolution(w, h, fullscreen=enabled)
        if ok:
            if enabled:
                self.log(t("feedback_fullscreen_on",
                           fallback="Tryb pełnoekranowy włączony."), LOG_SUCCESS)
            else:
                self.log(t("feedback_windowed_on",
                           fallback="Tryb okna włączony."), LOG_SUCCESS)
        return ok

    # ── Prompt 11: settings popup ─────────────────────────────────────────

    def _open_settings(self):
        """Build settings UI state and switch to STATE_SETTINGS."""
        from ..ui import settings as _settings
        from ..config import SUPPORTED_RESOLUTIONS
        s = _settings.load_settings()
        try:
            cur_res_idx = SUPPORTED_RESOLUTIONS.index(
                (s["resolution_width"], s["resolution_height"]))
        except ValueError:
            cur_res_idx = 0
        try:
            cur_llm_idx = _settings.LLM_MODES.index(s.get("llm_mode", "performance"))
        except ValueError:
            cur_llm_idx = 0
        self.settings_state = {
            # 0=resolution, 1=fullscreen, 2=llm_mode, 3=apply, 4=back
            "row": 0,
            "res_idx": cur_res_idx,
            "fullscreen": bool(s.get("fullscreen", False)),
            "llm_idx": cur_llm_idx,
            "prev_state": self.state,
        }
        self.state = STATE_SETTINGS

    def _handle_settings_keydown(self, key, shift_held):
        from ..config import SUPPORTED_RESOLUTIONS
        from ..ui import settings as _settings
        st = getattr(self, "settings_state", None)
        if st is None:
            self.state = STATE_TITLE
            return
        n_rows = 5
        if key in (pygame.K_UP, pygame.K_w):
            st["row"] = (st["row"] - 1) % n_rows
            self._suppress_textinput = True; return
        if key in (pygame.K_DOWN, pygame.K_s):
            st["row"] = (st["row"] + 1) % n_rows
            self._suppress_textinput = True; return
        if key in (pygame.K_LEFT, pygame.K_a):
            if st["row"] == 0:
                st["res_idx"] = (st["res_idx"] - 1) % len(SUPPORTED_RESOLUTIONS)
            elif st["row"] == 1:
                st["fullscreen"] = not st["fullscreen"]
            elif st["row"] == 2:
                st["llm_idx"] = (st["llm_idx"] - 1) % len(_settings.LLM_MODES)
            self._suppress_textinput = True; return
        if key in (pygame.K_RIGHT, pygame.K_d):
            if st["row"] == 0:
                st["res_idx"] = (st["res_idx"] + 1) % len(SUPPORTED_RESOLUTIONS)
            elif st["row"] == 1:
                st["fullscreen"] = not st["fullscreen"]
            elif st["row"] == 2:
                st["llm_idx"] = (st["llm_idx"] + 1) % len(_settings.LLM_MODES)
            self._suppress_textinput = True; return
        if key == pygame.K_RETURN:
            row = st["row"]
            if row in (0, 1, 2, 3):
                # Apply current selection.
                w, h = SUPPORTED_RESOLUTIONS[st["res_idx"]]
                self.set_resolution(w, h, fullscreen=st["fullscreen"])
                # Persist + activate the LLM mode.
                _settings.set_llm_mode(_settings.LLM_MODES[st["llm_idx"]])
            elif row == 4:
                self.state = st.get("prev_state", STATE_TITLE)
            self._suppress_textinput = True; return
        if key == pygame.K_ESCAPE or key == pygame.K_F2:
            self.state = st.get("prev_state", STATE_TITLE)
            self._suppress_textinput = True; return
        if key == pygame.K_F1:
            self._show_settings_help()
            self._suppress_textinput = True; return

    def _show_settings_help(self):
        for line in [
            t("settings_help_1", fallback="Ustawienia — sterowanie:"),
            t("settings_help_2", fallback="  Góra/Dół: wybór pola"),
            t("settings_help_3", fallback="  Lewo/Prawo: zmień wartość"),
            t("settings_help_4", fallback="  Enter: zastosuj   Escape: powrót"),
        ]:
            self.log(line, LOG_SYSTEM)

    # ── Prompt 10: journal overlay ────────────────────────────────────────

    def _open_journal(self, tab_key: str | None = None):
        """Open the journal overlay on `tab_key` (or its current tab).

        Prompt 12: if the journal subsystem ever raises while preparing
        the overlay, fall back to the legacy log-dump helpers so the
        player still sees their information. Reliability over elegance."""
        from ..ui import journal as _journal
        try:
            if tab_key:
                if tab_key not in _journal.TABS:
                    tab_key = _journal.TAB_MAP
                self.journal_state.tab = tab_key
            self.journal_state.open = True
        except Exception:
            # Journal init failed for some reason — dump into the log.
            fallbacks = {
                _journal.TAB_INVENTORY:    self._show_inventory,
                _journal.TAB_MAP:          self._show_map,
                _journal.TAB_MATERIALS:    self._show_materials,
                _journal.TAB_KNOWLEDGE:    self._show_knowledge,
                _journal.TAB_BELIEFS:      self._show_beliefs,
                _journal.TAB_RUMORS:       self._show_beliefs,
            }
            fn = fallbacks.get(tab_key)
            if fn:
                try: fn()
                except Exception: pass

    def _journal_handle_key(self, key, shift_held: bool) -> bool:
        """Consume a keydown while the journal is open. Returns True iff
        the key was handled; False lets the normal handler run."""
        if not self.journal_state.open:
            return False
        from ..ui import journal as _journal
        import pygame as _pg
        # Close on Escape or F2 (mirror of the open hotkey).
        if key in (_pg.K_ESCAPE, _pg.K_F2):
            self.journal_state.open = False
            self._suppress_textinput = True
            return True
        if key == _pg.K_j and not shift_held:
            # Toggle off via J (same as opening hotkey).
            self.journal_state.open = False
            self._suppress_textinput = True
            return True
        # Tab cycling.
        tabs = list(_journal.TABS)
        cur_idx = tabs.index(self.journal_state.tab) if self.journal_state.tab in tabs else 0
        if key in (_pg.K_LEFT,) or (key == _pg.K_TAB and shift_held):
            self.journal_state.tab = tabs[(cur_idx - 1) % len(tabs)]
            self._suppress_textinput = True; return True
        if key in (_pg.K_RIGHT,) or key == _pg.K_TAB:
            self.journal_state.tab = tabs[(cur_idx + 1) % len(tabs)]
            self._suppress_textinput = True; return True
        # Selection.
        entries = _journal.get_journal_entries(self.world, self.journal_state.tab)
        n = len(entries)
        if n > 0:
            if key == _pg.K_UP:
                self.journal_state.set_selected((self.journal_state.selected() - 1) % n)
                self._suppress_textinput = True; return True
            if key == _pg.K_DOWN:
                self.journal_state.set_selected((self.journal_state.selected() + 1) % n)
                self._suppress_textinput = True; return True
            if key == _pg.K_HOME:
                self.journal_state.set_selected(0)
                self._suppress_textinput = True; return True
            if key == _pg.K_END:
                self.journal_state.set_selected(n - 1)
                self._suppress_textinput = True; return True
            if key == _pg.K_PAGEUP:
                if shift_held:
                    # Shift+PageUp scrolls the DETAIL panel.
                    self.journal_state.bump_detail_scroll(-6)
                else:
                    self.journal_state.bump_scroll(-8)
                    self.journal_state.set_selected(max(0, self.journal_state.selected() - 8))
                self._suppress_textinput = True; return True
            if key == _pg.K_PAGEDOWN:
                if shift_held:
                    self.journal_state.bump_detail_scroll(+6)
                else:
                    self.journal_state.bump_scroll(+8)
                    self.journal_state.set_selected(min(n - 1, self.journal_state.selected() + 8))
                self._suppress_textinput = True; return True
            if key == _pg.K_RETURN:
                # Enter is harmless — toggle/reset detail scroll so the
                # player can "rewind" a long entry.
                self.journal_state.reset_detail_scroll()
                self._suppress_textinput = True; return True
        if key == _pg.K_F1:
            self._show_journal_help()
            self._suppress_textinput = True; return True
        # Swallow ALL other keys while journal is open so the world below
        # doesn't react to typing.
        self._suppress_textinput = True
        return True

    def _show_journal_help(self):
        for line in [
            t("journal_help_1", fallback="Dziennik — sterowanie:"),
            t("journal_help_2", fallback="  Lewo/Prawo lub Tab: zmiana zakładki"),
            t("journal_help_3", fallback="  Góra/Dół: wybór wpisu   PageUp/PageDown: przewijanie listy"),
            t("journal_help_4", fallback="  Shift+PageUp/PageDown: przewijanie szczegółów   Enter: powrót do początku szczegółów"),
            t("journal_help_5", fallback="  Escape lub J: zamknij dziennik"),
        ]:
            self.log(line, LOG_SYSTEM)

    def _show_resolutions(self):
        from ..config import SUPPORTED_RESOLUTIONS
        from ..ui import settings as _settings
        cur = (_settings.load_settings()["resolution_width"],
               _settings.load_settings()["resolution_height"])
        self.log(t("ui_resolution_header",
                   fallback="Obsługiwane rozdzielczości:"), LOG_SYSTEM)
        for (w, h) in SUPPORTED_RESOLUTIONS:
            marker = "▶" if (w, h) == cur else " "
            self.log(f"  {marker} {w}x{h}  — komenda: ustaw rozdzielczość {w}x{h}",
                     LOG_NORMAL)
        full = _settings.load_settings().get("fullscreen", False)
        line = (t("ui_resolution_fullscreen_on",
                  fallback="Tryb pełnoekranowy: WŁĄCZONY") if full
                else t("ui_resolution_fullscreen_off",
                       fallback="Tryb pełnoekranowy: WYŁĄCZONY"))
        self.log(f"  {line}", LOG_NORMAL)
        self.log(t("ui_resolution_hint",
                   fallback="  Komendy: fullscreen / tryb okna / ustaw rozdzielczość WxH"),
                 LOG_NORMAL)

    def submit_generated_command(self, command: str):
        """Prompt 08: route a cursor/option-selected command through the
        same submit_input path used by typed text. The command is logged
        like a manual entry, then dispatched to the normal parser pipeline.
        Never mutates game state directly."""
        cmd = (command or "").strip()
        if not cmd:
            return
        self.input_text = cmd
        self.submit_input()

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

        # Special quick-intents — Prompt 10: most info commands open the
        # journal overlay on the appropriate tab. Character sheet + help
        # still dump to the log because they're short.
        from ..ui import journal as _journal
        if intent.intent == "check_inventory":
            self._open_journal(_journal.TAB_INVENTORY); return
        if intent.intent == "check_character":
            self._show_character(); return
        if intent.intent == "check_map":
            self._open_journal(_journal.TAB_MAP); return
        if intent.intent == "help":
            self._show_help(); return
        if intent.intent == "save":
            ok = save_load.save(self.world)
            self.log(t("log_save_done", fallback="Zapisano.") if ok else
                     t("log_save_fail", fallback="Zapis nie powiódł się."), LOG_SUCCESS if ok else LOG_DANGER)
            return
        # Prompt 06 quick intents
        if intent.intent == "check_materials":
            self._open_journal(_journal.TAB_MATERIALS); return
        if intent.intent == "craft_help":
            self._show_craft_help(); return
        if intent.intent == "salvage_help":
            self._show_salvage_help(); return
        if intent.intent == "trap_help":
            self._show_trap_help(); return
        # Prompt 07/10 — beliefs vs rumors tab: route by phrasing.
        if intent.intent == "check_beliefs":
            text_l = (intent.normalized_text or "").lower()
            tab = (_journal.TAB_RUMORS
                   if ("plotk" in text_l or "rumor" in text_l) else
                   _journal.TAB_BELIEFS)
            self._open_journal(tab); return
        # Prompt 07b — knowledge journal opens the Knowledge tab.
        if intent.intent == "check_knowledge":
            self._open_journal(_journal.TAB_KNOWLEDGE); return
        # Prompt 10 — explicit journal intents.
        if intent.intent == "journal_open":
            self._open_journal(self.journal_state.tab or _journal.TAB_MAP); return
        if intent.intent == "journal_close":
            self.journal_state.open = False; return
        if intent.intent == "journal_objectives":
            self._open_journal(_journal.TAB_OBJECTIVES); return
        if intent.intent == "journal_crawlers":
            self._open_journal(_journal.TAB_CRAWLERS); return
        if intent.intent == "journal_crafting":
            self._open_journal(_journal.TAB_CRAFTING); return
        if intent.intent == "journal_achievements":
            self._open_journal(_journal.TAB_ACHIEVEMENTS); return

        # Prompt 09 — display settings
        if intent.intent == "show_resolutions":
            self._show_resolutions(); return
        if intent.intent == "set_fullscreen":
            self.toggle_fullscreen(True); return
        if intent.intent == "set_windowed":
            self.toggle_fullscreen(False); return
        if intent.intent == "set_resolution":
            w = h = None
            for m in intent.modifiers or []:
                if isinstance(m, str) and m.startswith("w:"):
                    try: w = int(m.split(":",1)[1])
                    except ValueError: pass
                if isinstance(m, str) and m.startswith("h:"):
                    try: h = int(m.split(":",1)[1])
                    except ValueError: pass
            if w and h:
                self.set_resolution(w, h)
            else:
                self.log(t("feedback_resolution_unsupported",
                           fallback="Ta rozdzielczość nie jest obsługiwana."),
                         LOG_WARN)
            return

        # Crafting intent: route to crafting engine, NOT generic validate/resolve
        if intent.intent == "craft":
            self._attempt_craft(intent); return

        # Salvage / strip / harvest: validate target, then run salvage flow
        if intent.intent in ("salvage", "strip", "harvest"):
            self._attempt_salvage(intent); return

        # Gap 4: deploy a crafted/portable trap or device
        if intent.intent == "deploy":
            self._attempt_deploy(intent); return

        # Prompt 12: object destruction. Routes through validation for
        # target resolution (so ambiguous names still get a clarify prompt),
        # then a STR check + state mutation + optional salvage payout.
        if intent.intent == "break":
            self._attempt_break(intent); return

        # Prompt 14: "zaatakuj X" where X is a non-creature object should
        # route to break, not to a missing-affordance refusal. Peek at the
        # current room's visible entities — if the named target is an
        # object-type with a destructive-compatible profile, treat the
        # attack as a break attempt.
        if intent.intent == "attack" and intent.targets:
            room = self.world.current_floor.current_room() if self.world.current_floor else None
            if room is not None:
                from .validation import _resolve_entities
                candidates = _resolve_entities(room, intent.targets[0])
                if candidates:
                    e = candidates[0]
                    if e.entity_type in ("object", "hazard", "door",
                                         "environmental_feature", "container",
                                         "terminal", "corpse"):
                        intent.intent = "break"
                        self._attempt_break(intent); return

        # Prompt 07: memetic / belief-seed intents go to their own handler.
        if intent.intent in ("seed_belief", "spread_rumor", "create_taboo",
                             "issue_false_order", "logic_exploit",
                             "identity_attack", "sow_distrust",
                             "incite_panic", "religious_framing",
                             "sponsor_disinformation", "propaganda",
                             "forge_social_proof"):
            self._attempt_memetic(intent); return

        # Prompt 07b: clue-gated resolution paths.
        if intent.intent == "use_password":
            self._attempt_use_password(intent); return
        if intent.intent == "exploit_weakness":
            self._attempt_exploit_weakness(intent); return
        if intent.intent == "invoke_belief":
            self._attempt_invoke_belief(intent); return

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
        from ..systems.safehouses import services, perform
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
            from ..systems.classes import suggest_classes
            self.offer_candidates = suggest_classes(c, n=3)
            self.state = STATE_CLASS_OFFER
            self.log(narrate("class_offer") or
                     t("log_class_offer", fallback="Syndykat ma dla ciebie propozycję."), LOG_SYNDIC)

    def _accept_class(self, idx: int):
        if not (0 <= idx < len(self.offer_candidates)): return
        from ..systems.classes import assign_class
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
            if not e:
                continue
            tags = []
            st = e.state or {}
            q = st.get("quality")
            if q and q != "normal":
                tags.append(q)
            if st.get("damaged"):
                tags.append("uszk.")
            if st.get("unstable"):
                tags.append("niestabilne")
            if "trap" in (e.tags or []) or "deploy" in (e.affordances or []):
                tags.append("[do rozstawienia]")
            suffix = f"  ({', '.join(tags)})" if tags else ""
            self.log(f"  • {e.display_name()}{suffix}", LOG_NORMAL)
        # Surface achievement count, but only if any are unlocked.
        if c.unlocked_achievements:
            self.log(t("ui_inv_achievements",
                       fallback=f"  Osiągnięcia: {len(c.unlocked_achievements)}",
                       count=len(c.unlocked_achievements)),
                     LOG_NORMAL)

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
            t("help_4", fallback="           plecak, materiały, postać, mapa, zapisz, pomoc,"),
            t("help_5", fallback="           rozbierz X, zdemontuj X, pozyskaj kości z X,"),
            t("help_6", fallback="           zrób pułapkę / nóż / dymówkę / opatrunek,"),
            t("help_7", fallback="           rozstaw pułapkę, podłóż linkę, zamontuj dymówkę,"),
            t("help_8", fallback="           pomoc craftingu, pomoc odzyskiwania, pomoc pułapek"),
            t("controls_help_title", fallback="Sterowanie:"),
            t("controls_help_1", fallback="  Tryb tekstowy: pisz po polsku. Enter wysyła. ↑/↓ historia."),
            t("controls_help_2", fallback="  Tryb wyboru: [T] wejdź, ↑↓ wybór, ←→/Tab grupa, Enter zatwierdź."),
            t("controls_help_3", fallback="  Hotkeys: I plecak, M mapa, C postać, J wiedza, R odpocznij,"),
            t("controls_help_4", fallback="           Ctrl+S zapisz, F1 pomoc, Esc tryb tekstowy / wyczyść."),
        ]:
            self.log(line, LOG_SYSTEM)

    # ── Prompt 06: materials / salvage / crafting commands ─────────────────

    def _show_materials(self):
        from ..content import materials
        rows = materials.inventory_summary(self.world.character)
        if not rows:
            self.log(t("ui_materials_empty", fallback="Materiały: brak."), LOG_NORMAL)
            return
        self.log(t("ui_materials_header", fallback="Materiały:"), LOG_SYSTEM)
        for r in rows:
            self.log(r, LOG_NORMAL)

    def _show_craft_help(self):
        from ..content.crafting import all_recipes, improvised_categories
        self.log(t("ui_craft_help_h", fallback="Crafting:"), LOG_SYSTEM)
        self.log("  Znane przepisy:", LOG_NORMAL)
        for k, v in all_recipes().items():
            aliases = ", ".join((v.get("aliases_pl") or [])[:3])
            extra = f"  [tak nazwiesz: {aliases}]" if aliases else ""
            self.log(f"    {k}  ({v.get('name_pl','?')}){extra}", LOG_NORMAL)
        self.log("  Improwizowane kategorie:", LOG_NORMAL)
        for k, v in improvised_categories().items():
            tagsets = " | ".join("+".join(s) for s in v.get("required_tag_sets", []))
            self.log(f"    {k}  → wymaga {tagsets}", LOG_NORMAL)
        self.log("  Przykłady: 'zrób pułapkę z kabli i baterii', 'skleć broń ze szkła i drewna'.", LOG_NORMAL)
        # Gap 5: nudge towards deploy
        self.log("  Po skrafceniu pułapki: 'rozstaw pułapkę' albo 'podłóż pułapkę'.", LOG_NORMAL)

    def _show_trap_help(self):
        """Gap 5: list player's deployable items + sample commands."""
        self.log(t("ui_trap_help_h", fallback="Pułapki i rozstawianie:"), LOG_SYSTEM)
        ch = self.world.character
        deployable = []
        for eid in ch.inventory_ids:
            e = self.world.get(eid)
            if e is None: continue
            if "trap" in (e.tags or []) or "deploy" in (e.affordances or []) \
                    or "deployable" in (e.tags or []):
                deployable.append(e)
        if not deployable:
            self.log("  Plecak: brak czegokolwiek do rozstawienia.", LOG_NORMAL)
        else:
            self.log("  Plecak — gotowe do rozstawienia:", LOG_NORMAL)
            for e in deployable:
                self.log(f"    • {e.display_name()}", LOG_NORMAL)
        self.log("  Polecenia: 'rozstaw pułapkę', 'podłóż pułapkę zwarciową',", LOG_NORMAL)
        self.log("             'ustaw linkę potykającą', 'zamontuj dymówkę'.", LOG_NORMAL)
        self.log("  Pułapka zadziała na pierwszego wrogo nastawionego, który tu wejdzie.", LOG_NORMAL)

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
            return

        target = v.matched_entities[0] if v.matched_entities else None
        if target is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego szukasz."), LOG_WARN)
            return

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
                  fallback=f"„{target.display_name()}” należy do safehouse — patrzą na to.",
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
        self.log(f"  [break] d20({raw}) + STR({mod:+d}) = {total} vs DC {dc} → {level}",
                 LOG_SYSTEM)

        ts.advance(self.world, 4)
        room = self.world.current_floor.current_room() if self.world.current_floor else None

        if level in ("critical_success", "success"):
            target.state = {**(target.state or {}), "broken": True, "destroyed": True}
            self.log(t("feedback_break_ok",
                       fallback=f"Rozbijasz „{target.display_name()}”.",
                       name=target.display_name()), LOG_SUCCESS)
            if room:
                room.noise_level += 2 if level == "critical_success" else 3
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
        elif level == "partial_success":
            target.state = {**(target.state or {}), "damaged": True}
            self.log(t("feedback_break_partial",
                       fallback=f"„{target.display_name()}” pęka, ale trzyma się jeszcze w jednym kawałku.",
                       name=target.display_name()), LOG_WARN)
            if room:
                room.noise_level += 1
        elif level == "failure":
            self.log(t("feedback_break_fail",
                       fallback=f"Nie udaje ci się rozbić „{target.display_name()}”. Sprzęt cię wyśmiewa.",
                       name=target.display_name()), LOG_WARN)
            if room:
                room.noise_level += 1
        else:   # critical_failure
            self.log(t("feedback_break_critfail",
                       fallback=f"Coś trzeszczy — głównie ty. Cios odbija ci się rykoszetem.",
                       name=target.display_name()), LOG_DANGER)
            ch.take_damage(1)
            if room:
                room.noise_level += 2

        # Affinity nudge for environment plays.
        ch.affinity["environment"] = ch.affinity.get("environment", 0) + 1

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
        self.log(f"  [deploy] d20({raw}) + {stat}({mod:+d}) = {total} vs DC {dc} → {level}",
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
        # Pre-compute damage payload (used when something walks in)
        if "shock" in item.key or "shock" in item.tags:
            trap_record["effect"] = {"type": "damage_and_stun", "amount": 4 if level == "critical_success" else 3}
        elif "smoke" in item.key:
            trap_record["effect"] = {"type": "obscure", "amount": 2}
        elif "trip" in item.key or "tripwire" in item.tags:
            trap_record["effect"] = {"type": "knockdown", "amount": 1}
        else:
            trap_record["effect"] = {"type": "damage", "amount": 2 if level != "critical_success" else 4}
        traps.append(trap_record)

        self.log(t("feedback_deploy_ok",
                   fallback=f"Rozstawiasz: {item.display_name()}.",
                   name=item.display_name()), LOG_SUCCESS)
        room.noise_level += 1
        ch.affinity["trap"] = ch.affinity.get("trap", 0) + 1

        # Narrator hook
        nline = narrate("deploy_trap_success") or narrate("deploy_trap")
        if nline:
            self.log(nline, LOG_SYNDIC)
        try:
            from ..systems import achievements
            achievements.unlock(ch, "pulapka_z_niczego", world=self.world)
        except Exception:
            pass

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
        self.log(f"  [memetic:{method}] d20({raw}) + {stat}({mod:+d}) = {total} vs DC {dc} → {level}",
                 LOG_SYSTEM)

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
            if level == "critical_success":
                immediate.append({"type": "add_audience", "amount": 1})

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
        self.log(f"  [invoke_belief] d20({raw}) + {stat}({mod:+d}) = {total} vs DC {dc}",
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

    def _show_knowledge(self):
        """Render the structured knowledge journal."""
        from ..systems import knowledge as _kn
        self.log(t("ui_knowledge_header", fallback="Twoja wiedza:"), LOG_SYSTEM)
        for ln in _kn.summarize_for_journal(self.world):
            self.log(ln, LOG_NORMAL)

    def _show_beliefs(self):
        """Journal command: idee / plotki / wpływy / beliefs / rumors."""
        from ..systems import memetics
        seeds = memetics.all_active(self.world)
        if not seeds:
            self.log(t("ui_beliefs_empty",
                       fallback="Idee: na razie nic z twojej strony nie krąży."),
                     LOG_NORMAL)
            return
        self.log(t("ui_beliefs_header", fallback="Krążące idee i plotki:"),
                 LOG_SYSTEM)
        for s in seeds:
            self.log("  " + memetics.summarize_seed(s, lang="pl"), LOG_NORMAL)
        # Mention current floor's known rumors too. Memetic synthetic keys
        # `memetic:<seed_id>:<n>` are rendered to natural text via memetics;
        # plain rumor keys go through the rumor-template registry.
        f = self.world.current_floor
        if f and f.rumors:
            self.log(t("ui_beliefs_rumors_header",
                       fallback="Znane plotki na tym piętrze:"), LOG_SYSTEM)
            for r in f.rumors[-8:]:
                rendered = memetics.render_rumor_key(self.world, r, language="pl")
                self.log(f"  • {rendered or r}", LOG_NORMAL)

    # ── Event handling ───────────────────────────────────────────────────────

    def handle_keydown(self, ev):
        key = ev.key
        digit = _NUMS.get(key)
        mods = pygame.key.get_mods()
        shift_held = bool(mods & pygame.KMOD_SHIFT)
        ctrl_held  = bool(mods & pygame.KMOD_CTRL)

        if self.state == STATE_TITLE:
            # Arrow-key navigation mirroring the four visible items.
            title_actions = ["new_game", "load_game", "settings", "quit"]
            if key in (pygame.K_UP, pygame.K_w):
                self.title_idx = (self.title_idx - 1) % len(title_actions)
                self._suppress_textinput = True
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.title_idx = (self.title_idx + 1) % len(title_actions)
                self._suppress_textinput = True
                return
            if key == pygame.K_RETURN:
                action = title_actions[self.title_idx]
                if action == "new_game":
                    self.cc = {"step":"name","name_input":"","selected_bg":0}
                    self._suppress_textinput = True
                    self.input_text = ""
                    self.state = STATE_CREATE
                elif action == "load_game" and save_load.exists():
                    w = save_load.load()
                    if w is not None:
                        self.world = w; self.state = STATE_PLAY
                        self.log(t("log_save_loaded", fallback="Zapis wczytany."), LOG_SUCCESS)
                    else:
                        self.log(t("log_save_load_failed",
                                   fallback="Zapis uszkodzony."), LOG_DANGER)
                elif action == "settings":
                    # Prompt 11: open the settings popup.
                    self._open_settings()
                elif action == "quit":
                    pygame.quit(); raise SystemExit
                return
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
            if digit == "3":
                self._open_settings()
                return
            if digit == "4":
                pygame.quit(); raise SystemExit
            if key == pygame.K_l:
                set_language("en" if get_language() == "pl" else "pl")
                self._suppress_textinput = True
            return

        if self.state == STATE_SETTINGS:
            return self._handle_settings_keydown(key, shift_held)

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
                # Arrow navigation for the background list.
                if key in (pygame.K_UP, pygame.K_w):
                    self.cc["selected_bg"] = (self.cc.get("selected_bg",0) - 1) % len(bgs)
                    self._suppress_textinput = True
                    return
                if key in (pygame.K_DOWN, pygame.K_s):
                    self.cc["selected_bg"] = (self.cc.get("selected_bg",0) + 1) % len(bgs)
                    self._suppress_textinput = True
                    return
                if key == pygame.K_PAGEUP:
                    self.cc["selected_bg"] = max(0, self.cc.get("selected_bg",0) - 4)
                    self._suppress_textinput = True; return
                if key == pygame.K_PAGEDOWN:
                    self.cc["selected_bg"] = min(len(bgs)-1, self.cc.get("selected_bg",0) + 4)
                    self._suppress_textinput = True; return
                if key == pygame.K_HOME:
                    self.cc["selected_bg"] = 0
                    self._suppress_textinput = True; return
                if key == pygame.K_END:
                    self.cc["selected_bg"] = len(bgs) - 1
                    self._suppress_textinput = True; return
                if key == pygame.K_RETURN:
                    idx = self.cc.get("selected_bg", 0)
                    if 0 <= idx < len(bgs):
                        self._suppress_textinput = True
                        self.start_new_game(self.cc["name_input"], bgs[idx])
                    return
                if digit is not None:
                    idx = int(digit) - 1
                    if 0 <= idx < len(bgs):
                        self._suppress_textinput = True
                        self.start_new_game(self.cc["name_input"], bgs[idx])
                elif key == pygame.K_ESCAPE or key == pygame.K_BACKSPACE:
                    self.cc["step"] = "name"
            return

        if self.state == STATE_PLAY:
            return self._handle_play_keydown(ev, key, digit, shift_held, ctrl_held)

        if self.state == STATE_CLASS_OFFER:
            offered = self.offer_candidates or []
            if key in (pygame.K_UP, pygame.K_w) and offered:
                self.title_idx = (self.title_idx - 1) % len(offered)
                self._suppress_textinput = True
                return
            if key in (pygame.K_DOWN, pygame.K_s) and offered:
                self.title_idx = (self.title_idx + 1) % len(offered)
                self._suppress_textinput = True
                return
            if key == pygame.K_RETURN and offered:
                self._suppress_textinput = True
                self._accept_class(self.title_idx % len(offered))
                return
            if digit is not None:
                self._suppress_textinput = True
                self._accept_class(int(digit) - 1)
            return

        if self.state in (STATE_VICTORY, STATE_DEFEAT):
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = STATE_TITLE
                self.world = None
            return

    def _handle_play_keydown(self, ev, key, digit, shift_held, ctrl_held):
        """Prompt-08 keydown router for STATE_PLAY.

        Two input modes: `text` (default — typing fills input_text) and
        `nav` (arrows move selection, Enter activates option, typed
        letters trigger hotkeys). The mode is toggled by `/` or `T` and
        leaving navigation mode is always Escape.

        Prompt 10: when the journal overlay is open, hand the keypress
        to `_journal_handle_key` first; if it consumes the event, return.
        """
        # Journal overlay owns input while it's open.
        if self.journal_state.open:
            if self._journal_handle_key(key, shift_held):
                return

        # J / F2 toggle the journal from the play state too.
        if key in (pygame.K_F2,):
            self._open_journal(self.journal_state.tab); self._suppress_textinput = True
            return
        if key == pygame.K_j and self.input_mode == "nav":
            # In nav mode J already submits 'wiedza' command — keep that
            # behaviour. In text mode the textinput layer handles 'j' as a
            # typed character.
            pass

        # Global hotkeys that work in either mode — Ctrl+S save, F1/? help.
        if ctrl_held and key == pygame.K_s:
            ok = save_load.save(self.world)
            self.log(t("log_save_done", fallback="Zapisano.") if ok else
                     t("log_save_fail", fallback="Zapis nie powiódł się."),
                     LOG_SUCCESS if ok else LOG_DANGER)
            self._suppress_textinput = True
            return
        if key == pygame.K_F1:
            self._show_help()
            self._suppress_textinput = True
            return

        # Mode switching:
        # `/` or `T` => enter nav mode; Escape leaves nav mode (and also
        # clears the text input in text mode).
        if key == pygame.K_SLASH:
            self.input_mode = "text"
            self._suppress_textinput = True
            return
        if key == pygame.K_t and self.input_mode == "text" and not self.input_text:
            # Enter nav mode only when the input box is empty so 't' typed
            # inside a real command doesn't surprise the player.
            self.input_mode = "nav"
            self._suppress_textinput = True
            return

        if self.input_mode == "nav":
            # Arrows navigate the option list/group.
            if key in (pygame.K_UP, pygame.K_w):
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.move_selection(self.nav_state, -1)
                self._suppress_textinput = True
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.move_selection(self.nav_state, +1)
                self._suppress_textinput = True
                return
            if key in (pygame.K_LEFT, pygame.K_a):
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.cycle_group(self.nav_state, -1)
                self._suppress_textinput = True
                return
            if key in (pygame.K_RIGHT, pygame.K_d):
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.cycle_group(self.nav_state, +1)
                self._suppress_textinput = True
                return
            if key == pygame.K_TAB:
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.cycle_group(self.nav_state, -1 if shift_held else +1)
                self._suppress_textinput = True
                return
            if key == pygame.K_HOME:
                self._ensure_nav_state()
                self.nav_state.set_selected_index(0)
                self._suppress_textinput = True
                return
            if key == pygame.K_END:
                self._ensure_nav_state()
                g = self.nav_state.current_group()
                opts = self.nav_state.options_in(g)
                if opts:
                    self.nav_state.set_selected_index(len(opts) - 1, g)
                self._suppress_textinput = True
                return
            if key == pygame.K_RETURN:
                from ..ui import ui_nav
                self._ensure_nav_state()
                opt = ui_nav.current_option(self.nav_state)
                if opt and opt.enabled and opt.command:
                    self.submit_generated_command(opt.command)
                self._suppress_textinput = True
                return
            if key == pygame.K_ESCAPE:
                # Return to text mode.
                self.input_mode = "text"
                self._suppress_textinput = True
                return
            # Letter hotkeys in nav mode.
            if key == pygame.K_i:
                self.submit_generated_command("plecak"); self._suppress_textinput = True; return
            if key == pygame.K_m:
                self.submit_generated_command("mapa"); self._suppress_textinput = True; return
            if key == pygame.K_c:
                self.submit_generated_command("postać"); self._suppress_textinput = True; return
            if key == pygame.K_j:
                self.submit_generated_command("wiedza"); self._suppress_textinput = True; return
            if key == pygame.K_r:
                self.submit_generated_command("odpocznij"); self._suppress_textinput = True; return
            if key == pygame.K_QUESTION:   # may not fire on Polish layouts
                self._show_help(); self._suppress_textinput = True; return
            return

        # ── Text mode (default) ──────────────────────────────────────────
        # Prompt 12: when the input box is empty, arrow keys / Tab / Enter
        # drive the visible action panel directly — no mode toggle needed.
        # As soon as the player starts typing, text input takes priority
        # and the same keys revert to text-edit / history behavior.
        input_empty = not self.input_text
        if input_empty:
            from ..ui import ui_nav
            if key in (pygame.K_UP, pygame.K_w):
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.move_selection(self.nav_state, -1)
                    self._suppress_textinput = True
                    return
            if key in (pygame.K_DOWN, pygame.K_s):
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.move_selection(self.nav_state, +1)
                    self._suppress_textinput = True
                    return
            if key in (pygame.K_LEFT,):
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.cycle_group(self.nav_state, -1)
                    self._suppress_textinput = True
                    return
            if key in (pygame.K_RIGHT,):
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.cycle_group(self.nav_state, +1)
                    self._suppress_textinput = True
                    return
            if key == pygame.K_TAB:
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.cycle_group(self.nav_state, -1 if shift_held else +1)
                    self._suppress_textinput = True
                    return
            if key == pygame.K_RETURN:
                # Empty input + Enter = activate currently-selected nav
                # option. Submitting an empty command would be a no-op
                # anyway, so this can never steal a real command.
                self._ensure_nav_state()
                opt = ui_nav.current_option(self.nav_state)
                if opt and opt.enabled and opt.command:
                    self.submit_generated_command(opt.command)
                    self._suppress_textinput = True
                    return

        if key == pygame.K_RETURN:
            self.submit_input()
            return
        if key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
            return
        if key == pygame.K_ESCAPE:
            self.input_text = ""
            return
        # Up/Down browses command history when the input is empty or the
        # user has started browsing already.
        if key == pygame.K_UP and (not self.input_text or self.cmd_history_idx >= 0):
            if self.cmd_history:
                if self.cmd_history_idx == -1:
                    self.cmd_history_idx = len(self.cmd_history) - 1
                else:
                    self.cmd_history_idx = max(0, self.cmd_history_idx - 1)
                self.input_text = self.cmd_history[self.cmd_history_idx]
                self._suppress_textinput = True
            return
        if key == pygame.K_DOWN and self.cmd_history_idx >= 0:
            self.cmd_history_idx += 1
            if self.cmd_history_idx >= len(self.cmd_history):
                self.cmd_history_idx = -1
                self.input_text = ""
            else:
                self.input_text = self.cmd_history[self.cmd_history_idx]
            self._suppress_textinput = True
            return

    def _ensure_nav_state(self):
        """Build (or rebuild) the nav state on demand. Called both from
        handle_keydown and from draw."""
        from ..ui import ui_nav
        self.nav_state = ui_nav.build_play_options(self.world)

    def handle_textinput(self, ev):
        if self._suppress_textinput:
            self._suppress_textinput = False
            return
        if self.state == STATE_PLAY:
            # In nav mode, typing letters is suppressed — only hotkeys
            # routed through handle_keydown should fire.
            if self.input_mode == "nav":
                return
            # Prompt 10: journal overlay also swallows typed text.
            if self.journal_state.open:
                return
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
            ui.draw_title(s, save_load.exists(), selected_idx=self.title_idx)
        elif self.state == STATE_SETTINGS:
            ui.draw_settings(s, getattr(self, "settings_state", {}),
                             save_exists=save_load.exists())
        elif self.state == STATE_CREATE:
            ui.draw_creation(s, self.cc)
        elif self.state == STATE_PLAY:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  input_mode=self.input_mode, layout=L)
            self._ensure_nav_state()
            ui.draw_nav_panel(s, self.nav_state, self.input_mode, layout=L)
            # Prompt 10: journal overlay sits on top.
            if self.journal_state.open:
                ui.draw_journal(s, self.world, self.journal_state, layout=L)
        elif self.state == STATE_CLASS_OFFER:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  layout=L)
            # Overlay listing the suggested classes
            from ..ui.lang import t as tr
            from ..systems.classes import CLASS_CATALOG
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
        from ..config import PANEL_BG, BORDER, ACCENT, NORMAL_TEXT
        sw, sh = self.screen.get_size()
        w = sw - 200; h = max(160, 40 + len(lines)*22)
        x = (sw - w)//2; y = (sh - h)//2
        bg = pygame.Surface((sw, sh), pygame.SRCALPHA)
        bg.fill((0,0,0,160))
        self.screen.blit(bg, (0,0))
        pygame.draw.rect(self.screen, PANEL_BG, (x,y,w,h))
        pygame.draw.rect(self.screen, ACCENT, (x,y,w,h), 2)
        cy = y + 16
        for ln in lines:
            ui.text(self.screen, ln, x + 16, cy, NORMAL_TEXT, 16); cy += 24

    def _end_screen(self, title_str, success: bool):
        self.screen.fill((10,12,18))
        sw, sh = self.screen.get_size()
        col = (90,210,120) if success else (230,80,80)
        ui.text(self.screen, title_str, sw//2 - 200, 200, col, 26, True)
        if self.world:
            c = self.world.character
            ui.text(self.screen, f"{c.name} — D{self.world.current_floor.day_number() if self.world.current_floor else 0}",
                    sw//2 - 200, 260, (190,205,220), 16)
        ui.text(self.screen, t("end_press_enter", fallback="[Enter] Powrót do menu"),
                sw//2 - 200, sh - 80, (90,110,130), 14)
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
