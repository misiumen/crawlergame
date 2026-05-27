"""Prompt 29.34 — Meta-progression smoke (replaces NG+).

Audit + user-flagged regression: the empty new_game_plus badge
shipped in P29.26/P29.31 promised meta-progression but delivered
none. DCC isn't roguelike-NG+; the right model is additive options
at character creation.

P29.34 ships:
  * engine/meta_progression.py — 12 unlock entries (5 species,
    3 origins, 1 companion, 3 legendary items).
  * Evaluation at every end-of-run (death + victory) stamps
    qualifying unlocks via run_history.unlock(key).
  * Each death/victory log includes per-unlock "Sezon otwiera nowe
    opcje:" lines so the player knows what got opened.
  * start_new_game applies species + origin bonuses at character
    creation. _apply_starting_companion grants the flagship parrot
    when chosen.

Covers:
  * UNLOCK_CATALOG has 12+ entries across the 5 kinds.
  * evaluate_run_for_unlocks fires `drugi_cykl` for any finish.
  * mutant_chemiczny fires when player reached floor 12.
  * sponsorowany fires when any sponsor at attention ≥10.
  * kolyski fires only on victory + finalista achievement.
  * NewGame+ unlock NO LONGER stamped (regression catch).
  * is_unlocked + unlocked_species reflect persistent state.
  * start_new_game with species_grzybica applies WIS +1 + flag.
  * start_new_game with origin_drugi_cykl bumps audience to 5.
  * start_new_game with chosen_companion=parrot registers it.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import meta_progression as _mp
from ..engine import run_history as _rh


def _mk_world(*, audience_peak=10, max_floor=2,
              achievements=()):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    w.character.run_audience_peak = audience_peak
    w.character.run_max_floor_reached = max_floor
    w.character.unlocked_achievements = list(achievements)
    f = FloorState(floor_id="f1", floor_number=max_floor)
    r = RoomState(room_id="r0", fallback_short_title="x")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


# ── Catalog shape ───────────────────────────────────────────────────────

def test_catalog_has_expected_unlocks():
    cat = _mp.UNLOCK_CATALOG
    assert len(cat) >= 12, f"catalog should be >=12; got {len(cat)}"
    by_kind = {}
    for ud in cat.values():
        by_kind[ud.kind] = by_kind.get(ud.kind, 0) + 1
    assert by_kind.get("species", 0) >= 5
    assert by_kind.get("origin", 0) >= 3
    assert by_kind.get("companion", 0) >= 1
    assert by_kind.get("item", 0) >= 3
    print(f"  catalog: {len(cat)} entries across "
          f"{len(by_kind)} kinds: OK")


# ── Evaluation ──────────────────────────────────────────────────────────

def test_drugi_cykl_fires_for_any_finish():
    _rh.reset()
    w = _mk_world()
    keys = _mp.evaluate_run_for_unlocks(w, victory=False)
    assert "origin_drugi_cykl" in keys
    _rh.reset()
    print("  drugi_cykl fires on any finish: OK")


def test_mutant_requires_floor_12():
    _rh.reset()
    w_shallow = _mk_world(max_floor=8)
    keys_shallow = _mp.evaluate_run_for_unlocks(w_shallow, victory=False)
    assert "species_mutant_chemiczny" not in keys_shallow
    w_deep = _mk_world(max_floor=12)
    keys_deep = _mp.evaluate_run_for_unlocks(w_deep, victory=False)
    assert "species_mutant_chemiczny" in keys_deep
    _rh.reset()
    print("  mutant unlocks only at floor ≥12: OK")


def test_sponsorowany_requires_attention_10():
    _rh.reset()
    from ..engine import sponsors as _sp
    w_low = _mk_world()
    keys = _mp.evaluate_run_for_unlocks(w_low, victory=False)
    assert "origin_sponsorowany" not in keys
    w_hi = _mk_world()
    _sp.adjust_attention(w_hi, "novachem_biotech", 12)
    keys2 = _mp.evaluate_run_for_unlocks(w_hi, victory=False)
    assert "origin_sponsorowany" in keys2
    _rh.reset()
    print("  sponsorowany requires attention ≥10: OK")


def test_kolyski_requires_victory_AND_finalista():
    _rh.reset()
    w_lost = _mk_world(achievements=["finalista_sezonu"])
    keys = _mp.evaluate_run_for_unlocks(w_lost, victory=False)
    assert "species_kolyski_anti_hosta" not in keys, \
        "must require victory=True"
    w_won = _mk_world(achievements=["finalista_sezonu"])
    keys2 = _mp.evaluate_run_for_unlocks(w_won, victory=True)
    assert "species_kolyski_anti_hosta" in keys2
    _rh.reset()
    print("  kolyski requires victory AND finalista achievement: OK")


# ── NG+ regression: no longer stamped ───────────────────────────────────

def test_ng_plus_no_longer_stamped():
    _rh.reset()
    w = _mk_world()
    _rh.record_run(w, victory=True)
    m = _rh.meta()
    assert "new_game_plus" not in (m.get("unlocks") or []), \
        f"new_game_plus should no longer be auto-stamped; got {m['unlocks']}"
    _rh.reset()
    print("  NG+ flag no longer auto-stamped on victory: OK")


# ── Unlock persistence + filtered views ─────────────────────────────────

def test_persistent_unlock_round_trip():
    _rh.reset()
    w = _mk_world()
    _mp.record_unlocks_for_run(w, victory=False)
    # drugi_cykl should now be persistent.
    assert _mp.is_unlocked("origin_drugi_cykl")
    # Filtered view sees it.
    origins = _mp.unlocked_origins()
    assert any(o.key == "origin_drugi_cykl" for o in origins)
    _rh.reset()
    print("  unlock persists + unlocked_origins() reads it back: OK")


# ── Character creation hooks ────────────────────────────────────────────

def test_start_new_game_applies_species_bonus():
    from ..engine.game import Game
    g = Game(screen=None)
    g.start_new_game("Test", "janitor", species="species_grzybica")
    ch = g.world.character
    assert ch.species_key == "species_grzybica"
    # WIS bumped +1 (janitor base WIS=11, post-grzybica should be 12).
    assert ch.stats["WIS"] >= 12, f"WIS not bumped: {ch.stats['WIS']}"
    # Regeneration flag set.
    assert (ch.flags or {}).get("species_regenerates") == 1
    print(f"  species_grzybica: WIS+1 + regen flag: OK "
          f"(WIS={ch.stats['WIS']})")


def test_start_new_game_applies_origin_bonus():
    from ..engine.game import Game
    g = Game(screen=None)
    g.start_new_game("Test", "origin_drugi_cykl")
    ch = g.world.character
    assert ch.background == "origin_drugi_cykl"
    assert ch.audience_rating >= 5, \
        f"drugi_cykl should set audience >=5; got {ch.audience_rating}"
    assert (ch.flags or {}).get("origin_has_scar") is True
    print(f"  origin_drugi_cykl: audience={ch.audience_rating} + scar: OK")


def test_start_new_game_with_chosen_companion():
    """When self._chosen_companion is set on the Game BEFORE
    start_new_game runs, the flagship parrot should land in
    world.companions."""
    from ..engine.game import Game
    from ..engine import companion as _comp
    g = Game(screen=None)
    g._chosen_companion = "companion_papuga_anty_host"
    g.start_new_game("Test", "janitor")
    # At least one companion in the registry.
    assert (g.world.companions or {}), "no companions registered"
    pets = [c for c in g.world.companions.values()
            if c.species_key == "papuga_anty_host"]
    assert pets, "parrot not registered"
    print(f"  starting companion (parrot): OK "
          f"(bond={pets[0].bond})")


# ── End-to-end via Game._check_player_dead ──────────────────────────────

def test_death_records_meta_unlocks():
    """A real death should evaluate + stamp drugi_cykl (any finish
    qualifies)."""
    from ..engine.game import Game
    _rh.reset()
    g = Game(screen=None)
    g.start_new_game("Test", "janitor")
    # Burn last-stand + zero HP for real death.
    g.world.character.near_death_used = True
    g.world.character.hp = 0
    g._check_player_dead("test", "test")
    m = _rh.meta()
    assert "origin_drugi_cykl" in (m.get("unlocks") or [])
    _rh.reset()
    print("  death path stamps drugi_cykl unlock: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    _rh.reset()
    try:
        test_catalog_has_expected_unlocks()
        test_drugi_cykl_fires_for_any_finish()
        test_mutant_requires_floor_12()
        test_sponsorowany_requires_attention_10()
        test_kolyski_requires_victory_AND_finalista()
        test_ng_plus_no_longer_stamped()
        test_persistent_unlock_round_trip()
        test_start_new_game_applies_species_bonus()
        test_start_new_game_applies_origin_bonus()
        test_start_new_game_with_chosen_companion()
        test_death_records_meta_unlocks()
    finally:
        _rh.reset()
    print("Prompt 29.34 meta-progression smoke: OK")


if __name__ == "__main__":
    main()
