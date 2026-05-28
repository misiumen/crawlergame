"""P29.57e — Wiercimajster: trener w safehouse + codex bossów.

Wiercimajster to instytucjonalny trener w każdym safehouse. Nie spawnuje
się jako entity — jest „ambient service" dostępny przez intent
`consult_codex` (wezwij trenera / kodeks bossów / porozmawiaj z
wiercimajstrem). Gating: gracz musi być w safehouse.

Codex persystuje między runami przez run_history.boss_codex().
Każdy boss zapisany w trakcie poprzedniego runa (kill / escape /
died_elsewhere) jest dostępny dla nowego runa — DCC „next run
knowledge".
"""
from __future__ import annotations
from typing import Dict, List

from ...config import LOG_NORMAL, LOG_WARN, LOG_SUCCESS, LOG_SYSTEM
from .. import boss_ranks as _br
from .. import run_history as _rh


def _is_player_in_safehouse(game) -> bool:
    """Czy current_room jest safehouse'em? Wiercimajster pracuje tylko
    tam — w wave czy bossroomie milczy."""
    try:
        f = game.world.current_floor
        if f is None:
            return False
        room = f.current_room()
        if room is None:
            return False
        if getattr(room, "safehouse_subtype", None):
            return True
        return room.actual_type == "safehouse"
    except (AttributeError, KeyError):
        return False


def _format_fate_summary(fates: Dict[str, int]) -> str:
    """Polskie zdanie podsumowujące losy bossa.
    Np. „Zabity 3×, raz uciekł, raz padł w innych okolicznościach."""
    killed = int(fates.get("killed", 0) or 0)
    escaped = int(fates.get("escaped", 0) or 0)
    elsewhere = int(fates.get("died_elsewhere", 0) or 0)
    parts: List[str] = []
    if killed:
        parts.append(f"zabity {killed}×")
    if escaped:
        parts.append(f"uciekł {escaped}×")
    if elsewhere:
        parts.append(f"padł od innych {elsewhere}×")
    if not parts:
        return "tylko widziany, nigdy nie pokonany"
    return ", ".join(parts)


def _format_weakness_line(entry: Dict) -> str:
    """Polski podgląd słabości / typu dmg."""
    vuln = entry.get("vulnerable_to") or []
    pl_map = {
        "acid":     "kwas",
        "fire":     "ogień",
        "electric": "prąd",
        "ice":      "mróz",
        "poison":   "trucizna",
        "blunt":    "obuch",
        "slash":    "cięcie",
        "pierce":   "kłucie",
        "psychic":  "psyche",
    }
    vuln_pl = [pl_map.get(v, v) for v in vuln]
    dtype = entry.get("damage_type", "")
    dtype_pl = pl_map.get(dtype, dtype) if dtype else ""

    bits: List[str] = []
    if vuln_pl:
        bits.append("wrażliwy na: " + ", ".join(vuln_pl))
    if dtype_pl:
        bits.append(f"bije „{dtype_pl}”")
    return " · ".join(bits) if bits else "brak danych o słabościach"


def _sort_by_rank(codex: Dict[str, Dict]) -> List[tuple]:
    """Sortuje (key, entry) od najwyższej rangi do najniższej."""
    def _key(pair):
        _, e = pair
        return -_br.rank_order(e.get("rank", "") or "")
    return sorted(codex.items(), key=_key)


def attempt_consult_codex(game, intent) -> None:
    """Player intent `consult_codex`. Wymaga safehouse'u — inaczej
    krótka odpowiedź feedback. Drukuje codex w tonie Wiercimajstra
    (krótki, suchy, Dinniman-flavor)."""
    if not _is_player_in_safehouse(game):
        game.log("Wiercimajstra znajdziesz w safehouse — ten się "
                 "z lokalu nie rusza.", LOG_WARN)
        return

    codex = _rh.boss_codex()
    if not codex:
        game.log("Wiercimajster: „Pierwszy raz tu? Wracaj, jak zaczniesz "
                 "wpisywać nazwiska na ścianę. Dzisiaj nic nie wiem.”",
                 LOG_NORMAL)
        return

    game.log("Wiercimajster otwiera notes oprawiony w skórę. "
             "Strony szeleszczą jak suche liście.", LOG_SYSTEM)

    # Banner per known rank, najwyższe rangi pierwsze
    for boss_key, entry in _sort_by_rank(codex):
        name = entry.get("name") or boss_key
        rank = entry.get("rank") or ""
        rank_pl = _br.rank_label_pl(rank) if rank else "bez rangi"
        hp = entry.get("hp_max", 0)
        ac = entry.get("ac", 10)
        last_floor = entry.get("last_seen_floor", "?")
        fate_line = _format_fate_summary(entry.get("fates") or {})
        weak_line = _format_weakness_line(entry)

        game.log(f"  • {name} ({rank_pl}) — HP {hp}, AC {ac}, "
                 f"ostatnio na piętrze {last_floor}.",
                 LOG_SUCCESS)
        game.log(f"      {fate_line}.", LOG_NORMAL)
        game.log(f"      {weak_line}.", LOG_NORMAL)

    game.log("Wiercimajster zamyka notes. „Wracaj jak coś dorzucisz.”",
             LOG_SYSTEM)
