"""Prompt 29.36 — Floor-3 species offer + 11-species catalog with
passives + drawbacks wired across the engine.

DCC-faithful: first time the player reaches floor 3, the mutation
chamber offers 4 random species + the "stay as you are" decline
option. Choice is permanent for the run.

Each non-baseline species has 2-4 passive traits + 2-4 drawback
traits. Traits are stamped on character.flags at apply_species time
and queried via engine/species_effects.

Covers:
  * Catalog shape (11 species; ferromanta present; baseline_human is
    the decline sentinel; non-baseline pool has 4+ traits each).
  * apply_species() stamps stat_bonus + hp_bonus + every passive +
    drawback flag.
  * Idempotent re-apply (save/load) doesn't double the stat bumps.
  * AC bonus (metal_skin scrapkin) lands in effective_ac.
  * Incoming damage mul: fragile +25%, EMP +50% on shock, half_dead
    50% resist on necrotic.
  * Status immunity: poison synthetic, bleed synthetic, grappled
    chimera, disarmed ferromanta.
  * Audience multiplier: enhanced ×1.25, void ×0.5.
  * Sponsor goodwill cap (chimera 10 except Kanał 7).
  * Sponsor envy (enhanced -1 non-NovaChem).
  * Ministerstwo-hostile (half_dead blocks positive Ministerstwo
    delta).
  * Movement minutes: pathfinder -1, leaden_steps +1.
  * Trap refuse: ferromanta + non-metal trap.
  * Stealth refuse: ferromanta scanner.
  * Rest doubled: synthetic.
  * Threat escalation slowdown: fungal in player's room.
  * Regen tick: fungal +1 HP per minute, capped at half max.
  * Telepathy + precog: one-shot per floor.
  * On-descent biopsy drain (enhanced -1 audience) + companion bond
    drift (fungal -2, half_dead -1).
  * Game flow: _maybe_offer_species fires once on floor 3, then never
    again; accept commits the species_key; decline leaves it.
  * Random offer pool excludes player's current species.
"""
from __future__ import annotations
import os
import random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..systems import species as _sp_cat
from ..engine import species_effects as _sp_fx
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _world(species_pre=None):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    w.character.species_key = species_pre or "baseline_human"
    if w.character.flags is None:
        w.character.flags = {}
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="x")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    w.floor_number = 1
    return w


def _apply(w, key):
    assert _sp_cat.apply_species(w, key), f"apply failed for {key}"


# ── Catalog shape ───────────────────────────────────────────────────────

def test_catalog_has_eleven_species():
    cat = _sp_cat.SPECIES_CATALOG
    assert len(cat) == 11, f"expected 11 species; got {len(cat)}"
    assert "baseline_human" in cat
    assert "ferromanta" in cat
    print(f"  catalog has 11 species incl. ferromanta: OK")


def test_each_non_baseline_has_passives_and_drawbacks():
    for key, sp in _sp_cat.SPECIES_CATALOG.items():
        if key == "baseline_human":
            continue
        assert sp.passives, f"{key} has no passives"
        assert sp.drawbacks, f"{key} has no drawbacks"
        assert sp.name_pl, f"{key} missing name_pl"
        assert sp.flavor_pl, f"{key} missing flavor_pl"
    print("  each non-baseline species has passives+drawbacks+PL: OK")


# ── apply_species: stats, flags, idempotent ─────────────────────────────

def test_apply_species_stamps_stats_and_flags():
    w = _world()
    base_str = w.character.stats["STR"]
    base_hp = w.character.max_hp
    _apply(w, "chimera")
    assert w.character.species_key == "chimera"
    assert w.character.stats["STR"] == base_str + 2
    assert w.character.max_hp == base_hp + 8
    assert _sp_fx.has_trait(w.character, "third_arm_unarmed")
    assert _sp_fx.has_trait(w.character, "grapple_immune")
    assert _sp_fx.has_trait(w.character, "horror_first_meet")
    print("  chimera apply: STR+2, +8 HP, traits flagged: OK")


def test_apply_species_idempotent():
    """Save/load round-trip: re-apply same species shouldn't double
    stats."""
    w = _world()
    _apply(w, "scrapkin")
    hp_after_first = w.character.max_hp
    con_after_first = w.character.stats["CON"]
    _apply(w, "scrapkin")
    assert w.character.max_hp == hp_after_first
    assert w.character.stats["CON"] == con_after_first
    print("  re-apply scrapkin: idempotent: OK")


# ── Combat: AC ─────────────────────────────────────────────────────────

def test_metal_skin_grants_ac():
    w = _world()
    base_ac = w.character.effective_ac()
    _apply(w, "scrapkin")
    assert w.character.effective_ac() == base_ac + 2, \
        f"scrapkin +2 AC missing; got {w.character.effective_ac()}"
    print("  scrapkin metal_skin +2 AC: OK")


# ── Combat: incoming damage ────────────────────────────────────────────

def test_fragile_amplifies_damage():
    w = _world()
    _apply(w, "glassblood")
    pre_hp = w.character.hp
    w.character.take_damage(10)
    # 10 dmg × 1.25 = 12 (or 13 with rounding).
    actual = pre_hp - w.character.hp
    assert actual >= 12, f"fragile didn't amplify; took {actual}"
    print(f"  glassblood fragile: 10 dmg -> {actual} hp lost: OK")


def test_emp_vuln_amplifies_shock():
    w = _world()
    _apply(w, "synthetic")
    pre_hp = w.character.hp
    w.character.take_damage(10, source_tag="shock")
    actual = pre_hp - w.character.hp
    assert actual >= 15, f"EMP didn't amplify; took {actual}"
    # Sanity: NON-shock damage should be normal.
    w.character.hp = pre_hp
    w.character.take_damage(10)
    base = pre_hp - w.character.hp
    assert base == 10, f"non-shock should be 10; got {base}"
    print(f"  synthetic EMP shock: 10 -> {actual}, generic 10 stays 10: OK")


def test_half_dead_resists_necrotic():
    w = _world()
    _apply(w, "half_dead")
    pre_hp = w.character.hp
    w.character.take_damage(10, source_tag="necrotic")
    actual = pre_hp - w.character.hp
    assert actual <= 5, f"necrotic_resist didn't reduce; took {actual}"
    print(f"  half_dead necrotic resist 50%: 10 -> {actual}: OK")


# ── Status immunity ────────────────────────────────────────────────────

def test_synthetic_poison_immune():
    from ..engine import combat as _cmb
    w = _world()
    _apply(w, "synthetic")
    _cmb.add_status(w.character, "poisoned", duration=3)
    assert "poisoned" not in (w.character.conditions or [])
    print("  synthetic poison-immune: status add refused: OK")


def test_chimera_grappled_immune():
    from ..engine import combat as _cmb
    w = _world()
    _apply(w, "chimera")
    _cmb.add_status(w.character, "grappled", duration=3)
    assert "grappled" not in (w.character.conditions or [])
    print("  chimera grappled-immune: OK")


def test_ferromanta_disarmed_immune():
    from ..engine import combat as _cmb
    w = _world()
    _apply(w, "ferromanta")
    _cmb.add_status(w.character, "disarmed", duration=3)
    assert "disarmed" not in (w.character.conditions or [])
    print("  ferromanta iron_grip disarmed-immune: OK")


# ── Audience ───────────────────────────────────────────────────────────

def test_enhanced_human_audience_amplified():
    from ..engine import audience as _aud
    w = _world()
    _apply(w, "enhanced_human")
    pre = w.character.audience_rating
    _aud.change_audience(w, 4, source="test", emit_log=False)
    # 4 × 1.25 = 5
    assert w.character.audience_rating - pre >= 5, \
        f"enhanced amp missing; got +{w.character.audience_rating - pre}"
    print(f"  enhanced_human audience ×1.25: +4 -> +"
          f"{w.character.audience_rating - pre}: OK")


def test_void_touched_audience_halved():
    from ..engine import audience as _aud
    w = _world()
    _apply(w, "void_touched")
    pre = w.character.audience_rating
    _aud.change_audience(w, 10, source="test", emit_log=False)
    delta = w.character.audience_rating - pre
    assert delta <= 5, f"void audience halving missing; got +{delta}"
    print(f"  void_touched audience ×0.5: +10 -> +{delta}: OK")


# ── Sponsors ───────────────────────────────────────────────────────────

def test_chimera_sponsor_cap_non_kanal7():
    from ..engine import sponsors as _sp
    w = _world()
    _apply(w, "chimera")
    _sp.adjust_attention(w, "novachem_biotech", 25)
    val = _sp.get_attention(w, "novachem_biotech")
    assert val == 10, f"chimera should cap NovaChem at 10; got {val}"
    # Kanał 7 exempt.
    _sp.adjust_attention(w, "kanal_7_krawedz", 25)
    k7 = _sp.get_attention(w, "kanal_7_krawedz")
    assert k7 > 10, f"Kanał 7 exempt; got {k7}"
    print(f"  chimera sponsor cap=10 (NovaChem={val}, K7={k7} exempt): OK")


def test_enhanced_human_sponsor_envy():
    from ..engine import sponsors as _sp
    w = _world()
    _apply(w, "enhanced_human")
    # Non-NovaChem positive delta should be -1.
    _sp.adjust_attention(w, "kult_recyklingu", 5)
    val = _sp.get_attention(w, "kult_recyklingu")
    assert val == 4, f"envy should drop delta by 1; got {val}"
    # NovaChem gets full bonus.
    _sp.adjust_attention(w, "novachem_biotech", 5)
    n = _sp.get_attention(w, "novachem_biotech")
    assert n == 5, f"NovaChem should be unaffected; got {n}"
    print(f"  enhanced sponsor envy: kult={val} (-1), nova={n} (full): OK")


def test_half_dead_blocks_ministerstwo():
    from ..engine import sponsors as _sp
    w = _world()
    _apply(w, "half_dead")
    _sp.adjust_attention(w, "ministerstwo_pamieci", 8)
    val = _sp.get_attention(w, "ministerstwo_pamieci")
    assert val == 0, f"half_dead should block positive ministerstwo; got {val}"
    print(f"  half_dead ministerstwo hostile freeze: OK")


# ── Movement minutes ───────────────────────────────────────────────────

def test_pathfinder_reduces_movement():
    w = _world()
    _apply(w, "tunnelborn")
    assert _sp_fx.movement_minutes(w.character, 3) == 2
    print("  tunnelborn pathfinder: 3 min -> 2 min: OK")


def test_leaden_steps_increases_movement():
    w = _world()
    _apply(w, "ferromanta")
    assert _sp_fx.movement_minutes(w.character, 3) == 4
    print("  ferromanta leaden_steps: 3 min -> 4 min: OK")


# ── Trap deploy refusal (ferromanta) ───────────────────────────────────

def test_ferromanta_refuses_non_metal_traps():
    w = _world()
    _apply(w, "ferromanta")
    class FakeTrap:
        tags = ["snare", "rope"]
    class MetalTrap:
        tags = ["metal", "trap"]
    assert _sp_fx.trap_deploy_refused(w.character, FakeTrap())
    assert not _sp_fx.trap_deploy_refused(w.character, MetalTrap())
    print("  ferromanta refuses snare/rope, accepts metal: OK")


# ── Stealth refusal ────────────────────────────────────────────────────

def test_ferromanta_stealth_refused():
    w = _world()
    _apply(w, "ferromanta")
    assert _sp_fx.stealth_refused(w.character)
    print("  ferromanta scanner_attention -> no stealth: OK")


# ── Rest doubled ───────────────────────────────────────────────────────

def test_synthetic_rest_doubled():
    w = _world()
    _apply(w, "synthetic")
    assert _sp_fx.rest_heal_mul(w.character) == 2.0
    print("  synthetic double_rest: heal mul = 2.0: OK")


# ── Threat slowdown ────────────────────────────────────────────────────

def test_fungal_threat_escalation_slowed():
    from ..engine import threat as _th
    w = _world()
    _apply(w, "fungal_host")
    room = w.current_floor.current_room()
    # 10 noise units in the player's room: should land as 7 (×0.7).
    _th.bump(w, room, 10, source="test", log_threshold_lines=False)
    assert room.noise_level <= 8, \
        f"fungal slow missing; got noise_level={room.noise_level}"
    print(f"  fungal spore_intimidate: 10 noise -> "
          f"{room.noise_level} in player's room: OK")


# ── Regen tick ─────────────────────────────────────────────────────────

def test_fungal_regen_ticks():
    w = _world()
    _apply(w, "fungal_host")
    w.character.hp = 5
    healed = _sp_fx.on_idle_tick(w, minutes=3)
    assert healed > 0
    assert w.character.hp == 5 + healed
    print(f"  fungal regen: +{healed} HP per 3-min idle tick: OK")


def test_regen_caps_at_half_max():
    w = _world()
    _apply(w, "fungal_host")
    w.character.max_hp = 20
    w.character.hp = 12   # already above half
    healed = _sp_fx.on_idle_tick(w, minutes=5)
    assert healed == 0, f"regen should cap at half; healed={healed}"
    print("  fungal regen caps at ½ max: OK")


# ── Telepathy + precog one-shot per floor ─────────────────────────────

def test_telepathy_one_shot_per_floor():
    w = _world()
    _apply(w, "void_touched")
    w.current_floor.floor_number = 4
    assert _sp_fx.telepathy_use(w) is True
    assert _sp_fx.telepathy_use(w) is False, "should be consumed"
    # Floor change → refreshed.
    w.current_floor.floor_number = 5
    assert _sp_fx.telepathy_use(w) is True
    print("  void telepathy: 1/floor, refreshes on descent: OK")


def test_precog_dodge_one_shot():
    w = _world()
    _apply(w, "void_touched")
    w.current_floor.floor_number = 4
    assert _sp_fx.precog_dodge_consume(w) is True
    assert _sp_fx.precog_dodge_consume(w) is False
    print("  void precog_dodge: 1/floor: OK")


# ── on_descent: biopsy + companion bond drift ─────────────────────────

def test_enhanced_human_biopsy_on_descent():
    from ..engine import audience as _aud
    w = _world()
    _apply(w, "enhanced_human")
    _aud.change_audience(w, 20, emit_log=False)
    pre = w.character.audience_rating
    lines = _sp_fx.on_descent(w)
    assert w.character.audience_rating == pre - 1
    assert any("biopsj" in ln.lower() for ln in lines)
    print(f"  enhanced biopsy on descent: -1 audience + line: OK")


def test_fungal_companion_bond_drift_on_descent():
    from ..engine import companion as _comp
    w = _world()
    _apply(w, "fungal_host")
    pet = _comp.Companion(kind=_comp.KIND_PET,
                           species_key="dog", display_name_pl="Rex",
                           bond=7, stress=0)
    _comp.register_companion(w, pet)
    pre = pet.bond
    _sp_fx.on_descent(w)
    assert pet.bond == pre - 2
    print(f"  fungal companion repel: bond {pre} -> {pet.bond}: OK")


# ── Game flow: offer fires once on floor 3 ─────────────────────────────

def test_offer_fires_once_on_floor_3():
    """P29.36: latch is set on COMMIT (accept or decline), not on
    initial render — that way a crash mid-offer doesn't silently
    consume the only chance. Re-calling _maybe_offer_species before
    commit DOES re-fire (defensive); after decline, it doesn't."""
    from ..engine.game import Game, STATE_SPECIES_OFFER, STATE_PLAY
    g = Game(screen=None)
    g.start_new_game("Test", "janitor")
    g.world.floor_number = 3
    g.world.current_floor.floor_number = 3
    g._maybe_offer_species()
    assert g.state == STATE_SPECIES_OFFER
    assert len(getattr(g, "species_offer_candidates", []) or []) == 4
    # Player declines → latch sets.
    g._decline_species()
    assert g.state == STATE_PLAY
    # Second call after commit: latched, doesn't re-fire.
    g._maybe_offer_species()
    assert g.state == STATE_PLAY, "offer should be one-shot after commit"
    print("  offer one-shot AFTER commit (decline-then-retry): OK")


def test_offer_does_not_latch_until_commit():
    """If the player triggers the offer but crashes/exits before
    committing, the latch should NOT be set — they'd lose their
    only chance otherwise."""
    from ..engine.game import Game, STATE_SPECIES_OFFER, STATE_PLAY
    g = Game(screen=None)
    g.start_new_game("Test", "janitor")
    g.world.floor_number = 3
    g.world.current_floor.floor_number = 3
    g._maybe_offer_species()
    assert g.state == STATE_SPECIES_OFFER
    # Simulate "player exited without choosing" — manually clear state.
    g.state = STATE_PLAY
    g.species_offer_candidates = []
    # Latch should still be unset → re-call re-opens.
    g._maybe_offer_species()
    assert g.state == STATE_SPECIES_OFFER, \
        "latch shouldn't trigger before commit; reentry must work"
    print("  no latch before commit (crash-safe re-entry): OK")


def test_decline_path_keeps_species_key():
    from ..engine.game import Game, STATE_PLAY
    g = Game(screen=None)
    g.start_new_game("Test", "janitor")
    g.world.floor_number = 3
    g.world.current_floor.floor_number = 3
    g._maybe_offer_species()
    pre_key = g.world.character.species_key
    g._decline_species()
    assert g.state == STATE_PLAY
    assert g.world.character.species_key == pre_key
    print(f"  decline keeps species_key={pre_key!r}: OK")


def test_accept_path_commits_species():
    from ..engine.game import Game, STATE_PLAY
    g = Game(screen=None)
    g.start_new_game("Test", "janitor")
    g.world.floor_number = 3
    g.world.current_floor.floor_number = 3
    g._maybe_offer_species()
    candidates = g.species_offer_candidates
    target = candidates[0]
    g._accept_species(0)
    assert g.world.character.species_key == target
    assert g.state == STATE_PLAY
    print(f"  accept commits species_key={target}: OK")


# ── Random offer pool excludes current species ─────────────────────────

def test_random_offer_excludes_current():
    rng = random.Random(42)
    offer = _sp_cat.random_offer(rng, exclude_keys=("scrapkin",))
    assert "scrapkin" not in offer
    assert "baseline_human" not in offer
    assert len(offer) == 4
    print(f"  random_offer excludes scrapkin: {offer}: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_catalog_has_eleven_species()
    test_each_non_baseline_has_passives_and_drawbacks()
    test_apply_species_stamps_stats_and_flags()
    test_apply_species_idempotent()
    test_metal_skin_grants_ac()
    test_fragile_amplifies_damage()
    test_emp_vuln_amplifies_shock()
    test_half_dead_resists_necrotic()
    test_synthetic_poison_immune()
    test_chimera_grappled_immune()
    test_ferromanta_disarmed_immune()
    test_enhanced_human_audience_amplified()
    test_void_touched_audience_halved()
    test_chimera_sponsor_cap_non_kanal7()
    test_enhanced_human_sponsor_envy()
    test_half_dead_blocks_ministerstwo()
    test_pathfinder_reduces_movement()
    test_leaden_steps_increases_movement()
    test_ferromanta_refuses_non_metal_traps()
    test_ferromanta_stealth_refused()
    test_synthetic_rest_doubled()
    test_fungal_threat_escalation_slowed()
    test_fungal_regen_ticks()
    test_regen_caps_at_half_max()
    test_telepathy_one_shot_per_floor()
    test_precog_dodge_one_shot()
    test_enhanced_human_biopsy_on_descent()
    test_fungal_companion_bond_drift_on_descent()
    test_offer_fires_once_on_floor_3()
    test_offer_does_not_latch_until_commit()
    test_decline_path_keeps_species_key()
    test_accept_path_commits_species()
    test_random_offer_excludes_current()
    print("Prompt 29.36 species offer smoke: OK")


if __name__ == "__main__":
    main()
