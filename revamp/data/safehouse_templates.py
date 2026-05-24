"""Safehouse templates for CRAWL PROTOCOL revamp."""

SAFEHOUSE_TEMPLATES = {
    "cafe": {
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
        "name_pool": ["Klinika Bez Pytań", "Punkt Sanitarny 7", "NovaChem Triage"],
        "entry_descriptions": [
            "Zapach środków dezynfekujących walczy z czymś gorszym i wygrywa tylko techniczne. Lampy halogenowe odbijają się od białych płytek z mściwą czystością.",
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
