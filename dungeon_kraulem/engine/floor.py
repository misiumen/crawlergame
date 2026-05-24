"""Floor model — a persistent dungeon level with its own clock."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .room import RoomState
from ..config import MINUTES_PER_DAY, FLOOR1_DEADLINE_DAYS


@dataclass
class FloorState:
    floor_id: str = "floor_1"
    floor_number: int = 1
    theme_key: str = ""
    theme_fallback: str = ""
    title_key: str = ""
    title_fallback: str = ""
    sponsor_key: str = ""
    sponsor_fallback: str = ""

    current_minute: int = 0
    deadline_minute: int = MINUTES_PER_DAY * FLOOR1_DEADLINE_DAYS

    rooms: Dict[str, RoomState] = field(default_factory=dict)
    current_room_id: str = ""
    start_room_id: str = ""
    exit_room_ids: List[str] = field(default_factory=list)

    discovered_room_ids: Set[str] = field(default_factory=set)
    known_room_ids: Set[str] = field(default_factory=set)   # hinted/scouted/visited

    floor_alert_level: int = 0                              # 0-10
    audience_rating: int = 0
    crawler_population: int = 0
    rumors: List[str] = field(default_factory=list)         # i18n keys for known rumors

    # Exit conditions can be any of: defeat_boss, find_key, bribe_warden, etc.
    exit_conditions: List[str] = field(default_factory=list)
    exits_unlocked: Set[str] = field(default_factory=set)

    # Floor objective (Prompt 1 — pulled from floor_objective_templates)
    objective_key: str = ""
    objective_title_fallback: str = ""
    objective_description_fallback: str = ""
    objective_solution_paths: List[str] = field(default_factory=list)

    # Each entry: {"minute": int, "kind": str, "args": {...}}
    active_events: List[Dict] = field(default_factory=list)

    # Prompt 07: belief seeds active on this floor (subset of world.belief_seeds).
    active_belief_seed_ids: List[str] = field(default_factory=list)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def current_room(self) -> Optional[RoomState]:
        return self.rooms.get(self.current_room_id)

    def add_room(self, room: RoomState):
        self.rooms[room.room_id] = room

    def link(self, from_id: str, exit_label: str, to_id: str,
             locked: bool = False, hidden: bool = False,
             hint_key: str = "", fallback_hint: str = "",
             bidirectional: bool = True, back_label: Optional[str] = None):
        """Create an exit between two rooms."""
        a = self.rooms.get(from_id); b = self.rooms.get(to_id)
        if not a or not b:
            raise KeyError(f"link: missing room {from_id} or {to_id}")
        a.exits[exit_label] = {
            "target": to_id, "locked": locked, "hidden": hidden,
            "hint_key": hint_key, "fallback_hint": fallback_hint,
        }
        if bidirectional:
            back = back_label or exit_label
            # Don't overwrite a manually-set back link
            if back not in b.exits:
                b.exits[back] = {
                    "target": from_id, "locked": locked, "hidden": hidden,
                    "hint_key": "", "fallback_hint": "",
                }

    def deadline_remaining_minutes(self) -> int:
        return max(0, self.deadline_minute - self.current_minute)

    def time_of_day_label(self) -> str:
        """Returns 'morning'|'day'|'evening'|'night' from current_minute."""
        h = (self.current_minute // 60) % 24
        if 5 <= h < 11:   return "morning"
        if 11 <= h < 17:  return "day"
        if 17 <= h < 22:  return "evening"
        return "night"

    def day_number(self) -> int:
        return self.current_minute // MINUTES_PER_DAY + 1

    def to_dict(self):
        return {
            "floor_id": self.floor_id, "floor_number": self.floor_number,
            "theme_key": self.theme_key, "theme_fallback": self.theme_fallback,
            "title_key": self.title_key, "title_fallback": self.title_fallback,
            "sponsor_key": self.sponsor_key, "sponsor_fallback": self.sponsor_fallback,
            "current_minute": self.current_minute, "deadline_minute": self.deadline_minute,
            "rooms": {rid: r.to_dict() for rid, r in self.rooms.items()},
            "current_room_id": self.current_room_id,
            "start_room_id": self.start_room_id,
            "exit_room_ids": list(self.exit_room_ids),
            "discovered_room_ids": list(self.discovered_room_ids),
            "known_room_ids": list(self.known_room_ids),
            "floor_alert_level": self.floor_alert_level,
            "audience_rating": self.audience_rating,
            "crawler_population": self.crawler_population,
            "rumors": list(self.rumors),
            "exit_conditions": list(self.exit_conditions),
            "exits_unlocked": list(self.exits_unlocked),
            "active_events": list(self.active_events),
            "objective_key": self.objective_key,
            "objective_title_fallback": self.objective_title_fallback,
            "objective_description_fallback": self.objective_description_fallback,
            "objective_solution_paths": list(self.objective_solution_paths),
            "active_belief_seed_ids": list(self.active_belief_seed_ids),
        }

    @classmethod
    def from_dict(cls, d):
        f = cls(floor_id=d.get("floor_id", "floor_1"))
        for k in ("floor_number","theme_key","theme_fallback","title_key","title_fallback",
                 "sponsor_key","sponsor_fallback","current_minute","deadline_minute",
                 "current_room_id","start_room_id","floor_alert_level",
                 "audience_rating","crawler_population"):
            setattr(f, k, d.get(k, getattr(f, k)))
        f.rooms = {rid: RoomState.from_dict(rd) for rid, rd in d.get("rooms", {}).items()}
        f.exit_room_ids = list(d.get("exit_room_ids", []))
        f.discovered_room_ids = set(d.get("discovered_room_ids", []))
        f.known_room_ids = set(d.get("known_room_ids", []))
        f.rumors = list(d.get("rumors", []))
        f.exit_conditions = list(d.get("exit_conditions", []))
        f.exits_unlocked = set(d.get("exits_unlocked", []))
        f.active_events = list(d.get("active_events", []))
        f.objective_key = d.get("objective_key", "")
        f.objective_title_fallback = d.get("objective_title_fallback", "")
        f.objective_description_fallback = d.get("objective_description_fallback", "")
        f.objective_solution_paths = list(d.get("objective_solution_paths", []))
        f.active_belief_seed_ids = list(d.get("active_belief_seed_ids", []))
        return f
