"""Demo (Intake) mode smoke.

The Demo (Intake) playtest is the *real* game restricted to a single floor:
a title-menu mode (like Arena Testowa) that always plays Floor 1 in the
intake biome, varies layout/encounters by seed, and on floor clear shows the
normal victory summary before returning to the title. It shares all engine
code — the only differences are which biome Floor 1 uses and what happens
when you clear it.

Asserts:
1. start_new_game(demo_mode=True) flags world.demo_mode, stays on Floor 1,
   pins the intake biome, and rolls a seed.
2. Same seed reproduces the same floor; a different seed still stays intake
   but (almost always) changes the layout.
3. _descend_or_win in demo mode routes to STATE_VICTORY with a run summary
   (no descent to Floor 2).
4. enter_demo_intake() opens character creation with the pending-demo flag.
5. A normal new game is NOT flagged demo (no leakage), and opening the slot
   picker clears a stale pending-demo flag.
6. Reseed from the pause menu preserves demo mode (stays on intake Floor 1).
7. The forced-biome override on generate_floor pins the requested biome.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_VICTORY, STATE_CREATE, STATE_SLOTS
from ..engine.world import WorldState
from ..engine.floor_generator import generate_floor


def _demo_game(seed=None):
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", seed=seed, demo_mode=True)
    return g


def test_demo_start_pins_intake_floor1():
    g = _demo_game()
    w = g.world
    assert w.flags.get("demo_mode") is True, "demo_mode flag not set"
    assert int(w.floor_number) == 1, "demo must start on Floor 1"
    assert w.current_floor.biome_key == "intake_industrial", \
        f"expected intake biome, got {w.current_floor.biome_key}"
    assert w.random_seed is not None, "demo should roll a seed"
    assert len(w.current_floor.rooms) >= 2, "floor should have rooms"
    print("  demo start pins intake Floor 1: OK")


def test_seed_reproducible_and_varies():
    g = _demo_game()
    seed = g.world.random_seed
    same = _demo_game(seed=seed)
    assert same.world.current_floor.biome_key == "intake_industrial"
    assert len(same.world.current_floor.rooms) == len(g.world.current_floor.rooms), \
        "same seed must reproduce the same floor size"
    # A different seed stays intake but should vary the layout across a
    # small sweep (room count is a coarse proxy; at least one differs).
    base_n = len(g.world.current_floor.rooms)
    varied = False
    for s in range(seed + 1, seed + 8):
        other = _demo_game(seed=s)
        assert other.world.current_floor.biome_key == "intake_industrial", \
            "forced biome must hold across seeds"
        if len(other.world.current_floor.rooms) != base_n:
            varied = True
    assert varied, "different seeds should vary the floor layout"
    print("  seed reproducible + varies: OK")


def test_floor_clear_routes_to_victory():
    g = _demo_game()
    g.run_summary = None
    g._descend_or_win()
    assert g.state == STATE_VICTORY, f"expected victory, got {g.state}"
    assert g.run_summary is not None, "victory should build a run summary"
    # Demo must NOT descend to a deeper floor.
    assert int(g.world.floor_number) == 1, "demo must not descend past Floor 1"
    print("  floor clear routes to victory: OK")


def test_enter_demo_opens_creation():
    g = Game(screen=None)
    g.enter_demo_intake()
    assert g.state == STATE_CREATE, "demo entry should open character creation"
    assert g._pending_demo is True, "pending-demo flag should be set"
    print("  enter_demo opens creation: OK")


def test_normal_game_not_demo_and_picker_clears_flag():
    g = Game(screen=None)
    g.start_new_game("Norm", "janitor")
    assert not getattr(g.world, "flags", {}).get("demo_mode"), \
        "normal game must not be flagged demo"
    # A stale pending-demo flag (e.g. backed out of demo creation) must be
    # cleared when the player starts a normal new game via the slot picker.
    g._pending_demo = True
    g._open_slot_picker("new")
    assert g._pending_demo is False, "slot picker must clear pending-demo"
    assert g.state == STATE_SLOTS
    print("  normal game not demo + picker clears flag: OK")


def test_reseed_preserves_demo():
    g = _demo_game()
    assert g.world.flags.get("demo_mode") is True
    g._restart_with_new_rolls()
    assert g.world.flags.get("demo_mode") is True, "reseed dropped demo flag"
    assert int(g.world.floor_number) == 1, "reseed must stay on Floor 1"
    assert g.world.current_floor.biome_key == "intake_industrial", \
        "reseed must stay in the intake biome"
    print("  reseed preserves demo: OK")


def test_generate_floor_biome_override():
    w = WorldState()
    f = generate_floor(w, floor_number=1, seed=5, biome="intake_industrial")
    assert f.biome_key == "intake_industrial", \
        f"biome override ignored, got {f.biome_key}"
    # An unknown key falls back to the normal roll (no crash, valid floor).
    w2 = WorldState()
    f2 = generate_floor(w2, floor_number=1, seed=5, biome="does_not_exist")
    assert f2.biome_key, "fallback should still assign a biome"
    print("  generate_floor biome override: OK")


def main():
    test_demo_start_pins_intake_floor1()
    test_seed_reproducible_and_varies()
    test_floor_clear_routes_to_victory()
    test_enter_demo_opens_creation()
    test_normal_game_not_demo_and_picker_clears_flag()
    test_reseed_preserves_demo()
    test_generate_floor_biome_override()
    print("Demo (Intake) mode smoke: OK")


if __name__ == "__main__":
    main()
