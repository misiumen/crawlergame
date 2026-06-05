"""P29.20 — Companion narrative arc / chatter system.

The Companion data model (engine/companion.py) had bond + stress
fields and a 10-pet catalog since P19, but the pet was silent — no
log lines, no DCC-flavored commentary. Players didn't feel they had
a partner in the run, just a stat-stick.

This module fixes that. It exposes one public function,
maybe_say(world, trigger, **ctx), called from the relevant game
events:

  trigger="hp_low"          — fires once when HP first crosses 50%
  trigger="combat_start"    — at top of first round of a new fight
  trigger="enemy_killed"    — after each kill
  trigger="sponsor_pod_open" — when player opens a drop pod
  trigger="floor_descent"   — when player descends a floor
  trigger="idle"            — random ambient line every ~25 min
  trigger="player_death"    — last words

Chatter is gated by:
  * an active pet exists on the world
  * the pet is alive + ACTIVE status
  * a per-trigger cooldown stamp on companion (no spam)
  * bond-band selects tone:
      0-2 (estranged) — terse, distrustful
      3-6 (cool)      — neutral
      7-9 (close)     — supportive
      10  (devoted)   — adoring / pep-talk

Each pet may declare its own override line in `companion_voice_overrides`
on its catalog entry (P29.20 ships overrides for the FLAGSHIP pet);
otherwise the generic pool is used.
"""
from __future__ import annotations
import random
from typing import Optional, Dict, List

# Triggers and the minimum minutes between successive fires of the
# same trigger (per companion). Keeps chatter from drowning the log.
_TRIGGER_COOLDOWN = {
    "hp_low":           60,    # once per HP-50% crossing, ~floor lifetime
    "combat_start":     8,
    "enemy_killed":     5,
    "sponsor_pod_open": 30,
    "floor_descent":    1,
    "idle":             25,
    "player_death":     0,
}


# Generic chatter pool. Each entry: (trigger, bond_min, bond_max, line)
# bond_min/max bracket inclusive. The renderer picks weighted-random
# among matching lines.
_LINES: List[tuple] = [
    # hp_low — bond shifts the tone hard
    ("hp_low", 0, 2,
     "Twoje zwierzę warczy z dystansu. Wiedziało, że tak się skończy."),
    ("hp_low", 3, 6,
     "Twoje zwierzę zaczyna się kręcić nerwowo. Próbuje pomóc, ale nie wie jak."),
    ("hp_low", 7, 9,
     "Twoje zwierzę przytuliło się do nogi. „Ej, nie poddawaj się.”"),
    ("hp_low", 10, 10,
     "Twoje zwierzę wpada w panikę o ciebie, jakby to ono krwawiło. "
     "Liż-liż-szturchnij — nie chce cię stracić."),

    # combat_start
    ("combat_start", 0, 2,
     "Zwierzę patrzy na ciebie ze sceptycyzmem. „Znów to robisz?”"),
    ("combat_start", 3, 6,
     "Zwierzę cofa się o dwa kroki — chce mieć dobry kąt na obserwację."),
    ("combat_start", 7, 9,
     "Zwierzę napina się obok ciebie. „Idziemy razem.”"),
    ("combat_start", 10, 10,
     "Zwierzę staje obok ciebie z taką pewnością siebie, że nawet ty "
     "zaczynasz w siebie wierzyć."),

    # enemy_killed
    ("enemy_killed", 0, 2,
     "Twoje zwierzę szturcha pyskiem zwłoki, jakby sprawdzało, "
     "czy się nie ruszy."),
    ("enemy_killed", 3, 6,
     "Zwierzę warczy raz, dla porządku."),
    ("enemy_killed", 7, 9,
     "Zwierzę spogląda na ciebie z aprobatą. „Dobrze poszło.”"),
    ("enemy_killed", 10, 10,
     "Zwierzę robi krótki taniec zwycięstwa. Studio łapie ujęcie."),

    # sponsor_pod_open — companions HATE sponsor crap by default
    ("sponsor_pod_open", 0, 2,
     "Twoje zwierzę odwraca głowę, jakby nie chciało być w tej scenie."),
    ("sponsor_pod_open", 3, 6,
     "Zwierzę wącha pakiet z dystansu. Nie wygląda na przekonane."),
    ("sponsor_pod_open", 7, 9,
     "Zwierzę pozwala ci otworzyć pakiet. „No to chociaż coś z tego mamy.”"),
    ("sponsor_pod_open", 10, 10,
     "Zwierzę pozuje do kamery, kiedy otwierasz pakiet. Wie, kiedy "
     "być w ujęciu."),

    # floor_descent
    ("floor_descent", 0, 2,
     "Zwierzę wchodzi za tobą po schodach, prychając pod nosem."),
    ("floor_descent", 3, 6,
     "Zwierzę bezgłośnie idzie obok ciebie."),
    ("floor_descent", 7, 9,
     "Zwierzę macha ogonem przy zejściu. „Dalej. Razem.”"),
    ("floor_descent", 10, 10,
     "Zwierzę wskazuje pyskiem na schody, jakby je samodzielnie "
     "znalazło. Może i znalazło."),

    # idle ambient
    ("idle", 0, 2,
     "Zwierzę leży w kącie i obserwuje cię, jakbyś był pomyłką."),
    ("idle", 3, 6,
     "Zwierzę drapie się o framugę. Sprawdza akustykę."),
    ("idle", 7, 9,
     "Zwierzę kładzie się obok ciebie. Cisza, ale dobra."),
    ("idle", 10, 10,
     "Zwierzę przytuliło się tak, że trudno ci wstać. Wybaczasz mu."),

    # player_death — the last words
    ("player_death", 0, 5,
     "Twoje zwierzę odwraca się i wychodzi z pokoju. Tyle widziałeś."),
    ("player_death", 6, 10,
     "Twoje zwierzę siedzi obok przez całą reklamę. Producent musi "
     "kazać operatorowi przesunąć kamerę."),
]


# Per-pet override pool. Keyed by Companion.species_key. Each value
# is a list of (trigger, bond_min, bond_max, line) — replaces / adds
# to generic pool for that pet.
_OVERRIDES: Dict[str, List[tuple]] = {
    # FLAGSHIP — the talking-bird Donut-analog. Smart-mouth canned
    # lines, regardless of bond (it's a celebrity, not a dog).
    "papuga_anty_host": [
        ("combat_start", 0, 10,
         "Papuga: „TRZECI cykl! POWTARZAM, TRZECI cykl! Czy on wie, "
         "co robi? CZY ON WIE?!”"),
        ("enemy_killed", 0, 10,
         "Papuga: „Łojezuuu, zliczcie to. ZLICZCIE. Sponsorzy chcą "
         "wiedzieć.”"),
        ("hp_low", 0, 10,
         "Papuga: „Ej. EJ. Nie umieraj na antenie, mam reklamę za "
         "trzy minuty.”"),
        ("sponsor_pod_open", 0, 10,
         "Papuga: „Bierz, bierz. Ja widziałam, co tam jest. Bierz."),
        ("floor_descent", 0, 10,
         "Papuga: „Schody w dół. Reżyser kocha schody w dół. Zostań w "
         "kadrze!”"),
        ("idle", 0, 10,
         "Papuga: „Hej. HEJ. Powiedz coś. Mikrofon się nudzi."),
        ("player_death", 0, 10,
         "Papuga (do kamery): „Pamiętaj, że ta śmierć była "
         "sponsorowana przez Kanał 7.”"),
    ],
}


def _bond_band(bond: int) -> str:
    if bond <= 2: return "estranged"
    if bond <= 6: return "cool"
    if bond <= 9: return "close"
    return "devoted"


def _now_minute(world) -> int:
    f = getattr(world, "current_floor", None)
    if f is None:
        return 0
    return int(getattr(f, "current_minute", 0) or 0)


def _last_minute_for_trigger(comp, trigger: str) -> int:
    """Per-companion cooldown stamp. Stored on companion's runtime
    dict (not serialized — chatter timing is ephemeral)."""
    if not hasattr(comp, "_voice_stamps"):
        comp._voice_stamps = {}
    return int(comp._voice_stamps.get(trigger, -10_000))


def _stamp(comp, trigger: str, minute: int) -> None:
    if not hasattr(comp, "_voice_stamps"):
        comp._voice_stamps = {}
    comp._voice_stamps[trigger] = minute


def _eligible_lines(comp, trigger: str) -> List[str]:
    """Pick lines whose bond range covers the companion's current
    bond and whose trigger matches. Pet overrides are FIRST priority;
    if the species has overrides for this trigger, use ONLY those."""
    # Note: don't use `or 5` here — bond=0 (estranged) is a real
    # value, and `0 or 5` collapses it to 5 because 0 is falsy.
    raw_bond = getattr(comp, "bond", 5)
    bond = int(raw_bond) if raw_bond is not None else 5
    skey = getattr(comp, "species_key", "")
    overrides = _OVERRIDES.get(skey, [])
    override_lines = [ln for trig, lo, hi, ln in overrides
                      if trig == trigger and lo <= bond <= hi]
    if override_lines:
        return override_lines
    return [ln for trig, lo, hi, ln in _LINES
            if trig == trigger and lo <= bond <= hi]


def maybe_say(world, trigger: str, *,
              rng: Optional[random.Random] = None,
              force: bool = False) -> Optional[str]:
    """Try to emit a chatter line. Returns the line on fire, or None.

    `force=True` bypasses the cooldown (used by `player_death` so
    final words always appear)."""
    from . import companion as _comp
    if world is None or trigger not in _TRIGGER_COOLDOWN:
        return None
    pet = _comp.active_pet(world)
    if pet is None or not pet.is_alive():
        return None
    cd = _TRIGGER_COOLDOWN[trigger]
    now = _now_minute(world)
    last = _last_minute_for_trigger(pet, trigger)
    if not force and (now - last) < cd:
        return None
    lines = _eligible_lines(pet, trigger)
    if not lines:
        return None
    rng = rng or random.Random((now + len(lines)) % 100_000)
    line = rng.choice(lines)
    _stamp(pet, trigger, now)
    if hasattr(world, "log_msg"):
        world.log_msg(line, "companion")
    return line


def add_flagship_pet(world) -> Optional["_comp.Companion"]:
    """Convenience for tests / future tutorial: assign the
    DCC-flagship talking parrot as the player's active pet.

    Sets up bond=7 (close) so the first session lines feel partnered
    rather than estranged. Use sparingly — players shouldn't get
    this by default; reserve for a sponsor-quest reward."""
    from . import companion as _comp
    pet = _comp.Companion(
        kind=_comp.KIND_PET,
        species_key="papuga_anty_host",
        display_name_pl="Papuga Konferansjera",
        bond=7,
        stress=0,
        tags=["bird", "talking", "celebrity_pet", "broadcast"],
        abilities=["morale_boost", "repeat_phrase"],
        sponsor_likes_tags=["kanal_7_krawedz"],
    )
    return _comp.register_companion(world, pet)
