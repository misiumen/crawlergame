"""E2E P29.66 — silnik A/3: PSYCHIKA (lęk / odraza / pragnienie).

Sygnaturowy mechanizm immersive sim: „boss boi się pająków" = `lęk:X` na
celu + istota/przedmiot o tożsamości `X` + JEDNA generyczna reguła. Match
tożsamości źródła ∩ psyche celu → efekt umysłowy. Bez LLM, bez scriptu.

Dowodzi reguł, priorytetu, braku fałszywych trafień ORAZ żywego seedu
treści (inspektor NovaChem brzydzi się robactwa — cisnij w niego szczura).
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import systemic as _sys
from ...engine.entity import Entity, T_MONSTER, T_OBJECT
from .headless import HeadlessSession, assert_polish_only


def _src(*tags):
    return Entity(key="s", entity_type=T_OBJECT, fallback_name="rzecz",
                  tags=list(tags))


def _tgt(*tags, hp=30):
    return Entity(key="t", entity_type=T_MONSTER, fallback_name="cel",
                  tags=list(tags), hp=hp, max_hp=hp)


# ── Trzy reguły psychiki ────────────────────────────────────────────


def test_fear_triggers_terror():
    r = _sys.resolve_psyche(None, "rzuć", _src("robactwo"),
                            _tgt("lęk:robactwo"))
    assert r.matched and r.effect == "przerażenie"


def test_terror_sets_stun_and_status():
    tgt = _tgt("lęk:robactwo")
    _sys.resolve_psyche(None, "rzuć", _src("robactwo"), tgt)
    st = tgt.state or {}
    assert _sys.has_systemic_status(tgt, "przerażony")
    assert st.get("systemic_stun_chance", 0) > 0
    assert st.get("systemic_turns", 0) > 0


def test_disgust_triggers_recoil():
    tgt = _tgt("odraza:robactwo")
    r = _sys.resolve_psyche(None, "rzuć", _src("robactwo"), tgt)
    assert r.matched and r.effect == "cofnięcie"
    assert (tgt.state or {}).get("systemic_slow") is True


def test_desire_triggers_distraction():
    tgt = _tgt("pragnienie:mięso")
    r = _sys.resolve_psyche(None, "podrzuć", _src("mięso", "jedzenie"), tgt)
    assert r.matched and r.effect == "rozproszenie"


# ── Priorytet + brak fałszywych trafień ─────────────────────────────


def test_fear_beats_desire_when_both_match():
    tgt = _tgt("lęk:gad", "pragnienie:gad")
    r = _sys.resolve_psyche(None, "rzuć", _src("gad"), tgt)
    assert r.effect == "przerażenie"


def test_no_psyche_no_match():
    assert _sys.resolve_psyche(None, "rzuć", _src("robactwo"),
                               _tgt("monster", "humanoid")).matched is False


def test_identity_mismatch_no_match():
    # Cel boi się robactwa, ale rzucamy ogniem — inna tożsamość.
    assert _sys.resolve_psyche(None, "rzuć", _src("ogień"),
                               _tgt("lęk:robactwo")).matched is False


def test_source_identity_ignores_prefixed_tags():
    # Źródło z samym tagiem psyche (z dwukropkiem) nie ma tożsamości.
    assert _sys.resolve_psyche(None, "rzuć", _src("lęk:robactwo"),
                               _tgt("lęk:robactwo")).matched is False


# ── Helpery ─────────────────────────────────────────────────────────


def test_target_psyche_and_has_psyche():
    tgt = _tgt("lęk:robactwo", "odraza:brud")
    assert _sys.target_psyche(tgt, "lęk") == {"robactwo"}
    assert _sys.target_psyche(tgt, "odraza") == {"brud"}
    assert _sys.has_psyche(tgt) is True
    assert _sys.has_psyche(_tgt("monster")) is False


# ── Żywy seed treści ────────────────────────────────────────────────


def test_content_seed_inspector_disgusted_by_vermin():
    sess = HeadlessSession()
    inspector = sess.spawn_from_mon("biotech_inspector")
    assert _sys.has_psyche(inspector)
    assert _sys.target_psyche(inspector, "odraza") == {"robactwo"}
    rat = sess.spawn_from_mon("tunnel_runt")
    assert "robactwo" in _sys._source_identity(rat)
    r = _sys.resolve_psyche(sess.world, "rzuć", rat, inspector)
    assert r.matched and r.effect == "cofnięcie"


def test_throw_vermin_at_inspector_via_command():
    sess = HeadlessSession()
    sess.spawn_from_mon("tunnel_runt")
    sess.spawn_from_mon("biotech_inspector")
    out = sess.send("rzuć szczurek w inspektor")
    text = "\n".join(t for t, _ in out)
    assert "wzdryga" in text or "odsuwa" in text, \
        f"psychika nie odpaliła przez komendę:\n{text}"
    assert_polish_only(text)
