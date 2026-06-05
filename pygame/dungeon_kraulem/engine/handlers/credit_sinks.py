"""P29.27 — Credit-sink handlers extracted from engine/game.py.

Originally inline in Game._attempt_train_stat / _attempt_bribe_sponsor /
_attempt_call_pod / _attempt_upgrade_loadout (added P29.19). Moved
out so game.py shrinks toward maintainable territory and so each
handler is testable as a plain function.

Public API — each function takes (game, intent) where `game` is a
Game instance carrying world + log helpers. Returns None; all
side effects flow through game.log / game.world / etc.

Cost constants are also re-exported here so tuning passes don't
need to edit game.py.
"""
from __future__ import annotations
from typing import Any

from ...config import LOG_NORMAL, LOG_WARN, LOG_SUCCESS, LOG_DANGER, LOG_SYSTEM
from ...ui.lang import t


# Cost constants — single source of truth for credit-sink balance.
TRAIN_COST    = 80
RESPEC_COST   = 40   # P29.76 — Wiercimajster przekłada Twoje punkty, nie sprzedaje surowych statów
BRIBE_COST    = 20
CALL_POD_COST = 50
UPGRADE_COST  = 100


# Polish + ASCII stat-name aliases for the trainer command. The
# parser already folds diacritics + lowercases the input.
_STAT_ALIAS = {
    "str": "STR", "siła": "STR", "sila": "STR", "siłę": "STR",
    "dex": "DEX", "zręczność": "DEX", "zrecznosc": "DEX",
    "con": "CON", "kondycja": "CON",
    "int": "INT", "inteligencja": "INT",
    "wis": "WIS", "mądrość": "WIS", "madrosc": "WIS",
    "cha": "CHA", "charyzma": "CHA",
}


def attempt_train_stat(game, intent) -> None:
    """P29.76 — Wiercimajster = RESPEC, nie sprzedaż surowych statów.
    `przebudowa <stat>` (alias: trening) — za RESPEC_COST kr zdejmuje 1 punkt
    z danego statu (nie poniżej bazy z profilu pochodzenia) i zwraca go do puli
    nierozdanych punktów (`unspent_stat_points`) do ponownego rozdania w
    pickerze awansu. Powtarzalne (brak flagi one-time)."""
    if not intent.targets:
        game.log(t("feedback_respec_syntax",
                   fallback="Składnia: przebudowa <stat> "
                            "(STR/DEX/CON/INT/WIS/CHA). Punkt wraca do puli."),
                 LOG_WARN)
        return
    ch = game.world.character
    raw = (intent.targets[0] or "").strip().lower()
    stat = _STAT_ALIAS.get(raw)
    if stat is None:
        game.log(t("feedback_respec_bad_stat",
                   fallback=f"Nie wiem, jak przebudować „{raw}”. "
                            f"STR / DEX / CON / INT / WIS / CHA."),
                 LOG_WARN)
        return
    # Baza z profilu pochodzenia — poniżej startu nie zejdziemy.
    try:
        from ..character import STAT_PROFILES
        base = int(STAT_PROFILES.get(ch.background, {}).get(stat, 10))
    except Exception:
        base = 10
    cur = int(ch.stats.get(stat, 10))
    if cur <= base:
        game.log(t("feedback_respec_at_base",
                   fallback=f"Wiercimajster: „{stat} już na bazie "
                            f"({base}). Nie ma czego wyjmować.”"), LOG_WARN)
        return
    if ch.credits < RESPEC_COST:
        game.log(t("feedback_respec_no_credits",
                   fallback=f"Wiercimajster: {RESPEC_COST} kr za przebudowę. "
                            f"Masz {ch.credits}."), LOG_WARN)
        return
    ch.credits -= RESPEC_COST
    ch.stats[stat] = cur - 1
    ch.unspent_stat_points = int(getattr(ch, "unspent_stat_points", 0) or 0) + 1
    game.log(t("feedback_respec_ok",
               fallback=f"Wiercimajster wyłuskuje punkt z {stat} "
                        f"(teraz {ch.stats[stat]}). +1 do rozdania "
                        f"(masz {ch.unspent_stat_points}). -{RESPEC_COST} kr. "
                        f"Rozdaj komendą „rozdaj punkty”."),
             LOG_SUCCESS)
    try:
        from .. import time_system as _ts
        _ts.advance(game.world, 30)
    except Exception:
        pass


def attempt_bribe_sponsor(game, intent) -> None:
    """`łapówka <sponsor>` — pay 20 kr to nudge a sponsor +2.
    No per-use gating, just costs credits. Matches sponsor by
    loose name fragment (key or PL display name)."""
    if not intent.targets:
        game.log(t("feedback_bribe_syntax",
                   fallback="Składnia: łapówka <nazwa sponsora>."),
                 LOG_WARN)
        return
    ch = game.world.character
    from ..affordances import fold as _fold
    needle = _fold((intent.targets[0] or "").strip())
    try:
        from .. import sponsors as _sp
        keys = _sp.all_sponsor_keys()
        picked = None
        for k in keys:
            if needle in _fold(k):
                picked = k; break
            sdata = _sp.get_sponsor(k)
            pl = _fold(_sp._name_pl(sdata))
            if needle in pl:
                picked = k; break
        if picked is None:
            game.log(t("feedback_bribe_unknown",
                       fallback=f"Nie znam sponsora pasującego "
                                f"do „{intent.targets[0]}”."), LOG_WARN)
            return
        if ch.credits < BRIBE_COST:
            game.log(t("feedback_bribe_no_credits",
                       fallback=f"Łapówka: {BRIBE_COST} kr. "
                                f"Masz {ch.credits}."), LOG_WARN)
            return
        ch.credits -= BRIBE_COST
        _sp.adjust_attention(game.world, picked, 2)
        sdata = _sp.get_sponsor(picked)
        game.log(t("feedback_bribe_ok",
                   fallback=f"Łapówka dla {_sp._name_pl(sdata)} "
                            f"przyjęta. +2 uwagi. -{BRIBE_COST} kr."),
                 LOG_SUCCESS)
    except Exception as exc:
        game.log(f"(Łapówka nie poszła: {exc})", LOG_WARN)


def attempt_call_pod(game, intent) -> None:
    """`zamów pakiet [<sponsor>]` — pay 50 kr to materialize a
    sponsor drop-pod in the current room. If no sponsor specified,
    pick the current top-attention one."""
    ch = game.world.character
    if ch.credits < CALL_POD_COST:
        game.log(t("feedback_call_pod_no_credits",
                   fallback=f"Pakiet na żądanie: {CALL_POD_COST} kr. "
                            f"Masz {ch.credits}."), LOG_WARN)
        return
    room = (game.world.current_floor.current_room()
            if game.world.current_floor else None)
    if room is None:
        game.log(t("feedback_call_pod_no_room",
                   fallback="Nie ma pokoju, do którego mógłby "
                            "spaść pakiet."), LOG_WARN)
        return
    from .. import sponsors as _sp
    sponsor_key = ""
    if intent.targets:
        from ..affordances import fold as _fold
        needle = _fold((intent.targets[0] or "").strip())
        for k in _sp.all_sponsor_keys():
            if needle in _fold(k):
                sponsor_key = k; break
            sdata = _sp.get_sponsor(k)
            if needle in _fold(_sp._name_pl(sdata)):
                sponsor_key = k; break
    if not sponsor_key:
        try:
            sponsor_key = _sp.current_floor_sponsor_key(game.world) or \
                          "novachem_biotech"
        except Exception:
            sponsor_key = "novachem_biotech"
    sdata = _sp.get_sponsor(sponsor_key)
    gifts = list(sdata.get("gift_pool") or []) or ["stimpak"]
    import random as _r
    item_key = _r.choice(gifts)
    ch.credits -= CALL_POD_COST
    mode = _sp.deliver_sponsor_gift(game.world, sponsor_key, item_key)
    if mode != "pod":
        game.log(t("feedback_call_pod_fallback",
                   fallback="Pakiet zarejestrowano w safehouse "
                            "(producent nie zdążył przed reklamą)."),
                 LOG_WARN)
    game.log(t("feedback_call_pod_billed",
               fallback=f"Rachunek za pakiet: -{CALL_POD_COST} kr "
                        f"(sponsor: {sponsor_key})."), LOG_SYSTEM)


def attempt_upgrade_loadout(game, intent) -> None:
    """`wzmocnij hp|ac` — pay 100 kr for a permanent +5 max HP
    or +1 base AC. Each branch is one-time per character."""
    if not intent.targets:
        game.log(t("feedback_upgrade_syntax",
                   fallback="Składnia: wzmocnij hp / wzmocnij ac."),
                 LOG_WARN)
        return
    which = intent.targets[0]
    ch = game.world.character
    flag = f"upgrade_{which}"
    if (ch.flags or {}).get(flag):
        game.log(t("feedback_upgrade_already_done",
                   fallback=f"Wzmocnienie „{which}” już wzięte. "
                            f"Reszta to mit."), LOG_WARN)
        return
    if ch.credits < UPGRADE_COST:
        game.log(t("feedback_upgrade_no_credits",
                   fallback=f"Wzmocnienie kosztuje "
                            f"{UPGRADE_COST} kr. Masz {ch.credits}."),
                 LOG_WARN)
        return
    ch.credits -= UPGRADE_COST
    if ch.flags is None: ch.flags = {}
    ch.flags[flag] = True
    if which == "hp":
        ch.max_hp += 5
        ch.hp = min(ch.hp + 5, ch.max_hp)
        game.log(t("feedback_upgrade_hp_ok",
                   fallback=f"Wzmocnienie: max HP +5 "
                            f"(teraz {ch.max_hp}). -{UPGRADE_COST} kr."),
                 LOG_SUCCESS)
    else:
        ch.base_ac += 1
        game.log(t("feedback_upgrade_ac_ok",
                   fallback=f"Wzmocnienie: base AC +1 "
                            f"(teraz {ch.base_ac}). -{UPGRADE_COST} kr."),
                 LOG_SUCCESS)
    try:
        from .. import time_system as _ts
        _ts.advance(game.world, 20)
    except Exception:
        pass
