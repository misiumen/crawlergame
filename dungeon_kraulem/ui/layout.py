"""UI layout calculator (Prompt 09, restructured P24.5).

Returns rectangles for every UI panel given the current screen width and
height. The output adapts to three modes:

  compact    : width < 1500    — three-column tight (mini-strip | room | right)
  wide       : 1500 ≤ w < 2800 — three-column comfortable
  ultrawide  : width ≥ 2800    — three-column with extra room column space

P24.5 change: the minimap is now ALWAYS visible. The left strip splits
into a minimap rect (top) and a left_strip_rect (below, for known rooms /
objective / clues). The right sidebar keeps portrait + paper-doll +
quick-strip (or target panel during combat).

Caller usage:
    layout = calculate_layout(width, height)
    layout.minimap_rect
    layout.left_strip_rect
    layout.room_rect          # combat takes over this rect via draw_combat_arena
    layout.right_sidebar_rect
    layout.nav_rect
    layout.log_rect
    layout.input_rect
    layout.font_scale         # multiplier on body font size
"""
from __future__ import annotations
from dataclasses import dataclass
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

    # Columns inside main_rect.
    # P24.5: left column is now a vertical stack of minimap (top) +
    # left_strip (bottom — known rooms / objective / clues).
    # `left_sidebar_rect` is kept for back-compat (= the combined left
    # column rect = minimap + strip).
    left_sidebar_rect:  Rect = (0, 0, 0, 0)
    minimap_rect:       Rect = (0, 0, 0, 0)
    left_strip_rect:    Rect = (0, 0, 0, 0)
    room_rect:          Rect = (0, 0, 0, 0)
    right_sidebar_rect: Rect = (0, 0, 0, 0)

    # Convenience
    has_left_sidebar: bool = True   # P24.5: always true now

    # Fonts
    font_body:   int = 15
    font_small:  int = 13
    font_title:  int = 22
    font_scale:  float = 1.0


def _font_scale_for(width: int, height: int) -> float:
    """Pick a comfortable scale factor. We anchor 720p at 1.0 and grow
    modestly so 1440p reads well without becoming oversized."""
    ratio_w = width / 1280.0
    ratio_h = height / 720.0
    s = min(ratio_w, ratio_h)
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
    # Log: 22-32% of remaining height; clamp to readable range.
    log_h = int((h - top_bar_h - input_h) * (0.32 if w >= 1500 else 0.28))
    log_h = max(160, min(360, log_h))
    # Nav panel: scaled, lives above log.
    nav_h = max(110, min(170, int(140 * s)))

    main_y = top_bar_h
    main_h = h - top_bar_h - nav_h - log_h - input_h

    L.top_bar_rect = (0, 0, w, top_bar_h)
    L.main_rect   = (0, main_y, w, main_h)
    L.nav_rect    = (0, main_y + main_h, w, nav_h)
    L.log_rect    = (0, main_y + main_h + nav_h, w, log_h)
    L.input_rect  = (0, h - input_h, w, input_h)

    # P24.5: three-column layout at every resolution. Left strip is
    # narrower at compact, generous at wide+, large at ultrawide.
    if L.mode == "compact":
        left_w  = 160      # just enough for minimap + 4 row hints
        right_w = 320
        room_w  = max(400, w - left_w - right_w)
        room_x  = left_w
        right_x = left_w + room_w
    elif L.mode == "wide":
        left_w  = 220
        right_w = 380
        room_w  = max(400, w - left_w - right_w)
        room_x  = left_w
        right_x = left_w + room_w
    else:
        # Ultrawide: cap the room column so paragraphs don't stretch to
        # one long ribbon. Excess width becomes extra gutter +
        # proportionally wider sidebars.
        left_w  = max(280, min(int(w * 0.18), 420))
        right_w = max(380, min(int(w * 0.22), 540))
        # Cap room column at 1080 for comfortable reading.
        room_w_max = 1080
        avail_center = w - left_w - right_w
        room_w = min(avail_center, room_w_max)
        # Center the room column in the available middle.
        slack = avail_center - room_w
        room_x = left_w + max(0, slack // 2)
        right_x = w - right_w

    L.left_sidebar_rect  = (0,       main_y, left_w,  main_h)
    L.room_rect          = (room_x,  main_y, room_w,  main_h)
    L.right_sidebar_rect = (right_x, main_y, right_w, main_h)
    L.has_left_sidebar = True

    # Split the left column: minimap is a square at the top, strip
    # below. Minimap height scales with available width so it stays
    # roughly square.
    mm_size = max(120, min(left_w, int(left_w * 1.05)))
    L.minimap_rect    = (0, main_y, left_w, mm_size)
    L.left_strip_rect = (0, main_y + mm_size, left_w, main_h - mm_size)

    return L


def is_ultrawide(width: int, height: int) -> bool:
    return (width / max(1, height)) >= 2.2
