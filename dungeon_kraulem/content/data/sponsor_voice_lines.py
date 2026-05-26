"""Sponsor voice lines (Prompt 27) — Polish quips by sponsor + tag.

Each sponsor key maps to a dict: `tag → list of Polish one-liners`.
When the player triggers a tag-bus event of weight >= 2,
`engine.sponsor_voice.maybe_speak` rolls to surface one of these lines
in the player's log as a LOG_SYNDIC entry (avatar gutter shows the
sponsor's initial).

Tone guide per sponsor:
  novachem            — klinicznie sarkastyczny, korpo-medyczny
  liga (sport)        — bezduszny korporacyjny biurokrata, regulaminy
  czarny_rynek        — konspiracyjnie życzliwy, podszepty
  ministerstwo        — formalny, urzędowy, sucho-pasywno-agresywny
  syndykat            — zimny prowadzący, dziennikarski dystans
  obywatele_ulicy     — kibice, hałaśliwi, oddolni

Adding new tags: just add to the dict — `maybe_speak` silently
no-ops when a tag has no entry. New sponsors: add a top-level key.
"""
from __future__ import annotations
from typing import Dict, List


VOICE_LINES: Dict[str, Dict[str, List[str]]] = {

    "novachem_biotech": {
        "kill_lethal": [
            "Świetna demonstracja toksyczności. Notujemy.",
            "Statystyki śmiertelności są dziś łaskawe dla naszych prognoz.",
        ],
        "crit_hit": [
            "Kliniczna precyzja. Lubimy to.",
            "Subiekt wykazał nadspodziewaną reaktywność.",
        ],
        "butchered_corpse": [
            "Ciekawy materiał próbny. Niech leży.",
            "Z tej tkanki by się dało zrobić coś użytecznego.",
        ],
        "looted_novachem": [
            "Przykro nam, że nasz inspektor okazał się tak… porowaty.",
        ],
        "novachem_enemy": [
            "Ta wrogość zostanie odnotowana w aktach.",
            "Pamiętamy każdą fakturę.",
        ],
        "crossfire": [
            "Wzajemna eliminacja w zasięgu polisy. Bardzo elegancko.",
        ],
        "deadline_pressure": [
            "Czas to pieniądz. Twój pieniądz, w naszej kasie.",
        ],
    },

    "sponsor_bezpieczenstwa_sportu": {
        "kill_lethal": [
            "Regulamin 4.2: zabity przeciwnik zostaje skreślony z listy.",
            "Liczy się ostateczność. Punkt dla ciebie.",
        ],
        "crit_hit": [
            "Trafienie krytyczne. Widzowie kochają takie ujęcia.",
            "Pełnia widowiska. Klatka po klatce.",
        ],
        "env_kill": [
            "Wykorzystanie środowiska — dodatkowy punkt stylowy.",
            "Sędziowie biorą pod uwagę kreatywność.",
        ],
        "heavy_attack_hit": [
            "Brutalność. Lubimy to.",
        ],
        "flee": [
            "Ucieczka. Notujemy w protokole.",
            "Spadek formy w trzeciej minucie. Niezgodne z regulaminem.",
        ],
        "crossfire": [
            "Walka frakcji. Plansza wyników rośnie.",
        ],
        "looted_authority": [
            "Strażnik miał ważną odznakę. Liga monitoruje.",
        ],
        "killed_league": [
            "Egzekutor Ligi pełnił służbę. Wystawiamy ci rachunek.",
        ],
    },

    "czarny_rynek_plus": {
        "butchered_corpse": [
            "Z tych części znajdziesz nabywcę. Mamy listę.",
            "Tkanka ludzka — wahanie podaży, stałe ceny.",
        ],
        "theft": [
            "Dobre oko do tego, co cudze.",
            "Pamiętaj — komuś to należało. Ale teraz tobie.",
        ],
        "salvage_sponsor_property": [
            "Nikt nie zauważy. A jeśli zauważą, mamy adwokata.",
        ],
        "killed_collector": [
            "Jeden Windykator mniej. Bilans dnia: korzystny.",
        ],
        "looted_authority": [
            "Mamy klienta na tę odznakę. Bez pytań.",
        ],
        "crossfire": [
            "Dwie strony, jedno spotkanie. Idealnie.",
        ],
        "crafting": [
            "Pracujesz rękami. Lubimy ludzi z umiejętnościami.",
        ],
    },

    "ministerstwo_pamieci": {
        "kill_lethal": [
            "Należy złożyć formularz P-7 z trzema kopiami.",
            "Każdy przypadek likwidacji wymaga uzasadnienia.",
        ],
        "rebel_speech": [
            "Tego rodzaju wypowiedzi podlegają monitoringowi.",
        ],
        "ministerstwo_enemy": [
            "Akta zostały otwarte. Nie zostaną zamknięte.",
        ],
        "killed_editor": [
            "Naczelny był naszym partnerem. Sprawa otwarta.",
        ],
        "compliance": [
            "Dziękujemy za współpracę z procedurami.",
        ],
        "deadline_pressure": [
            "Termin to wartość regulaminowa. Należy go dotrzymać.",
        ],
    },

    # Floor 1 default sponsor (per existing rotation). Same voice as
    # NovaChem if not declared — covered by fallback. The dict above
    # already covers the rotating sponsors; add new keys as floors land.
}
