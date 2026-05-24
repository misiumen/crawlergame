"""UI layout calculator (Prompt 09).

Returns rectangles for every UI panel given the current screen width and
height. The output adapts to three modes:

  compact    : width < 1500    — two-column (room | sidebar)
  wide       : 1500 ≤ w < 2800 — two-column with larger sidebar
  ultrawide  : width ≥ 2800    — three-column (left | room | right)

Also returns the nav-panel rect anchored above the log so it never
overlays sidebar content (Prompt 09 fix).

Caller usage:
    layout = calculate_layout(width, height)
    layout.room_rect          # (x, y, w, h)
    layout.right_sidebar_rect
    layout.left_sidebar_rect  # zero-sized in compact/wide modes
    layout.nav_rect
    layout.font_scale         # multiplier on body font size
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple


Rect = Tuple[int, int, int, int]


@dataclass
class Layout:
    width: int = 1280
    height: int = 720
    mode: str = "compact"                # compact / wide / ultrawide
    is_ultrawide: bool = False

    # Vertical bands
    top_bar_rect:     Rect = (0, 0, 0, 0)
    main_rect:        Rect = (0, 0, 0, 0)
    nav_rect:         Rect = (0, 0, 0, 0)
    log_rect:         Rect = (0, 0, 0, 0)
    input_rect:       Rect = (0, 0, 0, 0)

    # Columns inside main_rect
    left_sidebar_rect:  Rect = (0, 0, 0, 0)
    room_rect:          Rect = (0, 0, 0, 0)
    right_sidebar_rect: Rect = (0, 0, 0, 0)

    # Convenience
    has_left_sidebar: bool = False

    # Fonts
    font_body:   int = 15
    font_small:  int = 13
    font_title:  int = 22
    font_scale:  float = 1.0


def _font_scale_for(width: int, height: int) -> float:
    """Pick a comfortable scale factor. We anchor 720p at 1.0 and grow
    modestly so 1440p reads well without becoming oversized."""
    # Use the smaller of the two ratios so an ultrawide doesn't blow up
    # font sizes that are tied mostly to vertical space.
    ratio_w = width / 1280.0
    ratio_h = height / 720.0
    s = min(ratio_w, ratio_h)
    # Round into discrete tiers so tiny resolution diffs don't shift fonts.
    if s < 1.05:  return 1.0
    if s < 1.4:   return 1.15
    if s < 1.7:   return 1.25
    return 1.35


def calculate_layout(width: int, height: int) -> Layout:
    """Return a fully-populated Layout for the given screen size."""
    w, h = int(width), int(height)
    L = Layout(width=w, height=h)
    L.is_ultrawide = (w / max(1, h)) >= 2.2
    if w < 1500:
        L.mode = "compact"
    elif w < 2800:
        L.mode = "wide"
    else:
        L.mode = "ultrawide"

    # Font tiers
    L.font_scale = _font_scale_for(w, h)
    s = L.font_scale
    L.font_body  = int(round(15 * s))
    L.font_small = int(round(13 * s))
    L.font_title = int(round(22 * s))

    # Vertical bands. Top bar scales gently; log + input stay readable.
    top_bar_h = max(48, min(72, int(60 * s)))
    input_h   = max(36, int(40 * s))
    # Log: 22% of remaining height at compact, 28% at wide+, but never less
    # than 160 px or more than 360 px.
    log_h = int((h - top_bar_h - input_h) * (0.32 if w >= 1500 else 0.28))
    log_h = max(160, min(360, log_h))
    # Nav panel: ~110-160 px depending on resolution. Lives above log.
    nav_h = max(110, min(170, int(140 * s)))

    main_y = top_bar_h
    main_h = h - top_bar_h - nav_h - log_h - input_h

    L.top_bar_rect = (0, 0, w, top_bar_h)
    L.main_rect   = (0, main_y, w, main_h)
    L.nav_rect    = (0, main_y + main_h, w, nav_h)
    L.log_rect    = (0, main_y + main_h + nav_h, w, log_h)
    L.input_rect  = (0, h - input_h, w, input_h)

    # Columns inside main_rect.
    gutter = 8
    if L.mode == "compact":
        right_w = 360
        L.room_rect = (0, main_y, w - right_w, main_h)
        L.right_sidebar_rect = (w - right_w, main_y, right_w, main_h)
        L.left_sidebar_rect = (0, main_y, 0, 0)
        L.has_left_sidebar = False
    elif L.mode == "wide":
        right_w = 420
        L.room_rect = (0, main_y, w - right_w, main_h)
        L.right_sidebar_rect = (w - right_w, main_y, right_w, main_h)
        L.left_sidebar_rect = (0, main_y, 0, 0)
        L.has_left_sidebar = False
    else:
        # Three-column ultrawide. Constrain room column so text doesn't
        # stretch into a paragraph of one line.
        left_w  = max(360, int(w * 0.22))
        right_w = max(360, int(w * 0.22))
        # Room column: cap centre width so wrapping stays comfortable.
        room_w = min(int(w * 0.50), 1080)
        # Distribute remainder symmetrically as gutter.
        center_x = (w - room_w) // 2
        L.left_sidebar_rect  = (0, main_y, left_w, main_h)
        L.room_rect          = (center_x, main_y, room_w, main_h)
        L.right_sidebar_rect = (w - right_w, main_y, right_w, main_h)
        L.has_left_sidebar = True

    return L


def is_ultrawide(width: int, height: int) -> bool:
    return (width / max(1, height)) >= 2.2
