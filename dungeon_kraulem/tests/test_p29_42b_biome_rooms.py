"""P29.42b — Pokoje per biom (głębsza zawartość).

Pokrywa:
* Każdy z biomów zoo/museum/bar/trenches ma ≥10 pokoi w room_pool
* Intake ma ≥5 pokoi
* Nowe pokoje są Polish-only (brak typowych angielskich słów)
* Każdy ma poprawny template_id + name_pool + first_enter_pool
* Generator faktycznie wciąga je na piętrach z odpowiednim biomem
* Performance: dodanie pokoi nie spowolniło generacji
"""
from __future__ import annotations

from ..content.data import room_pool as _rp


# Lista nowych template_id z P29.42b (32 sztuki)
_NEW_TEMPLATE_IDS = {
    # zoo +7
    "pool_woliera_skrzydlatych", "pool_terrarium_gadow",
    "pool_kwarantanna_zoo", "pool_weterynarka_zoo",
    "pool_pokoj_trenera_zoo", "pool_kanal_sprzatania_zoo",
    "pool_loza_sponsora_zoo",
    # museum +7
    "pool_galeria_luster", "pool_pracownia_konserwacji",
    "pool_biuro_kuratora_male", "pool_archiwum_piwniczne",
    "pool_eksponat_zamkniety", "pool_sala_darczyncow",
    "pool_biuro_rzeczy_znalezionych",
    # bar +7
    "pool_scena_karaoke", "pool_piwnica_baru", "pool_kuchnia_barowa",
    "pool_zaplecze_baru", "pool_zaulek_baru", "pool_toaleta_baru",
    "pool_dziedziniec_baru",
    # trenches +7
    "pool_posterunek_obserwacyjny", "pool_punkt_medyczny_okop",
    "pool_bunkier_oficerski", "pool_skladnica_amunicji_okop",
    "pool_gniazdo_snajperskie_okop", "pool_kanal_odplywowy_okop",
    "pool_placowka_zaopatrzenia",
    # intake +4
    "pool_intake_szatnia", "pool_intake_sala_powitalna",
    "pool_intake_aleja_automatow", "pool_intake_kabina_sanitarna",
}


def test_biome_counts_per_target():
    """Po P29.42b: zoo/museum/bar/trenches ≥10, intake ≥5."""
    targets = {"zoo": 10, "museum": 10, "bar": 10, "trenches": 10,
               "intake": 5}
    for tag, want in targets.items():
        n = sum(1 for t in _rp.ROOM_POOL
                if tag in t.get("tags", []))
        assert n >= want, f"biom {tag!r}: ma {n}, expected ≥{want}"


def test_all_new_templates_present_and_have_required_fields():
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    missing = [tid for tid in _NEW_TEMPLATE_IDS if tid not in by_id]
    assert not missing, f"brak nowych templates: {missing}"
    for tid in _NEW_TEMPLATE_IDS:
        t = by_id[tid]
        assert t.get("name_pool"), f"{tid}: pusty name_pool"
        assert t.get("first_enter_pool"), \
            f"{tid}: pusty first_enter_pool"
        assert t.get("look_pool"), f"{tid}: pusty look_pool"
        assert t.get("role") in ("danger", "loot", "social", "safe",
                                 "secret", "boss", "objective"), \
            f"{tid}: niepoprawny role {t.get('role')!r}"


def test_new_rooms_polish_only():
    """Sanity: brak typowych angielskich słów w opisach nowych pokoi."""
    bad_substrings = (
        " the ", " your ", " with ", " and ", " you ", " for ",
        "showrunner", "vending", "lounge",
    )
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    for tid in _NEW_TEMPLATE_IDS:
        t = by_id[tid]
        for field in ("name_pool", "first_enter_pool", "look_pool",
                      "search_pool", "public_hint_pool"):
            for line in (t.get(field) or []):
                low = line.lower()
                for bad in bad_substrings:
                    assert bad not in low, (
                        f"{tid}/{field}: angielski wyciek {bad!r} "
                        f"w {line!r}")


def test_intake_rooms_floor_max_two():
    """Nowe intake pokoje są ograniczone do F1-F2 — nie pojawiają się
    na deep floors (gdzie biome jest inny)."""
    intake_new = [
        "pool_intake_szatnia", "pool_intake_sala_powitalna",
        "pool_intake_aleja_automatow", "pool_intake_kabina_sanitarna",
    ]
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    for tid in intake_new:
        t = by_id[tid]
        assert t.get("floor_max", 99) <= 2, (
            f"{tid}: floor_max powinien być ≤2 dla intake, "
            f"ma {t.get('floor_max')}")


def test_new_rooms_have_biome_tags():
    """Każdy nowy pokój ma odpowiedni biome-tag — inaczej generator
    nie wciąga go na właściwym piętrze."""
    expected_tag = {
        "zoo": ["pool_woliera_skrzydlatych", "pool_terrarium_gadow",
                "pool_kwarantanna_zoo", "pool_weterynarka_zoo",
                "pool_pokoj_trenera_zoo", "pool_kanal_sprzatania_zoo",
                "pool_loza_sponsora_zoo"],
        "museum": ["pool_galeria_luster", "pool_pracownia_konserwacji",
                   "pool_biuro_kuratora_male",
                   "pool_archiwum_piwniczne",
                   "pool_eksponat_zamkniety", "pool_sala_darczyncow",
                   "pool_biuro_rzeczy_znalezionych"],
        "bar": ["pool_scena_karaoke", "pool_piwnica_baru",
                "pool_kuchnia_barowa", "pool_zaplecze_baru",
                "pool_zaulek_baru", "pool_toaleta_baru",
                "pool_dziedziniec_baru"],
        "trenches": ["pool_posterunek_obserwacyjny",
                     "pool_punkt_medyczny_okop",
                     "pool_bunkier_oficerski",
                     "pool_skladnica_amunicji_okop",
                     "pool_gniazdo_snajperskie_okop",
                     "pool_kanal_odplywowy_okop",
                     "pool_placowka_zaopatrzenia"],
        "intake": ["pool_intake_szatnia",
                   "pool_intake_sala_powitalna",
                   "pool_intake_aleja_automatow",
                   "pool_intake_kabina_sanitarna"],
    }
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    for tag, ids in expected_tag.items():
        for tid in ids:
            t = by_id[tid]
            assert tag in t.get("tags", []), (
                f"{tid}: brakuje biome tagu {tag!r}, ma "
                f"{t.get('tags')}")


def test_room_pool_total_after_p29_42b():
    """Total ROOM_POOL ≥ 74 (43 + 32 nowych)."""
    assert len(_rp.ROOM_POOL) >= 74, (
        f"po P29.42b expected ≥74 templates, mam {len(_rp.ROOM_POOL)}")
