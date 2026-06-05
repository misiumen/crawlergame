"""P29.65 Etap A — hydraulika kości (regression guard).

Trzy buy martwych danych, które rozmontowały balans walki (Bug #19/#25):
  1. `_enemy_attack_damage` parsował kości przez `split("d")`+`int(sides)` →
     rzucał na formacie skalera "NdS+B" i cicho fallbackował do 1d4.
  2. `make_item` nie kopiował `equip_state["weapon_dice"]` → `damage_dice`, więc
     każda broń kontentowa biła jak default Entity "1d4".
  3. roller gracza gubił "-B".

Te testy pilnują, że JEDEN współdzielony roller (`engine.dice.roll_spec`) działa
dla obu stron i że broń realnie tnie swoją kością.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import random

from ..engine import dice as D
from ..engine import combat as C
from ..engine.entity import Entity
from ..content import items as I


# ── roller ───────────────────────────────────────────────────────────────

def test_roll_spec_handles_all_formats():
    rng = random.Random(7)
    cases = {
        "1d4": (1, 4), "2d8+13": (15, 29), "1d10+2": (3, 12),
        "2d6-1": (1, 11), "3": (3, 3),
    }
    for spec, (lo, hi) in cases.items():
        vals = [D.roll_spec(spec, rng) for _ in range(2000)]
        assert min(vals) >= lo and max(vals) <= hi, \
            f"{spec!r} range {min(vals)}-{max(vals)} poza [{lo},{hi}]"
        # sampled mean blisko analitycznej średniej
        assert abs(sum(vals) / len(vals) - D.avg_spec(spec)) < 0.6, spec
    # śmieci → 0, nie wyjątek
    assert D.roll_spec("garbage", rng) == 0
    assert D.roll_spec("", rng) == 0
    assert D.roll_spec(None, rng) == 0
    print("  roll_spec: NdS / NdS+B / NdS-B / N / junk OK")


def test_roll_spec_negative_bonus_not_silently_zeroed():
    # Stary game._roll_dice_spec zwracał 0 na "2d6-1" (gubił minus).
    rng = random.Random(1)
    vals = [D.roll_spec("2d6-1", rng) for _ in range(2000)]
    assert sum(vals) / len(vals) > 4.5, "‑B musi liczyć kości, nie zerować"
    print("  roll_spec: -B liczone, nie zerowane OK")


# ── broń realnie tnie ──────────────────────────────────────────────────────

def test_make_item_wires_weapon_dice_to_damage_dice():
    # Bug #19 root: equip_state.weapon_dice musi trafić na damage_dice.
    # (Konkretne wartości kości pilnuje Etap B — tu tylko WIRING.)
    for key in ["miecz_okopowy_oficera", "mlot_kowalski_polorka"]:
        e = I.make_item(key)
        wd = e.state.get("weapon_dice")
        assert wd and wd != "1d4", f"{key}: brak weapon_dice w state"
        assert e.damage_dice == wd, \
            f"{key}: damage_dice={e.damage_dice!r} != weapon_dice {wd!r}"
    print("  make_item: weapon_dice → damage_dice OK")


def test_entity_from_dict_backfills_weapon_dice():
    # Stary save broni: damage_dice="1d4" (default), ale state ma weapon_dice.
    d = Entity(key="x", damage_dice="1d4").to_dict()
    d["state"]["weapon_dice"] = "2d6+3"
    e = Entity.from_dict(d)
    assert e.damage_dice == "2d6+3", "back-fill ze state nie zadziałał"
    # gdy NIE ma weapon_dice, zostaje "1d4" (nie ruszamy zwykłych encji)
    d2 = Entity(key="mob", damage_dice="1d4").to_dict()
    assert Entity.from_dict(d2).damage_dice == "1d4"
    print("  from_dict: back-fill weapon_dice OK")


# ── mob: parser naprawiony + brak atk_bonus w obrażeniach ──────────────────

def test_enemy_attack_damage_parses_scaled_dice():
    # "2d8+13" musi dawać 15..29, NIGDY fallback 1d4 (1..4).
    e = Entity(key="mob", damage_dice="2d8+13", attack_bonus=5)
    vals = [C._enemy_attack_damage(e) for _ in range(3000)]
    assert min(vals) >= 15, f"min {min(vals)} → fallback 1d4 wrócił"
    assert 20.0 < sum(vals) / len(vals) < 24.0
    print("  _enemy_attack_damage: parsuje NdS+B OK")


def test_enemy_attack_damage_ignores_attack_bonus():
    # attack_bonus to stat TO-HIT — nie wolno go dodawać do obrażeń.
    e = Entity(key="mob", damage_dice="3", attack_bonus=50)
    vals = {C._enemy_attack_damage(e) for _ in range(200)}
    assert vals == {3}, f"obrażenia {vals} — atk_bonus przeciekł do dmg"
    print("  _enemy_attack_damage: atk_bonus NIE w obrażeniach OK")


def main():
    test_roll_spec_handles_all_formats()
    test_roll_spec_negative_bonus_not_silently_zeroed()
    test_make_item_wires_weapon_dice_to_damage_dice()
    test_entity_from_dict_backfills_weapon_dice()
    test_enemy_attack_damage_parses_scaled_dice()
    test_enemy_attack_damage_ignores_attack_bonus()
    print("P29.65 Etap A dice plumbing: OK")


if __name__ == "__main__":
    main()
