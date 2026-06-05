"""Hand-authored Floor 1 — 14 rooms.

Each template:
  id, short_title, title, first_enter, look, search, public_hint,
  actual_type, sensory_tags, exits, entity_seeds, locked, secret,
  safehouse_subtype.

The procgen module instantiates these into RoomState objects and wires exits.

All `*_key` strings are i18n keys. `fallback_*` are inline Polish so the
game still reads naturally even before the JSON is filled in.
"""

FLOOR_1_TITLE_KEY = "floor1_title"
FLOOR_1_TITLE_FALLBACK = "Piętro 1 — Sortownia Zawodników"
FLOOR_1_THEME_KEY = "floor1_theme"
FLOOR_1_THEME_FALLBACK = "Przemysłowe korytarze, sponsorowane przez 'NovaChem'."
FLOOR_1_SPONSOR_KEY = "floor1_sponsor"
FLOOR_1_SPONSOR_FALLBACK = "Sponsoruje: NovaChem Biotech."


# An entity_seed is one of:
#   ("env",  key)                                 -> environmental feature
#   ("haz",  key)                                 -> hazard
#   ("door", key, label, target_room, locked)     -> door entity (also referenced by exits)
#   ("term", key)                                 -> terminal
#   ("item", item_key)                            -> loose item
#   ("mon",  monster_key)                         -> monster
#   ("npc",  archetype, disposition)              -> crawler (random name)
#   ("svc",  service_key)                         -> safehouse service object
#
# `locked` doors are also reflected on the room.exits dict.

ROOMS = [
    {
        "id": "r1_intake",
        "short_title_key": "room_intake_short",   "fallback_short_title": "Sala Wejścia",
        "title_key":       "room_intake_title",   "fallback_title": "Sala Wejścia / Aklimatyzacja",
        "first_enter_key": "room_intake_fe",
        "fallback_first_enter":
          "Świetlówki nad głową drgają w nieregularnym rytmie. Powietrze jest zimne, sterylne, "
          "z lekko metalicznym posmakiem. Na podłodze leżą zdjęte folie z opakowań po zawodnikach. "
          "Pod ścianą stoi automat z kawą, który łaskawie nie działa. Na suficie wisi przewrócona "
          "kamera sponsora, lekko bujająca się na przewodzie.",
        "look_key": "room_intake_look",
        "fallback_look":
          "Wracasz wzrokiem po sali wejściowej. Plakat: 'Witamy uczestników. Powodzenia w Crawlu™. "
          "Twoja widownia już patrzy.' Z korytarza po wschodniej stronie sączy się ciepłe powietrze "
          "i zapach palonego plastiku. Drzwi na zachód wyglądają jak normalne wyjście. Na północy "
          "luki serwisowe — uchylone.",
        "search_key": "room_intake_search",
        "fallback_search":
          "Pod automatem znajdujesz wciśnięty plastikowy identyfikator z napisem 'KONTRAKTOR — "
          "MOŻE POMÓC, NIE MUSI'. Czyjeś łzy zdarły z niego nazwisko.",
        "public_hint_key": "room_intake_hint",
        "fallback_public_hint": "Słychać brzęczenie automatu i czyjś śmiech przez radio.",
        "actual_type": "start",
        "sensory_tags": ["dim","cold","sterile","sponsor_ads"],
        "exits": {
            "wschód":  {"target":"r1_corridor_a","locked":False,"hidden":False,
                        "hint_key":"","fallback_hint":"Ciepło i palony plastik."},
            "zachód":  {"target":"r1_cafeteria","locked":False,"hidden":False,
                        "hint_key":"","fallback_hint":"Kawa. Naprawdę kawa."},
            "północ":  {"target":"r1_service_duct","locked":False,"hidden":False,
                        "hint_key":"","fallback_hint":"Otwarta luka serwisowa. Wąsko."},
        },
        "entity_seeds": [
            ("env","sponsor_camera"),
            ("env","coffee_machine"),
            ("item","plastic_badge"),
        ],
    },
    {
        "id": "r1_cafeteria",
        "short_title_key": "room_cafeteria_short", "fallback_short_title": "Kafejka",
        "title_key":       "room_cafeteria_title", "fallback_title": "Kafejka „Posłuszny Klient”",
        "first_enter_key": "room_cafeteria_fe",
        "fallback_first_enter":
          "Stoliki z taniego laminatu, krzesła ustawione zbyt regularnie. Na ścianie ekran "
          "z reklamą sponsorską na pętli, dźwięk wyłączony. Za ladą stoi zawodnik w fartuchu, "
          "udający, że pracuje. Pachnie palonym ziarnem i resztą dnia, którego ktoś już nie ma.",
        "look_key": "room_cafeteria_look",
        "fallback_look":
          "Lampy nad stolikami świecą za jasno. Na środkowym stoliku ktoś zostawił kubek z resztką "
          "zimnej kawy. Drzwi z napisem 'PERSONEL' są lekko uchylone. Wyjście na wschód prowadzi "
          "z powrotem do Sali Wejścia.",
        "public_hint_key": "room_cafeteria_hint",
        "fallback_public_hint": "Skrzypiące krzesło. Ekran reklamy. Zapach kawy.",
        "actual_type": "safehouse",
        "safehouse_subtype": "cafe",
        "sensory_tags": ["bright","warm","coffee","sponsor_ads","crowded"],
        "exits": {
            "wschód": {"target":"r1_intake","locked":False,"hidden":False},
            "zaplecze": {"target":"r1_storage","locked":True,"hidden":False,
                         "hint_key":"","fallback_hint":"Drzwi 'PERSONEL'. Zamknięte."},
        },
        "entity_seeds": [
            ("svc","coffee_counter"),
            ("npc","scavenger","friendly"),
            ("item","cracked_mug"),
            ("env","sponsor_screen"),
        ],
    },
    {
        "id": "r1_storage",
        "short_title_key": "room_storage_short", "fallback_short_title": "Zaplecze",
        "title_key":       "room_storage_title", "fallback_title": "Zaplecze Kafejki",
        "first_enter_key": "room_storage_fe",
        "fallback_first_enter":
          "Klimatyzacja wyje. Na regałach stoją kartony z napisem 'KONTAKT — NIE OTWIERAĆ'. "
          "Ktoś otworzył. W kącie leży karton z brakującą połową boku. Pachnie kurzem i kawą.",
        "look_key": "room_storage_look",
        "fallback_look":
          "Półki pełne syropów, mleka w proszku i czegoś, co ma datę ważności sprzed dwóch lat. "
          "Pod sufitem szafa serwisowa z czerwoną diodą.",
        "search_key": "room_storage_search",
        "fallback_search":
          "Pod jednym z kartonów znajdujesz baterię i kawałek taśmy izolacyjnej. "
          "W szafie serwisowej trzeszczy starszy terminal.",
        "public_hint_key": "room_storage_hint",
        "fallback_public_hint": "Klimatyzacja. Coś brzęczy.",
        "actual_type": "loot",
        "sensory_tags": ["dusty","warm","electrical_hum"],
        "exits": {
            "kafejka": {"target":"r1_cafeteria","locked":False,"hidden":False},
        },
        "entity_seeds": [
            ("item","battery"),
            ("item","duct_tape"),
            ("term","storage_terminal"),
        ],
        "locked": True,
    },
    {
        "id": "r1_corridor_a",
        "short_title_key": "room_corra_short", "fallback_short_title": "Korytarz A",
        "title_key":       "room_corra_title", "fallback_title": "Korytarz Serwisowy A",
        "first_enter_key": "room_corra_fe",
        "fallback_first_enter":
          "Wąski korytarz, sufit nisko, jedna świetlówka pulsuje. Ściany pokrywa zielonkawy "
          "osad, który wygląda jak coś, co kiedyś żyło. Powietrze wibruje cichym buczeniem maszyn. "
          "Słychać kroki — niekoniecznie ludzkie.",
        "look_key": "room_corra_look",
        "fallback_look":
          "Z jednej strony korytarz prowadzi z powrotem do Sali Wejścia. Na wschodzie ciemniejszy "
          "łuk drzwi. Na południu otwarte przejście do czegoś, co kiedyś było łazienką.",
        "public_hint_key": "room_corra_hint",
        "fallback_public_hint": "Coś chodzi tam i z powrotem. Mokry odgłos kroków.",
        "actual_type": "combat",
        "sensory_tags": ["dim","humming","mossy_smell"],
        "exits": {
            "zachód": {"target":"r1_intake","locked":False,"hidden":False},
            "wschód": {"target":"r1_chem_lab","locked":False,"hidden":False,
                       "hint_key":"","fallback_hint":"Zapach chemii."},
            "południe": {"target":"r1_bathroom","locked":False,"hidden":False,
                         "hint_key":"","fallback_hint":"Kafelki. Mokro."},
        },
        "entity_seeds": [
            ("mon","tunnel_runt"),
            ("env","exposed_wiring"),
            ("env","water_pool"),
        ],
    },
    {
        "id": "r1_bathroom",
        "short_title_key": "room_bath_short", "fallback_short_title": "Łazienka",
        "title_key":       "room_bath_title", "fallback_title": "Publiczna Łazienka 1A",
        "first_enter_key": "room_bath_fe",
        "fallback_first_enter":
          "Kafelki w kolorze 'kiedyś białym'. Pod jedną z umywalek bulgocze coś, co nie powinno. "
          "Lustro popękane, ale w jednym fragmencie nadal coś pokazuje. Drzwi do kabin uchylone, "
          "puste. Na ścianie świeże graffiti: 'NIE WCHODŹ DO POKOJU 7'.",
        "look_key": "room_bath_look",
        "fallback_look":
          "Kafelki. Zimne, mokre, nieprzyjemnie czyste. Drzwi do korytarza A na północy. "
          "Jedna kabina w głębi wygląda na zaryglowaną od środka.",
        "search_key": "room_bath_search",
        "fallback_search":
          "Pod umywalką znajdujesz brudny bandaż i kawałek metalowego drutu. Nad lustrem ktoś "
          "wyrysował małą strzałkę wskazującą na sufit. Sufit ma wyglądającą na luźną kratę.",
        "public_hint_key": "room_bath_hint",
        "fallback_public_hint": "Bulgotanie. Kapanie. Ktoś szepcze do lustra.",
        "actual_type": "safehouse",
        "safehouse_subtype": "bathroom",
        "sensory_tags": ["damp","cold","echo","graffiti"],
        "exits": {
            "północ": {"target":"r1_corridor_a","locked":False,"hidden":False},
            "sufit":  {"target":"r1_vent","locked":False,"hidden":True,
                       "hint_key":"","fallback_hint":"Krata w suficie, łatwo zerwać."},
        },
        "entity_seeds": [
            ("svc","mirror"),
            ("item","dirty_bandage"),
            ("env","loose_grate"),
        ],
    },
    {
        "id": "r1_vent",
        "short_title_key": "room_vent_short", "fallback_short_title": "Szyb Wentylacyjny",
        "title_key":       "room_vent_title", "fallback_title": "Szyb Wentylacyjny — Sekcja Pn",
        "first_enter_key": "room_vent_fe",
        "fallback_first_enter":
          "Ciasno. Czarno. Kolana boli już po pięciu metrach. Powietrze zalatuje smarem i czymś "
          "słodkim, czego nie chcesz znać.",
        "look_key": "room_vent_look",
        "fallback_look":
          "Szyb rozgałęzia się. Jedna nitka prowadzi w dół do łazienki, druga — w stronę dziwnego "
          "ciepła, prawdopodobnie biura technicznego.",
        "search_key": "room_vent_search",
        "fallback_search":
          "Wciśnięta między blachy karteczka: '7-3-7 nie działa od piątku. Spróbuj 7-3-9.'",
        "public_hint_key": "room_vent_hint",
        "fallback_public_hint": "Echo. Cichy stuk metalu.",
        "actual_type": "secret",
        "sensory_tags": ["dark","cramped","oily"],
        "exits": {
            "w dół do łazienki": {"target":"r1_bathroom","locked":False,"hidden":False},
            "biuro techniczne":  {"target":"r1_office","locked":False,"hidden":False,
                                  "hint_key":"","fallback_hint":"Ciepło. Klawiatura."},
        },
        "entity_seeds": [
            ("item","suspicious_keycard"),
        ],
        "secret": True,
    },
    {
        "id": "r1_chem_lab",
        "short_title_key": "room_chem_short", "fallback_short_title": "Sala Chemiczna",
        "title_key":       "room_chem_title", "fallback_title": "Sala Chemiczna — Sekcja NovaChem",
        "first_enter_key": "room_chem_fe",
        "fallback_first_enter":
          "Zielonkawe światło bije z górnej rury. Na podłodze kałuża czegoś, co dymi przy "
          "dotknięciu z metalem. Stół laboratoryjny zastawiony pustymi szkłami. Z kąta sapie "
          "duża butla z gazem.",
        "look_key": "room_chem_look",
        "fallback_look":
          "Kwas na podłodze. Butla gazu. Na ścianie naklejka: 'NIE MIESZAĆ KWASU Z "
          "OGNIEM. DZIĘKUJEMY ZA WSPÓŁPRACĘ.' Drzwi na wschód są ciężkie, opisane "
          "jako 'PRZECHOWALNIA'.",
        "search_key": "room_chem_search",
        "fallback_search":
          "Pod stołem zardzewiały, ale ostry nóż. Ktoś musiał stracić cierpliwość.",
        "public_hint_key": "room_chem_hint",
        "fallback_public_hint": "Słodki zapach. Ciche bulgotanie.",
        "actual_type": "trap",
        "sensory_tags": ["acid","gas","green_light"],
        "exits": {
            "zachód": {"target":"r1_corridor_a","locked":False,"hidden":False},
            "wschód": {"target":"r1_freezer","locked":True,"hidden":False,
                       "hint_key":"","fallback_hint":"Ciężkie drzwi 'PRZECHOWALNIA'."},
        },
        "entity_seeds": [
            ("haz","acid_pool"),
            ("env","gas_canister"),
            ("item","cheap_knife"),
        ],
    },
    {
        "id": "r1_freezer",
        "short_title_key": "room_freezer_short", "fallback_short_title": "Przechowalnia",
        "title_key":       "room_freezer_title", "fallback_title": "Zamrażarka — Mięso Nieidentyfikowalne",
        "first_enter_key": "room_freezer_fe",
        "fallback_first_enter":
          "Zimno. Białe światło z fluorków. Pod ścianami wiszą foliowane bryły, które kiedyś "
          "mogły być czymś żywym. Coś chrupie. Coś łowi. Ktoś tu kiedyś krzyczał.",
        "look_key": "room_freezer_look",
        "fallback_look":
          "Mróz wgryza ci się w policzki. W głębi pomieszczenia stoi otwarty kontener z "
          "wyposażeniem ratowniczym. Wyjście tylko na zachód do Sali Chemicznej.",
        "search_key": "room_freezer_search",
        "fallback_search":
          "Z kontenera wyciągasz batona z 2023 roku i podejrzanie sprawną latarkę.",
        "public_hint_key": "room_freezer_hint",
        "fallback_public_hint": "Bardzo zimno. Skrobanie. Cichy oddech.",
        "actual_type": "combat",
        "sensory_tags": ["cold","bright","meat_smell"],
        "exits": {
            "zachód": {"target":"r1_chem_lab","locked":False,"hidden":False},
        },
        "entity_seeds": [
            ("mon","freezer_carver"),
            ("item","flashlight"),
            ("item","snack_bar"),
        ],
        "locked": True,
    },
    {
        "id": "r1_service_duct",
        "short_title_key": "room_duct_short", "fallback_short_title": "Luki Serwisowe",
        "title_key":       "room_duct_title", "fallback_title": "Pion Serwisowy",
        "first_enter_key": "room_duct_fe",
        "fallback_first_enter":
          "Wąski pion w betonie. Na ścianach kable, niektóre obnażone do miedzi. Sufit "
          "nieskończenie wysoko. W dół prowadzi drabinka, w górę — luka z czerwonym napisem.",
        "look_key": "room_duct_look",
        "fallback_look":
          "Drabinka w dół. Luka w górę z naklejką 'DOSTĘP OGRANICZONY'. Z południa otwarte "
          "wyjście do nudnego, ciepłego korytarza.",
        "search_key": "room_duct_search",
        "fallback_search":
          "Pod drabinką luźno wisi pęk kabli. Wystarczyłoby pociągnąć, żeby je wyrwać.",
        "public_hint_key": "room_duct_hint",
        "fallback_public_hint": "Wiatr. Szelest plastikowych worków.",
        "actual_type": "neutral",
        "sensory_tags": ["dim","cool","draft"],
        "exits": {
            "z powrotem do sali": {"target":"r1_intake","locked":False,"hidden":False},
            "południe":            {"target":"r1_warm_hall","locked":False,"hidden":False,
                                    "hint_key":"","fallback_hint":"Ciepły, normalny korytarz."},
            "w górę (zamknięte)":  {"target":"r1_relay","locked":True,"hidden":False,
                                    "hint_key":"","fallback_hint":"Czerwona naklejka. Zamknięte."},
        },
        "entity_seeds": [
            ("env","loose_cables"),
            ("npc","runner","ignoring"),
        ],
    },
    {
        "id": "r1_warm_hall",
        "short_title_key": "room_warmhall_short", "fallback_short_title": "Ciepły Korytarz",
        "title_key":       "room_warmhall_title", "fallback_title": "Korytarz Administracyjny",
        "first_enter_key": "room_warmhall_fe",
        "fallback_first_enter":
          "Po raz pierwszy od dłuższego czasu — normalny, ciepły korytarz. Dywanik. Drukowane "
          "plakaty motywacyjne. Z jednego boku okienko kiosku 'INFO'.",
        "look_key": "room_warmhall_look",
        "fallback_look":
          "Kiosk sponsorski. Drzwi z napisem 'KLINIKA'. Schody w dół do czegoś, co wygląda na "
          "ćwiczebną arenę.",
        "public_hint_key": "room_warmhall_hint",
        "fallback_public_hint": "Cicha muzyka windowa. Plakat motywacyjny.",
        "actual_type": "safehouse",
        "safehouse_subtype": "sponsor_kiosk",
        "sensory_tags": ["warm","music","ads"],
        "exits": {
            "luki":      {"target":"r1_service_duct","locked":False,"hidden":False},
            "klinika":   {"target":"r1_clinic","locked":False,"hidden":False,
                          "hint_key":"","fallback_hint":"Klinika polowa. Pachnie alkoholem."},
            "schody":    {"target":"r1_arena","locked":False,"hidden":False,
                          "hint_key":"","fallback_hint":"Echo wielkiej pustej hali."},
        },
        "entity_seeds": [
            ("svc","sponsor_kiosk"),
            ("env","sponsor_screen"),
        ],
    },
    {
        "id": "r1_clinic",
        "short_title_key": "room_clinic_short", "fallback_short_title": "Klinika",
        "title_key":       "room_clinic_title", "fallback_title": "Klinika Polowa NovaChem",
        "first_enter_key": "room_clinic_fe",
        "fallback_first_enter":
          "Białe płytki, lampy halogenowe i zapach środka dezynfekującego, który próbuje "
          "ukryć krew. Recepcja obsługiwana przez maszynę. Kolejka jednego pacjenta.",
        "look_key": "room_clinic_look",
        "fallback_look":
          "Cennik wisi na ścianie. Wszystko bardzo drogie i bardzo dokładne. W kącie półka "
          "z apteczkami pierwszej pomocy.",
        "public_hint_key": "room_clinic_hint",
        "fallback_public_hint": "Cisza. Zapach alkoholu. Cichy ekran z kolejką.",
        "actual_type": "safehouse",
        "safehouse_subtype": "clinic",
        "sensory_tags": ["bright","cold","clinical","ads"],
        "exits": {
            "korytarz": {"target":"r1_warm_hall","locked":False,"hidden":False},
        },
        "entity_seeds": [
            ("svc","clinic_counter"),
            ("npc","medic","friendly"),
        ],
    },
    {
        "id": "r1_office",
        "short_title_key": "room_office_short", "fallback_short_title": "Biuro Techniczne",
        "title_key":       "room_office_title", "fallback_title": "Biuro Technika Konserwującego",
        "first_enter_key": "room_office_fe",
        "fallback_first_enter":
          "Małe biuro z biurkiem zasłanym papierami, zdychającym monitorem i kubkiem po kawie, "
          "który stoi tu od zbyt długiego czasu. Pod ścianą wisi schemat piętra z odręcznymi "
          "kreskami i przekleństwami.",
        "look_key": "room_office_look",
        "fallback_look":
          "Schemat piętra na ścianie. Terminal z migającym logiem. Drzwi do szybu serwisowego "
          "w głębi.",
        "search_key": "room_office_search",
        "fallback_search":
          "Pod papierami: zestaw wytrychów (improwizowany) i karteczka z hasłem 'klepsydra'.",
        "public_hint_key": "room_office_hint",
        "fallback_public_hint": "Ledwo działający monitor.",
        "actual_type": "loot",
        "sensory_tags": ["warm","paper","old_tech"],
        "exits": {
            "szyb":  {"target":"r1_vent","locked":False,"hidden":False},
            "relay": {"target":"r1_relay","locked":False,"hidden":False,
                      "hint_key":"","fallback_hint":"Drzwi z kartą dostępu."},
        },
        "entity_seeds": [
            ("term","office_terminal"),
            ("item","improvised_lockpick"),
        ],
    },
    {
        "id": "r1_relay",
        "short_title_key": "room_relay_short", "fallback_short_title": "Relay",
        "title_key":       "room_relay_title", "fallback_title": "Stacja Przekaźnikowa A",
        "first_enter_key": "room_relay_fe",
        "fallback_first_enter":
          "Pomieszczenie pełne szafek serwerowych. Czerwone diody migoczą w nieprzewidywalnym "
          "rytmie. Na końcu sali widać duże drzwi z napisem 'WYJŚCIE Z PIĘTRA'. Pod drzwiami "
          "stoi coś, co kiedyś było ochroniarzem.",
        "look_key": "room_relay_look",
        "fallback_look":
          "Drzwi wyjściowe. Ochroniarz. Szafki, które brzęczą. Czujesz tu zakończenie czegoś.",
        "public_hint_key": "room_relay_hint",
        "fallback_public_hint": "Buczenie serwerów. Ciężkie kroki ochroniarza.",
        "actual_type": "boss",
        "sensory_tags": ["bright","loud","electric"],
        "exits": {
            "biuro":          {"target":"r1_office","locked":False,"hidden":False},
            "luki (w dół)":   {"target":"r1_service_duct","locked":True,"hidden":False,
                               "hint_key":"","fallback_hint":"Drzwi z czerwoną naklejką."},
            "wyjście piętra": {"target":"r1_exit","locked":True,"hidden":False,
                               "hint_key":"","fallback_hint":"Wymaga klucza ochroniarza."},
        },
        "entity_seeds": [
            ("mon","relay_warden"),
            ("env","server_rack"),
        ],
        "locked": True,
    },
    {
        "id": "r1_arena",
        "short_title_key": "room_arena_short", "fallback_short_title": "Arena Ćwiczebna",
        "title_key":       "room_arena_title", "fallback_title": "Hala Treningowa — Pokaz na Żywo",
        "first_enter_key": "room_arena_fe",
        "fallback_first_enter":
          "Wielka hala z miękką wykładziną imitującą piasek. Refleksor obraca się leniwie. "
          "Na środku coś chrupie kostki. Dookoła, na trybunach, świecące kamery. Widownia jest, "
          "ale nie jest tutaj.",
        "look_key": "room_arena_look",
        "fallback_look":
          "Otwarta przestrzeń. Z dwóch stron wyjścia: schody w górę i tunel boczny. Na środku "
          "stoi coś, co bardzo wyraźnie czeka.",
        "public_hint_key": "room_arena_hint",
        "fallback_public_hint": "Echo dużej pustej hali. Refleksor.",
        "actual_type": "encounter",
        "sensory_tags": ["bright","spotlight","echo","audience"],
        "exits": {
            "schody (w górę)": {"target":"r1_warm_hall","locked":False,"hidden":False},
            "tunel boczny":    {"target":"r1_service_duct","locked":False,"hidden":True,
                                "hint_key":"","fallback_hint":"Tunel, jeśli wiesz gdzie."},
        },
        "entity_seeds": [
            ("npc","showman","hostile"),
        ],
    },
    {
        "id": "r1_exit",
        "short_title_key": "room_exit_short", "fallback_short_title": "Wyjście z Piętra",
        "title_key":       "room_exit_title", "fallback_title": "Korytarz Zejściowy",
        "first_enter_key": "room_exit_fe",
        "fallback_first_enter":
          "Po drugiej stronie ciężkich drzwi czeka prosta klatka schodowa w dół. Pierwszy raz "
          "od chwili wejścia czujesz coś podobnego do nadziei. Loch przyjmuje to do wiadomości.",
        "look_key": "room_exit_look",
        "fallback_look":
          "Klatka schodowa w dół. Czerwony przycisk z napisem 'POTWIERDZAM ZEJŚCIE'.",
        "public_hint_key": "room_exit_hint",
        "fallback_public_hint": "Cisza. Świeże powietrze. Echo schodów.",
        "actual_type": "exit",
        "sensory_tags": ["fresh_air","echo"],
        "exits": {
            "z powrotem": {"target":"r1_relay","locked":False,"hidden":False},
        },
        "entity_seeds": [],
    },
]
