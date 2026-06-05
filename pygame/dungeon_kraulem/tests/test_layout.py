"""Smoke for Prompt 09 — resolution / layout.

Asserts:
1. `calculate_layout` returns sensible rects for compact / wide / ultrawide.
2. The nav panel rect never overlaps the right sidebar rect (the bug
   from Prompt 08).
3. The room rect at ultrawide is capped (no full-width paragraph).
4. Settings JSON round-trips and rejects unsupported resolutions.
5. Parser recognizes the resolution / fullscreen / windowed commands.

Run: python -m revamp._smoke_layout
"""
import os, json, tempfile

from ..ui import layout as L
from ..ui import settings
from ..engine.parser_core import parse


def _rects_disjoint_vertically(a, b) -> bool:
    """True iff rect `a` ends at or before rect `b` begins (or vice versa)
    on the y axis. Rects are (x,y,w,h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ay + ah <= by or by + bh <= ay


def _rects_disjoint(a, b) -> bool:
    """True if rectangles share no area."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax + aw <= bx or bx + bw <= ax
            or ay + ah <= by or by + bh <= ay)


def test_compact_layout_panels_disjoint():
    lo = L.calculate_layout(1280, 720)
    assert lo.mode == "compact"
    # P24.5: minimap is always visible, so left sidebar is always on.
    assert lo.has_left_sidebar
    # Nav must be ABOVE the log (no vertical overlap).
    assert _rects_disjoint_vertically(lo.nav_rect, lo.log_rect)
    # Nav must NOT overlap any sidebar.
    assert _rects_disjoint(lo.nav_rect, lo.right_sidebar_rect), \
        f"nav/sidebar overlap: nav={lo.nav_rect} sidebar={lo.right_sidebar_rect}"
    assert _rects_disjoint(lo.nav_rect, lo.left_sidebar_rect)
    # Three columns disjoint.
    assert _rects_disjoint(lo.left_sidebar_rect, lo.room_rect)
    assert _rects_disjoint(lo.room_rect, lo.right_sidebar_rect)
    # Log and input don't overlap.
    assert _rects_disjoint_vertically(lo.log_rect, lo.input_rect)
    print(f"  compact: left={lo.left_sidebar_rect} room={lo.room_rect} right={lo.right_sidebar_rect} nav={lo.nav_rect}")


def test_wide_layout():
    lo = L.calculate_layout(1920, 1080)
    assert lo.mode == "wide"
    # P24.5: minimap always visible.
    assert lo.has_left_sidebar
    assert _rects_disjoint(lo.nav_rect, lo.right_sidebar_rect)
    assert _rects_disjoint(lo.left_sidebar_rect, lo.room_rect)
    assert _rects_disjoint(lo.room_rect, lo.right_sidebar_rect)
    print(f"  wide: left w={lo.left_sidebar_rect[2]} room w={lo.room_rect[2]} sidebar w={lo.right_sidebar_rect[2]} font_body={lo.font_body}")


def test_ultrawide_layout_three_columns():
    lo = L.calculate_layout(3440, 1440)
    assert lo.mode == "ultrawide"
    assert lo.has_left_sidebar
    assert lo.is_ultrawide
    # Three disjoint columns
    assert _rects_disjoint(lo.left_sidebar_rect, lo.room_rect)
    assert _rects_disjoint(lo.room_rect, lo.right_sidebar_rect)
    assert _rects_disjoint(lo.left_sidebar_rect, lo.right_sidebar_rect)
    # Room column must be capped — no full-width paragraph.
    assert lo.room_rect[2] <= 1100, f"room column too wide: {lo.room_rect[2]}"
    # Nav doesn't overlap any column
    for col in (lo.left_sidebar_rect, lo.room_rect, lo.right_sidebar_rect):
        assert _rects_disjoint(lo.nav_rect, col), \
            f"nav overlaps a column at ultrawide: nav={lo.nav_rect} col={col}"
    print(f"  ultrawide: L={lo.left_sidebar_rect[2]} C={lo.room_rect[2]} R={lo.right_sidebar_rect[2]}")


def test_font_scaling_tiers():
    s720  = L.calculate_layout(1280, 720)
    s1080 = L.calculate_layout(1920, 1080)
    s1440 = L.calculate_layout(2560, 1440)
    sUW   = L.calculate_layout(3440, 1440)
    # Body font must grow, but not balloon at ultrawide.
    assert s720.font_body  >= 14
    assert s1080.font_body > s720.font_body
    assert s1440.font_body >= s1080.font_body
    assert sUW.font_body  <= s1440.font_body + 2, \
        "ultrawide must not balloon fonts past 1440p"
    print(f"  fonts: 720={s720.font_body} 1080={s1080.font_body} "
          f"1440={s1440.font_body} UW={sUW.font_body}")


def test_settings_roundtrip_in_tempdir():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as td:
        try:
            os.chdir(td)
            # Missing file → defaults
            s = settings.load_settings()
            assert s["resolution_width"] == 1280
            assert s["resolution_height"] == 720
            # Save a supported resolution
            assert settings.set_resolution(1920, 1080)
            s2 = settings.load_settings()
            assert s2["resolution_width"] == 1920
            assert s2["resolution_height"] == 1080
            # Reject unsupported resolution
            assert not settings.set_resolution(999, 999)
            # File still says 1920x1080
            s3 = settings.load_settings()
            assert s3["resolution_width"] == 1920
            # Toggle fullscreen
            assert settings.set_fullscreen(True)
            assert settings.load_settings()["fullscreen"] is True
            # Corrupt JSON loads as defaults
            with open(settings.SETTINGS_FILE, "w", encoding="utf-8") as f:
                f.write("not json {")
            s4 = settings.load_settings()
            assert s4["resolution_width"] == 1280
        finally:
            os.chdir(cwd)
    print("  settings round-trip + bad-file tolerance: OK")


def test_parser_resolution_commands():
    cases = [
        ("rozdzielczość", "show_resolutions"),
        ("resolution", "show_resolutions"),
        ("fullscreen", "set_fullscreen"),
        ("pełny ekran", "set_fullscreen"),
        ("windowed", "set_windowed"),
        ("tryb okna", "set_windowed"),
        ("ustaw rozdzielczość 1600x900", "set_resolution"),
        ("set resolution 1920x1080", "set_resolution"),
    ]
    for text, expected in cases:
        i = parse(text)
        assert i.intent == expected, f"{text!r} -> got {i.intent}, expected {expected}"
    # set_resolution must encode w/h on modifiers
    i = parse("ustaw rozdzielczość 1600x900")
    assert "w:1600" in i.modifiers and "h:900" in i.modifiers, \
        f"missing w/h modifiers: {i.modifiers}"
    print("  parser: resolution commands recognized")


def main():
    test_compact_layout_panels_disjoint()
    test_wide_layout()
    test_ultrawide_layout_three_columns()
    test_font_scaling_tiers()
    test_settings_roundtrip_in_tempdir()
    test_parser_resolution_commands()
    print("Prompt 09 layout smoke: OK")


if __name__ == "__main__":
    main()
