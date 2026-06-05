"""P29.67 — Magia jako warstwa silnika systemowego (A/4).

Czar NIE jest osobnym podsystemem combat — to ŹRÓDŁO, które wpada w te
same reguły co fizyka. Płomień działa jak koktajl zapalający, iskra jak
zwarcie, mara odpala lęk celu. Piszemy raz (systemic), magia tylko
PRODUKUJE sygnały.

Counterplay (design): mag potężny ale kruchy + limit many. Stąd mana
gating tutaj; odporność/strefy pustki przyjdą z exotic schools (A/4b).

AKWIZYCJA (świadomie follow-on): w normalnej grze gracz NIE zna zaklęć
(`flags["known_spells"]` puste) — „szary człowiek" zostaje szary, póki
nie wprowadzimy ksiąg/originu maga. Magia jest castowalna od ręki tylko
w arenie testowej (grant przy starcie) i w testach.

KROK A/4a (ten plik): mana + 4 żywioły + telekineza + iluzja — wszystkie
reużywają systemic. Egzotyczne szkoły (nekromancja/ferromancja/krew/
pustka) = A/4b.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from . import systemic as _sys
from .entity import Entity, T_OBJECT, T_MONSTER


# ── Katalog zaklęć (A/4a) ───────────────────────────────────────────
# kind: "element" → apply_environmental(damage_type); "push" → uderzenie
# na odległość; "illusion" → fałszywy bodziec odpalający psyche celu.
SPELLS: Dict[str, dict] = {
    "ogień": {"name": "Płomień",        "mana": 2, "kind": "element",
              "damage_type": "fire"},
    "prąd":  {"name": "Iskra",          "mana": 2, "kind": "element",
              "damage_type": "electric"},
    "kwas":  {"name": "Żrący Strumień", "mana": 2, "kind": "element",
              "damage_type": "acid"},
    "mróz":  {"name": "Szron",          "mana": 2, "kind": "element",
              "damage_type": "cold"},
    "telekineza": {"name": "Pchnięcie", "mana": 3, "kind": "push"},
    "iluzja":     {"name": "Mara",      "mana": 3, "kind": "illusion"},
    # ── Egzotyczne szkoły (A/4b) ──
    "nekromancja": {"name": "Wskrzeszenie", "mana": 4, "kind": "necro"},
    "ferromancja": {"name": "Magnetar",     "mana": 3, "kind": "ferro"},
    "krew":        {"name": "Krwawa Danina", "mana": 0, "hp_cost": 6,
                    "kind": "blood"},
    "pustka":      {"name": "Pustka",       "mana": 3, "kind": "void"},
}

# Podstawowy zestaw (żywioły + bazowe). Egzotyczne osobno.
CORE_SPELLS = ("ogień", "prąd", "kwas", "mróz", "telekineza", "iluzja")
EXOTIC_SPELLS = ("nekromancja", "ferromancja", "krew", "pustka")
ALL_SPELLS = CORE_SPELLS + EXOTIC_SPELLS


def resolve_school(token: Optional[str]) -> Optional[str]:
    """Mapuje wpisany przez gracza token (z diakrytykami lub bez) na
    kanoniczny klucz zaklęcia. „ogien"/„ogień"→„ogień"."""
    if not token:
        return None
    from .parser_core import fold
    f = fold(token)
    for key in SPELLS:
        if fold(key) == f:
            return key
    return None


# ── Mana (przechowywana w flags — bez migracji dataclass) ───────────


def _stat_mod(ch, stat: str) -> int:
    try:
        return int(ch.stat_mod(stat))
    except Exception:
        return (int((getattr(ch, "stats", {}) or {}).get(stat, 10)) - 10) // 2


def max_mana(ch) -> int:
    """Pula many skaluje się z INT (mag = intelekt). Min 0."""
    return max(0, 4 + 2 * _stat_mod(ch, "INT"))


def ensure_mana(ch) -> None:
    """Inicjalizuje manę na starcie, jeśli nieustawiona."""
    flags = getattr(ch, "flags", None)
    if flags is None:
        return
    if "max_mana" not in flags:
        flags["max_mana"] = max_mana(ch)
    if "mana" not in flags:
        flags["mana"] = int(flags["max_mana"])


def mana(ch) -> int:
    ensure_mana(ch)
    return int((getattr(ch, "flags", {}) or {}).get("mana", 0))


def spend_mana(ch, n: int) -> bool:
    ensure_mana(ch)
    flags = getattr(ch, "flags", None) or {}
    if int(flags.get("mana", 0)) < n:
        return False
    flags["mana"] = int(flags["mana"]) - n
    return True


def restore_mana(ch, n: int) -> None:
    ensure_mana(ch)
    flags = getattr(ch, "flags", None) or {}
    flags["mana"] = min(int(flags.get("max_mana", 0)),
                        int(flags.get("mana", 0)) + max(0, n))


def knows(ch, school: str) -> bool:
    known = (getattr(ch, "flags", {}) or {}).get("known_spells") or []
    return school in known


def learn(ch, school: str) -> None:
    flags = getattr(ch, "flags", None)
    if flags is None:
        return
    known = list(flags.get("known_spells") or [])
    if school not in known:
        known.append(school)
    flags["known_spells"] = known


def grant_core(ch) -> None:
    """Daje pełny zestaw zaklęć (arena / testy) — wszystkie szkoły."""
    for s in ALL_SPELLS:
        learn(ch, s)


# ── Rzucanie ────────────────────────────────────────────────────────


def _transient_source(school: str, spec: dict) -> Entity:
    """Ulotne „źródło" czaru — wpada w systemic jak fizyczny obiekt."""
    return Entity(key=f"czar_{school}", entity_type=T_OBJECT,
                  fallback_name=spec.get("name", school),
                  tags=(["uderzenie"] if spec.get("kind") == "push" else []),
                  damage_type=spec.get("damage_type", "physical"))


class CastResult:
    def __init__(self, ok: bool, lines: List[str], reason: str = ""):
        self.ok = ok
        self.lines = lines
        self.reason = reason   # "" / "unknown" / "no_mana" / "fizzle"


def cast(world, school: str, caster, target) -> CastResult:
    """Rzuca zaklęcie. Produkuje sygnał systemowy i pozwala silnikowi
    rozstrzygnąć skutek (materia / psyche). Mana gating tutaj."""
    spec = SPELLS.get(school)
    if spec is None or not knows(caster, school):
        return CastResult(False, [], "unknown")
    if mana(caster) < int(spec["mana"]):
        return CastResult(False, [], "no_mana")
    if target is None:
        return CastResult(False, [], "fizzle")

    kind = spec["kind"]
    name = spec["name"]
    cel = _sys._display(target)

    if kind in ("element", "push"):
        src = _transient_source(school, spec)
        res = _sys.apply_environmental(world, "czar", src, target)
        if not res.matched:
            # Czar trafia, ale cel nie ma podatności — minimalny efekt.
            # (push zawsze ma „uderzenie" base; element base też — więc
            # tu trafiamy rzadko, np. cel bez HP.)
            spend_mana(caster, int(spec["mana"]))
            return CastResult(True, [f"„{name}” pryska o {cel} bez wyraźnego "
                                     f"skutku."])
        spend_mana(caster, int(spec["mana"]))
        lead = (f"Rzucasz „{name}”. " if kind == "element"
                else f"„{name}” — niewidzialna siła uderza. ")
        return CastResult(True, [lead + ln for ln in res.lines] or [lead])

    if kind == "illusion":
        # Mara czyta UMYSŁ celu i podsuwa jego własny lęk/odrazę.
        fears = _sys.target_psyche(target, "lęk")
        disgusts = _sys.target_psyche(target, "odraza")
        if fears:
            res = _sys._apply_psyche(target, "przerażenie")
        elif disgusts:
            res = _sys._apply_psyche(target, "cofnięcie")
        else:
            spend_mana(caster, int(spec["mana"]))
            return CastResult(True, [f"„{name}” pełznie wokół {cel}, ale nie "
                                     f"znajduje w nim żadnego lęku."],
                              "fizzle")
        spend_mana(caster, int(spec["mana"]))
        return CastResult(True, [f"„{name}” przybiera kształt z najgłębszego "
                                 f"lęku celu. "] + list(res.lines))

    # ── Egzotyczne szkoły (A/4b) ──────────────────────────────────

    if kind == "necro":
        from .entity import T_CORPSE
        if getattr(target, "entity_type", None) != T_CORPSE:
            return CastResult(True, [f"„{name}” szuka zwłok do podniesienia, "
                                     f"ale {cel} jeszcze oddycha."], "fizzle")
        st = target.state if target.state is not None else {}
        if st.get("reanimated"):
            return CastResult(True, [f"{cel} już raz wstał. Drugi raz nie "
                                     f"da rady."], "fizzle")
        spend_mana(caster, int(spec["mana"]))
        # Wskrzeszenie: trup wstaje jako słaby, krótkotrwały sojusznik.
        st["reanimated"] = True
        target.state = st
        target.entity_type = T_MONSTER
        target.hp = target.max_hp = 6
        tags = list(getattr(target, "tags", None) or [])
        if "sojusznik" not in tags:
            tags.append("sojusznik")
        target.tags = tags
        return CastResult(True, [f"„{name}”: {cel} drga, wstaje i staje po "
                                 f"twojej stronie. Na krótko."])

    if kind == "ferro":
        spend_mana(caster, int(spec["mana"]))
        is_metal = "metal" in _sys.target_matter_props(target)
        ac_drop = 3 if is_metal else 1
        if hasattr(target, "ac"):
            target.ac = max(0, int(target.ac) - ac_drop)
        st = target.state if target.state is not None else {}
        statuses = st.setdefault("systemic_statuses", [])
        if "rozbrojony" not in statuses:
            statuses.append("rozbrojony")
        target.state = st
        dmg = 4 if is_metal else 1
        if getattr(target, "max_hp", 0) > 0:
            target.hp = max(0, int(target.hp) - dmg)
        flavor = ("Metal jęczy — pancerz wygina się do środka"
                  if is_metal else "Pole ledwie szarpie")
        return CastResult(True, [f"„{name}”: {flavor}. {cel} — broń wyrwana "
                                 f"z dłoni, AC w dół (-{dmg})."])

    if kind == "blood":
        hp_cost = int(spec.get("hp_cost", 6))
        if int(getattr(caster, "hp", 0)) <= hp_cost:
            return CastResult(False, [f"„{name}”: za mało krwi, by zapłacić "
                                      f"daninę."], "no_hp")
        caster.hp = int(caster.hp) - hp_cost          # paliwo = HP, nie mana
        dmg = 10
        healed = 0
        if getattr(target, "max_hp", 0) > 0:
            target.hp = max(0, int(target.hp) - dmg)
            healed = min(dmg // 2,
                         int(getattr(caster, "max_hp", 0)) - int(caster.hp))
            if healed > 0:
                caster.hp = int(caster.hp) + healed
        return CastResult(True, [f"„{name}”: tniesz własną dłoń (-{hp_cost} "
                                 f"HP). Krew leci ku {cel} (-{dmg}) i wraca "
                                 f"do ciebie (+{healed})."])

    if kind == "void":
        spend_mana(caster, int(spec["mana"]))
        had = bool((getattr(target, "state", None) or {}).get(
            "systemic_statuses"))
        _sys._clear_systemic(target)
        st = target.state if target.state is not None else {}
        statuses = st.setdefault("systemic_statuses", [])
        if "uciszony" not in statuses:
            statuses.append("uciszony")
        st["systemic_turns"] = max(int(st.get("systemic_turns", 0)), 2)
        target.state = st
        tail = (" Wszystkie zaklęcia z niego opadają."
                if had else "")
        return CastResult(True, [f"„{name}”: wokół {cel} gaśnie magia — "
                                 f"cisza, pustka.{tail}"])

    return CastResult(False, [], "unknown")
