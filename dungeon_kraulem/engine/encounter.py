"""Prompt 20 — Scheduled encounter system (alarm → prep → arrival).

When the player triggers an alarm (or any future "something is coming"
event), a `ScheduledEncounter` is appended to
`floor.scheduled_encounters`. The time system ticks the list each
minute-advance:

  - On every advance, narrator warnings emit at the alarm's configured
    `warnings_at` minutes (T-15 / T-5 / T-1 etc.).
  - When `floor.current_minute >= fires_at_minute`, `fire()` runs:
        * Spawn the alarm's hostile_keys as entities in the encounter's
          room.
        * For each arriver, roll against every armed trap in the room:
          on success the trap deals damage / applies a status / is
          consumed (state.armed = False). Each trap fires at most
          once per encounter.
        * If the player is in the room AND not hidden:
              kick `combat.start_combat(...)` — but with the arrivers
              already pre-damaged/conditioned.
          If the player IS hidden: arrivers search briefly, traps still
          fire, then they leave with no combat. Stays narrative.
          If the player isn't in the room at all: arrivers occupy it
          (so future entries to that room trigger combat normally).
  - Each fired encounter emits the alarm's `sponsor_tags` via
    `engine.sponsors.note_player_tag` so the sponsor system reacts.

The module deliberately stays small: the alarm content table lives in
`content/data/encounter_definitions.py`; combat-side trap rolls live in
`engine.combat`; the narrator lines come from `systems.narrator` /
locale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import random

from ..content.data.encounter_definitions import (
    get_alarm_definition, ALARM_ENCOUNTERS,
)


# ── Data model ────────────────────────────────────────────────────────────

@dataclass
class ScheduledEncounter:
    """One pending encounter on the floor's scheduled_encounters list.

    `warnings_emitted` is a set of minute-offsets (e.g. {15, 5}) we've
    already fired warning lines for, so a single 60-min advance doesn't
    re-emit the T-15 warning over and over.
    """
    alarm_type: str = "default"
    room_id: str = ""
    fires_at_minute: int = 0
    hostile_keys: List[str] = field(default_factory=list)
    warnings_at: List[int] = field(default_factory=list)
    warnings_emitted: Set[int] = field(default_factory=set)
    source: str = "alarm"
    audience_bump: int = 0
    sponsor_tags: List[str] = field(default_factory=list)
    log_intro_pl: str = ""
    log_intro_en: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alarm_type": self.alarm_type,
            "room_id": self.room_id,
            "fires_at_minute": int(self.fires_at_minute),
            "hostile_keys": list(self.hostile_keys),
            "warnings_at": list(self.warnings_at),
            "warnings_emitted": list(self.warnings_emitted),
            "source": self.source,
            "audience_bump": int(self.audience_bump),
            "sponsor_tags": list(self.sponsor_tags),
            "log_intro_pl": self.log_intro_pl,
            "log_intro_en": self.log_intro_en,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScheduledEncounter":
        return cls(
            alarm_type=str(d.get("alarm_type") or "default"),
            room_id=str(d.get("room_id") or ""),
            fires_at_minute=int(d.get("fires_at_minute") or 0),
            hostile_keys=list(d.get("hostile_keys") or []),
            warnings_at=list(d.get("warnings_at") or []),
            warnings_emitted=set(d.get("warnings_emitted") or []),
            source=str(d.get("source") or "alarm"),
            audience_bump=int(d.get("audience_bump") or 0),
            sponsor_tags=list(d.get("sponsor_tags") or []),
            log_intro_pl=str(d.get("log_intro_pl") or ""),
            log_intro_en=str(d.get("log_intro_en") or ""),
        )


# ── Public API ────────────────────────────────────────────────────────────

def schedule(world, room_id: str, alarm_type: str = "default",
             *, source: str = "alarm") -> Optional[ScheduledEncounter]:
    """Schedule an encounter to arrive in the given room after the alarm
    type's delay. Logs the intro line. Bumps audience. Emits the
    alarm's sponsor tags. Returns the scheduled object (or None if the
    floor is missing).

    Idempotency: if an encounter is already scheduled for the same room
    from the same `source`, the existing one wins — we don't double-up.
    The player can't re-trigger the same alarm twice and double their
    response.
    """
    if world is None or getattr(world, "current_floor", None) is None:
        return None
    floor = world.current_floor
    if not room_id:
        return None
    queue = _queue(floor)

    # Idempotency check.
    for existing in queue:
        if (existing.room_id == room_id and
                existing.source == source and
                existing.alarm_type == alarm_type):
            return existing

    defn = get_alarm_definition(alarm_type)
    delay = int(defn.get("delay_minutes") or 30)
    enc = ScheduledEncounter(
        alarm_type=alarm_type,
        room_id=room_id,
        fires_at_minute=int(floor.current_minute) + delay,
        hostile_keys=list(defn.get("hostile_keys") or []),
        warnings_at=list(defn.get("warnings_at") or [15, 5, 1]),
        source=source,
        audience_bump=int(defn.get("audience_bump") or 0),
        sponsor_tags=list(defn.get("sponsor_tags") or []),
        log_intro_pl=str(defn.get("log_intro_pl") or ""),
        log_intro_en=str(defn.get("log_intro_en") or ""),
    )
    queue.append(enc)

    # Intro line + audience + sponsor tags.
    intro = enc.log_intro_pl or "Alarm. Coś nadchodzi."
    if hasattr(world, "log"):
        world.log.append((intro, "warn"))
    try:
        from . import audience as _aud
        if enc.audience_bump:
            _aud.change_audience(world, enc.audience_bump,
                                 source=f"alarm:{alarm_type}")
    except Exception:
        pass
    try:
        from . import sponsors as _sp
        for tag in enc.sponsor_tags:
            _sp.note_player_tag(world, tag, weight=1)
    except Exception:
        pass
    return enc


def tick_due(world, minutes_elapsed: int) -> None:
    """Called by time_system.advance after the clock bumps. Emits any
    pending warnings and fires any encounters whose time has come.

    Safe when there's no current_floor or when the queue is empty."""
    if world is None or getattr(world, "current_floor", None) is None:
        return
    floor = world.current_floor
    queue = _queue(floor)
    if not queue:
        return

    now = int(floor.current_minute)
    still_pending: List[ScheduledEncounter] = []
    for enc in queue:
        remaining = enc.fires_at_minute - now
        # Emit warnings whose threshold we've crossed (and not yet
        # emitted) regardless of whether the encounter fires this tick.
        for w in enc.warnings_at:
            if w in enc.warnings_emitted:
                continue
            if remaining <= w and remaining > 0:
                _emit_warning(world, enc, w)
                enc.warnings_emitted.add(w)
        if remaining <= 0:
            fire(world, enc)
        else:
            still_pending.append(enc)
    # Persist only the unfired encounters.
    floor.scheduled_encounters = still_pending


def fire(world, enc: ScheduledEncounter) -> None:
    """Materialize the encounter NOW. Spawn arrivers, run trap rolls,
    start combat or narrate hidden/empty outcomes.

    Clears the player's `hidden_for_encounter` flag at the end so a
    follow-up alarm requires a fresh hide attempt.
    """
    floor = world.current_floor
    room = floor.rooms.get(enc.room_id) if floor else None
    if room is None:
        return

    try:
        arrivers = _spawn_arrivers(world, room, enc.hostile_keys)
        if not arrivers:
            if hasattr(world, "log"):
                world.log.append((
                    "(Patrol miał przyjść, ale gdzieś się zgubił. "
                    "Sponsor jest niepocieszony.)",
                    "system"))
            return

        _resolve_pre_combat_traps(world, room, arrivers)
        arrivers = [a for a in arrivers if a.is_alive()]

        player_room_id = (floor.current_room_id or "")
        player_present = (player_room_id == enc.room_id)
        player_hidden = _player_is_hidden(world)

        if not arrivers:
            if hasattr(world, "log"):
                world.log.append((
                    "Pułapki zrobiły swoje. Nikt już tu nie wchodzi.",
                    "success"))
            _emit_post_encounter_tags(world, enc, outcome="traps_only")
            return

        if player_present and not player_hidden:
            from . import combat as _cmb
            _cmb.start_combat(room, world,
                              triggered_by=f"alarm:{enc.alarm_type}")
            if hasattr(world, "log"):
                world.log.append((
                    f"Patrol wpada: "
                    f"{', '.join(a.display_name() for a in arrivers)}.",
                    "danger"))
            _emit_post_encounter_tags(world, enc, outcome="combat")
            return

        if player_present and player_hidden:
            if hasattr(world, "log"):
                world.log.append((
                    "Słyszysz ich kroki. Szukają. Nie znajdują. "
                    "Po chwili wychodzą.",
                    "success"))
            _emit_post_encounter_tags(world, enc, outcome="hidden_success")
            return
    finally:
        # Hidden flag is per-encounter — clear it now so the next alarm
        # requires a fresh hide attempt.
        _clear_hidden_flag(world)

    # Player not in the room. Arrivers occupy it; entering later starts
    # combat normally.
    if hasattr(world, "log"):
        world.log.append((
            f"Słychać dalekie głosy w pokoju, z którego uciekłeś. "
            f"Patrol go zajął.",
            "warn"))
    _emit_post_encounter_tags(world, enc, outcome="player_fled")
    _clear_hidden_flag(world)


def _clear_hidden_flag(world) -> None:
    """Drop the per-encounter hidden flag so the next alarm requires a
    fresh hide. Called at the end of every fire()."""
    char = getattr(world, "character", None)
    if char is None or not getattr(char, "flags", None):
        return
    char.flags.pop("hidden_for_encounter", None)


def time_until_next(world) -> Optional[int]:
    """Convenience for the topbar: minutes until the soonest scheduled
    encounter in the player's current room, or None if none. Used by
    the warning indicator."""
    if world is None or getattr(world, "current_floor", None) is None:
        return None
    floor = world.current_floor
    if not floor.current_room_id:
        return None
    queue = _queue(floor)
    soonest = None
    for enc in queue:
        if enc.room_id != floor.current_room_id:
            continue
        remaining = enc.fires_at_minute - int(floor.current_minute)
        if remaining < 0:
            remaining = 0
        if soonest is None or remaining < soonest:
            soonest = remaining
    return soonest


# ── Internals ─────────────────────────────────────────────────────────────

def _queue(floor) -> List[ScheduledEncounter]:
    """Return the live encounter queue, initializing if absent."""
    q = getattr(floor, "scheduled_encounters", None)
    if q is None:
        floor.scheduled_encounters = []
        q = floor.scheduled_encounters
    return q


def _emit_warning(world, enc: ScheduledEncounter, minutes_left: int) -> None:
    """Player-facing warning line at T-N minutes."""
    if not hasattr(world, "log"):
        return
    if minutes_left >= 30:
        msg = (f"Słyszysz przez radio: „Patrol przybywa za ~{minutes_left} min.” "
               f"Masz jeszcze czas.")
    elif minutes_left >= 10:
        msg = f"~{minutes_left} minut do przybycia patrolu."
    elif minutes_left >= 3:
        msg = f"Niedługo będą tu. ~{minutes_left} min."
    else:
        msg = "Tuż-tuż. Słyszysz kroki."
    world.log.append((msg, "warn"))


def _spawn_arrivers(world, room, hostile_keys: List[str]):
    """Materialize each hostile_key as an Entity in `room`. Skip unknown
    keys silently. Returns the list of newly-spawned Entity objects."""
    try:
        from ..content.data.entity_templates import MON
        from .entity import Entity, T_MONSTER
    except Exception:
        return []
    arrivers = []
    for key in hostile_keys:
        tmpl = MON.get(key)
        if not tmpl:
            continue
        ent = Entity(
            key=key,
            entity_type=T_MONSTER,
            name_key=tmpl.get("name_key", ""),
            fallback_name=tmpl.get("fallback_name", key),
            desc_key=tmpl.get("desc_key", ""),
            fallback_desc=tmpl.get("fallback_desc", ""),
            tags=list(tmpl.get("tags") or []) + ["alarm_responder"],
            affordances=list(tmpl.get("affordances") or ["attack"]),
            hp=int(tmpl.get("hp", 8)),
            max_hp=int(tmpl.get("max_hp", tmpl.get("hp", 8))),
            ac=int(tmpl.get("ac", 11)),
            attack_bonus=int(tmpl.get("attack_bonus", 2)),
            damage_dice=str(tmpl.get("damage_dice", "1d4")),
            location_id=room.room_id,
            visible=True,
            discovered=True,
        )
        world.register(ent)
        room.entities.append(ent)
        arrivers.append(ent)
    return arrivers


def _resolve_pre_combat_traps(world, room, arrivers) -> None:
    """Consume any un-triggered traps the player deployed via
    `_attempt_deploy` (which stores them on `room.state["player_traps"]`
    with a rich `effect` dict). Each trap fires at most once and is
    matched against the next still-alive arriver.

    Effect kinds supported (matching game.py:_attempt_deploy):
      * "damage"            — flat HP damage
      * "damage_and_stun"   — HP damage + `stunned` condition
      * "knockdown"         — apply `prone`
      * "obscure"           — apply `blinded`
    """
    from ..ui.lang import t
    if not room.state:
        return
    traps = list(room.state.get("player_traps") or [])
    if not traps:
        return
    rng = random.Random()

    for trap in traps:
        if trap.get("triggered"):
            continue
        live = [a for a in arrivers if a.is_alive()]
        if not live:
            break
        target = live[0]
        # Trap "level" set at deploy ("success" / "critical_success" /
        # "partial_success") affects to-hit. Critical deploys auto-hit;
        # partial-success deploys have a 50/50 chance to fire.
        level = trap.get("level", "success")
        if level == "critical_success":
            hit = True
        elif level == "partial_success":
            hit = rng.random() < 0.5
        else:
            # Standard deploy: DC 11 vs target's attack_bonus (used as
            # a stand-in for their general agility).
            roll = rng.randint(1, 20) + int(target.attack_bonus or 0)
            hit = roll < 11   # low rolls = the trap surprised them

        effect = trap.get("effect") or {}
        trap_name = trap.get("display_name", "pułapka")
        if hit:
            dmg = int(effect.get("amount", 0)) if effect.get("type") in (
                "damage", "damage_and_stun") else 0
            if dmg > 0:
                target.hp = max(0, target.hp - dmg)
            # Conditions per effect type.
            condition = None
            if effect.get("type") == "damage_and_stun":
                condition = "stunned"
            elif effect.get("type") == "knockdown":
                condition = "prone"
            elif effect.get("type") == "obscure":
                condition = "blinded"
            if condition and condition not in target.conditions:
                target.conditions.append(condition)
            trap["triggered"] = True
            # Compose feedback line.
            parts = []
            if dmg > 0:
                parts.append(f"{dmg} obrażeń")
            if condition:
                parts.append(condition)
            payload = ", ".join(parts) or "trafia"
            line = t("encounter_trap_fired",
                     fallback=(f"Pułapka „{trap_name}” trafia "
                               f"„{target.display_name()}” ({payload})."))
            if hasattr(world, "log"):
                world.log.append((line, "success"))
            # Sponsor tag emission per trap hit.
            try:
                from . import sponsors as _sp
                _sp.note_player_tag(world, "clever_craft", weight=1)
                if not target.is_alive():
                    _sp.note_player_tag(world, "env_kill", weight=1)
            except Exception:
                pass
        else:
            trap["triggered"] = True
            line = t("encounter_trap_missed",
                     fallback=(f"Pułapka „{trap_name}” pęka bezskutecznie. "
                               f"„{target.display_name()}” omija."))
            if hasattr(world, "log"):
                world.log.append((line, "warn"))


def _player_is_hidden(world) -> bool:
    """Player has the `hidden` condition (set by a successful `hide`
    attempt in pre-combat). Both Character.conditions and an explicit
    flag are checked, for forward-compat with however hide gets wired."""
    char = getattr(world, "character", None)
    if char is None:
        return False
    if "hidden" in (getattr(char, "conditions", []) or []):
        return True
    if (getattr(char, "flags", None) or {}).get("hidden_for_encounter"):
        return True
    return False


def _emit_post_encounter_tags(world, enc: ScheduledEncounter,
                              outcome: str) -> None:
    """After an encounter resolves, push outcome-specific sponsor tags
    so Kanał 7 / Sport / Czarny Rynek / etc. react. Outcome strings:
        combat         — real fight starting
        hidden_success — player stayed concealed
        traps_only     — traps cleaned them up before any fight
        player_fled    — player left the room beforehand
    """
    try:
        from . import sponsors as _sp
    except Exception:
        return
    if outcome == "hidden_success":
        _sp.note_player_tag(world, "hide", weight=1)
    elif outcome == "player_fled":
        _sp.note_player_tag(world, "flee", weight=1)
    elif outcome == "traps_only":
        _sp.note_player_tag(world, "clever_craft", weight=2)
        _sp.note_player_tag(world, "spectacle",    weight=1)
    elif outcome == "combat":
        _sp.note_player_tag(world, "combat",       weight=1)
        _sp.note_player_tag(world, "spectacle",    weight=1)


def _roll_dice(spec: str, rng: random.Random) -> int:
    """Parse and roll '1d6+2' / '2d4' / '3' spec. Robust to garbage."""
    if not spec:
        return 0
    spec = spec.strip().lower().replace(" ", "")
    if spec.isdigit():
        return int(spec)
    plus = 0
    if "+" in spec:
        spec, plus_s = spec.split("+", 1)
        try:
            plus = int(plus_s)
        except ValueError:
            plus = 0
    if "d" not in spec:
        return plus
    try:
        n, sides = spec.split("d", 1)
        n = int(n or "1")
        sides = int(sides)
    except ValueError:
        return plus
    if n <= 0 or sides <= 0:
        return plus
    return sum(rng.randint(1, sides) for _ in range(n)) + plus


# ── Save/load helpers (used by world.py serializer) ───────────────────────

def serialize_queue(floor) -> List[Dict[str, Any]]:
    return [e.to_dict() for e in _queue(floor)]


def deserialize_queue(floor, raw: List[Dict[str, Any]]) -> None:
    floor.scheduled_encounters = [
        ScheduledEncounter.from_dict(d) for d in (raw or [])
    ]
