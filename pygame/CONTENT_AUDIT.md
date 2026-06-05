# Audyt zawartości tekstowej (P29.40)

Cel: ustalić ile tekstu produkuje aktualnie każdy system gry, porównać
to z gęstością DCC (Dinniman), zaproponować budżet narratywny per
system i sekwencję rewritów.

Zgłoszenie: *„to gra tekstowa, dość ubogo jest jeśli chodzi o ilość
tekstu, nie ma czego czytać. Jest bardzo krótko."*

---

## 1. Stan aktualny (pomiary)

Średnia liczba słów na pojedynczy element widziany przez gracza:

| System | N pozycji | śr. słów | zakres |
|---|---:|---:|---|
| Pokój: pierwsze wejście (`first_enter_pool`) | 111 | **8.1** | 2–13 |
| Pokój: `rozejrzyj się` (`look_pool`) | 62 | **7.1** | 1–15 |
| Pokój: `przeszukaj` (`search_pool`) | 37 | 8.0 | 2–15 |
| Pokój: plotka publiczna (`public_hint_pool`) | 41 | 5.8 | 2–12 |
| Entity: `sprawdź` (`fallback_desc`) | 102 | **8.4** | 5–16 |
| Entity: nazwa (`fallback_name`) | 102 | 2.0 | 1–4 |
| Locale: narrator (`narrator_*`) | 99 | 10.1 | 4–19 |
| Locale: feedback (`feedback_*`) | 109 | 5.4 | 1–12 |
| Locale: sponsor (`sponsor_*`) | 30 | 7.3 | 2–14 |
| Locale: companion (`companion_*`) | 13 | 8.8 | 2–16 |
| Locale: encounter (`encounter_*`) | 21 | 5.7 | 2–11 |

**Najgorzej:**
- `feedback_*` ma najwięcej elementów (109) i jest najuboższe (5.4 słowa)
  — to znaczy KAŻDA akcja gracza dostaje pojedyncze suche zdanie.
- `look_pool` / `first_enter_pool` ~7-8 słów — pokój ma "kubek na stole"
  jako *cały* opis.
- `entity desc` ~8 słów — `sprawdź skrzynia` = jedno zdanie typu
  *„Pełna albo pusta. Z zewnątrz wygląda tak samo."*

**Najlepiej:**
- `narrator_*` ~10 słów — i tak za krótkie, ale to jedyna kategoria gdzie
  pojawiają się dłuższe linijki (1 linia ma 19 słów).

## 2. Punkt odniesienia: Dinniman

Polskie tłumaczenie **DCC** (Dungeon Crawler Carl) ma:

- Pojedynczy akapit narracyjny: **30–50 słów** (krótkie zdania, dużo
  ich, ale każdy „opis sceny" to akapit, nie linijka).
- Scena pomieszczenia: **3–5 akapitów = 150–300 słów łącznie**.
- Konferansjer / system text: jedna ogłoszeniowa wstawka **20–60 słów**
  z energią gospodarza teleturnieju.
- Narrator (Carl) komentuje sytuację **co kilka linijek mechaniki** —
  nigdy nie zostawia gracza z samym wynikiem rzutu.

**Stosunek prosty:** Dinniman daje ~4-6× więcej tekstu per scenę niż
nasza obecna gra.

## 3. Co gracz widzi w jednym pokoju (przykład realny)

Screenshot kafejki, gracz spamuje `rozejrzyj się`:

> `Lampy nad stolikami świecą za jasno. Na środkowym stoliku ktoś
> zostawił kubek z resztką zimnej kawy. Ktoś siedzi przy oknie i nie
> pije. Ekspres do kawy syczy jak mały smok z umową franczyzową.`

To są **dwa zdania** (29 słów). Klimat jest, ale to wszystko. Gracz
po `sprawdź ekran sponsorski` dostaje:

> `Przyglądasz się. Obiekt — „ekran sponsorski". (następna sprawdź
> ujawni szczegóły)`

Druga `sprawdź` — pełny card — i tam pewnie znowu 1-2 zdania flavora.

**DCC odpowiednik tej samej kafejki** to byłyby 3 akapity:
1. *Pierwsze wejście — narrator Carl* (ok. 50 słów): co czuję, czym
   tu pachnie, co mnie uderza w oczy, jakie ironiczne porównanie sam
   sobie wymyślam.
2. *Konferansjer w głośniku* (ok. 30 słów): „A oto, drodzy widzowie,
   strefa franczyzowa kafejki ‚Posłuszny Klient'! Sponsor: niegdyś
   znana sieć…"
3. *Co konkretnego widzę* (ok. 60 słów): trzy detale po jednym zdaniu
   każdy — kubek, gość przy oknie, ekspres. Każdy detal nawiązuje do
   czegoś (sponsor, plotka, ekonomia lochu).

---

## 4. Budżet narratywny per system

Cele liczbowe na rewrity. Liczby to **min — cel — max** słów na
element:

| System | Aktualnie | Cel | Mnożnik | Uwagi |
|---|---:|---:|---:|---|
| Pokój: pierwsze wejście | 8.1 | **40–60** | 5–7× | Narrator (2-3 zdania) + krótka wstawka Konferansjera / sponsora gdy uzasadnione |
| Pokój: `rozejrzyj się` | 7.1 | **30–50** | 4–7× | 3 zmysły × 1 zdanie = 3 zdania |
| Pokój: `przeszukaj` | 8.0 | **25–40** | 3–5× | Konkret co znalazłem + jeden ironiczny komentarz |
| Entity: `sprawdź` desc | 8.4 | **30–50** | 4–6× | Kształt + jeden szczegół + sugestia akcji |
| `feedback_*` (akcje) | 5.4 | **15–30** | 3–5× | Wynik + jedno zdanie konsekwencji / flavor |
| `narrator_*` (eventy) | 10.1 | **30–60** | 3–6× | Te są blisko celu, tylko podrasować |
| `sponsor_*` (uwaga) | 7.3 | **25–50** | 3–6× | Wstawki w głosie konkretnego sponsora |
| Konferansjer (system) | brak | **20–60** per cinematic moment | nowy | Na descent, floor unlock, boss death, audience milestone |
| NPC dialog (per linia) | brak | **20–80** | nowy | Drzewka — patrz UX-4 |

**Wstępna estymacja całkowitej objętości po rewrite:**

- 14 pokoi Floor 1 × ~150 słów łącznie (first_enter + look + search) = **~2 100 słów**
- 102 entity × ~40 słów desc = **~4 080 słów**
- 109 feedback strings × ~20 słów = **~2 180 słów** (ale tylko te
  często widziane warto pisać dłużej — patrz priorytety)
- Konferansjer cinematic vault (50 wstawek × 40 słów) = **~2 000 słów**
- NPC drzewka (10 NPC × ~300 słów na drzewko) = **~3 000 słów**

**Razem: ~13 000 słów nowej prozy** dla pełnego Floor 1 + reszta gry
ogólnie. To 4-5 dni pisania (mojego, z draftami do akceptu) + redakcja.

## 5. Sekwencja rewritów (priorytety)

Nie wszystko trzeba przepisać. Lecimy po hot-path — to co gracz widzi
najczęściej, w pierwszej kolejności.

### Faza 1 — Floor 1 hot-path (P29.42)

Co gracz widzi w pierwszej godzinie gry. **~2 500 słów nowej prozy.**

1. **Intro cinematic + pierwsze pokoje** (~400 słów)
   - Otwarcie gry (kto jest, co się stało, gdzie jest)
   - Pierwszy pokój — pełna scena Dinniman-style
2. **14 pokoi Floor 1** — `first_enter` + `look` + `search` (~1 500 słów)
3. **20 podstawowych entity** w pokojach Floor 1 — desc (~500 słów)
4. **6-8 najczęstszych `feedback_*`** (rozejrzyj_ok, search_empty,
   inspect_unknown, force_ok, force_fail, …) (~150 słów)

**Output:** Floor 1 czyta się jak rozdział DCC.

### Faza 2 — Konferansjer wstawki (P29.44)

Cinematic moments. **~2 000 słów.**

- Descent (między piętrami): 5 wariantów × 50 słów
- Floor unlock: 18 wariantów × 30 słów (per piętro)
- Boss start / kill: 2 × 18 × 30 słów
- Audience milestone (25, 50, 75, 100): 4 × 40 słów
- Sponsor drop-pod (per sponsor): 11 × 40 słów
- Player death (różne przyczyny): 10 wariantów × 40 słów

### Faza 3 — Entity rewrite (P29.45)

Pozostałe entity nie zrobione w Fazie 1. **~3 500 słów.**

- 82 entity (poza Floor 1 podstawowymi) × ~40 słów

### Faza 4 — Pozostałe piętra (P29.46+)

Floor 2-18 hot-path. **~5 000 słów.**

- Per floor: ~14 pokoi × 100 słów uśredniony rewrite = 1 400 słów
- Floor 2: pełny rewrite (drugi co gracz widzi)
- Floor 3-18: lekki rewrite, hot pokoje tylko

### Faza 5 — Feedback przedrostek `_long` (P29.47)

Krytyczne, często-widziane `feedback_*` dostają warianty
`feedback_X_long` (2-3 zdania) i `feedback_X_short` (1 zdanie). Engine
wybiera wariant zależnie od kontekstu (combat = short, exploration =
long). **~1 500 słów.**

### Faza 6 — NPC drzewka (P29.43, równolegle)

Faza 6 to UX-4 (dialog tree engine + content). Niezależna od reszty.

---

## 6. Strategia draftowania

Reguła z `project_dungeon_kraulem.md`: **nie commituję nowej prozy
bez akceptu**. Implementacja:

1. **Per fazę: drafty w batchach po 10-20 elementów.** Pokazuję
   listę: stary tekst → propozycja. Akceptujesz / odrzucasz / korygujesz.
2. **Style guide w pamięci** — Dinniman, dwa głosy (narrator vs.
   Konferansjer), krótkie zdania, brak kalk angielskich. Już zapisane.
3. **Akcept jednego batcha = commit jednego batcha.** Nie czekamy
   z 5 fazami w pull-requeście.
4. **Per pokój / entity: trzy zdania jako minimum, maksimum 5.**
   Nie próbujemy pisać akapitów filmowych — gra musi się płynnie
   czytać, nie blokować akcji.

---

## 7. Co NIE zmieniamy

- Mechaniczne wyniki rzutów (`[atak] d20(13) + STR(+2) = 15 vs TT 12
  → sukces`) — to jest na osobnej linii, krótkie, ok.
- Nazwy własne entity / pokoi — już dobre.
- UI labels / panel headers — z definicji krótkie.
- Achievement names — krótkie chwytliwe formy.
- System messages techniczne (zapis, ustawienia) — to nie narracja.

---

## 8. Co po B (P29.40)

→ **C (P29.41):** silnik dialog tree + UI overlay. Techniczne, bez
prozy. Można shippować przed wszelką prozą.

→ **D (P29.42):** Faza 1 — Floor 1 hot-path rewrite. Wymaga akceptów.

Plan domknięty. Zaczynam C, gdy potwierdzisz.
