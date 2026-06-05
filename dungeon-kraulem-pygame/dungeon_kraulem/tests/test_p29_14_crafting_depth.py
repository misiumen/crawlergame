"""Prompt 29.14 — Crafting depth smoke suite.

Audit finding: 14 named recipes, no quality tiers wired to combat,
no buff stack (poison-on-blade etc.), no sponsor-branded recipes.
P29.14 lifts the catalog to ~30, plumbs masterwork/good/normal/flawed
all the way through to weapon damage, adds the enhancement category
(consumables that apply to existing weapons/armor), adds cooking +
sponsor-branded recipes gated by attention.

Covers:
  * Recipe catalog grew (>= 28 entries now, was 14).
  * Quality-tier mapping: critical_success → masterwork, partial
    → flawed.
  * Crafted weapon with quality=masterwork carries
    state["quality"]="masterwork" and combat path adds +1 attack +1 dmg.
  * Enhancement items are tagged and carry the recipe key for the
    apply handler to look up.
  * Parser recognises `nałóż X na Y`.
  * Apply handler: poison_coat puts a coating on the weapon.
  * Apply handler: grip tape bumps attack_bonus_perm.
  * Apply handler: armor_padding bumps ac_bonus_perm + flows to AC.
  * Sponsor-branded recipe refuses without unlock flag.
  * Sponsor attention crossing +5 stamps the unlock flag.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data.recipe_templates import RECIPES
from ..content import crafting as _cr
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_ITEM
from ..engine.parser_core import parse


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Catalog growth ───────────────────────────────────────────────────────

def test_recipe_catalog_expanded():
    """P29.14 added at least 14 new recipes on top of the original 14."""
    assert len(RECIPES) >= 28, f"recipe catalog regressed: {len(RECIPES)}"
    new_keys = [
        "fire_trap_recipe", "acid_flask_recipe", "poison_dart_recipe",
        "frost_charge_recipe",
        "weapon_poison_coat", "weapon_grip_tape",
        "weapon_balance_weight", "weapon_silencer",
        "armor_padding", "armor_acid_lining",
        "cooked_meat", "morale_brew", "caffeine_pill",
        "nova_chem_stim_pack", "kanal_7_microphone",
        "czarny_rynek_lockpick_kit",
    ]
    missing = [k for k in new_keys if k not in RECIPES]
    assert not missing, f"missing new recipes: {missing}"
    print(f"  {len(RECIPES)} recipes in catalog ({len(new_keys)} new): OK")


# ── Quality tier mapping ────────────────────────────────────────────────

def test_quality_tier_mapping():
    assert _cr.quality_for_level("critical_success") == "masterwork"
    assert _cr.quality_for_level("success") == "good"
    assert _cr.quality_for_level("partial_success") == "flawed"
    assert _cr.quality_for_level("failure") == "normal"
    print("  quality_for_level mapping: OK")


def test_quality_bonuses_for_weapon():
    mw = _cr.quality_bonus_for_weapon("masterwork")
    assert mw == {"attack_bonus": 1, "damage_bonus": 1}
    fl = _cr.quality_bonus_for_weapon("flawed")
    assert fl == {"attack_bonus": -1, "damage_bonus": 0}
    print("  quality bonuses table: OK")


# ── Crafted entity carries quality + tags ────────────────────────────────

def test_make_crafted_entity_quality_propagates():
    ent_mw = _cr.make_crafted_entity("improvised_knife", quality="masterwork")
    assert ent_mw.state.get("quality") == "masterwork"
    assert "weapon" in ent_mw.tags
    ent_fl = _cr.make_crafted_entity("improvised_knife", quality="flawed",
                                     damaged=True)
    assert ent_fl.state.get("quality") == "flawed"
    assert ent_fl.state.get("damaged") is True
    print("  make_crafted_entity respects quality + damaged: OK")


# ── Enhancements tag + recipe-key plumbing ───────────────────────────────

def test_enhancement_entities_tagged_correctly():
    for key in ("weapon_poison_coat", "weapon_grip_tape", "armor_padding"):
        ent = _cr.make_crafted_entity(key)
        assert "enhancement" in ent.tags, f"{key} missing 'enhancement' tag"
        assert "consumable" in ent.tags
        assert ent.state.get("enhancement_key") == key, \
            f"{key} didn't stash enhancement_key"
    print("  enhancement items tagged + carry recipe key: OK")


# ── Parser ──────────────────────────────────────────────────────────────

def test_parser_apply_enhancement_intent():
    for cmd in ("nałóż olej zatrucia na nóż", "zamontuj owijka uchwytu na pała",
                "apply poison coat to knife"):
        intent = parse(cmd)
        assert intent.intent == "apply_enhancement", \
            f"{cmd!r} parsed as {intent.intent}"
        assert intent.tool, f"no tool: {cmd}"
        assert intent.targets, f"no targets: {cmd}"
    print("  parser maps nałóż/zamontuj/apply → apply_enhancement: OK")


# ── Apply: poison coat → weapon coating ─────────────────────────────────

def test_apply_poison_coat_sets_coating():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    # Build a weapon + an enhancement, both in inventory.
    weapon = _cr.make_crafted_entity("improvised_knife", quality="normal")
    w.register(weapon); w.character.inventory_ids.append(weapon.entity_id)
    enh = _cr.make_crafted_entity("weapon_poison_coat")
    w.register(enh); w.character.inventory_ids.append(enh.entity_id)
    pre_inv = len(w.character.inventory_ids)
    g.submit_generated_command("nałóż olej na nóż")
    # Coating set on weapon.
    coating = (weapon.state or {}).get("coating") or {}
    assert coating.get("damage_type") == "poison", \
        f"coating not set: {weapon.state}"
    assert coating.get("hits_remaining", 0) > 0
    # Enhancement consumed.
    assert enh.entity_id not in w.character.inventory_ids, \
        "enhancement should be consumed"
    assert len(w.character.inventory_ids) == pre_inv - 1
    print(f"  poison_coat → weapon coating + consumed: OK "
          f"(type={coating['damage_type']}, hits={coating['hits_remaining']})")


# ── Apply: grip tape → permanent attack bonus ───────────────────────────

def test_apply_grip_tape_permanent_attack_bonus():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    weapon = _cr.make_crafted_entity("improvised_club", quality="normal")
    w.register(weapon); w.character.inventory_ids.append(weapon.entity_id)
    enh = _cr.make_crafted_entity("weapon_grip_tape")
    w.register(enh); w.character.inventory_ids.append(enh.entity_id)
    g.submit_generated_command("nałóż owijka na pała")
    assert weapon.state.get("attack_bonus_perm") == 1, \
        f"attack_bonus_perm not set: {weapon.state}"
    assert "gripped" in (weapon.tags or [])
    print("  grip_tape → +1 attack_bonus_perm + gripped tag: OK")


# ── Apply: armor padding → AC flows through equipment.total_ac_bonus ────

def test_apply_armor_padding_flows_to_effective_ac():
    from ..engine.game import Game
    from ..engine import equipment as _eq
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    # Craft armor + put it in worn_slots["chest"].
    armor = _cr.make_crafted_entity("armor_patch", quality="normal")
    # Make sure tags include "armor" so apply check passes.
    assert "armor" in armor.tags
    w.register(armor); w.character.inventory_ids.append(armor.entity_id)
    # Equip the armor — direct slot wiring (canonical slot key is "torso").
    w.character.worn_slots["torso"] = armor.entity_id
    # Craft the padding enhancement.
    enh = _cr.make_crafted_entity("armor_padding")
    w.register(enh); w.character.inventory_ids.append(enh.entity_id)
    pre_ac = _eq.total_ac_bonus(w, w.character)
    g.submit_generated_command("nałóż wyściółka na łatka")
    post_ac = _eq.total_ac_bonus(w, w.character)
    assert post_ac == pre_ac + 1, \
        f"armor AC didn't bump: {pre_ac}→{post_ac}"
    assert "padded" in (armor.tags or [])
    print(f"  armor padding → AC {pre_ac}→{post_ac} via equipment.total_ac_bonus: OK")


# ── Sponsor-branded recipes gated by unlock flag ────────────────────────

def test_sponsor_recipe_refused_without_unlock():
    w, _r = _mk_world()
    # Give the player every material the recipe wants — refusal must
    # be the sponsor gate, not missing materials.
    w.character.materials = {"cloth_strips": 5, "chem_reagent": 5,
                             "disinfectant": 5}
    plan = _cr.try_known_recipe(w.character, "nova_chem_stim_pack")
    assert plan["valid"] is False
    assert plan["reason"] == "sponsor_locked", \
        f"expected sponsor_locked refusal, got {plan['reason']}"
    print("  sponsor recipe refused without unlock: OK")


def test_sponsor_recipe_unlocked_when_flag_set():
    w, _r = _mk_world()
    w.character.materials = {"cloth_strips": 5, "chem_reagent": 5,
                             "disinfectant": 5}
    w.character.flags["sponsor_recipe_unlocked_novachem_biotech"] = True
    plan = _cr.try_known_recipe(w.character, "nova_chem_stim_pack")
    assert plan["valid"] is True, f"unlock flag should let it pass: {plan}"
    print("  sponsor recipe unlocked when flag set: OK")


def test_sponsor_attention_5_stamps_unlock_flag():
    from ..engine import sponsors as _sp
    w, _r = _mk_world()
    # Attention lives on character.flags["sponsor_attention"] — seed
    # it directly to keep the test independent of rate-limited tag-bus
    # paths. Canonical sponsor key is `novachem_biotech`.
    w.character.flags = {"sponsor_attention": {"novachem_biotech": 5}}
    _sp._check_gift_thresholds(w)
    assert w.character.flags.get("sponsor_recipe_unlocked_novachem_biotech"), \
        f"attention=5 should stamp unlock flag; flags={w.character.flags}"
    print("  attention >= 5 stamps sponsor_recipe_unlocked_<sponsor>: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_recipe_catalog_expanded()
    test_quality_tier_mapping()
    test_quality_bonuses_for_weapon()
    test_make_crafted_entity_quality_propagates()
    test_enhancement_entities_tagged_correctly()
    test_parser_apply_enhancement_intent()
    test_apply_poison_coat_sets_coating()
    test_apply_grip_tape_permanent_attack_bonus()
    test_apply_armor_padding_flows_to_effective_ac()
    test_sponsor_recipe_refused_without_unlock()
    test_sponsor_recipe_unlocked_when_flag_set()
    test_sponsor_attention_5_stamps_unlock_flag()
    print("Prompt 29.14 crafting depth smoke: OK")


if __name__ == "__main__":
    main()
