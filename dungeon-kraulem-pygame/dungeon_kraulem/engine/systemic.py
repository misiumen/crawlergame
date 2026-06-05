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

# P29.65 — INFERENCJA właściwości z istniejących tagów contentu. Cały
# bestiariusz (141 szablonów) reaguje na silnik BEZ ręcznego tagowania
# każdego wpisu — jeden tag może implikować kilka właściwości
# (robot = metal + przewodzące). Mapowania celowo wąskie, żeby NIE było
# „wszystko płonie": tylko jednoznaczne materiały.
_TAG_INFERENCE = {
    # metal (kwas → korozja)
    "armored":    ("metal",),
    "machine":    ("metal", "przewodzące"),
    "mechanical": ("metal",),
    "robot":      ("metal", "przewodzące"),
    "drone":      ("metal", "przewodzące"),
    "construct":  ("metal",),
    "scrap":      ("metal",),
    "terminal":   ("metal", "przewodzące"),
    # przewodzące (prąd → porażenie)
    "electronic": ("przewodzące",),
    "electrical": ("przewodzące",),
    "electric":   ("przewodzące",),
    "wire":       ("przewodzące",),
    "spark":      ("przewodzące",),
    # łatwopalne (ogień → pożar)
    "wood":       ("łatwopalne",),
    "fungal":     ("łatwopalne",),
    "gas":        ("łatwopalne",),
    "plastic":    ("łatwopalne",),
    "paper":      ("łatwopalne",),
    "cloth":      ("łatwopalne",),
    "oil":        ("łatwopalne",),
    "grease":     ("łatwopalne",),
    # kruche (uderzenie → roztrzaskanie)
    "ceramic":    ("kruche",),
    # mokre (mróz → zamrożenie)
    "liquid":     ("mokre",),
    "water":      ("mokre",),
    "slime":      ("mokre",),
}

# Tagi, które czynią encję ŹRÓDŁEM żywiołu (aktywna energia — hazard /
# nasączony przedmiot). Pasywny „wire"/„metal" NIE jest źródłem.
_ELEMENT_TAG_SOURCE = {
    "electric":   "prąd",
    "electrical": "prąd",
    "spark":      "prąd",
    "fire":       "ogień",
    "flame":      "ogień",
    "burning":    "ogień",
    "acid":       "kwas",
    "caustic":    "kwas",
    "frost":      "mróz",
    "ice":        "mróz",
    "cold":       "mróz",
    "cryo":       "mróz",
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


# P29.63 — efekty TRWAŁE per synergia. Reguła materii zadaje natychmiast
# (wyżej), a tu deklaruje co zostaje na CELU i tyka turach walki:
#   dot/turns  — obrażenia na turę przez N tur (DoT)
#   stun       — szansa że cel traci turę (paraliż)
#   slow       — cel spowolniony (kara do trafienia / brak szarży)
# Bez tego synergia była jednorazowym hitem — „pożar" nie palił dalej.
_EFFECT_LINGER = {
    "pożar":          {"dot": 3, "turns": 3},
    "porażenie":      {"dot": 2, "turns": 2, "stun": 0.5},
    "korozja":        {"dot": 0, "turns": 0},   # AC w dół utrzymuje się samo
    "zamrożenie":     {"dot": 0, "turns": 2, "slow": True, "stun": 0.4},
    "roztrzaskanie":  {"dot": 0, "turns": 0},
}

# Flavor PL do logu tykania DoT (po statusie celu). Polish-only.
_TICK_FLAVOR = {
    "płonie":          "ogień trawi",
    "porażony":        "prąd dobija",
    "trawiony kwasem": "kwas żre",
    "zmrożony":        "szron krępuje",
    "zamrożony":       "lód krępuje",
    "ogłuszony":       "wstrząs dudni",
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
    # P29.65 — żywioł z tagów aktywnej energii (hazard/nasączony przedmiot).
    for t in tagset:
        el = _ELEMENT_TAG_SOURCE.get(t)
        if el:
            out.add(el)
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
        # P29.65 — inferencja z tagów contentu (jeden tag → kilka props).
        for p in _TAG_INFERENCE.get(t, ()):
            out.add(p)
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

    # P29.63 — efekt TRWAŁY (DoT / stun / slow) zapisany na cel, żeby
    # tykał w turach (combat woła systemic.tick co rundę).
    linger = _EFFECT_LINGER.get(effect_key)
    if linger:
        turns = int(linger.get("turns", 0))
        if int(linger.get("dot", 0)) > 0:
            st["systemic_dot"] = {"dmg": int(linger["dot"]),
                                  "turns": turns, "status": status}
        if linger.get("slow"):
            st["systemic_slow"] = True
        if linger.get("stun"):
            st["systemic_stun_chance"] = float(linger["stun"])
        if turns > 0:
            st["systemic_turns"] = turns
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
    # P29.63 — licznik żywotności (jeden dla całego efektu). DoT trwa
    # tyle co dot_turns; sam slow/stun bez DoT dostaje 2 tury.
    lifetime = dot_turns if dot_turns > 0 else (
        2 if (slow or stun_chance > 0) else 0)
    if lifetime > 0:
        st["systemic_turns"] = lifetime
    target.state = st

    return Interaction(
        matched=True, effect=f"baza_{element}", damage=dmg,
        lines=[line_tmpl.format(cel=_display(target), dmg=dmg)])


# ── Display helper (element PL) ─────────────────────────────────────


def element_pl(damage_type: str) -> str:
    """Mapuje angielski damage_type na PL element. Fallback: zwraca
    wejście (dla „physical" itp.)."""
    return _DAMAGE_TO_ELEMENT.get(damage_type, damage_type)


# ── Tykanie efektów trwałych w turach (P29.63 — głębia walki) ───────


def _st(target):
    """Bezpieczny dostęp do słownika stanu celu (Entity ma `.state`;
    Character trzyma stany gdzie indziej — systemic celuje w Entity)."""
    return getattr(target, "state", None)


@dataclass
class TickResult:
    """Co zdarzyło się celowi w tej turze od efektu systemowego."""
    damage: int = 0
    status: str = ""
    flavor: str = ""
    expired: bool = False
    hp: int = 0
    max_hp: int = 0


def tick(target) -> Optional[TickResult]:
    """Tyka efekty trwałe (DoT + żywotność) na celu o JEDNĄ turę.
    Zwraca TickResult, gdy coś jest aktywne, albo None. Stun/slow są
    konsumowane osobno (faza akcji wroga) — tu odliczamy ich żywotność
    i czyścimy po wygaśnięciu."""
    st = _st(target)
    if not st or int(st.get("systemic_turns", 0)) <= 0:
        return None

    dotinfo = st.get("systemic_dot")
    status = ""
    dmg = 0
    if isinstance(dotinfo, dict):
        status = dotinfo.get("status", "") or ""
        d = int(dotinfo.get("dmg", 0))
        if (d > 0 and getattr(target, "max_hp", 0) > 0
                and getattr(target, "is_alive", lambda: True)()):
            target.hp = max(0, int(getattr(target, "hp", 0)) - d)
            dmg = d
    if not status:
        statuses = st.get("systemic_statuses") or []
        status = statuses[0] if statuses else ""

    turns = int(st.get("systemic_turns", 0)) - 1
    expired = turns <= 0
    if expired:
        _clear_systemic(target)
    else:
        st["systemic_turns"] = turns

    return TickResult(
        damage=dmg, status=status,
        flavor=_TICK_FLAVOR.get(status, "efekt działa"),
        expired=expired,
        hp=int(getattr(target, "hp", 0)),
        max_hp=int(getattr(target, "max_hp", 0)))


def _clear_systemic(target) -> None:
    """Zdejmuje wszystkie tymczasowe efekty systemowe z celu (po
    wygaśnięciu). NIE rusza korozji/roztrzaskania — te mają turns=0,
    więc nigdy tu nie trafiają (AC w dół zostaje na stałe)."""
    st = _st(target)
    if not st:
        return
    for k in ("systemic_dot", "systemic_slow", "systemic_stun_chance",
              "systemic_turns"):
        st.pop(k, None)
    st["systemic_statuses"] = []


def is_slowed(target) -> bool:
    st = _st(target) or {}
    return bool(st.get("systemic_slow"))


# ── Odkrycie OTOCZENIA: obserwacje właściwości (P29.64) ─────────────
#
# `zbadaj pomieszczenie` ujawnia WŁAŚCIWOŚCI rzeczy, nie gotowe przepisy.
# Gracz sam dedukuje („łatwopalne + mam zapałki = podpalę"). To realizuje
# „odkrycie jako mechanika" + „mechaniki ukryte" — pokazujemy świat, nie
# instrukcję obsługi.


# Property celu → naturalna obserwacja PL (co gracz „widzi/czuje").
_PROP_OBSERVATION = {
    "łatwopalne":  "suche, łatwo zajmie się ogniem",
    "przewodzące": "wilgotne albo metalowe — poprowadzi prąd",
    "metal":       "z litego metalu",
    "mokre":       "ocieka wodą",
    "kruche":      "kruche, pęknie od porządnego ciosu",
}

# Element źródła (hazard / przedmiot) → obserwacja PL.
_ELEMENT_OBSERVATION = {
    "ogień": "bucha żarem",
    "prąd":  "trzaska iskrami — pod napięciem",
    "kwas":  "żrące opary, syczy",
    "mróz":  "wieje przejmującym chłodem",
}


def salient_observations(ent) -> List[str]:
    """Lista obserwacji PL o systemowo istotnych cechach encji
    (właściwości materii + niesiony żywioł). Pusta, gdy nic
    eksploatowalnego — wtedy obiekt jest po prostu tłem."""
    out: List[str] = []
    for prop in target_matter_props(ent):
        obs = _PROP_OBSERVATION.get(prop)
        if obs and obs not in out:
            out.append(obs)
    for el in source_elements(ent):
        obs = _ELEMENT_OBSERVATION.get(el)
        if obs and obs not in out:
            out.append(obs)
    return out


def roll_stun(target, rng) -> bool:
    """True, jeśli cel w tej turze traci akcję (paraliż od prądu/lodu)."""
    st = _st(target) or {}
    chance = st.get("systemic_stun_chance")
    if not chance:
        return False
    return rng.random() < float(chance)


# ── Rozprzestrzenianie ognia (reaktywne otoczenie) ──────────────────


def _is_flammable(ent) -> bool:
    return "łatwopalne" in target_matter_props(ent)


def spread_fire(world, room) -> List[str]:
    """Ogień z płonącej istoty/obiektu przeskakuje na JEDEN łatwopalny
    cel w pokoju (bounded: max jeden skok na turę, żeby pełzał a nie
    wybuchał). Zwraca linie logu PL. Pusta lista = nic się nie zajęło."""
    if room is None:
        return []
    ents = list(getattr(room, "entities", None) or [])
    burning = [e for e in ents if has_systemic_status(e, "płonie")]
    if not burning:
        return []
    for src in burning:
        for tgt in ents:
            if tgt is src or has_systemic_status(tgt, "płonie"):
                continue
            if _is_flammable(tgt):
                _apply_effect(tgt, "pożar", "płonie")
                return [f"Ogień przeskakuje na {_display(tgt)} — "
                        f"zajmuje się."]
    return []


# ── PSYCHIKA (P29.66) — reguły umysłu, nie materii ──────────────────
#
# Sygnaturowy mechanizm immersive sim: „boss boi się pająków" =
# `lęk:pajęczak` na bossie + istota/przedmiot z tożsamością `pajęczak` +
# JEDNA generyczna reguła. Piszesz raz, działa dla wszystkiego, co ktoś
# komuś rzuci/pokaże. Absurd emerguje sam, bez LLM i scriptu.
#
# Psyche to UKRYTA właściwość celu (tag z prefiksem, np. `lęk:robactwo`).
# Tożsamość ŹRÓDŁA to jego zwykłe tagi (czym JEST: robactwo, ogień, gad).
# Match tożsamości źródła ∩ psyche celu → efekt umysłowy.
#
# Prefiksy psyche (PL, internal):
#   lęk:<X>        — czego się boi  → przerażenie (panika, traci tury)
#   odraza:<X>     — co go brzydzi  → cofnięcie (wzdryga się, odsuwa)
#   pragnienie:<X> — czego pożąda   → rozproszenie (rzuca się ku temu)


_PSYCHE_PREFIXES = ("lęk", "odraza", "pragnienie")

# (prefix psyche, klucz efektu, profil trwały, szablon logu PL)
_PSYCHE_EFFECT = {
    "przerażenie": {
        "status": "przerażony", "stun": 0.8, "turns": 3,
        "line": "{cel} wpada w panikę — kuli się, zasłania, traci głowę.",
    },
    "cofnięcie": {
        "status": "cofnięty", "slow": True, "turns": 2,
        "line": "{cel} wzdryga się z obrzydzeniem i odsuwa, byle dalej.",
    },
    "rozproszenie": {
        "status": "rozproszony", "slow": True, "turns": 2,
        "line": "{cel} traci cię z oczu — rzuca się ku temu, czego pożąda.",
    },
}

# Kolejność = priorytet (strach > odraza > pragnienie).
_PSYCHE_RULES = (
    ("lęk", "przerażenie"),
    ("odraza", "cofnięcie"),
    ("pragnienie", "rozproszenie"),
)


def target_psyche(target, prefix: str) -> Set[str]:
    """Zbiór wartości psyche celu dla danego prefiksu (np. lęk:robactwo
    → {'robactwo'})."""
    out: Set[str] = set()
    pre = prefix + ":"
    for t in (getattr(target, "tags", None) or []):
        if isinstance(t, str) and t.startswith(pre):
            v = t[len(pre):].strip()
            if v:
                out.add(v)
    return out


def has_psyche(target) -> bool:
    """Czy cel ma jakąkolwiek deklarację psyche (lęk/odraza/pragnienie)."""
    for t in (getattr(target, "tags", None) or []):
        if isinstance(t, str) and any(
                t.startswith(p + ":") for p in _PSYCHE_PREFIXES):
            return True
    return False


def _source_identity(source) -> Set[str]:
    """Czym źródło JEST — jego zwykłe tagi (bez prefiksów psyche)."""
    return {t for t in (getattr(source, "tags", None) or [])
            if isinstance(t, str) and ":" not in t}


def _apply_psyche(target, effect_key: str) -> Interaction:
    prof = _PSYCHE_EFFECT[effect_key]
    st = target.state if target.state is not None else {}
    statuses = st.setdefault("systemic_statuses", [])
    if prof["status"] not in statuses:
        statuses.append(prof["status"])
    if prof.get("stun"):
        st["systemic_stun_chance"] = float(prof["stun"])
    if prof.get("slow"):
        st["systemic_slow"] = True
    st["systemic_turns"] = int(prof["turns"])
    target.state = st
    return Interaction(matched=True, effect=effect_key,
                       lines=[prof["line"].format(cel=_display(target))])


def resolve_psyche(world, verb: str, source, target) -> Interaction:
    """Reguła umysłu: tożsamość źródła ∩ psyche celu → efekt. Czasownik
    (rzuć / pokaż / podrzuć) jest już zawężony przez router łańcucha;
    o efekcie decyduje, KTÓRA psyche celu trafiona."""
    if source is None or target is None:
        return Interaction(matched=False)
    ident = _source_identity(source)
    if not ident:
        return Interaction(matched=False)
    for prefix, effect_key in _PSYCHE_RULES:
        psyche = target_psyche(target, prefix)
        if psyche and (ident & psyche):
            return _apply_psyche(target, effect_key)
    return Interaction(matched=False)


# ── BODŹCE + REAKCJE (P29.68) — hałas/światło/zapach jako NARZĘDZIE ──
#
# Każdy mob ma profil reakcji na bodziec (ciekawski/płochliwy/agresywny/
# obojętny). Gracz emituje bodziec (hałas, błysk, zapach) → mob reaguje
# WEDŁUG PROFILU, nie wedle płaskiej liczby. Hałas przestaje być karą
# (stary noise = sama eskalacja threatu) i staje się dźwignią: zwab
# ciekawskiego, spłosz płochliwego, ściągnij agresywnego na wabik.


_REACTION_PROFILES = ("ciekawski", "płochliwy", "agresywny", "obojętny")

# Inferencja profilu z tagów (gdy brak jawnego `reakcja:<profil>`).
# Priorytet skanu: agresja > ciekawość > płochliwość > obojętność.
def reaction_profile(ent) -> str:
    tags = set(getattr(ent, "tags", None) or [])
    for tg in tags:
        if isinstance(tg, str) and tg.startswith("reakcja:"):
            v = tg.split(":", 1)[1].strip()
            if v in _REACTION_PROFILES:
                return v
    if tags & {"brute", "pack", "hunter", "aggressive", "biting", "rabid"}:
        return "agresywny"
    if tags & {"cunning", "curious", "mental", "sensor", "scavenger"}:
        return "ciekawski"
    if tags & {"beast", "small", "prey", "skittish", "vermin", "robactwo"}:
        return "płochliwy"
    if tags & {"construct", "robot", "machine", "drone", "undead", "ai"}:
        return "obojętny"
    return "obojętny"


# profil → (status, profil_efektu, szablon_logu). Wszystkie nie-obojętne
# zabierają mobowi turę przeciw graczowi (rusza ku/od hałasu).
_STIMULUS_REACTION = {
    "ciekawski": ("zwabiony", {"slow": True, "turns": 2},
                  "{cel} nadstawia uszu i rusza w stronę hałasu."),
    "płochliwy": ("spłoszony", {"stun": 0.6, "turns": 2},
                  "{cel} płoszy się, kuli i pierzcha od dźwięku."),
    "agresywny": ("rozjuszony", {"stun": 0.5, "turns": 1},
                  "{cel} wpada w furię i szarżuje na źródło hałasu."),
    "obojętny":  (None, None, "{cel} nawet nie drgnie."),
}


def apply_stimulus(target, bodziec: str = "hałas") -> Interaction:
    """Emituje bodziec na cel; reakcja zależy od profilu. Zwraca
    Interaction (matched=False dla obojętnych — brak skutku)."""
    if target is None:
        return Interaction(matched=False)
    profile = reaction_profile(target)
    status, prof, tmpl = _STIMULUS_REACTION.get(
        profile, (None, None, "{cel} nie reaguje."))
    line = tmpl.format(cel=_display(target))
    if status is None or prof is None:
        return Interaction(matched=False, lines=[line])
    st = target.state if target.state is not None else {}
    statuses = st.setdefault("systemic_statuses", [])
    if status not in statuses:
        statuses.append(status)
    if prof.get("slow"):
        st["systemic_slow"] = True
    if prof.get("stun"):
        st["systemic_stun_chance"] = float(prof["stun"])
    st["systemic_turns"] = int(prof.get("turns", 1))
    target.state = st
    return Interaction(matched=True, effect=f"bodziec_{profile}",
                       lines=[line])
