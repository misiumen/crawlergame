"""Procedural room pool.

Each entry is a *template*, not a placed room. A floor generator selects
templates by tag + role, instantiates them with random names from pools,
and wires exits dynamically (room_pool templates do NOT carry hardcoded
`target` room ids — that is done at generation time).

Shape (kept compatible with revamp/data/room_templates.py for the
hand-authored slice, but with `exits` intentionally empty):

  {
    "template_id": str,             # stable ASCII key
    "role": str,                    # safe | danger | loot | social | secret | objective | boss
    "actual_type": str,             # combat | trap | loot | safehouse | lore | secret | boss
    "tags": [str, ...],             # safe/dangerous/loot/social/secret/non_combat/...
    "safehouse_subtype": str|None,  # if role == safe
    "name_pool": [str, ...],        # localized display-name choices
    "first_enter_pool": [str, ...], # one of these is picked at generation
    "look_pool": [str, ...],
    "search_pool": [str, ...],
    "public_hint_pool": [str, ...],
    "sensory_tags": [str, ...],
    "entity_seed_pools": {           # role-driven seed buckets
      "env":  [seed_keys...],        # picked from entity_templates.ENV
      "haz":  [seed_keys...],
      "item": [seed_keys...],
      "term": [seed_keys...],
      "svc":  [seed_keys...],
      "mon":  [seed_keys...],
      "npc":  [(archetype_key, disposition), ...],
    },
    "exit_hints": [str, ...],        # natural exit labels the generator can pick from
    "guaranteed_min_exits": 1,
    "guaranteed_max_exits": 3,
    "weight": int,                   # selection weight inside the role bucket
    "floor_min": 1,
  }

A generator-side instantiator should pick exactly one entry from each
"_pool" list, then assign IDs and wire exits when the floor graph is built.
"""

ROOM_POOL = [
    # ── Safe zones ──────────────────────────────────────────────────────────
    {
        "template_id": "pool_cafe",
        "role": "safe",
        "actual_type": "safehouse",
        "tags": ["safe", "safehouse", "social", "rumor"],
        "safehouse_subtype": "cafe",
        "name_pool": ["Kafejka „Posłuszny Klient”", "Ostatni Łyk",
                      "Bufet Neutralności", "Kawa Przed Przemocą"],
        "first_enter_pool": [
            "Stoliki z taniego laminatu, krzesła ustawione zbyt regularnie. Na ścianie "
            "ekran z reklamą sponsorską na pętli, dźwięk wyłączony. Za ladą stoi zawodnik "
            "w fartuchu, udający, że pracuje.",
            "Neon nad ladą mruga: KAWA NIE GWARANTUJE PRZEŻYCIA. Pod spodem ktoś dopisał: "
            "ALE POMAGA UMRZEĆ PRZYTOMNIE. Pachnie palonym ziarnem i wczorajszą krwią.",
        ],
        "look_pool": [
            "Lampy nad stolikami świecą za jasno. Na środkowym stoliku ktoś zostawił kubek "
            "z resztką zimnej kawy. Ktoś siedzi przy oknie i nie pije.",
        ],
        "search_pool": [
            "Pod stolikiem dwa: wciśnięta wizytówka z napisem 'kontaktor'.",
        ],
        "public_hint_pool": [
            "Skrzypiące krzesło. Ekran reklamy. Zapach kawy.",
            "Brzęk szkła. Cichy śmiech. Klimat dnia powszedniego, który nigdy nie był powszedni.",
        ],
        "sensory_tags": ["bright", "warm", "coffee", "sponsor_ads"],
        "entity_seed_pools": {
            "svc":  ["coffee_counter"],
            "env":  ["sponsor_screen","coffee_machine","furniture_wood","loose_chair",
                     "vending_machine","trash_bin"],
            "npc":  [("paranoid_mapper", "friendly"), ("loot_goblin_crawler", "neutral")],
            "item": ["cracked_mug", "snack_bar"],
        },
        "exit_hints": ["zachód", "wschód", "zaplecze"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 3,
        "weight": 8,
        "floor_min": 1,
        "unique_per_floor": True,   # P28.5: one cafe per floor
    },
    {
        "template_id": "pool_bathroom",
        "role": "safe",
        "actual_type": "safehouse",
        "tags": ["safe", "safehouse", "secret_entry"],
        "safehouse_subtype": "bathroom",
        "name_pool": ["Publiczna Łazienka 1A", "Autoryzowana Łazienka 7",
                      "Sanitarny Rozejm", "Kabiny Bez Gwarancji"],
        "first_enter_pool": [
            "Kafelki w kolorze 'kiedyś białym'. Pod jedną z umywalek bulgocze coś, co "
            "nie powinno. Lustro popękane, ale w jednym fragmencie nadal coś pokazuje. "
            "Drzwi do kabin uchylone, puste.",
            "Łazienka jest za czysta. To pierwszy i najgorszy znak. Lustra pokazują cię "
            "z opóźnieniem o pół sekundy.",
        ],
        "look_pool": [
            "Kafelki. Zimne, mokre, nieprzyjemnie czyste. Drzwi do korytarza. Jedna kabina "
            "w głębi wygląda na zaryglowaną od środka.",
        ],
        "search_pool": [
            "Pod umywalką znajdujesz brudny bandaż i kawałek metalowego drutu. Nad lustrem "
            "ktoś wyrysował małą strzałkę wskazującą na sufit. Sufit ma wyglądającą na "
            "luźną kratę.",
        ],
        "public_hint_pool": [
            "Bulgotanie. Kapanie. Ktoś szepcze do lustra.",
        ],
        "sensory_tags": ["damp", "cold", "echo", "graffiti"],
        "entity_seed_pools": {
            "svc":  ["mirror"],
            "env":  ["loose_grate","bathroom_fixture","sink","toilet_stall",
                     "pipe_cluster","cleaning_cabinet","mirror"],
            "item": ["dirty_bandage"],
        },
        "exit_hints": ["północ", "sufit"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 6,
        "floor_min": 1,
        "unique_per_floor": True,   # P28.5: one bathroom per floor
    },
    {
        "template_id": "pool_black_market",
        "role": "safe",
        "actual_type": "safehouse",
        "tags": ["safe", "safehouse", "trade", "contraband", "objective_path"],
        "safehouse_subtype": "black_market",
        "name_pool": ["Bez Paragonu", "Gwarancja Martwa",
                      "Rynek Pod Zlewem", "Legalnie Prawie"],
        "first_enter_pool": [
            "Czarny rynek mieści się tam, gdzie mapa pokazuje ścianę. To dobry znak albo "
            "bardzo zły, zależnie od twojego budżetu.",
            "Na ladzie leżą rzeczy, które ktoś zgubił, sprzedał albo nadal próbuje "
            "odzyskać z zaświatów.",
        ],
        "look_pool": [
            "Lada. Sprzedawca w okularach przeciwsłonecznych. Pod ladą widać kawałek karty "
            "z napisem SERWIS.",
        ],
        "search_pool": [
            "Pod jedną ze skrzynek znajdujesz odznakę z innego piętra.",
        ],
        "public_hint_pool": [
            "Cisza za drzwiami. Bardzo deliberowana cisza.",
        ],
        "sensory_tags": ["dim", "quiet", "contraband", "sponsor_free"],
        "entity_seed_pools": {
            "svc":  ["sponsor_kiosk"],
            "npc":  [("loot_goblin_crawler", "friendly")],
            "env":  ["supply_crate", "metal_shelf"],
            "item": ["suspicious_keycard"],
        },
        "exit_hints": ["z powrotem do korytarza"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 4,
        "floor_min": 1,
        "unique_per_floor": True,   # P28.5: one black market per floor
    },
    {
        "template_id": "pool_clinic",
        "role": "safe",
        "actual_type": "safehouse",
        "tags": ["safe", "safehouse", "heal", "expensive"],
        "safehouse_subtype": "clinic",
        "name_pool": ["Klinika Polowa NovaChem", "Klinika Bez Pytań",
                      "Punkt Sanitarny 7", "NovaChem Triage"],
        "first_enter_pool": [
            "Białe płytki, lampy halogenowe i zapach środka dezynfekującego, który "
            "próbuje ukryć krew. Recepcja obsługiwana przez maszynę.",
        ],
        "look_pool": [
            "Cennik wisi na ścianie. Wszystko bardzo drogie i bardzo dokładne.",
        ],
        "search_pool": [
            "Pod regałem znajdujesz zalakowany bandaż i kartonik z napisem ZWROT NIEMOŻLIWY.",
        ],
        "public_hint_pool": [
            "Cisza. Zapach alkoholu. Cichy ekran z kolejką.",
        ],
        "sensory_tags": ["bright", "cold", "clinical"],
        "entity_seed_pools": {
            "svc":  ["clinic_counter"],
            "item": ["dirty_bandage"],
            "env":  ["medical_cabinet","biohazard_bin","bandage_box",
                     "disinfectant_shelf","broken_monitor"],
        },
        "exit_hints": ["korytarz"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 5,
        "floor_min": 1,
        "unique_per_floor": True,   # P28.5: one clinic per floor
    },

    # ── Combat / dangerous ──────────────────────────────────────────────────
    {
        "template_id": "pool_corridor_runt",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "environment", "non_combat"],
        "name_pool": ["Korytarz Serwisowy A", "Mokry Łącznik B",
                      "Sekcja Konserwacyjna 3"],
        "first_enter_pool": [
            "Wąski korytarz, sufit nisko, jedna świetlówka pulsuje. Ściany pokrywa "
            "zielonkawy osad, który wygląda jak coś, co kiedyś żyło. Powietrze wibruje "
            "cichym buczeniem maszyn.",
        ],
        "look_pool": [
            "Z jednej strony korytarz, z drugiej ciemniejszy łuk drzwi. Na ścianach gołe "
            "przewody, w kącie kałuża wody.",
        ],
        "search_pool": [
            "Pod luźną płytą podłogi znajdujesz fragment notatki z numerem dostępu.",
        ],
        "public_hint_pool": [
            "Coś chodzi tam i z powrotem. Mokry odgłos kroków.",
            "Słychać kapanie i krótkie, krótkie oddechy.",
        ],
        "sensory_tags": ["dim", "humming", "mossy_smell"],
        "entity_seed_pools": {
            "mon": ["tunnel_runt"],
            "env": ["exposed_wiring","water_pool","broken_table","debris_pile",
                    "sponsor_camera","loose_shelf"],
        },
        "exit_hints": ["wschód", "zachód", "południe"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 7,
        "floor_min": 1,
    },
    {
        "template_id": "pool_chem_lab",
        "role": "danger",
        "actual_type": "trap",
        "tags": ["dangerous", "hazard", "environment", "non_combat"],
        "name_pool": ["Sala Chemiczna NovaChem", "Laboratorium B-3",
                      "Sekcja Reaktywna"],
        "first_enter_pool": [
            "Zielonkawe światło bije z górnej rury. Na podłodze kałuża czegoś, co dymi "
            "przy dotknięciu z metalem. Stół laboratoryjny zastawiony pustymi szkłami.",
        ],
        "look_pool": [
            "Kwas na podłodze. Butla gazu pod ścianą. Na ścianie naklejka: "
            "NIE MIESZAĆ KWASU Z OGNIEM. DZIĘKUJEMY ZA WSPÓŁPRACĘ.",
        ],
        "search_pool": [
            "Pod stołem zardzewiały, ale ostry nóż. Ktoś musiał stracić cierpliwość.",
        ],
        "public_hint_pool": [
            "Słodki zapach. Ciche bulgotanie.",
        ],
        "sensory_tags": ["acid", "gas", "green_light"],
        "entity_seed_pools": {
            "haz":  ["acid_pool"],
            "env":  ["gas_canister", "pipe_cluster", "broken_table",
                     "broken_monitor"],
            "item": ["cheap_knife"],
        },
        "exit_hints": ["zachód", "wschód"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
    },
    {
        "template_id": "pool_freezer_carver",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "stealth", "non_combat", "locked"],
        "name_pool": ["Zamrażarka — Mięso Nieidentyfikowalne",
                      "Chłodnia Konserwacyjna", "Lodówka 4-C"],
        "first_enter_pool": [
            "Zimno. Białe światło z fluorków. Pod ścianami wiszą foliowane bryły, które "
            "kiedyś mogły być czymś żywym. Coś chrupie. Coś łowi.",
        ],
        "look_pool": [
            "Mróz wgryza ci się w policzki. W głębi pomieszczenia stoi otwarty kontener z "
            "wyposażeniem ratowniczym.",
        ],
        "search_pool": [
            "Z kontenera wyciągasz batona z 2023 roku i podejrzanie sprawną latarkę.",
        ],
        "public_hint_pool": [
            "Bardzo zimno. Skrobanie. Cichy oddech.",
        ],
        "sensory_tags": ["cold", "bright", "meat_smell"],
        "entity_seed_pools": {
            "mon":  ["freezer_carver"],
            "item": ["flashlight", "snack_bar"],
        },
        "exit_hints": ["zachód"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 3,
        "floor_min": 1,
    },

    # ── Loot / utility ──────────────────────────────────────────────────────
    {
        "template_id": "pool_storage",
        "role": "loot",
        "actual_type": "loot",
        "tags": ["loot", "search_rewarded"],
        "name_pool": ["Zaplecze Kafejki", "Magazyn 2", "Sekcja Konserwacji"],
        # P27.5: zmiana flavor — poprzedni „KONTAKT — NIE OTWIERAĆ"
        # sugerował że pokój jest zamknięty (a w data nie był), co
        # spowodowało dezorientację playtestera. Nowy tekst opisuje
        # pomieszczenie jako standardowy magazyn — gracz nie ma
        # narratywnego oczekiwania że jest zamknięte.
        "first_enter_pool": [
            "Magazyn pełen zakurzonych pudeł. Etykiety wyblakłe. "
            "Klimatyzacja brzęczy nierównomiernie.",
        ],
        "look_pool": [
            "Półki pełne syropów, mleka w proszku i czegoś, co ma datę ważności sprzed dwóch lat.",
        ],
        "search_pool": [
            "Pod jednym z kartonów znajdujesz baterię i kawałek taśmy izolacyjnej.",
        ],
        "public_hint_pool": [
            "Klimatyzacja. Coś brzęczy.",
        ],
        "sensory_tags": ["dusty", "warm", "electrical_hum"],
        "entity_seed_pools": {
            "item": ["battery", "duct_tape"],
            "term": ["storage_terminal"],
            "env":  ["supply_crate","locker","metal_shelf","sealed_box","machine_scrap"],
        },
        "exit_hints": ["z powrotem"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 6,
        "floor_min": 1,
    },
    {
        "template_id": "pool_maintenance_closet",
        "role": "loot",
        "actual_type": "loot",
        "tags": ["loot", "objective_path", "search_rewarded", "non_combat"],
        "name_pool": ["Schowek Serwisowy", "Schowek Konserwatora", "Pakamera Sponsora"],
        "first_enter_pool": [
            "Ciasno. Półki, na których stoi wszystko poza tym, czego szukasz. Pod ścianą "
            "wisi tabliczka z napisem 'KLUCZE — NIE BRAĆ' nad pustym haczykiem.",
        ],
        "look_pool": [
            "Półki, kratka wentylacyjna, pusty haczyk. Jedyne wyjście to drzwi za tobą.",
        ],
        "search_pool": [
            "Po dłuższym przeszukaniu pod paczką ścierek znajdujesz niewielką, "
            "ciemnoczerwoną kartę z napisem KONTRAKTOR.",
        ],
        "public_hint_pool": [
            "Drzwi z napisem 'SERWIS — TYLKO PERSONEL'. Cisza w środku.",
        ],
        "sensory_tags": ["dim", "dusty", "crowded"],
        "entity_seed_pools": {
            "item": ["suspicious_keycard", "duct_tape"],
            "env":  ["loose_cables","electrical_panel","wire_bundle_source",
                     "machine_scrap","vent_grate","pressure_valve","broken_terminal"],
        },
        "exit_hints": ["z powrotem", "kratka (sufit)"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
    },

    # ── Social hubs ─────────────────────────────────────────────────────────
    {
        "template_id": "pool_lounge",
        "role": "social",
        "actual_type": "safehouse",
        "tags": ["safe", "social", "crawler", "rumor"],
        "safehouse_subtype": "lounge",
        "name_pool": ["Lounge — „Druga Szansa”", "Salon Restytucji",
                      "Bar Pod Czerwoną Lampką"],
        "first_enter_pool": [
            "Przyćmione światło, kanapy z imitacji skóry, ekran nad barem z aktualnym "
            "rankingiem. Crawlerzy udają, że nie liczą się nawzajem.",
        ],
        "look_pool": [
            "Bar, kanapy, ekran rankingowy. Pod ścianą — drzwi bez klamki z napisem "
            "'KIEROWNICTWO'.",
        ],
        "search_pool": [
            "Pod kanapą znajdujesz wciśniętą zapomnianą wizytówkę z napisem 'ma kartę w marynarce'.",
        ],
        "public_hint_pool": [
            "Tłumiona muzyka. Brzęk kostek lodu.",
        ],
        "sensory_tags": ["dim", "music", "crowded"],
        "entity_seed_pools": {
            "npc": [("wounded_brawler", "friendly"), ("loot_goblin_crawler", "neutral")],
            "env": ["sponsor_screen"],
        },
        "exit_hints": ["korytarz administracyjny"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 1,
        "unique_per_floor": True,   # P28.5: one lounge per floor (fixes
                                     # bug where Druga Szansa + Bar Pod
                                     # Czerwoną Lampką spawned side-by-side
                                     # with identical NPCs).
    },

    # ── Secret / sneaky ─────────────────────────────────────────────────────
    {
        "template_id": "pool_vent_shaft",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "shortcut", "non_combat", "stealth"],
        "name_pool": ["Szyb Wentylacyjny", "Pion Serwisowy", "Kanał Powietrzny"],
        "first_enter_pool": [
            "Ciasno. Czarno. Kolana boli już po pięciu metrach. Powietrze zalatuje "
            "smarem i czymś słodkim, czego nie chcesz znać.",
        ],
        "look_pool": [
            "Szyb rozgałęzia się. Jedna nitka prowadzi w dół, druga w stronę dziwnego "
            "ciepła.",
        ],
        "search_pool": [
            "Wciśnięta między blachy karteczka: '7-3-7 nie działa od piątku. Spróbuj 7-3-9.'",
        ],
        "public_hint_pool": [
            "Echo. Cichy stuk metalu.",
        ],
        "sensory_tags": ["dark", "cramped", "oily"],
        "entity_seed_pools": {
            "item": ["suspicious_keycard"],
        },
        "exit_hints": ["w dół", "biuro techniczne"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 1,
    },

    # ── Lore ────────────────────────────────────────────────────────────────
    {
        "template_id": "pool_office",
        "role": "lore",
        "actual_type": "lore",
        "tags": ["lore", "loot", "objective_path", "tech"],
        "name_pool": ["Biuro Technika", "Biuro Konserwatora", "Punkt Operacyjny"],
        "first_enter_pool": [
            "Małe biuro z biurkiem zasłanym papierami, zdychającym monitorem i kubkiem po "
            "kawie, który stoi tu od zbyt długiego czasu.",
        ],
        "look_pool": [
            "Schemat piętra na ścianie. Terminal z migającym logiem.",
        ],
        "search_pool": [
            "Pod papierami: zestaw wytrychów (improwizowany) i karteczka z hasłem 'klepsydra'.",
        ],
        "public_hint_pool": [
            "Ledwo działający monitor.",
        ],
        "sensory_tags": ["warm", "paper", "old_tech"],
        "entity_seed_pools": {
            "term": ["office_terminal"],
            "env":  ["broken_monitor", "loose_shelf"],
            "item": ["improvised_lockpick"],
        },
        "exit_hints": ["szyb", "przekaźnik"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
    },

    # ═════════════════════════════════════════════════════════════════════
    # P29.1 — Piętra 3-6 content. DCC-themed: ZOO / NEIGHBORHOOD /
    # MUSEUM / BAR. Each floor has 3 themed templates: a combat room,
    # a danger/loot room, and the floor boss. Monsters & sponsors are
    # in entity_templates.py and content/data/sponsors.py respectively.
    # ═════════════════════════════════════════════════════════════════════

    # ── Piętro 3: ZOO (sponsor: Czarny Rynek) ─────────────────────────────
    {
        "template_id": "pool_cage_block",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "zoo", "animal"],
        "name_pool": ["Klatkowy Sektor B", "Sala Egzotyczna",
                      "Korytarz Klatek 3"],
        "first_enter_pool": [
            "Klatki. Niektóre puste, niektóre nie. Powietrze pachnie sianem, "
            "potem i czymś, co kiedyś żyło zbyt długo. Ze ścian odbija się "
            "wycie — nie wiesz, czy zwierzęce, czy z głośnika.",
        ],
        "look_pool": [
            "Pręty wygięte od środka. Karmnik przewrócony. W kącie kałuża, "
            "której nikt nie sprząta. Coś chodzi tu i z powrotem.",
        ],
        "search_pool": [
            "Pod złamaną kratą znajdujesz kartkę: 'EGZEMPLARZ 7 — NIE KARMIĆ "
            "PALCAMI. PALCE NA WYŻYWIENIE'.",
        ],
        "public_hint_pool": [
            "Pazury po podłodze. Ciężkie sapanie zza krat.",
            "Coś macha ogonem o pręt. Rytmicznie.",
        ],
        "sensory_tags": ["fur", "blood", "animal_smell"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur", "klatkowy_kot"],
            "env":  ["broken_cage", "feeding_trough", "loose_chain"],
            "item": ["snack_bar"],
        },
        "exit_hints": ["wschód", "zachód", "korytarz"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 3,
        # P29.2 — ZOO inspires Czarny Rynek (exotic exemplars trade)
        # and slightly Ministerstwo dislikes (illegal pet handling).
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_feeding_pit",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "zoo"],
        "name_pool": ["Pit Karmienia", "Resztki Atrakcji", "Dół"],
        "first_enter_pool": [
            "Schodzisz po metalowych szczeblach w dół. Smród uderza pierwszy. "
            "Na dnie szczątki — kości, futro, paragony. Ktoś prowadził tu "
            "rachunkowość, a potem przestał.",
        ],
        "look_pool": [
            "Stos szkieletów, pęknięta beczka po krwi, połamana sponsoreska "
            "tabliczka. Wgnieciona barierka — coś tu z dołu wyszło.",
        ],
        "search_pool": [
            "W gruzowisku znajdujesz nadgryzioną torbę z odznaczeniem "
            "Czarnego Rynku i parę kredytów rozsypanych po kościach.",
        ],
        "public_hint_pool": [
            "Brzęczą muchy. Inaczej cicho.",
        ],
        "sensory_tags": ["rot", "metal", "blood_dried"],
        "entity_seed_pools": {
            "mon":  ["bekajacy_paw"],
            "env":  ["bone_pile", "broken_barrel", "sponsor_plaque_cracked"],
            "item": ["dirty_bandage", "snack_bar"],
        },
        "exit_hints": ["góra", "drabina"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_zoo_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "zoo"],
        "name_pool": ["Apex Klatka", "Sala Główna Pokazów",
                      "Arena Egzemplarza"],
        "first_enter_pool": [
            "Olbrzymia okrągła sala. Trybuny puste. Pośrodku — klatka "
            "centralna, otwarta. Coś z niej wyszło i siedzi na trybunach. "
            "Reflektor punktowo śledzi to coś. Drzwi wyjściowe za areną.",
        ],
        "look_pool": [
            "Arena. Trybuny. Reflektor podąża za tym czymś. Drzwi na "
            "drugim końcu mają tabliczkę: 'WYJŚCIE Z PIĘTRA — TYLKO PO "
            "ROZWIĄZANIU PROBLEMU'.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Pomruk. Bardzo niski. Nie wiesz, czy z głośnika, czy z gardła.",
        ],
        "sensory_tags": ["bright", "loud", "blood"],
        "entity_seed_pools": {
            "mon": ["boss_panicz_zoo"],
            "env": ["sponsor_camera", "feeding_trough"],
        },
        "exit_hints": ["wyjście piętra", "wschód"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 3,
        "unique_per_floor": True,
        # Boss fight in zoo nets double Czarny Rynek love.
        "theme_sponsor_boost": {"czarny_rynek_plus": 2},
    },

    # ── Piętro 4: NEIGHBORHOOD (sponsor: Ministerstwo) ────────────────────
    {
        "template_id": "pool_kuchnia_sasiada",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "domestic", "neighborhood"],
        "name_pool": ["Kuchnia Pana Sąsiada", "Jadalnia z Frywolnością",
                      "Bistro Mieszkańca"],
        "first_enter_pool": [
            "Wnętrze tańsze niż wygląda. Stół zastawiony jak na święta, "
            "ale wszystko zimne. Z piekarnika sączy się dym, który nie "
            "pachnie jak chleb. Sąsiad uśmiecha się od progu — za szeroko.",
        ],
        "look_pool": [
            "Stół. Talerze. Sąsiad. Sąsiad nie mruga. Z piekarnika płynie "
            "wąska strużka czerwonego.",
        ],
        "search_pool": [
            "Pod talerzem znajdujesz wycinek z gazety: 'PRAWDZIWE SĄSIEDZTWO "
            "GŁOSUJE GOTOWE NOŻE'.",
        ],
        "public_hint_pool": [
            "Cichy dzwonek z piekarnika. Sąsiad nuci coś z reklamy.",
        ],
        "sensory_tags": ["warm", "burnt_meat", "polish_floor"],
        "entity_seed_pools": {
            "mon":  ["usmiechniety_sasiad"],
            "env":  ["set_table", "smoking_oven", "wall_clock"],
            "item": ["cheap_knife"],
        },
        "exit_hints": ["korytarz", "ogród", "spiżarnia"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 4,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_ogrod_szczescia",
        "role": "danger",
        "actual_type": "trap",
        "tags": ["dangerous", "hazard", "neighborhood", "non_combat"],
        "name_pool": ["Ogród Szczęścia", "Ogródek Pani M.",
                      "Trawnik z Hasłem"],
        "first_enter_pool": [
            "Sztuczna trawa, sztuczne słońce. Płot z plastiku. Na "
            "pagórku tabliczka: 'TUTAJ JEST DOBRZE. NIE WCHODŹ NA "
            "TRAWNIK.' Pod trawą — coś metalowego, błyszczy.",
        ],
        "look_pool": [
            "Płot. Tabliczka. Pod trawą widać setki cienkich linek. "
            "Krzaki kiwają się bez wiatru.",
        ],
        "search_pool": [
            "Pod sztuczną darnią znajdujesz potykacz z drutu i pęczek "
            "etykietek 'GOSPODARCZA ZNALEZIONA'.",
        ],
        "public_hint_pool": [
            "Wieje wiatr, którego nie czujesz na skórze.",
        ],
        "sensory_tags": ["plastic", "fake_sun", "wire"],
        "entity_seed_pools": {
            "mon":  ["dzieciak_z_blokowiska"],
            "haz":  ["trip_wire_array"],
            "env":  ["plastic_fence", "neighborhood_sign", "fake_grass"],
        },
        "exit_hints": ["bramka", "tylne wejście"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 4,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_swietlica_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "neighborhood"],
        "name_pool": ["Świetlica Osiedlowa", "Sala Wspólnoty",
                      "Dom Sąsiedzki"],
        "first_enter_pool": [
            "Sala konferencyjna z plastikowymi krzesełkami w okręgu. "
            "Pośrodku — fotel z poduszką. W fotelu siedzi Block Parent. "
            "Uśmiecha się tak, jak uśmiecha się ktoś, kto wie więcej "
            "o twoim dzieciństwie niż ty sam.",
        ],
        "look_pool": [
            "Krzesełka. Fotel. Block Parent. Tabliczka z napisem "
            "'KIEROWNICTWO OSIEDLOWE — WSTĘP PO ZATWIERDZENIU' nad "
            "drzwiami wyjściowymi.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Stary plakat 'Dobry sąsiad nie pyta o twoje plany' szeleści.",
        ],
        "sensory_tags": ["fluorescent", "old_carpet", "tea"],
        "entity_seed_pools": {
            "mon": ["boss_blok_parent"],
            "env": ["sponsor_camera", "wall_clock", "neighborhood_sign"],
        },
        "exit_hints": ["wyjście piętra", "biuro"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 4,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 2},
    },

    # ── Piętro 5: MUSEUM (sponsor: Recykling Świętej Pamięci) ─────────────
    {
        "template_id": "pool_galeria",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "museum", "fragile"],
        "name_pool": ["Galeria Wschodnia", "Sala Eksponatów",
                      "Krużganek Pamięci"],
        "first_enter_pool": [
            "Wysokie sklepienie, marmurowa posadzka. Gabloty z eksponatami. "
            "Pod jedną z nich błyska niebieska dioda — alarm gotowy. "
            "Cisza tak głęboka, że słyszysz własne oczy.",
        ],
        "look_pool": [
            "Gabloty. Eksponaty: stara konsola gier, dyplom uczelni, "
            "płyta winylowa, telefon z klapką. Każde ma tabliczkę "
            "'PAMIĘĆ ZE ŚWIATA PRZED ZAŁAMANIEM'.",
        ],
        "search_pool": [
            "Pod jedną gablotą znajdujesz mosiężny klucz z etykietą "
            "'MAGAZYN B-2 / RELIKWIE NIEAUTORYZOWANE'.",
        ],
        "public_hint_pool": [
            "Z głębi szepty. Brzęk metalu o szkło.",
        ],
        "sensory_tags": ["echo", "dust", "old_paper"],
        "entity_seed_pools": {
            "mon":  ["kostny_kurator", "duch_zwiedzajacego"],
            "haz":  ["broken_glass_field"],
            "env":  ["display_case", "exhibit_plaque", "velvet_rope"],
        },
        "exit_hints": ["wschód", "magazyn", "korytarz"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 5,
        "theme_sponsor_boost": {"kult_recyklingu": 1},
    },
    {
        "template_id": "pool_magazyn_relikwii",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "museum", "contraband"],
        "name_pool": ["Magazyn B-2", "Skarbiec Niepowiązany",
                      "Archiwum Pomijane"],
        "first_enter_pool": [
            "Sala zamknięta. Regały do sufitu, na nich pudła oznaczone "
            "kodem. Klimatyzacja syczy. Na jednej półce — przedmiot, "
            "który wygląda jak zwykła rękawiczka, ale dłoń pamięta "
            "co miała w niej zrobić.",
        ],
        "look_pool": [
            "Regały. Pudła. Kilka rzeczy stoi otwartych — ktoś tu "
            "ostatnio przebierał.",
        ],
        "search_pool": [
            "W jednym z pudeł znajdujesz mały okrągły artefakt z "
            "ciepłym rdzeniem. 'NIE NOSIĆ DŁUŻEJ NIŻ 4h'.",
        ],
        "public_hint_pool": [
            "Klimatyzacja syczy. Coś szura w głębi półek.",
        ],
        "sensory_tags": ["cold", "stale_air", "rust"],
        "entity_seed_pools": {
            "mon":  ["mechaniczny_strazak"],
            "env":  ["metal_shelf", "sealed_crate", "ventilation_grate"],
            "item": ["amulet_szczescia"],
        },
        "exit_hints": ["galeria", "wentylacja"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 5,
        "theme_sponsor_boost": {"kult_recyklingu": 1},
    },
    {
        "template_id": "pool_kurator_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "museum"],
        "name_pool": ["Gabinet Kuratora", "Sala Tronowa Eksponatów",
                      "Pokój Naczelnika Zbiorów"],
        "first_enter_pool": [
            "Półokrągła sala. Pośrodku — biurko z mahonu. Za biurkiem "
            "Kurator Naczelny: szlafrok, monokl, sześć palców u prawej "
            "dłoni. Za nim drzwi z napisem 'EKSPONOWANIE ZAKOŃCZONE'.",
        ],
        "look_pool": [
            "Biurko. Kurator. Drzwi. Na ścianie wisi twoje zdjęcie "
            "z metryczką: 'EGZEMPLARZ — DO ZAKLASYFIKOWANIA'.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Cichy tykot zegara, którego nigdzie nie widać.",
        ],
        "sensory_tags": ["wood", "leather", "old_books"],
        "entity_seed_pools": {
            "mon": ["boss_kurator_naczelny"],
            "env": ["display_case", "exhibit_plaque"],
        },
        "exit_hints": ["wyjście piętra", "galeria"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"kult_recyklingu": 2},
    },

    # ── Piętro 6: BAR (sponsor: Kanał 7 Krawędź) ──────────────────────────
    {
        "template_id": "pool_glowna_sala_baru",
        "role": "social",
        "actual_type": "safehouse",
        "tags": ["social", "bar", "crawler", "rumor"],
        "safehouse_subtype": "bar",
        "name_pool": ["Bar 'Ostatni Łyk Piętra 6'",
                      "Pub 'Pod Zerwaną Antenę'",
                      "Knajpa 'Kanał Siódmy'"],
        "first_enter_pool": [
            "Drewniana podłoga lepi się od piwa wczorajszego. Bar pełny "
            "crawlerów. Wszyscy wyglądają, jakby tu siedzieli zbyt długo. "
            "Z głośnika leci skecz Kanału 7, ale nikt się nie śmieje.",
        ],
        "look_pool": [
            "Bar. Krzesła. Kilkunastu crawlerów. Kilkoro patrzy na ciebie, "
            "kilkoro nie. Drzwi do zaplecza nad wejściem mają 'CISZA — "
            "FIGHT CLUB W CISZY'.",
        ],
        "search_pool": [
            "Pod kontuarem znajdujesz kupon na darmowy drink i wycinek "
            "z papier-mâché o Showmanie z VIPu.",
        ],
        "public_hint_pool": [
            "Brzęk szkła. Cichy śmiech. Kanał 7 mruczy z głośnika.",
        ],
        "sensory_tags": ["dim", "beer", "smoke", "crowd"],
        "entity_seed_pools": {
            "npc":  [("pijany_crawler", "neutral"),
                     ("lokator_baru", "neutral")],
            "env":  ["beer_tap", "broken_chair", "tv_with_kanal_7"],
            "item": ["coffee"],
        },
        "exit_hints": ["zaplecze", "balkon VIP", "korytarz"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 6,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"kanal_7_krawedz": 1},
    },
    {
        "template_id": "pool_zaplecze_bar",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "bar", "underground"],
        "name_pool": ["Zaplecze 'Cisza'", "Sala Bez Imienia",
                      "Beton Pod Barem"],
        "first_enter_pool": [
            "Beton, gołe ściany, krew na podłodze. Krąg crawlerów wokół "
            "dwóch walczących. Bramkarz cię widzi i pokazuje palcem: "
            "'Następny.' Z głośników syk.",
        ],
        "look_pool": [
            "Beton. Krew. Krąg. Bramkarz. Wyjście do baru i zejście "
            "do piwnicy.",
        ],
        "search_pool": [
            "Pod jednym z krzeseł znajdujesz zwitek banknotów z napisem "
            "'JEŚLI NIE WYJDZIESZ — TO JEST DLA TWOICH'.",
        ],
        "public_hint_pool": [
            "Pięść w kość. Brawa bez radości.",
        ],
        "sensory_tags": ["concrete", "sweat", "blood_fresh"],
        "entity_seed_pools": {
            "mon":  ["bramkarz"],
            "env":  ["broken_chair", "blood_pool", "old_speaker"],
        },
        "exit_hints": ["bar", "piwnica"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 6,
        "theme_sponsor_boost": {"kanal_7_krawedz": 1},
    },
    {
        "template_id": "pool_balkon_vip_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "bar", "social"],
        "name_pool": ["Balkon VIP Kanału 7", "Sala Showmana",
                      "Wieczorny Specjalny"],
        "first_enter_pool": [
            "Wąskie schody w górę kończą się drzwiami z czerwonym "
            "kotarą. Za kotarą — mały bar oświetlony jak studio. "
            "W fotelu Showman: smoking, mikrofon, zęby. 'Witaj, "
            "gościu. Nasi widzowie czekali na ciebie cały odcinek.'",
        ],
        "look_pool": [
            "Studio-bar. Showman. Mikrofon. Drzwi za jego plecami "
            "to wyjście z piętra — ale Showman blokuje.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Brawy z głośnika. Showman pyta o twoje plany.",
        ],
        "sensory_tags": ["spotlight", "champagne", "applause_loop"],
        "entity_seed_pools": {
            "mon": ["boss_showman"],
            "env": ["sponsor_camera", "studio_light", "microphone"],
        },
        "exit_hints": ["wyjście piętra", "schody w dół"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 6,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"kanal_7_krawedz": 2},
    },

    # ── P29.42b — FRONTOWE OKOPY (biom WWI, F3-8) ────────────────────────
    # Sponsorzy zorganizowali wojnę bez frontu i bez wroga. Walczą tu
    # ludzie, którzy zapomnieli, kogo nienawidzą. Plakaty propagandowe
    # są dwie warstwy głębokie — pod każdą leży inna armia, każda już
    # nieaktualna. Liga Brawurowa lubi to piętro za jakość spektakli.
    {
        "template_id": "pool_linia_strzelecka",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "trenches", "ranged"],
        "name_pool": ["Linia Strzelecka", "Okop Pierwszej Linii",
                      "Stanowisko 7-B"],
        "first_enter_pool": [
            "Błoto sięga ci do kostek po dwóch krokach, a do kolan, "
            "jak postoisz. Drewno ścian okopu wgryzło się w glinę. "
            "Drabiny do góry, otwory strzelnicze, w jednym z nich "
            "ktoś wystawia lufę. Powietrze pachnie prochem i kanapką, "
            "którą ktoś zostawił na desce w ubiegłą zmianę. Plakat "
            "propagandowy: WALCZ DOBRZE — TWOJA WIDOWNIA CIĘ KOCHA. "
            "Pod plakatem ktoś dopisał ołówkiem: WIDOWNIA NIE WIE, "
            "JAK MASZ NA IMIĘ.",
            "Okop. Sześć metrów głęboki, dwa szeroki, długi w "
            "obie strony tak, że nie widzisz końca. Na drabince "
            "siedzi grenadier i je kanapkę z konserwą, jakby "
            "nie zauważył, że wojna trwa. Z głośnika ktoś czyta "
            "listę nazwisk, żadnego nie kończy.",
        ],
        "look_pool": [
            "Drewno ścian, drabinki, otwory strzelnicze. Worki z "
            "piaskiem ułożone od niechcenia. Skrzynia po amunicji "
            "stoi otwarta — pusta. Albo prawie.",
            "Błoto. Trochę krwi (cudza, twoja jeszcze nie). Drabinki, "
            "z których kapie zaschnięte coś. Dziura w deskach, którą "
            "ktoś próbował załatać kawałkiem afisza.",
        ],
        "search_pool": [
            "Pod deską znajdujesz wciśnięty pamiętnik. Pierwsza "
            "strona: „Mama. Wracam w czwartek.” Ostatnia: „Mama. "
            "Czwartek to chyba dzisiaj.”",
            "W worku z piaskiem wymacujesz coś metalowego — łuska "
            "po pocisku, jeszcze ciepła. Ktoś tu strzelał w sufit "
            "z nudów, jakieś dziesięć minut temu.",
        ],
        "public_hint_pool": [
            "Świst pocisku gdzieś z lewa. Daleko, ale nie aż tak.",
            "Ktoś nuci marsz okopowy. Bez słów, bo nie pamięta.",
            "Z głośnika trzeszczy lista nazwisk. Twojego jeszcze nie.",
        ],
        "sensory_tags": ["mud","gunpowder","wet_wood","propaganda"],
        "entity_seed_pools": {
            "mon":  ["okopowy_grenadier", "sanitariuszka_propaganda"],
            "env":  ["sponsor_camera", "loose_chain", "broken_barrel"],
            "haz":  ["exposed_wiring"],
            "item": ["maska_filtrujaca", "dirty_bandage"],
        },
        "exit_hints": ["dalej okopem", "boczny chodnik",
                       "drabinka w górę"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 3,
        "floor_max": 8,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },
    {
        "template_id": "pool_sklep_polowy",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "trenches"],
        "name_pool": ["Sklep Polowy", "Magazyn Intendentury",
                      "Składnica Drugiej Linii"],
        "first_enter_pool": [
            "Drewniana buda wkopana w błoto. Drzwi wiszą na jednym "
            "zawiasie, jakby już rezygnowały. W środku półki — "
            "puszki, opatrunki, papierosy w nielegalnej walucie. "
            "Intendent leży na pulpicie, niby śpi. Sponsor zostawił "
            "tu paczki, których nikt nie podpisał. „PROSIMY "
            "RACJONOWAĆ” — pisze tabliczka. Nikt nie racjonował.",
        ],
        "look_pool": [
            "Półki z konserwami w trzech językach. Beczka po wódce "
            "(pusta). Stos opatrunków zapakowanych w gazety. Liczy "
            "się ich więcej, niż żołnierzy w okopie obok.",
            "Pulpit intendenta. Lampa naftowa kopci. Książka "
            "rachunkowa otwarta — ostatnia pozycja: „kanapka, "
            "podpis nieczytelny, dług niespłacony do śmierci.”",
        ],
        "search_pool": [
            "Pod pulpitem znajdujesz manierkę — pełną, choć ciężką. "
            "Etykieta starannie wyklejona, nazwa armii zamazana "
            "ołówkiem. Pachnie wodą i czymś jeszcze.",
            "W kącie puszki, dwie nadgryzione, jedna z czerwonym "
            "stemplem „SPONSORSKI KONTRABAND — NIE DOTYKAĆ”. Pod "
            "puszką ktoś zostawił dziesięć kredytów i wymówkę.",
        ],
        "public_hint_pool": [
            "Skrzypienie drzwi. Lampa naftowa. Ktoś chrapie pod "
            "pulpitem, regularnie, jakby na zmianę.",
            "Cisza, którą sklep polowy ma tylko jak właśnie ktoś "
            "wszedł i jeszcze nic nie ukradł.",
        ],
        "sensory_tags": ["wax","tin","kerosene","mud"],
        "entity_seed_pools": {
            "mon":  ["lazarz_blotny"],
            "env":  ["broken_barrel", "bone_pile"],
            "item": ["snack_bar", "coffee", "duct_tape",
                     "maska_filtrujaca"],
        },
        "exit_hints": ["okopem dalej", "schody do bunkra"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "floor_max": 8,
        "theme_sponsor_boost": {"liga_brawurowa": 1,
                                 "bractwo_komornika": 1},
    },
    {
        "template_id": "pool_bunkier_dowodzenia",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "trenches"],
        "name_pool": ["Bunkier Dowodzenia",
                      "Sztab Polowy 3-A",
                      "Salon Kapelmistrza"],
        "first_enter_pool": [
            "Bunkier ma sufit niżej niż twoja głowa. Mapa na ścianie "
            "pokazuje wojnę, której już nie ma. Krzyżyki na mapie "
            "kreślone dwoma rękami naraz, jak ktoś miał za dużo "
            "kawy i za mało strategii. Pośrodku stół, na stole "
            "płyta gramofonowa kręci się bez igły. Przy stole "
            "Kapelmistrz Wojny we fraku — pałeczka w prawej dłoni, "
            "mikrofon okopowy w lewej. „Witaj. Spóźniłeś się na "
            "uwerturę. Ale na finał — w sam raz.”",
        ],
        "look_pool": [
            "Mapa wojny. Stół z gramofonem. Kapelmistrz. Drzwi "
            "z napisem „WYJŚCIE — TYLKO PO OKLASKACH”.",
            "Bunkier. Dwa wyjścia: jedno, którym wszedłeś, drugie "
            "za plecami Kapelmistrza. Ten drugi jest mniejszy. "
            "Symboliczny.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Pałeczka stuka rytmicznie o stół. Trzy uderzenia, "
            "potem cisza, potem znowu.",
            "Gramofon szumi. Bez muzyki, ale z intencją.",
        ],
        "sensory_tags": ["bunker","wax","baton","muffled"],
        "entity_seed_pools": {
            "mon": ["boss_kapelmistrz_wojny"],
            "env": ["sponsor_camera", "broken_barrel"],
        },
        "exit_hints": ["wyjście piętra", "okopem z powrotem"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "floor_max": 8,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"liga_brawurowa": 2},
    },

    # ── Boss / objective gate ───────────────────────────────────────────────
    {
        "template_id": "pool_relay_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "non_combat"],
        "name_pool": ["Stacja Przekaźnikowa A", "Serwerownia Sponsora", "Punkt Kontroli"],
        "first_enter_pool": [
            "Pomieszczenie pełne szafek serwerowych. Czerwone diody migoczą w "
            "nieprzewidywalnym rytmie. Na końcu sali widać duże drzwi z napisem "
            "'WYJŚCIE Z PIĘTRA'. Pod drzwiami stoi coś, co kiedyś było ochroniarzem.",
        ],
        "look_pool": [
            "Drzwi wyjściowe. Ochroniarz. Szafki, które brzęczą.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Buczenie serwerów. Ciężkie kroki.",
        ],
        "sensory_tags": ["bright", "loud", "electric"],
        "entity_seed_pools": {
            "mon": ["relay_warden"],
            "env": ["server_rack"],
        },
        "exit_hints": ["biuro", "wyjście piętra"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 1,            # only 1 per floor; generator forces uniqueness
        "floor_min": 2,        # P29.1: gated to floor 2 (fallback gate)
        "floor_max": 2,        # so floors 3-6 use their themed bosses
        "unique_per_floor": True,
    },

    # ── P29.18 — Vending pod (absurd loot machine) ──────────────────────────
    {
        "template_id": "pool_vending_pod",
        "role": "filler",
        "actual_type": "loot",
        "tags": ["loot", "vending", "sponsor"],
        "name_pool": ["Alkowa Automatów", "Pomieszczenie z Wendingami",
                      "Korytarz Reklamowy"],
        "first_enter_pool": [
            "Wąski korytarz oświetlony reklamami. Trzy automaty z "
            "logiem różnych sponsorów migają na wpół-pracy. Spróbuj "
            "którymkolwiek — `użyj automat`.",
        ],
        "look_pool": ["Trzy automaty, dwa neony, jedna kałuża chłodziwa."],
        "search_pool": [
            "Pod automatem znajdujesz monetę z napisem „PIJ”.",
        ],
        "public_hint_pool": ["Reklamy lecą głośniej niż normalnie."],
        "sensory_tags": ["neon", "chłodziwo", "reklama"],
        "entity_seed_pools": {
            "env":  ["vending_machine", "vending_machine",
                     "sponsor_screen"],
            "item": ["coffee"],
        },
        "exit_hints": ["korytarz", "dalej"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 3,
        "floor_min": 2,
        "floor_max": 14,
    },

    # ── P29.11 — DEEP FLOORS 7-18 ───────────────────────────────────────────
    # Floors 7-9: UNDERGROUND (zaplecze, kanały)
    {
        "template_id": "pool_kanaly_korytarz",
        "role": "filler",
        "actual_type": "social",
        "tags": ["underground","wet","corridor","floor7","floor8","floor9"],
        "name_pool": ["Kanał Główny", "Tunel Serwisowy", "Ciemny Odpływ"],
        "first_enter_pool": [
            "Cuchnący korytarz pod miastem. Woda po kostki. Na ścianach "
            "graffiti starszych sezonów: imiona, daty, ostrzeżenia.",
        ],
        "look_pool": ["Ściek. Echo. Coś się porusza w dali."],
        "search_pool": [
            "Znajdujesz monetę z napisem „SR-2027 — pamiętaj o sponsorach”.",
        ],
        "public_hint_pool": ["Plusk w głębi. Powolny."],
        "sensory_tags": ["wet","mold","echo","cold"],
        "entity_seed_pools": {
            "env":  ["pipe_cluster","exposed_wiring","trash_bin"],
            "item": ["dirty_bandage"],
        },
        "exit_hints": ["dalej kanałem", "włazem do góry", "boczna komora"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 7,
        "floor_max": 9,
    },
    {
        "template_id": "pool_kanaly_walka",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["underground","combat","floor7","floor8","floor9"],
        "name_pool": ["Komora Serwisowa", "Zalany Pokój Pomp",
                      "Stare Zwężenie"],
        "first_enter_pool": [
            "Mała sala z pompami. Wokół zbiera się grupka — mieszkańcy "
            "kanałów. Patrzą na ciebie jak na dostawę.",
        ],
        "look_pool": ["Stare pompy. Krzywe ślady stóp w mule."],
        "search_pool": [],
        "public_hint_pool": ["Mokre kroki za plecami."],
        "sensory_tags": ["wet","metal","threat"],
        "entity_seed_pools": {
            "mon": ["kanal_widmo","mokry_kolega"],
            "env": ["pipe_cluster","exposed_wiring"],
        },
        "exit_hints": ["kanałem", "klatka schodowa", "kratka w ścianie"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 7,
        "floor_max": 9,
    },
    {
        "template_id": "pool_kanaly_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous","boss","objective","underground","floor9"],
        "name_pool": ["Tron Burmistrza", "Komnata Pod Ratuszem",
                      "Centralny Zawór"],
        "first_enter_pool": [
            "Wielka okrągła komora pod miastem. Pośrodku tron z rur. "
            "Na tronie postać w hełmie z latarką. „Witam w moim "
            "miasteczku. Nie zostajesz długo, prawda?”",
        ],
        "look_pool": [
            "Tron z rur. Korona z taśmy klejącej. Wyjście za nim.",
        ],
        "search_pool": [],
        "public_hint_pool": ["Echo: TY-TY-TY-TY."],
        "sensory_tags": ["wet","echo","authority"],
        "entity_seed_pools": {
            "mon": ["boss_burmistrz_kanalow"],
            "env": ["pipe_cluster","trash_bin"],
        },
        "exit_hints": ["wyjście piętra", "wąski tunel"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 9,
        "floor_max": 9,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"recykling_obywatelski": 2},
    },

    # Floors 10-12: FUNGAL_BLOOM
    {
        "template_id": "pool_zarodniki_korytarz",
        "role": "filler",
        "actual_type": "social",
        "tags": ["fungal","biome","floor10","floor11","floor12"],
        "name_pool": ["Zarośnięty Korytarz", "Komnata Pleśni",
                      "Sala Wegetacji"],
        "first_enter_pool": [
            "Ściany zarosła grzybnia. W powietrzu unosi się słodki "
            "zapach. Coś tu kiedyś się zepsuło — i nikt nie sprzątnął.",
        ],
        "look_pool": ["Grzybnia. Para. Zapach syropu."],
        "search_pool": [
            "Pod warstwą pleśni — stary identyfikator pracownika NovaChem.",
        ],
        "public_hint_pool": ["Powolne pulsowanie ścian."],
        "sensory_tags": ["fungal","sweet","damp","biotic"],
        "entity_seed_pools": {
            "env":  ["biohazard_bin","disinfectant_shelf"],
            "item": ["dirty_bandage"],
        },
        "exit_hints": ["dalej w głąb", "boczna szczelina", "klatka schodowa"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 10,
        "floor_max": 12,
        "theme_sponsor_boost": {"nova_chem": 1},
    },
    {
        "template_id": "pool_zarodniki_walka",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["fungal","combat","poison","floor10","floor11","floor12"],
        "name_pool": ["Sala Kwitnienia", "Komnata Zarodników",
                      "Hala Eksperymentów"],
        "first_enter_pool": [
            "Pomieszczenie wypełnione gnijącą roślinnością. Dwa kwiaty "
            "wielkości człowieka odwracają się w twoją stronę.",
        ],
        "look_pool": ["Gnijące kwiaty. Zarodniki w powietrzu."],
        "search_pool": [],
        "public_hint_pool": ["Słodkawy zapach. Cisza."],
        "sensory_tags": ["fungal","poison","damp"],
        "entity_seed_pools": {
            "mon": ["kwiat_padliny","zarodnikowiec"],
            "env": ["biohazard_bin","exposed_wiring"],
        },
        "exit_hints": ["dalej", "boczna komora"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 10,
        "floor_max": 12,
        "theme_sponsor_boost": {"nova_chem": 1},
    },
    {
        "template_id": "pool_zarodniki_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous","boss","objective","fungal","floor12"],
        "name_pool": ["Komnata Matki", "Inkubator", "Sala 12-B"],
        "first_enter_pool": [
            "Kopuła z mięsa o trzymetrowej średnicy pulsuje pośrodku "
            "sali. Z każdym uderzeniem opadają zarodniki. Słychać "
            "dziecięcy śpiew. NovaChem nie odbiera telefonu.",
        ],
        "look_pool": ["Pulsująca kopuła. Mglista posadzka. Wyjście za nią."],
        "search_pool": [],
        "public_hint_pool": ["Śpiew. Coraz głośniejszy."],
        "sensory_tags": ["fungal","bio_horror","lullaby"],
        "entity_seed_pools": {
            "mon": ["boss_matka_zarodników"],
            "env": ["biohazard_bin"],
        },
        "exit_hints": ["wyjście piętra"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 12,
        "floor_max": 12,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"nova_chem": 2},
    },

    # Floors 13-15: MACHINE_CHURCH
    {
        "template_id": "pool_kaplica_korytarz",
        "role": "filler",
        "actual_type": "social",
        "tags": ["church","cult","corporate","floor13","floor14","floor15"],
        "name_pool": ["Nawa Sponsorska", "Krużganek Memetyczny",
                      "Korytarz Kaplicy 7.0"],
        "first_enter_pool": [
            "Korytarz w stylu kaplicy: witraże z logo Ministerstwa, "
            "ławki, w głębi ołtarz z serwerem. Modlitwa leci z głośników.",
        ],
        "look_pool": ["Witraż. Ołtarz-serwer. Echo recytacji."],
        "search_pool": [
            "Pod ławką znajdujesz tablet z otwartym aktem darowizny.",
        ],
        "public_hint_pool": ["Monotonna recytacja: „kup, daj, słuchaj.”"],
        "sensory_tags": ["incense","data_hum","reverent"],
        "entity_seed_pools": {
            "env":  ["sponsor_screen","server_rack","sponsor_camera"],
            "item": ["coffee"],
        },
        "exit_hints": ["nawa boczna", "zakrystia", "klatka schodowa"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 13,
        "floor_max": 15,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_kaplica_walka",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["church","combat","memetic","floor13","floor14","floor15"],
        "name_pool": ["Konfesjonał", "Sala Posiedzenia Diakonów",
                      "Galeria Sponsorów"],
        "first_enter_pool": [
            "Pomieszczenie z rzędem konfesjonałów. Każdy ma wyświetlacz "
            "z formularzem. Z trzech wychodzą postacie w szatach.",
        ],
        "look_pool": ["Konfesjonały. Wyświetlacze. Cisza."],
        "search_pool": [],
        "public_hint_pool": ["Stukot tabletów."],
        "sensory_tags": ["data_hum","cold_light","incense"],
        "entity_seed_pools": {
            "mon": ["kantor_pamieci","diakon_korpo"],
            "env": ["sponsor_screen","server_rack"],
        },
        "exit_hints": ["nawa", "ołtarz", "zakrystia"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 13,
        "floor_max": 15,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_kaplica_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous","boss","objective","church","floor15"],
        "name_pool": ["Ołtarz Główny", "Sanktuarium Pamięci",
                      "Tron Proboszcza"],
        "first_enter_pool": [
            "Ogromna nawa z wysokim sklepieniem. Pośrodku ołtarz, "
            "na nim serwer. Za ołtarzem Proboszcz Korpo w szatach "
            "Ministerstwa. „Cieszę się, że dotarłeś. Mamy do omówienia "
            "twój pakiet sponsorski.”",
        ],
        "look_pool": ["Ołtarz. Serwer. Proboszcz. Wyjście za jego plecami."],
        "search_pool": [],
        "public_hint_pool": ["Cisza. Świece elektryczne."],
        "sensory_tags": ["data_hum","incense","spotlight"],
        "entity_seed_pools": {
            "mon": ["boss_proboszcz_korpo"],
            "env": ["server_rack","sponsor_camera","sponsor_screen"],
        },
        "exit_hints": ["wyjście piętra", "zakrystia"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 15,
        "floor_max": 15,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 2},
    },

    # Floors 16-18: HELLFLOOR (Syndykat sanctum)
    {
        "template_id": "pool_syndykat_korytarz",
        "role": "filler",
        "actual_type": "social",
        "tags": ["syndykat","executive","corridor",
                 "floor16","floor17","floor18"],
        "name_pool": ["Recepcja Syndykatu", "Korytarz Prezydialny",
                      "Sala Trofeów"],
        "first_enter_pool": [
            "Marmurowy korytarz z czerwonym dywanem. Na ścianach "
            "fotografie poprzednich Crawlerów-zwycięzców. Wszyscy się "
            "uśmiechają. Każdy ma już inny zawód.",
        ],
        "look_pool": ["Marmur. Fotografie. Cisza grobowa."],
        "search_pool": [
            "Pod ramą zdjęcia znajdujesz cudzy kontrakt. Czerwony stempel: "
            "„ZAWIESZONY 6 PIĘTRO.”",
        ],
        "public_hint_pool": ["Klimatyzacja szumi spokojnie."],
        "sensory_tags": ["luxury","stillness","threat_quiet"],
        "entity_seed_pools": {
            "env":  ["sponsor_camera","sponsor_screen","mirror"],
        },
        "exit_hints": ["dalej korytarzem", "windą w górę",
                       "drzwi z numerem 18-B"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 6,
        "floor_min": 16,
        "floor_max": 18,
        "theme_sponsor_boost": {"sport_safety": 1,
                                "kanal_7_krawedz": 1},
    },
    {
        "template_id": "pool_syndykat_walka",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["syndykat","combat","executive",
                 "floor16","floor17","floor18"],
        "name_pool": ["Sala Konferencyjna 18-A",
                      "Pokój Spotkań Zarządu",
                      "Gabinet Wiceprezesa"],
        "first_enter_pool": [
            "Sala konferencyjna z owalnym stołem. Po obu stronach stołu "
            "siedzą postacie w garniturach. Wszyscy wstają synchronicznie. "
            "Jeden z nich przedstawia się: „windykacja końcowa, "
            "trzeci cykl.”",
        ],
        "look_pool": ["Stół. Krzesła. Postacie w garniturach."],
        "search_pool": [],
        "public_hint_pool": ["Cisza biurowa. Klimatyzacja. Krzesła odsuwane."],
        "sensory_tags": ["luxury","threat","silent"],
        "entity_seed_pools": {
            "mon": ["windykator_ostateczny","anti_host_lite"],
            "env": ["sponsor_camera","sponsor_screen"],
        },
        "exit_hints": ["korytarz prezydialny", "winda służbowa"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 16,
        "floor_max": 18,
        "theme_sponsor_boost": {"czarny_rynek": 1},
    },
    {
        "template_id": "pool_prezes_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous","boss","final","objective","syndykat","floor18"],
        "name_pool": ["Gabinet Prezesa", "Pokój 18-PR",
                      "Antresola Korporacyjna"],
        "first_enter_pool": [
            "Olbrzymi gabinet z panoramiczną szybą wychodzącą na "
            "studio Kanału 7. Za biurkiem siedzi Prezes Syndykatu — "
            "spokojny, uśmiechnięty, z herbatą. „Proszę usiąść. "
            "Mamy do omówienia twoje przyszłe role.”",
        ],
        "look_pool": [
            "Biurko. Pięć Emmy. Prezes. Drzwi „WOLNOŚĆ?” na bocznej ścianie.",
        ],
        "search_pool": [],
        "public_hint_pool": ["Cisza absolutna. Tylko herbata stygnie."],
        "sensory_tags": ["luxury","finale","camera"],
        "entity_seed_pools": {
            "mon": ["boss_prezes_syndykatu"],
            "env": ["sponsor_camera","sponsor_screen","server_rack"],
        },
        "exit_hints": ["WOLNOŚĆ?", "winda awaryjna"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 18,
        "floor_max": 18,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"kanal_7_krawedz": 3},
    },
]


# Buckets by role for quick lookup
ROOM_POOL_BY_ROLE: dict = {}
for _t in ROOM_POOL:
    ROOM_POOL_BY_ROLE.setdefault(_t["role"], []).append(_t)


def templates_with_tag(tag: str):
    return [t for t in ROOM_POOL if tag in t.get("tags", [])]


def templates_for_role(role: str):
    return list(ROOM_POOL_BY_ROLE.get(role, []))
