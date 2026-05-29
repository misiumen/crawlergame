"""E2E P29.64b — głos bohatera (wewnętrzny monolog per origin).

User: „mój główny bohater to póki co niemowa bez osobowości. to się musi
zmienić" + „głos zależnie od origin". Dowodzi:
  * każde pochodzenie ma własny głos,
  * monolog rotuje (różne myśli przy kolejnych „zbadaj"),
  * podszept percepcji jest GATOWANY percepcją (MDR/INT), nie klasą:
    spostrzegawczy dostaje konkret, reszta tylko przeczucie,
  * `zbadaj pomieszczenie` faktycznie wypuszcza głos w logu.
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import voice as _voice
from ...engine.character import Character, BACKGROUNDS
from ...engine.entity import Entity, T_MONSTER, T_OBJECT
from .headless import HeadlessSession, assert_polish_only


def _ch(bg, **stats):
    c = Character(name="T", background=bg)
    for k, v in stats.items():
        c.stats[k] = v
    return c


# ── Głos per origin ─────────────────────────────────────────────────


def test_every_origin_has_a_voice():
    for bg in BACKGROUNDS:
        assert bg in _voice._ORIGIN_EXAMINE, f"brak głosu dla origin {bg}"


def test_origins_speak_differently():
    a = _voice.monologue(_ch("soldier"), "examine")
    b = _voice.monologue(_ch("streamer"), "examine")
    assert a and b and a != b


def test_monologue_rotates_deterministically():
    c = _ch("mechanic")
    first = _voice.monologue(c, "examine")
    second = _voice.monologue(c, "examine")
    # Dwie różne linie (origin ma >1), licznik w flags przesunięty.
    assert first != second
    assert c.flags.get("voice_examine_i") == 2


def test_monologue_none_safe():
    assert _voice.monologue(None, "examine") is None
    assert _voice.monologue(_ch("nurse"), "combat") is None


# ── Podszept percepcji: gating po MDR/INT, nie po klasie ────────────


def test_perception_hint_concrete_for_perceptive():
    c = _ch("student", WIS=16)            # mod +3 → powyżej progu
    hint = _voice.perception_hint(
        c, [("regał", ["suche, łatwo zajmie się ogniem"])])
    assert hint and "regał" in hint


def test_perception_hint_vague_for_dull():
    c = _ch("security_guard", WIS=8, INT=8)   # mod ujemny
    hint = _voice.perception_hint(
        c, [("regał", ["suche, łatwo zajmie się ogniem"])])
    assert hint and "regał" not in hint       # mgliste przeczucie, bez nazwy


def test_perception_hint_none_without_exploitable():
    c = _ch("student", WIS=16)
    assert _voice.perception_hint(c, [("kamień", [])]) is None
    assert _voice.perception_hint(c, []) is None


# ── Integracja: zbadaj pomieszczenie wypuszcza głos ─────────────────


def test_examine_room_emits_voice_line():
    sess = HeadlessSession(background="bezdomny")
    regal = Entity(key="regal", entity_type=T_OBJECT,
                   fallback_name="regał z księgami", tags=["łatwopalne"])
    sess.put_in_room(regal)
    out = sess.send("zbadaj pomieszczenie")
    text = "\n".join(t for t, _ in out)
    # Któraś z linii głosu bezdomnego pojawia się w logu.
    assert ("dziurach" in text or "ulica" in text.lower()), \
        f"brak głosu bohatera w:\n{text}"
    assert_polish_only(text)


def test_examine_room_perceptive_gets_concrete_hint():
    sess = HeadlessSession(background="student")
    sess.character.stats["WIS"] = 16          # spostrzegawczy
    regal = Entity(key="regal", entity_type=T_OBJECT,
                   fallback_name="regał z księgami", tags=["łatwopalne"])
    sess.put_in_room(regal)
    out = sess.send("zbadaj pomieszczenie")
    text = "\n".join(t for t, _ in out)
    assert "nie daje spokoju" in text and "regał" in text
