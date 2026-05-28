"""Headless Game driver — Rule 12d core.

Pozwala E2E testom symulować flow gracza:
1. Tworzy `Game(screen=None)` instance bez pygame display
2. Buduje minimalny WorldState + Character + FloorState
3. Eksponuje `send(command)` → dispatches parsed input
4. Eksponuje `log_lines()` / `log_since(idx)` do inspection
5. Eksponuje `spawn_in_current_room(entity)` do controlled scenarios

Każdy test który chce sprawdzić USER-FACING behavior (a nie tylko
mechanikę modułu) idzie przez ten driver.

Limity:
* Brak renderingu pygame — bleed tekstu / visual bugs wymagają osobnej
  ścieżki (Surface snapshot, follow-up).
* Brak input keyboard symulacji niskopoziomowej — operuje na level
  parsed command strings, jak gdyby gracz wpisał i nacisnął Enter.
"""
from __future__ import annotations
import os
from typing import List, Optional, Tuple

# Headless pygame (bez wymagania monitora) — w razie potrzeby init.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine.game import Game, STATE_PLAY, STATE_DIALOG
from ...engine.world import WorldState
from ...engine.character import Character
from ...engine.floor import FloorState
from ...engine.room import RoomState
from ...engine.entity import Entity


class HeadlessSession:
    """Single-player E2E driver. Każdy test tworzy nową sesję.

    Typical use:
        sess = HeadlessSession(background="janitor")
        sess.put_in_room(some_entity)
        sess.send("pogadaj z X")
        assert sess.state == "dialog"
        assert "drzewko" in sess.last_log_text()
    """

    def __init__(self, *, character_name: str = "Tester",
                 background: str = "janitor",
                 floor_number: int = 1):
        """Build minimalny world + game w STATE_PLAY.

        Args:
            character_name: imię gracza
            background: pochodzenie (wpływa na stats)
            floor_number: na którym piętrze startujemy (1-18)
        """
        # World + character
        self.world = WorldState()
        self.world.character = Character(
            name=character_name, background=background)

        # Minimalne piętro — 2 pokoje: start + boczny (na potrzeby
        # exit checks gdyby były). Dostatecznie żeby Game.handle_play
        # nie crashował.
        floor = FloorState(floor_id=f"e2e_f{floor_number}",
                            floor_number=floor_number)
        start = RoomState(room_id="r_start", actual_type="combat")
        side = RoomState(room_id="r_side", actual_type="combat")
        floor.rooms["r_start"] = start
        floor.rooms["r_side"] = side
        floor.start_room_id = "r_start"
        floor.current_room_id = "r_start"
        floor.exit_room_ids = ["r_side"]
        self.world.current_floor = floor

        # Game w STATE_PLAY (skip title/character creation)
        self.game = Game(screen=None)
        self.game.world = self.world
        self.game.state = STATE_PLAY

        # Stable RNG seed dla deterministycznych testów
        import random
        self._rng = random.Random(0)
        random.seed(0)

    # ── State accessors ──────────────────────────────────────────────

    @property
    def state(self) -> str:
        """Game state: 'play' / 'dialog' / 'victory' / ..."""
        return self.game.state

    @property
    def dialogue_state(self):
        """Open dialog state (DialogueState | None)."""
        return self.game.dialogue_state

    @property
    def character(self) -> Character:
        return self.world.character

    @property
    def current_room(self) -> RoomState:
        return self.world.current_floor.current_room()

    # ── Input ────────────────────────────────────────────────────────

    def send(self, command: str) -> List[Tuple[str, str]]:
        """Symuluje wpisanie komendy + Enter w grze.

        Zwraca log lines DODANE w czasie dispatch (lista
        (text, category) tuples). Pre-existing log nie wraca.
        """
        pre_len = len(self.world.log)
        self.game.input_text = command
        self.game.submit_input()
        return list(self.world.log[pre_len:])

    # ── Log inspection ───────────────────────────────────────────────

    def log_lines(self) -> List[str]:
        """Pełen log z gry (text only, bez categories)."""
        return [t for t, _ in self.world.log]

    def log_with_cats(self) -> List[Tuple[str, str]]:
        """Pełen log z categories."""
        return list(self.world.log)

    def last_log_text(self, joined: str = "\n") -> str:
        """Last N log lines as joined string (cała historia)."""
        return joined.join(self.log_lines())

    def log_contains(self, substring: str) -> bool:
        """True jeśli jakakolwiek linia loga zawiera substring."""
        return any(substring in t for t in self.log_lines())

    def log_contains_any(self, *substrings: str) -> bool:
        """True jeśli choć jeden substring obecny."""
        return any(self.log_contains(s) for s in substrings)

    # ── Entity placement ─────────────────────────────────────────────

    def put_in_room(self, entity: Entity,
                    room: Optional[RoomState] = None) -> Entity:
        """Dorzuca entity do current room (albo wskazanego)."""
        if room is None:
            room = self.current_room
        entity.location_id = room.room_id
        room.entities.append(entity)
        self.world.register(entity)
        return entity

    def spawn_from_mon(self, mon_key: str,
                       room: Optional[RoomState] = None) -> Entity:
        """Tworzy entity z MON catalog template (np. 'kapitan_druzyny',
        'intake_warden') i wstawia do pokoju."""
        from ...content.data.entity_templates import MON
        from ...engine.entity import Entity as E, T_MONSTER
        proto = MON[mon_key]
        ent = E(
            key=mon_key, entity_type=T_MONSTER,
            name_key=proto.get("name_key", ""),
            fallback_name=proto.get("fallback_name", mon_key),
            desc_key=proto.get("desc_key", ""),
            fallback_desc=proto.get("fallback_desc", ""),
            tags=list(proto.get("tags", [])),
            affordances=list(proto.get("affordances",
                                       ["inspect", "attack"])),
            hp=proto.get("hp", 1), max_hp=proto.get("max_hp", 1),
            ac=proto.get("ac", 10),
            attack_bonus=proto.get("attack_bonus", 0),
            damage_dice=proto.get("damage_dice", "1d4"),
        )
        return self.put_in_room(ent, room)


# ── Polish-only audit helper ────────────────────────────────────────


_BLACKLIST_PATTERNS = (
    " the ", " your ", " with ", " and ", " you ", " for ",
    "showrunner", "vending", "loker",
    # Calque patterns (Reguła 8):
    ", którego nigdzie nie ma",
    "Pytanie tylko",
    # Raw item keys (display layer leak):
    "snack bar", "dead phone", "credits pile",
    "broken camera lens",
)


def assert_polish_only(text: str, *, allowlist: Tuple[str, ...] = ()) -> None:
    """Assert że text NIE zawiera typowych English / calque patterns.
    Allowlist do pomijania konkretnych dopuszczonych terminów."""
    low = text.lower()
    for bad in _BLACKLIST_PATTERNS:
        if bad in allowlist:
            continue
        assert bad.lower() not in low, (
            f"Polish-only leak: znaleziono {bad!r} w tekście:\n{text!r}")
