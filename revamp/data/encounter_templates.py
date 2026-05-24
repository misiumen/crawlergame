"""Encounter templates for CRAWL PROTOCOL revamp.

These are content-level templates, not full engine logic.
"""

ENCOUNTER_TEMPLATES = {
    "wounded_crawler_in_hall": {
        "type": "wounded_crawler",
        "weight": 8,
        "floor_min": 1,
        "tags": ["crawler", "social", "risk", "information"],
        "fallback_title": "Ranny crawler przy ścianie",
        "intro": [
            "Pod ścianą siedzi crawler, trzymając obie ręce na brzuchu. Między palcami sączy się ciemna krew, a jego oczy śledzą cię z wyuczoną nieufnością.",
            "Ktoś zostawił za sobą smugę krwi. Kończy się przy crawlerze, który próbuje nie oddychać zbyt głośno."
        ],
        "participants": ["crawler"],
        "possible_resolutions": {
            "help": {"stat": "WIS", "dc": 10, "time": 20, "effects": ["relationship_up", "rumor", "minor_xp"]},
            "rob": {"stat": "DEX", "dc": 13, "time": 5, "effects": ["loot", "relationship_down", "audience_down"]},
            "kill": {"stat": "STR", "dc": 8, "time": 3, "effects": ["loot", "reputation_down", "possible_future_retaliation"]},
            "ignore": {"time": 1, "effects": ["none_or_minor_guilt"]},
            "talk": {"stat": "CHA", "dc": 9, "time": 10, "effects": ["rumor", "relationship_small_up"]}
        },
        "partial_success": [
            "Pomagasz mu, ale zużywasz więcej materiałów niż chciałeś.",
            "Dostajesz plotkę, ale nie jesteś pewien, czy mówi z bólu, czy z rozsądku."
        ],
        "failure": [
            "Crawler odsuwa się od ciebie jak od kolejnej pułapki.",
            "Twoja pomoc pogarsza sprawę. System taktownie przybliża kamerę."
        ],
        "narrator_hooks": ["crawler_helped", "crawler_robbed", "crawler_ignored"]
    },

    "monster_feeding": {
        "type": "hostile_monster",
        "weight": 7,
        "floor_min": 1,
        "tags": ["monster", "avoidance", "environment"],
        "fallback_title": "Potwór przy żerowisku",
        "intro": [
            "Coś dużego klęczy nad resztkami, których lepiej nie identyfikować. Dźwięk żucia jest mokry, spokojny i obraźliwie pewny siebie.",
            "Stwór nie zauważył cię od razu. Na razie liczy się dla niego tylko ciało rozsmarowane po kafelkach."
        ],
        "participants": ["monster"],
        "possible_resolutions": {
            "fight": {"stat": "STR", "dc": 12, "time": 5, "effects": ["combat"]},
            "sneak": {"stat": "DEX", "dc": 12, "time": 10, "effects": ["bypass", "stealth_affinity"]},
            "throw_bait": {"requires_item_tag": "food", "stat": "WIS", "dc": 9, "time": 3, "effects": ["bypass", "lose_item"]},
            "use_environment": {"requires_environment": True, "stat": "INT", "dc": 11, "time": 5, "effects": ["damage_or_disable", "environment_affinity"]},
            "wait": {"time": 40, "effects": ["monster_may_leave", "time_passes"]}
        }
    },

    "loot_conflict_crawler": {
        "type": "loot_conflict",
        "weight": 6,
        "floor_min": 1,
        "tags": ["crawler", "loot", "social"],
        "fallback_title": "Spór o skrzynkę",
        "intro": [
            "Przy skrzynce klęczy inny crawler. Jedną ręką trzyma łom, drugą osłania zamek, jakby skrzynka była dzieckiem, którego jeszcze nie zdążył nazwać.",
            "Ktoś już znalazł loot. Niestety, wciąż żyje."
        ],
        "participants": ["crawler", "container"],
        "possible_resolutions": {
            "negotiate_split": {"stat": "CHA", "dc": 11, "time": 15, "effects": ["shared_loot", "relationship_up"]},
            "threaten": {"stat": "CHA", "dc": 13, "time": 5, "effects": ["loot_or_combat", "audience_up"]},
            "attack": {"stat": "STR", "dc": 10, "time": 4, "effects": ["combat_crawler"]},
            "trick": {"stat": "INT", "dc": 12, "time": 10, "effects": ["loot", "relationship_down"]},
            "walk_away": {"time": 1, "effects": ["none"]}
        }
    },

    "ambush_in_dark": {
        "type": "hostile_monster",
        "weight": 4,
        "floor_min": 1,
        "tags": ["monster", "stealth", "darkness", "avoidance"],
        "fallback_title": "Coś czeka w ciemności",
        "intro": [
            "Latarka mruga raz, dwa razy, i wtedy widzisz, że nie patrzysz na ścianę — patrzysz na coś, co stoi nieruchomo, bo wie, że jeszcze nie musi się ruszać.",
            "W ciemności słychać własny oddech wracający odbiciem od cudzych zębów.",
        ],
        "participants": ["monster"],
        "possible_resolutions": {
            "fight": {"stat": "STR", "dc": 13, "time": 6, "effects": ["combat"]},
            "sneak_past": {"stat": "DEX", "dc": 13, "time": 8, "effects": ["bypass", "stealth_affinity"]},
            "blind_with_light": {"requires_item_tag": "light", "stat": "DEX", "dc": 10, "time": 2, "effects": ["disable_temporary"]},
            "throw_decoy": {"requires_item_tag": "throwable", "stat": "DEX", "dc": 11, "time": 3, "effects": ["bypass", "lose_item"]},
            "back_off": {"time": 2, "effects": ["retreat"]},
        },
        "partial_success": [
            "Mijasz go bokiem, ale słyszy uderzenie twojego pulsu szybciej niż twoje kroki.",
        ],
        "failure": [
            "Patrzysz mu w oczy. To był błąd, ale przynajmniej krótki.",
        ],
    },

    "merchant_haggle_blocked": {
        "type": "social_obstacle",
        "weight": 5,
        "floor_min": 1,
        "tags": ["crawler", "social", "negotiation", "trade", "non_combat"],
        "fallback_title": "Handlarz blokuje przejście",
        "intro": [
            "Crawler ustawił skrzynki w poprzek korytarza i robi za sklep. Z uśmiechem, który mówi: 'opłata albo wycena.'",
            "Pod ścianą leży tabliczka: PRZEJŚCIE = 30 cr LUB ZWROT. Z dopiskiem: 'ZWROTÓW NIE PRZYJMUJEMY.'",
        ],
        "participants": ["crawler"],
        "possible_resolutions": {
            "pay": {"requires_credits": 30, "time": 5, "effects": ["pass", "lose_credits"]},
            "haggle": {"stat": "CHA", "dc": 12, "time": 8, "effects": ["pass", "diplomacy_affinity"]},
            "intimidate": {"stat": "CHA", "dc": 13, "time": 3, "effects": ["pass", "audience_up", "relationship_down"]},
            "trade_info": {"requires_rumor": True, "stat": "WIS", "dc": 10, "time": 5, "effects": ["pass", "relationship_up"]},
            "force_through": {"stat": "STR", "dc": 14, "time": 4, "effects": ["combat_crawler"]},
            "go_around": {"time": 15, "effects": ["long_detour", "time_passes"]},
        },
        "partial_success": [
            "Przepuszcza cię, ale notuje twoją twarz i cenę następnego razu.",
        ],
        "failure": [
            "Sprzedawca uśmiecha się szerzej. To rzadko jest sygnał sukcesu.",
        ],
    },

    "terminal_locked_exit": {
        "type": "blocked_path",
        "weight": 5,
        "floor_min": 1,
        "tags": ["terminal", "locked", "information"],
        "fallback_title": "Terminal przy zamkniętym przejściu",
        "intro": [
            "Drzwi nie mają klamki. Mają za to terminal, który mruga komunikatem: AUTORYZACJA W TOKU OD 17 LAT.",
            "Obok drzwi wisi ekran. Ktoś wydrapał pod nim: 'Hasło jest w kawie. Albo we krwi. Nie pamiętam.'"
        ],
        "participants": ["terminal", "locked_door"],
        "possible_resolutions": {
            "hack": {"stat": "INT", "dc": 13, "time": 30, "effects": ["unlock", "tech_affinity"]},
            "find_password": {"requires_rumor": True, "time": 5, "effects": ["unlock"]},
            "force": {"stat": "STR", "dc": 16, "time": 20, "effects": ["unlock_or_noise"]},
            "bribe_npc": {"requires_npc": True, "stat": "CHA", "dc": 11, "time": 20, "effects": ["unlock", "lose_credits"]},
            "leave": {"time": 1, "effects": ["none"]}
        }
    },
}
