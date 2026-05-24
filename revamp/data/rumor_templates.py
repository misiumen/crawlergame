"""Rumor templates for sandbox floor gameplay.

Each rumor has:
  key          -- stable id used to dedupe + drive consequences
  truth        -- 0..1; lower means more likely false/biased
  text         -- the visible Polish line
  reveals_tags -- (optional) tags the player learns about

Buckets are by category so the engine can ask for a specific kind:
  floor_hint    — about the floor layout / shortcut / hazards
  boss_hint     — about a floor boss
  class_hint    — meta hint nudging toward a class affinity
  objective_hint— about reaching the floor exit
  npc_hint      — about a specific crawler/NPC
  false_or_biased — deliberately wrong or self-serving info
"""

RUMOR_TEMPLATES = {
    "floor_hint": [
        {
            "key": "acid_room_warning",
            "truth": 0.85,
            "text": "Crawler przy kawie twierdzi, że zielona ciecz w laboratorium reaguje na metal szybciej niż na mięso. Nie brzmi pocieszająco, ale brzmi użytecznie.",
            "reveals_tags": ["acid", "lab", "environment_weapon"],
        },
        {
            "key": "bathroom_shortcut",
            "truth": 0.75,
            "text": "Ktoś wydrapał na lustrze w łazience: 'Wentylacja za trzecią kabiną prowadzi tam, gdzie nikt nie chce iść dwa razy.'",
            "reveals_tags": ["bathroom", "vent", "shortcut"],
        },
        {
            "key": "freezer_carver_pattern",
            "truth": 0.9,
            "text": "Stary technik mówi, że Rzeźnik z Zamrażarki nie atakuje, dopóki nie usłyszy oddechu. Nie sprawdzaj tego empirycznie.",
            "reveals_tags": ["freezer", "stealth_kill_possible"],
        },
        {
            "key": "wiring_corridor",
            "truth": 0.7,
            "text": "Pod kafelkami w korytarzu A leżą gołe przewody. Ktoś wylał na nie wodę i potem nikt o nim nie słyszał.",
            "reveals_tags": ["corridor_a", "electric", "environment_weapon"],
        },
        {
            "key": "patrol_timer",
            "truth": 0.6,
            "text": "Patrol ochrony przechodzi przez relay co czterdzieści minut. Albo tak myśli ten, kto już dwa razy nie trafił.",
            "reveals_tags": ["relay", "patrol", "timing"],
        },
    ],
    "boss_hint": [
        {
            "key": "boss_likes_noise",
            "truth": 0.65,
            "text": "Ranny crawler mówi, że duży przy windzie reaguje na hałas. Potem poprawia: 'Nie reaguje. Celebruje.'",
            "reveals_tags": ["boss", "noise"],
        },
        {
            "key": "warden_keycard",
            "truth": 0.95,
            "text": "W kuble obok sali serwerowej leży połowa karty dostępu Strażnika. Połowa. Druga jest na nim.",
            "reveals_tags": ["boss", "keycard", "loot_corpse"],
        },
        {
            "key": "boss_bribe_route",
            "truth": 0.5,
            "text": "Barista szepcze, że Strażnik bierze pięćdziesiąt kredytów i jeden dobry argument. 'Może być argument w gotówce.'",
            "reveals_tags": ["boss", "bribe", "social"],
        },
    ],
    "objective_hint": [
        {
            "key": "keycard_seen_in_cafe",
            "truth": 0.8,
            "text": "Ktoś przy bufecie chwalił się kartą dostępu w kolorze, którego nie powinno się mieć na sobie publicznie.",
            "reveals_tags": ["keycard", "cafe", "crawler"],
        },
        {
            "key": "crawler_has_keycard",
            "truth": 0.7,
            "text": "Łatwiej rozpoznać karciarza po sposobie, w jaki nie patrzy w stronę swojej kieszeni.",
            "reveals_tags": ["keycard", "crawler", "social"],
        },
        {
            "key": "blackmarket_keycard",
            "truth": 0.55,
            "text": "Czarny rynek miał wczoraj kartę z napisem 'SERWIS'. Może mają jeszcze. Cena rośnie z każdym 'może'.",
            "reveals_tags": ["keycard", "black_market", "trade"],
        },
    ],
    "class_hint": [
        {
            "key": "env_class_hint",
            "truth": 1.0,
            "text": "Terminal rankingowy pokazuje klip, jak ktoś zabija potwora regałem. Podpis: 'Protokół lubi kandydatów, którzy rozumieją meble.'",
        },
        {
            "key": "social_class_hint",
            "truth": 1.0,
            "text": "Inny klip: zawodnik wygaduje strażnika ze stanowiska. Komentarz: 'Klasa Negocjator notuje wzrost zainteresowania sponsorów.'",
        },
    ],
    "npc_hint": [
        {
            "key": "wounded_brawler_trade",
            "truth": 0.85,
            "text": "Bydlak z bandażem oddaje informacje za bandaże. Pełen cykl: ty leczysz, on mówi.",
            "reveals_tags": ["wounded_brawler", "trade_info"],
        },
        {
            "key": "loot_goblin_betrays",
            "truth": 0.9,
            "text": "Rączka zdradza po cenie wyższej niż się umawia. Liczy się to, że umawia się.",
            "reveals_tags": ["loot_goblin_crawler", "betrayal"],
        },
    ],
    "false_or_biased": [
        {
            "key": "fake_free_loot",
            "truth": 0.15,
            "text": "Ktoś przysięga, że automat przy zamrażarce wydaje darmowe medkity, jeśli go kopnąć. Ma bandaż na stopie.",
        },
        {
            "key": "fake_safe_acid",
            "truth": 0.1,
            "text": "Pijany crawler twierdzi, że kwas w laboratorium jest 'tylko z marketingu'. Pokazuje rękę. Reszta ręki nie pokazuje.",
        },
        {
            "key": "sponsor_lie_easy_boss",
            "truth": 0.05,
            "text": "Reklama sponsora: 'Floor 1 boss padł średnio po trzech sekundach.' Drobny druk: '...od początku transmisji.'",
        },
    ],
}
