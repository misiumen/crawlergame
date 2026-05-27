# Dungeon Kraulem — Backlog

Notatki o rzeczach do poprawy. Po commit/fix przerzucamy do "Done"
albo usuwamy. Najnowsze na górze.

---

## Open

### UX-1 · Scroll log: tylko przy overflow tekstu (zgłoszone w P29.37 sweep)

**Problem (user):**
> Scroll powinien się pojawić dopiero gdy jest overflow tekstu, teraz
> zmieniam strony tam, trochę mylące.

**Diagnoza:**
- `engine/game.py:6461-6470` (PgUp/PgDn) — pułap = `len(world.log) - 1`,
  nie zależy od tego ile linii rzeczywiście mieści się w log_rect.
- `engine/game.py:7117-7122` (mouse wheel) — ten sam pułap.
- Efekt: nawet jak w logu jest 5 linii i wszystkie są widoczne, gracz
  może scrollować "wstecz" o 4 wpisy i widzieć przesuwającą się stronę
  złożoną z niczego. Wygląda jak page-flip bez treści.

**Fix-szkic:**
- W `ui/layout.py` lub przy renderze logu policzyć
  `rows_visible = log_rect.h // line_height` (już to liczy
  `draw_log_and_input`).
- Wystawić ile linii mieści się w widoku jako pole layout albo
  helper (np. `world.log_max_visible_rows` ustawiane przy każdym
  draw, albo lepiej: query z `ui.layout`).
- W handlerach scrolla cap = `max(0, len(world.log) - rows_visible)`.
- Jeśli `len(world.log) <= rows_visible` → scrollback jest no-op
  (nic się nie dzieje przy PgUp).
- Opcjonalnie: pokazać wskaźnik scrolla (▲ na górze logu) gdy
  `log_scroll > 0`, ukryty gdy 0 — sygnał że jest gdzie iść.

**Pliki:** `engine/game.py`, `ui/ui.py:draw_log_and_input`,
`ui/layout.py`.

**Test:** smoke który tworzy world z 3-liniowym logiem, woła
PgUp przez handle_keydown, asserta że `log_scroll == 0`. Drugi case:
50-liniowy log, PgUp przesuwa, PgUp znowu się dobija do końca.

---

## Done (recent)

### P29.38 · Polish-only display dla companion status + abilities

Zgłoszone w P29.37 sweep przez user'a (screenshot pokazał "Stan:
active" i "Umiejętności: scout_aerial, warn_danger"). Dodane:
`engine/companion.py` helpery `status_pl()`, `abilities_pl_list()`,
`sponsor_tag_pl()`, `sponsor_tags_pl_list()` z mapowaniami na polski.
Wireowane w `engine/companion_actions.py` (komenda "sprawdź zwierzę")
i `ui/journal.py` (zakładka Towarzysze). Smoke
`test_p29_38_companion_polish` z 9 testami.

**Reguła zapisana w pamięci projektu:** gra jest TYLKO po polsku,
każdy player-facing string PL od początku. Internal slugs (save/test
IDs) zostają snake_case, ale display przechodzi przez polski lookup.
