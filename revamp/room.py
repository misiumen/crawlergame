"""Room model — persistent, partially-revealed locations."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .entity import Entity


# Map-state constants
S_UNKNOWN   = "unknown"      # never heard of
S_HINTED    = "hinted"       # known to exist; some surface info
S_SCOUTED   = "scouted"      # listened-at / peeked
S_VISITED   = "visited"      # been there at least once
S_SEARCHED  = "searched"     # searched thoroughly
S_CLEARED   = "cleared"      # threats neutralized
S_DANGEROUS = "dangerous"    # threats remain
S_SAFE      = "safe"         # safehouse
S_LOCKED    = "locked"
S_SECRET    = "secret"
S_RUMORED   = "rumored"


@dataclass
class RoomState:
    room_id: str
    short_title_key: str = ""
    fallback_short_title: str = ""
    title_key: str = ""                       # title shown after discovery
    fallback_title: str = ""
    first_enter_key: str = ""                 # i18n key for first-enter narration
    fallback_first_enter: str = ""
    look_key: str = ""                        # repeat-look narration
    fallback_look: str = ""
    search_key: str = ""                      # what searching turns up (flavor)
    fallback_search: str = ""
    public_hint_key: str = ""                 # one-line teaser visible from adjacent room
    fallback_public_hint: str = ""

    # Connections: exit_label -> {target_room_id, locked, hidden, hint_key, ...}
    exits: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Sensory tags used by procgen and narrator (light, smell, sound, temperature)
    sensory_tags: List[str] = field(default_factory=list)

    actual_type: str = "unknown"              # combat/safehouse/lore/etc — never shown directly
    visible_state: str = S_UNKNOWN            # what map UI shows

    # Persistent payload
    entities: List[Entity] = field(default_factory=list)
    fragments: List[str] = field(default_factory=list)   # discoverable lore i18n keys

    # Bookkeeping
    visited: bool = False
    scouted: bool = False
    searched_depth: int = 0
    cleared: bool = False
    locked: bool = False
    secret: bool = False
    safehouse_subtype: Optional[str] = None
    last_visited_minute: int = -1
    noise_level: int = 0                       # rises with combat; bleeds across rooms
    light_level: str = "dim"                   # "bright" | "dim" | "dark"

    def is_safe(self) -> bool:
        return self.safehouse_subtype is not None or self.actual_type == "safehouse"

    def add_entity(self, ent: Entity):
        ent.location_id = self.room_id
        self.entities.append(ent)

    def remove_entity(self, ent: Entity):
        if ent in self.entities:
            self.entities.remove(ent)

    def visible_entities(self) -> List[Entity]:
        return [e for e in self.entities if e.visible and e.discovered]

    def find_entity(self, predicate) -> Optional[Entity]:
        for e in self.entities:
            if predicate(e):
                return e
        return None

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "short_title_key": self.short_title_key, "fallback_short_title": self.fallback_short_title,
            "title_key": self.title_key, "fallback_title": self.fallback_title,
            "first_enter_key": self.first_enter_key, "fallback_first_enter": self.fallback_first_enter,
            "look_key": self.look_key, "fallback_look": self.fallback_look,
            "search_key": self.search_key, "fallback_search": self.fallback_search,
            "public_hint_key": self.public_hint_key, "fallback_public_hint": self.fallback_public_hint,
            "exits": {k: dict(v) for k, v in self.exits.items()},
            "sensory_tags": list(self.sensory_tags),
            "actual_type": self.actual_type,
            "visible_state": self.visible_state,
            "entities": [e.to_dict() for e in self.entities],
            "fragments": list(self.fragments),
            "visited": self.visited,
            "scouted": self.scouted,
            "searched_depth": self.searched_depth,
            "cleared": self.cleared,
            "locked": self.locked,
            "secret": self.secret,
            "safehouse_subtype": self.safehouse_subtype,
            "last_visited_minute": self.last_visited_minute,
            "noise_level": self.noise_level,
            "light_level": self.light_level,
        }

    @classmethod
    def from_dict(cls, d):
        r = cls(room_id=d["room_id"])
        for k in ("short_title_key","fallback_short_title","title_key","fallback_title",
                 "first_enter_key","fallback_first_enter","look_key","fallback_look",
                 "search_key","fallback_search","public_hint_key","fallback_public_hint",
                 "actual_type","visible_state","safehouse_subtype","light_level"):
            setattr(r, k, d.get(k, getattr(r, k)))
        r.exits = {k: dict(v) for k, v in d.get("exits", {}).items()}
        r.sensory_tags = list(d.get("sensory_tags", []))
        r.entities = [Entity.from_dict(e) for e in d.get("entities", [])]
        r.fragments = list(d.get("fragments", []))
        r.visited = d.get("visited", False)
        r.scouted = d.get("scouted", False)
        r.searched_depth = d.get("searched_depth", 0)
        r.cleared = d.get("cleared", False)
        r.locked = d.get("locked", False)
        r.secret = d.get("secret", False)
        r.last_visited_minute = d.get("last_visited_minute", -1)
        r.noise_level = d.get("noise_level", 0)
        return r

    # ── Display ──────────────────────────────────────────────────────────────
    def display_short_title(self):
        from .lang import t
        return t(self.short_title_key, fallback=self.fallback_short_title or self.room_id)

    def display_title(self):
        from .lang import t
        return t(self.title_key, fallback=self.fallback_title or self.display_short_title())

    def display_public_hint(self):
        from .lang import t
        return t(self.public_hint_key, fallback=self.fallback_public_hint or "")

    def display_first_enter(self):
        from .lang import t
        return t(self.first_enter_key, fallback=self.fallback_first_enter or self.display_title())

    def display_look(self):
        from .lang import t
        return t(self.look_key, fallback=self.fallback_look or self.display_first_enter())

    def display_search(self):
        from .lang import t
        return t(self.search_key, fallback=self.fallback_search or "")
