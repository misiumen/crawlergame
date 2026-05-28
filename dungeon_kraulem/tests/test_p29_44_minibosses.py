"""Prompt 29.44 — Minibossy per piętro + drop kawałka mapy.

Zgłoszenie: „minibossów chyba powinno być więcej na piętro myśle,
plus każdy z nich powinien dropić kawałek mapy piętra."

Diagnoza: minibossowie istnieli w content/data/entity_templates jako
oddzielne wpisy z tagiem `miniboss`, ale GENERATOR nigdy ich nie
spawnował. Tylko bossy floor_boss wpadały na piętra. Minibossy były
content rot.

Fix:
  * floor_generator._place_minibosses(f, rng, world) — wstawia
    2-4 minibossów per piętro (skalowane do floor_number), losując
    z puli MON gdzie tag=`miniboss`, filtrowane po biom-tagu piętra
    + floor_min/max.
  * 2 uniwersalne minibossy bez biom-tagu (Kartograf-Dłużnik, Egzekutor
    Widowni) jako floater'y.
  * game._drop_miniboss_map_fragment — po zabiciu minibossa upuszcza
    map_fragment (F1-9) lub 50% szans na floor_map (F10+).

Pokrywa:
  * count per piętro zgodny z _miniboss_count_for_floor
  * placement w danger/loot, NIE w bossroomie
  * biome filter (miniboss z obcego biomu nie wpada)
  * miniboss z fmin/fmax respected
  * pula uniwersalnych minibossów istnieje
  * po transform_to_corpse + drop, map_fragment ląduje w pokoju
  * F1-2 → zero minibossów (intake)
  * 5 biome-specific minibossów (zoo/nbh/museum/bar/trenches) wciąż
    obecnych w katalogu
"""
from __future__ import annotations

from ..engine import run_history as _rh
from ..engine import floor_generator as _fg
from ..engine.world import WorldState
from ..engine.character import Character
from ..content.data.entity_templates import MON


# ── Helpers ──────────────────────────────────────────────────────────


def _new_world():
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    return w


def _generate_floor(floor_num: int, seed: int = 12345):
    w = _new_world()
    floor = _fg.generate_floor(w, floor_number=floor_num, seed=seed)
    return w, floor


def _minibosses_on_floor(floor):
    out = []
    for room in floor.rooms.values():
        for ent in room.entities:
            tags = ent.tags or []
            if "miniboss" in tags and "boss" not in tags:
                out.append((room.room_id, ent.key))
    return out


# ── Tests ────────────────────────────────────────────────────────────


def test_miniboss_count_scaling():
    """Skalowanie zgodne z _miniboss_count_for_floor."""
    assert _fg._miniboss_count_for_floor(1) == 0
    assert _fg._miniboss_count_for_floor(2) == 0
    assert _fg._miniboss_count_for_floor(3) == 2
    assert _fg._miniboss_count_for_floor(8) == 2
    assert _fg._miniboss_count_for_floor(9) == 3
    assert _fg._miniboss_count_for_floor(12) == 3
    assert _fg._miniboss_count_for_floor(15) == 3
    assert _fg._miniboss_count_for_floor(18) == 4
    print("  count scaling: 0/0/2/2/3/3/3/4: OK")


def test_low_floors_get_no_minibosses():
    _, f1 = _generate_floor(1)
    _, f2 = _generate_floor(2)
    assert _minibosses_on_floor(f1) == []
    assert _minibosses_on_floor(f2) == []
    print("  F1-2 (intake) bez minibossów: OK")


def test_mid_floor_gets_minibosses():
    """F3-8 dostają ~2 minibossów. Sprawdzamy 5 różnych seedów."""
    counts = []
    for s in (101, 202, 303, 404, 505):
        _, f = _generate_floor(4, seed=s)
        counts.append(len(_minibosses_on_floor(f)))
    # Generator może mieć mniej kandydatów niż n (mały floor) — więc
    # weryfikujemy że >=1 w większości przypadków, a średnia >= 1.5.
    avg = sum(counts) / len(counts)
    assert avg >= 1.5, f"za mało minibossów w średniej F4: {avg}"
    assert max(counts) >= 2, f"żaden run nie wbił 2 minibossów: {counts}"
    print(f"  F4 minibossy avg={avg:.1f}, max={max(counts)}: OK")


def test_miniboss_not_in_boss_room():
    """Miniboss nie pakuje się do pokoju z floor_boss."""
    for s in (1, 7, 42, 99):
        _, f = _generate_floor(5, seed=s)
        for room in f.rooms.values():
            if room.actual_type != "boss":
                continue
            keys = [e.key for e in room.entities]
            minis = [k for k in keys
                     if "miniboss" in (MON.get(k) or {}).get("tags", [])]
            assert not minis, f"miniboss w bossroomie: {minis}"
    print("  miniboss nigdy nie ląduje w bossroomie: OK")


def test_universal_minibosses_exist():
    """Floater'y bez biom-tagu (Kartograf-Dłużnik, Egzekutor Widowni)."""
    for key in ("miniboss_kartograf_dluznik",
                "miniboss_egzekutor_widowni"):
        tpl = MON.get(key)
        assert tpl is not None, f"brak {key} w MON"
        tags = tpl.get("tags") or []
        assert "miniboss" in tags
    print("  2 uniwersalne minibossy w katalogu: OK")


def test_biome_specific_minibosses_still_present():
    """Wcześniejsze minibossy F3-6 + okopowy (P29.42b) muszą zostać."""
    for key in ("miniboss_alfa_szczur", "miniboss_oddzialowa",
                "miniboss_strazak_galerii", "miniboss_szef_baru",
                "miniboss_sierzant_blachy"):
        assert key in MON, f"brak biome miniboss: {key}"
    print("  5 biome-specific minibossów w katalogu: OK")


def test_available_minibosses_respects_floor_range():
    """Helper _available_minibosses honoruje floor_min/max + biome."""
    # F3 z biomem zoo: powinien znaleźć alfa_szczura (F3-3, zoo)
    keys = _fg._available_minibosses(3, "zoo")
    assert "miniboss_alfa_szczur" in keys
    # Z biomem zoo nie powinien wpaść szef baru (bar-only).
    assert "miniboss_szef_baru" not in keys
    # F4 z biomem trenches: sierzant blachy (F4-7, trenches) — tak.
    keys = _fg._available_minibosses(4, "trenches")
    assert "miniboss_sierzant_blachy" in keys
    # Uniwersalny floater (bez biom-tagu) zawsze dostępny.
    assert "miniboss_kartograf_dluznik" in keys
    print("  _available_minibosses honoruje floor + biome filter: OK")


def test_miniboss_drop_map_fragment_on_kill():
    """Symulujemy zabicie minibossa — w pokoju powinien pojawić się
    map_fragment."""
    from ..engine.game import drop_miniboss_map

    w, f = _generate_floor(5, seed=42)
    mlist = _minibosses_on_floor(f)
    if not mlist:
        for s in (11, 22, 33, 88, 777):
            w, f = _generate_floor(5, seed=s)
            mlist = _minibosses_on_floor(f)
            if mlist:
                break
    assert mlist, "żaden seed nie dał minibossów"
    room_id, mkey = mlist[0]
    f.current_room_id = room_id
    room = f.current_room()
    target = next(e for e in room.entities if e.key == mkey)
    items_before = {e.key for e in room.entities
                    if (e.tags or []) and "map" in e.tags}
    it = drop_miniboss_map(w, room, target, f.floor_number or 5)
    assert it is not None
    items_after = {e.key for e in room.entities
                   if (e.tags or []) and "map" in e.tags}
    new = items_after - items_before
    assert new, f"nie spadł żaden map item, before={items_before}"
    assert "map_fragment" in new or "floor_map" in new
    print(f"  drop po zabiciu minibossa: {new}: OK")


def test_drop_picks_floor_map_for_deep_floors():
    """Na piętrach 10+ z 50% szans pada pełna mapa zamiast fragmentu.
    Sprawdzamy że przy wielu próbach co najmniej raz spadła floor_map."""
    from ..engine.game import drop_miniboss_map

    w, f = _generate_floor(11, seed=1)
    # Sztucznie postaw gracza w jakimś pokoju z miniboss-tagiem; jeśli
    # brak, użyjemy zwykłego pokoju + fake target.
    room = next(iter(f.rooms.values()))
    from ..engine.entity import Entity, T_MONSTER
    saw_floor_map = False
    for i in range(40):
        fake = Entity(key=f"miniboss_test_{i}", entity_type=T_MONSTER,
                      fallback_name="fake miniboss",
                      tags=["miniboss"], location_id=room.room_id)
        w.register(fake)
        it = drop_miniboss_map(w, room, fake, 11)
        if it is not None and it.key == "floor_map":
            saw_floor_map = True
            break
    assert saw_floor_map, "F11 nigdy nie dało floor_map mimo 40 prób"
    print("  F11 czasem dropuje floor_map zamiast fragment: OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_miniboss_count_scaling()
        test_low_floors_get_no_minibosses()
        test_mid_floor_gets_minibosses()
        test_miniboss_not_in_boss_room()
        test_universal_minibosses_exist()
        test_biome_specific_minibosses_still_present()
        test_available_minibosses_respects_floor_range()
        test_miniboss_drop_map_fragment_on_kill()
        test_drop_picks_floor_map_for_deep_floors()
    finally:
        _rh.reset()
    print("Prompt 29.44 minibosses + map drop smoke: OK")


if __name__ == "__main__":
    main()
