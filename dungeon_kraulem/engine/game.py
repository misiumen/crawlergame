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
from .combat_rules import CombatRulesMixin
from .action_handlers import ActionHandlersMixin
from .salvage_util import _pick_salvage_table_key


STATE_TITLE     = "title"
STATE_CREATE    = "create"
STATE_PLAY      = "play"
STATE_DIALOG    = "dialog"
STATE_CLASS_OFFER = "class_offer"
STATE_SPECIES_OFFER = "species_offer"
# P29.76 — picker rozdawania punktów atrybutu z awansów (DCC: gracz sam
# rozdaje). Wzór: STATE_CLASS_OFFER.
STATE_LEVELUP_ALLOC = "levelup_alloc"
STAT_ORDER = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
STAT_LABELS_PL = {
    "STR": "Siła", "DEX": "Zręczność", "CON": "Kondycja",
    "INT": "Inteligencja", "WIS": "Mądrość", "CHA": "Charyzma",
}
STATE_VICTORY   = "victory"
STATE_DEFEAT    = "defeat"
STATE_SETTINGS  = "settings"   # Prompt 11: simple settings popup from title
STATE_SLOTS     = "slots"      # P29.9: save-slot picker (3 slots)
STATE_PAUSE     = "pause"      # P30: in-game pause / escape menu
# P29.60 — Arena testowa: combat-only sandbox.
# STATE_ARENA_MENU = wybór wariantu, STATE_ARENA_PLAY reuses STATE_PLAY
# input/render ale z arena_mode flag żeby ominąć floor descent / save.
STATE_ARENA_MENU = "arena_menu"
STATE_ARENA_LOADOUT = "arena_loadout"
STATE_ARENA_PLAY = "arena_play"


# P29.60 — Arena loadout pickers content.
# (key, label_pl, description_pl)
ARENA_WEAPONS = [
    ("tani_noz", "Tani nóż",
     "1k6 cięcia. Standardowy janitor-grade."),
    ("zardzewiala_paika", "Zardzewiała pałka",
     "1k6+1 obuch. Cięższa, prostsza, głośniejsza."),
    ("paralizator", "Paralizator sponsorski",
     "1k4 prąd. Szansa na ogłuszenie celu."),
    ("kij_baseballowy", "Kij baseballowy",
     "1k8 obuch. Klasyk piętra 2, ciężki, dwuręczny."),
]

ARENA_CLASSES = [
    ("janitor", "Sprzątacz",
     "+1 INT, +1 KON. Skromne statystyki, dobre HP."),
    ("brawler", "Pięściarz",
     "+2 SIŁ, -1 INT. Premia do obrażeń, słaby na włamywanie."),
    ("medic", "Medyk polowy",
     "+1 MDR, +1 ZRĘ. Bandaże leczą +2."),
    ("scout", "Zwiadowca",
     "+2 ZRĘ, -1 CHA. Wysoka inicjatywa, słaba społecznie."),
]


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


class Game(CombatRulesMixin, ActionHandlersMixin):
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
        # P29.60 — Arena testowa state cursors.
        self.arena_menu_idx = 0          # variant picker selected
        self.arena_loadout_step = "weapon"  # "weapon" | "class"
        self.arena_loadout_weapon_idx = 0
        self.arena_loadout_class_idx = 0
        self.arena_loadout = {}          # final picks: {"weapon", "class"}
        # Demo (Intake) mode: set while the player is creating a character
        # for the single-floor playtest, so _creation_commit knows to start
        # the run in demo mode. Cleared on a normal new game.
        self._pending_demo = False
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

        # P29.76 / Feature#2 — stan reveala skrzynki (hybryda VS: modal +
        # lekka animacja). None = brak. Ustawiany przez handlers.boxes.
        self._box_reveal = None

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
        # Keyboard cursor for the dialogue option list (mouse + keyboard
        # parity). Reset on open; clamped to the available options each draw.
        self.dialogue_sel_idx = 0

        # Prompt 23.5 (backlog #1): log scrollback. 0 = pinned to newest.
        # PgUp / PgDn bump this in `_handle_play_keydown`; new log writes
        # auto-reset to 0 so the player never misses the latest hit.
        self.log_scroll = 0

        # Prompt 23.5 (backlog #2): when an action-panel option commits a
        # command, this carries the option's `target_id` through one
        # dispatch cycle so the validator can bypass disambiguation for
        # the already-resolved target. Cleared after each command.
        self._preresolved_target_id = None
        # When set (by dispatch_entity_action), the next _handle_play_input
        # skips the fuzzy parser and uses this pre-built intent instead, so a
        # UI click that already knows its entity + verb can't be hijacked by
        # keyword matching on the entity's name (UX-9). Read-once.
        self._forced_intent = None

        # UX-10 — contextual action popover. When set, a floating menu of an
        # entity's verbs is open (anchored at the clicked pin). Shape:
        #   {"entity_id": int, "options": [SelectableOption], "idx": int,
        #    "anchor": (x, y), "rect": (x, y, w, h) | None}
        # `rect` is filled by the renderer so the mouse handler can detect
        # clicks outside the menu (→ dismiss). None == no menu open.
        self.entity_popover = None

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
                        species: str = "baseline_human",
                        *, seed=None, demo_mode: bool = False):
        """Create a fresh world + character.

        P29.34: optional `species` parameter accepts any species key
        previously unlocked via meta-progression. Defaults to
        baseline_human (the pre-P29.34 behavior). Species bonuses
        get applied AFTER stat-profile + background-loadout so they
        stack on top of the base.

        Demo (Intake) mode: when `demo_mode` is True the run is flagged on
        `world.flags["demo_mode"]`, Floor 1's biome is pinned to the intake
        biome, and a fresh `seed` is rolled if none was supplied so each
        playtest gets a different layout/encounters while staying on the
        same intake floor. Everything else is the *same* game — demo mode
        only changes which biome Floor 1 uses and what happens when you
        clear it (see `_descend_or_win`).
        """
        self.world = WorldState()
        if demo_mode and seed is None:
            import random as _r
            seed = _r.randint(1, 2_000_000_000)
        if seed is not None:
            self.world.random_seed = seed
        if demo_mode:
            # `flags` is a dynamic attr on the world (like arena_mode),
            # not a dataclass field — init defensively before writing.
            self.world.flags = getattr(self.world, "flags", {}) or {}
            self.world.flags["demo_mode"] = True
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
            # P29.62 — bezdomny: NAJSŁABSZY profil (suma 54 vs 64-68 reszty).
            # Żaden stat nie wybija się ponad przeciętność; CHA dno (świat
            # go spisał na straty). Wyzwanie origin — rekompensuje go
            # Przetrwanie + mechanika underdoga, nie surowe staty.
            "bezdomny":          {"STR": 9,  "DEX": 10, "CON": 9,  "INT": 9,  "WIS": 11, "CHA": 6},
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
            # P29.62 — bezdomny: same uzbierane śmieci. Pęknięty kubek
            # (improwizowana tłuczka) + ochłap jedzenia. Bez bandaża —
            # ze swoim startowym statusem ma się zmierzyć Przetrwaniem,
            # nie gotową kuracją.
            "bezdomny":      ["cracked_mug","snack_bar"],
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
            # P29.62 — bezdomny: żadnej zbroi, żadnej broni. Czapka i
            # gumiaki ze śmietnika — tyle, ile uzbierał na ulicy.
            "bezdomny":          [("czapka_uszanka","head"),("kalosze","legs")],
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

        # P29.62 — bezdomny: underdog na każdym froncie. Wchodzi do lochu
        # bez grosza przy duszy i z dolegliwością, którą wlókł ze sobą
        # z ulicy (świeża rana / zatrucie czymś, co zjadł / niezaleczone
        # nadwerężenie). Status nakładamy na conditions — combat i
        # consequences czytają tę listę. Rekompensata (Przetrwanie,
        # mnożnik widowni dla underdoga) jest gdzie indziej.
        if background == "bezdomny":
            self.world.character.credits = 0
            import random as _r
            # Statusy spójne z kluczami combat (STATUS_BLEEDING/_POISONED/
            # _WOUNDED). Gracz widzi PL etykietę przez _STATUS_PL.
            start_ail = _r.choice(["bleeding", "poisoned", "wounded"])
            conds = self.world.character.conditions
            if start_ail not in conds:
                conds.append(start_ail)

        # Prompt 19 — pet-owner background gets a random companion. The
        # pet is registered BEFORE Floor 1 is built so its location_room_id
        # gets set to the start room (which doesn't exist yet); we patch
        # location_room_id after build below.
        if background == "opiekun_zwierzaka":
            self._assign_starter_pet()

        # Build Floor 1. Demo (Intake) mode pins the biome so the floor is
        # always the intake setting; the seed (rolled above) still varies
        # rooms / encounters / objectives between playtests.
        _demo_biome = "intake_industrial" if demo_mode else None
        self.world.current_floor = build_floor_1(self.world, seed=seed,
                                                 biome=_demo_biome)
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
            # P29.69 — skonsoliduj reakcję widowni z całej komendy (wraz
            # z turą wroga) w jedną linię „Widownia +N", zamiast rozsiewać
            # „+2" po logu.
            try:
                from . import audience as _aud_flush
                _aud_flush.flush_audience_log(self.world)
            except Exception:
                pass
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
        elif action_key == "arena_menu":
            # P29.60 — wejście do arena variant picker.
            self.arena_menu_idx = 0
            self.open_arena_menu()
        elif action_key == "demo_intake":
            # Single-floor intake playtest.
            self.enter_demo_intake()
        elif action_key == "settings":
            self._open_settings()
        elif action_key == "quit":
            pygame.quit()
            raise SystemExit
        elif action_key == "toggle_lang":
            set_language("en" if get_language() == "pl" else "pl")

    # ── P30 — in-game pause / escape menu ─────────────────────────────────

    def open_pause_menu(self) -> None:
        """Open the in-game pause menu (Escape). Remembers the state we came
        from so 'Wróć do gry' returns to it (play vs arena)."""
        self._pause_return_state = self.state
        self.pause_idx = 0
        # Debounce: key auto-repeat (set_repeat 400/50) fires a 2nd Escape
        # KEYDOWN shortly after the press that opened the menu, which would
        # immediately resume — making the menu flash open then closed. Stamp
        # the open time and ignore the resume-Escape for a short window.
        self._pause_opened_ms = pygame.time.get_ticks()
        self.state = STATE_PAUSE

    def _pause_resume(self) -> None:
        self.state = getattr(self, "_pause_return_state", STATE_PLAY) or STATE_PLAY

    def _pause_action(self, action_key: str) -> None:
        """Shared click/keyboard callback for the pause menu rows."""
        _demo = bool(getattr(self.world, "flags", {}).get("demo_mode")) \
            if self.world else False
        if action_key == "resume":
            self._pause_resume()
        elif action_key in ("save", "load") and _demo:
            # Demo (Intake) is an ephemeral sandbox with no save slot — saving
            # would clobber a real slot and loading would drop the demo flag.
            self.log("Zapis/wczytywanie niedostępne w piętrze próbnym.",
                     LOG_WARN)
            self._pause_resume()
        elif action_key == "save":
            ok = save_load.save(self.world)
            self.log(t("log_save_done", fallback="Zapisano.") if ok else
                     t("log_save_fail", fallback="Zapis nie powiódł się."),
                     LOG_SUCCESS if ok else LOG_DANGER)
            self._pause_resume()
        elif action_key == "load":
            if save_load.exists():
                self.slot_picker_mode = "load"
                self.slot_picker_idx = 0
                self.state = STATE_SLOTS
            else:
                self.log("Brak zapisu do wczytania.", LOG_WARN)
        elif action_key == "reseed":
            self._restart_with_new_rolls()
        elif action_key == "settings":
            # _open_settings stashes prev_state; make it return to pause.
            self._open_settings()
            try:
                self.settings_state["prev_state"] = STATE_PAUSE
            except Exception:
                pass
        elif action_key == "quit_to_menu":
            self.run_summary = None
            self.world = None
            self.state = STATE_TITLE
            self.title_idx = 0
        elif action_key == "quit_game":
            pygame.quit()
            raise SystemExit

    def _restart_with_new_rolls(self) -> None:
        """Reseed: start a fresh run with the SAME character name /
        background / species but newly rolled floors + a new random seed.
        Mirrors start_new_game's inputs from the current character."""
        ch = self.world.character if self.world else None
        name = getattr(ch, "name", "") or "Bezimienny"
        background = getattr(ch, "background", "unemployed_hustler")
        species = getattr(ch, "species_key", "baseline_human")
        # Preserve Demo (Intake) mode across a reseed — a playtest reroll
        # should stay on the intake floor, not silently become a full run.
        demo = bool(getattr(self.world, "flags", {}).get("demo_mode")) \
            if self.world else False
        self.run_summary = None
        self.start_new_game(name, background, species, demo_mode=demo)
        if not demo:
            # Fresh seed so floor generation + rolls differ from the old run.
            # (Demo mode already rolled its own fresh seed in start_new_game.)
            try:
                import random as _r
                self.world.random_seed = _r.randint(1, 2_000_000_000)
            except Exception:
                pass
        self.state = STATE_PLAY
        self.log("Nowy rozkład: świeże piętra i rzuty. Powodzenia.",
                 LOG_SYSTEM)

    # ── P29.9 — slot picker ──────────────────────────────────────────────

    def _open_slot_picker(self, mode: str) -> None:
        """Enter STATE_SLOTS. `mode` is 'new' or 'load'."""
        # Normal new/load flow is never a demo — clear any stale flag left
        # over from backing out of the Demo (Intake) creation screen.
        self._pending_demo = False
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
        demo = bool(getattr(self, "_pending_demo", False))
        self._pending_demo = False
        self.start_new_game(name, bg, species=species, demo_mode=demo)
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
            from .entity import T_CRAWLER, T_NPC
        except Exception:
            T_CRAWLER = "crawler"; T_NPC = "npc"
        if getattr(entity, "entity_type", "") == T_CRAWLER:
            return "default_crawler"
        # UX-4b — KAŻDY rozmawialny NPC dostaje drzewko (placeholder), zamiast
        # spadać do gołego legacy skill-checka „[rozmowa] d20… → sukces" bez
        # treści. Lepszy ogólny placeholder niż pusty rzut.
        affs = getattr(entity, "affordances", None) or []
        if getattr(entity, "entity_type", "") == T_NPC or "talk" in affs:
            return "placeholder_npc"
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
        self.dialogue_sel_idx = 0
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

    # Action-type → Polish display verb. The action_type IS the affordance /
    # intent key (talk, attack, inspect, hack, salvage, …), so the forced
    # intent uses it directly; this map only supplies the echoed command line.
    _ENTITY_ACTION_VERB_PL = {
        "inspect": "sprawdź", "talk": "pogadaj", "attack": "zaatakuj",
        "intimidate": "zastrasz", "hack": "zhakuj", "use": "użyj",
        "salvage": "rozbierz", "strip": "zdemontuj", "search": "przeszukaj",
        "loot": "przeszukaj", "open": "otwórz", "bribe": "przekup",
    }

    def dispatch_entity_action(self, entity_id, action_type: str = "inspect") -> None:
        """Run an action against a specific entity WITHOUT round-tripping
        through the fuzzy text parser.

        Pins and the action panel already know exactly which entity and which
        verb the player picked, so serialising to "<verb> <name>" and
        re-parsing is both wasteful and buggy: an entity whose name contains a
        reserved keyword (e.g. "…dla zadania") gets hijacked into a global
        quick-intent like opening the journal (UX-9). We build the
        ActionIntent directly and feed it to the normal validate→dispatch
        pipeline via `_forced_intent`. `action_type` equals the intent key.
        """
        if self.world is None or entity_id is None:
            return
        ent = self.world.get(entity_id)
        if ent is None:
            return
        at = action_type or "inspect"
        verb = self._ENTITY_ACTION_VERB_PL.get(at, at)
        name = ent.display_name()
        self.input_text = f"{verb} {name}".strip()
        self._preresolved_target_id = entity_id
        self._forced_intent = {"intent": at, "verb": verb, "targets": [name]}
        self.submit_input()

    # ── UX-10 — contextual action popover ────────────────────────────────

    def open_entity_popover(self, entity_id, anchor=None) -> None:
        """Open the floating verb menu for an entity (clicked pin / row).

        Builds the entity's verbs via the same logic the action panel uses,
        so menu and tabs stay in sync. If the entity offers exactly one verb
        (or none beyond inspect), we skip the menu and act directly — no
        point making the player click twice for a single option."""
        if self.world is None or entity_id is None:
            return
        ent = self.world.get(entity_id)
        if ent is None:
            return
        room = (self.world.current_floor.current_room()
                if self.world.current_floor else None)
        if room is None:
            return
        try:
            from ..ui import ui_nav as _nav
            opts = _nav.action_options_for_entity(self.world, room, ent)
        except Exception:
            opts = []
        if not opts:
            # Nothing structured — fall back to a plain inspect.
            self.dispatch_entity_action(entity_id, "inspect")
            return
        if len(opts) == 1:
            o = opts[0]
            self.dispatch_entity_action(o.target_id, o.action_type or "inspect")
            return
        self.entity_popover = {
            "entity_id": entity_id,
            "name": ent.display_name(),
            "options": opts,
            "idx": 0,
            "anchor": anchor,
            "rect": None,
        }

    def _close_entity_popover(self) -> None:
        self.entity_popover = None

    def _entity_popover_move(self, step: int) -> None:
        pop = self.entity_popover
        if not pop:
            return
        n = len(pop.get("options") or [])
        if n:
            pop["idx"] = (int(pop.get("idx", 0)) + step) % n

    def _entity_popover_activate(self, idx=None) -> None:
        """Run the selected verb, then close the menu."""
        pop = self.entity_popover
        if not pop:
            return
        opts = pop.get("options") or []
        i = pop.get("idx", 0) if idx is None else idx
        self._close_entity_popover()
        if 0 <= i < len(opts):
            o = opts[i]
            if o.target_id is not None and o.action_type:
                self.dispatch_entity_action(o.target_id, o.action_type)
            elif o.command:
                self.submit_generated_command(o.command, target_id=o.target_id)

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
        # UX-9 — direct entity dispatch from a pin / action-panel click.
        # `dispatch_entity_action` stashed the exact intent + target, so we
        # replace the parser's (possibly keyword-hijacked) result with it.
        fi = getattr(self, "_forced_intent", None)
        if fi is not None:
            self._forced_intent = None
            from .parser_core import ActionIntent
            forced = ActionIntent()
            forced.intent = fi["intent"]
            forced.verb = fi["verb"]
            forced.targets = list(fi["targets"])
            forced.normalized_text = (text_val or "").strip().lower()
            forced.raw_text = text_val or ""
            forced.parser_source = "ui_direct"
            intent = forced
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
        # P29.61 — systemowy łańcuch POZA walką. Wepchnij/zwab/rzuć
        # wroga w hazard działa niezależnie od tego, czy walka formalnie
        # trwa (immersive sim). W walce obsługuje to combat router
        # powyżej; tu łapiemy gdy walka nieaktywna, zanim generic
        # pipeline odmówi „nie odpowiada na takie działanie".
        if (intent.intent in ("push_into", "throw_at", "lure")
                and getattr(intent, "destination", None)):
            if self._try_systemic_chain(intent, None):
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
        if intent.intent == "rozdaj_punkty":
            self.open_stat_allocation(); return
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
        # P29.64 — `zbadaj pomieszczenie`: zunifikowane odkrycie OTOCZENIA
        # (istoty / środowisko z właściwościami / wyjścia). Obserwacja,
        # nie loot — `przeszukaj` zostaje osobno na przeszukiwanie.
        if intent.intent == "examine_room":
            self._attempt_examine_room(); return
        if intent.intent == "cast":
            self._attempt_cast(intent); return
        if intent.intent == "distract":
            self._attempt_distract(); return
        if intent.intent == "mass_salvage":
            self._attempt_mass_salvage(intent); return

        # UX-2 — room-wide scan actions (rozejrzyj się / nasłuchuj /
        # przeszukaj pokój) are one-and-done per room. A repeat just
        # reprints the same text with no progress, so we refuse cheaply
        # (no turn) and the action panel hides the row (ui_nav._basic_
        # actions reads room.state["actions_done"], which saves/loads).
        # This guard sits BEFORE the mass_search dispatch because
        # "przeszukaj pokój" parses to `mass_search` and returns right
        # after; `look`/`listen` continue to the standard pipeline below.
        # Per-OBJECT searches ("przeszukaj <skrzynia>") parse to `loot`
        # and are never affected.
        _scan_key = None
        if intent.intent in ("look", "listen"):
            _scan_key = intent.intent
        elif intent.intent == "mass_search":
            _scan_key = "search"
        if _scan_key is not None:
            _room = (self.world.current_floor.current_room()
                     if self.world.current_floor else None)
            if _room is not None:
                _done = _room.state.setdefault("actions_done", [])
                if _scan_key in _done:
                    self.log(t("feedback_action_exhausted",
                               fallback="Już to zrobiłeś tutaj. "
                                        "Nic nowego się nie pojawia."),
                             LOG_WARN)
                    return
                _done.append(_scan_key)

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

        # NOTE: the UX-2 room-scan exhaustion guard lives EARLIER (right
        # before the mass_search dispatch ~line 2849), because "przeszukaj
        # pokój" parses to `mass_search` which returns there and would never
        # reach this point. See `_scan_key` block above.

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
                    self._combat_open_briefing(cs2)
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
        self._arena_begin_combat()
        return True

    def _arena_begin_combat(self) -> None:
        """P29.61 — arena to combat sandbox: jeśli w pokoju są wrogowie,
        od razu odpalamy walkę (HUD/VATS aktywne, wróg kontruje na
        systemowe interakcje). Bez tego gracz stoi poza walką i część
        mechanik nie działa."""
        try:
            from . import combat as _cmb
            from . import magic as _magic
            from .entity import T_MONSTER, T_CRAWLER
            # P29.67 — w arenie gracz dostaje podstawowy zestaw zaklęć +
            # pełną manę, żeby przetestować magię (w normalnej grze brak,
            # póki nie ma akwizycji — „szary człowiek" zostaje szary).
            _magic.grant_core(self.world.character)
            _magic.ensure_mana(self.world.character)
            self.world.character.flags["mana"] = \
                _magic.max_mana(self.world.character)
            room = self.world.current_floor.current_room()
            if room is None:
                return
            has_hostile = any(
                e.entity_type in (T_MONSTER, T_CRAWLER) and e.is_alive()
                for e in room.entities)
            if has_hostile and _cmb.get_combat(room) is None:
                cs = _cmb.start_combat(room, self.world,
                                       triggered_by="arena_start")
                self.log(t("feedback_combat_start",
                           fallback="Walka się zaczyna."), LOG_WARN)
                self._combat_open_briefing(cs)
                # P30 — do NOT run an enemy turn here. start_combat already
                # telegraphs each hostile's intent; the player should act
                # first and respond to that telegraph, not eat a free hit
                # the instant the arena loads.
        except Exception:
            pass

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

    # ── Demo (Intake) — single-floor playtest mode ────────────────────────

    def enter_demo_intake(self) -> None:
        """Title → character creation for the Demo (Intake) playtest.

        Reuses the *exact* same creation flow as a normal new game (so the
        demo is a faithful excerpt, not a parallel system); we just flag the
        upcoming run as demo via `_pending_demo`, which `_creation_commit`
        reads. Demo skips the save-slot picker — it's an ephemeral sandbox
        like the arena, not tied to a save slot."""
        self._pending_demo = True
        self.cc = {"step": "name", "name_input": "",
                   "selected_bg": 0,
                   "selected_species": 0,
                   "selected_companion": 0}
        self.input_text = ""
        self.state = STATE_CREATE

    def _arena_pick_variant(self, variant_key: str) -> None:
        """Mouse/Enter callback z STATE_ARENA_MENU. Otwiera loadout
        picker dla wybranego wariantu."""
        from . import arena as _arena
        v = _arena.get_variant(variant_key)
        if v is None or not v.enabled:
            return
        self._pending_arena_variant = variant_key
        self.arena_loadout_step = "weapon"
        self.arena_loadout_weapon_idx = 0
        self.arena_loadout_class_idx = 0
        self.arena_loadout = {}
        self.state = STATE_ARENA_LOADOUT

    def _arena_back_to_title(self) -> None:
        """Z arena menu back to STATE_TITLE."""
        self.state = STATE_TITLE
        self.title_idx = 2  # cursor na "ARENA TESTOWA"

    def _arena_back_to_menu(self) -> None:
        """Z arena loadout back to arena menu."""
        self.state = STATE_ARENA_MENU
        self._pending_arena_variant = None

    def _arena_loadout_pick(self, step: str, key: str) -> None:
        """Mouse callback z STATE_ARENA_LOADOUT. Confirm wybor dla
        bieżącego kroku, advance do nastepnego lub start variant."""
        if step == "weapon":
            self.arena_loadout["weapon"] = key
            self.arena_loadout_step = "class"
        elif step == "class":
            self.arena_loadout["class"] = key
            # Start the variant with selected loadout
            self.start_arena_variant_with_loadout(
                self._pending_arena_variant,
                weapon_key=self.arena_loadout.get("weapon", "tani_noz"),
                class_key=self.arena_loadout.get("class", "janitor"))

    def start_arena_variant_with_loadout(self, variant_key: str, *,
                                          weapon_key: str = "tani_noz",
                                          class_key: str = "janitor") -> bool:
        """Wraps start_arena_variant — passes class jako background,
        zapisuje weapon do character.flags do późniejszego wpięcia
        przez arena.build_arena_world (P29.60 cz.3 follow-up: faktyczna
        equipment integration)."""
        from . import arena as _arena
        try:
            world, _floor = _arena.build_arena_world(
                variant_key, background=class_key, weapon_key=weapon_key)
        except ValueError as exc:
            if self.world is not None:
                self.world.log_msg(f"Arena: {exc}", "warn")
            return False
        self.world = world
        # Mark weapon w flags — full equipment integration follow-up
        if world.character.flags is None:
            world.character.flags = {}
        world.character.flags["arena_starting_weapon"] = weapon_key
        self.state = STATE_ARENA_PLAY
        self.world.log_msg(
            world.current_floor.current_room().fallback_first_enter,
            "normal")
        # Resolve the weapon's PL display name instead of the raw key so the
        # log reads "miecz okopowy oficera", not "miecz_okopowy_oficera"
        # (and never the English "warden baton").
        try:
            from ..content.items import make_item as _mk
            _wname = _mk(weapon_key).display_name()
        except Exception:
            _wname = weapon_key.replace("_", " ")
        self.world.log_msg(
            f"Loadout: broń = {_wname}, klasa = {class_key}.",
            "system")
        # The loadout flow is the path the arena menu actually uses, but it
        # never kicked off combat (only the legacy direct start_arena_variant
        # did) — so the player dropped into the arena standing outside any
        # fight. Auto-start combat here too.
        self._arena_begin_combat()
        return True

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
        # Demo (Intake) mode: clearing the single floor IS the win. Route to
        # the same victory screen the full game uses (summary built lazily in
        # _end_screen), then Enter/Esc returns to the title. We deliberately
        # do NOT descend or record the run into persistent meta-progression /
        # history — the demo is an ephemeral sandbox (same stance as arena).
        if getattr(self.world, "flags", {}).get("demo_mode"):
            self.log("Piętro próbne zaliczone. Test zakończony.", LOG_SUCCESS)
            try:
                from . import run_summary as _rs
                self.run_summary = _rs.build_run_summary(self.world)
            except Exception:
                self.run_summary = None
            self.state = STATE_VICTORY
            return
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

    # ── P30 — awans: klikalna karta rozdania atrybutów ──────────────────
    def open_stat_allocation(self) -> bool:
        """Otwiera klikalną kartę rozdania punktów, jeśli są nierozdane.
        Zwraca True gdy otwarto, False gdy nic do rozdania."""
        ch = self.world.character if self.world else None
        if ch is None or int(getattr(ch, "unspent_stat_points", 0) or 0) <= 0:
            self.log("Brak punktów awansu do rozdania.", LOG_NORMAL)
            return False
        self.title_idx = 0
        self._return_state_after_alloc = self.state
        self._levelup_zones = []
        self.state = STATE_LEVELUP_ALLOC
        return True

    def _levelup_close(self) -> None:
        """Leave the allocation card, back to whatever opened it."""
        self.state = (getattr(self, "_return_state_after_alloc", STATE_PLAY)
                      or STATE_PLAY)
        self._levelup_zones = []

    def _accept_stat_point(self, idx: int):
        ch = self.world.character if self.world else None
        if ch is None or int(getattr(ch, "unspent_stat_points", 0) or 0) <= 0:
            self._levelup_close()
            return
        if not (0 <= idx < len(STAT_ORDER)):
            return
        stat = STAT_ORDER[idx]
        ch.stats[stat] = int(ch.stats.get(stat, 10)) + 1
        ch.unspent_stat_points = int(ch.unspent_stat_points) - 1
        self.log(f"+1 {STAT_LABELS_PL.get(stat, stat)} (teraz {ch.stats[stat]}). "
                 f"Punkty do rozdania: {ch.unspent_stat_points}.", LOG_SUCCESS)
        # Stay on the card while points remain so the player can keep
        # spending and watch the live preview; auto-close on the last point.
        if int(ch.unspent_stat_points) <= 0:
            self._levelup_close()

    def _levelup_click(self, pos) -> None:
        """Mouse hit-test for the stat card: per-stat [+] buttons + the
        Gotowe/Zatwierdź button. Zones registered by _draw_levelup_card."""
        mx, my = pos
        for (rx, ry, rw, rh), kind, payload in getattr(self, "_levelup_zones", []):
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                if kind == "add":
                    self._accept_stat_point(payload)
                elif kind == "confirm":
                    self._levelup_close()
                return

    def _draw_levelup_card(self) -> None:
        """P30 — mouse-driven stat allocation card themed as a contestant
        upgrade. Each attribute is a row with value + modifier and a green
        [+] button; a live preview shows derived stats (HP / AC / to-hit);
        a confirm button closes. Click zones are stashed on
        self._levelup_zones and hit-tested by _levelup_click. Keyboard
        (↑/↓ + Enter, digits, Esc) still works via handle_keydown."""
        from ..ui.ui import (text, font, panel, PANEL_BG, BORDER, BRIGHT_TEXT,
                             NORMAL_TEXT, DIM_TEXT, ACCENT, ACCENT2, DANGER,
                             SUCCESS)
        import pygame
        s = self.screen
        if s is None:
            return
        ch = self.world.character
        W, H = s.get_size()
        left = int(getattr(ch, "unspent_stat_points", 0) or 0)

        # Dim the world behind the card.
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        s.blit(veil, (0, 0))

        row_h = 42
        bw = min(W - 120, 560)
        bh = 104 + len(STAT_ORDER) * row_h + 66
        bx = (W - bw) // 2
        by = (H - bh) // 2
        panel(s, (bx, by, bw, bh))
        pygame.draw.rect(s, ACCENT, (bx, by, bw, bh), 2)

        zones = []
        text(s, "AWANS — ROZBUDOWA ZAWODNIKA", bx + 22, by + 16,
             BRIGHT_TEXT, font(22), True)
        text(s, f"Punkty sponsorskie do rozdania: {left}",
             bx + 22, by + 46, ACCENT2 if left > 0 else DIM_TEXT, font(15))

        rows_y = by + 82
        name_x = bx + 26
        val_x = bx + 230
        mod_x = bx + 300
        btn_w, btn_h = 36, 30
        btn_x = bx + bw - btn_w - 28
        cur_i = self.title_idx % len(STAT_ORDER)

        for i, sk in enumerate(STAT_ORDER):
            ry = rows_y + i * row_h
            sel = (i == cur_i)
            if sel:
                pygame.draw.rect(s, (40, 48, 64),
                                 (bx + 12, ry - 4, bw - 24, row_h - 4))
            cur = ch.stats.get(sk, 10)
            mod = ch.stat_mod(sk)
            text(s, STAT_LABELS_PL.get(sk, sk), name_x, ry + 4,
                 BRIGHT_TEXT if sel else NORMAL_TEXT, font(18), sel)
            text(s, f"{cur}", val_x, ry + 4, BRIGHT_TEXT, font(18), True)
            text(s, f"({mod:+d})", mod_x, ry + 6, DIM_TEXT, font(14))
            active = left > 0
            bcol = SUCCESS if active else (60, 60, 68)
            pygame.draw.rect(s, bcol, (btn_x, ry, btn_w, btn_h))
            pygame.draw.rect(s, BORDER, (btn_x, ry, btn_w, btn_h), 1)
            text(s, "+", btn_x + btn_w // 2 - 5, ry + 4,
                 (10, 10, 12) if active else DIM_TEXT, font(22), True)
            if active:
                zones.append(((btn_x, ry, btn_w, btn_h), "add", i))

        # Live derived-stat preview.
        prev_y = rows_y + len(STAT_ORDER) * row_h + 6
        try:
            ac = (ch.effective_ac(self.world)
                  if hasattr(ch, "effective_ac") else 10 + ch.stat_mod("DEX"))
            text(s, f"HP {ch.hp}/{ch.max_hp}    KP {ac}    "
                    f"trafienie: SIŁ {ch.stat_mod('STR'):+d} / "
                    f"ZRĘ {ch.stat_mod('DEX'):+d}",
                 name_x, prev_y, ACCENT2, font(13))
        except Exception:
            pass

        # Confirm button.
        label = "ZATWIERDŹ" if left <= 0 else "GOTOWE (resztę później)"
        cw = max(170, font(15).size(label)[0] + 28)
        cb_h = 32
        cb_x = bx + (bw - cw) // 2
        cb_y = by + bh - cb_h - 16
        pygame.draw.rect(s, (30, 60, 40), (cb_x, cb_y, cw, cb_h))
        pygame.draw.rect(s, SUCCESS, (cb_x, cb_y, cw, cb_h), 1)
        text(s, label, cb_x + 14, cb_y + 7, BRIGHT_TEXT, font(15), True)
        zones.append(((cb_x, cb_y, cw, cb_h), "confirm", None))

        text(s, "klik [+] lub ↑/↓ + Enter · Esc / Gotowe = zamknij",
             bx + 22, cb_y + 7, DIM_TEXT, font(12))

        self._levelup_zones = zones

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

    def _active_combat(self):
        """COMBAT-1 P1 — return the active CombatState for the current room,
        or None. Used by draw() to switch to the dedicated combat surface
        (combat bar instead of exploration tabs) while a fight is on."""
        try:
            from . import combat as _cmb
            f = self.world.current_floor if self.world else None
            room = f.current_room() if f else None
            cs = _cmb.get_combat(room) if room else None
            return cs if (cs is not None and cs.active) else None
        except Exception:
            return None

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
            # P29.64 — ocena otoczenia w walce (czego użyć?) jest darmowa.
            "examine_room",
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
            "cast",         # P29.67 — czar w walce (gł. tryb maga)
            "distract",     # P29.68 — hałas jako narzędzie (zwab/spłosz)
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

    def _spawn_combat_fx(self, anchor, txt, color, *, big=False, shake=0.0,
                         kick=0):
        """P29.65 / COMBAT-1 P2 game-juice: przejściowy efekt walki —
        pływająca liczba obrażeń + błysk celu + opcjonalny shake + KICK
        (odrzut portretu/karty na trafieniu, DD-style). Trzymane na
        `world.combat_fx`, rysowane przez ui, wygaszane w update(dt).
        Defensywne — nigdy nie wywala tury. `anchor` = entity_id albo
        „player". `kick` = px odrzutu (dodatni = w prawo dla wroga)."""
        try:
            w = self.world
            if w is None:
                return
            fx = getattr(w, "combat_fx", None)
            if not isinstance(fx, dict):
                fx = {"floaters": [], "flash": {}, "shake": 0.0}
                w.combat_fx = fx
            fx["floaters"].append({"anchor": anchor, "text": str(txt),
                                   "color": color, "age": 0.0,
                                   "ttl": 950.0, "big": bool(big)})
            if len(fx["floaters"]) > 24:
                del fx["floaters"][:-24]
            fx.setdefault("flash", {})[anchor] = max(
                float(fx.get("flash", {}).get(anchor, 0.0)), 240.0)
            if shake:
                fx["shake"] = max(float(fx.get("shake", 0.0)), float(shake))
            if kick:
                # Per-anchor recoil: {anchor: [offset_px, ttl_ms]}. Decays
                # toward 0 in update(dt); the renderer shifts the portrait.
                kd = fx.setdefault("kick", {})
                kd[anchor] = [float(kick), 220.0]
        except Exception:
            pass

    def _combat_open_briefing(self, cs) -> None:
        """COMBAT-1 Slice A — emit a one-line read of the primary target the
        moment combat opens, so the player isn't forced to spend the `assess`
        action just to see what they're up against. Shows band, threat,
        weakness (the lever) and the telegraphed intent (what's coming). Does
        NOT set cs.assessed — the full `oceń` action still adds the deeper
        per-enemy breakdown + environment cues."""
        # COMBAT-1 P1 — fire the "WALKA SIĘ ZACZYNA" transition banner. A
        # short timed overlay (counted down in update(dt), drawn in
        # draw_combat_arena) so combat starting is a clear MOMENT, not a
        # silent slide into a turn.
        try:
            fx = getattr(self.world, "combat_fx", None)
            if not isinstance(fx, dict):
                fx = {}
                self.world.combat_fx = fx
            fx["banner"] = {"text": "WALKA SIĘ ZACZYNA", "ttl": 1100.0,
                            "age": 0.0}
        except Exception:
            pass
        from . import combat as _cmb
        tid = getattr(cs, "selected_target_id", None)
        e = self.world.get(tid) if tid is not None else None
        if e is None or not e.is_alive():
            return
        # Polish-only labels for damage-type keys.
        try:
            from .damage import damage_type_label as _dtl
            def _pl(k): return _dtl(k, "pl")
        except Exception:
            def _pl(k): return k
        band = _cmb.describe_band(cs, e)
        threat = _cmb.describe_threat(e)
        bits = [band, threat]
        weak = list(getattr(e, "vulnerable_to", None) or [])
        if weak:
            bits.append("słaby na: " + ", ".join(_pl(k) for k in weak))
        intent = (getattr(cs, "enemy_intents", None) or {}).get(e.entity_id)
        if intent:
            label = intent.get("label_pl") or intent.get("category", "")
            if label:
                bits.append("zamiar: " + label)
        self.log(f"Naprzeciw: „{e.display_name()}” — {', '.join(bits)}.",
                 LOG_WARN)
        # COMBAT-1 P3 — the "thinking" nudge. When the enemy RESISTS physical,
        # plain attacks are halved (engine/damage), so brute is slow + costly.
        # Tell the player the lever exists (coat the blade / use the room /
        # hit the weakness) WITHOUT forcing one method — brute still works.
        resists = list(getattr(e, "resists", None) or [])
        if "physical" in resists:
            lever = []
            if weak:
                lever.append("posmaruj broń (" + ", ".join(_pl(k) for k in weak) + ")")
            lever.append("wykorzystaj otoczenie")
            self.log("Zwykłe ciosy się ślizgają po tym czymś — "
                     + " albo ".join(lever) + ". Brute zadziała, ale wolno.",
                     LOG_SYNDIC)

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
        # P29.76 — reveal skrzynki przechwytuje input: 1. klawisz pomija
        # animację (pełne ujawnienie), 2. klawisz zamyka overlay.
        _br = self._box_reveal
        if _br is not None:
            if not _br.get("done"):
                _br["shown"] = len(_br.get("content_lines") or [])
                _br["done"] = True
            else:
                self._box_reveal = None
            self._suppress_textinput = True
            return
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
            # Arrow-key navigation mirroring the five visible items.
            # P29.60 — arena_menu wstawione przed settings.
            title_actions = ["new_game", "load_game", "arena_menu",
                             "demo_intake", "settings", "quit"]
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
                elif action == "arena_menu":
                    # P29.60 — arena testowa.
                    self._suppress_textinput = True
                    self.arena_menu_idx = 0
                    self.open_arena_menu()
                elif action == "demo_intake":
                    # Single-floor intake playtest.
                    self._suppress_textinput = True
                    self.enter_demo_intake()
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
                # P29.60 — arena testowa.
                self._suppress_textinput = True
                self.arena_menu_idx = 0
                self.open_arena_menu()
                return
            if digit == "4":
                self._suppress_textinput = True
                self.enter_demo_intake()
                return
            if digit == "5":
                self._open_settings()
                return
            if digit == "6":
                pygame.quit(); raise SystemExit
            if key == pygame.K_l:
                set_language("en" if get_language() == "pl" else "pl")
                self._suppress_textinput = True
            return

        if self.state == STATE_SETTINGS:
            return self._handle_settings_keydown(key, shift_held)

        # P30 — pause / escape menu.
        if self.state == STATE_PAUSE:
            from ..ui import ui as _uimod
            items = _uimod.PAUSE_MENU_ITEMS
            n = len(items)
            self._suppress_textinput = True
            if key == pygame.K_ESCAPE:
                # Ignore the auto-repeat Escape that follows the opening
                # press (see open_pause_menu); a real second tap (>250 ms
                # later) still resumes.
                if pygame.time.get_ticks() - getattr(
                        self, "_pause_opened_ms", 0) < 250:
                    return
                self._pause_resume(); return
            if key in (pygame.K_UP, pygame.K_w):
                self.pause_idx = (self.pause_idx - 1) % n; return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.pause_idx = (self.pause_idx + 1) % n; return
            if key == pygame.K_RETURN:
                self._pause_action(items[self.pause_idx % n][0]); return
            if digit is not None and 1 <= int(digit) <= n:
                self._pause_action(items[int(digit) - 1][0])
            return

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

        # P29.60 — arena variant picker
        if self.state == STATE_ARENA_MENU:
            self._suppress_textinput = True
            from . import arena as _arena
            variants = _arena.all_variants()
            total = len(variants) + 1  # +1 for "Powrót"
            if key == pygame.K_ESCAPE:
                self._arena_back_to_title(); return
            if key in (pygame.K_UP, pygame.K_w):
                self.arena_menu_idx = (self.arena_menu_idx - 1) % total
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.arena_menu_idx = (self.arena_menu_idx + 1) % total
                return
            if key == pygame.K_RETURN:
                if self.arena_menu_idx < len(variants):
                    v = variants[self.arena_menu_idx]
                    if v.enabled:
                        self._arena_pick_variant(v.key)
                else:
                    self._arena_back_to_title()
                return
            if digit is not None:
                n = int(digit) - 1
                if 0 <= n < len(variants):
                    v = variants[n]
                    if v.enabled:
                        self._arena_pick_variant(v.key)
                elif n == len(variants):
                    self._arena_back_to_title()
            return

        # P29.60 — arena loadout picker
        if self.state == STATE_ARENA_LOADOUT:
            self._suppress_textinput = True
            step = self.arena_loadout_step
            options = ARENA_WEAPONS if step == "weapon" else ARENA_CLASSES
            cur = (self.arena_loadout_weapon_idx if step == "weapon"
                   else self.arena_loadout_class_idx)
            if key == pygame.K_ESCAPE:
                if step == "class":
                    # Back to weapon step
                    self.arena_loadout_step = "weapon"
                else:
                    self._arena_back_to_menu()
                return
            if key in (pygame.K_UP, pygame.K_w):
                cur = (cur - 1) % len(options)
                if step == "weapon":
                    self.arena_loadout_weapon_idx = cur
                else:
                    self.arena_loadout_class_idx = cur
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                cur = (cur + 1) % len(options)
                if step == "weapon":
                    self.arena_loadout_weapon_idx = cur
                else:
                    self.arena_loadout_class_idx = cur
                return
            if key == pygame.K_RETURN:
                self._arena_loadout_pick(step, options[cur][0])
                return
            if digit is not None:
                n = int(digit) - 1
                if 0 <= n < len(options):
                    self._arena_loadout_pick(step, options[n][0])
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

        if self.state == STATE_PLAY or self.state == STATE_ARENA_PLAY:
            # P29.60 — arena play używa tego samego keydown routera
            # (typing/Enter/Backspace/strzałki) co normalna gra.
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

        if self.state == STATE_LEVELUP_ALLOC:
            n = len(STAT_ORDER)
            if key in (pygame.K_UP, pygame.K_w):
                self.title_idx = (self.title_idx - 1) % n
                self._suppress_textinput = True
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.title_idx = (self.title_idx + 1) % n
                self._suppress_textinput = True
                return
            if key == pygame.K_RETURN:
                self._suppress_textinput = True
                self._accept_stat_point(self.title_idx % n)
                return
            if key == pygame.K_ESCAPE:
                self._suppress_textinput = True
                self._levelup_close()
                return
            if digit is not None and 1 <= int(digit) <= n:
                self._suppress_textinput = True
                self._accept_stat_point(int(digit) - 1)
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

        # P29.41 — dialog tree z NPC. 1-9 / strzałki+Enter wybiera, Esc zamyka.
        if self.state == STATE_DIALOG:
            self._suppress_textinput = True
            if digit is not None:
                idx = int(digit) - 1
                if idx >= 0:
                    self._pick_dialogue_option(idx)
                return
            if key in (pygame.K_UP, pygame.K_w):
                self.dialogue_sel_idx = max(0, self.dialogue_sel_idx - 1)
                return
            if key in (pygame.K_DOWN, pygame.K_s):
                self.dialogue_sel_idx += 1   # clamped against options at draw
                return
            if key == pygame.K_RETURN:
                self._pick_dialogue_option(self.dialogue_sel_idx)
                return
            if key == pygame.K_ESCAPE:
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
        # UX-10 — the contextual entity popover owns input while open.
        if self.entity_popover is not None:
            self._suppress_textinput = True
            if key == pygame.K_ESCAPE:
                self._close_entity_popover()
                return
            if key in (pygame.K_UP, pygame.K_w):
                self._entity_popover_move(-1); return
            if key in (pygame.K_DOWN, pygame.K_s):
                self._entity_popover_move(1); return
            if key == pygame.K_RETURN:
                self._entity_popover_activate(); return
            if digit is not None:
                idx = int(digit) - 1
                opts = self.entity_popover.get("options") or []
                if 0 <= idx < len(opts):
                    self._entity_popover_activate(idx)
                return
            return

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

        # COMBAT-1 P1: in combat, number keys 1-7 fire the COMBAT BAR actions
        # (Atak / Ostrożny / Mocny / Unik / Obrona / Oceń / Uciekaj). Body
        # ZONE selection moved to the portrait reticle (mouse) — digits now
        # drive the action bar, matching the dedicated combat surface. Only
        # fires when the input box is empty so typed numbers still work.
        if not self.input_text and digit is not None:
            cs_bar = self._active_combat()
            if cs_bar is not None:
                from ..ui.ui import _COMBAT_BAR_ACTIONS
                idx = int(digit) - 1
                if 0 <= idx < len(_COMBAT_BAR_ACTIONS):
                    _label, _cmd, _hot = _COMBAT_BAR_ACTIONS[idx]
                    self.submit_generated_command(_cmd)
                    self._suppress_textinput = True
                    return

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
            # P30 — Esc with a non-empty command box just clears it (old
            # behavior). On an empty box, open the pause / escape menu.
            if self.input_text:
                self.input_text = ""
            else:
                self.open_pause_menu()
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
        # verb / plain — run the command. When the option targets a known
        # entity with a known action_type, dispatch directly (parser-free)
        # so an entity name containing a reserved keyword can't be hijacked.
        if getattr(opt, "target_id", None) is not None and getattr(opt, "action_type", None):
            self.dispatch_entity_action(opt.target_id, opt.action_type)
        elif opt.command:
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
        if getattr(opt, "target_id", None) is not None and getattr(opt, "action_type", None):
            self.dispatch_entity_action(opt.target_id, opt.action_type)
        elif opt.command:
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
        # P29.76 — klik pomija/zamyka reveal skrzynki.
        _br = self._box_reveal
        if _br is not None:
            if not _br.get("done"):
                _br["shown"] = len(_br.get("content_lines") or [])
                _br["done"] = True
            else:
                self._box_reveal = None
            return
        mx, my = ev.pos
        # UX-10 — the entity popover is modal-ish: a click outside it dismisses
        # the menu; a click on a row is handled by its registered zone below.
        if self.entity_popover is not None:
            rect = self.entity_popover.get("rect")
            if rect is not None:
                rx, ry, rw, rh = rect
                if not (rx <= mx < rx + rw and ry <= my < ry + rh):
                    self._close_entity_popover()
                    return
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
        if self.state == STATE_PLAY or self.state == STATE_ARENA_PLAY:
            # P29.60 — arena play przyjmuje tekst tak samo jak gra.
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
        # P29.76 — animacja reveala skrzynki: ujawniaj zawartość sekwencyjnie
        # (~200 ms/item), po pełnym ujawnieniu czeka na dismiss (done=True).
        _br = self._box_reveal
        if _br is not None and not _br.get("done"):
            _br["elapsed"] = _br.get("elapsed", 0.0) + dt
            total = len(_br.get("content_lines") or [])
            _br["shown"] = min(total, 1 + int(_br["elapsed"] // 200))
            if _br["elapsed"] >= 200 * (total + 1):
                _br["shown"] = total
                _br["done"] = True
        # P29.65 — wygaszanie efektów walki (pływające liczby / błysk / shake).
        _fx = getattr(self.world, "combat_fx", None) if self.world else None
        if isinstance(_fx, dict):
            _fl = _fx.get("floaters")
            if _fl:
                for _f in _fl:
                    _f["age"] = _f.get("age", 0.0) + dt
                _fx["floaters"] = [_f for _f in _fl
                                   if _f["age"] < _f.get("ttl", 950.0)]
            _fla = _fx.get("flash")
            if _fla:
                for _k in list(_fla.keys()):
                    _fla[_k] -= dt
                    if _fla[_k] <= 0:
                        del _fla[_k]
            if _fx.get("shake", 0.0) > 0:
                _fx["shake"] = max(0.0, _fx["shake"] - dt)
            # COMBAT-1 P1 — combat-start banner countdown.
            _ban = _fx.get("banner")
            if _ban:
                _ban["age"] = _ban.get("age", 0.0) + dt
                if _ban["age"] >= _ban.get("ttl", 1100.0):
                    _fx["banner"] = None
            # COMBAT-1 P2 — recoil kick decay (per anchor).
            _kick = _fx.get("kick")
            if _kick:
                for _k in list(_kick.keys()):
                    _kick[_k][1] -= dt
                    if _kick[_k][1] <= 0:
                        del _kick[_k]
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
        elif self.state == STATE_PAUSE:
            # Render the frozen game underneath, then overlay the menu.
            self._refresh_layout()
            L = self._layout
            try:
                ui.draw_topbar(s, self.world, layout=L)
                if L.has_left_sidebar:
                    ui.draw_left_sidebar(s, self.world, layout=L)
                ui.draw_room_panel(s, self.world, layout=L)
                ui.draw_sidebar(s, self.world, layout=L)
                ui.draw_log_and_input(s, self.world.log, self.input_text,
                                      self.blink, scroll=self.log_scroll,
                                      input_mode=self.input_mode, layout=L)
            except Exception:
                pass
            ui.draw_pause_menu(s, selected_idx=getattr(self, "pause_idx", 0),
                               click_registry=self.click_registry,
                               on_select=self._pause_action)
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
        elif self.state == STATE_ARENA_MENU:
            # P29.60 — variant picker
            from . import arena as _arena
            ui.draw_arena_menu(
                s, _arena.all_variants(),
                selected_idx=getattr(self, "arena_menu_idx", 0),
                click_registry=self.click_registry,
                on_select=self._arena_pick_variant,
                on_back=self._arena_back_to_title)
        elif self.state == STATE_ARENA_LOADOUT:
            # P29.60 — loadout picker (broń + klasa)
            variant_key = getattr(self, "_pending_arena_variant", "")
            from . import arena as _arena
            v = _arena.get_variant(variant_key)
            ui.draw_arena_loadout(
                s, v.label_pl if v else variant_key,
                step=getattr(self, "arena_loadout_step", "weapon"),
                weapons=ARENA_WEAPONS, classes=ARENA_CLASSES,
                weapon_idx=getattr(self, "arena_loadout_weapon_idx", 0),
                class_idx=getattr(self, "arena_loadout_class_idx", 0),
                click_registry=self.click_registry,
                on_pick=self._arena_loadout_pick,
                on_back=self._arena_back_to_menu)
        elif self.state == STATE_ARENA_PLAY:
            # P29.60 — reuse STATE_PLAY rendering (same room/log/UI)
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L,
                           click_registry=self.click_registry)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L,
                                     click_registry=self.click_registry,
                                     on_room_click=self._on_minimap_room_click)
            ui.draw_room_panel(s, self.world, layout=L,
                               click_registry=self.click_registry,
                               command_cb=self.submit_generated_command,
                               entity_action_cb=self.dispatch_entity_action,
                               entity_menu_cb=self.open_entity_popover)
            ui.draw_sidebar(s, self.world, layout=L,
                            click_registry=self.click_registry)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll,
                                  input_mode=self.input_mode, layout=L)
            _cs_arena = self._active_combat()
            if _cs_arena is not None:
                ui.draw_combat_bar(s, self.world, _cs_arena, layout=L,
                                   click_registry=self.click_registry,
                                   command_cb=self.submit_generated_command)
            else:
                self._ensure_nav_state()
                ui.draw_nav_panel(s, self.nav_state, self.input_mode, layout=L,
                                  armed=getattr(self, "_nav_selection_armed", False),
                                  click_registry=self.click_registry,
                                  on_option_click=self._on_nav_option_click)
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
                               click_registry=self.click_registry,
                               command_cb=self.submit_generated_command,
                               entity_action_cb=self.dispatch_entity_action,
                               entity_menu_cb=self.open_entity_popover)
            ui.draw_sidebar(s, self.world, layout=L,
                            click_registry=self.click_registry)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll,
                                  input_mode=self.input_mode, layout=L)
            _cs_play = self._active_combat()
            if _cs_play is not None:
                # COMBAT-1 P1 — combat replaces the exploration tabs with a
                # dedicated action bar (Atak/Unik/Obrona/Oceń/Uciekaj...).
                ui.draw_combat_bar(s, self.world, _cs_play, layout=L,
                                   click_registry=self.click_registry,
                                   command_cb=self.submit_generated_command)
            else:
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
        elif self.state == STATE_LEVELUP_ALLOC:
            self._refresh_layout()
            L = self._layout
            ui.draw_topbar(s, self.world, layout=L)
            if L.has_left_sidebar:
                ui.draw_left_sidebar(s, self.world, layout=L)
            ui.draw_room_panel(s, self.world, layout=L)
            ui.draw_sidebar(s, self.world, layout=L)
            ui.draw_log_and_input(s, self.world.log, self.input_text, self.blink,
                                  scroll=self.log_scroll, layout=L)
            self._draw_levelup_card()
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
            # Full-screen conversation (room backdrop + NPC portrait + clickable
            # / keyboard options). Replaces the old text-only overlay so the
            # mouse works and the NPC gets a face.
            from . import dialogue as _dlg
            node = _dlg.current_node(self.dialogue_state)
            npc = self.world.get(self.dialogue_state.npc_entity_id)
            room = (self.world.current_floor.current_room()
                    if self.world.current_floor else None)
            biome = getattr(self.world.current_floor, "biome_key", "") \
                if self.world.current_floor else ""
            option_rows = []
            speaker = ""
            body = "(rozmowa zakończona)"
            if node is not None:
                speaker = node.speaker
                body = node.text or ""
                avail = _dlg.available_options(
                    self.world, self.dialogue_state, node)
                for (_real, opt) in avail:
                    suffix = ""
                    if opt.skill_check is not None:
                        stat, dc = opt.skill_check
                        suffix = f"[{stat} vs TT {dc}]"
                    option_rows.append((opt.label, suffix))
            # Clamp the keyboard cursor to the available rows.
            n_opts = len(option_rows)
            if n_opts:
                self.dialogue_sel_idx = max(0, min(self.dialogue_sel_idx,
                                                   n_opts - 1))
            else:
                self.dialogue_sel_idx = 0
            ui.draw_dialogue_screen(
                s, self.world, npc, speaker=speaker, body=body,
                option_rows=option_rows, sel_idx=self.dialogue_sel_idx,
                biome=biome, room=room, layout=L,
                click_registry=self.click_registry,
                on_pick=self._pick_dialogue_option,
                on_close=self._close_dialogue)
        elif self.state == STATE_VICTORY:
            self._end_screen(t("victory_title", fallback="ZEJŚCIE ZALICZONE."), True)
        elif self.state == STATE_DEFEAT:
            self._end_screen(t("defeat_title", fallback="ZAWODNIK WYELIMINOWANY."), False)
        # UX-10 — contextual entity popover floats above the world panels.
        # Auto-dismiss if its entity vanished or the player left the room.
        if self.entity_popover is not None and self.state in (
                STATE_PLAY, STATE_ARENA_PLAY):
            eid = self.entity_popover.get("entity_id")
            ent = self.world.get(eid) if self.world else None
            room = (self.world.current_floor.current_room()
                    if (self.world and self.world.current_floor) else None)
            if ent is None or room is None or ent not in room.entities:
                self.entity_popover = None
            else:
                try:
                    ui.draw_entity_popover(
                        s, self.entity_popover, layout=self._layout,
                        click_registry=self.click_registry,
                        on_select=self._entity_popover_activate)
                except Exception:
                    self.entity_popover = None
        elif self.entity_popover is not None:
            # Not in a play state any more — drop it.
            self.entity_popover = None
        # P29.76 / Feature#2 — reveal skrzynki (hybryda VS) rysowany NA WIERZCHU
        # każdego stanu, tuż przed flip.
        if self._box_reveal is not None:
            try:
                ui.draw_box_reveal(s, self._box_reveal)
            except Exception:
                self._box_reveal = None
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



def _roll_dice_spec(spec: str, rng) -> int:
    """Prompt 23 / P29.65: roll '1d6+2' / '2d4' / '3'. Cienki wrapper na
    współdzielony `engine.dice.roll_spec` (jedno źródło z mobami; obsługuje
    `NdS+B`, `NdS-B`, gołą liczbę). Woła go ścieżka obrażeń gracza."""
    from .dice import roll_spec
    return roll_spec(spec, rng)


