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

    # Prompt 07: persistent memetic / belief seeds the player has planted.
    # Keyed by seed_id. Old saves without this field load as {} via from_dict.
    belief_seeds: Dict[str, Any] = field(default_factory=dict)

    # Prompt 07b: structured knowledge stores. Each entry is a plain dict so
    # the save/load layer needs no special handling. Old saves load as empty.
    known_clues: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    known_facts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    known_routes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    known_passwords: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unlocked_paths: List[str] = field(default_factory=list)

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
        # Belief seeds: each is a BeliefSeed dataclass; serialize via its
        # to_dict if present, otherwise pass through (e.g. plain dicts that
        # may have crept in via mods/tests).
        bs_out = {}
        for sid, seed in (self.belief_seeds or {}).items():
            if hasattr(seed, "to_dict"):
                bs_out[sid] = seed.to_dict()
            elif isinstance(seed, dict):
                bs_out[sid] = dict(seed)
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
            "belief_seeds": bs_out,
            # Prompt 07b — knowledge stores (already plain dicts/lists).
            "known_clues": dict(self.known_clues or {}),
            "known_facts": dict(self.known_facts or {}),
            "known_routes": dict(self.known_routes or {}),
            "known_passwords": dict(self.known_passwords or {}),
            "unlocked_paths": list(self.unlocked_paths or []),
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
        # Restore belief_seeds — tolerate missing field on old saves.
        from .memetics import BeliefSeed as _BS
        w.belief_seeds = {
            sid: _BS.from_dict(sd) for sid, sd in (d.get("belief_seeds") or {}).items()
        }
        # Prompt 07b — knowledge stores. All dicts/lists default empty.
        w.known_clues     = dict(d.get("known_clues") or {})
        w.known_facts     = dict(d.get("known_facts") or {})
        w.known_routes    = dict(d.get("known_routes") or {})
        w.known_passwords = dict(d.get("known_passwords") or {})
        w.unlocked_paths  = list(d.get("unlocked_paths") or [])
        # Old saves predate these stores; bootstrap will fill defaults too.
        from . import knowledge as _kn
        _kn.bootstrap(w)
        return w
