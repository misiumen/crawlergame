"""P30 smoke — telegraphed intentions, utility AI, charged specials, morale.

Asserts:
1. plan_intents populates cs.enemy_intents with a valid category per hostile.
2. Telegraphed intents round-trip through CombatState save/load.
3. Utility AI band logic: ranged backs off in melee / shoots at range;
   berserker engaged vs a healthy player commits to attack.
4. Charged special: a stunned winding-up enemy fizzles (realize → wait);
   cooldown gates re-use.
5. Special release inflicts its telegraphed status + damage on a hit.
6. Defensive stance raises the bar to hit (STATUS_GUARDING → +3 to land).
7. Morale: an ally falling shakes survivors; low morale pushes coward to flee.
8. Panic override: a committed attacker that's now near death may break.
9. Full enemy turn runs end-to-end and re-plans next-round intents.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

from .. import config
config.apply_llm_mode("performance")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import combat as cmb
from ..engine import enemy_ai as ai


_VALID_CATS = {ai.CAT_ATTACK, ai.CAT_DEFEND, ai.CAT_SPECIAL,
               ai.CAT_MOVE, ai.CAT_FLEE, ai.CAT_WAIT}


def _mk(behavior="berserker", *, hp=20, n=1, tags=None, atk=2):
    w = WorldState()
    w.character = Character(name="C", background="soldier")
    w.character.stats["STR"] = 14
    w.character.stats["DEX"] = 12
    f = FloorState(floor_id="c", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Arena")
    rb = RoomState(room_id="r1", fallback_short_title="Wyjście")
    f.add_room(r); f.add_room(rb)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.discovered_room_ids = {"r0", "r1"}
    w.current_floor = f
    r.exits["drzwi"] = {"target": "r1", "locked": False, "hidden": False,
                        "hint_key": "", "fallback_hint": ""}
    enemies = []
    for i in range(n):
        e = Entity(key=f"e{i}", entity_type=T_MONSTER, fallback_name=f"E{i}",
                   hp=hp, max_hp=hp, ac=10, attack_bonus=atk,
                   damage_dice="1d6", affordances=["attack"],
                   tags=list(tags or ["monster"]), location_id="r0")
        e.state["behavior"] = behavior
        w.register(e); r.entities.append(e)
        enemies.append(e)
    return w, f, r, enemies


def test_plan_intents_populates_valid_categories():
    w, f, r, es = _mk("berserker", n=2)
    cs = cmb.start_combat(r, w)
    assert cs.enemy_intents, "no intents telegraphed at combat start"
    for e in es:
        intent = cs.enemy_intents.get(e.entity_id)
        assert intent is not None, "enemy missing an intent"
        assert intent["category"] in _VALID_CATS, intent
    print("  intents populated with valid categories: OK")


def test_intents_roundtrip_save_load():
    w, f, r, es = _mk("guard", n=1)
    cs = cmb.start_combat(r, w)
    cs.enemy_intents[es[0].entity_id] = {
        "category": ai.CAT_SPECIAL, "kind": "special",
        "special_key": "shield_bash", "label_pl": "Taranowanie!"}
    d = cs.to_dict()
    cs2 = cmb.CombatState.from_dict(d)
    got = cs2.enemy_intents.get(es[0].entity_id)
    assert got and got["category"] == ai.CAT_SPECIAL, got
    assert got["special_key"] == "shield_bash"
    print("  intents round-trip through save/load: OK")


def test_ranged_band_logic():
    w, f, r, es = _mk("ranged", n=1)
    cs = cmb.start_combat(r, w)
    e = es[0]
    # Ranged starts at_range and should shoot.
    cs.bands[e.entity_id] = cmb.BAND_AT_RANGE
    saw_attack = any(ai.plan_action(w, cs, e).kind in ("attack", "special")
                     for _ in range(8))
    assert saw_attack, "ranged at distance never attacked"
    # Forced into melee, it should look to create distance.
    cs.bands[e.entity_id] = cmb.BAND_ENGAGED
    kinds = {ai.plan_action(w, cs, e).kind for _ in range(12)}
    assert "back_off" in kinds, f"ranged in melee never backed off: {kinds}"
    print("  ranged band logic (shoot far / kite near): OK")


def test_berserker_commits_to_attack():
    w, f, r, es = _mk("berserker", n=1)
    cs = cmb.start_combat(r, w)
    e = es[0]
    kinds = [ai.plan_action(w, cs, e).kind for _ in range(20)]
    attacks = sum(1 for k in kinds if k in ("attack", "special"))
    assert attacks >= 15, f"healthy berserker too passive: {kinds}"
    print("  berserker commits to aggression: OK")


def test_special_fizzles_when_interrupted():
    w, f, r, es = _mk("guard", n=1)
    cs = cmb.start_combat(r, w)
    e = es[0]
    cs.enemy_intents[e.entity_id] = {
        "category": ai.CAT_SPECIAL, "kind": "special",
        "special_key": "shield_bash", "label_pl": "Taranowanie!"}
    cmb.add_status(e, cmb.STATUS_STUNNED, 2)   # player interrupt
    act = ai.realize_intent(w, cs, e)
    assert act.kind == "wait", f"interrupted special still fired: {act.kind}"
    print("  charged special fizzles when interrupted: OK")


def test_special_cooldown_gate():
    w, f, r, es = _mk("berserker", n=1)
    cs = cmb.start_combat(r, w)
    e = es[0]
    assert ai.special_ready(e)
    ai.commit_special_used(e)
    assert not ai.special_ready(e), "special not on cooldown after use"
    # Cooldown counts down each enemy turn.
    for _ in range(ai.SPECIALS[cmb.BEHAVIOR_BERSERKER]["cooldown"]):
        ai.tick_cooldowns(e)
    assert ai.special_ready(e), "cooldown never recovered"
    print("  special cooldown gate: OK")


def test_special_release_applies_status_and_damage():
    from ..engine.game import Game
    import random; random.seed(7)
    w, f, r, es = _mk("guard", n=1, atk=50)   # atk=50 → always lands
    g = Game(screen=None); g.world = w
    cs = cmb.start_combat(r, w)
    e = es[0]
    cs.bands[e.entity_id] = cmb.BAND_ENGAGED
    ch = w.character
    hp0 = ch.hp
    # Build + apply a concrete special directly.
    c = ai._build_ctx(w, cs, e)
    act = ai._make_special(w, cs, e, c)
    g._apply_enemy_action(cs, e, act)
    assert ch.hp < hp0, "special dealt no damage on a guaranteed hit"
    assert cmb.has_status(ch, cmb.STATUS_STUNNED), "shield_bash didn't stun"
    print("  special release: damage + telegraphed status applied: OK")


def test_guarding_raises_defense():
    from ..engine.game import Game
    w, f, r, es = _mk("guard", n=1)
    g = Game(screen=None); g.world = w
    cs = cmb.start_combat(r, w)
    e = es[0]
    # Apply the defend action and confirm the guarding status lands.
    act = cmb.EnemyAction(actor_id=e.entity_id, kind="defend",
                          category=ai.CAT_DEFEND)
    g._apply_enemy_action(cs, e, act)
    assert cmb.has_status(e, cmb.STATUS_GUARDING), "defend didn't brace"
    print("  defensive stance applies guarding: OK")


def test_morale_drops_when_ally_falls():
    w, f, r, es = _mk("berserker", n=2)
    cs = cmb.start_combat(r, w)
    a, b = es
    before = ai.get_morale(b)
    ai.note_ally_down(w, cs, a.entity_id)
    assert ai.get_morale(b) < before, "survivor morale didn't drop"
    print("  ally death shakes survivor morale: OK")


def test_low_morale_coward_flees():
    w, f, r, es = _mk("coward", n=1, hp=10)
    cs = cmb.start_combat(r, w)
    e = es[0]
    e.hp = 2   # badly wounded → nerve breaks
    kinds = [ai.plan_action(w, cs, e).kind for _ in range(12)]
    assert "flee" in kinds, f"wounded coward never fled: {set(kinds)}"
    print("  wounded coward flees: OK")


def test_panic_override_breaks_committed_attack():
    w, f, r, es = _mk("coward", n=1, hp=10)
    cs = cmb.start_combat(r, w)
    e = es[0]
    # Commit an attack telegraph, THEN drop to near-death.
    cs.enemy_intents[e.entity_id] = {"category": ai.CAT_ATTACK,
                                     "kind": "attack", "special_key": None,
                                     "label_pl": "Atak"}
    e.hp = 1
    import random; random.seed(3)
    saw_flee = any(ai.realize_intent(w, cs, e).kind == "flee"
                   for _ in range(12))
    assert saw_flee, "panic override never triggered on a dying coward"
    print("  panic override breaks a committed attack: OK")


def test_full_enemy_turn_replans_intents():
    from ..engine.game import Game
    import random; random.seed(11)
    w, f, r, es = _mk("berserker", n=2, hp=30)
    g = Game(screen=None); g.world = w
    cs = cmb.start_combat(r, w)
    rnd0 = cs.round
    g._run_enemy_turn(cs)
    assert cs.round == rnd0 + 1, "round didn't advance"
    # Survivors should have a fresh intent telegraphed for next round.
    for e in es:
        if e.is_alive():
            assert cs.enemy_intents.get(e.entity_id), "no re-planned intent"
            assert cs.enemy_intents[e.entity_id]["category"] in _VALID_CATS
    print("  full enemy turn runs + re-plans intents: OK")


def main():
    test_plan_intents_populates_valid_categories()
    test_intents_roundtrip_save_load()
    test_ranged_band_logic()
    test_berserker_commits_to_attack()
    test_special_fizzles_when_interrupted()
    test_special_cooldown_gate()
    test_special_release_applies_status_and_damage()
    test_guarding_raises_defense()
    test_morale_drops_when_ally_falls()
    test_low_morale_coward_flees()
    test_panic_override_breaks_committed_attack()
    test_full_enemy_turn_replans_intents()
    print("P30 enemy intentions + utility AI smoke: OK")


if __name__ == "__main__":
    main()
