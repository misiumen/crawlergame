"""Pygame UI for the revamp.

Three main layouts:
  - title menu
  - character creation
  - in-game (top bar / room panel / sidebar / log / input)
"""
import pygame

from ..config import (SCREEN_W, SCREEN_H, TOP_BAR_H, LOG_H, INPUT_H,
                     ROOM_PANEL_W, SIDEBAR_W,
                     DARK_BG, PANEL_BG, BORDER, DIM_TEXT, NORMAL_TEXT,
                     BRIGHT_TEXT, ACCENT, ACCENT2, WARN, DANGER, SUCCESS,
                     INPUT_BG, LOG_BG, LOG_COLORS, BASE_STATS)
from .lang import t, get_language, set_language
from ..engine.time_system import format_clock, format_deadline


_fonts = {}


def font(size=15, bold=False):
    key = (size, bold)
    if key not in _fonts:
        candidates = ["Consolas","Lucida Console","Courier New","DejaVu Sans Mono"]
        f = None
        for nm in candidates:
            try:
                f = pygame.font.SysFont(nm, size, bold=bold)
                if f is not None: break
            except Exception:
                continue
        _fonts[key] = f or pygame.font.Font(None, size + 4)
    return _fonts[key]


def text(surf, s, x, y, color=NORMAL_TEXT, size=15, bold=False):
    img = font(size, bold).render(str(s), True, color)
    surf.blit(img, (x, y))
    return img.get_height()


def text_wrapped(surf, s, x, y, max_w, color=NORMAL_TEXT, size=15):
    """Render wrapped text. Returns total height drawn."""
    f = font(size)
    line_h = f.get_height() + 3
    if not s:
        return 0
    words = s.split()
    lines = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        if f.size(candidate)[0] <= max_w:
            cur = candidate
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    cy = y
    for line in lines:
        img = f.render(line, True, color)
        surf.blit(img, (x, cy))
        cy += line_h
    return cy - y


def panel(surf, rect, bg=PANEL_BG, border=BORDER):
    pygame.draw.rect(surf, bg, rect)
    pygame.draw.rect(surf, border, rect, 1)


def hp_bar(surf, x, y, w, h, val, mx, color=SUCCESS):
    pygame.draw.rect(surf, (40,20,20), (x,y,w,h))
    if mx > 0:
        fill = int(w * val / mx)
        pygame.draw.rect(surf, color, (x,y,fill,h))
    pygame.draw.rect(surf, BORDER, (x,y,w,h), 1)


# ── Title ────────────────────────────────────────────────────────────────────

def draw_title(surf, save_exists: bool, selected_idx: int = 0):
    surf.fill(DARK_BG)
    sw, sh = surf.get_size()
    L = _resolve_layout(None)
    title_size = max(28, int(34 * L.font_scale))
    body_size  = max(14, int(15 * L.font_scale))
    item_size  = max(18, int(20 * L.font_scale))
    cy = sh // 2 - 140
    img = font(title_size, bold=True).render("Dungeon Kraulem", True, ACCENT)
    surf.blit(img, ((sw - img.get_width())//2, cy)); cy += img.get_height() + 4

    for line, col in [
        (t("title_tagline_1", fallback="Tabletopowe przeżycie w sponsorowanym lochu."), NORMAL_TEXT),
        (t("title_tagline_2", fallback="Każde piętro to wiele dni."), DIM_TEXT),
        (t("title_tagline_3", fallback="Każda decyzja kosztuje czas."), DIM_TEXT),
    ]:
        img = font(body_size).render(line, True, col)
        surf.blit(img, ((sw - img.get_width())//2, cy)); cy += 22

    cy += 30
    items = [
        (t("title_build_character", fallback="[1] Nowa gra"), BRIGHT_TEXT),
        (t("title_load_game",       fallback="[2] Wczytaj grę") if save_exists else
         t("title_load_disabled",   fallback="[2] Wczytaj grę (brak zapisu)"),
         BRIGHT_TEXT if save_exists else DIM_TEXT),
        (t("title_settings",        fallback="[3] Ustawienia"), BRIGHT_TEXT),
        (t("title_quit",            fallback="[4] Wyjdź"), BRIGHT_TEXT),
    ]
    sel = max(0, min(int(selected_idx or 0), len(items) - 1))
    for i, (label, col) in enumerate(items):
        if i == sel:
            label = "▶ " + label
            col = ACCENT
        img = font(item_size, bold=True).render(label, True, col)
        surf.blit(img, ((sw - img.get_width())//2, cy)); cy += 32

    cy += 16
    lang_str = f"[L] {t('lang_toggle_label', fallback='Język')}: {get_language().upper()}"
    img = font(body_size - 2).render(lang_str, True, ACCENT2)
    surf.blit(img, ((sw - img.get_width())//2, cy))

    footer = t("title_syndicate_footer", fallback="Syndykat patrzy. Protokół działa.")
    img = font(body_size - 3).render(footer, True, DIM_TEXT)
    surf.blit(img, ((sw - img.get_width())//2, sh - 30))


# ── Character creation ──────────────────────────────────────────────────────

def draw_creation(surf, state):
    surf.fill(DARK_BG)
    sw, sh = surf.get_size()
    L = _resolve_layout(None)
    title_size = max(20, int(24 * L.font_scale))
    body_size = max(14, int(16 * L.font_scale))
    small_size = max(11, int(13 * L.font_scale))
    text(surf, t("create_title", fallback="REJESTRACJA UCZESTNIKA"),
         40, 24, ACCENT, title_size, True)
    text(surf, t("create_subtitle", fallback="Dungeon Kraulem — Kontrakt zawodnika"),
         40, 54, DIM_TEXT, small_size)

    step = state.get("step", "name")
    if step == "name":
        text(surf, t("create_enter_name", fallback="Wpisz imię (lub pseudonim):"),
             80, 160, NORMAL_TEXT, body_size + 2)
        pygame.draw.rect(surf, INPUT_BG, (80, 200, 400, 40))
        pygame.draw.rect(surf, ACCENT, (80, 200, 400, 40), 2)
        text(surf, state.get("name_input","") + "|", 90, 212, BRIGHT_TEXT, body_size + 2)
        text(surf, t("create_hint_name",
                     fallback="[Enter] Dalej   [Esc] Powrót"),
             80, 260, DIM_TEXT, small_size)
    elif step == "background":
        text(surf, t("create_select_bg", fallback="Wybierz tło (nie klasę):"),
             60, 100, NORMAL_TEXT, body_size + 2)
        # Prompt 19 audit fix S2: single source from engine.character.
        from ..engine.character import BACKGROUNDS
        bgs = list(BACKGROUNDS)
        sel = state.get("selected_bg", 0)
        cy = 140
        for i, key in enumerate(bgs):
            col = ACCENT if i == sel else NORMAL_TEXT
            label = t(f"bg_{key}_n", fallback=key)
            marker = "▶ " if i == sel else "  "
            text(surf, f"{marker}[{i+1:2d}] {label}", 80, cy, col,
                 body_size, bold=(i==sel)); cy += 22
            desc = t(f"bg_{key}_d", fallback="")
            if desc:
                text(surf, "        " + desc, 80, cy, DIM_TEXT, small_size - 1); cy += 18
        text(surf, t("create_keys_bg",
                     fallback="[1-9/0/↑↓] Wybierz   [Enter] Potwierdź   [Esc] Wstecz"),
             80, sh - 40, DIM_TEXT, small_size)


# ── In-game ─────────────────────────────────────────────────────────────────

def _resolve_layout(layout):
    """Return a Layout — accept either an explicit Layout or compute one
    from the current pygame surface size."""
    if layout is not None:
        return layout
    from . import layout as _L
    surf = pygame.display.get_surface()
    if surf is not None:
        w, h = surf.get_size()
    else:
        w, h = SCREEN_W, SCREEN_H
    return _L.calculate_layout(w, h)


def draw_topbar(surf, world, layout=None):
    L = _resolve_layout(layout)
    rect = L.top_bar_rect
    panel(surf, rect)
    x, y, w, h = rect
    f = world.current_floor
    if f is None: return
    title = t(f.title_key, fallback=f.title_fallback)
    text(surf, title, x + 12, y + 8, ACCENT, L.font_title - 4, True)
    # Prompt 18: show sponsor NAME + the player's mood with that
    # sponsor, so the player has a constant visible signal of who's
    # watching and how they feel about it.
    sponsor_label = t(f.sponsor_key, fallback=f.sponsor_fallback)
    try:
        from ..engine import sponsors as _sp
        sk = _sp.current_floor_sponsor_key(world)
        if sk:
            # Prompt 19 audit fix N2: strip a trailing period from the
            # sponsor line before appending the mood, so we don't get
            # "Sponsoruje: NovaChem Biotech. — życzliwy" with a stray
            # full-stop floating in the middle.
            base = sponsor_label.rstrip().rstrip(".").rstrip()
            mood = _sp.sponsor_mood(world, sk)
            sponsor_label = f"{base} — {mood}"
    except Exception:
        pass
    text(surf, sponsor_label, x + 12, y + 32, DIM_TEXT, L.font_small - 1)
    # Clock + deadline
    clock = format_clock(world)
    deadline = format_deadline(world)
    s = f"{t('ui_clock', fallback='Zegar')}: {clock}   {t('ui_deadline', fallback='Termin')}: {deadline}"
    img = font(L.font_small + 1).render(s, True, BRIGHT_TEXT)
    surf.blit(img, (x + w - img.get_width() - 16, y + 14))
    # Prompt 18: replace raw audience number with BAND label + rating.
    # The number stays visible (small) so power-players still see it.
    try:
        from ..engine import audience as _aud
        rating = int(world.character.audience_rating or 0)
        band = _aud.band_for(rating)
        band_label = _aud.band_label(band)
        aud = (f"{t('ui_audience', fallback='Widownia')}: "
               f"{band_label} ({rating})")
    except Exception:
        aud = f"{t('ui_audience', fallback='Widownia')}: {world.character.audience_rating}"
    img = font(L.font_small - 1).render(aud, True, WARN)
    surf.blit(img, (x + w - img.get_width() - 16, y + 36))


def draw_room_panel(surf, world, layout=None):
    L = _resolve_layout(layout)
    x, y, w, h = L.room_rect
    panel(surf, (x, y, w, h))
    f = world.current_floor
    if f is None: return
    room = f.current_room()
    if room is None: return

    text(surf, room.display_title(), x + 14, y + 12, ACCENT2, L.font_title - 4, True)
    desc = room.display_first_enter() if room.last_visited_minute == f.current_minute else room.display_look()
    cy = y + 42
    # Cap wrap width — at ultrawide the room column already has a
    # comfortable max width, but compact resolutions get the full panel.
    wrap_w = min(w - 28, 900)
    cy += text_wrapped(surf, desc, x + 14, cy, wrap_w, NORMAL_TEXT, L.font_body - 1)
    cy += 8

    visible = room.visible_entities()
    if visible:
        text(surf, t("ui_visible", fallback="Widzisz:"), x + 14, cy, ACCENT,
             L.font_small, True); cy += 18
        for e in visible:
            name = e.display_name()
            tag = ""
            if e.entity_type == "monster":   tag = " ⚔"
            elif e.entity_type == "crawler": tag = " ☻"
            elif e.entity_type == "hazard":  tag = " ⚠"
            text(surf, f"  • {name}{tag}", x + 16, cy, NORMAL_TEXT, L.font_small); cy += 16
            if cy > y + h - 80: break

    if room.exits:
        cy += 6
        text(surf, t("ui_exits", fallback="Wyjścia:"), x + 14, cy, ACCENT,
             L.font_small, True); cy += 18
        for label, ed in room.exits.items():
            target_id = ed.get("target","")
            target = f.rooms.get(target_id)
            target_name = target.display_short_title() if target else "?"
            lock = "🔒" if ed.get("locked") else ""
            hint = ed.get("fallback_hint") or t(ed.get("hint_key",""), fallback="")
            line = f"  → {label}  ({target_name}) {lock}"
            text(surf, line, x + 16, cy, NORMAL_TEXT, L.font_small); cy += 16
            if hint:
                text(surf, f"      {hint}", x + 16, cy, DIM_TEXT, L.font_small - 1); cy += 14
            if cy > y + h - 30: break


def draw_sidebar(surf, world, layout=None):
    """Right column: character status + stats + conditions. The map / known
    rooms / clues list lives in the left sidebar on ultrawide, or stays
    here on compact/wide."""
    L = _resolve_layout(layout)
    x, y, w, h = L.right_sidebar_rect
    panel(surf, (x, y, w, h))
    c = world.character
    cy = y + 12
    text(surf, c.name or "—", x + 14, cy, BRIGHT_TEXT, L.font_title - 4, True); cy += 24
    text(surf, t(f"bg_{c.background}_n", fallback=c.background),
         x + 14, cy, ACCENT2, L.font_small); cy += 18
    if c.class_key:
        text(surf, t(f"class_{c.class_key}_n", fallback=c.class_key),
             x + 14, cy, ACCENT, L.font_small); cy += 18
    if c.species_key and c.species_key != "baseline_human":
        text(surf, t(f"species_{c.species_key}_n", fallback=c.species_key),
             x + 14, cy, ACCENT, L.font_small - 1); cy += 16
    cy += 4
    hp_bar(surf, x + 14, cy, w - 28, 14, c.hp, c.max_hp); cy += 18
    text(surf, f"HP {c.hp}/{c.max_hp}   AC {c.effective_ac()}   "
               f"{t('ui_credits', fallback='Kr')} {c.credits}",
         x + 14, cy, NORMAL_TEXT, L.font_small); cy += 22

    text(surf, t("ui_stats", fallback="Statystyki"), x + 14, cy, ACCENT,
         L.font_small, True); cy += 16
    for stat in BASE_STATS:
        v = c.stats.get(stat, 10); mod = c.stat_mod(stat); s = "+" if mod >= 0 else ""
        text(surf, f"  {stat}: {v:2d} ({s}{mod})", x + 14, cy, NORMAL_TEXT,
             L.font_small - 1); cy += 14

    if c.conditions:
        cy += 4
        text(surf, "Status: " + ", ".join(c.conditions), x + 14, cy, DANGER,
             L.font_small - 1); cy += 16

    # On compact/wide layouts, the map / known rooms also live here. On
    # ultrawide, draw_left_sidebar handles them and we leave this column
    # for character details + inventory/material/belief summaries.
    if not L.has_left_sidebar:
        f = world.current_floor
        if f:
            cy += 8
            text(surf, t("ui_known_rooms", fallback="Znane pokoje"),
                 x + 14, cy, ACCENT, L.font_small, True); cy += 16
            for rid in sorted(f.discovered_room_ids):
                r = f.rooms.get(rid)
                if r is None: continue
                mark = "@" if rid == f.current_room_id else "·"
                text(surf, f"  {mark} {r.display_short_title()}",
                     x + 14, cy, NORMAL_TEXT, L.font_small - 1); cy += 14
                if cy > y + h - 24: break
    else:
        # Ultrawide: show inventory + materials summary as right-column extras.
        cy += 8
        text(surf, t("ui_inv_header", fallback="W plecaku:"),
             x + 14, cy, ACCENT, L.font_small, True); cy += 16
        for eid in (c.inventory_ids or [])[:8]:
            ent = world.entities.get(eid)
            if ent is None: continue
            text(surf, f"  • {ent.display_name()}",
                 x + 14, cy, NORMAL_TEXT, L.font_small - 1); cy += 14
            if cy > y + h - 80: break
        # Materials count summary — resolve player-facing Polish names
        # via the materials registry; never leak raw internal keys.
        mats = (c.materials or {})
        if mats:
            cy += 6
            text(surf, t("ui_materials_header", fallback="Materiały:"),
                 x + 14, cy, ACCENT, L.font_small, True); cy += 16
            from ..content import materials as _mat
            shown = 0
            for k, v in mats.items():
                md = _mat.get(k)
                display = md.name() if md is not None else k.replace("_", " ")
                text(surf, f"  {v}× {display}", x + 14, cy, NORMAL_TEXT,
                     L.font_small - 1); cy += 14
                shown += 1
                if shown >= 6 or cy > y + h - 24: break


def draw_left_sidebar(surf, world, layout=None):
    """Ultrawide-only left column: map / known rooms / clue summary."""
    L = _resolve_layout(layout)
    if not L.has_left_sidebar:
        return
    x, y, w, h = L.left_sidebar_rect
    panel(surf, (x, y, w, h))
    f = world.current_floor
    if f is None:
        return
    cy = y + 12
    text(surf, t("ui_known_rooms", fallback="Znane pokoje"),
         x + 14, cy, ACCENT, L.font_small, True); cy += 18
    for rid in sorted(f.discovered_room_ids):
        r = f.rooms.get(rid)
        if r is None: continue
        mark = "@" if rid == f.current_room_id else "·"
        text(surf, f"  {mark} {r.display_short_title()}",
             x + 14, cy, NORMAL_TEXT, L.font_small - 1); cy += 14
        if cy > y + h // 2: break

    # Objective summary
    cy += 12
    if f.objective_key:
        text(surf, t("ui_objective", fallback="Cel piętra"),
             x + 14, cy, ACCENT, L.font_small, True); cy += 16
        txt = f.objective_title_fallback or f.objective_key
        cy += text_wrapped(surf, txt, x + 14, cy, w - 28, NORMAL_TEXT,
                           L.font_small - 1)

    # Active clue / fact summary
    try:
        from ..systems import knowledge
        kc = (world.known_clues or {})
        if kc:
            cy += 12
            text(surf, t("ui_clue_summary", fallback="Wskazówki"),
                 x + 14, cy, ACCENT, L.font_small, True); cy += 16
            for entry in list(kc.values())[-6:]:
                title = entry.get("title") or entry.get("key") or "?"
                text(surf, f"  • {title}", x + 14, cy, NORMAL_TEXT,
                     L.font_small - 1); cy += 14
                if cy > y + h - 24: break
    except Exception:
        pass


def draw_log_and_input(surf, log, input_text, blink, scroll=0,
                       input_mode="text", layout=None):
    L = _resolve_layout(layout)
    # Log
    lx, ly, lw, lh = L.log_rect
    panel(surf, (lx, ly, lw, lh), bg=LOG_BG)
    text(surf, t("log_broadcast", fallback="DZIENNIK"),
         lx + 10, ly + 4, ACCENT, L.font_small, True)
    f = font(L.font_small)
    line_h = f.get_height() + 2
    max_lines = (lh - 22) // line_h
    visible = log[-(max_lines + scroll): len(log) - scroll if scroll else None]
    if not visible: visible = log[-max_lines:]
    cy = ly + 22
    for s, cat in visible[-max_lines:]:
        col = LOG_COLORS.get(cat, NORMAL_TEXT)
        max_w = lw - 24
        for line in _soft_wrap(s, max_w, L.font_small):
            img = f.render(line, True, col)
            surf.blit(img, (lx + 12, cy))
            cy += line_h
            if cy > ly + lh - 4: break
        if cy > ly + lh - 4: break

    # Input
    ix, iy, iw, ih = L.input_rect
    pygame.draw.rect(surf, INPUT_BG, (ix, iy, iw, ih))
    border_col = ACCENT if input_mode == "text" else ACCENT2
    pygame.draw.rect(surf, border_col, (ix, iy, iw, ih), 1)
    if input_mode == "text":
        prompt = "> " + input_text + ("|" if blink else "")
        img = font(L.font_body + 1).render(prompt, True, BRIGHT_TEXT)
        surf.blit(img, (ix + 12, iy + (ih - img.get_height())//2))
        hint = t("ui_mode_text_hint",
                 fallback="Tryb: komendy tekstowe   [T] wybór   [Esc] wyczyść")
        himg = font(L.font_small - 2).render(hint, True, DIM_TEXT)
        surf.blit(himg, (ix + iw - himg.get_width() - 12,
                          iy + (ih - himg.get_height())//2))
    else:
        prompt = "[" + t("ui_mode_nav", fallback="Tryb: wybór opcji") + "]"
        img = font(L.font_body + 1).render(prompt, True, ACCENT2)
        surf.blit(img, (ix + 12, iy + (ih - img.get_height())//2))
        hint = t("ui_mode_nav_hint",
                 fallback="Góra/Dół wybór   Lewo/Prawo/Tab grupa   Enter zatwierdź   Esc / komendy")
        himg = font(L.font_small - 2).render(hint, True, DIM_TEXT)
        surf.blit(himg, (ix + iw - himg.get_width() - 12,
                          iy + (ih - himg.get_height())//2))


# ── Prompt 08/09: Navigation panel (option groups) ─────────────────────────

def draw_nav_panel(surf, nav_state, input_mode="text", layout=None):
    """Render the current group's option list. The nav rect comes from
    the Layout (anchored above the log), so it no longer overlays the
    sidebar regardless of resolution."""
    if nav_state is None or not getattr(nav_state, "groups", None):
        return
    L = _resolve_layout(layout)
    x, y, w, h = L.nav_rect
    panel(surf, (x, y, w, h))

    groups = list(nav_state.groups)
    cur = nav_state.current_group()
    header = t("ui_nav_header", fallback="Akcje i wybór")
    text(surf, header, x + 12, y + 6,
         ACCENT2 if input_mode == "nav" else DIM_TEXT,
         L.font_small, True)

    # Group tabs in a horizontal row at the top of the panel.
    cy = y + 26
    cx = x + 12
    from .ui_nav import group_label
    for g in groups:
        lbl = "[" + group_label(g) + "]"
        col = ACCENT if g == cur and input_mode == "nav" else \
              ACCENT2 if g == cur else DIM_TEXT
        img = font(L.font_small - 1, bold=g == cur).render(lbl, True, col)
        if cx + img.get_width() > x + w - 12:
            cy += 18
            cx = x + 12
        surf.blit(img, (cx, cy))
        cx += img.get_width() + 8
    cy += 22

    opts = nav_state.options_in(cur)
    if not opts:
        text(surf, t("ui_nav_no_options", fallback="(brak opcji)"),
             x + 14, cy, DIM_TEXT, L.font_small - 1)
        return
    sel_idx = nav_state.selected_index(cur)

    # Multi-column option list — at wider resolutions we get two columns.
    n = len(opts)
    col_count = 1
    col_w = w - 24
    if w >= 1200:
        col_count = 2; col_w = (w - 36) // 2
    if w >= 2200:
        col_count = 3; col_w = (w - 48) // 3
    per_col = max(1, (n + col_count - 1) // col_count)

    line_h = font(L.font_small).get_height() + 2
    max_lines_per_col = max(1, (h - (cy - y) - 12) // line_h)
    visible_total = min(n, col_count * max_lines_per_col)
    visible = opts[:visible_total]

    f_opt = font(L.font_small)
    start_cy = cy
    for i, opt in enumerate(visible):
        col_idx = i // per_col
        row_idx = i % per_col
        ox = x + 12 + col_idx * col_w
        oy = start_cy + row_idx * line_h
        marker = "▶ " if (i == sel_idx and input_mode == "nav") else "  "
        col = (BRIGHT_TEXT if input_mode == "nav" and i == sel_idx
               else NORMAL_TEXT if opt.enabled else DIM_TEXT)
        line = marker + opt.label
        max_w = col_w - 12
        if f_opt.size(line)[0] > max_w:
            while line and f_opt.size(line + "…")[0] > max_w:
                line = line[:-1]
            line = line + "…"
        img = f_opt.render(line, True, col)
        surf.blit(img, (ox, oy))
    if n > len(visible):
        text(surf, f"  +{n - len(visible)} więcej…",
             x + 12, y + h - 18, DIM_TEXT, L.font_small - 2)


# ── Prompt 11: settings popup ─────────────────────────────────────────────

def draw_settings(surf, settings_state, save_exists=False):
    """Settings popup. Reuses font scaling but does not need a Layout."""
    from ..config import SUPPORTED_RESOLUTIONS
    surf.fill(DARK_BG)
    sw, sh = surf.get_size()
    L = _resolve_layout(None)
    title_size = max(22, int(28 * L.font_scale))
    body_size  = max(15, int(L.font_body + 2))
    small_size = max(12, int(L.font_small))

    # Header
    text(surf, t("settings_title", fallback="USTAWIENIA"),
         sw // 2 - 120, max(40, sh // 8), ACCENT, title_size, True)

    cy = max(120, sh // 4)
    row = settings_state.get("row", 0)
    res_idx = settings_state.get("res_idx", 0)
    fullscreen = settings_state.get("fullscreen", False)
    w_cur, h_cur = SUPPORTED_RESOLUTIONS[res_idx]

    # Prompt 13: LLM mode row.
    llm_idx = settings_state.get("llm_idx", 0)
    from . import settings as _settings
    llm_mode = _settings.LLM_MODES[llm_idx % len(_settings.LLM_MODES)]
    llm_label = {
        "performance": t("settings_llm_performance", fallback="Performance — bez modeli (najlżejszy)"),
        "enhanced":    t("settings_llm_enhanced",    fallback="Enhanced — parser + narrator"),
        "full_show":   t("settings_llm_full_show",   fallback="Full Show — narrator + loot + dialogi"),
    }.get(llm_mode, llm_mode)
    rows = [
        (t("settings_resolution", fallback="Rozdzielczość"),
         f"<  {w_cur} x {h_cur}  >"),
        (t("settings_display_mode", fallback="Tryb ekranu"),
         t("settings_fullscreen", fallback="Pełny ekran") if fullscreen
         else t("settings_windowed", fallback="Okno")),
        (t("settings_llm_mode", fallback="Tryb LLM"),
         f"<  {llm_label}  >"),
        (t("settings_apply", fallback="Zastosuj"), ""),
        (t("settings_back", fallback="Wróć"), ""),
    ]
    label_x = sw // 2 - 280
    value_x = sw // 2 + 20
    for i, (label, value) in enumerate(rows):
        is_sel = (i == row)
        col = ACCENT if is_sel else NORMAL_TEXT
        marker = "▶ " if is_sel else "  "
        text(surf, marker + label, label_x, cy, col, body_size, bold=is_sel)
        if value:
            text(surf, value, value_x, cy,
                 BRIGHT_TEXT if is_sel else NORMAL_TEXT, body_size, bold=is_sel)
        cy += 40

    # Footer help
    hint = t("settings_footer",
             fallback="Góra/Dół: wybór   Lewo/Prawo: zmień wartość   Enter: zastosuj   Esc: powrót")
    himg = font(small_size).render(hint, True, DIM_TEXT)
    surf.blit(himg, ((sw - himg.get_width()) // 2, sh - 50))


# ── Prompt 10: tabbed journal overlay ─────────────────────────────────────

def draw_journal(surf, world, j_state, layout=None):
    """Render the journal overlay on top of whatever the underlying state
    drew. j_state is a `journal.JournalState`."""
    if j_state is None or not j_state.open:
        return
    from . import journal as J
    L = _resolve_layout(layout)
    sw, sh = surf.get_size()

    # Dim the world behind the journal.
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 200))
    surf.blit(veil, (0, 0))

    # Journal panel — leaves a small margin to indicate "overlay" status.
    margin_x = max(24, int(sw * 0.04))
    margin_y = max(24, int(sh * 0.04))
    jx = margin_x
    jy = margin_y
    jw = sw - 2 * margin_x
    jh = sh - 2 * margin_y
    pygame.draw.rect(surf, PANEL_BG, (jx, jy, jw, jh))
    pygame.draw.rect(surf, ACCENT, (jx, jy, jw, jh), 2)

    # Header.
    fs = L.font_scale
    title_size = max(20, int(24 * fs))
    body_size  = max(14, int(L.font_body))
    small_size = max(12, int(L.font_small))

    text(surf, t("journal_header", fallback="DZIENNIK"),
         jx + 16, jy + 12, ACCENT, title_size, True)
    footer_help = t("journal_footer",
                    fallback="Lewo/Prawo lub Tab: zakładka   Góra/Dół: wybór   "
                             "PageUp/Dn: przewijaj   Enter: szczegóły   Esc: zamknij")
    fh_img = font(small_size - 2).render(footer_help, True, DIM_TEXT)
    surf.blit(fh_img, (jx + jw - fh_img.get_width() - 16, jy + jh - 28))

    # Tab bar (one row, wrapped to next row if needed).
    tab_y = jy + 48
    tab_x = jx + 16
    tab_h = max(28, int(28 * fs))
    f_tab = font(small_size)
    for k in J.TABS:
        lbl = J.tab_label(k)
        is_cur = (k == j_state.tab)
        col = ACCENT if is_cur else NORMAL_TEXT
        bg = ACCENT2 if is_cur else PANEL_BG
        pad = 12
        w = f_tab.size(lbl)[0] + pad * 2
        if tab_x + w > jx + jw - 16:
            tab_y += tab_h + 4
            tab_x = jx + 16
        rect = (tab_x, tab_y, w, tab_h)
        if is_cur:
            pygame.draw.rect(surf, ACCENT, rect)
            pygame.draw.rect(surf, BRIGHT_TEXT, rect, 1)
            img = f_tab.render(lbl, True, (10, 12, 18))
        else:
            pygame.draw.rect(surf, PANEL_BG, rect)
            pygame.draw.rect(surf, BORDER, rect, 1)
            img = f_tab.render(lbl, True, col)
        surf.blit(img, (tab_x + pad, tab_y + (tab_h - img.get_height())//2))
        tab_x += w + 6

    content_y = tab_y + tab_h + 14
    content_x = jx + 16
    content_w = jw - 32
    content_h = jy + jh - content_y - 40

    # Three-column inside the journal at ultrawide; two-column at wide; one-
    # column at compact. We split the inner content area only, regardless
    # of outer layout — so journal works at every resolution.
    if sw >= 2800:
        list_w   = int(content_w * 0.38)
        detail_w = content_w - list_w - 16
    elif sw >= 1500:
        list_w   = int(content_w * 0.50)
        detail_w = content_w - list_w - 16
    else:
        list_w   = content_w
        detail_w = 0

    entries = J.get_journal_entries(world, j_state.tab)
    sel_idx = j_state.selected()
    if entries:
        sel_idx = max(0, min(sel_idx, len(entries) - 1))
    j_state.set_selected(sel_idx)

    # Entry list panel.
    pygame.draw.rect(surf, INPUT_BG, (content_x, content_y, list_w, content_h))
    pygame.draw.rect(surf, BORDER,  (content_x, content_y, list_w, content_h), 1)
    if not entries:
        text(surf, J.empty_state(j_state.tab),
             content_x + 14, content_y + 12, DIM_TEXT, body_size - 1)
    else:
        line_h = max(20, body_size + 6)
        scroll = j_state.scroll()
        visible_lines = max(1, (content_h - 24) // line_h)
        first = max(0, min(scroll, max(0, len(entries) - visible_lines)))
        # Auto-scroll to keep selection visible.
        if sel_idx < first:
            first = sel_idx
        elif sel_idx >= first + visible_lines:
            first = sel_idx - visible_lines + 1
        j_state.scroll_by_tab[j_state.tab] = first
        for row, e in enumerate(entries[first:first + visible_lines]):
            idx = first + row
            row_y = content_y + 8 + row * line_h
            is_sel = (idx == sel_idx)
            if is_sel:
                pygame.draw.rect(surf, ACCENT2,
                                 (content_x + 4, row_y - 2, list_w - 8, line_h),
                                 1)
            marker = "▶ " if is_sel else "  "
            line = marker + e.title
            f_b = font(body_size - 1)
            # Trim to fit
            max_w = list_w - 28
            if f_b.size(line)[0] > max_w:
                while line and f_b.size(line + "…")[0] > max_w:
                    line = line[:-1]
                line = line + "…"
            img = f_b.render(line,
                             True,
                             BRIGHT_TEXT if is_sel else NORMAL_TEXT)
            surf.blit(img, (content_x + 12, row_y + 2))
            # Status badge / subtitle on the right side of the row.
            badge = e.status or e.subtitle
            if badge:
                f_s = font(small_size - 1)
                bimg = f_s.render(badge, True,
                                  ACCENT if is_sel else DIM_TEXT)
                bx = content_x + list_w - bimg.get_width() - 10
                surf.blit(bimg, (bx, row_y + 4))

    # Detail panel.
    if detail_w > 0:
        dx = content_x + list_w + 16
        pygame.draw.rect(surf, INPUT_BG, (dx, content_y, detail_w, content_h))
        pygame.draw.rect(surf, BORDER,  (dx, content_y, detail_w, content_h), 1)
        if entries:
            sel = entries[sel_idx]
            # Header lines (title / subtitle / status) — pinned, not scrolled.
            header_y = content_y + 12
            text(surf, sel.title, dx + 12, header_y, ACCENT, body_size + 1, True)
            header_y += 26
            if sel.subtitle:
                text(surf, sel.subtitle, dx + 12, header_y, ACCENT2, small_size)
                header_y += 18
            if sel.status:
                text(surf, sel.status, dx + 12, header_y, BRIGHT_TEXT, small_size)
                header_y += 16
            header_y += 6
            wrap_w = detail_w - 24
            # Render the full body to a list of wrapped lines so we can
            # apply detail_scroll line-by-line.
            wrapped = _wrap_paragraphs(sel.detail or "", wrap_w, small_size + 1)
            line_h = font(small_size + 1).get_height() + 4
            avail = (content_y + content_h - header_y - 8) // line_h
            avail = max(1, avail)
            total = len(wrapped)
            max_scroll = max(0, total - avail)
            scroll = min(j_state.detail_scroll(), max_scroll)
            j_state.detail_scroll_by[(j_state.tab, sel_idx)] = scroll
            cy = header_y
            for line in wrapped[scroll:scroll + avail]:
                img = font(small_size + 1).render(line, True, NORMAL_TEXT)
                surf.blit(img, (dx + 12, cy))
                cy += line_h
            # Subtle scroll indicators.
            if scroll > 0:
                text(surf, "↑ więcej powyżej", dx + detail_w - 130,
                     header_y - 16, DIM_TEXT, small_size - 2)
            if scroll + avail < total:
                text(surf, "↓ więcej poniżej", dx + detail_w - 130,
                     content_y + content_h - 16, DIM_TEXT, small_size - 2)
        else:
            text(surf, J.empty_state(j_state.tab),
                 dx + 12, content_y + 12, DIM_TEXT, small_size)
    elif entries:
        # Compact: show selected entry detail beneath the list, with the
        # same scrollable body as the wide layout but a shorter strip.
        sel = entries[sel_idx]
        strip_h = max(120, int(content_h * 0.32))
        dy = content_y + content_h - strip_h
        pygame.draw.rect(surf, INPUT_BG, (content_x, dy, content_w, strip_h))
        pygame.draw.rect(surf, BORDER, (content_x, dy, content_w, strip_h), 1)
        header_y = dy + 6
        text(surf, sel.title, content_x + 10, header_y, ACCENT, small_size + 1, True)
        header_y += 22
        if sel.status:
            text(surf, sel.status, content_x + 10, header_y, BRIGHT_TEXT, small_size - 1)
            header_y += 16
        wrap_w = content_w - 24
        wrapped = _wrap_paragraphs(sel.detail or sel.body or sel.subtitle or "",
                                   wrap_w, small_size)
        line_h = font(small_size).get_height() + 4
        avail = max(1, (dy + strip_h - header_y - 6) // line_h)
        total = len(wrapped)
        max_scroll = max(0, total - avail)
        scroll = min(j_state.detail_scroll(), max_scroll)
        j_state.detail_scroll_by[(j_state.tab, sel_idx)] = scroll
        cy = header_y
        for line in wrapped[scroll:scroll + avail]:
            img = font(small_size).render(line, True, NORMAL_TEXT)
            surf.blit(img, (content_x + 10, cy))
            cy += line_h
        if scroll > 0:
            text(surf, "↑", content_x + content_w - 18, header_y - 14, DIM_TEXT, small_size - 2)
        if scroll + avail < total:
            text(surf, "↓", content_x + content_w - 18, dy + strip_h - 16, DIM_TEXT, small_size - 2)


def _wrap_paragraphs(text_str: str, max_w: int, size: int) -> list:
    """Wrap a multi-line text into a flat list of fitted lines."""
    if not text_str:
        return []
    out = []
    f = font(size)
    for para in text_str.split("\n"):
        if not para:
            out.append("")
            continue
        if f.size(para)[0] <= max_w:
            out.append(para); continue
        cur = ""
        for w in para.split():
            cand = (cur + " " + w).strip()
            if f.size(cand)[0] <= max_w:
                cur = cand
            else:
                if cur: out.append(cur)
                cur = w
        if cur: out.append(cur)
    return out


def _soft_wrap(s: str, max_w: int, size: int = 13):
    f = font(size)
    if f.size(s)[0] <= max_w:
        return [s]
    out = []
    words = s.split()
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if f.size(cand)[0] <= max_w:
            cur = cand
        else:
            if cur: out.append(cur)
            cur = w
    if cur: out.append(cur)
    return out
