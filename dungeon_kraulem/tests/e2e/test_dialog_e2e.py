"""E2E dla #189 — pogadaj z NPC otwiera dialog tree, nie legacy
skill check.

Te testy CAPTUREUJĄ dokładnie failure mode z playtest user:
> pogadaj z Kapitan Drużyny
[rozmowa] d20(8) + CHA(-1) + tła(+1) = 4 vs TT 10 → kryt. porażka

Po fix (commit d411a2f): EXPECT że Game przechodzi do STATE_DIALOG
z odpowiednim drzewkiem, NIE wykonuje skill check resolver.

Rule 12b — regression tests które wyłapałyby observed failure mode.
"""
from __future__ import annotations

from .headless import HeadlessSession, assert_polish_only


# ── Kapitan Drużyny → liga_brawurowa_grunt ─────────────────────────


def test_pogadaj_z_kapitan_druzyny_opens_dialog_tree():
    """Repro #189: na F2 spawn Kapitan, pogadaj → dialog state."""
    sess = HeadlessSession(floor_number=2)
    sess.spawn_from_mon("kapitan_druzyny")

    new_logs = sess.send("pogadaj z Kapitan Drużyny")

    # EXPECT: dialog state opened
    assert sess.state == "dialog", (
        f"oczekiwany state='dialog', got {sess.state!r}\n"
        f"logs: {new_logs}")
    assert sess.dialogue_state is not None, "brak dialogue_state"
    assert sess.dialogue_state.tree_key == "liga_brawurowa_grunt", (
        f"zły tree_key: {sess.dialogue_state.tree_key!r}")

    # NOT: skill check fallback (legacy 'rozmowa' d20 log line)
    joined = sess.last_log_text()
    assert "[rozmowa]" not in joined, (
        f"WYCIEK do legacy skill check zamiast dialog:\n{joined}")
    assert "d20" not in joined.lower() or sess.state == "dialog", (
        f"d20 roll wykonany zamiast dialog open:\n{joined}")


def test_pogadaj_z_trener_szkoleniowiec_opens_liga_tree():
    """Trener Szkoleniowiec (też faction:liga) → ten sam tree."""
    sess = HeadlessSession(floor_number=2)
    sess.spawn_from_mon("trener_szkoleniowiec")

    sess.send("pogadaj z Trener Szkoleniowiec")

    assert sess.state == "dialog"
    assert sess.dialogue_state.tree_key == "liga_brawurowa_grunt"


# ── Strażnik Bramy → intake_warden ──────────────────────────────────


def test_pogadaj_z_straznik_bramy_opens_intake_warden_tree():
    """F1 floor boss — pogadaj → intake_warden tree."""
    sess = HeadlessSession(floor_number=1)
    sess.spawn_from_mon("intake_warden")

    sess.send("pogadaj ze Strażnik")

    assert sess.state == "dialog"
    assert sess.dialogue_state.tree_key == "intake_warden"


# ── Default crawler (fallback) ──────────────────────────────────────


def test_pogadaj_z_random_crawler_opens_default_tree():
    """Random T_CRAWLER bez explicit tree_key → default_crawler."""
    from ..e2e.headless import HeadlessSession
    from ...engine.entity import Entity, T_CRAWLER

    sess = HeadlessSession(floor_number=1)
    crawler = Entity(
        key="crawler_test", entity_type=T_CRAWLER,
        fallback_name="Arek Vance", tags=["vet", "calm"],
        affordances=["inspect", "talk", "attack"],
        hp=10, max_hp=10, ac=11)
    sess.put_in_room(crawler)

    sess.send("pogadaj z Arek")

    assert sess.state == "dialog"
    assert sess.dialogue_state.tree_key == "default_crawler"


# ── Regular mob (no talk affordance) ────────────────────────────────


def test_pogadaj_z_szczurek_no_dialog_legacy_path():
    """Tunelowy szczurek (beast, brak talk) — talk fallback.
    Engine NIE crashuje, ale dialog się NIE otwiera."""
    from ...engine.entity import Entity, T_MONSTER

    sess = HeadlessSession(floor_number=1)
    szczurek = Entity(
        key="szczurek", entity_type=T_MONSTER,
        fallback_name="Tunelowy Szczurek",
        tags=["beast", "small"],
        affordances=["inspect", "attack"],  # NO talk
        hp=5, max_hp=5, ac=11)
    sess.put_in_room(szczurek)

    sess.send("pogadaj ze Szczurek")

    # Dialog NOT opened (no talk affordance)
    assert sess.state != "dialog", (
        f"dialog opened for non-talkable mob: state={sess.state}")


# ── Dialog content Polish-only ──────────────────────────────────────


def test_kapitan_dialog_content_no_calque():
    """Tekst startowego nodu Kapitana nie ma typowych English / calque
    patterns. Capturuje failure mode w którym moje fixe wpadały."""
    from ...engine import dialogue as _dlg

    tree = _dlg.get_tree("liga_brawurowa_grunt")
    assert tree is not None
    start = tree.node(tree.start_node)
    assert start is not None
    # Full text + all option labels
    text = start.text + " " + " ".join(o.label for o in start.options)
    assert_polish_only(text)


def test_warden_dialog_content_no_calque():
    from ...engine import dialogue as _dlg

    tree = _dlg.get_tree("intake_warden")
    start = tree.node(tree.start_node)
    text = start.text + " " + " ".join(o.label for o in start.options)
    assert_polish_only(text)


def test_default_crawler_dialog_content_no_calque():
    from ...engine import dialogue as _dlg

    tree = _dlg.get_tree("default_crawler")
    start = tree.node(tree.start_node)
    text = start.text + " " + " ".join(o.label for o in start.options)
    assert_polish_only(text)
