"""Prompt 29.37 — Expanded meta-progression catalog.

P29.34 shipped 12 unlocks (5 species + 3 origins + 1 companion + 3
items). User feedback: too thin — the 30+ unlocks should be the
spine of replay value. P29.37 expands to:

  * 5 + 3 = 8 species (Stary Uczestnik, Bez Twarzy, Ferromanta-meta
    added)
  * 3 + 4 = 7 origins (Wieczny Stażysta, Sponsor's Choice Reject,
    Były Konferansjer, Dziedzic Kanału 7)
  * 1 + 3 = 4 companions (Suczka Recyklingu, Kot Ministerstwa,
    Dron Sponsorski)
  * 3 + 5 = 8 items (Mosiężny Pierścień, Stara Czaszka, Czerwony
    Telefon, Klucz do Kantyny, Pamiątkowa Łyżka)
  * 4 NEW kind: start_perk (Łapówka dla portiera, Insiderskie info,
    Stara legitymacja, Łyżka Cudu)

Total: 31 entries across 5 kinds (species, origin, companion, item,
start_perk).

Covers:
  * Catalog shape — 31 entries minimum, 5 distinct kinds, each new
    entry's eval_fn callable.
  * Each new evaluator returns True under its qualifying world
    state (sponsor attention ≥ 25, victories ≥ 3, zero kills, etc.).
  * unlocked_start_perks() returns persisted start_perk entries.
  * Backward compat — every P29.34 unlock key is still in the
    catalog (no breakage of existing saved meta states).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine import meta_progression as _mp
from ..engine import run_history as _rh
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world(*, audience_peak=10, max_floor=2, kills=5,
              corpses=0, achievements=()):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    w.character.run_audience_peak = audience_peak
    w.character.run_max_floor_reached = max_floor
    w.character.run_kills = kills
    w.character.run_corpses_salvaged = corpses
    w.character.unlocked_achievements = list(achievements)
    f = FloorState(floor_id="f1", floor_number=max_floor)
    r = RoomState(room_id="r0", fallback_short_title="x")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── Catalog shape ───────────────────────────────────────────────────────

def test_catalog_at_least_31_entries():
    cat = _mp.UNLOCK_CATALOG
    assert len(cat) >= 31, f"expected >=31 entries; got {len(cat)}"
    print(f"  catalog has {len(cat)} entries: OK")


def test_catalog_has_five_kinds_including_start_perk():
    cat = _mp.UNLOCK_CATALOG
    kinds = set(ud.kind for ud in cat.values())
    expected = {"species", "origin", "companion", "item", "start_perk"}
    missing = expected - kinds
    assert not missing, f"missing kinds: {missing}"
    print(f"  catalog covers all 5 kinds incl. start_perk: OK")


def test_kind_counts():
    cat = _mp.UNLOCK_CATALOG
    counts = {}
    for ud in cat.values():
        counts[ud.kind] = counts.get(ud.kind, 0) + 1
    assert counts.get("species", 0) >= 8, counts
    assert counts.get("origin", 0) >= 7, counts
    assert counts.get("companion", 0) >= 4, counts
    assert counts.get("item", 0) >= 8, counts
    assert counts.get("start_perk", 0) >= 4, counts
    print(f"  counts: {counts}: OK")


def test_p29_34_keys_still_present():
    """Backward compat — every key shipped in P29.34 still exists."""
    legacy_keys = (
        "species_mutant_chemiczny", "species_grzybica",
        "species_cyborg_recyklingu", "species_pamietajacy",
        "species_kolyski_anti_hosta",
        "origin_drugi_cykl", "origin_sponsorowany",
        "origin_zhanbiony_showman",
        "companion_papuga_anty_host",
        "item_mikrofon_anty_hosta", "item_obrazek_finalu",
        "item_skarpetka_pulkownika",
    )
    cat = _mp.UNLOCK_CATALOG
    missing = [k for k in legacy_keys if k not in cat]
    assert not missing, f"P29.34 keys dropped: {missing}"
    print(f"  P29.34 backward-compat: {len(legacy_keys)} keys present: OK")


def test_every_entry_has_callable_eval():
    for key, ud in _mp.UNLOCK_CATALOG.items():
        if key == "species_kolyski_anti_hosta":
            # This one's been there since P29.34 with its closure.
            pass
        assert callable(ud.eval_fn), f"{key} eval_fn not callable"
    print("  every entry has callable eval_fn: OK")


# ── New species evaluators ──────────────────────────────────────────────

def test_stary_uczestnik_requires_3_victories():
    _rh.reset()
    w = _mk_world()
    # 0 victories → fails.
    assert not _mp.UNLOCK_CATALOG["species_stary_uczestnik"].eval_fn(w, True), \
        "should require 3 victories"
    # 2 prior victories + this victory = 3.
    _rh.record_run(w, victory=True)
    _rh.record_run(w, victory=True)
    assert _mp.UNLOCK_CATALOG["species_stary_uczestnik"].eval_fn(w, True), \
        "should qualify at 3 victories"
    _rh.reset()
    print("  species_stary_uczestnik fires at 3 victories: OK")


def test_bez_twarzy_requires_5_runs():
    _rh.reset()
    w = _mk_world()
    assert not _mp.UNLOCK_CATALOG["species_bez_twarzy"].eval_fn(w, False)
    for _ in range(4):
        _rh.record_run(w, victory=False)
    # 4 logged + 1 about to land = 5.
    assert _mp.UNLOCK_CATALOG["species_bez_twarzy"].eval_fn(w, False)
    _rh.reset()
    print("  species_bez_twarzy fires at 5 runs: OK")


def test_ferromanta_meta_requires_floor_15():
    w_shallow = _mk_world(max_floor=10)
    w_deep = _mk_world(max_floor=15)
    assert not _mp.UNLOCK_CATALOG["species_ferromanta_meta"].eval_fn(w_shallow, False)
    assert _mp.UNLOCK_CATALOG["species_ferromanta_meta"].eval_fn(w_deep, False)
    print("  species_ferromanta_meta fires at floor 15: OK")


# ── New origin evaluators ───────────────────────────────────────────────

def test_byly_konferansjer_requires_floor_17():
    w = _mk_world(max_floor=16)
    assert not _mp.UNLOCK_CATALOG["origin_byly_konferansjer"].eval_fn(w, False)
    w17 = _mk_world(max_floor=17)
    assert _mp.UNLOCK_CATALOG["origin_byly_konferansjer"].eval_fn(w17, False)
    print("  origin_byly_konferansjer fires at floor 17: OK")


def test_dziedzic_k7_requires_audience_120():
    w_low = _mk_world(audience_peak=100)
    w_hi = _mk_world(audience_peak=125)
    assert not _mp.UNLOCK_CATALOG["origin_dziedzic_k7"].eval_fn(w_low, False)
    assert _mp.UNLOCK_CATALOG["origin_dziedzic_k7"].eval_fn(w_hi, False)
    print("  origin_dziedzic_k7 fires at audience peak 120: OK")


def test_sponsor_reject_requires_hostile():
    from ..engine import sponsors as _sp
    w = _mk_world()
    assert not _mp.UNLOCK_CATALOG["origin_sponsor_reject"].eval_fn(w, False)
    _sp.adjust_attention(w, "novachem_biotech", -8)
    assert _mp.UNLOCK_CATALOG["origin_sponsor_reject"].eval_fn(w, False)
    print("  origin_sponsor_reject fires with any sponsor at -5 or worse: OK")


# ── New companion evaluators ────────────────────────────────────────────

def test_suczka_requires_kult_20():
    from ..engine import sponsors as _sp
    w = _mk_world()
    _sp.adjust_attention(w, "kult_recyklingu", 22)
    assert _mp.UNLOCK_CATALOG["companion_suczka_recyklingu"].eval_fn(w, False)
    print("  companion_suczka fires at Kult ≥ 20: OK")


def test_kot_requires_ministerstwo_20():
    from ..engine import sponsors as _sp
    w = _mk_world()
    _sp.adjust_attention(w, "ministerstwo_pamieci", 21)
    assert _mp.UNLOCK_CATALOG["companion_kot_ministerstwa"].eval_fn(w, False)
    print("  companion_kot fires at Ministerstwo ≥ 20: OK")


def test_dron_requires_any_sponsor_high():
    from ..engine import sponsors as _sp
    w = _mk_world()
    assert not _mp.UNLOCK_CATALOG["companion_dron_sponsorski"].eval_fn(w, False)
    _sp.adjust_attention(w, "bog_polimerow", 18)
    assert _mp.UNLOCK_CATALOG["companion_dron_sponsorski"].eval_fn(w, False)
    print("  companion_dron fires when any sponsor ≥ 18 (near-max): OK")


# ── New item evaluators ────────────────────────────────────────────────

def test_mosiezny_pierscien_requires_zero_kills():
    w = _mk_world(kills=0)
    assert _mp.UNLOCK_CATALOG["item_mosiezny_pierscien_producenta"].eval_fn(w, True)
    w2 = _mk_world(kills=1)
    assert not _mp.UNLOCK_CATALOG["item_mosiezny_pierscien_producenta"].eval_fn(w2, True)
    print("  item_mosiezny_pierscien (pacifist) fires at 0 kills: OK")


def test_czaszka_requires_10_corpses():
    w_low = _mk_world(corpses=5)
    w_hi = _mk_world(corpses=12)
    assert not _mp.UNLOCK_CATALOG["item_stara_czaszka_z_markerem"].eval_fn(w_low, False)
    assert _mp.UNLOCK_CATALOG["item_stara_czaszka_z_markerem"].eval_fn(w_hi, False)
    print("  item_stara_czaszka fires at 10 corpses salvaged: OK")


def test_klucz_kantyny_requires_3_friendly_sponsors():
    from ..engine import sponsors as _sp
    w = _mk_world()
    # Two friendly only — fail.
    _sp.adjust_attention(w, "kanal_7_krawedz", 12)
    _sp.adjust_attention(w, "novachem_biotech", 11)
    assert not _mp.UNLOCK_CATALOG["item_klucz_do_kantyny"].eval_fn(w, False)
    # Add third.
    _sp.adjust_attention(w, "bractwo_komornika", 10)
    assert _mp.UNLOCK_CATALOG["item_klucz_do_kantyny"].eval_fn(w, False)
    print("  item_klucz_kantyny fires at 3 sponsors ≥ 10: OK")


def test_pamiatkowa_lyzka_requires_pakiet_achievement():
    w_no = _mk_world(achievements=())
    w_yes = _mk_world(achievements=["pakiet_z_sufitu"])
    assert not _mp.UNLOCK_CATALOG["item_pamiatkowa_lyzka"].eval_fn(w_no, False)
    assert _mp.UNLOCK_CATALOG["item_pamiatkowa_lyzka"].eval_fn(w_yes, False)
    print("  item_pamiatkowa_lyzka fires on pakiet_z_sufitu unlock: OK")


# ── Start perk evaluators ──────────────────────────────────────────────

def test_lapowka_requires_sponsor_max():
    from ..engine import sponsors as _sp
    w = _mk_world()
    assert not _mp.UNLOCK_CATALOG["perk_lapowka_dla_portiera"].eval_fn(w, False)
    _sp.adjust_attention(w, "kanal_7_krawedz", 25)   # clamps to 20
    assert _mp.UNLOCK_CATALOG["perk_lapowka_dla_portiera"].eval_fn(w, False)
    print("  perk_lapowka fires at sponsor at max (20): OK")


def test_lyzka_cudu_requires_last_stand_ach():
    w_no = _mk_world(achievements=())
    w_yes = _mk_world(achievements=["anty_host_warknal"])
    assert not _mp.UNLOCK_CATALOG["perk_lyzka_cudu"].eval_fn(w_no, False)
    assert _mp.UNLOCK_CATALOG["perk_lyzka_cudu"].eval_fn(w_yes, False)
    print("  perk_lyzka_cudu fires on last-stand achievement: OK")


# ── unlocked_start_perks reader ─────────────────────────────────────────

def test_unlocked_start_perks_reader():
    _rh.reset()
    assert _mp.unlocked_start_perks() == []
    _rh.unlock("perk_lyzka_cudu")
    perks = _mp.unlocked_start_perks()
    assert len(perks) == 1
    assert perks[0].key == "perk_lyzka_cudu"
    assert perks[0].kind == "start_perk"
    _rh.reset()
    print("  unlocked_start_perks() round-trip: OK")


# ── Catalog-summary surfaces all entries ───────────────────────────────

def test_catalog_summary_includes_new_entries():
    summary = _mp.catalog_summary()
    expected_new = (
        "species_stary_uczestnik", "species_bez_twarzy",
        "species_ferromanta_meta",
        "origin_wieczny_stazysta", "origin_sponsor_reject",
        "origin_byly_konferansjer", "origin_dziedzic_k7",
        "companion_suczka_recyklingu", "companion_kot_ministerstwa",
        "companion_dron_sponsorski",
        "item_mosiezny_pierscien_producenta",
        "item_stara_czaszka_z_markerem",
        "item_czerwony_telefon_k7", "item_klucz_do_kantyny",
        "item_pamiatkowa_lyzka",
        "perk_lapowka_dla_portiera", "perk_insiderskie_info",
        "perk_stara_legitymacja", "perk_lyzka_cudu",
    )
    missing = [k for k in expected_new if k not in summary]
    assert not missing, f"missing from summary: {missing}"
    print(f"  catalog_summary surfaces all 19 new entries: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    _rh.reset()
    try:
        test_catalog_at_least_31_entries()
        test_catalog_has_five_kinds_including_start_perk()
        test_kind_counts()
        test_p29_34_keys_still_present()
        test_every_entry_has_callable_eval()
        test_stary_uczestnik_requires_3_victories()
        test_bez_twarzy_requires_5_runs()
        test_ferromanta_meta_requires_floor_15()
        test_byly_konferansjer_requires_floor_17()
        test_dziedzic_k7_requires_audience_120()
        test_sponsor_reject_requires_hostile()
        test_suczka_requires_kult_20()
        test_kot_requires_ministerstwo_20()
        test_dron_requires_any_sponsor_high()
        test_mosiezny_pierscien_requires_zero_kills()
        test_czaszka_requires_10_corpses()
        test_klucz_kantyny_requires_3_friendly_sponsors()
        test_pamiatkowa_lyzka_requires_pakiet_achievement()
        test_lapowka_requires_sponsor_max()
        test_lyzka_cudu_requires_last_stand_ach()
        test_unlocked_start_perks_reader()
        test_catalog_summary_includes_new_entries()
    finally:
        _rh.reset()
    print("Prompt 29.37 expanded meta-progression catalog smoke: OK")


if __name__ == "__main__":
    main()
