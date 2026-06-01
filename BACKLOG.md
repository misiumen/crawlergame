# Dungeon Kraulem — Backlog

Notatki o rzeczach do poprawy. Po commit/fix przerzucamy do "Done"
albo usuwamy. Najnowsze na górze.

---

## Status sesji 2026-05-31

ZROBIONE i wypchnięte: UX-9 (direct dispatch), UX-10 (popover akcji —
mysz+klawiatura, ZOSTAJE: usunięcie zakładek world-interaction),
pełnoekranowy dialog (mysz + art), typy pinów + piny wyjść (UX-7 część),
UX-4b (placeholder dialog dla NPC), UX-6 (znikają piny zużytych obiektów),
CMB-2 (ogony bestii), LOC-1 (nazwy osiągnięć — „Nie tak szybko",
„Pierwszy boss z głowy", „Zabójca karaoke", „Widziałem legendę"),
UX-1 (scroll tylko przy overflow), UX-8 (cel = zejście + „Zadania
dodatkowe"), UX-2 (look/listen/przeszukaj-pokój wyczerpują się per pokój,
znikają z panelu; per-obiekt search bez zmian).

ODŁOŻONE (świadomie):
- **UX-3** — zrewertowane DWUKROTNIE. `display_name()` zostaje. Maska w
  panelu jest poprawna dla realnej gry (trywialne obiekty auto-promują do
  `seen`), ale koliduje z wieloma fixture'ami testów. Prawdziwy fix =
  PARYTET opisu pokoju vs panel na warstwie mgły + promocja w fixture'ach,
  jako jedna świadoma zmiana. NIE override w panelu.
- **Audyt duplikatów osiągnięć** — sweep LOC-1 wyłapał możliwe duplikaty
  (spawn-task odpalony osobno).

EPIKI (nie „szybkie taski", osobne sesje): COMBAT-1 (przeprojektowanie
walki A–D), DIAL-1 (archetypy drzew + system relacji + LLM flavor),
CMB-3 (hitboxy z dostarczonych PNG — czeka na art), UX-10 finał
(usunięcie zakładek Środowisko/Istoty po dopieszczeniu popovera).

---

## Open

### CMB-6 · Ekonomia akcji 2 PA/turę (COMBAT-1 Slice D — odłożone)
**Stan:** ŚWIADOMIE odłożone — za ryzykowne by wpychać bez gracza przy
ekranie. Reszta COMBAT-1 (A: zero-friction start; B: telegraf/kontry;
C: flinch/stagger + zone payoffs; D: dramat widowni + finisher) ZROBIONA
i wypchnięta (commits do 005b455).
**Co zostało:** zamiana „1 akcja → tura wroga" na sekwencję 2 punktów
akcji (ruch+cios, finta+ciężki itd.). Dotyka KAŻDEJ akcji bojowej
(consume-turn) + kadencji `_run_enemy_turn`. Wymaga live-tuningu, nie
ślepego pusha. Pliki: `CombatState` (nowe pole `action_points`),
`_combat_after_player_action`, `_run_enemy_turn`, wszystkie `_combat_*`.



### CMB-4 · Cios w kończynę musi MIEĆ ZNACZENIE (combat depth — Slice C/D)
**Problem (user, playtest):** „złamałem tułów i szczur nawet nie drgnął.
Walka czuje się płytka." Trafienia w strefy nie dają wyczuwalnego
feedbacku poza paskiem HP strefy.
**Diagnoza:** torso z definicji nie ma `maim_status` (to korpus), więc
złamanie go nic nie robi poza obrażeniami — zgodnie z danymi, ale gracz
oczekuje reakcji. Brakuje: reakcji wroga na trafienie (flinch/stagger),
realnego efektu złamania kończyny w jego turze, finisherów.
**To jest COMBAT-1 Slice C + D** (called-shot rdzeniem + ekonomia akcji /
dramat). NIE quick-fix. Zrobić jako osobny, świadomy etap:
- C: klik strefy = atak; głowa→stun, ręce→mniej dmg/disarm, nogi→stop
  ruchu, ogon→strach; flinch/stagger na każdym solidnym trafieniu.
- D: ekonomia akcji (2 PA), reakcje widowni, finisher przy niskim HP.

### CMB-5 · Minimapa 3D / nawigacja między warstwami
**Problem (user):** minimapa ma warstwy (oś Z — ruch w 3 osiach na
piętrze), ale brak sposobu na przełączanie warstw; trudna w nawigacji.
Rozważyć minimapę 3D / izometryczną zamiast płaskich warstw.
**Zakres:** realny redesign UI (osobny task). Pliki: `ui/minimap.py`,
input handler dla zmiany warstwy.

### ORIGIN-1 · Salvage gated przez origin (note for later)
User: rozbieranie powinno być może zablokowane dla mniej technicznych
pochodzeń. Do zrobienia przy refaktorze originów (osobny etap).



### DIAL-1 · Głębokie drzewka dialogowe (sojusze / zdrada / romans / stawki)
**Cel (user):** dużo rozgałęzień, zdrada, sojusze, stawki, romans — jak w
porządnym RPG — BEZ pisania wszystkiego ręcznie.

**Co już jest (silnik wystarczający):** `engine/dialogue.py` — węzły +
opcje z `skill_check (stat, DC)` i `fail_node_id`, `requires_flag`/
`forbids_flag` (gating), `one_shot`, oraz `consequences`: audience,
sponsor, threat, give_item, **set_flag**, log, end. To wystarcza na
rozgałęzienia, stawki (checki), sojusze/zdradę/romans (flagi + relacja +
konsekwencje). Bottleneck = TREŚĆ (ręczne drzewka w
`content/data/npc_dialogues.py`, dziś ~4 drzewka). Pełny ekran rozmowy +
mysz: ZROBIONE (`ui.draw_dialogue_screen`).

**Skalowanie treści bez pisania (rekomendacja — hybryda):**
1. **Szablonowe archetypy drzewek** — kilkanaście parametryzowanych
   drzew („nieufny biegacz", „desperacki sojusznik", „rywal", „romans-
   kandydat") wypełnianych nazwą/frakcją/relacją NPC. Piszesz ~12, grasz
   setki. Deterministyczne, mechaniki pewne.
2. **Relacja/flagi jako system** — generyczne łuki (alliance/betrayal/
   romance) jako stan + relacja; dialog tylko je *ujawnia* przez
   szablonowe linie. Głębia z interakcji systemowych, nie z prozy.
3. **LLM tylko na FLAWOR** — `llm/llm_roles.py` ma już `ROLE_DIALOGUE`
   (lokalny Ollama, bezpieczny fallback, nie mutuje stanu). Może
   generować *prozę* linii NPC na bazie kontekstu; szkielet (gałęzie,
   checki, konsekwencje) zostaje deterministyczny. NIE oddawać LLM-owi
   logiki rozgałęzień/stawek.
**Wniosek:** szkielet szablonowy + flagowy system relacji = dużo RPG przy
małym pisaniu; LLM dokłada zmienność prozy gdy włączony. Czysto-LLM pełne
gałęzie ze stawkami = zawodne.

**Pliki:** `content/data/npc_dialogues.py` (archetypy), `engine/dialogue.py`
(ew. `relationship` delta + romance arc), nowy `engine/relationships.py`?,
`llm/llm_roles.py` (ROLE_DIALOGUE flavor).

---

### UX-10 · Model interakcji ze ŚWIATEM bez zakładek
**Problem (user):** „nie lubię całego designu zakładek dla obiektów
interaktywnych… nienawidzę pomysłu interakcji z grą w ten sposób".
Żeby dotknąć obiektu / postaci / pokoju trzeba przełączać
`[Akcje][Wyjścia][Środowisko][Istoty]…` i wybierać z list — męczące.

**Granica (ważna, wg user'a):**
- **Zakładki ZOSTAJĄ** dla systemów menu: dziennik, crafting,
  lootboxy/skrzynki, ekwipunek — to ekrany-menu, tam zakładki są OK.
- **Zakładki PRECZ** z interakcji ze światem: obiekty, NPC, pokój,
  wyjścia, środowisko. To ma być bezpośrednie, nie nawigacja po
  zakładkach.

**Kierunek (do rozwinięcia):** interakcja BEZPOŚREDNIA i kontekstowa —
klik w encję (pin na ilustracji albo wiersz) ujawnia jej istotne
czasowniki INLINE w miejscu (`sprawdź / pogadaj / zaatakuj / zbierz /
rozbierz…`). Ta sama zasada co COMBAT-1 A („jedna powierzchnia,
działasz na to, co wskazujesz") + spójne z pinami (UX-7/UX-9). Parser
tekstowy zostaje jako równoległa ścieżka.

**Powiązane:** UX-7, UX-9 (piny), COMBAT-1 A. Duży redesign — rozbić na
etapy; iterować w trybie Demo (Intake).

**Status (2026-05-31): POPOVER DZIAŁA (mysz + klawiatura w otwartym menu).**
Klik w pin/encję otwiera kontekstowe menu czasowników przy encji
(`Game.open_entity_popover`, `ui.draw_entity_popover`,
`ui_nav.action_options_for_entity` — te same czasowniki co panel, zawsze z
„Sprawdź" na wierzchu). Encja z 1 czasownikiem pomija menu i działa od
razu. Menu obsługiwane myszą (klik wiersza / klik poza = zamknij) ORAZ
klawiaturą gdy otwarte (↑↓ / Enter / 1-9 / Esc). Auto-zamyka się gdy encja
zniknie / zmiana pokoju. Test: `test_entity_popover.py`. Suite 117/117.

**ZOSTAJE (kolejne etapy):**
- [ ] Klawiaturowe OTWARCIE popovera z pina (np. cyfra pina w trybie nav)
  — wymaga decyzji o bindzie (konflikt z trybem tekstowym). Na razie
  klawiaturowy dostęp do akcji encji przez istniejące zakładki Istoty/
  Środowisko (pełna parzystość możliwości).
- [ ] Usunięcie zakładek world-interaction (Środowisko/Istoty) gdy popover
  je w pełni zastąpi — osobny, ryzykowny krok.

**Pliki:** `ui/ui.py` (`draw_entity_popover`, pin cb), `ui/ui_nav.py`
(`action_options_for_entity`), `engine/game.py` (popover state + open/
close/activate + mouse/keyboard + draw).

---

### UX-4b · „pogadaj" z generycznym NPC nie odpala drzewka (root cause)
**Problem (user, re-test):** „pogadaj z Nadzorca Sortowni" → tylko
`[rozmowa] d20(8) + CHA(-1) + tła(+1) = 8 vs TT 10 → częśc. sukces`,
zero treści. (Powiązane z UX-4.)

**Diagnoza (potwierdzona):** system drzewek dialogowych DZIAŁA
(`engine/dialogue.py` + `content/data/npc_dialogues.py` ma drzewka:
default_crawler / liga_brawurowa / intake_warden / placeholder). ALE
`game.py:_guess_dialogue_tree` (1986) zwraca tree tylko dla
`faction:liga`, `intake`+`floor_boss`, albo `T_CRAWLER`. Generyczny NPC
(„Nadzorca Sortowni") nie pasuje → zwraca `""` → talk-intent przechodzi
do **legacy skill-check** (`game.py:2880` `resolve`) → goły rzut
`[rozmowa]`, bez treści. Co ważne: `npc_dialogues.py:538`
`_build_placeholder_tree()` ISTNIEJE, ale nie jest używane jako
fallback.

**Fix-szkic (mały):**
- `_guess_dialogue_tree`: dla DOWOLNEGO NPC z affordance „talk" bez
  specyficznego drzewka → zwróć `placeholder` zamiast `""`.
- Upewnić się, że legacy `[rozmowa]` roll już nie odpala, gdy jest
  drzewko (albo całkiem wyciąć legacy ścieżkę dla „talk").
- Docelowo: placeholder per-archetyp/sponsor zamiast jednego ogólnego
  (treść wg `docs/CONTENT_BIBLE.md`), ale fallback najpierw.

**Pliki:** `engine/game.py` (`_guess_dialogue_tree`, talk dispatch),
`content/data/npc_dialogues.py` (placeholder), `engine/dialogue.py`.

---

### LOC-1 · Słabe polskie nazwy osiągnięć (tytuł vs. opis zdarzenia)
**Problem (user):** „Osiągnięcia: Konferansjer warknął" jest bez sensu
jako nazwa. To tytuł osiągnięcia za last-stand (`anty_host_warknal`,
`systems/achievements.py:285`) — ale brzmi jak fragment logu opisujący
reakcję KONFERANSJERA, nie wyczyn GRACZA.

**Fix-szkic:**
- Przemianować `fallback_name_pl` na tytuł-wyczyn, np. **„Nie tak
  szybko"** (echo kwestii hosta), „Jedna klatka życia", „Na resztkach
  adrenaliny", „Jeszcze nie teraz". (opis PL już dobry.)
- **Sweep:** przejrzeć WSZYSTKIE `fallback_name_pl` w
  `systems/achievements.py` pod kątem tego samego błędu (nazwa = tytuł
  wyczynu, nie zdanie-zdarzenie). Voice wg `docs/CONTENT_BIBLE.md`.
- Szersza zasada: nazwy = tytuły, nie opisy zdarzeń; opisy zdania pełne.

**Pliki:** `systems/achievements.py`, ew. inne player-facing nazwy.

---

### CMB-2 · Ogony (i inne części) dla bestii w VATS
**Problem (user):** bestie (np. szczur z długim ogonem) powinny mieć
celowalny **ogon**, nie tylko głowa/tułów/łapy — żeby okaleczyć albo
przestraszyć stwora. Części tylko tam, gdzie mają sens.

**Fix-szkic:**
- `content/data/body_plans.py`: dodać zonę `"tail"` (`label_pl:"ogon"`)
  do planu czworonoga — albo nowy plan `large_quadruped`/`tailed_beast`
  dla stworów z ogonem (szczur, bestia-pies). Silnik wspiera
  `maim_status` → trafienie/złamanie ogona = `STATUS_AFRAID` (postraszyć)
  lub `STATUS_SLOWED` (utrata równowagi) + drop przy patroszeniu.
- `ui/portrait_zones.py`: hitbox `tail` per art-key (np. ogon szczura
  zamiatający w prawo) + ew. w archetypie `quadruped`/`beast`.
- Zero zmian w silniku — to dane per-plan/per-art.

**Pliki:** `content/data/body_plans.py`, `ui/portrait_zones.py`.

---

### CMB-3 · Dokładniejsze hitboxy VATS z dostarczonych PNG
**Problem (user):** czy mogę „lepiej zeskanować" dostarczony PNG, żeby
narysować strefy celowania dokładniej?

**Ustalenia:** hitboxy to ręcznie obrysowane znormalizowane boxy per
art-key (`ui/portrait_zones.py HITBOXES`) + generyczne fallbacki
archetypów (stąd niedopasowania do konkretnej ilustracji).
- **Realna ścieżka:** asystent OTWIERA dostarczony PNG (Read renderuje
  obrazy), patrzy na anatomię i ręcznie obrysowuje strefy (głowa/tułów/
  łapy/**ogon**/itd.) pod ten konkretny obrazek. Najpewniejsze, skaluje
  się z dokładaniem artu.
- **Czego unikać:** w pełni automatyczna detekcja semantyczna („znajdź
  ogon") z dowolnego stylizowanego PNG jest zawodna. Analiza alpha/
  sylwetki da bounding-box figury (przydatne do auto-dopasowania ramki),
  ale nie rozróżni „to ręka vs ogon" bez ML (overkill + kruche na
  nie-ludzkich kształtach).
- **Proces docelowy:** user wrzuca portret → asystent ogląda → obrysowuje
  strefy do faktycznego artu.

**Pliki:** `ui/portrait_zones.py` (+ widok delivered PNG przez Read).

---

### COMBAT-1 · Przeprojektowanie odczucia walki (epik)
**Problem (user):** start walki i cała pętla są niesatysfakcjonujące:
zidentyfikuj wroga → wejdź w zakładkę [Istoty] → kliknij „zaatakuj" →
1 tura gra się automatycznie → klikaj aż padnie. Złe odczucie i zła
ergonomia. Oczekiwana zmiana — „probably more dramatically than before".

**Diagnoza:** silnik JUŻ ma głębię (`engine/combat.py`,
`engine/enemy_ai.py`), tylko UX/pacing ją spłaszcza:
- telegraf intencji wroga (`CombatState.enemy_intents`),
- VATS / cios w kończynę (`targeted_zone_by_eid` + `body_plans`),
- warianty ataku `careful`/`heavy`, `defend`, `dodge`, `assess`,
  `reposition` (zbliż/oddal), push-into-hazard / throw / break, `lure`,
- słabości (`Słaby na: …`), bandy (zwarcie/oddal), statusy, frakcje,
  ładowane specjale wroga.
Trzy realne wady: (1) tarcie wejścia (sprawdź + zakładka [Istoty]),
(2) brak znaczącej decyzji na turę → dominuje spam „zaatakuj",
(3) martwy pacing (1 akcja → auto-tura wroga → powtórz).

**Kierunki (user wybrał WSZYSTKIE A–D, 2026-05-31). Kolejność wg
satysfakcja/koszt):**

- **A · Jeden ekran, zero tarcia** *(głównie reuse UI)*: na starcie
  walki auto-zaznacz najbliższego wroga; assess inline pod portretem
  (banda HP, threat, **słabość**, **telegraf intencji**); kontekstowy
  pasek akcji na/pod portretem (Atak / Unik / Obrona / Cel: kończyna /
  Otoczenie). Usuwa krok `sprawdź` i zakładkę [Istoty].

- **B · Odczyt telegrafu i kontry** *(reuse intents+dodge/defend/VATS)*:
  głośno pokaż planowaną intencję wroga („szykuje cios w głowę",
  „ładuje specjał") i każ na nią ODPOWIEDZIEĆ — unik neguje ciężki
  cios, obrona tłumi, atak w ładującą kończynę PRZERYWA specjał. Tura =
  pętla odczyt/kontra zamiast wyścigu obrażeń.

- **C · Cios w kończynę jako główny czasownik**: klik strefy ciała na
  portrecie = atak (nie ukryta podopcja). Głowa = ryzyko/kryt+oszołom,
  ręce = rozbrojenie/mniej ich dmg, nogi = stop podejściu/ucieczce.
  Plus eksploatacja słabości (posmaruj broń kwasem, wepchnij w iskrzące
  przewody). Ujawnia `body_plans`/VATS.

- **D · Pacing + dramat teleturnieju** *(NAJWIĘCEJ nowego kodu+testów)*:
  ekonomia akcji (2 PA/turę → sekwencja decyzji, nie 1 klik); reakcje
  widowni/sponsorów na efektowne zabójstwa (krytyczny cios w kończynę →
  skok widowni → pod sponsora w trakcie walki); prompty finiszera przy
  niskim HP wroga; kinowy log + shake/SFX (częściowo już są).

**Rekomendowana sekwencja:** A+B najpierw (największy zysk/koszt, niemal
sam reuse) → potem C (called-shot rdzeniem) → potem D (ekonomia akcji +
dramat widowni; tu dochodzą nowe systemy + testy).

**Iteracja:** używać trybu **Demo (Intake)** do szybkiego tuningu walki
na F1 — zmiany w `engine/combat.py` propagują do wszystkich trybów.

**Pliki:** `engine/combat.py`, `engine/enemy_ai.py`,
`ui/portrait_zones.py` + render walki w `ui/ui.py`, dispatch w
`engine/game.py` (`_combat_*`), `content/data/body_plans.py`; ekonomia
akcji = nowe pole na `CombatState` + testy.

---

### UX-9 · Klik w pin (sprawdź) otwiera dziennik zamiast inspekcji
**Problem (user):** klik w pin 7 (obiekt „coś ważnego dla zadania")
otwiera dziennik zamiast wykonać `sprawdź`. „wiring here must be janky".

**Diagnoza (potwierdzona):**
- Pin to encja celu z `floor_generator.py:1326`
  (`fallback_name="coś ważnego dla zadania"`, unknown → „???").
- Klik pina NIE inspekcjonuje encji wprost — buduje komendę tekstową
  `"sprawdz " + name` i przepuszcza ją przez fuzzy parser
  (`ui/ui.py` ~938, `command_cb`).
- Parser (`parser_core.py:119`) mapuje słowo **`zadania`** (też
  `cel`/`cele`) na intent `journal_objectives` → `_open_journal(
  TAB_OBJECTIVES)`. Stąd otwarcie dziennika.
- **Szersze niż ten jeden pin:** każda encja, której nazwa zawiera
  zarezerwowane słowo (`mapa`, `wiedza`, `cel`, `zadania`,
  `ekwipunek`, `postać`, `plotki`…) zostanie przejęta tak samo — i
  klikiem, i przez wpisanie z palca.

**Status (2026-05-31): KLIKI NAPRAWIONE.** Dodano parser-free
`Game.dispatch_entity_action(entity_id, action_type)` (buduje ActionIntent
wprost via `_forced_intent`, pomija `parse_with_optional_llm`). Piny i
panel akcji (oba commit-paths) routują przez nią po `target_id`+
`action_type`. Test: `test_direct_entity_dispatch.py`. ZOSTAJE: ścieżka
WPISANA z palca (np. wpisanie „sprawdź coś ważnego dla zadania") nadal
może być przejęta przez keyword — niższy priorytet, do rozważenia
precedencja w `parser_core`.

**Fix-szkic (zrobione / reszta):**
- [x] pin / panel → bezpośrednia inspekcja po entity_id, bez fuzzy
  keyword-matchingu.
- [ ] parser: przy jawnym verbie preferować encję w pokoju PRZED
  globalnymi quick-intentami (dla ścieżki wpisywanej).

**Pliki:** `ui/ui.py` (callback pina), `engine/game.py`
(`dispatch_entity_action`, `_forced_intent`), `engine/parser_core.py`
(precedencja — TODO).

---

### UX-8 · Cel piętra bez sensu — przepisać na „znajdź drogę w dół"
**Problem (user, ze screenshota demo F1):** `Cel piętra: Zrób coś, co
wygra przerywnik reklamowy` — kompletnie nie ma sensu jako główny cel.

**Fix-szkic:**
- Główny cel każdego piętra = dotrzeć do wyjścia przed deadline'em.
  Tekst typu: **„Znajdź drogę na następne piętro zanim upłynie czas."**
  (jeden, stały, niezależny od proc-genu).
- Obecny losowy „floor objective" (`content/data/floor_objective_
  templates.py`, wybierany w `floor_generator._pick_objective` /
  `procgen`) → zdegradować do **celów pobocznych**, nie głównego.
- Cele poboczne (z klasy, sponsorów, NPC, crawlerów, itd.) pokazywać
  pod głównym jako osobna sekcja **„Zadania dodatkowe"**. Pusta sekcja
  = nie pokazujemy nagłówka.
- Render: panel „Cel piętra" w lewej kolumnie (minimap/known-rooms
  blok, `ui/ui.py` / `ui/minimap.py`?) — najpierw główny cel, potem
  lista zadań dodatkowych.

**Pliki:** `engine/floor_generator.py` (`_pick_objective`),
`engine/floor.py` (objective_* pola), `content/data/floor_objective_
templates.py`, render celu w `ui/`.

---

### UX-7 · Piny obiektów: pozycja losowa zamiast logicznej / stałej siatki
**Problem (user):** piny zawsze w tej samej kolejności i miejscach;
rozmieścić bardziej losowo, a najlepiej logicznie (krata/wentylacja
u góry, złom na podłodze itd.).

**Diagnoza:** `ui/ui.py` ~888-943 rozkłada piny po stałej siatce
4-kolumnowej w kolejności `room.visible_entities()` (`col = idx % 4`).
Pozycja = funkcja kolejności na liście, nie natury obiektu.

**Fix-szkic:**
- Mapowanie tag/`entity_type` → strefa pionowa (sufit / ściana /
  środek / podłoga). Dane już są w `entity_templates`: `loose_grate`
  (sufit), `exposed_wiring`/`pipe_cluster`/`mirror` (ściana),
  `water_pool`/złom/`trash_bin` (podłoga), `furniture_*` (środek).
- Opcjonalny jawny hint `placement` w szablonach dla niejasnych.
- **Stabilność:** pozycję seedować z (`room_id` + key/id encji), bo
  draw() liczy ją co klatkę — gołe `random()` = skaczące piny.
- Anty-overlap: minimalny odstęp / jitter w obrębie strefy.

**Status (2026-05-31): TYPY PINÓW + PINY WYJŚĆ ZROBIONE** (commit 986b99f).
4 odrębne rodzaje: wróg (czerwone koło + halo), npc (zielone koło), obiekt
(szare koło), wyjście (bursztynowy „door" rounded-rect z → / 🔒 przy
krawędziach wg kierunku, klik = idź/wyłam). `ui._entity_pin_kind`,
`_PIN_COLORS`, `_draw_exit_pins`. Test: `test_exit_and_pin_kinds.py`.
ZOSTAJE: logiczne rozmieszczenie pinów ENCJI wg natury (sufit/ściana/
podłoga) + stabilny seed + anty-overlap.

**Pliki:** `ui/ui.py` (pętla pinów, `_draw_exit_pins`), ew. `content/data/
entity_templates.py` (hint `placement`).

---

### UX-6 · Piny zużytych obiektów nie znikają z ilustracji
**Problem (user):** obiekt zsalvage'owany / przeszukany / podniesiony
(np. „złom maszynowy — zdemontowany") dalej ma pin, mimo że nie ma już
z nim sensownej interakcji.

**Diagnoza:** piny biorą się z `room.visible_entities()`
(`room.py:81` → `e.visible and e.discovered`). Zużycie nie czyści tych
flag, więc encja zostaje na liście. Brak JEDNEJ flagi „zużyte" — różne
ścieżki ustawiają różne klucze w `entity.state`: `stripped`/`depleted`
(salvage, `game.py:3970` itd.), `destroyed`, `no_salvage`, `hacked`
(terminale, `visibility.py:303`), przeszukane kontenery.

**Fix-szkic:**
- Jeden predykat „czy pin jeszcze wart pokazania?" (np. ukryj gdy
  `state` ma którąś z {stripped, depleted, destroyed, hacked,
  no_salvage} **i** jedyny afordans to bierny `inspect`). Wspólny
  helper (`engine/affordances.py`/`visibility.py`), żeby pin-filtr,
  panel `[Środowisko]` i opis pokoju się zgadzały.
- **Decyzja do podjęcia:** zużyte obiekty znikają też z prozy opisu +
  panelu `[Środowisko]`, czy tracą tylko pin (zostają jako tło)?
  (Powiązane z UX-2.)

**Pliki:** `ui/ui.py` (filtr pinów), `engine/visibility.py` /
`engine/affordances.py` (predykat), ew. panel akcji w `engine/game.py`.

---

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
