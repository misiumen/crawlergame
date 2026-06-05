"""P29.65 Etap B — fixed-dice tabela broni (Bug #19).

Po naprawie wiringu (Etap A) broń realnie tnie swoją kością. Tu pilnujemy, że
krzywa ma sens: rośnie wg rzadkości, a goła pięść (1d4) jest ŚCIŚLE najsłabsza —
podniesienie JAKIEJKOLWIEK broni musi być lepsze niż walka pięściami (dziś było
odwrotnie: hardkod pięści 2d6+8 bił mocniej niż legendarny młot).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.dice import avg_spec
from ..content import items as I
from ..content import crafting as CR

FIST = "1d4"  # game.py — domyślna „broń" gołych rąk

# Krzywa wg rzadkości (kotwica P29.65).
RARITY_CURVE = [
    ("common",    "1d6"),
    ("uncommon",  "1d6+1"),
    ("rare",      "1d8+1"),
    ("epic",      "1d10+2"),
    ("legendary", "2d6+3"),
]


def test_rarity_curve_is_strictly_increasing():
    avgs = [avg_spec(d) for _r, d in RARITY_CURVE]
    assert all(a < b for a, b in zip(avgs, avgs[1:])), \
        f"krzywa broni nie rośnie monotonicznie: {avgs}"
    print(f"  krzywa rarity rośnie: {avgs}")


def test_fist_is_strictly_weakest():
    fist = avg_spec(FIST)
    weakest_weapon = min(avg_spec(d) for _r, d in RARITY_CURVE)
    assert fist < weakest_weapon, \
        f"pięść ({fist}) nie jest słabsza od najsłabszej broni ({weakest_weapon})"
    print(f"  pięść {fist} < najsłabsza broń {weakest_weapon}")


def test_content_weapons_match_their_tier():
    cases = {
        "cleaver_handle":        ("1d6",    "common"),
        "cheap_knife":           ("1d6+1",  "uncommon"),
        "warden_baton":          ("1d6+1",  "uncommon"),
        "miecz_okopowy_oficera": ("1d10+2", "epic"),
        "mlot_kowalski_polorka": ("2d6+3",  "legendary"),
    }
    for key, (dice, rarity) in cases.items():
        e = I.make_item(key)
        assert e.damage_dice == dice, f"{key}: {e.damage_dice!r} != {dice!r}"
        assert e.state.get("rarity") == rarity, f"{key} rarity"
        assert avg_spec(e.damage_dice) > avg_spec(FIST), f"{key} <= pięść"
    # warden_baton: typ obrażeń elektryczny przeszedł na encję
    assert I.make_item("warden_baton").damage_type == "electric"
    print("  bronie kontentowe na właściwych kościach + typ OK")


def test_every_crafted_weapon_beats_the_fist():
    fist = avg_spec(FIST)
    crafted = ["crafted_shiv", "improvised_weapon", "improvised_knife",
               "improvised_spear", "improvised_club", "improvised_garrote",
               "improvised_taser", "improvised_chembottle"]
    for key in crafted:
        e = CR.make_crafted_entity(key)
        assert avg_spec(e.damage_dice) > fist, \
            f"craft {key} ({e.damage_dice}) nie bije pięści ({FIST})"
    print(f"  {len(crafted)} broni craftowanych > pięść OK")


def main():
    test_rarity_curve_is_strictly_increasing()
    test_fist_is_strictly_weakest()
    test_content_weapons_match_their_tier()
    test_every_crafted_weapon_beats_the_fist()
    print("P29.65 Etap B weapon curve: OK")


if __name__ == "__main__":
    main()
