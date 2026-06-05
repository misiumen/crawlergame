"""VATS reticle render — boxes-over-art replaced by targeting pips.

The visual changed (no more permanent zone rectangles over the portrait;
each limb is a reticle pip, hover/selected reveal the name) but the
TARGETING contract must hold: _draw_silhouette still registers one
clickable zone per body part, and clicking sets the targeted zone.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.entity import Entity, T_MONSTER
from ..engine import combat as _cmb
from ..content.data import body_plans as _bp
from ..ui import ui as _ui
from ..ui.click_registry import ClickRegistry


def _target():
    e = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=30, max_hp=30, ac=12, damage_dice="1d6",
               tags=["monster", "humanoid"])
    _bp.init_body_parts(e)
    return e


def _render(target, selected):
    surf = pygame.Surface((400, 600))
    reg = ClickRegistry()
    cs = _cmb.CombatState(active=True)
    cs.participants = [target.entity_id]
    cs.targeted_zone_by_eid[target.entity_id] = selected
    plan = _bp.plan_for_entity(target)
    _ui._draw_silhouette(surf, target, plan, 0, 0, 400, 600, _ui._resolve_layout(None),
                         selected, cs=cs, click_registry=reg,
                         category_override="vats_zone")
    return reg, cs, plan


def test_one_click_zone_per_body_part():
    t = _target()
    reg, cs, plan = _render(t, "torso")
    zones = [z for z in reg.zones if z.category.startswith("vats_zone:")]
    assert len(zones) == len(plan), (len(zones), len(plan))
    print(f"  one click zone per body part ({len(zones)}): OK")


def test_clicking_zone_sets_target():
    t = _target()
    reg, cs, plan = _render(t, "torso")
    head_zone = next(z for z in reg.zones
                     if z.category == "vats_zone:head")
    head_zone.callback()
    assert cs.targeted_zone_by_eid[t.entity_id] == "head", \
        "clicking the head reticle should target the head"
    print("  clicking a reticle sets the targeted zone: OK")


def test_renders_without_crash_all_states():
    # selected / wounded / broken zones all render (pip variants).
    t = _target()
    parts = t.body_parts
    # wound one, break another.
    if "l_arm" in parts:
        parts["l_arm"]["hp"] = max(0, parts["l_arm"]["max_hp"] // 2)
    if "r_leg" in parts:
        parts["r_leg"]["hp"] = 0
        parts["r_leg"]["broken"] = True
    reg, cs, plan = _render(t, "head")
    assert any(z.category.startswith("vats_zone:") for z in reg.zones)
    print("  renders pips for default/wounded/broken/selected: OK")


def main():
    test_one_click_zone_per_body_part()
    test_clicking_zone_sets_target()
    test_renders_without_crash_all_states()
    print("VATS reticle render smoke: OK")


if __name__ == "__main__":
    main()
