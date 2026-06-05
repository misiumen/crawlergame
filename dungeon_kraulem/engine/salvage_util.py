"""Salvage tag->table lookup — neutral helper extracted from game.py
(Phase 0.5). Shared by action_handlers (moved _attempt_*) and game.py's
kept _do_single_salvage, so it lives in its own module both import.
"""
from __future__ import annotations


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
