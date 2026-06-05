"""Prompt 29.38 — Polish-only display for companion status + abilities.

Bug zgłoszony przez użytkownika (P29.37 sweep): w widoku zwierzaka
pojawiało się "Stan: active" i "Umiejętności: scout_aerial,
warn_danger" — surowe sluga zamiast polskich tłumaczeń. Gra jest
Polish-only, więc każdy raw slug widoczny dla gracza to bug.

P29.38 dodaje w engine/companion.py:
  * _STATUS_PL    — mapowanie statusów (active/missing/injured/dead)
  * _ABILITY_PL   — 12 umiejętności zwierzaków na polski
  * _SPONSOR_TAG_PL — sponsor keys + descriptive tags (bird, cat,
                       talking, …) na polski
  * status_pl(key) / abilities_pl_list(list) / sponsor_tag_pl(key) /
    sponsor_tags_pl_list(list) — publiczne helpery do zawijania
    surowych sluga w polskie etykiety przed wyświetleniem.

Wireuje przez:
  * engine/companion_actions.py — komenda "sprawdź zwierzę" w logu
  * ui/journal.py — zakładka Towarzysze w dzienniku

Pokrywa:
  * status_pl() mapuje wszystkie 4 statusy.
  * abilities_pl_list() mapuje typowe sluga z content/data/pets.
  * Nieznany slug przechodzi przez (czytelny "fall-through" sygnał
    że trzeba dodać tłumaczenie).
  * Smoke: render journal entry dla zwierzaka z slugami scout_aerial
    + warn_danger nie zawiera surowych sluga (test regresji wycieku
    z screenshota użytkownika).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine import companion as _comp
from ..engine.world import WorldState
from ..engine.character import Character


# ── status_pl ──────────────────────────────────────────────────────────

def test_status_pl_maps_all_four_statuses():
    assert _comp.status_pl("active") == "aktywny"
    assert _comp.status_pl("missing") == "zaginiony"
    assert _comp.status_pl("injured") == "ranny"
    assert _comp.status_pl("dead") == "martwy"
    print("  status_pl mapuje 4 statusy na polski: OK")


def test_status_pl_unknown_falls_through():
    # Nieznany slug przechodzi bez modyfikacji — sygnał że trzeba
    # dodać tłumaczenie, nie cichy fallback na pustkę.
    assert _comp.status_pl("zombie") == "zombie"
    print("  status_pl unknown -> fall-through (loud signal): OK")


# ── abilities_pl_list ──────────────────────────────────────────────────

def test_abilities_pl_list_covers_pet_catalog():
    """Każdy slug z content/data/pets.ABILITY_* musi mieć polskie
    tłumaczenie."""
    from ..content.data import pets as _pets
    slugs = [v for k, v in vars(_pets).items()
             if k.startswith("ABILITY_") and isinstance(v, str)]
    assert slugs, "no ABILITY_* constants found"
    pl_labels = _comp.abilities_pl_list(slugs)
    # Żadna etykieta nie powinna być surowym slugiem (skoro mamy
    # mapowanie, fall-through = brak tłumaczenia).
    missing = [s for s, pl in zip(slugs, pl_labels) if s == pl]
    assert not missing, f"missing PL labels for: {missing}"
    print(f"  abilities_pl_list pokrywa {len(slugs)} sluga z catalogu: OK")


def test_abilities_pl_list_specific_translations():
    out = _comp.abilities_pl_list(["scout_aerial", "warn_danger"])
    assert out == ["zwiad z powietrza", "ostrzeganie przed pułapkami"], out
    print(f"  scout_aerial + warn_danger -> {out}: OK")


def test_abilities_pl_list_empty_and_none():
    assert _comp.abilities_pl_list(None) == []
    assert _comp.abilities_pl_list([]) == []
    print("  abilities_pl_list None / [] -> []: OK")


# ── sponsor_tag_pl ─────────────────────────────────────────────────────

def test_sponsor_tag_pl_translates_sponsor_keys():
    assert _comp.sponsor_tag_pl("kanal_7_krawedz") == "Kanał 7 Krawędź"
    assert _comp.sponsor_tag_pl("novachem_biotech") == "NovaChem-Biotech"
    print("  sponsor_tag_pl mapuje sponsor keys na polski: OK")


def test_sponsor_tag_pl_translates_descriptive_tags():
    assert _comp.sponsor_tag_pl("bird") == "ptak"
    assert _comp.sponsor_tag_pl("talking") == "mówiący"
    print("  sponsor_tag_pl mapuje tagi opisowe (bird, talking, …): OK")


# ── Journal render: regresja wycieku z screenshota ─────────────────────

def test_journal_companion_render_has_no_raw_slugs():
    """Regresja: screenshot użytkownika pokazał 'Umiejętności:
    scout_aerial, warn_danger' i 'Stan: active'. Po P29.38 render
    journala dla zwierzaka z tymi samymi slugami musi mieć polskie
    etykiety — nigdy surowych snake_case."""
    from ..ui.journal import _collect_companions
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    pet = _comp.Companion(
        kind=_comp.KIND_PET,
        species_key="papuga_anty_host",
        display_name_pl="Papuga Konferansjera",
        bond=5, stress=0,
        status=_comp.STATUS_ACTIVE,
        abilities=["scout_aerial", "warn_danger"],
        sponsor_likes_tags=["kanal_7_krawedz", "bird", "talking"],
    )
    _comp.register_companion(w, pet)
    entries = _collect_companions(w)
    assert entries, "no journal entries returned"
    blob = ""
    for e in entries:
        blob += f"{e.title} {e.subtitle} {e.status} {e.detail}\n"
    # Te surowce NIGDY nie powinny się pokazać w widoku gracza.
    banned = ["scout_aerial", "warn_danger", "kanal_7_krawedz",
              "papuga_anty_host"]
    leaks = [s for s in banned if s in blob]
    assert not leaks, f"raw slugs leaked into journal: {leaks}\n{blob}"
    # I polskie tłumaczenia muszą tam być.
    assert "zwiad z powietrza" in blob
    assert "ostrzeganie przed pułapkami" in blob
    print("  journal companion render: zero raw slugs, polskie etykiety: OK")


def test_journal_subtitle_uses_polish_status_when_not_active():
    from ..ui.journal import _collect_companions
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    pet = _comp.Companion(
        kind=_comp.KIND_PET,
        species_key="papuga_anty_host",
        display_name_pl="Papuga Konferansjera",
        bond=5, stress=0,
        status=_comp.STATUS_INJURED,   # nie-active -> pokazuje się w subtitle
        abilities=[],
    )
    _comp.register_companion(w, pet)
    entries = _collect_companions(w)
    assert entries
    subtitle = entries[0].subtitle
    assert "RANNY" in subtitle, f"expected polish status in subtitle; got {subtitle}"
    assert "INJURED" not in subtitle, f"raw slug leaked; got {subtitle}"
    print(f"  injured -> 'RANNY' nie 'INJURED' w subtitle: OK ({subtitle})")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_status_pl_maps_all_four_statuses()
    test_status_pl_unknown_falls_through()
    test_abilities_pl_list_covers_pet_catalog()
    test_abilities_pl_list_specific_translations()
    test_abilities_pl_list_empty_and_none()
    test_sponsor_tag_pl_translates_sponsor_keys()
    test_sponsor_tag_pl_translates_descriptive_tags()
    test_journal_companion_render_has_no_raw_slugs()
    test_journal_subtitle_uses_polish_status_when_not_active()
    print("Prompt 29.38 companion Polish-display smoke: OK")


if __name__ == "__main__":
    main()
