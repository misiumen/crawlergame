"""E2E P29.75 — „Sortownia Zawodników" (biom intake): tożsamość + naprawa
wiringu profilu bojowego.

Sedno: damage_type / resists / vulnerable_to / immune_to / behavior z
szablonów MON były MARTWYM kodem — buildery encji
(floor_generator._entity_from_table, procgen._from_template, combat
sponsor-hunter) konstruowały Entity bez ich przepisania. Tylko arena.py
je kopiowała. Efekt: „freezer_carver wrażliwy na ogień" nigdy nie działał
w realnej grze. Te testy pilnują, że teraz słabości faktycznie gryzą i że
override zachowania AI ląduje na encji — przez WSZYSTKIE ścieżki spawnu.
"""
from __future__ import annotations

from ...engine.floor_generator import _entity_from_table
from ...engine.procgen import _from_template
from ...engine.entity import T_MONSTER
from ...engine import damage as dmg
from ...content.data.entity_templates import MON, apply_combat_profile
from ...content.data.floor_biomes import FLOOR_BIOMES


# ── Wiring profilu bojowego (regresja martwej tabeli słabości) ──────


def test_weakness_survives_spawn_via_floor_generator():
    # Główna ścieżka spawnu floor — wcześniej GUBIŁA te pola.
    fc = _entity_from_table(MON, "freezer_carver", "r1", T_MONSTER)
    assert fc.vulnerable_to == ["fire"]
    assert fc.resists == ["cold"]


def test_weakness_survives_spawn_via_procgen():
    # Druga ścieżka (hand-authored F1) — też musi przepisać profil.
    e = _from_template(MON, "freezer_carver", "r1", T_MONSTER)
    assert e is not None
    assert "fire" in e.vulnerable_to
    assert "cold" in e.resists


def test_immune_and_damage_type_survive_spawn():
    bi = _entity_from_table(MON, "biotech_inspector", "r1", T_MONSTER)
    assert "poison" in bi.immune_to        # hazmat — chem-proof
    iw = _entity_from_table(MON, "intake_warden", "r1", T_MONSTER)
    assert iw.damage_type == "electric"    # paralizator


def test_freezer_carver_fire_doubles_cold_halves():
    fc = _entity_from_table(MON, "freezer_carver", "r1", T_MONSTER)
    fc.hp = fc.max_hp = 100
    r_fire = dmg.apply_damage(None, fc, 10, "fire", apply_status=False)
    assert r_fire["vulnerable"] is True
    assert r_fire["amount_dealt"] == 20         # 2× — słabość gryzie

    fc.hp = 100
    r_cold = dmg.apply_damage(None, fc, 10, "cold", apply_status=False)
    assert r_cold["resisted"] is True
    assert r_cold["amount_dealt"] == 5          # ½× — odporność działa


def test_intake_warden_acid_doubles():
    iw = _entity_from_table(MON, "intake_warden", "r1", T_MONSTER)
    iw.hp = iw.max_hp = 200
    r = dmg.apply_damage(None, iw, 10, "acid", apply_status=False)
    assert r["vulnerable"] is True
    assert r["amount_dealt"] == 20


# ── Override zachowania AI per mob (różnorodność per biom) ──────────


def test_behavior_override_lands_on_spawn():
    # Tylko moby Sortowni (z grafikami usera). relay_warden / QC-agent to
    # moby wieloBiomowe — celowo NIE intake, więc nie ma ich tu.
    cases = {
        "biotech_inspector": "guard",
        "intake_warden":     "guard",
        "freezer_carver":    "berserker",
    }
    for key, expected in cases.items():
        ent = _entity_from_table(MON, key, "r1", T_MONSTER)
        assert (ent.state or {}).get("behavior") == expected, key


def test_default_behavior_reads_override():
    # Pełna integracja z combat.default_behavior (nie tylko surowy state).
    from ...engine import combat as cmb
    iw = _entity_from_table(MON, "intake_warden", "r1", T_MONSTER)
    assert cmb.default_behavior(iw) == cmb.BEHAVIOR_GUARD
    # tunnel_runt — swarm z taga „small" (bez jawnego override).
    tr = _entity_from_table(MON, "tunnel_runt", "r1", T_MONSTER)
    assert cmb.default_behavior(tr) == cmb.BEHAVIOR_SWARM


# ── Roster Sortowni: tagowanie + nazwa biomu ────────────────────────


def test_intake_roster_tagged():
    # Moby Sortowni = te, do których user zrobił grafiki. Każdy mob należy
    # do JEDNEGO biomu (nie ma puli generycznych) → wszystkie niosą „intake".
    roster = ["tunnel_runt", "freezer_carver", "biotech_inspector",
              "intake_warden"]
    for key in roster:
        ent = _entity_from_table(MON, key, "r1", T_MONSTER)
        assert "intake" in ent.tags, key


def test_intake_mobs_do_not_leak_to_other_biomes():
    # REGRESJA wycieku: tunnel_runt/freezer_carver były seedowane przez
    # neutralne pokoje → trafiały na zoo/muzeum/itd. Po dodaniu room_tagu
    # „intake" pokojom które je seedują, nie mogą już spawnować się poza
    # Sortownią. (intake_warden to boss F1 — osobna ścieżka, pomijamy.)
    from ...engine.floor_generator import generate_floor
    from ...engine.world import WorldState
    from ...engine.character import Character
    watch = {"tunnel_runt", "freezer_carver", "biotech_inspector"}
    for seed in range(1, 60):
        for fn in (3, 4, 5, 6):
            w = WorldState(); w.character = Character(name="t", background="janitor")
            f = generate_floor(w, floor_number=fn, seed=seed)
            if f.biome_key == "intake_industrial":
                continue
            for r in f.rooms.values():
                for e in r.entities:
                    assert e.key not in watch, (
                        f"{e.key} wyciekł na biom {f.biome_key} (F{fn}, seed {seed})")


def test_biome_name_is_sortownia():
    assert FLOOR_BIOMES["intake_industrial"].name_pl == "Sortownia Zawodników"
    # slug (klucz) NIE zmieniony — tylko display PL.
    assert FLOOR_BIOMES["intake_industrial"].key == "intake_industrial"


def test_old_biome_name_does_not_leak():
    # Po rename nie powinno być „Aklimatyzacj" w tytułach/etykietach/nazwie
    # bossa (sub-roomy mogą zostać — to flavor wewnątrz biomu).
    from ...content.data.room_templates import FLOOR_1_TITLE_FALLBACK
    from ...content.data.floor_archetypes import FLOOR_ARCHETYPES
    assert "Aklimatyzacj" not in FLOOR_1_TITLE_FALLBACK
    assert "Aklimatyzacj" not in FLOOR_ARCHETYPES["survival_sprawl"]["fallback_label"]
    iw = _entity_from_table(MON, "intake_warden", "r1", T_MONSTER)
    assert "Aklimatyzacj" not in iw.fallback_name


def test_apply_combat_profile_safe_on_non_monster():
    # Helper musi być bezpieczny dla braku proto / pustego dicta.
    assert apply_combat_profile(None, {}) is None
    env = _entity_from_table(MON, "tunnel_runt", "r1", T_MONSTER)
    # Idempotencja — drugie wywołanie nie psuje stanu.
    apply_combat_profile(env, MON["tunnel_runt"])
    assert "fire" in env.vulnerable_to


# ── P29.75b — miniboss Sortowni + kompletność roster/pokoi ──────────


def test_intake_miniboss_exists_and_tagged():
    nz = _entity_from_table(MON, "nadzorca_sortowni", "r1", T_MONSTER)
    assert nz is not None
    assert "intake" in nz.tags and "miniboss" in nz.tags
    assert "acid" in nz.vulnerable_to          # odkrywalna słabość (wiring P29.75)
    assert (nz.state or {}).get("behavior") == "guard"
    tpl = MON["nadzorca_sortowni"]
    assert tpl.get("floor_min") == 1 and tpl.get("floor_max") == 2


def test_intake_miniboss_in_placement_pool():
    # Miniboss musi być w puli _available_minibosses dla biomu intake na F1,
    # inaczej nigdy się nie pojawi.
    from ...engine.floor_generator import _available_minibosses
    pool = _available_minibosses(1, "intake")
    assert "nadzorca_sortowni" in pool


def test_intake_combat_rooms_seed_only_intake_mobs():
    # REGRESJA: pokój intake seedował mutant_szczur (mob ZOO). Każdy mob
    # seedowany przez pokój intake MUSI być mobem intake (jeden biom = jeden mob).
    from ...content.data.room_pool import ROOM_POOL
    offenders = []
    for tmpl in ROOM_POOL:
        tags = set(tmpl.get("tags") or [])
        if "intake" not in tags:
            continue
        for mkey in (tmpl.get("entity_seed_pools", {}) or {}).get("mon", []):
            mob_tags = set(MON.get(mkey, {}).get("tags") or [])
            if "intake" not in mob_tags:
                offenders.append((tmpl.get("template_id"), mkey))
    assert not offenders, f"pokoje intake seedują obce moby: {offenders}"


def test_biotech_inspector_is_seeded_somewhere():
    # biotech_inspector był martwym contentem (żaden pokój go nie seedował).
    from ...content.data.room_pool import ROOM_POOL
    seeded = any("biotech_inspector" in (t.get("entity_seed_pools", {}) or {}).get("mon", [])
                 for t in ROOM_POOL)
    assert seeded, "biotech_inspector nie jest seedowany przez żaden pokój"


def test_intake_floor_gets_miniboss():
    # Na zbudowanym biomie (Sortownia) F1 dostaje min 1 mini bossa.
    from ...engine.floor_generator import generate_floor
    from ...engine.world import WorldState
    from ...engine.character import Character
    for seed in range(1, 200):
        w = WorldState(); w.character = Character(name="t", background="janitor")
        f = generate_floor(w, floor_number=1, seed=seed)
        if f.biome_key != "intake_industrial":
            continue
        minis = [e for r in f.rooms.values() for e in r.entities
                 if "miniboss" in (e.tags or []) and "boss" not in (e.tags or [])]
        assert minis, f"intake F1 (seed {seed}) bez minibossa"
        return
    import pytest
    pytest.skip("nie trafiono seedu intake na F1 w zakresie 1-200")
