"""P29.43 — System rarity dla itemów (i potencjalnie monsterów /
encounterów).

Standardowy 5-stopniowy fantasy naming (jak Diablo / Path of Exile /
D&D loot tables):

  common      — biały, podstawowy sprzęt, sól ziemi (pospolity)
  uncommon    — zielony, lepszy materiał / drobny bonus (niepospolity)
  rare        — niebieski, wyraźny power-spike (rzadki)
  epic        — fioletowy, klasowy gear końcówki gry (epicki)
  legendary   — pomarańczowo-złoty, unikat, często meta-unlocked
                (legendarny)

Field-based (`rarity: str = "common"` na template'cie / state),
nie tag-based — żeby dało się sortować, klasyfikować i porównywać
liniowo. Tagi mogą równolegle ujednoznaczniać (`tag: "legendary"` w
display sortowaniu), ale field jest source of truth.

Wagi loot per piętro: rzadsze itemy stają się dostępne głębiej —
common dominują przez całą grę, ale od F8 pojawiają się rare, od
F12 epic, legendary tylko z boss dropów / sponsor drop-podów / meta-
unlocków.
"""
from __future__ import annotations
from typing import Dict, List


# ── Stopnie (klucze field, sortowalne) ───────────────────────────────

RARITY_COMMON     = "common"
RARITY_UNCOMMON   = "uncommon"
RARITY_RARE       = "rare"
RARITY_EPIC       = "epic"
RARITY_LEGENDARY  = "legendary"

ALL_RARITIES = (
    RARITY_COMMON,
    RARITY_UNCOMMON,
    RARITY_RARE,
    RARITY_EPIC,
    RARITY_LEGENDARY,
)

# Order index — przyda się do sortowania ekwipunku.
_RARITY_ORDER: Dict[str, int] = {r: i for i, r in enumerate(ALL_RARITIES)}


# ── Polskie etykiety ──────────────────────────────────────────────────

_RARITY_PL: Dict[str, str] = {
    RARITY_COMMON:    "pospolity",
    RARITY_UNCOMMON:  "niepospolity",
    RARITY_RARE:      "rzadki",
    RARITY_EPIC:      "epicki",
    RARITY_LEGENDARY: "legendarny",
}


def rarity_pl(rarity: str) -> str:
    """Polski display name. Fallback do raw klucza dla nieznanych."""
    return _RARITY_PL.get(rarity, rarity)


def rarity_order(rarity: str) -> int:
    """0..4 — wyższe = rzadsze. Sortowanie itemów w panelu."""
    return _RARITY_ORDER.get(rarity, 0)


def is_valid_rarity(rarity: str) -> bool:
    return rarity in _RARITY_ORDER


# ── Kolory UI ─────────────────────────────────────────────────────────
#
# Kolory RGB w stylu Diablo. UI panel ekwipunku renderuje nazwę
# itemu w odpowiednim kolorze przez rarity_color(rarity).

_RARITY_COLORS: Dict[str, tuple] = {
    RARITY_COMMON:    (200, 200, 200),   # biały szary
    RARITY_UNCOMMON:  (90, 200, 90),     # zielony
    RARITY_RARE:      (90, 140, 240),    # niebieski
    RARITY_EPIC:      (180, 90, 220),    # fioletowy
    RARITY_LEGENDARY: (240, 165, 60),    # pomarańczowo-złoty
}


def rarity_color(rarity: str) -> tuple:
    """RGB tuple. Fallback do common-szarego."""
    return _RARITY_COLORS.get(rarity, _RARITY_COLORS[RARITY_COMMON])


# ── Wagi lootu per piętro ─────────────────────────────────────────────
#
# Loot generator (gdzie tylko losuje z itemów) bierze wagę per rarity
# dla bieżącego piętra. Wagi dobrane tak, żeby:
#   * Floor 1-3:  common dominuje (90%), uncommon czasem
#   * Floor 4-7:  common nadal trzon, uncommon częsty, rare rzadko
#   * Floor 8-11: rare zauważalny, epic pierwszy raz
#   * Floor 12-15: epic regularnie, legendary sporadycznie
#   * Floor 16-18: epic dominują, legendary realne
#
# Legendarne items i tak są w większości meta-unlocked (P29.34/.37),
# więc wagi to drugi gatekeeper.

_FLOOR_RARITY_WEIGHTS: List[tuple] = [
    # (floor_min, weights: dict[rarity, weight])
    (1,  {"common": 90, "uncommon": 10, "rare": 0,  "epic": 0,  "legendary": 0}),
    (4,  {"common": 65, "uncommon": 25, "rare": 9,  "epic": 1,  "legendary": 0}),
    (8,  {"common": 45, "uncommon": 30, "rare": 18, "epic": 6,  "legendary": 1}),
    (12, {"common": 30, "uncommon": 30, "rare": 25, "epic": 12, "legendary": 3}),
    (16, {"common": 20, "uncommon": 25, "rare": 28, "epic": 20, "legendary": 7}),
]


def rarity_weights_for_floor(floor_num: int) -> Dict[str, int]:
    """Zwraca dict[rarity_key -> weight] dla danego piętra. Klamruje
    do najwyższego pasującego progu — F18 dziedziczy F16+ tabelę."""
    best = _FLOOR_RARITY_WEIGHTS[0][1]
    for thr, w in _FLOOR_RARITY_WEIGHTS:
        if floor_num >= thr:
            best = w
    return dict(best)


def pick_rarity_for_floor(rng, floor_num: int) -> str:
    """Wylosuj rarity dla itemu który ma trafić na piętro `floor_num`.
    Generator lootu używa tego do wybrania KORYTARZA rarity, a potem
    z tej rarity-puli wybiera konkretny item (z istniejących tagów,
    biome filter itd.)."""
    weights = rarity_weights_for_floor(floor_num)
    keys = list(weights.keys())
    ws = [max(0, weights[k]) for k in keys]
    if sum(ws) == 0:
        return RARITY_COMMON
    return rng.choices(keys, weights=ws, k=1)[0]


# ── Item rarity lookup ────────────────────────────────────────────────

def item_rarity(item_template: dict) -> str:
    """Zwraca rarity z item template. Fallback: common. Akceptuje
    zarówno field „rarity" jak i (fallback) tag "rare" / „legendary"
    żeby pre-P29.43 dane nie wybuchały."""
    if not isinstance(item_template, dict):
        return RARITY_COMMON
    r = item_template.get("rarity")
    if isinstance(r, str) and is_valid_rarity(r):
        return r
    # Legacy fallback z tagów.
    tags = item_template.get("tags") or []
    for t in tags:
        if t in _RARITY_ORDER:
            return t
    return RARITY_COMMON


def entity_rarity(entity) -> str:
    """Z Entity instance. Najpierw state.rarity (jeśli pamiętany),
    potem template lookup z `items.ITEM_TEMPLATES` po key, fallback
    common."""
    if entity is None:
        return RARITY_COMMON
    state = getattr(entity, "state", None) or {}
    r = state.get("rarity")
    if isinstance(r, str) and is_valid_rarity(r):
        return r
    try:
        from ..content.items import ITEM_TEMPLATES
        proto = ITEM_TEMPLATES.get(getattr(entity, "key", ""), {})
        return item_rarity(proto)
    except Exception:
        return RARITY_COMMON
