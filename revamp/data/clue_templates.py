"""Clue templates — partial information chains.

A clue is a small revelation that points the player toward the next step
without solving anything. Chains are explicit: clue A says where to find
clue B, clue B unlocks an objective path.

Schema per clue:
  key            -- stable ASCII id
  source         -- "rumor" | "terminal" | "graffiti" | "corpse_note" | "npc_dialogue" | "lore_fragment"
  text           -- Polish line shown to the player
  reveals        -- list of stable tags the player now "knows"
  unlocks_chain  -- (optional) key of the next clue this one points to
  enables_paths  -- (optional) list of objective_solution_path keys
                    that become available when this clue is known

Engine usage:
  - When emitted, the clue's `reveals` tags are added to a player-side
    "known_facts" set on Character (TBD; for now `Character.flags["known_clues"]`).
  - When picking an encounter resolution, the validator may consult the
    player's known_facts to widen `possible_resolutions`.

Clues compose with rumors — a rumor can be the *source* of a clue but
clues are stronger: their `reveals` tags are treated as factual by the
validator, even if the rumor that delivered them had `truth < 1.0`.

Defaults applied to every clue at lookup time (via get_clue) when the
field is missing:
  weight       = 1
  floor_min    = 1
  floor_max    = 5
  tags         = []
  risks        = []
  rewards      = ["partial_information"]
"""

CLUE_DEFAULTS = {
    "weight": 1, "floor_min": 1, "floor_max": 5,
    "tags": [], "risks": [], "rewards": ["partial_information"],
    "requires_clues": [],          # prerequisite clue keys (sequence support)
    "can_skip_sequence": False,    # if True, this clue is always revealable
    # Prompt 07b additions:
    "reliability": 1.0,            # 0..1, like rumor truth
    "possible_sources": [],        # rooms/entities that can yield it
    "related_objective_tags": [],  # objective tags this clue helps with
    "false_variant_chance": 0.0,   # 0..1; if rolled, deliver a distorted version
    "title_pl": "",
    "title_en": "",
    "text_pl": "",
    "text_en": "",
}

CLUE_TEMPLATES = {
    # ── Keycard chain (for the find_keycard objective) ──────────────────────
    "keycard_chain_start": {
        "source": "rumor",
        "text": "Karta dostępu Strażnika krąży po piętrze. Trzy razy widziano ją "
                "w okolicy kafejki, raz w schowku serwisowym, raz pod ladą u handlarza.",
        "reveals": ["keycard_in_circulation"],
        "unlocks_chain": "keycard_chain_locations",
        "enables_paths": [],
    },
    "keycard_chain_locations": {
        "source": "graffiti",
        "text": "Na ścianie obok wentylatora wydrapane: 'Karta = czerwona z napisem "
                "KONTRAKTOR. Schowek za biurem albo Bezparagonu. Nie u ochroniarzy. "
                "Już nie.'",
        "reveals": ["keycard_in_maintenance", "keycard_in_blackmarket",
                    "keycard_color_red"],
        "enables_paths": ["loot_corpse", "black_market", "steal"],
        "requires_clues": ["keycard_chain_start"],
    },

    "warden_pattern": {
        "source": "terminal",
        "text": "Log dyżurów strażnika: '04:00-12:00 — relay. 12:00-20:00 — przerwa. "
                "20:00-04:00 — patrol korytarza A.' Aktualna godzina mruga.",
        "reveals": ["warden_schedule_known"],
        "enables_paths": ["bypass_during_break", "sneak_during_patrol"],
    },

    "boss_weakness_noise": {
        "source": "corpse_note",
        "text": "Na ciele crawlera notatka, jakby spisana na kolanie: 'Boss nie "
                "atakuje, gdy wszyscy krzyczą. Hałas mu się podoba. Ja krzyczałem.'",
        "reveals": ["boss_pacified_by_noise"],
        "enables_paths": ["lure_boss_away"],
    },

    "freezer_silent_kill": {
        "source": "npc_dialogue",
        "text": "Stary technik: 'Rzeźnik z Zamrażarki nie zaatakuje, jak nie usłyszy "
                "twojego oddechu. Wstrzymaj go. Albo nie wchodź.'",
        "reveals": ["carver_pacified_by_silence"],
        "enables_paths": ["sneak_past"],
    },

    "acid_pool_metal": {
        "source": "lore_fragment",
        "text": "Zaszyte w protokole bezpieczeństwa: 'Kwas reaguje z metalem trzykrotnie "
                "szybciej niż z tkanką. Stąd to nie jest zalecane jako broń, ALE...'",
        "reveals": ["acid_eats_metal"],
        "enables_paths": ["use_environment"],
    },

    "vent_shortcut_path": {
        "source": "graffiti",
        "text": "Wydrapane na lustrze w łazience: 'Krata w suficie prowadzi do biura. "
                "Biuro ma klucz do relay. Reszta — w twoich rękach.'",
        "reveals": ["vent_to_office", "office_has_keycard"],
        "enables_paths": ["secret_route"],
    },

    "merchant_password": {
        "source": "npc_dialogue",
        "text": "Barista, ściszonym głosem: 'Powiedz handlarzowi: «szyba boli». Wtedy "
                "pokaże ci to, czego oficjalnie nie ma.'",
        "reveals": ["blackmarket_password_known"],
        "enables_paths": ["black_market", "trade_info"],
    },

    # ── Prompt 07b additions ────────────────────────────────────────────────
    # Each new clue declares title_pl/text_pl + possible_sources +
    # related_objective_tags so the rumor-side biaser and the validator can
    # both reason about them.

    "service_password_elevator": {
        "source": "terminal",
        "title_pl": "Hasło serwisowe windy",
        "title_en": "Service password for the elevator",
        "text_pl": "Z poszarpanej notatki wynika, że panel windy przyjmuje krótkie "
                   "hasła serwisowe. Jedno z nich ktoś dopisał tłustym markerem: JAZDA-0.",
        "text_en": "A torn note says the elevator panel accepts short service codes. "
                   "Someone wrote one in marker: JAZDA-0.",
        "reveals": ["elevator_password_known", "service_code_pattern"],
        "enables_paths": ["use_password", "service_route"],
        "tags": ["password", "elevator", "service"],
        "related_objective_tags": ["exit", "elevator", "locked_door"],
        "possible_sources": ["terminal", "graffiti"],
        "reliability": 0.85,
    },
    "machine_protocol_handshake": {
        "source": "terminal",
        "title_pl": "Protokół powitalny maszyn",
        "title_en": "Machine handshake protocol",
        "text_pl": "Log z konsoli: maszyny piętra czekają na pakiet powitalny "
                   "z trzema bajtami. Brak pakietu — wezmą cię za sygnał zewnętrzny.",
        "text_en": "Console log: floor machines expect a 3-byte handshake. Without it, "
                   "they treat you as an external signal.",
        "reveals": ["machine_protocol_known"],
        "enables_paths": ["logic_exploit", "use_password"],
        "tags": ["machine", "protocol", "technical"],
        "related_objective_tags": ["machine", "control_panel"],
        "possible_sources": ["terminal"],
        "reliability": 0.9,
    },
    "boss_weakness_water": {
        "source": "corpse_note",
        "title_pl": "Słabość bossa: woda",
        "title_en": "Boss weakness: water",
        "text_pl": "Crawler trzymał w dłoni rozmokłą kartkę: 'Strażnik nie wytrzymuje "
                   "wilgoci. Mokre podłoże = wolniejsze obroty głowy. Sprawdziłem dwa razy. "
                   "Trzeci raz mnie kosztował.'",
        "text_en": "A crawler held a soaked note: 'The Warden can't handle moisture. "
                   "Wet floor = slower turning. I checked twice. The third try cost me.'",
        "reveals": ["boss_weakness_water"],
        "enables_paths": ["exploit_weakness", "use_environment", "lure_to_specific_object"],
        "tags": ["boss", "weakness", "environment"],
        "related_objective_tags": ["boss"],
        "possible_sources": ["corpse_note", "rumor"],
        "reliability": 0.85,
    },
    "maintenance_cycle_office": {
        "source": "terminal",
        "title_pl": "Rytm patroli serwisowych",
        "title_en": "Maintenance patrol rhythm",
        "text_pl": "Zauważasz rytm patroli. To nie jest bezpieczeństwo, to rozkład jazdy. "
                   "Pomiędzy 14:00 a 14:20 nikt nie wchodzi na poziom biura.",
        "text_en": "You notice a rhythm to the patrols. It's not security — it's a "
                   "schedule. Between 14:00 and 14:20 no one enters the office level.",
        "reveals": ["patrol_window_known"],
        "enables_paths": ["wait_for_cycle", "bypass_during_break"],
        "tags": ["patrol", "maintenance", "timing"],
        "related_objective_tags": ["maintenance", "secret_route"],
        "possible_sources": ["terminal", "graffiti"],
        "reliability": 0.8,
    },
    "keycard_dropbox": {
        "source": "graffiti",
        "title_pl": "Skrzynka z kartami",
        "title_en": "Keycard drop box",
        "text_pl": "Pod automatem z kawą ktoś zostawił wiadomość: 'Karta zamiast napiwku. "
                   "Włóż tu, weź stamtąd. Komendant nigdy nie zaglądał pod swój automat.'",
        "text_en": "Under the coffee machine: 'Card instead of tip. Drop here, take from "
                   "there. The chief never looked under his own vending machine.'",
        "reveals": ["keycard_dropbox_location"],
        "enables_paths": ["search_dropbox", "steal"],
        "tags": ["keycard", "drop_point", "cafe"],
        "related_objective_tags": ["keycard", "cafe"],
        "possible_sources": ["graffiti", "rumor"],
        "reliability": 0.7,
    },
    "power_reroute_cable": {
        "source": "lore_fragment",
        "title_pl": "Obejście zasilania",
        "title_en": "Power reroute",
        "text_pl": "Schemat na blasze obok rozdzielni: 'Czerwony do żółtego — relay milknie. "
                   "Żółty do zielonego — kamery śpią. Cokolwiek do niebieskiego — uciekaj.'",
        "text_en": "A diagram next to the panel: 'Red to yellow — relay quiets. Yellow to "
                   "green — cameras sleep. Anything to blue — run.'",
        "reveals": ["cable_reroute_known"],
        "enables_paths": ["reroute_power", "disable_panel", "repair_panel"],
        "tags": ["power", "cable", "control_panel", "panel"],
        "related_objective_tags": ["power", "control_panel", "cable"],
        "possible_sources": ["lore_fragment", "terminal"],
        "reliability": 0.95,
    },
    "camera_blindspot_corner": {
        "source": "rumor",
        "title_pl": "Martwy kąt kamery",
        "title_en": "Camera blind spot",
        "text_pl": "Streamerka z safehouse pokazuje pustym kursorem na ekranie: 'Tu, w "
                   "prawym dolnym rogu kafelka, kamera nie widzi. Bo nie chce.'",
        "text_en": "A streamer in the safehouse points an empty cursor at the screen: "
                   "'Right here, lower right corner — the camera can't see. Won't.'",
        "false_variant_pl": "Streamerka pokazuje na ekranie róg, ale przy każdym ujęciu trafia "
                            "w inny róg. Może to po prostu kafelki tak drgają.",
        "reveals": ["camera_blindspot_known"],
        "enables_paths": ["sneak_past", "stage_action_offscreen"],
        "tags": ["camera", "sponsor", "stealth"],
        "related_objective_tags": ["camera", "sponsor"],
        "possible_sources": ["rumor", "npc_dialogue"],
        "reliability": 0.7,
        "false_variant_chance": 0.25,
    },
    "faction_dispute_warden_blackmarket": {
        "source": "npc_dialogue",
        "title_pl": "Strażnik kontra czarny rynek",
        "title_en": "Warden vs. black market",
        "text_pl": "Handlarz mówi cicho: 'Strażnik wziął im zaliczkę i nie oddał. Teraz "
                   "biorą u kogo innego. Wystarczy przypomnieć obu, że to wystarczy.'",
        "text_en": "Merchant, quietly: 'Warden took an advance from them and never paid "
                   "back. They source elsewhere now. Just remind both that's enough.'",
        "reveals": ["faction_dispute_known"],
        "enables_paths": ["sow_distrust", "reveal_secret", "blackmail"],
        "tags": ["faction", "warden", "black_market", "social"],
        "related_objective_tags": ["boss", "faction"],
        "possible_sources": ["npc_dialogue", "rumor"],
        "reliability": 0.75,
    },
    "safehouse_rule_cafe": {
        "source": "npc_dialogue",
        "title_pl": "Zasada kawiarni",
        "title_en": "Cafe rule",
        "text_pl": "Barista wyciera ladę i mówi mimochodem: 'Niczego się nie rusza po cichu. "
                   "Po głośnym — można. Logika lokalu.'",
        "text_en": "The barista wipes the counter and says, casually: 'You don't take "
                   "anything quietly. Loudly is fine. House logic.'",
        "reveals": ["safehouse_cafe_rule_known"],
        "enables_paths": ["loud_purchase"],
        "tags": ["safehouse", "cafe", "social_rule"],
        "related_objective_tags": ["safehouse"],
        "possible_sources": ["npc_dialogue"],
        "reliability": 0.95,
    },
    "chemical_neutralizer_recipe": {
        "source": "lore_fragment",
        "title_pl": "Neutralizator chemiczny",
        "title_en": "Chemical neutralizer",
        "text_pl": "Wyrwana strona protokołu: 'Kwas neutralizuje się solą i sodą — proporcja "
                   "trzy do jednego. Sól z kuchni, soda z apteczki. Reszta to chemia '92.'",
        "text_en": "A torn protocol page: 'Acid neutralizes with salt and soda — three to "
                   "one. Salt from kitchen, soda from medkit. The rest is '92 chemistry.'",
        "reveals": ["chemical_neutralizer_known"],
        "enables_paths": ["craft_neutralizer", "safe_passage_acid"],
        "tags": ["chemical", "lab", "crafting"],
        "related_objective_tags": ["chemical", "lab"],
        "possible_sources": ["lore_fragment"],
        "reliability": 0.9,
    },
    "bathroom_oddity_haunt": {
        "source": "graffiti",
        "title_pl": "Łazienka chodzi",
        "title_en": "The bathroom moves",
        "text_pl": "Coraz więcej kresek dopisanych obok zwierciadła. Pod ostatnim podpisem: "
                   "'Trzecia kabina przekręca głowę. Tylko trzecia. Sprawdzone.'",
        "text_en": "More marks every day around the mirror. Under the last one: 'Third "
                   "stall turns your head. Only the third. Checked.'",
        "false_variant_pl": "Pod lustrem inny pismem dopisano: 'Pierwsza kabina przekręca "
                            "głowę. Druga zostawia w spokoju. Czwarta to dyskusja.' Pewności "
                            "brak, kresek dużo.",
        "reveals": ["bathroom_anomaly_known"],
        "enables_paths": ["invoke_belief", "create_taboo"],
        "tags": ["bathroom", "anomaly", "social"],
        "related_objective_tags": ["bathroom"],
        "possible_sources": ["graffiti", "rumor"],
        "reliability": 0.55,
        "false_variant_chance": 0.3,
    },
    "sponsor_manipulation_clip": {
        "source": "terminal",
        "title_pl": "Manipulacja sponsora",
        "title_en": "Sponsor edit",
        "text_pl": "W rankingu pojawia się ten sam klip dwa razy z różnym podpisem. Treść "
                   "ta sama. Wniosek: ktoś tnie pod komentarz.",
        "text_en": "The ranking shows the same clip twice with different captions. The "
                   "footage is identical. Someone edits the framing.",
        "reveals": ["sponsor_edits_visible"],
        "enables_paths": ["sponsor_disinformation", "forge_social_proof"],
        "tags": ["sponsor", "broadcast", "propaganda"],
        "related_objective_tags": ["sponsor"],
        "possible_sources": ["terminal", "rumor"],
        "reliability": 0.95,
    },
    "salvage_opportunity_panel": {
        "source": "graffiti",
        "title_pl": "Panel pełen kabli",
        "title_en": "Cable-rich panel",
        "text_pl": "Strzałka na ścianie, opisana drobiazgowo: 'Panel B2 ma dwa razy więcej "
                   "kabli niż wynika ze schematu. Nikt nie pyta, czyje.'",
        "text_en": "An arrow on the wall, annotated: 'Panel B2 carries twice the cable the "
                   "schematic shows. Nobody asks whose.'",
        "reveals": ["panel_b2_overstocked"],
        "enables_paths": ["salvage_panel"],
        "tags": ["salvage", "panel", "cable"],
        "related_objective_tags": ["cable", "control_panel"],
        "possible_sources": ["graffiti"],
        "reliability": 0.7,
    },
    "memetic_belief_propagation": {
        "source": "rumor",
        "title_pl": "Plotka, która się sama opowiada",
        "title_en": "A self-repeating rumor",
        "text_pl": "Słyszysz w dwóch różnych pokojach to samo zdanie, z dwóch różnych ust. "
                   "Drugie mu już zmieniło sens. Pierwsze nie wie.",
        "text_en": "You hear the same line in two different rooms, from two different "
                   "mouths. The second has already shifted its meaning. The first doesn't know.",
        "false_variant_pl": "Słyszysz w dwóch różnych pokojach dwie różne wersje tej samej plotki. "
                            "Nie potrafisz powiedzieć, która z nich była pierwsza, ani której rozsądniej "
                            "wierzyć.",
        "reveals": ["belief_seed_propagating"],
        "enables_paths": ["invoke_belief"],
        "tags": ["memetic", "social", "broadcast"],
        "related_objective_tags": ["social", "faction"],
        "possible_sources": ["rumor", "npc_dialogue"],
        "reliability": 0.6,
        "false_variant_chance": 0.25,
    },
    "machine_logic_loop_clue": {
        "source": "terminal",
        "title_pl": "Pętla decyzyjna maszyny",
        "title_en": "Machine decision loop",
        "text_pl": "Z logu wynika, że dron nie potrafi wybrać między dwoma celami o tej "
                   "samej priorytecie. Czeka. Czeka długo. Wystarczy mu dać drugi powód.",
        "text_en": "The log shows a drone can't pick between two same-priority targets. "
                   "It waits. Long. Just give it a second reason.",
        "reveals": ["machine_logic_loop_known"],
        "enables_paths": ["logic_exploit", "target_priority_shift"],
        "tags": ["machine", "ai", "exploit"],
        "related_objective_tags": ["machine"],
        "possible_sources": ["terminal"],
        "reliability": 0.85,
    },
    "secret_route_storage": {
        "source": "graffiti",
        "title_pl": "Wejście serwisowe za regałami",
        "title_en": "Service entry behind shelves",
        "text_pl": "Wydrapane na ścianie magazynu: 'Trzeci regał od końca przesuwa się "
                   "w prawo. Sam tego nie wymyśliłem.'",
        "text_en": "Scratched on the storage wall: 'Third shelf from the end slides right. "
                   "I didn't make this up.'",
        "reveals": ["secret_route_storage_known"],
        "enables_paths": ["secret_route", "use_crawlspace"],
        "tags": ["storage", "secret_route", "hidden"],
        "related_objective_tags": ["secret_route"],
        "possible_sources": ["graffiti"],
        "reliability": 0.8,
    },
    "false_lead_boss_food": {
        "source": "rumor",
        "title_pl": "Strażnik je za kasą",
        "title_en": "Warden eats by the counter",
        "text_pl": "Pijany crawler zarzeka się, że Strażnik wraca codziennie po jedzenie "
                   "za kasę kawiarni. Nikt nigdy go tam nie widział.",
        "text_en": "A drunk crawler swears the Warden returns daily for food behind the "
                   "cafe counter. No one has ever seen him there.",
        "reveals": ["boss_food_pattern_false"],
        "enables_paths": [],
        "tags": ["boss", "false"],
        "related_objective_tags": ["boss"],
        "possible_sources": ["rumor"],
        "reliability": 0.15,
        "false_variant_chance": 0.0,   # already a false lead
    },
}


def all_clue_keys():
    return list(CLUE_TEMPLATES.keys())


def get_clue(key: str):
    """Return clue dict with CLUE_DEFAULTS layered in for missing fields."""
    c = CLUE_TEMPLATES.get(key)
    if c is None:
        return None
    merged = dict(CLUE_DEFAULTS)
    merged.update(c)
    # Ensure key always present
    merged["key"] = key
    return merged


def clues_unlocking_path(path_key: str):
    """Reverse-lookup: which clues enable the given solution path."""
    return [c for c in CLUE_TEMPLATES.values()
            if path_key in c.get("enables_paths", [])]
