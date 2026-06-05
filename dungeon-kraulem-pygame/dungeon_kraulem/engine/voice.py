"""P29.64b — Głos bohatera (wewnętrzny monolog per origin).

User: „mój główny bohater to póki co niemowa bez osobowości. to się musi
zmienić" + „głos zależnie od origin".

Każde pochodzenie patrzy na świat inaczej. Przy `zbadaj pomieszczenie`
(moment odkrycia) bohater rzuca krótką myśl zabarwioną swoim fachem —
to jego OSOBOWOŚĆ, nie podpowiedź mechaniki.

Osobno: PODSZEPT PERCEPCJI — gdy postać jest spostrzegawcza (wysoki mod
MDR/INT), monolog kończy się konkretną wskazówką co w pokoju aż się
prosi, żeby wykorzystać. Gating po PERCEPCJI, nie po umiejętności:
spostrzegawczy zauważa więcej, ale działać może każdy (immersive sim —
wiedza ≠ zdolność).

Polish-only. Bez bezpośrednich odniesień do prozy źródłowej.
"""
from __future__ import annotations
from typing import List, Optional


# Monolog „przy oglądaniu otoczenia" per origin. 2-3 linie, rotowane
# deterministycznie (licznik w flags) — różnorodność bez RNG.
_ORIGIN_EXAMINE: dict = {
    "office_worker": [
        "Gdyby to był projekt, narysowałbym diagram zależności. Co tu z czym gada?",
        "Sześć lat w open space nauczyło mnie czytać salę. To czytajmy.",
    ],
    "mechanic": [
        "Wszystko da się rozkręcić. Pytanie tylko w jakiej kolejności.",
        "Czuję, gdzie tu coś chrupie. Gdzie słaby spaw.",
    ],
    "nurse": [
        "Najpierw oceniam, co krwawi, co poczeka. Jak na dyżurze.",
        "Spokojnie, po kolei. Co groźne, a co tylko tak wygląda.",
    ],
    "cook": [
        "Kuchnia w godzinach szczytu była gorsza. Co tu się da podgrzać?",
        "Każdy bałagan ma swój porządek. Trzeba wiedzieć, gdzie ostry nóż.",
    ],
    "security_guard": [
        "Stałem przy gorszych drzwiach. Co tu jest nie tak?",
        "Patrzę jak na monitoringu. Kto i co tu nie pasuje.",
    ],
    "courier": [
        "Wejście, trasa, wyjście. Liczę sekundy.",
        "Znam takie zaułki. Wiem, gdzie się przecisnąć.",
    ],
    "student": [
        "Gdzieś to czytałem. Albo i nie. Sprawdźmy empirycznie.",
        "Hipoteza: da się to obejść. Zbierzmy dane.",
    ],
    "streamer": [
        "Kamera by to pokochała. Co da najlepszy materiał?",
        "Patrzą na mnie. Zróbmy coś, czego nie zapomną.",
    ],
    "soldier": [
        "Ocena terenu: osłony, drogi odwrotu, co tu wybucha.",
        "Stary nawyk — najpierw zagrożenia, potem reszta.",
    ],
    "unemployed_hustler": [
        "Zawsze coś się da z tego ukręcić. Co tu leży luzem?",
        "Kombinuję. Zawsze kombinowałem.",
    ],
    "janitor": [
        "Każdy budynek ma swoje flaki. Takie znam.",
        "Ślepe zaułki, kratki, rury — moje terytorium.",
    ],
    "paramedic": [
        "Oddech. Ocena. Działanie. Jak zawsze.",
        "Widziałem gorsze sceny. Co tu jest realnym zagrożeniem?",
    ],
    "opiekun_zwierzaka": [
        "Zwierzak wyczułby to pierwszy. Ja muszę się bardziej starać.",
        "Spokojnie, jak przy spłoszonym kocie. Po kolei.",
    ],
    "bezdomny": [
        "Tyle nocy w gorszych dziurach. Co tu się nada, żeby przeżyć?",
        "Ulica nauczyła: patrz, co złapiesz i czym dostaniesz.",
    ],
}

_FALLBACK_EXAMINE = [
    "Rozglądam się powoli. Co tu jest moje, a co przeciwko mnie.",
]


def _stat_mod(character, stat: str) -> int:
    try:
        return int(character.stat_mod(stat))
    except Exception:
        # Fallback: (wartość-10)//2 z dict statów.
        try:
            return (int((getattr(character, "stats", {}) or {}).get(stat, 10)) - 10) // 2
        except Exception:
            return 0


def perception_mod(character) -> int:
    """Spostrzegawczość = lepszy z modów MDR (WIS) / INT."""
    return max(_stat_mod(character, "WIS"), _stat_mod(character, "INT"))


def monologue(character, context: str = "examine") -> Optional[str]:
    """Krótka myśl bohatera zabarwiona pochodzeniem. Rotuje
    deterministycznie po liczniku w flags (różnorodność bez RNG).
    Zwraca None, gdy brak postaci."""
    if character is None:
        return None
    if context != "examine":
        return None
    bg = getattr(character, "background", "") or ""
    lines: List[str] = _ORIGIN_EXAMINE.get(bg) or _FALLBACK_EXAMINE
    flags = getattr(character, "flags", None)
    idx = 0
    if isinstance(flags, dict):
        key = f"voice_{context}_i"
        idx = int(flags.get(key, 0) or 0)
        flags[key] = idx + 1
    return lines[idx % len(lines)]


# Próg percepcji, od którego podszept staje się KONKRETNY (wskazuje
# rzecz). Poniżej — bohater czuje, że „coś tu jest", ale nie nazywa.
_PERCEPTION_HINT_THRESHOLD = 2


def perception_hint(character, observed: List[tuple]) -> Optional[str]:
    """`observed` = lista (nazwa, [obserwacje]) ze środowiska. Jeśli
    postać jest spostrzegawcza i jest co wskazać — zwraca konkretny
    podszept; przy słabej percepcji zwraca mgliste przeczucie albo None.

    Gating po PERCEPCJI, nie po klasie/umiejętności (immersive sim)."""
    exploitable = [(nm, obs) for nm, obs in (observed or []) if obs]
    if not exploitable:
        return None
    if perception_mod(character) >= _PERCEPTION_HINT_THRESHOLD:
        nm, obs = exploitable[0]
        return f"Coś ci nie daje spokoju: {nm} — {obs[0]}."
    # Słaba percepcja: tylko mgliste przeczucie, bez wskazania rzeczy.
    return "Masz wrażenie, że dałoby się tu coś sprytnie wykorzystać — ale co?"
