"""P29.34 — Persistent meta-progression / unlock catalog.

DCC-faithful design: every run is fully random and ephemeral.
What persists between runs is NOT difficulty or "harder mode"
unlocks — it's the menu of available choices at character
creation. Each end-of-run scan adds new species / origins /
companions / legendary items to the available pool.

Replaces the empty `new_game_plus` flag from P29.26.

Architecture:
  * UNLOCK_CATALOG: dict keyed by unlock_id with:
      - kind: "species" | "origin" | "companion" | "item" | "class"
      - label_pl: short display name
      - description_pl: 1-line explanation of what unlocks it
      - reward_pl: 1-line description of what it grants
      - eval(world, victory) -> bool: closure that inspects the
        finished run and decides if this unlock qualifies
  * evaluate_run_for_unlocks(world, victory) -> list[str]
        Returns newly-qualifying unlock keys (excluding ones
        already unlocked).
  * record_unlocks_for_run(world, victory)
        Calls evaluate + writes each new key via
        run_history.unlock(key). Logs a "Sezon otwiera nowe
        opcje:" line per unlock for the player.
  * unlocked_species() / unlocked_origins() / unlocked_companions() /
    unlocked_items() — convenience filtered views of the catalog
    intersected with the player's persistent unlock list.

Character creation reads `unlocked_species()` + `unlocked_origins()`
to extend the pickers; floor generation reads `unlocked_items()` for
legendary drops.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class UnlockDef:
    key: str
    kind: str               # species | origin | companion | item | class
    label_pl: str
    description_pl: str
    reward_pl: str
    eval_fn: Optional[Callable] = None    # (world, victory) -> bool


# ── Eval closures ───────────────────────────────────────────────────────
#
# All take the same signature (world, victory: bool) -> bool. They peek
# at the CURRENT character + sponsor attention + run summary fields to
# decide. World is in the post-run state (death/victory both fire after
# all state mutations).

def _has_attention(world, key: str, threshold: int) -> bool:
    try:
        from . import sponsors as _sp
        return int(_sp.get_attention(world, key)) >= threshold
    except Exception:
        return False


def _floor_reached(world, n: int) -> bool:
    try:
        return int(getattr(world.character, "run_max_floor_reached", 1) or 1) >= n
    except Exception:
        return False


def _audience_peak(world) -> int:
    try:
        return int(getattr(world.character, "run_audience_peak", 0) or 0)
    except Exception:
        return 0


def _victory_against(world, victory: bool, achievement_key: str) -> bool:
    """True when this run unlocked the given achievement."""
    try:
        ch = world.character
        return achievement_key in (ch.unlocked_achievements or [])
    except Exception:
        return False


def _eval_drugi_cykl(world, victory): return True      # any run finished
def _eval_mutant(world, victory):     return _floor_reached(world, 12)
def _eval_grzybica(world, victory):
    return _victory_against(world, victory, "boss_padl_pierwszy") and \
           _floor_reached(world, 12)
def _eval_cyborg(world, victory):
    return _has_attention(world, "kult_recyklingu", 10)
def _eval_pamietajacy(world, victory):
    return _has_attention(world, "ministerstwo_pamieci", 10)
def _eval_kolyski_anti_hosta(world, victory):
    return victory and _victory_against(world, victory, "finalista_sezonu")
def _eval_origin_sponsorowany(world, victory):
    # Finish with at least one sponsor at attention ≥ 10.
    try:
        from . import sponsors as _sp
        att = _sp._attention_dict(world)
        return any(int(v) >= 10 for v in att.values())
    except Exception:
        return False
def _eval_origin_zhanbiony(world, victory):
    return _audience_peak(world) >= 70
def _eval_papuga(world, victory):
    return _has_attention(world, "kanal_7_krawedz", 15)
def _eval_total_runs(world, victory, n: int) -> bool:
    """Lazy-import run_history to avoid cycle."""
    try:
        from . import run_history as _rh
        return int(_rh.meta().get("total_runs", 0)) + 1 >= n
        # +1 because this fires BEFORE record_run updates the counter
        # on death; we want the threshold reached AFTER this run lands.
    except Exception:
        return False


# ── Catalog ─────────────────────────────────────────────────────────────

UNLOCK_CATALOG: Dict[str, UnlockDef] = {

    # ── Species (replaces Character.species_key default flow) ──────────
    "species_mutant_chemiczny": UnlockDef(
        key="species_mutant_chemiczny", kind="species",
        label_pl="Mutant chemiczny",
        description_pl="Przeżyj piętro 12 (FUNGAL_BLOOM).",
        reward_pl="+1 CON, odporność na truciznę, podatność na ogień.",
        eval_fn=_eval_mutant,
    ),
    "species_grzybica": UnlockDef(
        key="species_grzybica", kind="species",
        label_pl="Grzybica",
        description_pl="Pokonaj Matkę Zarodników na piętrze 12.",
        reward_pl="+1 WIS, powolna regeneracja, grzybowa ręka widoczna.",
        eval_fn=_eval_grzybica,
    ),
    "species_cyborg_recyklingu": UnlockDef(
        key="species_cyborg_recyklingu", kind="species",
        label_pl="Cyborg Recyklingu",
        description_pl="Zakończ sezon z uwagą Kultu Recyklingu ≥10.",
        reward_pl="+1 STR, mechaniczna kończyna (naprawialna złomem).",
        eval_fn=_eval_cyborg,
    ),
    "species_pamietajacy": UnlockDef(
        key="species_pamietajacy", kind="species",
        label_pl="Pamiętający",
        description_pl="Zakończ sezon z uwagą Ministerstwa Pamięci ≥10.",
        reward_pl="+1 INT, czasem pamiętasz to, czego nie widziałeś.",
        eval_fn=_eval_pamietajacy,
    ),
    "species_kolyski_anti_hosta": UnlockDef(
        key="species_kolyski_anti_hosta", kind="species",
        label_pl="Kołyska Konferansjera",
        description_pl="Wygraj sezon — pokonaj Prezesa Syndykatu.",
        reward_pl="+1 do wszystkich statystyk; Konferansjer osobiście "
                  "komentuje twój run.",
        eval_fn=_eval_kolyski_anti_hosta,
    ),

    # ── Origins (extends BACKGROUNDS at character creation) ────────────
    "origin_drugi_cykl": UnlockDef(
        key="origin_drugi_cykl", kind="origin",
        label_pl="Drugi cykl",
        description_pl="Przetrwaj swój pierwszy sezon (zwycięstwo lub porażka).",
        reward_pl="Zaczynasz z widownią +5 i blizną opowiadającą się sama.",
        eval_fn=_eval_drugi_cykl,
    ),
    "origin_sponsorowany": UnlockDef(
        key="origin_sponsorowany", kind="origin",
        label_pl="Sponsorowany Uczestnik",
        description_pl="Zakończ sezon z uwagą dowolnego sponsora ≥10.",
        reward_pl="Startujesz z kontraktem — większe bonusy uwagi, ale "
                  "podwójne kary za nielubiane akcje.",
        eval_fn=_eval_origin_sponsorowany,
    ),
    "origin_zhanbiony_showman": UnlockDef(
        key="origin_zhanbiony_showman", kind="origin",
        label_pl="Zhańbiony Showman",
        description_pl="Zakończ sezon z szczytem widowni ≥70.",
        reward_pl="Startujesz z widownią=20, ale Kanał 7 ma na ciebie oko.",
        eval_fn=_eval_origin_zhanbiony,
    ),

    # ── Companions (selectable at character creation) ──────────────────
    "companion_papuga_anty_host": UnlockDef(
        key="companion_papuga_anty_host", kind="companion",
        label_pl="Papuga Konferansjera",
        description_pl="Zakończ sezon z uwagą Kanału 7 ≥15.",
        reward_pl="Sarkastyczna papuga startuje z tobą — komentuje "
                  "każdą walkę, każdy upadek.",
        eval_fn=_eval_papuga,
    ),

    # ── Legendary items (added to global drop / craft pools) ───────────
    "item_mikrofon_anty_hosta": UnlockDef(
        key="item_mikrofon_anty_hosta", kind="item",
        label_pl="Mikrofon Konferansjera",
        description_pl="Pokonaj Konferansjera (anti_host_lite, piętra 16-18).",
        reward_pl="Mikrofon kierunkowy: +5 widowni na użycie, gada "
                  "do ciebie pomiędzy walkami.",
        eval_fn=lambda w, v: _victory_against(
            w, v, "rzeznia_kontrolowana"),  # proxy: lots of kills
    ),
    "item_obrazek_finalu": UnlockDef(
        key="item_obrazek_finalu", kind="item",
        label_pl="Obrazek Finału",
        description_pl="Wygraj sezon (pokonaj Prezesa).",
        reward_pl="Drobiazg, który podnosi jedną losową statystykę +5 "
                  "na nową postać.",
        eval_fn=_eval_kolyski_anti_hosta,
    ),
    "item_skarpetka_pulkownika": UnlockDef(
        key="item_skarpetka_pulkownika", kind="item",
        label_pl="Skarpetka Pułkownika Recyklingu",
        description_pl="Przeżyj pięć sezonów (zwycięstwa lub porażki).",
        reward_pl="Używana skarpetka rozgrzewająca. +1 do testów WIS "
                  "kiedy jest na tobie. Nie pytaj.",
        eval_fn=lambda w, v: _eval_total_runs(w, v, 5),
    ),
}


# ── Public API ──────────────────────────────────────────────────────────

def evaluate_run_for_unlocks(world, victory: bool) -> List[str]:
    """Scan the catalog. Return keys of unlocks the current run
    qualifies for AND that aren't already unlocked.

    Order matters minimally — duplicate writes are deduped by
    run_history.unlock anyway."""
    try:
        from . import run_history as _rh
        already = set(_rh.meta().get("unlocks", []) or [])
    except Exception:
        already = set()
    out = []
    for key, ud in UNLOCK_CATALOG.items():
        if key in already:
            continue
        try:
            if ud.eval_fn and ud.eval_fn(world, victory):
                out.append(key)
        except Exception:
            continue
    return out


def record_unlocks_for_run(world, victory: bool) -> List[str]:
    """Persist any new unlocks. Returns the keys that were newly
    stamped. Caller (Game) emits a Polish "Sezon otwiera nowe
    opcje:" line for each — that surfaces in the death/victory log."""
    keys = evaluate_run_for_unlocks(world, victory)
    try:
        from . import run_history as _rh
        for k in keys:
            _rh.unlock(k)
    except Exception:
        pass
    return keys


def is_unlocked(key: str) -> bool:
    try:
        from . import run_history as _rh
        return key in (_rh.meta().get("unlocks", []) or [])
    except Exception:
        return False


def _by_kind(kind: str) -> List[UnlockDef]:
    return [u for u in UNLOCK_CATALOG.values()
            if u.kind == kind and is_unlocked(u.key)]


def unlocked_species() -> List[UnlockDef]:
    return _by_kind("species")


def unlocked_origins() -> List[UnlockDef]:
    return _by_kind("origin")


def unlocked_companions() -> List[UnlockDef]:
    return _by_kind("companion")


def unlocked_items() -> List[UnlockDef]:
    return _by_kind("item")


def unlocked_classes() -> List[UnlockDef]:
    return _by_kind("class")


def catalog_summary() -> Dict[str, Dict]:
    """For the title-screen overlay. Returns dict[key → {label,
    description, reward, kind, unlocked: bool}]."""
    out = {}
    try:
        from . import run_history as _rh
        unlocked_set = set(_rh.meta().get("unlocks", []) or [])
    except Exception:
        unlocked_set = set()
    for key, ud in UNLOCK_CATALOG.items():
        out[key] = {
            "label": ud.label_pl,
            "description": ud.description_pl,
            "reward": ud.reward_pl,
            "kind": ud.kind,
            "unlocked": key in unlocked_set,
        }
    return out
