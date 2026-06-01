"""COMBAT-1 P3 — the "thinking" loop holds, end to end.

Against a physical-resistant enemy: brute (physical) is HALVED, while its
elemental weakness is DOUBLED. So coating the blade / using the environment
is clearly better — but brute still works (bite "in between"). Also: the
combat briefing surfaces the lever so the player knows to think.
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
from ..engine import damage as _dmg


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g._refresh_layout()
    return g


def _armored_foe(g, hp=80):
    room = g.world.current_floor.current_room()
    e = Entity(key="armored", entity_type=T_MONSTER, fallback_name="Pancerny",
               hp=hp, max_hp=hp, ac=10, damage_dice="1d6",
               affordances=["attack"], tags=["monster", "humanoid"],
               location_id=room.room_id)
    e.resists = ["physical"]
    e.vulnerable_to = ["acid"]
    e.visible = True; e.discovered = True; e.visibility_state = "seen"
    g.world.register(e); room.entities.append(e)
    return e, room


def test_brute_halved_weakness_doubled():
    g = _demo_game()
    e, room = _armored_foe(g, hp=200)
    # Brute (physical) is resisted → halved.
    hp0 = e.hp
    res_phys = _dmg.apply_damage(g.world, e, 20, damage_type="physical",
                                 source="test")
    assert res_phys["amount_dealt"] == 10, res_phys
    # Weakness (acid) → doubled.
    res_acid = _dmg.apply_damage(g.world, e, 20, damage_type="acid",
                                 source="test")
    assert res_acid["amount_dealt"] == 40, res_acid
    # Clever (acid) deals 4x the brute hit for the same swing — strongly
    # rewarded, but brute still dealt damage (it works, just slow).
    assert res_acid["amount_dealt"] == 4 * res_phys["amount_dealt"]
    print("  brute halved, weakness doubled (4x swing value): OK")


def test_briefing_flags_the_lever():
    g = _demo_game()
    e, room = _armored_foe(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    cs.selected_target_id = e.entity_id
    n0 = len(g.world.log)
    g._combat_open_briefing(cs)
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert "ślizgają" in new, f"briefing should flag physical resistance: {new}"
    # acid's PL display label is "żrące" (damage.damage_type_label).
    assert "żrące" in new, f"briefing should name the weakness in PL: {new}"
    print("  briefing flags the lever (resist + PL weakness): OK")


def test_brute_still_kills_eventually():
    # bite "in between": brute is not gated, just slow. A physical hit on a
    # low-HP resistant foe still reduces and can finish it.
    g = _demo_game()
    e, room = _armored_foe(g, hp=6)
    _dmg.apply_damage(g.world, e, 20, damage_type="physical", source="test")
    assert not e.is_alive(), "brute must still be able to kill (not hard-gated)"
    print("  brute still works (not a hard gate): OK")


def main():
    test_brute_halved_weakness_doubled()
    test_briefing_flags_the_lever()
    test_brute_still_kills_eventually()
    print("COMBAT-1 P3 thinking-loop smoke: OK")


if __name__ == "__main__":
    main()
