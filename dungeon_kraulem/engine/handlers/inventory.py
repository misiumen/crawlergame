"""P29.33 — Inventory/crafting handlers extracted from engine/game.py.

Three clean, self-contained handlers from P29.14 / P29.23:
  * attempt_cook(game, intent)              — gotuj/piecz/smaż
  * attempt_read(game, intent)              — czytaj/przeczytaj
  * attempt_apply_enhancement(game, intent) — nałóż <X> na <Y>

Each takes `game` (a Game instance carrying world + log) and `intent`.
Imports are kept local-to-call so the handlers' import overhead lives
where it matters (most game ticks don't invoke them).
"""
from __future__ import annotations

from ...config import LOG_NORMAL, LOG_WARN, LOG_SUCCESS, LOG_DANGER, LOG_SYSTEM
from ...ui.lang import t


# ── Cook ────────────────────────────────────────────────────────────────

def attempt_cook(game, intent) -> None:
    """`gotuj` / `piecz` / `smaż` — convert raw meat to cooked food.

    Needs 1 meat_chunk + 1 wood_fragments. Rolls WIS at TT 8.
    Outcomes:
      critical_success → masterwork cooked_meat
      success / partial → normal cooked_meat
      failure → wasted, "spoiled" line
      critical_failure → -2 HP (your own fire bit you)
    """
    from .. import time_system as _ts
    from ..utils_compat import roll_d20
    from ...content import crafting as _cr

    ch = game.world.character
    pool = ch.materials or {}
    meat_qty = int(pool.get("meat_chunk", 0))
    wood_qty = int(pool.get("wood_fragments", 0))
    if meat_qty < 1:
        game.log(t("feedback_cook_no_meat",
                   fallback="Nie masz mięsa do gotowania. "
                            "Rozbierz coś świeżego, najpierw."), LOG_WARN)
        return
    if wood_qty < 1:
        game.log(t("feedback_cook_no_wood",
                   fallback="Nie masz drewna ani niczego, na czym "
                            "rozpalić ogień."), LOG_WARN)
        return

    raw = roll_d20()
    mod = ch.stat_mod("WIS")
    dc = 8
    total = raw + mod
    if   raw == 20:       level = "critical_success"
    elif raw == 1:        level = "critical_failure"
    elif total >= dc + 5: level = "critical_success"
    elif total >= dc:     level = "success"
    elif total >= dc - 3: level = "partial_success"
    else:                 level = "failure"

    # Consume materials regardless of outcome (you used the supplies).
    ch.materials["meat_chunk"] = meat_qty - 1
    ch.materials["wood_fragments"] = wood_qty - 1

    _ts.advance(game.world, 10)

    if level == "critical_failure":
        game.log(t("feedback_cook_critfail",
                   fallback="Rozpalasz coś, ale ogień gryzie cię "
                            "w rękę. -2 HP. Mięso przepada."),
                 LOG_DANGER)
        ch.take_damage(2)
        game._check_player_dead("cook_critfail", "od własnego ogniska")
        return
    if level == "failure":
        game.log(t("feedback_cook_fail",
                   fallback="Mięso spalone na zewnątrz, surowe w "
                            "środku. Wyrzucasz."), LOG_WARN)
        return

    quality = _cr.quality_for_level(level)
    ent = _cr.make_crafted_entity("cooked_meat", quality=quality)
    game.world.register(ent)
    ch.inventory_ids.append(ent.entity_id)
    qlabel = _cr.quality_label_pl(quality)
    if qlabel:
        game.log(t("feedback_cook_ok_qual",
                   fallback=f"Gotujesz ({qlabel}): {ent.display_name()}.",
                   quality=qlabel, name=ent.display_name()), LOG_SUCCESS)
    else:
        game.log(t("feedback_cook_ok",
                   fallback=f"Gotujesz: {ent.display_name()}.",
                   name=ent.display_name()), LOG_SUCCESS)


# ── Read ────────────────────────────────────────────────────────────────

def attempt_read(game, intent) -> None:
    """`czytaj <X>` — surface lore on a lore-tagged item or env.

    Inventory first, then current room. Matches by display-name
    fragment or tag substring. Reading is free (no time cost)."""
    from ..affordances import fold as _fold

    ch = game.world.character
    room = (game.world.current_floor.current_room()
            if game.world.current_floor else None)
    if not intent.targets:
        game.log(t("feedback_read_syntax",
                   fallback="Co czytać? Spróbuj `czytaj <nazwa>`."),
                 LOG_WARN)
        return
    needle = _fold((intent.targets[0] or "").strip())

    for eid in (ch.inventory_ids or []):
        e = game.world.get(eid)
        if e is None:
            continue
        if needle in _fold(e.display_name()) or \
           any(needle in _fold(tg or "") for tg in (e.tags or [])):
            if "lore" in (e.tags or []) or \
               "readable" in (e.tags or []) or \
               "paper" in (e.tags or []):
                txt = e.fallback_desc or e.display_name()
                game.log(f"„{e.display_name()}”: {txt}", LOG_NORMAL)
                return
            game.log(t("feedback_read_unreadable",
                       fallback=f"„{e.display_name()}” — "
                                f"tu nic nie ma do czytania."),
                     LOG_WARN)
            return

    if room is not None:
        for e in (room.entities or []):
            if e is None:
                continue
            if needle in _fold(e.display_name()) or \
               any(needle in _fold(tg or "") for tg in (e.tags or [])):
                if "lore" in (e.tags or []) or \
                   "readable" in (e.tags or []) or \
                   "paper" in (e.tags or []) or \
                   "screen" in (e.tags or []) or \
                   "terminal" in (e.tags or []):
                    txt = e.fallback_desc or e.display_name()
                    game.log(f"„{e.display_name()}”: {txt}", LOG_NORMAL)
                    return
                game.log(t("feedback_read_unreadable",
                           fallback=f"„{e.display_name()}” — "
                                    f"tu nic nie ma do czytania."),
                         LOG_WARN)
                return
    game.log(t("feedback_read_nothing",
               fallback=f"Nie widzisz tu „{intent.targets[0]}” "
                        f"do przeczytania."), LOG_WARN)


# ── Apply enhancement (P29.14) ──────────────────────────────────────────

def attempt_apply_enhancement(game, intent) -> None:
    """Apply an enhancement consumable to a weapon/armor item."""
    from ..affordances import fold as _fold

    ch = game.world.character
    if ch is None:
        return
    if not intent.tool or not intent.targets:
        game.log(t("feedback_apply_syntax",
                   fallback="Składnia: nałóż <wzmocnienie> "
                            "na <broń lub pancerz>."), LOG_WARN)
        return

    tool_needle = _fold(intent.tool)
    target_needle = _fold(intent.targets[0])
    enhancement = None
    target = None
    for eid in list(ch.inventory_ids):
        e = game.world.get(eid)
        if e is None:
            continue
        nm = _fold(e.display_name())
        tags = e.tags or []
        if "enhancement" in tags and enhancement is None and tool_needle in nm:
            enhancement = e
        elif target is None and target_needle in nm:
            target = e

    if enhancement is None:
        game.log(t("feedback_apply_no_tool",
                   fallback=f"Nie masz „{intent.tool}” w plecaku, "
                            f"albo to nie jest wzmocnienie."), LOG_WARN)
        return
    if target is None:
        game.log(t("feedback_apply_no_target",
                   fallback=f"Nie masz „{intent.targets[0]}” w plecaku."),
                 LOG_WARN)
        return

    from ...content import crafting as _cr
    recipes = _cr.all_recipes()
    enh_key = (enhancement.state or {}).get("enhancement_key") or \
              enhancement.key
    rec = recipes.get(enh_key) or {}
    spec = rec.get("enhancement") or {}
    applies_to = spec.get("applies_to_tags") or []
    effect = spec.get("effect") or ""

    tgt_tags = set(target.tags or [])
    if applies_to and not (set(applies_to) & tgt_tags):
        need = ", ".join(applies_to)
        game.log(t("feedback_apply_wrong_target",
                   fallback=f"„{target.display_name()}” nie jest w "
                            f"stanie przyjąć tego wzmocnienia "
                            f"(potrzeba: {need})."), LOG_WARN)
        return

    applied_label = ""
    if effect == "coating":
        coating = dict(spec.get("coating") or {})
        target.state = target.state or {}
        target.state["coating"] = coating
        applied_label = (
            f"Powlekasz „{target.display_name()}” — następne "
            f"{coating.get('hits_remaining', 1)} ciosów zada "
            f"obrażenia typu {coating.get('damage_type', 'physical')}.")
    elif effect == "permanent":
        perm = spec.get("permanent") or {}
        target.state = target.state or {}
        target.tags = list(target.tags or [])
        if "damage_bonus" in perm:
            cur = int((target.state or {}).get("damage_bonus_perm", 0))
            target.state["damage_bonus_perm"] = cur + int(perm["damage_bonus"])
        if "attack_bonus" in perm:
            cur = int((target.state or {}).get("attack_bonus_perm", 0))
            target.state["attack_bonus_perm"] = cur + int(perm["attack_bonus"])
        if "ac_bonus" in perm:
            cur = int((target.state or {}).get("ac_bonus_perm", 0))
            target.state["ac_bonus_perm"] = cur + int(perm["ac_bonus"])
        new_tag = perm.get("tag_add")
        if new_tag and new_tag not in target.tags:
            target.tags.append(new_tag)
        resist = perm.get("resist_add")
        if resist:
            resists = list(getattr(target, "resists", None) or [])
            if resist not in resists:
                resists.append(resist)
            target.resists = resists
        applied_label = (
            f"Modyfikujesz „{target.display_name()}”: efekt trwały "
            f"({new_tag or 'wzmocnienie'}).")
    else:
        game.log(t("feedback_apply_unknown_effect",
                   fallback=f"„{enhancement.display_name()}” nie "
                            f"wie, jak na to zadziałać."), LOG_WARN)
        return

    try:
        ch.inventory_ids.remove(enhancement.entity_id)
    except ValueError:
        pass
    if applied_label:
        game.log(applied_label, LOG_SUCCESS)

    from .._debug import swallow as _swallow
    with _swallow("time_system.advance[apply_enhancement]"):
        from .. import time_system as _ts
        _ts.advance(game.world, 2)
    with _swallow("achievements.unlock[apteka_w_plecaku]"):
        from ...systems import achievements as _ach
        _ach.unlock(ch, "apteka_w_plecaku", world=game.world)
