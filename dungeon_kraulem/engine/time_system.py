"""Time system — minute-based clock with floor deadline."""
from ..config import MINUTES_PER_DAY
from ..ui.lang import t


def advance(world, minutes: int):
    """Advance the floor clock and run any time-bound events."""
    if not world.current_floor or minutes <= 0:
        return
    f = world.current_floor
    prev_day = f.day_number()
    prev_remaining = f.deadline_remaining_minutes()
    # Snapshot for memetic propagation tick (every ~2h of game time).
    prev_2h_bucket = f.current_minute // 120
    f.current_minute += minutes

    # Prompt 18: audience idle decay tick. Safe-noop when audience module
    # is missing (e.g. tests stubbing the engine).
    try:
        from . import audience as _aud
        _aud.tick_decay(world, minutes)
    except Exception:
        pass

    # P29.0 — encounter scheduling REMOVED. The "alarm → patrol arrives
    # after N minutes" pipeline is gone. The dungeon doesn't send
    # patrols; the thing already in the room is what wakes up.
    # See engine/threat.py for the replacement mechanic.

    # Prompt 21: slow-decay status clocks out of combat. Burning /
    # poisoned / bleeding / corroded keep ticking at half rate during
    # exploration. Combat's own tick_statuses handles in-combat pace.
    try:
        from . import damage as _dmg
        _dmg.slow_decay_tick(world, minutes)
    except Exception:
        pass

    # P29.0 — threat decay. Quiet rooms cool down over time, latches
    # clear when thresholds drop below their levels. Replaces noise
    # propagation + patrol-spawn from P26b.
    try:
        from . import threat as _threat
        if f and getattr(f, "rooms", None):
            for r in list(f.rooms.values()):
                _threat.decay(world, r, minutes)
    except Exception:
        pass

    # P29.30 — corpse decay tick. Fields decay_min_remaining +
    # smell_budget were set on corpse creation since P24 but never
    # decremented. Now they actually count down; expired corpses
    # lose their salvage/butcher affordances + gain "decomposed" tag.
    try:
        from . import corpses as _corpses
        _corpses.tick_decay(world, minutes)
    except Exception:
        pass

    # P29.18 — show-director interventions. One roll per tick; the
    # module itself gates by audience band, per-floor cap, and an
    # 8-minute cooldown.
    # P29.32 — silent swallow now goes through _debug.swallow so
    # devs can flip DK_DEBUG=1 and see what's actually breaking.
    from ._debug import swallow as _swallow
    with _swallow("show_director.maybe_fire"):
        from . import show_director as _sd
        _sd.maybe_fire(world)

    # P29.18 — proxy-war event check. Cheap to call every tick; the
    # module owns the per-pair cooldown and per-floor cap, so this
    # only actually fires when conditions converge.
    with _swallow("proxy_wars.maybe_fire"):
        from . import proxy_wars as _pw
        _pw.maybe_fire(world)

    # P29.20 — companion idle chatter. Module owns its own cooldown
    # (~25 min between idle lines), so calling every tick is safe.
    with _swallow("companion_voice.maybe_say[idle]"):
        from . import companion_voice as _cv
        _cv.maybe_say(world, "idle")

    # Day-change event
    if f.day_number() != prev_day:
        world.log_msg(_day_change_line(f), "syndicate")

    # Prompt 07: ambient belief-seed propagation tick.
    new_2h_bucket = f.current_minute // 120
    if new_2h_bucket != prev_2h_bucket:
        try:
            from ..systems import memetics
            events = memetics.process_belief_seeds(world, minutes, trigger="tick")
            for ev in events:
                kind = ev.get("kind")
                if kind == "rumor":
                    world.log_msg(t("feedback_belief_spreads",
                                    fallback="Plotka, którą zasiałeś, znajduje nowe usta."),
                                  "syndicate")
                elif kind == "backlash":
                    world.log_msg(t("feedback_belief_distorts",
                                    fallback="Twój pomysł zmienił właściciela — i sens."),
                                  "warn")
                elif kind == "burned_out":
                    world.log_msg(t("feedback_belief_burned",
                                    fallback="Jeden z twoich pomysłów wypalił się i zostawił po sobie ciszę."),
                                  "normal")
        except Exception:
            # Memetics is auxiliary; never break time advancement.
            pass

    # Deadline warnings — P26b adds sub-hour drama (30/10/0 min) +
    # sponsor reactions on threshold cross.
    remaining = f.deadline_remaining_minutes()
    DEADLINE_THRESHOLDS = [
        (MINUTES_PER_DAY * 7, "warn_7d",
         "Termin: pozostało 7 dni.",                   "warn"),
        (MINUTES_PER_DAY * 3, "warn_3d",
         "Termin: pozostało 3 dni.",                   "warn"),
        (MINUTES_PER_DAY,     "warn_1d",
         "Termin: pozostała doba.",                    "warn"),
        (60,                  "warn_1h",
         "Termin: pozostała godzina.",                 "warn"),
        (30,                  "warn_30m",
         "Termin: pół godziny. Loch zaczyna trzeszczeć.", "danger"),
        (10,                  "warn_10m",
         "Termin: dziesięć minut. Pajęczyny pyłu cementowego.", "danger"),
    ]
    for threshold, key, fallback_msg, severity in DEADLINE_THRESHOLDS:
        if prev_remaining > threshold >= remaining:
            world.log_msg(t(f"time_{key}", fallback=fallback_msg), severity)
            # Sponsor reaction on threshold cross — drives audience and
            # sponsor attention. Final-hour thresholds bump harder.
            try:
                from . import sponsors as _sp
                weight = 3 if threshold <= 60 else 1
                _sp.note_player_tag(world, "deadline_pressure", weight=weight)
            except Exception:
                pass

    if remaining == 0 and prev_remaining > 0:
        world.log_msg(t("time_deadline_missed",
                        fallback="Termin minął. Loch zamyka piętro. "
                                 "Strop pęka."),
                      "danger")
        # P26b: trigger the floor-collapse path. Player_at_exit allows
        # last-second escape; otherwise the game ends.
        try:
            _trigger_floor_collapse(world)
        except Exception:
            pass


def _trigger_floor_collapse(world) -> None:
    """Called when deadline_remaining_minutes hits 0. Sets the floor
    state flag `collapsed` which `Game.update` polls to switch state
    to DEFEAT.

    P29.24 — escape-at-exit: if the player is already in a room flagged
    as the floor exit (actual_type == "boss" with exits_unlocked, OR
    a room tagged "exit") at the moment of collapse, they descend to
    the next floor instead of dying. The descent path is driven by
    `floor.state["collapse_descend_requested"]` so Game.update can run
    the existing _descend_or_win path on the next tick without
    crossing engine layers here.
    """
    if not getattr(world, "current_floor", None):
        return
    floor = world.current_floor
    if not hasattr(floor, "state") or floor.state is None:
        floor.state = {}
    # P29.24 — escape check. Player_at_exit + unlocked → flag descent.
    player_room = floor.current_room() if hasattr(
        floor, "current_room") else None
    at_exit = False
    if player_room is not None:
        room_tags = set(getattr(player_room, "sensory_tags", None) or []) | \
                    ({player_room.actual_type} if player_room.actual_type else set())
        # An "exit" tag, an "objective" tag, or being in the boss room
        # after exits_unlocked all count as "you found the way down."
        if ("exit" in room_tags or
                ("objective" in room_tags and
                 bool(getattr(floor, "exits_unlocked", False)))):
            at_exit = True
        # Also accept: actual_type=="boss" + exits already unlocked
        # (you killed the boss and were about to descend anyway).
        if player_room.actual_type == "boss" and \
                bool(getattr(floor, "exits_unlocked", False)):
            at_exit = True
    if at_exit:
        floor.state["collapse_descend_requested"] = True
        world.log_msg(t("time_collapse_escape",
                        fallback="Strop pęka, ale jesteś już przy "
                                 "drzwiach. Wciskasz się w lukę. "
                                 "Piętro za tobą znika."),
                      "success")
        return
    # No escape — game over.
    floor.state["collapsed"] = True
    world.log_msg(t("time_collapse_final",
                    fallback="Sufit się zapada. To koniec twojej trasy."),
                  "danger")


def format_clock(world) -> str:
    if not world.current_floor:
        return ""
    f = world.current_floor
    h = (f.current_minute // 60) % 24
    m = f.current_minute % 60
    return f"D{f.day_number()} {h:02d}:{m:02d}"


def format_deadline(world) -> str:
    if not world.current_floor:
        return ""
    rem = world.current_floor.deadline_remaining_minutes()
    d = rem // MINUTES_PER_DAY
    h = (rem % MINUTES_PER_DAY) // 60
    return f"{d}d {h}h"


def _day_change_line(floor) -> str:
    day = floor.day_number()
    return t("time_day_change", fallback=f"=== Dzień {day} ===", day=day)
