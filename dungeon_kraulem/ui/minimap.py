"""Persistent minimap (P24.5).

Auto-grid layout from BFS over cardinal exit labels, with fog of war by
the floor's `discovered_room_ids` and `known_room_ids` sets. Pure 2D
rectangle rendering — no asset deps. Each cell shows one of:

  @  current room
  S  safehouse (any subtype)
  B  floor boss room
  !  miniboss / encounter not yet cleared
  ?  known but never visited (revealed via map fragment, or peeked)
  ·  cleared / safe traversal room
  □  visited but unknown actual_type
  ✕  blocked / locked-impassable (no current canon use; reserved)

Color is also encoded so colorblind-friendly + glyph + color both
disambiguate cell types.

API:
    grid_positions(floor) -> Dict[room_id, (col, row)]
    bounds(positions) -> (min_col, min_row, max_col, max_row)
    draw_minimap(surf, world, rect, layout) -> None
    handle_minimap_click(world, layout, mx, my) -> Optional[room_id]
       (Player-marked highlight only; no fast-travel.)
"""
from __future__ import annotations
from typing import Dict, Tuple, Optional, Set
import pygame

from ..config import (DARK_BG, PANEL_BG, BORDER, DIM_TEXT, NORMAL_TEXT,
                      BRIGHT_TEXT, ACCENT, ACCENT2, WARN, DANGER, SUCCESS)


# Cardinal direction → (dx, dy) delta in grid space. East+, South+ chosen
# so PL `wschód`/`zachód` map onto a screen-natural +x/-x and
# `północ`/`południe` map onto -y/+y (top is north, like a paper map).
_CARDINAL_DELTAS: Dict[str, Tuple[int, int]] = {
    # Polish
    "wschód":   (+1,  0), "wschod":   (+1,  0),
    "zachód":   (-1,  0), "zachod":   (-1,  0),
    "północ":   ( 0, -1), "polnoc":   ( 0, -1),
    "południe": ( 0, +1), "poludnie": ( 0, +1),
    # English (rare but cheap to support)
    "east":     (+1,  0),
    "west":     (-1,  0),
    "north":    ( 0, -1),
    "south":    ( 0, +1),
}


def _is_cardinal(label: str) -> bool:
    if not label:
        return False
    key = label.strip().lower()
    return key in _CARDINAL_DELTAS


def grid_positions(floor) -> Dict[str, Tuple[int, int]]:
    """BFS the floor's exit graph from start_room_id, deriving an
    integer (col, row) position per discovered/known room. Non-cardinal
    exits are queued but placed at the next free slot adjacent to their
    source (so the room exists on the map even when geometry is
    non-Euclidean — DCC stairwells, vents, anomalies).

    Rooms not reachable from start_room_id by ANY exit chain (rare,
    procgen edge case) get auto-placed at (huge_offset, n) so the map
    still renders something.
    """
    if floor is None or not getattr(floor, "rooms", None):
        return {}
    start = floor.start_room_id or floor.current_room_id
    if not start or start not in floor.rooms:
        # Fallback: arbitrary first room.
        start = next(iter(floor.rooms.keys()))

    placed: Dict[str, Tuple[int, int]] = {start: (0, 0)}
    occupied: Set[Tuple[int, int]] = {(0, 0)}
    queue = [start]
    visited_for_bfs: Set[str] = {start}
    while queue:
        rid = queue.pop(0)
        r = floor.rooms.get(rid)
        if r is None:
            continue
        col, row = placed[rid]
        for label, ed in (r.exits or {}).items():
            tgt = ed.get("target", "")
            if not tgt or tgt not in floor.rooms:
                continue
            if tgt in placed:
                continue
            if _is_cardinal(label):
                dx, dy = _CARDINAL_DELTAS[label.strip().lower()]
                desired = (col + dx, row + dy)
                if desired in occupied:
                    desired = _next_free_near(desired, occupied)
            else:
                # Non-cardinal hop: place adjacent in a free slot,
                # prefer east, then south, west, north.
                desired = _next_free_near((col, row), occupied)
            placed[tgt] = desired
            occupied.add(desired)
            visited_for_bfs.add(tgt)
            queue.append(tgt)

    # Place any unreachable rooms in a fallback strip below the main map.
    leftover = [rid for rid in floor.rooms.keys() if rid not in placed]
    if leftover:
        # Find bottom row of the placed graph.
        max_row = max((p[1] for p in placed.values()), default=0)
        for i, rid in enumerate(leftover):
            placed[rid] = (i, max_row + 2)

    return placed


def _next_free_near(origin: Tuple[int, int],
                    occupied: Set[Tuple[int, int]]) -> Tuple[int, int]:
    """Find the closest unoccupied cell using a small spiral search.
    Bounded so a pathological exit graph can't loop forever."""
    cx, cy = origin
    # Try the 8 immediate neighbours first, prefer cardinal first.
    candidates = [(1, 0), (0, 1), (-1, 0), (0, -1),
                  (1, 1), (-1, 1), (1, -1), (-1, -1)]
    for dx, dy in candidates:
        p = (cx + dx, cy + dy)
        if p not in occupied:
            return p
    # Expand by radius up to 4 cells.
    for r in range(2, 5):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r:
                    continue
                p = (cx + dx, cy + dy)
                if p not in occupied:
                    return p
    # Pathological fall-back: way out.
    return (cx + 99, cy)


def bounds(positions: Dict[str, Tuple[int, int]]
           ) -> Tuple[int, int, int, int]:
    if not positions:
        return (0, 0, 0, 0)
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    return (min(xs), min(ys), max(xs), max(ys))


def room_marker(room, floor, *, is_current: bool) -> Tuple[str, tuple]:
    """Return (glyph, color) for one room cell."""
    if is_current:
        return ("@", ACCENT)
    if room is None:
        return ("·", DIM_TEXT)
    rid = room.room_id
    visited = bool(getattr(room, "visited", False))
    cleared = bool(getattr(room, "cleared", False))
    if not visited:
        # Known but not visited — fog/peek marker.
        return ("?", DIM_TEXT)
    # Visited.
    if room.is_safe():
        return ("S", SUCCESS)
    if "floor_boss" in (getattr(room, "sensory_tags", []) or []) \
            or room.actual_type == "boss":
        return ("B", DANGER)
    # Miniboss heuristic: room state flagged as miniboss not yet cleared.
    if (room.state or {}).get("miniboss") and not cleared:
        return ("!", DANGER)
    if cleared:
        return ("·", NORMAL_TEXT)
    if room.actual_type == "combat":
        return ("⚔", WARN)
    if room.actual_type == "lore":
        return ("i", ACCENT2)
    if room.actual_type == "shop":
        return ("$", ACCENT2)
    # Visited but type unknown: open square.
    return ("□", BRIGHT_TEXT)


def _font(size: int, bold: bool = False):
    """Local font helper — avoids importing ui.py to dodge circular deps."""
    candidates = ["Consolas", "Lucida Console", "Courier New",
                  "DejaVu Sans Mono"]
    for nm in candidates:
        try:
            f = pygame.font.SysFont(nm, size, bold=bold)
            if f is not None:
                return f
        except Exception:
            continue
    return pygame.font.Font(None, size + 4)


def draw_minimap(surf, world, rect, layout, *,
                 click_registry=None,
                 on_room_click=None) -> None:
    """Render the persistent minimap. `rect` is the layout.minimap_rect.

    `click_registry`, if provided, gets a hit zone per room cell.
    `on_room_click(room_id)`, if provided, is called when a room cell is
    clicked. The callback decides whether to move there (adjacent +
    unlocked), open a route plan, toggle a mark, etc. Without a callback
    the default behavior is mark-toggle only — no fast-travel.
    """
    x, y, w, h = rect
    # P24.6: no heavy panel fill — just a subtle bottom edge so the
    # minimap reads as part of the left strip rather than a boxed-in
    # window. Matches the room / sidebar restyle.
    pygame.draw.line(surf, BORDER, (x, y + h - 1), (x + w, y + h - 1), 1)

    floor = getattr(world, "current_floor", None)
    if floor is None:
        return

    # Header.
    header_font = _font(max(11, int(layout.font_small) - 1), bold=True)
    himg = header_font.render("MAPA", True, ACCENT)
    surf.blit(himg, (x + 8, y + 4))

    positions = grid_positions(floor)
    if not positions:
        return

    min_col, min_row, max_col, max_row = bounds(positions)
    cols = max(1, max_col - min_col + 1)
    rows = max(1, max_row - min_row + 1)

    # Available area below header. P27.8 (P27-UX-18) — reserve 16px at
    # the bottom for a legend strip so glyphs (@/!/S/B/$/⚔) make sense
    # to a new player without opening help.
    pad_top = 22
    pad = 8
    legend_h = 16
    area_x = x + pad
    area_y = y + pad_top
    area_w = w - 2 * pad
    area_h = h - pad_top - pad - legend_h
    if area_w <= 0 or area_h <= 0:
        return

    # Cell size fits the bounds. P27.8 (P27-UX-17): bumped min cell from
    # 8→14 so glyphs stay legible on dense floors; cap raised 28→34 so
    # sparse floors don't waste the panel. Cells below 14 px get filled
    # with a simpler dot instead of a glyph.
    cell_w = max(14, min(34, area_w // cols))
    cell_h = max(14, min(34, area_h // rows))
    cell = min(cell_w, cell_h)

    # Center the grid within available area.
    grid_w = cell * cols
    grid_h = cell * rows
    off_x = area_x + max(0, (area_w - grid_w) // 2)
    off_y = area_y + max(0, (area_h - grid_h) // 2)

    revealed: Set[str] = set(getattr(floor, "discovered_room_ids", set()) or set())
    revealed |= set(getattr(floor, "known_room_ids", set()) or set())
    revealed |= set(getattr(floor, "revealed_room_ids", set()) or set())

    current_id = getattr(floor, "current_room_id", "")
    marked = set((getattr(world, "player_map_marks", None) or {}).get(
        floor.floor_id if hasattr(floor, "floor_id") else "f", []))

    glyph_font = _font(max(10, int(cell * 0.65)), bold=True)

    for rid, (col, row) in positions.items():
        if rid not in revealed and rid != current_id:
            continue
        room = floor.rooms.get(rid)
        # Pixel rect for this cell.
        cx = off_x + (col - min_col) * cell
        cy = off_y + (row - min_row) * cell
        # Cell background.
        pygame.draw.rect(surf, DARK_BG, (cx + 1, cy + 1, cell - 2, cell - 2))
        glyph, color = room_marker(room, floor, is_current=(rid == current_id))
        # Player-marked highlight.
        if rid in marked:
            pygame.draw.rect(surf, ACCENT, (cx, cy, cell, cell), 2)
        else:
            pygame.draw.rect(surf, BORDER, (cx, cy, cell, cell), 1)
        # Glyph centered.
        img = glyph_font.render(glyph, True, color)
        gx = cx + (cell - img.get_width()) // 2
        gy = cy + (cell - img.get_height()) // 2
        surf.blit(img, (gx, gy))
        # Connectors to adjacent placed rooms (only for cardinal exits).
        if room is not None:
            for label, ed in (room.exits or {}).items():
                tgt = ed.get("target", "")
                if tgt not in positions:
                    continue
                if tgt not in revealed:
                    continue
                tcol, trow = positions[tgt]
                if (tcol, trow) == (col + 1, row):       # east
                    pygame.draw.line(surf, BORDER,
                                     (cx + cell, cy + cell // 2),
                                     (cx + cell + 2, cy + cell // 2), 1)
                elif (tcol, trow) == (col, row + 1):     # south
                    pygame.draw.line(surf, BORDER,
                                     (cx + cell // 2, cy + cell),
                                     (cx + cell // 2, cy + cell + 2), 1)
        # Click zone. Default: toggle a player-placed mark. When
        # `on_room_click` is given, defer the decision to the caller —
        # they may choose to move (adjacent + unlocked), preview a
        # route, or fall back to mark-toggle.
        if click_registry is not None:
            def _click(_rid=rid, _world=world, _floor=floor):
                if on_room_click is not None:
                    handled = on_room_click(_rid)
                    if handled:
                        return
                fid = getattr(_floor, "floor_id", "f")
                book = _world.player_map_marks if hasattr(_world, "player_map_marks") \
                    else None
                if book is None:
                    _world.player_map_marks = {}
                    book = _world.player_map_marks
                bucket = book.setdefault(fid, [])
                if _rid in bucket:
                    bucket.remove(_rid)
                else:
                    bucket.append(_rid)
            tooltip = ""
            if room is not None:
                tooltip = room.display_short_title() if hasattr(room, "display_short_title") else rid
                # Hint that adjacent unlocked rooms are walkable.
                cur = getattr(floor, "current_room_id", "")
                cur_room = floor.rooms.get(cur)
                if cur_room and rid != cur:
                    for label, ed in (cur_room.exits or {}).items():
                        if ed.get("target") == rid and not ed.get("locked") \
                                and not ed.get("hidden"):
                            tooltip = f"Idź: {label} → {tooltip}"
                            break
            click_registry.add((cx, cy, cell, cell), _click,
                               tooltip=tooltip)

    # P27.8 — legend strip at the bottom of the panel.
    legend_font = _font(max(9, int(layout.font_small) - 2), bold=False)
    legend_y = y + h - legend_h + 1
    legend_items = [("@", ACCENT, "tu"), ("S", SUCCESS, "safe"),
                    ("!", DANGER, "wróg"), ("B", DANGER, "boss"),
                    ("$", ACCENT2, "sklep")]
    lx = x + 6
    for glyph, color, label in legend_items:
        gimg = legend_font.render(glyph, True, color)
        timg = legend_font.render(label, True, DIM_TEXT)
        if lx + gimg.get_width() + 2 + timg.get_width() + 8 > x + w:
            break
        surf.blit(gimg, (lx, legend_y))
        lx += gimg.get_width() + 2
        surf.blit(timg, (lx, legend_y))
        lx += timg.get_width() + 8


def handle_minimap_click(world, layout, mx: int, my: int) -> Optional[str]:
    """Optional direct dispatch — returns the room_id under the cursor
    if the click hits the minimap. Used as a fallback when no click
    registry is wired."""
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return None
    rect = layout.minimap_rect
    x, y, w, h = rect
    if not (x <= mx < x + w and y <= my < y + h):
        return None
    positions = grid_positions(floor)
    if not positions:
        return None
    min_col, min_row, max_col, max_row = bounds(positions)
    cols = max(1, max_col - min_col + 1)
    rows = max(1, max_row - min_row + 1)
    pad_top = 22
    pad = 8
    area_x = x + pad
    area_y = y + pad_top
    area_w = w - 2 * pad
    area_h = h - pad_top - pad
    cell_w = max(8, min(28, area_w // cols))
    cell_h = max(8, min(28, area_h // rows))
    cell = min(cell_w, cell_h)
    grid_w = cell * cols
    grid_h = cell * rows
    off_x = area_x + max(0, (area_w - grid_w) // 2)
    off_y = area_y + max(0, (area_h - grid_h) // 2)
    # Inverse mapping.
    col = (mx - off_x) // cell + min_col
    row = (my - off_y) // cell + min_row
    for rid, (c, r) in positions.items():
        if (c, r) == (col, row):
            return rid
    return None
