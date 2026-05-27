# Dungeon Kraulem — Backlog

Notatki o rzeczach do poprawy. Po commit/fix przerzucamy do "Done"
albo usuwamy. Najnowsze na górze.

---

## Open

### UX-5 · Audio: prawdziwa muzyka klimatyczna, nie pikanie w tle
**Problem (user):** "dźwięk w grze to tylko pikanie w tle, liczyłem
na jakąś muzyczkę pasującą do klimatu, a nie taki ambient".

**Diagnoza:** `ui/audio.py` jest gotowy (pygame.mixer init, load,
play_sfx, play_music). `assets/audio/{sfx,music}` istnieją ale są
PUSTE — brak plików .wav/.ogg/.mp3. AUDIO_ENABLED=True ale nie ma
czego załadować. P29.13 (Audio assets) zaznaczone jako done w
trackerze, ale tylko hookuje API; samych dźwięków brak.

**Fix-szkic:**
- Wybrać ścieżki: menu / gameplay (per band-piętra) / walka /
  safehouse / victory / defeat / boss.
- DCC-flavor: synth-wave / chiptune retro game-show, gritty
  industrial dla bossów, lekki ambient + jazzy beat dla safehouse.
- Albo proceduralnie (jak P29.13 SFX z numpy), albo zewnętrzne CC0
  (OpenGameArt, Freesound). Procedural daje pełną kontrolę +
  unikamy licencji.
- music_for_state(state, floor_number, in_combat) w game.py state
  transitions; cross-fade między utworami.

**Pliki:** `ui/audio.py` (już ma `play_music`), `engine/game.py`
(state transitions), nowy `ui/music_director.py` lub
`audio_assets/` z proceduralnie generowanymi .wav-ami przy build.

---

### UX-4 · Rozmowa z NPC nie ma żadnej treści — same kości
**Problem (user):** "akcja rozmowy z NPC ciągle kompletnie nie ma
sensu". Screenshot: `pogadaj z Stary Kompas` → tylko
`[rozmowa] d20(20) + CHA(+1) + tła(+0) = 21 vs TT 10 → kryt. sukces`.
Zero dialogu, zero flavora, zero info dla gracza.

**Fix-szkic:**
- `content/data/npc_dialogues.py` — dict[npc_template_id ->
  {"opening": [...], "outcomes": {"crit_success": [...],
  "success": [...], "partial": [...], "fail": [...], "crit_fail":
  [...]}, "rewards_on_crit": ..., "consequences_on_fail": ...}]
- Per-outcome line wybierany losowo z puli; różny dla każdego NPC.
- crit. sukces → info-drop (sponsor lead, plotka, krótki quest);
  porażka → threat bump w pokoju, sponsor minus, NPC się obraża;
  kryt. porażka → potencjalna eskalacja do walki.
- Exhaustion: po N rozmowach NPC mówi "nie mam ci nic więcej do
  powiedzenia" + akcja "pogadaj" znika z [Postacie].
- Routing przez `engine/handlers/social.py` (nowy) albo w istniejącej
  ścieżce gdzie teraz dispatchuje "rozmowa" roll.

**Powiązane:** UX-2 (exhausted actions) — wykorzystać ten sam
mechanizm "wyczerpane = znika z paneli".

---

### UX-3 · Niespójność fog-of-war: opis vs panel [Obiekty]
**Problem (user, ze screenshota):**
- Opis pokoju: `Widzisz: coś ?, ekran sponsorski, urządzenie ?,
  mebel ?, skrzynia ?, ktoś ?, ktoś ?, skrzynia ?, rzecz ?`
- Panel `[Obiekty]` w akcjach: `ekran sponsorski, automat z kawą,
  drewniane meble, luźne krzesło, automat sponsorski, kosz na
  śmieci, pęknięty kubek, baton energetyczny`

Spojler — gracz widzi rozwiązanie w panelu zamiast się go domyślać.

**Fix-szkic:**
- Znaleźć kod budowy panelu `[Obiekty]` (prawdopodobnie
  `engine/handlers/look.py` lub `engine/visibility.py`).
- Przepuścić nazwy obiektów przez ten sam visibility filter co opis
  pokoju (jeśli `state == "unknown"` → "coś ?", "seen" → pełna
  nazwa). Funkcja prawdopodobnie istnieje już (engine/visibility.py
  ma `describe_entity_for_player`).
- Decyzja: spójność > UI-discovery. Wolimy "ślepego" panelu (gracz
  musi `sprawdź X` żeby ujawnić) niż spoilera. Skutek: panel
  pokazuje "coś ?" 3× a po `sprawdź` ujawnia nazwy.
- Alternatywa: w panelu Obiekty zostawić pełne nazwy ALE w opisie
  pokoju też je dawać (zniesienie fog-of-war na poziomie pokoju).
  Mniej DCC-faithful, ale jednak spójne.

**Polecam:** opcja 1 (panel = visibility-filtered). Zachowuje
napięcie eksploracji.

---

### UX-2 · Wyczerpane akcje znikają z action panelu
**Problem (user):** "mogę spamować te same akcje bez większego celu,
jeśli jakaś akcja jest wyczerpana w danej lokacji jak tutaj to ją
usuwajmy z action logu". Screenshot: 3× `> rozejrzyj się` w logu z
identycznym tekstem.

**Fix-szkic:**
- `room.state["actions_done"] = set()` (zachowane przez save/load
  bo room.state już jest).
- Handler `rozejrzyj się` po wykonaniu: dodaje "rozejrzeć" do
  zbioru, drugi call → "Już to widziałeś. Czas: 0 minut" (lub
  refusal).
- Builder action_panel filtruje listę: jeśli `"rozejrzeć" in
  room.state["actions_done"]` → nie pokazuj w [Akcje].
- To samo dla `przeszukaj pokój`, `nasłuchuj`.
- Niektóre akcje per-room-reset (po `descent`, `room_change`)
  vs. permanent. "Rozejrzyj" jest permanent dla pokoju.

**Pliki:** `engine/handlers/look.py`, `engine/handlers/search.py`
(jeśli istnieją), `engine/game.py` (action_panel build).

---

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
