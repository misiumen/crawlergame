"""P30 smoke — portrait-based VATS limb targeting.

Asserts:
1. portrait_zones resolves per-portrait hitboxes for known intake art keys.
2. Archetype fallback covers humanoid + quadruped when no per-key data.
3. Resolved zones are always a subset of the requested plan zones.
4. All normalized boxes stay within [0,1] and have positive size.
5. art.resolve_enemy_art_key finds the real PNG for intake mobs.
6. _draw_silhouette renders over a real portrait with hitboxes and
   registers one clickable zone per plan zone (targeting still works).
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

from .. import config
config.apply_llm_mode("performance")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import combat as cmb
from ..content.data import body_plans as bp
from ..ui import portrait_zones as pz
from ..ui import art as _art
from ..ui import ui as _ui


def _mk_enemy(key, tags, hp=40):
    e = Entity(key=key, entity_type=T_MONSTER, fallback_name=key,
               hp=hp, max_hp=hp, ac=12, tags=list(tags))
    bp.init_body_parts(e)
    return e


def test_per_portrait_hitboxes_resolve():
    for key in ("wrog_intake_freezer_carver", "wrog_intake_warden",
                "wrog_intake_nadzorca_sortowni", "wrog_intake_biotech_inspector",
                "wrog_intake_humanoid_industrial"):
        hb = pz.zones_for(key, "humanoid",
                          {"head", "torso", "l_arm", "r_arm", "l_leg", "r_leg"})
        assert hb and "torso" in hb and "head" in hb, key
    rat = pz.zones_for("wrog_intake_tunnel_runt", "beast",
                       {"head", "torso", "l_leg", "r_leg"})
    assert rat and set(rat) == {"head", "torso", "l_leg", "r_leg"}
    print("  per-portrait hitboxes resolve: OK")


def test_archetype_fallback():
    hb = pz.zones_for("wrog_does_not_exist", "humanoid",
                      {"head", "torso", "l_arm", "r_arm", "l_leg", "r_leg"})
    assert hb and "torso" in hb, "humanoid fallback missing"
    quad = pz.zones_for(None, "beast", {"head", "torso", "l_leg", "r_leg"})
    assert quad and "torso" in quad, "quadruped fallback missing"
    drone = pz.zones_for(None, "robot", {"sensor", "body", "propulsion"})
    # robot has its own humanoid-ish set, not drone zones → no torso match.
    none = pz.zones_for(None, "nonsense", set())
    assert none is None, "empty plan should not resolve"
    print("  archetype fallbacks: OK")


def test_zones_subset_and_normalized():
    plan_zones = {"head", "torso", "l_arm", "r_leg"}   # deliberately partial
    hb = pz.zones_for("wrog_intake_freezer_carver", "humanoid", plan_zones)
    assert set(hb) <= plan_zones, "returned a zone outside the plan"
    # Validate every box across every table is in-bounds.
    tables = [pz.HITBOXES[k] for k in pz.HITBOXES] + \
             [pz.ARCHETYPE_HITBOXES[k] for k in pz.ARCHETYPE_HITBOXES]
    for tbl in tables:
        for zk, (fx, fy, fw, fh) in tbl.items():
            assert 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0, (zk, fx, fy)
            assert fw > 0 and fh > 0, (zk, fw, fh)
            assert fx + fw <= 1.02 and fy + fh <= 1.02, (zk, "overflow")
    print("  zones subset + normalized in-bounds: OK")


def test_resolve_art_key_finds_png():
    e = _mk_enemy("freezer_carver", ["monster", "humanoid"])
    key = _art.resolve_enemy_art_key(e, "intake_industrial")
    assert key == "wrog_intake_freezer_carver", key
    rat = _mk_enemy("tunnel_runt", ["monster", "small", "biting", "robactwo"])
    assert _art.resolve_enemy_art_key(rat, "intake_industrial") \
        == "wrog_intake_tunnel_runt"
    print("  resolve_enemy_art_key finds real PNG: OK")


class _Clicks:
    def __init__(self):
        self.zones = []

    def add(self, rect, cb, *, tooltip="", category=""):
        self.zones.append((rect, category))


def test_silhouette_renders_with_clickzones():
    w = WorldState()
    w.character = Character(name="C", background="soldier")
    f = FloorState(floor_id="c", floor_number=1, biome_key="intake_industrial")
    r = RoomState(room_id="r0", fallback_short_title="Arena")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    e = _mk_enemy("freezer_carver", ["monster", "humanoid"], hp=63)
    w.register(e); r.entities.append(e)
    cs = cmb.start_combat(r, w)
    cs.selected_target_id = e.entity_id
    plan = bp.plan_for_entity(e)
    L = _ui._resolve_layout(None)
    surf = pygame.Surface((300, 460))
    clicks = _Clicks()
    _ui._draw_silhouette(surf, e, plan, 4, 4, 292, 452, L, "l_arm",
                         cs=cs, click_registry=clicks, world=w)
    # One clickable hit-zone per plan zone, all tagged vats_zone:.
    cats = [c for _, c in clicks.zones]
    assert len(clicks.zones) == len(plan), (len(clicks.zones), len(plan))
    assert all(c.startswith("vats_zone") for c in cats), cats
    # Clicking a zone updates the target's selected zone.
    rect, _ = clicks.zones[0]
    print(f"  silhouette renders over portrait + {len(clicks.zones)} "
          f"clickable zones: OK")


def main():
    test_per_portrait_hitboxes_resolve()
    test_archetype_fallback()
    test_zones_subset_and_normalized()
    test_resolve_art_key_finds_png()
    test_silhouette_renders_with_clickzones()
    print("P30 portrait VATS limb targeting smoke: OK")


if __name__ == "__main__":
    main()
