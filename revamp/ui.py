"""Pygame UI for the revamp.

Three main layouts:
  - title menu
  - character creation
  - in-game (top bar / room panel / sidebar / log / input)
"""
import pygame

from .config import (SCREEN_W, SCREEN_H, TOP_BAR_H, LOG_H, INPUT_H,
                     ROOM_PANEL_W, SIDEBAR_W,
                     DARK_BG, PANEL_BG, BORDER, DIM_TEXT, NORMAL_TEXT,
                     BRIGHT_TEXT, ACCENT, ACCENT2, WARN, DANGER, SUCCESS,
                     INPUT_BG, LOG_BG, LOG_COLORS, BASE_STATS)
from .lang import t, get_language, set_language
from .time_system import format_clock, format_deadline


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

def draw_title(surf, save_exists: bool):
    surf.fill(DARK_BG)
    cx = SCREEN_W // 2
    cy = SCREEN_H // 2 - 100
    img = font(34, bold=True).render("CRAWL PROTOCOL", True, ACCENT)
    surf.blit(img, ((SCREEN_W - img.get_width())//2, cy)); cy += img.get_height() + 4

    for line, col in [
        (t("title_tagline_1", fallback="Tabletopowe przeżycie w sponsorowanym lochu."), NORMAL_TEXT),
        (t("title_tagline_2", fallback="Każde piętro to wiele dni."), DIM_TEXT),
        (t("title_tagline_3", fallback="Każda decyzja kosztuje czas."), DIM_TEXT),
    ]:
        img = font(15).render(line, True, col)
        surf.blit(img, ((SCREEN_W - img.get_width())//2, cy)); cy += 22

    cy += 30
    items = [
        (t("title_build_character", fallback="[1] Nowa gra"), BRIGHT_TEXT),
        (t("title_load_game",       fallback="[2] Wczytaj grę") if save_exists else
         t("title_load_disabled",   fallback="[2] Wczytaj grę (brak zapisu)"),
         BRIGHT_TEXT if save_exists else DIM_TEXT),
        (t("title_settings",        fallback="[3] Ustawienia"), BRIGHT_TEXT),
        (t("title_quit",            fallback="[4] Wyjdź"), BRIGHT_TEXT),
    ]
    for label, col in items:
        img = font(20, bold=True).render(label, True, col)
        surf.blit(img, ((SCREEN_W - img.get_width())//2, cy)); cy += 32

    cy += 16
    lang_str = f"[L] {t('lang_toggle_label', fallback='Język')}: {get_language().upper()}"
    img = font(13).render(lang_str, True, ACCENT2)
    surf.blit(img, ((SCREEN_W - img.get_width())//2, cy))

    footer = t("title_syndicate_footer", fallback="Syndykat patrzy. Protokół działa.")
    img = font(12).render(footer, True, DIM_TEXT)
    surf.blit(img, ((SCREEN_W - img.get_width())//2, SCREEN_H - 30))


# ── Character creation ──────────────────────────────────────────────────────

def draw_creation(surf, state):
    surf.fill(DARK_BG)
    text(surf, t("create_title", fallback="REJESTRACJA UCZESTNIKA"), 40, 24, ACCENT, 24, True)
    text(surf, t("create_subtitle", fallback="CRAWL PROTOCOL — Kontrakt zawodnika"), 40, 54, DIM_TEXT, 13)

    step = state.get("step", "name")
    if step == "name":
        text(surf, t("create_enter_name", fallback="Wpisz imię (lub pseudonim):"), 80, 160, NORMAL_TEXT, 18)
        pygame.draw.rect(surf, INPUT_BG, (80, 200, 400, 40))
        pygame.draw.rect(surf, ACCENT, (80, 200, 400, 40), 2)
        text(surf, state.get("name_input","") + "|", 90, 212, BRIGHT_TEXT, 18)
        text(surf, t("create_hint_name",
                     fallback="[Enter] Dalej   [Esc] Powrót"),
             80, 260, DIM_TEXT, 13)
    elif step == "background":
        text(surf, t("create_select_bg", fallback="Wybierz tło (nie klasę):"), 60, 100, NORMAL_TEXT, 18)
        from .data.entity_templates import MON  # arbitrary import to avoid circular
        bgs = ["office_worker","mechanic","nurse","cook","security_guard",
               "courier","student","streamer","soldier","unemployed_hustler",
               "janitor","paramedic"]
        sel = state.get("selected_bg", 0)
        cy = 140
        for i, key in enumerate(bgs):
            col = ACCENT if i == sel else NORMAL_TEXT
            label = t(f"bg_{key}_n", fallback=key)
            text(surf, f"[{i+1:2d}] {label}", 80, cy, col, 16, bold=(i==sel)); cy += 22
            desc = t(f"bg_{key}_d", fallback="")
            if desc:
                text(surf, "      " + desc, 80, cy, DIM_TEXT, 12); cy += 18
        text(surf, t("create_keys_bg",
                     fallback="[1-9/0] Wybierz   [Enter] Potwierdź   [Esc] Wstecz"),
             80, SCREEN_H - 40, DIM_TEXT, 13)


# ── In-game ─────────────────────────────────────────────────────────────────

def draw_topbar(surf, world):
    rect = (0, 0, SCREEN_W, TOP_BAR_H)
    panel(surf, rect)
    f = world.current_floor
    if f is None: return
    title = t(f.title_key, fallback=f.title_fallback)
    text(surf, title, 12, 8, ACCENT, 18, True)
    sponsor = t(f.sponsor_key, fallback=f.sponsor_fallback)
    text(surf, sponsor, 12, 32, DIM_TEXT, 12)
    # Clock + deadline
    clock = format_clock(world)
    deadline = format_deadline(world)
    s = f"{t('ui_clock', fallback='Zegar')}: {clock}   {t('ui_deadline', fallback='Termin')}: {deadline}"
    img = font(14).render(s, True, BRIGHT_TEXT)
    surf.blit(img, (SCREEN_W - img.get_width() - 16, 14))
    aud = f"{t('ui_audience', fallback='Widownia')}: {world.character.audience_rating}"
    img = font(12).render(aud, True, WARN)
    surf.blit(img, (SCREEN_W - img.get_width() - 16, 36))


def draw_room_panel(surf, world):
    x, y, w, h = 0, TOP_BAR_H, ROOM_PANEL_W, SCREEN_H - TOP_BAR_H - LOG_H - INPUT_H
    panel(surf, (x, y, w, h))
    f = world.current_floor
    if f is None: return
    room = f.current_room()
    if room is None: return

    # Room title
    text(surf, room.display_title(), x + 14, y + 12, ACCENT2, 18, True)

    # Description (first-enter on the first turn of arrival, then look_description after)
    desc = room.display_first_enter() if room.last_visited_minute == f.current_minute else room.display_look()
    cy = y + 42
    cy += text_wrapped(surf, desc, x + 14, cy, w - 28, NORMAL_TEXT, 14)
    cy += 8

    # Visible entities
    visible = room.visible_entities()
    if visible:
        text(surf, t("ui_visible", fallback="Widzisz:"), x + 14, cy, ACCENT, 13, True); cy += 18
        for e in visible:
            name = e.display_name()
            tag = ""
            if e.entity_type == "monster":   tag = " ⚔"
            elif e.entity_type == "crawler": tag = " ☻"
            elif e.entity_type == "hazard":  tag = " ⚠"
            text(surf, f"  • {name}{tag}", x + 16, cy, NORMAL_TEXT, 13); cy += 16
            if cy > y + h - 80: break

    # Exits
    if room.exits:
        cy += 6
        text(surf, t("ui_exits", fallback="Wyjścia:"), x + 14, cy, ACCENT, 13, True); cy += 18
        for label, ed in room.exits.items():
            target_id = ed.get("target","")
            target = f.rooms.get(target_id)
            target_name = target.display_short_title() if target else "?"
            lock = "🔒" if ed.get("locked") else ""
            hint = ed.get("fallback_hint") or t(ed.get("hint_key",""), fallback="")
            line = f"  → {label}  ({target_name}) {lock}"
            text(surf, line, x + 16, cy, NORMAL_TEXT, 13); cy += 16
            if hint:
                text(surf, f"      {hint}", x + 16, cy, DIM_TEXT, 12); cy += 14
            if cy > y + h - 30: break


def draw_sidebar(surf, world):
    x = ROOM_PANEL_W
    y = TOP_BAR_H
    w = SIDEBAR_W
    h = SCREEN_H - TOP_BAR_H - LOG_H - INPUT_H
    panel(surf, (x, y, w, h))
    c = world.character
    cy = y + 12
    text(surf, c.name or "—", x + 14, cy, BRIGHT_TEXT, 18, True); cy += 24
    text(surf, t(f"bg_{c.background}_n", fallback=c.background), x + 14, cy, ACCENT2, 13); cy += 18
    if c.class_key:
        text(surf, t(f"class_{c.class_key}_n", fallback=c.class_key), x + 14, cy, ACCENT, 13); cy += 18
    if c.species_key and c.species_key != "baseline_human":
        text(surf, t(f"species_{c.species_key}_n", fallback=c.species_key), x + 14, cy, ACCENT, 12); cy += 16
    cy += 4
    hp_bar(surf, x + 14, cy, w - 28, 14, c.hp, c.max_hp); cy += 18
    text(surf, f"HP {c.hp}/{c.max_hp}   AC {c.effective_ac()}   {t('ui_credits', fallback='Kr')} {c.credits}", x + 14, cy, NORMAL_TEXT, 13); cy += 22

    # Stats
    text(surf, t("ui_stats", fallback="Statystyki"), x + 14, cy, ACCENT, 13, True); cy += 16
    for stat in BASE_STATS:
        v = c.stats.get(stat, 10); mod = c.stat_mod(stat); s = "+" if mod >= 0 else ""
        text(surf, f"  {stat}: {v:2d} ({s}{mod})", x + 14, cy, NORMAL_TEXT, 12); cy += 14

    # Conditions
    if c.conditions:
        cy += 4
        text(surf, "Status: " + ", ".join(c.conditions), x + 14, cy, DANGER, 12); cy += 16

    # Map hints — discovered room titles
    f = world.current_floor
    if f:
        cy += 8
        text(surf, t("ui_known_rooms", fallback="Znane pokoje"), x + 14, cy, ACCENT, 13, True); cy += 16
        for rid in sorted(f.discovered_room_ids):
            r = f.rooms.get(rid)
            if r is None: continue
            mark = "@" if rid == f.current_room_id else "·"
            text(surf, f"  {mark} {r.display_short_title()}", x + 14, cy, NORMAL_TEXT, 12); cy += 14
            if cy > y + h - 24: break


def draw_log_and_input(surf, log, input_text, blink, scroll=0):
    # Log
    y = SCREEN_H - LOG_H - INPUT_H
    rect = (0, y, SCREEN_W, LOG_H)
    panel(surf, rect, bg=LOG_BG)
    text(surf, t("log_broadcast", fallback="DZIENNIK"), 10, y + 4, ACCENT, 13, True)
    f = font(13)
    line_h = f.get_height() + 2
    max_lines = (LOG_H - 22) // line_h
    visible = log[-(max_lines + scroll): len(log) - scroll if scroll else None]
    if not visible: visible = log[-max_lines:]
    cy = y + 22
    for s, cat in visible[-max_lines:]:
        col = LOG_COLORS.get(cat, NORMAL_TEXT)
        # Wrap each log line softly
        max_w = SCREEN_W - 24
        for line in _soft_wrap(s, max_w):
            img = f.render(line, True, col)
            surf.blit(img, (12, cy))
            cy += line_h
            if cy > y + LOG_H - 4: break
        if cy > y + LOG_H - 4: break

    # Input
    iy = SCREEN_H - INPUT_H
    pygame.draw.rect(surf, INPUT_BG, (0, iy, SCREEN_W, INPUT_H))
    pygame.draw.rect(surf, ACCENT, (0, iy, SCREEN_W, INPUT_H), 1)
    prompt = "> " + input_text + ("|" if blink else "")
    img = font(16).render(prompt, True, BRIGHT_TEXT)
    surf.blit(img, (12, iy + (INPUT_H - img.get_height())//2))


def _soft_wrap(s: str, max_w: int):
    f = font(13)
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
