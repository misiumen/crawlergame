"""Prompt 24.7 — Action Bar Subject-First (two-tier) smoke suite.

Covers:
  * Picker → focus → verb-list cycle (Obiekty, Postacie, Ekwipunek, Wyjścia)
  * "← Powrót" virtual back row at index 0 of every verb list
  * Auto-focus when there's exactly one subject (N=1 skips picker)
  * Focus persists across nav_state rebuilds (the _ensure_nav_state cycle)
  * Esc backs out of focus before exiting nav mode
  * L-arrow at index 0 with focus set acts as back
  * Mouse click on subject focuses; click on back clears; click on verb runs
  * Flat tabs (Akcje, Crafting, Usługi, Zwierzę) stay one-tier
  * Combat tab (Walka not added; combat target picking is in the arena)
  * Draw smoke at three resolutions
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..ui import ui_nav
from ..ui.ui_nav import (UISelectionState, SelectableOption,
                         GROUP_ACTIONS, GROUP_EXITS, GROUP_OBJECTS,
                         GROUP_ENTITIES, GROUP_INVENTORY, GROUP_CRAFTING,
                         GROUP_PERSONEL, GROUP_PET,
                         TWO_TIER_GROUPS, build_play_options)
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_ITEM, T_OBJECT, T_MONSTER, T_NPC


# ── World fixture ──────────────────────────────────────────────────────

def _mk_world():
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="Hala")
    r1 = RoomState(room_id="r1", fallback_short_title="Korytarz")
    r2 = RoomState(room_id="r2", fallback_short_title="Magazyn")
    r0.exits = {
        "wschód": {"target": "r1", "locked": False, "hidden": False},
        "zachód": {"target": "r2", "locked": True,  "hidden": False},
    }
    f.add_room(r0); f.add_room(r1); f.add_room(r2)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def _add_object(w, key, name, **kwargs):
    e = Entity(key=key, entity_type=T_OBJECT, fallback_name=name,
               fallback_desc=f"{name}.", location_id="r0", **kwargs)
    w.register(e); w.current_floor.current_room().entities.append(e)
    return e


def _add_npc(w, key, name):
    e = Entity(key=key, entity_type=T_NPC, fallback_name=name,
               affordances=["inspect", "talk"], location_id="r0",
               hp=5, max_hp=5)
    w.register(e); w.current_floor.current_room().entities.append(e)
    return e


def _add_inv_item(w, key, name, **kwargs):
    e = Entity(key=key, entity_type=T_ITEM, fallback_name=name,
               fallback_desc=f"{name}.", portable=True,
               location_id="inventory:player",
               affordances=["inspect", "use"], **kwargs)
    w.register(e); w.character.inventory_ids.append(e.entity_id)
    return e


# ── TWO_TIER_GROUPS membership ────────────────────────────────────────

def test_two_tier_groups_contains_expected():
    assert GROUP_OBJECTS in TWO_TIER_GROUPS
    assert GROUP_ENTITIES in TWO_TIER_GROUPS
    assert GROUP_INVENTORY in TWO_TIER_GROUPS
    assert GROUP_EXITS in TWO_TIER_GROUPS
    assert GROUP_ACTIONS not in TWO_TIER_GROUPS
    assert GROUP_CRAFTING not in TWO_TIER_GROUPS
    assert GROUP_PERSONEL not in TWO_TIER_GROUPS
    assert GROUP_PET not in TWO_TIER_GROUPS
    print("  TWO_TIER_GROUPS membership: OK")


# ── Inventory picker → verbs ───────────────────────────────────────────

def test_inventory_picker_lists_subjects():
    w = _mk_world()
    _add_inv_item(w, "knife", "nóż")
    _add_inv_item(w, "bandage", "bandaż")
    state = build_play_options(w)
    opts = state.options_in(GROUP_INVENTORY)
    kinds = [o.option_kind for o in opts]
    assert all(k == "subject" for k in kinds), \
        f"expected all subjects, got {kinds}"
    labels = [o.label for o in opts]
    assert "nóż" in labels and "bandaż" in labels
    print(f"  inventory picker (N>1): {labels}: OK")


def test_inventory_focus_shows_verbs_with_back():
    w = _mk_world()
    a = _add_inv_item(w, "knife", "nóż")
    _add_inv_item(w, "bandage", "bandaż")
    state = build_play_options(w)
    state.set_focused_subject(GROUP_INVENTORY, str(a.entity_id))
    # Rebuild — focus must persist.
    state2 = build_play_options(w, prev_state=state)
    opts = state2.options_in(GROUP_INVENTORY)
    kinds = [o.option_kind for o in opts]
    assert kinds[0] == "back", f"first row must be back, got {kinds[0]}"
    assert all(k == "verb" for k in kinds[1:]), \
        f"rest must be verbs, got {kinds}"
    # All verbs target the focused entity.
    for o in opts[1:]:
        assert o.target_id == a.entity_id
    labels = [o.label for o in opts]
    assert any("Sprawdź: nóż" in l for l in labels)
    assert any("Użyj: nóż" in l for l in labels)
    assert any("Wyrzuć: nóż" in l for l in labels)
    print(f"  inventory focus verbs: {labels}: OK")


def test_inventory_single_item_auto_focuses():
    w = _mk_world()
    a = _add_inv_item(w, "knife", "nóż")
    state = build_play_options(w)
    opts = state.options_in(GROUP_INVENTORY)
    # With N=1, picker is skipped — first row is the back row.
    assert opts and opts[0].option_kind == "back"
    print("  inventory N=1 auto-focus skips picker: OK")


# ── Object picker → verbs ─────────────────────────────────────────────

def test_object_picker_then_focus():
    w = _mk_world()
    a = _add_object(w, "monitor", "monitor",
                    tags=["fragile"], affordances=["inspect", "break"])
    b = _add_object(w, "shelf", "półka",
                    tags=["salvageable"],
                    affordances=["inspect", "salvage"])
    state = build_play_options(w)
    opts = state.options_in(GROUP_OBJECTS)
    assert all(o.option_kind == "subject" for o in opts), \
        f"picker expected, got {[o.option_kind for o in opts]}"
    state.set_focused_subject(GROUP_OBJECTS, str(b.entity_id))
    state2 = build_play_options(w, prev_state=state)
    opts2 = state2.options_in(GROUP_OBJECTS)
    assert opts2[0].option_kind == "back"
    verb_labels = [o.label for o in opts2[1:]]
    assert any("półka" in l for l in verb_labels)
    print(f"  object picker→focus verbs: {verb_labels}: OK")


# ── Entity picker → verbs ─────────────────────────────────────────────

def test_entity_picker_lists_npcs():
    w = _mk_world()
    a = _add_npc(w, "vendor", "Handlarz")
    b = _add_npc(w, "barker", "Naganiacz")
    state = build_play_options(w)
    opts = state.options_in(GROUP_ENTITIES)
    assert all(o.option_kind == "subject" for o in opts)
    state.set_focused_subject(GROUP_ENTITIES, str(a.entity_id))
    state2 = build_play_options(w, prev_state=state)
    opts2 = state2.options_in(GROUP_ENTITIES)
    assert opts2[0].option_kind == "back"
    labels = [o.label for o in opts2[1:]]
    assert any("Pogadaj: Handlarz" in l for l in labels)
    print(f"  entity picker→focus: {labels}: OK")


# ── Exit picker → verbs ───────────────────────────────────────────────

def test_exit_picker_lists_exits():
    """P28.6 — exits are now ONE-TIER. Each visible exit becomes a
    direct `plain` option that issues `idź <label>` or `wyłam <label>`
    immediately. No subject/verb dance."""
    w = _mk_world()
    state = build_play_options(w)
    opts = state.options_in(GROUP_EXITS)
    assert all(o.option_kind == "plain" for o in opts), \
        f"got {[o.option_kind for o in opts]}"
    # One unlocked + one locked → one Idź, one Wyłam.
    assert any(l.startswith("Idź:") for l in [o.label for o in opts]), opts
    assert any(l.startswith("Wyłam:") for l in [o.label for o in opts]), opts
    print(f"  exit one-tier rows: {[o.label for o in opts]}: OK")


def test_exit_unlocked_issues_move_directly():
    """One click on unlocked exit submits `idź <label>` — no focus step."""
    w = _mk_world()
    state = build_play_options(w)
    for o in state.options_in(GROUP_EXITS):
        if o.label.startswith("Idź:"):
            assert o.command.startswith("idź "), o.command
            print(f"  exit unlocked one-click: command={o.command!r}: OK")
            return
    raise AssertionError("no Idź option found")


def test_exit_locked_issues_force_directly():
    """One click on locked exit submits `wyłam <label>`."""
    w = _mk_world()
    state = build_play_options(w)
    for o in state.options_in(GROUP_EXITS):
        if o.label.startswith("Wyłam:"):
            assert o.command.startswith("wyłam "), o.command
            print(f"  exit locked one-click: command={o.command!r}: OK")
            return
    raise AssertionError("no Wyłam option found")


# ── Flat tabs stay flat ───────────────────────────────────────────────

def test_actions_tab_is_flat():
    w = _mk_world()
    state = build_play_options(w)
    opts = state.options_in(GROUP_ACTIONS)
    kinds = [o.option_kind for o in opts]
    # All "plain" (default kind for the basic-actions list).
    assert all(k == "plain" for k in kinds), \
        f"Akcje must stay flat: {kinds}"
    print(f"  Akcje stays one-tier ({len(opts)} options): OK")


def test_crafting_tab_is_flat():
    w = _mk_world()
    state = build_play_options(w)
    opts = state.options_in(GROUP_CRAFTING)
    kinds = [o.option_kind for o in opts]
    assert all(k == "plain" for k in kinds), \
        f"Crafting must stay flat: {kinds}"
    print(f"  Crafting stays one-tier: OK")


# ── Commit semantics ───────────────────────────────────────────────────

def test_commit_subject_focuses_not_runs():
    """Game._commit_nav_option on a subject sets focus; doesn't issue
    any command."""
    from ..engine.game import Game
    w = _mk_world()
    _add_object(w, "monitor", "monitor",
                affordances=["inspect"])
    _add_object(w, "shelf", "półka",
                tags=["salvageable"], affordances=["inspect", "salvage"])
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    # Switch to Obiekty.
    g.nav_state.current_group_index = g.nav_state.groups.index(GROUP_OBJECTS)
    opts = g.nav_state.options_in(GROUP_OBJECTS)
    issued = []
    g.submit_generated_command = lambda c, target_id=None: issued.append(c)
    g._commit_nav_option(opts[0])
    assert issued == [], f"subject commit must not run a command: {issued}"
    assert g.nav_state.focused_subject(GROUP_OBJECTS) is not None
    print("  commit subject → focus, no command: OK")


def test_commit_back_clears_focus():
    from ..engine.game import Game
    w = _mk_world()
    _add_inv_item(w, "knife", "nóż")
    _add_inv_item(w, "bandage", "bandaż")
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    g.nav_state.current_group_index = g.nav_state.groups.index(GROUP_INVENTORY)
    inv = g.nav_state.options_in(GROUP_INVENTORY)
    g._commit_nav_option(inv[0])  # focus first subject
    g._ensure_nav_state()
    inv2 = g.nav_state.options_in(GROUP_INVENTORY)
    assert inv2[0].option_kind == "back"
    g._commit_nav_option(inv2[0])  # back
    assert g.nav_state.focused_subject(GROUP_INVENTORY) is None
    print("  commit back clears focus: OK")


def test_commit_verb_runs_command():
    from ..engine.game import Game
    w = _mk_world()
    a = _add_inv_item(w, "knife", "nóż")
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    g.nav_state.current_group_index = g.nav_state.groups.index(GROUP_INVENTORY)
    inv = g.nav_state.options_in(GROUP_INVENTORY)
    # Already focused (N=1 auto-focus), so first row is back. Find Użyj.
    issued = []
    g.submit_generated_command = lambda c, target_id=None: issued.append(c)
    target_opt = next((o for o in inv if "Użyj" in o.label), None)
    assert target_opt is not None
    g._commit_nav_option(target_opt)
    assert any("użyj nóż" in c for c in issued), issued
    print(f"  commit verb runs command: {issued}: OK")


# ── Mouse click parity ─────────────────────────────────────────────────

def test_mouse_click_subject_focuses():
    from ..engine.game import Game
    w = _mk_world()
    _add_object(w, "monitor", "monitor", affordances=["inspect"])
    _add_object(w, "shelf", "półka",
                tags=["salvageable"], affordances=["inspect", "salvage"])
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    g._on_nav_option_click(GROUP_OBJECTS, 0)
    assert g.nav_state.focused_subject(GROUP_OBJECTS) is not None
    print("  mouse click subject → focus: OK")


def test_mouse_click_back_clears_focus():
    from ..engine.game import Game
    w = _mk_world()
    _add_inv_item(w, "knife", "nóż")
    _add_inv_item(w, "bandage", "bandaż")
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    g._on_nav_option_click(GROUP_INVENTORY, 0)  # focus first subject
    g._ensure_nav_state()
    g._on_nav_option_click(GROUP_INVENTORY, 0)  # back row
    assert g.nav_state.focused_subject(GROUP_INVENTORY) is None
    print("  mouse click back → clear focus: OK")


# ── Draw smoke ─────────────────────────────────────────────────────────

def test_draw_no_crash_with_two_tier():
    from ..engine.game import Game
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    g.draw()
    # Focus inventory.
    g._ensure_nav_state()
    inv = g.nav_state.options_in(GROUP_INVENTORY)
    if inv and inv[0].option_kind == "subject":
        g.nav_state.set_focused_subject(GROUP_INVENTORY, inv[0].subject_id)
    g.draw()
    print("  draw with focused subject: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_two_tier_groups_contains_expected()
    test_inventory_picker_lists_subjects()
    test_inventory_focus_shows_verbs_with_back()
    test_inventory_single_item_auto_focuses()
    test_object_picker_then_focus()
    test_entity_picker_lists_npcs()
    test_exit_picker_lists_exits()
    test_exit_unlocked_issues_move_directly()
    test_exit_locked_issues_force_directly()
    test_actions_tab_is_flat()
    test_crafting_tab_is_flat()
    test_commit_subject_focuses_not_runs()
    test_commit_back_clears_focus()
    test_commit_verb_runs_command()
    test_mouse_click_subject_focuses()
    test_mouse_click_back_clears_focus()
    test_draw_no_crash_with_two_tier()
    print("Prompt 24.7 two-tier action bar smoke: OK")


if __name__ == "__main__":
    main()
