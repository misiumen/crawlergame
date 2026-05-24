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
