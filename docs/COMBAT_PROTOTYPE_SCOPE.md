# Combat Prototype — pełny scope (working doc)

> Status: ZBUDOWANE (P1-P4 wszystkie wypchnięte, suite zielony na każdym
> kroku). Reticle pip (A+B) — 47e96cb. P1 surface+transition — ab00d5d.
> P2 juice (kick/shake/SFX) — db492dd. P3 thinking-loop — 2e8056c.
> P4 limb-loss (wound overlay + sever/break) — fa026fb.
> ZOSTAJE (świadomie odłożone): hit-stop + ekonomia 2 PA (CMB-6, wymaga
> przeróbki turn-flow — z userem), pełny cut-vs-break (CMB-8: amputation
> drops/bleed), art-warianty limbloss (zamiast proceduralnych nakładek),
> środowiskowe haczyki wymuszone w layoucie pokoju (P3 dowiedzione na
> istniejącej treści, nie na bespoke roomie).
>
> --- oryginalny scope poniżej ---
> Status (orig): SCOPING do akceptacji. Zero kodu dopóki nie zatwierdzone.
> Cel: ZBIEŻYĆ wszystkie nitki tej sesji w JEDNYM pionowym plasterku —
> animowany combat overlay z jednym „myślącym" starciem — w trybie
> Demo (Intake). Jeśli ten jeden fight czuje się dobrze, walidujemy
> kierunek całej gry. Jeśli nie — spaliliśmy jeden slice, nie grę.

---

## 0. Po co prototyp (a nie od razu „full overhaul")
„Full overhaul" bez granicy = miesiące i ryzyko zepsucia działającej gry.
Prototyp = najmniejszy slice, który dowodzi NARAZ trzech rzeczy, o które
prosiłeś:
1. **Pętla gameplay** (immersive-sim: nagradzaj spryt/systemy, brute
   możliwy ale nieoptymalny — bite „in between").
2. **UI „world-first"** zamiast paneli/zakładek (lek na „PowerPoint").
3. **Animacja/juice à la Darkest Dungeon** (lek na „klikanie hitboxa na
   png").
Jeden ekran, mały zasięg, wyrzucalny. Potem rozlewamy na grę.

---

## 1. Co budujemy (zawartość prototypu)

### 1.1 Combat overlay (UI world-first)
- Walka przejmuje CAŁY ekran (osobny stan, nie te same panele z wrogiem
  w środku). Wyraźny moment „WALKA SIĘ ZACZYNA" (transition), nie ciche
  wejście w turę.
- Na ekranie TYLKO: scena (tło pokoju + portrety), pasek akcji bojowych +
  środowiskowych, HUD HP/zamiar. Żadnych zakładek Ekwipunek/Mapa/Wiedza —
  te są SUMMONED overlayem (Esc/klawisz), nie stałym meblem.
- Akcje są czasownikami NA scenie / kontekstowym pasku, nie listą w tabie.
- Klawiatura + mysz parytet (twoja zasada: każda nowa funkcja działa myszą).

### 1.2 Juice — animacja (1.a + trochę 1.b)
Wszystko na ISTNIEJĄCEJ pętli `update(dt)` + `world.combat_fx` (shake/
flash/floaters JUŻ są, niedoużyte):
- **1.a (tanie, robimy w pełni):** atakujący portret **lunge** w stronę
  celu i powrót; cel **recoil**; **impact flash** + sprite uderzenia na
  trafionej strefie; **hit-stop** (krótka pauza na trafieniu); shake
  skalowany siłą ciosu; duże **floating numbers**; tint/desat portretu
  przy śmierci. Słownik Darkest Dungeon = statyczne portrety, które się
  rzucają/trzęsą/błyskają na rytm tury.
- **1.b (ograniczone, wymaga ARTU — patrz §3 ryzyka):** portret odbija
  STAN ciała. Realistyczny zakres na teraz: **overlay-owe warstwy**
  (krew/opalenie/odcięta kończyna jako nakładka na bazowy PNG), NIE
  pełna re-animacja. Przy złamaniu/odcięciu kończyny: nakładka „brakuje
  kończyny" + inny stagger pose jeśli dostarczysz wariant.

### 1.3 Turn flow ze stanem animacji
Dziś: akcja rozwiązuje się natychmiast, log się aktualizuje. Do animacji:
mała maszyna stanów walki — `player_input → animating(lock) → resolve →
enemy_animating → back`. Input zablokowany podczas animacji (~300-500ms),
potem efekt ląduje. Zawarte w ścieżce walki, nie rusza reszty gry.

### 1.4 Jeden „myślący" encounter (pętla gameplay)
- Wróg z czytelną **odpornością na fizyczne** (telegraf: „gruba skóra")
  i **słabością systemową** (ogień/kwas).
- Pokój daje **2+ telegrafowane odpowiedzi środowiskowe** (kałuża+przewody
  → prąd; butla gazowa → ogień) + materiał na coating broni.
- **Bilans „in between":** brute-click ZABIJA, ale wolno i drogo (HP/czas);
  coating/środowisko = szybko i tanio. Gracz wybiera. Zero wymuszenia.
- Sprytny/efektowny kill → audience+ i kinowy feedback (łączy z gotowym
  Slice D).

### 1.5 SFX (rozszerzenie — tanie)
SFX są **proceduralne** (`tools/synthesize_audio.py`, stdlib). Mamy 11.
Dorzucamy combat-juice keys (recipe + regen): lunge/whoosh, impact ciężki,
sever/wet-crunch (limb), zap (prąd), whoosh-ignite (ogień), stagger,
finisher. „Więcej SFX" = dopisać recepturę, nie szukać plików.

---

## 2. Czego prototyp DOWODZI (kryteria sukcesu)
- Walka CZUJE się jak gra, nie PowerPoint (ruch, rytm, impact).
- „Myślący" kill (środowisko/coating) jest WYRAŹNIE lepszy i fajniejszy
  niż brute — ale brute działa.
- Świadczy o nowym UI (akcja na scenie, brak meblowych zakładek).
- Limb-loss daje SATYSFAKCJĘ wizualną (choćby overlay), nie tylko label.

---

## 3. Ryzyka i UCZCIWE braki (gdzie czegoś brakuje)
- **ART to wąskie gardło 1.b.** Silnik narysuje lunge/shake/flash/overlay,
  ALE „sprite odbija odciętą kończynę" wymaga WARIANTÓW ARTU per stan
  (czysty / krew / brak ręki / brak nogi / martwy). Bez nich limb-loss =
  proceduralna nakładka (czerwony rozbłysk + „kikut" jako prymityw), nie
  prawdziwy nowy sprite. **Decyzja: czy dostarczysz warstwy/warianty, czy
  jedziemy na proceduralnych nakładkach na start?** (CMB-3/ART-1 powiązane.)
- **Hit-stop w turówce** zmienia turn flow — kontenerowane w walce, ale to
  realna zmiana, nie kosmetyka.
- **Tuning „in between"** (jak wolny brute, jak tani spryt) = iteracja na
  żywo w Demo, nie da się trafić od pierwszego strzału.
- **To NIE jest jeszcze**: pełny model obstacle-first/ITEM-1 (rodziny
  rozwiązań w całej grze), reshape UI eksploracji (poza walką), tor
  narracji DCC, meta-progresja. Prototyp dotyka tylko WALKI. Reszta to
  osobne tory PO walidacji.

---

## 4. Czego prawdopodobnie NIE pomyślałeś, a warto (moje propozycje)
- **Telegraf zamiaru wroga jako część animacji** — wróg „bierze zamach"
  (pose/glow) zanim uderzy, żebyś zdążył zareagować (unik/obrona). Łączy
  juice z czytelnością Slice B.
- **Czytelność co robi maim** — przy odcięciu kończyny log+ikona mówią
  efekt („nie podejdzie", „−atak"), nie tylko „złamana". (user wcześniej:
  „nie wiem co robi złamanie kończyny".)
- **Leżący/okaleczony wróg = łatwiejszy do trafienia** (user pomysł) —
  wpięte w animację (pose leżący) + bonus to-hit.
- **Dostęp do Unik/Obrona** musi być oczywisty na pasku (user: „nie wiem
  jak robić unik"). Prototyp to naprawia z definicji (world-first bar).
- **Wyjście z walki / środowiskowe akcje** na tym samym pasku (wepchnij,
  podpal, zwab) — Dishonored-owy „rozwiąż inaczej".

---

## 5. Faza po fazie (prototyp też budujemy plasterkami, każdy zielony+push)
- **P1.** Combat jako osobny stan + transition + world-first pasek akcji
  (bez animacji jeszcze). Dowodzi UI.
- **P2.** Juice 1.a (lunge/recoil/shake/flash/hit-stop/floaters) + nowe SFX.
- **P3.** „Myślący" encounter + środowiskowe odpowiedzi + bilans in-between.
- **P4.** Limb-loss wizualny (overlay proceduralny LUB art-warianty wg §3).
Każdy plasterek testowalny w Demo Intake.

---

## 6. Pytania do usera
- **O1.** Akceptujesz prototyp = animowany combat overlay + 1 myślący
  encounter w Demo Intake, budowany plasterkami P1→P4?
- **O2.** Limb-loss start: proceduralne nakładki (działa od razu) czy
  czekamy aż dostarczysz warianty/warstwy artu? (Mogę zacząć na
  proceduralnych i podmienić na art później.)
- **O3.** Czy zaczynamy od P1 (UI/stan walki) — czy wolisz najpierw P2
  (juice) na obecnym layoucie, żeby SZYBCIEJ poczuć ruch, a UI-reshape
  potem? (Trade-off: P1-first = czysto, P2-first = szybszy dopamine.)
