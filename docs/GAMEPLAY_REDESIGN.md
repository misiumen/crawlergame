# Dungeon Kraulem — Redesign (working doc)

> Status: KIERUNEK USTALONY z userem. Zero kodu dopóki Faza 1 nie
> zaakceptowana. Język: rationale po ang. (doc wewnętrzny); WSZYSTKO
> player-facing po polsku.

DWA OSOBNE TORY (user był wyraźny — nie mieszać, nie „jeden fix na oba"):
- **TOR GAMEPLAY** — gra jest nudna w graniu, niezależnie od narracji.
- **TOR NARRATIVE** — brak duszy DCC; gracz to niemy przechodzień w cichym
  świecie. (Osobny doc/etap, NIE teraz.)

Ten doc = TOR GAMEPLAY.

---

## 1. Docelowy fantasy (słowami usera + referencje)

„Trochę A (absurdalna potęga) i trochę C (przechytrzanie gry)."
Referencje: **FTL** (każdy wybór = hazard zasobami pod presją),
**Dysmantle** (świat = surowiec, wszystko rozbieralne w moc),
**Dead Island** (craft konkretnych, brutalnych narzędzi: maczeta na prąd,
kij w kwasie), **Dishonored** (poziom = pudełko systemów do exploitowania;
wiele dróg, radość z tej sprytnej).

Synteza: **immersive-sim survival-crafter — obracasz materiały i systemy
wrogiego lochu przeciwko niemu. Możesz stać się absurdalnie SILNY albo
absurdalnie SPRYTNY. Twój wybór.** (A+C zlane. Bardzo DCC: Carl wygrywa
improwizacją ze śmieci i łamaniem reguł lochu.)

## 2. Bite-level (USTALONE): „in between"
- NIE soft (brute-force równie dobry → systemy bezużyteczne).
- NIE hard-gate (jedna słuszna metoda → wymuszony styl).
- **TAK: challenge, który NAGRADZA użycie systemów, ale nie KARZE za
  niekorzystanie z konkretnego.** Każdy encounter ma KILKA realnych
  odpowiedzi; crafting/otoczenie/spryt czynią cię efektywniejszym/
  bezpieczniejszym/efektowniejszym; brute force zostaje MOŻLIWY, tylko
  rzadko OPTYMALNY. Zero wymuszonego stylu. (Model: Dishonored — ghost
  albo rzeź, oba działają, oba satysfakcjonują.)

## 3. Sedno diagnozy (dlaczego nudne — bez narracji)
Gra = seria ciekawych decyzji. Teraz decyzji prawie nie ma:
- Klik pina nic nie kosztuje i niczym nie ryzykuje → to nie wybór, to
  obowiązek (feeling „Excel").
- Brak budowania mocy, którą CZUJESZ w trakcie runu — run jest płaski.
- Brak gradientu ryzyko/nagroda — wszystko równie bezpieczne.
- **Głębokie systemy JUŻ ISTNIEJĄ, ale są opcjonalnymi zabawkami, nie
  kręgosłupem.** Można wygrać klikając „atak", więc nikt nie robi maczety
  na prąd ani nie wpycha wroga w iskrzącą kałużę.

KLUCZOWY WNIOSEK: to NIE jest „dodaj funkcje". To **„zrób z istniejących
głębokich systemów nagradzaną domyślną ścieżkę, a nudną ścieżkę przestań
nagradzać"** — przy bite-level „in between" (brute nadal możliwy).

## 4. Co JUŻ jest (kręgosłup istnieje, jest side-toyem)
- **Crafting:** 40 receptur (`recipe_templates`), **coatingi broni**
  (kwas/ogień/prąd, `_attempt_coat_weapon`), salvage→materiały. Pętla
  Dysmantle/Dead Island ISTNIEJE.
- **Systemowe interakcje:** prawdziwy silnik (`engine/systemic.py`) —
  żywioły, ogień się ROZPRZESTRZENIA, push-into-hazard, prąd przez wodę,
  propagacja statusów. Warstwa Dishonored „exploituj systemy" ISTNIEJE.
- **Meta-unlocki:** 48 w `meta_progression` + 48 osiągnięć (osobny tor
  replay; póki co parkujemy).

## 5. Jak zrobić z nich kręgosłup (bite „in between")
1. **Wrogowie/przeszkody premiują myślenie, nie blokują.** Część wrogów
   ma odporności/pancerz, przez które brute-click jest WOLNY i kosztowny
   (HP, czas) — ale coated weapon / kill środowiskowy / called-shot robią
   to szybko i czysto. Brute działa, tylko boli. (NIE hard-gate.)
2. **Loot = wejścia do mocy (Dysmantle).** Mniej „+1 dmg", więcej
   materiałów i komponentów, które craft zamienia w konkretne narzędzia.
3. **Power compound w trakcie runu.** Run buduje COMBO, które sam
   złożyłeś (maczeta krwawiąca + wabik grupujący + pułapka). Czujesz, że
   rośniesz — w mocy ALBO w sprycie.
4. **Otoczenie to broń (Dishonored/DCC).** Każdy combat-room ma 1-2
   systemowe haczyki (kałuża+prąd, gaz+ogień, ciężki obiekt do zrzucenia),
   czytelnie telegrafowane, jako realna alternatywa dla „atak".
5. **Scarcity z zębami (FTL).** Materiały/czas/HP napięte na tyle, że
   „skuć kwas teraz czy zachować mat na pułapkę?" to prawdziwy hazard.

## 6. Faza 1 — najmniejszy testowalny dowód pętli (PROPOZYCJA)
Cel: w trybie **Demo (Intake)** poczuć, że spryt/craft >>> brute, bez
wymuszania jednej metody. Najmniejszy pionowy plasterek:

- **Jeden „myślący" encounter w intake**: wróg z wyraźną odpornością na
  fizyczne (telegrafowane przy sprawdź/assess: „gruba skóra — zwykłe
  ciosy się ślizgają") i wyraźną słabością systemową (np. ogień/kwas).
- **Pokój daje 2+ systemowe odpowiedzi**, czytelnie telegrafowane:
  np. kałuża + obnażone przewody (wepchnij → prąd), albo butla gazowa
  (rozbij przy ogniu). Plus dostępny materiał na coating.
- **Bilans bite „in between":** brute-click ZABIJA, ale wolno i z dużym
  HP-kosztem; coating/środowisko = szybko i tanio. Gracz SAM wybiera.
- **Czytelność:** assess/inspect mówi co zadziała (nie spoileruje
  wszystkiego z góry — patrz CMB-9), log nagradza sprytny kill (audience
  +, „efektowne" — łączy z już zrobionym Slice D).

To dowodzi pętli na JEDNYM starciu, zanim rozlejemy na całą grę. Tuning
liczb (jak wolny brute, jak tani spryt) na żywo w Demo.

## 7. Po Fazie 1 (kolejność do potwierdzenia)
- F2: rozlać „myślące" encountery + systemowe haczyki na pulę combat-roomów.
- F3: loot→komponenty (Dysmantle), craftowalne combo, power-compound.
- F4: scarcity/balance (FTL) + meta-unlocki napędzające replay.
- F5: model obstacle-first / rodziny rozwiązań (ITEM-1) — pełny immersive-sim.
- (osobno) TOR NARRATIVE — dusza DCC.

## 8. Pytania do usera
- **O1.** Akceptujesz Fazę 1 (jeden „myślący" intake-encounter jako dowód
  pętli) jako pierwszy krok kodu?
- **O2.** „Mniej pinów / trywialne rzeczy jako proza tła" — wchodzi już w
  Fazie 1 czy osobno? (Bezpośredni lek na „Excel".)
- **O3.** Telegrafowanie słabości: od razu na `inspect`, czy nagroda za
  głębszy recon (CMB-9)? Wpływa na czytelność Fazy 1.
