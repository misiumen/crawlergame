"""E2E P29.76 — system XP + poziomów (Etap A: model + silnik + save/load).

DCC-faithful: zabójstwa dają XP wg tieru, awans daje +max HP + punkt
atrybutu do rozdania + loot box (system Skrzynek). Picker rozdawania
punktów + UI to Etap B; tu pilnujemy silnika i persystencji.
"""
from __future__ import annotations

from ...engine.world import WorldState
from ...engine.character import Character
from ...engine import leveling as L


def _world(background="security_guard"):
    w = WorldState()
    w.character = Character(name="Tester", background=background)
    return w


# ── Krzywa XP ───────────────────────────────────────────────────────


def test_xp_curve_thresholds():
    assert L.xp_to_reach(1) == 0
    assert L.xp_to_reach(2) == 100
    assert L.xp_to_reach(3) == 300
    assert L.level_for_xp(0) == 1
    assert L.level_for_xp(99) == 1
    assert L.level_for_xp(100) == 2
    assert L.level_for_xp(350) == 3


# ── XP za zabójstwo wg tieru ────────────────────────────────────────


def test_xp_for_kill_tiers_and_floor_scaling():
    normal = L.xp_for_kill_tags(["monster"], 1)
    miniboss = L.xp_for_kill_tags(["monster", "miniboss"], 1)
    boss = L.xp_for_kill_tags(["monster", "floor_boss"], 1)
    assert miniboss > normal and boss > miniboss        # tiery rosną
    assert boss == normal * 10                           # boss ×10
    assert L.xp_for_kill_tags(["monster"], 5) > normal   # głębsze piętro = więcej


# ── award_xp + awans ────────────────────────────────────────────────


def test_award_xp_single_level():
    w = _world()
    gained = L.award_xp(w, 120)          # >100 → L2
    assert gained == [2]
    assert w.character.level == 2
    assert w.character.unspent_stat_points == 1


def test_award_xp_multi_level_at_once():
    w = _world()
    hp0 = w.character.max_hp
    gained = L.award_xp(w, 350)          # przez L2 i L3 naraz
    assert gained == [2, 3]
    assert w.character.level == 3
    assert w.character.unspent_stat_points == 2   # punkt za każdy poziom
    assert w.character.max_hp > hp0               # +HP per poziom


def test_level_up_grants_loot_box():
    w = _world()
    L.award_xp(w, 120)                    # L2
    boxes = [w.get(i) for i in w.character.inventory_ids]
    boxes = [b for b in boxes if b and "box" in (b.tags or [])]
    assert len(boxes) == 1
    assert boxes[0].state.get("box_source") == "level_up"


def test_no_xp_no_level():
    w = _world()
    assert L.award_xp(w, 0) == []
    assert w.character.level == 1


# ── Persystencja ────────────────────────────────────────────────────


def test_level_xp_points_round_trip():
    w = _world()
    L.award_xp(w, 350)
    d = w.character.to_dict()
    c2 = Character.from_dict(d)
    assert c2.level == 3
    assert c2.xp == 350
    assert c2.unspent_stat_points == 2


def test_old_save_defaults_to_level_1():
    # Save sprzed P29.76 (brak pól level/xp) → L1, 0 XP, 0 punktów.
    c = Character.from_dict({"name": "Stary", "background": "janitor"})
    assert c.level == 1 and c.xp == 0 and c.unspent_stat_points == 0


# ── Loot box za awans + reveal w stylu VS (hybryda) ─────────────────


def test_levelup_grants_openable_box_with_vs_reveal():
    import types
    from .headless import HeadlessSession
    from ...engine.handlers import boxes as B
    s = HeadlessSession(background="security_guard")
    L.award_xp(s.world, 120)              # L2 → skrzynka level_up w EQ
    box = next(s.world.get(i) for i in s.character.inventory_ids
               if s.world.get(i) and "box" in (s.world.get(i).tags or []))
    assert (box.state or {}).get("box_source") == "level_up"
    # Otwarcie ustawia stan reveala (overlay VS), nie tylko log.
    B.attempt_open_box(s.game, types.SimpleNamespace(
        intent="open_box", targets=[box.fallback_name], raw=box.fallback_name))
    br = s.game._box_reveal
    assert br is not None and br.get("rarity") == "common"
    assert br.get("content_lines")          # ma zawartość do ujawnienia
    # Animacja: po dużym czasie wszystko ujawnione + done.
    for _ in range(25):
        s.game.update(300)
    assert br["done"] and br["shown"] == len(br["content_lines"])
