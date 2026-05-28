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
# Prompt 22 — safehouse services as their own tab so the player has
# a discoverable surface for "talk to the receptionist / buy coffee /
# rest" instead of typing a number from memory.
GROUP_PERSONEL  = "personel"
# Prompt 22 — pet actions get their own tab. Surfaces all 5 pet verbs
# instead of just the 2 that fit cleanly in Akcje. Only appears when
# the player has an active pet.
GROUP_PET       = "pet"

ALL_GROUPS = (GROUP_ACTIONS, GROUP_EXITS, GROUP_OBJECTS, GROUP_ENTITIES,
              GROUP_PERSONEL, GROUP_PET, GROUP_INVENTORY, GROUP_CRAFTING)


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

    # P24.7 — two-tier picker. Each option declares its "kind":
    #   "plain"   — single-tier: clicking/Entering runs `command`
    #   "subject" — first-tier subject row; selecting it focuses
    #               `subject_id` for that group so the next build
    #               surfaces verbs for that subject
    #   "verb"    — second-tier verb row; runs `command` against the
    #               currently-focused subject
    #   "back"    — virtual "← Powrót" row; clears the group's focus
    option_kind: str = "plain"
    subject_id: Optional[str] = None     # opaque key used by the
                                         # builder to focus this row's
                                         # subject (e.g. entity_id-as-str,
                                         # exit label, item entity_id)


# P24.7 — which groups participate in the two-tier subject→verb pattern.
# Other groups (Akcje, Crafting, Usługi, Zwierzę) stay flat because their
# rows are already verb-shape and don't share a common subject.
TWO_TIER_GROUPS = frozenset({
    GROUP_OBJECTS,
    GROUP_ENTITIES,
    GROUP_INVENTORY,
    GROUP_EXITS,
})


@dataclass
class UISelectionState:
    groups: List[str] = field(default_factory=list)
    current_group_index: int = 0
    selected_index_by_group: Dict[str, int] = field(default_factory=dict)
    options_by_group: Dict[str, List[SelectableOption]] = field(default_factory=dict)
    # P24.7 — per-group focused subject. When set, that group renders
    # the verb-list for the subject (with a ← Powrót row at index 0).
    # When unset (default), the group renders the subject picker.
    focused_subject_by_group: Dict[str, str] = field(default_factory=dict)

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

    # P24.7 — focus helpers.
    def focused_subject(self, group: Optional[str] = None) -> Optional[str]:
        group = group or self.current_group()
        return self.focused_subject_by_group.get(group)

    def set_focused_subject(self, group: str, subject_id: Optional[str]) -> None:
        if subject_id is None:
            self.focused_subject_by_group.pop(group, None)
        else:
            self.focused_subject_by_group[group] = str(subject_id)
        # Reset selection to 0 when focus changes so the cursor lands
        # on the back row (or first verb / first subject).
        self.selected_index_by_group[group] = 0

    def clear_focus(self, group: Optional[str] = None) -> None:
        group = group or self.current_group()
        self.set_focused_subject(group, None)


# ── Localized headers ──────────────────────────────────────────────────────

_GROUP_LABEL_KEYS = {
    GROUP_ACTIONS:   ("ui_group_actions",   "Akcje"),
    GROUP_EXITS:     ("ui_group_exits",     "Wyjścia"),
    GROUP_OBJECTS:   ("ui_group_objects",   "Obiekty"),
    GROUP_ENTITIES:  ("ui_group_entities",  "Postacie"),
    GROUP_PERSONEL:  ("ui_group_personel",  "Usługi"),
    GROUP_PET:       ("ui_group_pet",       "Zwierzę"),
    GROUP_INVENTORY: ("ui_group_inventory", "Ekwipunek"),
    GROUP_CRAFTING:  ("ui_group_crafting",  "Crafting"),
}


def group_label(group_key: str) -> str:
    key, fb = _GROUP_LABEL_KEYS.get(group_key, ("", group_key))
    return t(key, fallback=fb)


# ── Builder ─────────────────────────────────────────────────────────────────

def build_play_options(world, prev_state: Optional["UISelectionState"] = None) -> UISelectionState:
    """Build a `UISelectionState` from world snapshot. Only includes
    visible/known things — never reveals hidden objects, hidden exits, or
    unidentified items.

    P24.7: the four object-bearing tabs (Obiekty / Postacie / Ekwipunek /
    Wyjścia) use a two-tier picker. The builder reads the focused subject
    from `prev_state.focused_subject_by_group` BEFORE constructing
    options, so subjects can be re-focused across rebuilds (every
    keystroke). Auto-focus when there's exactly one subject available.
    """
    state = UISelectionState()
    # Carry focus forward from prev_state so the rebuild reflects the
    # player's two-tier choice.
    if prev_state is not None:
        state.focused_subject_by_group = dict(prev_state.focused_subject_by_group)
    if world is None or world.current_floor is None:
        state.groups = [GROUP_ACTIONS]
        state.options_by_group[GROUP_ACTIONS] = _basic_actions(world)
        _restore_selection(state, prev_state)
        return state
    room = world.current_floor.current_room()
    if room is None:
        state.groups = [GROUP_ACTIONS]
        state.options_by_group[GROUP_ACTIONS] = _basic_actions(world)
        _restore_selection(state, prev_state)
        return state

    actions   = _basic_actions(world, room=room)
    exits     = _exit_options(world, room,
                              focused=state.focused_subject(GROUP_EXITS))
    objects   = _object_options(world, room,
                                focused=state.focused_subject(GROUP_OBJECTS))
    entities  = _entity_options(world, room,
                                focused=state.focused_subject(GROUP_ENTITIES))
    personel  = _personel_options(world, room)
    pet       = _pet_options(world)
    inv       = _inventory_options(world,
                                   focused=state.focused_subject(GROUP_INVENTORY))
    crafting  = _crafting_options(world)

    layout = []
    for gk, opts in (
        (GROUP_ACTIONS,   actions),
        (GROUP_EXITS,     exits),
        (GROUP_OBJECTS,   objects),
        (GROUP_ENTITIES,  entities),
        (GROUP_PERSONEL,  personel),
        (GROUP_PET,       pet),
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
    _restore_selection(state, prev_state)
    return state


def _restore_selection(state: "UISelectionState",
                       prev: Optional["UISelectionState"]) -> None:
    """Carry over prev group-tab + per-group selected index, if compatible
    with the newly-built layout. If the previously-selected group is no
    longer present (e.g. inventory just emptied), leaves the default."""
    if prev is None or not prev.groups or not state.groups:
        return
    prev_group_key = prev.groups[prev.current_group_index % len(prev.groups)] \
        if prev.groups else ""
    if prev_group_key and prev_group_key in state.groups:
        state.current_group_index = state.groups.index(prev_group_key)
    # Preserve per-group cursor positions, clamped to new option counts.
    for gk, idx in (prev.selected_index_by_group or {}).items():
        opts = state.options_by_group.get(gk, [])
        if opts:
            state.selected_index_by_group[gk] = max(0, min(idx, len(opts) - 1))
    # Prompt 23.5b: carry the grid shape (set by draw_nav_panel) across
    # rebuilds so the very next keydown's L/R can hop columns correctly.
    # Without this, every keystroke rebuilds the nav_state and wipes
    # `_grid_per_col`, forcing L/R to fall back to flat ±1.
    for attr in ("_grid_per_col", "_grid_col_count"):
        v = getattr(prev, attr, None)
        if v:
            try:
                setattr(state, attr, v)
            except AttributeError:
                pass


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
    # Prompt 22 — pet actions moved out of Akcje into their own Zwierzę
    # tab so generic actions stay uncluttered. See _pet_options below.
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


# ── P24.7 — generic two-tier helpers ─────────────────────────────────

def _back_option(group: str) -> SelectableOption:
    """The "← Powrót" virtual row that always sits at index 0 of a
    verb-list. Selecting it clears the group's focus, returning to
    the subject picker."""
    return SelectableOption(
        option_id=f"{group}_back",
        label="← Powrót",
        command="",
        group=group,
        option_kind="back",
    )


def _auto_focus_if_single(state_focus: Optional[str],
                          subject_ids: List[str]) -> Optional[str]:
    """If a tab's picker would have exactly one subject, auto-focus it
    so the player lands on the verb list directly. Returns the focus
    to use (existing focus wins; otherwise the lone subject)."""
    if state_focus is not None:
        return state_focus
    if len(subject_ids) == 1:
        return subject_ids[0]
    return None


def _exit_options(world, room, *,
                  focused: Optional[str] = None) -> List[SelectableOption]:
    """P28.6 — collapsed to ONE-TIER. The two-tier subject→verb dance
    was annoying for exits: every player wants to GO, not Sprawdź /
    Wyłam (the latter only ever applies to locked doors). Each exit
    now becomes a single clickable row that directly issues
    `idź <label>` (unlocked) or `wyłam <label>` (locked). Label
    includes the destination name so the player sees where they're
    going without a second click. Hidden exits stay hidden.
    """
    floor = world.current_floor
    visible = [(label, ed) for label, ed in (room.exits or {}).items()
               if not ed.get("hidden")]
    if not visible:
        return []
    out: List[SelectableOption] = []
    for label, ed in visible:
        target_id = ed.get("target", "")
        target_room = floor.rooms.get(target_id) if floor else None
        discovered = (floor.discovered_room_ids
                      if floor and hasattr(floor, "discovered_room_ids")
                      else set()) or set()
        target_name = (target_room.display_short_title()
                       if target_room and target_id in discovered
                       else "?")
        locked = bool(ed.get("locked"))
        if locked:
            out.append(SelectableOption(
                option_id=f"exit_force_{target_id or label}",
                label=f"Wyłam: {label}  →  {target_name}  🔒",
                command=f"wyłam {label}",
                group=GROUP_EXITS,
                option_kind="plain",
                subject_id=label,
                action_type="force",
            ))
        else:
            out.append(SelectableOption(
                option_id=f"exit_go_{target_id or label}",
                label=f"Idź: {label}  →  {target_name}",
                command=f"idź {label}",
                group=GROUP_EXITS,
                option_kind="plain",
                subject_id=label,
                action_type="move",
            ))
    return out


def _object_options(world, room, *,
                    focused: Optional[str] = None) -> List[SelectableOption]:
    """Two-tier (P24.7):
      * Picker: one row per visible non-creature object the player could
        meaningfully interact with.
      * Verbs (focused): per-entity verb set for the focused subject.
    """
    out = _flat_object_verbs(world, room)
    return _two_tier_route(out, focused, group=GROUP_OBJECTS,
                           subject_label_fn=_object_subject_label,
                           world=world)


def _object_subject_label(world, eid_str: str) -> str:
    """Resolve a subject_id (entity_id as string) to its display name."""
    try:
        ent = world.get(int(eid_str)) if world else None
    except (TypeError, ValueError):
        ent = None
    return ent.display_name() if ent is not None else eid_str


def _two_tier_route(flat_options: List[SelectableOption],
                    focused: Optional[str],
                    *, group: str,
                    subject_label_fn=None,
                    world=None) -> List[SelectableOption]:
    """Convert a flat verb list (with `target_id` per option) into
    either a subject picker or a focused-verb list.

    Each option must carry `target_id` (entity_id) — that's the
    subject the option acts upon. Options grouped by target_id become
    one subject row in the picker.
    """
    if not flat_options:
        return []
    # Preserve subject order from the flat list.
    subjects: List[str] = []
    by_subject: Dict[str, List[SelectableOption]] = {}
    for opt in flat_options:
        sid = str(opt.target_id) if opt.target_id is not None else ""
        if not sid:
            continue
        if sid not in by_subject:
            subjects.append(sid)
            by_subject[sid] = []
        by_subject[sid].append(opt)

    # P27.5 (P27-UX-22/26): if focused subject no longer exists in the
    # current subject list (left inventory, moved to another room,
    # exit doesn't exist in new room), auto-clear it back to picker
    # mode. Otherwise the verb-list block is empty and the player sees
    # just "← Powrót" — dead end.
    if focused is not None and focused not in by_subject:
        focused = None

    focused = _auto_focus_if_single(focused, subjects)

    if focused is None:
        # PICKER — one row per subject. Label = subject's display name.
        picker: List[SelectableOption] = []
        for sid in subjects:
            label = subject_label_fn(world, sid) if subject_label_fn else sid
            picker.append(SelectableOption(
                option_id=f"{group}_pick_{sid}",
                label=label,
                command="",
                group=group,
                option_kind="subject",
                subject_id=sid,
                target_id=int(sid) if sid.isdigit() else None,
                action_type=f"{group}_pick",
            ))
        return picker

    # VERBS — back row + focused subject's verbs (tagged kind="verb").
    out: List[SelectableOption] = [_back_option(group)]
    for opt in by_subject.get(focused, []):
        opt.option_kind = "verb"
        opt.subject_id = focused
        out.append(opt)
    return out


def _flat_object_verbs(world, room) -> List[SelectableOption]:
    """Original per-entity object-verb generator (pre-P24.7 logic).
    Now used by `_object_options` as the source for picker/verb routing.
    """
    out = []
    for e in room.visible_entities():
        if e.entity_type in ("monster", "crawler", "npc"):
            continue
        state = e.state or {}
        tags = e.tags or []
        # Prompt 22 fix: hide fully-dismantled / depleted objects so
        # the action bar doesn't keep showing "rozdzielnia" after it's
        # been reduced to parts. We still surface them if they're a
        # container (loot remnants may still be inside).
        # Prompt 24 fix (backlog #5): for corpses, hide them once they've
        # been BUTCHERED (state.butchered) — the corpse stays in the
        # room for narrative continuity but the action options stop
        # offering Wypatrosz / Zjedz.
        is_corpse = (e.entity_type == "corpse" or "corpse" in tags)
        fully_consumed = (state.get("stripped") or state.get("depleted")) and \
                         not (("container" in tags) or is_corpse)
        if fully_consumed:
            continue
        # Corpses are surfaced through a dedicated block below.
        if is_corpse:
            butchered = bool(state.get("butchered"))
            name = e.display_name()
            # Inspect remains available even after butchering (lore is
            # decoupled from material extraction).
            if e.fallback_desc or e.desc_key:
                out.append(SelectableOption(
                    option_id=f"inspect_{e.entity_id}",
                    label=f"Sprawdź: {name}",
                    command=f"sprawdź {name}",
                    group=GROUP_OBJECTS, target_id=e.entity_id,
                    action_type="inspect",
                ))
            # Wypatrosz / Zjedz only when not yet butchered/eaten.
            if not butchered:
                if "salvage" in (e.affordances or []):
                    out.append(SelectableOption(
                        option_id=f"butcher_{e.entity_id}",
                        label=f"Wypatrosz: {name}",
                        command=f"wypatrosz {name}",
                        group=GROUP_OBJECTS, target_id=e.entity_id,
                        action_type="butcher",
                    ))
                # Eat only if the corpse template marked it edible — query
                # via the corpses helper so authoring stays in content/data.
                try:
                    from ..engine import corpses as _cp
                    if _cp.is_edible(e) and "eat_corpse" in (e.affordances or []):
                        out.append(SelectableOption(
                            option_id=f"eat_{e.entity_id}",
                            label=f"Zjedz: {name}",
                            command=f"zjedz {name}",
                            group=GROUP_OBJECTS, target_id=e.entity_id,
                            action_type="eat",
                        ))
                except Exception:
                    pass
            continue
        # Prompt 22 fix: hide safehouse `service` entities from Obiekty.
        # Their interaction is mediated by the numbered safehouse-pick
        # menu, not by generic inspect/use. Otherwise we'd offer
        # "Sprawdź recepcja kliniki" / "Użyj recepcja kliniki" that
        # don't do anything meaningful — pure noise.
        if "service" in tags:
            continue
        name = e.display_name()
        affs = e.affordances or []
        # Inspect: always offer when the entity has a description to
        # display. Decorations with no desc would just print a generic
        # line — keep them out of the action bar.
        if e.fallback_desc or e.desc_key:
            out.append(SelectableOption(
                option_id=f"inspect_{e.entity_id}",
                label=f"Sprawdź: {name}",
                command=f"sprawdź {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="inspect",
            ))
        # Prompt 22 fix: distinguish PORTABLE items (player picks them
        # up with "podnieś") from CONTAINERS / CORPSES (player searches
        # them with "przeszukaj"). Previously both rendered as
        # "Przeszukaj" which is wrong for cards / cables / scrap.
        is_container = "container" in tags or "corpse" in tags or \
                       e.entity_type == "corpse"
        if e.portable and not is_container:
            out.append(SelectableOption(
                option_id=f"loot_{e.entity_id}",
                label=f"Podnieś: {name}",
                command=f"podnieś {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="loot",
            ))
        elif is_container and not state.get("depleted") \
                          and not state.get("searched"):
            out.append(SelectableOption(
                option_id=f"loot_{e.entity_id}",
                label=f"Przeszukaj: {name}",
                command=f"przeszukaj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="loot",
            ))
        # Salvage if tagged or affordance lists it AND not already
        # stripped AND not flagged no_salvage. P28.6: `no_salvage` is
        # stamped the first time the player tries to salvage an entity
        # with no salvage table — stops the bar offering Zdemontuj on
        # objects that will never yield surowce (e.g. a `zepsuty
        # terminal` lacking a SALVAGE_TABLES entry).
        if ("salvageable" in tags or "salvage" in affs) and \
           not state.get("stripped") and not state.get("no_salvage"):
            out.append(SelectableOption(
                option_id=f"salvage_{e.entity_id}",
                label=f"Zdemontuj: {name}",
                command=f"zdemontuj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="salvage",
            ))
        # Prompt 22 bug fix 8: Użyj is only meaningful for entities with
        # both `use` in affordances AND at least one "actually-usable"
        # tag. Bare terminals + safehouse counters previously offered
        # Użyj that produced zero feedback — pure noise.
        USE_TAGS = {"consumable","wearable","wield","interface","tool",
                    "powered","button","switch","controllable"}
        # P29.50 (#148) — vending_machine + jednorazowe `use`-able obiekty
        # znikają po wykorzystaniu. State flagi ustawione przez handlery
        # (np. vending_used, hacked dla terminala który wymaga use po
        # hack'u). Generic `used` flag jako fallback.
        use_exhausted = bool(state.get("used") or state.get("vending_used"))
        if "use" in affs and (set(tags) & USE_TAGS) and not use_exhausted:
            out.append(SelectableOption(
                option_id=f"use_{e.entity_id}",
                label=f"Użyj: {name}",
                command=f"użyj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="use",
            ))
        # Prompt 22 bug fix 9: Zhakuj requires both `hack` affordance
        # AND an actual interface tag. A sealed crate has no interface
        # to hack. Electronic / digital / networked entities qualify.
        # P29.50 (#148) — ukryj `zhakuj` jeśli state.hacked. Wcześniej
        # gracz mógł re-hackować w nieskończoność (każda kolejna próba
        # to nadmiarowy log + brak nowego efektu).
        HACK_TAGS = {"electrical","electronic","digital","interface",
                     "terminal","computer","network","camera","sensor",
                     "robot","drone","machine","ai","construct",
                     "door_electronic"}
        if ("hack" in affs and (set(tags) & HACK_TAGS)
                and not state.get("hacked")):
            out.append(SelectableOption(
                option_id=f"hack_{e.entity_id}",
                label=f"Zhakuj: {name}",
                command=f"zhakuj {name}",
                group=GROUP_OBJECTS, target_id=e.entity_id,
                action_type="hack",
            ))
    return out


def _entity_options(world, room, *,
                    focused: Optional[str] = None) -> List[SelectableOption]:
    """Two-tier (P24.7)."""
    flat = _flat_entity_verbs(world, room)
    return _two_tier_route(flat, focused, group=GROUP_ENTITIES,
                           subject_label_fn=_object_subject_label,
                           world=world)


def _flat_entity_verbs(world, room) -> List[SelectableOption]:
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
        # Prompt 22 bug fix 9: machine/robot/drone enemies can be hacked.
        # Per the user, this is a real and asked-for path: hack a robot
        # to disable it / turn it / read intel. Affordance is auto-added
        # below if the entity has a robot-class tag, in case the
        # content templates forgot it.
        ROBOT_TAGS = {"robot","drone","machine","ai","construct"}
        if (set(e.tags or []) & ROBOT_TAGS) and "hack" not in affs:
            # Soft-add hack: don't mutate the entity, just offer the
            # action. The hack handler validates the target's tags
            # again at resolve time.
            out.append(SelectableOption(
                option_id=f"hack_{e.entity_id}",
                label=f"Zhakuj: {name}",
                command=f"zhakuj {name}",
                group=GROUP_ENTITIES, target_id=e.entity_id,
                action_type="hack",
            ))
        elif "hack" in affs:
            out.append(SelectableOption(
                option_id=f"hack_{e.entity_id}",
                label=f"Zhakuj: {name}",
                command=f"zhakuj {name}",
                group=GROUP_ENTITIES, target_id=e.entity_id,
                action_type="hack",
            ))
    return out


def _pet_options(world) -> List[SelectableOption]:
    """Prompt 22 — Zwierzę tab. All 5 pet verbs surface here when the
    player has an active pet; tab disappears entirely otherwise."""
    out: List[SelectableOption] = []
    try:
        from ..engine import companion as _comp
        pet = _comp.active_pet(world)
    except Exception:
        return out
    if pet is None:
        return out
    name = pet.display_name_pl or "zwierzę"
    out.append(SelectableOption(
        "pet_inspect",
        t("nav_pet_inspect", fallback=f"Sprawdź {name}"),
        f"sprawdź zwierzę", GROUP_PET))
    out.append(SelectableOption(
        "pet_feed",
        t("nav_pet_feed", fallback=f"Nakarm {name}"),
        f"nakarm zwierzę", GROUP_PET))
    out.append(SelectableOption(
        "pet_calm",
        t("nav_pet_calm", fallback=f"Uspokój {name}"),
        f"uspokój zwierzę", GROUP_PET))
    out.append(SelectableOption(
        "pet_scout",
        t("nav_pet_scout", fallback=f"Wyślij {name} na zwiad"),
        f"wyślij zwierzę na zwiad", GROUP_PET))
    out.append(SelectableOption(
        "pet_lure",
        t("nav_pet_lure", fallback=f"Wabik ({name})"),
        f"użyj zwierzęcia jako wabika", GROUP_PET))
    return out


def _personel_options(world, room) -> List[SelectableOption]:
    """Prompt 22 — Personel (safehouse-staff / services) tab.

    Surfaces the safehouse-pick menu as labeled, navigable options
    instead of forcing the player to type numbers. Empty list when
    the current room isn't a safehouse — the tab disappears entirely
    in that case.
    """
    out: List[SelectableOption] = []
    subtype = getattr(room, "safehouse_subtype", None)
    if not subtype:
        return out
    try:
        from ..systems.safehouses import services as _services
    except Exception:
        return out

    # Polish-only labels per service action_key. The safehouse menu
    # already uses these strings via numeric-pick locale lookups; here
    # we re-render them in human form for the action bar.
    SERVICE_LABEL_PL = {
        "coffee":  ("Kawa (5 kr)",              "kawa"),
        "food":    ("Coś do jedzenia (12 kr)",  "jedzenie"),
        "chat":    ("Pogadaj z obsługą",        "pogadaj"),
        "wash":    ("Umyj się",                 "umyj się"),
        "hide":    ("Schowaj się tu",           "ukryj się"),
        "mirror":  ("Spójrz w lustro",          "spójrz w lustro"),
        "drink":   ("Drink (8 kr)",             "drink"),
        "schmooze":("Powiedz coś ciepłego",     "rozmowa"),
        "heal":    ("Opatrunek (20 kr)",        "opatrunek"),
        "cure":    ("Lek (30 kr)",              "lek"),
        "full":    ("Pełna kuracja (60 kr)",    "pełna kuracja"),
        "buy":     ("Kup coś",                  "kup"),
        "sell":    ("Sprzedaj",                 "sprzedaj"),
        "info":    ("Kup informację (15 kr)",   "informacja"),
        "ad":      ("Włącz reklamę sponsora",   "reklama"),
        "intel":   ("Zamów raport (10 kr)",     "raport"),
        "read":    ("Czytaj ogłoszenia",        "ogłoszenia"),
        "rest_short": ("Krótki odpoczynek",     "odpocznij"),
        "rumor":   ("Posłuchaj plotek",         "plotki"),
        "rest":    ("Odpocznij",                "odpocznij"),
    }

    svc_list = _services(subtype) or []
    for idx, svc in enumerate(svc_list, start=1):
        action_key = svc[0] if isinstance(svc, (tuple, list)) else svc
        label_text, cmd = SERVICE_LABEL_PL.get(
            action_key, (action_key, action_key))
        # Command is the numeric quick-pick — already wired through
        # the existing safehouse menu code path. Falls back to the
        # named verb if the player types it directly.
        out.append(SelectableOption(
            option_id=f"svc_{action_key}",
            label=label_text,
            command=str(idx),
            group=GROUP_PERSONEL,
            target_id=None,
            action_type="safehouse_service",
        ))
    return out


def _inventory_options(world, *,
                       focused: Optional[str] = None) -> List[SelectableOption]:
    """Two-tier (P24.7)."""
    flat = _flat_inventory_verbs(world)
    return _two_tier_route(flat, focused, group=GROUP_INVENTORY,
                           subject_label_fn=_object_subject_label,
                           world=world)


def _flat_inventory_verbs(world) -> List[SelectableOption]:
    out = []
    ch = world.character
    for eid in (ch.inventory_ids or [])[:12]:   # cap visible to 12
        ent = world.entities.get(eid)
        if ent is None: continue
        name = ent.display_name()
        tags = set(ent.tags or [])
        affs = ent.affordances or []
        # P24.7: Sprawdź on every item so the two-tier picker has
        # at least one verb per subject.
        if ent.fallback_desc or ent.desc_key:
            out.append(SelectableOption(
                option_id=f"inv_inspect_{eid}",
                label=f"Sprawdź: {name}",
                command=f"sprawdź {name}",
                group=GROUP_INVENTORY, target_id=eid,
                action_type="inspect",
            ))
        # P27 (P25-UX-1): wearables get Załóż in the Ekwipunek tab
        # so the player can equip without hunting for the paper-doll
        # slot. Detected by any slot:X tag.
        if any(t.startswith("slot:") for t in tags):
            out.append(SelectableOption(
                option_id=f"inv_wear_{eid}",
                label=f"Załóż: {name}",
                command=f"załóż {name}",
                group=GROUP_INVENTORY, target_id=eid,
                action_type="wear",
            ))
        # Weapons get Dobądź (P23 wield path) — same idea, equip
        # without typing.
        if "weapon" in tags or "wield" in affs:
            out.append(SelectableOption(
                option_id=f"inv_wield_{eid}",
                label=f"Dobądź: {name}",
                command=f"dobądź {name}",
                group=GROUP_INVENTORY, target_id=eid,
                action_type="wield",
            ))
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
        # Wyrzuć — always available; cheap escape from over-encumbrance.
        out.append(SelectableOption(
            option_id=f"inv_drop_{eid}",
            label=f"Wyrzuć: {name}",
            command=f"wyrzuć {name}",
            group=GROUP_INVENTORY, target_id=eid,
            action_type="drop",
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
        from ..content import crafting
        from ..content import materials
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
    """Move selection up/down within the current group (flat step)."""
    if not state.groups:
        return
    g = state.current_group()
    opts = state.options_in(g)
    if not opts:
        return
    idx = state.selected_index(g)
    idx = (idx + dy) % len(opts)
    state.set_selected_index(idx, g)


def move_selection_column(state: UISelectionState, direction: int) -> None:
    """Move selection LEFT (direction=-1) or RIGHT (direction=+1) by one
    grid column. The current grid shape is stashed on the state by
    `draw_nav_panel` at render time (per_col = rows per column).

    Layout is filled top-to-bottom-then-rightward: option i lives at
    (col = i // per_col, row = i % per_col). So a one-column hop is
    `idx + direction * per_col`, with bounds-aware wrap that preserves
    the player's row when possible.

    Falls back to the flat ±1 step when grid shape isn't known yet
    (first frame before render, or single-column layout).
    """
    if not state.groups:
        return
    g = state.current_group()
    opts = state.options_in(g)
    if not opts:
        return
    n = len(opts)
    per_col = int(getattr(state, "_grid_per_col", 0) or 0)
    col_count = int(getattr(state, "_grid_col_count", 0) or 0)
    if per_col <= 0 or col_count <= 1:
        # Single column or shape unknown — degrade to flat step. Players
        # at compact resolutions never see multiple columns, so L/R = ±1
        # is the only useful behavior there.
        return move_selection(state, direction)

    idx = state.selected_index(g)
    row = idx % per_col
    col = idx // per_col
    new_col = col + direction
    # Wrap horizontally — past the rightmost column loops to the
    # leftmost, and vice versa. This matches Up/Down's vertical wrap so
    # the two axes feel symmetric.
    new_col = new_col % col_count
    candidate = new_col * per_col + row
    # The bottom-right grid cell may be empty if n isn't a multiple of
    # per_col. In that case snap to the last available option in the
    # target column (highest row that exists).
    if candidate >= n:
        last_in_col = min(n - 1, new_col * per_col + (per_col - 1))
        candidate = last_in_col
    state.set_selected_index(candidate, g)


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
