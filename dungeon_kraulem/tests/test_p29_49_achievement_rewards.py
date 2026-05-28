"""Prompt 29.49 — Achievementy: bonus widowni + nowy katalog + gating meta.

Pytanie gracza: „co tak naprawde achievementy dają graczowi? to tylko
tytuł czy niosą nagrody lub efekty?"

Stan przed: 33 osiągnięcia, każde tylko logowe + 3 z 33 gating-em
dla meta-unlocków. Reszta to pure flavor.

Stan po (B + E):
  B. Każdy unlock daje natychmiastowy bonus widowni (+5 normalne,
     +10 hidden). Gracz czuje wynagrodzenie na bieżący run.
  E. 15 nowych osiągnięć za niestandardowe podejście (biomy, rarity,
     styl gry), 8 z nich gate'm dla meta-perków.

Pokrywa:
  * unlock() bumpuje audience zgodnie z hidden/normal
  * routing przez audience.change_audience respektuje clamp
  * 15 nowych achievementów obecnych w katalogu
  * każdy z 8 nowych meta-unlocków ma poprawny eval_fn
  * audit test (z P29.48) wciąż przechodzi (każdy nowy ma trigger)
"""
from __future__ import annotations

from ..engine import run_history as _rh
from ..systems import achievements as _ach
from ..engine import meta_progression as _mp


def test_unlock_grants_audience_bonus_normal():
    """Normalne (non-hidden) achievement → +5 widowni."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.audience_rating = 20
    # `dno_jeszcze_dalej` to public achievement.
    ok = _ach.unlock(w.character, "dno_jeszcze_dalej", world=w)
    assert ok
    assert w.character.audience_rating == 25, \
        f"non-hidden +5: got {w.character.audience_rating}"
    print("  non-hidden achievement → +5 widowni: OK")


def test_unlock_grants_audience_bonus_hidden():
    """Hidden achievement → +10 widowni (cenniejszy)."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.audience_rating = 20
    # `anty_host_warknal` ma hidden=True.
    ok = _ach.unlock(w.character, "anty_host_warknal", world=w)
    assert ok
    assert w.character.audience_rating == 30, \
        f"hidden +10: got {w.character.audience_rating}"
    print("  hidden achievement → +10 widowni: OK")


def test_unlock_respects_clamp():
    """audience nie przekracza 100 mimo bonusu."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.audience_rating = 98
    _ach.unlock(w.character, "anty_host_warknal", world=w)
    assert w.character.audience_rating == 100, \
        f"clamp 100: got {w.character.audience_rating}"
    print("  clamp 100 respektowany: OK")


def test_unlock_no_double_dip():
    """Drugi raz tego samego klucza nie daje bonusu."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.character.audience_rating = 30
    _ach.unlock(w.character, "dno_jeszcze_dalej", world=w)
    pre = w.character.audience_rating
    _ach.unlock(w.character, "dno_jeszcze_dalej", world=w)
    assert w.character.audience_rating == pre, \
        f"drugi unlock nie powinien dać bonusu"
    print("  re-unlock to no-op (no double-dip): OK")


def test_new_achievements_present_in_catalog():
    """15 nowych z P29.49 są w katalogu."""
    new = [
        "globtroter", "okopowiec", "zoofobia_skonczona", "archiwista",
        "karaoke_killer",
        "widzialem_legende", "cala_paleta", "niezwykly_zbieracz",
        "klepacz_minibossow", "czystka_srodowiska", "taneczny_krok",
        "kompletny_hacker", "bez_zbroi_bez_smutku",
        "nadzwyczajne_oszczednosci", "kazdy_ma_imie",
    ]
    cat = _ach.catalog()
    missing = [k for k in new if k not in cat]
    assert not missing, f"brakuje w katalogu: {missing}"
    print(f"  {len(new)} nowych achievementów w katalogu: OK")


def test_new_meta_unlocks_gated_on_achievements():
    """8 nowych meta-unlocków z P29.49 z eval_fn na achievement-key."""
    expected = [
        "item_apteczka_kompletna", "perk_rzemieslnik_terminala",
        "perk_okopowy_weteran", "perk_handlarz_pakietow",
        "perk_taneczne_nogi", "perk_dzikus_z_arena",
        "perk_skapy_jak_widz", "perk_kolekcjoner",
    ]
    cat = _mp.UNLOCK_CATALOG
    missing = [k for k in expected if k not in cat]
    assert not missing, f"brakuje meta-unlocków: {missing}"
    # Każdy ma niepustą eval_fn.
    for k in expected:
        assert cat[k].eval_fn is not None
    print(f"  {len(expected)} nowych meta-unlocków: OK")


def test_meta_unlock_activates_after_achievement():
    """End-to-end: unlock achievement → record_unlocks_for_run
    odblokowuje gated meta-unlock."""
    _rh.reset()
    from ..engine.world import WorldState
    from ..engine.character import Character
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    _ach.unlock(w.character, "okopowiec", world=w)
    new_keys = _mp.record_unlocks_for_run(w, victory=False)
    assert "perk_okopowy_weteran" in new_keys, \
        f"okopowiec → perk_okopowy_weteran nie odblokowany: {new_keys}"
    print("  okopowiec achievement → perk_okopowy_weteran meta-unlock: OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_unlock_grants_audience_bonus_normal()
        test_unlock_grants_audience_bonus_hidden()
        test_unlock_respects_clamp()
        test_unlock_no_double_dip()
        test_new_achievements_present_in_catalog()
        test_new_meta_unlocks_gated_on_achievements()
        test_meta_unlock_activates_after_achievement()
    finally:
        _rh.reset()
    print("Prompt 29.49 achievement rewards smoke: OK")


if __name__ == "__main__":
    main()
