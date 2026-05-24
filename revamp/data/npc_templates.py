"""NPC and crawler archetypes for CRAWL PROTOCOL revamp."""

CRAWLER_ARCHETYPES = {
    "paranoid_mapper": {
        "fallback_name_pool": ["Kreda", "Stary Kompas", "Mapa bez Mapy"],
        "personality": "paranoid",
        "survival_style": "scout",
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
        "wants": ["skrzynki", "klucze", "cokolwiek co błyszczy"],
        "fears": ["uczciwe podziały", "audyt ekwipunku"],
        "secret": ["ma kradzioną kartę dostępu", "wie, który automat wydaje fałszywe medkity"],
        "helps_if": ["paid", "offered_loot_split"],
        "betrays_if": ["valuable_loot_visible", "relationship_low"],
        "dialogue": [
            "Nie kradnę. Przesuwam zasoby w stronę talentu.",
            "Możemy się podzielić. Ty bierzesz ryzyko, ja biorę rzeczy."
        ]
    }
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
            "Nie pytaj, skąd mleko. Pytaj, czy działa."
        ]
    }
}
