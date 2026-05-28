"""Prompt 29.51 — Punktowy wyciek angielskich raw kluczy w UI.

Zgłoszenie: screenshot z `_show_craft_help` wypluwał:
  morale_brew  (wywar morale)  [tak nazwiesz: ...]
  trap  → wymaga wire+binding | sharp | ...

Diagnoza: TO NIE JEST systemowy bug. Klucze snake_case w
katalogach (ITEM_TEMPLATES, IMPROVISED_CATEGORIES, MATERIAL_TAGS)
są słusznie angielskie — to stabilne identyfikatory wewnętrzne.
Bug jest punktowy: `_show_craft_help` był pisany jak debug-log
i wypluwał klucze obok polskich nazw. Plus brak polskich etykiet
dla tagów materiałów (sharp/wire/heavy/...).

Fix:
  * Centralna mapa `_MATERIAL_TAG_PL` + helper `tag_pl()` w crafting.py.
  * `_show_craft_help` używa `tag_pl()` + `category_pl()` zamiast
    raw kluczy.
  * Format zmieniony z „{key}  ({polski})" na samo „{polski}".

Pokrywa:
  * craft-help nie zawiera raw template_id w wyniku
  * craft-help nie zawiera raw category_key
  * raw material tags (sharp/wire/...) ZAMIENIONE na polskie
  * tag_pl() / category_pl() helper'y zwracają polski string
  * tag_pl() fallback do oryginalnego klucza przy nieznanym (nie
    crashuje, ale staje się widoczne że trzeba dopisać)
"""
from __future__ import annotations

from ..engine import run_history as _rh


def test_tag_pl_translates_known_keys():
    """Helper tłumaczy znane tagi materiałów na polski."""
    from ..content.crafting import tag_pl
    assert tag_pl("sharp") == "ostre"
    assert tag_pl("wire") == "drut"
    assert tag_pl("heavy") == "ciężkie"
    assert tag_pl("electrical") == "elektryczne"
    print("  tag_pl tłumaczy 4 znane tagi: OK")


def test_tag_pl_fallback_for_unknown():
    """Nieznany tag zwraca oryginalny klucz (nie crashuje)."""
    from ..content.crafting import tag_pl
    assert tag_pl("totally_made_up_xyz") == "totally_made_up_xyz"
    print("  tag_pl fallback dla unknown: OK")


def test_category_pl_translates():
    from ..content.crafting import category_pl
    assert category_pl("trap") == "improwizowana pułapka"
    assert category_pl("weapon") == "improwizowana broń"
    assert category_pl("disguise") == "improwizowana przebranie" or \
           category_pl("disguise") == "improwizowane przebranie"
    print("  category_pl tłumaczy znane kategorie: OK")


def test_show_craft_help_no_raw_keys():
    """E2E: _show_craft_help wypisuje TYLKO polski tekst — bez
    raw template_id, kategorii ani tagów."""
    from ..engine.game import Game
    from ..engine.world import WorldState
    from ..engine.character import Character

    g = Game(screen=None)
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    g.world = w

    # Przechwyć logowane linie:
    logged = []
    orig_log = g.log
    g.log = lambda s, cat=None: logged.append(s)
    try:
        g._show_craft_help()
    finally:
        g.log = orig_log

    full = "\n".join(logged)
    # Surowe template_id które wcześniej wyciekały:
    forbidden_raw = [
        "morale_brew", "caffeine_pill", "nova_chem_stim_pack",
        "kanal_7_microphone", "czarny_rynek_lockpick_kit",
    ]
    leaked = [k for k in forbidden_raw if k in full]
    assert not leaked, \
        f"surowe template_id w craft-help: {leaked}\n\nFULL:\n{full[:500]}"
    # Surowe kategorie:
    # NOTE: „weapon"/„tool" mogą jednak wystąpić w polskim tekście np.
    # „improwizowana broń (weapon)" więc nie blokujemy ich w pełni.
    # Sprawdzamy że NIE pojawiają się jako SAMODZIELNE słowa na początku
    # punktora.
    for raw_cat in ("trap  →", "weapon  →", "tool  →", "disguise  →"):
        assert raw_cat not in full, \
            f"raw category leak: {raw_cat!r}\n\nFULL:\n{full[:500]}"
    # Surowe tagi mat — szczególnie te jakie były na screenshocie.
    for raw_tag in ("wire+binding", "sharp |", "electrical |", "heavy |"):
        assert raw_tag not in full, \
            f"raw tag leak: {raw_tag!r}\n\nFULL:\n{full[:500]}"
    # Polski musi się pojawić:
    assert "improwizowana" in full, \
        "polski label kategorii nie pojawił się"
    print("  _show_craft_help: zero raw kluczy w wyniku: OK")


def main():
    _rh.reset()
    try:
        test_tag_pl_translates_known_keys()
        test_tag_pl_fallback_for_unknown()
        test_category_pl_translates()
        test_show_craft_help_no_raw_keys()
    finally:
        _rh.reset()
    print("Prompt 29.51 no raw keys in UI smoke: OK")


if __name__ == "__main__":
    main()
