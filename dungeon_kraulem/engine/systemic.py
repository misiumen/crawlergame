"""P29.61 — Systemowy silnik interakcji (immersive sim core).

Jedna maszyna reguł, której używają combat, hazardy, crafting i (później)
magia. Reguły dopasowują TAGI, nie konkretne obiekty — stąd emergentne
i absurdalne rozwiązania bez LLM i bez scriptowania per-encounter.

„Boss boi się pająków" = `lęki:["pajęczak"]` na bossie + pająki istnieją
jako łapalne istoty z tagiem `pajęczak` + JEDNA generyczna reguła
(rzuć czymś z tagiem ∩ lęki → przerażenie). Regułę piszesz raz, działa
dla wszystkiego otagowanego.

KROK 1 (ten plik): resolver + 5 reguł MATERII.
  ogień      + łatwopalne  → pożar
  prąd       + przewodzące → porażenie
  kwas       + metal       → korozja
  mróz       + mokre       → zamrożenie
  uderzenie  + kruche      → roztrzaskanie

Kolejne kroki dokładają warstwy (ciało / psychika / społeczne / magia)
jako nowe reguły w tym samym resolverze.

TAGI (decyzja user 2026-05-29, wariant I):
  * Nowe property tagi PO POLSKU: łatwopalne, przewodzące, metal,
    mokre, kruche, ...
  * Istniejący `damage_type` zostaje angielski wewnętrznie (fire/acid/
    electric/cold — wbity w combat) i jest mapowany na PL „element"
    tylko w tej warstwie (_DAMAGE_TO_ELEMENT).
  * Gracz NIGDY nie widzi angielskiego — log lines są PL.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ── Element mapping (damage_type EN → element PL) ───────────────────


_DAMAGE_TO_ELEMENT: Dict[str, str] = {
    "fire":     "ogień",
    "electric": "prąd",
    "acid":     "kwas",
    "cold":     "mróz",
    # "physical" → brak elementu materii (zwykłe obrażenia)
}


# Tagi broni/źródła które liczą się jako uderzenie (impact).
_IMPACT_TAGS = frozenset({"blunt", "heavy", "obuch", "ciężkie", "uderzenie"})

# Wszystkie PL elementy które źródło może deklarować wprost przez tag
# (np. crafted koktajl z tagiem „ogień", czar żywiołów z tagiem „mróz").
_PL_ELEMENTS = frozenset({"ogień", "prąd", "kwas", "mróz", "uderzenie"})


# ── Property tagi celu (materia) ────────────────────────────────────


_MATTER_PROPS = frozenset({
    "łatwopalne", "przewodzące", "metal", "mokre", "kruche",
})

# P29.61 — aliasy EN→PL dla istniejącego contentu (tagi sprzed
# immersive-sim). Pozwalają silnikowi działać NA ISTNIEJĄCYCH mobach
# i obiektach (flammable/fragile/glass...) zanim krok 2 (obtagowanie)
# sformalizuje wszystko na PL. Gracz i tak nigdy nie widzi tych tagów.
_PROP_ALIASES = {
    "flammable":  "łatwopalne",
    "conductive": "przewodzące",
    "wet":        "mokre",
    "fragile":    "kruche",
    "glass":      "kruche",
    "metal":      "metal",   # ten sam po obu stronach
}


# ── Wynik interakcji ────────────────────────────────────────────────


@dataclass
class Interaction:
    """Wynik zastosowania źródła na celu."""
    matched: bool = False
    effect: str = ""               # klucz efektu (np. „pożar")
    lines: List[str] = field(default_factory=list)  # log PL
    damage: int = 0                # natychmiastowe obrażenia (jeśli są)
    ac_delta: int = 0              # zmiana AC celu (korozja)


# ── Reguły materii ──────────────────────────────────────────────────
#
# (element_źródła, property_celu, klucz_efektu, status_celu,
#  szablon_logu)  — {cel} podstawiany display name.


_MATTER_RULES = [
    ("ogień", "łatwopalne", "pożar", "płonie",
     "{cel} staje w płomieniach. Ogień szuka, czego się chwycić dalej."),
    ("prąd", "przewodzące", "porażenie", "porażony",
     "Prąd przeskakuje przez {cel}. Iskry, zapach spalenizny."),
    ("kwas", "metal", "korozja", "skorodowany",
     "Kwas wgryza się w metal: {cel}. Coś syczy i mięknie."),
    ("mróz", "mokre", "zamrożenie", "zamrożony",
     "Wilgoć na {cel} zamarza w sekundę. Ruch zamiera."),
    ("uderzenie", "kruche", "roztrzaskanie", "roztrzaskany",
     "{cel} pęka z trzaskiem. Odłamki rozsypują się po podłodze."),
]


# Natychmiastowe efekty mechaniczne (baseline; pełna integracja DoT /
# rozprzestrzenianie / strefa przyjdzie w krokach combat-integration).
_EFFECT_DAMAGE = {
    "pożar":          4,   # + DoT w przyszłym kroku
    "porażenie":      5,
    "korozja":        0,   # głównie AC down
    "zamrożenie":     0,   # głównie unieruchomienie
    "roztrzaskanie":  8,   # kruche obiekty często giną od razu
}
_EFFECT_AC_DELTA = {
    "korozja": -2,
}


# ── Odczyt sygnałów ze źródła / celu ────────────────────────────────


def source_elements(source) -> Set[str]:
    """Zbiór elementów PL, które niesie źródło. Z `damage_type`
    (mapowany) + z tagów (impact + wprost zadeklarowane PL elementy)."""
    out: Set[str] = set()
    dt = getattr(source, "damage_type", None) or ""
    el = _DAMAGE_TO_ELEMENT.get(dt)
    if el:
        out.add(el)
    tags = getattr(source, "tags", None) or []
    tagset = set(tags)
    if tagset & _IMPACT_TAGS:
        out.add("uderzenie")
    out |= (tagset & _PL_ELEMENTS)
    return out


def target_matter_props(target) -> Set[str]:
    """Property materii na celu — z tagów PL + aliasy EN→PL dla
    istniejącego contentu (flammable→łatwopalne, glass→kruche, ...)."""
    tags = getattr(target, "tags", None) or []
    out: Set[str] = set()
    for t in tags:
        if t in _MATTER_PROPS:
            out.add(t)
        elif t in _PROP_ALIASES:
            out.add(_PROP_ALIASES[t])
    return out


def _display(target) -> str:
    try:
        nm = target.display_name()
        if nm:
            return nm
    except Exception:
        pass
    return getattr(target, "fallback_name", "obiekt")


# ── Aplikacja efektu na cel ─────────────────────────────────────────


def _apply_effect(target, effect_key: str, status: str) -> Interaction:
    """Nakłada status systemowy (trwały stan celu, np. „płonie") +
    natychmiastowe obrażenia/AC. `effect_key` to typ interakcji
    („pożar"); `status` to warunek nakładany na cel („płonie").
    Zwraca częściowy Interaction (damage/ac_delta) do złożenia."""
    st = target.state if target.state is not None else {}
    statuses = st.setdefault("systemic_statuses", [])
    if status and status not in statuses:
        statuses.append(status)
    target.state = st

    dmg = _EFFECT_DAMAGE.get(effect_key, 0)
    ac_delta = _EFFECT_AC_DELTA.get(effect_key, 0)

    # Natychmiastowe obrażenia (jeśli cel ma HP).
    if dmg > 0 and getattr(target, "max_hp", 0) > 0:
        target.hp = max(0, int(getattr(target, "hp", 0)) - dmg)
    # Korozja AC (jeśli cel ma AC).
    if ac_delta and hasattr(target, "ac"):
        target.ac = max(0, int(target.ac) + ac_delta)

    return Interaction(matched=True, effect=effect_key,
                       damage=dmg, ac_delta=ac_delta)


# ── Resolver ────────────────────────────────────────────────────────


def resolve(world, verb: str, source, target) -> Interaction:
    """Sprawdza reguły systemowe dla (czasownik, źródło, cel).
    Zwraca pierwszy pasujący Interaction, albo Interaction(matched=False).

    `verb` — np. „rzuć", „wepchnij", „polej". Dla reguł materii
    czasownik jest nieistotny (rzut/wepchnięcie/polanie wywołują tę
    samą reakcję), ale zostaje w sygnaturze dla reguł verb-specific
    w kolejnych krokach (psychika: „pokaż" vs „rzuć").
    """
    if source is None or target is None:
        return Interaction(matched=False)

    src_el = source_elements(source)
    if not src_el:
        return Interaction(matched=False)
    tgt_props = target_matter_props(target)
    if not tgt_props:
        return Interaction(matched=False)

    for element, prop, effect_key, status, log_tmpl in _MATTER_RULES:
        if element in src_el and prop in tgt_props:
            result = _apply_effect(target, effect_key, status)
            result.lines = [log_tmpl.format(cel=_display(target))]
            return result

    return Interaction(matched=False)


def has_systemic_status(target, effect_key: str) -> bool:
    """Czy cel ma nałożony dany status systemowy."""
    st = getattr(target, "state", None) or {}
    return effect_key in (st.get("systemic_statuses") or [])


# ── Interakcja środowiskowa (hazard jako źródło) ────────────────────


# Bazowy efekt środowiskowy PER ŻYWIOŁ — nawet bez synergii tagów
# każdy żywioł działa INACZEJ (flavor + mechanika), żeby „w kwas" ≠
# „w kable". # TODO TUNE
#   element: (obrażenia, status, dot_na_turę, tury_dot, slow, stun_szansa,
#             szablon_logu)
_ELEMENT_BASE = {
    "kwas":  (5, "trawiony kwasem", 2, 2, False, 0.0,
              "Kwas obejmuje {cel}. Skóra syczy, dym gryzie w oczy — "
              "i nie przestaje (-{dmg})."),
    "prąd":  (6, "porażony", 0, 0, False, 0.4,
              "Prąd przeszywa {cel}. Mięśnie tężeją, szczęka szczęka, "
              "z futra idzie dym (-{dmg})."),
    "ogień": (4, "płonie", 3, 3, False, 0.0,
              "{cel} łapie ogień. Smród palonego włosia, panika "
              "(-{dmg})."),
    "mróz":  (3, "zmrożony", 0, 0, True, 0.0,
              "Szron oblepia {cel}. Ruchy grzęzną, oddech staje "
              "(-{dmg})."),
    "uderzenie": (5, "ogłuszony", 0, 0, False, 0.0,
              "{cel} obrywa z impetem. Coś chrupie (-{dmg})."),
}

# Priorytet wyboru żywiołu, gdy źródło niesie kilka.
_ELEMENT_PRIORITY = ("ogień", "prąd", "kwas", "mróz", "uderzenie")


def _primary_element(elements: Set[str]) -> Optional[str]:
    for el in _ELEMENT_PRIORITY:
        if el in elements:
            return el
    return None


def apply_environmental(world, verb: str, source, target) -> Interaction:
    """Pełna interakcja środowiskowa. Synergia reguł materii ma
    pierwszeństwo (pożar/korozja/porażenie/zamrożenie/roztrzaskanie —
    każda już odrębna). Bez synergii: bazowy efekt PER ŻYWIOŁ, też
    odrębny — kwas żre (DoT), prąd razi (stun), ogień pali (DoT),
    mróz mrozi (slow), uderzenie ogłusza. Stąd „w kwas" ≠ „w kable"
    feel-owo i mechanicznie nawet na zwykłym celu.

    DoT/stun/slow są zapisywane na state celu; ich tykanie w turach
    realizuje krok integracji combat (tu: natychmiastowy hit +
    odrębny status + flavor)."""
    if source is None or target is None:
        return Interaction(matched=False)

    syn = resolve(world, verb, source, target)
    if syn.matched:
        return syn

    element = _primary_element(source_elements(source))
    base = _ELEMENT_BASE.get(element) if element else None
    if base is None or getattr(target, "max_hp", 0) <= 0:
        return Interaction(matched=False)

    dmg, status, dot, dot_turns, slow, stun_chance, line_tmpl = base
    target.hp = max(0, int(getattr(target, "hp", 0)) - dmg)

    st = target.state if target.state is not None else {}
    statuses = st.setdefault("systemic_statuses", [])
    if status not in statuses:
        statuses.append(status)
    # Zapisz przedłużone efekty do realizacji w turach (krok combat).
    if dot > 0:
        st["systemic_dot"] = {"dmg": dot, "turns": dot_turns,
                              "status": status}
    if slow:
        st["systemic_slow"] = True
    if stun_chance > 0:
        st["systemic_stun_chance"] = stun_chance
    target.state = st

    return Interaction(
        matched=True, effect=f"baza_{element}", damage=dmg,
        lines=[line_tmpl.format(cel=_display(target), dmg=dmg)])


# ── Display helper (element PL) ─────────────────────────────────────


def element_pl(damage_type: str) -> str:
    """Mapuje angielski damage_type na PL element. Fallback: zwraca
    wejście (dla „physical" itp.)."""
    return _DAMAGE_TO_ELEMENT.get(damage_type, damage_type)
