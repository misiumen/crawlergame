"""Enemy combat AI — utility-scoring planner + telegraphed intentions.

P30. Replaces the old flat `if/elif behavior` action picker with a small
utility system: each enemy enumerates the candidate actions its situation
allows, scores every candidate against a handful of weighted considerations
(player HP, player exposure, own HP, morale, band, surviving allies), and
takes the highest-scoring one (with light noise so equal fights don't play
out identically every time). The behavior profile no longer *decides* the
action — it biases the weights, so a berserker and a coward facing the same
board lean different ways but can still surprise.

Three player-facing systems ride on top of the planner:

  * Intentions — every living hostile commits to a *category* of action for
    its next turn (attack / defend / special / move / flee / wait). That
    category is surfaced on the enemy card during the player's turn so the
    player can read the room and respond. Exact numbers are never shown.

  * Charged specials — a telegraphed heavy move per behavior. Because the
    intent is shown a full player-turn ahead, a "special" telegraph is a
    react-or-suffer moment: stun / knock-down the winding-up enemy and the
    special fizzles (interrupt).

  * Morale — a 0..100 meter per enemy that drifts with the fight (allies
    dying, taking big hits, being intimidated drop it; landing big hits on
    the player lifts it). Low morale pushes the utility weights toward
    defend / flee; berserker-types instead ENRAGE at low morale/HP, trading
    defense for damage.

No LLM, no per-frame cost — the planner runs once per enemy per round.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import random as _random

from . import combat as cmb


# ── Intent categories (display buckets) ───────────────────────────────────

CAT_ATTACK  = "attack"
CAT_DEFEND  = "defend"
CAT_SPECIAL = "special"
CAT_MOVE    = "move"
CAT_FLEE    = "flee"
CAT_WAIT    = "wait"

# Short PL labels for the intent chip. Specials override with their own.
CATEGORY_LABEL_PL = {
    CAT_ATTACK:  "Atak",
    CAT_DEFEND:  "Obrona",
    CAT_SPECIAL: "Szykuje cios!",
    CAT_MOVE:    "Manewr",
    CAT_FLEE:    "Ucieczka",
    CAT_WAIT:    "Zwłoka",
}

_KIND_TO_CATEGORY = {
    "attack":   CAT_ATTACK,
    "special":  CAT_SPECIAL,
    "defend":   CAT_DEFEND,
    "flee":     CAT_FLEE,
    "approach": CAT_MOVE,
    "back_off": CAT_MOVE,
    "wait":     CAT_WAIT,
}


def kind_to_category(kind: str) -> str:
    return _KIND_TO_CATEGORY.get(kind, CAT_ATTACK)


# ── Charged specials (one per behavior; coward has none) ──────────────────
#
# dmg_mult     multiplies the base damage roll on release.
# inflict      (status_key, duration) applied to the victim on a hit.
# ranged       requires/uses the at_range band.
# cooldown     turns before the enemy can telegraph it again.

SPECIALS: Dict[str, Dict[str, Any]] = {
    cmb.BEHAVIOR_BERSERKER: {
        "key": "frenzied_charge", "label_pl": "Szał!", "cooldown": 3,
        "dmg_mult": 2.0, "inflict": (cmb.STATUS_BLEEDING, 3), "ranged": False,
        "note_pl": "tnie w szale",
    },
    cmb.BEHAVIOR_GUARD: {
        "key": "shield_bash", "label_pl": "Taranowanie!", "cooldown": 3,
        "dmg_mult": 1.4, "inflict": (cmb.STATUS_STUNNED, 1), "ranged": False,
        "note_pl": "uderza tarczą",
    },
    cmb.BEHAVIOR_RANGED: {
        "key": "aimed_shot", "label_pl": "Strzał celowany!", "cooldown": 3,
        "dmg_mult": 2.2, "inflict": None, "ranged": True,
        "note_pl": "bierze cię na cel",
    },
    cmb.BEHAVIOR_MACHINE: {
        "key": "overload", "label_pl": "Przeciążenie!", "cooldown": 4,
        "dmg_mult": 1.6, "inflict": (cmb.STATUS_BLINDED, 2), "ranged": False,
        "note_pl": "wyładowuje energię",
    },
    cmb.BEHAVIOR_SWARM: {
        "key": "gang_up", "label_pl": "Zmasowany atak!", "cooldown": 2,
        "dmg_mult": 1.5, "inflict": None, "ranged": False,
        "note_pl": "atakuje hurmą",
    },
}


def special_for(enemy) -> Optional[Dict[str, Any]]:
    return SPECIALS.get(cmb.default_behavior(enemy))


# ── Per-enemy combat memory (morale + cooldowns) ──────────────────────────

def _mem(enemy) -> Dict[str, Any]:
    """Mutable per-enemy AI scratch that round-trips through save/load via
    Entity.state. Lazily initialised."""
    if getattr(enemy, "state", None) is None:
        try:
            enemy.state = {}
        except Exception:
            return {}
    return enemy.state.setdefault("combat_ai", {})


def get_morale(enemy) -> int:
    return int(_mem(enemy).get("morale", 100))


def set_morale(enemy, value: int) -> None:
    _mem(enemy)["morale"] = max(0, min(100, int(value)))


def adjust_morale(enemy, delta: int) -> int:
    set_morale(enemy, get_morale(enemy) + int(delta))
    return get_morale(enemy)


def special_ready(enemy) -> bool:
    return int(_mem(enemy).get("special_cd", 0)) <= 0


def _put_special_on_cooldown(enemy) -> None:
    spec = special_for(enemy)
    if spec:
        _mem(enemy)["special_cd"] = int(spec.get("cooldown", 3))


def tick_cooldowns(enemy) -> None:
    """Called once per enemy turn: count special cooldowns down."""
    m = _mem(enemy)
    cd = int(m.get("special_cd", 0))
    if cd > 0:
        m["special_cd"] = cd - 1


def is_enraged(enemy) -> bool:
    return cmb.has_status(enemy, cmb.STATUS_ENRAGED)


# ── Decision context ──────────────────────────────────────────────────────

class _Ctx:
    __slots__ = ("player_low", "exposed", "wounded", "self_low", "morale01",
                 "allies", "band", "behavior", "enraged", "can_attack",
                 "can_approach", "can_back_off", "special_avail")


_WOUND_STATUSES = (cmb.STATUS_BLEEDING, cmb.STATUS_WOUNDED, cmb.STATUS_PRONE,
                   cmb.STATUS_STUNNED, cmb.STATUS_BLINDED, cmb.STATUS_POISONED)


def _build_ctx(world, cs, enemy) -> _Ctx:
    c = _Ctx()
    ch = getattr(world, "character", None)
    p_ratio = 1.0
    if ch is not None and getattr(ch, "max_hp", 0):
        p_ratio = max(0.0, min(1.0, ch.hp / max(1, ch.max_hp)))
    c.player_low = 1.0 - p_ratio
    # Player is "exposed" when not defending and not braced to dodge.
    defending = int(getattr(cs, "player_defend", 0) or 0) > 0
    dodging = bool(getattr(cs, "player_dodge", False))
    c.exposed = 1.0 if not (defending or dodging) else 0.35
    # Smart targeting: press the advantage when the player is already hurt.
    wnd = 0.0
    if ch is not None:
        if any(cmb.has_status(ch, s) for s in _WOUND_STATUSES):
            wnd += 0.5
        if p_ratio < 0.35:
            wnd += 0.5
    c.wounded = min(1.0, wnd)

    s_ratio = 1.0
    if getattr(enemy, "max_hp", 0):
        s_ratio = max(0.0, min(1.0, enemy.hp / max(1, enemy.max_hp)))
    c.self_low = 1.0 - s_ratio
    # Effective morale folds in active fear: an intimidated / afraid enemy
    # fights with less nerve even if its meter hasn't been spent. This is
    # how the player's `zastrasz` (intimidate → afraid/shaken) pushes the
    # AI toward defend/flee without a bespoke hook in that handler.
    mor = get_morale(enemy) / 100.0
    # Wounds sap nerve directly: a near-dead enemy fights scared regardless
    # of its meter (this is what makes a hurt coward break and run).
    mor *= (0.4 + 0.6 * s_ratio)
    if cmb.has_status(enemy, cmb.STATUS_AFRAID) or cmb.has_status(enemy, "shaken"):
        mor *= 0.5
    c.morale01 = max(0.0, mor)

    allies = 0
    for eid in (cs.participants or []):
        if eid == enemy.entity_id:
            continue
        other = world.get(eid)
        if other is not None and other.is_alive():
            allies += 1
    c.allies = min(1.0, allies / 3.0)

    c.band = cs.bands.get(enemy.entity_id, cmb.BAND_ENGAGED)
    c.behavior = cmb.default_behavior(enemy)
    c.enraged = is_enraged(enemy)

    ranged_behavior = (c.behavior == cmb.BEHAVIOR_RANGED)
    c.can_attack = (c.band == cmb.BAND_ENGAGED) or \
                   (ranged_behavior and c.band == cmb.BAND_AT_RANGE)
    # A broken leg (slowed) means it can't close the distance.
    c.can_approach = (c.band == cmb.BAND_AT_RANGE and not ranged_behavior
                      and not cmb.has_status(enemy, cmb.STATUS_SLOWED))
    c.can_back_off = (c.band == cmb.BAND_ENGAGED and ranged_behavior)

    spec = special_for(enemy)
    spec_avail = False
    if spec is not None and special_ready(enemy):
        if spec.get("ranged"):
            spec_avail = (c.band == cmb.BAND_AT_RANGE)
        else:
            spec_avail = (c.band == cmb.BAND_ENGAGED)
    c.special_avail = spec_avail
    return c


# ── Profile weight biases ─────────────────────────────────────────────────
#   kind -> multiplier. Missing kind defaults to 1.0.

_PROFILE_WEIGHTS: Dict[str, Dict[str, float]] = {
    cmb.BEHAVIOR_BERSERKER: {"attack": 1.45, "special": 1.25, "approach": 1.2,
                             "defend": 0.25, "back_off": 0.1, "flee": 0.1},
    cmb.BEHAVIOR_GUARD:     {"attack": 0.95, "special": 1.1, "approach": 0.85,
                             "defend": 1.4, "back_off": 0.3, "flee": 0.15},
    cmb.BEHAVIOR_COWARD:    {"attack": 0.7, "special": 0.4, "approach": 0.5,
                             "defend": 1.05, "back_off": 1.0, "flee": 1.5},
    cmb.BEHAVIOR_MACHINE:   {"attack": 1.1, "special": 1.15, "approach": 1.05,
                             "defend": 0.7, "back_off": 0.35, "flee": 0.0},
    cmb.BEHAVIOR_RANGED:    {"attack": 1.15, "special": 1.2, "approach": 0.2,
                             "defend": 0.6, "back_off": 1.25, "flee": 0.4},
    cmb.BEHAVIOR_SWARM:     {"attack": 1.15, "special": 0.7, "approach": 1.25,
                             "defend": 0.4, "back_off": 0.15, "flee": 0.55},
}

_ENRAGE_WEIGHTS = {"attack": 1.5, "special": 1.4, "approach": 1.3,
                   "defend": 0.15, "back_off": 0.2, "flee": 0.0, "wait": 0.3}


def _weight(behavior: str, kind: str, enraged: bool) -> float:
    base = _PROFILE_WEIGHTS.get(behavior, {}).get(kind, 1.0)
    if enraged:
        base *= _ENRAGE_WEIGHTS.get(kind, 1.0)
    return base


# ── Candidate scoring ─────────────────────────────────────────────────────

def _raw_scores(c: _Ctx) -> Dict[str, float]:
    s: Dict[str, float] = {}
    if c.can_attack:
        atk = (0.50 + 0.40 * c.player_low + 0.40 * c.exposed
               + 0.25 * c.wounded + 0.15 * c.allies + 0.10 * c.morale01)
        # A ranged fighter caught in melee swings clumsily — it would much
        # rather make distance, so its in-melee attack is heavily discounted.
        if c.behavior == cmb.BEHAVIOR_RANGED and c.band == cmb.BAND_ENGAGED:
            atk *= 0.5
        s["attack"] = atk
    if c.special_avail:
        s["special"] = (0.45 + 0.50 * c.player_low + 0.40 * c.exposed
                        + 0.25 * c.wounded + 0.20 * c.morale01)
    if c.can_approach:
        s["approach"] = 0.60 + 0.30 * c.player_low + 0.20 * c.morale01
    if c.can_back_off:
        s["back_off"] = 0.50 + 0.40 * c.self_low + 0.30 * (1.0 - c.morale01)
    # Defend / flee / wait are always on the table.
    s["defend"] = 0.25 + 0.60 * c.self_low + 0.20 * (1.0 - c.morale01)
    s["flee"] = 0.05 + 0.70 * (1.0 - c.morale01) + 0.45 * c.self_low
    s["wait"] = 0.12
    return s


def _decide_kind(world, cs, enemy, *, rng=_random) -> Tuple[str, _Ctx]:
    c = _build_ctx(world, cs, enemy)
    raw = _raw_scores(c)
    best_kind, best_score = "wait", float("-inf")
    for kind, base in raw.items():
        score = base * _weight(c.behavior, kind, c.enraged)
        score += rng.uniform(0.0, 0.12)     # light noise breaks ties / patterns
        if score > best_score:
            best_kind, best_score = kind, score
    return best_kind, c


# ── Action construction ───────────────────────────────────────────────────

def _attack_damage(enemy, *, ranged=False, heavy=False) -> int:
    return cmb._enemy_attack_damage(enemy, ranged=ranged, heavy=heavy)


def _make_attack(world, cs, enemy, c: _Ctx) -> "cmb.EnemyAction":
    heavy = (c.behavior == cmb.BEHAVIOR_BERSERKER) or c.enraged
    ranged = (c.behavior == cmb.BEHAVIOR_RANGED and c.band == cmb.BAND_AT_RANGE)
    dmg = _attack_damage(enemy, ranged=ranged, heavy=heavy)
    if c.behavior == cmb.BEHAVIOR_GUARD:
        dmg = max(1, dmg - 1)
    elif c.behavior == cmb.BEHAVIOR_SWARM:
        dmg = max(1, dmg - 1)
    act = cmb.EnemyAction(actor_id=enemy.entity_id, kind="attack", damage=dmg,
                          category=CAT_ATTACK,
                          label_pl=CATEGORY_LABEL_PL[CAT_ATTACK],
                          note=("ranged shot" if ranged else "strike"))
    _apply_faction_retarget(world, cs, enemy, act)
    return act


def _make_special(world, cs, enemy, c: _Ctx) -> "cmb.EnemyAction":
    spec = special_for(enemy)
    if spec is None:
        return _make_attack(world, cs, enemy, c)
    ranged = bool(spec.get("ranged"))
    base = _attack_damage(enemy, ranged=ranged, heavy=False)
    dmg = max(1, int(round(base * float(spec.get("dmg_mult", 1.5)))))
    inflict = spec.get("inflict")
    act = cmb.EnemyAction(
        actor_id=enemy.entity_id, kind="special", damage=dmg,
        category=CAT_SPECIAL, special_key=spec["key"],
        label_pl=spec.get("label_pl", CATEGORY_LABEL_PL[CAT_SPECIAL]),
        note=spec.get("note_pl", "szykuje cios"),
        target_status=(inflict[0] if inflict else None),
        target_status_duration=(inflict[1] if inflict else 0),
    )
    _apply_faction_retarget(world, cs, enemy, act)
    return act


def _apply_faction_retarget(world, cs, enemy, act) -> None:
    rival_id = cmb._pick_rival_target(world, cs, enemy)
    if rival_id is not None:
        act.target_id = rival_id
        act.note = (act.note + " → rywal").strip()


def _build_from_kind(world, cs, enemy, kind: str, c: _Ctx) -> "cmb.EnemyAction":
    eid = enemy.entity_id
    if kind == "attack":
        return _make_attack(world, cs, enemy, c)
    if kind == "special":
        return _make_special(world, cs, enemy, c)
    if kind == "approach":
        return cmb.EnemyAction(actor_id=eid, kind="approach", category=CAT_MOVE,
                               label_pl="Naciera",
                               note="closes distance")
    if kind == "back_off":
        return cmb.EnemyAction(actor_id=eid, kind="back_off", category=CAT_MOVE,
                               label_pl="Odskok",
                               note="keeps distance")
    if kind == "defend":
        return cmb.EnemyAction(actor_id=eid, kind="defend", category=CAT_DEFEND,
                               label_pl=CATEGORY_LABEL_PL[CAT_DEFEND],
                               note="braces")
    if kind == "flee":
        return cmb.EnemyAction(actor_id=eid, kind="flee", category=CAT_FLEE,
                               label_pl=CATEGORY_LABEL_PL[CAT_FLEE],
                               note="retreats")
    return cmb.EnemyAction(actor_id=eid, kind="wait", category=CAT_WAIT,
                           label_pl=CATEGORY_LABEL_PL[CAT_WAIT], note="waits")


# ── Public planner ────────────────────────────────────────────────────────

def plan_action(world, cs, enemy, *, rng=_random) -> "cmb.EnemyAction":
    """Score the situation and return the chosen `EnemyAction`.

    Hard guards first: a stunned / prone enemy always waits (and a winding-up
    special is interrupted elsewhere). Otherwise update enrage state, then
    pick the best-scoring candidate kind and realise it into a concrete
    action (rolling damage now)."""
    eid = enemy.entity_id
    if cmb.has_status(enemy, cmb.STATUS_STUNNED) or \
            cmb.has_status(enemy, cmb.STATUS_PRONE):
        return cmb.EnemyAction(actor_id=eid, kind="wait", category=CAT_WAIT,
                               label_pl="Oszołomiony",
                               note="stunned/prone — straci turę")
    _update_enrage(enemy)
    kind, c = _decide_kind(world, cs, enemy, rng=rng)
    return _build_from_kind(world, cs, enemy, kind, c)


def _update_enrage(enemy) -> None:
    """Berserker-flavoured enemies flip into ENRAGED when badly hurt or
    when morale collapses — they stop defending and hit harder. Other
    profiles never enrage (they defend / flee instead)."""
    behavior = cmb.default_behavior(enemy)
    enrages = behavior in (cmb.BEHAVIOR_BERSERKER, cmb.BEHAVIOR_SWARM) or \
        ("berserk" in (enemy.tags or []) or "frenzy" in (enemy.tags or []))
    if not enrages:
        return
    s_ratio = 1.0
    if getattr(enemy, "max_hp", 0):
        s_ratio = enemy.hp / max(1, enemy.max_hp)
    if (s_ratio <= 0.35 or get_morale(enemy) <= 35) and not is_enraged(enemy):
        cmb.add_status(enemy, cmb.STATUS_ENRAGED, 99)


# ── Intent telegraphing ───────────────────────────────────────────────────

def plan_intents(world, cs) -> None:
    """(Re)compute the next-turn intent for every living participant and
    store the category on `cs.enemy_intents`. Called at combat start and at
    the end of each enemy turn so the player always sees the upcoming move
    during their phase."""
    if cs is None:
        return
    if cs.enemy_intents is None:
        cs.enemy_intents = {}
    for eid in list(cs.participants):
        ent = world.get(eid)
        if ent is None or not ent.is_alive():
            cs.enemy_intents.pop(eid, None)
            continue
        try:
            action = plan_action(world, cs, ent)
            cs.enemy_intents[eid] = action.intent_dict()
        except Exception:
            cs.enemy_intents.pop(eid, None)


def realize_intent(world, cs, enemy) -> "cmb.EnemyAction":
    """Turn the telegraphed intent into a concrete action to execute now.

    Honors the *kind* the player was shown (so the telegraph doesn't lie),
    re-rolling damage at execution time, but re-validates band-dependent
    kinds so a stale plan can't do something impossible."""
    intent = (cs.enemy_intents or {}).get(enemy.entity_id)
    if not intent:
        return plan_action(world, cs, enemy)
    # Stun / prone interrupts everything (special fizzle handled by caller).
    if cmb.has_status(enemy, cmb.STATUS_STUNNED) or \
            cmb.has_status(enemy, cmb.STATUS_PRONE):
        return cmb.EnemyAction(actor_id=enemy.entity_id, kind="wait",
                               category=CAT_WAIT, special_key=intent.get("special_key"),
                               label_pl="Oszołomiony",
                               note="stunned/prone — straci turę")
    # Self-preservation override. An intent committed while healthy
    # shouldn't force a now-dying enemy to stand and trade blows. If a
    # fresh read of the board says "flee", honor the panic. This is the one
    # sanctioned break from the telegraph — and it only ever DOWNGRADES
    # aggression (never escalates), so the shown intent never under-sells
    # danger to the player.
    s_ratio = (enemy.hp / max(1, enemy.max_hp)) if getattr(enemy, "max_hp", 0) else 1.0
    if intent.get("kind") != "flee" and s_ratio <= 0.30:
        fresh = plan_action(world, cs, enemy)
        if fresh.kind == "flee":
            return fresh
    c = _build_ctx(world, cs, enemy)
    kind = intent.get("kind", "attack")
    # Re-validate against the current board.
    if kind == "attack" and not c.can_attack:
        kind = "approach" if c.can_approach else "wait"
    elif kind == "approach" and c.band == cmb.BAND_ENGAGED:
        kind = "attack" if c.can_attack else "wait"
    elif kind == "back_off" and c.band == cmb.BAND_AT_RANGE:
        kind = "wait"
    elif kind == "special" and not c.special_avail:
        # Lost the window (got cooled down, or band moved) — fall back.
        kind = "attack" if c.can_attack else ("approach" if c.can_approach else "wait")
    act = _build_from_kind(world, cs, enemy, kind, c)
    return act


def commit_special_used(enemy) -> None:
    """Put the enemy's special on cooldown after a successful release."""
    _put_special_on_cooldown(enemy)


# ── Morale events (called from the combat loop) ───────────────────────────

def note_ally_down(world, cs, dead_eid: int) -> List[Tuple[Any, int]]:
    """An ally just fell — surviving hostiles lose nerve. Returns a list of
    (enemy, new_morale) for any that dropped, so the caller can flavour-log
    a wobble."""
    out: List[Tuple[Any, int]] = []
    for eid in list(cs.participants or []):
        if eid == dead_eid:
            continue
        ent = world.get(eid)
        if ent is None or not ent.is_alive():
            continue
        before = get_morale(ent)
        adjust_morale(ent, -22)
        out.append((ent, get_morale(ent)))
        _ = before
    return out


def note_took_big_hit(enemy, dmg: int) -> None:
    if getattr(enemy, "max_hp", 0) and dmg >= max(1, enemy.max_hp // 4):
        adjust_morale(enemy, -15)


def note_intimidated(enemy) -> None:
    adjust_morale(enemy, -20)


def note_hit_player(enemy, dmg: int, player_max_hp: int) -> None:
    if player_max_hp and dmg >= max(1, player_max_hp // 5):
        adjust_morale(enemy, +10)
