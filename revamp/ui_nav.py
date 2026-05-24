"""Keyboard cursor / option-group navigation for the revamp UI (Prompt 08).

Design rule: every selectable option just builds a TEXT COMMAND that runs
through the same parser pipeline as direct typing. The nav layer never
bypasses parser → validator → resolution → consequences.

Public API:
    SelectableOption                              — one selectable row
    UISelectionState                              — current selection state
    build_play_options(world, character) -> dict  — contextual option groups
    move_selection(state, dx, dy)                 — arrow keys
    cycle_group(state, step)                      — Tab / Shift+Tab
    current_option(state) -> SelectableOption|None
    group_label(group_key) -> str                 — localized header
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lang import t


# Group keys are stable ASCII identifiers; localization happens in
# `group_label` only.
GROUP_ACTIONS   = "actions"
GROUP_EXITS     = "exits"
GROUP_OBJECTS   = "objects"
GROUP_ENTITIES  = "entities"
GROUP_INVENTORY = "inventory"
GROUP_CRAFTING  = "crafting"

ALL_GROUPS = (GROUP_ACTIONS, GROUP_EXITS, GROUP_OBJECTS, GROUP_ENTITIES,
              GROUP_INVENTORY, GROUP_CRAFTING)


@dataclass
class SelectableOption:
    option_id: str = ""
    label: str = ""
    command: str = ""
    group: str = GROUP_ACTIONS
    enabled: bool = True
    tooltip: str = ""
    hotkey: str = ""
    target_id: Optional[int] = None
    action_type: str = ""


@dataclass
class UISelectionState:
    groups: List[str] = field(default_factory=list)
    current_group_index: int = 0
    selected_index_by_group: Dict[str, int] = field(default_factory=dict)
    options_by_group: Dict[str, List[SelectableOption]] = field(default_factory=dict)

    def current_group(self) -> str:
        if not self.groups:
            return ""
        return self.groups[self.current_group_index % len(self.groups)]

    def options_in(self, group: str) -> List[SelectableOption]:
        return self.options_by_group.get(group, [])

    def selected_index(self, group: Optional[str] = None) -> int:
        group = group or self.current_group()
        return self.selected_index_by_group.get(group, 0)

    def set_selected_index(self, idx: int, group: Optional[str] = None) -> None:
        group = group or self.current_group()
        opts = self.options_in(group)
        if not opts:
            return
        self.selected_index_by_group[group] = max(0, min(idx, len(opts) - 1))


# ── Localized headers ──────────────────────────────────────────────────────

_GROUP_LABEL_KEYS = {
    GROUP_ACTIONS:   ("ui_group_actions",   "Akcje"),
    GROUP_EXITS:     ("ui_group_exits",     "Wyjścia"),
    GROUP_OBJECTS:   ("ui_group_objects",   "Obiekty"),
    GROUP_ENTITIES:  ("ui_group_entities",  "Postacie"),
    GROUP_INVENTORY: ("ui_group_inventory", "Ekwipunek"),
    GROUP_CRAFTING:  ("ui_group_crafting",  "Crafting"),
}


def group_label(group_key: str) -> str:
    key, fb = _GROUP_LABEL_KEYS.get(group_key, ("", group_key))
    return t(key, fallback=fb)


# ── Builder ─────────────────────────────────────────────────────────────────

def build_play_options(world) -> UISelectionState:
    """Build a `UISelectionState` from world snapshot. Only includes
    visible/known things — never reveals hidden objects, hidden exits, or
    unidentified items."""
    state = UISelectionState()
    if world is None or world.current_floor is None:
        state.groups = [GROUP_ACTIONS]
        state.options_by_group[GROUP_ACTIONS] = _basic_actions(world)
        return state
    room = world.current_floor.current_room()
    if room is None:
        state.groups = [GROUP_ACTIONS]
        state.options_by_group[GROUP_ACTIONS] = _basic_actions(world)
        return state

    actions   = _basic_actions(world, room=room)
    exits     = _exit_options(world, room)
    objects   = _object_options(world, room)
    entities  = _entity_options(world, room)
    inv       = _inventory_options(world)
    crafting  = _crafting_options(world)

    layout = []
    for gk, opts in (
        (GROUP_ACTIONS,   actions),
        (GROUP_EXITS,     exits),
        (GROUP_OBJECTS,   objects),
        (GROUP_ENTITIES,  entities),
        (GROUP_INVENTORY, inv),
        (GROUP_CRAFTING,  crafting),
    ):
        if opts:
            layout.append(gk)
            state.options_by_group[gk] = opts
    state.groups = layout
    # Default to Actions if present.
    if GROUP_ACTIONS in layout:
        state.current_group_index = layout.index(GROUP_ACTIONS)
    return state


# ── Group builders ─────────────────────────────────────────────────────────

def _basic_actions(world, room=None) -> List[SelectableOption]:
    out = [
        SelectableOption("act_look",   t("nav_look",   fallback="Rozejrzyj się"),
                         "rozejrzyj się", GROUP_ACTIONS),
        SelectableOption("act_search", t("nav_search", fallback="Przeszukaj pokój"),
                         "przeszukaj pokój", GROUP_ACTIONS),
        SelectableOption("act_listen", t("nav_listen", fallback="Nasłuchuj"),
                         "nasłuchuj", GROUP_ACTIONS),
        SelectableOption("act_wait",   t("nav_wait",   fallback="Czekaj"),
                         "czekaj", GROUP_ACTIONS),
    ]
    # Rest only in safe rooms (allows it always at low cost — engine validates).
    if room and (room.is_safe() if hasattr(room, "is_safe") else False):
        out.append(SelectableOption("act_rest",
                                    t("nav_rest", fallback="Odpocznij"),
                                    "odpocznij", GROUP_ACTIONS,
                                    hotkey="r"))
    # Always-available info panels — short row.
    out.extend([
        SelectableOption("act_inventory",
                         t("nav_inventory", fallback="Ekwipunek"),
                         "plecak", GROUP_ACTIONS, hotkey="i"),
        SelectableOption("act_character",
                         t("nav_character", fallback="Postać"),
                         "postać", GROUP_ACTIONS, hotkey="c"),
        SelectableOption("act_map",
                         t("nav_map", fallback="Mapa"),
                         "mapa", GROUP_ACTIONS, hotkey="m"),
        SelectableOption("act_knowledge",
                         t("nav_knowledge", fallback="Wiedza"),
                         "wiedza", GROUP_ACTIONS, hotkey="j"),
        SelectableOption("act_save",
                         t("nav_save", fallback="Zapisz"),
                         "zapisz", GROUP_ACTIONS),
    ])
    return out


def _exit_options(world, room) -> List[SelectableOption]:
    out = []
    floor = world.current_floor
    for label, ed in (room.exits or {}).items():
        if ed.get("hidden"):
            continue
        target_id = ed.get("target", "")
        target_room = floor.rooms.get(target_id) if floor else None
        target_name = (target_room.display_short_title()
                       if target_room and target_id in (floor.discovered_room_ids or set())
                       else "?")
        locked = " (zamkn.)" if ed.get("locked") else ""
        out.append(SelectableOption(
            option_id=f"exit_{target_id or label}",
            label=f"Idź: {label}{locked}  →  {target_name}",
            command=f"idź {label}",
            group=GROUP_EXITS,
            enabled=not ed.get("locked"),
            target_id=None,
            action_type="move",
        ))
    return out


def _object_options(world, room) -> List[SelectableOption]:
    out = []
    for e in room.visible_entities():
        if e.entity_type in ("monster", "crawler", "npc"):
            continue
        name = e.display_name()
        tags = e.tags or []
        affs = e.affordances or []
        # Inspect is universally cheap; always offer it.
        out.append(SelectableOption(
            option_id=f"inspect_{e.entity_id}",
            label=f"Sprawdź: {name}",
            command=f"sprawdź {name}",
            group=GROUP_OBJECTS, target_id=e.entity_id,
            action_type="inspect",
        ))
        # Loot if portable or container.
        if e.portable or "container" in tags or "corpse" in tags or e.entity_type == "corpse":
            out.append(SelectableOption(
                option_id=f"loot_{e.entity_id}",
                label=f"Przeszukaj: {name}",
                command=f"przeszukaj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="loot",
            ))
        # Salvage if tagged or affordance lists it.
        if "salvageable" in tags or "salvage" in affs:
            out.append(SelectableOption(
                option_id=f"salvage_{e.entity_id}",
                label=f"Zdemontuj: {name}",
                command=f"zdemontuj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="salvage",
            ))
        # Use / open / hack pass-throughs when affordance is declared.
        if "use" in affs:
            out.append(SelectableOption(
                option_id=f"use_{e.entity_id}",
                label=f"Użyj: {name}",
                command=f"użyj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="use",
            ))
        if "hack" in affs:
            out.append(SelectableOption(
                option_id=f"hack_{e.entity_id}",
                label=f"Zhakuj: {name}",
                command=f"zhakuj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="hack",
            ))
    return out


def _entity_options(world, room) -> List[SelectableOption]:
    out = []
    for e in room.visible_entities():
        if e.entity_type not in ("monster", "crawler", "npc"):
            continue
        if not e.is_alive():
            continue
        name = e.display_name()
        affs = e.affordances or []
        # Talk path — always for crawler/npc, only if affordance for monster.
        if e.entity_type in ("crawler", "npc") or "talk" in affs:
            out.append(SelectableOption(
                option_id=f"talk_{e.entity_id}",
                label=f"Pogadaj: {name}",
                command=f"pogadaj z {name}",
                group=GROUP_ENTITIES, target_id=e.entity_id,
                action_type="talk",
            ))
        if "intimidate" in affs:
            out.append(SelectableOption(
                option_id=f"intimidate_{e.entity_id}",
                label=f"Zastrasz: {name}",
                command=f"zastrasz {name}",
                group=GROUP_ENTITIES, target_id=e.entity_id,
                action_type="intimidate",
            ))
        # Combat path — always available if alive and hostile-ish.
        if "attack" in affs or e.entity_type == "monster":
            out.append(SelectableOption(
                option_id=f"attack_{e.entity_id}",
                label=f"Zaatakuj: {name}",
                command=f"zaatakuj {name}",
                group=GROUP_ENTITIES, target_id=e.entity_id,
                action_type="attack",
            ))
    return out


def _inventory_options(world) -> List[SelectableOption]:
    out = []
    ch = world.character
    for eid in (ch.inventory_ids or [])[:12]:   # cap visible to 12
        ent = world.entities.get(eid)
        if ent is None: continue
        name = ent.display_name()
        out.append(SelectableOption(
            option_id=f"inv_use_{eid}",
            label=f"Użyj: {name}",
            command=f"użyj {name}",
            group=GROUP_INVENTORY, target_id=eid,
            action_type="use",
        ))
        tags = ent.tags or []
        affs = ent.affordances or []
        if "trap" in tags or "deploy" in affs or "deployable" in tags:
            out.append(SelectableOption(
                option_id=f"inv_deploy_{eid}",
                label=f"Rozstaw: {name}",
                command=f"rozstaw {name}",
                group=GROUP_INVENTORY, target_id=eid,
                action_type="deploy",
            ))
    return out


def _crafting_options(world) -> List[SelectableOption]:
    out = [
        SelectableOption("craft_materials",
                         t("nav_materials", fallback="Materiały"),
                         "materiały", GROUP_CRAFTING),
        SelectableOption("craft_help",
                         t("nav_craft_help", fallback="Pomoc craftingu"),
                         "pomoc craftingu", GROUP_CRAFTING),
        SelectableOption("salvage_help",
                         t("nav_salvage_help", fallback="Pomoc odzyskiwania"),
                         "pomoc odzyskiwania", GROUP_CRAFTING),
        SelectableOption("trap_help",
                         t("nav_trap_help", fallback="Pomoc pułapek"),
                         "pomoc pułapek", GROUP_CRAFTING),
    ]
    # Add up to 3 ready-to-craft recipes the player has materials for.
    try:
        from . import crafting, materials
        for rk, rv in list(crafting.all_recipes().items())[:8]:
            needed = rv.get("required_materials") or {}
            if needed and materials.has_materials(world.character, needed):
                name_pl = rv.get("name_pl", rk)
                out.append(SelectableOption(
                    option_id=f"craft_make_{rk}",
                    label=f"Zrób: {name_pl}",
                    command=f"zrób {name_pl}",
                    group=GROUP_CRAFTING,
                    action_type="craft",
                ))
                if sum(1 for o in out if o.action_type == "craft") >= 3:
                    break
    except Exception:
        pass
    return out


# ── Movement / selection helpers ───────────────────────────────────────────

def move_selection(state: UISelectionState, dy: int) -> None:
    """Move selection up/down within the current group."""
    if not state.groups:
        return
    g = state.current_group()
    opts = state.options_in(g)
    if not opts:
        return
    idx = state.selected_index(g)
    idx = (idx + dy) % len(opts)
    state.set_selected_index(idx, g)


def cycle_group(state: UISelectionState, step: int) -> None:
    """Tab forward (step=+1) or Shift+Tab back (step=-1)."""
    if not state.groups:
        return
    state.current_group_index = (state.current_group_index + step) % len(state.groups)


def current_option(state: UISelectionState) -> Optional[SelectableOption]:
    if not state.groups:
        return None
    g = state.current_group()
    opts = state.options_in(g)
    if not opts:
        return None
    idx = state.selected_index(g)
    if 0 <= idx < len(opts):
        return opts[idx]
    return None


# ── Helper for character creation / class offer / etc ─────────────────────

def clamp_index(idx: int, length: int) -> int:
    if length <= 0:
        return 0
    return max(0, min(idx, length - 1))
