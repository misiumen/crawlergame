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

_STATUS_PL = {
    STATUS_PRONE:        "przewrócony",
    STATUS_STUNNED:      "ogłuszony",
    STATUS_BLINDED:      "oślepiony",
    STATUS_BLEEDING:     "krwawiący",
    STATUS_BEHIND_COVER: "za osłoną",
    STATUS_AFRAID:       "spanikowany",
    STATUS_SHOCKED:      "porażony",
    STATUS_WOUNDED:      "ranny",
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
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["CombatState"]:
        if not d:
            return None
        cs = cls()
        for k in ("active","round","side","assessed","player_defend",
                  "player_dodge","last_action","noise_added",
                  "companion_advantage_pending"):
            if k in d:
                setattr(cs, k, d[k])
        cs.participants = list(d.get("participants", []))
        cs.bands = {int(k): str(v) for k, v in (d.get("bands") or {}).items()}
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
    return cs


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
    Bleeding deals small damage as the clock ticks."""
    if entity is None:
        return
    clocks = _clocks_for(entity) or {}
    if not clocks:
        return
    drop = []
    for k, v in list(clocks.items()):
        if k == STATUS_BLEEDING and getattr(entity, "is_alive", lambda: True)():
            entity.hp = max(0, entity.hp - 1)
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
    return EnemyAction(actor_id=eid, kind="attack",
                       damage=_enemy_attack_damage(enemy, heavy=True),
                       note="berserker hit")


def _enemy_attack_damage(enemy, *, ranged: bool = False,
                         heavy: bool = False) -> int:
    """Roll the entity's damage dice + bonus, with rough modifiers."""
    import random as _r
    # Parse damage_dice like "1d4" / "2d6"
    dice = enemy.damage_dice or "1d4"
    try:
        n, sides = dice.lower().split("d")
        n = int(n or "1"); sides = int(sides)
    except (ValueError, AttributeError):
        n, sides = 1, 4
    roll = sum(_r.randint(1, max(1, sides)) for _ in range(max(1, n)))
    dmg = roll + int(getattr(enemy, "attack_bonus", 0) or 0)
    if heavy:  dmg += 1
    if ranged: dmg = max(1, dmg - 1)
    # Statuses on the enemy itself reduce its output.
    if has_status(enemy, STATUS_BLINDED): dmg = max(1, dmg - 2)
    if has_status(enemy, STATUS_AFRAID):  dmg = max(1, dmg - 1)
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
