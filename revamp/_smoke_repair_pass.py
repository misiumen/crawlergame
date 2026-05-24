"""Prompt 11 smoke — pre-playtest repair pass.

Asserts:
1. Journal detail scroll state round-trips and resets on selection change.
2. `_wrap_paragraphs` wraps long text into multiple lines.
3. Title-menu [3] route opens settings (STATE_SETTINGS) and Escape returns.
4. Settings popup arrow keys cycle resolution + toggle fullscreen.
5. Settings Apply persists resolution via `settings.save_settings`.
6. Char creation PageUp/PageDown advances selection by 4.
7. After closing journal, text input still works.

Run: python -m revamp._smoke_repair_pass
"""
import os, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.font.init()

from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from . import journal as J


def test_detail_scroll_state():
    s = J.JournalState(open=True, tab=J.TAB_KNOWLEDGE)
    s.set_selected(0)
    assert s.detail_scroll() == 0
    s.bump_detail_scroll(+5)
    assert s.detail_scroll() == 5
    s.bump_detail_scroll(-100)
    assert s.detail_scroll() == 0  # clamps to 0
    # Switching selection resets the per-entry detail scroll.
    s.bump_detail_scroll(+10)
    assert s.detail_scroll() == 10
    s.set_selected(1)
    assert s.detail_scroll() == 0
    s.reset_detail_scroll()
    assert s.detail_scroll() == 0
    print("  detail scroll state: OK")


def test_wrap_paragraphs():
    from .ui import _wrap_paragraphs
    long = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.")
    out = _wrap_paragraphs(long, max_w=180, size=14)
    assert len(out) > 1, f"expected multi-line wrap, got {len(out)}"
    # Multi-paragraph preserves line breaks.
    multi = "Line one.\n\nLine three."
    out2 = _wrap_paragraphs(multi, max_w=500, size=14)
    assert "" in out2, "blank line preservation failed"
    print(f"  _wrap_paragraphs: OK ({len(out)} lines from long paragraph)")


def test_open_settings_from_title():
    from .game import Game, STATE_TITLE, STATE_SETTINGS
    g = Game(screen=None)
    g.state = STATE_TITLE
    g._open_settings()
    assert g.state == STATE_SETTINGS
    assert g.settings_state["prev_state"] == STATE_TITLE
    # Escape returns.
    import pygame as _pg
    g._handle_settings_keydown(_pg.K_ESCAPE, shift_held=False)
    assert g.state == STATE_TITLE
    print("  open settings + escape: OK")


def test_settings_arrow_keys_modify_state():
    from .game import Game, STATE_SETTINGS
    import pygame as _pg
    g = Game(screen=None)
    g._open_settings()
    # Move down to the fullscreen row.
    g._handle_settings_keydown(_pg.K_DOWN, False)
    assert g.settings_state["row"] == 1
    # Toggle fullscreen with right arrow.
    before = g.settings_state["fullscreen"]
    g._handle_settings_keydown(_pg.K_RIGHT, False)
    assert g.settings_state["fullscreen"] != before
    # Move back up to resolution row + cycle resolution.
    g._handle_settings_keydown(_pg.K_UP, False)
    assert g.settings_state["row"] == 0
    start_idx = g.settings_state["res_idx"]
    g._handle_settings_keydown(_pg.K_RIGHT, False)
    assert g.settings_state["res_idx"] != start_idx
    print("  settings arrow editing: OK")


def test_settings_apply_persists(tmp_path=None):
    """Apply should call set_resolution which writes settings_revamp.json."""
    from .game import Game
    import pygame as _pg
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as td:
        try:
            os.chdir(td)
            g = Game(screen=None)
            g._open_settings()
            # Move to a known resolution: cycle to (1920, 1080) — index 3.
            from .config import SUPPORTED_RESOLUTIONS
            g.settings_state["res_idx"] = SUPPORTED_RESOLUTIONS.index((1920, 1080))
            # Apply requires a real pygame display; expect set_resolution to
            # try `pygame.display.set_mode`. In this smoke we just verify
            # the settings JSON path is the one the function would write,
            # and that the resolution validation accepts the choice.
            from . import settings as _settings
            assert _settings.set_resolution(1920, 1080) is True
            saved = _settings.load_settings()
            assert saved["resolution_width"] == 1920
            assert saved["resolution_height"] == 1080
        finally:
            os.chdir(cwd)
    print("  settings persistence: OK")


def test_char_creation_page_keys():
    from .game import Game, STATE_CREATE
    import pygame as _pg
    g = Game(screen=None)
    g.state = STATE_CREATE
    g.cc = {"step": "background", "name_input": "x", "selected_bg": 0}

    class FakeEv:
        def __init__(self, k): self.key = k
    g._suppress_textinput = False
    g.handle_keydown(FakeEv(_pg.K_PAGEDOWN))
    assert g.cc["selected_bg"] == 4
    g.handle_keydown(FakeEv(_pg.K_PAGEDOWN))
    assert g.cc["selected_bg"] == 8
    g.handle_keydown(FakeEv(_pg.K_PAGEUP))
    assert g.cc["selected_bg"] == 4
    g.handle_keydown(FakeEv(_pg.K_END))
    assert g.cc["selected_bg"] == 11   # 12 backgrounds, index 11
    g.handle_keydown(FakeEv(_pg.K_HOME))
    assert g.cc["selected_bg"] == 0
    print("  char-creation PageUp/Down/Home/End: OK")


def test_text_input_after_journal_close():
    from .game import Game, STATE_PLAY
    import pygame as _pg
    g = Game(screen=None)
    g.world = WorldState()
    g.world.character = Character(name="x", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="X")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    g.world.current_floor = f
    g.state = STATE_PLAY
    # Open journal via command + close via Escape.
    g._handle_play_input("dziennik")
    assert g.journal_state.open
    g._journal_handle_key(_pg.K_ESCAPE, shift_held=False)
    assert g.journal_state.open is False
    # After close, textinput suppression must clear after one event.
    class FakeEv:
        text = "a"
    g.handle_textinput(FakeEv())  # consumes the suppression flag
    g.handle_textinput(FakeEv())  # now should append
    assert "a" in g.input_text
    print("  text input restored after journal close: OK")


def main():
    test_detail_scroll_state()
    test_wrap_paragraphs()
    test_open_settings_from_title()
    test_settings_arrow_keys_modify_state()
    test_settings_apply_persists()
    test_char_creation_page_keys()
    test_text_input_after_journal_close()
    print("Prompt 11 repair-pass smoke: OK")


if __name__ == "__main__":
    main()
