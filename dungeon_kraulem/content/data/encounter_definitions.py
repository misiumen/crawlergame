"""Prompt 20 — alarm-to-encounter definitions.

When the player triggers an alarm (e.g. failed lockpick + critical fail,
hacked-but-traced terminal, broken sponsor-property, manual button
press), the engine schedules an "arrival encounter" in the same room.
This table maps the *kind* of alarm to:
  - how long the player has before hostiles arrive,
  - which hostile templates spawn,
  - which warning minutes get a narrator line.

The hostile_keys reference entries in
`content/data/entity_templates.MON`. Unknown keys are silently dropped
at spawn time (so authoring a new alarm doesn't require defining the
responders first).

The audience- and sponsor-tag emission live on the encounter side, not
here; this stays pure data.
"""
from __future__ import annotations

from typing import Dict, List, Any


# Default warning ticks (in-game minutes BEFORE arrival).
_DEFAULT_WARNINGS_AT = [15, 5, 1]


ALARM_ENCOUNTERS: Dict[str, Dict[str, Any]] = {

    # Generic loud alarm — broken glass, force door, panic button.
    # Standard corporate response: two patrol officers.
    "default": {
        "delay_minutes": 30,
        "hostile_keys": ["patrol_security", "patrol_security"],
        "warnings_at": _DEFAULT_WARNINGS_AT,
        "log_intro_pl": "Alarm wyje na cały korytarz. Patrol w drodze. ~30 minut.",
        "log_intro_en": "An alarm howls down the corridor. Patrol incoming. ~30 minutes.",
        "audience_bump":  2,
        "sponsor_tags":   ["spectacle"],
    },

    # Silent alarm — fast quiet corporate response. Player won't even
    # hear it. Less time to prep, but fewer attackers.
    "silent_alarm": {
        "delay_minutes": 15,
        "hostile_keys": ["silent_response"],
        "warnings_at": [5, 1],   # no T-15 (player has 15 to begin with)
        "log_intro_pl": "Cichy alarm. Coś się dzieje. Nie wiesz co. Masz ~15 minut.",
        "log_intro_en": "A silent alarm fires somewhere. You wouldn't know. ~15 minutes.",
        "audience_bump":  1,
        "sponsor_tags":   ["theft"],
    },

    # Biotech-lab containment protocol — slow but heavily armored.
    # NovaChem's inspector + cleanup crew.
    "biotech_containment": {
        "delay_minutes": 45,
        "hostile_keys": ["biotech_inspector", "patrol_security"],
        "warnings_at": [30, 15, 5, 1],
        "log_intro_pl":
            "Procedura kwarantanny biochemicznej. NovaChem wysyła "
            "inspektora. ~45 minut.",
        "log_intro_en":
            "Biohazard containment protocol. NovaChem is dispatching an "
            "inspector. ~45 minutes.",
        "audience_bump":  3,
        "sponsor_tags":   ["chemical", "spectacle"],
    },
}


def get_alarm_definition(alarm_type: str) -> Dict[str, Any]:
    """Return the alarm encounter definition. Falls back to 'default' if
    `alarm_type` isn't in the table — never raises, never returns None."""
    return ALARM_ENCOUNTERS.get(alarm_type) or ALARM_ENCOUNTERS["default"]


def all_alarm_types() -> List[str]:
    return list(ALARM_ENCOUNTERS.keys())
