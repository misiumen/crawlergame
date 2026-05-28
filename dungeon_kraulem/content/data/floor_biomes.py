"""P29.42a — Floor biomes.

Każde piętro w runie dostaje losowy biom z dostępnej puli (filter
floor_min/max + starting_unlocked albo meta_unlock_key satysfakcjonowany).
Biomy to **świat fizyczny / setting** — kraj, sektor, epoka. Sponsorzy
zostają WARSTWĄ NADRZĘDNĄ (drop pody, interwencje, voice lines) i nie
są częścią nazwy biomu.

Architektura:
  * FloorBiome dataclass — key, name_pl, theme_pl, floor_min/max,
    room_tag (do filtra room_pool), sponsor_likes, weight,
    starting_unlocked, meta_unlock_key, enabled.
  * FLOOR_BIOMES — registry per biome_key.
  * `available_biomes(floor_num, world)` — biomy aktualnie dostępne
    dla danego piętra (po unlock'ach). Generator z tego losuje.
  * `enabled=False` — biom istnieje koncepcyjnie ale generator go
    POMIJA dopóki ktoś nie zrobi dla niego pokoi (P29.42b). Bezpieczna
    ścieżka — najpierw arch, potem treść.

room_tag → tag, który musi się znaleźć w `tags` puli room_pool, żeby
pokój pasował do biomu. Pokoje BEZ żadnego biome-tagu są neutralne
(safehouse'y, korytarze) i mogą wejść do dowolnego biomu.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FloorBiome:
    key: str
    name_pl: str
    theme_pl: str
    floor_min: int
    floor_max: int
    room_tag: str                          # filter dla room_pool
    sponsor_likes: Dict[str, int] = field(default_factory=dict)
    weight: int = 2
    starting_unlocked: bool = True
    meta_unlock_key: Optional[str] = None  # klucz w meta_progression.UNLOCK_CATALOG
    enabled: bool = True                   # generator pomija False


# ── Catalog ────────────────────────────────────────────────────────────

FLOOR_BIOMES: Dict[str, FloorBiome] = {

    # ── Tier 0 — F1-2 default ─────────────────────────────────────────

    "intake_industrial": FloorBiome(
        key="intake_industrial",
        name_pl="Strefa Aklimatyzacji",
        theme_pl="Świetlówki nad głową drgają, automaty nie działają, "
                 "kamery sponsorów bujają się na przewodach.",
        floor_min=1, floor_max=2,
        room_tag="intake",         # bardzo wąski — w praktyce pokoje
                                    # neutralne (bez biome tagu) wpadają tu
        weight=3,
        # F1-2 pokoje są w większości neutralne — generator i tak je
        # wpuści bo nie mają żadnego biome-tagu. Ten biom służy głównie
        # do tytułowania piętra.
    ),

    # ── Tier 1 — F3-8, starting unlocked ─────────────────────────────

    "zoo_korporacyjne": FloorBiome(
        key="zoo_korporacyjne",
        name_pl="Zoo Korporacyjne",
        theme_pl="Klatki, futro, krzyk pawia. Korporacja Borant "
                 "zostawiła tu kiedyś menażerię.",
        floor_min=3, floor_max=8,
        room_tag="zoo",
        sponsor_likes={"czarny_rynek_plus": 1},
        weight=2,
        # Pokoje istnieją w room_pool (3 entry z tagiem "zoo").
    ),

    "okopy_frontowe": FloorBiome(
        key="okopy_frontowe",
        name_pl="Frontowe Okopy",
        theme_pl="Błoto po kolana, druty kolczaste, drewno wgryzione "
                 "w ziemię. Plakaty propagandowe nieczytelnych armii.",
        floor_min=3, floor_max=8,
        room_tag="trenches",
        sponsor_likes={"liga_brawurowa": 1},
        weight=2,
        # P29.42b — pokoje + potwory napisane, biom aktywny.
    ),

    "muzeum_spektakli": FloorBiome(
        key="muzeum_spektakli",
        name_pl="Muzeum Spektakli",
        theme_pl="Gabloty, marmurowa podłoga, kuratorzy w mundurach. "
                 "Eksponaty z ostatniego sezonu.",
        floor_min=3, floor_max=8,
        room_tag="museum",
        sponsor_likes={"ministerstwo_pamieci": 1},
        weight=2,
        # Pokoje istnieją w room_pool (3 entry z tagiem "museum").
    ),

    "bar_skurczybyk": FloorBiome(
        key="bar_skurczybyk",
        name_pl='Bar „U Skurczybyka"',
        theme_pl="Neon mruga, butelki, scena karaoke, piwnica pod sceną. "
                 "Lokal lokalny do bólu.",
        floor_min=3, floor_max=8,
        room_tag="bar",
        sponsor_likes={"czarny_rynek_plus": 1},
        weight=2,
        # Pokoje istnieją w room_pool (3 entry z tagiem "bar").
    ),

    "fabryka_pary": FloorBiome(
        key="fabryka_pary",
        name_pl='Fabryka Pary „Sterling-9"',
        theme_pl="Kotły wielkości autobusu, manometry w czerwonej "
                 "strefie, pas transmisyjny ciągnie coś bez końca.",
        floor_min=3, floor_max=8,
        room_tag="steampunk_factory",
        sponsor_likes={"kult_recyklingu": 1},
        weight=2,
        enabled=False,
    ),

    "stacja_orbital": FloorBiome(
        key="stacja_orbital",
        name_pl="Stacja Orbital-7",
        theme_pl="Okrągłe śluzy syczą, próżnia za grubą szybą, "
                 "sterylne kafelki, grawitacja niestabilna.",
        floor_min=3, floor_max=8,
        room_tag="orbital",
        sponsor_likes={"novachem_biotech": 1, "bog_polimerow": 1},
        weight=2,
        enabled=False,
    ),

    "kuznia_polorkow": FloorBiome(
        key="kuznia_polorkow",
        name_pl="Kuźnia Półorków",
        theme_pl="Trzy kowadła bite naraz, węgiel zasypia oczy, młoty "
                 "walą rytmem reklamy, kowale w cechowych opaskach.",
        floor_min=3, floor_max=8,
        room_tag="forge",
        sponsor_likes={"bractwo_komornika": 1},
        weight=2,
        enabled=False,
    ),

    "biblioteka_miejska": FloorBiome(
        key="biblioteka_miejska",
        name_pl="Biblioteka Miejska",
        theme_pl="Regały do sufitu, mikrofilmy, lampki czytelnicze, "
                 "kurz pamięci, archiwista w fartuchu.",
        floor_min=3, floor_max=8,
        room_tag="library",
        sponsor_likes={"ministerstwo_pamieci": 1},
        weight=2,
        enabled=False,
    ),

    # ── Tier 2 — F3-8, meta unlocks ─────────────────────────────────

    "oboz_goblinski": FloorBiome(
        key="oboz_goblinski",
        name_pl="Obóz Gobliński",
        theme_pl="Palisady z drewna i blachy, ogniska, jamy z workami "
                 "po cemencie. Gobliny krzyczą bez kontekstu.",
        floor_min=3, floor_max=8,
        room_tag="goblin_camp",
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_oboz_goblinski",
        enabled=False,
    ),

    "siec_kanalizacyjna": FloorBiome(
        key="siec_kanalizacyjna",
        name_pl="Sieć Kanalizacyjna",
        theme_pl="Rury, smród, kałuże gęste jak budyń, szczury "
                 "wielkości terierów.",
        floor_min=3, floor_max=8,
        room_tag="sewers",
        sponsor_likes={"kult_recyklingu": 1},
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_siec_kanalizacyjna",
        enabled=False,
    ),

    "tunel_karnawalowy": FloorBiome(
        key="tunel_karnawalowy",
        name_pl="Tunel Karnawałowy",
        theme_pl="Luna park po nocy, klauni-manekiny, słodki smród "
                 "waty cukrowej, muzyka karuzeli wolniejsza o jeden ton.",
        floor_min=3, floor_max=8,
        room_tag="carnival",
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_tunel_karnawalowy",
        enabled=False,
    ),

    # ── Tier 3 — F9-12 ─────────────────────────────────────────────

    "grzybica_bloom": FloorBiome(
        key="grzybica_bloom",
        name_pl="Grzybowa Inwazja",
        theme_pl="Zarodniki, miękkie ściany, sponsorowane mleko, ciało "
                 "stało się dom.",
        floor_min=10, floor_max=12,
        room_tag="fungal",
        sponsor_likes={"kult_recyklingu": 1},
        weight=3,
        # Pokoje istnieją w room_pool (3 entry z tagiem "fungal").
    ),

    "stary_reaktor": FloorBiome(
        key="stary_reaktor",
        name_pl="Stary Reaktor",
        theme_pl="Rdza, gorąco, hum, rdzawy pył w powietrzu, znaki "
                 "ostrzegawcze cyrylicą i jeszcze starszym alfabetem.",
        floor_min=9, floor_max=11,
        room_tag="reactor",
        sponsor_likes={"bog_polimerow": 1},
        weight=2,
        enabled=False,
    ),

    "cell_block_c": FloorBiome(
        key="cell_block_c",
        name_pl="Cell Block C",
        theme_pl="Cele, kraty, łańcuchy, krzyki z głębi, kałuże "
                 "nieznanego płynu.",
        floor_min=9, floor_max=12,
        room_tag="prison",
        sponsor_likes={"bractwo_komornika": 1},
        weight=2,
        enabled=False,
    ),

    "katakumby_faktur": FloorBiome(
        key="katakumby_faktur",
        name_pl="Katakumby Spóźnionych Faktur",
        theme_pl="Świece, ołtarze z plastiku, mnisi w lateksowych "
                 "szatach, śpiew obrotowych mantr finansowych.",
        floor_min=9, floor_max=12,
        room_tag="catacombs",
        sponsor_likes={"bractwo_komornika": 1},
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_katakumby_faktur",
        enabled=False,
    ),

    "farma_klonow": FloorBiome(
        key="farma_klonow",
        name_pl="Farma Klonów",
        theme_pl="Kapsuły z biopłynem, klony w różnych stadiach, "
                 "etykiety o nieczytelnym składzie.",
        floor_min=9, floor_max=12,
        room_tag="clone_farm",
        sponsor_likes={"novachem_biotech": 1},
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_farma_klonow",
        enabled=False,
    ),

    "elfia_kolonia": FloorBiome(
        key="elfia_kolonia",
        name_pl="Elfia Kolonia",
        theme_pl="Drzewa rosną przez beton, łuki, lutnie, elfy zbyt "
                 "zadbane jak na warunki lochu.",
        floor_min=9, floor_max=12,
        room_tag="elf_colony",
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_elfia_kolonia",
        enabled=False,
    ),

    # ── Tier 4 — F13-18 ────────────────────────────────────────────

    "redakcja_krawedzi": FloorBiome(
        key="redakcja_krawedzi",
        name_pl="Redakcja Krawędzi",
        theme_pl="Biurka, kamery na statywach, plakaty programów, "
                 "czarna kawa w dzbankach, pisarzy nie ma już od dawna.",
        floor_min=13, floor_max=17,
        room_tag="newsroom",
        sponsor_likes={"kanal_7_krawedz": 2},
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_redakcja_krawedzi",
        enabled=False,
    ),

    "palac_prezesa": FloorBiome(
        key="palac_prezesa",
        name_pl="Pałac Prezesa Syndykatu",
        theme_pl="Marmury, fontanny, służba w skafandrach, miniaturowy "
                 "las pod kopułą, fortepian dla siebie.",
        floor_min=15, floor_max=17,
        room_tag="palace",
        weight=2,
        enabled=False,
    ),

    "swiatynia_konferansjera": FloorBiome(
        key="swiatynia_konferansjera",
        name_pl="Świątynia Konferansjera",
        theme_pl="Ołtarze, popiersia, mikrofony pozłacane, śpiew "
                 "pieśni teleturniejowych z głębi.",
        floor_min=13, floor_max=17,
        room_tag="host_temple",
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_swiatynia_konferansjera",
        enabled=False,
    ),

    "lawowe_tunele": FloorBiome(
        key="lawowe_tunele",
        name_pl="Lawowe Tunele",
        theme_pl="Magma pulsuje pod kratownicami, jaszczury w skórach "
                 "innych jaszczurów, ognioznawcy z młotami.",
        floor_min=13, floor_max=17,
        room_tag="lava_tubes",
        weight=2,
        starting_unlocked=False,
        meta_unlock_key="biome_lawowe_tunele",
        enabled=False,
    ),

    "studio_glowne": FloorBiome(
        key="studio_glowne",
        name_pl="Studio Główne",
        theme_pl="Kable jak węże, sufity studyjne, scena z miejscami "
                 "dla widzów. Słychać każdy oddech.",
        floor_min=13, floor_max=18,
        room_tag="studio",
        sponsor_likes={"kanal_7_krawedz": 1},
        weight=3,
        enabled=False,
    ),

    "arena_finalna": FloorBiome(
        key="arena_finalna",
        name_pl="Arena Finalna",
        theme_pl="Krwawe trybuny, mikrofon w centrum, scena ringu, "
                 "świateł reflektorów więcej niż powietrza.",
        floor_min=18, floor_max=18,
        room_tag="finale_arena",
        weight=5,    # mocno faworyzowany na F18
        enabled=False,
    ),
}


# ── Public API ────────────────────────────────────────────────────────

def all_biomes() -> List[FloorBiome]:
    """Wszystkie biomy w katalogu (włącznie z disabled)."""
    return list(FLOOR_BIOMES.values())


def get_biome(biome_key: str) -> Optional[FloorBiome]:
    return FLOOR_BIOMES.get(biome_key)


def available_biomes(floor_num: int, world=None) -> List[FloorBiome]:
    """Biomy aktualnie dostępne dla danego piętra. Filtruje po:
      * floor_min <= floor_num <= floor_max
      * enabled is True
      * starting_unlocked OR meta_unlock_key satysfakcjonowany"""
    out = []
    for b in FLOOR_BIOMES.values():
        if not b.enabled:
            continue
        if floor_num < b.floor_min or floor_num > b.floor_max:
            continue
        if b.starting_unlocked:
            out.append(b)
            continue
        # Meta-unlock check.
        if b.meta_unlock_key and _is_biome_meta_unlocked(b.meta_unlock_key):
            out.append(b)
    return out


def _is_biome_meta_unlocked(unlock_key: str) -> bool:
    """Sprawdza run_history.meta()["unlocks"] przez meta_progression.
    Bezpiecznie zwraca False jeśli moduł nie załadowany."""
    try:
        from ..engine import meta_progression as _mp
        return _mp.is_unlocked(unlock_key)
    except Exception:
        return False
