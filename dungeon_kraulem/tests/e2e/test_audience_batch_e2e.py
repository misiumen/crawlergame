"""E2E P29.69 — silnik A/6: batchowanie reakcji widowni (koniec spamu).

`change_audience` akumuluje deltę; flush_audience_log emituje JEDNĄ
skonsolidowaną linię na koniec komendy gracza. Stary spam „+2/+2/+2"
rozsiany po logu znika.
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import audience as _aud
from .headless import HeadlessSession


def test_command_flushes_pending_audience_once():
    sess = HeadlessSession()
    # Zasymuluj kilka zmian widowni zakumulowanych w trakcie akcji.
    _aud.change_audience(sess.world, 3, source="a")
    _aud.change_audience(sess.world, 2, source="b")
    _aud.change_audience(sess.world, 1, source="c")
    # Przed komendą — żadnej linii (tylko akumulacja).
    assert not any(t.startswith("Widownia") for t in sess.log_lines())
    # Dowolna komenda kończy się flushem → JEDNA skonsolidowana linia.
    sess.send("rozejrzyj się")
    aud_lines = [t for t in sess.log_lines() if t.startswith("Widownia")]
    assert len(aud_lines) == 1, f"oczekiwano 1 linii widowni; jest {aud_lines}"
    assert "+6" in aud_lines[0]


def test_no_audience_line_when_no_change():
    sess = HeadlessSession()
    sess.send("rozejrzyj się")
    assert not any(t.startswith("Widownia") for t in sess.log_lines())
