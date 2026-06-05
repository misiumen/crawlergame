"""P29.53n — Konsumuj tab in action panel.

Food/drink/medical items should surface in a dedicated UI group so
the player can hit them without scrolling through wearables/weapons.
The tab disappears when the player has nothing to consume.
"""
from __future__ import annotations

from ..ui import ui_nav as _nav
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.entity import Entity, T_ITEM


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    return w


def _add_item(w: WorldState, key: str, tags) -> Entity:
    e = Entity(key=key, entity_type=T_ITEM, fallback_name=key.replace("_", " "),
               tags=list(tags), portable=True,
               affordances=["inspect", "loot"])
    w.register(e)
    if w.character.inventory_ids is None:
        w.character.inventory_ids = []
    w.character.inventory_ids.append(e.entity_id)
    return e


def test_consume_tab_empty_when_no_consumables():
    """Nothing edible/drinkable → no Konsumuj group in layout."""
    w = _mk_world()
    _add_item(w, "rusty_knife", ["weapon"])
    opts = _nav._consume_options(w)
    assert opts == []


def test_consume_tab_lists_food_with_zjedz_verb():
    w = _mk_world()
    _add_item(w, "energy_bar", ["food"])
    opts = _nav._consume_options(w)
    assert len(opts) == 1
    o = opts[0]
    assert o.command.startswith("zjedz")
    assert "Zjedz" in o.label
    assert o.group == _nav.GROUP_CONSUME


def test_consume_tab_lists_drink_with_wypij_verb():
    w = _mk_world()
    _add_item(w, "coffee_cup", ["drink"])
    opts = _nav._consume_options(w)
    assert opts[0].command.startswith("wypij")
    assert "Wypij" in opts[0].label


def test_consume_tab_lists_medical_with_uzyj_verb():
    """Bandage = medical → Użyj verb (handler routes to consume)."""
    w = _mk_world()
    _add_item(w, "bandage", ["medical"])
    opts = _nav._consume_options(w)
    assert opts[0].command.startswith("użyj")


def test_consume_tab_skips_non_consumables():
    """Weapons, wearables, junk → not in Konsumuj."""
    w = _mk_world()
    _add_item(w, "energy_bar", ["food"])
    _add_item(w, "rusty_knife", ["weapon"])
    _add_item(w, "torn_jacket", ["clothing", "slot:torso"])
    _add_item(w, "scrap_metal", ["material"])
    opts = _nav._consume_options(w)
    assert len(opts) == 1
    assert "energy_bar".replace("_", " ") in opts[0].command


def test_consume_tab_handles_multiple_items_separately():
    w = _mk_world()
    _add_item(w, "energy_bar", ["food"])
    _add_item(w, "coffee_cup", ["drink"])
    _add_item(w, "bandage", ["medical"])
    opts = _nav._consume_options(w)
    assert len(opts) == 3
    cmds = [o.command.split()[0] for o in opts]
    assert "zjedz" in cmds
    assert "wypij" in cmds
    assert "użyj" in cmds


def test_consume_group_label_is_polish():
    """Label shown in the tab strip is „Konsumuj"."""
    assert _nav.group_label(_nav.GROUP_CONSUME) == "Konsumuj"
