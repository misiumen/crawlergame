"""P29.53q — Random absurd ambient events (DCC flavor).

The world is a reality show inside a collapsing arcology. Stuff
happens that has nothing to do with you. A goat wanders by. A
sponsor's logo blinks on every wall for six seconds. The
showrunner forgets to mute themselves for a sentence.

These are tiny, frequency-capped, mostly-cosmetic events that fire
on the floor clock and inject Dinniman-style absurdity. They keep
the world feeling alive between meaningful player actions.

Mechanical scope is intentionally small (±1-3 audience, ±1-2 HP,
±5 credits, never more). Anything bigger goes through sponsors /
intervention pipelines, not here.
"""
from __future__ import annotations
import random as _r
from typing import Optional


# ── Tick cadence ─────────────────────────────────────────────────────


# Minimum minutes between two absurd events. With 6% per-tick chance
# and 60-minute floor of cadence, average is ~1 event every 2-3
# floor-hours of game time. Frequent enough to notice, rare enough
# not to spam the log.
_MIN_COOLDOWN_MIN = 60
_TICK_CHANCE = 0.06


# ── Catalog ──────────────────────────────────────────────────────────


# Each entry:
#   key        — internal id, used in flags for one-shot dedupe
#   line_pl    — log line (Polish, Dinniman tone)
#   tone       — log category: "narrator" | "syndicate" | "warn"
#                | "success" | "system"
#   effect     — optional dict applied to character / world:
#                  audience: int (delta)
#                  hp:       int (delta, clamped)
#                  credits:  int (delta, clamped to 0)
#   one_shot   — bool; if True, only ever fires once per run.

ABSURD_EVENTS = [
    {"key":"flicker_logo",
     "line_pl":"Logo sponsora mruga ci w sufit przez sześć sekund. "
               "Sześć sekund to bardzo długo, kiedy patrzysz na sufit.",
     "tone":"narrator",
     "effect":{"audience": 1}},

    {"key":"showrunner_unmuted",
     "line_pl":"Z głośnika dochodzi: „...nie, mówiłem PIES, nie PISK, "
               "kurwa.” — i cisza. Showrunner zapomniał się wyłączyć.",
     "tone":"syndicate",
     "effect":{"audience": 2}},

    {"key":"wandering_goat",
     "line_pl":"Mija cię koza. Nie reaguje. Idzie dalej. Ma na "
               "obroży naszywkę „MASKOTKA SEZONU 4”.",
     "tone":"narrator"},

    {"key":"vending_singing",
     "line_pl":"Automat ze snackami zaczyna nucić jingle z lat "
               "osiemdziesiątych. Po chwili przestaje. Snacks tańsze "
               "o 5 kredytów (jingle to upgrade).",
     "tone":"narrator",
     "effect":{"credits": 5}},

    {"key":"fan_throws_doughnut",
     "line_pl":"Z górnej rampy ktoś rzuca pączka. Trafia w ścianę. "
               "Odbija się. Spada przed twoje stopy. Smaczny.",
     "tone":"narrator",
     "effect":{"hp": 1, "audience": 1}},

    {"key":"camera_glitch",
     "line_pl":"Najbliższa kamera kłania ci się w pas. Mechanicznie. "
               "Hydraulika syka. Wraca do pozycji.",
     "tone":"narrator"},

    {"key":"intercom_horoscope",
     "line_pl":"Intercom: „Crawler bieżącego znaku — wagi nie ufają "
               "ci dzisiaj. Mars w polu drugim. Powodzenia.”",
     "tone":"syndicate"},

    {"key":"sponsored_chant",
     "line_pl":"Słyszysz odległy śpiew widowni: „PIWO! KRREW! "
               "BLEU-CHEESE!” Nikt nie wie kto pisał setlistę.",
     "tone":"narrator",
     "effect":{"audience": 1}},

    {"key":"second_moon",
     "line_pl":"Przez chwilę masz wrażenie, że nad lochem są dwa "
               "księżyce. Loch nie ma okien.",
     "tone":"warn"},

    {"key":"hp_bar_sponsor",
     "line_pl":"Pasek HP w prawym górnym pulsuje kolorem nowego "
               "sponsora. Sponsor jeszcze nie istnieje. Trwa licytacja.",
     "tone":"system"},

    {"key":"polite_drone",
     "line_pl":"Mała kamera-dron zatrzymuje się przed tobą i "
               "kiwa się — w przybliżeniu „przepraszam”. Lata dalej.",
     "tone":"narrator"},

    {"key":"merch_drop",
     "line_pl":"Z sufitu spada pojedyncza miniaturowa kapelusz-laska. "
               "Brand jakiegoś sponsora. Plastik trzeszczy pod butem.",
     "tone":"narrator"},

    {"key":"silent_minute",
     "line_pl":"Cały loch milknie na sekundę. Sponsor odpalił "
               "płatną reklamę. Nikt jej nie kupił.",
     "tone":"syndicate"},

    {"key":"crawler_selfie",
     "line_pl":"Mijasz innego crawlera robiącego sobie zdjęcie z "
               "trupem. Nie patrzysz dłużej niż musisz.",
     "tone":"narrator"},

    {"key":"phantom_applause",
     "line_pl":"Słyszysz krótkie oklaski. Z niczego konkretnego. "
               "Widownia czasem oklaskuje na zaliczkę.",
     "tone":"narrator",
     "effect":{"audience": 2}},

    {"key":"vendor_freebie",
     "line_pl":"Automat z bandażami wypluwa jeden bandaż za darmo. "
               "Wpada do twojej kieszeni, zanim zdążysz pomyśleć.",
     "tone":"success",
     "effect":{"hp": 1}},

    {"key":"loch_burp",
     "line_pl":"Coś głęboko poniżej burczy. Loch trawi.",
     "tone":"warn"},

    {"key":"emergency_jingle",
     "line_pl":"Krótki, fałszywy alarm. Trwa ćwierć sekundy. "
               "„Test systemu reklam”, podaje intercom z wyrzutem.",
     "tone":"system"},

    # P29.53q-bonus — one-shot mid-run "memorable moment".
    {"key":"empty_room_with_chair",
     "line_pl":"Wchodzisz w róg pomieszczenia i widzisz krzesło. "
               "Tylko krzesło. Zwykłe. Nie da się go ruszyć.",
     "tone":"narrator",
     "one_shot": True},

    {"key":"sponsored_haiku",
     "line_pl":"Showrunner czyta haiku. „W lochu jesień. Krew. "
               "Subskrybuj kanał B-7.” Cisza.",
     "tone":"syndicate",
     "one_shot": True,
     "effect":{"audience": 1}},
]


# ── Hook ──────────────────────────────────────────────────────────────


def maybe_fire(world, rng: Optional[_r.Random] = None) -> Optional[dict]:
    """Roll once. Return the fired event dict, or None.

    Caller is expected to be the floor-clock tick. Internal cooldown
    is tracked in `world.character.flags["_absurd_last_min"]` so the
    cadence doesn't depend on caller frequency.
    """
    if world is None or not getattr(world, "current_floor", None):
        return None
    ch = getattr(world, "character", None)
    if ch is None:
        return None
    if ch.flags is None:
        ch.flags = {}
    now = int(getattr(world.current_floor, "current_minute", 0) or 0)
    last = int(ch.flags.get("_absurd_last_min", -10**6))
    if now - last < _MIN_COOLDOWN_MIN:
        return None
    rng = rng or _r.Random(now * 31 + len(ch.flags))
    if rng.random() > _TICK_CHANCE:
        return None

    fired_set = set(ch.flags.get("_absurd_fired", []) or [])
    pool = [e for e in ABSURD_EVENTS
            if not (e.get("one_shot") and e["key"] in fired_set)]
    if not pool:
        return None
    ev = rng.choice(pool)
    _apply(world, ch, ev)
    ch.flags["_absurd_last_min"] = now
    if ev.get("one_shot"):
        fired = list(ch.flags.get("_absurd_fired", []) or [])
        fired.append(ev["key"])
        ch.flags["_absurd_fired"] = fired
    return ev


def _apply(world, ch, ev: dict) -> None:
    """Emit log line + apply small effect (audience/HP/credits)."""
    line = ev.get("line_pl") or ""
    tone = ev.get("tone") or "narrator"
    if line and hasattr(world, "log_msg"):
        try:
            world.log_msg(line, tone)
        except Exception:
            pass
    fx = ev.get("effect") or {}
    # Audience routed through change_audience for clamping + band cross.
    delta = int(fx.get("audience", 0))
    if delta:
        try:
            from . import audience as _aud
            _aud.change_audience(world, delta,
                                 source=f"absurd:{ev.get('key','?')}")
        except Exception:
            pass
    # HP — clamp to [0, max_hp]; never lethal.
    hp_delta = int(fx.get("hp", 0))
    if hp_delta:
        try:
            ch.hp = max(0, min(int(ch.max_hp or ch.hp),
                               int(ch.hp) + hp_delta))
        except Exception:
            pass
    # Credits — never negative.
    cr_delta = int(fx.get("credits", 0))
    if cr_delta:
        try:
            ch.credits = max(0, int(getattr(ch, "credits", 0) or 0)
                             + cr_delta)
        except Exception:
            pass
