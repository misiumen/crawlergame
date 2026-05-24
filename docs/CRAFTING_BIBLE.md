# CRAFTING_BIBLE.md

## Cel dokumentu

Ten dokument definiuje sposób działania craftingu, odzysku materiałów, rozbiórki obiektów i improwizacji w revampie. Ma ograniczyć przypadkowe dopisywanie receptur bez wspólnej logiki. Crafting nie jest osobnym menu ekonomicznym. To część eksploracji, przetrwania, lore i stylu gry.

## Filozofia systemu

Loch jest zbiorem zasobów, ale nie jest magazynem bez właściciela. Gracz może próbować rozebrać meble, ciała, kamery, automaty, drzwi, armaturę, terminale, potwory i śmieci. Świat powinien reagować na to fizycznie, społecznie i narracyjnie.

Crafting ma wspierać improwizację. Dokładne receptury istnieją, ale nie mogą być jedyną drogą. Jeżeli gracz pisze „robię pułapkę z kabli, szkła i baterii”, system powinien sprawdzić tagi materiałów, ryzyko, czas, narzędzia oraz kontekst. Wynik może być pełnym sukcesem, częściowym sukcesem, porażką albo katastrofą.

System nie może tworzyć nieskończonych zasobów. Każda encja po rozbiórce zmienia stan: `stripped`, `depleted`, `damaged`, `destroyed`, `harvested` albo podobny. Stan musi przechodzić przez save/load.

## Taksonomia akcji

### search / przeszukaj

Akcja informacyjno-lootowa. Służy do znalezienia tego, co jest ukryte, ale nadal sensownie dostępne. Nie niszczy obiektu domyślnie.

Przykłady:
- „przeszukaj ciało”
- „sprawdź szafkę”
- „poszukaj czegoś użytecznego przy terminalu”

Typowe efekty:
- znalezienie itemu,
- odkrycie materiału,
- odkrycie ukrytej encji,
- trop, clue albo plotka,
- upływ czasu.

### loot / ograb / weź

Zabranie przenośnych rzeczy z encji lub kontenera. Nie oznacza automatycznie rozbiórki.

Przykłady:
- „weź kartę z ciała”
- „ograb crawlera”
- „zabierz baterię z szuflady”

Typowe efekty:
- item trafia do inventory,
- świadkowie mogą zareagować,
- safehouse może potraktować to jako kradzież.

### strip / rozbierz

Usuwanie wyposażenia, ubrań, paneli, osłon albo części z większej encji. Bardziej inwazyjne niż loot.

Przykłady:
- „rozbierz ciało z pancerza”
- „ściągnij panel z automatu”
- „rozbierz drona z obudowy”

Typowe efekty:
- itemy lub materiały,
- uszkodzenie encji,
- wzrost obrzydzenia, podejrzliwości albo uwagi sponsorów.

### salvage / odzyskaj / zdemontuj

Rozbiórka obiektu na materiały. Może wymagać narzędzi, czasu i testu.

Przykłady:
- „zdemontuj kamerę”
- „odzyskaj przewody z panelu”
- „rozbij stół i weź nogi”

Typowe efekty:
- materiały,
- hałas,
- uszkodzenie obiektu,
- ryzyko elektryczne, chemiczne albo społeczne.

### harvest / pozyskaj

Organiczny odzysk materiałów z ciał, potworów, narośli, grzybów lub biomasy. To nie jest neutralna czynność.

Przykłady:
- „pozyskaj kości z potwora”
- „wytnij gruczoł z martwego śluzowca”
- „zbierz włókna z grzyba”

Typowe efekty:
- materiały organiczne,
- ryzyko infekcji,
- reakcje NPC,
- komentarz narratora,
- możliwe konsekwencje etyczne lub reputacyjne.

### dismantle / disassemble / rozmontuj

Techniczna rozbiórka z większą kontrolą niż `break_down`. Zwykle INT/DEX, często wymaga narzędzia.

### break_down / rozbij

Szybkie, brutalne niszczenie obiektu. Daje gorszy odzysk, robi hałas, może otworzyć drogę.

### craft / wytwórz

Tworzenie przedmiotu z materiałów według znanej receptury lub tagowej logiki improwizacji.

### improvise / improwizuj / skleć

Crafting bez pełnej receptury. System sprawdza cel, tagi materiałów, narzędzia, kontekst i ryzyko.

### repair / napraw

Przywraca działanie itemu, obiektu albo infrastruktury. Może używać materiałów.

### reinforce / wzmocnij

Tymczasowe albo trwałe ulepszenie itemu, barykady, pancerza lub narzędzia.

### deploy / rozstaw

Umieszczenie craftowanego przedmiotu w pokoju: pułapki, wabika, barykady, czujnika, ładunku, linki, przynęty. Po deployu przedmiot staje się encją lub efektem pokoju.

## Materiały i tagi

Każdy materiał powinien mieć tagi opisujące funkcję. Tagi są ważniejsze niż nazwa materiału.

### Kategorie materiałów

- metaliczne: `scrap_metal`, `screws`, `metal_pipe`, `pressure_valve`
- drewniane i konstrukcyjne: `wood_fragments`, `table_leg`, `shelf_board`
- techniczne: `wire_bundle`, `circuit_board`, `battery_cell`, `camera_lens`, `sensor_module`
- chemiczne: `cleaning_fluid`, `acid_residue`, `flammable_gel`, `coolant`, `medical_alcohol`
- organiczne: `bone_fragments`, `monster_hide`, `sinew`, `meat_chunk`, `strange_organ`, `fungal_fiber`
- tekstylne i miękkie: `cloth_strips`, `leather_scraps`, `rubber_strip`
- sponsorowane i dziwne: `sponsor_chip`, `audience_token`, `contract_scrap`, `anomaly_dust`, `void_residue`

### Tagi użytkowe

- `sharp`: cięcie, pułapki, broń
- `rigid`: konstrukcja, kij, dźwignia
- `flexible`: opaski, zawiasy, amortyzacja
- `binding`: wiązanie, linki, pułapki
- `electrical`: porażenie, panel, bateria
- `conductive`: przewodzenie
- `insulating`: izolacja, bezpieczniejszy kontakt z prądem
- `flammable`: ogień, wabiki, bomby
- `toxic`: trucizna, chemia
- `adhesive`: klejenie, mocowanie
- `organic`: przynęty, obrzydliwe craftingi
- `medical`: leczenie, dezynfekcja
- `structural`: barykady, podpory
- `sponsor_tech`: kamery, chipy, publiczność
- `anomalous`: efekty dziwne, ryzykowne
- `disguise`: kamuflaż społeczny
- `noise`: dystrakcja
- `bait`: wabienie

## Logika improwizacji

Jeżeli nie znaleziono dokładnej receptury, system powinien spróbować tagowej klasyfikacji celu.

Przykłady:

- `binding` + `sharp` → linka tnąca, pułapka na nogi
- `battery/electrical` + `wire/conductive` → shock trap
- `organic/bait` + `noise` → wabik
- `rigid` + `sharp` → prowizoryczna broń
- `cloth` + `medical/alcohol` → opatrunek
- `sponsor_tech` + `camera_lens` → wabik na kamerę lub czujnik
- `flammable` + `container` → butelka zapalająca
- `structural` + `rigid` + `binding` → barykada lub wzmocnienie drzwi
- `disguise` + `cloth/leather` + `badge` → prowizoryczne przebranie

Wynik improwizacji powinien mieć jakość:
- `crude`
- `unstable`
- `functional`
- `clever`
- `excellent`

Jakość wpływa na bonus, ryzyko, trwałość i narrator lines.

## Kontekst i własność

### Swobodny odzysk

Zwykle akceptowalny:
- martwe potwory,
- opuszczone śmieci,
- połamane meble,
- zniszczone maszyny,
- wraki po walce,
- gruz lochu.

### Ryzykowny odzysk

Wymaga reakcji świata:
- ciała crawlerów,
- sprzęt safehouse,
- wyposażenie kliniki,
- półki handlarza,
- kamery sponsorów,
- armatura łazienkowa,
- własność frakcji.

Encje w safehouse lub miejscach neutralnych powinny dostawać:
- `state["owned_by"] = "safehouse"` albo nazwę właściciela,
- `state["theft_sensitive"] = True`.

Kradzież i rozbiórka mogą być fizycznie możliwe, ale społecznie kosztowne.

## Wyniki testów i fail-forward

Crafting i salvage nie mogą być wyłącznie binarne.

### Critical success

- item lepszej jakości,
- mniej zużytych materiałów,
- dodatkowy materiał,
- audience bonus,
- wyjątkowa narrator line,
- achievement.

### Success

- zamierzony wynik,
- standardowy koszt czasu i materiałów.

### Partial success

- item działa, ale ma wadę,
- dodatkowy koszt czasu,
- hałas,
- widoczna prowizorka,
- mniejsza trwałość,
- wzrost podejrzeń,
- częściowa utrata materiałów.

### Failure

- brak itemu albo bezużyteczny item,
- część materiałów przepada,
- czas mija,
- drobny hałas albo frustracja.

### Critical failure

- samookaleczenie,
- pożar, porażenie, chemiczny rozbryzg,
- natychmiastowe odpalenie pułapki,
- alarm,
- sponsorzy oznaczają gracza,
- właściciel reaguje.

## Narrator

Narrator nie jest dodatkiem. Jest głosem systemu i feedbackiem lore.

Kategorie obowiązkowe:
- `salvage_success`
- `salvage_partial`
- `salvage_fail`
- `salvage_critical_fail`
- `furniture_salvage`
- `tech_salvage`
- `bathroom_salvage`
- `safehouse_theft_attempt`
- `safehouse_theft_escalation`
- `sponsor_property_salvage`
- `corpse_loot`
- `corpse_strip`
- `corpse_harvest`
- `monster_harvest`
- `crawler_corpse_looted`
- `disgusting_but_useful`
- `everything_is_material`
- `craft_success`
- `craft_partial`
- `craft_fail`
- `craft_critical_fail`
- `absurd_craft_attempt`
- `clever_craft`
- `dangerous_craft`
- `unstable_item_created`
- `improvised_weapon_created`
- `improvised_trap_created`
- `improvised_tool_created`
- `repair_success`
- `reinforce_success`
- `deploy_trap_success`
- `deploy_trap_fail`
- `trap_self_trigger`
- `rare_material_found`
- `sponsor_component_found`
- `anomalous_material_found`
- `forbidden_material_harvested`
- `audience_likes_recycling`
- `audience_disgusted`
- `sponsor_files_complaint`

Styl: polski jako pierwszy, krótko, złośliwie, bez suchego technicznego tonu. Unikaj serii zdań o tej samej składni. Zmieniaj rytm, długość i konstrukcję zdań.

## Achievementy

Achievementy są częścią lore. Nie są wyłącznie odznakami.

Lista minimalna:
- `wszystko_jest_surowcem` — pierwszy udany salvage
- `meble_tez_krwawia` — salvage mebla
- `recykling_agresywny` — rozbiórka pięciu obiektów
- `rzemieslnik_z_paniki` — crafting w niebezpieczeństwie
- `przepis_jaki_przepis` — udana improwizacja bez dokładnej receptury
- `rozbiorka_zwlok` — harvest ciała
- `technicznie_to_loot` — moralnie wątpliwa rozbiórka
- `kradziez_armatury` — rozbiórka armatury łazienkowej
- `sponsor_nie_pochwala` — naruszenie własności sponsora/safehouse
- `pulapka_z_niczego` — pierwsza craftowana pułapka
- `samo_sie_rozstawilo` — krytyczna porażka deployu
- `inzynieria_odwagi` — craftowany item rozwiązał encounter
- `obrzydliwe_ale_dziala` — crafting z organicznych/cielesnych materiałów
- `zlota_raczka_lochu` — dziesięć craftowanych itemów
- `ekonomia_przetrwania` — dwadzieścia udanych operacji salvage
- `smiec_wartosciowy` — śmieciowy materiał użyty w ważnej akcji

## UI i feedback

Gracz musi widzieć:
- materiały zdobyte,
- stan encji po rozbiórce,
- jakość craftu,
- wadę itemu,
- konsekwencje społeczne,
- czy przedmiot da się rozstawić,
- achievement unlock,
- komentarz narratora.

Komendy pomocy:
- `materiały`
- `materialy`
- `materials`
- `pomoc craftingu`
- `craft help`
- `pomoc odzysku`
- `salvage help`
- `pomoc pułapek`
- `trap help`
- `deploy help`
- `pomoc rozstawiania`

## Save/load

Zapisywać:
- `character.materials`,
- crafted items,
- item quality,
- item flaws,
- item damage,
- placed traps,
- entity salvage state,
- entity ownership flags,
- social suspicion,
- achievements,
- relevant narrator flags if needed to avoid spam.

Nie przeliczać craftingu po wczytaniu. Nie rerollować materiałów z tej samej encji.

## Granice systemu

Crafting nie może:
- omijać każdego encountera bez kosztu,
- dawać nieskończonych materiałów,
- działać bez odpowiednich encji lub materiałów,
- zastępować informacji, relacji i planowania,
- ignorować własności safehouse,
- zmieniać świata bez zapisu stanu.

Crafting powinien:
- nagradzać obserwację,
- nagradzać powrót do wcześniejszych pokoi,
- wspierać improwizację,
- tworzyć komplikacje,
- budować styl gracza,
- dostarczać narratorowi i achievementom silnego materiału lore.
