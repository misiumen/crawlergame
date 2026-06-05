"""COMBAT-1 Slice C — called-shots that matter.

Every solid hit should make the enemy react (flinch), and a big hit should
STAGGER it (weakening its next swing). Addresses "I broke its torso and it
didn't even flinch — feels shallow."
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
from ..engine.combat import EnemyAction


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _spawn(g, hp=60):
    room = g.world.current_floor.current_room()
    e = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=hp, max_hp=hp, ac=1, damage_dice="1d4",  # ac=1 so we always hit
               attack_bonus=0, affordances=["attack"], tags=["monster", "humanoid"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True; e.visibility_state = "seen"
    g.world.register(e); room.entities.append(e)
    return e, room


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


def test_solid_hit_flinches():
    g = _demo_game()
    e, room = _spawn(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    n0 = len(g.world.log)
    _force_d20(12)  # ordinary hit (not crit), torso
    try:
        g._handle_play_input("zaatakuj Bandzior")
    finally:
        _restore_d20()
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert ("wzdryga się" in new or "zachwiał" in new), \
        f"a landed hit should produce a flinch/stagger line: {new}"
    print("  solid hit produces a flinch reaction: OK")


def test_crit_staggers_and_weakens():
    # A crit applies STAGGERED and the resulting enemy turn swings weaker.
    # (Stagger is a 1-turn status, consumed by that same enemy turn — so we
    # assert on the log, which captures both the stagger line and the
    # "weaker swing" line within the one _handle_play_input call.)
    g = _demo_game()
    e, room = _spawn(g, hp=200)  # tanky so the crit can't one-shot it
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    n0 = len(g.world.log)
    _force_d20(20)  # crit → big hit → stagger
    try:
        g._handle_play_input("zaatakuj Bandzior")
    finally:
        _restore_d20()
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert "zachwiał" in new, f"crit should stagger: {new}"
    assert "cios słabszy" in new, f"staggered enemy should swing weaker: {new}"
    print("  crit staggers + next enemy swing is weaker: OK")


def test_staggered_enemy_hits_weaker():
    g = _demo_game()
    e, room = _spawn(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    ch = g.world.character
    _cmb.add_status(e, _cmb.STATUS_STAGGERED, 1)
    hp0 = ch.hp
    # Big fixed-damage attack; staggered should cut it to 2/3.
    atk = EnemyAction(actor_id=e.entity_id, kind="attack", damage=30,
                      category="attack")
    _force_d20(20)  # ensure the enemy's to-hit lands
    try:
        g._apply_enemy_action(cs, e, atk)
    finally:
        _restore_d20()
    lost = hp0 - ch.hp
    # 30 base, doubled by e_crit(20) = 60, staggered -> 40 (2/3 of 60). The
    # exact number varies with mitigation; key check: it dealt LESS than the
    # un-staggered crit would (60).
    assert 0 < lost < 60, f"staggered enemy should hit for less than full: {lost}"
    print(f"  staggered enemy hits weaker (lost {lost} < 60): OK")


def main():
    test_solid_hit_flinches()
    test_crit_staggers_and_weakens()
    test_staggered_enemy_hits_weaker()
    print("COMBAT-1 Slice C smoke: OK")


if __name__ == "__main__":
    main()
