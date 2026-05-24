"""Prompt 10 smoke — tabbed journal.

Asserts:
1. Parser routes journal commands to their tabs.
2. `get_journal_entries` produces valid `JournalEntry` shapes for every
   tab and never raises.
3. The Rumors tab does NOT leak raw `memetic:<seed_id>:<n>` keys.
4. Reliability buckets pick the right Polish label for representative
   reliability values.
5. Selection state clamps safely on empty tabs.
6. Old saves without knowledge fields load cleanly into journal collectors.

Run: python -m revamp._smoke_journal
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_OBJECT, T_MONSTER, T_NPC
from . import journal as J
from . import memetics
from .parser_core import parse


def _mk_world():
    w = WorldState()
    w.character = Character(name="J", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    f.discovered_room_ids = {"r0"}
    f.objective_key = "find_exit"
    f.objective_title_fallback = "Znajdź zejście"
    f.objective_description_fallback = "Znajdź działające zejście na niższe piętro."
    f.objective_solution_paths = ["use_password","sneak_past"]
    w.current_floor = f
    return w, f, r


def test_parser_routes_to_tabs():
    cases = [
        ("dziennik",        "journal_open"),
        ("journal",         "journal_open"),
        ("notatki",         "journal_open"),
        ("mapa",            "check_map"),
        ("ekwipunek",       "check_inventory"),
        ("materiały",       "check_materials"),
        ("wiedza",          "check_knowledge"),
        ("mity",            "check_beliefs"),
        ("plotki",          "check_beliefs"),
        ("przekonania",     "check_beliefs"),
        ("cele",            "journal_objectives"),
        ("crafting",        "journal_crafting"),
        ("crawlerzy",       "journal_crawlers"),
        ("osiągnięcia",     "journal_achievements"),
    ]
    for text, expected in cases:
        i = parse(text)
        assert i.intent == expected, f"{text!r} -> {i.intent} (expected {expected})"
    print(f"  parser routes: OK ({len(cases)} commands)")


def test_every_tab_returns_list():
    w, f, r = _mk_world()
    for tab in J.TABS:
        entries = J.get_journal_entries(w, tab)
        assert isinstance(entries, list), f"{tab} did not return list"
        for e in entries:
            assert isinstance(e, J.JournalEntry), f"{tab} returned non-entry"
            assert isinstance(e.title, str)
            assert isinstance(e.detail, str)
    print("  every tab returns valid entries: OK")


def test_map_tab_uses_discovered_rooms_only():
    w, f, r = _mk_world()
    # Add a second room but DON'T add it to discovered_room_ids.
    f.add_room(RoomState(room_id="r1", fallback_short_title="Schowek"))
    entries = J.get_journal_entries(w, J.TAB_MAP)
    titles = [e.title for e in entries]
    assert "Studio" in titles, f"discovered room missing: {titles}"
    assert "Schowek" not in titles, f"undiscovered room leaked: {titles}"
    print("  map tab respects discovered set: OK")


def test_rumors_tab_renders_memetic_naturally():
    w, f, r = _mk_world()
    seed = memetics.create_seed(method="rumor", core_claim="boss boi się luster",
                                target_tags=["crawler"], strength=70)
    memetics.register_seed(w, seed)
    key = f"memetic:{seed.seed_id}:0"
    f.rumors.append(key)
    entries = J.get_journal_entries(w, J.TAB_RUMORS)
    assert entries, "rumor entry missing"
    for e in entries:
        assert "memetic:" not in (e.body or "")
        assert "memetic:" not in (e.title or "")
        assert "memetic:" not in (e.detail or "")
    print(f"  rumors tab hides raw memetic keys: OK ({len(entries)} rumor entries)")


def test_reliability_buckets():
    cases = [
        ({"reliability": 1.0}, "confirmed", "Potwierdzone"),
        ({"reliability": 0.75}, "uncertain", "Niepewne"),
        ({"reliability": 0.55}, "suspicious", "Podejrzane"),
        ({"reliability": 0.4}, "distorted", "Zniekształcone"),
        ({"reliability": 0.2}, "contaminated", "Skażone"),
        ({"reliability": 0.9, "tags":["contaminated"]}, "contaminated", "Skażone"),
        ({"reliability": 1.0, "source":"memetic_propagation"}, "hearsay", "Zasłyszane"),
    ]
    for clue, expected_bucket, expected_label in cases:
        b = J.reliability_bucket(clue)
        assert b == expected_bucket, f"{clue} -> {b} (expected {expected_bucket})"
        assert J.reliability_label(b, "pl") == expected_label
    print("  reliability bucketing: OK")


def test_clue_formatter_marks_distorted():
    w, f, r = _mk_world()
    # Inject a known clue with low reliability + contaminated tag.
    w.known_clues = {
        "shaky_one": {
            "key":"shaky_one", "title":"Plotka z łazienki",
            "description":"Coś jest nie tak.",
            "reliability":0.2, "tags":["contaminated"],
        },
        "solid_one": {
            "key":"solid_one", "title":"Hasło JAZDA-0",
            "description":"Sprawdzone.",
            "reliability":0.95, "tags":[],
        },
    }
    entries = J.get_journal_entries(w, J.TAB_KNOWLEDGE)
    titles = {e.title: e.status for e in entries}
    assert titles.get("Plotka z łazienki") == "Skażone", f"got {titles}"
    assert titles.get("Hasło JAZDA-0") == "Potwierdzone", f"got {titles}"
    print("  contaminated vs confirmed clue labeling: OK")


def test_journal_state_selection_safe_on_empty():
    state = J.JournalState(open=True, tab=J.TAB_BELIEFS)
    state.set_selected(99)
    # Should not crash; selection stays clamped.
    assert state.selected() >= 0
    state.bump_scroll(-50)
    assert state.scroll() >= 0
    print("  journal state safety: OK")


def test_empty_tabs_return_empty_state_line():
    w, f, r = _mk_world()
    # No beliefs / no crawlers / no inventory yet.
    e = J.get_journal_entries(w, J.TAB_BELIEFS)
    assert e == []
    msg = J.empty_state(J.TAB_BELIEFS)
    assert "mit" in msg.lower() or "Brak" in msg
    print("  empty-state message present for empty tabs: OK")


def test_open_journal_handler():
    """Drive Game._open_journal + the route from `check_inventory`."""
    from .game import Game
    g = Game(screen=None)
    g.world = WorldState()
    g.world.character = Character(name="J", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    g.world.current_floor = f
    g.state = "play"
    g._handle_play_input("ekwipunek")
    assert g.journal_state.open is True
    assert g.journal_state.tab == J.TAB_INVENTORY
    # Close via command.
    g._handle_play_input("zamknij")
    assert g.journal_state.open is False
    # Re-open via command "dziennik".
    g._handle_play_input("dziennik")
    assert g.journal_state.open is True
    # Open beliefs via "mity".
    g._handle_play_input("mity")
    assert g.journal_state.tab == J.TAB_BELIEFS
    # Open rumors via "plotki".
    g._handle_play_input("plotki")
    assert g.journal_state.tab == J.TAB_RUMORS
    print("  command-to-tab routing: OK")


def test_old_save_tolerance():
    """Old save without any knowledge or belief fields must still render."""
    minimal = {
        "version": 1,
        "character": {"name":"old","background":"janitor"},
        "current_floor": None,
        "floor_number": 1,
        "entities": {}, "log": [], "known_crawlers": [],
        "settings": {}, "random_seed": None,
    }
    w = WorldState.from_dict(minimal)
    for tab in J.TABS:
        entries = J.get_journal_entries(w, tab)
        assert isinstance(entries, list)
    print("  old-save tolerance: OK")


def main():
    test_parser_routes_to_tabs()
    test_every_tab_returns_list()
    test_map_tab_uses_discovered_rooms_only()
    test_rumors_tab_renders_memetic_naturally()
    test_reliability_buckets()
    test_clue_formatter_marks_distorted()
    test_journal_state_selection_safe_on_empty()
    test_empty_tabs_return_empty_state_line()
    test_open_journal_handler()
    test_old_save_tolerance()
    print("Prompt 10 journal smoke: OK")


if __name__ == "__main__":
    main()
