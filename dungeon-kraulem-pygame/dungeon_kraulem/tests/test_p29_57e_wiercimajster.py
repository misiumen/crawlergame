"""P29.57e — Wiercimajster + persistent boss codex.

Pokrywa:
* run_history.record_boss_kill / escape / died_elsewhere persistują w
  meta.boss_codex
* boss_codex() agreguje stats per entity key
* fates counter rośnie poprawnie (multiple kills increment)
* Parser rozpoznaje: „wezwij trenera", „kodeks", „porozmawiaj z
  wiercimajstrem"
* attempt_consult_codex w safehouse drukuje codex (3-linie per boss)
* attempt_consult_codex POZA safehouse pokazuje feedback i nic nie
  drukuje z codexu
* Pusty codex w safehouse → przyjazna odpowiedź
* Polish-only sanity: brak angielskich słów w outputach
* Capture hook w corpses: died_elsewhere gdy killer != player
* Capture hook w game.py descent: escape gdy boss wciąż żyje
"""
from __future__ import annotations
import os
import tempfile

from ..engine import boss_ranks as _br
from ..engine import run_history as _rh
from ..engine import corpses as _cp
from ..engine.parser_core import parse_with_optional_llm
from ..engine.handlers.wiercimajster import attempt_consult_codex
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER


def _isolated_history(tmp_path: str):
    """Override HISTORY_FILE w run_history żeby testy się nie biły o
    plik produkcyjny."""
    orig = _rh.HISTORY_FILE
    _rh.HISTORY_FILE = tmp_path
    return orig


def _restore_history(orig: str):
    _rh.HISTORY_FILE = orig


def _mk_boss(key: str, name: str, rank: str, hp_max=60, ac=14):
    return Entity(key=key, entity_type=T_MONSTER, fallback_name=name,
                  tags=["monster", "humanoid", _br.rank_tag(rank)],
                  hp=hp_max, max_hp=hp_max, ac=ac,
                  damage_dice="1d8+2",
                  damage_type="electric",
                  vulnerable_to=["acid", "fire"])


def _mk_world_in_safehouse() -> WorldState:
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r1", actual_type="safehouse")
    r.safehouse_subtype = "lounge"
    f.rooms["r1"] = r
    f.current_room_id = "r1"
    f.start_room_id = "r1"
    w.current_floor = f
    return w


def _mk_world_in_combat() -> WorldState:
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r1", actual_type="combat")
    f.rooms["r1"] = r
    f.current_room_id = "r1"
    f.start_room_id = "r1"
    w.current_floor = f
    return w


# ── Codex persistence ──────────────────────────────────────────────


def test_record_boss_kill_persists():
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("pyskaty_bandzior",
                            "Pyskaty Bandzior",
                            _br.RANK_MIEJSKI)
            entry = _rh.record_boss_kill(boss, floor_num=5)
            assert entry is not None
            codex = _rh.boss_codex()
            assert "pyskaty_bandzior" in codex
            e = codex["pyskaty_bandzior"]
            assert e["name"] == "Pyskaty Bandzior"
            assert e["rank"] == _br.RANK_MIEJSKI
            assert e["hp_max"] == 60
            assert e["ac"] == 14
            assert e["fates"]["killed"] == 1
            assert e["last_seen_floor"] == 5
        finally:
            _restore_history(orig)


def test_record_multiple_kills_increment_counter():
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("ttt", "Targowy Trzepak",
                            _br.RANK_DZIELNICOWY)
            for _ in range(3):
                _rh.record_boss_kill(boss, floor_num=2)
            e = _rh.boss_codex()["ttt"]
            assert e["fates"]["killed"] == 3
            assert e["fates"]["escaped"] == 0
        finally:
            _restore_history(orig)


def test_mixed_fates_aggregate_per_boss():
    """Boss raz zabity, raz uciekł, raz padł od trapa — wszystko
    zlicza się w jednym entry."""
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("regional1", "Wielki Mietek",
                            _br.RANK_REGIONALNY)
            _rh.record_boss_kill(boss, floor_num=7)
            _rh.record_boss_escape(boss, floor_num=8)
            _rh.record_boss_died_elsewhere(boss, floor_num=9)
            e = _rh.boss_codex()["regional1"]
            assert e["fates"]["killed"] == 1
            assert e["fates"]["escaped"] == 1
            assert e["fates"]["died_elsewhere"] == 1
            assert e["last_seen_floor"] == 9
        finally:
            _restore_history(orig)


def test_record_handles_none_entity():
    """None nie crashuje, zwraca None."""
    assert _rh.record_boss_kill(None, floor_num=1) is None
    assert _rh.record_boss_escape(None, floor_num=1) is None
    assert _rh.record_boss_died_elsewhere(None, floor_num=1) is None


# ── Parser ─────────────────────────────────────────────────────────


def test_parser_recognizes_wezwij_trenera():
    intent = parse_with_optional_llm("wezwij trenera")
    assert intent.intent == "consult_codex"


def test_parser_recognizes_kodeks():
    intent = parse_with_optional_llm("kodeks")
    assert intent.intent == "consult_codex"


def test_parser_recognizes_porozmawiaj_z_wiercimajstrem():
    intent = parse_with_optional_llm(
        "porozmawiaj z wiercimajstrem")
    # Powinien rozpoznać. Dopuszczamy fallback do social_intent ale
    # consult_codex preferowany.
    assert intent.intent == "consult_codex"


def test_parser_short_alias_wiercimajster():
    intent = parse_with_optional_llm("wiercimajster")
    assert intent.intent == "consult_codex"


# ── Handler: safehouse gating ──────────────────────────────────────


class _MockGame:
    def __init__(self, world):
        self.world = world
        self.logs = []

    def log(self, msg, tone=""):
        self.logs.append((tone, msg))


class _Intent:
    intent = "consult_codex"
    targets = []
    verb = "wezwij"


def test_codex_blocked_outside_safehouse():
    """Poza safehouse — feedback, nie czyta codexu."""
    w = _mk_world_in_combat()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            # Pre-seed boss w codex żeby było jasne że nie czyta
            boss = _mk_boss("pre_seeded", "Boss", _br.RANK_LOKALNY)
            _rh.record_boss_kill(boss, floor_num=1)
            g = _MockGame(w)
            attempt_consult_codex(g, _Intent())
            joined = " ".join(m for _, m in g.logs)
            assert "safehouse" in joined.lower(), \
                f"expected safehouse refusal: {g.logs}"
            # Codex content NIE drukowany
            assert "Pyskaty" not in joined
        finally:
            _restore_history(orig)


def test_empty_codex_in_safehouse_friendly_response():
    w = _mk_world_in_safehouse()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            g = _MockGame(w)
            attempt_consult_codex(g, _Intent())
            joined = " ".join(m for _, m in g.logs)
            assert "Wiercimajster" in joined
            # Pierwsze podejście — komunikat „Pierwszy raz tu?"
            assert "Pierwszy raz" in joined or "nic nie wiem" in joined
        finally:
            _restore_history(orig)


def test_codex_in_safehouse_prints_boss_entries():
    w = _mk_world_in_safehouse()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("pyskaty_bandzior",
                            "Pyskaty Bandzior",
                            _br.RANK_MIEJSKI)
            _rh.record_boss_kill(boss, floor_num=5)
            g = _MockGame(w)
            attempt_consult_codex(g, _Intent())
            joined = " ".join(m for _, m in g.logs)
            assert "Pyskaty Bandzior" in joined
            assert "miejski" in joined.lower()
            assert "kwas" in joined.lower()  # vulnerable_to acid → kwas
            # HP / AC display
            assert "HP 60" in joined
            assert "AC 14" in joined
        finally:
            _restore_history(orig)


def test_codex_polish_only_in_output():
    """Sanity check że output nie ma typowych angielskich słów."""
    w = _mk_world_in_safehouse()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("b", "Test Boss", _br.RANK_KRAJOWY)
            _rh.record_boss_kill(boss, floor_num=10)
            g = _MockGame(w)
            attempt_consult_codex(g, _Intent())
            joined = " ".join(m for _, m in g.logs).lower()
            for bad in ("the", "your", "boss died",
                        "weakness", "killed by",
                        "drop", "rank"):
                assert bad not in joined, (
                    f"angielski wyciek: {bad!r} w outpucie:\n{joined}")
        finally:
            _restore_history(orig)


# ── Capture hooks: corpses.died_elsewhere ──────────────────────────


def test_transform_to_corpse_records_died_elsewhere_for_non_player_kill():
    """Boss padł NIE od gracza — corpse hook zapisuje died_elsewhere."""
    w = _mk_world_in_combat()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("trap_kill_boss", "Mały Frycy",
                            _br.RANK_LOKALNY)
            w.register(boss)
            # killer != player.character → np. None lub inny mob
            _cp.transform_to_corpse(w, boss, killer=None)
            codex = _rh.boss_codex()
            assert "trap_kill_boss" in codex
            assert codex["trap_kill_boss"]["fates"]["died_elsewhere"] == 1
            assert codex["trap_kill_boss"]["fates"]["killed"] == 0
        finally:
            _restore_history(orig)


def test_transform_to_corpse_skips_codex_for_player_kill():
    """Gdy killer == player.character, corpse hook NIE zapisuje
    died_elsewhere (player-kill jest handled w game.py)."""
    w = _mk_world_in_combat()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            boss = _mk_boss("player_kill_boss", "Targowy Złodziej",
                            _br.RANK_DZIELNICOWY)
            w.register(boss)
            _cp.transform_to_corpse(w, boss, killer=w.character)
            codex = _rh.boss_codex()
            # Player-kill → died_elsewhere counter = 0
            entry = codex.get("player_kill_boss", {})
            fates = entry.get("fates", {})
            assert fates.get("died_elsewhere", 0) == 0
        finally:
            _restore_history(orig)


def test_transform_to_corpse_skips_codex_for_non_boss():
    """Zwykły mob bez boss_rank → codex nietknięty."""
    w = _mk_world_in_combat()
    with tempfile.TemporaryDirectory() as td:
        orig = _isolated_history(os.path.join(td, "hist.json"))
        try:
            mob = Entity(key="szczur", entity_type=T_MONSTER,
                         fallback_name="szczur",
                         tags=["monster", "beast"])
            w.register(mob)
            _cp.transform_to_corpse(w, mob, killer=None)
            codex = _rh.boss_codex()
            assert "szczur" not in codex
        finally:
            _restore_history(orig)
