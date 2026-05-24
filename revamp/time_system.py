"""Time system — minute-based clock with floor deadline."""
from .config import MINUTES_PER_DAY
from .lang import t


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

    # Day-change event
    if f.day_number() != prev_day:
        world.log_msg(_day_change_line(f), "syndicate")

    # Prompt 07: ambient belief-seed propagation tick.
    new_2h_bucket = f.current_minute // 120
    if new_2h_bucket != prev_2h_bucket:
        try:
            from . import memetics
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

    # Deadline warnings
    remaining = f.deadline_remaining_minutes()
    for threshold, key in [(MINUTES_PER_DAY*7, "warn_7d"),
                           (MINUTES_PER_DAY*3, "warn_3d"),
                           (MINUTES_PER_DAY,   "warn_1d"),
                           (60,                "warn_1h")]:
        if prev_remaining > threshold >= remaining:
            world.log_msg(t(f"time_{key}", fallback=f"Termin: pozostało {threshold//60}h."), "warn")

    if remaining == 0 and prev_remaining > 0:
        world.log_msg(t("time_deadline_missed",
                        fallback="Termin minął. Loch zamyka piętro."),
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
