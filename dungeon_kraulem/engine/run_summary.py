"""P29.8 — Run summary / "highlight reel" for game-over screens.

Build a snapshot of how the run went at the moment of death (or
victory). The data is rendered by the end screen in `game.py` and is
also useful for testing that death actually captures something real.

Why a separate module: keeps `game.py` from getting another 80 lines
of scoring logic, and the summary is referenced by both the death
screen and (later) potential intro-cinematic / replay features.

The character itself carries the running counters (`run_*` fields on
Character — see engine/character.py). This module just packages them
at end-of-run plus reads world-level data (sponsors, floor reached,
total minutes) and renders the Polish display lines.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict


# Pool of DCC-flavored "anti-host last words" lines. Picked randomly
# on death — these are the show's final commentary over the body,
# not the player's narration.
ANTI_HOST_DEATH_LINES = (
    "Anti-host pochyla się do mikrofonu: „I to by było na tyle.”",
    "Widownia milknie na pół sekundy. Potem klaszcze.",
    "Kamera 4 łapie ostatnie ujęcie. Reklama za trzy, dwa…",
    "Anti-host: „Sponsorzy nie zwrócą pieniędzy.”",
    "Z głośników leci jingiel końca odcinka. Smaczny.",
    "Anti-host wzdycha: „Liczyliśmy na dłużej. No cóż.”",
    "Tłum w studio krzyczy: „JESZCZE RAZ!” — to nie tak działa.",
    "Operator kamery prosi o cięcie. Producent mówi: „nie, tak zostaje.”",
)


# Pool of generic "you died" lines for the log itself (player-facing,
# more matter-of-fact than the host commentary).
DEATH_LOG_LINES = (
    "Zalewa cię czerń. Loch zapamiętuje twoją pozycję — taką, jaką "
    "zostawiłeś.",
    "Ciało odmawia. Świat zawęża się do jednego punktu, potem do "
    "niczego.",
    "Ostatnia myśl: „nie tak to miało wyglądać”. Tradycyjna.",
    "Tracisz nitkę. Reszta jest hałasem.",
)


@dataclass
class RunSummary:
    """End-of-run snapshot. Populated by build_run_summary()."""
    player_name: str = ""
    background: str = ""
    class_key: str = ""
    species_key: str = ""
    floor_reached: int = 1
    minutes_survived: int = 0
    kills: int = 0
    corpses_salvaged: int = 0
    traps_armed: int = 0
    audience_peak: int = 0
    audience_final: int = 0
    credits_final: int = 0
    hp_final: int = 0
    hp_max: int = 0
    achievements: List[str] = field(default_factory=list)
    top_sponsors: List[tuple] = field(default_factory=list)  # [(key, attention), …]
    death_cause: str = ""
    death_cause_label: str = ""
    anti_host_line: str = ""
    death_log_line: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_name": self.player_name,
            "background": self.background,
            "class_key": self.class_key,
            "species_key": self.species_key,
            "floor_reached": self.floor_reached,
            "minutes_survived": self.minutes_survived,
            "kills": self.kills,
            "corpses_salvaged": self.corpses_salvaged,
            "traps_armed": self.traps_armed,
            "audience_peak": self.audience_peak,
            "audience_final": self.audience_final,
            "credits_final": self.credits_final,
            "hp_final": self.hp_final,
            "hp_max": self.hp_max,
            "achievements": list(self.achievements),
            "top_sponsors": list(self.top_sponsors),
            "death_cause": self.death_cause,
            "death_cause_label": self.death_cause_label,
            "anti_host_line": self.anti_host_line,
            "death_log_line": self.death_log_line,
        }


def _total_minutes_played(world) -> int:
    """Best-effort: sum minutes spent across all floors visited.
    Fallback to the current floor's clock if floor history isn't
    tracked. Used as the "czas w lochu" line in the summary."""
    try:
        floors = getattr(world, "floors_visited_minutes", None) or {}
        if floors:
            return sum(int(v) for v in floors.values())
    except Exception:
        pass
    f = getattr(world, "current_floor", None)
    if f is not None:
        return int(getattr(f, "current_minute", 0) or 0)
    return 0


def _top_sponsors(world, n: int = 3):
    """Return the top n sponsors by attention. Sorted desc, empty list
    on failure. Uses the dynamic attention dict introduced in P29.2."""
    try:
        from . import sponsors as _sp
        att = _sp._attention_dict(world)
        if not att:
            return []
        ranked = sorted(att.items(), key=lambda kv: kv[1], reverse=True)
        return [(k, int(v)) for k, v in ranked[:n] if int(v) != 0]
    except Exception:
        return []


def build_run_summary(world, *, rng=None) -> RunSummary:
    """Scrape every counter we care about off the world + character.
    `rng` is optional; when provided, anti-host / death-log line picks
    use it (lets tests seed deterministically)."""
    import random as _r
    rng = rng or _r
    ch = getattr(world, "character", None)
    rs = RunSummary()
    if ch is None:
        return rs
    rs.player_name = ch.name or "Crawler"
    rs.background = ch.background or ""
    rs.class_key = ch.class_key or ""
    rs.species_key = ch.species_key or ""
    rs.kills = int(getattr(ch, "run_kills", 0))
    rs.corpses_salvaged = int(getattr(ch, "run_corpses_salvaged", 0))
    rs.traps_armed = int(getattr(ch, "run_traps_armed", 0))
    rs.audience_peak = int(getattr(ch, "run_audience_peak", 0))
    rs.audience_final = int(getattr(ch, "audience_rating", 0) or 0)
    rs.credits_final = int(getattr(ch, "credits", 0) or 0)
    rs.hp_final = int(getattr(ch, "hp", 0) or 0)
    rs.hp_max = int(getattr(ch, "max_hp", 0) or 0)
    rs.achievements = list(getattr(ch, "unlocked_achievements", []) or [])
    rs.death_cause = str(getattr(ch, "run_death_cause", "") or "")
    rs.death_cause_label = str(getattr(ch, "run_death_cause_label", "") or "")
    rs.minutes_survived = _total_minutes_played(world)
    # Floor reached: prefer the cumulative high-water mark on the
    # character (Game bumps this on descent). Falls back to the
    # current floor number.
    fnum = 1
    f = getattr(world, "current_floor", None)
    if f is not None:
        fnum = int(getattr(f, "floor_number", 1) or 1)
    rs.floor_reached = max(int(getattr(ch, "run_max_floor_reached", 1)), fnum)
    rs.top_sponsors = _top_sponsors(world, n=3)
    rs.anti_host_line = rng.choice(ANTI_HOST_DEATH_LINES)
    rs.death_log_line = rng.choice(DEATH_LOG_LINES)
    return rs


def render_lines(rs: RunSummary) -> List[str]:
    """Format a RunSummary as the list of Polish lines drawn on the
    game-over screen. Order is roughly: who, where, how long, what
    happened, scoreboard. Each entry is a single line of <= ~80 chars
    so the renderer can lay them out without word-wrap surprises."""
    lines = []
    name = rs.player_name or "Crawler"
    bg = rs.background or "uczestnik"
    lines.append(f"{name} — {bg}")
    if rs.class_key:
        lines.append(f"klasa: {rs.class_key}    gatunek: {rs.species_key}")
    lines.append("")
    if rs.death_cause_label:
        lines.append(f"Przyczyna: {rs.death_cause_label}")
    if rs.anti_host_line:
        lines.append(rs.anti_host_line)
    lines.append("")
    lines.append(f"Piętro:               {rs.floor_reached} / 18")
    lines.append(f"Czas w lochu:         {rs.minutes_survived} min")
    lines.append(f"Zabójstwa:            {rs.kills}")
    lines.append(f"Truchła rozebrane:    {rs.corpses_salvaged}")
    lines.append(f"Pułapek rozstawiono:  {rs.traps_armed}")
    lines.append(f"Widownia (szczyt):    {rs.audience_peak}")
    lines.append(f"Kredyty na koniec:    {rs.credits_final}")
    lines.append("")
    if rs.top_sponsors:
        lines.append("Top sponsorzy:")
        for k, v in rs.top_sponsors:
            sign = "+" if v > 0 else ""
            lines.append(f"  {k:20s} {sign}{v}")
    else:
        lines.append("Top sponsorzy:        — (żaden nie był pod wrażeniem)")
    if rs.achievements:
        lines.append("")
        lines.append(f"Osiągnięcia: {', '.join(rs.achievements[:5])}"
                     + (f" (+{len(rs.achievements)-5})" if len(rs.achievements) > 5 else ""))
    return lines
