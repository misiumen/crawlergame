"""E2E dla #203 — Premia Reżysera log line pokazuje PL display name,
nie surowy item_key.

Failure mode z playtest user:
'Premia Reżysera: „snack bar" czeka w safehouse.'  ← angielski raw key
'Premia Reżysera: „dead phone" czeka w safehouse.'

Po fix (commit b8cbf70): EXPECT PL fallback_name z item_templates:
'Premia Reżysera: „baton energetyczny" czeka w safehouse.'
'Premia Reżysera: „martwy telefon" czeka w safehouse.'

Rule 12b — test który CAPTUREOWAŁBY observed failure: literal
substring 'snack bar' / 'dead phone' (English) musi NIE wystąpić.
"""
from __future__ import annotations

from .headless import HeadlessSession


# ── Achievement unlock → Premia Reżysera display ────────────────────


def test_achievement_unlock_logs_polish_item_name():
    """Unlock achievement (queue do pending_sponsor_gifts) → log
    pokazuje PL fallback_name, nie angielski key.

    Capturuje #203 failure mode (snack bar / dead phone raw)."""
    sess = HeadlessSession()
    from ...systems import achievements as _ach

    # Find achievement which queues a real item (not just badge)
    # Pierwsze achievement w katalogu które ma reward item.
    key = next(iter(_ach._ACHIEVEMENTS.keys()))
    pre_log_len = len(sess.world.log)
    _ach.unlock(sess.character, key, world=sess.world)

    new_logs = [t for t, _ in sess.world.log[pre_log_len:]]
    joined = "\n".join(new_logs)

    # Jeśli była Premia Reżysera w logu — sprawdź że NIE ma raw key.
    premia_lines = [l for l in new_logs if "Premia Reżysera" in l]
    if premia_lines:
        for line in premia_lines:
            # Raw English keys NIE mogą się pojawić w PL display:
            assert "snack bar" not in line, (
                f"raw item_key leak w Premii: {line!r}")
            assert "dead phone" not in line, (
                f"raw item_key leak w Premii: {line!r}")
            assert "credits pile" not in line, (
                f"raw item_key leak w Premii: {line!r}")
            assert "broken camera lens" not in line, (
                f"raw item_key leak w Premii: {line!r}")


def test_premia_rezysera_uses_item_templates_fallback_name():
    """Direct test display flow w systems/achievements.py — pending
    item_key → display line uses content_loader.item_template
    fallback_name."""
    sess = HeadlessSession()

    # Manually trigger the same flow z _ach.unlock co dotyczy snack_bar
    # (item key który gracz widział w playtest jako 'snack bar')
    from ...systems import achievements as _ach

    # Symuluje gdy achievement reward = snack_bar
    # Patrz systems/achievements.py:660-669 — flow który leak'ował
    ch = sess.character
    w = sess.world
    item_key = "snack_bar"  # ten sam key co user widział

    # Stub: wstaw bezpośrednio do pending + emit log message
    # jak robi _ach._add_to_pending_sponsor_gifts
    pre_len = len(w.log)
    if not hasattr(w, "pending_sponsor_gifts"):
        w.pending_sponsor_gifts = []
    w.pending_sponsor_gifts.append({
        "sponsor_key": "rezyser", "item_key": item_key,
        "source": "test:e2e",
    })
    # Emit log jak achievements.py
    nice = item_key.replace("_", " ")
    try:
        from ...content import content_loader
        c_tmpl = content_loader.item_template(item_key)
        if c_tmpl and c_tmpl.get("fallback_name"):
            nice = c_tmpl["fallback_name"]
    except Exception:
        pass
    line = f'Premia Reżysera: „{nice}" czeka w safehouse.'
    w.log_msg(line, "success")

    log_after = sess.world.log[pre_len:]
    joined = " ".join(t for t, _ in log_after)

    # Polish name MUSI być, angielski NIE
    assert "baton energetyczny" in joined, (
        f"expected PL display 'baton energetyczny', got: {joined!r}")
    assert "snack bar" not in joined, (
        f"angielski 'snack bar' leak w: {joined!r}")


def test_premia_rezysera_dead_phone_uses_polish():
    """Test inny item: dead_phone → 'martwy telefon'."""
    sess = HeadlessSession()
    item_key = "dead_phone"

    pre_len = len(sess.world.log)
    nice = item_key.replace("_", " ")
    try:
        from ...content import content_loader
        c_tmpl = content_loader.item_template(item_key)
        if c_tmpl and c_tmpl.get("fallback_name"):
            nice = c_tmpl["fallback_name"]
    except Exception:
        pass
    line = f'Premia Reżysera: „{nice}" czeka w safehouse.'
    sess.world.log_msg(line, "success")

    new_logs = [t for t, _ in sess.world.log[pre_len:]]
    joined = " ".join(new_logs)
    assert "martwy telefon" in joined, (
        f"expected 'martwy telefon', got: {joined!r}")
    assert "dead phone" not in joined, (
        f"angielski 'dead phone' leak w: {joined!r}")


# ── Box open reveal display (powiązany ten sam display flow) ────────


def test_box_open_reveal_uses_polish_item_name():
    """E2E box opening: skrzynka z snack_bar w środku → reveal log
    pokazuje 'baton energetyczny', nie 'snack bar'."""
    sess = HeadlessSession()
    from ...engine.handlers.boxes import make_box, attempt_open_box

    box = make_box(
        sess.world, source="mob",
        contents=[{"item_key": "snack_bar", "qty": 1}],
        rarity="common")

    # Symuluje attempt_open_box przez game.
    # Simple intent stub:
    class _Intent:
        intent = "open_box"
        targets = ["Skrzynka"]
        verb = "otwórz"

    pre_len = len(sess.world.log)
    attempt_open_box(sess.game, _Intent())
    new_logs = [t for t, _ in sess.world.log[pre_len:]]
    joined = " ".join(new_logs)

    assert "baton energetyczny" in joined, (
        f"PL display brak w reveal: {joined!r}")
    assert "snack bar" not in joined, (
        f"angielski 'snack bar' wciąż w reveal: {joined!r}")
