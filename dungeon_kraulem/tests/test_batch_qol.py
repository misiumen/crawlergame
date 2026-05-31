"""QoL batch: UX-4b (placeholder dialogue) + UX-6 (spent pins) + CMB-2 (tails)."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY
from ..engine.entity import Entity, T_OBJECT, T_MONSTER
from ..ui import ui as _ui
from ..ui import portrait_zones as _pz
from ..content.data import body_plans as _bp


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    return g


# ── UX-4b ──────────────────────────────────────────────────────────────
def test_generic_npc_gets_placeholder_tree():
    g = _demo_game()
    npc = Entity(key="x", entity_type="npc", fallback_name="Nadzorca",
                 affordances=["talk"])
    assert g._guess_dialogue_tree(npc) == "placeholder_npc"
    crawler = Entity(key="c", entity_type="crawler", fallback_name="Zawodnik")
    assert g._guess_dialogue_tree(crawler) == "default_crawler"
    obj = Entity(key="o", entity_type=T_OBJECT, fallback_name="kosz")
    assert g._guess_dialogue_tree(obj) == ""
    print("  UX-4b generic npc → placeholder tree: OK")


# ── UX-6 ───────────────────────────────────────────────────────────────
def test_spent_object_pin_hidden():
    g = _demo_game()
    room = g.world.current_floor.current_room()

    def mk(name, **kw):
        e = Entity(key="t", entity_type=T_OBJECT, fallback_name=name,
                   fallback_desc="Opis.", location_id=room.room_id, **kw)
        e.visible = True; e.discovered = True
        g.world.register(e); room.entities.append(e)
        return e

    fresh = mk("świeża szafka", tags=["salvageable"],
               affordances=["inspect", "salvage"])
    spent = mk("złom maszynowy", tags=["salvageable"],
               affordances=["inspect", "salvage"])
    spent.state = {"stripped": True, "no_salvage": True}
    monster = Entity(key="m", entity_type=T_MONSTER, fallback_name="wróg",
                     location_id=room.room_id)
    monster.visible = True; monster.discovered = True
    monster.state = {"depleted": True}  # creatures never count as spent
    g.world.register(monster); room.entities.append(monster)

    assert _ui._pin_is_spent(g.world, room, fresh) is False
    assert _ui._pin_is_spent(g.world, room, spent) is True
    assert _ui._pin_is_spent(g.world, room, monster) is False
    print("  UX-6 spent object pin hidden (fresh/monster kept): OK")


# ── CMB-2 ──────────────────────────────────────────────────────────────
def test_beast_has_tail_zone():
    assert "tail" in _bp.PLAN_SMALL_QUADRUPED, "quadruped plan needs a tail"
    assert _bp.PLAN_SMALL_QUADRUPED["tail"]["label_pl"] == "ogon"
    assert "tail" in _pz.ARCHETYPE_HITBOXES["quadruped"]
    assert "tail" in _pz.ARCHETYPE_HITBOXES["beast"]
    # zones_for returns the tail when the plan declares it.
    boxes = _pz.zones_for(None, "quadruped",
                          list(_bp.PLAN_SMALL_QUADRUPED.keys()))
    assert boxes and "tail" in boxes, boxes
    # Per-art rat portrait carries a tail hitbox too.
    assert "tail" in _pz.HITBOXES["wrog_intake_tunnel_runt"]
    print("  CMB-2 beast tail zone + hitbox: OK")


def main():
    test_generic_npc_gets_placeholder_tree()
    test_spent_object_pin_hidden()
    test_beast_has_tail_zone()
    print("QoL batch (UX-4b / UX-6 / CMB-2) smoke: OK")


if __name__ == "__main__":
    main()
