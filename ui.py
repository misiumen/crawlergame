"""CRAWL PROTOCOL v2 - Pygame rendering layer."""
import pygame
import math
from config import *
from utils import wrap_text, rating_label, box_tier_color, ability_modifier
from lang import tr


# ── Font cache ─────────────────────────────────────────────────────────────────

_fonts = {}


def get_font(size=FONT_SIZE_MD, bold=False):
    key = (size, bold)
    if key not in _fonts:
        # Try fonts known to ship Polish diacritics on Windows/macOS/Linux.
        candidates = [FONT_MONO, "Consolas", "Lucida Console", "DejaVu Sans Mono"]
        font = None
        for name in candidates:
            try:
                font = pygame.font.SysFont(name, size, bold=bold)
                if font is not None:
                    break
            except Exception:
                continue
        if font is None:
            font = pygame.font.Font(None, size + 4)
        _fonts[key] = font
    return _fonts[key]


# ── Primitives ─────────────────────────────────────────────────────────────────

def draw_rect_outline(surf, color, rect, width=1):
    pygame.draw.rect(surf, color, rect, width)


def draw_panel(surf, rect, bg=PANEL_BG, border=BORDER):
    x, y, w, h = rect
    pygame.draw.rect(surf, bg, rect)
    pygame.draw.rect(surf, border, rect, 1)


def draw_text(surf, text, x, y, color=NORMAL_TEXT, size=FONT_SIZE_MD, bold=False):
    font = get_font(size, bold)
    img = font.render(str(text), True, color)
    surf.blit(img, (x, y))
    return img.get_height()


def draw_text_wrapped(surf, text, x, y, max_w, color=NORMAL_TEXT, size=FONT_SIZE_MD, line_h=None):
    font = get_font(size)
    if line_h is None:
        line_h = font.get_height() + 2
    chars_per_line = max(1, max_w // max(1, font.size("X")[0]))
    lines = wrap_text(text, chars_per_line)
    cy = y
    for line in lines:
        img = font.render(line, True, color)
        surf.blit(img, (x, cy))
        cy += line_h
    return cy - y


def draw_bar(surf, x, y, w, h, value, max_value, fg=HP_BAR_FG, bg=HP_BAR_BG, label=""):
    pygame.draw.rect(surf, bg, (x, y, w, h))
    if max_value > 0:
        filled = int(w * value / max_value)
        pygame.draw.rect(surf, fg, (x, y, filled, h))
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1)
    if label:
        font = get_font(FONT_SIZE_SM)
        img = font.render(label, True, BRIGHT_TEXT)
        surf.blit(img, (x + 2, y + (h - img.get_height()) // 2))


# ── Map panel ──────────────────────────────────────────────────────────────────

NODE_RADIUS = 16


def draw_map_panel(surf, floor, player_node_id, hovered_node=None):
    x, y, w, h = MAP_RECT
    draw_panel(surf, MAP_RECT)

    # Header
    font_sm = get_font(FONT_SIZE_SM)
    header = f"FLOOR {floor.floor_num} - {floor.theme_name}"
    draw_text(surf, header, x + 8, y + 6, ACCENT, FONT_SIZE_SM, bold=True)
    draw_text(surf, floor.theme_desc, x + 8, y + 22, DIM_TEXT, FONT_SIZE_SM)

    offset_y = 38

    # Draw edges
    for node_id, room in floor.rooms.items():
        for conn_id in room.connections:
            if conn_id in floor.rooms:
                nx1, ny1 = room.x + x, room.y + y + offset_y
                r2 = floor.rooms[conn_id]
                nx2, ny2 = r2.x + x, r2.y + y + offset_y
                pygame.draw.line(surf, EDGE_COLOR, (nx1, ny1), (nx2, ny2), 1)

    # Draw nodes
    for node_id, room in floor.rooms.items():
        nx = room.x + x
        ny = room.y + y + offset_y

        # Determine node color
        if node_id == player_node_id:
            color = NODE_CURR
        elif room.cleared:
            color = NODE_VISIT
        elif not room.visited:
            color = NODE_UNVIS
        elif room.room_type == "boss":
            color = NODE_BOSS
        elif room.room_type == "checkpoint":
            color = NODE_SAFE
        else:
            color = NODE_BORDER

        # Highlight hovered
        border_color = BRIGHT_TEXT if node_id == hovered_node else NODE_BORDER
        border_w = 2 if node_id == hovered_node else 1

        pygame.draw.circle(surf, color, (nx, ny), NODE_RADIUS)
        pygame.draw.circle(surf, border_color, (nx, ny), NODE_RADIUS, border_w)

        # Symbol
        sym = room.symbol()
        font = get_font(FONT_SIZE_SM, bold=(node_id == player_node_id))
        sym_img = font.render(sym, True, BRIGHT_TEXT if not room.cleared else DIM_TEXT)
        surf.blit(sym_img, (nx - sym_img.get_width() // 2, ny - sym_img.get_height() // 2))

    # Legend
    legend_y = y + h - 50
    draw_text(surf, "@ you  E enemy  T trap  $ loot  R rest", x + 6, legend_y, DIM_TEXT, FONT_SIZE_SM)
    draw_text(surf, "M shop  ? lore  ~ mutation  C checkpoint  B boss", x + 6, legend_y + 14, DIM_TEXT, FONT_SIZE_SM)


def map_node_at(floor, mx, my):
    """Return node_id under mouse position (mx, my) or None."""
    ox, oy, _, _ = MAP_RECT
    offset_y = 38
    for node_id, room in floor.rooms.items():
        nx = room.x + ox
        ny = room.y + oy + offset_y
        dist = math.sqrt((mx - nx) ** 2 + (my - ny) ** 2)
        if dist <= NODE_RADIUS:
            return node_id
    return None


# ── Info panel ─────────────────────────────────────────────────────────────────

def draw_info_panel(surf, player, current_room=None, combat_state=None):
    x, y, w, h = INFO_RECT
    draw_panel(surf, INFO_RECT)
    cx = x + 10
    cy = y + 8
    line_h = get_font(FONT_SIZE_MD).get_height() + 3
    sm_line_h = get_font(FONT_SIZE_SM).get_height() + 2

    # Name and class
    cls_str = player.class_name or "Unclassified"
    if player.hybrid_class:
        cls_str = player.hybrid_class
    elif player.specialization:
        cls_str = f"{player.class_name} (Spec)"
    draw_text(surf, f"{player.name}  [{cls_str}]", cx, cy, BRIGHT_TEXT, FONT_SIZE_LG, bold=True)
    cy += line_h + 4

    # Floor / level
    draw_text(surf, f"Floor {player.current_floor}   Level {player.level}   Prof +{player.prof()}", cx, cy, DIM_TEXT, FONT_SIZE_SM)
    cy += sm_line_h + 2

    # HP bar
    draw_bar(surf, cx, cy, w - 20, 14, player.hp, player.max_hp,
             HP_BAR_FG, HP_BAR_BG, f"HP {player.hp}/{player.max_hp}")
    cy += 18

    # XP bar
    xp_needed = player.xp_to_next()
    draw_bar(surf, cx, cy, w - 20, 10, player.xp, xp_needed,
             XP_BAR_FG, XP_BAR_BG, f"XP {player.xp}/{xp_needed}")
    cy += 14

    # Audience rating
    rating = player.audience_rating
    rlabel = rating_label(rating)
    draw_text(surf, f"Audience: {rating}  [{rlabel}]", cx, cy, RATING_FG, FONT_SIZE_SM)
    cy += sm_line_h + 4

    # Credits + AC
    draw_text(surf, f"CR: {player.credits}   AC: {player.effective_ac()}", cx, cy, ACCENT, FONT_SIZE_SM)
    cy += sm_line_h + 4

    # Separator
    pygame.draw.line(surf, BORDER, (cx, cy), (x + w - 10, cy), 1)
    cy += 6

    # Stats in two columns
    stats = player.stat_block_lines()
    col_w = (w - 20) // 2
    for i, line in enumerate(stats):
        col = i % 2
        row = i // 2
        sx = cx + col * col_w
        sy = cy + row * sm_line_h
        draw_text(surf, line, sx, sy, NORMAL_TEXT, FONT_SIZE_SM)
    cy += (math.ceil(len(stats) / 2)) * sm_line_h + 6

    pygame.draw.line(surf, BORDER, (cx, cy), (x + w - 10, cy), 1)
    cy += 6

    # Gear
    draw_text(surf, tr("ui_gear"), cx, cy, ACCENT, FONT_SIZE_SM, bold=True)
    cy += sm_line_h
    for line in player.gear_lines():
        draw_text(surf, line, cx, cy, NORMAL_TEXT, FONT_SIZE_SM)
        cy += sm_line_h
    cy += 4

    # Features
    pygame.draw.line(surf, BORDER, (cx, cy), (x + w - 10, cy), 1)
    cy += 6
    draw_text(surf, tr("ui_features"), cx, cy, ACCENT, FONT_SIZE_SM, bold=True)
    cy += sm_line_h
    for i, feat in enumerate(player.features):
        avail_color = NORMAL_TEXT if feat.is_available() else DIM_TEXT
        cooldown = f" ({feat.cooldown_max - feat.cooldown_cur}/{feat.cooldown_max})" if feat.cooldown_max > 0 else ""
        draw_text(surf, f"[{i+6}] {feat.name}{cooldown}", cx, cy, avail_color, FONT_SIZE_SM)
        cy += sm_line_h
        if cy > y + h - 80:
            break

    # Conditions
    if player.conditions:
        cy += 4
        cond_str = tr("ui_status", conds=", ".join(player.conditions))
        draw_text(surf, cond_str, cx, cy, DANGER, FONT_SIZE_SM)
        cy += sm_line_h

    # Combat enemy bar (if in combat)
    if combat_state and combat_state.active_enemies():
        pygame.draw.line(surf, BORDER, (cx, cy), (x + w - 10, cy), 1)
        cy += 6
        draw_text(surf, tr("ui_enemies"), cx, cy, DANGER, FONT_SIZE_SM, bold=True)
        cy += sm_line_h
        for enemy in combat_state.active_enemies():
            draw_bar(surf, cx, cy, w - 20, 12, enemy.hp, enemy.max_hp,
                     DANGER, HP_BAR_BG, f"{enemy.name} {enemy.hp}/{enemy.max_hp}")
            cy += 16
            if cy > y + h - 20:
                break

    # Current room info (if exploring)
    if current_room and not combat_state:
        pygame.draw.line(surf, BORDER, (cx, cy), (x + w - 10, cy), 1)
        cy += 6
        draw_text(surf, f"{tr('ui_room')}: {current_room.name}", cx, cy, ACCENT, FONT_SIZE_SM, bold=True)
        cy += sm_line_h
        draw_text(surf, current_room.description(), cx, cy, DIM_TEXT, FONT_SIZE_SM)
        cy += sm_line_h + 2

        # Navigation options
        reachable = current_room.connections
        if reachable:
            draw_text(surf, "Paths:", cx, cy, DIM_TEXT, FONT_SIZE_SM)
            cy += sm_line_h
            # Show type icons for connected rooms
            for nid in reachable[:6]:
                # (just show IDs; actual labels in log)
                pass


# ── Log panel ──────────────────────────────────────────────────────────────────

def draw_log_panel(surf, log_lines, scroll_offset=0):
    x, y, w, h = LOG_RECT
    draw_panel(surf, LOG_RECT, bg=LOG_BG)
    draw_text(surf, tr("log_broadcast"), x + 8, y + 4, ACCENT, FONT_SIZE_SM, bold=True)

    font = get_font(FONT_SIZE_SM)
    line_h = font.get_height() + 1
    max_lines = (h - 20) // line_h

    visible = log_lines[-(max_lines + scroll_offset): len(log_lines) - scroll_offset if scroll_offset else None]
    if not visible:
        visible = log_lines[-max_lines:]

    cy = y + 18
    for text, category in visible[-max_lines:]:
        color = LOG_COLORS.get(category, NORMAL_TEXT)
        draw_text(surf, text, x + 8, cy, color, FONT_SIZE_SM)
        cy += line_h
        if cy > y + h - 4:
            break


# ── Input bar ──────────────────────────────────────────────────────────────────

def draw_input_bar(surf, input_text, prompt="> ", blink=True):
    x, y, w, h = INPUT_RECT
    pygame.draw.rect(surf, INPUT_BG, INPUT_RECT)
    pygame.draw.rect(surf, ACCENT, INPUT_RECT, 1)

    font = get_font(FONT_SIZE_MD)
    full = prompt + input_text
    if blink:
        full += "|"
    img = font.render(full, True, BRIGHT_TEXT)
    surf.blit(img, (x + 8, y + (h - img.get_height()) // 2))


# ── Popup / modal dialogs ──────────────────────────────────────────────────────

def draw_popup(surf, title, lines, options=None, width=600, height=None):
    """Draw a centered popup. options = list of (key, label) tuples."""
    font_title = get_font(FONT_SIZE_LG, bold=True)
    font_body = get_font(FONT_SIZE_MD)
    font_opt = get_font(FONT_SIZE_SM)

    line_h = font_body.get_height() + 4
    opt_h = font_opt.get_height() + 3

    content_h = font_title.get_height() + 12 + len(lines) * line_h
    if options:
        content_h += len(options) * opt_h + 8
    if height is None:
        height = min(content_h + 40, SCREEN_H - 60)

    px = (SCREEN_W - width) // 2
    py = (SCREEN_H - height) // 2

    # Dim background
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surf.blit(overlay, (0, 0))

    # Popup box
    pygame.draw.rect(surf, PANEL_BG, (px, py, width, height))
    pygame.draw.rect(surf, ACCENT, (px, py, width, height), 2)

    cy = py + 12

    # Title
    title_img = font_title.render(title, True, ACCENT)
    surf.blit(title_img, (px + (width - title_img.get_width()) // 2, cy))
    cy += title_img.get_height() + 8
    pygame.draw.line(surf, BORDER, (px + 10, cy), (px + width - 10, cy), 1)
    cy += 8

    # Body lines
    for line in lines:
        color = NORMAL_TEXT
        if line.startswith("  ["):
            color = ACCENT
        elif line.startswith("  SUCCESS") or line.startswith("  Crit"):
            color = SUCCESS
        elif line.startswith("  FAIL") or line.startswith("  Miss"):
            color = DANGER
        elif line.startswith("  --"):
            color = DIM_TEXT
        img = font_body.render(line, True, color)
        surf.blit(img, (px + 12, cy))
        cy += line_h

    # Options
    if options:
        cy += 8
        pygame.draw.line(surf, BORDER, (px + 10, cy), (px + width - 10, cy), 1)
        cy += 6
        for key, label in options:
            opt_text = f"[{key}] {label}"
            img = font_opt.render(opt_text, True, ACCENT)
            surf.blit(img, (px + 20, cy))
            cy += opt_h

    return (px, py, width, height)


def draw_title_screen(surf):
    """Full-screen title splash."""
    surf.fill(DARK_BG)
    lines = [
        ("CRAWL PROTOCOL",            ACCENT,      FONT_SIZE_XL, True),
        ("",                          NORMAL_TEXT, FONT_SIZE_MD, False),
        (tr("title_tagline_1"),       NORMAL_TEXT, FONT_SIZE_MD, False),
        (tr("title_tagline_2"),       DIM_TEXT,    FONT_SIZE_MD, False),
        (tr("title_tagline_3"),       DIM_TEXT,    FONT_SIZE_MD, False),
        ("",                          NORMAL_TEXT, FONT_SIZE_MD, False),
        (tr("title_build_character"), BRIGHT_TEXT, FONT_SIZE_LG, True),
        (tr("title_random_start"),    ACCENT,      FONT_SIZE_LG, True),
        (tr("title_load_game"),       BRIGHT_TEXT, FONT_SIZE_LG, True),
        (tr("title_how_to_play"),     BRIGHT_TEXT, FONT_SIZE_LG, True),
        (tr("title_quit"),            BRIGHT_TEXT, FONT_SIZE_LG, True),
    ]
    total_h = sum(get_font(size).get_height() + 6 for _, _, size, _ in lines)
    cy = (SCREEN_H - total_h) // 2 - 30
    for text, color, size, bold in lines:
        font = get_font(size, bold)
        img = font.render(text, True, color)
        surf.blit(img, ((SCREEN_W - img.get_width()) // 2, cy))
        cy += img.get_height() + 6

    hint = tr("title_press_15")
    hint_img = get_font(FONT_SIZE_SM).render(hint, True, DIM_TEXT)
    surf.blit(hint_img, ((SCREEN_W - hint_img.get_width()) // 2, cy + 10))

    # Language toggle hint (top-right corner)
    from lang import get_language, lang_label
    lang_str = f"{tr('title_toggle_lang')}   [ {lang_label(get_language())} ]"
    lang_img = get_font(FONT_SIZE_SM).render(lang_str, True, ACCENT2)
    surf.blit(lang_img, (SCREEN_W - lang_img.get_width() - 20, 20))

    tag = tr("title_syndicate_footer")
    draw_text(surf, tag, (SCREEN_W - get_font(FONT_SIZE_SM).size(tag)[0]) // 2,
              SCREEN_H - 30, DIM_TEXT, FONT_SIZE_SM)


def draw_race_pick(surf, data):
    """Render the race selection screen. data = {"races": [Race,...]}."""
    races = data.get("races", [])
    lines = [tr("race_pick_intro"), ""]
    for i, r in enumerate(races, 1):
        lines.append(f"  [{i}] {r.name}")
        lines.append(f"       {r.description}")
        lines.append(f"       {r.passive_description}")
    lines.append("")
    lines.append(tr("race_pick_choose", n=len(races)))
    draw_popup(surf, tr("race_pick_title"), lines, width=900, height=None)


def draw_dialog(surf, npc, node):
    """Render an NPC dialog popup."""
    # Translate disposition/archetype labels
    arch = tr(f"arch_{npc.archetype}")
    dispo = tr(f"dispo_{npc.disposition}")
    header = tr("dialog_npc_appears", name=npc.name, arch=arch, dispo=dispo)

    lines = [header, "", f"  \"{node.get('say','...')}\"", ""]
    for i, (label, _) in enumerate(node.get("options", []), 1):
        lines.append(f"  [{i}] {label}")
    lines.append("")
    lines.append(tr("dialog_choose"))

    draw_popup(surf, "DIALOG", lines, width=700)


def draw_intro_screen(surf, player, backstory, page=0):
    """
    Two-page intro sequence.
    Page 0: backstory narrative text + Syndicate intake note.
    Page 1: character sheet with starting gear summary.
    """
    surf.fill(DARK_BG)

    if backstory is None:
        backstory = {
            "paragraphs": ["You are here. That is all that is known."],
            "intake_note": "INTAKE NOTE: Unknown origin. Participation confirmed.",
            "gear_keys": [],
        }

    font_lg = get_font(FONT_SIZE_LG, bold=True)
    font_md = get_font(FONT_SIZE_MD)
    font_sm = get_font(FONT_SIZE_SM)
    line_h_md = font_md.get_height() + 5
    line_h_sm = font_sm.get_height() + 3

    if page == 0:
        # ── Story page ─────────────────────────────────────────────────────────
        # Header bar
        pygame.draw.rect(surf, PANEL_BG, (0, 0, SCREEN_W, 60))
        pygame.draw.line(surf, ACCENT, (0, 60), (SCREEN_W, 60), 1)

        # Syndicate classification header
        class_tag = f"CONTESTANT FILE  //  {player.name.upper()}  //  BACKGROUND: {player.background.upper()}"
        draw_text(surf, class_tag, 40, 18, ACCENT, FONT_SIZE_SM, bold=True)

        # Redacted-style decorations
        draw_text(surf, "SYNDICATE INTAKE DIVISION  //  CONFIDENTIAL", SCREEN_W - 420, 18, DIM_TEXT, FONT_SIZE_SM)

        cy = 90
        # Narrative paragraphs
        paragraphs = backstory.get("paragraphs", [])
        for para in paragraphs:
            if para == "":
                cy += line_h_md // 2
                continue
            img = font_md.render(para, True, NORMAL_TEXT)
            surf.blit(img, (80, cy))
            cy += line_h_md

        cy += 20
        pygame.draw.line(surf, BORDER, (80, cy), (SCREEN_W - 80, cy), 1)
        cy += 14

        # Intake note
        note = backstory.get("intake_note", "")
        draw_text(surf, note, 80, cy, ACCENT2, FONT_SIZE_SM, bold=True)
        cy += line_h_sm + 4

        # Syndicate sign-off
        draw_text(surf, "Processing complete. Contestant added to broadcast schedule.", 80, cy, DIM_TEXT, FONT_SIZE_SM)

        # Page prompt bottom
        pygame.draw.rect(surf, PANEL_BG, (0, SCREEN_H - 50, SCREEN_W, 50))
        pygame.draw.line(surf, BORDER, (0, SCREEN_H - 50), (SCREEN_W, SCREEN_H - 50), 1)
        draw_text(surf, "[Enter / Space]  Continue to loadout", 40, SCREEN_H - 34, DIM_TEXT, FONT_SIZE_SM)
        draw_text(surf, "Page 1 / 2", SCREEN_W - 120, SCREEN_H - 34, DIM_TEXT, FONT_SIZE_SM)

    else:
        # ── Gear / character summary page ─────────────────────────────────────
        pygame.draw.rect(surf, PANEL_BG, (0, 0, SCREEN_W, 60))
        pygame.draw.line(surf, ACCENT, (0, 60), (SCREEN_W, 60), 1)
        draw_text(surf, f"CONTESTANT LOADOUT  //  {player.name.upper()}", 40, 18, ACCENT, FONT_SIZE_SM, bold=True)

        cx_left  = 80
        cx_right = SCREEN_W // 2 + 40
        cy = 80

        # Left column: stats
        draw_text(surf, "STATS", cx_left, cy, ACCENT, FONT_SIZE_MD, bold=True)
        cy += line_h_md
        from utils import ability_modifier
        from config import BASE_STATS
        for stat in BASE_STATS:
            val = player.stats.get(stat, 10)
            mod = ability_modifier(val)
            sign = "+" if mod >= 0 else ""
            draw_text(surf, f"  {stat}  {val:2d}  ({sign}{mod})", cx_left, cy, NORMAL_TEXT, FONT_SIZE_MD)
            cy += line_h_md

        cy += 8
        draw_text(surf, f"HP   {player.hp}/{player.max_hp}", cx_left, cy, SUCCESS, FONT_SIZE_MD)
        cy += line_h_md
        draw_text(surf, f"AC   {player.effective_ac()}", cx_left, cy, NORMAL_TEXT, FONT_SIZE_MD)
        cy += line_h_md
        draw_text(surf, f"CR   {player.credits}", cx_left, cy, GOLD_COLOR, FONT_SIZE_MD)

        # Right column: gear
        cy_r = 80
        draw_text(surf, "STARTING GEAR", cx_right, cy_r, ACCENT, FONT_SIZE_MD, bold=True)
        cy_r += line_h_md

        def gear_row(label, item, cy_r):
            if item:
                draw_text(surf, f"  {label}", cx_right, cy_r, DIM_TEXT, FONT_SIZE_SM)
                cy_r += line_h_sm
                draw_text(surf, f"  {item.display()}", cx_right + 10, cy_r, NORMAL_TEXT, FONT_SIZE_MD)
                cy_r += line_h_md
                desc = getattr(item, 'description', '')
                if desc:
                    draw_text(surf, f"  {desc}", cx_right + 10, cy_r, DIM_TEXT, FONT_SIZE_SM)
                    cy_r += line_h_sm
                cy_r += 6
            return cy_r

        cy_r = gear_row("WEAPON", player.weapon, cy_r)
        cy_r = gear_row("ARMOR", player.armor, cy_r)
        cy_r = gear_row("TRINKET", player.trinket, cy_r)

        if player.inventory:
            draw_text(surf, "  BAG:", cx_right, cy_r, DIM_TEXT, FONT_SIZE_SM)
            cy_r += line_h_sm
            for item in player.inventory:
                if hasattr(item, 'display'):
                    draw_text(surf, f"    {item.display()}", cx_right + 10, cy_r, NORMAL_TEXT, FONT_SIZE_SM)
                    cy_r += line_h_sm

        # Background perk
        from character import BACKGROUNDS
        bg = BACKGROUNDS.get(player.background, {})
        perk_desc = bg.get("perk_desc", "")
        if perk_desc:
            cy_r += 10
            draw_text(surf, "BACKGROUND PERK", cx_right, cy_r, ACCENT, FONT_SIZE_SM, bold=True)
            cy_r += line_h_sm
            draw_text(surf, f"  {perk_desc}", cx_right, cy_r, NORMAL_TEXT, FONT_SIZE_SM)

        # Prompt
        pygame.draw.rect(surf, PANEL_BG, (0, SCREEN_H - 50, SCREEN_W, 50))
        pygame.draw.line(surf, BORDER, (0, SCREEN_H - 50), (SCREEN_W, SCREEN_H - 50), 1)
        draw_text(surf, "[Enter / Space]  Begin the Crawl", 40, SCREEN_H - 34, SUCCESS, FONT_SIZE_SM, bold=True)
        draw_text(surf, "Page 2 / 2", SCREEN_W - 120, SCREEN_H - 34, DIM_TEXT, FONT_SIZE_SM)


def draw_char_creation(surf, state):
    """Character creation screen — fully localized."""
    surf.fill(DARK_BG)
    draw_text(surf, tr("create_title"),    40, 20, ACCENT, FONT_SIZE_XL, bold=True)
    draw_text(surf, tr("create_subtitle"), 40, 50, DIM_TEXT, FONT_SIZE_SM)

    step = state.get("step", "name")

    if step == "name":
        draw_text(surf, tr("create_enter_name"), 100, 200, NORMAL_TEXT, FONT_SIZE_LG)
        name = state.get("name_input", "")
        pygame.draw.rect(surf, INPUT_BG, (100, 240, 400, 40))
        pygame.draw.rect(surf, ACCENT, (100, 240, 400, 40), 2)
        draw_text(surf, name + "|", 110, 252, BRIGHT_TEXT, FONT_SIZE_LG)
        draw_text(surf, tr("common_enter_to_continue"), 100, 300, DIM_TEXT, FONT_SIZE_SM)

    elif step == "background":
        from character import BACKGROUNDS
        draw_text(surf, tr("create_select_bg"), 60, 100, NORMAL_TEXT, FONT_SIZE_LG)
        selected = state.get("selected_bg", 0)
        bg_keys = list(BACKGROUNDS.keys())
        for i, key in enumerate(bg_keys):
            bg = BACKGROUNDS[key]
            color = ACCENT if i == selected else NORMAL_TEXT
            y_pos = 140 + i * 44
            # Background names are localized via bg_<key>_n, descriptions via _d
            label = tr(f"bg_{key.lower()}_n")
            desc  = tr(f"bg_{key.lower()}_d")
            # Fallback: if localization missing, use the catalog English
            if label == f"bg_{key.lower()}_n":
                label = key
            if desc == f"bg_{key.lower()}_d":
                desc = bg.get("desc", "")
            draw_text(surf, f"[{i+1}] {label}", 80, y_pos, color, FONT_SIZE_MD, bold=(i == selected))
            draw_text(surf, desc, 80, y_pos + 18, DIM_TEXT, FONT_SIZE_SM)
        draw_text(surf, tr("create_keys_bg"), 80, SCREEN_H - 50, DIM_TEXT, FONT_SIZE_SM)

    elif step == "stats":
        from config import BASE_STATS, STAT_COST
        pool = state.get("point_pool", 27)
        stats = state.get("stats", {s: 8 for s in BASE_STATS})
        cursor = state.get("cursor", 0)

        draw_text(surf, tr("create_assign_stats"), 60, 100, NORMAL_TEXT, FONT_SIZE_LG)
        draw_text(surf, tr("create_points_left", pool=pool), 60, 130, ACCENT, FONT_SIZE_MD)

        for i, stat in enumerate(BASE_STATS):
            val = stats[stat]
            mod = ability_modifier(val)
            sign = "+" if mod >= 0 else ""
            color = ACCENT if i == cursor else NORMAL_TEXT
            y_pos = 170 + i * 44
            cost = STAT_COST.get(val + 1, 99)
            draw_text(surf, f"{stat}:", 80, y_pos, color, FONT_SIZE_MD, bold=(i == cursor))
            draw_text(surf, f"{val}  ({sign}{mod})", 160, y_pos, color, FONT_SIZE_LG, bold=(i == cursor))
            draw_text(surf, tr("create_cost_label", cost=cost), 260, y_pos + 4, DIM_TEXT, FONT_SIZE_SM)

        draw_text(surf, tr("create_keys_stats"), 60, SCREEN_H - 50, DIM_TEXT, FONT_SIZE_SM)
        draw_text(surf, tr("create_min_max"),    60, SCREEN_H - 70, DIM_TEXT, FONT_SIZE_SM)

    elif step == "confirm":
        from character import BACKGROUNDS
        bg_key = state.get("background_key", "Drifter")
        bg = BACKGROUNDS.get(bg_key, {})
        name = state.get("name", "Unknown")
        stats = state.get("stats", {})
        draw_text(surf, tr("create_confirm"), 60, 100, NORMAL_TEXT, FONT_SIZE_LG)
        draw_text(surf, f"{tr('create_name_label')} {name}",    80, 150, BRIGHT_TEXT, FONT_SIZE_MD)
        bg_label = tr(f"bg_{bg_key.lower()}_n")
        if bg_label == f"bg_{bg_key.lower()}_n":
            bg_label = bg_key
        draw_text(surf, f"{tr('create_bg_label')} {bg_label}",   80, 180, BRIGHT_TEXT, FONT_SIZE_MD)
        perk_desc = tr(f"bg_{bg_key.lower()}_perk_d")
        if perk_desc == f"bg_{bg_key.lower()}_perk_d":
            perk_desc = bg.get("perk_desc", "")
        draw_text(surf, f"{tr('create_perk_label')} {perk_desc}", 80, 200, DIM_TEXT, FONT_SIZE_SM)
        y_s = 240
        for stat, val in stats.items():
            mod = ability_modifier(val)
            bonus = bg.get("stat_bonus", {}).get(stat, 0)
            final = val + bonus
            final_mod = ability_modifier(final)
            fsign = "+" if final_mod >= 0 else ""
            draw_text(surf, f"{stat}: {val} + {bonus} bg = {final} ({fsign}{final_mod})",
                      80, y_s, NORMAL_TEXT, FONT_SIZE_SM)
            y_s += 22
        draw_text(surf, tr("create_keys_confirm"), 80, SCREEN_H - 50, DIM_TEXT, FONT_SIZE_SM)


def draw_victory_screen(surf, player):
    surf.fill(DARK_BG)
    draw_text(surf, tr("victory_title"), SCREEN_W // 2 - 280, 200, SUCCESS, FONT_SIZE_XL, bold=True)
    draw_text(surf, tr("victory_survived", name=player.name), 300, 280, NORMAL_TEXT, FONT_SIZE_LG)
    draw_text(surf, tr("victory_level",   level=player.level), 320, 330, ACCENT, FONT_SIZE_MD)
    draw_text(surf, tr("victory_rating",
                       rating=player.audience_rating,
                       label=rating_label(player.audience_rating)),
              320, 360, ACCENT, FONT_SIZE_MD)
    draw_text(surf, tr("victory_credits", cr=player.credits), 320, 390, ACCENT, FONT_SIZE_MD)
    draw_text(surf, tr("victory_rooms",   rooms=player.rooms_cleared), 320, 420, ACCENT, FONT_SIZE_MD)
    draw_text(surf, tr("victory_flavor1"), 320, 470, DIM_TEXT, FONT_SIZE_MD)
    draw_text(surf, tr("victory_flavor2"), 320, 500, DIM_TEXT, FONT_SIZE_SM)
    draw_text(surf, tr("victory_return"),  320, 580, DIM_TEXT, FONT_SIZE_SM)


def draw_defeat_screen(surf, player):
    surf.fill(DARK_BG)
    draw_text(surf, tr("defeat_title"), SCREEN_W // 2 - 250, 200, DANGER, FONT_SIZE_XL, bold=True)
    draw_text(surf, tr("defeat_died", name=player.name), 300, 280, NORMAL_TEXT, FONT_SIZE_LG)
    draw_text(surf, tr("defeat_level",   level=player.level),         320, 330, WARN, FONT_SIZE_MD)
    draw_text(surf, tr("defeat_floor",   floor=player.current_floor), 320, 360, WARN, FONT_SIZE_MD)
    draw_text(surf, tr("defeat_rating",  rating=player.audience_rating), 320, 390, WARN, FONT_SIZE_MD)
    draw_text(surf, tr("defeat_credits", cr=player.credits),          320, 420, WARN, FONT_SIZE_MD)
    draw_text(surf, tr("defeat_flavor"), 300, 480, DIM_TEXT, FONT_SIZE_MD)
    draw_text(surf, tr("defeat_return"), 320, 560, DIM_TEXT, FONT_SIZE_SM)


def draw_howtoplay(surf):
    surf.fill(DARK_BG)
    draw_text(surf, tr("help_title"), 60, 30, ACCENT, FONT_SIZE_XL, bold=True)
    sections = [
        (tr("help_overview_h"), [tr("help_overview_1"), tr("help_overview_2")]),
        (tr("help_input_h"),    [tr("help_input_1"), tr("help_input_2"),
                                 tr("help_input_3"), tr("help_input_4")]),
        (tr("help_combat_h"),   [tr("help_combat_1"), tr("help_combat_2"),
                                 tr("help_combat_3"), tr("help_combat_4")]),
        (tr("help_classes_h"),  [tr("help_classes_1"), tr("help_classes_2"),
                                 tr("help_classes_3")]),
        (tr("help_explore_h"),  [tr("help_explore_1"), tr("help_explore_2"),
                                 tr("help_explore_3")]),
    ]
    cy = 80
    for title, lines in sections:
        draw_text(surf, title, 60, cy, ACCENT, FONT_SIZE_MD, bold=True)
        cy += get_font(FONT_SIZE_MD).get_height() + 4
        for line in lines:
            draw_text(surf, line, 80, cy, NORMAL_TEXT, FONT_SIZE_SM)
            cy += get_font(FONT_SIZE_SM).get_height() + 2
        cy += 10
    draw_text(surf, tr("help_back"), 60, SCREEN_H - 40, DIM_TEXT, FONT_SIZE_SM)


def draw_box_open(surf, tier, items):
    """Popup for box opening animation/reveal."""
    lines = [f"  {tier.upper()} {tr('box_opened_label')}", ""]
    if not items:
        lines.append(f"  {tr('box_empty')}")
    for item in items:
        if isinstance(item, tuple) and item[0] == "credits":
            lines.append(f"  + {item[1]} {tr('ui_credits')}")
        elif hasattr(item, "display"):
            lines.append(f"  + {item.display()}")
        else:
            lines.append(f"  + {item}")
    lines.append("")
    lines.append(f"  {tr('common_enter_to_continue')}")
    draw_popup(surf, f"{tier}", lines)


def draw_class_choice(surf, choices):
    """Popup for choosing a class from 3 options."""
    from character import CLASSES
    lines = [f"  {tr('popup_class_intro')}", f"  {tr('popup_class_choose')}", ""]
    options = []
    for i, key in enumerate(choices[:3]):
        cls = CLASSES.get(key, {})
        cls_name = tr(f"class_{key}_n")
        if cls_name == f"class_{key}_n":
            cls_name = cls.get("name", key)
        cls_desc = tr(f"class_{key}_d")
        if cls_desc == f"class_{key}_d":
            cls_desc = cls.get("desc", "")
        lines.append(f"  [{i+1}] {cls_name}")
        lines.append(f"       {cls_desc}")
        options.append((str(i + 1), cls_name))
    draw_popup(surf, tr("popup_class_title"), lines, options)


def draw_level_up(surf, player, new_level):
    lines = [
        f"  {tr('level_up_reached', level=new_level)}",
        f"  {tr('ui_hp')}: {player.max_hp}  Prof: +{player.prof()}",
        "",
        f"  {tr('common_enter_to_continue')}",
    ]
    draw_popup(surf, tr("level_up_title"), lines)


def draw_merchant(surf, player, stock, selected=0):
    surf.fill(DARK_BG)
    draw_panel(surf, (60, 60, SCREEN_W - 120, SCREEN_H - 120))
    draw_text(surf, tr("merchant_title"), 80, 80, ACCENT, FONT_SIZE_XL, bold=True)
    draw_text(surf, f"{tr('ui_credits')}: {player.credits}", 80, 120, GOLD_COLOR, FONT_SIZE_MD)
    draw_text(surf, tr("merchant_cut"), SCREEN_W - 320, 120, DIM_TEXT, FONT_SIZE_SM)

    cy = 160
    for i, (item, price) in enumerate(stock):
        color = ACCENT if i == selected else NORMAL_TEXT
        discount = player.trinket and player.trinket.passive == "merchant_10"
        final_price = int(price * 0.9) if discount else price
        tag = " (-10% Whisper Coin)" if discount else ""
        draw_text(surf, f"[{i+1}] {item.display()}  -  {final_price} CR{tag}", 80, cy, color, FONT_SIZE_MD, bold=(i == selected))
        cy += get_font(FONT_SIZE_MD).get_height() + 4

    cy += 20
    draw_text(surf, tr("merchant_sell"),  80, cy, DIM_TEXT, FONT_SIZE_SM); cy += 24
    draw_text(surf, tr("merchant_heal"),  80, cy, DIM_TEXT, FONT_SIZE_SM); cy += 24
    draw_text(surf, tr("merchant_keys"),  80, cy, DIM_TEXT, FONT_SIZE_SM)


def draw_inventory(surf, player, selected=0):
    surf.fill(DARK_BG)
    draw_panel(surf, (60, 60, SCREEN_W - 120, SCREEN_H - 120))
    draw_text(surf, tr("inv_title"), 80, 80, ACCENT, FONT_SIZE_XL, bold=True)
    draw_text(surf, f"{tr('ui_credits')}: {player.credits}", 80, 120, GOLD_COLOR, FONT_SIZE_MD)

    if not player.inventory:
        draw_text(surf, f"  {tr('common_empty')}", 80, 160, DIM_TEXT, FONT_SIZE_MD)
    else:
        cy = 160
        for i, item in enumerate(player.inventory):
            color = ACCENT if i == selected else NORMAL_TEXT
            if hasattr(item, "display"):
                draw_text(surf, f"[{i+1}] {item.display()}", 80, cy, color, FONT_SIZE_MD, bold=(i == selected))
            cy += get_font(FONT_SIZE_MD).get_height() + 4

    draw_text(surf, tr("inv_keys"), 80, SCREEN_H - 100, DIM_TEXT, FONT_SIZE_SM)


def draw_faction_hall(surf, faction_data, player):
    """Faction checkpoint interaction."""
    name, tag, desc = faction_data
    draw_panel(surf, (100, 80, SCREEN_W - 200, SCREEN_H - 160))
    draw_text(surf, f"{tr('faction_label')}: {name}", 120, 100, ACCENT2, FONT_SIZE_LG, bold=True)
    draw_text(surf, desc, 120, 138, NORMAL_TEXT, FONT_SIZE_MD)
    draw_text(surf, tr("faction_keys"), 120, 240, DIM_TEXT, FONT_SIZE_SM)
