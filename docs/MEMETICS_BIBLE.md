# MEMETICS_BIBLE.md

## Cel dokumentu

Ten dokument definiuje system memetyki: plotek, sugestii, fałszywych przekonań, logicznych infekcji, haseł, propagandy i idei, które gracz może zasiewać w świecie. System nie służy wyłącznie tworzeniu frakcji. Jego celem jest umożliwienie zagrywek typu: gracz przekonuje grupę wrogów do fałszywej interpretacji rzeczywistości, a konsekwencje wracają później w encounterach, rumorach, zachowaniu NPC i komentarzach narratora.

## Filozofia

Memetyka jest społecznym i poznawczym odpowiednikiem craftingu. Gracz nie przerabia stołu na pułapkę, tylko przerabia lęk, pychę, przesąd, błąd logiczny albo pragnienie na narzędzie.

System powinien obsługiwać:
- ziarna przekonań,
- fałszywe rozkazy,
- plotki,
- panikę,
- skłócanie wrogów,
- sponsorowane kłamstwa,
- logiczne exploity maszyn,
- tabu,
- hasła,
- symbole,
- błędne interpretacje zdarzeń.

Ollama lub inny parser może pomóc rozpoznać intencję gracza, lecz nie może samodzielnie zmieniać świata. Silnik gry waliduje kontekst, wykonuje test, zapisuje efekt i kontroluje eskalację.

## Podstawowe pojęcia

### BeliefSeed

Trwały zapis idei zasianej przez gracza.

Pola:
- `belief_id`
- `origin_text`
- `created_floor`
- `created_time`
- `source_actor`
- `target_tags`
- `target_factions`
- `core_claim`
- `emotional_hook`
- `logic_hook`
- `spread_channels`
- `strength`
- `stability`
- `distortion`
- `stage`
- `effects`
- `known_by`
- `suppressed_by`
- `last_triggered_time`

### Rumor

Konkretny tekst lub informacja rozchodząca się przez NPC, terminale, crawlerów, safehouse albo sponsorów. Rumor może być prawdziwy, fałszywy, częściowy lub zniekształcony.

### Logic exploit

Memetyka wymierzona w maszyny, AI, drony, proceduralne systemy, protokoły, kontrakty lub automaty. Nie działa jak magia. Działa przez sprzeczność, priorytet, wadliwy rozkaz, błędną klasyfikację albo pętlę decyzyjną.

### Social contagion

Rozprzestrzenianie się hasła, plotki, memu lub interpretacji przez rozmowy, transmisje, powtórki, graffiti, komentarze publiczności i zachowanie NPC.

## Intent types

Parser powinien obsługiwać:
- `seed_belief`
- `spread_rumor`
- `sow_distrust`
- `false_order`
- `incite_panic`
- `create_taboo`
- `identity_attack`
- `logic_exploit`
- `sponsor_disinformation`
- `mythic_framing`
- `blame_shift`
- `fabricate_authority`
- `propaganda`
- `rally`
- `demoralize`

## Walidacja kontekstu

Przed testem gra musi sprawdzić:
- czy adresaci są obecni albo istnieje kanał transmisji,
- czy adresaci rozumieją język, symbol, rozkaz albo bodziec,
- czy gracz ma wiarygodność, dowód, rekwizyt, terminal, kamerę lub publiczność,
- czy safehouse pozwala na agitację,
- czy wrogowie mają tag podatny na daną ideę,
- czy wcześniejsze wydarzenia wspierają kłamstwo,
- czy ryzyko obejmuje odwet, sponsorów, panikę lub zniekształcenie.

## Statystyki i testy

- CHA: perswazja, performans, manipulacja, publiczne kłamstwo
- INT: logiczny exploit, fałszywy protokół, techniczna dezinformacja
- WIS: trafienie w lęk, przesąd, słaby punkt psychologiczny
- DEX: podrzucenie dowodu, spreparowanie sceny
- STR/CON: rzadko, tylko przy memetyce opartej na demonstracji siły lub wytrzymałości

Wyniki:
- critical success: silny belief seed, natychmiastowy efekt i dobre kanały rozprzestrzeniania
- success: lokalny efekt i zapisany belief seed
- partial success: działa, ale zniekształca się albo tworzy koszt
- failure: cel odrzuca przekaz, czas mija, sytuacja się pogarsza
- critical failure: gracz zostaje oznaczony jako manipulator, kłamstwo uderza w niego albo sponsorzy przejmują narrację

## Etapy belief seed

- `seeded`: idea powstała lokalnie
- `noticed`: ktoś ją powtarza
- `spreading`: idea wpływa na encountery
- `distorted`: idea ewoluuje w niekontrolowany sposób
- `weaponized`: ktoś inny używa jej przeciwko graczowi albo wrogom
- `suppressed`: system/frakcja próbuje ją zdusić
- `myth`: idea stała się częścią lokalnego lore

## Efekty mechaniczne

Belief seed może dawać:
- szansę wahania u przeciwników,
- nowe opcje dialogowe,
- clue-gated resolution,
- zmianę priorytetów NPC,
- obniżenie morale,
- panikę,
- fałszywy alarm,
- konflikt między grupami,
- zmianę rumor pool,
- reakcję sponsora,
- achievement,
- audience swing,
- ostrzeżenie w safehouse,
- specjalny encounter później.

## Integracja z rumorami i clue paths

Memetyka powinna wpinać się w system informacji:
- udany belief seed może dodać rumor,
- rumor może odblokować resolution,
- distorted rumor może dodać komplikację,
- silny belief seed może odblokować specjalny exploit wobec tagów pasujących do celu.

Przykład:
- Gracz przekonuje drony, że ich „serca” są w skrzynkach sponsorów.
- System zapisuje belief seed z target tagami `machine`, `sponsor_tech`.
- Później w safehouse pojawia się rumor o dronach rozbierających lootboxy.
- Przy encounterze z maszyną pojawia się opcja „odwołaj się do mitu skradzionego serca”.

## Narrator

Kategorie:
- `belief_seed_success`
- `belief_seed_partial`
- `belief_seed_fail`
- `belief_seed_critical_fail`
- `rumor_spread`
- `rumor_distorted`
- `logic_exploit_success`
- `logic_exploit_backfire`
- `sow_distrust_success`
- `panic_incited`
- `false_order_accepted`
- `sponsor_seizes_narrative`
- `audience_repeats_phrase`
- `enemy_hesitates_from_belief`
- `belief_returns_later`

Styl: polski jako pierwszy, złośliwie, bez monotonnych serii zdań o tej samej konstrukcji. Komentarz ma pokazywać, że system zauważa manipulację, ale nie zawsze ją rozumie.

## Achievementy

Minimalna lista:
- `pierwsze_klamstwo_systemowe` — pierwszy udany belief seed
- `to_brzmi_jak_religia` — belief seed nabiera cech mitu
- `przekonales_maszyne` — logic exploit wobec maszyn
- `plotka_ma_nogi` — rumor rozprzestrzenił się na inny pokój/piętro
- `to_wasza_wina` — skuteczne przerzucenie winy
- `publicznosc_powtarza` — audience zaczyna cytować hasło
- `nie_tak_to_mialo_dzialac` — belief seed ulega zniekształceniu i szkodzi graczowi
- `wojna_na_slowa` — skłócenie dwóch grup bez walki
- `doktryna_z_kartonu` — stworzenie skutecznej idei z absurdalnego założenia
- `sponsor_przejmuje_meme` — sponsor wykorzystuje kłamstwo gracza

## Granice

Memetyka nie może:
- natychmiast przejmować kontroli nad każdą grupą,
- tworzyć efektów bez świadków, kanału albo kontekstu,
- zastępować wszystkich społecznych encounterów,
- działać bez ryzyka,
- usuwać potrzeby testów,
- ignorować odporności celów.

Memetyka powinna:
- nagradzać kreatywność,
- pamiętać udane idee,
- komplikować świat,
- wracać później,
- dawać alternatywy wobec walki,
- tworzyć lore wynikające z działań gracza.
