"""P29.12 — Floor-1 tutorial / onboarding tips.

The game has 7+ mechanics that aren't obvious to a new player:
sponsor attention, threat escalation, fog-of-war / sprawdź, VATS
body-targeting, save slots, mid-floor drop pods, the last-stand
rescue. Each tip surfaces ONCE per character when its trigger
fires, written as a `LOG_SYSTEM` line tagged "TUTORIAL:" so it
reads as overlay-style flavor rather than as a popup that steals
focus.

Each tip ID stamps a `character.flags["tutorial_seen_<id>"]` so
it can't re-fire — and so saves preserve onboarding state. A
settings toggle (future) can globally suppress them via
`character.flags["tutorial_disabled"]`.
"""
from __future__ import annotations
from typing import Optional


# Tip catalog. Keep each entry short (1-2 sentences). The player
# sees these inline, not as a modal.
TIPS = {
    "welcome": (
        "Witaj na Piętrze 1. Sterowanie: pisz polecenia, Tab = nawigacja, "
        "PgUp/PgDn = przewijanie logu. Jeśli coś jest niejasne — "
        "spróbuj `pomoc`."
    ),
    "fog_of_war": (
        "Nie widzisz wszystkiego naraz. Użyj `sprawdź <coś>`, żeby "
        "rozpoznać kogoś lub coś. Pierwszy sprawdź pokazuje sylwetkę, "
        "drugi — pełne statystyki."
    ),
    "sponsors": (
        "Sponsorzy obserwują. Twoje akcje dodają im uwagi — jak "
        "uzbierasz +8, dostajesz pakiet (pojawi się w pokoju jako "
        "kapsuła; `otwórz pakiet`)."
    ),
    "threat": (
        "Cisza się opłaca. Hałaśliwe akcje (atak, walenie, sprawdzanie) "
        "podnoszą Zagrożenie pokoju — wrogowie eskalują od czujnego "
        "po wściekłego. Patrz na pasek u góry."
    ),
    "combat_vats": (
        "W walce możesz celować w konkretne miejsca ciała (głowa, "
        "ramię, noga). Otwórz panel VATS w boku ekranu albo wpisz "
        "`atak <wróg> głowa`."
    ),
    "save_slots": (
        "Masz 3 sloty zapisu. W menu „Wczytaj” widać każdy — imię, "
        "piętro, HP. Śmierć kasuje TYLKO bieżący slot, inne czekają."
    ),
    "drop_pods": (
        "Pakiety sponsorskie spadają w pokoju, w którym jesteś. "
        "`otwórz pakiet` zgarnia zawartość. Publiczne otwarcie = "
        "+widownia."
    ),
    "low_hp": (
        "Niskie HP. Masz jednorazową rezerwę: pierwszy „śmiertelny” "
        "cios zostawia cię na 1 HP. Później — naprawdę umierasz. "
        "Lecz się odpoczynkiem lub stymulantem."
    ),
    "trap_deploy": (
        "Pułapki w plecaku można rozstawić: `rozstaw <pułapka>`. "
        "Jeśli rozstawisz w złym miejscu — `zwiń pułapkę` ją "
        "zabierze (test DEX/INT)."
    ),
    "descend": (
        "Schody w dół czekają w pokoju oznaczonym jako wyjście. "
        "Zejście resetuje większość ścieżek — zapisz progres, jeśli "
        "ci na nim zależy."
    ),
}


def is_disabled(world) -> bool:
    ch = getattr(world, "character", None)
    if ch is None:
        return True
    return bool((ch.flags or {}).get("tutorial_disabled"))


def has_seen(world, tip_key: str) -> bool:
    ch = getattr(world, "character", None)
    if ch is None:
        return True
    return bool((ch.flags or {}).get(f"tutorial_seen_{tip_key}"))


def mark_seen(world, tip_key: str) -> None:
    ch = getattr(world, "character", None)
    if ch is None:
        return
    if ch.flags is None:
        ch.flags = {}
    ch.flags[f"tutorial_seen_{tip_key}"] = True


def _on_floor_1(world) -> bool:
    """Tutorials only fire on the first floor — by then a player who
    has descended has clearly figured the basics out. Override with
    `force=True` for tips that should fire on later floors too
    (e.g. low_hp warning)."""
    f = getattr(world, "current_floor", None)
    if f is None:
        return False
    return int(getattr(f, "floor_number", 1) or 1) == 1


def try_show_tip(world, tip_key: str, *, force_any_floor: bool = False) -> bool:
    """Surface a tip in the log. No-op if:
      * world has no character (e.g. title screen),
      * tutorials are disabled,
      * the tip has already been shown,
      * the player is past floor 1 and `force_any_floor` is False.
    Returns True if the tip was actually emitted."""
    if world is None:
        return False
    if is_disabled(world):
        return False
    if has_seen(world, tip_key):
        return False
    if not force_any_floor and not _on_floor_1(world):
        return False
    text = TIPS.get(tip_key)
    if not text:
        return False
    mark_seen(world, tip_key)
    line = f"TUTORIAL: {text}"
    if hasattr(world, "log_msg"):
        world.log_msg(line, "system")
    elif hasattr(world, "log"):
        world.log.append((line, "system"))
    return True


def reset_for_world(world) -> None:
    """Test helper: clear every tutorial_seen_* flag on the character."""
    ch = getattr(world, "character", None)
    if ch is None or ch.flags is None:
        return
    drop = [k for k in ch.flags if k.startswith("tutorial_seen_")]
    for k in drop:
        del ch.flags[k]
