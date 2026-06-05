"""Prompt 29.35 — Character creation UI for meta-unlocks.

P29.34 shipped the unlock catalog + character-creation hooks
(species, origin, companion params on start_new_game), but the UI
state-machine still ran name → background → start. There was no
way for the player to actually PICK an unlocked species or origin
through the screen.

P29.35 extends:
  * cc dict carries selected_species + selected_companion.
  * Step machine: name → background → species → maybe companion →
    world.
  * _creation_background_keys() includes unlocked `origin_*` keys.
  * _creation_species_keys() always offers baseline_human; adds
    unlocked species.
  * _creation_companion_keys() returns [""] sentinel + unlocks.
    When only [""] exists the companion step is skipped silently.
  * draw_creation renders species + companion picker rows with the
    same click+keyboard pattern as background.

Covers:
  * Background-key list includes unlocked origin (test stamps
    `origin_drugi_cykl` first).
  * Species-key list always starts with baseline_human; appended
    species lands after.
  * commit_bg transitions step → "species" (not straight to play).
  * commit_species with NO unlocked companion runs the world
    immediately (state → "play").
  * commit_species with unlocked companion routes to "companion"
    step.
  * commit_companion with index>0 sets _chosen_companion and
    launches.
  * commit_companion with index 0 launches with no companion.
  * Back from species → background, back from companion → species.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine import meta_progression as _mp
from ..engine import run_history as _rh


def _new_game():
    from ..engine.game import Game
    g = Game(screen=None)
    g.cc = {"step": "name", "name_input": "Tester",
            "selected_bg": 0, "selected_species": 0,
            "selected_companion": 0}
    # Force into STATE_CREATE so commits land in the right branch.
    from ..engine.game import STATE_CREATE
    g.state = STATE_CREATE
    return g


# ── Option-list builders ────────────────────────────────────────────────

def test_background_list_includes_unlocked_origin():
    _rh.reset()
    _rh.unlock("origin_drugi_cykl")
    g = _new_game()
    keys = g._creation_background_keys()
    assert "origin_drugi_cykl" in keys, \
        f"unlocked origin missing from picker: {keys}"
    _rh.reset()
    print(f"  bg list includes unlocked origin: OK ({len(keys)} total)")


def test_species_list_default_baseline_only():
    _rh.reset()
    g = _new_game()
    keys = g._creation_species_keys()
    assert keys == ["baseline_human"], f"got {keys}"
    _rh.reset()
    print("  species default: baseline_human only: OK")


def test_species_list_includes_unlocked():
    _rh.reset()
    _rh.unlock("species_grzybica")
    g = _new_game()
    keys = g._creation_species_keys()
    assert keys[0] == "baseline_human"
    assert "species_grzybica" in keys
    _rh.reset()
    print(f"  species list w/ unlock: {keys}: OK")


def test_companion_list_default_empty_sentinel():
    _rh.reset()
    g = _new_game()
    keys = g._creation_companion_keys()
    # Sentinel only — picker step should be skipped.
    assert keys == [""], f"got {keys}"
    _rh.reset()
    print("  companion default: [\"\"] sentinel only: OK")


def test_companion_list_includes_unlocked():
    _rh.reset()
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    keys = g._creation_companion_keys()
    assert keys[0] == ""
    assert "companion_papuga_anty_host" in keys
    _rh.reset()
    print(f"  companion list w/ unlock: {keys}: OK")


# ── State machine: commit_bg → species ─────────────────────────────────

def test_commit_bg_routes_to_species_not_play():
    _rh.reset()
    g = _new_game()
    g.cc["step"] = "background"
    g.cc["selected_bg"] = 0
    g._create_action("commit_bg")
    assert g.cc["step"] == "species", \
        f"step after commit_bg should be 'species'; got {g.cc['step']}"
    # State should still be STATE_CREATE — not play yet.
    from ..engine.game import STATE_CREATE
    assert g.state == STATE_CREATE
    _rh.reset()
    print("  commit_bg -> species step: OK")


# ── commit_species without companions → launch ────────────────────────

def test_commit_species_without_companions_launches():
    _rh.reset()
    g = _new_game()
    g.cc["step"] = "species"
    g.cc["selected_species"] = 0
    g._create_action("commit_species")
    from ..engine.game import STATE_PLAY
    assert g.state == STATE_PLAY, \
        f"should launch; got state={g.state}"
    assert g.world is not None
    assert g.world.character.species_key == "baseline_human"
    _rh.reset()
    print("  commit_species (no comp unlocks) -> STATE_PLAY: OK")


# ── commit_species with companions → companion step ───────────────────

def test_commit_species_with_companion_routes():
    _rh.reset()
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    g.cc["step"] = "species"
    g.cc["selected_species"] = 0
    g._create_action("commit_species")
    assert g.cc["step"] == "companion", \
        f"should route to companion; got {g.cc['step']}"
    from ..engine.game import STATE_CREATE
    assert g.state == STATE_CREATE
    _rh.reset()
    print("  commit_species (with comp unlock) -> companion step: OK")


# ── commit_companion sets _chosen_companion + launches ────────────────

def test_commit_companion_with_pet_sets_chosen():
    _rh.reset()
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    g.cc["step"] = "companion"
    g.cc["selected_companion"] = 1   # 0=none, 1=parrot
    g._create_action("commit_companion")
    from ..engine.game import STATE_PLAY
    assert g.state == STATE_PLAY
    # Companion should be in world.companions.
    pets = [c for c in (g.world.companions or {}).values()
            if c.species_key == "papuga_anty_host"]
    assert pets, "parrot not registered"
    _rh.reset()
    print(f"  commit_companion (parrot): registered: OK")


def test_commit_companion_with_none_launches_clean():
    _rh.reset()
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    g.cc["step"] = "companion"
    g.cc["selected_companion"] = 0   # explicit "no companion"
    g._create_action("commit_companion")
    from ..engine.game import STATE_PLAY
    assert g.state == STATE_PLAY
    # No parrot in companions.
    parrots = [c for c in (g.world.companions or {}).values()
               if c.species_key == "papuga_anty_host"]
    assert not parrots, "should not have spawned a parrot at index 0"
    _rh.reset()
    print("  commit_companion (none) launches clean: OK")


# ── Back navigation ───────────────────────────────────────────────────

def test_back_from_species_returns_to_background():
    _rh.reset()
    g = _new_game()
    g.cc["step"] = "species"
    g._create_action("back")
    assert g.cc["step"] == "background"
    _rh.reset()
    print("  back from species -> background: OK")


def test_back_from_companion_returns_to_species():
    _rh.reset()
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    g.cc["step"] = "companion"
    g._create_action("back")
    assert g.cc["step"] == "species"
    _rh.reset()
    print("  back from companion -> species: OK")


# ── End-to-end with origin + species + companion ──────────────────────

def test_full_creation_with_unlocks_e2e():
    _rh.reset()
    _rh.unlock("origin_drugi_cykl")
    _rh.unlock("species_grzybica")
    _rh.unlock("companion_papuga_anty_host")
    g = _new_game()
    bg_keys = g._creation_background_keys()
    sp_keys = g._creation_species_keys()
    comp_keys = g._creation_companion_keys()
    # Pick the origin, grzybica, parrot.
    g.cc["selected_bg"] = bg_keys.index("origin_drugi_cykl")
    g.cc["selected_species"] = sp_keys.index("species_grzybica")
    g.cc["selected_companion"] = comp_keys.index("companion_papuga_anty_host")
    # Walk the state machine.
    g.cc["step"] = "background"
    g._create_action("commit_bg")
    assert g.cc["step"] == "species"
    g._create_action("commit_species")
    assert g.cc["step"] == "companion"
    g._create_action("commit_companion")
    from ..engine.game import STATE_PLAY
    assert g.state == STATE_PLAY
    ch = g.world.character
    assert ch.background == "origin_drugi_cykl"
    assert ch.species_key == "species_grzybica"
    assert ch.audience_rating >= 5, "drugi_cykl audience bonus"
    pets = [c for c in (g.world.companions or {}).values()
            if c.species_key == "papuga_anty_host"]
    assert pets, "parrot missing"
    _rh.reset()
    print("  e2e creation w/ origin+species+companion: OK")


# ── Suite ─────────────────────────────────────────────────────────────

def main():
    _rh.reset()
    try:
        test_background_list_includes_unlocked_origin()
        test_species_list_default_baseline_only()
        test_species_list_includes_unlocked()
        test_companion_list_default_empty_sentinel()
        test_companion_list_includes_unlocked()
        test_commit_bg_routes_to_species_not_play()
        test_commit_species_without_companions_launches()
        test_commit_species_with_companion_routes()
        test_commit_companion_with_pet_sets_chosen()
        test_commit_companion_with_none_launches_clean()
        test_back_from_species_returns_to_background()
        test_back_from_companion_returns_to_species()
        test_full_creation_with_unlocks_e2e()
    finally:
        _rh.reset()
    print("Prompt 29.35 creation-UI smoke: OK")


if __name__ == "__main__":
    main()
