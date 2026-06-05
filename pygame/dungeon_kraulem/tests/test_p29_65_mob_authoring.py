"""P29.65 Etap C — re-author mobów na fixed-dice + krzywa głębokości.

Pilnuje, że: (1) ślepy mnożnik ×5/×4 ZNIKNĄŁ, (2) autorskie stat-blocki z
MOB_COMBAT_STATS faktycznie siedzą na encjach MON, (3) role trzymają sensowne
pasma HP/obrażeń, (4) scale_for_floor jest łagodne i home-relative (bez
podwójnego liczenia), (5) arena (testbed usera) buduje trio na nowych statach,
a broń gracza realnie tnie (damage_dice != "1d4").
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data import entity_templates as ET
from ..content.data.entity_templates import MON, MOB_COMBAT_STATS
from ..engine.dice import avg_spec
from ..engine.entity import Entity
from ..engine import balance, arena

FIST_AVG = avg_spec("1d4")  # 2.5


def test_blanket_scaler_is_gone():
    # Stary hack P27.6 usunięty (×5 HP/×4 dmg, który i tak był martwy).
    for sym in ("_apply_balance_scale", "_scale_damage_dice", "_HP_SCALE",
                "_DMG_MULT"):
        assert not hasattr(ET, sym), f"{sym} powinno zniknąć (P29.65)"
    assert hasattr(ET, "MOB_COMBAT_STATS")
    print("  ślepy skaler ×5/×4 usunięty; MOB_COMBAT_STATS żyje")


def test_authoring_applied_to_MON():
    for key, (hp, dice, atk, ac) in MOB_COMBAT_STATS.items():
        t = MON.get(key)
        assert t is not None, f"{key} brak w MON"
        assert t["hp"] == hp and t["max_hp"] == hp, f"{key} HP"
        assert t["damage_dice"] == dice, f"{key} dice"
        assert t["attack_bonus"] == atk and t["ac"] == ac, f"{key} atk/ac"
    print(f"  {len(MOB_COMBAT_STATS)} stat-blocków nałożonych na MON")


def test_roles_in_sane_bands():
    # Tagowe role muszą trzymać sensowne pasma (tripwire na literówki w tabeli).
    for key, (hp, dice, atk, ac) in MOB_COMBAT_STATS.items():
        tags = set(MON[key].get("tags") or [])
        dmg = avg_spec(dice)
        assert dmg > FIST_AVG, f"{key} bije <= pięść"
        if "final_boss" in tags:
            assert hp >= 280, f"{key} final boss za słaby ({hp})"
        elif "floor_boss" in tags:
            assert 90 <= hp <= 260 and 10 <= dmg <= 17, f"{key} boss poza pasmem"
        elif "miniboss" in tags or any(str(t).startswith("boss_rank:") for t in tags):
            assert 90 <= hp <= 185 and 9 <= dmg <= 14, f"{key} miniboss poza pasmem"
        elif "small" in tags:
            assert hp <= 30 and dmg <= 5, f"{key} chaff poza pasmem"
        else:
            assert 28 <= hp <= 180 and 4 <= dmg <= 11, f"{key} mob poza pasmem ({hp},{dmg})"
    print("  role trzymają pasma HP/obrażeń")


# ── scale_for_floor ────────────────────────────────────────────────────────

def _mob(hp=40, dice="1d6+2", floor_min=None):
    tags = ["monster"]
    if floor_min is not None:
        tags.append(f"floor_min:{floor_min}")
    return Entity(key="m", hp=hp, max_hp=hp, damage_dice=dice, tags=tags)

def test_scale_for_floor_home_relative():
    # Na piętrze domowym → bez zmian.
    e = _mob(floor_min=3)
    balance.scale_for_floor(e, 3, home_floor=3)
    assert e.max_hp == 40 and e.damage_dice == "1d6+2"
    # Głębiej → HP rośnie, stała obrażeń rośnie co 3 piętra.
    e2 = _mob(floor_min=3)
    balance.scale_for_floor(e2, 9, home_floor=3)   # depth 6
    assert e2.max_hp > 40, "głębiej powinno podbić HP"
    assert avg_spec(e2.damage_dice) > avg_spec("1d6+2"), "depth 6 → +bonus"
    # Nieznane piętro domowe → no-op (bezpiecznie, bez podwójnego liczenia).
    e3 = _mob(floor_min=None)
    balance.scale_for_floor(e3, 12, home_floor=None)
    assert e3.max_hp == 40 and e3.damage_dice == "1d6+2"
    print("  scale_for_floor: home-relative + no-op gdy nieznane")


def test_scale_for_floor_ignores_non_combat():
    env = Entity(key="env", hp=0, max_hp=0, tags=["floor_min:1"])
    balance.scale_for_floor(env, 10, home_floor=1)
    assert env.max_hp == 0  # brak max_hp → no-op
    print("  scale_for_floor: nie rusza nie-potworów")


# ── arena testbed (wymóg usera) ─────────────────────────────────────────────

def test_arena_trio_authored_and_weapon_cuts():
    for vk in ("duel_1v1", "miniboss_sortownia", "boss_fight"):
        res = arena.build_arena_world(vk)
        w = res[0] if isinstance(res, tuple) else res
        ch = w.character
        wpn = w.get(ch.wielded_main_id)
        assert wpn is not None, f"{vk}: brak broni w łapie"
        assert wpn.damage_dice != "1d4", \
            f"{vk}: broń nadal bije 1d4 (wiring zepsuty) — {wpn.key}"
        mobs = [e for e in w.current_floor.current_room().entities
                if e.entity_type == "monster"]
        assert mobs, f"{vk}: brak wroga na arenie"
        for m in mobs:
            assert m.key in MOB_COMBAT_STATS, f"{vk}: {m.key} bez autorskich statów"
            assert m.max_hp == MOB_COMBAT_STATS[m.key][0], \
                f"{vk}: {m.key} HP {m.max_hp} != autorskie"
    print("  arena: trio na autorskich statach + broń tnie (nie 1d4)")


def test_arena_weakness_coating_is_testable():
    # Wymóg usera: arena musi pozwolić PRZETESTOWAĆ nowy combat — w tym system
    # słabości. Powłoka broni daje narzędzie; tu sprawdzamy cały rurociąg:
    # kwas na nadzorcy (słabość) = 2×, fizyczne (odporność) = ½.
    from ..engine import damage
    res = arena.build_arena_world("miniboss_sortownia")
    w = res[0] if isinstance(res, tuple) else res
    wpn = w.get(w.character.wielded_main_id)
    coat = (wpn.state or {}).get("coating") or {}
    assert coat.get("damage_type") == "acid", "miniboss: powłoka kwasowa"
    nad = [e for e in w.current_floor.current_room().entities
           if e.key == "nadzorca_sortowni"][0]
    r_acid = damage.apply_damage(w, nad, 10, damage_type="acid")
    assert r_acid.get("vulnerable") and r_acid.get("amount_dealt") == 20, \
        "kwas na nadzorcy musi być 2× (podatny)"
    nad.hp = nad.max_hp
    r_phys = damage.apply_damage(w, nad, 10, damage_type="physical")
    assert r_phys.get("resisted") and r_phys.get("amount_dealt") == 5, \
        "fizyczne na nadzorcy musi być ½ (osłabione)"
    print("  arena: powłoka kwasowa + słabość/odporność testowalne (2× / ½)")


def main():
    test_blanket_scaler_is_gone()
    test_authoring_applied_to_MON()
    test_roles_in_sane_bands()
    test_scale_for_floor_home_relative()
    test_scale_for_floor_ignores_non_combat()
    test_arena_trio_authored_and_weapon_cuts()
    print("P29.65 Etap C mob authoring: OK")


if __name__ == "__main__":
    main()
