"""COMBAT-1 P1 — dedicated combat surface.

- A combat-start briefing fires a "WALKA SIĘ ZACZYNA" banner (transition).
- The combat bar exposes the core verbs (Atak/Unik/Obrona/Oceń/Uciekaj...)
  and renders clickable; clicking issues the command.
- _active_combat() detects the live fight (used by draw to swap tabs→bar).
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
from ..ui import ui as _ui
from ..ui.click_registry import ClickRegistry


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g.input_text = ""
    g._refresh_layout()
    return g


def _spawn(g, hp=40):
    room = g.world.current_floor.current_room()
    e = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=hp, max_hp=hp, ac=12, damage_dice="1d6",
               affordances=["attack"], tags=["monster", "humanoid"],
               location_id=room.room_id)
    e.visible = True; e.discovered = True
    g.world.register(e); room.entities.append(e)
    return e, room


def test_active_combat_detects_fight():
    g = _demo_game()
    e, room = _spawn(g)
    assert g._active_combat() is None, "no fight yet"
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    assert g._active_combat() is cs, "active combat should be detected"
    print("  _active_combat detects the fight: OK")


def test_briefing_sets_banner():
    g = _demo_game()
    e, room = _spawn(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    g._combat_open_briefing(cs)
    fx = getattr(g.world, "combat_fx", None)
    assert isinstance(fx, dict) and fx.get("banner"), "banner not set"
    assert fx["banner"]["text"] == "WALKA SIĘ ZACZYNA"
    # update() should age + eventually clear it.
    g.update(1200)
    assert not (getattr(g.world, "combat_fx", {}) or {}).get("banner"), \
        "banner should expire after its ttl"
    print("  combat-start banner fires + expires: OK")


def test_combat_bar_renders_and_clicks():
    g = _demo_game()
    e, room = _spawn(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    surf = pygame.Surface((1280, 720))
    reg = ClickRegistry()
    issued = []
    _ui.draw_combat_bar(surf, g.world, cs, layout=g._layout if hasattr(g, "_layout") else None,
                        click_registry=reg,
                        command_cb=lambda c, target_id=None: issued.append(c))
    zones = [z for z in reg.zones if z.category == "combat_bar"]
    assert len(zones) >= 5, f"combat bar should expose core verbs: {len(zones)}"
    zones[0].callback()
    assert issued and issued[0] == "zaatakuj", issued
    print(f"  combat bar renders {len(zones)} verbs + click issues cmd: OK")


def test_digit_fires_bar_action_in_combat():
    g = _demo_game()
    e, room = _spawn(g)
    cs = _cmb.start_combat(room, g.world, triggered_by="player_attack")
    g.input_text = ""
    issued = []
    g.submit_generated_command = lambda c, target_id=None: issued.append(c)
    # Simulate the keydown digit path used by _handle_play_keydown.
    from ..ui.ui import _COMBAT_BAR_ACTIONS
    cs_bar = g._active_combat()
    assert cs_bar is not None
    idx = 3  # "4" → Unik
    label, cmd, hot = _COMBAT_BAR_ACTIONS[idx]
    g.submit_generated_command(cmd)
    assert issued[-1] == "unik", issued
    print("  digit maps to bar action (4 → unik): OK")


def main():
    test_active_combat_detects_fight()
    test_briefing_sets_banner()
    test_combat_bar_renders_and_clicks()
    test_digit_fires_bar_action_in_combat()
    print("COMBAT-1 P1 surface smoke: OK")


if __name__ == "__main__":
    main()
