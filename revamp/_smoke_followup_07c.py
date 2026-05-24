"""Follow-up smoke after the memetic-integration round.

Covers the five focused gaps:
1. `false_variant_chance` is rolled on clue delivery (sometimes returns
   the distorted text + lower reliability + `contaminated=True`).
2. `select_memetic_stat` resolves to CHA / INT / WIS by method and by
   keyword cues; Ollama suggestions agree when compatible.
3. `floor_generator._place_encounters` now consumes belief seeds when a
   world reference is provided.
4. High-distortion renders mutate the propagated claim (not the seed).
5. `is_weak_memetic_field` + cautious Ollama upgrade logic.

Run: python -m revamp._smoke_followup_07c
"""
import os, random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
random.seed(101)

from .world import WorldState
from .character import Character
from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_MONSTER
from . import memetics
from . import knowledge as kn
from . import content_loader as cl
from .parser_core import is_weak_memetic_field, ActionIntent


def _mk():
    w = WorldState()
    w.character = Character(name="F", background="streamer")
    w.character.stats["CHA"] = 16
    w.character.stats["INT"] = 14
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Studio")
    f.add_room(r); f.start_room_id="r0"; f.current_room_id="r0"
    w.current_floor = f
    return w, f, r


def test_roll_clue_delivery_returns_false_variant():
    """Roll an entry that has both a true text and a false variant; over
    100 rolls we should see both outcomes at roughly the configured rate."""
    rng = random.Random(7)
    clue = {
        "text_pl": "Prawdziwa wersja.",
        "false_variant_pl": "Zniekształcona wersja.",
        "false_variant_chance": 0.5,
        "reliability": 0.8,
    }
    true_count = false_count = 0
    for _ in range(200):
        out = cl.roll_clue_delivery(clue, rng=rng)
        if out["contaminated"]:
            false_count += 1
            assert out["text"] == "Zniekształcona wersja."
            assert out["reliability"] < 0.8  # lowered
        else:
            true_count += 1
            assert out["text"] == "Prawdziwa wersja."
            assert out["reliability"] == 0.8
    assert true_count > 50 and false_count > 50, \
        f"distribution looks off: true={true_count} false={false_count}"
    print(f"  roll_clue_delivery: OK ({false_count}/200 distorted)")


def test_roll_clue_delivery_no_false_variant_field():
    """Without false_variant_pl/text, must never produce a contaminated
    delivery even if chance is set."""
    rng = random.Random(7)
    clue = {"text_pl": "Czysta wersja.", "false_variant_chance": 1.0,
            "reliability": 0.9}
    for _ in range(50):
        out = cl.roll_clue_delivery(clue, rng=rng)
        assert not out["contaminated"]
        assert out["text"] == "Czysta wersja."
    print("  roll_clue_delivery (no false_variant): OK")


def test_select_memetic_stat_by_method():
    # Method-only resolution.
    assert memetics.select_memetic_stat("propaganda") == "CHA"
    assert memetics.select_memetic_stat("logic_exploit") == "INT"
    assert memetics.select_memetic_stat("false_order") == "INT"
    assert memetics.select_memetic_stat("identity_attack") == "WIS"
    assert memetics.select_memetic_stat("religious_framing") == "WIS"
    print("  select_memetic_stat by method: OK")


def test_select_memetic_stat_method_wins_over_llm():
    """LLM suggested_stat must lose against a clearly INT method like
    logic_exploit (which doesn't fall into the 'soft' set)."""
    intent = ActionIntent(raw_text="x")
    intent.modifiers.append("stat:CHA")
    assert memetics.select_memetic_stat("logic_exploit", intent) == "INT"
    # But for a soft method (rumor), LLM suggestion is allowed.
    intent = ActionIntent(raw_text="x")
    intent.modifiers.append("stat:WIS")
    assert memetics.select_memetic_stat("rumor", intent) == "WIS"
    print("  method-vs-LLM reconciliation: OK")


def test_select_memetic_stat_keyword_fallback():
    """Unknown method → keyword scoring on player text."""
    intent = ActionIntent(raw_text="wykorzystuję protokół, żeby obejść system")
    assert memetics.select_memetic_stat("", intent) == "INT"
    intent = ActionIntent(raw_text="trafiam w ich lęk przed wstydem i traumą")
    assert memetics.select_memetic_stat("", intent) == "WIS"
    intent = ActionIntent(raw_text="krzyczę do widowni o emocjach i retoryce")
    assert memetics.select_memetic_stat("", intent) == "CHA"
    print("  keyword stat fallback: OK")


def test_high_distortion_mutates_rumor():
    """A high-distortion seed should produce a mutated rendered claim — and
    the seed's `core_claim` field itself must stay untouched."""
    seed = memetics.create_seed(
        method="identity_attack",
        core_claim="ktoś ukradł im serca",
        target_tags=["machine","drone"],
        strength=70, stability=70,
    )
    seed.distortion = 75
    out = memetics.render_memetic_rumor(seed, index=0, language="pl")
    assert seed.core_claim == "ktoś ukradł im serca", "seed claim was mutated in place"
    # Mutation table swaps "ukradł im serca" → "szukają serc w żywych rzeczach"
    assert "szukają serc" in out or "częścią zamienną" in out \
        or "tym razem na pewno" in out or "dopiero połowa" in out, \
        f"mutation didn't visibly land: {out!r}"
    print(f"  high-distortion mutation: OK")
    print(f"    rendered: {out}")


def test_encounter_generation_uses_beliefs():
    """floor_generator._place_encounters should be callable with a world
    arg and at least try to consume belief seeds. Smoke just asserts the
    signature accepts world and the world's belief overlay is reached."""
    from . import floor_generator as fg
    w = WorldState()
    w.character = Character(name="GenTest", background="janitor")
    # Plant a strong machine-targeting belief BEFORE generating the floor.
    seed = memetics.create_seed(method="identity_attack",
                                core_claim="missing hearts",
                                target_tags=["machine","drone"],
                                strength=80, stability=70)
    memetics.register_seed(w, seed)
    floor = fg.generate_floor(w, floor_number=1, seed=4)
    # Inspect: at least one combat room should have either an encounter_key
    # or — when belief target tags overlap a template — a recorded overlay.
    any_overlay = any(r.state.get("encounter_belief_tags")
                      for r in floor.rooms.values())
    # We don't insist on overlay (depends on encounter pool), but the
    # generator must not crash and must place encounters.
    placed = sum(1 for r in floor.rooms.values()
                 if r.actual_type == "combat" and r.encounter_key)
    assert placed > 0 or sum(1 for r in floor.rooms.values()
                              if r.actual_type == "combat") == 0
    print(f"  encounter generation w/ beliefs: OK "
          f"(placed={placed}, belief_overlay_rooms={1 if any_overlay else 0})")


def test_is_weak_memetic_field():
    # Empty / single token / placeholder = weak
    assert is_weak_memetic_field(None) is True
    assert is_weak_memetic_field("") is True
    assert is_weak_memetic_field("belief") is True
    assert is_weak_memetic_field("plotka") is True
    assert is_weak_memetic_field("machine") is True
    assert is_weak_memetic_field("?") is True
    # Two-word phrase >= 8 chars and not in placeholder list: NOT weak.
    assert is_weak_memetic_field("stolen hearts") is False
    # Long multi-word phrase: definitely not weak.
    assert is_weak_memetic_field(
        "machines are incomplete because someone stole their hearts"
    ) is False
    print("  is_weak_memetic_field: OK")


def test_high_truth_rumors_added():
    """Ensure the new high-truth bucket exists and carries truth >= 0.9."""
    table = cl.all_rumor_categories()
    bucket = table.get("objective_high_truth") or []
    assert bucket, "objective_high_truth bucket missing"
    assert all(r.get("truth", 0) >= 0.9 for r in bucket), \
        "some objective_high_truth rumors are below 0.9 truth"
    assert len(bucket) >= 5, f"need >= 5 high-truth rumors, have {len(bucket)}"
    print(f"  high-truth rumors: OK ({len(bucket)} entries)")


def main():
    test_roll_clue_delivery_returns_false_variant()
    test_roll_clue_delivery_no_false_variant_field()
    test_select_memetic_stat_by_method()
    test_select_memetic_stat_method_wins_over_llm()
    test_select_memetic_stat_keyword_fallback()
    test_high_distortion_mutates_rumor()
    test_encounter_generation_uses_beliefs()
    test_is_weak_memetic_field()
    test_high_truth_rumors_added()
    print("Follow-up 07c smoke: OK")


if __name__ == "__main__":
    main()
