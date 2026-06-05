"""P29.42c — Aktywacja 4 biomów Tier-1 + content.

Pokrywa:
* fabryka_pary / stacja_orbital / kuznia_polorkow / biblioteka_miejska
  są enabled w FLOOR_BIOMES
* Każdy biome ma ≥5 pokoi w room_pool
* Każdy biome ma ≥5 mobów w MON (3 combat + 1 miniboss + 1 floor_boss)
* Każdy biome ma ≥1 materiał biome-locked
* Każdy biome ma ≥1 biome-locked recipe
* Generator F5 może wylosować nowe biomy
"""
from __future__ import annotations

from ..content.data import room_pool as _rp
from ..content.data.entity_templates import MON
from ..content.data import floor_biomes as _fb
from ..content import materials as _mat
from ..content.data import experimental_recipes as _exp


NEW_BIOMES = ("fabryka_pary", "stacja_orbital",
              "kuznia_polorkow", "biblioteka_miejska")

BIOME_ROOM_TAG = {
    "fabryka_pary":       "steampunk_factory",
    "stacja_orbital":     "orbital",
    "kuznia_polorkow":    "forge",
    "biblioteka_miejska": "library",
}


def test_all_four_biomes_enabled():
    for key in NEW_BIOMES:
        b = _fb.FLOOR_BIOMES[key]
        assert b.enabled, f"biome {key} powinien być enabled"


def test_each_biome_has_min_5_rooms():
    for key, tag in BIOME_ROOM_TAG.items():
        n = sum(1 for t in _rp.ROOM_POOL if tag in t.get("tags", []))
        assert n >= 5, f"biome {key}: ma {n} pokoi, expected ≥5"


def test_each_biome_has_min_5_mobs():
    for key, tag in BIOME_ROOM_TAG.items():
        n = sum(1 for k, v in MON.items()
                if tag in v.get("tags", []))
        assert n >= 5, f"biome {key}: ma {n} mobów, expected ≥5"


def test_each_biome_has_miniboss():
    for key, tag in BIOME_ROOM_TAG.items():
        mini = [k for k, v in MON.items()
                if tag in v.get("tags", [])
                and "miniboss" in v.get("tags", [])]
        assert len(mini) >= 1, (
            f"biome {key}: brak minibossa (tag={tag!r})")


def test_each_biome_has_floor_boss():
    for key, tag in BIOME_ROOM_TAG.items():
        bs = [k for k, v in MON.items()
              if tag in v.get("tags", [])
              and "floor_boss" in v.get("tags", [])]
        assert len(bs) >= 1, (
            f"biome {key}: brak floor_boss (tag={tag!r})")


def test_each_biome_has_locked_material():
    for key in NEW_BIOMES:
        tag = f"biome:{key}"
        n = sum(1 for m in _mat.MATERIALS.values() if tag in m.tags)
        assert n >= 1, (
            f"biome {key}: brak materiału z tagiem {tag!r}")


def test_each_biome_has_locked_recipe():
    for key in NEW_BIOMES:
        recipes = _exp.recipes_for_biome(key)
        assert len(recipes) >= 1, (
            f"biome {key}: brak biome-locked recipe")


def test_new_biomes_can_generate_in_floor():
    """30 seedów F5 — przynajmniej 1 z nowych biomów się pojawia."""
    from ..engine import floor_generator as _fg
    from ..engine.world import WorldState
    from ..engine.character import Character

    hits = set()
    for seed in range(1, 31):
        w = WorldState()
        w.character = Character(name="T", background="janitor")
        f = _fg.generate_floor(w, floor_number=5, seed=seed)
        hits.add(f.biome_key)
    new_hit = hits & set(NEW_BIOMES)
    assert len(new_hit) >= 1, (
        f"żaden z 4 nowych biomów nie wylosował się w 30 seedach: "
        f"hits={hits}")


def test_mob_names_polish_only():
    """Sanity: nowe moby mają polskie nazwy/opisy."""
    NEW_MOB_KEYS = {
        "konserwator_kotla", "manometrowiec", "smarownik_pasow",
        "miniboss_brygadzista_kuzni", "boss_palacz_sterling",
        "technik_sluzy", "drono_sprzatacz", "pasazer_zaginiony",
        "miniboss_kapitan_doku", "boss_komandor_proznii",
        "podkowiarz_polork", "wegielnik_kuzni", "mlociarz_cechowy",
        "miniboss_majster_cechu", "boss_starszy_cechu",
        "bibliotekarz_zlowieszczy", "czytelnik_zaginiony",
        "indeksowy_robak", "miniboss_archiwista_zakazany",
        "boss_konserwator_zbiorow",
    }
    BAD = (" the ", " your ", " with ", " and ", " for ",
           "showrunner")
    for key in NEW_MOB_KEYS:
        v = MON.get(key)
        assert v is not None, f"brak moba {key}"
        name = (v.get("fallback_name") or "").lower()
        desc = (v.get("fallback_desc") or "").lower()
        for bad in BAD:
            assert bad not in name, (
                f"{key} name leak {bad!r}: {name!r}")
            assert bad not in desc, (
                f"{key} desc leak {bad!r}: {desc!r}")
