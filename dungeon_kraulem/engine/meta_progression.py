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


# ── P29.37 — Extended evaluators ────────────────────────────────────────

def _eval_total_victories(world, victory: bool, n: int) -> bool:
    """True when victories AFTER this run lands >= n."""
    try:
        from . import run_history as _rh
        cur = int(_rh.meta().get("victories", 0))
        if victory:
            cur += 1
        return cur >= n
    except Exception:
        return False


def _eval_audience_peak(world, victory, n: int) -> bool:
    return _audience_peak(world) >= n


def _eval_corpses_salvaged(world, victory, n: int) -> bool:
    try:
        return int(getattr(world.character, "run_corpses_salvaged",
                            0) or 0) >= n
    except Exception:
        return False


def _eval_zero_kills(world, victory) -> bool:
    """Pacifist run — finished with run_kills == 0."""
    try:
        return int(getattr(world.character, "run_kills", 0) or 0) == 0
    except Exception:
        return False


def _eval_sponsor_hostile(world, victory) -> bool:
    """True if any sponsor's attention is at -5 or lower at end of
    run. Models "Sponsor's Choice Reject" — someone hates you enough
    to be hostile."""
    try:
        from . import sponsors as _sp
        att = _sp._attention_dict(world)
        return any(int(v) <= -5 for v in att.values())
    except Exception:
        return False


def _eval_three_sponsors_friendly(world, victory) -> bool:
    """3+ sponsors at attention >= 10 simultaneously."""
    try:
        from . import sponsors as _sp
        att = _sp._attention_dict(world)
        return sum(1 for v in att.values() if int(v) >= 10) >= 3
    except Exception:
        return False


def _eval_achievement(world, victory, ach_key: str) -> bool:
    """True if the character has unlocked this achievement key."""
    try:
        return ach_key in (world.character.unlocked_achievements or [])
    except Exception:
        return False


def _any_sponsor_at(world, threshold: int) -> bool:
    """True if ANY sponsor has attention >= threshold. Iterates
    the live attention dict — no hardcoded sponsor key list, so it
    stays in sync as the sponsor catalog evolves."""
    try:
        from . import sponsors as _sp
        att = _sp._attention_dict(world)
        return any(int(v) >= threshold for v in att.values())
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

    # ────────── P29.37 — Expanded catalog ──────────────────────────────
    # Three new species, four new origins, three new companions,
    # five new items, and a brand-new "start_perk" kind (one-shot
    # mid-run effects spendable at character creation).

    # ── Species (extends creation picker via meta_progression.unlocked_species)
    "species_stary_uczestnik": UnlockDef(
        key="species_stary_uczestnik", kind="species",
        label_pl="Stary Uczestnik",
        description_pl="Wygraj trzy sezony.",
        reward_pl="Zaczynasz z blizną poprzedniego zwycięzcy i "
                  "widownią bazową 25 (zamiast 0).",
        eval_fn=lambda w, v: _eval_total_victories(w, v, 3),
    ),
    "species_bez_twarzy": UnlockDef(
        key="species_bez_twarzy", kind="species",
        label_pl="Bez Twarzy",
        description_pl="Przetrwaj pięć sezonów (porażki też się "
                       "liczą).",
        reward_pl="Widownia nigdy nie spada poniżej 10, ale CHA "
                  "wymuszone na 5 (twoja twarz nie ma rysów).",
        eval_fn=lambda w, v: _eval_total_runs(w, v, 5),
    ),
    "species_ferromanta_meta": UnlockDef(
        key="species_ferromanta_meta", kind="species",
        label_pl="Ferromanta (start)",
        description_pl="Dotrzyj na piętro 15 w jakimkolwiek sezonie.",
        reward_pl="Startujesz jako Ferromanta — magnetyczna skóra, "
                  "metal sam do ciebie idzie. Pomiń losowanie na "
                  "piętrze 3 jeśli chcesz to zostawić jak jest.",
        eval_fn=lambda w, v: _floor_reached(w, 15),
    ),

    # ── Origins (extend BACKGROUNDS at character creation)
    "origin_wieczny_stazysta": UnlockDef(
        key="origin_wieczny_stazysta", kind="origin",
        label_pl="Wieczny Stażysta",
        description_pl="Przetrwaj trzy sezony.",
        reward_pl="Startujesz z credits ×2. Konferansjer nigdy nie "
                  "zaoferuje ci klasy w tym runie (jesteś stażystą, "
                  "Syndykat ci nie ufa).",
        eval_fn=lambda w, v: _eval_total_runs(w, v, 3),
    ),
    "origin_sponsor_reject": UnlockDef(
        key="origin_sponsor_reject", kind="origin",
        label_pl="Sponsor's Choice Reject",
        description_pl="Zakończ sezon ze sponsorem na uwadze ≤ −5.",
        reward_pl="Każdy sponsor startuje z uwagą −5 (nielubiany), "
                  "ale jeden losowy ma cię za swojego (+10).",
        eval_fn=_eval_sponsor_hostile,
    ),
    "origin_byly_konferansjer": UnlockDef(
        key="origin_byly_konferansjer", kind="origin",
        label_pl="Były Konferansjer",
        description_pl="Dotrzyj na piętro 17.",
        reward_pl="Konferansjer mówi o tobie ze współczuciem. "
                  "Pomijasz jedną dezambiguację na piętro (znasz "
                  "montaż programu).",
        eval_fn=lambda w, v: _floor_reached(w, 17),
    ),
    "origin_dziedzic_k7": UnlockDef(
        key="origin_dziedzic_k7", kind="origin",
        label_pl="Dziedzic Kanału 7",
        description_pl="Osiągnij szczyt widowni 120 w jednym runie.",
        reward_pl="Startujesz z wbudowanym mikrofonem kierunkowym + "
                  "dron-kamera leci za tobą (audience +1 co minutę "
                  "w pierwszym dniu piętra 1).",
        eval_fn=lambda w, v: _eval_audience_peak(w, v, 120),
    ),

    # ── Companions (creation-time picker via unlocked_companions)
    "companion_suczka_recyklingu": UnlockDef(
        key="companion_suczka_recyklingu", kind="companion",
        label_pl="Suczka Recyklingu",
        description_pl="Zakończ sezon z uwagą Kultu Recyklingu ≥ 20.",
        reward_pl="Trzy-nożna sunia, która scrappuje 1 losowy "
                  "przedmiot z każdego trupa wroga w pokoju.",
        eval_fn=lambda w, v: _has_attention(w, "kult_recyklingu", 20),
    ),
    "companion_kot_ministerstwa": UnlockDef(
        key="companion_kot_ministerstwa", kind="companion",
        label_pl="Kot Ministerstwa",
        description_pl="Zakończ sezon z uwagą Ministerstwa Pamięci "
                       "≥ 20.",
        reward_pl="Kot z legitymacją służbową. 1 raz na piętro "
                  "cofa twój ostatni nieudany rzut (re-roll).",
        eval_fn=lambda w, v: _has_attention(w, "ministerstwo_pamieci", 20),
    ),
    "companion_dron_sponsorski": UnlockDef(
        key="companion_dron_sponsorski", kind="companion",
        label_pl="Dron Sponsorski",
        description_pl="Zakończ sezon z jakimś sponsorem ≥ 18 "
                       "(niemal pełna uwaga).",
        reward_pl="Latająca kamera, audience ×1.5. Jeśli zdradzisz "
                  "sponsora-właściciela, jego pody się rozwścieczają.",
        eval_fn=lambda w, v: _any_sponsor_at(w, 18),
    ),

    # ── Items (legendary drops + craft pool extensions)
    "item_mosiezny_pierscien_producenta": UnlockDef(
        key="item_mosiezny_pierscien_producenta", kind="item",
        label_pl="Mosiężny Pierścień Producenta",
        description_pl="Zakończ sezon bez ani jednego zabójstwa "
                       "(pacyfista).",
        reward_pl="Na początku piętra możesz przerolować layout "
                  "jednego pokoju.",
        eval_fn=_eval_zero_kills,
    ),
    "item_stara_czaszka_z_markerem": UnlockDef(
        key="item_stara_czaszka_z_markerem", kind="item",
        label_pl="Stara Czaszka z Markerem",
        description_pl="Rozbierz 10 zwłok w jednym runie.",
        reward_pl="Gadająca czaszka w safehouse'ach. Mówi, którzy "
                  "sponsorzy najbardziej nienawidzą mobów z "
                  "ostatniego piętra.",
        eval_fn=lambda w, v: _eval_corpses_salvaged(w, v, 10),
    ),
    "item_czerwony_telefon_k7": UnlockDef(
        key="item_czerwony_telefon_k7", kind="item",
        label_pl="Czerwony Telefon Kanału 7",
        description_pl="Zakończ sezon z uwagą Kanału 7 ≥ 20.",
        reward_pl="Raz na run zadzwoń po drop-pod wybranego sponsora "
                  "(zamiast czekać na losowy).",
        eval_fn=lambda w, v: _has_attention(w, "kanal_7_krawedz", 20),
    ),
    "item_klucz_do_kantyny": UnlockDef(
        key="item_klucz_do_kantyny", kind="item",
        label_pl="Klucz do Kantyny Sponsorów",
        description_pl="Zakończ sezon z 3+ sponsorami na ≥ 10 "
                       "uwagi jednocześnie.",
        reward_pl="Otwiera ukryty pokój na piętrze 18 — credits + "
                  "apteczka + pełna butelka wody (rzecz święta).",
        eval_fn=_eval_three_sponsors_friendly,
    ),
    "item_pamiatkowa_lyzka": UnlockDef(
        key="item_pamiatkowa_lyzka", kind="item",
        label_pl="Pamiątkowa Łyżka",
        description_pl="Otwórz drop-pod (osiągnięcie pakiet_z_sufitu).",
        reward_pl="Łyżka do podważania. +2 do otwierania zamków, "
                  "działa też na automaty bez płacenia kredytów.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "pakiet_z_sufitu"),
    ),

    # ── Start perks — NEW KIND ────────────────────────────────────────
    # One-shot effects spent at character creation. The picker shows
    # them as a 4th tier alongside species/origin/companion.
    "perk_lapowka_dla_portiera": UnlockDef(
        key="perk_lapowka_dla_portiera", kind="start_perk",
        label_pl="Łapówka dla portiera",
        description_pl="Zakończ sezon z jakimś sponsorem na 20 (max).",
        reward_pl="Startujesz z 1 darmowym uzupełnieniem usług "
                  "w pierwszym safehouse'ie (cokolwiek wybierzesz).",
        eval_fn=lambda w, v: _any_sponsor_at(w, 20),
    ),
    "perk_insiderskie_info": UnlockDef(
        key="perk_insiderskie_info", kind="start_perk",
        label_pl="Insiderskie info",
        description_pl="Przetrwaj pięć sezonów.",
        reward_pl="Startujesz znając gatunek bossa pierwszego "
                  "piętra (pokazane przy wyborze postaci).",
        eval_fn=lambda w, v: _eval_total_runs(w, v, 5),
    ),
    "perk_stara_legitymacja": UnlockDef(
        key="perk_stara_legitymacja", kind="start_perk",
        label_pl="Stara legitymacja Syndykatu",
        description_pl="Wygraj trzy sezony.",
        reward_pl="Pierwszy nieudany rzut społeczny auto-sukces. "
                  "Wypala się po użyciu.",
        eval_fn=lambda w, v: _eval_total_victories(w, v, 3),
    ),
    "perk_lyzka_cudu": UnlockDef(
        key="perk_lyzka_cudu", kind="start_perk",
        label_pl="Łyżka Cudu",
        description_pl="Przeżyj piętro mając 1 HP (osiągnięcie "
                       "anty_host_warknal).",
        reward_pl="Startujesz z jednorazowym „drugim oddechem” — "
                  "pierwsza śmierć przywraca cię do 5 HP. Osobno "
                  "od last-stand.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "anty_host_warknal"),
    ),

    # ── P29.49 — meta-unlocki gated na nowych achievementach ────────
    "item_apteczka_kompletna": UnlockDef(
        key="item_apteczka_kompletna", kind="item",
        label_pl="Apteczka Kompletna",
        description_pl="Zbierz przedmioty każdej klasy rzadkości w "
                       "jednym sezonie (osiągnięcie cala_paleta).",
        reward_pl="Startujesz z apteczką polową — używaj raz na piętro, "
                  "leczy 50% max HP, koszt 0 kr.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "cala_paleta"),
    ),
    "perk_rzemieslnik_terminala": UnlockDef(
        key="perk_rzemieslnik_terminala", kind="start_perk",
        label_pl="Rzemieślnik terminala",
        description_pl="Zhakuj 5 terminali w jednym sezonie "
                       "(osiągnięcie kompletny_hacker).",
        reward_pl="Startujesz z 2 elektronikami + lockpick_set. "
                  "Pierwszy hack na sezon = darmowy.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "kompletny_hacker"),
    ),
    "perk_okopowy_weteran": UnlockDef(
        key="perk_okopowy_weteran", kind="start_perk",
        label_pl="Okopowy weteran",
        description_pl="Skończ piętro we Frontowych Okopach "
                       "(osiągnięcie okopowiec).",
        reward_pl="Maska filtrująca i kombinezon startowy. "
                  "Odporność na gaz okopowy.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "okopowiec"),
    ),
    "perk_handlarz_pakietow": UnlockDef(
        key="perk_handlarz_pakietow", kind="start_perk",
        label_pl="Handlarz Pakietów",
        description_pl="Zabij 3 minibossów w jednym piętrze "
                       "(osiągnięcie klepacz_minibossow).",
        reward_pl="Każdy zabity miniboss dropuje +1 dodatkową paczkę "
                  "(materiały + małe szanse na rzadki item).",
        eval_fn=lambda w, v: _eval_achievement(w, v, "klepacz_minibossow"),
    ),
    "perk_taneczne_nogi": UnlockDef(
        key="perk_taneczne_nogi", kind="start_perk",
        label_pl="Taneczne nogi",
        description_pl="Przejdź piętro nie wpadając w żaden hazard "
                       "(osiągnięcie taneczny_krok).",
        reward_pl="Pierwsza interakcja z hazardem w runie jest "
                  "automatycznym sukcesem (unik / disable).",
        eval_fn=lambda w, v: _eval_achievement(w, v, "taneczny_krok"),
    ),
    "perk_dzikus_z_arena": UnlockDef(
        key="perk_dzikus_z_arena", kind="start_perk",
        label_pl="Dzikus z areny",
        description_pl="Przejdź piętro bez zbroi (osiągnięcie "
                       "bez_zbroi_bez_smutku).",
        reward_pl="+10 max HP + +1 do testów STR gdy brak zbroi "
                  "w slot:torso. Klimat: blizny zamiast naszywek.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "bez_zbroi_bez_smutku"),
    ),
    "perk_skapy_jak_widz": UnlockDef(
        key="perk_skapy_jak_widz", kind="start_perk",
        label_pl="Skąpy jak widz",
        description_pl="Przejdź piętro nie wydając kredytów "
                       "(osiągnięcie nadzwyczajne_oszczednosci).",
        reward_pl="Startujesz z +50 kredytami i 20% rabatem na "
                  "wszystko w safehouse'ach.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "nadzwyczajne_oszczednosci"),
    ),
    "perk_kolekcjoner": UnlockDef(
        key="perk_kolekcjoner", kind="start_perk",
        label_pl="Kolekcjoner",
        description_pl="Znajdź legendarny przedmiot "
                       "(osiągnięcie widzialem_legende).",
        reward_pl="Pierwszy legendarny przedmiot na sezon dropuje "
                  "10 pięter wcześniej niż normalnie.",
        eval_fn=lambda w, v: _eval_achievement(w, v, "widzialem_legende"),
    ),

    # ────────── P29.42a — Biome unlocks ───────────────────────────────
    # Każdy z tych biomów ląduje w puli generatora dla piętra po
    # spełnieniu warunku. Reward_pl mówi GDZIE biom się pojawi.

    "biome_oboz_goblinski": UnlockDef(
        key="biome_oboz_goblinski", kind="biome",
        label_pl="Obóz Gobliński",
        description_pl="Wygraj sezon.",
        reward_pl="Biom dostępny na piętrach 3-8: palisady, ogniska, "
                  "gobliny krzyczące bez kontekstu.",
        eval_fn=lambda w, v: _eval_total_victories(w, v, 1),
    ),
    "biome_siec_kanalizacyjna": UnlockDef(
        key="biome_siec_kanalizacyjna", kind="biome",
        label_pl="Sieć Kanalizacyjna",
        description_pl="Przetrwaj trzy sezony.",
        reward_pl="Biom dostępny na piętrach 3-8: rury, smród, "
                  "szczury wielkości terierów.",
        eval_fn=lambda w, v: _eval_total_runs(w, v, 3),
    ),
    "biome_tunel_karnawalowy": UnlockDef(
        key="biome_tunel_karnawalowy", kind="biome",
        label_pl="Tunel Karnawałowy",
        description_pl="Osiągnij szczyt widowni 60.",
        reward_pl="Biom dostępny na piętrach 3-8: luna park po nocy, "
                  "klauni-manekiny, słodki smród waty cukrowej.",
        eval_fn=lambda w, v: _eval_audience_peak(w, v, 60),
    ),
    "biome_katakumby_faktur": UnlockDef(
        key="biome_katakumby_faktur", kind="biome",
        label_pl="Katakumby Spóźnionych Faktur",
        description_pl="Zakończ sezon z uwagą Bractwa Komornika ≥ 15.",
        reward_pl="Biom dostępny na piętrach 9-12: świece, ołtarze "
                  "z plastiku, mnisi w lateksowych szatach.",
        eval_fn=lambda w, v: _has_attention(w, "bractwo_komornika", 15),
    ),
    "biome_farma_klonow": UnlockDef(
        key="biome_farma_klonow", kind="biome",
        label_pl="Farma Klonów",
        description_pl="Zakończ sezon z uwagą NovaChem-Biotech ≥ 15.",
        reward_pl="Biom dostępny na piętrach 9-12: kapsuły z biopłynem, "
                  "klony w różnych stadiach.",
        eval_fn=lambda w, v: _has_attention(w, "novachem_biotech", 15),
    ),
    "biome_elfia_kolonia": UnlockDef(
        key="biome_elfia_kolonia", kind="biome",
        label_pl="Elfia Kolonia",
        description_pl="Wygraj sezon klasą occultist.",
        reward_pl="Biom dostępny na piętrach 9-12: drzewa rosną przez "
                  "beton, łuki, lutnie, elfy zbyt zadbane.",
        eval_fn=lambda w, v: (
            v and (getattr(w.character, "class_key", "") == "occultist")),
    ),
    "biome_redakcja_krawedzi": UnlockDef(
        key="biome_redakcja_krawedzi", kind="biome",
        label_pl="Redakcja Krawędzi",
        description_pl="Zakończ sezon z uwagą Kanału 7 Krawędź ≥ 20.",
        reward_pl="Biom dostępny na piętrach 13-17: biurka, kamery na "
                  "statywach, plakaty programów, kawa w dzbankach.",
        eval_fn=lambda w, v: _has_attention(w, "kanal_7_krawedz", 20),
    ),
    "biome_swiatynia_konferansjera": UnlockDef(
        key="biome_swiatynia_konferansjera", kind="biome",
        label_pl="Świątynia Konferansjera",
        description_pl="Pokonaj Konferansjera (anti_host_lite, "
                       "piętra 16-18).",
        reward_pl="Biom dostępny na piętrach 13-17: ołtarze, popiersia, "
                  "mikrofony pozłacane.",
        eval_fn=lambda w, v: _eval_achievement(
            w, v, "rzeznia_kontrolowana"),
    ),
    "biome_lawowe_tunele": UnlockDef(
        key="biome_lawowe_tunele", kind="biome",
        label_pl="Lawowe Tunele",
        description_pl="Dotrzyj na piętro 15.",
        reward_pl="Biom dostępny na piętrach 13-17: magma, jaszczury, "
                  "ognioznawcy z młotami.",
        eval_fn=lambda w, v: _floor_reached(w, 15),
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


def unlocked_start_perks() -> List[UnlockDef]:
    """P29.37 — one-shot character-creation perks (Łapówka,
    Insiderskie info, Stara legitymacja, Łyżka Cudu)."""
    return _by_kind("start_perk")


def unlocked_biomes() -> List[UnlockDef]:
    """P29.42a — biomy piętra odblokowane przez run-history. Generator
    czyta tę listę przy losowaniu biomu (przez floor_biomes.is_unlocked)."""
    return _by_kind("biome")


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
