"""Pygame UI for the revamp.

Three main layouts:
  - title menu
  - character creation
  - in-game (top bar / room panel / sidebar / log / input)
"""
from typing import Tuple
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
    """P27 — DCC reality-TV main menu.

    Broadcast-terminal aesthetic: dark slab background, scanlines, a
    syndicate "logo" mark at top, cycling sponsor stripe at bottom, the
    title set in a CRT-glow style. Mood: you booted a corporate
    surveillance terminal and a game show is loading.
    """
    surf.fill((6, 8, 12))
    sw, sh = surf.get_size()
    L = _resolve_layout(None)
    title_size = max(36, int(48 * L.font_scale))
    body_size  = max(14, int(15 * L.font_scale))
    item_size  = max(18, int(22 * L.font_scale))

    # Top broadcast header bar — corp stripe.
    bar_h = max(48, int(60 * L.font_scale))
    pygame.draw.rect(surf, (18, 22, 30), (0, 0, sw, bar_h))
    pygame.draw.line(surf, ACCENT, (0, bar_h), (sw, bar_h), 1)
    # Syndicate "logo" — ASCII glyph + name on left.
    logo_img = font(body_size + 2, bold=True).render(
        "▣ SYNDYKAT // KANAŁ KRAULEM", True, ACCENT)
    surf.blit(logo_img, (24, (bar_h - logo_img.get_height()) // 2))
    # Live indicator on right.
    live_img = font(body_size, bold=True).render("● LIVE", True, DANGER)
    surf.blit(live_img, (sw - live_img.get_width() - 24,
                          (bar_h - live_img.get_height()) // 2))

    # CRT scanline overlay — subtle horizontal lines across the whole frame.
    line_col = (12, 14, 20)
    for ly in range(bar_h + 8, sh - 60, 4):
        pygame.draw.line(surf, line_col, (0, ly), (sw, ly), 1)

    # Main title — large, glowy.
    cy = bar_h + max(60, sh // 8)
    # Title text with a slight color-ghost behind it for CRT-glow feel.
    title_text = "DUNGEON KRAULEM"
    title_font = font(title_size, bold=True)
    timg = title_font.render(title_text, True, ACCENT)
    tx = (sw - timg.get_width()) // 2
    # Ghost (warm offset behind main).
    ghost = title_font.render(title_text, True, (60, 20, 80))
    surf.blit(ghost, (tx + 3, cy + 2))
    surf.blit(timg, (tx, cy))
    cy += timg.get_height() + 12

    # Show tagline — single dramatic line.
    tagline = t("title_show_tagline",
                fallback="JEDNA ŚMIERĆ. WIELE PIĘTER. NIESKOŃCZONA REKLAMA.")
    timg = font(body_size + 2, bold=True).render(tagline, True, BRIGHT_TEXT)
    surf.blit(timg, ((sw - timg.get_width()) // 2, cy))
    cy += timg.get_height() + 6

    # Secondary taglines.
    for line, col in [
        (t("title_tagline_1", fallback="Sponsorzy patrzą. Widzowie krzyczą."), NORMAL_TEXT),
        (t("title_tagline_2", fallback="Termin tyka. Loch zapada się powoli."), DIM_TEXT),
    ]:
        timg = font(body_size).render(line, True, col)
        surf.blit(timg, ((sw - timg.get_width()) // 2, cy))
        cy += 22

    # Menu items.
    cy += max(40, int(40 * L.font_scale))
    items = [
        (t("title_build_character", fallback="[1] NOWA GRA"), BRIGHT_TEXT),
        (t("title_load_game",       fallback="[2] WCZYTAJ ZAPIS") if save_exists else
         t("title_load_disabled",   fallback="[2] WCZYTAJ ZAPIS (brak)"),
         BRIGHT_TEXT if save_exists else DIM_TEXT),
        (t("title_settings",        fallback="[3] USTAWIENIA"), BRIGHT_TEXT),
        (t("title_quit",            fallback="[4] WYJDŹ Z TRANSMISJI"), BRIGHT_TEXT),
    ]
    sel = max(0, min(int(selected_idx or 0), len(items) - 1))
    for i, (label, col) in enumerate(items):
        if i == sel:
            label = "▶  " + label + "  ◀"
            col = ACCENT
        timg = font(item_size, bold=True).render(label, True, col)
        surf.blit(timg, ((sw - timg.get_width()) // 2, cy))
        cy += item_size + 14

    # Sponsor stripe — bottom cycling band.
    stripe_h = max(36, int(44 * L.font_scale))
    stripe_y = sh - stripe_h - 30
    pygame.draw.rect(surf, (16, 12, 22), (0, stripe_y, sw, stripe_h))
    pygame.draw.line(surf, ACCENT2, (0, stripe_y), (sw, stripe_y), 1)
    pygame.draw.line(surf, ACCENT2, (0, stripe_y + stripe_h),
                     (sw, stripe_y + stripe_h), 1)
    sponsors_strip = (
        "NovaChem Biotech  ·  Sponsor Bezpieczeństwa Sportu  ·  "
        "Czarny Rynek Plus  ·  Ministerstwo Słusznej Treści  ·  "
        "Obywatele Ulicy  ·  Syndykat"
    )
    sp_img = font(body_size - 1).render(sponsors_strip, True, DIM_TEXT)
    surf.blit(sp_img, ((sw - sp_img.get_width()) // 2,
                       stripe_y + (stripe_h - sp_img.get_height()) // 2))

    # Language toggle + footer.
    lang_str = f"[L] {t('lang_toggle_label', fallback='Język')}: {get_language().upper()}"
    lang_img = font(body_size - 2).render(lang_str, True, ACCENT2)
    surf.blit(lang_img, (24, sh - 24))

    footer = t("title_syndicate_footer",
               fallback="© Syndykat Rozrywki Wydobywczej.  "
                        "Wszystkie zgony są dobrowolne.")
    f_img = font(body_size - 3).render(footer, True, DIM_TEXT)
    surf.blit(f_img, (sw - f_img.get_width() - 24, sh - 24))


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


def draw_topbar(surf, world, layout=None, *, click_registry=None):
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
    # P27 — Viewer count HUD. Renders: band label + raw rating + delta
    # indicator (▲+12 / ▼-5 from last change) + tiny sparkline of recent
    # audience values. Drives the "you are on TV" feeling — the player
    # sees their numbers move in real time as they do dramatic things.
    try:
        from ..engine import audience as _aud
        rating = int(world.character.audience_rating or 0)
        band = _aud.band_for(rating)
        band_label = _aud.band_label(band)
        history = list(getattr(world, "audience_history", []) or [])
        delta = 0
        if len(history) >= 2:
            delta = history[-1] - history[-2]
        delta_glyph = ""
        delta_col = WARN
        if delta > 0:
            delta_glyph = f" ▲+{delta}"
            delta_col = SUCCESS
        elif delta < 0:
            delta_glyph = f" ▼{delta}"
            delta_col = DANGER
        aud = (f"{t('ui_audience', fallback='Widownia')}: "
               f"{band_label} ({rating})")
        a_img = font(L.font_small - 1).render(aud, True, WARN)
        surf.blit(a_img, (x + w - a_img.get_width() - 16, y + 36))
        # Delta after the audience line.
        if delta_glyph:
            d_img = font(L.font_small - 1, bold=True).render(
                delta_glyph, True, delta_col)
            surf.blit(d_img, (x + w - 16, y + 36))
        # Sparkline: last 16 values as a tiny bar graph.
        if len(history) >= 2:
            spark_w = 96
            spark_h = 12
            sx = x + w - a_img.get_width() - 16 - spark_w - 8
            sy = y + 38
            recent = history[-16:]
            lo = min(recent); hi = max(recent)
            span = max(1, hi - lo)
            bar_w = max(2, spark_w // len(recent))
            for i, v in enumerate(recent):
                h_pct = (v - lo) / span
                h_px = max(1, int(spark_h * h_pct))
                bx = sx + i * bar_w
                by = sy + (spark_h - h_px)
                # Color shifts from danger (low) → success (high).
                col = (max(60, int(80 + 140 * h_pct)),
                       max(60, int(120 + 80 * h_pct)),
                       max(50, int(60 + 40 * h_pct)))
                pygame.draw.rect(surf, col, (bx, by, max(1, bar_w - 1), h_px))
    except Exception:
        # Defensive fallback — never let HUD math crash the top bar.
        aud = f"Widownia: {world.character.audience_rating}"
        img = font(L.font_small - 1).render(aud, True, WARN)
        surf.blit(img, (x + w - img.get_width() - 16, y + 36))

    # Prompt 20: encounter countdown badge. Shown when a scheduled
    # encounter is pending for the player's current room. The badge
    # uses warning red and sits below the audience line.
    try:
        from ..engine import encounter as _enc
        rem = _enc.time_until_next(world)
        if rem is not None:
            if rem <= 0:
                label = "⚠ TUŻ-TUŻ"
            elif rem < 10:
                label = f"⚠ {rem} min"
            else:
                hours = rem // 60
                mins = rem % 60
                label = (f"⚠ {hours:d}h {mins:02d}m" if hours
                         else f"⚠ {mins} min")
            img = font(L.font_small).render(label, True,
                                            DANGER if rem < 5 else WARN)
            surf.blit(img, (x + w - img.get_width() - 16, y + 56))
    except Exception:
        pass


def draw_room_panel(surf, world, layout=None, *, click_registry=None):
    """Render the center panel. P24.5: when combat is active in the
    current room, this delegates to draw_combat_arena() so the player
    gets a dedicated tactical surface instead of the normal room view."""
    L = _resolve_layout(layout)
    f = world.current_floor
    if f is None:
        return
    room = f.current_room()
    if room is None:
        return

    # P24.5: combat takeover. The center panel becomes the arena.
    try:
        from ..engine import combat as _cmb
        cs = _cmb.get_combat(room)
        if cs is not None and cs.active:
            draw_combat_arena(surf, world, cs, layout=L,
                              click_registry=click_registry)
            return
    except Exception:
        pass

    x, y, w, h = L.room_rect
    # P24.6 (P24.5-1): drop the dark panel fill — the global DARK_BG
    # already provides the visual ground. Without the inner-panel
    # rect we no longer get a "dark void" of unused space below the
    # content. A subtle separator line on the left edge gives the
    # column a soft delimiter without boxing it in.
    pygame.draw.line(surf, BORDER, (x, y), (x, y + h), 1)

    # P24.6 (P24.5-3): clearly-labeled mood placeholder. Reads as
    # "intentional slot for future art" instead of "broken asset".
    mood_h = max(48, min(120, h // 6))
    _draw_room_mood_placeholder(surf, x + 14, y + 12, w - 28, mood_h, room,
                                show_caption=True)

    # Compose the content block, render top-down. Vertical centering
    # happens AFTER measuring total height when content is short
    # relative to the panel.
    content_start_y = y + 12 + mood_h + 14
    title_str = room.display_title()
    desc_str = (room.display_first_enter()
                if room.last_visited_minute == f.current_minute
                else room.display_look())
    wrap_w = min(w - 28, 900)

    # Measure pass — figure out total content height to decide whether
    # to center vertically. Cheap because we re-wrap; only matters for
    # short rooms.
    desc_lines = _soft_wrap(desc_str, wrap_w, L.font_body - 1)
    f_body = font(L.font_body - 1)
    body_lh = f_body.get_height() + 3
    title_h = font(L.font_title - 4, bold=True).get_height() + 6
    desc_h = len(desc_lines) * body_lh
    visible = room.visible_entities()
    ents_h  = 0
    if visible:
        ents_h = 22 + 16 * min(len(visible), 6)
    exits_h = 0
    if room.exits:
        exits_h = 22 + 16 * min(len(room.exits), 6)
    total_h = title_h + desc_h + 12 + ents_h + 16 + exits_h
    avail_h = (y + h) - content_start_y - 12
    pad_top = max(0, (avail_h - total_h) // 4) if total_h < avail_h else 0
    cy = content_start_y + pad_top

    text(surf, title_str, x + 14, cy, ACCENT2, L.font_title - 4, True)
    cy += title_h
    cy += text_wrapped(surf, desc_str, x + 14, cy, wrap_w,
                       NORMAL_TEXT, L.font_body - 1)
    cy += 10

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
        # P27.5 (P27-UX-21): filter hidden + skip per-exit hint text
        # when stack is getting tight, so the list doesn't truncate
        # mid-room (Lounge had 6 exits, last one fell off-screen).
        visible_exits = [(lbl, ed) for lbl, ed in room.exits.items()
                         if not ed.get("hidden")]
        # Compact mode: if more than 5 exits, skip the per-exit hint
        # lines (which double the height).
        compact = len(visible_exits) > 5
        for label, ed in visible_exits:
            target_id = ed.get("target","")
            target = f.rooms.get(target_id)
            target_name = target.display_short_title() if target else "?"
            lock = "🔒" if ed.get("locked") else ""
            hint = ed.get("fallback_hint") or t(ed.get("hint_key",""), fallback="")
            line = f"  → {label}  ({target_name}) {lock}"
            text(surf, line, x + 16, cy, NORMAL_TEXT, L.font_small); cy += 16
            if hint and not compact:
                text(surf, f"      {hint}", x + 16, cy, DIM_TEXT, L.font_small - 1); cy += 14
            if cy > y + h - 18: break


def _draw_enemy_panel(surf, world, target, cs, x, y, w, h, L,
                      *, click_registry=None):
    """P26a — VATS-style target detail: silhouette with clickable body
    zones + per-zone HP bars + targeted-zone preview line. Replaces
    the simple HP/AC strip from P23.
    """
    from ..engine import combat as _cmb
    from ..content.data import body_plans as _bp
    _bp.init_body_parts(target)
    plan = _bp.plan_for_entity(target)
    cy = y + 8
    text(surf, t("ui_enemy_header", fallback="CEL"),
         x + 14, cy, DANGER, L.font_small, True); cy += 18
    text(surf, target.display_name(), x + 14, cy, BRIGHT_TEXT,
         L.font_small, True); cy += 18
    hp_bar(surf, x + 14, cy, w - 28, 12, target.hp, target.max_hp); cy += 16
    text(surf, f"HP {target.hp}/{target.max_hp}   AC {target.ac}",
         x + 14, cy, NORMAL_TEXT, L.font_small - 1); cy += 16

    # P26a — silhouette: a colored-rect humanoid laid out vertically
    # with clickable zone rects. Body plan dictates which zones render.
    cy += 4
    selected_zone = (cs.targeted_zone_by_eid or {}).get(target.entity_id) \
        if cs is not None else None
    if selected_zone is None or selected_zone not in plan:
        selected_zone = "torso" if "torso" in plan else next(iter(plan.keys()))

    sil_w = w - 28
    sil_h = max(150, min(220, h - (cy - y) - 80))
    sil_x = x + 14
    sil_y = cy
    _draw_silhouette(surf, target, plan, sil_x, sil_y, sil_w, sil_h, L,
                     selected_zone, cs=cs,
                     click_registry=click_registry)
    cy = sil_y + sil_h + 6

    # Preview line for selected zone.
    zp = (target.body_parts or {}).get(selected_zone) or {}
    zp_max = max(1, zp.get("max_hp", 1))
    zp_hp = zp.get("hp", zp_max)
    broken = zp.get("broken", False)
    z_props = plan.get(selected_zone, {})
    z_label = z_props.get("label_pl", selected_zone)
    z_mod = int(z_props.get("to_hit_mod", 0))
    z_mul = float(z_props.get("damage_mul", 1.0))
    maim = z_props.get("maim_status")
    maim_label = _cmb.status_label(maim, "pl") if maim else "—"
    parts = [f"Cel: {z_label}",
             f"trafienie {z_mod:+d}",
             f"obraż. ×{z_mul:.1f}"]
    if maim:
        parts.append(f"maim: {maim_label}")
    text(surf, "  ·  ".join(parts), x + 14, cy, ACCENT2,
         L.font_small - 1); cy += 14
    text(surf, f"HP strefy: {zp_hp}/{zp_max}"
               + ("  [złamana]" if broken else ""),
         x + 14, cy, DANGER if broken else NORMAL_TEXT,
         L.font_small - 1); cy += 14

    # Distance band.
    if cs and target.entity_id in cs.bands:
        band = cs.bands[target.entity_id]
        band_pl = {"engaged": "zwarcie", "at_range": "dystans"}.get(band, band)
        text(surf, f"Dystans: {band_pl}", x + 14, cy, ACCENT2,
             L.font_small - 1); cy += 14

    # Statuses with PL labels.
    if target.conditions:
        cy += 4
        text(surf, t("ui_enemy_statuses", fallback="Stan:"),
             x + 14, cy, DANGER, L.font_small - 1, True); cy += 14
        labels = [_cmb.status_label(s, "pl") for s in target.conditions]
        # Wrap statuses across rows.
        line_w = w - 28
        f_small = font(L.font_small - 1)
        line = ""
        for lbl in labels:
            test = (line + ", " + lbl) if line else lbl
            if f_small.size(test)[0] > line_w:
                text(surf, line, x + 14, cy, WARN, L.font_small - 1)
                cy += 14
                line = lbl
            else:
                line = test
        if line:
            text(surf, line, x + 14, cy, WARN, L.font_small - 1); cy += 14

    # Resistances if known (always visible for now — could be gated by clues later).
    if target.resists or target.vulnerable_to or target.immune_to:
        cy += 4
        if target.resists:
            text(surf, "Odporny: " + ", ".join(target.resists),
                 x + 14, cy, ACCENT2, L.font_small - 1); cy += 13
        if target.vulnerable_to:
            text(surf, "Podatny: " + ", ".join(target.vulnerable_to),
                 x + 14, cy, ACCENT, L.font_small - 1); cy += 13
        if target.immune_to:
            text(surf, "Niewrażliwy: " + ", ".join(target.immune_to),
                 x + 14, cy, DIM_TEXT, L.font_small - 1); cy += 13

    # Companion advantage flag (Prompt 19).
    if cs and getattr(cs, "companion_advantage_pending", False):
        cy += 4
        text(surf, t("ui_enemy_advantage_flag",
                     fallback="• Towarzysz odwraca uwagę"),
             x + 14, cy, ACCENT, L.font_small - 1); cy += 13


def draw_sidebar(surf, world, layout=None, *, click_registry=None):
    """Right column: portrait + HP/AC + statuses + paper-doll + quick-strip.
    Combat splits this — the quick-strip area is replaced by an expanded
    target panel for the selected combat target.

    P24.5: paper-doll is the equipment management surface (replaces the
    separate Ekwipunek tab as the primary path). Quick-strip exposes the
    top-5 carried items for one-click use.
    """
    L = _resolve_layout(layout)
    x, y, w, h = L.right_sidebar_rect

    # Prompt 23 — detect combat and target.
    target_ent = None
    cs = None
    try:
        from ..engine import combat as _cmb
        f = world.current_floor
        room = f.current_room() if f else None
        cs = _cmb.get_combat(room) if room else None
        if cs is not None and cs.active and cs.participants:
            for eid in cs.participants:
                ent = world.get(eid)
                if ent is not None and ent.is_alive():
                    target_ent = ent
                    break
    except Exception:
        target_ent = None
        cs = None

    # Combat: select target via cs.selected_target_id (set by arena card
    # clicks); fall back to first alive participant.
    target_ent = None
    if cs is not None and cs.active:
        sel_id = getattr(cs, "selected_target_id", None)
        if sel_id is not None:
            t_ent = world.get(sel_id)
            if t_ent is not None and t_ent.is_alive():
                target_ent = t_ent
        if target_ent is None:
            for eid in cs.participants:
                ent = world.get(eid)
                if ent is not None and ent.is_alive():
                    target_ent = ent; break

    # Sidebar layout: portrait + name + HP + statuses (always), then
    # paper-doll (always), then quick-strip OR target panel.
    # P24.6: subtle left-edge separator instead of a full panel fill
    # — matches the room panel restyle and removes the "dark slab"
    # feel.
    pygame.draw.line(surf, BORDER, (x, y), (x, y + h), 1)
    c = world.character
    cy = y + 10

    # Portrait (placeholder).
    port_size = max(72, min(128, w - 28))
    port_x = x + (w - port_size) // 2
    _draw_player_portrait_placeholder(surf, c, port_x, cy, port_size, port_size)
    cy += port_size + 6

    # Name + background.
    text(surf, c.name or "—", x + 14, cy, BRIGHT_TEXT,
         L.font_title - 4, True); cy += 22
    text(surf, t(f"bg_{c.background}_n", fallback=c.background),
         x + 14, cy, ACCENT2, L.font_small - 1); cy += 14
    if c.class_key:
        text(surf, t(f"class_{c.class_key}_n", fallback=c.class_key),
             x + 14, cy, ACCENT, L.font_small - 1); cy += 14

    # HP/AC/Kr.
    cy += 2
    hp_bar(surf, x + 14, cy, w - 28, 12, c.hp, c.max_hp); cy += 16
    text(surf, f"HP {c.hp}/{c.max_hp}   AC {c.effective_ac(world)}   "
               f"{t('ui_credits', fallback='Kr')} {c.credits}",
         x + 14, cy, NORMAL_TEXT, L.font_small - 1); cy += 18

    # Statuses (compact, one line).
    if c.conditions:
        text(surf, "Status: " + ", ".join(c.conditions[:4]),
             x + 14, cy, DANGER, L.font_small - 2); cy += 14

    cy += 4
    pygame.draw.line(surf, BORDER, (x + 14, cy), (x + w - 14, cy), 1)
    cy += 6

    # Paper-doll.
    cy = draw_paper_doll(surf, world, x + 8, cy, w - 16,
                         180, layout=L, click_registry=click_registry)

    pygame.draw.line(surf, BORDER, (x + 14, cy), (x + w - 14, cy), 1)
    cy += 6

    # In combat: target panel replaces quick-strip. Out of combat: strip.
    if target_ent is not None:
        _draw_enemy_panel(surf, world, target_ent, cs,
                          x, cy, w, y + h - cy, L,
                          click_registry=click_registry)
    else:
        draw_quick_strip(surf, world, x + 8, cy, w - 16,
                         max(80, y + h - cy - 8),
                         layout=L, click_registry=click_registry)


def draw_left_sidebar(surf, world, layout=None, *,
                      click_registry=None, on_room_click=None):
    """Left column (P24.5: always-on): minimap on top, known-rooms /
    objective / clue summary below.

    Replaces the old ultrawide-only sidebar — the minimap is now
    persistent at every resolution. Compact resolutions get a narrower
    strip; the minimap still fits.
    """
    L = _resolve_layout(layout)
    if not L.has_left_sidebar:
        return
    # Minimap (always at the top).
    from . import minimap as _mm
    _mm.draw_minimap(surf, world, L.minimap_rect, L,
                     click_registry=click_registry,
                     on_room_click=on_room_click)
    # The text strip below.
    x, y, w, h = L.left_strip_rect
    # P24.6: no panel fill — subtle right-edge separator only.
    pygame.draw.line(surf, BORDER, (x + w, y), (x + w, y + h), 1)
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
    header_label = t("log_broadcast", fallback="DZIENNIK")
    if scroll and scroll > 0:
        # Prompt 23.5 (backlog #1): when the player has scrolled away from
        # the newest entry, surface that state in the header so they don't
        # think the log is frozen / broken.
        header_label = (header_label + "  ↑ -" + str(int(scroll))
                        + " (PgDn aby wrócić)")
    text(surf, header_label,
         lx + 10, ly + 4, ACCENT, L.font_small, True)
    f = font(L.font_small)
    # P27.5 (P27-UX-9): bumped line spacing 2→5 to eliminate residual
    # vertical overlap visible when consecutive entries with descender
    # glyphs (ę, ą, ł) render close together. Cheap fix.
    line_h = f.get_height() + 5
    max_w = lw - 24

    # Prompt 22 bug fix: previously the log render picked the LAST N
    # entries (where N = lh/line_h) and walked forward, top-down.
    # When entries wrapped to multiple visual lines (audience bumps +
    # alarm + narrator hits in a burst), the first entries filled the
    # panel and the NEWEST entries got clipped — exactly opposite of
    # what the player wants. Now we render bottom-up: start at the
    # last entry, push it onto a stack of (line, color) rows, walk
    # backwards through history until we have enough rows to fill the
    # visible area + the `scroll` offset, then blit from the top of
    # that final window.
    #
    # `scroll` here is how many full entries to skip from the bottom
    # — for future PageUp/PageDown support. 0 means "newest pinned".
    # P24.6 (P24.5-7): visible_rows now carries a per-row (text, color,
    # is_first_of_entry) tuple. Only the FIRST line of a multi-line
    # sponsor entry gets the avatar circle; continuation lines indent to
    # match but draw no circle. AND sponsor entries wrap against a
    # gutter-reduced max width so text doesn't overflow into the next
    # row's space (which was the visual "overlap" the playtester saw).
    visible_rows: list = []   # list of (line_text, color, is_first)
    syndic_color_pre = LOG_COLORS.get("syndicate", None)
    sponsor_gutter_w = max(7, line_h // 2 - 1) * 2 + 6   # matches render
    if scroll < 0:
        scroll = 0
    available_rows = max(1, (lh - 22) // line_h)
    skipped_entries = 0
    for entry in reversed(log):
        if skipped_entries < scroll:
            skipped_entries += 1
            continue
        s, cat = entry
        col = LOG_COLORS.get(cat, NORMAL_TEXT)
        is_sponsor_entry = (syndic_color_pre is not None
                            and col == syndic_color_pre)
        # Sponsor lines have less horizontal room because of the gutter.
        wrap_w = max(40, max_w - sponsor_gutter_w) if is_sponsor_entry else max_w
        wrapped = list(_soft_wrap(s, wrap_w, L.font_small))
        # First line of the entry is the only one that earns the avatar.
        block = [(ln, col, (i == 0)) for i, ln in enumerate(wrapped)]
        visible_rows = block + visible_rows
        if len(visible_rows) >= available_rows:
            visible_rows = visible_rows[-available_rows:]
            break

    # Render top-down within the panel bounds.
    cy = ly + 22
    bottom_limit = ly + lh - 4
    syndic_color = LOG_COLORS.get("syndicate", None)
    for line_text, col, is_first in visible_rows:
        if cy + line_h > bottom_limit:
            break
        is_sponsor = (col == syndic_color) if syndic_color else False
        gutter_w = 0
        if is_sponsor:
            # Reserve the gutter on every sponsor row (so text aligns)
            # but only draw the avatar circle on the FIRST line of the
            # entry. Continuation lines indent to match without doubling
            # the visual.
            r = max(7, line_h // 2 - 1)
            gutter_w = r * 2 + 6
            if is_first:
                speaker_initial = ""
                for sep in (":", "„"):
                    if sep in line_text:
                        spk = line_text.split(sep, 1)[0].strip()
                        if 1 <= len(spk) <= 24:
                            speaker_initial = spk[:1].upper()
                            break
                if not speaker_initial:
                    speaker_initial = "S"
                cx_av = lx + 14 + r
                cy_av = cy + line_h // 2
                pygame.draw.circle(surf, (50, 40, 70), (cx_av, cy_av), r)
                pygame.draw.circle(surf, ACCENT2, (cx_av, cy_av), r, 1)
                ai = font(max(9, r), bold=True).render(speaker_initial,
                                                       True, BRIGHT_TEXT)
                surf.blit(ai, (cx_av - ai.get_width() // 2,
                               cy_av - ai.get_height() // 2))
        img = f.render(line_text, True, col)
        surf.blit(img, (lx + 12 + gutter_w, cy))
        cy += line_h

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

def draw_nav_panel(surf, nav_state, input_mode="text", layout=None,
                   *, armed: bool = False, click_registry=None,
                   on_option_click=None):
    """Render the current group's option list. The nav rect comes from
    the Layout (anchored above the log), so it no longer overlays the
    sidebar regardless of resolution.

    Prompt 20: `armed` means the player has used arrow keys / Tab from
    text-empty mode to drive the panel (the Prompt-18 arming latch) but
    `input_mode` is still "text". Treat that visually the same as full
    nav-mode — show the cursor marker + bright selection. Otherwise the
    cursor would move silently and the player would see no feedback,
    which is exactly the bug the playtester hit on Obiekty tab."""
    if nav_state is None or not getattr(nav_state, "groups", None):
        return
    L = _resolve_layout(layout)
    x, y, w, h = L.nav_rect
    panel(surf, (x, y, w, h))

    # Prompt 20: treat "armed" as effectively the same as nav mode
    # for rendering purposes (cursor marker + bright selection color).
    nav_active = (input_mode == "nav") or bool(armed)

    groups = list(nav_state.groups)
    cur = nav_state.current_group()
    header = t("ui_nav_header", fallback="Akcje i wybór")
    text(surf, header, x + 12, y + 6,
         ACCENT2 if nav_active else DIM_TEXT,
         L.font_small, True)

    # Group tabs in a horizontal row at the top of the panel.
    cy = y + 26
    cx = x + 12
    from .ui_nav import group_label
    for g in groups:
        lbl = "[" + group_label(g) + "]"
        col = ACCENT if g == cur and nav_active else \
              ACCENT2 if g == cur else DIM_TEXT
        img = font(L.font_small - 1, bold=g == cur).render(lbl, True, col)
        if cx + img.get_width() > x + w - 12:
            cy += 18
            cx = x + 12
        # P24.5: click zone for the tab chip — switches groups.
        if click_registry is not None:
            tab_rect = (cx - 2, cy - 2, img.get_width() + 4, img.get_height() + 4)
            def _switch(group_key=g, ns=nav_state):
                if group_key in ns.groups:
                    ns.current_group_index = ns.groups.index(group_key)
            click_registry.add(tab_rect, _switch,
                               tooltip=group_label(g),
                               category="nav_tab")
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

    line_h = font(L.font_small).get_height() + 2
    max_lines_per_col = max(1, (h - (cy - y) - 12) // line_h)
    # Prompt 22 fix: previously `per_col` was ceil(n / col_count) and the
    # row index iterated by `i % per_col`. If ceil exceeded
    # `max_lines_per_col`, rows rendered past the panel and bled into
    # the log below. Now cap `per_col` first so layout never overflows.
    ideal_per_col = (n + col_count - 1) // col_count
    per_col = max(1, min(max_lines_per_col, ideal_per_col))
    visible_total = min(n, col_count * per_col)
    # Stash the grid shape on the nav_state so the keydown handler can
    # use the SAME numbers for L/R/U/D navigation (column hop = per_col,
    # row step = 1). Without this, input and render would compute
    # per_col independently and could disagree at boundary resolutions.
    try:
        nav_state._grid_per_col = per_col
        nav_state._grid_col_count = col_count
    except AttributeError:
        pass

    # Prompt 23.5 (backlog #9): paginate the option list so `+N więcej…`
    # isn't a dead-end. When the selected index falls outside the visible
    # window, slide the window so the cursor stays visible. Hidden
    # entries before / after the window are indicated with ↑ / ↓ markers
    # plus the count, so the player knows the action is reachable by
    # scrolling.
    page_start = 0
    if sel_idx >= visible_total:
        page_start = sel_idx - visible_total + 1
        # Snap to a column boundary so visual layout stays stable.
        page_start = (page_start // per_col) * per_col
    page_start = max(0, min(page_start, max(0, n - visible_total)))
    visible = opts[page_start:page_start + visible_total]

    f_opt = font(L.font_small)
    start_cy = cy
    for i, opt in enumerate(visible):
        col_idx = i // per_col
        row_idx = i % per_col
        ox = x + 12 + col_idx * col_w
        oy = start_cy + row_idx * line_h
        abs_idx = page_start + i
        marker = "▶ " if (abs_idx == sel_idx and nav_active) else "  "
        col = (BRIGHT_TEXT if nav_active and abs_idx == sel_idx
               else NORMAL_TEXT if opt.enabled else DIM_TEXT)
        line = marker + opt.label
        max_w = col_w - 12
        if f_opt.size(line)[0] > max_w:
            while line and f_opt.size(line + "…")[0] > max_w:
                line = line[:-1]
            line = line + "…"
        img = f_opt.render(line, True, col)
        surf.blit(img, (ox, oy))
        # P24.5: click zone for the option cell.
        if click_registry is not None and on_option_click is not None:
            cell_rect = (ox - 2, oy - 2, col_w - 8, line_h)
            def _click(grp=cur, idx=abs_idx, cb=on_option_click):
                cb(grp, idx)
            click_registry.add(cell_rect, _click,
                               tooltip=opt.label, category="nav_opt",
                               keyboard_sync=(cur, abs_idx))

    # Scroll indicators.
    hidden_before = page_start
    hidden_after = max(0, n - (page_start + visible_total))
    if hidden_before > 0:
        text(surf, f"  ↑ +{hidden_before}",
             x + 12, start_cy - 14, DIM_TEXT, L.font_small - 2)
    if hidden_after > 0:
        text(surf, f"  ↓ +{hidden_after} więcej…",
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

    # P27 — LLM mode row removed from UI. The settings system still
    # supports the field internally (for re-enablement when the
    # online-narrator path lands), but the row is hidden so players
    # don't see an option that requires a 50GB local model download.
    rows = [
        (t("settings_resolution", fallback="Rozdzielczość"),
         f"<  {w_cur} x {h_cur}  >"),
        (t("settings_display_mode", fallback="Tryb ekranu"),
         t("settings_fullscreen", fallback="Pełny ekran") if fullscreen
         else t("settings_windowed", fallback="Okno")),
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


# ── Prompt 25 — paper-doll slot swap popover ─────────────────────────────

def draw_slot_popover(surf, world, slot_key: str, cursor_idx: int,
                      layout=None, *, click_registry=None,
                      on_pick=None, on_unequip=None, on_close=None) -> None:
    """Modal popover triggered by clicking a paper-doll slot. Lists
    eligible inventory items + a Zdejmij row (when slot is occupied) +
    Anuluj row. Click / Enter commits; Esc closes via `on_close`.

    `on_pick(entity_id)`: callback when the player chooses an item to
    equip into the slot.
    `on_unequip()`: callback when "Zdejmij" is chosen.
    `on_close()`: callback when "Anuluj" is chosen.
    """
    from ..engine import equipment as _eq
    L = _resolve_layout(layout)
    sw, sh = surf.get_size()
    # Veil behind popover.
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 180))
    surf.blit(veil, (0, 0))
    # Popover frame, centered.
    pw, ph = min(640, int(sw * 0.55)), min(480, int(sh * 0.6))
    px, py = (sw - pw) // 2, (sh - ph) // 2
    pygame.draw.rect(surf, PANEL_BG, (px, py, pw, ph))
    pygame.draw.rect(surf, ACCENT, (px, py, pw, ph), 2)

    sd = _eq.SLOT_DEFS.get(slot_key)
    sd_label = sd.label_pl if sd else slot_key
    text(surf, t("ui_slot_popover_title",
                 fallback=f"Slot: {sd_label}",
                 slot=sd_label),
         px + 16, py + 12, ACCENT, L.font_title - 4, True)

    # Currently-worn entity for context.
    cur_eid = _eq.equipped(world.character, slot_key)
    cur_ent = world.get(cur_eid) if cur_eid is not None else None
    if cur_ent is not None:
        text(surf, t("ui_slot_popover_current",
                     fallback=f"Aktualnie: {cur_ent.display_name()}",
                     name=cur_ent.display_name()),
             px + 16, py + 40, BRIGHT_TEXT, L.font_small)

    # Build the row list.
    eligibles = _eq.eligible_inventory_for_slot(world, world.character, slot_key)
    rows = []
    for ent in eligibles:
        # Add a small AC/effect hint after the name.
        hint = ""
        ac = 0
        if ent.state:
            ac = int(ent.state.get("ac_bonus", 0) or 0)
        if ac:
            hint = f"  (+{ac} AC)" if ac > 0 else f"  ({ac} AC)"
        rows.append(("equip", ent, f"{ent.display_name()}{hint}"))
    if cur_ent is not None:
        rows.append(("unequip", None,
                     t("ui_slot_popover_unequip",
                       fallback=f"Zdejmij: {cur_ent.display_name()}",
                       name=cur_ent.display_name())))
    rows.append(("cancel", None,
                 t("ui_slot_popover_cancel", fallback="Anuluj")))

    cursor_idx = max(0, min(cursor_idx, len(rows) - 1)) if rows else 0
    list_y = py + 70
    line_h = font(L.font_body).get_height() + 8
    f_row = font(L.font_body)
    for i, (kind, ent, label) in enumerate(rows):
        ry = list_y + i * line_h
        is_sel = (i == cursor_idx)
        if is_sel:
            pygame.draw.rect(surf, ACCENT2,
                             (px + 12, ry - 2, pw - 24, line_h - 2), 1)
        marker = "▶ " if is_sel else "  "
        col = (BRIGHT_TEXT if is_sel
               else (ACCENT if kind == "unequip"
                     else (DIM_TEXT if kind == "cancel" else NORMAL_TEXT)))
        img = f_row.render(marker + label, True, col)
        surf.blit(img, (px + 18, ry))
        if click_registry is not None:
            row_rect = (px + 12, ry - 2, pw - 24, line_h - 2)
            def _click(k=kind, e=ent):
                if k == "equip" and e is not None and on_pick is not None:
                    on_pick(e.entity_id)
                elif k == "unequip" and on_unequip is not None:
                    on_unequip()
                elif k == "cancel" and on_close is not None:
                    on_close()
            click_registry.add(row_rect, _click,
                               tooltip=label, category="slot_popover")

    # Footer hint.
    hint = t("ui_slot_popover_hint",
             fallback="↑↓ wybór · Enter zatwierdź · Esc anuluj")
    himg = font(L.font_small - 1).render(hint, True, DIM_TEXT)
    surf.blit(himg, (px + 16, py + ph - 26))


# ── Prompt 24.5 — full-screen map overlay ────────────────────────────────

def draw_full_map_overlay(surf, world, layout=None, *,
                          click_registry=None) -> None:
    """Modal full-screen map. M toggles, Esc closes.

    Renders the same grid as the persistent minimap but zoomed and with
    full room titles + a legend strip. Click a room to mark it. No
    fast-travel (DCC keeps movement turn-based).
    """
    from . import minimap as _mm
    L = _resolve_layout(layout)
    sw, sh = surf.get_size()
    # Veil the world.
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 210))
    surf.blit(veil, (0, 0))
    # Frame.
    mx_pad = max(24, int(sw * 0.06))
    my_pad = max(24, int(sh * 0.06))
    fx, fy = mx_pad, my_pad
    fw, fh = sw - 2 * mx_pad, sh - 2 * my_pad
    pygame.draw.rect(surf, PANEL_BG, (fx, fy, fw, fh))
    pygame.draw.rect(surf, ACCENT, (fx, fy, fw, fh), 2)
    # Header.
    text(surf, t("ui_full_map_title", fallback="MAPA PIĘTRA"),
         fx + 16, fy + 10, ACCENT, L.font_title - 2, True)
    text(surf, t("ui_full_map_hint",
                 fallback="Esc / M — zamknij   ·   klik — oznacz pokój"),
         fx + 16, fy + fh - 28, DIM_TEXT, L.font_small)
    # Inner area for the grid.
    legend_h = 60
    grid_y = fy + 46
    grid_h = fh - 46 - legend_h - 18
    grid_rect = (fx + 16, grid_y, fw - 32, grid_h)

    floor = world.current_floor if world else None
    if floor is None:
        return
    positions = _mm.grid_positions(floor)
    if not positions:
        return
    min_col, min_row, max_col, max_row = _mm.bounds(positions)
    cols = max(1, max_col - min_col + 1)
    rows = max(1, max_row - min_row + 1)
    gx, gy, gw, gh = grid_rect
    cell = max(28, min(64, min(gw // cols, gh // rows)))
    off_x = gx + (gw - cell * cols) // 2
    off_y = gy + (gh - cell * rows) // 2

    revealed = set(getattr(floor, "discovered_room_ids", set()) or set())
    revealed |= set(getattr(floor, "known_room_ids", set()) or set())
    revealed |= set(getattr(floor, "revealed_room_ids", set()) or set())
    current_id = getattr(floor, "current_room_id", "")
    marked = set((getattr(world, "player_map_marks", None) or {}).get(
        getattr(floor, "floor_id", "f"), []))

    glyph_font = font(max(14, int(cell * 0.4)), bold=True)
    name_font  = font(max(11, int(cell * 0.22)))

    for rid, (col, row) in positions.items():
        if rid not in revealed and rid != current_id:
            continue
        room = floor.rooms.get(rid)
        cx = off_x + (col - min_col) * cell
        cy = off_y + (row - min_row) * cell
        pygame.draw.rect(surf, DARK_BG, (cx + 2, cy + 2, cell - 4, cell - 4))
        glyph, color = _mm.room_marker(room, floor,
                                       is_current=(rid == current_id))
        border_col = ACCENT if rid in marked else BORDER
        border_w = 3 if rid in marked else 1
        pygame.draw.rect(surf, border_col, (cx, cy, cell, cell), border_w)
        # Glyph.
        img = glyph_font.render(glyph, True, color)
        surf.blit(img, (cx + (cell - img.get_width()) // 2,
                        cy + 4))
        # Room title (truncated).
        if room is not None:
            title = room.display_short_title() if hasattr(room, "display_short_title") else rid
            if name_font.size(title)[0] > cell - 6:
                while title and name_font.size(title + "…")[0] > cell - 6:
                    title = title[:-1]
                title += "…"
            n_img = name_font.render(title, True, NORMAL_TEXT)
            surf.blit(n_img, (cx + (cell - n_img.get_width()) // 2,
                              cy + cell - n_img.get_height() - 4))
        # Click zone.
        if click_registry is not None:
            def _toggle(rid=rid, world=world, floor=floor):
                fid = getattr(floor, "floor_id", "f")
                if not hasattr(world, "player_map_marks"):
                    world.player_map_marks = {}
                bucket = world.player_map_marks.setdefault(fid, [])
                if rid in bucket: bucket.remove(rid)
                else: bucket.append(rid)
            click_registry.add((cx, cy, cell, cell), _toggle,
                               category="fullmap_room",
                               tooltip=room.display_short_title() if room else rid)

    # Legend strip.
    legend_y = fy + fh - legend_h - 6
    text(surf, "Legenda:", fx + 16, legend_y, ACCENT, L.font_small, True)
    legend_items = [
        ("@", "tu jesteś", ACCENT),
        ("S", "kryjówka", SUCCESS),
        ("B", "boss", DANGER),
        ("!", "miniboss", DANGER),
        ("⚔", "walka", WARN),
        ("?", "znane / niezbadane", DIM_TEXT),
        ("·", "rozpoznane", NORMAL_TEXT),
    ]
    lx = fx + 16
    ly = legend_y + 22
    for glyph, label, color in legend_items:
        gi = font(L.font_small, bold=True).render(glyph, True, color)
        surf.blit(gi, (lx, ly))
        li = font(L.font_small - 1).render(label, True, NORMAL_TEXT)
        surf.blit(li, (lx + gi.get_width() + 6, ly + 1))
        lx += gi.get_width() + 12 + li.get_width()


# ── Prompt 24.5 — hover tooltip overlay ──────────────────────────────────

def draw_hover_tooltip(surf, click_registry, mouse_xy, layout=None) -> None:
    """Floating tooltip rendered last so it sits above all panels.
    Reads the topmost click zone at the cursor and shows its tooltip
    text (if any) as a tinted chip slightly offset from the cursor."""
    if click_registry is None or mouse_xy is None:
        return
    mx, my = mouse_xy
    if mx < 0 or my < 0:
        return
    zone = click_registry.find(mx, my)
    if zone is None or not zone.tooltip:
        return
    L = _resolve_layout(layout)
    f = font(L.font_small - 1)
    text_w, text_h = f.size(zone.tooltip)
    pad = 5
    bw = text_w + pad * 2
    bh = text_h + pad * 2
    sw, sh = surf.get_size()
    bx = min(mx + 14, sw - bw - 4)
    by = min(my + 14, sh - bh - 4)
    pygame.draw.rect(surf, (10, 14, 22), (bx, by, bw, bh))
    pygame.draw.rect(surf, ACCENT, (bx, by, bw, bh), 1)
    img = f.render(zone.tooltip, True, BRIGHT_TEXT)
    surf.blit(img, (bx + pad, by + pad))


# ── Prompt 24.5 — placeholders, combat arena, paper-doll, quick-strip ────

def _draw_room_mood_placeholder(surf, x, y, w, h, room, *,
                                show_caption: bool = False) -> None:
    """Placeholder for the room mood image slot. Future P35 swaps in a
    real PNG keyed by biome / mood. Today: a soft colored band with a
    biome glyph + an explicit `[obraz nastrojowy — wkrótce]` caption so
    the player reads this as an intentional slot, not a broken asset
    (P24.5-3, Option B locked in).
    """
    # Pick a tint from the room's actual_type or sensory_tags.
    tags = (getattr(room, "sensory_tags", []) or []) + [
        getattr(room, "actual_type", "") or ""]
    base = (32, 32, 44)
    if any(t in tags for t in ("safehouse", "shop", "lore")):
        base = (40, 50, 38)
    elif any(t in tags for t in ("combat", "boss")):
        base = (60, 30, 30)
    elif any(t in tags for t in ("dark", "cold", "freezer")):
        base = (28, 36, 48)
    elif any(t in tags for t in ("warm", "fire", "chem", "acid")):
        base = (52, 38, 28)
    # Two-tone gradient via two filled rects (cheap).
    pygame.draw.rect(surf, base, (x, y, w, h))
    lighter = tuple(min(255, c + 18) for c in base)
    pygame.draw.rect(surf, lighter, (x, y, w, h // 2))
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1)
    # Glyph hint in the bottom-right.
    glyph = "·"
    if "safehouse" in tags or room.is_safe():
        glyph = "S"
    elif "boss" in tags or getattr(room, "actual_type", "") == "boss":
        glyph = "B"
    elif "combat" in tags:
        glyph = "⚔"
    elif "lore" in tags:
        glyph = "i"
    elif "shop" in tags:
        glyph = "$"
    g_img = font(max(14, h // 3), bold=True).render(glyph, True, DIM_TEXT)
    surf.blit(g_img, (x + w - g_img.get_width() - 10,
                      y + h - g_img.get_height() - 6))
    # Caption (top-left corner of the slot) — clearly placeholder.
    if show_caption:
        cap = t("ui_mood_placeholder",
                fallback="[obraz nastrojowy — wkrótce]")
        c_img = font(11).render(cap, True, DIM_TEXT)
        surf.blit(c_img, (x + 8, y + 6))


def draw_combat_arena(surf, world, cs, layout=None, *, click_registry=None):
    """Combat-mode takeover of the center panel.

    Lays out enemies grouped by distance band, the player chip at the
    bottom (weapon / off-hand / coating / HP / AC / buffs), and a
    one-line room banner at top. The currently-selected combat target
    drives the right sidebar's expanded detail panel — selection lives
    on `cs.selected_target_id` (added lazily here if absent).
    """
    L = _resolve_layout(layout)
    x, y, w, h = L.room_rect
    panel(surf, (x, y, w, h))
    floor = world.current_floor
    room = floor.current_room() if floor else None
    if room is None or cs is None:
        return

    # Header: round banner + room one-liner.
    n_hostile = sum(1 for eid in cs.participants
                    if world.get(eid) and world.get(eid).is_alive())
    n_exits = len(room.exits or {})
    title = (f"⚔ WALKA — Runda {cs.round} · "
             f"{room.display_short_title()} · "
             f"{n_hostile} {'wróg' if n_hostile == 1 else 'wrogów'} · "
             f"{n_exits} {'wyjście' if n_exits == 1 else 'wyjścia'}")
    text(surf, title, x + 14, y + 10, DANGER, L.font_small + 1, True)
    pygame.draw.line(surf, BORDER, (x + 14, y + 30),
                     (x + w - 14, y + 30), 1)

    # Build the cards from cs.participants. Group by band.
    try:
        from ..engine import combat as _cmb
    except Exception:
        return
    engaged_ids = []
    ranged_ids  = []
    for eid in cs.participants:
        ent = world.get(eid)
        if ent is None or not ent.is_alive():
            continue
        band = cs.bands.get(eid, _cmb.BAND_ENGAGED)
        if band == _cmb.BAND_AT_RANGE:
            ranged_ids.append(eid)
        else:
            engaged_ids.append(eid)

    # Selection: lazy-init to first engaged (or first ranged) target.
    sel_id = getattr(cs, "selected_target_id", None)
    if sel_id is None or world.get(sel_id) is None or not world.get(sel_id).is_alive():
        candidates = engaged_ids + ranged_ids
        sel_id = candidates[0] if candidates else None
        try:
            cs.selected_target_id = sel_id
        except AttributeError:
            pass

    # Layout: two horizontal strips for the two bands, then player chip.
    cy = y + 42
    card_h = max(70, min(110, (h - 130) // 2))
    if ranged_ids:
        text(surf, "DYSTANS:", x + 14, cy, ACCENT2, L.font_small - 1, True)
        cy += 14
        cy = _draw_enemy_card_row(surf, world, cs, ranged_ids,
                                  x + 14, cy, w - 28, card_h,
                                  L, sel_id, click_registry)
        cy += 6
    if engaged_ids:
        text(surf, "ZWARCIE:", x + 14, cy, DANGER, L.font_small - 1, True)
        cy += 14
        cy = _draw_enemy_card_row(surf, world, cs, engaged_ids,
                                  x + 14, cy, w - 28, card_h,
                                  L, sel_id, click_registry)

    # Player chip at the bottom of the arena.
    chip_h = 76
    chip_y = y + h - chip_h - 10
    _draw_player_combat_chip(surf, world, x + 14, chip_y, w - 28, chip_h, L)


def _draw_enemy_card_row(surf, world, cs, eids, x, y, w, h, L,
                         sel_id, click_registry):
    """Lay out enemy cards horizontally in a row. Returns the y after
    the row ends, so the caller can stack the next band beneath."""
    if not eids:
        return y
    n = len(eids)
    gap = 8
    card_w = max(110, (w - (n - 1) * gap) // n)
    cx = x
    for eid in eids:
        ent = world.get(eid)
        if ent is None:
            continue
        is_sel = (eid == sel_id)
        # Card frame.
        col_border = DANGER if is_sel else BORDER
        pygame.draw.rect(surf, PANEL_BG, (cx, y, card_w, h))
        pygame.draw.rect(surf, col_border, (cx, y, card_w, h),
                         2 if is_sel else 1)
        # Portrait slot — 48×48 placeholder.
        port_size = 48
        _draw_entity_portrait_placeholder(surf, ent,
                                          cx + 6, y + 6,
                                          port_size, port_size)
        # Name + HP + statuses.
        nm_x = cx + 6 + port_size + 8
        nm_w = card_w - (port_size + 22)
        nm = ent.display_name()
        f_nm = font(L.font_small - 1, bold=is_sel)
        # Trim to fit.
        if f_nm.size(nm)[0] > nm_w:
            while nm and f_nm.size(nm + "…")[0] > nm_w:
                nm = nm[:-1]
            nm += "…"
        img = f_nm.render(nm, True, BRIGHT_TEXT if is_sel else NORMAL_TEXT)
        surf.blit(img, (nm_x, y + 6))
        # HP bar.
        hp_bar(surf, nm_x, y + 22, nm_w, 8, ent.hp, ent.max_hp)
        text(surf, f"HP {ent.hp}/{ent.max_hp}  AC {ent.ac}",
             nm_x, y + 32, NORMAL_TEXT, L.font_small - 2)
        # Statuses (truncated).
        if ent.conditions:
            try:
                from ..engine import combat as _cmb
                lbl = ", ".join(_cmb.status_label(s, "pl")
                                for s in ent.conditions)
            except Exception:
                lbl = ", ".join(ent.conditions)
            f_st = font(L.font_small - 2)
            if f_st.size(lbl)[0] > nm_w:
                while lbl and f_st.size(lbl + "…")[0] > nm_w:
                    lbl = lbl[:-1]
                lbl += "…"
            text(surf, lbl, nm_x, y + 46, WARN, L.font_small - 2)

        # Click zone: select this enemy as target.
        if click_registry is not None:
            def _select(eid=eid, cs=cs):
                try:
                    cs.selected_target_id = eid
                except AttributeError:
                    pass
            click_registry.add((cx, y, card_w, h), _select,
                               tooltip=f"Cel: {ent.display_name()}",
                               category="combat_target")
        cx += card_w + gap
    return y + h


def _draw_player_combat_chip(surf, world, x, y, w, h, L):
    """Player loadout strip shown at the bottom of the combat arena.
    Echoes the paper-doll's weapon slots so the player can see at-a-
    glance what they're swinging with and what's coated."""
    ch = world.character
    pygame.draw.rect(surf, PANEL_BG, (x, y, w, h))
    pygame.draw.rect(surf, ACCENT, (x, y, w, h), 1)
    text(surf, "TY", x + 8, y + 4, ACCENT, L.font_small - 1, True)
    # Weapons.
    main_id = getattr(ch, "wielded_main_id", None)
    off_id  = getattr(ch, "wielded_offhand_id", None)
    main_ent = world.get(main_id) if main_id else None
    off_ent  = world.get(off_id)  if off_id  else None
    main_name = main_ent.display_name() if main_ent else "pięść"
    off_name  = off_ent.display_name()  if off_ent  else "—"
    text(surf, f"Główna: {main_name}", x + 8, y + 20,
         BRIGHT_TEXT, L.font_small - 1)
    text(surf, f"Pomocnicza: {off_name}", x + 8, y + 36,
         BRIGHT_TEXT, L.font_small - 1)
    # Coating.
    coating = None
    if main_ent is not None and main_ent.state:
        coating = main_ent.state.get("coating")
    if coating and coating.get("hits_remaining", 0) > 0:
        text(surf, f"Powłoka: {coating.get('damage_type','?')} "
                   f"({coating['hits_remaining']})",
             x + 8, y + 52, WARN, L.font_small - 2)
    # HP + AC on the right side.
    hp_w = max(140, w // 3)
    hp_x = x + w - hp_w - 8
    hp_bar(surf, hp_x, y + 22, hp_w, 10, ch.hp, ch.max_hp)
    text(surf, f"HP {ch.hp}/{ch.max_hp}   AC {ch.effective_ac(world)}",
         hp_x, y + 34, NORMAL_TEXT, L.font_small - 1)


def _draw_player_portrait_placeholder(surf, character, x, y, w, h):
    """Placeholder for the player portrait. Future P27 swaps in
    `assets/portraits/<class>.png` (or background fallback). Today: a
    tinted square with the first letter of the character name + class
    glyph in the corner."""
    tint = (40, 50, 60)
    if character.class_key:
        # Slight per-class tint so the placeholder isn't a uniform gray.
        seed = sum(ord(c) for c in character.class_key) % 6
        palette = [(48, 44, 60), (60, 48, 44), (44, 60, 48),
                   (44, 50, 60), (60, 56, 44), (50, 44, 60)]
        tint = palette[seed]
    pygame.draw.rect(surf, tint, (x, y, w, h))
    pygame.draw.rect(surf, ACCENT, (x, y, w, h), 2)
    initial = (character.name or "?")[:1].upper() if character.name else "?"
    img = font(max(28, h // 2), bold=True).render(initial, True, BRIGHT_TEXT)
    surf.blit(img, (x + (w - img.get_width()) // 2,
                    y + (h - img.get_height()) // 2))
    # Class glyph in corner.
    if character.class_key:
        c_img = font(max(10, h // 8)).render(
            character.class_key[:3].upper(), True, ACCENT2)
        surf.blit(c_img, (x + 4, y + h - c_img.get_height() - 4))


def _draw_silhouette(surf, target, plan, x, y, w, h, L,
                     selected_zone, *, cs=None,
                     click_registry=None) -> None:
    """P26a — render a body silhouette with clickable body-part zones.

    Layout is plan-dependent. Each zone gets a colored rect (red gradient
    by HP fraction), its label, and a click hit-zone. The selected zone
    gets a thick accent border.

    Plans we support natively:
      humanoid          — vertical 5-row layout (head/torso/arms/legs)
      small_quadruped   — wide horizontal layout
      drone             — 3-row stack (sensor/body/propulsion)
      blob              — single big rect
    All other plans fall back to a vertical "stack of zones" rendering.
    """
    pygame.draw.rect(surf, (24, 28, 36), (x, y, w, h))
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1)

    # Decide the layout family.
    zones_in_plan = set(plan.keys())
    body_parts = target.body_parts or {}

    def _zone_rect(zone_key: str) -> Tuple[int, int, int, int]:
        return _zone_layout_rect(zones_in_plan, zone_key, x, y, w, h)

    def _zone_color(zp: dict, broken: bool) -> Tuple[int, int, int]:
        if broken:
            return (90, 30, 30)
        frac = (zp.get("hp", 1) / max(1, zp.get("max_hp", 1)))
        # Healthy = teal-blue; wounded = redder.
        r = int(60 + (200 - 60) * (1 - frac))
        g = int(120 * frac + 40)
        b = int(140 * frac + 40)
        return (r, g, b)

    for zone_key, props in plan.items():
        rect = _zone_rect(zone_key)
        if rect is None:
            continue
        rx, ry, rw, rh = rect
        zp = body_parts.get(zone_key) or {}
        broken = zp.get("broken", False)
        color = _zone_color(zp, broken)
        pygame.draw.rect(surf, color, (rx, ry, rw, rh))
        # Selected zone gets a thicker accent border + glow effect.
        if zone_key == selected_zone:
            pygame.draw.rect(surf, DANGER, (rx - 1, ry - 1, rw + 2, rh + 2), 2)
        else:
            pygame.draw.rect(surf, BORDER, (rx, ry, rw, rh), 1)
        # Label centered in the rect (single short word).
        label = props.get("label_pl", zone_key)
        # Truncate to fit.
        f_lbl = font(max(9, min(L.font_small - 2, rh // 2)))
        if f_lbl.size(label)[0] > rw - 4:
            while label and f_lbl.size(label + "…")[0] > rw - 4:
                label = label[:-1]
            label = label + "…"
        img = f_lbl.render(label, True, BRIGHT_TEXT)
        surf.blit(img, (rx + (rw - img.get_width()) // 2,
                        ry + (rh - img.get_height()) // 2))
        # Click zone — sets cs.targeted_zone_by_eid for this target.
        if click_registry is not None and cs is not None:
            def _select(zk=zone_key, eid=target.entity_id, _cs=cs):
                _cs.targeted_zone_by_eid[eid] = zk
            click_registry.add((rx, ry, rw, rh), _select,
                               tooltip=props.get("label_pl", zone_key),
                               category="vats_zone")


def _zone_layout_rect(zones_in_plan, zone_key, x, y, w, h):
    """Return the pixel rect (x, y, w, h) for a body-zone within the
    given silhouette frame. Layouts:
      humanoid (head/torso/arms/legs)
      small_quadruped
      drone (sensor/body/propulsion)
      blob (single mass)
    """
    pad = 6
    iw = w - pad * 2
    ih = h - pad * 2
    x0 = x + pad
    y0 = y + pad

    is_humanoid = {"head", "torso", "l_arm", "r_arm", "l_leg", "r_leg"} <= zones_in_plan
    is_drone = {"sensor", "body", "propulsion"} <= zones_in_plan
    is_quadruped = {"head", "torso", "l_leg", "r_leg"} <= zones_in_plan and not is_humanoid

    if is_humanoid:
        # 4-row layout: head | (arm | torso | arm) | torso (continued) | (leg | leg)
        head_h = int(ih * 0.20)
        body_h = int(ih * 0.40)
        leg_h  = ih - head_h - body_h
        # Head: centered, ~40% wide.
        if zone_key == "head":
            hw = int(iw * 0.42)
            return (x0 + (iw - hw) // 2, y0, hw, head_h)
        # Arms + torso row.
        if zone_key in ("l_arm", "torso", "r_arm"):
            arm_w = int(iw * 0.22)
            torso_w = iw - 2 * arm_w
            ry = y0 + head_h
            if zone_key == "l_arm":
                return (x0, ry, arm_w, body_h)
            if zone_key == "torso":
                return (x0 + arm_w, ry, torso_w, body_h)
            return (x0 + arm_w + torso_w, ry, arm_w, body_h)
        # Legs.
        if zone_key in ("l_leg", "r_leg"):
            leg_w = (iw - 2) // 2
            ry = y0 + head_h + body_h
            if zone_key == "l_leg":
                return (x0, ry, leg_w, leg_h)
            return (x0 + leg_w + 2, ry, leg_w, leg_h)
        return None

    if is_drone:
        # 3-row stack.
        if zone_key == "sensor":
            return (x0, y0, iw, int(ih * 0.25))
        if zone_key == "body":
            return (x0, y0 + int(ih * 0.25), iw, int(ih * 0.50))
        if zone_key == "propulsion":
            return (x0, y0 + int(ih * 0.75), iw, int(ih * 0.25))
        return None

    if is_quadruped:
        # Side-on view: head on the right, two legs spread, torso on the left.
        if zone_key == "head":
            hw = int(iw * 0.30)
            return (x0 + iw - hw, y0 + int(ih * 0.20), hw, int(ih * 0.40))
        if zone_key == "torso":
            tw = int(iw * 0.55)
            return (x0, y0 + int(ih * 0.30), tw, int(ih * 0.40))
        if zone_key == "l_leg":
            return (x0 + int(iw * 0.10), y0 + int(ih * 0.70), int(iw * 0.25),
                    int(ih * 0.25))
        if zone_key == "r_leg":
            return (x0 + int(iw * 0.40), y0 + int(ih * 0.70), int(iw * 0.25),
                    int(ih * 0.25))
        return None

    # Blob / fallback — first zone fills.
    return (x0, y0, iw, ih)


def _draw_entity_portrait_placeholder(surf, ent, x, y, w, h):
    """Placeholder rectangle for an enemy/NPC portrait. Uses
    entity_type to pick a glyph + tint so the player has a coarse
    visual cue until real art lands at P27. Future enhancement: load
    `assets/enemies/<key>.png` here and blit if present."""
    et = getattr(ent, "entity_type", "object")
    glyph = "?"
    tint = (40, 40, 50)
    if et == "monster":
        glyph = "⚔"; tint = (60, 30, 30)
    elif et == "crawler":
        glyph = "☻"; tint = (45, 45, 60)
    elif et == "npc":
        glyph = "☺"; tint = (40, 50, 40)
    elif et == "corpse":
        glyph = "✕"; tint = (50, 40, 40)
    pygame.draw.rect(surf, tint, (x, y, w, h))
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1)
    img = font(max(14, w // 2), bold=True).render(glyph, True, BRIGHT_TEXT)
    surf.blit(img, (x + (w - img.get_width()) // 2,
                    y + (h - img.get_height()) // 2))


# ── Paper-doll + quick-strip (right sidebar redesign) ────────────────

# Slot keys + grid position. Layout is 3×3 with center reserved for torso.
PAPER_DOLL_SLOTS = [
    ("head",   "H", "Głowa",        (1, 0)),
    ("torso",  "T", "Tors",         (1, 1)),
    ("legs",   "L", "Nogi",         (1, 2)),
    ("main",   "M", "Główna ręka",  (0, 1)),
    ("off",    "O", "Pomocnicza",   (2, 1)),
    ("acc",    "A", "Akcesorium",   (0, 2)),
    ("back",   "B", "Plecy",        (2, 2)),
]


def draw_paper_doll(surf, world, x, y, w, h, layout=None, *,
                    click_registry=None) -> int:
    """Render the 7-slot paper-doll grid on the right sidebar. Returns
    the y after the doll ends, for caller stacking.

    P24.5: only `main` and `off` slots are wired to actual gameplay
    state (existing P23 wield system). The other 5 slots render but
    their swap popovers are no-ops — P25 wires the full 7-slot logic.
    """
    L = _resolve_layout(layout)
    ch = world.character
    title = "EKWIPUNEK"
    text(surf, title, x + 4, y, ACCENT, L.font_small - 1, True)
    grid_y = y + 16
    # P27 (P25-UX-1): bump cell size 36→52 so slots are easier to
    # click precisely.
    cell = max(48, min(64, (w - 24) // 3))
    grid_w = cell * 3
    grid_x = x + (w - grid_w) // 2

    def _slot_entity(slot_key):
        if slot_key == "main":
            return world.get(getattr(ch, "wielded_main_id", None)) \
                if getattr(ch, "wielded_main_id", None) else None
        if slot_key == "off":
            return world.get(getattr(ch, "wielded_offhand_id", None)) \
                if getattr(ch, "wielded_offhand_id", None) else None
        # P25 will wire the rest.
        worn = (getattr(ch, "worn_slots", None) or {})
        eid = worn.get(slot_key)
        return world.get(eid) if eid else None

    for slot_key, letter, label, (cx, cy) in PAPER_DOLL_SLOTS:
        sx = grid_x + cx * cell
        sy = grid_y + cy * cell
        ent = _slot_entity(slot_key)
        # Cell.
        col = ACCENT2 if ent is not None else DIM_TEXT
        pygame.draw.rect(surf, PANEL_BG, (sx, sy, cell - 4, cell - 4))
        pygame.draw.rect(surf, col, (sx, sy, cell - 4, cell - 4),
                         2 if ent is not None else 1)
        # Letter + content.
        letter_img = font(L.font_small, bold=True).render(
            letter, True, BRIGHT_TEXT if ent is not None else DIM_TEXT)
        surf.blit(letter_img, (sx + 4, sy + 4))
        if ent is not None:
            # Tiny icon placeholder (colored fill) + first 2 chars of name.
            tag_short = ent.display_name()[:6]
            ti = font(L.font_small - 3).render(tag_short, True, BRIGHT_TEXT)
            surf.blit(ti, (sx + 4, sy + cell - 18))
        # Click zone.
        if click_registry is not None:
            def _open(slot=slot_key, slot_label=label,
                      world=world):
                # P24.5: only main/off truly act; others are no-op for
                # now. We attach the intent string into a Game attr so
                # the handler picks it up.
                world._pending_slot_swap = (slot, slot_label)
            click_registry.add((sx, sy, cell - 4, cell - 4), _open,
                               tooltip=label, category="paperdoll_slot")
    return grid_y + cell * 3 + 4


def draw_quick_strip(surf, world, x, y, w, h, layout=None, *,
                     click_registry=None) -> int:
    """Render up to 5 carried items in compact cards. Click → use.
    Returns y after rendering."""
    L = _resolve_layout(layout)
    ch = world.character
    text(surf, "PRZY SOBIE", x + 4, y, ACCENT, L.font_small - 1, True)
    cy = y + 16
    inv_ids = list(getattr(ch, "inventory_ids", []) or [])
    # Don't list worn / wielded items here.
    worn_ids = set()
    if getattr(ch, "wielded_main_id", None):
        worn_ids.add(ch.wielded_main_id)
    if getattr(ch, "wielded_offhand_id", None):
        worn_ids.add(ch.wielded_offhand_id)
    visible = [eid for eid in inv_ids if eid not in worn_ids][:5]
    row_h = 22
    for eid in visible:
        ent = world.get(eid)
        if ent is None:
            continue
        name = ent.display_name()
        line = f"• {name}"
        f_b = font(L.font_small - 1)
        max_w = w - 12
        if f_b.size(line)[0] > max_w:
            while line and f_b.size(line + "…")[0] > max_w:
                line = line[:-1]
            line += "…"
        text(surf, line, x + 4, cy, NORMAL_TEXT, L.font_small - 1)
        if click_registry is not None:
            cmd = f"użyj {name}"
            def _use(c=cmd):
                world._pending_quick_use = c
            click_registry.add((x, cy - 2, w, row_h - 2), _use,
                               tooltip=f"Użyj: {name}",
                               category="quickstrip")
        cy += row_h
    extra = max(0, len(inv_ids) - len(worn_ids) - len(visible))
    if extra > 0:
        text(surf, f"+{extra} więcej…", x + 4, cy, DIM_TEXT, L.font_small - 2)
        cy += row_h
    return cy


def _soft_wrap(s: str, max_w: int, size: int = 13):
    f = font(size)
    if f.size(s)[0] <= max_w:
        return [s]
    out = []
    words = s.split()
    cur = ""

    def _emit_long_word(word: str):
        """Break a single word that is wider than max_w by characters.
        Prompt 23.5 (backlog #1): the previous _soft_wrap accepted a
        single overlong word as its own line and rendered it past the
        log panel's right edge — visually "overlapping" the sidebar.
        Now we hard-break by character so every emitted line fits."""
        seg = ""
        for ch in word:
            if f.size(seg + ch)[0] <= max_w:
                seg += ch
            else:
                if seg:
                    out.append(seg)
                seg = ch
        if seg:
            out.append(seg)

    for w in words:
        cand = (cur + " " + w).strip()
        if f.size(cand)[0] <= max_w:
            cur = cand
        else:
            if cur:
                out.append(cur)
                cur = ""
            # `w` alone may still exceed max_w — break it by chars.
            if f.size(w)[0] > max_w:
                _emit_long_word(w)
            else:
                cur = w
    if cur:
        out.append(cur)
    return out
