"""COMBAT-1 Slice A — zero-friction combat start.

On engagement the game should: auto-select a target, reveal hostiles
(no fog '???'), telegraph intents, and emit a one-line briefing — so the
player never has to `sprawdź` or open the [Istoty] tab to start fighting.
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
from ..engine import visibility as _vis


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    return g


def _spawn(g, name="Bandzior", hp=30, band_ranged=False, vuln=None):
    room = g.world.current_floor.current_room()
    e = Entity(key="thug", entity_type=T_MONSTER, fallback_name=name,
               hp=hp, max_hp=hp, ac=12, damage_dice="1d6",
               affordances=["attack"], tags=["monster"],
               location_id=room.room_id)
    if vuln:
        e.vulnerable_to = list(vuln)
    e.visible = True; e.discovered = True
    e.visibility_state = "unknown"
    g.world.register(e); room.entities.append(e)
    return e, room


def test_start_autoselects_and_reveals():
    g = _demo_game()
    e, room = _spawn(g, vuln=["fire", "cold"])
    assert _vis.is_unknown(e), "precondition: enemy starts unknown"
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    assert cs.selected_target_id == e.entity_id, \
        f"target not auto-selected: {cs.selected_target_id}"
    assert not _vis.is_unknown(e), "enemy should be revealed (>= seen) on start"
    # Intent telegraphed for the target.
    assert e.entity_id in (cs.enemy_intents or {}), "intent not planned"
    print("  start auto-selects + reveals + telegraphs: OK")


def test_engaged_target_preferred_over_ranged():
    g = _demo_game()
    room = g.world.current_floor.current_room()
    # Ranged enemy (starts at-range) + melee enemy (engaged). Melee wins.
    ranged = Entity(key="sniper", entity_type=T_MONSTER, fallback_name="Strzelec",
                    hp=40, max_hp=40, ac=12, damage_dice="1d6",
                    affordances=["attack", "shoot"], tags=["monster", "ranged"],
                    location_id=room.room_id)
    melee = Entity(key="bruiser", entity_type=T_MONSTER, fallback_name="Zbir",
                   hp=20, max_hp=20, ac=12, damage_dice="1d6",
                   affordances=["attack"], tags=["monster"],
                   location_id=room.room_id)
    for e in (ranged, melee):
        e.visible = True; e.discovered = True
        g.world.register(e); room.entities.append(e)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    # Engaged (melee) should be chosen even though it has less HP.
    assert cs.selected_target_id == melee.entity_id, \
        f"expected engaged melee target, got {cs.selected_target_id}"
    print("  engaged target preferred over ranged: OK")


def test_open_briefing_logs_weakness_and_intent():
    g = _demo_game()
    e, room = _spawn(g, vuln=["fire"])
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    n0 = len(g.world.log)
    g._combat_open_briefing(cs)
    new = " ".join(str(x) for x in g.world.log[n0:])
    assert "Naprzeciw" in new, f"no briefing line: {new}"
    assert "słaby na: fire" in new, f"weakness not surfaced: {new}"
    # assess action remains available (briefing must NOT consume it).
    assert cs.assessed is False, "briefing must not set assessed"
    print("  open briefing surfaces weakness + keeps assess: OK")


def main():
    test_start_autoselects_and_reveals()
    test_engaged_target_preferred_over_ranged()
    test_open_briefing_logs_weakness_and_intent()
    print("COMBAT-1 Slice A smoke: OK")


if __name__ == "__main__":
    main()
