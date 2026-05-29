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
    """Property materii na celu (z tagów)."""
    tags = getattr(target, "tags", None) or []
    return set(tags) & _MATTER_PROPS


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


# ── Display helper (element PL) ─────────────────────────────────────


def element_pl(damage_type: str) -> str:
    """Mapuje angielski damage_type na PL element. Fallback: zwraca
    wejście (dla „physical" itp.)."""
    return _DAMAGE_TO_ELEMENT.get(damage_type, damage_type)
