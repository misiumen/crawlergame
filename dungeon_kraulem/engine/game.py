"""Game state machine for the revamp."""
import pygame

from ..config import (BASE_STATS, LOG_NORMAL, LOG_SYSTEM,
                     LOG_WARN, LOG_SUCCESS, LOG_SYNDIC, LOG_DANGER)
from ..ui.lang import t, get_language, set_language
from .world import WorldState
from .character import Character
from .floor import FloorState
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
STATE_SLOTS     = "slots"      # P29.9: save-slot picker (3 slots)
# P29.60 — Arena testowa: combat-only sandbox.
# STATE_ARENA_MENU = wybór wariantu, STATE_ARENA_PLAY reuses STATE_PLAY
# input/render ale z arena_mode flag żeby ominąć floor descent / save.
STATE_ARENA_MENU = "arena_menu"
STATE_ARENA_PLAY = "arena_play"


_NUMS = {
    pygame.K_1:"1", pygame.K_2:"2", pygame.K_3:"3", pygame.K_4:"4", pygame.K_5:"5",
    pygame.K_6:"6", pygame.K_7:"7", pygame.K_8:"8", pygame.K_9:"9", pygame.K_0:"0",
    pygame.K_KP1:"1", pygame.K_KP2:"2", pygame.K_KP3:"3", pygame.K_KP4:"4", pygame.K_KP5:"5",
    pygame.K_KP6:"6", pygame.K_KP7:"7", pygame.K_KP8:"8", pygame.K_KP9:"9", pygame.K_KP0:"0",
}


# P29.44 — standalone helper, żeby unit-testy mogły testować drop bez
# tworzenia całego Game'a (Game potrzebuje pygame screen).
def drop_miniboss_map(world, room, dead_target, floor_num: int):
    """Po zabiciu minibossa spawnuje map_fragment (F1-9) lub 50%
    floor_map (F10+) w pokoju zwłok. Zwraca utworzony Entity albo
    None przy błędzie."""
    import random as _r
    seed = getattr(world, "random_seed", None) or 0
    # Stabilny deterministic: salt o entity_id zwłok, żeby seed
    # generatora pięter nie powodował zawsze tego samego dropu.
    salt = int(getattr(dead_target, "entity_id", 0) or 0)
    rng = _r.Random(seed * 1009 + salt * 31 + 7)
    item_key = "map_fragment"
    if floor_num >= 10 and rng.random() < 0.5:
        item_key = "floor_map"
    try:
        from ..content.items import make_item
    except Exception:
        return None
    try:
        it = make_item(item_key, location_id=room.room_id)
    except Exception:
        return None
    try:
        world.register(it)
    except Exception:
        pass
    room.entities.append(it)
    return it


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

        # Prompt 18: explicit arming for nav-option Enter activation.
        # The Prompt-14 "empty input + Enter → fire selected option" UX
        # was a foot-gun: after a failed command, additional Enter presses
        # (autorepeat, accidental taps) would spam the selected nav option
        # (usually 'rozejrzyj się'). Now Enter on empty only fires the
        # nav option when the player has explicitly armed selection by
        # pressing an arrow / Tab. Any typed character or submit disarms.
        self._nav_selection_armed = False

        # Prompt 08: keyboard cursor navigation.
        # input_mode: "text" (default — typing goes to input_text and arrows
        # are inert) or "nav" (typing is suppressed except letters that
        # match hotkeys; arrows move selection; Enter activates option).
        self.input_mode = "text"
        self.nav_state = None         # built lazily per frame in draw()
        # Title-menu cursor index for arrow-key navigation.
        self.title_idx = 0
        # P29.9 — save-slot picker state (mode + cursor index).
        self.slot_picker_mode = "new"
        self.slot_picker_idx = 0
        # Command history (lightweight) — Up/Down in text mode walks it.
        self.cmd_history: list[str] = []
        self.cmd_history_idx = -1     # -1 = "current draft (not in history)"

        # Character creation sub-state.
        # P29.35 — extended with species + companion pickers driven by
        # meta_progression unlocks. selected_species == 0 always means
        # baseline_human; selected_companion == 0 means "no starting
        # companion" (the companion step is skipped entirely when
        # nothing is unlocked).
        self.cc = {"step": "name", "name_input": "",
                   "selected_bg": 0,
                   "selected_species": 0,
                   "selected_companion": 0}

        # Class / species offers
        self.offer_candidates = []

        # Prompt 20: pending disambiguation from the last ambiguous_target
        # validation. Holds the original intent + candidate entity ids so
        # follow-up commands like "oba" / "1" / "brudny" can resolve.
        # None means no pending disambiguation. Cleared on any command
        # that doesn't match a disambiguation follow-up.
        self.pending_disambiguation = None  # dict | None

        # P29.41 — runtime stan otwartego dialogu z NPC. Patrz
        # engine/dialogue.py + STATE_DIALOG. None == brak otwartej
        # rozmowy. Ustawiane przy interceptcie "talk", czyszczone
        # przy zakończeniu drzewka.
        self.dialogue_state = None  # engine.dialogue.DialogueState | None

        # Prompt 23.5 (backlog #1): log scrollback. 0 = pinned to newest.
        # PgUp / PgDn bump this in `_handle_play_keydown`; new log writes
        # auto-reset to 0 so the player never misses the latest hit.
        self.log_scroll = 0

        # Prompt 23.5 (backlog #2): when an action-panel option commits a
        # command, this carries the option's `target_id` through one
        # dispatch cycle so the validator can bypass disambiguation for
        # the already-resolved target. Cleared after each command.
        self._preresolved_target_id = None

        # P24.5: full-screen graphical map overlay (M key toggles).
        self.full_map_open = False

        # P25: paper-doll slot swap popover. When open, holds the slot
        # being edited + the cursor index within the eligible list.
        # Cleared on Esc / commit / clicking outside.
        self.slot_popover_open: Optional[str] = None  # slot key
        self.slot_popover_idx: int = 0

        # P24.5: per-frame click registry. Draw functions populate it;
        # mouse handlers query it. Cleared at the start of every draw.
        from ..ui.click_registry import ClickRegistry
        self.click_registry = ClickRegistry()
        # Mouse hover state: last-known mouse position so the tooltip
        # renderer knows where to draw. Updated on MOUSEMOTION.
        self._mouse_xy = (-1, -1)
        # P24.5: pending UI side-channels populated by clickable panels
        # (paper-doll slot picked, quick-strip item used). Game polls
        # them at top of update() and dispatches the right action.
        # Avoids passing Game callbacks into pure UI code.
        # (These are read by `_drain_ui_inputs()`.)
        # Each pending value is read-once: cleared after dispatch.

    # ── Helpers ──────────────────────────────────────────────────────────────

    def log(self, msg, cat=LOG_NORMAL):
        if self.world: self.world.log_msg(msg, cat)
        # Prompt 23.5 (backlog #1): any new log entry auto-pins the view
        # back to the newest. Without this, a player scrolled into history
        # would silently miss new entries (e.g. an enemy entering combat).
        self.log_scroll = 0

    def _bump_threat(self, amount: int, source: str = "",
                     room=None) -> None:
        """P29.0 — central helper: every loud action routes its noise
        through `threat.bump` so threshold-crossings fire (entities
        escalate, log lines emit). Old `room.noise_level += N`
        mutations leaked threat without escalation; this is the
        single chokepoint that fixes it everywhere.

        `room` defaults to player's current room. `source` is a
        free-text analytics tag (never shown to player)."""
        if self.world is None or amount <= 0:
            return
        if room is None:
            room = (self.world.current_floor.current_room()
                    if self.world.current_floor else None)
        if room is None:
            return
        try:
            from . import threat as _threat
            for ln in _threat.bump(self.world, room, int(amount),
                                   source=source):
                self.log(ln, LOG_WARN)
        except Exception:
            pass

    # ── P29.8: death detection ───────────────────────────────────────────────

    def _check_player_dead(self, cause: str = "", cause_label: str = "") -> bool:
        """Single chokepoint called after any path that can lower the
        player's HP. Returns True if the player has actually died (and
        the state has flipped to STATE_DEFEAT); False otherwise.

        Handles last-stand: the first time HP would drop to 0 in a run,
        we set hp=1 and burn `character.near_death_used`. Lets one
        accidental crit not end a 90-minute run. The next 0-HP event
        is the real death.

        Side effects on actual death:
          * cache run_summary on self for the end screen to render;
          * emit a death log line + DCC anti-host commentary;
          * play sfx 'player_death' (best-effort);
          * wipe the save file (permadeath default);
          * flip self.state → STATE_DEFEAT.
        """
        if self.world is None:
            return False
        ch = self.world.character
        if ch is None or ch.hp > 0:
            return False
        # P29.8 — idempotence: if we've already flipped to DEFEAT,
        # don't overwrite the death cause set by the original site.
        # The combat round-end check fires AFTER the immediate-hit
        # check, and without this guard the round-end label would
        # clobber the (more specific) "od ciosu Bandziora" line.
        if self.state == STATE_DEFEAT:
            return True
        # Last-stand: once per run, leave the player at 1 HP and shout.
        if not ch.near_death_used:
            ch.hp = 1
            ch.near_death_used = True
            from ._debug import swallow
            with swallow("audio.play_sfx[last_stand]"):
                audio.play_sfx("player_hit")
            self.log("Konferansjer warknął: „NIE TAK SZYBKO.” "
                     "Resztki adrenaliny — zostajesz na 1 HP. Raz.",
                     LOG_DANGER)
            # P29.12 — tutorial: explain that last-stand is one-shot.
            try:
                from . import tutorial as _tut
                _tut.try_show_tip(self.world, "low_hp", force_any_floor=True)
            except Exception:
                pass
            # P29.15 — last-stand achievement.
            try:
                from ..systems import achievements as _ach
                _ach.unlock(ch, "anty_host_warknal", world=self.world)
            except Exception:
                pass
            # P29.20 — companion chatter on near-death.
            try:
                from . import companion_voice as _cv
                _cv.maybe_say(self.world, "hp_low")
            except Exception:
                pass
            return False
        # Real death.
        ch.run_death_cause = cause
        ch.run_death_cause_label = cause_label or (cause or "nieznana")
        # Cache the summary so the end screen can render it without
        # re-scraping every draw().
        try:
            from . import run_summary as _rs
            self.run_summary = _rs.build_run_summary(self.world)
            self.log(self.run_summary.death_log_line, LOG_DANGER)
            self.log(self.run_summary.anti_host_line, LOG_SYNDIC)
            # P29.20 — companion's last words.
            try:
                from . import companion_voice as _cv
                _cv.maybe_say(self.world, "player_death", force=True)
            except Exception:
                pass
        except Exception:
            self.log("Tracisz nitkę. Reszta jest hałasem.", LOG_DANGER)
        # SFX
        from ._debug import swallow
        with swallow("audio.play_sfx[player_death]"):
            audio.play_sfx("player_death")
        # P29.26 — append run to persistent history BEFORE deleting
        # the slot. record_run reads the same world so order matters.
        from ._debug import swallow as _swallow
        with _swallow("run_history.record_run[death]"):
            from . import run_history as _rh
            _rh.record_run(self.world, victory=False)
        # P29.34 — evaluate meta-progression unlocks before the save
        # is wiped. Each newly qualifying option fires a Polish line
        # in the death log so the player knows what got opened.
        with _swallow("meta_progression.record_unlocks[death]"):
            from . import meta_progression as _mp
            new_keys = _mp.record_unlocks_for_run(self.world,
                                                  victory=False)
            for k in new_keys:
                ud = _mp.UNLOCK_CATALOG.get(k)
                if ud is not None:
                    self.log(
                        f"Sezon otwiera nowe opcje: "
                        f"„{ud.label_pl}” — {ud.reward_pl}",
                        LOG_SUCCESS)
        # Permadeath: wipe the save so resume can't bring you back.
        with _swallow("save_load.delete[death]"):
            from . import save_load
            save_load.delete()
        self.state = STATE_DEFEAT
        return True

    def _bump_run_counter(self, field_name: str, by: int = 1) -> None:
        """Tiny helper used by the death-summary system to bump
        cumulative run counters on the character. Silently noops when
        there is no world / character — keeps the call sites
        single-line. See engine/character.py for the run_* fields."""
        if self.world is None or self.world.character is None:
            return
        ch = self.world.character
        cur = int(getattr(ch, field_name, 0) or 0)
        setattr(ch, field_name, cur + int(by))

    def _stash_disambiguation_on_invalid(self, v, intent) -> None:
        """P26c — cross-handler disambiguation latch.

        Any handler that runs its own `validate()` (salvage, break,
        butcher, wear, deploy, env-fallback, etc.) must call this on
        the invalid result so that a subsequent `oba` / `1` / partial-
        name from the player can resolve. Without this, `oba` after a
        handler-internal validate falls through to the parser, which
        doesn't understand it as a command and reports "Nie rozumiem".

        Replicates the standard pipeline's behavior at game.py:1433.
        """
        if v is None or intent is None:
            return
        if (v.reason == "ambiguous_target"
                and getattr(v, "possible_entity_ids", None)):
            self.pending_disambiguation = {
                "intent": intent,
                "entity_ids": list(v.possible_entity_ids),
                "names": list(v.possible_interpretations or []),
            }
        else:
            self.pending_disambiguation = None

    # ── State transitions ────────────────────────────────────────────────────

    def start_new_game(self, name: str, background: str,
                        species: str = "baseline_human"):
        """Create a fresh world + character.

        P29.34: optional `species` parameter accepts any species key
        previously unlocked via meta-progression. Defaults to
        baseline_human (the pre-P29.34 behavior). Species bonuses
        get applied AFTER stat-profile + background-loadout so they
        stack on top of the base.
        """
        self.world = WorldState()
        self.world.character.name = name or "Bezimienny"
        self.world.character.background = background
        # P29.34 — species is an extra axis on top of background.
        # The Character dataclass already has species_key (P29.5).
        self.world.character.species_key = species or "baseline_human"
        # P27.6 balance pass: stat allocations per background are now
        # absolute target values, not modest +1 bumps. Each tło gets a
        # distinctive profile with at least one stat >=13 (meaningful
        # +1 or +2 mod) and at least one stat <=9 (clear weakness).
        # Player feels different from turn 1 across backgrounds.
        STAT_PROFILES = {
            # (STR, DEX, CON, INT, WIS, CHA)
            "office_worker":     {"STR": 8,  "DEX": 10, "CON": 9,  "INT": 14, "WIS": 11, "CHA": 12},
            "mechanic":          {"STR": 13, "DEX": 12, "CON": 12, "INT": 13, "WIS": 9,  "CHA": 9},
            "nurse":             {"STR": 9,  "DEX": 11, "CON": 11, "INT": 12, "WIS": 14, "CHA": 13},
            "cook":              {"STR": 11, "DEX": 14, "CON": 12, "INT": 10, "WIS": 10, "CHA": 9},
            "security_guard":    {"STR": 14, "DEX": 11, "CON": 13, "INT": 9,  "WIS": 9,  "CHA": 10},
            "courier":           {"STR": 10, "DEX": 15, "CON": 12, "INT": 9,  "WIS": 11, "CHA": 9},
            "student":           {"STR": 8,  "DEX": 10, "CON": 9,  "INT": 15, "WIS": 12, "CHA": 12},
            "streamer":          {"STR": 8,  "DEX": 11, "CON": 9,  "INT": 11, "WIS": 9,  "CHA": 15},
            "soldier":           {"STR": 14, "DEX": 12, "CON": 14, "INT": 9,  "WIS": 11, "CHA": 8},
            "unemployed_hustler":{"STR": 9,  "DEX": 13, "CON": 10, "INT": 11, "WIS": 9,  "CHA": 14},
            "janitor":           {"STR": 12, "DEX": 10, "CON": 14, "INT": 9,  "WIS": 11, "CHA": 8},
            "paramedic":         {"STR": 10, "DEX": 12, "CON": 11, "INT": 13, "WIS": 14, "CHA": 10},
            "opiekun_zwierzaka": {"STR": 9,  "DEX": 11, "CON": 10, "INT": 10, "WIS": 14, "CHA": 13},
        }
        profile = STAT_PROFILES.get(background)
        if profile:
            for stat, value in profile.items():
                self.world.character.stats[stat] = value

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
            # Prompt 19 — opiekun_zwierzaka starts with food for the pet
            # and a battered carrier; the pet itself is assigned below.
            "opiekun_zwierzaka": ["snack_bar","duct_tape"],
        }.get(background, ["cracked_mug"])
        for k in starters:
            it = make_item(k, location_id="inventory:player")
            self.world.register(it)
            self.world.character.inventory_ids.append(it.entity_id)

        # P27.7 (P27-MECH-4) — pre-equipped starter loadouts per
        # background. Items in STARTER_LOADOUT are created and IMMEDIATELY
        # equipped to the named slot (or wielded in main/off). Player
        # opens the game already kitted — no "fight the first patrol with
        # bare hands" phase. Items that fail validation (slot mismatch,
        # already equipped, etc.) silently fall back into inventory.
        from . import equipment as _eq
        STARTER_LOADOUT = {
            "office_worker":     [("spodnie_robocze","legs"),("opaska_imienna","accessory")],
            "mechanic":          [("pas_narzedziowy","back"),("spodnie_robocze","legs"),("duct_tape","main")],
            "nurse":             [("fartuch_laboratoryjny","torso"),("opaska_imienna","accessory")],
            "cook":              [("fartuch_laboratoryjny","torso"),("cheap_knife","main")],
            "security_guard":    [("kamizelka_taktyczna","torso"),("buty_taktyczne","legs"),("flashlight","main")],
            "courier":           [("plecak_taktyczny","back"),("buty_taktyczne","legs")],
            "student":           [("czapka_uszanka","head"),("spodnie_robocze","legs")],
            "streamer":          [("sponsor_kepi","head"),("zegarek_sponsora","accessory")],
            "soldier":           [("kamizelka_taktyczna","torso"),("buty_taktyczne","legs"),("cheap_knife","main")],
            "unemployed_hustler":[("kurtka_skorzana","torso"),("improvised_lockpick","off")],
            "janitor":           [("kalosze","legs"),("pas_narzedziowy","back")],
            "paramedic":         [("fartuch_laboratoryjny","torso"),("buty_taktyczne","legs"),("dirty_bandage","main")],
            "opiekun_zwierzaka": [("kurtka_skorzana","torso"),("snack_bar","off")],
        }
        for item_key, slot in STARTER_LOADOUT.get(background, []):
            try:
                it = make_item(item_key, location_id="inventory:player")
                self.world.register(it)
                self.world.character.inventory_ids.append(it.entity_id)
                if slot in ("main", "off"):
                    if slot == "main":
                        self.world.character.wielded_main_id = it.entity_id
                    else:
                        self.world.character.wielded_offhand_id = it.entity_id
                    try:
                        self.world.character.inventory_ids.remove(it.entity_id)
                    except ValueError:
                        pass
                else:
                    ok, _prev, _why = _eq.equip(self.world,
                                                self.world.character,
                                                it, slot)
                    # If equip fails, item just stays in inventory.
            except Exception:
                pass

        # P29.52 — starting recipes per background. Większość klas zna
        # 2 podstawowe (improvised_bandage + improvised_knife). Klasy
        # rzemieślnicze (mechanic/cook/paramedic/soldier) — więcej.
        # Reszta przepisów (25+) wymaga znalezienia recipe_note w
        # lochu albo odblokowania przez sponsora.
        try:
            from ..content import crafting as _cr
            self.world.character.known_recipes = \
                _cr.starting_recipes_for(background)
        except Exception:
            pass

        # Prompt 19 — pet-owner background gets a random companion. The
        # pet is registered BEFORE Floor 1 is built so its location_room_id
        # gets set to the start room (which doesn't exist yet); we patch
        # location_room_id after build below.
        if background == "opiekun_zwierzaka":
            self._assign_starter_pet()

        # Build Floor 1
        self.world.current_floor = build_floor_1(self.world)
        self.world.floor_number = 1
        # Place the pet in the player's starting room.
        if background == "opiekun_zwierzaka":
            from . import companion as _comp
            pet = _comp.active_pet(self.world)
            if pet is not None:
                pet.location_room_id = self.world.current_floor.current_room_id
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
        # P29.34 — apply species + origin bonuses on top of the
        # background's stat profile + loadout. Each route is idempotent
        # and only changes the character; world/state stay untouched.
        try:
            self._apply_species_bonuses()
            self._apply_origin_bonuses()
            self._apply_starting_companion()
        except Exception:
            pass
        # P29.12 — first-time welcome tip.
        try:
            from . import tutorial as _tut
            _tut.try_show_tip(self.world, "welcome")
            _tut.try_show_tip(self.world, "save_slots")
        except Exception:
            pass
        self.state = STATE_PLAY

    def _apply_species_bonuses(self) -> None:
        """P29.34 — apply species stat/tag changes at character
        creation. Backwards-compatible: baseline_human is a no-op
        and pre-P29.34 saves continue to work."""
        ch = self.world.character
        sk = (ch.species_key or "baseline_human").strip()
        if sk == "baseline_human" or not sk:
            return
        # Stat tweaks. Keep modest — these are starting tilts, not
        # power spikes. The audit's "additive, not harder" principle.
        SPECIES_STATS = {
            "species_mutant_chemiczny": {"CON": +1},
            "species_grzybica":         {"WIS": +1},
            "species_cyborg_recyklingu":{"STR": +1},
            "species_pamietajacy":      {"INT": +1},
            "species_kolyski_anti_hosta": {"STR": +1, "DEX": +1,
                                            "CON": +1, "INT": +1,
                                            "WIS": +1, "CHA": +1},
        }
        for stat, delta in (SPECIES_STATS.get(sk) or {}).items():
            ch.stats[stat] = int(ch.stats.get(stat, 10)) + int(delta)
        # Resists / vulnerabilities — flag on flags so combat picks
        # them up via Character.is_resistant / is_vulnerable readers.
        if ch.flags is None: ch.flags = {}
        if sk == "species_mutant_chemiczny":
            ch.flags["species_immune_to"] = "poison"
            ch.flags["species_vulnerable_to"] = "fire"
            self.log("Twoje ciało jest pokryte chemicznymi łuskami. "
                     "Truciznę ignorujesz, ale ogień parzy bardziej.",
                     LOG_SYSTEM)
        elif sk == "species_grzybica":
            ch.flags["species_regenerates"] = 1   # 1 HP / 10 min
            self.log("Z twojego ramienia wystaje grzybnia. "
                     "Regenerujesz, ale ogień cię niszczy.", LOG_SYSTEM)
        elif sk == "species_cyborg_recyklingu":
            ch.flags["species_metal_limb"] = True
            self.log("Jedna z twoich kończyn jest mechaniczna. Złom "
                     "naprawia ją zamiast leków.", LOG_SYSTEM)
        elif sk == "species_pamietajacy":
            ch.flags["species_memory"] = True
            self.log("Ministerstwo edytowało ci pamięć. Czasem "
                     "wiesz rzeczy, których nie powinieneś.", LOG_SYSTEM)
        elif sk == "species_kolyski_anti_hosta":
            self.log("Jesteś rebrandowanym uczestnikiem. Konferansjer "
                     "zna cię osobiście. To nie znaczy, że cię lubi.",
                     LOG_SYSTEM)

    def _apply_starting_companion(self) -> None:
        """P29.34 — if the player previously unlocked a companion
        AND chose to start with it (signaled by self._chosen_companion
        set by the slot picker), instantiate that companion now.

        Default: no starting companion (pre-P29.34 behavior). Pet
        catalog still applies via the existing P19 floor-1 grant
        path."""
        chosen = getattr(self, "_chosen_companion", "")
        if not chosen:
            return
        if chosen == "companion_papuga_anty_host":
            try:
                from . import companion_voice as _cv
                _cv.add_flagship_pet(self.world)
                self.log("Papuga Konferansjera siada na twoim ramieniu. "
                         "Patrzy się ironicznie.", LOG_SUCCESS)
            except Exception:
                pass

    def _apply_origin_bonuses(self) -> None:
        """P29.34 — apply origin (meta-unlocked variant) bonuses.
        Origins extend the existing backgrounds list, so the
        character's `background` field stores the chosen origin key."""
        ch = self.world.character
        bg = (ch.background or "").strip()
        if not bg.startswith("origin_"):
            return
        if ch.flags is None: ch.flags = {}
        if bg == "origin_drugi_cykl":
            ch.audience_rating = max(int(ch.audience_rating or 0), 5)
            ch.run_audience_peak = max(int(ch.run_audience_peak or 0), 5)
            ch.flags["origin_has_scar"] = True
            self.log("Drugi cykl. Blizna na lewym policzku otwiera "
                     "się dla kamery sama.", LOG_SYSTEM)
        elif bg == "origin_sponsorowany":
            # Find any sponsor with persistent attention ≥10 from
            # the previous run; default to NovaChem if none.
            ch.flags["origin_sponsor_doubled"] = True
            try:
                from . import sponsors as _sp
                _sp.adjust_attention(self.world, "novachem_biotech", 5)
            except Exception:
                pass
            self.log("Kontrakt sponsorski cię trzyma — sponsor już "
                     "ci ufa, ale błędy też będą podwójne.", LOG_SYSTEM)
        elif bg == "origin_zhanbiony_showman":
            ch.audience_rating = 20
            ch.run_audience_peak = max(int(ch.run_audience_peak or 0), 20)
            ch.flags["origin_wanted_kanal_7"] = True
            try:
                from . import sponsors as _sp
                _sp.adjust_attention(self.world, "kanal_7_krawedz", -3)
            except Exception:
                pass
            self.log("Wracasz jako zhańbiony showman. Widownia cię "
                     "pamięta — Kanał 7 też. Niedobrze.", LOG_SYSTEM)

    # ── Prompt 23: wield / sheathe / coat handlers ───────────────────────

    def _resolve_inventory_item(self, name: str):
        """Match `name` to an item in inventory by display name, key, or
        Polish-stem match. Returns the Entity or None."""
        from .polish_text import polish_match, fold as _fold
        ch = self.world.character
        name_f = _fold(name.strip())
        if not name_f:
            return None
        # Direct display-name match first.
        for ent_id in (ch.inventory_ids or []):
            ent = self.world.get(ent_id)
            if ent is None: continue
            if _fold(ent.display_name()) == name_f or _fold(ent.key) == name_f:
                return ent
        # Polish-stem fallback (handles inflections).
        for ent_id in (ch.inventory_ids or []):
            ent = self.world.get(ent_id)
            if ent is None: continue
            if polish_match(name_f, _fold(ent.display_name())) or \
               polish_match(name_f, _fold(ent.key.replace("_", " "))):
                return ent
        return None

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
    _CONSUMABLE_EFFECTS = {
        "snack_bar":      {"heal": 12, "clear": []},
        "coffee":         {"heal": 4,  "clear": ["afraid", "shaken"]},
        "dirty_bandage":  {"heal": 18, "clear": ["bleeding"]},
        "cracked_mug":    {"heal": 1,  "clear": []},   # tea? whatever's in it.
        "battery":        {"heal": 0,  "buff": "next_tech_plus2"},
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
        heal = int(spec.get("heal", 0))
        if heal > 0:
            heal = int(round(heal * _cf.heal_multiplier(ch)))
            pre = ch.hp
            ch.heal(heal)
            self.log(t("feedback_consume_heal",
                       fallback=f"Konsumujesz „{chosen.display_name()}”. "
                                f"+{ch.hp - pre} HP ({ch.hp}/{ch.max_hp}).",
                       name=chosen.display_name(),
                       gained=ch.hp - pre, hp=ch.hp, max=ch.max_hp),
                     LOG_SUCCESS)
        else:
            self.log(f"Konsumujesz „{chosen.display_name()}”.", LOG_NORMAL)
        # Clear listed statuses.
        for cond in spec.get("clear", []):
            if cond in ch.conditions:
                ch.conditions.remove(cond)
                self.log(f"  Stan „{cond}” mija.", LOG_SUCCESS)
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

    def _show_prep_readout(self) -> None:
        """Prompt 20 — print a structured 'what can I do right now?'
        list focused on combat prep. Lists:
          * time remaining to next scheduled arrival (if any)
          * deployable items in inventory
          * environmental hooks (objects with `push`/`break`/`hack`
            affordances) in the current room
          * visible exits
          * any armed traps already in place
        Does NOT advance time (1-min cost is cheap and the player will
        actually inspect things after this anyway).
        """
        floor = self.world.current_floor
        room = floor.current_room() if floor else None
        if room is None:
            self.log("Nigdzie nie jesteś.", LOG_WARN)
            return
        self.log("— Plan obrony —", LOG_SYSTEM)

        # P29.0 — no more "patrol arrival countdown". Show local threat
        # instead: how aware are the things already in this room?
        try:
            from . import threat as _threat
            hostiles = [e for e in room.entities
                        if e.is_alive() and e.entity_type == "monster"]
            if not hostiles:
                self.log("  W pokoju cicho. Nikt nie czeka.", LOG_NORMAL)
            else:
                for ent in hostiles:
                    lvl = int(getattr(ent, "threat_level", 0) or 0)
                    label = _threat.threat_label(lvl)
                    self.log(f"  „{ent.display_name()}” — {label}",
                             LOG_DANGER if lvl >= 2 else LOG_WARN)
            self.log(f"  hałas w pokoju: {int(getattr(room, 'noise_level', 0))}",
                     LOG_NORMAL)
        except Exception:
            pass

        # Deployable items in inventory.
        deployable = []
        for eid in (self.world.character.inventory_ids or []):
            it = self.world.get(eid)
            if it is None:
                continue
            tags = list(it.tags or [])
            affs = list(it.affordances or [])
            if "trap" in tags or "smoke" in tags or "tripwire" in tags or \
               "deploy" in affs:
                deployable.append(it.display_name())
        if deployable:
            self.log("  Do rozstawienia: " + ", ".join(deployable),
                     LOG_NORMAL)

        # Environmental hooks — objects you can interact with in
        # spectacle-friendly ways (push, break, hack, force).
        hooks = []
        for e in room.visible_entities():
            if e.entity_type in ("monster", "crawler", "npc"):
                continue
            affs = set(e.affordances or [])
            if affs & {"push_into","throw_at","break","force","hack"}:
                # Highlight which moves apply.
                actions = ", ".join(sorted(affs &
                    {"push_into","throw_at","break","force","hack"}))
                hooks.append(f"{e.display_name()} ({actions})")
        if hooks:
            self.log("  W otoczeniu: " + " · ".join(hooks), LOG_NORMAL)

        # Already-armed traps.
        armed = []
        for trap in ((room.state or {}).get("player_traps") or []):
            if not trap.get("triggered"):
                armed.append(trap.get("display_name", "pułapka"))
        if armed:
            self.log("  Już rozstawione: " + ", ".join(armed),
                     LOG_SUCCESS)

        # Visible exits.
        exit_labels = [lbl for lbl, ed in (room.exits or {}).items()
                       if not ed.get("hidden")]
        if exit_labels:
            self.log("  Wyjścia: " + ", ".join(exit_labels), LOG_NORMAL)

        if not (deployable or hooks or armed or exit_labels):
            self.log("  Pusto. Naprawdę pusto.", LOG_WARN)

    def _resolve_disambiguation(self, text_val: str) -> bool:
        """Prompt 20: handle a short reply that picks among the candidates
        from a previous ambiguous_target. Returns True iff the reply was
        consumed (and the original action got re-issued, possibly several
        times). Returns False if the reply doesn't look like a follow-up
        and should be parsed as a fresh command.

        Supported follow-up forms:
          - "oba" / "obu" / "obydwa" / "wszystko" / "wszystkie" /
            "both" / "all"               -> pick ALL candidates
          - "1" / "2" / "pierwszy" / "drugi" / "trzeci" -> by index
          - any partial-name match against candidate display names
        """
        pending = self.pending_disambiguation
        if not pending or not pending.get("entity_ids"):
            return False
        entity_ids = list(pending["entity_ids"])
        names      = list(pending.get("names") or [])
        orig       = pending["intent"]
        verb       = (getattr(orig, "verb", "") or
                      getattr(orig, "normalized_text", "").split()[0] or
                      "podnieś")
        from .polish_text import fold as _fold
        t_f = _fold(text_val)
        if not t_f:
            return False

        # 1. "all" / "both" forms.
        ALL_TOKENS = {"oba","obu","obydwa","obydwu","obydwoje","wszystko",
                      "wszystkie","wszystkim","both","all","everything"}
        # Token-level match: any token in the input matches the set.
        in_tokens = set(t_f.replace(",", " ").split())
        if in_tokens & ALL_TOKENS:
            # Clear BEFORE re-issuing so the synthesized commands don't
            # recursively hit the disambiguation path.
            self.pending_disambiguation = None
            self._reissue_for_entities(verb, entity_ids, label="oba")
            return True

        # 2. Numeric pick. "1" / "2" or "pierwszy" / "drugi" / etc.
        ORDINAL_MAP = {"pierwszy":1,"drugi":2,"trzeci":3,"czwarty":4,"piaty":5,
                       "piąty":5,"first":1,"second":2,"third":3,"fourth":4,
                       "fifth":5}
        picked_idx = None
        if t_f.isdigit():
            picked_idx = int(t_f)
        else:
            for tok in in_tokens:
                if tok in ORDINAL_MAP:
                    picked_idx = ORDINAL_MAP[tok]; break
        if picked_idx is not None and 1 <= picked_idx <= len(entity_ids):
            self.pending_disambiguation = None
            self._reissue_for_entities(verb, [entity_ids[picked_idx - 1]],
                                       label=str(picked_idx))
            return True

        # 3. Partial name match against candidate display names.
        # Use polish_match (5-char stem) so "brudny" matches "brudny
        # bandaż" without needing the full phrase.
        from .polish_text import polish_match
        matched_ids = []
        for ent_id, name in zip(entity_ids, names):
            if polish_match(t_f, _fold(name)):
                matched_ids.append(ent_id)
        if matched_ids:
            self.pending_disambiguation = None
            self._reissue_for_entities(verb, matched_ids,
                                       label=text_val[:40])
            return True

        # No match — caller will clear pending and parse fresh.
        return False

    def _reissue_for_entities(self, verb: str, entity_ids,
                              *, label: str = "") -> None:
        """Re-execute the disambiguated action for each picked entity.
        We synthesize a command `<verb> <display_name>` per entity and
        feed it back through the normal handler — that way every hook
        (combat, audience, sponsors) fires correctly per-entity."""
        if not entity_ids:
            return
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            return
        if len(entity_ids) > 1:
            self.log(f"  → {label or 'wszystkie'} "
                     f"({len(entity_ids)} obiekt(ów))", LOG_SYSTEM)
        # Re-emit per-entity. Use exact display name so the parser
        # resolves unambiguously this time.
        for eid in entity_ids:
            ent = self.world.get(int(eid))
            if ent is None or ent.location_id != room.room_id:
                continue
            name = ent.display_name() if hasattr(ent, "display_name") else \
                   getattr(ent, "fallback_name", "")
            cmd = f"{verb} {name}".strip()
            # NOTE: re-enter via _handle_play_input (not submit_input) so
            # the command is treated as a player action but not re-echoed
            # in the log (the "→ oba (2)" line already documents intent).
            self._handle_play_input(cmd)

    def _assign_starter_pet(self):
        """Prompt 19 — roll one random pet from the v1 catalog and
        register it as the player's first companion. Logs the intro line
        so the player sees the assignment in the opening narration."""
        from ..content.data import pets as _pets
        from . import companion as _comp
        import random as _r
        # Use the world's random seed if present so save/replay is
        # deterministic; fall back to module random otherwise.
        seed = getattr(self.world, "random_seed", None)
        rng = _r.Random(seed) if seed is not None else _r.Random()
        tmpl = _pets.roll_random_pet(rng)
        pet = _comp.Companion(
            kind=_comp.KIND_PET,
            species_key=tmpl["species_key"],
            display_name_pl=tmpl["display_name_pl"],
            bond=5,
            stress=0,
            status=_comp.STATUS_ACTIVE,
            temporary=False,
            tags=list(tmpl.get("risk_tags") or []),
            abilities=list(tmpl.get("abilities") or []),
            sponsor_likes_tags=list(tmpl.get("sponsor_likes") or []),
        )
        _comp.register_companion(self.world, pet)
        intro = tmpl.get("intro_line_pl") or \
            f"Twój towarzysz: {tmpl['display_name_pl']}."
        # Prompt 19 audit fix N3: pet intro is in-world ambient text, not
        # a Syndicate broadcast — use the normal log category.
        self.log(intro, LOG_NORMAL)

    def submit_input(self):
        text_val = self.input_text.strip()
        self.input_text = ""
        # Prompt 18: any submitted text disarms the nav-selection latch
        # so a subsequent stray Enter can't fire the panel option.
        self._nav_selection_armed = False
        # P28.6: snapshot the room id BEFORE running the command so we
        # can detect movement and reset stale nav focus afterwards.
        # Without this, a subject focused in the OLD room (e.g. exit
        # label "relay" or NPC "Żelazny Kuba" in Lounge) carried over
        # to the new room and the player kept clicking refusals.
        pre_room_id = (self.world.current_floor.current_room_id
                       if self.world and self.world.current_floor else None)
        if not text_val: return
        # P29.60 — arena play reuses STATE_PLAY input logic, just w
        # innym state. Tu treatujemy oba identycznie.
        if self.state == STATE_PLAY or self.state == STATE_ARENA_PLAY:
            # Record to lightweight command history for Up/Down recall.
            if not self.cmd_history or self.cmd_history[-1] != text_val:
                self.cmd_history.append(text_val)
                # Keep history bounded.
                if len(self.cmd_history) > 50:
                    self.cmd_history = self.cmd_history[-50:]
            self.cmd_history_idx = -1
            self.log(f"> {text_val}", LOG_NORMAL)
            # P26c — context pronoun support: remember the player's
            # raw command for `znowu`/`again` replay. Skip the
            # `znowu` command itself (we don't want znowu→znowu loops)
            # and skip ambiguity-resolution replies (oba/1/partial).
            from .polish_text import fold as _fold_pc
            _norm = _fold_pc(text_val).strip()
            REPLAY_TOKENS_PERSIST = {"znowu", "znow", "znów", "jeszcze raz",
                                     "again", "powtorz", "powtórz"}
            DISAMBIG_TOKENS = {"oba", "obu", "obydwa", "wszystko",
                               "wszystkie", "both", "all"}
            if (self.world is not None
                    and _norm not in REPLAY_TOKENS_PERSIST
                    and _norm not in DISAMBIG_TOKENS
                    and not _norm.isdigit()):
                self.world.last_player_command = text_val
            self._handle_play_input(text_val)
            # P28.6 — after every play command, if the player's room
            # changed, reset all nav focus + pre-resolved target. This
            # kills the "spam stale exit option after a move" bug.
            # Also clears stale focus tracking the no-longer-visible
            # subject (which used to leak as "Nie ma takiego wyjścia"
            # spam in the log).
            post_room_id = (self.world.current_floor.current_room_id
                            if self.world and self.world.current_floor else None)
            if pre_room_id != post_room_id and self.nav_state is not None:
                try:
                    for grp in list(self.nav_state.focused_subject_by_group.keys()):
                        self.nav_state.clear_focus(grp)
                except Exception:
                    pass
                self._preresolved_target_id = None
                # P28.6 — re-sync minimap layer view to the player's
                # new Z (used stairs / vent → minimap auto-follows).
                try:
                    from ..ui import minimap as _mm
                    self.world.minimap_z_view = _mm.player_z_layer(
                        self.world.current_floor)
                except Exception:
                    pass
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
        # Prompt 22: keep the window on the player's chosen monitor when
        # they change resolution mid-game.
        monitor = int(_settings.load_settings().get("monitor_index", 0) or 0)
        try:
            self.screen = pygame.display.set_mode((w, h), flags,
                                                  display=monitor)
        except (pygame.error, TypeError):
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

    # ── P28.7 — mouse handlers for title + creation screens ──────────────

    def _title_action(self, action_key: str) -> None:
        """Click callback from draw_title. Mirrors the keyboard path in
        handle_keydown for STATE_TITLE — same effects, just routed
        through one shared method so mouse and keyboard stay in sync.

        P29.9 — both "new_game" and "load_game" now route through the
        slot picker. The picker handles overwrite vs. empty / dead /
        active per-slot semantics.
        """
        if action_key == "new_game":
            self.slot_picker_mode = "new"
            self.slot_picker_idx = 0
            self.state = STATE_SLOTS
        elif action_key == "load_game":
            if save_load.exists():
                self.slot_picker_mode = "load"
                self.slot_picker_idx = 0
                self.state = STATE_SLOTS
        elif action_key == "settings":
            self._open_settings()
        elif action_key == "quit":
            pygame.quit()
            raise SystemExit
        elif action_key == "toggle_lang":
            set_language("en" if get_language() == "pl" else "pl")

    # ── P29.9 — slot picker ──────────────────────────────────────────────

    def _open_slot_picker(self, mode: str) -> None:
        """Enter STATE_SLOTS. `mode` is 'new' or 'load'."""
        self.slot_picker_mode = mode if mode in ("new", "load") else "new"
        self.slot_picker_idx = 0
        self.input_text = ""
        self.state = STATE_SLOTS

    def _slot_picker_pick(self, slot_index: int) -> None:
        """Mouse / Enter callback. Acts based on current mode + slot
        state:
          * load + empty/missing: ignored
          * load + has data: set active slot, load, → STATE_PLAY
          * new + anything: set active slot, wipe old data, → STATE_CREATE
        """
        n = max(0, min(int(slot_index), save_load.SAVE_SLOT_COUNT - 1))
        mode = getattr(self, "slot_picker_mode", "new")
        if mode == "load":
            if not save_load.exists_slot(n):
                return
            save_load.set_active_slot(n)
            w = save_load.load_from_slot(n)
            if w is None:
                self.log(t("log_save_load_failed",
                           fallback="Zapis uszkodzony."), LOG_DANGER)
                self.state = STATE_TITLE
                return
            self.world = w
            self.state = STATE_PLAY
            self.log(t("log_save_loaded", fallback="Zapis wczytany."), LOG_SUCCESS)
            return
        # New game: pick slot, wipe any old data, enter creation.
        save_load.set_active_slot(n)
        save_load.delete_slot(n)
        self.cc = {"step": "name", "name_input": "",
                   "selected_bg": 0,
                   "selected_species": 0,
                   "selected_companion": 0}
        self.input_text = ""
        self.state = STATE_CREATE

    def _slot_picker_back(self) -> None:
        self.state = STATE_TITLE

    # ── P29.35 — creation pickers + option list builders ──────────────────

    def _creation_background_keys(self) -> list:
        """All background keys offered at character creation: vanilla
        BACKGROUNDS list + any meta-unlocked `origin_*` keys."""
        from .character import BACKGROUNDS
        from . import meta_progression as _mp
        keys = list(BACKGROUNDS)
        try:
            for ud in _mp.unlocked_origins():
                if ud.key not in keys:
                    keys.append(ud.key)
        except Exception:
            pass
        return keys

    def _creation_species_keys(self) -> list:
        """Species pool: baseline_human is always offered; unlocked
        species append after."""
        from . import meta_progression as _mp
        keys = ["baseline_human"]
        try:
            for ud in _mp.unlocked_species():
                if ud.key not in keys:
                    keys.append(ud.key)
        except Exception:
            pass
        return keys

    def _creation_companion_keys(self) -> list:
        """Companion options. Index 0 means 'no starting companion'.
        Returns at least [""] (the no-pick sentinel). When the player
        has unlocked companions, the picker step is opened; otherwise
        the step is skipped silently and start_new_game runs with
        _chosen_companion left empty."""
        from . import meta_progression as _mp
        keys = [""]
        try:
            for ud in _mp.unlocked_companions():
                if ud.key not in keys:
                    keys.append(ud.key)
        except Exception:
            pass
        return keys

    def _creation_commit(self) -> None:
        """Finalize creation: read all four cc fields and launch the
        world. Called from `commit_species` (when no companions are
        unlocked) and `commit_companion`."""
        name = self.cc.get("name_input", "").strip() or "Bezimienny"
        bg_keys = self._creation_background_keys()
        sp_keys = self._creation_species_keys()
        comp_keys = self._creation_companion_keys()
        bg = bg_keys[int(self.cc.get("selected_bg", 0)) % len(bg_keys)]
        species = sp_keys[int(self.cc.get("selected_species", 0)) % len(sp_keys)]
        comp_idx = int(self.cc.get("selected_companion", 0)) % len(comp_keys)
        chosen = comp_keys[comp_idx] if comp_idx > 0 else ""
        # _apply_starting_companion (called from start_new_game) reads
        # this attribute. Empty string = no starting companion.
        self._chosen_companion = chosen
        self.start_new_game(name, bg, species=species)
        self.state = STATE_PLAY

    def _create_action(self, action) -> None:
        """Click callback from draw_creation. `action` is a string for
        single-arg ops ("confirm_name", "commit_bg", "commit_species",
        "commit_companion", "back") or a tuple ("pick_bg", idx) /
        ("pick_species", idx) / ("pick_companion", idx). Mirrors the
        STATE_CREATE keyboard path.

        P29.35 — step machine is now name → background → species →
        (companion if anything unlocked) → world."""
        if isinstance(action, tuple):
            kind, *args = action
        else:
            kind = action
            args = ()
        step = self.cc.get("step")
        if kind == "back":
            if step == "name":
                self.state = STATE_TITLE
            elif step == "background":
                self.cc["step"] = "name"
            elif step == "species":
                self.cc["step"] = "background"
            elif step == "companion":
                self.cc["step"] = "species"
            return
        if step == "name" and kind == "confirm_name":
            name = self.cc.get("name_input", "").strip() or "Bezimienny"
            self.cc["step"] = "background"
            self.cc["name_input"] = name
            return
        if step == "background":
            bgs = self._creation_background_keys()
            if kind == "pick_bg" and args:
                idx = int(args[0])
                if 0 <= idx < len(bgs):
                    self.cc["selected_bg"] = idx
            elif kind == "commit_bg":
                idx = int(self.cc.get("selected_bg", 0))
                if 0 <= idx < len(bgs):
                    self.cc["step"] = "species"
            return
        if step == "species":
            sp = self._creation_species_keys()
            if kind == "pick_species" and args:
                idx = int(args[0])
                if 0 <= idx < len(sp):
                    self.cc["selected_species"] = idx
            elif kind == "commit_species":
                idx = int(self.cc.get("selected_species", 0))
                if 0 <= idx < len(sp):
                    # If any companions are unlocked, route to that
                    # picker; otherwise commit directly.
                    if len(self._creation_companion_keys()) > 1:
                        self.cc["step"] = "companion"
                    else:
                        self._creation_commit()
            return
        if step == "companion":
            comp = self._creation_companion_keys()
            if kind == "pick_companion" and args:
                idx = int(args[0])
                if 0 <= idx < len(comp):
                    self.cc["selected_companion"] = idx
            elif kind == "commit_companion":
                self._creation_commit()
            return

    # ── P29.41: dialog tree handlers ──────────────────────────────────────

    def _guess_dialogue_tree(self, entity) -> str:
        """P29.59 — heurystyka mapująca tagi entity → tree_key, gdy
        entity NIE ma explicit `state.dialogue_tree_key`. Cel: każdy
        NPC z affordance „talk" dostaje JAKIEŚ drzewko zamiast
        legacy skill check. Kolejność od bardziej specyficznych do
        ogólniejszych.
        """
        tags = entity.tags or []
        # Mini-bossy + bossy Ligi Brawurowej (F2)
        if "faction:liga" in tags:
            return "liga_brawurowa_grunt"
        # Strażnik Bramy (F1 floor boss intake)
        if "intake" in tags and "floor_boss" in tags:
            return "intake_warden"
        # Generic random crawler (T_CRAWLER) — fallback dla
        # losowo spawnowanych zawodników bez tożsamości.
        try:
            from .entity import T_CRAWLER
            if entity.entity_type == T_CRAWLER:
                return "default_crawler"
        except Exception:
            pass
        return ""

    def _open_dialogue(self, npc_entity, tree_key: str) -> None:
        """Otwórz rozmowę z NPC. Uruchamia drzewko, ustawia
        self.dialogue_state i przełącza state na STATE_DIALOG."""
        # Lazy-load content żeby drzewka się zarejestrowały.
        try:
            from ..content.data import npc_dialogues  # noqa: F401
        except Exception:
            pass
        from . import dialogue as _dlg
        state = _dlg.start_dialogue(
            self.world, npc_entity, tree_key,
            log_callback=self._dialogue_log_callback)
        if state is None:
            name = npc_entity.display_name()
            self.log(f'Z „{name}" nie da się teraz rozmawiać.',
                     LOG_WARN)
            return
        self.dialogue_state = state
        self.state = STATE_DIALOG

    def _dialogue_log_callback(self, text: str, severity: str) -> None:
        """Most między dialogue.apply_consequences a Game.log
        (mapowanie severity string → constant)."""
        sev_map = {
            "normal": LOG_NORMAL,
            "success": LOG_SUCCESS,
            "warn": LOG_WARN,
            "danger": LOG_DANGER,
            "system": LOG_SYSTEM,
        }
        self.log(text, sev_map.get(severity, LOG_NORMAL))

    def _pick_dialogue_option(self, opt_idx: int) -> None:
        """Wybierz opcję `opt_idx` w bieżącym węźle drzewka. Może
        zamknąć dialog (przejście do None / end consequence) — wtedy
        czyścimy state i wracamy do STATE_PLAY."""
        if self.dialogue_state is None:
            return
        from . import dialogue as _dlg
        node = _dlg.current_node(self.dialogue_state)
        if node is None:
            self._close_dialogue()
            return
        # Mapowanie idx widziany przez gracza (1-9) na oryginalny
        # indeks w node.options (z uwzględnieniem ukrytych opcji).
        avail = _dlg.available_options(self.world, self.dialogue_state,
                                        node)
        if not (0 <= opt_idx < len(avail)):
            return
        real_idx, opt = avail[opt_idx]
        # Odnajdź NPC entity.
        npc = self.world.get(self.dialogue_state.npc_entity_id)
        keep_going, info_line = _dlg.pick_option(
            self.world, npc, self.dialogue_state, real_idx,
            log_callback=self._dialogue_log_callback)
        if info_line:
            self.log(info_line, LOG_SYSTEM)
        if not keep_going:
            self._close_dialogue()

    def _close_dialogue(self) -> None:
        """Zamknij aktywny dialog. Przywraca STATE_PLAY."""
        self.dialogue_state = None
        self.state = STATE_PLAY

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
        # P27 — LLM row removed from UI; 4 rows now: resolution, mode,
        # apply, back.
        n_rows = 4
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
            self._suppress_textinput = True; return
        if key in (pygame.K_RIGHT, pygame.K_d):
            if st["row"] == 0:
                st["res_idx"] = (st["res_idx"] + 1) % len(SUPPORTED_RESOLUTIONS)
            elif st["row"] == 1:
                st["fullscreen"] = not st["fullscreen"]
            self._suppress_textinput = True; return
        if key == pygame.K_RETURN:
            row = st["row"]
            if row in (0, 1, 2):
                # Apply current selection (resolution + fullscreen).
                w, h = SUPPORTED_RESOLUTIONS[st["res_idx"]]
                self.set_resolution(w, h, fullscreen=st["fullscreen"])
            elif row == 3:
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
                # Prompt 19 audit fix B2: surface tab-renderer crashes
                # to the player log instead of silently swallowing them.
                # Previously a broken locale key or missing field in any
                # journal tab would silently nuke the overlay.
                try:
                    fn()
                except Exception as exc:
                    self.log(
                        t("feedback_journal_render_failed",
                          fallback=f"(Dziennik: zakładka „{tab_key}” "
                                   f"nie wyrenderowała się: {exc})"),
                        LOG_WARN)

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

    def _handle_monitor_command(self, idx) -> None:
        """Prompt 22: list available monitors OR switch to monitor `idx`.

        Bare `monitor` (idx=None) prints the current and available
        monitors with their resolutions. `monitor N` saves
        monitor_index=N to settings and notes the next launch will
        place the window on that monitor — SDL can't reparent an
        existing window cleanly without a full re-init, so we don't
        try to apply it live.
        """
        from ..ui import settings as _settings
        import pygame as _pg
        try:
            num = _pg.display.get_num_displays()
        except Exception:
            num = 1
        cur = int(_settings.load_settings().get("monitor_index", 0) or 0)

        # List displays.
        if idx is None:
            # Prompt 22 bug fix: pass `idx` so the locale's {idx}
            # placeholder gets substituted (the player was seeing the
            # literal "{idx}" in the log).
            self.log(t("ui_monitor_header",
                       fallback=f"Dostępne ekrany (aktywny: {cur}):",
                       idx=cur),
                     LOG_SYSTEM)
            for i in range(num):
                try:
                    size = _pg.display.get_desktop_sizes()[i]
                    size_s = f"{size[0]}x{size[1]}"
                except Exception:
                    size_s = "?"
                marker = "▶" if i == cur else " "
                self.log(f"  {marker} monitor {i}  ({size_s})", LOG_NORMAL)
            self.log(t("ui_monitor_hint",
                       fallback="  Przełącz: 'monitor N' (zacznie działać po restarcie)."),
                     LOG_NORMAL)
            return

        # Switch.
        if idx < 0 or idx >= num:
            self.log(t("ui_monitor_out_of_range",
                       fallback=f"Nie ma monitora {idx}. Dostępne: 0..{num-1}.",
                       idx=idx, max=num-1),
                     LOG_WARN)
            return
        # Persist via the settings helper. If `set_monitor_index` doesn't
        # exist yet (this is its first user), fall back to direct write.
        if hasattr(_settings, "set_monitor_index"):
            _settings.set_monitor_index(idx)
        else:
            s = _settings.load_settings()
            s["monitor_index"] = int(idx)
            _settings.save_settings(s)
        self.log(t("ui_monitor_set",
                   fallback=f"Monitor: {idx}. Zacznie działać po restarcie gry.",
                   idx=idx),
                 LOG_SUCCESS)

    def submit_generated_command(self, command: str, target_id=None):
        """Prompt 08: route a cursor/option-selected command through the
        same submit_input path used by typed text. The command is logged
        like a manual entry, then dispatched to the normal parser pipeline.
        Never mutates game state directly.

        Prompt 23.5 (backlog #2): when called from the action panel, the
        `target_id` of the originating SelectableOption is carried through
        so the validator can bypass disambiguation. The action panel
        already knows which entity the player picked; making them answer
        "który?" again is a UX bug."""
        cmd = (command or "").strip()
        if not cmd:
            return
        self.input_text = cmd
        self._preresolved_target_id = target_id
        self.submit_input()

    def _handle_create_input(self, text_val):
        if self.cc.get("step") == "name":
            self.cc["name_input"] = text_val
            self.cc["step"] = "background"
            self._suppress_textinput = True

    def _handle_play_input(self, text_val):
        # P29.0 — if an entity escalated to enraged on the previous
        # tick, it owes the player a free attack of opportunity.
        # Run the enemy turn FIRST, then process the player's command
        # against whatever damage they just took. Self-clears the flag.
        try:
            from . import combat as _cmb
            room = (self.world.current_floor.current_room()
                    if self.world and self.world.current_floor else None)
            cs = _cmb.get_combat(room) if room else None
            if (cs is not None and cs.active
                    and getattr(cs, "free_attack_pending", False)):
                cs.free_attack_pending = False
                self.log("Wróg uderza pierwszy — sprowokowałeś.", LOG_DANGER)
                self._run_enemy_turn(cs)
                # If the free attack killed the player, bail before the
                # command runs.
                if not self.world.character.is_alive():
                    self._check_player_dead("combat_free_attack",
                                            "od ciosu, na który się sam wystawiłeś")
                    return
        except Exception:
            pass

        # Prompt 20: disambiguation follow-up. If the previous command
        # left an ambiguous_target pending, intercept short replies like
        # "oba" / "obu" / "wszystko" / "1" / "brudny" before the normal
        # parser runs. On match, synthesize new commands targeting the
        # picked entities and re-enter this handler for each. On
        # non-match, clear the pending state and fall through normally.
        if self.pending_disambiguation is not None:
            if self._resolve_disambiguation(text_val):
                return
            # Non-match — clear the pending state and let parser handle.
            self.pending_disambiguation = None

        # P26c — context pronouns. `znowu` / `again` / `znów` / `jeszcze
        # raz` replays the last successful player command. No-op when
        # there's no last command yet (fresh game / floor change).
        if self.world is not None:
            from .polish_text import fold as _fold
            normalized = _fold(text_val).strip()
            REPLAY_TOKENS = {"znowu", "znow", "znów", "jeszcze raz",
                             "again", "powtorz", "powtórz"}
            if normalized in REPLAY_TOKENS:
                last = (self.world.last_player_command or "").strip()
                if last:
                    self.log(t("feedback_replay",
                               fallback=f"(znowu: {last})",
                               cmd=last), LOG_SYSTEM)
                    text_val = last
                    # Fall through with the replayed command — do NOT
                    # update last_player_command to "znowu" itself; the
                    # update at the end stores the original command.
                else:
                    self.log(t("feedback_replay_empty",
                               fallback="Nie było jeszcze nic do powtórzenia."),
                             LOG_WARN)
                    return

        intent = parse_with_optional_llm(text_val, self.world)
        # Prompt 17: when combat is active, the combat router runs BEFORE
        # the generic intent dispatch. Combat-flavored commands (attack /
        # defend / dodge / flee / assess / use-environment / lure-into-
        # trap) need to land in the combat layer even when the parser
        # would normally route them elsewhere. Non-combat intents fall
        # through and run as usual; the standard pipeline below will
        # still see them.
        from . import combat as _cmb
        room_pre = self.world.current_floor.current_room() if self.world.current_floor else None
        cs_pre = _cmb.get_combat(room_pre)
        if cs_pre is not None:
            if self._combat_route(intent, cs_pre):
                return
        if intent.intent == "unknown":
            # During combat the "unknown" path is already handled above;
            # if we got here combat wasn't active or didn't consume it.
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
        # Prompt 19 — pet/companion intents and the companions journal tab.
        if intent.intent == "journal_companions":
            self._open_journal(_journal.TAB_COMPANIONS); return
        if intent.intent in ("companion_inspect", "companion_feed",
                             "companion_calm", "companion_scout",
                             "companion_lure"):
            from . import companion_actions as _ca
            _ca.handle(self, intent.intent, intent)
            return
        # Prompt 20: encounter-prep readout. Always available; especially
        # useful when an alarm has scheduled an arrival.
        if intent.intent == "prep_room":
            self._show_prep_readout(); return
        # Prompt 23: wield slot management.
        if intent.intent == "wield":
            self._attempt_wield(intent); return
        if intent.intent == "sheathe":
            self._attempt_sheathe(intent); return
        if intent.intent == "coat_weapon":
            self._attempt_coat_weapon(intent); return

        # Prompt 09 — display settings
        if intent.intent == "show_resolutions":
            self._show_resolutions(); return
        if intent.intent == "set_fullscreen":
            self.toggle_fullscreen(True); return
        if intent.intent == "set_windowed":
            self.toggle_fullscreen(False); return
        # Prompt 22: monitor picker. Bare "monitor" lists displays;
        # "monitor N" sets monitor_index in settings (takes effect on
        # next launch — SDL can't re-parent an existing window).
        if intent.intent == "set_monitor":
            idx = None
            for m in intent.modifiers or []:
                if isinstance(m, str) and m.startswith("index:"):
                    try:
                        idx = int(m.split(":", 1)[1])
                    except ValueError:
                        pass
            self._handle_monitor_command(idx); return
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

        # Prompt 24 — explicit butcher / eat verbs on corpses. The
        # `salvage` path above also routes to butcher when the target is
        # a corpse (so "rozbierz ciało" works), but these intent keys
        # come from corpse-specific verbs (`wypatrosz`, `oprawiaj`,
        # `zjedz` etc) and want their own handlers so the player gets
        # appropriately-flavored feedback even when the target is e.g.
        # a non-corpse (clean refusal: "to nie zwłoki").
        if intent.intent == "butcher_corpse":
            self._attempt_butcher_corpse(intent); return
        if intent.intent == "eat_corpse":
            self._attempt_eat_corpse(intent); return

        # Prompt 25 — 7-slot equipment.
        if intent.intent == "wear":
            self._attempt_wear(intent); return
        if intent.intent == "take_off":
            self._attempt_take_off(intent); return

        # P27.6 — rest handlers.
        if intent.intent == "rest_short":
            self._attempt_rest_short(); return
        if intent.intent == "rest_long":
            self._attempt_rest_long(); return

        # P27.7 — class active ability.
        if intent.intent == "class_active":
            self._attempt_class_active(); return

        # P27.9 — consume food/drink (eat/drink/skonsumuj X).
        if intent.intent == "consume":
            self._attempt_consume(intent); return

        # P29.7 — pick up a deployed trap (fallback for mis-placement).
        if intent.intent == "trap_pickup":
            self._attempt_trap_pickup(intent); return

        # P29.10 — open a sponsor drop-pod.
        if intent.intent == "open_pod":
            self._attempt_open_pod(intent); return

        # P29.14 — apply an enhancement (poison oil, grip tape, etc.).
        if intent.intent == "apply_enhancement":
            self._attempt_apply_enhancement(intent); return

        # P29.56 — eksperymentalny crafting: gracz miesza 3-5 materiałów
        # bez znanej receptury, rzut INT vs DC decyduje. Crit = unique.
        if intent.intent == "experiment":
            self._attempt_experiment(intent); return

        # P29.57b — otwórz skrzynkę: VS-style box system, reveal Dinniman
        if intent.intent == "open_box":
            self._attempt_open_box(intent); return

        # P29.57e — Wiercimajster: trener-NPC + codex bossów (safehouse-only)
        if intent.intent == "consult_codex":
            self._attempt_consult_codex(intent); return

        # P29.23 — cooking + reading.
        if intent.intent == "cook":
            self._attempt_cook(intent); return
        if intent.intent == "read":
            self._attempt_read(intent); return

        # P29.19 — credit sinks.
        if intent.intent == "train_stat":
            self._attempt_train_stat(intent); return
        if intent.intent == "bribe_sponsor":
            self._attempt_bribe_sponsor(intent); return
        if intent.intent == "call_pod":
            self._attempt_call_pod(intent); return
        if intent.intent == "upgrade_loadout":
            self._attempt_upgrade_loadout(intent); return

        # P29.4 — black-market buy/sell follow-ups.
        if intent.intent == "bm_buy":
            from ..systems import safehouses as _sh
            target = intent.targets[0] if intent.targets else ""
            line = _sh.try_buy(self.world, target)
            self.log(line, LOG_NORMAL)
            return
        if intent.intent == "bm_sell":
            from ..systems import safehouses as _sh
            target = intent.targets[0] if intent.targets else ""
            line = _sh.try_sell(self.world, target)
            self.log(line, LOG_NORMAL)
            return

        # Gap 4: deploy a crafted/portable trap or device
        if intent.intent == "deploy":
            self._attempt_deploy(intent); return

        # Prompt 12: object destruction. Routes through validation for
        # target resolution (so ambiguous names still get a clarify prompt),
        # then a STR check + state mutation + optional salvage payout.
        if intent.intent == "break":
            self._attempt_break(intent); return

        # P29.39 — „wyłam X" handler. Brakowało dispatchu, więc UI
        # sugerowało komendę a parser ją zwracał, ale validator
        # szukał entity i nic nie znajdował. Teraz osobna ścieżka,
        # która łapie locked exity (przez synth_door) i otwiera je
        # STR-em.
        if intent.intent == "force":
            self._attempt_force(intent); return

        # Prompt 16: mass-action commands. Deterministic, no LLM. Each
        # handler iterates the room's visible entities and applies the
        # action to every valid target — accumulating time, noise,
        # materials, and consequences.
        if intent.intent == "mass_salvage":
            self._attempt_mass_salvage(intent); return
        if intent.intent == "mass_search":
            self._attempt_mass_search(intent); return
        if intent.intent == "mass_loot_take":
            self._attempt_mass_loot(intent, mode="take"); return
        if intent.intent == "mass_loot_loose":
            self._attempt_mass_loot(intent, mode="loot"); return
        if intent.intent == "mass_break":
            self._attempt_mass_break(intent); return

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
            # Prompt 23.5 (backlog #2): if the player committed this
            # command via the action panel, `_preresolved_target_id` is
            # set to the chosen entity. When validation reports ambiguous
            # but our preresolved id is in the candidate list, re-issue
            # the command for THAT specific entity instead of asking the
            # player which one they meant — they already picked it.
            if (v.reason == "ambiguous_target"
                    and v.possible_entity_ids
                    and self._preresolved_target_id is not None
                    and self._preresolved_target_id in v.possible_entity_ids):
                verb = (getattr(intent, "verb", "") or
                        getattr(intent, "normalized_text", "").split()[0] or
                        intent.intent)
                tid = self._preresolved_target_id
                self._preresolved_target_id = None
                self.pending_disambiguation = None
                self._reissue_for_entities(verb, [tid], label="")
                return
            self.log(v.message() or "—", LOG_WARN)
            if v.possible_interpretations:
                self.log("  ? " + " | ".join(v.possible_interpretations), LOG_NORMAL)
            # Prompt 20: when validation reports ambiguous_target, stash
            # the candidates so the next command ("oba" / "1" / "brudny")
            # can refer back to them. Cleared otherwise.
            if v.reason == "ambiguous_target" and v.possible_entity_ids:
                self.pending_disambiguation = {
                    "intent": intent,
                    "entity_ids": list(v.possible_entity_ids),
                    "names": list(v.possible_interpretations or []),
                }
            else:
                self.pending_disambiguation = None
            self._preresolved_target_id = None
            return
        # Successful validation also consumes the preresolved hint.
        self._preresolved_target_id = None

        # P29.47 — `sprawdź X` daje pełną kartę OD RAZU. Dwustopniowy
        # state machine (unknown → seen → inspected) okazał się bloat:
        # gracz musiał wydać DWIE akcje żeby zobaczyć co to za skrzynia.
        # Teraz pierwsza sprawdź już ujawnia wszystko.
        if intent.intent == "inspect" and v.matched_entities:
            ent = v.matched_entities[0]
            from . import visibility as _vis
            try:
                from . import tutorial as _tut
                _tut.try_show_tip(self.world, "fog_of_war")
            except Exception:
                pass
            # Promuj od razu seen → inspected (lub unknown → inspected
            # w jednym kroku). build_inspect_block daje pełną kartę.
            _vis.mark_inspected(self.world, ent)
            lines = _vis.build_inspect_block(self.world, ent)
            for ln in lines:
                self.log(ln, LOG_NORMAL)
            # Time cost + noise — scouting wciąż kosztuje turę.
            try:
                if time_system is not None:
                    time_system.advance(self.world, 1)
                self._bump_threat(1, source="inspect")
            except Exception:
                pass

        # P24.5: use-handler for map items. Reveals rooms via the
        # floor's known/revealed sets so the minimap surfaces them.
        if intent.intent == "use" and v.matched_entities:
            ent = v.matched_entities[0]
            if ent.key in ("map_fragment", "floor_map"):
                self._consume_map_item(ent); return
            # P29.18 — vending machine: dispense one absurd item.
            if ent.key == "vending_machine" and \
                    not (ent.state or {}).get("vending_used"):
                self._attempt_vending_use(ent); return
            # P29.52 — recipe note: uczy przepisu i znika z plecaka.
            recipe_key = (ent.state or {}).get("recipe_key")
            if recipe_key and "recipe" in (ent.tags or []):
                self._consume_recipe_note(ent, recipe_key); return
            # P29.53c — keycard / key: otwiera zamknięte wyjście w
            # bieżącym pokoju. Bez tego gracz miał klucz dostępu w
            # plecaku i NIE WIEDZIAŁ jak go użyć na drzwi.
            tags = ent.tags or []
            if "key" in tags or "keycard" in tags:
                self._attempt_use_key(ent); return
            # P29.53f — food/drink/medical: routuj do consume zamiast
            # do generycznego `use` resolvera (który nic nie robił).
            # Zachowuje kompat ze starym verb'em `użyj baton` plus
            # mouse-click w panel z verb mapping (P29.53e).
            if ("food" in tags or "drink" in tags or
                    "consumable" in tags or "medical" in tags or
                    ent.key in self._CONSUMABLE_EFFECTS):
                # Wstrzykuj target jako dispay name żeby _attempt_consume
                # mogło znaleźć w inventory.
                from .parser_core import ActionIntent
                consume_intent = ActionIntent(
                    intent="consume",
                    verb="skonsumuj",
                    targets=[ent.display_name()],
                    normalized_text=f"skonsumuj {ent.display_name()}",
                )
                self._attempt_consume(consume_intent); return

        # P29.53d — drop verb: wyrzuca item z plecaka na podłogę.
        # Bez tego plecak rósł w nieskończoność bez sposobu na
        # opróżnienie poza zużyciem / założeniem.
        if intent.intent == "drop" and v.matched_entities:
            ent = v.matched_entities[0]
            self._attempt_drop(ent); return

        # P29.41 — talk dialog tree intercept. Jeśli NPC ma na
        # stanie pole `dialogue_tree_key`, otwieramy STATE_DIALOG
        # z odpowiednim drzewkiem. P29.59 — gdy brak explicit key,
        # zgadujemy z tagów entity (faction:liga → liga_brawurowa,
        # intake+floor_boss → intake_warden, default crawler →
        # default_crawler). Dopiero potem fallthrough do legacy.
        if intent.intent == "talk" and v.matched_entities:
            target = v.matched_entities[0]
            tree_key = (target.state or {}).get("dialogue_tree_key")
            if not tree_key:
                tree_key = self._guess_dialogue_tree(target)
            if tree_key:
                self._open_dialogue(target, tree_key)
                return

        r = resolve(v, self.world)
        if r.fallback_description and (v.required_checks or r.level != "success"):
            self.log(r.line(), LOG_SYSTEM)

        lines = apply(r.effects, self.world, time_system=time_system)
        for ln in lines:
            self.log(ln, LOG_NORMAL)

        # Prompt 17: if the player just attacked an alive hostile and
        # combat is NOT already active, kick it off and run the enemy
        # turn so the player feels the room react. Skip for already-dead
        # targets (post-mortem `zaatakuj X` on a corpse is harmless).
        if intent.intent == "attack" and v.matched_entities:
            target = v.matched_entities[0]
            if target.entity_type in ("monster","crawler","npc") and target.is_alive():
                from . import combat as _cmb
                room_after = self.world.current_floor.current_room() if self.world.current_floor else None
                if room_after is not None and _cmb.get_combat(room_after) is None:
                    cs2 = _cmb.start_combat(room_after, self.world,
                                            triggered_by="player_attack")
                    self.log(t("feedback_combat_start",
                               fallback="Walka się zaczyna."), LOG_WARN)
                    # P29.12 — tutorial: VATS + threat on first combat.
                    try:
                        from . import tutorial as _tut
                        _tut.try_show_tip(self.world, "combat_vats")
                        _tut.try_show_tip(self.world, "threat")
                    except Exception:
                        pass
                    # P29.20 — companion chatter at combat start.
                    try:
                        from . import companion_voice as _cv
                        _cv.maybe_say(self.world, "combat_start")
                    except Exception:
                        pass
                    self._run_enemy_turn(cs2)

        # Hooks: class offer trigger
        self._maybe_offer_class()
        # Hooks: floor descent (P27) or final victory.
        # P29.60 — arena mode: pomijamy descent (no exits) ale sprawdzamy
        # win/loss żeby wrócić do arena menu.
        in_arena = bool(getattr(self.world, "flags", {}).get("arena_mode"))
        if in_arena:
            self._check_arena_end()
        elif self.world.current_floor and self.world.current_floor.current_room_id in self.world.current_floor.exit_room_ids:
            if self.world.current_floor.exits_unlocked:
                self._descend_or_win()
            else:
                self.log(t("log_at_exit_locked",
                           fallback="Stoisz przed drzwiami wyjścia. Nadal zamknięte."),
                         LOG_WARN)

        # Health check
        if not self.world.character.is_alive():
            if in_arena:
                # Arena mode loss handled by _check_arena_end
                pass
            else:
                self._check_player_dead("post_action",
                                        "od kumulatywnych obrażeń")

    # ── P29.60 — Arena testowa ────────────────────────────────────────

    def start_arena_variant(self, variant_key: str) -> bool:
        """Inicjalizuje sesję arenową dla wybranego wariantu.
        Returns True on success, False (z log msg) on error."""
        from . import arena as _arena
        try:
            world, _floor = _arena.build_arena_world(variant_key)
        except ValueError as exc:
            # Powinno się dziać tylko gdy disabled variant — pokaż info.
            if self.world is not None:
                self.world.log_msg(f"Arena: {exc}", "warn")
            return False
        self.world = world
        self.state = STATE_ARENA_PLAY
        self.world.log_msg(
            world.current_floor.current_room().fallback_first_enter,
            "normal")
        return True

    def _check_arena_end(self) -> None:
        """Po każdym command dispatch w arena_mode sprawdza win/loss
        i routes do feedback + return-to-menu."""
        from . import arena as _arena
        if _arena.arena_is_lost(self.world):
            self.log("Arena: zawodnik wyeliminowany. Test zakończony.",
                     LOG_DANGER)
            self.state = STATE_ARENA_MENU
            return
        if _arena.arena_is_won(self.world):
            self.log("Arena: wszyscy przeciwnicy padli. Test zakończony.",
                     LOG_SUCCESS)
            self.state = STATE_ARENA_MENU
            return

    def open_arena_menu(self) -> None:
        """Przejście z title menu do arena variant picker."""
        self.state = STATE_ARENA_MENU
        # Reset world — arena nie korzysta z save state
        self.world = None

    # ── P27 — floor descent ────────────────────────────────────────────

    # Final floor — descending past this triggers true victory.
    MAX_FLOORS = 18

    def _descend_or_win(self) -> None:
        """At the unlocked floor exit. If there's a deeper floor, build
        + transition. Else mark final victory.

        DCC-faithful note: each floor's sponsor rotates, deadline
        resets, audience bonus on descent (you survived the floor),
        and pet/companion state carries over.
        """
        f = self.world.current_floor
        if f is None:
            return
        cur_num = int(f.floor_number or 1)
        if cur_num >= self.MAX_FLOORS:
            # Final floor cleared — true victory.
            # P29.15 — final boss / season finalist achievement.
            try:
                from ..systems import achievements as _ach
                _ach.unlock(self.world.character, "finalista_sezonu",
                            world=self.world)
            except Exception:
                pass
            # P29.26 — append victory to persistent history.
            # P29.34 — evaluate + record meta-progression unlocks.
            try:
                from . import run_history as _rh
                _rh.record_run(self.world, victory=True)
            except Exception:
                pass
            try:
                from . import meta_progression as _mp
                new_keys = _mp.record_unlocks_for_run(self.world,
                                                      victory=True)
                for k in new_keys:
                    ud = _mp.UNLOCK_CATALOG.get(k)
                    if ud is not None:
                        self.log(
                            f"Sezon otwiera nowe opcje: "
                            f"„{ud.label_pl}” — {ud.reward_pl}",
                            LOG_SUCCESS)
            except Exception:
                pass
            self.state = STATE_VICTORY
            return
        next_num = cur_num + 1
        # P29.8 — track high-water mark for the run summary.
        ch = self.world.character
        if ch is not None:
            ch.run_max_floor_reached = max(int(ch.run_max_floor_reached or 1),
                                           next_num)
        # P29.12 — tutorial: explain descent the first time.
        if cur_num == 1:
            try:
                from . import tutorial as _tut
                _tut.try_show_tip(self.world, "descend")
            except Exception:
                pass
        # P29.15 — floor-milestone achievements.
        try:
            from ..systems import achievements as _ach
            if cur_num == 1:
                _ach.unlock(ch, "dno_jeszcze_dalej", world=self.world)
                # P29.48 — pacifist F1: kills licznik = 0 przy zejściu.
                if int(ch.run_kills or 0) == 0:
                    _ach.unlock(ch, "brak_zwlok_brak_problemu",
                                world=self.world)
            if next_num >= 5:
                _ach.unlock(ch, "piaty_set", world=self.world)
            if next_num >= 10:
                _ach.unlock(ch, "dziesiate_pietro", world=self.world)
            # P29.49 — biome-completion achievements. Sprawdzamy
            # biom UKOŃCZONEGO piętra (cur_num, nie next_num).
            biome_key = getattr(f, "biome_key", "") or ""
            _biome_to_ach = {
                "zoo_korporacyjne": "zoofobia_skonczona",
                "muzeum_spektakli": "archiwista",
                "bar_skurczybyk":   "karaoke_killer",
                "okopy_frontowe":   "okopowiec",
            }
            if biome_key in _biome_to_ach:
                _ach.unlock(ch, _biome_to_ach[biome_key],
                            world=self.world)
            # Globtroter: 5 różnych biomów w jednym runie. Tracker
            # w flagach: visited_biomes_run = lista kluczy.
            visited = ch.flags.get("visited_biomes_run", []) or []
            if biome_key and biome_key not in visited:
                visited = list(visited) + [biome_key]
                ch.flags["visited_biomes_run"] = visited
            if len(visited) >= 5:
                _ach.unlock(ch, "globtroter", world=self.world)
            # Pomocnicze flagi per-floor które resetujemy przy zejściu.
            # Sprawdzamy PRZED resetem:
            if not int(ch.flags.get("floor_credits_spent", 0) or 0):
                _ach.unlock(ch, "nadzwyczajne_oszczednosci",
                            world=self.world)
            if int(ch.flags.get("floor_minibosses_killed", 0) or 0) >= 3:
                _ach.unlock(ch, "klepacz_minibossow",
                            world=self.world)
            if not int(ch.flags.get("floor_hazard_hits", 0) or 0):
                _ach.unlock(ch, "taneczny_krok", world=self.world)
            # No-armor floor: jeśli flag „armor_equipped_this_floor"
            # nie był ustawiony, gracz przeszedł bez zbroi.
            if not bool(ch.flags.get("armor_equipped_this_floor", False)):
                _ach.unlock(ch, "bez_zbroi_bez_smutku",
                            world=self.world)
            # Butchered every corpse — wymaga że floor_kills > 0
            # i floor_kills == floor_butchered.
            fk = int(ch.flags.get("floor_kills", 0) or 0)
            fb = int(ch.flags.get("floor_butchered", 0) or 0)
            if fk > 0 and fk == fb:
                _ach.unlock(ch, "kazdy_ma_imie", world=self.world)
            # Reset per-floor flag's po sprawdzeniu.
            for k in ("floor_credits_spent","floor_minibosses_killed",
                      "floor_hazard_hits","armor_equipped_this_floor",
                      "floor_kills","floor_butchered"):
                ch.flags[k] = 0 if k != "armor_equipped_this_floor" \
                                else False
        except Exception:
            pass
        # P29.20 — companion chatter on floor descent.
        try:
            from . import companion_voice as _cv
            _cv.maybe_say(self.world, "floor_descent")
        except Exception:
            pass
        # P29.31 — between-floor sponsor scoreboard. Tiny "Sponsorzy
        # oddali głos" line listing top-3 by current attention.
        try:
            from . import sponsors as _sp
            att = _sp._attention_dict(self.world)
            ranked = sorted(att.items(), key=lambda kv: int(kv[1]),
                            reverse=True)
            ranked = [(k, int(v)) for k, v in ranked if int(v) != 0][:3]
            if ranked:
                self.log("Sponsorzy oddali głos:", LOG_SYNDIC)
                for skey, val in ranked:
                    name = _sp._name_pl(_sp.get_sponsor(skey))
                    sign = "+" if val > 0 else ""
                    self.log(f"  • {name}: {sign}{val}", LOG_SYNDIC)
        except Exception:
            pass
        # P29.53s — highlight reel: pokazujemy top 3 najlepsze momenty
        # zakończonego piętra zanim zegar przeskoczy do nowego. Player
        # widzi „co zrobiłeś dobrze" — drobny dopamine hit między
        # piętrami.
        try:
            from ..systems import highlight_reel as _hr
            for ln in _hr.emit_floor_end_montage(self.world):
                self.log(ln, LOG_SUCCESS)
        except Exception:
            pass
        self.log(t("log_descend_intro",
                   fallback=f"Schodzisz na piętro {next_num}. Drzwi "
                            f"się zamykają za tobą. Loch nie pamięta "
                            f"twojej twarzy.",
                   floor=next_num), LOG_SUCCESS)
        # Audience bonus for survival.
        try:
            from . import audience as _aud
            _aud.change_audience(self.world, 5, source="floor_descent")
        except Exception:
            pass
        # SFX hook.
        try:
            audio.play_sfx("floor_descent")
        except Exception:
            pass
        # P29.53k — carryover bonus: time pozostały na poprzednim
        # piętrze + bonus 5 dni dorzucamy do nowej puli. Mechanika z
        # książki DCC: szybkie zejście = bankujesz dni na trudniejsze
        # piętra. Liczymy PRZED nadpisaniem current_floor.
        leftover_min = max(0, int(f.deadline_remaining_minutes() or 0))
        # P29.57e — Wiercimajster codex: bossy żywe na piętrze które
        # gracz teraz opuszcza = ucieczka (escape). Notujemy w codexie
        # między runami, żeby gracz wiedział „pominąłem tego krajowego
        # bossa" przy kolejnym podejściu. Robione PRZED generate_floor,
        # bo current_floor zostanie nadpisany.
        try:
            from . import run_history as _rh_e
            from .entity import T_CORPSE
            cur_floor_num = int(f.floor_number or 1)
            for room in f.rooms.values():
                for ent in room.entities:
                    if ent.entity_type == T_CORPSE:
                        continue
                    tags = ent.tags or []
                    if any(isinstance(t, str)
                           and t.startswith("boss_rank:")
                           for t in tags):
                        _rh_e.record_boss_escape(ent, cur_floor_num)
        except Exception:
            pass
        # Build next floor.
        try:
            from .floor_generator import generate_floor
            new_floor = generate_floor(self.world, floor_number=next_num)
        except Exception as exc:
            self.log(f"(Błąd budowy piętra: {exc})", LOG_DANGER)
            self.state = STATE_VICTORY
            return
        self.world.current_floor = new_floor
        self.world.floor_number = next_num
        # P29.53k — apply carryover. New floor's clock starts at 0 (set
        # by generator), deadline_minute already = base_for_floor. Dodaj
        # carryover + bonus. Komunikat w logu, żeby gracz widział że
        # czas się skumulował.
        try:
            from ..config import (DEADLINE_CARRYOVER_BONUS_DAYS,
                                  MINUTES_PER_DAY)
            bonus_min = int(DEADLINE_CARRYOVER_BONUS_DAYS) * MINUTES_PER_DAY
            total_extra = leftover_min + bonus_min
            if total_extra > 0:
                new_floor.deadline_minute = int(
                    new_floor.deadline_minute or 0) + total_extra
                lo_d = leftover_min // MINUTES_PER_DAY
                lo_h = (leftover_min % MINUTES_PER_DAY) // 60
                self.log(
                    f"Bonus za zejście: +{DEADLINE_CARRYOVER_BONUS_DAYS}d "
                    f"do deadline'u, plus carryover {lo_d}d {lo_h}h "
                    f"z poprzedniego piętra.",
                    LOG_SYSTEM)
        except Exception:
            pass
        # Reset some per-floor state.
        self.world.last_player_command = ""
        self.world.last_targeted_entity_id = None
        # Move the pet to the new start room if present.
        try:
            from . import companion as _comp
            pet = _comp.active_pet(self.world)
            if pet is not None:
                pet.location_room_id = new_floor.current_room_id
        except Exception:
            pass

        # P29.53l — pełne HP po zejściu. Canon DCC: piętro się
        # zamyka za tobą, ciało dostaje krótką regenerację (med-spray
        # od showrunner'a, „bonus za przeżycie"). Bez tego gracz musi
        # restować przed bossem F2 = nudne. HP reset usuwa też wszystkie
        # statusy z czasów F-prev które przeniosłyby się głupio (np.
        # bleeding/burning/poisoned). Disarmed/slowed (broken parts)
        # zostają — to permanentny maim.
        if ch is not None:
            healed = ch.max_hp - ch.hp
            if ch.conditions:
                _transient = {"bleeding", "burning", "poisoned", "chilled",
                              "stunned", "shocked", "afraid", "shaken",
                              "blinded"}
                ch.conditions = [c for c in ch.conditions
                                 if c not in _transient]
            ch.hp = ch.max_hp
            if healed > 0:
                self.log(f"Próg zejścia. Showrunner wysyła med-spray: "
                         f"+{healed} HP ({ch.hp}/{ch.max_hp}).",
                         LOG_SUCCESS)

        # P29.36 — species traits "on descent" hooks (biopsy drain,
        # companion bond drift). Emits a line per side-effect.
        try:
            from . import species_effects as _sp
            for ln in _sp.on_descent(self.world) or []:
                self.log(ln, LOG_SYSTEM)
        except Exception:
            pass

        # P29.36 — DCC-faithful floor-3 mutation chamber.
        # First entry to floor 3 fires the species offer (4 random
        # rolls + decline option). Latch keeps it one-shot per run.
        if next_num == 3:
            self._maybe_offer_species()

    def _maybe_offer_species(self) -> None:
        """First time the player reaches floor 3, offer 4 random
        mutations from systems.species.SPECIES_CATALOG. Player picks
        one (commits permanently) or declines (stays whatever they
        were). One-shot — the latch flag is set only AFTER the
        player commits (accept or decline), so a crash mid-offer
        won't silently consume the only chance."""
        ch = self.world.character
        if ch.flags is None:
            ch.flags = {}
        if ch.flags.get("species_offer_fired"):
            return
        # Build offer pool — exclude the player's current species
        # so they don't see themselves in the roll.
        import random as _r
        from ..systems import species as _sp_cat
        excl = (ch.species_key,) if ch.species_key else ()
        rng = _r.Random(int(self.world.current_floor.current_minute or 0)
                        * 31 + self.world.floor_number * 7)
        self.species_offer_candidates = _sp_cat.random_offer(
            rng, exclude_keys=excl)
        self.state = STATE_SPECIES_OFFER
        self.log("Wpadasz do komory mutacyjnej. Loch decyduje. "
                 "Konferansjer (z głośnika): „A teraz — TRZECIE "
                 "piętro. Czyli RACE PICK, panie i panowie.”",
                 LOG_SYNDIC)

    def _accept_species(self, idx: int) -> None:
        """Player picked one of the offered species. Apply it and
        return to play. Latches the offer so it can't re-fire."""
        candidates = getattr(self, "species_offer_candidates", None) or []
        if not (0 <= idx < len(candidates)):
            return
        key = candidates[idx]
        from ..systems import species as _sp_cat
        ok = _sp_cat.apply_species(self.world, key)
        ch = self.world.character
        if ch.flags is None:
            ch.flags = {}
        if not ok:
            self.log(f"Komora odrzuca twoją próbkę. ({key})", LOG_WARN)
            ch.flags["species_offer_fired"] = True
            self.species_offer_candidates = []
            self.state = STATE_PLAY
            return
        sp = _sp_cat.SPECIES_CATALOG.get(key)
        if sp is not None:
            self.log(sp.flavor_pl, LOG_SUCCESS)
            self.log(f"Stałeś się: {sp.name_pl}.", LOG_SUCCESS)
            # P29.36 — enhanced_human gets +1 to ALL stats on top
            # of the listed CON/DEX bumps. One-shot via flag inside
            # species_effects.
            try:
                from . import species_effects as _sp
                _sp.apply_all_stats_bonus(self.world.character)
            except Exception:
                pass
        # Latch only AFTER the choice committed.
        ch.flags["species_offer_fired"] = True
        self.species_offer_candidates = []
        self.state = STATE_PLAY

    def _decline_species(self) -> None:
        """Stay whatever you were. The decline path doesn't call
        apply_species — preserves the current species_key (could be
        baseline OR a meta-unlocked species). Latches the offer."""
        self.log("Pozostajesz sobą. Konferansjer: „Nuda, ale "
                 "udokumentowane.” Komora syczy i się otwiera dla "
                 "następnego.", LOG_SYSTEM)
        ch = self.world.character
        if ch.flags is None:
            ch.flags = {}
        ch.flags["species_offer_fired"] = True
        self.species_offer_candidates = []
        self.state = STATE_PLAY

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
        """P27.6 (P27-MECH-2): class offer trigger overhaul.

        Previous logic offered after just 5 total affinity — way too
        early, with random noise dominating the class pick because
        no single affinity was meaningfully bigger than the others.
        Now requires meaningful play AND a dominant affinity.
        """
        c = self.world.character
        if c.class_key is not None:
            return
        total = sum(c.affinity.values())
        sorted_aff = sorted(c.affinity.values(), reverse=True)
        top = sorted_aff[0] if sorted_aff else 0
        second = sorted_aff[1] if len(sorted_aff) >= 2 else 0
        floor_minute = (self.world.current_floor.current_minute
                        if self.world.current_floor else 0)
        # Forced offer at floor 2+ if they've at least played somewhat.
        force_offer = (self.world.floor_number >= 2 and total >= 15)
        # Earned offer: enough total, clear dominance, played awhile.
        earned_offer = (total >= 25
                        and top >= 8
                        and top >= 2 * max(1, second)
                        and floor_minute >= 60)
        if not (force_offer or earned_offer):
            return
        from ..systems.classes import suggest_classes
        self.offer_candidates = suggest_classes(c, n=3)
        self.state = STATE_CLASS_OFFER
        # Surface what behavior drove the offer so it doesn't feel arbitrary.
        from .dice_labels import intent_pl
        top_aff_name = next((k for k, v in c.affinity.items() if v == top), "?")
        self.log(narrate("class_offer") or
                 t("log_class_offer",
                   fallback=f"Syndykat ma dla ciebie propozycję. "
                            f"Widzieliśmy jak {top_aff_name} ({top}) "
                            f"dominuje twój styl. Wybierz:"),
                 LOG_SYNDIC)

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
            # P29.43 — rarity label tylko gdy niepospolity.
            try:
                from . import rarity as _rar
                r = _rar.entity_rarity(e)
                if r != _rar.RARITY_COMMON:
                    tags.insert(0, _rar.rarity_pl(r))
            except Exception:
                pass
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
        from .dice_labels import stat_pl as _spl
        for s in BASE_STATS:
            mod = c.stat_mod(s); sign = "+" if mod >= 0 else ""
            self.log(f"  {_spl(s)}: {c.stats[s]:2d} ({sign}{mod})", LOG_NORMAL)
        if c.class_key:
            self.log(f"  {t('ui_class', fallback='Klasa')}: {t(f'class_{c.class_key}_n', fallback=c.class_key)}", LOG_NORMAL)
        self.log(f"  HP {c.hp}/{c.max_hp}   AC {c.effective_ac(self.world)}   "
                 f"{t('ui_credits', fallback='Kr')} {c.credits}", LOG_NORMAL)

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
            # P27.8 (P27-UX-16) — mechanics primer. Always-on, surfaced by
            # F1 / `pomoc`. Teaches the d20 / AC / TT shorthand the log
            # uses so a new player can decode `d20(13)+SIŁ(+0)=13 vs AC 12 → trafienie`.
            t("controls_help_mech_title", fallback="Mechanika (skróty z logu):"),
            t("controls_help_mech_1",
              fallback="  d20(X): rzut kostką (1–20). Im wyższy, tym lepiej."),
            t("controls_help_mech_2",
              fallback="  AC (klasa pancerza): musisz przekroczyć w ataku — d20+modyfikatory ≥ AC = trafienie."),
            t("controls_help_mech_3",
              fallback="  TT (trudność testu): jak AC, ale dla testów niebojowych (skradanie, perswazja, naprawa)."),
            t("controls_help_mech_4",
              fallback="  Modyfikatory: SIŁ/ZRĘ/INT/MĄD/CHA = (stat-10)/2. Statystyka 14 → +2, statystyka 8 → -1."),
            t("controls_help_mech_5",
              fallback="  HP/AC: HP to życie (zero = śmierć). AC ≈ 10 + ZRĘ + zbroja."),
            t("controls_help_mech_6",
              fallback="  Crit/fumble: 20 na kostce = krytyk (×2 obrażeń). 1 na kostce = fumble (auto-pudło)."),
            t("controls_help_mech_7",
              fallback="  Klasa: po 60 min na piętrze możesz dostać ofertę klasy. `umiejętność` aktywuje zdolność (raz/piętro)."),
            t("controls_help_mech_8",
              fallback="  Odpoczynek: `odpocznij` (krótki, ~25% HP) wymaga bezpiecznego pokoju; `spij` w safehouse = pełne HP."),
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
        # P29.52 — filtrowanie przez character.known_recipes. Wcześniej
        # gracz widział WSZYSTKIE 29 przepisów na start. Teraz tylko
        # te które jego klasa zna + odnalezione w lochu.
        from ..content.crafting import (all_recipes, improvised_categories,
                                        tag_pl, category_pl,
                                        known_recipes_iter)
        all_recs = all_recipes()
        known = set(known_recipes_iter(self.world.character))
        self.log(t("ui_craft_help_h", fallback="Crafting:"), LOG_SYSTEM)
        if known:
            self.log("  Znane przepisy:", LOG_NORMAL)
            for k in known:
                v = all_recs.get(k)
                if v is None:
                    continue
                name = v.get("name_pl", "?")
                aliases = ", ".join((v.get("aliases_pl") or [])[:3])
                extra = f"  [tak nazwiesz: {aliases}]" if aliases else ""
                self.log(f"    • {name}{extra}", LOG_NORMAL)
            # Hint o nieznanych przepisach:
            unknown_count = len(all_recs) - len(known)
            if unknown_count > 0:
                self.log(f"  (Jest {unknown_count} przepisów których "
                         f"jeszcze nie znasz — szukaj notatek, "
                         f"podręczników i schematów w lochu.)",
                         LOG_NORMAL)
        else:
            self.log("  Nie znasz żadnych przepisów. Improwizuj — "
                     "albo poszukaj notatek w lochu.", LOG_NORMAL)
        self.log("  Improwizowane kategorie (działają BEZ przepisu, "
                 "z dostępnych materiałów):", LOG_NORMAL)
        for k, v in improvised_categories().items():
            tagsets_pl = []
            for tag_group in v.get("required_tag_sets", []):
                tagsets_pl.append("+".join(tag_pl(t) for t in tag_group))
            tagsets_str = " | ".join(tagsets_pl)
            self.log(f"    • {category_pl(k)}  → wymaga: {tagsets_str}",
                     LOG_NORMAL)
        self.log("  Przykłady: 'zrób pułapkę z kabli i baterii', "
                 "'skleć broń ze szkła i drewna'.", LOG_NORMAL)
        self.log("  Po skrafceniu pułapki: 'rozstaw pułapkę' albo "
                 "'podłóż pułapkę'.", LOG_NORMAL)

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

    def _resolve_corpse_target(self, intent):
        """Pick a corpse from the current room that matches the intent.
        Returns the Entity or None (and logs a clean refusal)."""
        from .entity import T_CORPSE
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            self.log(t("feedback_no_target",
                       fallback="Nie widzisz tu tego, czego szukasz."), LOG_WARN)
            return None
        target = None
        if intent.targets:
            from .validation import _resolve_entities
            candidates = _resolve_entities(room, intent.targets[0])
            target = candidates[0] if candidates else None
        else:
            # No explicit target: if exactly one corpse in the room, use it.
            corpses = [e for e in room.visible_entities()
                       if e.entity_type == T_CORPSE]
            if len(corpses) == 1:
                target = corpses[0]
            elif len(corpses) > 1:
                names = ", ".join(c.display_name() for c in corpses[:5])
                self.log(t("feedback_corpse_which",
                           fallback=f"Które ciało? {names}",
                           names=names), LOG_WARN)
                return None
        if target is None:
            self.log(t("feedback_corpse_none",
                       fallback="Nie widzisz tu ciała."), LOG_WARN)
            return None
        if target.entity_type != T_CORPSE:
            self.log(t("feedback_not_a_corpse",
                       fallback=f"„{target.display_name()}” to nie zwłoki.",
                       name=target.display_name()), LOG_WARN)
            return None
        return target

    def _attempt_butcher_corpse(self, intent):
        target = self._resolve_corpse_target(intent)
        if target is None:
            return
        self._run_butcher(target)

    def _run_butcher(self, corpse):
        """Shared butcher path used by both explicit `wypatrosz` and the
        salvage handler when salvaging a corpse. Mutates state, logs,
        applies tag-bus events, advances time."""
        from . import corpses as _cp
        from . import time_system as ts
        from ..content import materials as _mat
        ch = self.world.character
        result = _cp.butcher(self.world, corpse, ch)
        if not result.ok:
            self.log(result.message, LOG_WARN)
            return

        # Log yields with player-facing names.
        if result.materials:
            parts = []
            for k, v in result.materials.items():
                md = _mat.get(k)
                nm = md.name() if md is not None else k.replace("_", " ")
                parts.append(f"{v}× {nm}")
            self.log(t("feedback_butcher_yield",
                       fallback=f"Wypatroszono: {', '.join(parts)}.",
                       yields=", ".join(parts)), LOG_SUCCESS)
        else:
            self.log(t("feedback_butcher_nothing",
                       fallback="Wypatroszone — ale nic użytecznego."),
                     LOG_NORMAL)

        # Trophy goes to inventory as an entity. Falls back silently if
        # the trophy item template doesn't exist yet — hook for P24-onward
        # content drops.
        if result.trophy_item_key:
            try:
                from ..content.items import make_item
                it = make_item(result.trophy_item_key,
                               location_id="inventory:player")
                self.world.register(it)
                ch.inventory_ids.append(it.entity_id)
                self.log(t("feedback_trophy_drop",
                           fallback=f"Znalezione: {it.display_name()}.",
                           name=it.display_name()), LOG_SUCCESS)
            except Exception:
                pass

        # Time + noise.
        if result.time_min:
            ts.advance(self.world, int(result.time_min))
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is not None and result.noise:
            self._bump_threat(int(result.noise),
                              source="butcher", room=room)

        # Tag bus events — sponsor reactions, P28 titles, P31 vendetta.
        try:
            from . import sponsors as _sp
            _sp.note_player_tag(self.world, "butchered_corpse", weight=1)
            if result.audience_tag:
                _sp.note_player_tag(self.world, result.audience_tag, weight=2)
            if result.desecration_tag:
                _sp.note_player_tag(self.world, result.desecration_tag,
                                    weight=2)
        except Exception:
            pass

        # Title grants (P28 hook — for now just stash in character flags
        # so titles system can drain them when it lands).
        if result.title_grants:
            pending = ch.flags.setdefault("pending_title_grants", [])
            for tg in result.title_grants:
                if tg not in pending:
                    pending.append(tg)

        ch.affinity["survival"] = ch.affinity.get("survival", 0) + 1

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

    def _do_single_salvage(self, target, mute_narrator: bool = False):
        """Salvage one target deterministically (no parser dance). Used by
        mass-salvage. Stashes result on self._last_salvage_row +
        self._last_salvage_minutes for the caller's summary."""
        from . import time_system as ts
        from ..content import materials as _mat
        from ..content.data.salvage_tables import SALVAGE_TABLES
        from ..systems import risk_reward
        from .consequences import apply
        import random as _r
        self._last_salvage_row = []
        self._last_salvage_minutes = 0
        table_key = _pick_salvage_table_key(target)
        if not table_key:
            return
        table = SALVAGE_TABLES.get(table_key, {})
        ch = self.world.character
        # Auto-success-with-partial: mass salvage is methodical, not a
        # d20 roll per item. Use partial-success drops (floor qty/2).
        drops = {}
        for matkey, span in (table.get("drops") or {}).items():
            lo, hi = (span if isinstance(span, list) else [span, span])
            qty = max(0, _r.randint(int(lo), int(hi)) // 2)
            if qty <= 0 and hi > 0:
                qty = 1
            if qty > 0:
                drops[matkey] = qty
        if drops:
            _mat.add_materials(ch, drops)
            self._last_salvage_row = [
                f"{q}x {(_mat.get(k).name() if _mat.get(k) else k)}"
                for k, q in drops.items()
            ]
        target.state = target.state or {}
        target.state["stripped"] = True
        target.state["depleted"] = True
        # Time: from table or default 8.
        mins = int(table.get("time_minutes", 8)) // 2  # methodical batch
        self._last_salvage_minutes = max(2, mins)
        ts.advance(self.world, self._last_salvage_minutes)
        # Risks roll once per item — keep it light.
        risks = list(table.get("risks", []))
        if risks:
            effs = risk_reward.risk_effects(risks[:1])
            if effs:
                apply(effs, self.world, time_system=ts)
        # Safehouse social cost: per-item, light.
        if (target.state.get("owned_by") == "safehouse"
                or target.state.get("theft_sensitive")):
            ch.flags["safehouse_theft_warnings"] = int(
                ch.flags.get("safehouse_theft_warnings", 0)) + 1

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

    def _combat_route(self, intent, cs) -> bool:
        """Combat-state dispatch. Returns True iff this intent was consumed
        by the combat layer (don't fall through to the standard pipeline).
        Returns False for intents combat doesn't own — those run normally
        and still consume the player's turn, after which enemies react."""
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        # Combat-flavored verbs we own outright:
        if intent.intent == "flee":
            self._combat_flee(intent, cs); return True
        if intent.intent in ("attack",):
            self._combat_attack(intent, cs, mode="normal"); return True
        # Synthetic verbs from new parser cues.
        first_token = (intent.verb or intent.normalized_text or "").lower()
        if "ostroz" in first_token or "ostroż" in first_token:
            self._combat_attack(intent, cs, mode="careful"); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("ryzykow","mocno ataku","mocny atak","heavy","wściekle","wsciekle")):
            self._combat_attack(intent, cs, mode="heavy"); return True
        if intent.intent in ("hide",) or "broń" in first_token or "bron" in first_token:
            self._combat_defend(intent, cs); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("unik","uniknij","robie unik","robię unik","dodge","evade")):
            self._combat_dodge(intent, cs); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("oceń","ocen sytuac","oceń sytuac","oceniam","assess")):
            self._combat_assess(intent, cs); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("zwab","zwabiam","lure","wciągam","wciagam")):
            self._combat_lure(intent, cs); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("zbliż","zblizam","podchodz","approach")):
            self._combat_reposition(intent, cs, toward=True); return True
        if any(w in (intent.normalized_text or "").lower()
               for w in ("oddal","cofam","cofnij","wycofuj","back off","retreat"))\
                 and intent.intent != "flee":
            self._combat_reposition(intent, cs, toward=False); return True
        # Use-environment: break/throw/push during combat trigger an
        # environmental hook in addition to the normal effect.
        if intent.intent in ("break","push_into","throw_at"):
            consumed = self._combat_use_environment(intent, cs)
            if consumed:
                return True
            # Fall through to normal handling, but still take an enemy turn.
            return False
        # ── P26b: full combat lockdown whitelist ─────────────────────
        # The minimal P24.6 version only blacklisted a few intents.
        # Now we default-deny: every non-whitelisted intent gets a
        # clean refusal. Three intent buckets:
        #
        #   1. Combat-action whitelist (consumes turn + enemy retaliates
        #      via the handlers above; we return True after dispatch).
        #      Already routed before this block — by the time we reach
        #      here we know the intent is NOT a combat verb.
        #
        #   2. Info / free whitelist (no turn, no refusal — read-only).
        #
        #   3. Combat-compatible action whitelist — actions that
        #      legitimately happen mid-fight (use item, swap weapon,
        #      coat blade, push enemy into hazard, throw at enemy,
        #      break/destroy interactive). These FALL THROUGH so their
        #      normal handlers run, and the enemy then retaliates
        #      because the player's turn is consumed.
        #
        # Anything not in (2) or (3) is refused with no turn cost (no
        # double penalty for typos / muscle-memory).

        # Movement during combat → forced flee with check.
        if intent.intent == "move":
            from .parser_core import ActionIntent
            flee_intent = ActionIntent(
                intent="flee",
                verb="uciekaj",
                targets=[intent.destination] if intent.destination else [],
                modifiers=list(intent.modifiers or []),
                normalized_text=f"uciekaj {intent.destination or ''}".strip(),
            )
            flee_intent.destination = intent.destination
            self.log(t("feedback_combat_move_forced_flee",
                       fallback="Nie wyjdziesz spokojnie — próbujesz się "
                                "wycofać."), LOG_WARN)
            self._combat_flee(flee_intent, cs)
            return True

        # Bucket 2: free / info-only.
        FREE_IN_COMBAT = {
            "check_inventory", "check_character", "check_map",
            "check_materials", "check_beliefs", "check_knowledge",
            "help", "journal_open", "journal_close",
            "journal_objectives", "journal_crawlers", "save",
            "set_monitor", "set_resolution",
        }
        if intent.intent in FREE_IN_COMBAT:
            return False

        # Bucket 3: combat-compatible actions that fall through to their
        # normal handlers + count as a turn (enemy retaliates).
        ALLOWED_FALLTHROUGH = {
            "use",          # drink stim / throw grenade / activate item
            "wield",        # swap weapon mid-fight (P23)
            "sheathe",      # put weapon away (deliberate disengage)
            "coat_weapon",  # apply poison (P23)
            "inspect",      # look at something briefly — minor turn cost
            "wear", "take_off",  # P25 — re-armor mid-fight (risky)
            "intimidate", "bribe", "talk", "persuade",  # parley path
            "hack",         # robot combat → hack-to-disable is a key tactic
        }
        if intent.intent in ALLOWED_FALLTHROUGH:
            return False

        # Everything else: clean refusal, no turn consumed.
        REFUSAL_PL = {
            "loot":           "Nie teraz — masz walkę na karku.",
            "salvage":        "Nie zbierzesz złomu pod ostrzałem.",
            "harvest":        "Nie zbierzesz tego, póki cię atakują.",
            "search":         "Nie przeszukasz pokoju w środku walki.",
            "mass_loot_take": "Nie podniesiesz wszystkiego — masz inne kłopoty.",
            "mass_loot_loose": "Nie zgarniesz tego pod ostrzałem.",
            "mass_salvage":   "Nie rozbierzesz pokoju w środku walki.",
            "mass_search":    "Nie ma teraz na to czasu.",
            "mass_break":     "Bicie wszystkiego naraz nie jest atakiem.",
            "butcher_corpse": "Patroszenie poczeka — wróg żyje.",
            "eat_corpse":     "Naprawdę chcesz teraz jeść?",
            "rest":           "Nie odpoczniesz, póki cię biją.",
            "sleep":          "Próba snu w trakcie walki kończy się jednoznacznie.",
            "deploy":         "Pułapka wymaga spokoju — to nie ten moment.",
            "craft":          "Nie posklejasz tego pod uderzeniami.",
        }
        msg = REFUSAL_PL.get(intent.intent,
                             "Nie teraz — masz walkę na karku.")
        self.log(t(f"feedback_combat_refused_{intent.intent}",
                   fallback=msg), LOG_WARN)
        return True

    def _combat_after_player_action(self, cs) -> None:
        """Called at the end of every combat-aware player action. Ends
        combat if all hostiles are gone; otherwise runs the enemy turn."""
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        if room is None:
            return
        hostiles = _cmb.alive_hostiles_in(room)
        if not hostiles:
            _cmb.end_combat(room, self.world, outcome="all_down")
            self.log(t("feedback_combat_won",
                       fallback="Wszyscy wrogowie pokonani."), LOG_SUCCESS)
            return
        self._run_enemy_turn(cs)

    def _run_enemy_turn(self, cs) -> None:
        from . import combat as _cmb
        from . import time_system as ts
        room = self.world.current_floor.current_room()
        ch = self.world.character
        if room is None:
            return
        cs.side = "enemies"
        for eid in list(cs.participants):
            ent = self.world.get(eid)
            if ent is None or not ent.is_alive():
                continue
            action = _cmb.choose_enemy_action(self.world, cs, ent)
            self._apply_enemy_action(cs, ent, action)
            if not ch.is_alive():
                break
        # Tick statuses on all participants (including player via clocks on character)
        for eid in cs.participants:
            ent = self.world.get(eid)
            _cmb.tick_statuses(ent)
        _cmb.tick_statuses(ch)
        # Reset per-round player buffs.
        cs.player_defend = 0
        cs.player_dodge = False
        cs.round += 1
        cs.side = "player"
        ts.advance(self.world, 1)
        if not ch.is_alive():
            self._check_player_dead("combat_round_end",
                                    "na koniec rundy walki")
            return
        # Re-check end: if all hostiles dead/fled/disabled, end combat.
        hostiles = _cmb.alive_hostiles_in(room)
        if not hostiles:
            _cmb.end_combat(room, self.world, outcome="all_down")
            self.log(t("feedback_combat_won",
                       fallback="Wszyscy wrogowie pokonani."), LOG_SUCCESS)

    def _apply_enemy_action(self, cs, ent, action) -> None:
        from . import combat as _cmb
        ch = self.world.character
        room = self.world.current_floor.current_room()
        name = ent.display_name()
        if action.kind == "wait":
            self.log(f"{name}: {action.note or 'czeka'}.", LOG_NORMAL)
            return
        if action.kind == "approach":
            cs.bands[ent.entity_id] = _cmb.BAND_ENGAGED
            self.log(f"{name} zbliża się ({action.note or 'naciera'}).", LOG_WARN)
            return
        if action.kind == "back_off":
            cs.bands[ent.entity_id] = _cmb.BAND_AT_RANGE
            self.log(f"{name} cofa się, próbując utrzymać dystans.", LOG_NORMAL)
            return
        if action.kind == "flee":
            self.log(f"{name} ucieka z pola walki.", LOG_SUCCESS)
            ent.state = ent.state or {}
            ent.state["fled"] = True
            ent.hp = 0     # treated as no-longer-in-fight
            return
        if action.kind in ("attack",):
            dmg = int(action.damage or 1)
            # P27.6 (P27-UX-7): symmetric enemy roll log. Player only
            # saw final damage — never knew WHY they got hit or what
            # AC the enemy needed. Now we show the enemy's d20 + atk
            # vs player AC, so the math is transparent.
            try:
                import random as _r_enemy
                from .dice_labels import stat_pl as _spl_e
                e_raw = _r_enemy.randint(1, 20)
                e_atk = int(getattr(ent, "attack_bonus", 0) or 0)
                player_ac = ch.effective_ac(self.world)
                e_total = e_raw + e_atk
                e_outcome = ("KRYT" if e_raw == 20 else
                             ("trafienie" if e_total >= player_ac else
                              ("pudło" if e_raw > 1 else "fuks")))
                self.log(f"  [atak wroga] {ent.display_name()}: "
                         f"d20({e_raw}) + atak({e_atk:+d}) = "
                         f"{e_total} vs twoje AC {player_ac} → {e_outcome}",
                         LOG_SYSTEM)
                # Honor the roll: if enemy "missed" per the symmetric
                # math, suppress damage (was always landing before; now
                # there's a real miss chance shown to player).
                if e_total < player_ac and e_raw != 20:
                    self.log(f"{name} chybia.", LOG_NORMAL)
                    return
            except Exception:
                pass
            # P26b: faction-aware retarget. If the AI picked a rival
            # combat participant, damage that rival instead of the
            # player. Crossfire is the audience-pleasing scenario the
            # player can engineer by luring factions together.
            rival_id = getattr(action, "target_id", None)
            if rival_id is not None:
                rival = self.world.get(rival_id)
                if rival is not None and rival.is_alive():
                    rival.hp = max(0, rival.hp - dmg)
                    self.log(t("feedback_crossfire",
                               fallback=f"{name} atakuje rywala "
                                        f"„{rival.display_name()}” na {dmg} HP "
                                        f"(zostało {rival.hp}/{rival.max_hp}).",
                               attacker=name,
                               rival=rival.display_name(),
                               dmg=dmg,
                               hp=rival.hp, max_hp=rival.max_hp),
                             LOG_NORMAL)
                    # Crossfire is good TV — audience bump.
                    try:
                        from . import sponsors as _sp
                        _sp.note_player_tag(self.world, "crossfire", weight=2)
                    except Exception:
                        pass
                    # If the rival died, transform to corpse.
                    if rival.hp <= 0:
                        self.log(f"„{rival.display_name()}” pada.", LOG_SUCCESS)
                        try:
                            from . import corpses as _cp
                            _cp.transform_to_corpse(self.world, rival, killer=ent)
                        except Exception:
                            pass
                    return
            # Player target path (default / fallback).
            # P29.55 — precog_dodge (void): pierwszy hit/piętro
            # automatycznie missuje. Consumed one-shot.
            try:
                from . import species_effects as _sp_fx
                if _sp_fx.precog_dodge_consume(self.world):
                    self.log(f"Przewidujesz cios. {name} chybia w "
                             f"pustkę.", LOG_SUCCESS)
                    return
            except Exception:
                pass
            if _cmb.has_status(ch, _cmb.STATUS_BEHIND_COVER) and \
                    cs.bands.get(ent.entity_id) == _cmb.BAND_AT_RANGE:
                dmg = max(0, dmg - 2)
            if cs.player_dodge:
                # Dodge consumes; halve damage on success roll.
                import random as _r
                if _r.randint(1,20) + ch.stat_mod("DEX") >= 12:
                    dmg = max(0, dmg // 2)
                    self.log(f"Unikasz większej części ataku od {name}.", LOG_NORMAL)
            # Prompt 23: shield in offhand reduces damage by AC bonus.
            shield_bonus = ch.offhand_ac_bonus(self.world)
            if shield_bonus > 0:
                dmg = max(0, dmg - shield_bonus)
            dmg = max(0, dmg - cs.player_defend)
            if dmg <= 0:
                self.log(f"{name} atakuje, ale nie robi krzywdy.", LOG_NORMAL)
                return
            ch.take_damage(dmg)
            # P29.55 — glassblood (bleeds_easy): 20% szansy na bleed
            # gdy gracz dostaje HP loss. Doliczamy STATUS_BLEEDING
            # tylko jeśli nie ma już bleed-immune.
            try:
                import random as _r_bleed
                from . import species_effects as _sp_fx
                if _sp_fx.bleed_on_hit_check(ch, _r_bleed):
                    if not _sp_fx.status_blocked(ch, "bleeding"):
                        _cmb.add_status(ch, _cmb.STATUS_BLEEDING, 3)
                        self.log("Glassblood ranny — krwawisz.",
                                 LOG_WARN)
            except Exception:
                pass
            # P34-SFX-1 (P27.5): player_hit hook (always); player_crit
            # variant when ≥50% max HP in one blow.
            try:
                if dmg >= max(1, ch.max_hp // 2):
                    audio.play_sfx("player_crit_hit")
                else:
                    audio.play_sfx("player_hit")
            except Exception:
                pass
            self.log(f"{name} trafia cię na {dmg} HP "
                     f"(zostało {ch.hp}/{ch.max_hp}).", LOG_DANGER)
            # Heavy hits cause bleeding sometimes.
            if dmg >= 5:
                _cmb.add_status(ch, _cmb.STATUS_WOUNDED, 4)
            # P29.8 — check death immediately after the hit lands, not
            # only at end-of-round. Without this, multiple enemies in
            # one round can each land a "killing" blow before the
            # state actually flips, which messes with the log order
            # and the run-summary "cause of death".
            if self._check_player_dead(
                    f"combat:{ent.key}",
                    f"od ciosu „{ent.display_name()}”"):
                return

    # ── Player combat actions ──────────────────────────────────────────────

    def _combat_attack(self, intent, cs, mode: str = "normal"):
        from . import combat as _cmb
        from .utils_compat import roll_d20
        import random as _r
        room = self.world.current_floor.current_room()
        ch = self.world.character
        # Pick the first engaged enemy. Player can specify a name target via
        # intent.targets; we honor that if it resolves to a participant.
        target = None
        if intent.targets:
            from .validation import _resolve_entities
            candidates = _resolve_entities(room, intent.targets[0])
            if candidates and candidates[0].entity_id in cs.participants:
                target = candidates[0]
        if target is None:
            engaged = [self.world.get(eid) for eid in cs.participants
                       if cs.bands.get(eid) == _cmb.BAND_ENGAGED]
            engaged = [e for e in engaged if e and e.is_alive()]
            target = engaged[0] if engaged else \
                next((self.world.get(eid) for eid in cs.participants
                      if self.world.get(eid) and self.world.get(eid).is_alive()),
                     None)
        if target is None:
            self.log(t("feedback_combat_no_target",
                       fallback="Nie widzisz w kim uderzyć."), LOG_WARN)
            return
        band = cs.bands.get(target.entity_id, _cmb.BAND_ENGAGED)
        if band == _cmb.BAND_AT_RANGE:
            self.log(t("feedback_combat_out_of_range",
                       fallback=f"„{target.display_name()}” jest poza zasięgiem zwarcia. "
                                f"Zbliż się albo użyj czegoś z dystansu.",
                       name=target.display_name()), LOG_WARN)
            self._combat_after_player_action(cs)
            return
        raw = roll_d20()
        mod = ch.stat_mod("STR")
        to_hit_bonus = 0
        damage_bonus = 0
        defense_change = 0
        noise = 3
        # P29.21 — consume the show-director dramatic_zoom flag if
        # set. One-shot +1 to-hit. Flag lives on character.flags so
        # it survives save/load.
        if (ch.flags or {}).get("dramatic_zoom_attack"):
            to_hit_bonus += 1
            try:
                ch.flags["dramatic_zoom_attack"] = 0
            except Exception:
                pass
        # P29.14 — masterwork / good / flawed weapon quality + permanent
        # enhancement bonuses (grip tape, balance weight). Read from the
        # wielded main hand. Quality table:
        #   masterwork: +1 hit, +1 dmg
        #   good:       +0 hit, +1 dmg
        #   normal:     0 / 0
        #   flawed:     -1 hit, 0 dmg
        # Enhancements stack on top:
        #   attack_bonus_perm (grip tape)
        #   damage_bonus_perm (balance weight)
        try:
            from ..content import crafting as _cr
            _w = self.world.get(ch.wielded_main_id) if ch.wielded_main_id else None
            if _w is not None and _w.state:
                _q = _w.state.get("quality", "normal")
                _qb = _cr.quality_bonus_for_weapon(_q)
                to_hit_bonus += int(_qb.get("attack_bonus", 0))
                damage_bonus += int(_qb.get("damage_bonus", 0))
                to_hit_bonus += int(_w.state.get("attack_bonus_perm", 0))
                damage_bonus += int(_w.state.get("damage_bonus_perm", 0))
                # P29.14 — silent enhancement reduces attack noise.
                if "silent" in (_w.tags or []):
                    noise = max(1, noise - 2)
                # P29.29 — surface masterwork / good quality + perm
                # enhancements once per combat, so the player can
                # SEE that the +1s are working. The dice-roll log
                # line already shows the resulting bonus number, but
                # players can't tell which input contributed.
                if _q in ("masterwork", "good") or \
                   int(_w.state.get("attack_bonus_perm", 0)) or \
                   int(_w.state.get("damage_bonus_perm", 0)):
                    qlabel = _cr.quality_label_pl(_q)
                    parts = []
                    if qlabel:
                        parts.append(qlabel)
                    if int(_w.state.get("attack_bonus_perm", 0)):
                        parts.append(f"+{_w.state['attack_bonus_perm']} trafienie")
                    if int(_w.state.get("damage_bonus_perm", 0)):
                        parts.append(f"+{_w.state['damage_bonus_perm']} obrażenia")
                    if parts:
                        cs_state = getattr(cs, "state", None)
                        if cs_state is None:
                            try:
                                cs.state = {}
                                cs_state = cs.state
                            except Exception:
                                cs_state = None
                        if cs_state is not None and not cs_state.get(
                                "logged_weapon_quality"):
                            self.log(
                                f"„{_w.display_name()}” — "
                                f"{' · '.join(parts)}.",
                                LOG_SYSTEM)
                            cs_state["logged_weapon_quality"] = True
        except Exception:
            pass
        if mode == "careful":
            to_hit_bonus = 2
            damage_bonus = -1
            defense_change = 1
            noise = 2
        elif mode == "heavy":
            to_hit_bonus = -2
            damage_bonus = _r.randint(1,4)
            defense_change = -2
            noise = 5
        # P27.7 — class passive bonuses.
        try:
            from ..systems import class_features as _cf
            # Unarmed bruisers / demolitionists get extra damage.
            if ch.wielded_main_id is None:
                damage_bonus += _cf.passive_bonus(ch, "unarmed_dmg")
            # Buff flag set by the bruiser active.
            if ch.flags.pop("class_buff_next_attack_x2", False):
                damage_bonus += 10
        except Exception:
            pass
        dc = max(6, getattr(target, "ac", 10))
        total = raw + mod + to_hit_bonus
        # Status modifiers
        if _cmb.has_status(target, _cmb.STATUS_PRONE):     total += 2
        if _cmb.has_status(target, _cmb.STATUS_BLINDED):   total += 3
        if _cmb.has_status(target, _cmb.STATUS_STUNNED):   total += 3
        if _cmb.has_status(ch, _cmb.STATUS_BLINDED):       total -= 3
        # Prompt 21: status interactions get real teeth.
        if _cmb.has_status(target, _cmb.STATUS_CHILLED):   total += 2  # slow
        if _cmb.has_status(target, _cmb.STATUS_CORRODED):  total += 1  # AC -1
        if _cmb.has_status(ch, _cmb.STATUS_AFRAID):        total -= 2
        # Prompt 26a — maim modifiers.
        if _cmb.has_status(target, _cmb.STATUS_SLOWED):    total += 2  # easier to hit
        if _cmb.has_status(target, _cmb.STATUS_DISARMED):  total += 1  # off-balance
        if _cmb.has_status(ch, _cmb.STATUS_SLOWED):        total -= 2
        if _cmb.has_status(ch, _cmb.STATUS_DISARMED):
            # Player's arm is broken — main attacks are massively penalized.
            total -= 3
            damage_bonus -= 1
        # Prompt 21: prone+stunned compound auto-hit (was: just +5).
        if (_cmb.has_status(target, _cmb.STATUS_PRONE) and
                _cmb.has_status(target, _cmb.STATUS_STUNNED)):
            total += 5
        # Prompt 19 — companion advantage: +2 to-hit on the next player
        # attack after `użyj zwierzęcia jako wabika` fires in combat.
        # Consumed on use; one bonus per encounter.
        if getattr(cs, "companion_advantage_pending", False):
            total += 2
            cs.companion_advantage_pending = False
            self.log(t("companion_advantage_consumed",
                       fallback="(Towarzysz odwraca uwagę: +2 do trafienia.)"),
                     LOG_SYSTEM)
        # Prompt 26a — body-zone targeting. Reads the selected zone for
        # this target (defaults to "torso"). Applies to-hit modifier and
        # damage multiplier from the body plan. Already-broken zones get
        # a +1 to-hit because the wound makes them easier to hit again.
        from ..content.data import body_plans as _bp
        _bp.init_body_parts(target)
        plan = _bp.plan_for_entity(target)
        zone_key = (cs.targeted_zone_by_eid or {}).get(target.entity_id)
        if not zone_key or zone_key not in plan:
            # Default to torso if available; else the first zone.
            zone_key = "torso" if "torso" in plan else next(iter(plan.keys()))
        zone_props = plan.get(zone_key, {})
        zone_to_hit = int(zone_props.get("to_hit_mod", 0))
        zone_dmg_mul = float(zone_props.get("damage_mul", 1.0))
        total += zone_to_hit
        zone_part = target.body_parts.get(zone_key) or {}
        if zone_part.get("broken"):
            total += 1   # weakened zone, easier follow-up
        # P29.53m — graduated penalties from player's own body damage.
        # Damaged arm: −1 dmg. Crippled arm: −2 dmg, −1 to-hit. Damaged
        # head: −1 to-hit. Doesn't double-dip with STATUS_DISARMED
        # (broken parts) — that's handled separately above.
        player_body_mods = _bp.body_combat_mods(ch)
        total -= int(player_body_mods.get("attack_to_hit_delta", 0))
        damage_bonus -= int(player_body_mods.get("attack_dmg_delta", 0))
        # P29.53p — audience-as-lever: gorąca widownia "podkręca" gracza
        # (+1 / +2 to-hit), zimna sprawia że gracz traci flow (−1).
        # Małe wartości — bonusy nie zastąpią normalnej taktyki, tylko
        # nagradzają utrzymywanie spektaklu.
        try:
            from . import audience as _aud
            aud_mods = _aud.combat_mods_for_world(self.world)
            total += int(aud_mods.get("to_hit", 0))
        except Exception:
            pass
        # P29.55 — species: sun_sensitive penalty w jasnym pokoju
        # (safehouse / studio). Half_dead: −2 to-hit gdy w bright.
        try:
            from . import species_effects as _sp_fx
            room_for_species = (self.world.current_floor.current_room()
                                if self.world.current_floor else None)
            total += int(_sp_fx.to_hit_modifier(
                ch, room=room_for_species))
        except Exception:
            pass
        crit = (raw == 20)
        # Prompt 21: shocked players fumble on 1-2 instead of just 1.
        shocked_fumble_floor = 2 if _cmb.has_status(ch, _cmb.STATUS_SHOCKED) else 1
        fumble = (raw <= shocked_fumble_floor)
        hit = (not fumble) and (crit or total >= dc)
        mode_label = {"normal":"atak","careful":"ostrożny atak","heavy":"ryzykowny atak"}[mode]
        outcome_pl = ("KRYT" if crit else
                      ("trafienie" if hit else
                       ("pudło" if not fumble else "fuks")))
        from .dice_labels import stat_pl as _spl
        bonus_str = f" + bonus({to_hit_bonus:+d})" if to_hit_bonus else ""
        # Combat to-hit rolls vs AC (not TT) — AC is a target stat, not a
        # difficulty check, so it keeps its name. P26a: append the zone
        # label so the player sees WHICH part they swung at.
        zone_label_pl = zone_props.get("label_pl", zone_key) if zone_props else ""
        zone_str = f" → {zone_label_pl}" if zone_label_pl else ""
        zone_mod_str = (f" zona({zone_to_hit:+d})" if zone_to_hit else "")
        self.log(f"  [{mode_label}] d20({raw}) + {_spl('STR')}({mod:+d})"
                 f"{bonus_str}{zone_mod_str} = {total} vs AC {dc} → "
                 f"{outcome_pl}{zone_str}",
                 LOG_SYSTEM)
        # P27 — SFX hooks (silent until assets/sfx/* drops).
        try:
            if crit:        audio.play_sfx("hit_crit")
            elif hit:       audio.play_sfx("hit_landed")
            elif fumble:    audio.play_sfx("attack_fumble")
            else:           audio.play_sfx("attack_miss")
        except Exception:
            pass
        if hit:
            # Prompt 23: damage comes from the wielded main weapon
            # (damage_dice + damage_type). Unarmed default 1d6+2.
            # Coating, if present, overrides damage_type for this hit
            # and decrements. Routes through damage.apply_damage so
            # resistance/vulnerability/status-on-hit work uniformly.
            from . import damage as _dmg
            weapon = self.world.get(ch.wielded_main_id) if ch.wielded_main_id else None
            if weapon is not None:
                dmg_dice = weapon.damage_dice or "1d6+2"
                dmg_type = weapon.damage_type or "physical"
                weapon_name = weapon.display_name()
            else:
                # P27.6 balance: unarmed bumped to match new HP scale
                # (player now has 100 HP, monsters have ~25-200 HP).
                # 2d6+8 averages 15 — substantial chunk per hit without
                # being one-shot territory.
                dmg_dice = "2d6+8"
                dmg_type = "physical"
                weapon_name = "pięść"
            # Coating override.
            coating_status_applied = None
            coating = (weapon.state or {}).get("coating") if weapon else None
            if coating and coating.get("hits_remaining", 0) > 0:
                dmg_type = coating.get("damage_type", dmg_type)
            # Roll dice.
            base = _roll_dice_spec(dmg_dice, _r)
            dmg = base + mod + damage_bonus
            if crit:
                dmg *= 2
                # P29.55 — crit_amplifier trait (chimera): krytyki ×1.5
                # NA TOP normalnego ×2, czyli effective ×3.
                try:
                    from . import species_effects as _sp_fx
                    dmg = int(round(dmg * _sp_fx.outgoing_crit_mul(ch)))
                except Exception:
                    pass
            # Prompt 26a — scale damage by the zone's multiplier (head 1.5×,
            # limbs 0.8×, etc.).
            dmg = max(1, int(round(dmg * zone_dmg_mul)))
            # P29.5 — landing a hit reveals full stats (you learn HP
            # and AC from combat math). Promote target → inspected.
            try:
                from . import visibility as _vis
                _vis.mark_inspected(self.world, target)
            except Exception:
                pass
            # Apply via damage module (resistance + status on hit).
            res = _dmg.apply_damage(self.world, target, dmg,
                                    damage_type=dmg_type,
                                    source=f"weapon:{weapon_name}")
            # Prompt 26a — also debit zone HP. Damage applied to zone is
            # the actual amount dealt (post-resistance). Breaks trigger
            # maim status on the victim.
            actual = int(res.get("amount_dealt", dmg) or 0)
            if actual > 0 and zone_key in target.body_parts:
                zp = target.body_parts[zone_key]
                zp["hp"] = max(0, int(zp.get("hp", 0)) - actual)
                if zp["hp"] <= 0 and not zp.get("broken"):
                    zp["broken"] = True
                    maim = zone_props.get("maim_status")
                    if maim:
                        _cmb.add_status(target, maim, 3)
                    zone_label_pl = zone_props.get("label_pl", zone_key)
                    self.log(t("feedback_zone_broken",
                               fallback=f"„{target.display_name()}”: "
                                        f"{zone_label_pl} złamana!",
                               name=target.display_name(),
                               zone=zone_label_pl),
                             LOG_DANGER)
                    # P34-SFX-1 (P27.5): limb_broken hook.
                    try:
                        audio.play_sfx("limb_broken")
                    except Exception:
                        pass
            # P29.55 — ferromanta magnetic_disarm: 25% chance na
            # ściągnięcie broni z metal-armed targetu po hicie.
            try:
                from . import species_effects as _sp_fx
                if _sp_fx.magnetic_disarm_check(ch, target, _r):
                    _cmb.add_status(target, _cmb.STATUS_DISARMED, 3)
                    self.log(
                        f"Twoje pole magnetyczne wyrywa broń z dłoni "
                        f"„{target.display_name()}”.",
                        LOG_SUCCESS)
            except Exception:
                pass
            # Decrement coating on a landed hit.
            if coating and coating.get("hits_remaining", 0) > 0:
                coating["hits_remaining"] -= 1
                if coating["hits_remaining"] <= 0:
                    weapon.state["coating"] = None
                    self.log(t("feedback_coating_worn",
                               fallback=f"Powłoka „{weapon.display_name()}” się "
                                        f"zużyła."),
                             LOG_SYSTEM)
            tag = ""
            if res.get("immune"):
                tag = " (odporny)"
            elif res.get("resisted"):
                tag = " (osłabione)"
            elif res.get("vulnerable"):
                tag = " (podatny!)"
            type_label = _dmg.damage_type_label(dmg_type)
            self.log(f"„{target.display_name()}”: "
                     f"-{res['amount_dealt']} HP "
                     f"({type_label}){tag} "
                     f"(zostało {target.hp}/{target.max_hp}).",
                     LOG_SUCCESS if crit else LOG_NORMAL)
            if target.hp <= 0:
                self.log(f"„{target.display_name()}” pada.", LOG_SUCCESS)
                try:
                    audio.play_sfx("enemy_death")
                except Exception:
                    pass
                # Prompt 24 — corpse on death. Mutates target in place to
                # entity_type=corpse so all existing references (combat
                # state, sponsor tag bus, room.entities) stay valid. The
                # action bar will pick up the new affordances on its
                # next rebuild.
                try:
                    from . import corpses as _cp
                    _tags_pre = list(target.tags or [])
                    _cp.transform_to_corpse(self.world, target,
                                            killer=self.world.character)
                    # P29.44 — minibossy dropią kawałek mapy. Sprawdzamy
                    # tagi PRZED transformacją (corpse-tagi dodają się
                    # idempotentnie, ale na wszelki wypadek snapshot).
                    if "miniboss" in _tags_pre:
                        try:
                            self._drop_miniboss_map_fragment(target)
                        except Exception:
                            pass
                        # P29.49 — counter dla „klepacz_minibossow".
                        try:
                            ch_ = self.world.character
                            n = int(ch_.flags.get(
                                "floor_minibosses_killed", 0) or 0)
                            ch_.flags["floor_minibosses_killed"] = n + 1
                        except Exception:
                            pass
                    # P29.57d — Boss Box drop per rank. Każdy boss z
                    # tagiem `boss_rank:*` produkuje Skrzynkę odpowiedniej
                    # rangi w EQ gracza (DCC canon: zabójca dostaje łup).
                    # Plus bonus widowni zgodnie z rangą.
                    try:
                        _had_rank = any(
                            isinstance(t, str)
                            and t.startswith("boss_rank:")
                            for t in _tags_pre)
                        if _had_rank:
                            # Trzymamy snapshot tagów na bossie — corpse
                            # transform mógł je przepiąć, ale drop_boss_box
                            # czyta z entity, więc dorzucamy stare tagi
                            # z powrotem jeśli zostały zgubione.
                            for _t in _tags_pre:
                                if (isinstance(_t, str)
                                        and _t.startswith("boss_rank:")
                                        and _t not in (target.tags or [])):
                                    target.tags = (target.tags or []) + [_t]
                            from .handlers import boss_box as _bbx
                            _bbx.drop_boss_box(self.world, target,
                                               killer=self.world.character)
                            _bonus = _bbx.audience_bonus_for_dead_boss(target)
                            if _bonus > 0:
                                try:
                                    from . import audience as _aud2
                                    _aud2.change_audience(
                                        self.world, _bonus,
                                        source="boss_kill_rank")
                                except Exception:
                                    pass
                            # P29.57e — Wiercimajster codex: zapisz kill
                            # do persistent history (między runami).
                            try:
                                from . import run_history as _rh2
                                _fn = int(getattr(
                                    self.world.current_floor,
                                    "floor_number", 1) or 1)
                                _rh2.record_boss_kill(target, _fn)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # P29.49 — counter floor_kills (achievement
                    # „kazdy_ma_imie" sprawdza floor_kills==floor_butchered).
                    try:
                        ch_ = self.world.character
                        n = int(ch_.flags.get("floor_kills", 0) or 0)
                        ch_.flags["floor_kills"] = n + 1
                    except Exception:
                        pass
                    # P29.46 — CRITICAL FIX: ubicie floor_boss odblokowuje
                    # wyjście z piętra. Bez tego hook'a floor.exits_unlocked
                    # nigdy nie był ustawiany przez kod produkcyjny i
                    # gracz nie mógł zejść w dół. Bug pokrywał wszystkie
                    # 18 pięter — odkryty podczas playthrough.
                    if ("floor_boss" in _tags_pre
                            or "final_boss" in _tags_pre):
                        try:
                            self._unlock_floor_exits(reason="boss_defeated")
                        except Exception:
                            pass
                    # Tag-bus event: enemy_killed. Sponsor reactions, P28
                    # title tracking, and P31 vendetta hook into this.
                    try:
                        from . import sponsors as _sp
                        _sp.note_player_tag(self.world, "enemy_killed",
                                            weight=1)
                    except Exception:
                        pass
                    # P29.53p — audience-as-lever: kill daje +N widowni
                    # zależnie od bandu. HOT/VIRAL = +3/+5 (spektakl),
                    # COLD = +1 (widownia nudzi się). Dynamicznie nagradza
                    # za utrzymywanie show'u — gracz nie wydaje widowni,
                    # ale jej STAN dynamizuje progresję.
                    try:
                        from . import audience as _aud
                        kbonus = int(
                            _aud.combat_mods_for_world(self.world)
                            .get("audience_on_kill", 1))
                        if kbonus > 0:
                            _aud.change_audience(self.world, kbonus,
                                                 source="kill_band_bonus")
                    except Exception:
                        pass
                    # P29.8 — bump kill counter for the run summary.
                    self._bump_run_counter("run_kills", 1)
                    # P29.20 — companion chatter on kill.
                    try:
                        from . import companion_voice as _cv
                        _cv.maybe_say(self.world, "enemy_killed")
                    except Exception:
                        pass
                    # P29.15 — combat achievement triggers.
                    try:
                        from ..systems import achievements as _ach
                        ch_ = self.world.character
                        kills = int(ch_.run_kills or 0)
                        if kills == 1:
                            _ach.unlock(ch_, "pierwsza_krew", world=self.world)
                        if kills >= 50:
                            _ach.unlock(ch_, "rzeznia_kontrolowana",
                                        world=self.world)
                        if crit:
                            _ach.unlock(ch_, "finiszer_kanalu",
                                        world=self.world)
                        if "boss" in (target.tags or []) or \
                           "floor_boss" in (target.tags or []) or \
                           "final_boss" in (target.tags or []):
                            _ach.unlock(ch_, "boss_padl_pierwszy",
                                        world=self.world)
                    except Exception:
                        pass
                except Exception:
                    pass
            if mode == "heavy" and not crit:
                # Heavy attack exposes the player.
                _cmb.add_status(ch, _cmb.STATUS_WOUNDED, 2)
        else:
            if fumble:
                self.log(f"Twój atak idzie w bok i odsłaniasz się.", LOG_WARN)
                _cmb.add_status(ch, _cmb.STATUS_PRONE, 1)
            else:
                self.log(f"Chybiasz.", LOG_NORMAL)
        # Defense window for the enemy's reply.
        if defense_change != 0:
            cs.player_defend = max(0, cs.player_defend + max(0, defense_change))
        self._bump_threat(noise, source="combat_attack", room=room)
        cs.noise_added += noise
        cs.last_action = f"attack:{mode}"
        ch.affinity["melee"] = ch.affinity.get("melee", 0) + 1
        self._combat_after_player_action(cs)

    def _combat_defend(self, intent, cs):
        from . import combat as _cmb
        cs.player_defend = max(cs.player_defend, 3)
        self.log(t("feedback_combat_defend",
                   fallback="Bronisz się. Kolejny cios zaboli mniej."), LOG_SUCCESS)
        # P29.48 — track consecutive defends dla osiągnięcia
        # „reklama_przerywa_walke" (5 rund obrony pod rząd).
        prior = cs.last_action if hasattr(cs, "last_action") else ""
        if prior == "defend":
            cs.defend_streak = int(getattr(cs, "defend_streak", 0)) + 1
        else:
            cs.defend_streak = 1
        if cs.defend_streak >= 5:
            try:
                from ..systems import achievements as _ach
                _ach.unlock(self.world.character,
                            "reklama_przerywa_walke",
                            world=self.world)
            except Exception:
                pass
        cs.last_action = "defend"
        self._combat_after_player_action(cs)

    def _combat_dodge(self, intent, cs):
        cs.player_dodge = True
        self.log(t("feedback_combat_dodge",
                   fallback="Przygotowujesz się do uniku."), LOG_SUCCESS)
        cs.last_action = "dodge"
        self._combat_after_player_action(cs)

    def _combat_assess(self, intent, cs):
        from . import combat as _cmb
        if cs.assessed:
            self.log(t("feedback_combat_assessed_already",
                       fallback="Wiesz już wszystko, co da się ocenić bez bliższego oka."),
                     LOG_NORMAL)
            return
        cs.assessed = True
        self.log(t("feedback_combat_assess_h",
                   fallback="Oceniasz sytuację:"), LOG_SYSTEM)
        for eid in cs.participants:
            e = self.world.get(eid)
            if e is None or not e.is_alive():
                continue
            band = _cmb.describe_band(cs, e)
            threat = _cmb.describe_threat(e)
            behavior = _cmb.default_behavior(e)
            status = _cmb.list_status_pl(e)
            self.log(f"  • „{e.display_name()}” — {band}, {threat}. "
                     f"Styl: {behavior}. Status: {status}.", LOG_NORMAL)
        # Mention environment cues.
        room = self.world.current_floor.current_room()
        cues = []
        for e in (room.entities if room else []):
            tags = set(e.tags or [])
            if (e.state or {}).get("broken") or (e.state or {}).get("destroyed"):
                continue
            if "fragile" in tags or "glass" in tags:
                cues.append(f"{e.display_name()} — można rozbić")
            if "furniture" in tags and "salvageable" in tags:
                cues.append(f"{e.display_name()} — można przewrócić")
            if (room.state or {}).get("player_traps"):
                cues.append("masz w pokoju rozstawioną pułapkę — można w nią zwabić")
                break
        if cues:
            self.log("  Otoczenie: " + "; ".join(cues[:4]) + ".", LOG_NORMAL)
        cs.last_action = "assess"
        # Assess is free — DOES NOT trigger an enemy turn.

    def _combat_flee(self, intent, cs):
        """Try to escape through a known unlocked exit."""
        from . import combat as _cmb
        from .utils_compat import roll_d20
        room = self.world.current_floor.current_room()
        ch = self.world.character
        # Pick a destination: explicit if the player said one, else first
        # non-locked non-hidden exit.
        target_label = None
        if intent.destination:
            from .validation import fold
            tgt_f = fold(intent.destination)
            for label, ed in (room.exits or {}).items():
                if ed.get("hidden") or ed.get("locked"):
                    continue
                if fold(label) == tgt_f or tgt_f in fold(label):
                    target_label = label; break
        if target_label is None:
            for label, ed in (room.exits or {}).items():
                if not ed.get("hidden") and not ed.get("locked"):
                    target_label = label; break
        if target_label is None:
            self.log(t("feedback_combat_no_exit",
                       fallback="Nie widzisz, którędy uciekać."), LOG_WARN)
            self._combat_after_player_action(cs); return
        # DC scales with number of engaged hostiles and presence of guards.
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED]
        engaged = [e for e in engaged if e and e.is_alive()]
        guards = sum(1 for e in engaged
                     if _cmb.default_behavior(e) == _cmb.BEHAVIOR_GUARD)
        dc = 10 + 2 * len(engaged) + 3 * guards
        raw = roll_d20()
        mod = ch.stat_mod("DEX")
        total = raw + mod
        from .dice_labels import stat_pl as _spl
        self.log(f"  [ucieczka] d20({raw}) + {_spl('DEX')}({mod:+d}) = "
                 f"{total} vs TT {dc}", LOG_SYSTEM)
        if total >= dc or raw == 20:
            self.log(t("feedback_combat_flee_ok",
                       fallback=f"Wycofujesz się przez „{target_label}”.",
                       exit=target_label), LOG_SUCCESS)
            _cmb.end_combat(room, self.world, outcome="player_flee")
            # Move through the exit by submitting a normal move command.
            self.submit_generated_command(f"idź {target_label}")
            return
        else:
            self.log(t("feedback_combat_flee_fail",
                       fallback="Nie udaje ci się zerwać. Wrogowie wykorzystują moment."),
                     LOG_WARN)
            cs.last_action = "flee_fail"
            self._combat_after_player_action(cs)

    def _combat_reposition(self, intent, cs, toward: bool):
        from . import combat as _cmb
        # Move ALL enemies' bands in the chosen direction relative to player.
        # Approach (toward=True) sets engaged; back away sets at_range.
        new_band = _cmb.BAND_ENGAGED if toward else _cmb.BAND_AT_RANGE
        for eid in cs.participants:
            cs.bands[eid] = new_band
        if toward:
            self.log(t("feedback_combat_close_in",
                       fallback="Zbliżasz się do wrogów."), LOG_NORMAL)
        else:
            self.log(t("feedback_combat_back_off",
                       fallback="Cofasz się na dystans."), LOG_NORMAL)
        cs.last_action = "reposition"
        self._combat_after_player_action(cs)

    def _combat_use_environment(self, intent, cs) -> bool:
        """Break/throw/push in combat: in addition to the normal effect,
        apply a situational status to an engaged enemy if tags match.
        Returns True if a combat-environment hook fired (and an enemy turn
        followed); False if the action should just run normally."""
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        if room is None:
            return False
        from .validation import _resolve_entities
        if not intent.targets:
            return False
        candidates = _resolve_entities(room, intent.targets[0])
        if not candidates:
            return False
        target = candidates[0]
        tags = set(target.tags or [])
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED and
                   self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            return False
        victim = engaged[0]
        applied = None
        # Order matters: electrical+machine victim FIRST (so a panel
        # with both `electrical` and `fragile` tags shocks a machine
        # instead of just blinding it), then furniture push, then
        # generic fragile/glass break, then throw.
        if intent.intent == "break" and ("electrical" in tags or "wire" in tags) \
                and _cmb.default_behavior(victim) == _cmb.BEHAVIOR_MACHINE:
            _cmb.add_status(victim, _cmb.STATUS_SHOCKED, 2)
            applied = "shocked"
        elif intent.intent == "push_into" and "furniture" in tags:
            _cmb.add_status(victim, _cmb.STATUS_PRONE, 2)
            applied = "prone"
        elif intent.intent == "break" and ("glass" in tags or "fragile" in tags):
            _cmb.add_status(victim, _cmb.STATUS_BLINDED, 2)
            applied = "blinded"
        elif intent.intent == "throw_at" and "fragile" in tags:
            _cmb.add_status(victim, _cmb.STATUS_BLINDED, 1)
            applied = "blinded"
        if applied:
            self.log(t(f"feedback_combat_env_{applied}",
                       fallback=f"Otoczenie zwraca się przeciw „{victim.display_name()}” "
                                f"— status: {_cmb.status_label(applied)}.",
                       name=victim.display_name()), LOG_SUCCESS)
            # Don't double-process: run the underlying intent to actually
            # break/push/throw, then take an enemy turn.
            self._fallback_to_standard_pipeline(intent)
            cs.last_action = f"env:{applied}"
            self._combat_after_player_action(cs)
            return True
        return False

    def _combat_lure(self, intent, cs) -> None:
        from . import combat as _cmb
        room = self.world.current_floor.current_room()
        traps = (room.state or {}).get("player_traps") or []
        untriggered = [tr for tr in traps if not tr.get("triggered")]
        if not untriggered:
            self.log(t("feedback_combat_no_trap",
                       fallback="Nie masz w pokoju gotowej pułapki, do której można kogoś zwabić."),
                     LOG_WARN)
            return
        # Pick the first engaged hostile as the victim.
        engaged = [self.world.get(eid) for eid in cs.participants
                   if cs.bands.get(eid) == _cmb.BAND_ENGAGED and
                   self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            engaged = [self.world.get(eid) for eid in cs.participants
                       if self.world.get(eid) and self.world.get(eid).is_alive()]
        if not engaged:
            self.log(t("feedback_combat_no_target",
                       fallback="Nie widzisz w kogo wciągnąć w pułapkę."), LOG_WARN)
            return
        victim = engaged[0]
        # CHA check.
        from .utils_compat import roll_d20
        ch = self.world.character
        raw = roll_d20()
        mod = ch.stat_mod("CHA")
        if raw + mod >= 11:
            tr = untriggered[0]
            tr["triggered"] = True
            payload = tr.get("effect") or {}
            dmg = int(payload.get("amount", 3))
            victim.hp = max(0, victim.hp - dmg)
            self.log(t("feedback_combat_lure_ok",
                       fallback=f"„{victim.display_name()}” wpada w pułapkę — -{dmg} HP.",
                       name=victim.display_name(), amount=dmg), LOG_SUCCESS)
            if payload.get("type") == "damage_and_stun":
                _cmb.add_status(victim, _cmb.STATUS_STUNNED, 2)
            elif payload.get("type") == "knockdown":
                _cmb.add_status(victim, _cmb.STATUS_PRONE, 2)
        else:
            self.log(t("feedback_combat_lure_fail",
                       fallback="Próbujesz go zwabić, ale nie chwyta."),
                     LOG_WARN)
        cs.last_action = "lure"
        self._combat_after_player_action(cs)

    def _fallback_to_standard_pipeline(self, intent):
        """Run an intent through validate→resolve→apply as the standard
        play path would. Used by combat-environment hooks so we don't
        duplicate the break/salvage logic."""
        v = validate(intent, self.world)
        if not v.valid:
            self.log(v.message() or "—", LOG_WARN)
            # P26c: latch disambiguation (env-fallback path).
            self._stash_disambiguation_on_invalid(v, intent)
            return
        r = resolve(v, self.world)
        lines = apply(r.effects, self.world, time_system=time_system)
        for ln in lines:
            self.log(ln, LOG_NORMAL)

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
        # Prompt 22 bug fix: `_suppress_textinput` was sticky — a key that
        # didn't produce a TEXTINPUT (Enter, arrows, Backspace, Esc) would
        # leave the flag set, then steal the NEXT typed character. This
        # is why the first letter of a character name (and the first
        # letter typed in the command box after pressing any nav key) got
        # eaten. Clearing here means each keydown gets exactly one shot
        # to suppress its own corresponding textinput; nothing leaks past.
        self._suppress_textinput = False

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
                # P29.9 — route new_game / load_game through slot picker.
                if action == "new_game":
                    self._suppress_textinput = True
                    self._open_slot_picker("new")
                elif action == "load_game" and save_load.exists():
                    self._suppress_textinput = True
                    self._open_slot_picker("load")
                elif action == "settings":
                    # Prompt 11: open the settings popup.
                    self._open_settings()
                elif action == "quit":
                    pygame.quit(); raise SystemExit
                return
            if digit == "1":
                self._suppress_textinput = True
                self._open_slot_picker("new")
                return
            if digit == "2" and save_load.exists():
                self._suppress_textinput = True
                self._open_slot_picker("load")
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

        # P29.9 — slot picker.
        if self.state == STATE_SLOTS:
            self._suppress_textinput = True
            if key == pygame.K_ESCAPE:
                self._slot_picker_back(); return
            if key in (pygame.K_LEFT, pygame.K_a):
                self.slot_picker_idx = (self.slot_picker_idx - 1) % save_load.SAVE_SLOT_COUNT
                return
            if key in (pygame.K_RIGHT, pygame.K_d):
                self.slot_picker_idx = (self.slot_picker_idx + 1) % save_load.SAVE_SLOT_COUNT
                return
            if key == pygame.K_RETURN:
                self._slot_picker_pick(self.slot_picker_idx); return
            if digit is not None:
                # 1..3 → slots 0..2
                n = int(digit) - 1
                if 0 <= n < save_load.SAVE_SLOT_COUNT:
                    self._slot_picker_pick(n)
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
                bgs = self._creation_background_keys()
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
                    self._suppress_textinput = True
                    self._create_action("commit_bg")
                    return
                if digit is not None:
                    idx = int(digit) - 1
                    if 0 <= idx < len(bgs):
                        self._suppress_textinput = True
                        self.cc["selected_bg"] = idx
                        self._create_action("commit_bg")
                elif key == pygame.K_ESCAPE or key == pygame.K_BACKSPACE:
                    self.cc["step"] = "name"
            elif step == "species":
                sp = self._creation_species_keys()
                if key in (pygame.K_UP, pygame.K_w):
                    self.cc["selected_species"] = (self.cc.get("selected_species",0) - 1) % len(sp)
                    self._suppress_textinput = True; return
                if key in (pygame.K_DOWN, pygame.K_s):
                    self.cc["selected_species"] = (self.cc.get("selected_species",0) + 1) % len(sp)
                    self._suppress_textinput = True; return
                if key == pygame.K_RETURN:
                    self._suppress_textinput = True
                    self._create_action("commit_species")
                    return
                if digit is not None:
                    idx = int(digit) - 1
                    if 0 <= idx < len(sp):
                        self._suppress_textinput = True
                        self.cc["selected_species"] = idx
                        self._create_action("commit_species")
                elif key == pygame.K_ESCAPE or key == pygame.K_BACKSPACE:
                    self.cc["step"] = "background"
            elif step == "companion":
                comp = self._creation_companion_keys()
                if key in (pygame.K_UP, pygame.K_w):
                    self.cc["selected_companion"] = (self.cc.get("selected_companion",0) - 1) % len(comp)
                    self._suppress_textinput = True; return
                if key in (pygame.K_DOWN, pygame.K_s):
                    self.cc["selected_companion"] = (self.cc.get("selected_companion",0) + 1) % len(comp)
                    self._suppress_textinput = True; return
                if key == pygame.K_RETURN:
                    self._suppress_textinput = True
                    self._create_action("commit_companion")
                    return
                if digit is not None:
                    idx = int(digit) - 1
                    if 0 <= idx < len(comp):
                        self._suppress_textinput = True
                        self.cc["selected_companion"] = idx
                        self._create_action("commit_companion")
                elif key == pygame.K_ESCAPE or key == pygame.K_BACKSPACE:
                    self.cc["step"] = "species"
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

        if self.state == STATE_SPECIES_OFFER:
            offered = getattr(self, "species_offer_candidates", None) or []
            # Digit 1..4 picks one of the four offered species.
            # 0 (or 5) is the "stay as you are" decline.
            if digit is not None:
                self._suppress_textinput = True
                if int(digit) == 0 or int(digit) == 5:
                    self._decline_species()
                    return
                self._accept_species(int(digit) - 1)
                return
            if key == pygame.K_ESCAPE:
                self._suppress_textinput = True
                self._decline_species()
                return
            return

        # P29.41 — dialog tree z NPC. 1-9 wybiera opcję, Esc zamyka.
        if self.state == STATE_DIALOG:
            if digit is not None:
                self._suppress_textinput = True
                idx = int(digit) - 1
                if idx >= 0:
                    self._pick_dialogue_option(idx)
                return
            if key == pygame.K_ESCAPE:
                self._suppress_textinput = True
                self._close_dialogue()
                return
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

        # P25: slot popover swallows keyboard input while open.
        if self.slot_popover_open is not None:
            n = self._popover_row_count()
            if key == pygame.K_ESCAPE:
                self._popover_close()
                self._suppress_textinput = True
                return
            if key == pygame.K_UP:
                self.slot_popover_idx = max(0, self.slot_popover_idx - 1)
                self._suppress_textinput = True
                return
            if key == pygame.K_DOWN:
                self.slot_popover_idx = min(max(0, n - 1),
                                             self.slot_popover_idx + 1)
                self._suppress_textinput = True
                return
            if key == pygame.K_RETURN:
                self._popover_commit()
                self._suppress_textinput = True
                return
            self._suppress_textinput = True
            return

        # P26a: in combat, number keys 1-9 pick the selected target's
        # body zone (by display_order). Only fires when the input box is
        # empty so typing numbers in commands still works.
        if not self.input_text:
            try:
                from . import combat as _cmb
                from ..content.data import body_plans as _bp
                f = self.world.current_floor if self.world else None
                room = f.current_room() if f else None
                cs_zone = _cmb.get_combat(room) if room else None
                if cs_zone is not None and cs_zone.active and digit is not None:
                    tgt_id = getattr(cs_zone, "selected_target_id", None)
                    tgt = self.world.get(tgt_id) if tgt_id is not None else None
                    if tgt is not None and tgt.is_alive():
                        plan = _bp.plan_for_entity(tgt)
                        ordered = _bp.zones_in_display_order(plan)
                        idx = int(digit) - 1
                        if 0 <= idx < len(ordered):
                            zone_key, _props = ordered[idx]
                            cs_zone.targeted_zone_by_eid[tgt_id] = zone_key
                            self._suppress_textinput = True
                            return
            except Exception:
                pass

        # P24.5: full-screen map. Esc closes if open. M toggles only
        # when the input box is EMPTY (so 'M' as a typed letter still
        # works mid-command).
        if self.full_map_open:
            if key == pygame.K_ESCAPE:
                self.full_map_open = False
                self._suppress_textinput = True
                return
            # Map overlay swallows other keys (except Esc above).
            self._suppress_textinput = True
            return
        if key == pygame.K_m and not self.input_text:
            self.full_map_open = True
            self._suppress_textinput = True
            return
        if key == pygame.K_j and self.input_mode == "nav":
            # In nav mode J already submits 'wiedza' command — keep that
            # behaviour. In text mode the textinput layer handles 'j' as a
            # typed character.
            pass

        # Prompt 23.5 (backlog #1): PgUp / PgDn drive log scrollback in
        # both text and nav modes. Works on empty AND non-empty input
        # because they don't conflict with typing. Page step is 6 entries,
        # which is roughly one screenful at default resolutions.
        # P29.50 (#147) — clamp do REALNEGO overflow zamiast len(log)-1.
        # Wcześniej PgUp przy krótkim logu jeździł w pustkę (page-flip),
        # zamiast się zatrzymać kiedy nie ma już co odsłaniać.
        if key == pygame.K_PAGEUP and not self.journal_state.open:
            self.log_scroll = min(self.log_scroll + 6,
                                  self._log_max_scroll())
            self._suppress_textinput = True
            return
        if key == pygame.K_PAGEDOWN and not self.journal_state.open:
            self.log_scroll = max(0, self.log_scroll - 6)
            self._suppress_textinput = True
            return

        # P28.6 — minimap layer switching with [ / ]. Cycles through
        # available Z layers on the current floor (góra/dół exits create
        # multiple layers). The viewed layer lives on `world.minimap_z_view`;
        # `*` in the header marks "you are not on this layer". Only fires
        # when the input field is empty so it doesn't intercept brackets
        # the player might type.
        if (key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET)
                and not self.journal_state.open
                and not self.input_text.strip()):
            try:
                from ..ui import minimap as _mm
                floor = self.world.current_floor if self.world else None
                if floor is not None:
                    layers = _mm.available_z_layers(floor)
                    if len(layers) > 1:
                        cur = int(getattr(self.world, "minimap_z_view",
                                          _mm.player_z_layer(floor)))
                        if cur not in layers:
                            cur = _mm.player_z_layer(floor)
                        idx = layers.index(cur)
                        if key == pygame.K_RIGHTBRACKET:
                            idx = (idx + 1) % len(layers)
                        else:
                            idx = (idx - 1) % len(layers)
                        self.world.minimap_z_view = layers[idx]
                        self._suppress_textinput = True
                        return
            except Exception:
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
                # P23.5b: L/R hops by COLUMN (grid-aware).
                # P24.7: when a subject is focused AND cursor is on the
                # back row (index 0), L-arrow backs out instead of
                # column-hopping. Makes the back action discoverable.
                from ..ui import ui_nav
                self._ensure_nav_state()
                if self.nav_state.focused_subject() is not None \
                        and self.nav_state.selected_index() == 0:
                    self.nav_state.clear_focus()
                    self._suppress_textinput = True
                    return
                ui_nav.move_selection_column(self.nav_state, -1)
                self._suppress_textinput = True
                return
            if key in (pygame.K_RIGHT, pygame.K_d):
                from ..ui import ui_nav
                self._ensure_nav_state()
                ui_nav.move_selection_column(self.nav_state, +1)
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
                self._commit_nav_option(opt)
                self._suppress_textinput = True
                return
            if key == pygame.K_ESCAPE:
                # P24.7: in nav mode, Esc backs out of a two-tier focus
                # first; second Esc returns to text mode. Lets the player
                # navigate verbs → picker → tabs → text without an
                # explicit "← Powrót" click.
                self._ensure_nav_state()
                if self.nav_state.focused_subject() is not None:
                    self.nav_state.clear_focus()
                    self._suppress_textinput = True
                    return
                self.input_mode = "text"
                self._suppress_textinput = True
                return
            # Letter hotkeys in nav mode.
            if key == pygame.K_i:
                self.submit_generated_command("plecak"); self._suppress_textinput = True; return
            if key == pygame.K_m:
                # P24.5: M-key now opens the full-screen graphical map.
                self.full_map_open = not self.full_map_open
                self._suppress_textinput = True; return
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
            # Prompt 22 bug fix: WASD MUST NOT arm the nav latch in text
            # mode — the player typing `wschód` / `arszenik` / `daj` from
            # empty input expects W/A/S/D to land as letters. Only
            # arrow keys arm here. Nav mode (input_mode == "nav") keeps
            # WASD as nav shortcuts; that path is untouched.
            if key == pygame.K_UP:
                # P27.5 (P27-UX-25): PowerShell-style command history
                # WINS over nav-cursor arming when history is non-empty.
                # Gracz spodziewa się że UP w pustym polu pokaże
                # poprzednią komendę (jak w bash/powershell). Fallback
                # do nav arming gdy historia pusta.
                if self.cmd_history:
                    if self.cmd_history_idx == -1:
                        self.cmd_history_idx = len(self.cmd_history) - 1
                    else:
                        self.cmd_history_idx = max(0,
                                                    self.cmd_history_idx - 1)
                    self.input_text = self.cmd_history[self.cmd_history_idx]
                    self._suppress_textinput = True
                    return
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.move_selection(self.nav_state, -1)
                    self._nav_selection_armed = True
                    self._suppress_textinput = True
                    return
            if key == pygame.K_DOWN:
                # P27.5 (P27-UX-25): same PowerShell-style — DOWN walks
                # forward in history if we're browsing it. Else nav arm.
                if self.cmd_history_idx >= 0:
                    self.cmd_history_idx += 1
                    if self.cmd_history_idx >= len(self.cmd_history):
                        self.cmd_history_idx = -1
                        self.input_text = ""
                    else:
                        self.input_text = self.cmd_history[self.cmd_history_idx]
                    self._suppress_textinput = True
                    return
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.move_selection(self.nav_state, +1)
                    self._nav_selection_armed = True
                    self._suppress_textinput = True
                    return
            if key == pygame.K_LEFT:
                # P23.5b column hop + P24.7 back-row shortcut: when in
                # text mode with a focused subject AND the back row is
                # already selected, treat L-arrow as back.
                self._ensure_nav_state()
                if self.nav_state.groups:
                    if self.nav_state.focused_subject() is not None \
                            and self.nav_state.selected_index() == 0:
                        self.nav_state.clear_focus()
                        self._nav_selection_armed = True
                        self._suppress_textinput = True
                        return
                    ui_nav.move_selection_column(self.nav_state, -1)
                    self._nav_selection_armed = True
                    self._suppress_textinput = True
                    return
            if key == pygame.K_RIGHT:
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.move_selection_column(self.nav_state, +1)
                    self._nav_selection_armed = True
                    self._suppress_textinput = True
                    return
            if key == pygame.K_TAB:
                self._ensure_nav_state()
                if self.nav_state.groups:
                    ui_nav.cycle_group(self.nav_state, -1 if shift_held else +1)
                    self._nav_selection_armed = True
                    self._suppress_textinput = True
                    return
            if key == pygame.K_RETURN:
                # Prompt 18: Enter on empty input fires the nav option
                # ONLY when the player explicitly armed the selection by
                # pressing arrow / Tab first. Cold Enter on empty (e.g.
                # an extra tap after a failed typed command, or
                # autorepeat) is a no-op. This prevents the spam where
                # 'rozejrzyj się' replays itself N times after the
                # actual command fails.
                if self._nav_selection_armed:
                    self._ensure_nav_state()
                    opt = ui_nav.current_option(self.nav_state)
                    self._nav_selection_armed = False
                    self._commit_nav_option(opt)
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
        handle_keydown and from draw.

        Prompt 18: pass the previous nav_state so the rebuild preserves
        the currently-selected tab (group) and per-group cursor index.
        Otherwise every keystroke would snap selection back to Akcje,
        making Left/Right tab navigation between Akcje / Wyjścia /
        Ekwipunek / Crafting feel broken even though cycle_group fires.
        """
        from ..ui import ui_nav
        prev = getattr(self, "nav_state", None)
        self.nav_state = ui_nav.build_play_options(self.world, prev_state=prev)

    # ── P29.46: Floor exit unlock ────────────────────────────────────

    def _unlock_floor_exits(self, reason: str = "boss_defeated") -> None:
        """Odblokuj wyjście z piętra. Wywoływane po ubiciu floor_boss /
        final_boss. Bez tego floor.exits_unlocked NIGDY nie był
        ustawiany przez kod produkcyjny — wyjście z piętra zawsze
        było zamknięte. Klasyk."""
        floor = self.world.current_floor
        if floor is None:
            return
        if reason in floor.exits_unlocked:
            return
        floor.exits_unlocked.add(reason)
        # Komunikat dla gracza — w stylu Dinnimana, krótko:
        boss_pl = "Boss padł"
        if reason == "final_boss_defeated":
            boss_pl = "Finałowy boss padł"
        self.log(
            f"{boss_pl}. Z głośnika trzask: „Wyjście odblokowane. "
            f"Sponsorzy są zadowoleni. Przesuń się dalej.”",
            LOG_SUCCESS)

    # ── P29.53d: Drop → wyrzuca item z plecaka na podłogę ───────────

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

    def _consume_recipe_note(self, note_ent, recipe_key: str) -> None:
        """Po `użyj recipe_note_X` postać uczy się przepisu, notatka
        znika z plecaka (jednorazowa). Jeśli postać już zna przepis —
        notatka nadal się zużywa, ale gracz dostaje informację."""
        from ..content import crafting as _cr
        from ..content.data.recipe_templates import RECIPES
        ch = self.world.character
        new = _cr.teach_recipe(ch, recipe_key)
        # Zużyj notatkę — usuwamy z inventory.
        try:
            ch.inventory_ids.remove(note_ent.entity_id)
        except (ValueError, AttributeError):
            pass
        rec = RECIPES.get(recipe_key) or {}
        recipe_name = rec.get("name_pl", recipe_key)
        if new:
            msg = (f"Przeglądasz notatkę. Schemat „{recipe_name}” "
                   f"trafia ci pod powieki — zapamiętasz to bez "
                   f"czytania jeszcze raz.")
            self.log(msg, LOG_SUCCESS)
        else:
            msg = (f"Znowu „{recipe_name}”. Już to znałeś — notatka "
                   f"i tak rozsypała się w palcach.")
            self.log(msg, LOG_NORMAL)

    def _drop_miniboss_map_fragment(self, dead_target) -> None:
        """Po zabiciu minibossa upuść kawałek mapy obok zwłok.

        Delegacja do `drop_miniboss_map` (standalone), żeby unit-testy
        nie musiały tworzyć całego Game'a.
        """
        floor = self.world.current_floor
        if floor is None:
            return
        room = floor.current_room()
        if room is None:
            return
        it = drop_miniboss_map(self.world, room, dead_target,
                               floor.floor_number or 1)
        if it is None:
            return
        nm = "kawałek mapy" if it.key == "map_fragment" \
             else "pełna mapa piętra"
        dead_name = getattr(dead_target, "fallback_name", "") or "miniboss"
        msg = (f"Z kieszeni „{dead_name}” wypada coś pożytecznego: "
               f"{nm}. Ktoś tu wcześniej zaglądał.")
        self.log(msg, LOG_SUCCESS)

    # ── P24.5: Map item consumption ───────────────────────────────────

    def _consume_map_item(self, item) -> None:
        """A map fragment reveals 3-5 connected unexplored rooms from the
        player's current room; a full floor map reveals everything on
        the current floor. The revealed set lives on the floor as
        `known_room_ids` so the minimap picks them up."""
        floor = self.world.current_floor
        ch = self.world.character
        if floor is None:
            return
        import random as _r
        rng = _r.Random(self.world.random_seed) if getattr(self.world, "random_seed", None) else _r.Random()
        is_full = (item.key == "floor_map")
        revealed = set(floor.known_room_ids or set())
        if is_full:
            new_ids = set(floor.rooms.keys()) - revealed
            revealed |= new_ids
            self.log(t("feedback_floor_map_used",
                       fallback="Rozkładasz mapę całego piętra. "
                                "Wszystkie pokoje są teraz oznaczone."),
                     LOG_SUCCESS)
        else:
            # BFS from current room until we have N untracked rooms.
            start = floor.current_room_id
            queue = [start]
            seen = {start}
            collected = []
            while queue and len(collected) < 5:
                rid = queue.pop(0)
                r = floor.rooms.get(rid)
                if r is None:
                    continue
                for ed in (r.exits or {}).values():
                    tgt = ed.get("target", "")
                    if not tgt or tgt in seen:
                        continue
                    seen.add(tgt)
                    queue.append(tgt)
                    if tgt not in revealed:
                        collected.append(tgt)
            count = min(len(collected), rng.randint(3, 5))
            picked = collected[:count]
            revealed |= set(picked)
            self.log(t("feedback_map_fragment_used",
                       fallback=f"Strzęp mapy zdradza {len(picked)} "
                                f"sąsiednich pokoi.",
                       n=len(picked)), LOG_SUCCESS)
        floor.known_room_ids = revealed
        # Consume the item from inventory.
        try:
            ch.inventory_ids.remove(item.entity_id)
        except ValueError:
            pass

    # ── P24.5: Mouse input ────────────────────────────────────────────

    # ── P25 — slot popover handlers ──────────────────────────────────

    def _popover_equip(self, entity_id: int) -> None:
        from . import equipment as _eq
        slot = self.slot_popover_open
        if slot is None:
            return
        ent = self.world.get(entity_id)
        if ent is None:
            return
        # Wield slots route through the existing P23 wield path so
        # two-handed clears + Polish flavor lines stay consistent.
        if _eq.SLOT_DEFS[slot].is_wield:
            hand_mod = "hand:offhand" if slot == _eq.SLOT_OFF else "hand:main"
            from .parser_core import ActionIntent
            intent = ActionIntent(intent="wield", verb="dobądź",
                                  targets=[ent.display_name()],
                                  modifiers=[hand_mod])
            self._attempt_wield(intent)
        else:
            ok, prev_id, reason = _eq.equip(self.world, self.world.character,
                                            ent, slot)
            if not ok:
                self.log(reason or "Nie pasuje.", LOG_WARN)
            else:
                sd = _eq.SLOT_DEFS[slot]
                self.log(t("feedback_popover_wear_ok",
                           fallback=f"Zakładasz „{ent.display_name()}” "
                                    f"(slot: {sd.label_pl}).",
                           name=ent.display_name(), slot=sd.label_pl),
                         LOG_SUCCESS)
        self._popover_close()

    def _popover_unequip(self) -> None:
        from . import equipment as _eq
        slot = self.slot_popover_open
        if slot is None:
            return
        if _eq.SLOT_DEFS[slot].is_wield:
            # Reuse the P23 sheathe path.
            from .parser_core import ActionIntent
            self._attempt_sheathe(ActionIntent(intent="sheathe",
                                               verb="wycofaj broń"))
        else:
            ok, freed_id, reason = _eq.unequip(self.world,
                                                self.world.character, slot)
            if not ok:
                self.log(reason or "Slot pusty.", LOG_WARN)
            elif freed_id is not None:
                ent = self.world.get(freed_id)
                nm = ent.display_name() if ent is not None else "?"
                sd = _eq.SLOT_DEFS[slot]
                self.log(t("feedback_popover_unequip_ok",
                           fallback=f"Zdejmujesz „{nm}” (slot: {sd.label_pl}).",
                           name=nm, slot=sd.label_pl), LOG_SUCCESS)
        self._popover_close()

    def _popover_close(self) -> None:
        self.slot_popover_open = None
        self.slot_popover_idx = 0

    def _popover_row_count(self) -> int:
        """How many rows the popover currently shows (used by keyboard
        cursor bounds-clamping)."""
        from . import equipment as _eq
        slot = self.slot_popover_open
        if slot is None:
            return 0
        eligibles = _eq.eligible_inventory_for_slot(self.world,
                                                    self.world.character, slot)
        n = len(eligibles)
        if _eq.equipped(self.world.character, slot) is not None:
            n += 1   # Zdejmij row
        n += 1       # Anuluj row
        return n

    def _popover_commit(self) -> None:
        """Enter-pressed in the popover. Resolves the current cursor row
        to one of: equip an eligible / unequip / cancel."""
        from . import equipment as _eq
        slot = self.slot_popover_open
        if slot is None:
            return
        eligibles = _eq.eligible_inventory_for_slot(self.world,
                                                    self.world.character, slot)
        rows = []
        for ent in eligibles:
            rows.append(("equip", ent.entity_id))
        if _eq.equipped(self.world.character, slot) is not None:
            rows.append(("unequip", None))
        rows.append(("cancel", None))
        idx = max(0, min(self.slot_popover_idx, len(rows) - 1))
        kind, eid = rows[idx]
        if kind == "equip":
            self._popover_equip(eid)
        elif kind == "unequip":
            self._popover_unequip()
        else:
            self._popover_close()

    def _on_minimap_room_click(self, room_id: str) -> bool:
        """Click handler for minimap room cells (P24.6 / P24.5-2).

        Returns True if we acted on the click (moved or refused), so the
        default mark-toggle skips. Returns False to fall through to the
        mark-toggle behavior — which now only fires for the CURRENT
        room (a no-op visual ping).

        Move rules:
          - Target must be an ADJACENT room (i.e. one of the current
            room's exits points at it).
          - Exit must be unlocked AND not hidden — locked doors require
            keys/picks just like typed `idź <label>`.
          - Click on the CURRENT room: no-op move; fall through.
          - Click on a non-adjacent room: refuse with a log line so the
            player understands why nothing happened. P28 follow-up:
            silent mark-toggle was confusing — players read the
            highlight as "selected, will move next click", which was
            never the contract.
        """
        floor = self.world.current_floor if self.world else None
        if floor is None:
            return False
        cur_id = getattr(floor, "current_room_id", "")
        if room_id == cur_id:
            return False
        cur_room = floor.rooms.get(cur_id)
        if cur_room is None:
            return False
        # Find an exit pointing at `room_id`.
        matched_label = None
        matched_ed = None
        for label, ed in (cur_room.exits or {}).items():
            if ed.get("target") == room_id:
                matched_label = label
                matched_ed = ed
                break
        if matched_label is None:
            # Non-adjacent — refuse with explanation instead of silently
            # marking. Prevents the "I clicked but nothing visible
            # happened (except weird highlight)" UX bug.
            target_room = floor.rooms.get(room_id)
            target_name = (target_room.display_short_title()
                           if target_room else room_id)
            self.log(t("feedback_minimap_too_far",
                       fallback=f"„{target_name}” jest za daleko. "
                                f"Najpierw przejdź do sąsiedniego pokoju.",
                       name=target_name),
                     LOG_WARN)
            return True   # consume click — don't add a stray mark
        if matched_ed.get("hidden"):
            return False
        if matched_ed.get("locked"):
            self.log(t("feedback_minimap_locked",
                       fallback=f"Wyjście „{matched_label}” jest zamknięte."),
                     LOG_WARN)
            return True
        # Combat lockdown: in active combat the move resolver will
        # refuse / convert to flee. Route through the standard command
        # so the locking is consistent regardless of input source.
        self.submit_generated_command(f"idź {matched_label}")
        return True

    def _on_nav_option_click(self, group_key: str, option_idx: int) -> None:
        """Click callback for the action-bar option grid (P24.5 + P24.7).

        Mouse/keyboard parity: a click on a subject focuses that subject
        (and the next rebuild surfaces verbs); a click on a "back" row
        clears focus; a click on a verb (or "plain" option) commits its
        command. Keyboard cursor follows the click via the registry's
        keyboard_sync hint.
        """
        self._ensure_nav_state()
        if group_key not in self.nav_state.groups:
            return
        self.nav_state.current_group_index = self.nav_state.groups.index(group_key)
        opts = self.nav_state.options_in(group_key)
        if not (0 <= option_idx < len(opts)):
            return
        opt = opts[option_idx]
        self.nav_state.set_selected_index(option_idx, group_key)
        if not opt.enabled:
            return
        kind = getattr(opt, "option_kind", "plain")
        if kind == "subject":
            self.nav_state.set_focused_subject(group_key, opt.subject_id)
            return
        if kind == "back":
            self.nav_state.clear_focus(group_key)
            return
        # verb / plain — run the command.
        if opt.command:
            self.submit_generated_command(opt.command,
                                          target_id=opt.target_id)

    def _commit_nav_option(self, opt) -> None:
        """Shared Enter / armed-Enter logic for P24.7 — interprets the
        option's `option_kind` and either focuses, backs, or runs."""
        if opt is None or not opt.enabled:
            return
        kind = getattr(opt, "option_kind", "plain")
        if kind == "subject":
            group = self.nav_state.current_group()
            self.nav_state.set_focused_subject(group, opt.subject_id)
            return
        if kind == "back":
            self.nav_state.clear_focus()
            return
        if opt.command:
            self.submit_generated_command(opt.command,
                                          target_id=opt.target_id)

    def handle_mousedown(self, ev):
        """Left click → dispatch the topmost click zone under cursor.
        Right click / middle click ignored for now."""
        try:
            if ev.button != 1:
                return
        except AttributeError:
            return
        mx, my = ev.pos
        zone = self.click_registry.find(mx, my)
        if zone is None:
            return
        # Sync keyboard cursor with click target if hinted.
        if zone.keyboard_sync is not None:
            grp, idx = zone.keyboard_sync
            try:
                self._ensure_nav_state()
                if grp in self.nav_state.groups:
                    self.nav_state.current_group_index = \
                        self.nav_state.groups.index(grp)
                self.nav_state.set_selected_index(idx, grp)
            except Exception:
                pass
        # Fire the callback.
        try:
            zone.callback()
        except Exception as exc:
            # Don't let a UI handler bug crash the game; log + swallow.
            self.log(f"(klik: {exc})", LOG_WARN)
        # P28 (P27-UX-12): double-click on a VATS zone commits an
        # attack. The first click selects the zone (callback above);
        # a second click on the SAME zone within 400 ms submits
        # `zaatakuj`. Detection is by `zone.category` prefix.
        try:
            import pygame as _pg
            cat = (zone.category or "")
            if cat.startswith("vats_zone:"):
                now_ms = _pg.time.get_ticks()
                last = getattr(self, "_last_vats_click", None)
                if last and last[0] == cat and (now_ms - last[1]) < 400:
                    self.submit_generated_command("zaatakuj")
                    self._last_vats_click = None
                else:
                    self._last_vats_click = (cat, now_ms)
            else:
                # Click outside VATS resets the latch.
                self._last_vats_click = None
        except Exception:
            pass
        # Drain side-channel intents the click may have written.
        self._drain_ui_inputs()

    def handle_mousemotion(self, ev):
        try:
            self._mouse_xy = ev.pos
        except AttributeError:
            self._mouse_xy = (-1, -1)

    def handle_mousewheel(self, ev):
        """P29.3 — mouse wheel scrolls the log when hovering over the
        log panel. Up = older history, down = newer (back to live).
        Same step as PgUp/PgDn (3 per notch). Pygame-CE MOUSEWHEEL
        events have `ev.y`: +1 per notch up, -1 per notch down.

        Outside the log panel the wheel is a no-op (we don't hijack
        scroll on inventory popovers, minimap, etc.).
        """
        try:
            dy = int(getattr(ev, "y", 0))
        except (AttributeError, TypeError):
            return
        if dy == 0:
            return
        # Only act when cursor is over the log panel.
        try:
            mx, my = self._mouse_xy
        except Exception:
            return
        L = getattr(self, "_layout", None)
        if L is None:
            return
        lx, ly, lw, lh = L.log_rect
        if not (lx <= mx < lx + lw and ly <= my < ly + lh):
            return
        # Up (positive y) → scroll back into history; down → toward live.
        step = 3
        if dy > 0:
            self.log_scroll = min(self.log_scroll + step * dy,
                                  self._log_max_scroll())
        else:
            self.log_scroll = max(0, self.log_scroll + step * dy)

    def _log_max_scroll(self) -> int:
        """P29.50 (#147) — max scroll = ile WPISÓW jest poza ekranem
        nad widoczną listą. Bez tego clampa PgUp jeździł w pustkę
        (page-flip) zamiast się zatrzymać kiedy nie ma już nic
        nad widocznym oknem."""
        if self.world is None:
            return 0
        L = getattr(self, "_layout", None)
        if L is None:
            return 0
        # Aproksymacja available_rows wzięta z draw_log_and_input.
        try:
            _lx, _ly, _lw, lh = L.log_rect
            line_h = max(20, int(L.font_small) + 8)
            # P29.53 — uwzględnij 2px breathing room per row.
            avail = max(1, (lh - 22) // (line_h + 2))
        except Exception:
            return 0
        total = len(self.world.log or [])
        return max(0, total - avail)

    def _drain_ui_inputs(self):
        """Pick up side-channel signals that UI click handlers wrote to
        the world / game. Kept separate from the click callbacks so UI
        code doesn't need to import the parser pipeline."""
        # Paper-doll slot picked: open the P25 swap popover.
        pending_slot = getattr(self.world, "_pending_slot_swap", None)
        if pending_slot:
            slot_key, _slot_label = pending_slot
            self.world._pending_slot_swap = None
            self.slot_popover_open = slot_key
            self.slot_popover_idx = 0
        # Quick-strip item used.
        pending_use = getattr(self.world, "_pending_quick_use", None)
        if pending_use:
            self.world._pending_quick_use = None
            self.submit_generated_command(pending_use)

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
            # Prompt 18: typing immediately disarms the nav-selection
            # latch — the player is in text mode now.
            self._nav_selection_armed = False
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
        # P26b: floor-collapse end-of-run trigger. Time_system sets a
        # flag when the deadline crosses 0; Game flips to DEFEAT here
        # so the player sees the run end. P31 will add escape-at-exit
        # rescue + run-summary; today collapse == game over.
        if self.state == STATE_PLAY and self.world is not None:
            collapsed = False
            f = getattr(self.world, "current_floor", None)
            if f is not None:
                # Defensive getattr: pre-P26b FloorState objects (in
                # older save files or in tests that stub the class)
                # may not carry the `state` attribute. Treat absence
                # as "not collapsed" — the only side-effect of being
                # wrong is missing a deadline-cross from a stale save,
                # which is recoverable.
                fstate = getattr(f, "state", None) or {}
                collapsed = bool(fstate.get("collapsed"))
                # P29.24 — escape-at-exit: time_system flagged that
                # the player was at the exit when collapse fired.
                # Run the existing descent path instead of dying.
                if fstate.get("collapse_descend_requested"):
                    fstate["collapse_descend_requested"] = False
                    try:
                        self._descend_or_win()
                    except Exception:
                        # Defensive: if descent itself errors, fall
                        # through to defeat so we don't deadlock.
                        collapsed = True
            if collapsed:
                # P29.8 — collapse always kills (no last-stand save).
                # Force the flag so the helper runs its full death
                # path instead of granting an extra HP.
                ch = self.world.character if self.world else None
                if ch is not None:
                    ch.near_death_used = True
                    ch.hp = 0
                self._check_player_dead("floor_collapse",
                                        "przygniecony przez zawalające się piętro")

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
        # P28.7 — click registry is now reset BEFORE state-specific draw
        # so title + create + settings can register click zones too.
        # Mouse parity across every screen instead of "only works in play".
        self.click_registry.reset()
        if self.state == STATE_TITLE:
            ui.draw_title(s, save_load.exists(), selected_idx=self.title_idx,
                          click_registry=self.click_registry,
                          on_select=self._title_action)
        elif self.state == STATE_SETTINGS:
            ui.draw_settings(s, getattr(self, "settings_state", {}),
                             save_exists=save_load.exists())
        elif self.state == STATE_SLOTS:
            # P29.9 — three-card slot picker.
            slots_info = save_load.list_slots()
            ui.draw_slot_picker(s, slots_info,
                                mode=getattr(self, "slot_picker_mode", "new"),
                                selected_idx=getattr(self, "slot_picker_idx", 0),
                                click_registry=self.click_registry,
                                on_pick=self._slot_picker_pick,
                                on_back=self._slot_picker_back)
        elif self.state == STATE_CREATE:
            ui.draw_creation(s, self.cc,
                             click_registry=self.click_registry,
                             on_action=self._create_action)
        elif self.state == STATE_PLAY:
            self._refresh_layout()
            L = self._layout
            # P28.7 — registry already reset at draw() top.
            ui.draw_topbar(s, self.world, layout=L,
                           click_registry=self.click_registry)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L,
                                     click_registry=self.click_registry,
                                     on_room_click=self._on_minimap_room_click)
            ui.draw_room_panel(s, self.world, layout=L,
                               click_registry=self.click_registry)
            ui.draw_sidebar(s, self.world, layout=L,
                            click_registry=self.click_registry)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll,
                                  input_mode=self.input_mode, layout=L)
            self._ensure_nav_state()
            ui.draw_nav_panel(s, self.nav_state, self.input_mode, layout=L,
                              armed=getattr(self, "_nav_selection_armed", False),
                              click_registry=self.click_registry,
                              on_option_click=self._on_nav_option_click)
            # P24.5: full-screen map overlay (above all game UI, below tooltip).
            if getattr(self, "full_map_open", False):
                ui.draw_full_map_overlay(s, self.world, layout=L,
                                         click_registry=self.click_registry)
            # P25: slot-swap popover.
            if self.slot_popover_open is not None:
                ui.draw_slot_popover(
                    s, self.world, self.slot_popover_open,
                    self.slot_popover_idx, layout=L,
                    click_registry=self.click_registry,
                    on_pick=self._popover_equip,
                    on_unequip=self._popover_unequip,
                    on_close=self._popover_close,
                )
            # Hover tooltip overlay (drawn last so it floats above all).
            ui.draw_hover_tooltip(s, self.click_registry, self._mouse_xy, L)
            # Prompt 10: journal overlay sits on top.
            if self.journal_state.open:
                # P28.3 — mouse support: pass click_registry so tab + row
                # clicks dispatch (P27-UX-2). When the overlay is open,
                # clear the previously-registered world-view zones so
                # clicks outside the journal don't fire stale handlers.
                self.click_registry.reset()
                ui.draw_journal(s, self.world, self.journal_state, layout=L,
                                click_registry=self.click_registry)
        elif self.state == STATE_CLASS_OFFER:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll,
                                  layout=L)
            # Overlay listing the suggested classes
            from ..ui.lang import t as tr
            from ..systems.classes import CLASS_CATALOG
            lines = [tr("offer_title", fallback="PROPOZYCJA KLASY")]
            for i, key in enumerate(self.offer_candidates, 1):
                lines.append(f"[{i}] {tr(f'class_{key}_n', fallback=key)} — {tr(f'class_{key}_d', fallback='')}")
            lines.append(tr("offer_pick", fallback="Wybierz numerem (1-3)"))
            self._overlay(lines)
        elif self.state == STATE_SPECIES_OFFER:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll,
                                  layout=L)
            from ..systems import species as _sp_cat
            candidates = getattr(self, "species_offer_candidates",
                                 None) or []
            lines = ["KOMORA MUTACYJNA — PIĘTRO 3",
                     "Loch oferuje ci nową formę. Wybierz lub odmów."]
            for i, k in enumerate(candidates, 1):
                sp = _sp_cat.SPECIES_CATALOG.get(k)
                if sp is None:
                    continue
                lines.append("")
                lines.append(f"[{i}] {sp.name_pl}")
                lines.append(f"    Zysk: {sp.desc_pl}")
                lines.append(f"    Strata: {sp.drawback_pl}")
            lines.append("")
            lines.append("[0/Esc] Pozostań sobą (decline).")
            self._overlay(lines)
        elif self.state == STATE_DIALOG and self.dialogue_state is not None:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text,
                                   self.blink, scroll=self.log_scroll,
                                   layout=L)
            # P29.41 — dialog overlay: speaker + tekst + ponumerowane
            # opcje. Klawisz 1-9 wybiera, Esc zamyka.
            from . import dialogue as _dlg
            import textwrap as _tw
            node = _dlg.current_node(self.dialogue_state)
            lines = []
            if node is not None:
                lines.append(f"— {node.speaker} —")
                # Łamanie długiego tekstu na 80 znaków per linia.
                txt = node.text or ""
                lines.extend(_tw.wrap(txt, width=80) or [""])
                lines.append("")
                avail = _dlg.available_options(
                    self.world, self.dialogue_state, node)
                for i, (_real, opt) in enumerate(avail, 1):
                    suffix = ""
                    if opt.skill_check is not None:
                        stat, dc = opt.skill_check
                        suffix = f"  [{stat} vs TT {dc}]"
                    lines.append(f"[{i}] {opt.label}{suffix}")
                lines.append("")
                lines.append("[Esc] Wyjdź z rozmowy.")
            else:
                lines = ["(rozmowa zakończona — Esc)"]
            self._overlay(lines)
        elif self.state == STATE_VICTORY:
            self._end_screen(t("victory_title", fallback="ZEJŚCIE ZALICZONE."), True)
        elif self.state == STATE_DEFEAT:
            self._end_screen(t("defeat_title", fallback="ZAWODNIK WYELIMINOWANY."), False)
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
        """P29.8 — defeat renders the DCC highlight reel.
        P29.25 — victory ALSO renders the highlight reel via
        run_summary.render_lines(rs, victory=True). Title color +
        anti-host gloss swap, scoreboard structure is the same.
        """
        self.screen.fill((10, 12, 18))
        sw, sh = self.screen.get_size()
        col = (90, 210, 120) if success else (230, 80, 80)
        ui.text(self.screen, title_str, sw // 2 - 240, 80, col, 26, True)

        # Build / fetch the summary. Cached on death; built fresh on
        # victory (we don't intercept _descend_or_win → STATE_VICTORY
        # to cache it, so build it lazily here).
        if self.world is not None:
            rs = getattr(self, "run_summary", None)
            if rs is None:
                try:
                    from . import run_summary as _rs
                    rs = _rs.build_run_summary(self.world)
                    self.run_summary = rs
                except Exception:
                    rs = None
            if rs is not None:
                try:
                    from . import run_summary as _rs
                    lines = _rs.render_lines(rs, victory=success)
                except Exception:
                    lines = []
                cy = 140
                left = sw // 2 - 280
                for ln in lines:
                    color = (190, 205, 220)
                    # Subtle accent color for the anti-host line.
                    if ln == rs.anti_host_line:
                        color = (230, 200, 120)
                    elif ln.startswith("Top sponsorzy:") or \
                         ln.startswith("Przyczyna:"):
                        color = (180, 220, 240)
                    elif ln.startswith("Osiągnięcia:"):
                        color = (160, 230, 160)
                    elif ln.startswith("FINAŁ SEZONU"):
                        color = (140, 220, 160)
                    ui.text(self.screen, ln, left, cy, color, 16)
                    cy += 22

        ui.text(self.screen,
                t("end_press_enter", fallback="[Enter] Powrót do menu"),
                sw // 2 - 200, sh - 80, (90, 110, 130), 14)
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


def _roll_dice_spec(spec: str, rng) -> int:
    """Prompt 23: parse and roll '1d6+2' / '2d4' / '3'. Robust to
    garbage — returns the additive part on parse failure. Used for
    weapon damage dice."""
    if not spec:
        return 0
    spec = str(spec).strip().lower().replace(" ", "")
    if spec.isdigit():
        return int(spec)
    plus = 0
    if "+" in spec:
        spec, plus_s = spec.split("+", 1)
        try:
            plus = int(plus_s)
        except ValueError:
            plus = 0
    if "d" not in spec:
        return plus
    try:
        n, sides = spec.split("d", 1)
        n = int(n or "1")
        sides = int(sides)
    except ValueError:
        return plus
    if n <= 0 or sides <= 0:
        return plus
    return sum(rng.randint(1, sides) for _ in range(n)) + plus


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
