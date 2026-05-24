"""Rumor templates for sandbox floor gameplay.

Each rumor has at minimum:
  key          -- stable id used to dedupe + drive consequences
  truth        -- 0..1; lower means more likely false/biased
  text         -- the visible Polish line
  reveals_tags -- (optional) tags the player learns about

Defaults applied at lookup time (Prompt 06a, gap #5) when not set on a
rumor explicitly:
  tags          = []
  weight        = 1
  floor_min     = 1
  floor_max     = 5
  reliability   = same as `truth` (0..1)
  source_types  = ["npc_dialogue","rumor","graffiti"]
  objective_tags= []
  false_or_partial = (truth < 0.5)

Use get_rumor(key) or list_rumors(category=..., floor=..., source=..., tags=...)
to read with defaults applied. Direct access to RUMOR_TEMPLATES is still
supported but bypasses defaults.

Buckets are by category so the engine can ask for a specific kind:
  floor_hint    — about the floor layout / shortcut / hazards
  boss_hint     — about a floor boss
  class_hint    — meta hint nudging toward a class affinity
  objective_hint— about reaching the floor exit
  npc_hint      — about a specific crawler/NPC
  false_or_biased — deliberately wrong or self-serving info
"""

RUMOR_DEFAULTS = {
    "tags": [], "weight": 1, "floor_min": 1, "floor_max": 5,
    "source_types": ["npc_dialogue", "rumor", "graffiti"],
    "objective_tags": [],
}


def _with_defaults(category: str, rumor: dict) -> dict:
    """Return rumor with category injected and missing fields filled in."""
    merged = dict(RUMOR_DEFAULTS)
    merged.update(rumor)
    merged["category"] = category
    truth = float(merged.get("truth", 0.5))
    merged.setdefault("reliability", truth)
    merged.setdefault("false_or_partial", truth < 0.5)
    return merged


def get_rumor(key: str):
    """Lookup by stable key; applies defaults."""
    for cat, items in RUMOR_TEMPLATES.items():
        for r in items:
            if r.get("key") == key:
                return _with_defaults(cat, r)
    return None


def list_rumors(category=None, floor=None, source=None, tags=None):
    """Filter rumors by category, floor range, source type, or tag overlap.
    Returns a flat list of enriched dicts."""
    out = []
    for cat, items in RUMOR_TEMPLATES.items():
        if category and cat != category:
            continue
        for r in items:
            enriched = _with_defaults(cat, r)
            if floor is not None:
                if not (enriched["floor_min"] <= floor <= enriched["floor_max"]):
                    continue
            if source and source not in enriched["source_types"]:
                continue
            if tags:
                rumor_tag_pool = set(enriched.get("tags", []) +
                                     enriched.get("reveals_tags", []) +
                                     enriched.get("objective_tags", []))
                if not any(t in rumor_tag_pool for t in tags):
                    continue
            out.append(enriched)
    return out

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
    # Post-07b follow-up: high-truth, partial-info rumors per major
    # objective tag. Truth ≥ 0.9 — each one nudges the player toward a real
    # solution path without spelling it out.
    "objective_high_truth": [
        {
            "key": "power_panel_b2_overstocked",
            "truth": 0.92,
            "text": "Technik przy bufecie wspomina, że panel B2 ciągnie więcej kabla niż wynika ze schematu. Nie wyjaśnia, dlaczego sam go sprawdzał.",
            "tags": ["power","cable","control_panel"],
            "reveals_tags": ["panel_b2_overstocked"],
            "objective_tags": ["power","cable","control_panel"],
        },
        {
            "key": "elevator_service_code_pattern",
            "truth": 0.95,
            "text": "Stary serwisant kiwa głową: 'Hasła do windy są trzyznakowe. Pierwsze litery zwykle JZD, reszta cyfra. Nie wymyśliłem tego.'",
            "tags": ["elevator","password","service"],
            "reveals_tags": ["service_code_pattern"],
            "objective_tags": ["elevator","exit","locked_door"],
        },
        {
            "key": "maintenance_window_office_floor",
            "truth": 0.93,
            "text": "Crawlerka liczy na palcach: 'Między czternastą a czternastą dwadzieścia patrol omija biurowy poziom. To nie tajemnica, to harmonogram.'",
            "tags": ["maintenance","patrol","timing"],
            "reveals_tags": ["patrol_window_known"],
            "objective_tags": ["maintenance","secret_route"],
        },
        {
            "key": "machine_handshake_three_bytes",
            "truth": 0.91,
            "text": "Z logów konsoli sączy się szczegół: maszyny piętra czekają na trzy bajty powitalne. Bez nich uznają cię za sygnał zewnętrzny.",
            "tags": ["machine","protocol","handshake"],
            "reveals_tags": ["machine_protocol_known"],
            "objective_tags": ["machine","control_panel"],
        },
        {
            "key": "safehouse_cafe_rule_loud",
            "truth": 0.97,
            "text": "Barista wyciera ladę: 'Po cichu się nie kradnie. Po głośnym — można. To nie etyka, to logika lokalu.'",
            "tags": ["safehouse","cafe","rule"],
            "reveals_tags": ["safehouse_cafe_rule_known"],
            "objective_tags": ["safehouse"],
        },
        {
            "key": "keycard_dropbox_under_vending",
            "truth": 0.9,
            "text": "Kurierka rzuca przelotnie: 'Karty wymieniają pod automatem z kawą. Komendant nigdy tam nie patrzy. Komendant lubi automat.'",
            "tags": ["keycard","drop_point","cafe"],
            "reveals_tags": ["keycard_dropbox_location"],
            "objective_tags": ["keycard","cafe"],
        },
        {
            "key": "chemical_neutral_3_to_1",
            "truth": 0.92,
            "text": "Z protokołu BHP wynika, że kwas neutralizuje się solą i sodą — proporcja trzy do jednego. Reszta to historia chemii.",
            "tags": ["chemical","lab","crafting"],
            "reveals_tags": ["chemical_neutralizer_known"],
            "objective_tags": ["chemical","lab"],
        },
        {
            "key": "boss_water_slows_warden",
            "truth": 0.9,
            "text": "Crawler z bandażem dorzuca: 'Strażnik wolniej kręci głową na mokrym. Sprawdziłem dwa razy. Trzeci raz mnie kosztował.'",
            "tags": ["boss","weakness","environment","water"],
            "reveals_tags": ["boss_weakness_water"],
            "objective_tags": ["boss"],
        },
        {
            "key": "secret_route_storage_shelf",
            "truth": 0.91,
            "text": "Sprzątacz pokazuje pustym kursorem: trzeci regał od końca w magazynie przesuwa się w prawo. 'Nie ja to wymyśliłem, ja tylko sprzątam.'",
            "tags": ["storage","secret_route","hidden"],
            "reveals_tags": ["secret_route_storage_known"],
            "objective_tags": ["secret_route"],
        },
        {
            "key": "crawler_dispute_warden_market",
            "truth": 0.9,
            "text": "Handlarz mówi cicho: 'Strażnik wziął zaliczkę i nie oddał. Wystarczy przypomnieć obu, że to wystarczy.'",
            "tags": ["faction","warden","black_market","social"],
            "reveals_tags": ["faction_dispute_known"],
            "objective_tags": ["faction","boss"],
        },
    ],
}
