"""Encounter templates for Dungeon Kraulem.

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

    # ── P29.45 — 15 nowych encounterów. Każdy ma weight, floor_min,
    # tags (czasem biom) i co najmniej 2-3 resolution paths. Styl
    # Dinnimana: krótkie zdania, brudna ironia, sponsorzy w tle.

    "crawler_marketer": {
        "type": "social_obstacle",
        "weight": 5,
        "floor_min": 2,
        "tags": ["crawler","social","trade","sponsor"],
        "fallback_title": "Crawler-handlowiec",
        "intro": [
            "Pod ścianą stoi crawler z kartką na sznurku: KUPUJĘ "
            "POLECENIA SPONSORÓW. PŁACĘ. Druga kartka pod nią: "
            "PŁACĘ MAŁO ALE PŁACĘ.",
            "Ktoś rozłożył na podłodze koc, na kocu kasety z reklamami. "
            "Pyta cię: „Jak ci leci ze sponsorami? Mogę kupić kontakt.”",
        ],
        "participants": ["crawler"],
        "possible_resolutions": {
            "sell_intel":  {"requires_rumor": True, "stat": "CHA",
                             "dc": 10, "time": 5,
                             "effects": ["credits_up","relationship_up"]},
            "buy_rumor":   {"requires_credits": 15, "time": 5,
                             "effects": ["rumor","lose_credits"]},
            "rob":         {"stat": "DEX", "dc": 13, "time": 4,
                             "effects": ["loot","relationship_down"]},
            "walk_away":   {"time": 1, "effects": ["none"]},
        },
    },

    "drone_crash": {
        "type": "loot_environment",
        "weight": 4,
        "floor_min": 3,
        "tags": ["loot","sponsor","environment","tech"],
        "fallback_title": "Rozbity dron sponsorski",
        "intro": [
            "Mały dron z logiem sponsora rozbił się o sufit i leży "
            "teraz na środku korytarza, mrugając z resztą sił. Z "
            "boku otwarty schowek — coś ze środka wystaje.",
            "Dron sponsorski w rozsypce. Śmigła krzywe, kamera pęknięta, "
            "schowek otwarty. Reklama wciąż leci z głośnika.",
        ],
        "participants": ["container"],
        "possible_resolutions": {
            "loot_quick":   {"stat": "DEX", "dc": 9, "time": 2,
                              "effects": ["loot","audience_down"]},
            "salvage_tech": {"stat": "INT", "dc": 11, "time": 6,
                              "effects": ["materials","tech_affinity"]},
            "disable_first":{"stat": "INT", "dc": 12, "time": 4,
                              "effects": ["safe_loot","audience_up"]},
            "ignore":       {"time": 0, "effects": ["none"]},
        },
    },

    "two_monsters_fighting": {
        "type": "environment_choice",
        "weight": 5,
        "floor_min": 3,
        "tags": ["monster","environment","avoidance","tactical"],
        "fallback_title": "Dwa potwory się biją",
        "intro": [
            "W głębi korytarza dwa potwory robią coś, co sponsor "
            "nazwałby „treścią premiującą”. Na razie się nie zauważyły, "
            "bo bardzo się sobą zajęły.",
            "Walczą zaciekle. Sponsor zrzuci ci pud, jeśli któregoś "
            "skończysz — albo i obu, jeśli przejdziesz obok bez "
            "interwencji.",
        ],
        "participants": ["monster","monster"],
        "possible_resolutions": {
            "sneak_past":    {"stat": "DEX", "dc": 11, "time": 4,
                               "effects": ["bypass","stealth_affinity"]},
            "finish_winner": {"stat": "STR", "dc": 13, "time": 6,
                               "effects": ["combat","audience_up","double_kill"]},
            "throw_explosive":{"requires_item_tag": "explosive",
                               "stat": "DEX", "dc": 11, "time": 3,
                               "effects": ["damage_or_disable","audience_up","lose_item"]},
            "wait":          {"time": 30, "effects": ["one_survives","time_passes"]},
        },
    },

    "dying_sponsor_pet": {
        "type": "social_choice",
        "weight": 3,
        "floor_min": 3,
        "tags": ["beast","sponsor","social","moral"],
        "fallback_title": "Konający pieskreator sponsora",
        "intro": [
            "Na podłodze leży coś, co kiedyś było pieskreatorem — "
            "maskotką jednego ze sponsorów. Dyszy. Patrzy. Ma "
            "obróżkę z mrugającą diodą.",
            "Pieskreator z reklamy. Brakuje mu łapy i godności. "
            "Diody w obróżce żebrzą o sygnał z drona.",
        ],
        "participants": ["beast"],
        "possible_resolutions": {
            "mercy_kill":    {"stat": "STR", "dc": 6, "time": 2,
                               "effects": ["audience_split","attention_sponsor_down"]},
            "carry_to_safe": {"stat": "CON", "dc": 11, "time": 15,
                               "effects": ["audience_up","sponsor_relationship_up"]},
            "harvest_chip":  {"stat": "INT", "dc": 10, "time": 5,
                               "effects": ["materials","attention_sponsor_down"]},
            "leave":         {"time": 0, "effects": ["audience_neutral"]},
        },
    },

    "audience_vote_humiliation": {
        "type": "sponsor_event",
        "weight": 3,
        "floor_min": 4,
        "tags": ["sponsor","audience","social","buff"],
        "fallback_title": "Widownia coś przegłosowała",
        "intro": [
            "Reflektor zapala się dokładnie nad tobą. Konferansjer "
            "z głośnika: „Widzowie chcą zobaczyć, jak nazywasz swoją "
            "matkę. Dziesięć sekund.”",
            "Ekran nad drzwiami pokazuje pasek z wynikami głosowania. "
            "Słupek rośnie z każdą sekundą. Jeśli przegrasz — "
            "pojawi się drugi pasek.",
        ],
        "participants": ["sponsor"],
        "possible_resolutions": {
            "comply":        {"time": 3,
                               "effects": ["audience_up_big","attention_konferansjer_up","status_humiliated"]},
            "refuse_loud":   {"stat": "CHA", "dc": 12, "time": 3,
                               "effects": ["audience_down","attention_konferansjer_down"]},
            "deflect_joke":  {"stat": "CHA", "dc": 14, "time": 4,
                               "effects": ["audience_up","relationship_neutral"]},
            "smash_screen":  {"stat": "STR", "dc": 10, "time": 2,
                               "effects": ["audience_split","sponsor_anger"]},
        },
    },

    "hanged_crawler": {
        "type": "lore_environment",
        "weight": 3,
        "floor_min": 5,
        "tags": ["crawler","corpse","lore","loot","horror"],
        "fallback_title": "Wisielec — list pożegnalny",
        "intro": [
            "Z sufitu zwisa crawler. Ciało spokojne, jakby ktoś go "
            "tu zostawił specjalnie po pracy. Pod butami leży kartka "
            "z paskiem od taśmy klejącej.",
            "Wisielec. Pod butami list. Pod listem coś jeszcze.",
        ],
        "participants": ["corpse","note"],
        "possible_resolutions": {
            "read_note":     {"time": 3,
                               "effects": ["rumor","lore","audience_neutral"]},
            "loot_body":     {"stat": "WIS", "dc": 8, "time": 4,
                               "effects": ["loot","audience_down"]},
            "cut_down":      {"stat": "STR", "dc": 8, "time": 5,
                               "effects": ["title_decent_person","audience_up"]},
            "ignore":        {"time": 0, "effects": ["none"]},
        },
    },

    "trapped_corpse_baited": {
        "type": "trap",
        "weight": 4,
        "floor_min": 4,
        "tags": ["trap","corpse","loot","risk"],
        "fallback_title": "Zwłoki z podpiętym ładunkiem",
        "intro": [
            "Ktoś dawno leży pośrodku pokoju. Wokół nadziewane "
            "kredyty, kawalątki sprzętu i — chyba — broń. Pod "
            "ciałem jakaś druga warstwa, której wolisz nie ruszać.",
            "Zwłoki w zbyt wygodnej pozie. Loot w zbyt równym kółku. "
            "To pułapka, ale loot jest dobry.",
        ],
        "participants": ["corpse","trap"],
        "possible_resolutions": {
            "spot_trap":     {"stat": "WIS", "dc": 13, "time": 3,
                               "effects": ["safe_loot","trap_intel"]},
            "disarm_trap":   {"stat": "INT", "dc": 14, "time": 8,
                               "effects": ["safe_loot","materials"]},
            "grab_fast":     {"stat": "DEX", "dc": 13, "time": 2,
                               "effects": ["loot_or_explosion"]},
            "leave":         {"time": 0, "effects": ["none"]},
        },
    },

    "propaganda_speaker": {
        "type": "environment_choice",
        "weight": 3,
        "floor_min": 4,
        "tags": ["sponsor","audio","social","environment"],
        "fallback_title": "Głośnik propagandowy",
        "intro": [
            "Z głośnika nad drzwiami leci spokojnym tonem propaganda "
            "Ministerstwa Pamięci. Każde zdanie zaczyna się od "
            "„Według naszych ustaleń”. Każde kończy się inaczej.",
            "Lektor czyta nazwiska, których nie ma w żadnej kartotece, "
            "i daty, które już były. Głos jest miły.",
        ],
        "participants": ["sponsor_screen"],
        "possible_resolutions": {
            "listen":         {"time": 5,
                                "effects": ["rumor","audience_up_min","ministerstwo_relationship_up"]},
            "smash":          {"stat": "STR", "dc": 9, "time": 2,
                                "effects": ["audience_up","ministerstwo_relationship_down"]},
            "hack":           {"stat": "INT", "dc": 12, "time": 6,
                                "effects": ["change_message","tech_affinity"]},
            "ignore":         {"time": 0, "effects": ["none"]},
        },
    },

    "wounded_monster_choice": {
        "type": "moral_choice",
        "weight": 5,
        "floor_min": 3,
        "tags": ["monster","moral","corpse","social"],
        "fallback_title": "Ranny potwór w kącie",
        "intro": [
            "Potwór leży w kącie, oddycha, ale ledwo. Patrzy na ciebie "
            "z czymś, co u ludzi byłoby błaganiem.",
            "Krew tworzy małe jezioro. Potwór już zrezygnował z agresji, "
            "zostawił sobie tylko widok.",
        ],
        "participants": ["monster"],
        "possible_resolutions": {
            "execute":        {"stat": "STR", "dc": 5, "time": 2,
                                "effects": ["xp","audience_up","corpse"]},
            "mercy":          {"stat": "WIS", "dc": 9, "time": 3,
                                "effects": ["audience_split","title_decent_person"]},
            "harvest_alive":  {"stat": "INT", "dc": 12, "time": 8,
                                "effects": ["double_materials","audience_split","attention_sponsor_down"]},
            "leave":          {"time": 0, "effects": ["none"]},
        },
    },

    "broken_robot_offers_help": {
        "type": "social_obstacle",
        "weight": 3,
        "floor_min": 5,
        "tags": ["machine","tech","social","loot"],
        "fallback_title": "Zepsuty robot pyta o pomoc",
        "intro": [
            "Robot serwisowy, jedna gąsienica, druga w naprawie. "
            "Mówi monotonnie: „Hello. Identify yourself. Please.” "
            "Z brzucha sterczy mu portfel kogoś.",
            "Robot z napisem SERWIS BORANT. Trzęsie się jak chce "
            "wstać, ale nie potrafi.",
        ],
        "participants": ["machine"],
        "possible_resolutions": {
            "repair":         {"stat": "INT", "dc": 13, "time": 12,
                                "effects": ["companion_robot_temp","tech_affinity"]},
            "scavenge":       {"stat": "DEX", "dc": 9, "time": 5,
                                "effects": ["materials","loot"]},
            "destroy":        {"stat": "STR", "dc": 8, "time": 4,
                                "effects": ["materials","audience_down"]},
            "talk":           {"stat": "CHA", "dc": 12, "time": 5,
                                "effects": ["rumor","none_loot"]},
        },
    },

    "rival_crawler_duel": {
        "type": "challenge",
        "weight": 4,
        "floor_min": 6,
        "tags": ["crawler","social","challenge","audience"],
        "fallback_title": "Rywal proponuje pojedynek",
        "intro": [
            "Crawler w trzy razy lepszym sprzęcie wymachuje "
            "tobie ręką: „Hej, ty. Pierwszy do trzech trafień, "
            "stawka — to co masz w plecaku.” Z głośnika "
            "wstępna fanfara.",
            "Konferansjer już zaczął komentować na żywo. Reflektor "
            "skierowany. Drugiej szansy na uniknięcie nie będzie.",
        ],
        "participants": ["crawler"],
        "possible_resolutions": {
            "accept_duel":    {"stat": "STR", "dc": 12, "time": 10,
                                "effects": ["combat_crawler","audience_up_big","double_or_lose_loot"]},
            "decline_polite": {"stat": "CHA", "dc": 11, "time": 3,
                                "effects": ["audience_down","relationship_neutral"]},
            "cheap_shot":     {"stat": "DEX", "dc": 13, "time": 2,
                                "effects": ["combat_advantage","audience_split"]},
            "bribe":          {"requires_credits": 50, "time": 5,
                                "effects": ["bypass","audience_down","lose_credits"]},
        },
    },

    "fan_runs_up_for_autograph": {
        "type": "social_event",
        "weight": 2,
        "floor_min": 6,
        "tags": ["fan","sponsor","audience","social"],
        "fallback_title": "Fan dobiega po autograf",
        "intro": [
            "Z bocznych drzwi wybiega ktoś z koszulką twojego "
            "imienia i głupim uśmiechem. Macha kartką. Krzyczy "
            "twoje imię z błędem.",
            "Fan. Prawdziwy. To znaczy: ktoś dostał skierowanie z "
            "działu marketingu sponsora. Ale uśmiech ma autentyczny.",
        ],
        "participants": ["npc"],
        "possible_resolutions": {
            "sign_autograph": {"time": 3,
                                "effects": ["audience_up","sponsor_relationship_up"]},
            "selfie":         {"time": 4,
                                "effects": ["audience_up_big","title_celebrity"]},
            "ignore":         {"time": 1,
                                "effects": ["audience_down_small"]},
            "be_rude":        {"stat": "CHA", "dc": 10, "time": 2,
                                "effects": ["audience_down","fan_anger"]},
        },
    },

    "sponsor_offer_pop_up": {
        "type": "sponsor_event",
        "weight": 4,
        "floor_min": 4,
        "tags": ["sponsor","social","contract"],
        "fallback_title": "Sponsor proponuje kontrakt",
        "intro": [
            "Na ekranie nad drzwiami zapala się logo sponsora. "
            "Głos: „Witaj. Mamy dla ciebie ofertę. Niewielki rabat "
            "na śmierć w ciągu trzech pięter. Lub coś łatwiejszego.”",
            "Reklama z twoim imieniem. Trzy opcje na dole ekranu, "
            "wszystkie wyglądają na pułapkę.",
        ],
        "participants": ["sponsor_screen"],
        "possible_resolutions": {
            "accept":         {"time": 5,
                                "effects": ["sponsor_relationship_up","contract_burden"]},
            "haggle":         {"stat": "CHA", "dc": 13, "time": 8,
                                "effects": ["better_terms","sponsor_relationship_small_up"]},
            "smash_screen":   {"stat": "STR", "dc": 8, "time": 2,
                                "effects": ["audience_up","sponsor_anger"]},
            "ignore":         {"time": 1, "effects": ["none"]},
        },
    },

    "lost_kid_npc": {
        "type": "social_choice",
        "weight": 3,
        "floor_min": 5,
        "tags": ["civilian","social","moral","escort"],
        "fallback_title": "Zagubione dziecko",
        "intro": [
            "Dziecko. W lochu. Trzyma pluszowego potwora, którego "
            "nie powinno znać. Patrzy na ciebie spokojnie, jakby to "
            "ono prowadziło rozgrywkę.",
            "Mała postać w piżamie z reklamy. Nie pamięta, kiedy "
            "tu weszła. Pamięta twoje imię.",
        ],
        "participants": ["npc"],
        "possible_resolutions": {
            "escort_to_safe": {"stat": "WIS", "dc": 11, "time": 20,
                                "effects": ["audience_up_big","title_decent_person"]},
            "ignore":         {"time": 1,
                                "effects": ["audience_down_big","status_haunted"]},
            "interrogate":    {"stat": "CHA", "dc": 12, "time": 5,
                                "effects": ["rumor","lore"]},
            "follow_silently":{"time": 10,
                                "effects": ["hidden_room_reveal","lore"]},
        },
    },

    "fungal_choir": {
        "type": "environment_choice",
        "weight": 3,
        "floor_min": 10,
        "tags": ["fungal","environment","mental","horror"],
        "fallback_title": "Grzybowy chór",
        "intro": [
            "Ściana naprzeciw oddycha. Z każdym oddechem chór "
            "kolonii pleśni wymawia coś, co brzmi jak słowo „mama”.",
            "Mokre, słodkie powietrze. Pleśń tworzy układy "
            "geometryczne i powtarza znane ci nazwiska.",
        ],
        "participants": ["hazard"],
        "possible_resolutions": {
            "listen":         {"time": 5,
                                "effects": ["lore","status_unsettled"]},
            "burn":           {"requires_item_tag": "fire",
                                "stat": "DEX", "dc": 10, "time": 4,
                                "effects": ["clear_hazard","audience_up","attention_novachem_down"]},
            "sample":         {"stat": "INT", "dc": 14, "time": 8,
                                "effects": ["materials","status_unsettled","tech_affinity"]},
            "leave":          {"time": 1, "effects": ["none"]},
        },
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
