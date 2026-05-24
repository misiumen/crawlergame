"""Prompt 19 — companion action handlers.

Each handler takes (game, intent) and:
  - finds the active pet (or logs a failure line if none),
  - validates plausibility (e.g. fish can't scout vents),
  - applies time / stress / bond / audience effects,
  - emits sponsor tags so the Prompt-18 sponsor engine notices.

Action handlers MUST tolerate `game.world.current_floor is None` (the
parser smoke tests build worlds without a floor); in that case they
log a sensible fallback line and return without crashing.

Plausibility decisions are intentionally tag-based on the companion's
`abilities` list so a future content drop just adds the ability tag to
the catalog entry — no engine changes needed.
"""
from __future__ import annotations

from typing import Optional, Any

from ..ui.lang import t


# Log-category constants (mirror engine.game LOG_*).
LOG_NORMAL  = "normal"
LOG_SUCCESS = "success"
LOG_WARN    = "warn"
LOG_DANGER  = "danger"
LOG_SYSTEM  = "system"
LOG_SYNDIC  = "syndicate"


# ── Entry point ────────────────────────────────────────────────────────────

def handle(game, intent_key: str, intent) -> None:
    handler = _HANDLERS.get(intent_key)
    if handler is None:
        return
    pet = _active_pet(game)
    if pet is None:
        game.log(t("companion_feedback_none_owned",
                   fallback="Nie masz teraz przy sobie żadnego zwierzęcia."),
                 LOG_WARN)
        return
    handler(game, intent, pet)


# ── Helpers ────────────────────────────────────────────────────────────────

def _active_pet(game):
    from . import companion as _comp
    return _comp.active_pet(game.world)


def _advance_time(game, minutes: int) -> None:
    if minutes <= 0:
        return
    from . import time_system
    time_system.advance(game.world, minutes)


def _emit_sponsor_tags(game, pet, *extra_tags: str) -> None:
    """Emit the pet's catalog `sponsor_likes_tags` plus any per-action
    extras. Routed through engine.sponsors so attention/interventions
    fire from the same code path everything else uses."""
    try:
        from . import sponsors as _sp
        for tag in list(pet.sponsor_likes_tags or []) + list(extra_tags):
            if tag:
                _sp.note_player_tag(game.world, tag, weight=1)
        _sp.maybe_intervene(game.world)
    except Exception:
        pass


def _add_audience(game, delta: int, source: str) -> None:
    try:
        from . import audience as _aud
        _aud.change_audience(game.world, delta, source=source)
    except Exception:
        # Old code path that doesn't have audience module yet.
        if hasattr(game.world.character, "audience_rating"):
            game.world.character.audience_rating += int(delta)


def _has_food(game) -> bool:
    """Cheap check — does the player have anything food-tagged in
    inventory? Uses the same entity registry as inventory does."""
    for ent_id in (game.world.character.inventory_ids or []):
        ent = game.world.get(ent_id)
        if ent is None:
            continue
        tags = list(getattr(ent, "tags", []) or [])
        if any(t in tags for t in ("food", "ration", "snack")):
            return True
        # `snack_bar` template doesn't carry the `food` tag yet; treat
        # the entity key itself as a fallback identifier.
        if getattr(ent, "key", "") in ("snack_bar", "ration_pack",
                                       "chem_reagent"):
            return True
    return False


def _consume_one_food(game) -> Optional[str]:
    """Spend one food item from inventory. Returns the consumed item's
    display name, or None if nothing was consumed."""
    char = game.world.character
    for ent_id in list(char.inventory_ids or []):
        ent = game.world.get(ent_id)
        if ent is None:
            continue
        tags = list(getattr(ent, "tags", []) or [])
        key = getattr(ent, "key", "")
        if ("food" in tags or "ration" in tags or "snack" in tags or
            key in ("snack_bar", "ration_pack")):
            name = ent.display_name() if hasattr(ent, "display_name") else \
                   getattr(ent, "fallback_name", key) or key
            char.inventory_ids.remove(ent_id)
            return name
    return None


# ── Individual handlers ────────────────────────────────────────────────────

def _h_inspect(game, intent, pet) -> None:
    """1 min. No roll. Dump the pet's status to the log."""
    from ..content.data.pets import get_pet_template
    tmpl = get_pet_template(pet.species_key)
    game.log(t("companion_inspect_header",
               fallback=f"— {pet.display_name_pl} —"), LOG_SYSTEM)
    if tmpl:
        if tmpl.get("description_pl"):
            game.log(tmpl["description_pl"], LOG_NORMAL)
        for label, val in (
            ("Temperament", tmpl.get("temperament", "")),
            ("Rola", tmpl.get("role", "")),
            ("Potrzebuje", tmpl.get("need", "")),
            ("Ryzyko", tmpl.get("risk", "")),
        ):
            if val:
                game.log(f"  {label}: {val}", LOG_NORMAL)
    game.log(
        f"  Więź: {pet.bond}/10  •  Stres: {pet.stress}/10  •  "
        f"Stan: {pet.status}",
        LOG_NORMAL)
    if pet.abilities:
        game.log("  Umiejętności: " + ", ".join(pet.abilities), LOG_NORMAL)
    _advance_time(game, 1)


def _h_feed(game, intent, pet) -> None:
    """3 min, consumes one food item. Bond +1, stress −2.
    If no food: hint + small bond −0 (no penalty), 1 min only."""
    if not _has_food(game):
        game.log(t("companion_feed_no_food",
                   fallback=f"Nie masz nic, co {pet.display_name_pl} by ruszyła. "
                            f"Spróbuj znaleźć batonik albo racje."),
                 LOG_WARN)
        _advance_time(game, 1)
        return
    consumed = _consume_one_food(game)
    pet.adjust_bond(+1)
    pet.adjust_stress(-2)
    game.log(t("companion_feed_ok",
               fallback=f"Karmisz {pet.display_name_pl}. "
                        f"Zjada {consumed or 'co tam masz'}. "
                        f"(więź +1, stres −2)"),
             LOG_SUCCESS)
    _advance_time(game, 3)


def _h_calm(game, intent, pet) -> None:
    """5 min, CHA roll DC 10. Success: stress −3. Fail: stress −1 only."""
    import random as _r
    char = game.world.character
    roll = _r.randint(1, 20)
    mod  = char.stat_mod("CHA")
    total = roll + mod
    if total >= 10:
        pet.adjust_stress(-3)
        pet.adjust_bond(+1)
        game.log(t("companion_calm_success",
                   fallback=f"Mówisz spokojnym głosem. "
                            f"{pet.display_name_pl} oddycha wolniej. "
                            f"(stres −3, więź +1)"),
                 LOG_SUCCESS)
    else:
        pet.adjust_stress(-1)
        game.log(t("companion_calm_partial",
                   fallback=f"{pet.display_name_pl} nie do końca ci wierzy, "
                            f"ale przynajmniej przestaje się rzucać. "
                            f"(stres −1)"),
                 LOG_WARN)
    _advance_time(game, 5)


def _h_scout(game, intent, pet) -> None:
    """Plausibility: pet must have scout_tight or scout_aerial.
    15 min, WIS roll DC 11. Success: reveal one hidden tag in next room
    (best-effort — falls back to a flavor line). Fail: chance of pet
    becoming missing on critical fail (raw 1). Emits 'spectacle' tag."""
    from ..content.data.pets import (
        ABILITY_SCOUT_TIGHT, ABILITY_SCOUT_AERIAL,
    )
    if not (pet.has_ability(ABILITY_SCOUT_TIGHT) or
            pet.has_ability(ABILITY_SCOUT_AERIAL)):
        game.log(t("companion_scout_implausible",
                   fallback=f"{pet.display_name_pl} nie nadaje się na zwiad. "
                            f"Patrzy na ciebie z pretensją."),
                 LOG_WARN)
        _advance_time(game, 1)
        return

    import random as _r
    char = game.world.character
    # Slow pets ("painfully_slow") take 5× longer.
    time_cost = 15 * (5 if "painfully_slow" in (pet.tags or []) else 1)
    raw = _r.randint(1, 20)
    mod = char.stat_mod("WIS")
    total = raw + mod

    if raw == 1:
        # Critical fail — pet goes missing.
        from . import companion as _comp
        pet.status = _comp.STATUS_MISSING
        game.log(t("companion_scout_lost",
                   fallback=f"{pet.display_name_pl} znika za rogiem. "
                            f"Nie wraca. (status: zaginął)"),
                 LOG_DANGER)
        pet.adjust_stress(+5)
    elif total >= 11:
        pet.adjust_stress(+2)
        # Tease one hint about the current room's actual_type if known
        # (cheap, but better than a flat line).
        floor = game.world.current_floor
        room = floor.current_room() if floor else None
        hint = ""
        if room is not None:
            actual = getattr(room, "actual_type", "")
            if actual:
                hint = f" Coś tam czuje — {actual}."
        game.log(t("companion_scout_success",
                   fallback=f"{pet.display_name_pl} wraca z czymś.{hint} "
                            f"(stres +2)"),
                 LOG_SUCCESS)
    else:
        pet.adjust_stress(+3)
        game.log(t("companion_scout_fail",
                   fallback=f"{pet.display_name_pl} wraca bez niczego "
                            f"użytecznego. (stres +3)"),
                 LOG_WARN)
    _add_audience(game, 1, source="pet_scout")
    _emit_sponsor_tags(game, pet, "spectacle")
    _advance_time(game, time_cost)


def _h_lure(game, intent, pet) -> None:
    """Combat: set companion_advantage_pending on the room's CombatState.
    Exploration: distract an NPC for 5 minutes + audience +3.
    Stress cost +3 either way. Emits 'spectacle' tag.

    Prompt 19 audit fix B1: previously checked `game.combat_state` /
    `game.world.combat_state` which don't exist — combat lives on
    `room.state["combat"]` and must be fetched via `combat.get_combat`.
    Also ends the player's combat turn so enemies get their reaction,
    matching every other in-combat action.
    """
    from . import combat as _cmb
    floor = game.world.current_floor
    room  = floor.current_room() if floor else None
    cs = _cmb.get_combat(room) if room is not None else None
    if cs is not None:
        cs.companion_advantage_pending = True
        pet.adjust_stress(+3)
        game.log(t("companion_lure_combat",
                   fallback=f"{pet.display_name_pl} robi scenę. "
                            f"Twój następny atak ma przewagę. (stres +3)"),
                 LOG_SUCCESS)
        _add_audience(game, 3, source="pet_lure_combat")
        _emit_sponsor_tags(game, pet, "spectacle")
        _advance_time(game, 1)
        # End the player's combat turn so enemies react — the player
        # spent their action on the lure.
        if hasattr(game, "_combat_after_player_action"):
            try:
                game._combat_after_player_action(cs)
            except Exception as exc:
                game.log(f"(combat tick failed: {exc})", LOG_WARN)
        return
    # Exploration path
    pet.adjust_stress(+3)
    game.log(t("companion_lure_exploration",
               fallback=f"{pet.display_name_pl} biegnie przed siebie "
                        f"i robi taki spektakl, że nikt nie patrzy w "
                        f"twoją stronę przez chwilę. (stres +3)"),
             LOG_SUCCESS)
    _add_audience(game, 3, source="pet_lure_exploration")
    _emit_sponsor_tags(game, pet, "spectacle")
    _advance_time(game, 5)


_HANDLERS = {
    "companion_inspect": _h_inspect,
    "companion_feed":    _h_feed,
    "companion_calm":    _h_calm,
    "companion_scout":   _h_scout,
    "companion_lure":    _h_lure,
}
