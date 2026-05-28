"""Prompt 29.1 — floors 3-6 themed content smoke suite.

Covers:
  * 12 new room templates (3 per floor × 4 floors) are loaded with
    correct floor_min gating
  * floor_max gate works (pool_relay_boss now floor 2 only)
  * 20 new monsters (5 per floor × 4 floors) load from MON
  * Each monster has a salvage table in monster_salvage.py
  * Sponsors map correctly: 3=czarny_rynek, 4=ministerstwo,
    5=recykling, 6=kanal_7
  * generate_floor(N) for N=3..6 returns a valid floor with at least
    one floor-themed room and one floor-themed monster spawned
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data import room_pool as _rp
from ..content.data import entity_templates as _et
from ..content.data import monster_salvage as _ms
from ..content.data import sponsors as _sp


# P29.42a — biom piętra jest teraz LOSOWANY z zoo / neighborhood /
# museum / bar dla F3-8. Test akceptuje monstery z dowolnego z 4
# biomów, bo nie wiemy z góry który wylosuje generator dla danego seedu.
_ANY_F3_8_THEMED_MONSTERS = {
    # zoo
    "mutant_szczur", "klatkowy_kot", "bekajacy_paw",
    "miniboss_alfa_szczur", "boss_panicz_zoo",
    # neighborhood
    "usmiechniety_sasiad", "dzieciak_z_blokowiska",
    "kucharka_z_swietlicy", "miniboss_oddzialowa", "boss_blok_parent",
    # museum
    "kostny_kurator", "duch_zwiedzajacego", "mechaniczny_strazak",
    "miniboss_strazak_galerii", "boss_kurator_naczelny",
    # bar
    "pijany_crawler", "lokator_baru", "bramkarz",
    "miniboss_szef_baru", "boss_showman",
}


# ── Data layer ───────────────────────────────────────────────────────────

def test_new_room_templates_present():
    template_ids = {t["template_id"] for t in _rp.ROOM_POOL}
    expected = {
        # floor 3
        "pool_cage_block", "pool_feeding_pit", "pool_zoo_boss",
        # floor 4
        "pool_kuchnia_sasiada", "pool_ogrod_szczescia",
        "pool_swietlica_boss",
        # floor 5
        "pool_galeria", "pool_magazyn_relikwii", "pool_kurator_boss",
        # floor 6
        "pool_glowna_sala_baru", "pool_zaplecze_bar",
        "pool_balkon_vip_boss",
    }
    missing = expected - template_ids
    assert not missing, f"missing room templates: {missing}"
    print(f"  12 floor-3..6 room templates present: OK")


def test_floor_min_gates_correctly():
    """Each themed template has floor_min set to its floor number."""
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    expected_floor_min = {
        "pool_cage_block": 3, "pool_feeding_pit": 3, "pool_zoo_boss": 3,
        "pool_kuchnia_sasiada": 4, "pool_ogrod_szczescia": 4,
        "pool_swietlica_boss": 4,
        "pool_galeria": 5, "pool_magazyn_relikwii": 5,
        "pool_kurator_boss": 5,
        "pool_glowna_sala_baru": 6, "pool_zaplecze_bar": 6,
        "pool_balkon_vip_boss": 6,
    }
    for tid, expected_fm in expected_floor_min.items():
        assert by_id[tid].get("floor_min") == expected_fm, \
            f"{tid}: floor_min should be {expected_fm}"
    print(f"  floor_min gates set correctly on all 12: OK")


def test_relay_boss_capped_at_floor_2():
    """Old generic boss should NOT spawn on floors 3-6 anymore."""
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    assert by_id["pool_relay_boss"].get("floor_max") == 2
    print(f"  pool_relay_boss capped to floor 2: OK")


def test_new_monsters_present_in_MON():
    expected = {
        # floor 3
        "mutant_szczur", "klatkowy_kot", "bekajacy_paw",
        "miniboss_alfa_szczur", "boss_panicz_zoo",
        # floor 4
        "usmiechniety_sasiad", "dzieciak_z_blokowiska",
        "kucharka_z_swietlicy", "miniboss_oddzialowa",
        "boss_blok_parent",
        # floor 5
        "kostny_kurator", "duch_zwiedzajacego", "mechaniczny_strazak",
        "miniboss_strazak_galerii", "boss_kurator_naczelny",
        # floor 6
        "pijany_crawler", "lokator_baru", "bramkarz",
        "miniboss_szef_baru", "boss_showman",
    }
    missing = expected - set(_et.MON.keys())
    assert not missing, f"missing MON entries: {missing}"
    # Verify HP got scaled by _apply_balance_scale (×5)
    assert _et.MON["mutant_szczur"]["hp"] >= 12 * 5
    print(f"  20 new monsters present + balance-scaled: OK")


def test_new_monsters_have_salvage_tables():
    expected = {
        "mutant_szczur", "klatkowy_kot", "bekajacy_paw",
        "miniboss_alfa_szczur", "boss_panicz_zoo",
        "usmiechniety_sasiad", "dzieciak_z_blokowiska",
        "kucharka_z_swietlicy", "miniboss_oddzialowa", "boss_blok_parent",
        "kostny_kurator", "duch_zwiedzajacego", "mechaniczny_strazak",
        "miniboss_strazak_galerii", "boss_kurator_naczelny",
        "pijany_crawler", "lokator_baru", "bramkarz",
        "miniboss_szef_baru", "boss_showman",
    }
    missing = expected - set(_ms.CORPSE_TEMPLATES.keys())
    assert not missing, f"missing monster_salvage entries: {missing}"
    # Each should have salvage + name_pl
    for key in expected:
        tbl = _ms.CORPSE_TEMPLATES[key]
        assert "name_pl" in tbl, f"{key} missing name_pl"
        assert "salvage" in tbl, f"{key} missing salvage dict"
        assert tbl["salvage"], f"{key} salvage dict empty"
    print(f"  20 salvage tables complete: OK")


def test_themed_rooms_carry_sponsor_boost():
    """P29.2 — themed rooms NUDGE specific sponsors instead of
    locking them. Each floor's templates declare theme_sponsor_boost.
    """
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    expected = {
        "pool_cage_block":         _sp.SPONSOR_CZARNY_RYNEK,
        "pool_zoo_boss":           _sp.SPONSOR_CZARNY_RYNEK,
        "pool_kuchnia_sasiada":    _sp.SPONSOR_MINISTERSTWO,
        "pool_swietlica_boss":     _sp.SPONSOR_MINISTERSTWO,
        "pool_galeria":            _sp.SPONSOR_RECYKLING,
        "pool_kurator_boss":       _sp.SPONSOR_RECYKLING,
        "pool_glowna_sala_baru":   _sp.SPONSOR_KANAL_7,
        "pool_balkon_vip_boss":    _sp.SPONSOR_KANAL_7,
    }
    for tid, expected_key in expected.items():
        boost = by_id[tid].get("theme_sponsor_boost", {})
        assert expected_key in boost, \
            f"{tid} should boost {expected_key}; got boost={boost}"
    print(f"  themed rooms nudge their sponsors via theme_sponsor_boost: OK")


# ── Floor generation ────────────────────────────────────────────────────

def _generated_themed_template_count(floor, expected_prefixes):
    """How many rooms on the floor were built from one of the new
    floor-N templates (we tag rooms with template_id internally)."""
    n = 0
    for r in floor.rooms.values():
        for ev in (r.state or {}).get("source_template", "") or "":
            pass
    # Easier: check entity_seed_pools were drawn from new monsters.
    new_monster_keys = {
        # floor 3
        "mutant_szczur", "klatkowy_kot", "bekajacy_paw",
        "miniboss_alfa_szczur", "boss_panicz_zoo",
        # floor 4
        "usmiechniety_sasiad", "dzieciak_z_blokowiska",
        "kucharka_z_swietlicy", "miniboss_oddzialowa", "boss_blok_parent",
        # floor 5
        "kostny_kurator", "duch_zwiedzajacego", "mechaniczny_strazak",
        "miniboss_strazak_galerii", "boss_kurator_naczelny",
        # floor 6
        "pijany_crawler", "lokator_baru", "bramkarz",
        "miniboss_szef_baru", "boss_showman",
    }
    for r in floor.rooms.values():
        for ent in r.entities:
            if ent.key in new_monster_keys:
                n += 1
    return n


def test_generate_floor_3_uses_themed_monsters():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine import floor_generator as _fg
    w = WorldState(); w.character = Character(name="N", background="janitor")
    f = _fg.generate_floor(w, floor_number=3, seed=42)
    monsters_used = set()
    for r in f.rooms.values():
        for ent in r.entities:
            if ent.entity_type == "monster":
                monsters_used.add(ent.key)
    # P29.42a — biom piętra jest teraz LOSOWY (zoo / neighborhood /
    # museum / bar — losowanie z 3 enabled). Test akceptuje dowolny
    # zestaw themed monsters z tych biomów.
    themed = monsters_used & _ANY_F3_8_THEMED_MONSTERS
    assert themed, f"floor 3 had no themed monsters; got {monsters_used}"
    print(f"  floor 3 spawned themed monsters: {themed}: OK")


def test_generate_floor_4_uses_themed_monsters():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine import floor_generator as _fg
    w = WorldState(); w.character = Character(name="N", background="janitor")
    f = _fg.generate_floor(w, floor_number=4, seed=42)
    monsters_used = set()
    for r in f.rooms.values():
        for ent in r.entities:
            if ent.entity_type == "monster":
                monsters_used.add(ent.key)
    themed = monsters_used & _ANY_F3_8_THEMED_MONSTERS
    assert themed, f"floor 4 had no themed monsters; got {monsters_used}"
    print(f"  floor 4 spawned themed monsters: {themed}: OK")


def test_generate_floor_5_uses_themed_monsters():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine import floor_generator as _fg
    w = WorldState(); w.character = Character(name="N", background="janitor")
    f = _fg.generate_floor(w, floor_number=5, seed=42)
    monsters_used = set()
    for r in f.rooms.values():
        for ent in r.entities:
            if ent.entity_type == "monster":
                monsters_used.add(ent.key)
    themed = monsters_used & _ANY_F3_8_THEMED_MONSTERS
    assert themed, f"floor 5 had no themed monsters; got {monsters_used}"
    print(f"  floor 5 spawned themed monsters: {themed}: OK")


def test_generate_floor_6_uses_themed_monsters():
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine import floor_generator as _fg
    w = WorldState(); w.character = Character(name="N", background="janitor")
    f = _fg.generate_floor(w, floor_number=6, seed=42)
    monsters_used = set()
    for r in f.rooms.values():
        for ent in r.entities:
            if ent.entity_type == "monster":
                monsters_used.add(ent.key)
    themed = monsters_used & _ANY_F3_8_THEMED_MONSTERS
    assert themed, f"floor 6 had no themed monsters; got {monsters_used}"
    print(f"  floor 6 spawned themed monsters: {themed}: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_new_room_templates_present()
    test_floor_min_gates_correctly()
    test_relay_boss_capped_at_floor_2()
    test_new_monsters_present_in_MON()
    test_new_monsters_have_salvage_tables()
    test_themed_rooms_carry_sponsor_boost()
    test_generate_floor_3_uses_themed_monsters()
    test_generate_floor_4_uses_themed_monsters()
    test_generate_floor_5_uses_themed_monsters()
    test_generate_floor_6_uses_themed_monsters()
    print("Prompt 29.1 floors 3-6 content smoke: OK")


if __name__ == "__main__":
    main()
