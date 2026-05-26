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

    # Prompt 20: drain scheduled encounters — emit T-15/T-5/T-1 warnings,
    # fire any that came due. Safe when no encounters are queued.
    try:
        from . import encounter as _enc
        _enc.tick_due(world, minutes)
    except Exception:
        pass

    # Prompt 21: slow-decay status clocks out of combat. Burning /
    # poisoned / bleeding / corroded keep ticking at half rate during
    # exploration. Combat's own tick_statuses handles in-combat pace.
    try:
        from . import damage as _dmg
        _dmg.slow_decay_tick(world, minutes)
    except Exception:
        pass

    # Prompt 26b: noise mechanic — decay, propagate, threshold-spawn.
    # Per-room noise levels are bumped throughout combat / salvage /
    # break handlers; this tick is where they DO something.
    try:
        from . import noise as _noise
        _noise.tick_noise(world, minutes)
    except Exception:
        pass

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
    """Called when deadline_remaining_minutes hits 0. Sets the world
    flag `floor_collapsed` which `Game.update` polls to switch state to
    DEFEAT. A separate "escape-at-exit" check could land in P31 (run
    summary + meta progression); for now collapse = run over.
    """
    if not getattr(world, "current_floor", None):
        return
    flags = getattr(world, "flags", None)
    if flags is None:
        # WorldState doesn't currently carry a top-level flags dict;
        # store on the floor instead.
        st = getattr(world.current_floor, "state", None)
        if st is None:
            world.current_floor.state = {}
            st = world.current_floor.state
        st["collapsed"] = True
    else:
        flags["floor_collapsed"] = True
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
