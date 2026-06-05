"""Prompt 29.43 — System rarity (5 stopni) + biome tagi na itemach.

Wybór user'a (opcja B z audytu P29.43): struktura bez rozszerzania
puli. Field rarity na items, biome tagi tam gdzie sensowne, brak
wymyślania nowych itemów. Standardowy fantasy naming.

Pokrywa:
  * engine/rarity.py — 5 stopni, polskie labels, kolory RGB,
    rarity_order, rarity_weights_for_floor, pick_rarity_for_floor.
  * Items mają field `rarity` w ITEM_TEMPLATES; awansowane:
    floor_map (rare), kombinezon_hazmat (epic), amulet_szczescia
    (rare), kamizelka_taktyczna (rare), maska_filtrujaca (rare),
    cheap_knife (uncommon), itd. — większość zostaje common.
  * make_item kopiuje rarity z template do entity.state.
  * Niektóre items mają biome tagi: maska_filtrujaca → trenches,
    kombinezon_hazmat → reactor, kalosze → sewers,
    fartuch_laboratoryjny → clone_farm, amulet_szczescia → museum,
    pas_narzedziowy → forge.
  * JournalEntry.title_color (RGB) jest ustawiane przez
    _collect_inventory wg rarity itemu. UI renderer (ui.py) używa
    title_color jeśli ustawione.
  * Save/load round-trip rarity (state.rarity przeżywa).
"""
from __future__ import annotations
import os
import random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine import rarity as _rar
from ..content.items import ITEM_TEMPLATES, make_item


# ── engine/rarity.py: stopnie + lookups ──────────────────────────────

def test_five_rarities_in_canonical_order():
    assert _rar.ALL_RARITIES == (
        "common", "uncommon", "rare", "epic", "legendary",
    )
    # Order index rosnąco.
    assert _rar.rarity_order("common") < _rar.rarity_order("uncommon")
    assert _rar.rarity_order("rare") < _rar.rarity_order("epic")
    assert _rar.rarity_order("epic") < _rar.rarity_order("legendary")
    print("  ALL_RARITIES (5 stopni) + order index: OK")


def test_polish_labels():
    assert _rar.rarity_pl("common") == "pospolity"
    assert _rar.rarity_pl("uncommon") == "niepospolity"
    assert _rar.rarity_pl("rare") == "rzadki"
    assert _rar.rarity_pl("epic") == "epicki"
    assert _rar.rarity_pl("legendary") == "legendarny"
    print("  rarity_pl: standardowe nazewnictwo PL: OK")


def test_rarity_color_returns_rgb_tuple():
    for r in _rar.ALL_RARITIES:
        c = _rar.rarity_color(r)
        assert isinstance(c, tuple) and len(c) == 3
        assert all(0 <= ch <= 255 for ch in c)
    # Common = jasny szary, legendary = pomarańcz.
    assert _rar.rarity_color("common")[0] > 150
    assert _rar.rarity_color("legendary")[0] > 200    # red >>
    print("  rarity_color: RGB dla każdego stopnia: OK")


def test_invalid_rarity_falls_through_to_common_color():
    c = _rar.rarity_color("transcendent")
    assert c == _rar.rarity_color("common")
    print("  rarity_color invalid → fallback common: OK")


# ── Floor weights ────────────────────────────────────────────────────

def test_floor_weights_scale_with_depth():
    w1 = _rar.rarity_weights_for_floor(1)
    w8 = _rar.rarity_weights_for_floor(8)
    w16 = _rar.rarity_weights_for_floor(16)
    # F1: legendary niedostępny.
    assert w1.get("legendary", 0) == 0
    # F8: legendary 1, F16: znacznie więcej.
    assert w8["legendary"] >= 1
    assert w16["legendary"] > w8["legendary"]
    # Common spada z głębokością.
    assert w1["common"] > w16["common"]
    print(f"  wagi per piętro: F1.legendary=0, F8.legendary="
          f"{w8['legendary']}, F16.legendary={w16['legendary']}: OK")


def test_pick_rarity_for_floor_deterministic():
    rng = random.Random(42)
    # Na F1 z seedem powinno głównie wpadać common.
    picks = [_rar.pick_rarity_for_floor(rng, 1) for _ in range(100)]
    common_count = picks.count("common")
    assert common_count >= 75, f"F1 common count {common_count}/100"
    # Na F18 powinno być znacznie więcej rare+.
    rng2 = random.Random(42)
    picks_deep = [_rar.pick_rarity_for_floor(rng2, 18) for _ in range(100)]
    rare_plus = sum(1 for r in picks_deep
                    if _rar.rarity_order(r) >= _rar.rarity_order("rare"))
    assert rare_plus >= 30, f"F18 rare+ count {rare_plus}/100"
    print(f"  F1 common ratio: {common_count}%; F18 rare+ ratio: "
          f"{rare_plus}%: OK")


# ── Items: rarity field obecne ───────────────────────────────────────

def test_item_templates_all_have_rarity_field():
    """Po P29.43 każdy template ma field `rarity` (explicit albo
    fallback do common)."""
    missing = []
    for key, tmpl in ITEM_TEMPLATES.items():
        r = tmpl.get("rarity")
        if r is None:
            missing.append(key)
        elif not _rar.is_valid_rarity(r):
            missing.append(f"{key}:invalid={r}")
    # Items bez explicit rarity są OK (fallback do common), ale
    # liczę ile JEST explicit żeby się upewnić że refaktor zadziałał.
    explicit = [k for k, v in ITEM_TEMPLATES.items() if v.get("rarity")]
    assert len(explicit) >= 30, \
        f"oczekiwane ≥30 itemów z explicit rarity; jest {len(explicit)}"
    assert not missing, f"invalid rarity values: {missing}"
    print(f"  {len(explicit)}/{len(ITEM_TEMPLATES)} itemów z explicit rarity: OK")


def test_specific_items_advanced_to_higher_tiers():
    assert _rar.item_rarity(ITEM_TEMPLATES["floor_map"]) == "rare"
    assert _rar.item_rarity(ITEM_TEMPLATES["kombinezon_hazmat"]) == "epic"
    assert _rar.item_rarity(ITEM_TEMPLATES["amulet_szczescia"]) == "rare"
    assert _rar.item_rarity(ITEM_TEMPLATES["kamizelka_taktyczna"]) == "rare"
    assert _rar.item_rarity(ITEM_TEMPLATES["snack_bar"]) == "common"
    print("  konkretne items: floor_map=rare, kombinezon=epic, "
          "amulet=rare, snack=common: OK")


def test_some_items_have_biome_tags():
    """Część itemów dostaje biome tagi — generator filter w lootu
    będzie je preferował w odpowiednich biomach."""
    biome_tagged_items = {
        "maska_filtrujaca": "trenches",
        "kombinezon_hazmat": "reactor",
        "kalosze": "sewers",
        "fartuch_laboratoryjny": "clone_farm",
        "amulet_szczescia": "museum",
        "pas_narzedziowy": "forge",
    }
    for key, expected_tag in biome_tagged_items.items():
        tags = ITEM_TEMPLATES[key].get("tags") or []
        assert expected_tag in tags, \
            f"{key}: brak biome tag '{expected_tag}'; tags={tags}"
    print(f"  {len(biome_tagged_items)} itemów ma biome tagi: OK")


# ── make_item: state.rarity ──────────────────────────────────────────

def test_make_item_stamps_rarity_on_state():
    ent = make_item("floor_map", location_id="test")
    assert (ent.state or {}).get("rarity") == "rare"
    ent2 = make_item("snack_bar", location_id="test")
    assert (ent2.state or {}).get("rarity") == "common"
    # entity_rarity helper.
    assert _rar.entity_rarity(ent) == "rare"
    assert _rar.entity_rarity(ent2) == "common"
    print("  make_item zapisuje rarity na entity.state: OK")


def test_make_item_does_not_clobber_equip_state():
    """Wearables mają equip_state (ac_bonus, equip_resists) — rarity
    musi być DOPISANE, nie zamiast."""
    ent = make_item("kamizelka_taktyczna", location_id="test")
    assert ent.state.get("ac_bonus") == 2
    assert "physical" in (ent.state.get("equip_resists") or [])
    assert ent.state.get("rarity") == "rare"
    print("  make_item rarity + equip_state razem: OK")


# ── Journal entry: title_color ───────────────────────────────────────

def test_inventory_journal_sets_title_color_per_rarity():
    from ..ui.journal import _collect_inventory
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    # Dodaj do plecaka: jeden common, jeden epic.
    common = make_item("snack_bar", location_id="inventory:player")
    epic = make_item("kombinezon_hazmat", location_id="inventory:player")
    w.register(common); w.register(epic)
    w.character.inventory_ids.append(common.entity_id)
    w.character.inventory_ids.append(epic.entity_id)

    entries = _collect_inventory(w)
    titles_by_color = {e.title: e.title_color for e in entries}
    # Każdy item ma title_color.
    assert all(e.title_color is not None for e in entries)
    # Common != epic kolor.
    common_color = _rar.rarity_color("common")
    epic_color = _rar.rarity_color("epic")
    found_common = any(c == common_color for c in titles_by_color.values())
    found_epic = any(c == epic_color for c in titles_by_color.values())
    assert found_common, "brak common color w panelu"
    assert found_epic, "brak epic color w panelu"
    print(f"  Ekwipunek: title_color per rarity (common + epic obecne): OK")


def test_sponsor_gift_aliases_resolve_to_real_items():
    """P29.43-sweep — sponsor gift_pool ma 36 itemów których
    NIE BYŁO w ITEM_TEMPLATES (bandage, stimpak, antidote, ...).
    Po sweep mapują się przez _ITEM_ALIASES do istniejących template'ów,
    więc drop pod nie wystawia gołego entity bez tagów / affordances."""
    from dungeon_kraulem.content.data.sponsors import SPONSORS
    # Każdy item z gift_pool resolve'uje się do CZEGOŚ z tagami.
    failures = []
    for skey, sdata in SPONSORS.items():
        for ikey in (sdata.get("gift_pool") or []):
            ent = make_item(ikey, location_id="test")
            if not ent.tags:
                failures.append(f"{skey}:{ikey} → entity bez tagów")
            if "loot" not in (ent.affordances or []):
                failures.append(f"{skey}:{ikey} → brak affordance 'loot'")
    assert not failures, f"sponsor gifts bez tagów/affordances: {failures[:5]}"
    print("  sponsor gift_pool: 100% itemów dostaje tagi + loot affordance: OK")


def test_alias_specific_examples():
    """Konkretne aliasy: 'bandage' → dirty_bandage, 'stimpak' →
    ostatnia_pigulka, 'lockpick' → lockpick_set."""
    bandage = make_item("bandage", location_id="test")
    assert "medical" in (bandage.tags or []), \
        f"bandage alias nie zadziałał; tags={bandage.tags}"
    pick = make_item("lockpick", location_id="test")
    assert "lockpick" in (pick.tags or [])
    blessed = make_item("blessed_amulet", location_id="test")
    # blessed_amulet → amulet_szczescia (rare, museum biome)
    assert "occult" in (blessed.tags or [])
    assert blessed.state.get("rarity") == "rare"
    print("  konkretne aliasy: bandage / lockpick / blessed_amulet: OK")


def test_rarity_survives_save_load_round_trip():
    """Rarity ląduje w entity.state przez make_item; state jest
    serializowany do dict — sprawdzamy że po Entity.to_dict / from_dict
    rarity pozostaje na miejscu."""
    from ..engine.entity import Entity
    ent = make_item("kombinezon_hazmat", location_id="inventory:player")
    pre_rarity = (ent.state or {}).get("rarity")
    d = ent.to_dict()
    ent2 = Entity.from_dict(d)
    post_rarity = (ent2.state or {}).get("rarity")
    assert pre_rarity == "epic"
    assert post_rarity == "epic"
    assert _rar.entity_rarity(ent2) == "epic"
    print("  rarity save/load round-trip: OK")


def test_inventory_journal_sort_puts_rare_first():
    """sort_key powinien sortować rzadsze itemy NA GÓRĘ (rarity desc)."""
    from ..ui.journal import _collect_inventory
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    common = make_item("snack_bar", location_id="inventory:player")
    epic = make_item("kombinezon_hazmat", location_id="inventory:player")
    w.register(common); w.register(epic)
    w.character.inventory_ids.append(common.entity_id)
    w.character.inventory_ids.append(epic.entity_id)
    entries = _collect_inventory(w)
    entries.sort(key=lambda e: e.sort_key)
    # Epic ma rarity_order=3 (-3 jako sort_key), common 0 (0 jako sort_key)
    # → epic powinien być pierwszy.
    assert entries[0].raw_ref.key == "kombinezon_hazmat"
    print("  sort_key: epic > common w panelu Ekwipunek: OK")


# ── Suite ────────────────────────────────────────────────────────────

def main():
    test_five_rarities_in_canonical_order()
    test_polish_labels()
    test_rarity_color_returns_rgb_tuple()
    test_invalid_rarity_falls_through_to_common_color()
    test_floor_weights_scale_with_depth()
    test_pick_rarity_for_floor_deterministic()
    test_item_templates_all_have_rarity_field()
    test_specific_items_advanced_to_higher_tiers()
    test_some_items_have_biome_tags()
    test_make_item_stamps_rarity_on_state()
    test_make_item_does_not_clobber_equip_state()
    test_sponsor_gift_aliases_resolve_to_real_items()
    test_alias_specific_examples()
    test_rarity_survives_save_load_round_trip()
    test_inventory_journal_sets_title_color_per_rarity()
    test_inventory_journal_sort_puts_rare_first()
    print("Prompt 29.43 rarity + biome tags smoke: OK")


if __name__ == "__main__":
    main()
