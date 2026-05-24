"""Safehouse templates for Dungeon Kraulem.

Each subtype has metadata that the floor generator and rumor systems can read:
  tags        -- short ASCII tags used by filters (cafe/quiet/social/...)
  weight      -- pick-weight when generator picks a safehouse subtype
  floor_min   -- earliest floor where this subtype can appear
  risks       -- short list of bad outcomes the player can trigger here
  rewards     -- short list of services the safehouse offers
  possible_clue_sources -- where clues can land in this kind of safehouse
"""

SAFEHOUSE_TEMPLATES = {
    "cafe": {
        "tags": ["safehouse","cafe","social","rumor_source","crowded"],
        "weight": 6, "floor_min": 1,
        "risks": ["overheard","relationship_down","prices_up"],
        "rewards": ["coffee","food","rumor","short_rest"],
        "possible_clue_sources": ["rumor","graffiti","npc_dialogue"],
        "name_pool": ["Ostatni Łyk", "Kawa Przed Przemocą", "Mugs & Munitions", "Bufet Neutralności"],
        "entry_descriptions": [
            "Za drzwiami pachnie kawą, ozonem i mokrym strachem. Kilku crawlerów siedzi przy stolikach, udając, że nie liczy dróg ucieczki.",
            "Neon nad ladą mruga: KAWA NIE GWARANTUJE PRZEŻYCIA. Pod spodem ktoś dopisał: ALE POMAGA UMRZEĆ PRZYTOMNIE."
        ],
        "services": ["buy_coffee", "buy_food", "listen", "talk", "rumors", "rest_short"],
        "ambient_lines": [
            "Ekspres do kawy syczy jak mały smok z umową franczyzową.",
            "Ktoś śmieje się za głośno. Reszta sali natychmiast sprawdza, czy to nie początek eventu."
        ]
    },
    "bathroom": {
        "tags": ["safehouse","bathroom","quiet","graffiti_source","secret_entry"],
        "weight": 5, "floor_min": 1,
        "risks": ["mirror_event","ambush_in_stall"],
        "rewards": ["wash","minor_heal","graffiti_clue","short_rest"],
        "possible_clue_sources": ["graffiti","corpse_note","npc_dialogue"],
        "name_pool": ["Autoryzowana Łazienka 7", "Sanitarny Rozejm", "Kabiny Bez Gwarancji"],
        "entry_descriptions": [
            "Łazienka jest za czysta. To pierwszy i najgorszy znak. Lustra pokazują cię z opóźnieniem o pół sekundy.",
            "W środku pachnie chlorem, metalem i tajemnicą, którą ktoś próbował spłukać trzy razy."
        ],
        "services": ["bathroom", "wash", "shower", "minor_condition_remove", "mirror_event", "rumors"],
        "ambient_lines": [
            "Z kabiny numer dwa dobiega kaszel, modlitwa albo bardzo osobisty dialog z systemem.",
            "Na suszarce do rąk widnieje naklejka: NIE SUSZYĆ AMPUTOWANYCH KOŃCZYN."
        ]
    },
    "clinic": {
        "tags": ["safehouse","clinic","heal","expensive","clinical"],
        "weight": 4, "floor_min": 1,
        "risks": ["overpriced","kicked_out_no_credits","sponsored_drug"],
        "rewards": ["heal","cure","full_heal","short_rest"],
        "possible_clue_sources": ["npc_dialogue","terminal"],
        "name_pool": ["Klinika Bez Pytań", "Punkt Sanitarny 7", "NovaChem Triage"],
        "entry_descriptions": [
            "Zapach środków dezynfekujących walczy z czymś gorszym i wygrywa tylko technicznie. Lampy halogenowe odbijają się od białych płytek z mściwą czystością.",
            "Cennik wisi obok defibrylatora, jakby były tej samej kategorii produktów.",
        ],
        "services": ["heal", "cure", "full", "rumor", "rest_short"],
        "ambient_lines": [
            "Maszyna recepcji prosi o uśmiech do kamery. Nie określa którą.",
            "Z głośnika płynie spokojny głos: 'Państwa zgon jest dla nas wyzwaniem statystycznym.'",
            "W kącie ktoś czyta ulotkę o kosztach utraty kończyny.",
            "Pielęgniarz patrzy ci w oczy zbyt długo, jakby przypominał sobie czyjś sufit.",
        ],
    },
    "sponsor_kiosk": {
        "tags": ["safehouse","sponsor","intel","ads","quiet"],
        "weight": 4, "floor_min": 1,
        "risks": ["sponsor_brand_damage","audience_swing"],
        "rewards": ["intel","ad_credit","floor_hint"],
        "possible_clue_sources": ["terminal","npc_dialogue"],
        "name_pool": ["Punkt Informacyjny NovaChem", "Kiosk Sponsorski A-2", "Strefa Promocji"],
        "entry_descriptions": [
            "Małe okienko z ekranem pełnym reklam i tabliczką: PYTAJ O CIEKAWE OFERTY. Wszystkie oferty są ciekawe inaczej.",
            "Plastikowe ulotki z napisem 'NIE DAJ SIĘ ZASKOCZYĆ' układają się w stos, który właśnie kogoś zaskoczył.",
        ],
        "services": ["ad", "intel", "rumor"],
        "ambient_lines": [
            "Animowany maskotka sponsora macha do ciebie zbyt szybko, żeby wyglądało to przyjaźnie.",
            "Z głośników: 'Każdy zgon na tym piętrze sponsorowany jest przez NovaChem™.'",
            "Tabliczka pod ekranem: 'OPINIE NEGATYWNE BĘDĄ WYKORZYSTANE PRZECIWKO TOBIE.'",
        ],
    },
    "black_market": {
        "tags": ["safehouse","black_market","trade","contraband","sponsor_free"],
        "weight": 3, "floor_min": 1,
        "risks": ["overpriced","fake_goods","tracked_by_sponsor"],
        "rewards": ["contraband","keycard","rumor","illegal_goods"],
        "possible_clue_sources": ["npc_dialogue","corpse_note"],
        "name_pool": ["Bez Paragonu", "Gwarancja Martwa", "Rynek Pod Zlewem", "Legalnie Prawie"],
        "entry_descriptions": [
            "Czarny rynek mieści się tam, gdzie mapa pokazuje ścianę. To dobry znak albo bardzo zły, zależnie od twojego budżetu.",
            "Na ladzie leżą rzeczy, które ktoś zgubił, sprzedał albo nadal próbuje odzyskać z zaświatów."
        ],
        "services": ["buy", "sell", "illegal_goods", "cursed_items", "rumors"],
        "ambient_lines": [
            "Sprzedawca uśmiecha się tak, jakby cena była tylko początkiem obrażeń.",
            "W rogu stoi automat z napisem ZWROTY. Otwór wrzutowy jest wielkości dłoni."
        ]
    }
}
