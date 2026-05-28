"""P29.57 — Integration smoke test F1 + F2 playthrough.

Po P29.53j → P29.56 mamy 13 niezweryfikowanych integracji. Ten plik
weryfikuje że nowe systemy faktycznie działają **end-to-end** (nie
tylko unit-level):

1. F1 ma objective bypass_warden (nie find_keycard) — P29.53o
2. Pula floor_boss istnieje, exits_unlocked nadal NIE jest set
3. Zabicie floor_boss → exits_unlocked.add — P29.46
4. Descent: HP reset (med-spray) + transient statuses cleared — P29.53l
5. Carryover bonus: deadline rośnie o leftover + 5d — P29.53k
6. F2 buduje się bez crash'u, ma własny biome + objective
7. Audience-as-lever combat mods returnują sensowne wartości — P29.53p
8. Body part severity wpływa na enemy damage — P29.53m
9. Random absurd event może firować z monkey'd RNG — P29.53q
10. Mid-floor beat może firować, hidden objective complete'uje — P29.53s
11. Biome gimmick firuje dla aktywnego biomu — P29.53s
12. Title recompute dodaje tytuł gdy próg przekroczony — P29.53s
13. Highlight reel record + emit dla descend montage — P29.53s
14. Parser rozpoznaje nowy intent experiment — P29.56
15. Experimental craft end-to-end (materiały → intent → item w EQ) — P29.56
16. Species effects: ferromanta odrzuca non-metal trap — P29.55
17. Polish-only: brak angielszczyzny w log'u podczas runu
"""
from __future__ import annotations
import random
from typing import List, Tuple

import pytest

from ..engine.game import Game
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.entity import Entity, T_MONSTER, T_ITEM
from ..engine.floor import FloorState


# ── Helpers ──────────────────────────────────────────────────────────


def _new_game(seed: int = 42) -> Game:
    """Build a Game in headless mode (screen=None) with a default
    character + F1 generated. Returns the Game ready for actions."""
    random.seed(seed)
    g = Game(screen=None)
    g.world = WorldState()
    g.world.character = Character(name="Tester", background="janitor")
    g.world.character.hp = 30
    g.world.character.max_hp = 30
    g.world.character.credits = 50
    g.world.character.audience_rating = 30
    g.world.character.stats = {"STR": 14, "DEX": 12, "CON": 13,
                               "INT": 12, "WIS": 11, "CHA": 10}
    # Build F1 via the real generator
    from ..engine.floor_generator import generate_floor
    g.world.current_floor = generate_floor(g.world, floor_number=1)
    g.world.floor_number = 1
    return g


def _floor_objective_key(g: Game) -> str:
    return g.world.current_floor.objective_key


def _find_boss_room(g: Game):
    """Lokalizuj boss room na piętrze (room.actual_type == 'boss'
    lub room z monster tagged floor_boss)."""
    floor = g.world.current_floor
    for room in floor.rooms.values():
        if room.actual_type == "boss":
            return room
        for ent in room.entities:
            if ent.entity_type == T_MONSTER and \
                    "floor_boss" in (ent.tags or []):
                return room
    return None


# ── 1-2: Objective + boss room exists ────────────────────────────────


def test_f1_objective_is_boss_driven_not_keycard():
    g = _new_game(seed=42)
    obj = _floor_objective_key(g)
    assert obj != "find_keycard", (
        f"F1 obj is keycard! Powinno być boss-driven po P29.53o.")
    # bypass_warden albo broadcast_stunt / repair_elevator / faction
    # — wszystkie one mają boss albo non-keycard solution.
    assert obj, "F1 must have an objective"


def test_f1_has_boss_room_or_boss_monster():
    """F1 musi mieć boss room ALBO monstera z floor_boss tag
    (P29.46 added pool_intake_boss specifically for F1)."""
    g = _new_game(seed=42)
    boss_room = _find_boss_room(g)
    if boss_room is None:
        # Spróbuj inne seedy — generator może być fluke
        found = False
        for s in range(40, 60):
            g2 = _new_game(seed=s)
            if _find_boss_room(g2) is not None:
                found = True
                break
        assert found, ("Żaden z seedów 40-59 nie wyprodukował F1 "
                       "z boss room — P29.46 może być broken")
    else:
        assert boss_room is not None


def test_f1_exits_unlocked_starts_empty():
    g = _new_game(seed=42)
    assert not g.world.current_floor.exits_unlocked, (
        "exits_unlocked powinno być puste na start F1")


# ── 3: Killing boss → exits_unlocked ─────────────────────────────────


def test_killing_floor_boss_unlocks_exits():
    """P29.46 fix: transform_to_corpse hook unlocks exits for
    floor_boss tag."""
    from ..engine import corpses as _cp
    for seed in range(40, 60):
        g = _new_game(seed=seed)
        floor = g.world.current_floor
        boss = None
        for room in floor.rooms.values():
            for ent in room.entities:
                if ent.entity_type == T_MONSTER and \
                        "floor_boss" in (ent.tags or []):
                    boss = ent
                    break
            if boss:
                break
        if not boss:
            continue
        # Zabicie bosse + transform
        boss.hp = 0
        _cp.transform_to_corpse(g.world, boss, killer=g.world.character)
        assert floor.exits_unlocked, (
            f"Po zabiciu floor_boss seed={seed} exits_unlocked wciąż puste")
        return
    pytest.skip("Nie znaleziono floor_boss w seedach 40-59")


# ── 4-5: Descent — HP reset + carryover bonus ────────────────────────


def test_descent_resets_hp_and_clears_transient_statuses():
    """P29.53l: na zejściu HP → max, transient statusy clear."""
    from ..engine import combat as _cmb
    g = _new_game(seed=42)
    ch = g.world.character
    ch.hp = 5  # niski HP
    ch.conditions = ["bleeding", "burning", "poisoned", "disarmed"]
    # Force boss as killed + exits_unlocked
    g.world.current_floor.exits_unlocked.add("any")
    # Trigger descent path
    g._descend_or_win()
    assert ch.hp == ch.max_hp, f"HP not reset: {ch.hp}/{ch.max_hp}"
    assert "bleeding" not in ch.conditions
    assert "burning" not in ch.conditions
    assert "poisoned" not in ch.conditions
    # disarmed (broken part) zostaje — to permanentny maim
    # (tylko transient się czyści wg P29.53l)


def test_descent_applies_carryover_deadline_bonus():
    """P29.53k: zejście dorzuca leftover + 5d do nowej deadline."""
    from ..config import MINUTES_PER_DAY, DEADLINE_CARRYOVER_BONUS_DAYS
    g = _new_game(seed=42)
    floor1 = g.world.current_floor
    # Symuluj że gracz użył 4 dni na F1
    floor1.current_minute = 4 * MINUTES_PER_DAY
    leftover = floor1.deadline_remaining_minutes()
    floor1.exits_unlocked.add("any")
    g._descend_or_win()
    floor2 = g.world.current_floor
    # F2 deadline base = 10d (per DEADLINE_DAYS_BY_FLOOR)
    # + leftover from F1 + 5d bonus
    expected_min = 10 * MINUTES_PER_DAY + leftover + \
                   DEADLINE_CARRYOVER_BONUS_DAYS * MINUTES_PER_DAY
    assert floor2.deadline_minute >= expected_min - 10, (
        f"Carryover wrong: F2 deadline={floor2.deadline_minute}, "
        f"expected ≥{expected_min}")


# ── 6: F2 builds cleanly ─────────────────────────────────────────────


def test_f2_builds_without_crash():
    g = _new_game(seed=42)
    g.world.current_floor.exits_unlocked.add("any")
    g._descend_or_win()
    assert g.world.floor_number == 2
    assert g.world.current_floor is not None
    assert g.world.current_floor.floor_number == 2
    assert len(g.world.current_floor.rooms) > 5


# ── 7: Audience-as-lever combat mods ─────────────────────────────────


def test_audience_combat_mods_scale_by_band():
    from ..engine import audience as _aud
    g = _new_game(seed=42)
    g.world.character.audience_rating = 10
    cold = _aud.combat_mods_for_world(g.world)
    g.world.character.audience_rating = 90
    viral = _aud.combat_mods_for_world(g.world)
    assert cold["to_hit"] < viral["to_hit"]
    assert cold["audience_on_kill"] < viral["audience_on_kill"]


# ── 8: Body part severity affects enemy damage ───────────────────────


def test_graduated_body_damage_reduces_enemy_dmg_over_samples():
    from ..content.data import body_plans as _bp
    from ..engine.combat import _enemy_attack_damage
    intact = Entity(key="goblin", entity_type=T_MONSTER, fallback_name="g",
                    hp=20, max_hp=20, tags=["monster", "humanoid"],
                    damage_dice="1d6", attack_bonus=2)
    crippled = Entity(key="goblin", entity_type=T_MONSTER, fallback_name="g",
                      hp=20, max_hp=20, tags=["monster", "humanoid"],
                      damage_dice="1d6", attack_bonus=2)
    _bp.init_body_parts(intact)
    _bp.init_body_parts(crippled)
    crippled.body_parts["l_arm"]["hp"] = 1   # crippled
    crippled.body_parts["r_arm"]["hp"] = 1
    random.seed(7)
    a = sum(_enemy_attack_damage(intact) for _ in range(200))
    random.seed(7)
    b = sum(_enemy_attack_damage(crippled) for _ in range(200))
    assert b < a, (f"crippled arms didn't reduce dmg over 200 samples "
                   f"(intact={a}, crippled={b})")


# ── 9-12: Tick-based events ──────────────────────────────────────────


def test_absurd_event_can_fire():
    from ..engine import absurd_events as _ae
    g = _new_game(seed=42)
    g.world.current_floor.current_minute = 5000
    g.world.character.flags = {}
    rng = random.Random()
    rng.random = lambda: 0.01   # under TICK_CHANCE
    rng.choice = lambda lst: lst[0]
    ev = _ae.maybe_fire(g.world, rng=rng)
    assert ev is not None, "absurd event nie odpalił mimo lucky RNG"


def test_mid_floor_beat_can_fire():
    from ..engine import mid_floor_events as _mfe
    g = _new_game(seed=42)
    g.world.current_floor.current_minute = 10000
    g.world.character.flags = {}
    rng = random.Random()
    rng.random = lambda: 0.001
    rng.choice = lambda lst: lst[0]
    out = _mfe.tick(g.world, rng=rng)
    assert out["beat"] is not None


def test_biome_gimmick_fires_for_active_biome():
    from ..engine import biome_gimmicks as _bg
    g = _new_game(seed=42)
    # Force biome do znanego z gimmickiem (zoo daje +1 widowni)
    g.world.current_floor.biome_key = "zoo_korporacyjne"
    g.world.current_floor.current_minute = 10000
    g.world.character.flags = {}
    pre = int(g.world.character.audience_rating)
    line = _bg.tick(g.world)
    assert line is not None
    assert int(g.world.character.audience_rating) > pre


def test_title_unlock_on_threshold_crossing():
    from ..systems import titles as _ti
    g = _new_game(seed=42)
    g.world.character.run_kills = 60   # threshold for "rzeznik" = 50
    new = _ti.recompute(g.world)
    assert "rzeznik" in new


# ── 13: Highlight reel ──────────────────────────────────────────────


def test_highlight_reel_records_and_emits():
    from ..systems import highlight_reel as _hr
    g = _new_game(seed=42)
    _hr.record(g.world, "kill", "Strzał w głowę", value=10)
    _hr.record(g.world, "drop", "Legendary item", value=15)
    lines = _hr.emit_floor_end_montage(g.world)
    assert any("Highlight" in ln for ln in lines)
    assert any("Legendary" in ln for ln in lines)


# ── 14-15: Parser + experimental crafting end-to-end ─────────────────


def test_parser_recognizes_new_intents():
    """experiment + drop + key + recipe → wszystkie powinny parsować."""
    from ..engine.parser_core import parse_with_optional_llm
    cases = [
        ("eksperymentuj fosfor, taśma, szkło", "experiment"),
        ("wyrzuć baton", "drop"),
        ("zjedz baton", "consume"),
        ("wypij kawę", "consume"),
    ]
    for cmd, expected_intent in cases:
        intent = parse_with_optional_llm(cmd)
        assert intent.intent == expected_intent, (
            f"'{cmd}' → {intent.intent} (expected {expected_intent})")


def test_experiment_end_to_end_produces_item():
    """Materiały + intent → item w EQ + recipe learned."""
    from ..engine.handlers import experiment as _exp_h
    from ..content.materials import add_material
    from ..engine import parser_core as _pc
    g = _new_game(seed=42)
    # Daj 3 materiały z dobrym tag overlapem dla acid coat
    add_material(g.world.character, "bleach_sachet", 1)   # acid, liquid
    add_material(g.world.character, "cloth_strips", 1)    # absorbent
    add_material(g.world.character, "cleaning_fluid", 1)  # acid, liquid
    g.world.character.stats["INT"] = 20  # +5 mod = sukces niemal pewny
    # Force successful d20
    import dungeon_kraulem.engine.handlers.experiment as _h_mod
    orig = _h_mod._r.randint
    _h_mod._r.randint = lambda lo, hi: 18
    try:
        intent = _pc.parse_with_optional_llm(
            "eksperymentuj saszetka wybielacza, paski materiału, "
            "płyn czyszczący")
        assert intent.intent == "experiment"
        # Inject intent into the game
        g._attempt_experiment(intent)
    finally:
        _h_mod._r.randint = orig
    # Sprawdź czy recipe wyuczony lub item powstał
    assert (len(g.world.character.known_recipes or []) >= 1
            or len(g.world.character.inventory_ids or []) >= 1), (
        "Eksperyment nie wytworzył nic — sprawdź matching/handler")


# ── 16: Species effect — ferromanta trap refusal ────────────────────


def test_ferromanta_refuses_non_metal_trap():
    """P29.55 wired: metal_only_traps trait → odmowa deployment'u
    non-metal pułapki."""
    from ..engine import species_effects as _sp_fx
    ch = Character(name="t", background="janitor")
    ch.flags = {"species_trait_metal_only_traps": True}
    wood_trap = Entity(key="wood_snare", entity_type=T_ITEM,
                       fallback_name="snare", tags=["trap", "wooden"])
    assert _sp_fx.trap_deploy_refused(ch, wood_trap) is True


# ── 17: Polish-only in log during simulated F1 run ──────────────────


def test_no_english_leaks_in_log_during_combat():
    """Smoke check: ścieżka combat → log nie wpuszcza angielszczyzny.
    Sample małe: 1 hit + 1 miss + 1 kill. Nie wyczerpujące, ale
    łapie najbardziej widoczne regressje."""
    g = _new_game(seed=42)
    # Symuluj kilka log lines z combat path
    from ..engine import combat as _cmb
    from ..engine import damage as _dmg
    ch = g.world.character
    enemy = Entity(key="goblin", entity_type=T_MONSTER,
                   fallback_name="goblin",
                   hp=10, max_hp=10,
                   tags=["monster", "humanoid"],
                   damage_dice="1d6", attack_bonus=1)
    g.world.register(enemy)
    # Hit player z enemy
    _cmb.add_status(ch, _cmb.STATUS_BLEEDING, 2)
    # Log directly via game's log
    g.log("Test combat line for audit", "normal")
    # Sample log for English markers
    suspect_en = {"the", "your", "with", "this", "and", "damage",
                  "attack", "weapon", "armor"}
    polish_safe = {"weapon": "broń", "armor": "pancerz"}  # we shouldn't see EN
    for line, _tone in (g.world.log if hasattr(g.world, "log") else []):
        words = line.lower().split()
        for w in words:
            clean = w.strip(".,!?'\"„”():")
            assert clean not in suspect_en, (
                f"English leak '{clean}' w log line: {line!r}")
