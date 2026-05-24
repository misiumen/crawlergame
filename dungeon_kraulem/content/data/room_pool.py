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
            "Kwas na podłodze. Butla gazu pod ścianą. Na ścianie naklejka: NIE LĄCZYĆ "
            "KWASU Z OGNIEM. PROSIMY.",
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
        "first_enter_pool": [
            "Klimatyzacja wyje. Na regałach stoją kartony z napisem 'KONTAKT — NIE OTWIERAĆ'. "
            "Ktoś otworzył.",
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
        "exit_hints": ["szyb", "relay"],
        "guaranteed_min_exits": 1,
        "guaranteed_max_exits": 2,
        "weight": 4,
        "floor_min": 1,
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
        "floor_min": 1,
        "unique_per_floor": True,
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
