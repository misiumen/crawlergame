"""P29.36 — Species trait lookup + effect application.

Central API for every code site that needs to ask "does the player
have this species trait active?" Each trait corresponds to a flag
stamped on Character at apply_species time (see systems/species.py).
This module gives engine code a stable function-call surface so the
flag layout can evolve without churning every call site.

Three categories of helper:

1. `has_trait(ch, trait_key) -> bool` — flat lookup. Used for binary
   things (status immunity, can-stealth, can-deploy-non-metal-trap).

2. `incoming_damage_mul(ch, source_tag) -> float`
   `outgoing_audience_mul(ch) -> float`
   `effective_movement_minutes(ch, base) -> int`
   `social_modifier(ch, npc, sponsor_key) -> int`
   etc. — read the union of relevant traits and return the final
   number. Combines passive + drawback effects cleanly.

3. Hooks that mutate world state directly (regen tick, descent
   audience drain, scanner attention bump) — exposed as
   `on_descent(world)`, `on_room_enter(world, room)`,
   `on_safehouse_enter(world, room)`, `on_idle_tick(world, mins)`.

Trait dictionary
----------------
species_trait_<key> → True/False on character.flags. Keys:

Passives:
  all_stats_plus_one          — +1 to STR/DEX/CON/INT/WIS/CHA (enhanced)
  audience_loved              — audience ×1.25 (enhanced)
  low_light_vision            — listen surfaces enemy names adjacent
  pathfinder                  — movement −1 min/step
  metal_skin                  — +2 AC
  scrap_eater                 — eating metal_scrap heals 5 HP
  crit_amplifier              — crit damage +50%
  translucent_sight           — listen surfaces adjacent enemy COUNT
  telepathy                   — N skip-disambiguation/floor
  precog_dodge                — first incoming hit/floor auto-misses
  passive_regen               — +1 HP per idle minute
  spore_intimidate            — threat escalation in your room ×0.7
  third_arm_unarmed           — unarmed +2 dmg + 1d6 die
  grapple_immune              — immune to "grappled" status
  poison_immune               — immune to "poisoned"
  bleed_immune                — immune to "bleeding"
  double_rest                 — rest action heals ×2
  necrotic_resist_50          — 50% resist necrotic/bleeding damage
  corpse_whisper              — inspect_corpse always shows last_words
  magnetic_disarm             — 25% chance disarm on hit metal-armed
  metal_scavenger             — 50% extra metal_scrap per metal-loot room
  iron_grip                   — immune to "disarmed", +2 vs "stunned"

Drawbacks:
  novachem_biopsy_drain       — −1 audience on each descent
  sponsor_envy_non_novachem   — adjust_attention −1 mul for non-NovaChem
  sun_sensitive               — −2 to-hit in bright/safehouse rooms
  crowd_shy                   — −1 social in arena/show rooms
  npc_fear                    — −2 social with all NPCs
  drones_target_first         — drone drop-pods aggressors aim at you
  fragile                     — +25% incoming damage
  bleeds_easy                 — 20% bleed-on-hit on any HP loss
  audience_disturbed          — audience ×0.5
  void_garble                 — 1-in-12 commands get scrambled
  pheromone_attract           — 25% extra mob spawn per room-enter
  companion_repel_2           — companion bond −2 on descent
  horror_first_meet           — −3 social on first meet, persistent
  sponsor_goodwill_cap_10     — sponsor attention capped at 10 (not K7)
  no_food_taste               — cooked-food heal bonus = 0
  emp_vuln                    — +50% damage from shock sources
  uncanny_valley              — audience ×0.85
  companion_repel_1           — companion bond −1 on descent
  ministerstwo_hostile        — Ministerstwo Pamięci frozen hostile
  live_food_no_audience       — eating live food gives no audience
  leaden_steps                — movement +1 min/step
  metal_only_traps            — only metal-tagged traps deployable
  scanner_attention           — +1 NovaChem on safehouse enter
  em_weak                     — +50% damage from shock sources
"""
from __future__ import annotations
from typing import Optional


# ── Core lookup ─────────────────────────────────────────────────────────

def has_trait(ch, trait_key: str) -> bool:
    """True if the character has the named species trait active."""
    if ch is None:
        return False
    flags = getattr(ch, "flags", None) or {}
    return bool(flags.get(f"species_trait_{trait_key}"))


def species_key(ch) -> str:
    return getattr(ch, "species_key", "") or ""


# ── Combat: AC / damage / crit / status ─────────────────────────────────

def ac_bonus(ch) -> int:
    """Flat AC additions from species traits. Read by Character.effective_ac."""
    if ch is None:
        return 0
    bonus = 0
    if has_trait(ch, "metal_skin"):
        bonus += 2
    return bonus


def incoming_damage_mul(ch, source_tag: str = "") -> float:
    """Multiplier on damage TAKEN by the player. Default 1.0.
    `source_tag` is a free-text tag — e.g. "shock", "electric",
    "necrotic", "bleed". Empty = generic damage."""
    if ch is None:
        return 1.0
    mul = 1.0
    if has_trait(ch, "fragile"):
        mul *= 1.25
    tag = (source_tag or "").lower()
    if tag in ("shock", "electric", "emp", "lightning"):
        if has_trait(ch, "emp_vuln") or has_trait(ch, "em_weak"):
            mul *= 1.5
    if tag in ("necrotic", "bleeding", "bleed"):
        if has_trait(ch, "necrotic_resist_50"):
            mul *= 0.5
    return mul


def outgoing_crit_mul(ch) -> float:
    """Crit damage multiplier. Default 1.0 — glassblood crits do 1.5×
    on top of the normal crit (which is already 2×)."""
    if ch is None:
        return 1.0
    if has_trait(ch, "crit_amplifier"):
        return 1.5
    return 1.0


def status_blocked(ch, status_key: str) -> bool:
    """True if the species should refuse this status add."""
    if ch is None:
        return False
    if status_key == "poisoned" and has_trait(ch, "poison_immune"):
        return True
    if status_key in ("bleeding", "bleed") and has_trait(ch, "bleed_immune"):
        return True
    if status_key == "grappled" and has_trait(ch, "grapple_immune"):
        return True
    if status_key == "disarmed" and has_trait(ch, "iron_grip"):
        return True
    return False


def precog_dodge_consume(world) -> bool:
    """Try to consume a precog-dodge charge. True = next incoming
    attack should miss; charge is spent (per floor)."""
    if world is None or world.character is None:
        return False
    ch = world.character
    if not has_trait(ch, "precog_dodge"):
        return False
    if ch.flags is None:
        ch.flags = {}
    fnum = getattr(world.current_floor, "floor_number", 0) if world.current_floor else 0
    used_on = ch.flags.get("species_precog_used_on_floor")
    if used_on == fnum:
        return False
    ch.flags["species_precog_used_on_floor"] = fnum
    return True


def bleed_on_hit_check(ch, rng) -> bool:
    """20% chance to inflict bleeding on any HP loss (glassblood)."""
    if not has_trait(ch, "bleeds_easy"):
        return False
    return rng.random() < 0.20


def magnetic_disarm_check(ch, target_entity, rng) -> bool:
    """25% chance ferromanta magnetically disarms a metal-armed target
    when hitting it. target_entity should be an entity-like with .tags
    or .state[wielded_tags]; we look for "metal" tag."""
    if not has_trait(ch, "magnetic_disarm"):
        return False
    if target_entity is None:
        return False
    tags = []
    try:
        tags = list(target_entity.tags or [])
    except Exception:
        pass
    metal_armed = "metal" in tags or "metal_armed" in tags or \
                  "armored" in tags
    if not metal_armed:
        return False
    return rng.random() < 0.25


# ── Audience ────────────────────────────────────────────────────────────

def audience_mul(ch) -> float:
    """Multiplier applied to positive audience gains."""
    if ch is None:
        return 1.0
    mul = 1.0
    if has_trait(ch, "audience_loved"):
        mul *= 1.25
    if has_trait(ch, "audience_disturbed"):
        mul *= 0.5
    if has_trait(ch, "uncanny_valley"):
        mul *= 0.85
    return mul


def food_audience_suppressed(ch, food_tag: str = "") -> bool:
    """True if eating this food should give NO audience bonus."""
    if ch is None:
        return False
    tag = (food_tag or "").lower()
    if tag in ("live", "raw") and has_trait(ch, "live_food_no_audience"):
        return True
    return False


def cooked_food_heal_bonus_zero(ch) -> bool:
    """Synthetic doesn't taste, so cooked-food bonus heals = 0."""
    return has_trait(ch, "no_food_taste")


# ── Movement ────────────────────────────────────────────────────────────

def movement_minutes(ch, base_min: int) -> int:
    """Adjust per-step movement minutes for traits. pathfinder −1,
    leaden_steps +1. Floor at 1 minute."""
    if ch is None:
        return base_min
    n = base_min
    if has_trait(ch, "pathfinder"):
        n -= 1
    if has_trait(ch, "leaden_steps"):
        n += 1
    return max(1, n)


# ── Social ──────────────────────────────────────────────────────────────

def social_modifier(ch, *, room=None, first_meet: bool = False) -> int:
    """Modifier added to social-roll d20. Negative = harder."""
    if ch is None:
        return 0
    mod = 0
    if has_trait(ch, "npc_fear"):
        mod -= 2
    if first_meet and has_trait(ch, "horror_first_meet"):
        mod -= 3
    if room is not None:
        tags = []
        try:
            tags = list(getattr(room, "sensory_tags", None) or [])
        except Exception:
            pass
        is_show_room = ("arena" in tags or "studio" in tags
                        or "show" in tags or "stage" in tags)
        if is_show_room and has_trait(ch, "crowd_shy"):
            mod -= 1
    return mod


def to_hit_modifier(ch, *, room=None) -> int:
    """Modifier on player's d20 to-hit. Sun-sensitive penalty in
    bright/safehouse rooms."""
    if ch is None or room is None:
        return 0
    mod = 0
    tags = []
    try:
        tags = list(getattr(room, "sensory_tags", None) or [])
    except Exception:
        pass
    bright = ("safehouse" in tags or "bright" in tags
              or "studio_lit" in tags)
    if bright and has_trait(ch, "sun_sensitive"):
        mod -= 2
    return mod


# ── Sponsors ────────────────────────────────────────────────────────────

def sponsor_attention_cap(ch, sponsor_key: str) -> Optional[int]:
    """If the chimera goodwill cap applies to this sponsor, return 10
    (the max). Otherwise None (no cap from species). Kanał 7 is
    exempt."""
    if ch is None:
        return None
    if has_trait(ch, "sponsor_goodwill_cap_10"):
        if sponsor_key != "kanal_7_krawedz":
            return 10
    return None


def sponsor_attention_delta_mul(ch, sponsor_key: str, delta: int) -> int:
    """Adjust delta before clamping. Enhanced human's envy makes
    non-NovaChem positive deltas −1 (min 0). Ministerstwo-hostile
    half_dead suppresses positive deltas to Ministerstwo entirely."""
    if ch is None:
        return delta
    if (has_trait(ch, "ministerstwo_hostile")
            and sponsor_key == "ministerstwo_pamieci"
            and delta > 0):
        return 0
    if (has_trait(ch, "sponsor_envy_non_novachem")
            and sponsor_key != "novachem_biotech"
            and delta > 0):
        return max(0, delta - 1)
    return delta


# ── Traps ───────────────────────────────────────────────────────────────

def trap_deploy_refused(ch, trap_item) -> bool:
    """Ferromanta only deploys metal traps. Returns True if this trap
    should be refused (with a flavor message at the call site)."""
    if ch is None:
        return False
    if not has_trait(ch, "metal_only_traps"):
        return False
    tags = []
    try:
        tags = list(getattr(trap_item, "tags", None) or [])
    except Exception:
        pass
    if "metal" not in tags:
        return True
    return False


def trap_refused_log(ch) -> str:
    return ("Metal nie chce się rozdzielić z tobą — ta pułapka "
            "nie zadziała w twoich rękach.")


# ── Stealth ─────────────────────────────────────────────────────────────

def stealth_refused(ch) -> bool:
    """Ferromanta sets off every detector. Cannot enter hidden status."""
    return has_trait(ch, "scanner_attention")


# ── Rest ────────────────────────────────────────────────────────────────

def rest_heal_mul(ch) -> float:
    if ch is None:
        return 1.0
    if has_trait(ch, "double_rest"):
        return 2.0
    return 1.0


# ── Threat ──────────────────────────────────────────────────────────────

def threat_escalation_mul(ch) -> float:
    """Multiplier on per-tick threat increments in the player's room.
    fungal_host spore_intimidate slows enemies down to 0.7×."""
    if ch is None:
        return 1.0
    if has_trait(ch, "spore_intimidate"):
        return 0.7
    return 1.0


# ── Periodic hooks ──────────────────────────────────────────────────────

def on_idle_tick(world, minutes: int) -> int:
    """Called once per minute of out-of-combat advance_time. Returns
    HP healed by species (0 if none). fungal_host regenerates +1 HP
    per minute up to 50% of max."""
    if world is None or world.character is None:
        return 0
    ch = world.character
    if not has_trait(ch, "passive_regen"):
        return 0
    cap = max(1, ch.max_hp // 2)
    if ch.hp >= cap or ch.hp >= ch.max_hp:
        return 0
    healed = min(int(minutes), ch.max_hp - ch.hp, cap - ch.hp)
    if healed <= 0:
        return 0
    ch.hp += healed
    return healed


def on_safehouse_enter(world, room) -> Optional[str]:
    """Called when player enters a safehouse room. Ferromanta's
    scanner stamp adds +1 NovaChem attention each time. Returns a
    flavor log line or None."""
    if world is None or world.character is None:
        return None
    ch = world.character
    if not has_trait(ch, "scanner_attention"):
        return None
    try:
        from . import sponsors as _sp
        _sp.adjust_attention(world, "novachem_biotech", 1)
    except Exception:
        return None
    return ("Skanery przy wejściu cię klikają — NovaChem-Biotech "
            "notuje (+1 uwagi).")


def on_room_enter(world, room, rng) -> Optional[str]:
    """fungal_host pheromone extra-mob roll. Returns a Polish log
    line if a mob spawned (caller does the actual spawn). For now
    we just flag the room state — engine/floor handlers can read
    it later. Returns None when nothing happens."""
    if world is None or world.character is None or room is None:
        return None
    ch = world.character
    if not has_trait(ch, "pheromone_attract"):
        return None
    # 25% per non-safehouse, non-already-cleared room.
    if "safehouse" in (getattr(room, "sensory_tags", None) or []):
        return None
    if room.state.get("pheromone_spawn_done"):
        return None
    if rng.random() >= 0.25:
        return None
    room.state["pheromone_spawn_done"] = True
    room.state["pheromone_spawn_pending"] = True
    return ("Twoje feromony zwabiły dodatkowego mob'a (zostanie "
            "podłożony przy następnej walce).")


def on_descent(world) -> list:
    """Called at the end of _descend_or_win when the player has
    successfully moved to the next floor. Returns a list of Polish
    log lines for the game to emit. Handles:
      * enhanced_human biopsy drain (−1 audience)
      * companion bond drift (fungal −2, half_dead −1)
    """
    lines = []
    if world is None or world.character is None:
        return lines
    ch = world.character

    if has_trait(ch, "novachem_biopsy_drain"):
        try:
            from . import audience as _aud
            _aud.change_audience(world, -1, source="species_biopsy",
                                 emit_log=False)
        except Exception:
            pass
        lines.append("NovaChem-Biotech robi ci biopsję między piętrami. "
                     "Widownia −1.")

    bond_drift = 0
    if has_trait(ch, "companion_repel_2"):
        bond_drift -= 2
    if has_trait(ch, "companion_repel_1"):
        bond_drift -= 1
    if bond_drift:
        try:
            comps = getattr(world, "companions", None) or {}
            for c in comps.values():
                c.bond = max(-10, c.bond + bond_drift)
            if comps:
                lines.append(f"Towarzysze tracą {abs(bond_drift)} "
                             f"więzi (twoja obecność ich odpycha).")
        except Exception:
            pass
    return lines


# ── Telepathy / disambiguation skip ─────────────────────────────────────

def telepathy_use(world) -> bool:
    """Try to spend one telepathy charge this floor. Returns True if
    consumed (caller should auto-resolve disambiguation to the first
    candidate). One per floor."""
    if world is None or world.character is None:
        return False
    ch = world.character
    if not has_trait(ch, "telepathy"):
        return False
    if ch.flags is None:
        ch.flags = {}
    fnum = getattr(world.current_floor, "floor_number", 0) if world.current_floor else 0
    used_on = ch.flags.get("species_telepathy_used_on_floor")
    if used_on == fnum:
        return False
    ch.flags["species_telepathy_used_on_floor"] = fnum
    return True


# ── Apply species stat bonus for all_stats_plus_one ─────────────────────

def apply_all_stats_bonus(ch) -> None:
    """Enhanced human gets +1 to ALL stats. Called from
    Game._apply_species_full ONCE; sets a flag so re-apply (save/load)
    doesn't double-stack."""
    if ch is None or ch.flags is None:
        return
    if not has_trait(ch, "all_stats_plus_one"):
        return
    if ch.flags.get("species_all_stats_applied"):
        return
    for stat in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        ch.stats[stat] = ch.stats.get(stat, 10) + 1
    ch.flags["species_all_stats_applied"] = True
