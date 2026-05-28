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

    # ── P29.46 — Boss F1. Bez tego F1 nie miał killowalnego bossa
    # i exits_unlocked nigdy się nie ustawiał — gracz utknął na
    # pierwszym piętrze. Bug znaleziony w playthrough.
    {
        "template_id": "pool_intake_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "intake"],
        "name_pool": ["Punkt Aklimatyzacji", "Recepcja Lochu 1A",
                      "Bramka Wejściowa"],
        "first_enter_pool": [
            "Pomieszczenie z pojedynczą lampą i biurkiem. Za biurkiem "
            "siedzi Strażnik Aklimatyzacji — pierwszy mundur, jaki "
            "tu zobaczysz. Mówi spokojnie: „Witaj w programie. "
            "Twoja autoryzacja zejścia kosztuje dwie minuty życia. "
            "Czyli moją, jeśli pójdzie pechowo.”",
            "Mała sala recepcyjna. Plakat sponsorski: TWOJA KARIERA "
            "ZACZYNA SIĘ TUTAJ. Pod plakatem — Strażnik z paralizatorem "
            "i bardzo dobrym dressingiem.",
        ],
        "look_pool": [
            "Biurko z formularzami. Strażnik. Drzwi za jego plecami "
            "to wyjście z piętra. Nie ma klucza — jest tylko on.",
            "Lampa nad biurkiem mruga. Strażnik nie. Plakat: ZEJŚCIE "
            "DZIESIĘĆ KROKÓW DALEJ.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Strażnik klika długopisem rytmicznie. Bardzo długo.",
            "Z głośnika nad biurkiem cicha muzyka kantorska.",
        ],
        "sensory_tags": ["sterile","fluorescent","sponsor_ads"],
        "entity_seed_pools": {
            "mon": ["intake_warden"],
            "env": ["sponsor_camera","sponsor_screen"],
        },
        "exit_hints": ["wyjście piętra", "schody w dół"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 1,
        "floor_max": 1,
        "unique_per_floor": True,
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

    # ═══════════════════════════════════════════════════════════════════
    # P29.42b — Pokoje per biom (głębsza zawartość)
    # Per Q-fin (2026-05-28, user): „głębsze tylko istniejące" + intake.
    # Boost: zoo / museum / bar / trenches +7 każdy. Intake +4.
    # Tone: Dinniman — twardy, sponsorski sneer, fizyczne detale.
    # Polish-only (Rule 1 z 11 Claudiego).
    # ═══════════════════════════════════════════════════════════════════

    # ── ZOO +7 ────────────────────────────────────────────────────────
    {
        "template_id": "pool_woliera_skrzydlatych",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "zoo", "animal", "vertical"],
        "name_pool": ["Woliera Skrzydlatych", "Sektor Ptasi",
                      "Klatka Sufitowa"],
        "first_enter_pool": [
            "Siatka pod sufitem zwisa miejscami przerwana. Ekspozycja "
            "ptasia była zorganizowana w trzech piętrach żerdzi — dwa "
            "piętra leżą rozbite na podłodze. Pióra dryfują w ciepłym "
            "powietrzu. Nad tobą coś ostrzy dziób.",
        ],
        "look_pool": [
            "Żerdzie. Karmnik wbity w ścianę gwoździami od dołu, jakby "
            "ktoś próbował go zerwać siłą. Tabliczka „NIE STRASZYĆ — "
            "PTAKI POD PRESJĄ SPONSORA”.",
        ],
        "search_pool": [
            "W gnieździe znajdujesz nadgryzioną kartę pamięci kamery "
            "sponsorskiej i kilka monet, które wyglądają jak żetony.",
        ],
        "public_hint_pool": [
            "Skrzydła. Coś krzyczy z góry. Cienie szybkie i nierówne.",
        ],
        "sensory_tags": ["feathers", "draft", "high_pitched_sound"],
        "entity_seed_pools": {
            "mon":  ["bekajacy_paw"],
            "env":  ["broken_cage", "loose_chain", "sponsor_camera"],
            "item": ["snack_bar"],
        },
        "exit_hints": ["wschód", "zachód", "korytarz boczny"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_terrarium_gadow",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "zoo", "animal", "humid"],
        "name_pool": ["Terrarium Gadów", "Sekcja Pełzających",
                      "Mokra Klatka"],
        "first_enter_pool": [
            "Wilgoć od progu. Lampy podgrzewające bzyczą — większość "
            "popsuta, jedna jeszcze świeci. Szkło terrariów popękane, "
            "kilka rozbitych zupełnie. Pod nogami coś się przesuwa.",
        ],
        "look_pool": [
            "Akwaria osuszone. Mech wyschnięty. W rogu wąż liczy "
            "własne odcinki, jakby się nudził. Tabliczka „KARM RAZ "
            "DZIENNIE — PALEC NIE WYSTARCZY”.",
        ],
        "search_pool": [
            "Pod fałszywą skałą torebka z proszkiem, na której widnieje "
            "tylko skrót „N-7”. Plus dwa lekko ciepłe jajka.",
        ],
        "public_hint_pool": [
            "Wilgoć. Bzyczenie lampy. Sucha łuska po podłodze.",
        ],
        "sensory_tags": ["humid", "warm", "animal_smell"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["broken_cage", "feeding_trough"],
            "haz":  ["broken_glass"],
            "item": ["dirty_bandage"],
        },
        "exit_hints": ["północ", "korytarz"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 3,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_kwarantanna_zoo",
        "role": "danger",
        "actual_type": "lore",
        "tags": ["zoo", "lore", "medical"],
        "name_pool": ["Kwarantanna Sektor C", "Izolatka Eksperymentu",
                      "Boks Obserwacyjny"],
        "first_enter_pool": [
            "Plastikowa kurtyna przy wejściu, dwie warstwy. Za nią "
            "biel — biel dawno zżarta przez plamy. Kuwety, kroplówki "
            "do dawno wyschnięte. Dokumentacja przybita do ściany, "
            "rogi spalone od papierosów.",
        ],
        "look_pool": [
            "Stół opieki. Pas mocujący wciąż zapięty. Ekran "
            "elektrokardiogramu pokazuje płaską linię od lat.",
        ],
        "search_pool": [
            "Karta pacjenta: „Egzemplarz 11 — szczepiony dwa razy. "
            "Reakcja: nadmierne mówienie. Dyspozycja: cisza.”",
        ],
        "public_hint_pool": [
            "Zapach środka odkażającego. Po wszystkich tych latach.",
        ],
        "sensory_tags": ["sterile", "old_paper", "stale"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "torn_notebook"],
            "item": ["bandage", "stimpak"],
        },
        "exit_hints": ["korytarz", "drzwi przesuwne"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_weterynarka_zoo",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "zoo", "medical"],
        "name_pool": ["Gabinet Weterynarza", "Punkt Pierwszej Pomocy "
                      "Zwierzęcej", "Apteczka Główna"],
        "first_enter_pool": [
            "Lekarska szafka rozwalona, lekarstwa walają się po "
            "podłodze. Mikroskop przewrócony, soczewka rozbita. Stół "
            "operacyjny jeszcze ze sznurkiem do mocowania ogona.",
        ],
        "look_pool": [
            "Mnóstwo butelek, większość pęknięta. Strzykawki w pudełku "
            "pewnie z kompletnym zestawem.",
        ],
        "search_pool": [
            "Wsuwana szuflada okazuje się pełna — bandaże, dwa "
            "stimpaki, fiolka czegoś bez etykiety. Plus 30 kredytów "
            "w dolnej szufladzie.",
        ],
        "public_hint_pool": [
            "Lekarska szafka. Zapach środka odkażającego.",
        ],
        "sensory_tags": ["sterile", "broken_glass", "chemical"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "broken_glass"],
            "item": ["bandage", "stimpak", "dirty_bandage"],
        },
        "exit_hints": ["korytarz", "zaplecze"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_pokoj_trenera_zoo",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "zoo", "rumor", "npc"],
        "name_pool": ["Pokój Trenera", "Boks Personelu", "Pracownia "
                      "Tresera"],
        "first_enter_pool": [
            "Małe biuro. Krzesło obrotowe, blat poplamiony kawą. "
            "Kalendarz z poprzedniego sezonu, podpis: „PRZEŻYŁ”. "
            "W rogu klatka transportowa. Pusta.",
        ],
        "look_pool": [
            "Na ścianie zdjęcia: treser z białym tygrysem. Treser "
            "z lampartem. Treser z pustą klatką. Treser sam.",
        ],
        "search_pool": [
            "Notatnik tresera: „Sponsor mówi, że publiczność lubi "
            "ryk. Ryk wymaga karmienia. Karmienie wymaga budżetu. "
            "Budżet wymaga publiczności. Pętla.”",
        ],
        "public_hint_pool": [
            "Cisza biurowa. Brzęczenie kalkulatora.",
        ],
        "sensory_tags": ["coffee", "paper", "stale"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "npc":  [("paranoid_mapper", "neutral")],
            "item": ["snack_bar"],
        },
        "exit_hints": ["korytarz", "drzwi obrotowe"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_kanal_sprzatania_zoo",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "zoo", "hidden"],
        "name_pool": ["Kanał Sprzątania", "Spust Sektorowy",
                      "Tunel Serwisowy"],
        "first_enter_pool": [
            "Wąski, niski. Po ścianach plamy z dawnych wycieków. "
            "Tunel którym wozili żywe i nieżywe. Sponsor pewnie "
            "nigdy o tym nie pisał na ekranie.",
        ],
        "look_pool": [
            "Hak na suficie. Zwinięta lina. Studnia w podłodze "
            "z metalową kratką.",
        ],
        "search_pool": [
            "Pod kratką stara, ale szczelnie zamknięta puszka. W "
            "środku trzy stare karty dostępu i 50 kredytów w "
            "papierowych banknotach.",
        ],
        "public_hint_pool": [
            "Echo kapania.",
        ],
        "sensory_tags": ["damp", "rot", "metal"],
        "entity_seed_pools": {
            "env":  ["studzienka", "loose_chain"],
            "item": ["credits_pile", "snack_bar"],
        },
        "exit_hints": ["góra", "drabina"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_loza_sponsora_zoo",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "zoo", "elite", "vip"],
        "name_pool": ["Loża Sponsora", "Balkon VIP", "Sektor Premium"],
        "first_enter_pool": [
            "Loża nad areną. Pluszowe fotele, drewniana balustrada, "
            "lornetka na trójnogu. Ślad krwi na dywanie prowadzi pod "
            "fotel. Ktoś tu kiedyś oglądał show z bliska.",
        ],
        "look_pool": [
            "Pełny widok na arenę z góry. Kieliszki na stoliku — "
            "trzy puste, jeden napełniony i nietknięty.",
        ],
        "search_pool": [
            "Pod fotelem koperta z napisem „PREMIA — NIE OTWIERAĆ "
            "W TRAKCIE PROGRAMU”. Plus 80 kredytów.",
        ],
        "public_hint_pool": [
            "Ciężki dywan tłumi kroki. Czuć perfumy i drogi alkohol.",
        ],
        "sensory_tags": ["luxury", "blood_dried", "wood_polish"],
        "entity_seed_pools": {
            "mon":  ["klatkowy_kot"],
            "env":  ["sponsor_screen", "furniture_wood"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["schody w dół", "kotara"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
        "theme_sponsor_boost": {"czarny_rynek_plus": 2},
    },

    # ── MUSEUM +7 ─────────────────────────────────────────────────────
    {
        "template_id": "pool_galeria_luster",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "museum", "psychic"],
        "name_pool": ["Galeria Luster", "Sala Refleksji",
                      "Korytarz Odbić"],
        "first_enter_pool": [
            "Lustra od podłogi do sufitu, po obu stronach, w "
            "trzech rzędach. Twoje odbicie idzie z tobą — nie do "
            "końca w tym samym tempie. Jedno z luster pęknięte "
            "w spiralę. Reflektor nad lustrami świeci sponsorską "
            "purpurą.",
        ],
        "look_pool": [
            "Każde lustro odbija ciebie. Trzecie z prawej odbija "
            "ciebie sprzed minuty. Czwarte z lewej — ciebie za "
            "minutę. Nie patrz za długo.",
        ],
        "search_pool": [
            "Pod pęknięciem znajdujesz wgnieconą wizytówkę i "
            "kapsułę z czymś, co pulsuje delikatnie. Wizytówka: "
            "„Konserwator Iluzji, prośba o ciszę.”",
        ],
        "public_hint_pool": [
            "Pulsujące światło. Pięć ech kroków zamiast jednego.",
        ],
        "sensory_tags": ["bright", "echo", "stale"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["sponsor_screen", "broken_glass"],
            "item": ["snack_bar"],
        },
        "exit_hints": ["wschód", "korytarz boczny"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 5,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_pracownia_konserwacji",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "museum", "tools"],
        "name_pool": ["Pracownia Konserwacji", "Warsztat Restauracji",
                      "Boks Kuratorski"],
        "first_enter_pool": [
            "Długie stoły z lampami warsztatowymi. Skalpele, pędzelki, "
            "kleje. Po prawej szafa z chemikaliami — szyba popękana, "
            "fiolki wciąż na półkach. Eksponat na stole — wciąż w "
            "trakcie restauracji. Konserwator gdzie indziej, jego "
            "pęseta jeszcze ciepła.",
        ],
        "look_pool": [
            "Półprodukt rzeźby. Połowa pomalowana, połowa surowa. "
            "Z boku zaschła kawa w styropianie i komputer wyłączony "
            "w pośpiechu.",
        ],
        "search_pool": [
            "Szuflada warsztatu pełna — pęseta, kleje, drobne narzędzia. "
            "Plus dwa stimpaki w apteczce i 40 kredytów w portfelu.",
        ],
        "public_hint_pool": [
            "Chemia i klej. Drobne ostre dźwięki — coś gdzieś jeszcze "
            "pracuje na pół etatu.",
        ],
        "sensory_tags": ["chemical", "metal", "stale"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "torn_notebook", "broken_glass"],
            "item": ["bandage", "stimpak", "credits_pile"],
        },
        "exit_hints": ["korytarz", "schody w górę"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 5,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_biuro_kuratora_male",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "museum", "rumor", "npc"],
        "name_pool": ["Biuro Pomniejszego Kuratora",
                      "Stanowisko Adiunkta", "Pokój Doktorancki"],
        "first_enter_pool": [
            "Biurko mahonowe, ale niżej. Półki uginają się od katalogów "
            "z czarno-białych zdjęć. Adiunkt podnosi wzrok znad maszyny "
            "do pisania — nie elektrycznej. „Pan kuratorem?” pyta.",
        ],
        "look_pool": [
            "Sterty papierów posortowane chronologicznie. Notatka "
            "przyklejona do lampy: „SEZONÓW BYŁO DUŻO. PUBLICZNOŚCI "
            "MNIEJ.”",
        ],
        "search_pool": [
            "W szufladzie z napisem „STARE PIŚMA” paczka monet — "
            "20 kredytów, plus pożółknięta karta dostępu z napisem "
            "„MAGAZYN OS”.",
        ],
        "public_hint_pool": [
            "Stuk maszyny do pisania. Zapach kawy i naftaliny.",
        ],
        "sensory_tags": ["paper", "stale", "coffee"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "npc":  [("paranoid_mapper", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["korytarz", "drzwi"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 5,
    },
    {
        "template_id": "pool_archiwum_piwniczne",
        "role": "danger",
        "actual_type": "lore",
        "tags": ["museum", "lore", "underground"],
        "name_pool": ["Archiwum Piwniczne", "Magazyn OS",
                      "Sektor Wycofanych"],
        "first_enter_pool": [
            "Schodzisz w dół. Półki regałowe ciągną się w głąb, każda "
            "z opisem dekady. Lampa nad nimi mruga raz na pięć sekund. "
            "Na końcu rzędu coś usiadło na kartonie i czeka.",
        ],
        "look_pool": [
            "Pudła z opisami sezonów. „1923 — UNIEWAŻNIONY”, „1957 — "
            "PRZEZNACZONY DO USUNIĘCIA”, „2018 — NIE OTWIERAĆ”.",
        ],
        "search_pool": [
            "W pudle „2018” wpisany na maszynie raport: „Sponsor "
            "kupił dane wcześniej niż się stało. Ekipa odmówiła "
            "dostawy. Ekipa przeszła na drugą stronę.”",
        ],
        "public_hint_pool": [
            "Zimno. Sucho. Kurz nie osiada, tylko zawisa.",
        ],
        "sensory_tags": ["cold", "dry", "paper"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "broken_cage"],
            "item": ["snack_bar"],
        },
        "exit_hints": ["schody", "głębsze regały"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 5,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 2},
    },
    {
        "template_id": "pool_eksponat_zamkniety",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "museum", "fragile"],
        "name_pool": ["Eksponat Zamknięty", "Sala Specjalna",
                      "Boks z Tabliczką"],
        "first_enter_pool": [
            "Sala mała, zamknięta liną. Tabliczka: „CZASOWO "
            "NIEDOSTĘPNE — KONSERWACJA W TOKU”. Lina przerwana. "
            "Eksponat — drewniana figura w mundurze — patrzy "
            "wprost na ciebie. Ekran sponsorski w rogu nic nie "
            "pokazuje. Pierwszy raz w tej grze.",
        ],
        "look_pool": [
            "Figura. Drewno spękane, mundur podarty. Ktoś dorysował "
            "jej usta markerem. Usta się nie zgadzają z resztą "
            "twarzy.",
        ],
        "search_pool": [
            "Pod liną zwitek banknotów — 35 kredytów. Plus mała "
            "kapsuła z napisem „NIE TYKAĆ JEŚLI MOŻLIWE”.",
        ],
        "public_hint_pool": [
            "Ekran sponsorski wyłączony. Niespotykane.",
        ],
        "sensory_tags": ["stale", "wood", "ozone"],
        "entity_seed_pools": {
            "mon":  ["klatkowy_kot"],
            "env":  ["sponsor_screen", "furniture_wood"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["lina obrotowa", "korytarz"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 5,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_sala_darczyncow",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "museum", "elite", "vip"],
        "name_pool": ["Sala Darczyńców", "Galeria Patronów",
                      "Lista Honorowa"],
        "first_enter_pool": [
            "Ściana cała w plakietkach z nazwiskami. Pod nią marmurowy "
            "blok. Na bloku ktoś siedzi po turecku, z lornetką "
            "skierowaną na drzwi. Nie ruszył się, gdy wszedłeś. "
            "Ruszy się teraz.",
        ],
        "look_pool": [
            "Plakietki. Setki. Każdy darczyńca z roku, kwotą i krótkim "
            "podziękowaniem. Czterech ostatnich — bez kwoty, tylko "
            "podziękowanie: „ZA WSZYSTKO”.",
        ],
        "search_pool": [
            "W szczelinie marmuru tekturka: „WPŁACA SIĘ NIE PIENIĄDZEM. "
            "WPŁACA SIĘ CZASEM. CZAS LICZY KURATOR.”",
        ],
        "public_hint_pool": [
            "Marmur. Cisza muzealna. Skrzypnięcie skóry buta.",
        ],
        "sensory_tags": ["stone", "stale", "luxury"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["sponsor_screen", "furniture_wood"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["wyjście honorowe", "korytarz"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 5,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 2},
    },
    {
        "template_id": "pool_biuro_rzeczy_znalezionych",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "museum", "hidden", "loot"],
        "name_pool": ["Biuro Rzeczy Znalezionych", "Skrytka "
                      "Zaginionych", "Kąt Zapomnianych"],
        "first_enter_pool": [
            "Drzwi z nieczytelnym napisem. W środku półka, na "
            "półce karton z opisem „ZNALEZIONE W TYM ROKU — NIE "
            "ZGŁASZANE”. Zawiera dużo. Zaskakująco dużo.",
        ],
        "look_pool": [
            "Karton pełen. Klucze, portfele, ekwipunek. Każda rzecz "
            "z metką: na której gracz zginął, w którym pokoju.",
        ],
        "search_pool": [
            "Znajdujesz: stimpak, bandaż, 60 kredytów, oraz "
            "klucz uniwersalny do magazynu OS.",
        ],
        "public_hint_pool": [
            "Cisza biurowa. Zapach starego papieru.",
        ],
        "sensory_tags": ["stale", "paper", "metal"],
        "entity_seed_pools": {
            "env":  ["torn_notebook"],
            "item": ["bandage", "stimpak", "credits_pile"],
        },
        "exit_hints": ["korytarz", "drzwi"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 5,
    },

    # ── BAR +7 ────────────────────────────────────────────────────────
    {
        "template_id": "pool_scena_karaoke",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "bar", "loud"],
        "name_pool": ["Scena Karaoke", "Mała Estrada",
                      "Sektor Mikrofonu"],
        "first_enter_pool": [
            "Małe podium, zasłona z frędzlami, mikrofon na stojaku. "
            "Ekran wyświetla tekst — sponsorska piosenka o piwie. "
            "Ktoś trzyma mikrofon, ale nie śpiewa. Patrzy. Mikrofon "
            "skrzeczy.",
        ],
        "look_pool": [
            "Lista przebojów na ścianie. Pierwsze miejsce: ten "
            "sam tytuł od miesięcy. Pod nim drobnym drukiem: "
            "„SPONSOR REKOMENDUJE”.",
        ],
        "search_pool": [
            "Za zasłoną stary płaszcz z portfelem. W portfelu "
            "20 kredytów i karta lojalnościowa „PIWO ZA KAŻDĄ "
            "SZÓSTĄ ŚMIERĆ”.",
        ],
        "public_hint_pool": [
            "Sprzężenie mikrofonu. Tekst piosenki na pętli.",
        ],
        "sensory_tags": ["loud", "stale", "smoke"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["sponsor_screen", "furniture_wood"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["sala główna", "zaplecze"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 6,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },
    {
        "template_id": "pool_piwnica_baru",
        "role": "danger",
        "actual_type": "lore",
        "tags": ["bar", "lore", "underground", "contraband"],
        "name_pool": ["Piwnica pod Sceną", "Skład Płynów",
                      "Tajny Magazyn"],
        "first_enter_pool": [
            "Schodzisz. Beczki, skrzynki, plamy. Zapach fermentacji "
            "i czegoś bardziej osobistego. Ktoś tu spał — sienik "
            "wciąż ciepły. Dwie skrzynki bez etykiet.",
        ],
        "look_pool": [
            "Inwentarz przybity do beczki: „LEGALNE 30%, RESZTA — "
            "INACZEJ”. Pod spodem podpis: „ZAWSZE ZAPLAĆ ZA NIENIE-"
            "LEGALNE PIERWSZE”.",
        ],
        "search_pool": [
            "W skrzynce bez etykiety: trzy fiolki z napisem „N-7”, "
            "kilka monet (15 kredytów), i karteczka adresowa do "
            "Czarnego Rynku.",
        ],
        "public_hint_pool": [
            "Wilgoć z dołu. Zapach fermentacji.",
        ],
        "sensory_tags": ["damp", "fermented", "smoke"],
        "entity_seed_pools": {
            "env":  ["broken_barrel", "torn_notebook"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["schody w górę"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 3,
        "floor_min": 6,
        "theme_sponsor_boost": {"czarny_rynek_plus": 2},
    },
    {
        "template_id": "pool_kuchnia_barowa",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "bar", "food"],
        "name_pool": ["Kuchnia Barowa", "Smażalnia", "Boks "
                      "Wydawkowy"],
        "first_enter_pool": [
            "Tłuszcz na podłodze, frytkownica gaśnie sykiem. Talerze "
            "ułożone w stos, na wierzchu nóż wbity w drewno. Z piekarnika "
            "wyciekło coś czarnego. Kucharz w środku swojego kąta — "
            "ostry. Nie nóż. Wzrok.",
        ],
        "look_pool": [
            "Lodówka otwarta, w środku pakiety mięs z różnych "
            "źródeł. Tabliczka „WSZYSTKO ŚWIEŻE — ŹRÓDŁA "
            "ZWERYFIKOWANE NIECO MNIEJ”.",
        ],
        "search_pool": [
            "Pod fartuchem szefa: paczka soli, butelka z napisem "
            "„CHRZAN STARY”, 25 kredytów w napiwkach.",
        ],
        "public_hint_pool": [
            "Tłuszcz w powietrzu. Chrupie pod butami.",
        ],
        "sensory_tags": ["greasy", "smoke", "metal"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "broken_glass"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["sala główna", "wyjście kuchenne"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 6,
    },
    {
        "template_id": "pool_zaplecze_baru",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "bar", "rumor", "npc"],
        "name_pool": ["Zaplecze Baru", "Pokój Personelu",
                      "Boks Kelnerski"],
        "first_enter_pool": [
            "Mały pokój z sofą rozłożoną na połowę. Termos z kawą, "
            "popielniczka pełna. Kelner siedzi po turecku na sofie, "
            "liczy napiwki. Liczy też ciebie.",
        ],
        "look_pool": [
            "Plotek przyklejony do lustra: „PIWO Z BIBLIOTEKI MA "
            "WIĘCEJ INFORMACJI NIŻ JEJ KATALOG”.",
        ],
        "search_pool": [
            "W koszyku z brudnymi koszulkami portfel ze zdjęciem "
            "i 30 kredytów. Plus karteczka z numerem do speluny "
            "F8.",
        ],
        "public_hint_pool": [
            "Cisza. Brzęczy lodówka z napojami.",
        ],
        "sensory_tags": ["smoke", "stale", "coffee"],
        "entity_seed_pools": {
            "env":  ["furniture_wood", "torn_notebook"],
            "npc":  [("loot_goblin_crawler", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["sala główna", "wyjście służbowe"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 6,
    },
    {
        "template_id": "pool_zaulek_baru",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "bar", "hidden", "alley"],
        "name_pool": ["Boczny Zaułek", "Brama Tylna", "Cichy Kąt"],
        "first_enter_pool": [
            "Wąsko. Wysokie ściany, niebo skądś. Ktoś tu pali i "
            "się nie martwi widownią. Pojemnik na śmieci pełny, "
            "drugi z napisem „TYLKO PUSTE BUTELKI”. Trzeci "
            "z napisem „TYLKO PEŁNE KONTRAKTY”.",
        ],
        "look_pool": [
            "Niedopałek po niedopałku. Pod nogami ktoś wykreślił "
            "kredą sześciokąt z napisem: „NIE ZADAWAJ PYTAŃ”.",
        ],
        "search_pool": [
            "W pojemniku „TYLKO PEŁNE KONTRAKTY” koperta. "
            "W kopercie: 50 kredytów i karta dostępu do speluny.",
        ],
        "public_hint_pool": [
            "Echo. Daleki śmiech.",
        ],
        "sensory_tags": ["cold", "smoke", "urine"],
        "entity_seed_pools": {
            "env":  ["broken_barrel", "loose_chain"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["powrót do baru", "uliczka"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 6,
    },
    {
        "template_id": "pool_toaleta_baru",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "bar", "hidden"],
        "name_pool": ["Toaleta Barowa", "Łazienka — Stan Krytyczny",
                      "Boks WC"],
        "first_enter_pool": [
            "Płytki popękane. Lustro nad umywalką stłuczone w "
            "pajęczynę. Z trzech kabin dwie zamknięte, jedna "
            "uchylona — w niej tylko ślad ucieczki przez okno. "
            "Krany kapią różnie.",
        ],
        "look_pool": [
            "Graffiti pokrywa każdą wolną powierzchnię. „SPONSOR "
            "NIE WIDZI”, „TU WSZYSCY UCIEKAJĄ”, „F8 = TO PRAWDA”.",
        ],
        "search_pool": [
            "Za spłuczką taśma, na taśmie zawinięta torebka. "
            "W torebce 40 kredytów, dwie pigułki bez opisu, i "
            "klucz do piwnicy.",
        ],
        "public_hint_pool": [
            "Kapie. Wodociąg jęczy. Daleki śmiech zza ściany.",
        ],
        "sensory_tags": ["damp", "urine", "smoke"],
        "entity_seed_pools": {
            "env":  ["broken_glass", "studzienka"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["powrót", "okno"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 6,
    },
    {
        "template_id": "pool_dziedziniec_baru",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "bar", "elite"],
        "name_pool": ["Tylny Dziedziniec", "Brama Wewnętrzna",
                      "Patio Bramne"],
        "first_enter_pool": [
            "Bruk, śmieci, pojemniki. Pod ścianą dwie postacie — "
            "jedna stoi, jedna leży. Stojąca trzyma w ręku "
            "wyłączony telefon. Leżąca trzyma w ręku coś, czego "
            "nie chciałbyś być częścią.",
        ],
        "look_pool": [
            "Lampka nad bramą. Mig-mig. W kącie skrzynki "
            "z butelkami, większość pęknięta. Ktoś trenował na "
            "nich rzut.",
        ],
        "search_pool": [
            "Przy leżącej postaci portfel — 55 kredytów. "
            "Plus bilet sezonowy do Czarnego Rynku.",
        ],
        "public_hint_pool": [
            "Echo. Sponsorska reklama z głośnika ulicznego.",
        ],
        "sensory_tags": ["cold", "blood_fresh", "smoke"],
        "entity_seed_pools": {
            "mon":  ["klatkowy_kot"],
            "env":  ["broken_barrel", "loose_chain"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["powrót do baru", "brama"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 6,
        "theme_sponsor_boost": {"czarny_rynek_plus": 1},
    },

    # ── TRENCHES +7 ───────────────────────────────────────────────────
    {
        "template_id": "pool_posterunek_obserwacyjny",
        "role": "danger",
        "actual_type": "lore",
        "tags": ["trenches", "lore", "observation"],
        "name_pool": ["Posterunek Obserwacyjny", "Stanowisko "
                      "Nasłuchu", "Wieżyczka Forward"],
        "first_enter_pool": [
            "Wąski rów z drabiną do góry. Na górze stanowisko "
            "z workami piasku. Lornetka na statywie skierowana "
            "w pole. W radio cisza, ale dioda mruga.",
        ],
        "look_pool": [
            "Notatnik obserwatora. Wpisy co godzinę: „SPOKOJ”, "
            "„SPOKOJ”, „SPOKOJ”, „RUCH”, „NIE PISAĆ DALEJ”.",
        ],
        "search_pool": [
            "W skrzynce racje na trzy dni i radio polowe. Plus "
            "tabliczka z mapy: „SEKTOR 7 — UNIKAĆ KIEDY MOŻLIWE”.",
        ],
        "public_hint_pool": [
            "Wiatr przez worki piasku. Trzask radia.",
        ],
        "sensory_tags": ["cold", "wind", "metal"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "loose_chain"],
            "item": ["snack_bar", "bandage"],
        },
        "exit_hints": ["drabina w dół", "rów boczny"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },
    {
        "template_id": "pool_punkt_medyczny_okop",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "trenches", "medical"],
        "name_pool": ["Punkt Medyczny", "Sanitarka Polowa",
                      "Stanowisko Medyczne"],
        "first_enter_pool": [
            "Worki piasku, brezent rozpięty nad ranionym. Ranionego "
            "już nie ma. Medycyna polowa — szafka z lekami otwarta, "
            "noszem przykryto coś, co stara się nie być widziane.",
        ],
        "look_pool": [
            "Tabliczka: „TRIAGE — KOLOR ZIELONY: WRACA. KOLOR "
            "CZERWONY: WIDZÓW WIĘCEJ. KOLOR CZARNY: PROGRAM "
            "ZMIENIONY”.",
        ],
        "search_pool": [
            "W skrzynce sanitarnej: dwa bandaże, trzy stimpaki, "
            "fiolka morfiny, 30 kredytów w fartuchu sanitariusza.",
        ],
        "public_hint_pool": [
            "Zapach krwi i środka odkażającego. Krople z kroplówki.",
        ],
        "sensory_tags": ["blood_fresh", "sterile", "cold"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "broken_cage"],
            "item": ["bandage", "stimpak", "credits_pile"],
        },
        "exit_hints": ["rów główny", "tunel"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },
    {
        "template_id": "pool_bunkier_oficerski",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "trenches", "rumor", "npc"],
        "name_pool": ["Bunkier Oficerski", "Stanowisko Dowódcze",
                      "Boks Sztabowy"],
        "first_enter_pool": [
            "Schody w dół, drzwi metalowe. Wnętrze z mapami "
            "przybitymi do ściany. Oficer przy biurku, kreda "
            "w dłoni, słuchawka radia trzymana ramieniem. „A pan "
            "tu po co?” pyta, nie odwracając głowy.",
        ],
        "look_pool": [
            "Mapy z czerwonymi i niebieskimi liniami. Niebieskie "
            "prowadzą w nikąd. Czerwone otaczają coś z napisem "
            "„CEL SPONSORA”.",
        ],
        "search_pool": [
            "Na biurku planszetka z rozkazami: „NIE NACIERAĆ "
            "PRZED PRZERWĄ REKLAMOWĄ”. Plus 35 kredytów w "
            "rozkazówce „BUDŻET POLOWY”.",
        ],
        "public_hint_pool": [
            "Kreda po tablicy. Trzask radia.",
        ],
        "sensory_tags": ["metal", "smoke", "stale"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "npc":  [("paranoid_mapper", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["schody w górę", "tunel komunikacyjny"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },
    {
        "template_id": "pool_skladnica_amunicji_okop",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "trenches", "explosive"],
        "name_pool": ["Składnica Amunicji", "Sektor Granatów",
                      "Boks Detonacyjny"],
        "first_enter_pool": [
            "Niska ziemianka. Skrzynki z amunicją ułożone w stosy, "
            "tabliczki nieczytelne od pleśni. Ktoś tu zostawił "
            "papierosa, papieros wciąż się tli. Ktoś inny tu "
            "siedzi w głębi i się nie odzywa.",
        ],
        "look_pool": [
            "Skrzynki. Numerowane. Każda z napisem „OSTROŻNIE — "
            "ZA TRZASKI ODPOWIADA TY”.",
        ],
        "search_pool": [
            "Skrzynka 7-B: dwa granaty dymne i 45 kredytów w "
            "kopercie z pieczęcią Ligi Brawurowej.",
        ],
        "public_hint_pool": [
            "Zapach prochu. Ostrożnie.",
        ],
        "sensory_tags": ["smoke", "metal", "cold"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["broken_barrel", "loose_chain"],
            "haz":  ["broken_glass"],
            "item": ["credits_pile", "snack_bar"],
        },
        "exit_hints": ["rów", "schody w górę"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },
    {
        "template_id": "pool_gniazdo_snajperskie_okop",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "trenches", "elite",
                 "ranged"],
        "name_pool": ["Gniazdo Snajperskie", "Stanowisko "
                      "Strzeleckie", "Boks Strzelca"],
        "first_enter_pool": [
            "Mała szczelina w worek piasku. Karabin na statywie, "
            "luneta zaparowana. Strzelec w środku swojej pozycji "
            "— skupiony, nie patrzy na ciebie. Patrzy w "
            "konkretne miejsce w polu. Czeka.",
        ],
        "look_pool": [
            "Listy celów na kartonie. Dwadzieścia pozycji, "
            "siedemnaście wykreślone. Nazwisko strzelca u dołu.",
        ],
        "search_pool": [
            "Pod karabinem skrzynka z amunicją premium, plus "
            "60 kredytów premii za każdy wykreślony cel.",
        ],
        "public_hint_pool": [
            "Cicho. Tylko oddech. Wiatr przez szczelinę.",
        ],
        "sensory_tags": ["cold", "wind", "metal"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["sponsor_screen", "loose_chain"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["rów", "schody w dół"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 2},
    },
    {
        "template_id": "pool_kanal_odplywowy_okop",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "trenches", "hidden", "damp"],
        "name_pool": ["Kanał Odpływowy", "Rura Spustowa",
                      "Tunel Wodny"],
        "first_enter_pool": [
            "Rura odpływowa, dość szeroka żeby przejść kucem. "
            "Woda do kostek. Echo niesie wszystko, łącznie z "
            "twoim oddechem. Pod łokciem coś metalowego.",
        ],
        "look_pool": [
            "Rura przerdzewiała. Pęknięcia, woda kapie z sufitu. "
            "Na ścianie ktoś wyrył: „STĄD MOŻNA WYJŚĆ — JEŚLI WIESZ”.",
        ],
        "search_pool": [
            "W szczelinie ściany metalowa puszka. W środku "
            "70 kredytów, kompas wojskowy, i mapa sektora "
            "z zaznaczonymi „PRZEJŚCIAMI”.",
        ],
        "public_hint_pool": [
            "Echo. Kropla. Powolne.",
        ],
        "sensory_tags": ["damp", "rot", "cold"],
        "entity_seed_pools": {
            "env":  ["studzienka", "loose_chain"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["powierzchnia", "głębiej w rurę"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_placowka_zaopatrzenia",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "trenches"],
        "name_pool": ["Placówka Zaopatrzenia", "Stanowisko Logistyczne",
                      "Boks Magazynowy"],
        "first_enter_pool": [
            "Skrzynki, beczki, worki. Logistyk z planszetką liczy "
            "zapasy. Liczy w gorączce — sponsor wymaga, brakuje. "
            "Ktoś w kącie waży opóźnienia.",
        ],
        "look_pool": [
            "Tablica z manifestem dostaw. Ostatnia dostawa: "
            "„SPÓŹNIONA — POWODY: NIE PISAĆ”.",
        ],
        "search_pool": [
            "Pod kontuarem koperta z napisem „PREMIA ZA SZYBKOŚĆ”: "
            "40 kredytów. Plus paczka racji.",
        ],
        "public_hint_pool": [
            "Stuk planszetki. Echo skrzypiących butów.",
        ],
        "sensory_tags": ["dust", "metal", "stale"],
        "entity_seed_pools": {
            "mon":  ["klatkowy_kot"],
            "env":  ["broken_barrel", "furniture_wood"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["rów", "tunel zaopatrzeniowy"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"liga_brawurowa": 1},
    },

    # ── INTAKE +4 ─────────────────────────────────────────────────────
    {
        "template_id": "pool_intake_szatnia",
        "role": "safe",
        "actual_type": "safehouse",
        "tags": ["safe", "safehouse", "intake"],
        "safehouse_subtype": "lounge",
        "name_pool": ["Szatnia Aklimatyzacyjna", "Boks "
                      "Przygotowawczy", "Pokój Pierwszego Dnia"],
        "first_enter_pool": [
            "Szafki z numerami. Niektóre otwarte, niektóre "
            "puste, jedna wyrwana z zawiasów. Ławka mokrym od "
            "potu. Plakat: „WITAJ W SEZONIE — NIE PRZYJDZIESZ "
            "TU PONOWNIE”.",
        ],
        "look_pool": [
            "Szafka 7 wciąż czeka na właściciela. Szafka 11 z "
            "tabliczką „NIEDOSTĘPNA — PROGRAM ZMIENIONY”.",
        ],
        "search_pool": [
            "W otwartej szafce zostawione: bandaż, drobne "
            "monety (10 kredytów), notes z jednym wpisem: "
            "„NIE UFAJ APARATOM”.",
        ],
        "public_hint_pool": [
            "Echo metalowych szafek. Świetlówka mruga.",
        ],
        "sensory_tags": ["sterile", "stale", "metal"],
        "entity_seed_pools": {
            "env":  ["furniture_wood", "torn_notebook"],
            "item": ["bandage", "credits_pile"],
        },
        "exit_hints": ["korytarz", "drzwi obrotowe"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
        "floor_max": 2,
    },
    {
        "template_id": "pool_intake_sala_powitalna",
        "role": "danger",
        "actual_type": "lore",
        "tags": ["intake", "lore", "orientation"],
        "name_pool": ["Sala Powitalna", "Audytorium "
                      "Wstępne", "Boks Orientacyjny"],
        "first_enter_pool": [
            "Sala z rzędami plastikowych krzeseł. Większość pusta. "
            "Ekran sponsorski wyświetla pętlę „WITAJ W LOCHU — "
            "WIDZÓW MAMY MILIONY, A TY MASZ SZCZĘŚCIE”. Mikrofon "
            "wyłączony.",
        ],
        "look_pool": [
            "Krzesła. Numerki na oparciach. Na środkowym ktoś "
            "wyrył pieczołowicie: „NIE WSTAWAJ KIEDY WOŁAJĄ — "
            "WOŁAJĄ TYLKO RAZ”.",
        ],
        "search_pool": [
            "Pod krzesłem 17 znaleziony pomięty pamflet: "
            "„JAK PRZEŻYĆ PIERWSZE PIĘTRO — WSKAZÓWKI OD "
            "WIDZÓW BYŁYCH ZAWODNIKÓW”.",
        ],
        "public_hint_pool": [
            "Echo nagrania na pętli. Krzesła nie skrzypią.",
        ],
        "sensory_tags": ["bright", "stale", "echo"],
        "entity_seed_pools": {
            "env":  ["sponsor_screen", "torn_notebook"],
            "item": ["snack_bar"],
        },
        "exit_hints": ["korytarz", "drzwi główne"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
        "floor_max": 2,
    },
    {
        "template_id": "pool_intake_aleja_automatow",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "intake"],
        "name_pool": ["Aleja Automatów", "Korytarz Sprzedażowy",
                      "Sektor Automatów"],
        "first_enter_pool": [
            "Długi korytarz, automaty po obu stronach. Większość "
            "działa, większość pusta. Ktoś próbował wybić szybę "
            "automatu nr 4. Próbował zębami. Próbował niedawno.",
        ],
        "look_pool": [
            "Automaty: kawa, batony, ostrza ratunkowe, świece "
            "dymne. Ceny w kredytach. Wszystkie zawyżone.",
        ],
        "search_pool": [
            "W zwrocie reszty automatu 7 zapomniana paczka: "
            "15 kredytów i jeden snack.",
        ],
        "public_hint_pool": [
            "Brzęczenie automatu. Coś chodzi po pleksi szybą.",
        ],
        "sensory_tags": ["bright", "stale", "metal"],
        "entity_seed_pools": {
            "mon":  ["mutant_szczur"],
            "env":  ["vending_machine", "sponsor_screen"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["korytarz", "skręt"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 1,
        "floor_max": 2,
    },
    {
        "template_id": "pool_intake_kabina_sanitarna",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "intake", "hidden"],
        "name_pool": ["Kabina Sanitarna", "Boks Higieniczny",
                      "Punkt Mycia"],
        "first_enter_pool": [
            "Jedna z tych kabin, w których nikt nigdy nie chce "
            "zostać dłużej. Lustro zachlapane, kran kapie, "
            "papier wisi smutno. W kącie ktoś przykleił karteczkę: "
            "„WĄCHAJ — TO TWOJA WSKAZÓWKA”.",
        ],
        "look_pool": [
            "Wszystko z plastiku. Wszystko popsute. Spłuczka "
            "naprawiona drutem.",
        ],
        "search_pool": [
            "Za spłuczką ukryta saszetka. W środku 25 kredytów, "
            "fiolka antybiotyków, mała mapka sektora wstępnego.",
        ],
        "public_hint_pool": [
            "Kapie. Wymownie.",
        ],
        "sensory_tags": ["damp", "urine", "sterile"],
        "entity_seed_pools": {
            "env":  ["medical_drawer", "broken_glass"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["korytarz", "drzwi obrotowe"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 3,
        "floor_min": 1,
        "floor_max": 2,
    },

    # ═══════════════════════════════════════════════════════════════════
    # P29.42c — 4 biomy Tier-1: pokoje (5 per biome × 4 = 20)
    # fabryka_pary / stacja_orbital / kuznia_polorkow / biblioteka_miejska
    # ═══════════════════════════════════════════════════════════════════

    # ── FABRYKA PARY — Sterling-9 ─────────────────────────────────────
    {
        "template_id": "pool_hala_kotlow",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "steampunk_factory", "fire"],
        "name_pool": ["Hala Kotłów", "Sekcja Termiczna",
                      "Boks Palenisk"],
        "first_enter_pool": [
            "Kotły wielkości autobusu. Trzy działają, jeden cieknie. "
            "Manometry w czerwonej strefie, ale alarm dawno "
            "wyłączono — sponsor zaoszczędził na obsłudze. Powietrze "
            "drży od ciepła. Twoje buty miękną.",
        ],
        "look_pool": [
            "Każdy kocioł z plakietką producenta — wszystkie inne. "
            "Łopaty oparte o ścianę. Łopaty się zużywają. Łopatarze "
            "się zużywają szybciej.",
        ],
        "search_pool": [
            "Pod łopatą zapomniana torba narzędziowa — klucz "
            "francuski, pęczek śrub, 25 kredytów premii za "
            "przepracowaną zmianę.",
        ],
        "public_hint_pool": [
            "Sapanie ognia. Stuk metalowych łopat o beton.",
        ],
        "sensory_tags": ["hot", "smoke", "metal"],
        "entity_seed_pools": {
            "mon":  ["konserwator_kotla", "smarownik_pasow"],
            "env":  ["sponsor_screen", "broken_barrel"],
            "haz":  ["broken_glass"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["północ", "podest", "drabina"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"kult_recyklingu": 1},
    },
    {
        "template_id": "pool_warsztat_smarowniczy",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "steampunk_factory", "tools"],
        "name_pool": ["Warsztat Smarowniczy", "Boks Olejarski",
                      "Magazyn Smarów"],
        "first_enter_pool": [
            "Beczki olejów po obu stronach. Część otwarta, część "
            "wyciekła. Stół z narzędziami pełen — klucze, śruby, "
            "noże do uszczelek. Pod stołem coś syczy, ale to nie "
            "może być ważne. Nigdy nie jest.",
        ],
        "look_pool": [
            "Inwentarz olejów wisi krzywo. Smar typ 7, smar typ 11, "
            "smar typ „NIE PYTAĆ”. Wszystkie etykiety przybrudzone.",
        ],
        "search_pool": [
            "Pod stołem skrzynka z dobrym sprzętem: dwa klucze, "
            "rolka taśmy, fiolka smaru wysokotemperaturowego, "
            "45 kredytów w kopercie z napisem „PRZESCIANE”.",
        ],
        "public_hint_pool": [
            "Zapach oleju przemysłowego. Kapie gdzieś.",
        ],
        "sensory_tags": ["greasy", "metal", "smoke"],
        "entity_seed_pools": {
            "env":  ["broken_barrel", "medical_drawer"],
            "item": ["credits_pile", "snack_bar"],
        },
        "exit_hints": ["hala główna", "magazyn"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"kult_recyklingu": 1},
    },
    {
        "template_id": "pool_dyspozytornia_pary",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "steampunk_factory", "rumor", "npc"],
        "name_pool": ["Dyspozytornia", "Pokój Zmiany",
                      "Sterownia Główna"],
        "first_enter_pool": [
            "Konsola pełna pokręteł. Na ścianie tablica zmian — "
            "krzyżyki przy nieobecnych. Dyspozytor w fotelu, oczy "
            "podkrążone, kubek kawy zimny od godzin. „A pan w "
            "której zmianie?” pyta.",
        ],
        "look_pool": [
            "Lista alarmów: 47 aktywnych. „IGNORUJ DO PRZERWY "
            "REKLAMOWEJ” na pierwszej linii.",
        ],
        "search_pool": [
            "W szufladzie dyspozytora rzut oka na rozkład: "
            "30 kredytów w portfelu, klucz do magazynu olejów, "
            "notes z kontaktami.",
        ],
        "public_hint_pool": [
            "Stuk pokręteł. Sapanie ekspresu.",
        ],
        "sensory_tags": ["coffee", "stale", "metal"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "npc":  [("paranoid_mapper", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["hala", "korytarz służbowy"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_tunel_parowy",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "steampunk_factory", "hidden"],
        "name_pool": ["Tunel Parowy", "Spust Termiczny",
                      "Kanał Serwisowy"],
        "first_enter_pool": [
            "Wąsko. Wilgotno mimo ciepła. Para się tu skrapla "
            "i kapie. Idziesz schylony. Na ścianie ktoś wydrapał: "
            "„TYM PRZESZEDŁ FELIKS — ALE FELIKS BYŁ MNIEJSZY”.",
        ],
        "look_pool": [
            "Rury z parą po obu stronach. Jedna pęknięta — para "
            "wychodzi pionowo. Omijasz.",
        ],
        "search_pool": [
            "W szczelinie ściany torba narzędziowa: śruby, "
            "klucz nasadowy, 35 kredytów schowanych przez "
            "kogoś, kto już tu nie wraca.",
        ],
        "public_hint_pool": [
            "Syk pary. Bardziej blisko niż chciałbyś.",
        ],
        "sensory_tags": ["hot", "damp", "metal"],
        "entity_seed_pools": {
            "env":  ["loose_chain", "studzienka"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["powrót", "głębiej"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_fabryka_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "steampunk_factory"],
        "name_pool": ["Sala Główna Palenisk", "Centrum Termiczne",
                      "Sektor Główny Sterling"],
        "first_enter_pool": [
            "Olbrzymia hala. Centralne palenisko bije żarem. "
            "Z trzech kominów wychodzi dym w trzech różnych "
            "kolorach. Pośrodku — Palacz Sterling. Łopata wbita "
            "w beton. Czeka, aż wejdziesz w jego cień.",
        ],
        "look_pool": [
            "Palenisko. Trzy kominy. Z drugiej strony drzwi z "
            "tabliczką „WYJŚCIE PIĘTRA — TYLKO PRZEZ PALACZA”.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Huk ognia. Sapanie powietrza wciąganego do paleniska.",
        ],
        "sensory_tags": ["hot", "smoke", "metal"],
        "entity_seed_pools": {
            "mon":  ["boss_palacz_sterling"],
            "env":  ["sponsor_camera", "broken_barrel"],
        },
        "exit_hints": ["wyjście piętra", "wschód"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"kult_recyklingu": 2},
    },

    # ── STACJA ORBITAL-7 ──────────────────────────────────────────────
    {
        "template_id": "pool_modul_mieszkalny_orbital",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "orbital", "sterile"],
        "name_pool": ["Moduł Mieszkalny A", "Kapsuła Turystyczna",
                      "Boks Pasażerski"],
        "first_enter_pool": [
            "Krzesła zatrzaśnięte w fotelach, pasy zapięte. Pasy "
            "trzymają nadal. Trzymają na sucho. Ekran kabinowy "
            "wyświetla pętlę: „WITAMY NA POKŁADZIE — DZIĘKUJEMY "
            "ZA WYBÓR ORBITAL-7”.",
        ],
        "look_pool": [
            "Numery foteli na suficie. Po jednym foteliku "
            "papierowy lunch — szpitalnie spłaszczony.",
        ],
        "search_pool": [
            "W schowku nad fotelem 14 zapomniana saszetka "
            "z 30 kredytami i kartą dostępu „GŁÓWNY DOK”.",
        ],
        "public_hint_pool": [
            "Cisza ciśnieniowa. Mig-mig ekranu nawigacyjnego.",
        ],
        "sensory_tags": ["sterile", "cold", "metal"],
        "entity_seed_pools": {
            "mon":  ["pasazer_zaginiony", "technik_sluzy"],
            "env":  ["sponsor_screen", "furniture_wood"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["śluza", "korytarz"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"novachem_biotech": 1},
    },
    {
        "template_id": "pool_magazyn_dokowy",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "orbital", "storage"],
        "name_pool": ["Magazyn Dokowy", "Skład Cargo",
                      "Boks Logistyczny"],
        "first_enter_pool": [
            "Kontenery cargo do sufitu. Większość pieczętowana, "
            "kilka rozprutych. Wózek widłowy unieruchomiony na "
            "środku — operator zapomniał zaciągnąć hamulec, ale "
            "nie zapomniał uciec.",
        ],
        "look_pool": [
            "Listy przewozowe na ścianie. Część z pieczęcią "
            "„ZATWIERDZONE”, część z dopiskiem „STREFA SPONSORA”.",
        ],
        "search_pool": [
            "W rozprutym kontenerze: dwa bandaże, stimpak, "
            "puszka racji, 50 kredytów w kopercie cargo.",
        ],
        "public_hint_pool": [
            "Echo metalu. Lampka awaryjna mruga.",
        ],
        "sensory_tags": ["sterile", "metal", "cold"],
        "entity_seed_pools": {
            "env":  ["broken_barrel", "medical_drawer"],
            "item": ["bandage", "stimpak", "credits_pile"],
        },
        "exit_hints": ["śluza", "korytarz cargo"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_centrum_dowodzenia_orbital",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "orbital", "rumor", "npc"],
        "name_pool": ["Centrum Dowodzenia", "Mostek Stacji",
                      "Sterownia Główna"],
        "first_enter_pool": [
            "Półokrągłe stanowiska z ekranami. Większość wyłączona. "
            "Oficer dyżurny przy jednym z aktywnych — kawa, ciasto, "
            "logo sponsora w lewym górnym rogu. „Pasażer?” pyta, "
            "nie odwracając głowy.",
        ],
        "look_pool": [
            "Mapa stacji z modułami w pięciu kolorach. Trzy "
            "moduły wygaszone. Tabliczka: „NIE OTWIERAĆ MODUŁU C "
            "BEZ ZGODY SPONSORA”.",
        ],
        "search_pool": [
            "W szufladzie oficera: portfel z 40 kredytami, "
            "uniwersalna karta dostępu, notatnik z listami "
            "kontaktów planetarnych.",
        ],
        "public_hint_pool": [
            "Stuk klawiatur. Cichy alarm w tle, ignorowany.",
        ],
        "sensory_tags": ["sterile", "coffee", "ozone"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "sponsor_screen"],
            "npc":  [("paranoid_mapper", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["śluza", "korytarz służbowy"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_szyb_serwisowy_orbital",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "orbital", "hidden", "vertical"],
        "name_pool": ["Szyb Serwisowy", "Tunel Techniczny",
                      "Wąski Przejazd"],
        "first_enter_pool": [
            "Pionowy szyb z drabinką po jednej ścianie. Powietrze "
            "tu jest własne — taśma z napisem „STREFA AWARYJNA”. "
            "Każdy poziom ma kratę. Większość kraty już ktoś "
            "ominął.",
        ],
        "look_pool": [
            "Drabinka. Kable. Etykiety pokoi za kratą. „MODUŁ C — "
            "ZATWIERDZONE PRZEZ SPONSORA” jest jedyną w czerwieni.",
        ],
        "search_pool": [
            "Na podeście schowek z saszetką: 55 kredytów, "
            "stimpak, karta techniczna do modułu C.",
        ],
        "public_hint_pool": [
            "Brzęczy went. Drabinka się ugina.",
        ],
        "sensory_tags": ["metal", "cold", "ozone"],
        "entity_seed_pools": {
            "env":  ["loose_chain", "broken_barrel"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["góra", "dół"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_orbital_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "orbital"],
        "name_pool": ["Główny Dok Stacji", "Sektor Próżni",
                      "Sala Komandora"],
        "first_enter_pool": [
            "Okrągłe pomieszczenie ze szklaną kopułą. Za szybą — "
            "próżnia, dalej planeta. Komandor Próżni stoi pośrodku, "
            "trzyma dziennik stacji. Skafander bez przyłbicy. "
            "Nie potrzebuje powietrza.",
        ],
        "look_pool": [
            "Kopuła ze szkła ciśnieniowego. Pulpit z drugiej strony, "
            "drzwi z tabliczką „WYJŚCIE PIĘTRA — PRZECHODZIĆ TYLKO "
            "PO ZATWIERDZENIU DOWÓDCY”.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Cisza ciśnieniowa. Tylko twoje serce.",
        ],
        "sensory_tags": ["sterile", "cold", "ozone"],
        "entity_seed_pools": {
            "mon":  ["boss_komandor_proznii"],
            "env":  ["sponsor_camera", "sponsor_screen"],
        },
        "exit_hints": ["wyjście piętra", "śluza ewakuacyjna"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"novachem_biotech": 2},
    },

    # ── KUŹNIA PÓŁORKÓW ───────────────────────────────────────────────
    {
        "template_id": "pool_hala_kowadel",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "forge", "fire", "loud"],
        "name_pool": ["Hala Kowadeł", "Sekcja Trzech Młotów",
                      "Boks Bicia"],
        "first_enter_pool": [
            "Trzy kowadła w rzędzie, każde w pracy. Półork przy "
            "pierwszym uderzył metal, otarł pot, popatrzył na "
            "ciebie. Drugi nawet nie podniósł wzroku. Trzeci "
            "ciężej oddycha — ten skończy się pierwszy.",
        ],
        "look_pool": [
            "Kowadła. Stojaki z młotami różnej wagi. Beczki z "
            "wodą do hartowania — woda parująca, każda inna "
            "barwa.",
        ],
        "search_pool": [
            "Pod kowadłem trzecim: opaska cechowa, klucz do "
            "magazynu metali, 35 kredytów w skórzanym mieszku.",
        ],
        "public_hint_pool": [
            "Stuk młotów w rytm reklamy. Para z hartowania.",
        ],
        "sensory_tags": ["hot", "metal", "smoke"],
        "entity_seed_pools": {
            "mon":  ["podkowiarz_polork", "mlociarz_cechowy"],
            "env":  ["broken_barrel", "loose_chain"],
            "haz":  ["broken_glass"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["zaplecze", "kuźnia główna"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"bractwo_komornika": 1},
    },
    {
        "template_id": "pool_skladnica_metali",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "forge", "materials"],
        "name_pool": ["Składnica Metali", "Magazyn Surowca",
                      "Skład Półwyrobów"],
        "first_enter_pool": [
            "Pręty żelazne ułożone w piramidy. Sztaby brązu, "
            "skrzynki z nitami. Każda skrzynka z tabliczką cechu. "
            "Stary półork śpi w rogu, na worku z piaskiem. "
            "Brzuch unosi się rytmicznie.",
        ],
        "look_pool": [
            "Inwentarz metali wisi pieczołowicie. Brąz, żelazo, "
            "stal nieoznaczona. Plus jedna skrzynka z napisem "
            "„NIE OTWIERAĆ — PRÓBA SPONSORSKA”.",
        ],
        "search_pool": [
            "W skrzynce „PRÓBA SPONSORSKA”: dwa pręty rzadkiego "
            "metalu, klucz cechowy, 50 kredytów premii za "
            "milczenie.",
        ],
        "public_hint_pool": [
            "Chrapanie. Stuk wagi.",
        ],
        "sensory_tags": ["metal", "dust", "warm"],
        "entity_seed_pools": {
            "env":  ["broken_barrel", "loose_chain"],
            "item": ["credits_pile", "snack_bar"],
        },
        "exit_hints": ["kuźnia", "zaplecze"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"bractwo_komornika": 1},
    },
    {
        "template_id": "pool_szynkwas_cechowy",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "forge", "rumor", "npc"],
        "name_pool": ["Szynkwas Cechowy", "Karczma Półorków",
                      "Sala Wieczornicy"],
        "first_enter_pool": [
            "Stoły długie, ławy z surowego drewna. Półorki piją "
            "tu po szychcie — albo dwie szychty po sobie, czasem "
            "trzy. Karczmarz wyciera kufel rękawem. Nieświeży "
            "rękaw.",
        ],
        "look_pool": [
            "Tablica z plotkami: „SPONSOR PŁACI ZA NITY — "
            "ALE NIE ZA WĄTROBY”. Pod tablicą popielniczka pełna.",
        ],
        "search_pool": [
            "Pod ławą portfel: 30 kredytów, kostka z cechowymi "
            "znakami, papierek z adresem do magazynu rzeczy "
            "niepotrzebnych.",
        ],
        "public_hint_pool": [
            "Brzęk kufli. Półorkowy chichot.",
        ],
        "sensory_tags": ["smoke", "metal", "warm"],
        "entity_seed_pools": {
            "env":  ["furniture_wood", "broken_barrel"],
            "npc":  [("loot_goblin_crawler", "neutral")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["kuźnia", "wyjście tylne"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_studnia_hartownicza",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "forge", "hidden", "underground"],
        "name_pool": ["Studnia Hartownicza", "Loch Kowala",
                      "Studzienka Cechowa"],
        "first_enter_pool": [
            "Schodzisz po wykutych w skale stopniach. Studnia "
            "z lodowatą wodą. Tu hartują największe ostrza. "
            "Na dnie coś leży — być może klinga, być może "
            "kowal, który nie wyszedł.",
        ],
        "look_pool": [
            "Łańcuch zwisa z sufitu. Hak. Woda się świeci na "
            "zielono w jednym miejscu.",
        ],
        "search_pool": [
            "Na półce wykutej w ścianie schowek: 60 kredytów, "
            "stimpak, klinga rzadkiej stali w pochwie.",
        ],
        "public_hint_pool": [
            "Cisza. Tylko kapanie wody na metal.",
        ],
        "sensory_tags": ["cold", "damp", "metal"],
        "entity_seed_pools": {
            "env":  ["studzienka", "loose_chain"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["góra", "tunel boczny"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_kuznia_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "forge"],
        "name_pool": ["Hala Wielkiego Młota", "Sala Tronowa Cechu",
                      "Główne Kowadło"],
        "first_enter_pool": [
            "Okrągła sala. Pośrodku — kowadło wielkości stołu, "
            "obok stojak z trzema młotami. Najlżejszy waży tyle, "
            "co dwóch ludzi. Starszy Cechu stoi obok. Broda "
            "wpleciona w opaskę. Drugi koniec opaski przybity "
            "do ściany.",
        ],
        "look_pool": [
            "Kowadło. Trzy młoty. Drzwi za starszym z tabliczką "
            "„WYJŚCIE PIĘTRA — TYLKO PO OPŁACENIU CECHU”.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Stuk pojedynczych młotów. Echo cechowych pieśni.",
        ],
        "sensory_tags": ["hot", "metal", "smoke"],
        "entity_seed_pools": {
            "mon":  ["boss_starszy_cechu"],
            "env":  ["broken_barrel", "loose_chain"],
        },
        "exit_hints": ["wyjście piętra", "zaplecze"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"bractwo_komornika": 2},
    },

    # ── BIBLIOTEKA MIEJSKA ────────────────────────────────────────────
    {
        "template_id": "pool_czytelnia_glowna",
        "role": "danger",
        "actual_type": "combat",
        "tags": ["dangerous", "combat", "library", "quiet"],
        "name_pool": ["Czytelnia Główna", "Sala Studyjna",
                      "Boks Cichy"],
        "first_enter_pool": [
            "Stoły z zielonymi lampkami. Krzesła odsunięte, jakby "
            "ktoś nagle wstał. Książki w połowie czytania, nadal "
            "otwarte. Cisza tu nie jest cicha — ta cisza "
            "obserwuje.",
        ],
        "look_pool": [
            "Tabliczki z zasadami: „CISZA — KONSEKWENCJE NIEPISANE”, "
            "„PALCEM PO STRONACH — NIE NA STRONACH”.",
        ],
        "search_pool": [
            "Pod stołem ósmym zapomniana torba: 25 kredytów, "
            "fiolka czegoś zielonego, kartka z hasłem do "
            "magazynu „T”.",
        ],
        "public_hint_pool": [
            "Szelest stron — sam z siebie. Skrzypnięcie regału.",
        ],
        "sensory_tags": ["stale", "paper", "quiet"],
        "entity_seed_pools": {
            "mon":  ["czytelnik_zaginiony", "indeksowy_robak"],
            "env":  ["sponsor_screen", "torn_notebook"],
            "item": ["snack_bar", "credits_pile"],
        },
        "exit_hints": ["regały", "katalogi", "wyjście"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 3,
        "weight": 5,
        "floor_min": 3,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_katalogi_kartkowe",
        "role": "loot",
        "actual_type": "salvage",
        "tags": ["loot", "salvage", "library", "paper"],
        "name_pool": ["Katalogi Kartkowe", "Sala Indeksu",
                      "Magazyn Fiszek"],
        "first_enter_pool": [
            "Drewniane szafki z setkami szufladek. Każda z literą "
            "i zakresem. Kilka szuflad otwartych — fiszki "
            "porozrzucane, jakby ktoś szukał konkretnego nazwiska. "
            "Znalazł. Już go nie ma.",
        ],
        "look_pool": [
            "Szafki. Etykiety: A-Cz, Cz-Hi, Hi-Lo, Lo-Pa, Pa-Sz, "
            "Sz-Z. Szuflada „Z-Ż” brakuje.",
        ],
        "search_pool": [
            "W szufladzie „Lo-Pa” schowane: 40 kredytów, "
            "klucz biblioteczny, lista zakazanych autorów "
            "(z odręcznym dopiskiem „I TY”).",
        ],
        "public_hint_pool": [
            "Stuk drewna. Kurz dryfuje.",
        ],
        "sensory_tags": ["paper", "dust", "stale"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "item": ["credits_pile"],
        },
        "exit_hints": ["czytelnia", "magazyn"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 1},
    },
    {
        "template_id": "pool_pokoj_bibliotekarki",
        "role": "social",
        "actual_type": "social",
        "tags": ["social", "library", "rumor", "npc"],
        "name_pool": ["Pokój Bibliotekarki", "Biuro Działu",
                      "Stanowisko Wypożyczeń"],
        "first_enter_pool": [
            "Małe biuro za ladą. Bibliotekarka z kokiem, okulary "
            "na czubku nosa. Stempluje zwroty rytmicznie. Stempel "
            "„PRZETERMINOWANE” brzmi inaczej niż „ZWRÓCONE”. "
            "Obie pieczątki słyszysz dokładnie.",
        ],
        "look_pool": [
            "Lista czytelników z karami. Niektóre kary w "
            "kredytach, niektóre w czasie. Twoje nazwisko nie "
            "tam, ale rubryka oczekuje.",
        ],
        "search_pool": [
            "W szufladzie bibliotekarki: portfel z 35 kredytami, "
            "uniwersalna karta do magazynów, lista książek "
            "„DO PRZECZYTANIA POD GROŹBĄ”.",
        ],
        "public_hint_pool": [
            "Stuk pieczątek. Szelest stron.",
        ],
        "sensory_tags": ["paper", "stale", "coffee"],
        "entity_seed_pools": {
            "env":  ["torn_notebook", "furniture_wood"],
            "npc":  [("paranoid_mapper", "friendly")],
            "item": ["credits_pile"],
        },
        "exit_hints": ["czytelnia", "magazyn"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 3,
    },
    {
        "template_id": "pool_magazyn_t_biblioteczny",
        "role": "secret",
        "actual_type": "secret",
        "tags": ["secret", "library", "hidden", "restricted"],
        "name_pool": ["Magazyn T", "Skład Zakazany",
                      "Sektor Specjalny"],
        "first_enter_pool": [
            "Drzwi metalowe z trzema kłódkami. Wewnątrz półki "
            "z książkami w tekturowych pudłach. Każde pudło "
            "z tabliczką: „NIE WYDAWAĆ”, „NIE WYDAWAĆ”, "
            "„NIE WYDAWAĆ POD GROŹBĄ”.",
        ],
        "look_pool": [
            "Pudła. Większość zakurzona. Jedno z dopiskiem "
            "„WYDANE OSTATNIO” — pusto w środku.",
        ],
        "search_pool": [
            "W pustym pudle ukryta torba: 70 kredytów, "
            "stimpak, oprawiona książka bez tytułu "
            "(stary podręcznik magiczny).",
        ],
        "public_hint_pool": [
            "Cisza grobowa. Zapach naftaliny i papieru.",
        ],
        "sensory_tags": ["dust", "stale", "paper"],
        "entity_seed_pools": {
            "env":  ["torn_notebook"],
            "item": ["credits_pile", "stimpak"],
        },
        "exit_hints": ["powrót", "ukryte drzwi"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 1,
        "weight": 3,
        "floor_min": 3,
    },
    {
        "template_id": "pool_biblioteka_boss",
        "role": "boss",
        "actual_type": "boss",
        "tags": ["dangerous", "boss", "objective", "library"],
        "name_pool": ["Sala Konserwatora", "Czytelnia Specjalna",
                      "Sektor T-1"],
        "first_enter_pool": [
            "Wysoka sala z regałami do sufitu. Pośrodku biurko "
            "kuratorskie. Konserwator Zbiorów Specjalnych "
            "siedzi za nim, trzy pary okularów na łańcuszkach, "
            "klucze rozłożone wachlarzem. „A jak się pan tu "
            "dostał?” pyta, bez emocji.",
        ],
        "look_pool": [
            "Regały. Biurko. Drzwi za biurkiem z tabliczką "
            "„WYJŚCIE PIĘTRA — TYLKO PO ODDANIU KSIĄŻKI”.",
        ],
        "search_pool": [],
        "public_hint_pool": [
            "Cisza biblioteczna. Tylko twoje kroki.",
        ],
        "sensory_tags": ["dust", "stale", "paper"],
        "entity_seed_pools": {
            "mon":  ["boss_konserwator_zbiorow"],
            "env":  ["torn_notebook", "sponsor_camera"],
        },
        "exit_hints": ["wyjście piętra", "magazyn"],
        "guaranteed_min_exits": 2,
        "guaranteed_max_exits": 2,
        "weight": 1,
        "floor_min": 5,
        "unique_per_floor": True,
        "theme_sponsor_boost": {"ministerstwo_pamieci": 2},
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
