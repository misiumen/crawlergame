"""Combat v1 — tactical survival combat (Prompt 17).

Scope:
    * Range-band combat with two bands per enemy: `engaged` / `at_range`.
    * Side-based turns: player acts, then enemies react, then repeat.
    * ~6 player actions (attack / careful / heavy / defend / dodge / flee
      + assess + use-environment + lure-into-trap).
    * Status effects on Entity.conditions (prone / stunned / blinded /
      bleeding / behind_cover / afraid / shocked).
    * Enemy behavior profiles via `Entity.state["behavior"]`.
    * Environment hooks: break-glass blinds engaged, push-furniture
      prones, spark-wire shocks.
    * Save/load: state lives on room.state["combat"], round-trips through
      the existing room dict serializer. Old saves load without a combat
      state (None == not in combat).

Out-of-scope for v1:
    * Multi-target attacks.
    * Mini-boss phases (hooks left for v2).
    * Cover/hidden as bands (kept as statuses).
    * Initiative beyond side-based turns.
    * Combat-specific noise calculation beyond reusing room.noise_level.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Bands & statuses ──────────────────────────────────────────────────────

BAND_ENGAGED  = "engaged"     # melee touch range
BAND_AT_RANGE = "at_range"    # anywhere else in the room
BANDS = (BAND_ENGAGED, BAND_AT_RANGE)

# Status keys go into Entity.conditions (already a list[str]). Effects
# are read at decision time; durations live on Entity.state["status_clocks"]
# as a dict[status_key, int] (turns remaining; 0 means "next tick removes").
STATUS_PRONE        = "prone"
STATUS_STUNNED      = "stunned"
STATUS_BLINDED      = "blinded"
STATUS_BLEEDING     = "bleeding"
STATUS_BEHIND_COVER = "behind_cover"
STATUS_AFRAID       = "afraid"
STATUS_SHOCKED      = "shocked"
STATUS_WOUNDED      = "wounded"
# Prompt 21 — new statuses from the elemental system.
STATUS_BURNING      = "burning"     # DOT, can spread to flammables
STATUS_CORRODED     = "corroded"    # AC reduction, persists past combat
STATUS_POISONED     = "poisoned"    # DOT, cured by antidote
STATUS_CHILLED      = "chilled"     # halves DEX-derived stats
# Prompt 26a — maim statuses (body-part breakage).
STATUS_DISARMED     = "disarmed"    # arm broken — main attack -3, drops weapon
STATUS_SLOWED       = "slowed"      # leg broken — to-hit -2, can't approach

_STATUS_PL = {
    STATUS_PRONE:        "przewrócony",
    STATUS_STUNNED:      "ogłuszony",
    STATUS_BLINDED:      "oślepiony",
    STATUS_BLEEDING:     "krwawiący",
    STATUS_BEHIND_COVER: "za osłoną",
    STATUS_AFRAID:       "spanikowany",
    STATUS_SHOCKED:      "porażony",
    STATUS_WOUNDED:      "ranny",
    STATUS_BURNING:      "płonący",
    STATUS_CORRODED:     "skorodowany",
    STATUS_POISONED:     "zatruty",
    STATUS_CHILLED:      "wyziębiony",
    STATUS_DISARMED:     "rozbrojony",
    STATUS_SLOWED:       "okulały",
    # P27.5 (P27-UX-10): "shaken" was emitted by intimidate but never
    # had a PL label — leaked as raw English in the enemy panel.
    "shaken":            "roztrzęsiony",
    "hesitating":        "niezdecydowany",
    "sick":              "chory",
    "encumbered":        "obciążony",
}


def status_label(key: str, lang: str = "pl") -> str:
    if lang == "pl":
        return _STATUS_PL.get(key, key)
    return key


# ── Behavior profiles ─────────────────────────────────────────────────────

BEHAVIOR_BERSERKER = "berserker"   # close, attack hard, ignore wounds
BEHAVIOR_GUARD     = "guard"       # block exit, careful attacks
BEHAVIOR_COWARD    = "coward"      # flee/bargain when wounded
BEHAVIOR_MACHINE   = "machine"     # follow rules, vulnerable to shock+memetics
BEHAVIOR_RANGED    = "ranged"      # maintain distance, ranged attack
BEHAVIOR_SWARM     = "swarm"       # weak alone, gang up

# Default behavior derived from entity tags when nothing explicit on state.
def default_behavior(entity) -> str:
    if entity is None:
        return BEHAVIOR_BERSERKER
    explicit = (entity.state or {}).get("behavior")
    if explicit:
        return explicit
    tags = set(entity.tags or [])
    if "machine" in tags or "drone" in tags or "ai" in tags:
        return BEHAVIOR_MACHINE
    if "guard" in tags or "warden" in tags or "patrol" in tags:
        return BEHAVIOR_GUARD
    if "ranged" in tags or "sniper" in tags or "thrown" in tags:
        return BEHAVIOR_RANGED
    if "swarm" in tags or "small" in tags:
        return BEHAVIOR_SWARM
    if "cowardly" in tags or "scavenger" in tags or "civilian" in tags:
        return BEHAVIOR_COWARD
    return BEHAVIOR_BERSERKER


# ── Combat state ──────────────────────────────────────────────────────────

@dataclass
class CombatState:
    """Lives on RoomState.state["combat"] while combat is active. Empty /
    absent == not in combat."""
    active: bool = True
    round: int = 1
    side: str = "player"            # "player" | "enemies"
    participants: List[int] = field(default_factory=list)   # enemy entity ids
    bands: Dict[int, str] = field(default_factory=dict)     # eid -> band
    assessed: bool = False
    player_defend: int = 0          # +N to next defense roll
    player_dodge: bool = False      # consumed on next incoming attack
    last_action: str = ""
    noise_added: int = 0
    # Prompt 19 — companion advantage. Set by `companion_lure` during
    # combat; consumed by the next player attack roll (+2 to-hit). One
    # bonus per encounter; clears when combat ends.
    companion_advantage_pending: bool = False

    # Prompt 24.5 — selected combat target (drives the right sidebar
    # expanded panel + the arena cursor).
    selected_target_id: Optional[int] = None

    # Prompt 26a — per-target body-zone selection. dict eid → zone_key.
    # When the player attacks, the resolver reads this for the current
    # target. Empty means "torso" (default body shot).
    targeted_zone_by_eid: Dict[int, str] = field(default_factory=dict)

    # P29.0 — when combat started because an entity escalated to
    # threat_level=3 (enraged), the enraged hostiles get one free
    # attack BEFORE the player's next action. Set by threat.bump,
    # consumed by Game._run_enemy_turn (which fires regardless of
    # whose turn it normally is) and reset to False.
    free_attack_pending: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active, "round": self.round, "side": self.side,
            "participants": list(self.participants),
            "bands": dict(self.bands), "assessed": self.assessed,
            "player_defend": self.player_defend,
            "player_dodge": self.player_dodge,
            "last_action": self.last_action,
            "noise_added": self.noise_added,
            "companion_advantage_pending":
                bool(self.companion_advantage_pending),
            "selected_target_id": self.selected_target_id,
            "targeted_zone_by_eid": {str(k): v for k, v
                                     in (self.targeted_zone_by_eid or {}).items()},
            "free_attack_pending": bool(self.free_attack_pending),
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["CombatState"]:
        if not d:
            return None
        cs = cls()
        for k in ("active","round","side","assessed","player_defend",
                  "player_dodge","last_action","noise_added",
                  "companion_advantage_pending","free_attack_pending"):
            if k in d:
                setattr(cs, k, d[k])
        cs.participants = list(d.get("participants", []))
        cs.bands = {int(k): str(v) for k, v in (d.get("bands") or {}).items()}
        sti = d.get("selected_target_id")
        cs.selected_target_id = int(sti) if sti is not None else None
        tzb = d.get("targeted_zone_by_eid") or {}
        cs.targeted_zone_by_eid = {int(k): str(v) for k, v in tzb.items()}
        return cs


# ── Room helpers ──────────────────────────────────────────────────────────

def get_combat(room) -> Optional[CombatState]:
    if room is None:
        return None
    raw = (room.state or {}).get("combat")
    if isinstance(raw, CombatState):
        return raw if raw.active else None
    if isinstance(raw, dict):
        cs = CombatState.from_dict(raw)
        if cs and cs.active:
            room.state["combat"] = cs    # cache the live object
            return cs
    return None


def set_combat(room, cs: Optional[CombatState]) -> None:
    if room is None:
        return
    if room.state is None:
        room.state = {}
    if cs is None:
        room.state.pop("combat", None)
    else:
        room.state["combat"] = cs


def alive_hostiles_in(room) -> List:
    """All hostile, alive entities in the room."""
    out = []
    if room is None:
        return out
    for e in room.entities:
        if e.entity_type not in ("monster", "crawler", "npc"):
            continue
        if not e.is_alive():
            continue
        # Friendly relationships (existing data) -> not hostile.
        rel = (e.state or {}).get("relationship", 0)
        if rel > 0:
            continue
        out.append(e)
    return out


def start_combat(room, world, *, triggered_by: str = "player_attack") -> CombatState:
    """Build a fresh CombatState for the current hostiles in the room."""
    # Prompt 19 audit fix S1: drain pending sponsor hunters into this
    # encounter before banding is set, so they participate from round 1.
    _inject_pending_hunters(room, world)
    hostiles = alive_hostiles_in(room)
    cs = CombatState(active=True, round=1, side="player")
    cs.participants = [e.entity_id for e in hostiles]
    # Default banding: ranged enemies start at_range; everything else engaged.
    for e in hostiles:
        if default_behavior(e) == BEHAVIOR_RANGED:
            cs.bands[e.entity_id] = BAND_AT_RANGE
        else:
            cs.bands[e.entity_id] = BAND_ENGAGED
    cs.last_action = triggered_by
    set_combat(room, cs)
    # P29.53j — auto-trigger deployed traps when combat starts. Bez
    # tego pułapki wymagały od gracza ręcznego `zwabić`, więc rozstawi-
    # ane przed walką po prostu się ignorowało. Teraz pierwsza
    # rozstawiona pułapka łapie pierwszego mob'a od razu na start runy 1.
    try:
        _trigger_deployed_trap_on_combat_start(room, world, cs, hostiles)
    except Exception:
        pass
    return cs


def _trigger_deployed_trap_on_combat_start(room, world, cs, hostiles):
    """Pierwsza nieaktywowana pułapka w pokoju łapie pierwszego
    przeciwnika gdy walka się zaczyna. Pułapka oznaczona triggered=True.
    Komunikat w world.log_msg."""
    traps = (room.state or {}).get("player_traps") or []
    untriggered = [tr for tr in traps if not tr.get("triggered")]
    if not untriggered or not hostiles:
        return
    trap = untriggered[0]
    victim = hostiles[0]
    payload = trap.get("effect") or {}
    dmg = int(payload.get("amount", 3))
    victim.hp = max(0, victim.hp - dmg)
    trap["triggered"] = True
    trap_name = trap.get("name") or trap.get("recipe_key") or "pułapka"
    nm = victim.fallback_name or victim.key or "wróg"
    msg = (f"„{nm}” wpada na rozstawioną {trap_name}: −{dmg} HP. "
           f"Pułapka się wyczerpała.")
    try:
        world.log_msg(msg, "success")
    except Exception:
        pass
    # Bonus efekty zależne od typu pułapki.
    payload_kind = payload.get("type", "")
    if payload_kind == "damage_and_stun":
        add_status(victim, STATUS_STUNNED, 2)
    elif payload_kind == "knockdown":
        add_status(victim, STATUS_PRONE, 2)


def _inject_pending_hunters(room, world) -> None:
    """Spawn each pending sponsor hunter into `room` as a fresh monster
    entity. Pulls from `world.pending_sponsor_hunters` and consumes the
    queue. Hunter entity templates live in
    `content.data.entity_templates.MON`; if the key isn't known the
    entry stays on the queue for a later combat.
    """
    pending = list(getattr(world, "pending_sponsor_hunters", None) or [])
    if not pending or room is None:
        return
    leftover = []
    try:
        from ..content.data.entity_templates import MON, apply_combat_profile
        from .entity import Entity, T_MONSTER
    except Exception:
        return
    for entry in pending:
        hunter_key = str(entry.get("hunter_key") or "")
        if not hunter_key:
            continue
        tmpl = MON.get(hunter_key)
        if not tmpl:
            # Template not authored yet — keep on queue for a later
            # content drop.
            leftover.append(entry)
            continue
        try:
            ent = Entity(
                key=hunter_key,
                entity_type=T_MONSTER,
                fallback_name=tmpl.get("fallback_name", hunter_key),
                hp=int(tmpl.get("hp", 6)),
                max_hp=int(tmpl.get("max_hp", tmpl.get("hp", 6))),
                # P29.65 — kopiuj też ac/atk/dice z szablonu; wcześniej hunter
                # dostawał defaulty Entity (ac10/atk0/1d4), więc autorskie
                # stat-blocki (MOB_COMBAT_STATS) nigdy nie działały dla łowców.
                ac=int(tmpl.get("ac", 10)),
                attack_bonus=int(tmpl.get("attack_bonus", 0)),
                damage_dice=tmpl.get("damage_dice", "1d4"),
                tags=list(tmpl.get("tags") or []) + ["sponsor_hunter"],
                affordances=list(tmpl.get("affordances") or ["attack"]),
                location_id=room.room_id,
            )
            # P29.75 — profil bojowy z szablonu (typ obrażeń/odporności/
            # słabości/behavior); konstruktor wyżej ich nie ustawiał.
            apply_combat_profile(ent, tmpl)
            # P29.65 — łagodna krzywa głębokości (no-op gdy piętro nieznane).
            try:
                from .balance import scale_for_floor
                _fn = int(getattr(getattr(world, "current_floor", None),
                                  "floor_number", 1) or 1)
                scale_for_floor(ent, _fn, home_floor=tmpl.get("floor_min"))
            except Exception:
                pass
            world.register(ent)
            room.entities.append(ent)
        except Exception:
            leftover.append(entry)
    world.pending_sponsor_hunters = leftover


def end_combat(room, world, *, outcome: str = "ended") -> None:
    cs = get_combat(room)
    if cs is None:
        return
    cs.active = False
    cs.last_action = outcome
    set_combat(room, None)


# ── Status helpers ────────────────────────────────────────────────────────

def _clocks_for(entity):
    """Locate the dict that holds status timers on this actor. Entities
    have `state`; Character has `flags` instead. Returns a writable dict
    that lives on the actor and round-trips through save/load."""
    if entity is None:
        return None
    if hasattr(entity, "state"):
        if entity.state is None:
            entity.state = {}
        return entity.state.setdefault("status_clocks", {})
    if hasattr(entity, "flags"):
        if entity.flags is None:
            entity.flags = {}
        return entity.flags.setdefault("status_clocks", {})
    return None


def add_status(entity, key: str, duration: int = 2) -> None:
    if entity is None or not key:
        return
    # P29.36 — species immunity gate. Synthetic blocks poisoned/bleeding,
    # chimera blocks grappled, ferromanta iron_grip blocks disarmed.
    # Applies only to the player (entities with a `species_key` field).
    try:
        if hasattr(entity, "species_key"):
            from . import species_effects as _sp
            if _sp.status_blocked(entity, key):
                return
    except Exception:
        pass
    entity.conditions = entity.conditions or []
    if key not in entity.conditions:
        entity.conditions.append(key)
    clocks = _clocks_for(entity)
    if clocks is None:
        return
    # Refresh duration to the longer of existing / new.
    clocks[key] = max(int(clocks.get(key, 0)), int(duration))


def has_status(entity, key: str) -> bool:
    return bool(entity and key in (entity.conditions or []))


def tick_statuses(entity) -> None:
    """Decrement status clocks; remove statuses whose clock hits 0.
    Applies DOT damage for DOT statuses (bleeding/burning/poisoned).

    Prompt 21: also handles status interactions:
      - burning + chilled present → both clear (steam interaction)
    """
    if entity is None:
        return
    clocks = _clocks_for(entity) or {}
    if not clocks:
        return

    # Status interaction: burning + chilled cancels both.
    if STATUS_BURNING in clocks and STATUS_CHILLED in clocks:
        clocks.pop(STATUS_BURNING, None)
        clocks.pop(STATUS_CHILLED, None)
        if entity.conditions:
            for k in (STATUS_BURNING, STATUS_CHILLED):
                if k in entity.conditions:
                    entity.conditions.remove(k)

    # DOT damage table — keep in sync with damage.STATUS_DOT_PER_TURN.
    _dot = {
        STATUS_BLEEDING: 1,
        STATUS_BURNING:  2,
        STATUS_POISONED: 1,
    }
    drop = []
    for k, v in list(clocks.items()):
        dot = _dot.get(k, 0)
        if dot > 0 and getattr(entity, "is_alive", lambda: True)():
            entity.hp = max(0, entity.hp - dot)
        clocks[k] = v - 1
        if clocks[k] <= 0:
            drop.append(k)
    for k in drop:
        clocks.pop(k, None)
        if entity.conditions and k in entity.conditions:
            entity.conditions.remove(k)


# ── Enemy turn ────────────────────────────────────────────────────────────

@dataclass
class EnemyAction:
    actor_id: int
    kind: str                # "attack" / "approach" / "flee" / "shock" / "wait"
    note: str = ""
    damage: int = 0
    target_status: Optional[str] = None
    target_status_duration: int = 0
    # P26b: faction-aware AI. When set, the attack targets another
    # combat participant (a rival faction) instead of the player.
    # None means "target player" (legacy default).
    target_id: Optional[int] = None


def choose_enemy_action(world, cs: CombatState, enemy) -> EnemyAction:
    """Pick a v1 action for an enemy based on behavior + state + band.
    Deterministic + cheap; no LLM."""
    eid = enemy.entity_id
    band = cs.bands.get(eid, BAND_ENGAGED)
    behavior = default_behavior(enemy)
    hp_ratio = (enemy.hp / max(1, enemy.max_hp)) if enemy.max_hp else 1.0
    # Hard guard: if a status blocks acting, return "wait".
    if has_status(enemy, STATUS_STUNNED) or has_status(enemy, STATUS_PRONE):
        return EnemyAction(actor_id=eid, kind="wait",
                           note="stunned/prone — straci turę")

    if behavior == BEHAVIOR_COWARD and hp_ratio < 0.4:
        return EnemyAction(actor_id=eid, kind="flee",
                           note="cowardly retreat")
    if behavior == BEHAVIOR_RANGED:
        if band == BAND_ENGAGED:
            # Try to back away.
            return EnemyAction(actor_id=eid, kind="back_off",
                               note="ranged enemy backs off")
        return EnemyAction(actor_id=eid, kind="attack",
                           damage=_enemy_attack_damage(enemy, ranged=True),
                           note="ranged shot")
    if behavior == BEHAVIOR_MACHINE:
        if has_status(enemy, STATUS_SHOCKED):
            return EnemyAction(actor_id=eid, kind="wait", note="shock recovery")
        if band == BAND_AT_RANGE:
            return EnemyAction(actor_id=eid, kind="approach",
                               note="machine closes distance")
        return EnemyAction(actor_id=eid, kind="attack",
                           damage=_enemy_attack_damage(enemy))
    if behavior == BEHAVIOR_GUARD:
        # Guards block the exit, hit but conservative.
        if band == BAND_AT_RANGE:
            return EnemyAction(actor_id=eid, kind="approach",
                               note="guard advances")
        return EnemyAction(actor_id=eid, kind="attack",
                           damage=max(1, _enemy_attack_damage(enemy) - 1),
                           note="guard strikes")
    if behavior == BEHAVIOR_SWARM:
        # Swarm always engages; small damage.
        if band == BAND_AT_RANGE:
            return EnemyAction(actor_id=eid, kind="approach")
        return EnemyAction(actor_id=eid, kind="attack",
                           damage=max(1, _enemy_attack_damage(enemy) - 2))
    # Berserker default.
    if band == BAND_AT_RANGE:
        return EnemyAction(actor_id=eid, kind="approach", note="berserker charges")
    action = EnemyAction(actor_id=eid, kind="attack",
                       damage=_enemy_attack_damage(enemy, heavy=True),
                       note="berserker hit")
    # P26b: faction-aware retarget.
    rival_id = _pick_rival_target(world, cs, enemy)
    if rival_id is not None:
        action.target_id = rival_id
        action.note = action.note + " → rywal"
    return action


def _faction_tags(entity) -> set:
    """Extract `faction:X` tags from an entity. Returns the set of
    faction keys (without the prefix). Empty set means "no faction" —
    these entities don't participate in cross-faction conflict (they
    only ever target the player)."""
    if entity is None:
        return set()
    out = set()
    for t in (getattr(entity, "tags", []) or []):
        if t.startswith("faction:"):
            out.add(t.split(":", 1)[1])
    return out


def _pick_rival_target(world, cs: "CombatState", enemy) -> Optional[int]:
    """If `enemy` belongs to a faction AND another live participant
    belongs to a different faction, return that rival's entity_id.
    Probability gating keeps the player as primary target most of the
    time — rivalry kicks in ~30% of relevant turns, scaling with round
    count so longer fights see more cross-fire (DCC-faithful drama).
    """
    if world is None or cs is None or enemy is None:
        return None
    my_factions = _faction_tags(enemy)
    if not my_factions:
        return None
    # Scan participants for a rival.
    rivals = []
    for eid in cs.participants:
        if eid == enemy.entity_id:
            continue
        other = world.get(eid)
        if other is None or not getattr(other, "is_alive", lambda: True)():
            continue
        other_f = _faction_tags(other)
        if not other_f:
            continue
        # Different faction sets and no overlap means rivals.
        if my_factions.isdisjoint(other_f):
            rivals.append(eid)
    if not rivals:
        return None
    # 30% base chance to swap, scales up by 5% per round capped at 60%.
    import random as _r
    p = min(0.6, 0.30 + 0.05 * (cs.round - 1))
    if _r.random() > p:
        return None
    return _r.choice(rivals)


def _enemy_attack_damage(enemy, *, ranged: bool = False,
                         heavy: bool = False) -> int:
    """Roll the entity's damage dice, with rough modifiers.

    P29.65: routes through the shared `engine.dice.roll_spec` roller. The old
    inline `split("d")` + `int(sides)` threw on the scaler's `'NdS+B'` format
    (e.g. `int("8+13")`) and silently fell back to `1d4`, so every scaled mob
    dealt ~`1d4` instead of its real dice — the core of the dead-damage bug.
    Damage is now DICE-ONLY: `attack_bonus` is the to-hit stat and is no longer
    folded into the damage roll (that double-dip inflated both axes at once)."""
    import random as _r
    from .dice import roll_spec
    dmg = roll_spec(enemy.damage_dice or "1d4", _r)
    if heavy:  dmg += 1
    if ranged: dmg = max(1, dmg - 1)
    # Statuses on the enemy itself reduce its output.
    if has_status(enemy, STATUS_BLINDED): dmg = max(1, dmg - 2)
    if has_status(enemy, STATUS_AFRAID):  dmg = max(1, dmg - 1)
    # P29.53m — graduated body damage: damaged/crippled limbs
    # subtract from the damage roll even if not yet broken. Broken
    # parts route through STATUS_DISARMED handled at to-hit roll.
    try:
        from ..content.data import body_plans as _bp
        mods = _bp.body_combat_mods(enemy)
        dmg = max(1, dmg - int(mods.get("attack_dmg_delta", 0)))
    except Exception:
        pass
    return max(1, dmg)


# ── Public summary helpers (for assess + UI) ─────────────────────────────

def describe_band(cs: CombatState, enemy) -> str:
    band = cs.bands.get(enemy.entity_id, BAND_ENGAGED)
    if band == BAND_ENGAGED:
        return "w zwarciu"
    return "w oddali"


def describe_threat(enemy) -> str:
    ratio = (enemy.hp / max(1, enemy.max_hp)) if enemy.max_hp else 1.0
    if ratio > 0.66:  return "wygląda krzepko"
    if ratio > 0.33:  return "wygląda na ranionego"
    if ratio > 0.0:   return "ledwo trzyma się na nogach"
    return "padł"


def list_status_pl(entity) -> str:
    cond = [status_label(c, "pl") for c in (entity.conditions or [])
            if c in _STATUS_PL]
    return ", ".join(cond) if cond else "—"
