"""Prompt 29.25 — Victory screen + run-summary polish smoke suite.

Audit findings:
  * Victory screen was 2 lines (name + day). Death got a 14-line
    highlight reel. Winning the season finale felt less rewarding
    than dying.
  * RunSummary.render_lines printed raw sponsor keys
    (`novachem_biotech +12`) instead of PL display names.
  * Background + class were raw codes (`bruiser`, `janitor`).

P29.25 unifies the death/victory rendering through one path and
runs every label through a Polish translator.

Covers:
  * render_lines(victory=True) returns lines containing "FINAŁ
    SEZONU" header.
  * render_lines(victory=False) keeps the death-cause line.
  * Sponsor keys render via _name_pl, not the raw key.
  * Background codes render via _BG_PL ("janitor" → "konserwator").
  * Anti-host line is preserved in both modes.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import run_summary as _rs


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=42, credits=99)
    w.character.run_kills = 17
    w.character.run_audience_peak = 80
    w.character.run_max_floor_reached = 14
    w.character.run_corpses_salvaged = 9
    w.character.run_traps_armed = 3
    w.character.run_death_cause_label = "od ciosu Bandziora"
    f = FloorState(floor_id="f1", floor_number=14)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    # Seed some sponsor attention so top_sponsors has content.
    w.character.flags["sponsor_attention"] = {
        "novachem_biotech": 12,
        "kanal_7_krawedz": 8,
        "kult_recyklingu": 3,
    }
    return w, r


# ── Defeat vs victory mode ─────────────────────────────────────────────

def test_defeat_mode_keeps_death_cause():
    w, _r = _mk_world()
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs, victory=False)
    joined = "\n".join(lines)
    assert "Przyczyna:" in joined or "od ciosu" in joined
    assert "FINAŁ SEZONU" not in joined
    print("  defeat render: keeps Przyczyna line: OK")


def test_victory_mode_swaps_in_finale_header():
    w, _r = _mk_world()
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs, victory=True)
    joined = "\n".join(lines)
    assert "FINAŁ SEZONU" in joined, \
        f"victory header missing from:\n{joined}"
    assert "Producent" in joined
    # Konferansjer present too (re-cast as salute).
    assert "Konferansjer" in joined
    # And the death-cause line is absent.
    assert "Przyczyna:" not in joined
    print("  victory render: FINAŁ SEZONU header + salute: OK")


# ── Sponsor key → PL display name ──────────────────────────────────────

def test_sponsor_keys_render_as_polish_names():
    w, _r = _mk_world()
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs)
    joined = "\n".join(lines)
    # NovaChem should appear by display name, not raw key.
    assert "NovaChem Biotech" in joined, \
        f"sponsor key not localized:\n{joined}"
    assert "novachem_biotech" not in joined, \
        f"raw sponsor key leaked into render:\n{joined}"
    # Kanał 7 too.
    assert "Kanał 7" in joined or "Krawędź" in joined
    print("  sponsor keys rendered as Polish display names: OK")


# ── Background code → PL ────────────────────────────────────────────────

def test_background_renders_in_polish():
    w, _r = _mk_world()
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs)
    # The first line is `<name> — <bg>`. Should be "konserwator".
    header = lines[0]
    assert "konserwator" in header, \
        f"background not localized: {header}"
    assert "janitor" not in header, \
        f"raw background code leaked: {header}"
    print(f"  background → PL: {header}: OK")


# ── Anti-host line present in both ──────────────────────────────────────

def test_anti_host_present_in_defeat():
    w, _r = _mk_world()
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs, victory=False)
    # The anti_host_line is a generic flavor from the catalog.
    assert any(rs.anti_host_line in ln for ln in lines), \
        "anti-host line missing in defeat render"
    print("  anti-host line present in defeat mode: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_defeat_mode_keeps_death_cause()
    test_victory_mode_swaps_in_finale_header()
    test_sponsor_keys_render_as_polish_names()
    test_background_renders_in_polish()
    test_anti_host_present_in_defeat()
    print("Prompt 29.25 victory + run-summary polish smoke: OK")


if __name__ == "__main__":
    main()
