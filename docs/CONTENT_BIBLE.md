# CRAWL PROTOCOL — Content Bible

## Cel
Gra ma być immersyjnym survival RPG o przeżyciu na piętrze megalochu przez wiele dni, a nie roguelite'em z wyborem jednej ścieżki. Gracz ma improwizować, zbierać informacje, wracać do znanych miejsc, używać otoczenia, rozmawiać, zdradzać, odpoczywać, handlować i planować.

## Ton
Domyślny język: polski.

Ton gry:
- brutalny, ale nie edgelordowy,
- absurdalny, ale spójny,
- korporacyjnie okrutny,
- bardzo zmysłowy w opisach,
- ciemna komedia + survival horror + reality show,
- gracz jest obserwowany, oceniany i monetyzowany.

Narrator:
- krótki,
- sarkastyczny,
- systemowo-korporacyjny,
- komentuje wzorce zachowań gracza,
- nie tłumaczy mechaniki zbyt jawnie,
- nie zagaduje każdej akcji.

Dobry narrator:
> Protokół odnotował próbę rozwiązania problemu przez wandalizm infrastruktury. Infrastruktura wnosi sprzeciw.

Zły narrator:
> Użyłeś obiektu środowiskowego i dostałeś +2 audience.

## Zasada opisów
Opisy powinny dawać informację bez zdradzania całej mechaniki.

Zły opis:
> To jest pokój walki. Jest tu goblin, kwas i kamera.

Dobry opis:
> Powietrze za progiem jest gorące i kwaśne. Zielonkawa ciecz bulgocze między pękniętymi kafelkami, zjadając fugę z cichym sykiem. Kamera sponsora obraca się w twoją stronę z mechaniczną ciekawością. Za przewróconym stołem coś małego ostrzy nóż o własne zęby.

## Warstwy informacji
Każdy pokój powinien mieć warstwy:
1. `public_hint` — co widać/słychać przed wejściem.
2. `first_enter` — pierwszy opis po wejściu.
3. `look` — darmowe lub prawie darmowe rozejrzenie się.
4. `inspect` — celowe obejrzenie obiektu.
5. `search` — dłuższe przeszukanie, koszt czasu, ryzyko i nagroda.
6. `rumor` — niepełna informacja zdobyta z NPC, terminala lub plotki.

## Zasada pokoju
Pokój nie jest jedną akcją. Pokój to miejsce ze stanem:
- widoczne obiekty,
- ukryte obiekty,
- wyjścia,
- NPC/crawlerzy,
- hałas,
- bezpieczeństwo,
- czas ostatniej wizyty,
- czy został przeszukany,
- co zostało zużyte,
- co się zmieniło.

Gracz może wrócić. Pokoje pamiętają konsekwencje.

## Nie każdy problem to walka
Każdy większy obstacle/encounter powinien mieć przynajmniej 3 rodziny rozwiązań:
- walka,
- ucieczka/ominięcie,
- rozmowa/oszustwo/intimidacja,
- użycie otoczenia,
- użycie itemu,
- czas/czekanie,
- pomoc crawlera/NPC,
- informacja/hasło/sekret.

Nie każda opcja jest zawsze dostępna.

## Crawlerzy
Crawlerzy to inni uczestnicy. Nie są tylko sklepikarzami.
Każdy crawler powinien mieć:
- bieżący cel,
- strach,
- sekret,
- styl przetrwania,
- granicę moralną,
- możliwy powód do pomocy,
- możliwy powód do zdrady.

Crawler może:
- prosić o pomoc,
- kłamać,
- handlować,
- zaatakować,
- dołączyć na krótko,
- zdradzić,
- umrzeć poza ekranem,
- wrócić później zmieniony.

## Safehouse
Safehouse to nie miasto. To dziwne pomieszczenie bezpieczeństwa w środku maszynki do zabijania:
- kawiarnia,
- łazienka,
- prysznic,
- klinika,
- czarny rynek,
- lounge,
- kiosk sponsora,
- tablica zleceń,
- neutralny bar.

Safehouse powinien być kotwicą pętli:
wyjdź → ryzykuj → wróć ranny → umyj się → sprzedaj śmieci → kup plotkę → odpocznij → planuj.

## Czas
Czas jest zasobem.
Rozejrzenie się prawie nic nie kosztuje. Przeszukanie, crafting, leczenie, handel, odpoczynek i powrót kosztują minuty/godziny.

## Fail forward
Porażka nie powinna być wyłącznie “nic się nie stało”.
Rodziny porażek:
- sukces z kosztem,
- częściowy sukces,
- hałas,
- strata czasu,
- zużycie przedmiotu,
- pogorszenie relacji,
- komplikacja,
- ujawnienie informacji kosztem bezpieczeństwa.

## Loot
Loot jest narzędziem do rozwiązywania problemów, nie tylko statystyką.
Przykłady dobrego lootu:
- identyfikator,
- kubek,
- taśma,
- filtr,
- bateria,
- zapalniczka,
- kawa,
- mięso jako przynęta,
- fałszywy formularz,
- karta dostępu,
- śrubokręt,
- sprężyna,
- brudny mundur.

## Zakazane wzorce
Unikać:
- ujawniania typu pokoju z góry,
- każdej walki jako obowiązkowej,
- “wybierz node i idź dalej” jako głównej pętli,
- statycznych NPC bez celu,
- lootów typu tylko +1 damage,
- placeholderów po angielsku w polskim UI,
- opisu mechanicznego zamiast sensorycznego.

## Nazewnictwo
Klucze logiczne po angielsku:
- `acid_pool`,
- `safehouse_cafe`,
- `crawler_wounded`,
- `objective_find_keycard`.

Teksty widoczne po polsku przez `t(key, fallback=...)`.

---

## Procedural Floor Design

Piętra **nie są ręcznie układaną mapą**. Piętra są **generowane** z kontrolowanych
puli szablonów. Ręcznie wykonane Piętro 1 (15 pokoi w `revamp/data/room_templates.py`)
istnieje wyłącznie jako **slice pionowy / harness testowy** — nowa zawartość
nie powinna być do niego doklejana, tylko trafiać do puli, z których generator
piętra może wybierać.

### Reguły procedurality

- **Piętra są generowane z kontrolowanych szablonów.**
  Generator dobiera pokoje z `room_pool`, NPC z `npc_templates`, encountery
  z `encounter_templates`, plotki z `rumor_templates`, klucze fabularne
  z `clue_templates`, safehouse'y z `safehouse_templates`, cele z
  `floor_objective_templates`, obiekty środowiskowe z `entity_templates`.

- **Typ pokoju nie powinien być ujawniony przed odkryciem.**
  UI mapy nie pokazuje "Combat Room" ani "Boss". Pokazuje stan
  (`unknown` / `hinted` / `scouted` / `visited` / `searched` / `cleared`)
  i ewentualną podpowiedź zmysłową (`public_hint`).

- **Każde piętro musi pozwalać na backtrack.**
  Krawędzie grafu są dwukierunkowe domyślnie. Po odwiedzeniu pokój zostaje
  ze swoim stanem (loot zużyty, NPC zapamiętany, pułapka rozbrojona albo nie).

- **Każde piętro musi mieć:**
  - strefy bezpieczne (przynajmniej jeden safehouse, zwykle 2-3),
  - strefy niebezpieczne (combat / hazard / locked),
  - tropy (rumor + clue) prowadzące do celu piętra,
  - sekrety (przejścia ukryte za `Look`/`Search`),
  - wiele dróg postępu (graf nie jest liniowy; cel piętra ma >=2 ścieżki rozwiązania).

- **Piętro 1 ma gwarancje projektowe, nie ustalony układ.**
  Po wygenerowaniu Piętra 1 generator gwarantuje:
  - >= 12 pokoi,
  - >= 1 cafe lub bathroom safehouse,
  - >= 1 black-market lub kiosk-like safe room,
  - >= 2 spotkania z crawlerami,
  - >= 2 spotkania z potworami z wariantami non-combat,
  - >= 1 zamknięta lub zablokowana trasa,
  - >= 1 sekretna trasa,
  - >= 1 cel piętra z >=2 ścieżkami rozwiązania.

- **Treść ma być wielokrotnego użytku.**
  Pokoje, NPC, plotki, obiekty, encountery, safehouse'y i cele są
  **szablonami** (dataclasses lub dictsy ze stabilnymi kluczami ASCII).
  Generator instancjonuje je z losowymi nazwami z poola, losowymi
  rozstawkami i losową treścią — ale nigdy nie zmienia ich klucza.

### Anty-wzorce

- Hardcodowanie konkretnego pokoju w konkretnym miejscu mapy.
- Cel piętra z **jednym** rozwiązaniem.
- Statyczny boss bez non-combat opcji.
- Pokój, którego typ widać przed wejściem.
- Loot, którego nie da się użyć do problemu inaczej niż "+1 damage".
- Encounter, który ma tylko "fight" w `possible_resolutions`.

### Tagi pool-template'ów

Każdy template w puli (pokój, encounter, NPC) ma `tags: list[str]`.
Generator filtruje pule po tagach przy budowie piętra:
- `safe`, `dangerous`, `loot`, `social`, `secret`, `boss`, `objective`,
  `non_combat`, `stealth`, `environment`, `lore`, `trap`.

Tagi są dokumentacją kontraktu, nie magią — generator po prostu pyta
puli "daj mi pokój z tagiem X" i dobiera ważoną losowość.

### Klucze i fallbacky

Wszystkie szablony używają stabilnych angielskich kluczy oraz polskich
`fallback_*` tekstów. UI woła `t(key, fallback=fallback_*)`. Pula nie
zawiera lokalizowanych nazw — lokalizacja jest robiona przez `lang.tr()`.

## Crafting and salvage

Szczegóły w `docs/CRAFTING_BIBLE.md`. Najważniejsze założenia:

- Crafting jest filarem przetrwania i lore, nie osobnym menu ekonomicznym.
- Gracz może lootować, rozbierać, odzyskiwać, pozyskiwać, demontować, wytwarzać,
  improwizować, naprawiać, wzmacniać i rozstawiać. Każde z tych słów ma własny
  parser-friendly czasownik PL i EN.
- Materiały noszą tagi (`sharp`, `wire`, `binding`, `electrical`, `organic`,
  `chemical`, `metal`, `cloth`, `glass`, `wood`, ...). Receptury i improwizacja
  patrzą na tagi, nie tylko na klucz materiału.
- Improwizowany crafting musi się walidować przeciw aktualnym materiałom gracza,
  kontekstowi pokoju (safehouse, walka, niebezpieczeństwo) i ryzyku.
- Encje rozbierane zostawiają stan (`stripped`, `depleted`, `damaged`,
  `destroyed`, `harvested`) — nie ma niekończącego się farmienia.
- Kradzież w safehouse, pozyskiwanie organów z ciał, niszczenie własności
  sponsora, wandalizm armatury — każde uruchamia społeczną reakcję
  (`safehouse_consequence`, `social_suspicion`, `sponsor_attention`).
- Narrator i osiągnięcia są obowiązkową informacją zwrotną dla istotnych
  akcji salvage/craft. Nie ma być przy każdym podniesieniu jednej śrubki.

## Memetic actions

Szczegóły w `docs/MEMETICS_BIBLE.md`. Tu wystarczy zaznaczyć kontrakt:

- Memetyka to ziarna przekonań, plotki, fałszywe rozkazy, manipulacja społeczna,
  exploity logiczne i symboliczne ataki na NPC i frakcje. To nie to samo co
  tworzenie frakcji od zera.
- Parser (deterministyczny + opcjonalnie Ollama) interpretuje intencję; model
  świata waliduje kontekst — czy NPC w ogóle reaguje na takie zdanie, czy
  ma odpowiednie afordancje i podatność.
- Udane memetyczne akcje zostają zapisane w `world.flags` / `floor.active_events`
  i mogą wracać przez plotki, encountery, linijki narratora, clue chains i
  reroll rozwiązań celu piętra.
- Memetyka jest implementowana po tym, jak crafting jest stabilny. Wcześniejsze
  wzmianki w kodzie zostają jako TODO, nie jako działający system.
