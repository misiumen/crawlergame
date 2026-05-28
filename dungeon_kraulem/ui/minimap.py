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


# P28.6 — Z-axis support. Up/down exit labels push the target room onto
# a different vertical layer of the minimap. Player switches layers
# with PageUp / PageDown so a 3D dungeon (vents, stairwells, shafts)
# isn't squashed into one confusing 2D plane.
_VERTICAL_DELTAS: Dict[str, int] = {
    # Polish
    "góra":   +1, "gora":   +1, "w górę":   +1, "w gore":   +1,
    "dół":    -1, "dol":    -1, "w dół":    -1, "w dol":    -1,
    "sufit":  +1, "kratka": +1, "szyb":     +1, "winda":    +1,
    "podłoga": -1, "podloga": -1, "schody w dół": -1, "schody w dol": -1,
    "schody w górę": +1, "schody w gore": +1,
    # English
    "up":      +1, "down":     -1,
    "ceiling": +1, "floor_hole": -1,
    "stairs up": +1, "stairs down": -1,
    "elevator": +1, "vent": +1,
}


def _is_cardinal(label: str) -> bool:
    if not label:
        return False
    key = label.strip().lower()
    return key in _CARDINAL_DELTAS


def _vertical_delta(label: str) -> int:
    if not label:
        return 0
    return _VERTICAL_DELTAS.get(label.strip().lower(), 0)


def grid_positions(floor) -> Dict[str, Tuple[int, int]]:
    """Back-compat 2D positions: drops the Z component from
    grid_positions_3d. Callers that don't care about layers (legacy
    tests, simple layouts) keep working unchanged."""
    return {rid: (c, r) for rid, (c, r, _z) in grid_positions_3d(floor).items()}


def grid_positions_3d(floor) -> Dict[str, Tuple[int, int, int]]:
    """P28.6 — Z-aware BFS. Returns (col, row, z) per room. Up/down
    exit labels (góra/dół/szyb/winda/sufit/kratka/...) push the target
    onto a different Z layer instead of squashing it into the same
    2D plane. Cardinal NESW exits keep the same Z. Non-cardinal,
    non-vertical exits stay 2D-adjacent on the source's layer (the
    "place at next free slot" path from before).

    Z=0 is the layer containing start_room_id.
    """
    if floor is None or not getattr(floor, "rooms", None):
        return {}
    start = floor.start_room_id or floor.current_room_id
    if not start or start not in floor.rooms:
        start = next(iter(floor.rooms.keys()))

    placed: Dict[str, Tuple[int, int, int]] = {start: (0, 0, 0)}
    # Per-layer occupancy set so we only reject overlaps within the
    # same Z.
    occupied_by_z: Dict[int, Set[Tuple[int, int]]] = {0: {(0, 0)}}
    queue = [start]
    while queue:
        rid = queue.pop(0)
        r = floor.rooms.get(rid)
        if r is None:
            continue
        col, row, z = placed[rid]
        for label, ed in (r.exits or {}).items():
            tgt = ed.get("target", "")
            if not tgt or tgt not in floor.rooms:
                continue
            if tgt in placed:
                continue
            vz = _vertical_delta(label)
            if vz != 0:
                # Vertical hop: same (col, row) on a new Z layer.
                new_z = z + vz
                desired = (col, row)
                occ = occupied_by_z.setdefault(new_z, set())
                if desired in occ:
                    desired = _next_free_near(desired, occ)
                placed[tgt] = (desired[0], desired[1], new_z)
                occ.add(desired)
            elif _is_cardinal(label):
                dx, dy = _CARDINAL_DELTAS[label.strip().lower()]
                desired = (col + dx, row + dy)
                occ = occupied_by_z.setdefault(z, set())
                if desired in occ:
                    desired = _next_free_near(desired, occ)
                placed[tgt] = (desired[0], desired[1], z)
                occ.add(desired)
            else:
                # Non-cardinal, non-vertical: 2D-adjacent fallback.
                occ = occupied_by_z.setdefault(z, set())
                desired = _next_free_near((col, row), occ)
                placed[tgt] = (desired[0], desired[1], z)
                occ.add(desired)
            queue.append(tgt)

    # Stranded rooms (no exit chain from start) get parked below.
    leftover = [rid for rid in floor.rooms.keys() if rid not in placed]
    if leftover:
        max_row = max((p[1] for p in placed.values()), default=0)
        for i, rid in enumerate(leftover):
            placed[rid] = (i, max_row + 2, 0)

    return placed


def player_z_layer(floor) -> int:
    """Z coordinate of the room the player is currently in. Used by
    the minimap to default-view that layer when first opened."""
    if floor is None:
        return 0
    positions = grid_positions_3d(floor)
    cur = positions.get(getattr(floor, "current_room_id", ""))
    return cur[2] if cur else 0


def available_z_layers(floor) -> list:
    """Sorted list of unique Z layers present on this floor."""
    positions = grid_positions_3d(floor)
    return sorted({z for (_c, _r, z) in positions.values()})


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

    # P28.6 — Z-aware: gather 3D positions, filter to the layer the
    # player is currently viewing. View layer defaults to the player's
    # own Z, can be cycled with PageUp/PageDown (Game keystroke ↦
    # `world.minimap_z_view`).
    positions_3d = grid_positions_3d(floor)
    if not positions_3d:
        return
    z_layers = sorted({z for (_c, _r, z) in positions_3d.values()})
    player_z = player_z_layer(floor)
    viewed_z = int(getattr(world, "minimap_z_view", player_z))
    if viewed_z not in z_layers:
        viewed_z = player_z
    # Header with layer indicator.
    header_font = _font(max(11, int(layout.font_small) - 1), bold=True)
    n_layers = len(z_layers)
    if n_layers > 1:
        layer_idx = z_layers.index(viewed_z) + 1
        header_txt = f"MAPA · warstwa {layer_idx}/{n_layers}"
        # Hint that player is viewing a different layer than where they
        # actually stand — red asterisk-ish marker.
        if viewed_z != player_z:
            header_txt += "  (* nie tutaj)"
    else:
        header_txt = "MAPA"
    himg = header_font.render(header_txt, True, ACCENT)
    surf.blit(himg, (x + 8, y + 4))

    # Restrict positions to the viewed layer.
    positions = {rid: (c, r) for rid, (c, r, z) in positions_3d.items()
                 if z == viewed_z}
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
    # P28.4 — "marks" used to silently appear when you clicked a
    # non-adjacent room. That left players with random highlights they
    # never asked for, which read as "selected" and made the minimap
    # confusing. Marks no longer render. (Data stays in save files
    # harmlessly; we just stop drawing them.) Instead, we highlight the
    # rooms that left-click actually CAN walk to — the current room's
    # adjacent unlocked + non-hidden exits — so clickable cells stand
    # out from "you'd need to walk there first" cells.
    cur_room = floor.rooms.get(current_id)
    walkable_targets: Set[str] = set()
    if cur_room is not None:
        for _lbl, _ed in (cur_room.exits or {}).items():
            if not isinstance(_ed, dict):
                continue
            if _ed.get("locked") or _ed.get("hidden"):
                continue
            tgt = _ed.get("target")
            if tgt:
                walkable_targets.add(tgt)

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
        # Border: accent for adjacent walkable cells (left-click moves
        # here), normal for everything else. Current room keeps its
        # default border — the @ glyph already calls it out.
        if rid in walkable_targets:
            pygame.draw.rect(surf, ACCENT, (cx, cy, cell, cell), 2)
        else:
            pygame.draw.rect(surf, BORDER, (cx, cy, cell, cell), 1)
        # Glyph centered.
        img = glyph_font.render(glyph, True, color)
        gx = cx + (cell - img.get_width()) // 2
        gy = cy + (cell - img.get_height()) // 2
        surf.blit(img, (gx, gy))
        # Connectors to adjacent placed rooms. P28.3 (P27-UX-20): also
        # draw connectors for non-cardinal hops — long diagonal / chain
        # exits used to leave the player wondering whether a room was
        # actually reachable from another. Now any placed neighbour
        # whose position differs by 1 in either axis gets a connector.
        if room is not None:
            for label, ed in (room.exits or {}).items():
                tgt = ed.get("target", "")
                if tgt not in positions or tgt not in revealed:
                    continue
                tcol, trow = positions[tgt]
                dx = tcol - col
                dy = trow - row
                cx_mid = cx + cell // 2
                cy_mid = cy + cell // 2
                tcx_mid = off_x + (tcol - min_col) * cell + cell // 2
                tcy_mid = off_y + (trow - min_row) * cell + cell // 2
                # Only draw cardinals as a 1-px nub (matches old style);
                # everything else gets a dashed-style line between cell
                # centers so the link is visible without dominating.
                if dx == 1 and dy == 0:
                    pygame.draw.line(surf, BORDER,
                                     (cx + cell, cy_mid),
                                     (cx + cell + 2, cy_mid), 1)
                elif dx == 0 and dy == 1:
                    pygame.draw.line(surf, BORDER,
                                     (cx_mid, cy + cell),
                                     (cx_mid, cy + cell + 2), 1)
                # P29.47 — usunięte długie diagonalne łączniki między
                # cell-centrami. Po dodaniu więcej pokoi w piętrze
                # krzyż-krzyż linii zamulał minimapę. Cardinal nuby
                # wystarczą żeby pokazać sąsiedztwo; non-cardinal
                # exity i tak wymagają polecenia idź do <pokój>.
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
