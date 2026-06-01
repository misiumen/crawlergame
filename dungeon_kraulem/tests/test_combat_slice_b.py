"""COMBAT-1 Slice B — telegraphed special, read & counter.

Reading the enemy's telegraph should pay off: a successful dodge fully
negates a telegraphed SPECIAL (only halves an ordinary attack), defending
halves a special's hit, and a charging special fizzles on stun/prone.
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
    return g


def _spawn(g, hp=40):
    room = g.world.current_floor.current_room()
    e = Entity(key="brute", entity_type=T_MONSTER, fallback_name="Brutal",
               hp=hp, max_hp=hp, ac=12, damage_dice="1d6",
               attack_bonus=50,  # guarantee the to-hit lands so we test mitigation
               affordances=["attack"], tags=["monster"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    g.world.register(e); room.entities.append(e)
    return e


def _special_action(e, dmg=20):
    return EnemyAction(actor_id=e.entity_id, kind="special", damage=dmg,
                       category="special", special_key="frenzied_charge",
                       label_pl="Szał!", note="rzuca się w szale")


def test_dodge_fully_negates_special():
    g = _demo_game()
    e = _spawn(g)
    cs = _cmb.start_combat(g.world.current_floor.current_room(), g.world,
                           triggered_by="player_attack")
    ch = g.world.character
    hp0 = ch.hp
    cs.player_dodge = True
    # Force the dodge skill roll to succeed deterministically.
    import random as _r
    _orig = _r.randint
    _r.randint = lambda a, b: 20
    try:
        g._apply_enemy_action(cs, e, _special_action(e, dmg=20))
    finally:
        _r.randint = _orig
    assert ch.hp == hp0, f"dodged special should deal 0 dmg, lost {hp0 - ch.hp}"
    print("  dodge fully negates a telegraphed special: OK")


def test_dodge_only_halves_ordinary_attack():
    g = _demo_game()
    e = _spawn(g)
    cs = _cmb.start_combat(g.world.current_floor.current_room(), g.world,
                           triggered_by="player_attack")
    ch = g.world.character
    hp0 = ch.hp
    cs.player_dodge = True
    atk = EnemyAction(actor_id=e.entity_id, kind="attack", damage=20,
                      category="attack")
    import random as _r
    _orig = _r.randint
    _r.randint = lambda a, b: 20
    try:
        g._apply_enemy_action(cs, e, atk)
    finally:
        _r.randint = _orig
    lost = hp0 - ch.hp
    assert lost > 0, "ordinary attack should still hurt through a dodge"
    print(f"  dodge only halves an ordinary attack (lost {lost}): OK")


def test_charging_special_fizzles_on_stun():
    g = _demo_game()
    e = _spawn(g)
    cs = _cmb.start_combat(g.world.current_floor.current_room(), g.world,
                           triggered_by="player_attack")
    # Make the enemy charge a special, then stun it before its turn.
    cs.enemy_intents[e.entity_id] = {"category": "special",
                                     "kind": "special",
                                     "special_key": "frenzied_charge",
                                     "label_pl": "Szał!"}
    _cmb.add_status(e, _cmb.STATUS_STUNNED, 2)
    ch = g.world.character
    hp0 = ch.hp
    g._run_enemy_turn(cs)
    assert ch.hp == hp0, "a stunned charging enemy must not land its special"
    print("  charging special fizzles on stun: OK")


def main():
    test_dodge_fully_negates_special()
    test_dodge_only_halves_ordinary_attack()
    test_charging_special_fizzles_on_stun()
    print("COMBAT-1 Slice B smoke: OK")


if __name__ == "__main__":
    main()
