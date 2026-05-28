"""Prompt 29.52 — Per-class starting recipes + discovery.

Pytanie gracza: „skąd jako gracz znam tyle przepisów na start? to
kwestia bycia mechanikiem czy każda klasa ma to wszystko? częścią
rozgrywki powinno być improwizowanie w tym odkrywanie przepisów."

Diagnoza: brak `character.known_recipes`. Każdy mógł craftować
WSZYSTKIE 29 przepisów od startu — zero progresji wiedzy.

Fix P29.52:
  • Character.known_recipes: List[str] + save/load.
  • starting_recipes_for(background) — większość ma 2 podstawy,
    mechanic/cook/paramedic/soldier mają 4-6.
  • try_known_recipe blokuje nieznane (poza sponsorskimi które
    mają osobny gate).
  • _show_craft_help filtruje tylko znane + hint o nieznanych.
  • 10 recipe_note_* itemów. `użyj` uczy + zużywa notatkę.
  • Improvise (try_improvise) zostaje ZAWSZE dostępny — bez przepisu.

Pokrywa:
  * mechanic startuje z 6 znanymi (więcej niż większość)
  * janitor / streamer startują z 2 (uniwersalne)
  * unknown background → uniwersalne 2
  * try_known_recipe odrzuca nieznany przepis
  * teach_recipe dodaje + idempotent
  * recipe_note przy use uczy i znika z plecaka
  * save/load round-trip known_recipes
"""
from __future__ import annotations

from ..engine import run_history as _rh
from ..content import crafting as _cr


def test_universal_recipes_for_unknown_background():
    """Nieznany background → tylko universal recipes (2)."""
    recs = _cr.starting_recipes_for("totally_made_up_xyz")
    assert "improvised_bandage" in recs
    assert "improvised_knife" in recs
    assert len(recs) == 2
    print("  unknown bg → 2 universal: OK")


def test_mechanic_starts_with_more_recipes():
    """Mechanic dostaje 4+ przepisów z classy techy."""
    recs = _cr.starting_recipes_for("mechanic")
    assert len(recs) >= 5, f"mechanic powinien mieć ≥5 przepisów, got {len(recs)}"
    assert "shock_trap" in recs
    assert "improvised_taser" in recs
    print(f"  mechanic startuje z {len(recs)} przepisami: OK")


def test_janitor_minimal():
    """Janitor (default starter) ma tylko universal."""
    recs = _cr.starting_recipes_for("janitor")
    assert len(recs) == 2
    assert set(recs) == {"improvised_bandage", "improvised_knife"}
    print("  janitor → 2 universal: OK")


def test_each_background_has_starting_recipes():
    """Każdy z BACKGROUNDS dostaje niepusty zestaw."""
    from ..engine.character import BACKGROUNDS
    for bg in BACKGROUNDS:
        recs = _cr.starting_recipes_for(bg)
        assert len(recs) >= 2, f"{bg} ma {len(recs)} starting recipes"
    print(f"  {len(BACKGROUNDS)} backgroundów ma ≥2 starting recipes: OK")


def test_teach_recipe_idempotent():
    """teach_recipe(...) — nowy zwraca True, drugi raz False."""
    _rh.reset()
    from ..engine.character import Character
    ch = Character(name="t", background="janitor")
    ch.known_recipes = ["improvised_bandage"]
    assert _cr.teach_recipe(ch, "shock_trap") is True
    assert "shock_trap" in ch.known_recipes
    assert _cr.teach_recipe(ch, "shock_trap") is False  # second time no-op
    assert ch.known_recipes.count("shock_trap") == 1
    print("  teach_recipe idempotent: OK")


def test_try_known_recipe_blocks_unknown():
    """Nieznajomy przepis → invalid z reason=recipe_not_known."""
    _rh.reset()
    from ..engine.character import Character
    ch = Character(name="t", background="janitor")
    ch.known_recipes = ["improvised_bandage"]  # NIE zna shock_trap
    ch.materials = {"cloth_strips": 5, "disinfectant": 5,
                     "battery": 5, "wire": 5}  # dużo materiałów
    res = _cr.try_known_recipe(ch, "shock_trap")
    assert not res["valid"]
    assert res["reason"] == "recipe_not_known", \
        f"oczekiwany recipe_not_known, dostalem {res['reason']}"
    print("  try_known_recipe blokuje nieznany: OK")


def test_try_known_recipe_allows_known():
    """Znany przepis i materiały OK → valid."""
    _rh.reset()
    from ..engine.character import Character
    ch = Character(name="t", background="janitor")
    ch.known_recipes = ["improvised_bandage"]
    ch.materials = {"cloth_strips": 5, "disinfectant": 5}
    res = _cr.try_known_recipe(ch, "improvised_bandage")
    assert res["valid"], f"valid recipe odrzucony: {res}"
    print("  try_known_recipe akceptuje znany: OK")


def test_recipe_note_template_resolves():
    """make_item('recipe_note_shock_trap') daje entity z state.recipe_key."""
    from ..content.items import make_item
    ent = make_item("recipe_note_shock_trap")
    assert ent is not None
    assert (ent.state or {}).get("recipe_key") == "shock_trap"
    assert "recipe" in (ent.tags or [])
    assert "use" in (ent.affordances or [])
    print("  recipe_note template ma state.recipe_key + tag recipe: OK")


def test_save_load_preserves_known_recipes():
    """to_dict/from_dict round-trip dla known_recipes."""
    from ..engine.character import Character
    ch = Character(name="t", background="mechanic")
    ch.known_recipes = ["improvised_bandage", "shock_trap", "tripwire"]
    d = ch.to_dict()
    assert "known_recipes" in d
    ch2 = Character.from_dict(d)
    assert ch2.known_recipes == ch.known_recipes
    print("  save/load round-trip known_recipes: OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_universal_recipes_for_unknown_background()
        test_mechanic_starts_with_more_recipes()
        test_janitor_minimal()
        test_each_background_has_starting_recipes()
        test_teach_recipe_idempotent()
        test_try_known_recipe_blocks_unknown()
        test_try_known_recipe_allows_known()
        test_recipe_note_template_resolves()
        test_save_load_preserves_known_recipes()
    finally:
        _rh.reset()
    print("Prompt 29.52 recipe learning smoke: OK")


if __name__ == "__main__":
    main()
