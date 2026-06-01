"""COMBAT-1 Slice D — game-show drama.

Flashy combat feeds the show: crits/staggers nudge the audience, a kill
pops the crowd (harder for a flashy finish), and an enemy left on its last
legs prompts a finisher.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY
from ..engine.entity import Entity, T_MONSTER
from ..engine import combat as _cmb


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _spawn(g, hp=200):
    room = g.world.current_floor.current_room()
    e = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=hp, max_hp=hp, ac=1, damage_dice="1d4",
               attack_bonus=0, affordances=["attack"],
               tags=["monster", "humanoid"], location_id=room.room_id)
    e.visible = True; e.discovered = True; e.visibility_state = "seen"
    g.world.register(e); room.entities.append(e)
    return e, room


def _aud(g):
    return int(getattr(g.world.character, "audience_rating", 0) or 0)


def _force_d20(val):
    import random as _r
    from ..engine import utils_compat as _uc
    _r._orig = getattr(_r, "_orig", _r.randint)
    _uc._orig = getattr(_uc, "_orig", _uc.roll_d20)
    _r.randint = lambda a, b: val
    _uc.roll_d20 = lambda: val


def _restore_d20():
    import random as _r
    from ..engine import utils_compat as _uc
    if hasattr(_r, "_orig"):
        _r.randint = _r._orig
    if hasattr(_uc, "_orig"):
        _uc.roll_d20 = _uc._orig


def test_crit_bumps_audience():
    g = _demo_game()
    e, room = _spawn(g)
    _cmb.start_combat(room, g.world, triggered_by="player_attack")
    a0 = _aud(g)
    _force_d20(20)
    try:
        g._handle_play_input("zaatakuj Bandzior")
    finally:
        _restore_d20()
    assert _aud(g) > a0, f"a crit should raise the audience rating ({a0} -> {_aud(g)})"
    print(f"  crit bumps audience ({a0} -> {_aud(g)}): OK")


def test_flashy_kill_pops_crowd():
    g = _demo_game()
    e, room = _spawn(g, hp=8)  # low HP so a crit finishes it
    _cmb.start_combat(room, g.world, triggered_by="player_attack")
    n0 = len(g.world.log)
    a0 = _aud(g)
    _force_d20(20)  # crit kill = flashy
    try:
        g._handle_play_input("zaatakuj Bandzior")
    finally:
        _restore_d20()
    assert not e.is_alive(), "enemy should be dead"
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert "Widownia ryczy" in new, f"flashy kill should pop the crowd: {new}"
    assert _aud(g) > a0, "kill should raise audience"
    print("  flashy kill pops the crowd: OK")


def test_finisher_prompt_when_low():
    g = _demo_game()
    # Big max_hp (so it survives one hit) but current HP just inside the
    # 1/5 finisher band — any landed hit that doesn't kill leaves it low.
    e, room = _spawn(g, hp=200)
    _cmb.start_combat(room, g.world, triggered_by="player_attack")
    e.hp = 30  # 30/200 = 15% < 20% band, survives a ~5-15 dmg ordinary hit
    n0 = len(g.world.log)
    _force_d20(11)  # ordinary hit (not crit), modest damage
    try:
        g._handle_play_input("zaatakuj Bandzior")
    finally:
        _restore_d20()
    new = " ".join(str(x) for x in g.world.log[n0:])
    if e.is_alive():
        assert "dokończ go" in new, f"low-HP enemy should prompt finisher: {new}"
        print("  finisher prompt at low HP: OK")
    else:
        print("  enemy died on the hit (finisher path is for survivors): OK")


def main():
    test_crit_bumps_audience()
    test_flashy_kill_pops_crowd()
    test_finisher_prompt_when_low()
    print("COMBAT-1 Slice D smoke: OK")


if __name__ == "__main__":
    main()
