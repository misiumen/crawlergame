"""Prompt 19 — Pet catalog (10 fully-profiled + 20 flavor placeholders).

Each entry in `PETS_V1` is a dict the engine reads at character-creation
time to assign a random pet. Fields:

    species_key       stable id (ASCII, used in commands/locales)
    display_name_pl   Polish display name (singular nominative)
    name_aliases_pl   extra parser tokens (genitive/instrumental forms,
                      slang). Engine matcher does diacritic-fold +
                      5-char stem so "gęś/gęsi/gęsią" all hit.
    temperament       short PL descriptor for journal flavour
    role              short PL descriptor — what the pet is FOR
    need              PL one-liner — what it complains about
    risk              PL one-liner — what can go wrong
    abilities         list of ability_keys (engine reads these to gate
                      `wyślij na zwiad`, `użyj jako wabika`, etc.)
    sponsor_likes     list of sponsor tag_keys this pet emits when
                      acting — drives audience/sponsor system
    intro_line_pl     line shown when the pet is first assigned
    description_pl    one-line journal description

Abilities (canonical tags consumed by engine.companion_actions):
    scout_tight       can scout vents, ducts, small spaces
    scout_aerial      can scout from above (windows, balconies)
    find_scrap        searches help yield extra material drops
    distract_weak     can distract weak NPCs (DC penalty)
    intimidate        can spook weak/non-combat NPCs
    repeat_phrase     can echo a phrase to spread/distract
    detect_chemical   notices acid/toxin hazards early
    morale_boost      flat +1 audience and -1 player stress
    mark_trail        leaves a slow but unmistakable trail
    unlock_assist     +1 to player lockpick rolls when present
    reduce_noise      player noise cap -1 when companion is present
    warn_danger       reveals one hidden hazard tag per room

Risk tags (consumed for "things that go sideways"):
    noise             companion can suddenly make noise
    wrong_target      may distract YOU or the wrong NPC
    leaks_secret      may repeat sensitive phrases
    steals_shiny      may steal items
    fragile           low HP, dies easily
    panics_cold       refuses scouting in cold rooms
    attracts_predator scouting can attract worse things
    aloof             may ignore commands
    painfully_slow    actions take 5× longer
    steals_from_player can pickpocket the player

The 10 fully-profiled pets give meaningful playstyle variety on first
playthrough. The 20 placeholders ship as a flat data shape (species
name + tags only) so a future content drop fleshes them out without
engine changes.
"""
from __future__ import annotations

from typing import Dict, List, Any


# ── Ability + risk constants (re-exported for engine consumers) ───────────

ABILITY_SCOUT_TIGHT     = "scout_tight"
ABILITY_SCOUT_AERIAL    = "scout_aerial"
ABILITY_FIND_SCRAP      = "find_scrap"
ABILITY_DISTRACT_WEAK   = "distract_weak"
ABILITY_INTIMIDATE      = "intimidate"
ABILITY_REPEAT_PHRASE   = "repeat_phrase"
ABILITY_DETECT_CHEMICAL = "detect_chemical"
ABILITY_MORALE_BOOST    = "morale_boost"
ABILITY_MARK_TRAIL      = "mark_trail"
ABILITY_UNLOCK_ASSIST   = "unlock_assist"
ABILITY_REDUCE_NOISE    = "reduce_noise"
ABILITY_WARN_DANGER     = "warn_danger"

ALL_ABILITIES = (
    ABILITY_SCOUT_TIGHT, ABILITY_SCOUT_AERIAL, ABILITY_FIND_SCRAP,
    ABILITY_DISTRACT_WEAK, ABILITY_INTIMIDATE, ABILITY_REPEAT_PHRASE,
    ABILITY_DETECT_CHEMICAL, ABILITY_MORALE_BOOST, ABILITY_MARK_TRAIL,
    ABILITY_UNLOCK_ASSIST, ABILITY_REDUCE_NOISE, ABILITY_WARN_DANGER,
)


# ── 10 fully-profiled pets ─────────────────────────────────────────────────

PETS_V1: List[Dict[str, Any]] = [
    {
        "species_key": "gees",
        "display_name_pl": "Gęś",
        "name_aliases_pl": ["gęsi", "gęsią", "gęsiom", "gęś"],
        "temperament": "wojowniczo skupiona",
        "role": "chaos i zastraszanie",
        "need": "jedzenie i osobista wyższość",
        "risk": "atakuje nie tych, co trzeba, hałasuje",
        "abilities": [ABILITY_DISTRACT_WEAK, ABILITY_INTIMIDATE],
        "risk_tags": ["noise", "wrong_target"],
        "sponsor_likes": ["spectacle"],
        "intro_line_pl":
            "Idzie z tobą gęś. Nie zaprzeczaj. Ona już to ustaliła.",
        "description_pl":
            "Duża, biała, oburzona istnieniem reszty świata.",
    },
    {
        "species_key": "szczur",
        "display_name_pl": "Szczur",
        "name_aliases_pl": ["szczura", "szczurem", "szczurze", "szczurów"],
        "temperament": "praktyczny, podejrzliwy",
        "role": "zwiad w wąskich miejscach, znajdowanie złomu",
        "need": "jedzenie, schowek, ciepło",
        "risk": "kradnie błyskotki, przyciąga drapieżniki",
        "abilities": [ABILITY_SCOUT_TIGHT, ABILITY_FIND_SCRAP],
        "risk_tags": ["steals_shiny", "attracts_predator"],
        "sponsor_likes": ["lockpicking"],
        "intro_line_pl":
            "Szczur ocenia cię chłodno. Decyzję podejmie później.",
        "description_pl":
            "Inteligentny, zbyt dużo wie o tobie po dwóch godzinach.",
    },
    {
        "species_key": "papuga",
        "display_name_pl": "Papuga",
        "name_aliases_pl": ["papugi", "papugą", "papugę", "papugach"],
        "temperament": "głośna, towarzyska, niedyskretna",
        "role": "mimikra, plotki, propaganda",
        "need": "uwaga i okno",
        "risk": "powtarza sekrety i niebezpieczne frazy",
        "abilities": [ABILITY_REPEAT_PHRASE, ABILITY_DISTRACT_WEAK],
        "risk_tags": ["leaks_secret", "noise"],
        "sponsor_likes": ["propaganda_recite", "memetic_seed"],
        "intro_line_pl":
            "Papuga już wie, jak masz na imię. Powie to każdemu.",
        "description_pl":
            "Zielona, błyskotliwa, kiepska w utrzymaniu tajemnic.",
    },
    {
        "species_key": "waz",
        "display_name_pl": "Wąż",
        "name_aliases_pl": ["węża", "wężem", "węży", "wężu"],
        "temperament": "powolny, obojętny, cierpliwy",
        "role": "zwiad w ciasnych miejscach, zastraszanie",
        "need": "ciepło i ciemność",
        "risk": "panikuje w zimnie, wywołuje histerię u NPC",
        "abilities": [ABILITY_SCOUT_TIGHT, ABILITY_INTIMIDATE],
        "risk_tags": ["panics_cold"],
        "sponsor_likes": ["spectacle"],
        "intro_line_pl":
            "Wąż owija się wokół twojego ramienia. Nie szuka kłopotów. Ale je znajdzie.",
        "description_pl":
            "Szary, suchy, niepokojąco logiczny.",
    },
    {
        "species_key": "kot",
        "display_name_pl": "Kot",
        "name_aliases_pl": ["kota", "kotem", "kocie", "kotów"],
        "temperament": "obojętny, samowystarczalny",
        "role": "cichy towarzysz, ostrzeganie przed niebezpieczeństwem",
        "need": "spokój i sucha kanapa",
        "risk": "ignoruje rozkazy w połowie przypadków",
        "abilities": [ABILITY_WARN_DANGER, ABILITY_REDUCE_NOISE],
        "risk_tags": ["aloof"],
        "sponsor_likes": [],
        "intro_line_pl":
            "Kot wchodzi do twojego plecaka. Decyzja zapadła bez ciebie.",
        "description_pl":
            "Czarny, z jednym uchem nadgryzionym. Wie więcej niż mówi.",
    },
    {
        "species_key": "kruk",
        "display_name_pl": "Kruk",
        "name_aliases_pl": ["kruka", "krukiem", "kruku"],
        "temperament": "obserwujący, mściwy",
        "role": "zwiad z powietrza, znaki",
        "need": "wysokość i błyszczące rzeczy",
        "risk": "zwraca uwagę nie tych, co trzeba",
        "abilities": [ABILITY_SCOUT_AERIAL, ABILITY_WARN_DANGER],
        "risk_tags": ["steals_shiny", "noise"],
        "sponsor_likes": ["spectacle"],
        "intro_line_pl":
            "Kruk siada ci na ramieniu. Patrzy. Niczego nie obiecuje.",
        "description_pl":
            "Czarny, bystry, wyraźnie odgrywa rolę przed widownią.",
    },
    {
        "species_key": "rybka_w_sloju",
        "display_name_pl": "Rybka w słoiku",
        "name_aliases_pl": ["rybki", "rybką", "rybce", "rybkę"],
        "temperament": "obecna, znacząca, niedostępna",
        "role": "talizman, czujka chemiczna",
        "need": "woda, chłód, ochrona",
        "risk": "krucha, niewygodna do noszenia",
        "abilities": [ABILITY_DETECT_CHEMICAL, ABILITY_MORALE_BOOST],
        "risk_tags": ["fragile"],
        "sponsor_likes": ["chemical"],
        "intro_line_pl":
            "Bierzesz słoik. Rybka patrzy na ciebie. Wiesz już, że to ważne.",
        "description_pl":
            "Pomarańczowa, w litrowym słoiku. Wie coś, czego ty nie wiesz.",
    },
    {
        "species_key": "swinka_morska",
        "display_name_pl": "Świnka morska",
        "name_aliases_pl": ["świnki", "świnką", "świnkę", "świnek"],
        "temperament": "łagodna, paniczna, ciepła",
        "role": "morale, sympatia widowni",
        "need": "marchewka, dużo siana",
        "risk": "nieprzydatna w walce, zbyt głośno piszczy",
        "abilities": [ABILITY_MORALE_BOOST, ABILITY_REDUCE_NOISE],
        "risk_tags": ["noise", "fragile"],
        "sponsor_likes": ["spectacle"],
        "intro_line_pl":
            "Świnka morska wchodzi ci za pazuchę. Widownia natychmiast ją lubi.",
        "description_pl":
            "Brązowo-biała, ciepła, nieprzeciętnie wzruszająca.",
    },
    {
        "species_key": "slimak_bojowy",
        "display_name_pl": "Ślimak bojowy",
        "name_aliases_pl": ["ślimaka", "ślimakiem", "ślimaku"],
        "temperament": "spokojny do absurdu",
        "role": "absurdalna wytrwałość, znakowanie tras",
        "need": "wilgoć i czas",
        "risk": "potwornie powolny — każda akcja trwa 5× dłużej",
        "abilities": [ABILITY_MARK_TRAIL, ABILITY_MORALE_BOOST],
        "risk_tags": ["painfully_slow"],
        "sponsor_likes": ["spectacle"],
        "intro_line_pl":
            "Ślimak ma na pancerzu wymalowaną gwiazdkę. Idzie z tobą. Powoli.",
        "description_pl":
            "Większy niż powinien być. Z gwiazdką. Z planem na życie.",
    },
    {
        "species_key": "szop",
        "display_name_pl": "Szop pracz",
        "name_aliases_pl": ["szopa", "szopem", "szopie", "szopów"],
        "temperament": "zwinny, oportunistyczny",
        "role": "pomoc przy zamkach, drobna kradzież",
        "need": "ruch i błyskotki",
        "risk": "kradnie tobie",
        "abilities": [ABILITY_UNLOCK_ASSIST, ABILITY_FIND_SCRAP],
        "risk_tags": ["steals_from_player", "noise"],
        "sponsor_likes": ["theft", "lockpicking"],
        "intro_line_pl":
            "Szop pracz wybiera ciebie. Już zerka na twoje kieszenie.",
        "description_pl":
            "Mały, w masce, ze stażem w przestępczości zorganizowanej.",
    },
]


# ── 20 flavor-only placeholders for future content drop ────────────────────

PETS_FLAVOR: List[Dict[str, Any]] = [
    {"species_key": "pies",            "display_name_pl": "Pies"},
    {"species_key": "fretka",          "display_name_pl": "Fretka"},
    {"species_key": "jaszczurka",      "display_name_pl": "Jaszczurka"},
    {"species_key": "zolw",            "display_name_pl": "Żółw"},
    {"species_key": "krolik",          "display_name_pl": "Królik"},
    {"species_key": "jez",             "display_name_pl": "Jeż"},
    {"species_key": "gekon",           "display_name_pl": "Gekon"},
    {"species_key": "koza_miniaturowa","display_name_pl": "Koza miniaturowa"},
    {"species_key": "golab",           "display_name_pl": "Gołąb"},
    {"species_key": "aksolotl",        "display_name_pl": "Aksolotl w przenośnym pojemniku"},
    {"species_key": "kura_bojowa",     "display_name_pl": "Kura bojowa"},
    {"species_key": "chomik",          "display_name_pl": "Chomik"},
    {"species_key": "pajak",           "display_name_pl": "Pająk w pudełku"},
    {"species_key": "kanarek",         "display_name_pl": "Kanarek"},
    {"species_key": "kaczka",          "display_name_pl": "Kaczka"},
    {"species_key": "miniaturowa_swinia","display_name_pl": "Miniaturowa świnia"},
    {"species_key": "skorpion",        "display_name_pl": "Skorpion w terrarium"},
    {"species_key": "ropucha",         "display_name_pl": "Ropucha"},
    {"species_key": "szczur_laboratoryjny","display_name_pl": "Szczur laboratoryjny"},
    {"species_key": "nietoperz_owocowy","display_name_pl": "Nietoperz owocowy"},
]


# Lookup by species_key (only the v1 ten — flavor pool isn't roll-eligible yet).
def get_pet_template(species_key: str) -> Dict[str, Any]:
    for p in PETS_V1:
        if p["species_key"] == species_key:
            return p
    return {}


def all_v1_species_keys() -> List[str]:
    return [p["species_key"] for p in PETS_V1]


def roll_random_pet(rng=None) -> Dict[str, Any]:
    """Pick one pet at random from the v1 pool. Deterministic when
    `rng` is a seeded random.Random."""
    import random as _r
    rng = rng or _r.Random()
    return rng.choice(PETS_V1)
