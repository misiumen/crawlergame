"""Prompt 29.45 — Volume content (hazardy / encountery / legendary).

Audit P29.40 wykazał trzy krytyczne dziury w content volume:
  * HAZ — 1 wpis (kałuża kwasu) na cały build. Skutek: pokoje
    nigdy nie miały rzeczywistych zagrożeń środowiskowych.
  * ENCOUNTER_TEMPLATES — 6 wpisów na 13 danger-roomów. Powtórki
    co dwa-trzy pokoje.
  * Itemy — 0 legendary, 1 epic. Top tier rarity nieosiągalny.

Fix P29.45:
  * HAZ rozszerzone do 13 (12 nowych).
  * ENCOUNTER_TEMPLATES rozszerzone do 21 (15 nowych).
  * 5 epic + 6 legendary itemów dodane do ITEM_TEMPLATES.

Pokrywa:
  * count progu HAZ (>= 12)
  * każdy HAZ ma damage_type + tags + affordances + nazwę PL
  * każdy nowy HAZ ma sensowne `hazardous` w tags
  * count progu ENCOUNTER_TEMPLATES (>= 20)
  * każdy nowy encounter ma intro + at least 3 resolutions + fallback_title
  * count legendary >= 5 i epic >= 5
  * każdy legendary ma equip_state z co najmniej jednym efektem
  * wszystkie nowe itemy ozdobione `make_item()` rozwijają się do
    Entity z affordances + tags + rarity w state
"""
from __future__ import annotations

from ..content.data.entity_templates import HAZ
from ..content.data.encounter_templates import ENCOUNTER_TEMPLATES
from ..content.items import ITEM_TEMPLATES, make_item
from ..engine import run_history as _rh


# ── HAZ ──────────────────────────────────────────────────────────────


def test_haz_count_threshold():
    """HAZ ma teraz minimum 12 wpisów (było 1)."""
    assert len(HAZ) >= 12, f"HAZ ma tylko {len(HAZ)}"
    print(f"  HAZ count: {len(HAZ)}: OK")


def test_each_haz_well_formed():
    """Każdy HAZ: nazwa PL, fallback_desc, tags zawiera 'hazardous',
    damage_type, affordances zawiera 'inspect'."""
    for key, h in HAZ.items():
        assert h.get("fallback_name"), f"{key} bez fallback_name"
        assert h.get("fallback_desc"), f"{key} bez fallback_desc"
        tags = h.get("tags", [])
        assert "hazardous" in tags, f"{key} bez tagu 'hazardous'"
        assert h.get("damage_type"), f"{key} bez damage_type"
        aff = h.get("affordances", [])
        assert "inspect" in aff, f"{key} bez 'inspect' w affordances"
    print(f"  każdy z {len(HAZ)} HAZów dobrze sformowany: OK")


def test_haz_biome_tags_present():
    """Pula HAZ pokrywa różne biomy. Co najmniej 5 unikalnych
    biome-tagów wśród wszystkich hazardów."""
    biome_tags = {"trenches","steampunk_factory","orbital","forge",
                  "library","sewers","goblin_camp","fungal","reactor",
                  "bar","museum","zoo","clone_farm"}
    seen = set()
    for h in HAZ.values():
        seen |= set(h.get("tags", [])) & biome_tags
    assert len(seen) >= 5, f"za mało biome-tagów w HAZ: {seen}"
    print(f"  HAZ pokrywa {len(seen)} biomów: {seen}: OK")


# ── ENCOUNTERS ───────────────────────────────────────────────────────


def test_encounter_count_threshold():
    """ENCOUNTER_TEMPLATES >= 20 (było 6)."""
    n = len(ENCOUNTER_TEMPLATES)
    assert n >= 20, f"ENCOUNTER_TEMPLATES ma tylko {n}"
    print(f"  encounter count: {n}: OK")


def test_each_encounter_well_formed():
    """Każdy encounter: intro (lista zdań), fallback_title, weight,
    floor_min, possible_resolutions (>=3), tags."""
    for key, e in ENCOUNTER_TEMPLATES.items():
        assert e.get("intro"), f"{key} bez intro"
        assert isinstance(e["intro"], list) and e["intro"], \
            f"{key} intro nie jest niepustą listą"
        assert e.get("fallback_title"), f"{key} bez fallback_title"
        assert e.get("weight"), f"{key} bez weight"
        assert "floor_min" in e, f"{key} bez floor_min"
        res = e.get("possible_resolutions") or {}
        assert len(res) >= 3, (
            f"{key} ma tylko {len(res)} resolutions — minimum 3")
        assert e.get("tags"), f"{key} bez tagów"
    print(f"  każdy z {len(ENCOUNTER_TEMPLATES)} encounterów dobrze sformowany: OK")


def test_encounter_floor_spread():
    """Encountery rozkładają floor_min między 1 a F18. Powinno być
    co najmniej 4 różne floor_min w katalogu."""
    fmins = {e["floor_min"] for e in ENCOUNTER_TEMPLATES.values()}
    assert len(fmins) >= 4, f"za mała różnorodność floor_min: {fmins}"
    print(f"  encounter floor spread: {sorted(fmins)}: OK")


# ── ITEMY: legendary + epic ──────────────────────────────────────────


def test_legendary_count_threshold():
    """Co najmniej 5 itemów rarity=legendary."""
    legs = [k for k,t in ITEM_TEMPLATES.items()
            if t.get("rarity") == "legendary"]
    assert len(legs) >= 5, f"za mało legendary: {legs}"
    print(f"  legendary count: {len(legs)}: OK ({legs[:3]}...)")


def test_epic_count_threshold():
    """Co najmniej 5 itemów rarity=epic (było 1)."""
    eps = [k for k,t in ITEM_TEMPLATES.items()
           if t.get("rarity") == "epic"]
    assert len(eps) >= 5, f"za mało epic: {eps}"
    print(f"  epic count: {len(eps)}: OK")


def test_legendary_items_have_meaningful_state():
    """Każdy legendary ma equip_state z co najmniej jednym efektem."""
    legs = [k for k,t in ITEM_TEMPLATES.items()
            if t.get("rarity") == "legendary"]
    for k in legs:
        tpl = ITEM_TEMPLATES[k]
        st = tpl.get("equip_state") or {}
        assert st, f"legendary {k} ma pustą equip_state"
    print(f"  każdy z {len(legs)} legendary ma equip_state: OK")


def test_new_items_resolve_via_make_item():
    """Nowe itemy wpisane w P29.45 muszą rozwinąć się przez make_item
    z prawidłowym rarity na state."""
    new_keys = [
        "monoklokular_kuratora", "kombinezon_strażaka_korpo",
        "buty_z_blachy_okopowej", "lornetka_zwiadowcza",
        "miecz_okopowy_oficera",
        "krawat_konferansjera", "stara_mapa_borant",
        "mlot_kowalski_polorka", "amulet_widza_pierwszego",
        "garnitur_zarzadu", "plaszcz_kartograf_dluznika",
    ]
    for k in new_keys:
        ent = make_item(k)
        assert ent is not None, f"{k}: make_item zwróciło None"
        assert ent.tags, f"{k}: bez tagów"
        st = ent.state or {}
        assert st.get("rarity") in ("epic", "legendary"), \
            f"{k}: rarity={st.get('rarity')} nie jest top-tier"
    print(f"  {len(new_keys)} nowych itemów rozwija się przez make_item: OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_haz_count_threshold()
        test_each_haz_well_formed()
        test_haz_biome_tags_present()
        test_encounter_count_threshold()
        test_each_encounter_well_formed()
        test_encounter_floor_spread()
        test_legendary_count_threshold()
        test_epic_count_threshold()
        test_legendary_items_have_meaningful_state()
        test_new_items_resolve_via_make_item()
    finally:
        _rh.reset()
    print("Prompt 29.45 content volume smoke: OK")


if __name__ == "__main__":
    main()
