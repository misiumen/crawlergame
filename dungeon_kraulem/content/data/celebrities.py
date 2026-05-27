"""P29.18 — Celebrity crawler pool.

Named NPC crawlers with fixed loadouts and recognisable personas.
Encounter them rarely (~5% per floor build, gated by floor_min).
A celebrity unlock fires achievement + audience bump on first
sighting.

Schema:
    key                stable identifier
    fallback_name      "Stage Name (real name)" — what the player sees
    fallback_intro     first-meet log line
    archetype          legacy alias (vet|scavenger|preacher|runner|medic)
    personality        free-text descriptor
    disposition        neutral | hostile | friendly
    floor_min          earliest floor they can appear
    floor_max          latest floor (None = forever)
    hp_design          PRE-BALANCE hp number; combat scaling applies
    notoriety_boost    one-shot audience bump when first encountered
    fan_following      sponsor key whose attention bumps when this
                       celebrity is seen / killed / befriended
    tags               extra tags (always includes "celebrity")
"""
from __future__ import annotations
from typing import Dict, List, Optional


CELEBRITIES: Dict[str, Dict] = {
    "mrok_kanal7": {
        "key": "mrok_kanal7",
        "fallback_name": "„Mrok” Krystian Krawczyk (Kanał 7)",
        "fallback_intro": (
            "Z głębi pokoju wyłania się Mrok — drugi sezon, ten z "
            "ekstra mocnym mikrofonem. „Pamiętacie mnie, prawda? "
            "Powiedzcie, że pamiętacie.”"
        ),
        "archetype": "vet",
        "personality": "egotyczny gwiazdor",
        "disposition": "hostile",
        "floor_min": 4, "floor_max": 12,
        "hp_design": 24,
        "notoriety_boost": 6,
        "fan_following": "kanal_7_krawedz",
        "tags": ["celebrity", "kanal_7", "broadcast"],
    },
    "pulkownik_recykling": {
        "key": "pulkownik_recykling",
        "fallback_name": "Pułkownik Recykling",
        "fallback_intro": (
            "Pułkownik Recykling salutuje resztkami pielęgniarskiej "
            "czapki. „Każda część ma swoje miejsce. Ty masz swoje."
        ),
        "archetype": "scavenger",
        "personality": "fanatyk obowiązku",
        "disposition": "neutral",
        "floor_min": 3, "floor_max": 10,
        "hp_design": 28,
        "notoriety_boost": 5,
        "fan_following": "kult_recyklingu",
        "tags": ["celebrity", "recykling", "salvage_friend"],
    },
    "bostwo_pamieci": {
        "key": "bostwo_pamieci",
        "fallback_name": "„Bóstwo Pamięci” (anonim z Ministerstwa)",
        "fallback_intro": (
            "Postać w masce z logo Ministerstwa pochyla głowę. "
            "„Zapamiętaj prawidłowo. Albo zapomnij wszystko."
        ),
        "archetype": "preacher",
        "personality": "korporacyjnie hipnotyczny",
        "disposition": "hostile",
        "floor_min": 5, "floor_max": 14,
        "hp_design": 22,
        "notoriety_boost": 7,
        "fan_following": "ministerstwo_pamieci",
        "tags": ["celebrity", "ministerstwo", "memetic"],
    },
    "biegacz_tora": {
        "key": "biegacz_tora",
        "fallback_name": "„Biegacz Tora” Wiola Pęk",
        "fallback_intro": (
            "Wiola Pęk jest tu tylko na chwilę — biegnie obok ciebie "
            "i krzyczy: „Nie zatrzymuj się! Trzeci cykl rekordu!”"
        ),
        "archetype": "runner",
        "personality": "wiecznie zdyszany sprinter",
        "disposition": "neutral",
        "floor_min": 2, "floor_max": 8,
        "hp_design": 16,
        "notoriety_boost": 4,
        "fan_following": "sponsor_bezpieczenstwa_sportu",
        "tags": ["celebrity", "sport", "runner"],
    },
    "bankier_serca": {
        "key": "bankier_serca",
        "fallback_name": "Bankier Serca (debiut sezonu)",
        "fallback_intro": (
            "Garnitur w karminowym odcieniu, teczka, lekki uśmiech. "
            "„Witam, panie podpisze tutaj? Mam dla pana ofertę specjalną."
        ),
        "archetype": "preacher",
        "personality": "ujmująco złowieszczy",
        "disposition": "neutral",
        "floor_min": 6, "floor_max": 14,
        "hp_design": 26,
        "notoriety_boost": 8,
        "fan_following": "bractwo_komornika",
        "tags": ["celebrity", "bractwo_komornika", "social"],
    },
    "doktor_polimer": {
        "key": "doktor_polimer",
        "fallback_name": "„Doktor Polimer”",
        "fallback_intro": (
            "Białoplastykowy kombinezon, kadzielnica z gorącej żywicy, "
            "uśmiech zbyt wąski. „Witamy w miękkiej fazie."
        ),
        "archetype": "medic",
        "personality": "syntetycznie ekstatyczny",
        "disposition": "hostile",
        "floor_min": 10, "floor_max": 16,
        "hp_design": 30,
        "notoriety_boost": 9,
        "fan_following": "bog_polimerow",
        "tags": ["celebrity", "polimery", "chemical"],
    },
}


def all_celebrity_keys() -> List[str]:
    return list(CELEBRITIES.keys())


def get(key: str) -> Optional[Dict]:
    return CELEBRITIES.get(key)


def for_floor(floor_num: int) -> List[Dict]:
    """Celebrities eligible for this floor (floor_min <= n <= floor_max)."""
    out = []
    for d in CELEBRITIES.values():
        if int(d.get("floor_min", 1)) <= floor_num <= int(
                d.get("floor_max") or 999):
            out.append(d)
    return out
