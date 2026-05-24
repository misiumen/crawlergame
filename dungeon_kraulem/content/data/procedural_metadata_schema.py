"""Procedural content metadata schema notes.

This file is intentionally lightweight. It is a reference/helper module for Claude
or future generation code. It should not break runtime imports if unused.

The goal is to standardize procedural template metadata across:
- room templates
- encounter templates
- NPC/crawler templates
- rumor templates
- safehouse templates
- item templates
- floor objective templates
"""

from dataclasses import dataclass, field
from typing import Any


RARITIES = {"common", "uncommon", "rare", "setpiece", "unique"}


@dataclass
class TemplateMeta:
    key: str
    floor_min: int = 1
    floor_max: int = 18
    tags: list[str] = field(default_factory=list)
    weight: float = 1.0
    rarity: str = "common"
    required_room_tags: list[str] = field(default_factory=list)
    incompatible_tags: list[str] = field(default_factory=list)
    possible_clues: list[str] = field(default_factory=list)
    possible_rewards: list[str] = field(default_factory=list)
    possible_risks: list[str] = field(default_factory=list)
    possible_resolution_methods: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.key:
            errors.append("missing key")
        if self.floor_min < 1:
            errors.append("floor_min must be >= 1")
        if self.floor_max < self.floor_min:
            errors.append("floor_max must be >= floor_min")
        if self.weight <= 0:
            errors.append("weight must be positive")
        if self.rarity not in RARITIES:
            errors.append(f"unknown rarity: {self.rarity}")
        return errors


def metadata_from_dict(data: dict[str, Any]) -> TemplateMeta:
    return TemplateMeta(
        key=str(data.get("key", "")),
        floor_min=int(data.get("floor_min", 1)),
        floor_max=int(data.get("floor_max", 18)),
        tags=list(data.get("tags", [])),
        weight=float(data.get("weight", 1.0)),
        rarity=str(data.get("rarity", "common")),
        required_room_tags=list(data.get("required_room_tags", [])),
        incompatible_tags=list(data.get("incompatible_tags", [])),
        possible_clues=list(data.get("possible_clues", [])),
        possible_rewards=list(data.get("possible_rewards", [])),
        possible_risks=list(data.get("possible_risks", [])),
        possible_resolution_methods=list(data.get("possible_resolution_methods", [])),
    )


def validate_template_pool(pool: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    keys: set[str] = set()
    for idx, item in enumerate(pool):
        meta_data = item.get("metadata", item)
        meta = metadata_from_dict(meta_data)
        for error in meta.validate():
            errors.append(f"template[{idx}] {meta.key or '<missing>'}: {error}")
        if meta.key in keys:
            errors.append(f"duplicate template key: {meta.key}")
        keys.add(meta.key)
    return errors
