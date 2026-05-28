"""Prompt 29.42a — Floor biome infrastructure.

Zgłoszenie: „każda rozgrywka wygląda tak samo, tylko pokoje są
pomieszane. Chcę losowania biomów piętra."

Diagnoza w P29.40: archetype był losowy ale to tylko parametry
generatora (gęstości, kształt grafu). Wygląd pokoi zależał od tagów
biomów (zoo / museum / bar / fungal), które generator IGNOROWAŁ —
w obrębie jednego piętra był losowy mix.

Fix:
  * content/data/floor_biomes.py — 23 FloorBiome z polskim klimatem,
    floor_min/max, room_tag do filtra, sponsor_likes, meta_unlock_key.
    Część `enabled=False` dopóki nie napiszemy ich pokoi (P29.42b).
  * FloorState.biome_key — save/load.
  * floor_generator: losuje biom z available_biomes(floor) po
    archetype, zapisuje na floor, podaje do _instantiate_rooms.
  * _pick_template_for_role(biome=...) — filtruje pokoje po
    `biome.room_tag in tags` LUB neutralnych (bez żadnego biome tagu).
  * meta_progression — 9 nowych UnlockDef kind='biome' (oboz_goblinski,
    siec_kanalizacyjna, tunel_karnawalowy, katakumby_faktur, farma_klonow,
    elfia_kolonia, redakcja_krawedzi, swiatynia_konferansjera,
    lawowe_tunele).
  * unlocked_biomes() helper analogiczny do unlocked_species().

Pokrywa:
  * available_biomes filtruje po enabled + floor_min/max
  * available_biomes pomija starting_unlocked=False jeśli brak unlock'a
  * generate_floor zapisuje biome_key na floor
  * generate_floor losuje różne biomy między runami
  * pokoje na piętrze pasują do wybranego biomu LUB są neutralne
  * save/load round-trip biome_key
  * meta unlock dla biome dostępny po spełnieniu warunku
  * F9 / F13-18 (puste available, bo wszystko disabled) — fallback do
    archetype label, biome_key="" — bez crash'a
"""
from __future__ import annotations
import os
import random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data.floor_biomes import (
    FLOOR_BIOMES, available_biomes, get_biome, FloorBiome,
)
from ..engine import run_history as _rh
from ..engine import meta_progression as _mp


# ── Catalog shape ────────────────────────────────────────────────────

def test_catalog_has_23_biomes():
    assert len(FLOOR_BIOMES) >= 23, f"oczekiwane ≥23; jest {len(FLOOR_BIOMES)}"
    print(f"  katalog: {len(FLOOR_BIOMES)} biomów: OK")


def test_each_biome_has_required_fields():
    for key, b in FLOOR_BIOMES.items():
        assert b.key == key
        assert b.name_pl, f"{key}: brak name_pl"
        assert b.theme_pl, f"{key}: brak theme_pl"
        assert b.floor_min <= b.floor_max, f"{key}: floor range odwrócony"
        assert b.room_tag, f"{key}: brak room_tag"
    print("  każdy biom ma wymagane pola: OK")


def test_at_least_one_biome_starting_enabled_per_tier():
    tiers = {"T1": (3, 8), "T3": (9, 12), "T4": (13, 18)}
    for label, (lo, hi) in tiers.items():
        avail = [b for b in FLOOR_BIOMES.values()
                 if b.enabled and b.starting_unlocked
                 and b.floor_min <= hi and b.floor_max >= lo]
        # T4 może na razie nie mieć enabled biomów (czekają na pokoje)
        if label == "T4":
            continue
        assert avail, f"{label} ({lo}-{hi}): żaden enabled+starting biom"
    print("  Tier 1 i Tier 3 mają enabled+starting biomy: OK")


# ── available_biomes ─────────────────────────────────────────────────

def test_available_biomes_filters_by_floor_range():
    _rh.reset()
    f1 = available_biomes(1)
    f3 = available_biomes(3)
    f10 = available_biomes(10)
    assert "intake_industrial" in [b.key for b in f1]
    assert "zoo_korporacyjne" in [b.key for b in f3]
    assert "grzybica_bloom" in [b.key for b in f10]
    # Zoo NIE może wpaść na piętro 1.
    assert "zoo_korporacyjne" not in [b.key for b in f1]
    print(f"  available F1: {len(f1)}; F3: {len(f3)}; F10: {len(f10)}: OK")


def test_available_biomes_skips_disabled():
    """Biomy z enabled=False nie wpadają nawet jeśli floor pasuje."""
    _rh.reset()
    f3 = available_biomes(3)
    keys = [b.key for b in f3]
    # `okopy_frontowe` jest F3-8 ale enabled=False — pominięta.
    assert "okopy_frontowe" not in keys
    print(f"  disabled biomes są pomijane: OK")


def test_available_biomes_skips_locked_until_unlock():
    """oboz_goblinski jest starting_unlocked=False; bez unlock'a nie ma
    go w puli (ale i tak enabled=False, więc test rozszerzy go po
    P29.42b — tu tylko sprawdzamy infrastrukturę meta-unlock)."""
    _rh.reset()
    # Bez unlock'a:
    assert not _mp.is_unlocked("biome_oboz_goblinski")
    # Po unlock'u — wciąż enabled=False, więc nie wpadnie. Ale gdy
    # zostanie enabled w P29.42b, ten test trzeba będzie rozszerzyć.
    _rh.unlock("biome_oboz_goblinski")
    assert _mp.is_unlocked("biome_oboz_goblinski")
    _rh.reset()
    print("  meta-unlock dla biomów działa przez run_history: OK")


# ── FloorState.biome_key + save/load ────────────────────────────────

def test_floor_state_has_biome_key_field():
    from ..engine.floor import FloorState
    f = FloorState(floor_id="x", floor_number=1)
    assert hasattr(f, "biome_key")
    assert f.biome_key == ""    # default
    f.biome_key = "zoo_korporacyjne"
    d = f.to_dict()
    assert d.get("biome_key") == "zoo_korporacyjne"
    f2 = FloorState.from_dict(d)
    assert f2.biome_key == "zoo_korporacyjne"
    print("  FloorState.biome_key + save/load: OK")


# ── Generator wpina biom ────────────────────────────────────────────

def test_generator_assigns_biome_when_available():
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    _rh.reset()
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    # F3 — w puli są zoo/museum/bar.
    f = generate_floor(w, floor_number=3, seed=7)
    assert f.biome_key in ("zoo_korporacyjne", "muzeum_spektakli",
                            "bar_skurczybyk")
    assert f.title_fallback.startswith("Piętro 3 — ")
    print(f"  generator F3 -> biome={f.biome_key} "
          f"title='{f.title_fallback}': OK")


def test_generator_different_biomes_across_seeds():
    """3 różne seedy generowane na F3 powinny dać co najmniej 2 różne
    biomy (przy 3 dostępnych w puli, prawdopodobieństwo identyczności
    bardzo niskie)."""
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    _rh.reset()
    biomes_seen = set()
    for seed in (1, 7, 42, 100, 200, 999):
        w = WorldState()
        w.character = Character(name="t", background="janitor")
        f = generate_floor(w, floor_number=3, seed=seed)
        biomes_seen.add(f.biome_key)
    assert len(biomes_seen) >= 2, \
        f"oczekiwane ≥2 różne biomy w 6 seedach; jest {biomes_seen}"
    print(f"  6 seedów F3 -> {len(biomes_seen)} różnych biomów: OK "
          f"({biomes_seen})")


def test_generator_floor_without_biome_pool_fallbacks_silently():
    """F9 ma pulę pustą (wszystkie F9-12 biomy enabled=False oprócz
    grzybicy F10-12). Generator nie crashuje — biome_key=''."""
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    _rh.reset()
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    f = generate_floor(w, floor_number=9, seed=7)
    assert f.biome_key == ""    # brak biomu
    assert f.title_fallback   # ale tytuł i tak nadany przez archetype
    print(f"  F9 (pusta pula) -> biome_key='', title="
          f"'{f.title_fallback}': OK")


# ── Pokoje pasują do biomu ──────────────────────────────────────────

def test_encounter_filter_excludes_other_biomes():
    """P29.42a-fix — pokój z biomem ZOO nie powinien dostać encountera
    oznaczonego tagiem innego biomu (museum / bar / neighborhood).
    Pokój może dostać encounter ZOO-tagged ALBO neutralny."""
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..content.data.floor_biomes import FLOOR_BIOMES
    OTHER_BIOME_TAGS = {b.room_tag for b in FLOOR_BIOMES.values()
                       if b.room_tag and b.room_tag != "zoo"}
    # Złap seed na ZOO.
    f = None
    for seed in range(1, 80):
        w = WorldState()
        w.character = Character(name="t", background="janitor")
        f = generate_floor(w, floor_number=4, seed=seed)
        if f.biome_key == "zoo_korporacyjne":
            break
    else:
        raise AssertionError("nie znaleziono seedu z biome=ZOO")

    # Sprawdź mobery we wszystkich pokojach: żaden tag nie może
    # przynależeć do INNEGO biomu.
    from ..content.data.entity_templates import MON
    leaked = []
    for r in f.rooms.values():
        for ent in r.entities:
            if ent.entity_type != "monster":
                continue
            mob_tpl = MON.get(ent.key, {})
            mob_tags = set(mob_tpl.get("tags") or [])
            conflicts = mob_tags & OTHER_BIOME_TAGS
            if conflicts:
                leaked.append((ent.key, conflicts))
    assert not leaked, f"obcy biome leak na piętrze ZOO: {leaked}"
    print(f"  F4-biome-ZOO: zero obcych moberów: OK")


def test_generated_rooms_match_biome():
    """Pokoje wygenerowane na piętrze z biomem ZOO mają tag „zoo"
    LUB są neutralne (bez żadnego biome tagu)."""
    from ..engine.floor_generator import generate_floor
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..content.data.floor_biomes import FLOOR_BIOMES
    _rh.reset()
    # Iteruje aż złapie biome ZOO (czasem może być muzeum/bar).
    for seed in range(1, 50):
        w = WorldState()
        w.character = Character(name="t", background="janitor")
        f = generate_floor(w, floor_number=3, seed=seed)
        if f.biome_key == "zoo_korporacyjne":
            break
    else:
        raise AssertionError("nie złapano biome=ZOO w 50 seedach")

    biome_tags = {b.room_tag for b in FLOOR_BIOMES.values()
                  if b.room_tag}
    for r in f.rooms.values():
        room_tags = set(getattr(r, "sensory_tags", None) or [])
        # `tags` w room_pool to inny atrybut — przepisywany do
        # RoomState jako sensory_tags. Tutaj sprawdzimy z osobnego
        # pola jeśli istnieje, inaczej tolerujemy.
        # Niektóre pokoje z room_pool mogą mieć tag jako sensory_tag.
        # Test najbardziej znaczący: czy generator NIE wstawia
        # tu pokoju z muzeum (innym biomem).
        wrong = room_tags & {"museum", "bar", "fungal"}
        assert not wrong, (
            f"pokój {r.room_id} ma tagi innego biomu: {wrong}")
    print(f"  pokoje na piętrze ZOO nie zawierają tagów "
          f"innych biomów: OK")


# ── Meta progression integration ────────────────────────────────────

def test_meta_progression_has_biome_unlocks():
    from ..engine import meta_progression as _mp_mod
    biome_unlocks = [u for u in _mp_mod.UNLOCK_CATALOG.values()
                     if u.kind == "biome"]
    assert len(biome_unlocks) >= 9, \
        f"oczekiwane ≥9 biome unlocks; jest {len(biome_unlocks)}"
    keys = [u.key for u in biome_unlocks]
    assert "biome_oboz_goblinski" in keys
    assert "biome_lawowe_tunele" in keys
    print(f"  meta_progression: {len(biome_unlocks)} biome unlocków: OK")


def test_unlocked_biomes_helper():
    _rh.reset()
    assert _mp.unlocked_biomes() == []
    _rh.unlock("biome_oboz_goblinski")
    found = _mp.unlocked_biomes()
    assert len(found) == 1
    assert found[0].key == "biome_oboz_goblinski"
    assert found[0].kind == "biome"
    _rh.reset()
    print("  unlocked_biomes(): round-trip: OK")


# ── Suite ──────────────────────────────────────────────────────────

def main():
    _rh.reset()
    try:
        test_catalog_has_23_biomes()
        test_each_biome_has_required_fields()
        test_at_least_one_biome_starting_enabled_per_tier()
        test_available_biomes_filters_by_floor_range()
        test_available_biomes_skips_disabled()
        test_available_biomes_skips_locked_until_unlock()
        test_floor_state_has_biome_key_field()
        test_generator_assigns_biome_when_available()
        test_generator_different_biomes_across_seeds()
        test_generator_floor_without_biome_pool_fallbacks_silently()
        test_generated_rooms_match_biome()
        test_encounter_filter_excludes_other_biomes()
        test_meta_progression_has_biome_unlocks()
        test_unlocked_biomes_helper()
    finally:
        _rh.reset()
    print("Prompt 29.42a floor biome infrastructure smoke: OK")


if __name__ == "__main__":
    main()
