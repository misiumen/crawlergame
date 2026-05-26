"""Prompt 28.3 — journal mouse + craft polonization + movement +
minimap connectors smoke suite.

Covers:
  * Journal tab + row clicks switch state via click_registry
    (P27-UX-2)
  * Crafting detail contains Polish category + stat labels
    (P27-UX-3/4)
  * Bare direction commands (n / wschód / e) parse as `move`
    with the canonical exit label as destination (P27-UX-23)
  * Minimap draws non-cardinal connectors without crashing
    (P27-UX-20)
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1920, 1080))

from ..engine import parser_core as _pc


# ── Movement normalization ───────────────────────────────────────────────

def test_bare_direction_parses_as_move():
    for cmd, expected in [
        ("n", "północ"), ("s", "południe"), ("e", "wschód"),
        ("wschód", "wschód"), ("zachod", "zachód"),
        ("north", "północ"), ("south", "południe"),
        ("u", "góra"), ("d", "dół"),
    ]:
        i = _pc.parse(cmd, world=None)
        assert i.intent == "move", f"{cmd}: got intent {i.intent}"
        assert i.destination == expected, \
            f"{cmd}: got dest {i.destination!r}, want {expected!r}"
    print("  bare directions → move (8 forms): OK")


# ── Crafting polonization ────────────────────────────────────────────────

def test_crafting_detail_polonized():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..ui import journal as J
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    entries = J._collect_crafting(w)
    assert entries, "should have crafting entries"
    # At least one entry should contain "Kategoria: <PL>" and "Test: <stat>".
    # Polish keywords: narzędzie / pułapka / broń etc., and SIŁ/ZRĘ/INT/...
    saw_pl_category = False
    saw_pl_stat = False
    for e in entries:
        d = e.detail or ""
        if any(c in d for c in ("narzędzie", "pułapka", "broń", "medyczne",
                                "wabik", "pancerz", "ładunek", "mechaniczne")):
            saw_pl_category = True
        if "Test: " in d and any(s in d for s in ("SIŁ", "ZRĘ", "KON",
                                                  "INT", "MĄD", "CHA")):
            saw_pl_stat = True
        if saw_pl_category and saw_pl_stat:
            break
    assert saw_pl_category, "no PL category label in crafting detail"
    assert saw_pl_stat, "no PL stat label in crafting detail"
    print("  crafting detail polonized (category + stat): OK")


# ── Journal mouse hooks ──────────────────────────────────────────────────

def test_journal_tab_click_registers():
    from ..engine.game import Game
    from ..ui import ui as _ui
    from ..ui import journal as _journal
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    # Open the journal.
    g.journal_state.open = True
    g.journal_state.tab = _journal.TAB_LOG
    g.draw()
    cats = [z.category for z in g.click_registry.zones]
    tab_clicks = [c for c in cats if c == "journal_tab"]
    row_clicks = [c for c in cats if c == "journal_row"]
    assert tab_clicks, f"no journal_tab click zones; got {cats[:10]}"
    print(f"  journal: {len(tab_clicks)} tab clicks + {len(row_clicks)} row clicks: OK")


def test_journal_tab_click_switches_tab():
    """Simulate clicking a non-current tab — j_state.tab should change."""
    from ..engine.game import Game
    from ..ui import journal as _journal
    pygame.display.set_mode((1920, 1080))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.state = "play"
    g.journal_state.open = True
    g.journal_state.tab = _journal.TAB_LOG
    g.draw()
    # Find a tab zone for a different tab and trigger its callback.
    other_tab = _journal.TAB_INVENTORY
    # Locate the right tab zone — we know all tabs share category but
    # we can identify by tooltip == tab label.
    other_label = _journal.tab_label(other_tab)
    target = None
    for z in g.click_registry.zones:
        if z.category == "journal_tab" and z.tooltip == other_label:
            target = z
            break
    assert target is not None, f"no zone for tab '{other_label}'"
    target.callback()
    assert g.journal_state.tab == other_tab, \
        f"expected tab={other_tab}, got {g.journal_state.tab}"
    print(f"  journal tab click switched to {other_tab}: OK")


# ── Minimap non-cardinal ─────────────────────────────────────────────────

def test_minimap_draws_with_non_cardinal_exit():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor import FloorState
    from ..engine.room import RoomState
    from ..ui import minimap as _mm
    from ..ui import layout as _lay
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="A")
    r1 = RoomState(room_id="r1", fallback_short_title="B")
    r2 = RoomState(room_id="r2", fallback_short_title="C")
    # r0 → r1 cardinal east; r0 → r2 via NON-cardinal "schody w dół"
    r0.exits = {"wschód": {"target": "r1"},
                "schody_w_dół": {"target": "r2"}}
    r1.exits = {"zachód": {"target": "r0"}}
    r2.exits = {"schody_w_górę": {"target": "r0"}}
    f.add_room(r0); f.add_room(r1); f.add_room(r2)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.discovered_room_ids = {"r0", "r1", "r2"}
    w.current_floor = f
    surf = pygame.display.get_surface()
    layout = _lay.calculate_layout(surf.get_width(), surf.get_height())
    _mm.draw_minimap(surf, w, layout.minimap_rect, layout)
    positions = _mm.grid_positions(f)
    assert "r2" in positions, "r2 should still be placed despite non-cardinal exit"
    print(f"  minimap with non-cardinal exit + connector: OK (r2 at {positions['r2']})")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_bare_direction_parses_as_move()
    test_crafting_detail_polonized()
    test_journal_tab_click_registers()
    test_journal_tab_click_switches_tab()
    test_minimap_draws_with_non_cardinal_exit()
    print("Prompt 28.3 journal mouse + craft PL + movement + minimap smoke: OK")


if __name__ == "__main__":
    main()
