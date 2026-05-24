"""WorldState — top-level container threaded through the engine."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .character import Character
from .floor import FloorState
from .entity import Entity


@dataclass
class WorldState:
    character: Character = field(default_factory=Character)
    current_floor: Optional[FloorState] = None
    floor_number: int = 1

    # Global pool of entities by id (so inventory items don't have to nest)
    entities: Dict[int, Entity] = field(default_factory=dict)

    # Game log: list of (text, category)
    log: List = field(default_factory=list)

    # Crawlers known to the player by id (persists across floors)
    known_crawlers: List[str] = field(default_factory=list)

    settings: Dict[str, Any] = field(default_factory=dict)
    random_seed: Optional[int] = None

    # ── Entity registry ──────────────────────────────────────────────────────

    def register(self, ent: Entity) -> Entity:
        self.entities[ent.entity_id] = ent
        return ent

    def get(self, eid: int) -> Optional[Entity]:
        return self.entities.get(eid)

    # ── Logging helpers ──────────────────────────────────────────────────────

    def log_msg(self, text: str, category: str = "normal"):
        self.log.append((text, category))
        if len(self.log) > 800:
            self.log = self.log[-600:]

    # ── Save / load ──────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "version": 1,
            "character": self.character.to_dict(),
            "current_floor": self.current_floor.to_dict() if self.current_floor else None,
            "floor_number": self.floor_number,
            "entities": {str(k): v.to_dict() for k, v in self.entities.items()},
            "log": [(t, c) for t, c in self.log[-200:]],   # cap saved log
            "known_crawlers": list(self.known_crawlers),
            "settings": dict(self.settings),
            "random_seed": self.random_seed,
        }

    @classmethod
    def from_dict(cls, d):
        w = cls()
        w.character = Character.from_dict(d.get("character", {}))
        cf = d.get("current_floor")
        w.current_floor = FloorState.from_dict(cf) if cf else None
        w.floor_number = d.get("floor_number", 1)
        w.entities = {int(k): Entity.from_dict(v) for k, v in d.get("entities", {}).items()}
        w.log = [tuple(x) for x in d.get("log", [])]
        w.known_crawlers = list(d.get("known_crawlers", []))
        w.settings = dict(d.get("settings", {}))
        w.random_seed = d.get("random_seed")
        return w
