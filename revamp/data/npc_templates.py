"""NPC and crawler archetypes for CRAWL PROTOCOL revamp."""

CRAWLER_ARCHETYPES = {
    "paranoid_mapper": {
        "fallback_name_pool": ["Kreda", "Stary Kompas", "Mapa bez Mapy"],
        "personality": "paranoid",
        "survival_style": "scout",
        "tags": ["crawler", "scout", "non_combat", "rumor_source", "stealth"],
        "weight": 5, "floor_min": 1, "floor_max": 5,
        "risks": ["paranoia_spike", "false_intel"],
        "rewards": ["map_hint", "secret_route_hint", "rumor"],
        "wants": ["bezpieczne przejście", "informacje o patrolach", "baterie do latarki"],
        "fears": ["otwarte przestrzenie", "kamery sponsora", "cisza po alarmie"],
        "secret": ["zna skrót, ale uważa, że jest przeklęty", "ma fragment mapy z innego piętra"],
        "helps_if": ["player_shared_rumor", "relationship_positive", "player_has_battery"],
        "betrays_if": ["threatened", "player_too_famous"],
        "dialogue": [
            "Nie idź tam, gdzie jest czysto. Czysto znaczy, że coś właśnie sprzątało.",
            "Mapa nie pokazuje przejść. Mapa pokazuje miejsca, gdzie ludzie myśleli, że były przejścia."
        ]
    },
    "wounded_brawler": {
        "fallback_name_pool": ["Żelazny Kuba", "Bark", "Pęknięta Szczęka"],
        "personality": "honorable",
        "survival_style": "melee_brawler",
        "tags": ["crawler", "fighter", "wounded", "social", "ally_potential"],
        "weight": 6, "floor_min": 1, "floor_max": 4,
        "risks": ["follow_into_combat", "guilt"],
        "rewards": ["intel_floor", "temporary_ally", "boss_weakness_hint"],
        "wants": ["medykamenty", "szansę na rewanż", "kogoś do odprowadzenia do safehouse"],
        "fears": ["zostania samemu", "crawlerów z uśmiechem sponsora"],
        "secret": ["zabił przyjaciela w panice", "wie, gdzie boss nie patrzy"],
        "helps_if": ["healed_by_player", "player_fights_fair"],
        "betrays_if": ["never_if_trusted"],
        "dialogue": [
            "Nie mam nic przeciwko umieraniu. Mam przeciwko temu, że ktoś ma na tym zarobić.",
            "Pomóż mi dojść do kawiarni, a powiem ci, co robi ten bydlak przy windzie."
        ]
    },
    "loot_goblin_crawler": {
        "fallback_name_pool": ["Rączka", "Zguba", "Mały Leasing"],
        "personality": "opportunist",
        "survival_style": "loot_goblin",
        "tags": ["crawler", "trade", "betrayal_potential", "non_combat", "loot_hint"],
        "weight": 5, "floor_min": 1, "floor_max": 5,
        "risks": ["theft", "betrayal", "loot_split_unfair"],
        "rewards": ["contraband", "loot_location", "trade_credits"],
        "wants": ["skrzynki", "klucze", "cokolwiek co błyszczy"],
        "fears": ["uczciwe podziały", "audyt ekwipunku"],
        "secret": ["ma kradzioną kartę dostępu", "wie, który automat wydaje fałszywe medkity"],
        "helps_if": ["paid", "offered_loot_split"],
        "betrays_if": ["valuable_loot_visible", "relationship_low"],
        "dialogue": [
            "Nie kradnę. Przesuwam zasoby w stronę talentu.",
            "Możemy się podzielić. Ty bierzesz ryzyko, ja biorę rzeczy."
        ]
    },
    "broken_celebrity": {
        "fallback_name_pool": ["Były Mistrz", "Drugi Sezon", "Pan z Reklamy"],
        "personality": "celebrity",
        "survival_style": "social_manipulation",
        "tags": ["crawler", "social", "audience_pull", "fragile"],
        "weight": 3, "floor_min": 1, "floor_max": 5,
        "risks": ["audience_swing", "drama_event"],
        "rewards": ["audience_boost", "sponsor_intel"],
        "wants": ["widownię", "darmowe drinki", "powtórki własnych klipów"],
        "fears": ["bycia wymazanym z rankingu", "ciszy"],
        "secret": ["produkcja kazała mu udawać, że jeszcze nie umarł", "wie, gdzie sponsor chowa scenariusze"],
        "helps_if": ["audience_high", "offered_camera_time"],
        "betrays_if": ["audience_too_low", "another_celebrity_present"],
        "dialogue": [
            "Kiedyś robiłem to lepiej. Teraz robię to taniej.",
            "Daj mi minutę na kamerze, a ja oddam ci coś znacznie mniej wartego niż minuta.",
        ],
    },
    "quiet_killer": {
        "fallback_name_pool": ["Nikt", "Cichy Drugi Etat", "Patrz w Inną Stronę"],
        "personality": "silent_killer",
        "survival_style": "stealth",
        "tags": ["crawler", "hostile_potential", "stealth", "danger"],
        "weight": 3, "floor_min": 2, "floor_max": 5,
        "risks": ["assassination", "framed", "alert_patrol"],
        "rewards": ["kill_intel", "stealth_affinity"],
        "wants": ["pozostać niezauważonym", "skończyć kontrakt", "zniknąć przed finałem"],
        "fears": ["sponsorów", "audycji własnej śmierci na żywo"],
        "secret": ["zlikwidował 4 innych zawodników z polecenia", "ma listę celów na to piętro"],
        "helps_if": ["player_quiet", "player_useful_as_alibi"],
        "betrays_if": ["player_witness", "player_too_loud"],
        "dialogue": [
            "Nie patrz na mnie. Patrz w stronę kamery, jak wszyscy.",
            "Nie pytaj, co tu robię. Pytaj, kiedy stąd wyjdę.",
        ],
    },
    "preaching_witness": {
        "fallback_name_pool": ["Kaznodzieja z Korytarza", "Ostatni Świadek",
                                "Brat Ode Mnie"],
        "personality": "zealot",
        "survival_style": "diplomacy",
        "tags": ["crawler", "social", "lore_source", "non_combat"],
        "weight": 3, "floor_min": 1, "floor_max": 5,
        "risks": ["lecture", "audience_swing"],
        "rewards": ["lore_fragment", "rumor", "diplomacy_affinity"],
        "wants": ["kogoś, kto wysłucha", "raport z poprzedniego piętra",
                  "świadectwo na żywo"],
        "fears": ["cisza widowni", "moralna obojętność"],
        "secret": ["wie, że Syndykat fałszuje statystyki śmierci",
                   "ma fragment kontraktu z pieczęcią"],
        "helps_if": ["player_listens", "player_shared_grief"],
        "betrays_if": ["player_mocks", "player_too_violent"],
        "dialogue": [
            "Każdy crawler to dwa testimonia: jedno żywe, jedno po. Ja słucham obu.",
            "Powiedz mi imię. Tylko imię. Reszta dopisuje się sama.",
        ],
    },
}

SAFEHOUSE_NPCS = {
    "bathroom_attendant": {
        "role": "bathroom_attendant",
        "fallback_names": ["Pani od Kabin", "Sanitariusz Neutralności", "Dozorca Płytek"],
        "services": ["bathroom", "wash", "minor_condition_remove", "rumor"],
        "dialogue": [
            "Kabina trzecia jest zamknięta z powodów prawnych i biologicznych.",
            "Mycie rąk jest obowiązkowe. Mycie sumienia dodatkowo płatne."
        ]
    },
    "barista": {
        "role": "barista",
        "fallback_names": ["Barista z Przymusu", "Ekspresowy Kapłan", "Mleczna Pianka"],
        "services": ["coffee", "food", "rumor", "listen"],
        "dialogue": [
            "Kawa jest czarna, gorzka i zgodna z regulaminem przeżycia.",
            "Nie pytaj, skąd mleko. Pytaj, czy działa.",
        ],
    },
    "clinic_intake": {
        "role": "clinic_intake",
        "fallback_names": ["Recepcjonista", "Sanitariusz", "Pan z Cennikiem"],
        "services": ["heal", "cure", "full", "rumor"],
        "dialogue": [
            "Cennik jest negocjowalny tylko w zakresie monety.",
            "Państwa rana jest dla nas wyzwaniem statystycznym.",
        ],
    },
    "blackmarket_vendor": {
        "role": "blackmarket_vendor",
        "fallback_names": ["Sprzedawca Bez Imienia", "Pan Pod Ladą", "Trzecie Krzesło"],
        "services": ["buy", "sell", "rumor", "illegal_goods"],
        "dialogue": [
            "Gwarancja jest tylko na nazwę. Reszta — twoja sprawa.",
            "Nie pytaj, skąd to mam. Pytaj, czy chcesz dwa.",
        ],
    },
    "sponsor_clerk": {
        "role": "sponsor_clerk",
        "fallback_names": ["Pan z Kiosku", "Reprezentant NovaChem", "Voice Of Sponsor"],
        "services": ["ad", "intel", "rumor"],
        "dialogue": [
            "Sponsor cieszy się z państwa udziału. Cieszy się umiarkowanie.",
            "Mamy ciekawą ofertę. Wszystkie nasze oferty są ciekawe.",
        ],
    },
}
