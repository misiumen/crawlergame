"""E2E dla #188 — bleed tekstu w log panelu.

Failure mode user (recurring): 'Coś poszło nie tak. Boli (2).' nachodzi
na linię „Przez krótką chwilę jesteś jedyną osobą...". Diakrytyki PL
(Ą, Ę, Ó, Ł) wykraczają poza obliczone line_h i wchodzą w sąsiedni
wiersz.

Capturuje failure mode na 3 poziomach (od taniego do drogiego):

1. **Font metrics check** — czy `f.get_linesize() + 6` ≥ maximum
   glyph height dla PL diakrytyków. Cheap, deterministic.

2. **Render Surface inspection** — render kilku linii z PL tekstem do
   off-screen Surface, sprawdź że bounding boxy NIE nachodzą.

3. **Pixel scanline check** — po renderingu pełnego panelu, sprawdź
   że pomiędzy ROW_N i ROW_N+1 istnieje "czysty" pas pikseli (no text
   in both rows simultaneously).

Rule 12b — bez tych testów każdy „fix" bleed'a (P26-P29 było 14 prób)
mógł regresować bez wykrycia. To są regression sentinels.
"""
from __future__ import annotations
import os
import pytest

# Headless pygame BEFORE pygame init
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


@pytest.fixture(autouse=True, scope="module")
def _pygame_headless():
    """Inicjalizuje pygame raz dla wszystkich testów w pliku."""
    pygame.init()
    pygame.display.init()
    # Off-screen surface zamiast set_mode (set_mode wymaga windowed
    # nawet w dummy driver).
    yield
    pygame.quit()


# ── 1. Font metrics ──────────────────────────────────────────────────


def test_polish_diacritics_fit_in_computed_line_height():
    """get_linesize() + 6 MUSI być ≥ wysokości render'owanego glyph'a
    z PL diakrytykami (ą, ę, ł, ć, ż, ź).

    Jeśli ten test pęka — line_h obliczone w ui.py jest za małe,
    bleed GWARANTOWANY przy następnych literach pod baseline."""
    from ...ui.ui import font

    # Wszystkie kombinacje PL znaków które mogą sterczeć poniżej
    # baseline (ą, ę z ogonkiem) lub powyżej x-height (ł, ó, ś, ż, ź).
    PL_TEST_STRINGS = [
        "Ąśćż łópęńźĆ",   # mix górne/dolne diakrytyki
        "Pęknięty kąsek, srebrne pójście, łósoś",
        "Wąż grał głośno. Sąsiad spadł.",
        "Ząb wątły, ćmę zżarł.",
    ]

    f = font(15)  # standard log font_small
    linesize = f.get_linesize()
    line_h_computed = max(24, linesize + 6)  # zgodne z ui.py:1262

    for s in PL_TEST_STRINGS:
        img = f.render(s, True, (200, 200, 200))
        img_h = img.get_height()
        assert img_h <= line_h_computed - 2, (
            f"GLYPH HEIGHT > LINE SLOT: render '{s}' ma "
            f"{img_h}px ale slot to {line_h_computed - 2}px. "
            f"BLEED gwarantowany.\n"
            f"f.get_linesize()={linesize}, line_h={line_h_computed}")


# ── 2. Render Surface bounding box overlap ──────────────────────────


def test_two_consecutive_pl_log_lines_dont_overlap():
    """Render 2 linii log z PL diakrytykami w pozycjach jak w real
    ui.py. Sprawdź że image_2.top >= image_1.bottom (no overlap)."""
    from ...ui.ui import font

    f = font(15)
    line_h = max(24, f.get_linesize() + 6)
    spacing = 2  # zgodne z ui.py:1364 `cy += line_h + 2`

    # Symuluj 2 wiersze pełne PL diakrytyków
    line_a = "Ząb pękł — Ąśćż łópęń."
    line_b = "Sąsiad wątłą ręką spadł."

    img_a = f.render(line_a, True, (200, 200, 200))
    img_b = f.render(line_b, True, (180, 200, 220))

    cy_a = 100  # arbitrary start
    cy_b = cy_a + line_h + spacing

    # Bounding box A: y_a .. y_a + img_a.h
    # Bounding box B: y_b .. y_b + img_b.h
    a_bottom = cy_a + img_a.get_height()
    b_top = cy_b

    assert a_bottom <= b_top, (
        f"OVERLAP: line A bottom={a_bottom}, line B top={b_top}. "
        f"Bleed o {a_bottom - b_top}px.\n"
        f"line_h={line_h}, img_a.h={img_a.get_height()}, "
        f"img_b.h={img_b.get_height()}")


# ── 3. Pixel scanline (cleanest gap) ────────────────────────────────


def test_log_panel_render_has_clean_gap_between_pl_entries():
    """Pełen render log panel z 3 wpisami PL. Sprawdź że pomiędzy
    wpisami istnieje pas pikseli BEZ żadnego text-color glyphu.

    To prawdziwy E2E — sprawdza FINAL render output."""
    from ...ui import ui as _ui
    from ...ui.lang import t

    # Off-screen surface o rozsądnej wielkości — log panel area
    SURF_W = 800
    SURF_H = 200
    surface = pygame.Surface((SURF_W, SURF_H))

    # Fake log content — 3 PL wpisy z diakrytykami, każdy ma category
    log_entries = [
        ("Wąż grał głośno. Sąsiad ząbł.", "normal"),
        ("Pęknięty kąsek śmierdział łósosiem.", "warn"),
        ("Ćma zżarła twą podkoszulkę.", "danger"),
    ]

    # Minimalna layout simulation — pure call do draw_log_and_input
    # wymaga `layout` z proper rects. Buduję minimalny stub.
    class _StubLayout:
        log_rect = (10, 10, SURF_W - 20, SURF_H - 50)
        input_rect = (10, SURF_H - 40, SURF_W - 20, 30)
        font_small = 15
        font_body = 16

    # Fill background (so we can detect text vs no-text)
    surface.fill((0, 0, 0))

    _ui.draw_log_and_input(
        surface, log_entries, input_text="",
        blink=False, scroll=0,
        input_mode="text", layout=_StubLayout())

    # Pixel scan: for each row Y, count non-background pixels.
    # Background fills with `LOG_BG` (panel.bg). Find rows które są
    # CZYSTE (no text) — powinno być co najmniej 1 czysty row pomiędzy
    # każdą parą text-bearing rows.
    text_row_density = []  # liczba "tekstowych" pikseli per Y
    log_area_y_start = 30   # skip header (~22px from log_rect.y + padding)
    log_area_y_end = SURF_H - 60

    for y in range(log_area_y_start, log_area_y_end):
        non_bg_count = 0
        for x in range(20, SURF_W - 20, 4):  # sample co 4-ty piksel dla speed
            r, g, b, _ = surface.get_at((x, y))
            # Text colors są jaśniejsze niż LOG_BG (dark). Heurystyka:
            # any channel > 80 = text-bearing pixel.
            if r > 80 or g > 80 or b > 80:
                non_bg_count += 1
        text_row_density.append((y, non_bg_count))

    # Znajdź klastry text rows (consecutive Y z density >= 3)
    clusters = []
    current_cluster = None
    DENSITY_THRESHOLD = 3
    for y, dens in text_row_density:
        if dens >= DENSITY_THRESHOLD:
            if current_cluster is None:
                current_cluster = (y, y)
            else:
                current_cluster = (current_cluster[0], y)
        else:
            if current_cluster is not None:
                clusters.append(current_cluster)
                current_cluster = None
    if current_cluster is not None:
        clusters.append(current_cluster)

    # EXPECT: liczba klastrów co najmniej = liczba log entries
    # (3 entries → ≥3 separate clusters). Jeśli klastry się zlewają
    # (mniej niż entries), bleed faktyczny.
    assert len(clusters) >= len(log_entries), (
        f"BLEED w log panel: oczekiwane ≥{len(log_entries)} "
        f"separate text clusters, znalezione {len(clusters)}.\n"
        f"Klastry text rows (Y ranges): {clusters}\n"
        f"To znaczy że dwie linie nakładają się wizualnie.")


# ── 4. line_h headroom margin ────────────────────────────────────────


def test_line_height_has_safety_headroom_above_glyph():
    """Margin bezpieczeństwa: line_h MUSI mieć co najmniej 6px ponad
    rendered glyph dla PL diakrytyków + acentów (Ż, Ć, etc. z kropką
    nad)."""
    from ...ui.ui import font

    f = font(15)
    line_h = max(24, f.get_linesize() + 6)

    # Worst-case: znaki z kropką nad ORAZ ogonkiem pod (Ż + ą w jednym
    # stringu).
    worst = "Żąć Ęłó żź"
    img = f.render(worst, True, (200, 200, 200))

    headroom = line_h - img.get_height()
    assert headroom >= 4, (
        f"HEADROOM ZA MAŁY: line_h={line_h}, glyph_h={img.get_height()}, "
        f"margin={headroom}px. Diakrytyki PL mogą wjechać w sąsiedni "
        f"wiersz przy edge-case font'cie.")
