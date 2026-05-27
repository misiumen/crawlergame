"""Prompt 29.16 — Sponsor variety smoke suite.

Audit finding: 6 sponsors was thin for a DCC-faithful crawler.
P29.16 brings the roster to 11 by adding five new factions with
distinct mechanical niches:
  * Bractwo Komornika      — debt/bribery/intimidation
  * Liga Brawurowa         — stunt / dramatic plays
  * Spółdzielnia Mrówek    — stealth / non-lethal
  * Bóg Polimerów          — chemical / mutation / fungal
  * Stadion Wolności       — populist / mass-kill / spectacle

Covers:
  * SPONSORS catalog has 11 entries.
  * Each new entry passes schema check (all required keys present,
    non-empty likes/dislikes, hunter_key present in MON catalog).
  * Each new hunter exists in MON with reasonable scaled stats.
  * Sponsor competition: feeding a like-tag bumps the matching
    sponsor without affecting others.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..content.data.sponsors import SPONSORS, all_sponsor_keys as _file_keys
from ..engine.sponsors import all_sponsor_keys, note_player_tag, _attention_dict
from ..content.data.entity_templates import MON
from ..engine.world import WorldState
from ..engine.character import Character


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            audience_rating=60)
    return w


# ── Roster size + new keys ───────────────────────────────────────────────

def test_sponsor_count_grew():
    keys = all_sponsor_keys()
    assert len(keys) == 11, f"expected 11 sponsors, got {len(keys)}: {keys}"
    print(f"  {len(keys)} sponsors in catalog: OK")


def test_new_sponsor_keys_present():
    expected = {"bractwo_komornika", "liga_brawurowa",
                "spoldzielnia_mrowek", "bog_polimerow",
                "stadion_wolnosci"}
    missing = expected - set(all_sponsor_keys())
    assert not missing, f"missing new sponsors: {missing}"
    print(f"  5 new sponsor keys present: OK")


# ── Schema ──────────────────────────────────────────────────────────────

REQUIRED_KEYS = ("key", "name_fallback", "tagline_fallback",
                 "tone", "likes_tags", "dislikes_tags",
                 "gift_pool", "hunter_key", "heckle_keys",
                 "intervention_cooldown_minutes")


def test_every_sponsor_has_full_schema():
    bad = []
    for key, data in SPONSORS.items():
        for req in REQUIRED_KEYS:
            if req not in data or data[req] in ("", None):
                bad.append(f"{key}.{req}")
            elif isinstance(data[req], list) and not data[req]:
                bad.append(f"{key}.{req} (empty list)")
    assert not bad, f"schema gaps: {bad}"
    print(f"  every sponsor has required keys: OK")


def test_likes_and_dislikes_are_disjoint():
    """Sanity: a sponsor shouldn't both like and dislike the same tag."""
    for key, data in SPONSORS.items():
        common = set(data["likes_tags"]) & set(data["dislikes_tags"])
        assert not common, f"{key} has tag in both lists: {common}"
    print("  likes/dislikes are disjoint: OK")


# ── Hunter NPCs exist + have combat stats ───────────────────────────────

def test_every_hunter_key_resolves_to_mon():
    missing = []
    for key, data in SPONSORS.items():
        hkey = data["hunter_key"]
        if hkey not in MON:
            missing.append(f"{key} → {hkey}")
    assert not missing, f"sponsor hunters not in MON: {missing}"
    print("  every sponsor.hunter_key maps to a MON entry: OK")


def test_new_hunter_mon_templates_are_combat_ready():
    new = ("asesor_komornika", "ekstremalny_zawodnik",
           "koordynator_robotniczy", "kaplan_polimerow",
           "weteran_trybun")
    for k in new:
        m = MON[k]
        # _apply_balance_scale multiplied HP × 5; expect at least
        # 14 design → 70 effective.
        assert m["hp"] >= 60, f"{k} HP too low: {m['hp']}"
        assert m["ac"] >= 10
        assert m.get("damage_dice")
        assert "sponsor_hunter" in (m.get("tags") or [])
    print(f"  {len(new)} new hunters scaled + tagged sponsor_hunter: OK")


# ── Attention competition ───────────────────────────────────────────────

def test_tag_routes_to_matching_sponsor():
    """Feeding a tag only one sponsor likes should bump that sponsor.
    Mrówki likes 'stealth_takedown' (no one else in this roster).
    """
    w = _mk_world()
    note_player_tag(w, "stealth_takedown", weight=1)
    att = _attention_dict(w)
    val = int(att.get("spoldzielnia_mrowek", 0))
    assert val > 0, f"mrowki should have positive attention; att={att}"
    # Bractwo dislikes "amnesty" / "negotiate_kindly" — but doesn't
    # touch stealth tag; should stay at 0.
    assert int(att.get("bractwo_komornika", 0)) == 0
    print(f"  stealth tag → mrowki +{val}, bractwo unchanged: OK")


def test_unique_hunters_dont_collide():
    """The 5 new hunters must be distinct + distinct from the existing
    6 (audit: no double-booking)."""
    hunters = [d["hunter_key"] for d in SPONSORS.values()]
    assert len(hunters) == len(set(hunters)), \
        f"sponsor hunter_keys collide: {hunters}"
    print("  all 11 sponsor.hunter_keys are unique: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_sponsor_count_grew()
    test_new_sponsor_keys_present()
    test_every_sponsor_has_full_schema()
    test_likes_and_dislikes_are_disjoint()
    test_every_hunter_key_resolves_to_mon()
    test_new_hunter_mon_templates_are_combat_ready()
    test_tag_routes_to_matching_sponsor()
    test_unique_hunters_dont_collide()
    print("Prompt 29.16 sponsor variety smoke: OK")


if __name__ == "__main__":
    main()
