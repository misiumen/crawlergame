"""Corpse lifecycle (Prompt 24).

Pure functions; no pygame imports, no UI dependencies. Game.py calls these
from the death point + the player-action handlers. UI just queries entity
state.

API surface:
  transform_to_corpse(world, entity, *, killer=None) -> Entity
  inspect_corpse(world, corpse) -> str (lore line)
  butcher(world, corpse, character) -> ButcherResult
  eat(world, corpse, character) -> EatResult
  template_for(monster_key) -> dict   (re-exported convenience)

Hooks the rest of the codebase reads, but THIS module does not yet
implement (placeholder fields written, future prompts wire them):
  - decay_minutes:    P26b floor-collapse / time-tick decrements
  - smell_budget:     P26b monster aggro pull
  - trophy_drop:      P31 run summary references
  - title_grants:     P28 titles system reads + awards
  - LLM enrichment:   P30 narrator role looks up lore_id

Design notes:
  * Death does NOT delete the monster entity. It mutates in place to
    entity_type=T_CORPSE, sets state.dead=True, swaps the fallback_name,
    appends the 'corpse' tag, and rewrites affordances to the corpse
    set [inspect, salvage, eat, search]. This keeps existing
    references (combat history, sponsor tag bus) valid.
  * Butcher uses the existing materials system (`world.character.materials`).
    No new economy.
  * Eat is risk/reward: HP delta + optional status condition + a
    `note_player_tag` so sponsors react (P27 deepens this).
  * Cannibalism trigger: if the corpse's `original_type` (preserved at
    transform time) is `crawler`, eat emits `cannibal_tag`.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import random as _r

from .entity import Entity, T_CORPSE, T_CRAWLER, T_NPC, T_MONSTER
from ..content.data.monster_salvage import template_for, is_authored  # noqa: F401


# ── Public result types ──────────────────────────────────────────────────

@dataclass
class ButcherResult:
    ok: bool = False
    materials: Dict[str, int] = field(default_factory=dict)
    trophy_item_key: Optional[str] = None
    time_min: int = 0
    noise: int = 0
    title_grants: List[str] = field(default_factory=list)
    audience_tag: Optional[str] = None
    desecration_tag: Optional[str] = None
    message: str = ""


@dataclass
class EatResult:
    ok: bool = False
    hp_delta: int = 0
    status_applied: Optional[str] = None
    audience_tag: Optional[str] = None
    cannibal_tag: Optional[str] = None
    message: str = ""


# ── Death → corpse transformation ────────────────────────────────────────

CORPSE_AFFORDANCES = ["inspect", "salvage", "eat_corpse", "search"]


def transform_to_corpse(world, entity, *, killer=None) -> Optional[Entity]:
    """Convert a freshly-dead living entity into a corpse (in place).

    Idempotent: calling twice is a no-op. Safe to call even if the
    entity is already a corpse or wasn't of a transformable type.

    Returns the same entity (now mutated), or None if no transform
    happened.
    """
    if entity is None:
        return None
    # Already corpsed.
    if entity.entity_type == T_CORPSE:
        return entity
    # Only living types transform — objects / hazards don't leave corpses.
    if entity.entity_type not in (T_MONSTER, T_CRAWLER, T_NPC):
        return None

    monster_key = entity.key or ""
    tpl = template_for(monster_key)
    original_type = entity.entity_type
    original_name = entity.fallback_name or entity.key or "ciało"
    # Preserve enough context that handlers + LLM enrichment can reach
    # back to the living form's data.
    st = entity.state or {}
    st["dead"]            = True
    st["butchered"]       = False
    st["eaten_uses"]      = 0       # eat is one-shot for now but the field
                                    # is plural so multi-bite is possible
    st["original_type"]   = original_type
    st["original_key"]    = monster_key
    st["original_name"]   = original_name
    st["lore_id"]         = tpl.get("lore_id", "corpse_default")
    st["decay_min_remaining"] = int(tpl.get("decay_minutes", 240))
    st["smell_budget"]    = int(tpl.get("smell_budget", 1))
    # Stash the killer reference (for P31 vendetta + sponsor attribution).
    # `killer` may be the player Character (no entity_id), another Entity,
    # or None. We normalize to a stable string so save/load survives.
    if killer is not None:
        if hasattr(killer, "entity_id"):
            st["killed_by"] = int(killer.entity_id)
        elif hasattr(killer, "name") and getattr(killer, "name", None):
            st["killed_by"] = f"player:{killer.name}"
        else:
            st["killed_by"] = "player"
    # P29.31 — last words. A Polish quip tied to the monster's tags
    # gets stashed so inspect_corpse can surface it. Players who
    # read the dead remember the kill.
    st["last_words"] = _pick_last_words(entity, monster_key)
    entity.state = st

    # Visible mutations.
    entity.entity_type = T_CORPSE
    entity.hp = 0
    entity.conditions = []
    entity.fallback_name = tpl.get("name_pl") or f"ciało ({original_name})"
    # We keep the original name_key blank so display_name falls back to
    # the corpse-flavored fallback_name above. Authors can later add
    # explicit corpse i18n keys via tpl extension.
    entity.name_key = ""
    # Description: prefer template lore; otherwise leave whatever the
    # living entity had (still better than nothing).
    if tpl.get("lore"):
        entity.fallback_desc = tpl["lore"]
        entity.desc_key = ""
    # Tags: keep the originals (sponsors / responder / etc still matter
    # for tag-bus weighting) and add corpse-specific ones.
    tags = list(entity.tags or [])
    for new_tag in ("corpse", "organic"):
        if new_tag not in tags:
            tags.append(new_tag)
    entity.tags = tags
    # P29.57a — DCC canon: trup bossa = wyjście z piętra otwarte.
    # Niezależnie od ścieżki śmierci (gracz, faction crossfire, własna
    # pułapka, hazard, środowisko, sponsor-wars). Wcześniej hook żył
    # tylko w Game's player-kill path → boss zabity inaczej = floor
    # zablokowane. Przeniesienie tutaj realizuje wzorzec z DCC:
    # "Wszystkie bossy zostawiają za sobą trwały łup i ich trupy
    # zostają w Lochu" — exit unlock to KOLEKTYWNY skutek śmierci,
    # nie nagroda za zabicie. Achievement + Boss Box wciąż siedzi
    # w Game's path (DCC: "tylko zabijający dostają skrzynkę").
    # set.add() idempotent więc dwa wywołania nie psują niczego.
    try:
        if "floor_boss" in tags or "final_boss" in tags:
            if world is not None and getattr(world, "current_floor",
                                             None) is not None:
                world.current_floor.exits_unlocked.add("boss_defeated")
    except (AttributeError, KeyError):
        pass
    # Affordances flip to the corpse set. Some monsters had `talk` etc.
    # which obviously no longer apply.
    entity.affordances = list(CORPSE_AFFORDANCES)
    # Corpses are not portable by default (you can't pick up a body —
    # P26b will add a `drag` affordance if we want that).
    entity.portable = False
    # Stays visible + discovered (player just watched it die).
    entity.visible = True
    entity.discovered = True
    return entity


# ── Inspect lore ────────────────────────────────────────────────────────

def inspect_corpse(world, corpse: Entity) -> str:
    """Return the lore string for an inspected corpse. Pure read.

    P29.31 — if state['last_words'] was set on death, append it to
    the lore so the player who inspects gets a kill-flavored quip.
    """
    if corpse is None:
        return ""
    if corpse.entity_type != T_CORPSE:
        return corpse.fallback_desc or ""
    key = (corpse.state or {}).get("original_key", "")
    tpl = template_for(key)
    base = tpl.get("lore") or corpse.fallback_desc or ""
    last_words = (corpse.state or {}).get("last_words", "")
    if last_words:
        # Two-line composite: lore + "Ostatnie słowa: ..."
        return f"{base}\n  Ostatnie słowa: {last_words}".strip()
    return base


# ── Butcher ─────────────────────────────────────────────────────────────

def butcher(world, corpse: Entity, character,
            *, rng: Optional[_r.Random] = None) -> ButcherResult:
    """Extract materials from a corpse. Mutates character.materials and
    marks state.butchered = True. Does NOT advance time or write to
    the log — caller does that. Audience/title tags are RETURNED in the
    result for the caller to dispatch via the tag bus.

    Tool bonus: if the character's wielded main weapon has any tag in
    the template's `preferred_tool_tags`, every material yield gets +1.
    """
    if corpse is None or corpse.entity_type != T_CORPSE:
        return ButcherResult(ok=False, message="To nie zwłoki.")
    st = corpse.state or {}
    if st.get("butchered"):
        return ButcherResult(ok=False,
                             message="To ciało już zostało wypatroszone.")
    rng = rng or _r.Random()

    key = st.get("original_key", "")
    tpl = template_for(key)
    salvage_spec = tpl.get("salvage") or {}
    if not salvage_spec:
        return ButcherResult(ok=False,
                             message="Tu nie ma nic, co warto by wyciąć.")

    # Tool bonus.
    tool_bonus = 0
    preferred = set(tpl.get("preferred_tool_tags") or [])
    if preferred and character is not None:
        wid = getattr(character, "wielded_main_id", None)
        weapon = world.get(wid) if (wid is not None and world is not None) else None
        wtags = set(getattr(weapon, "tags", []) or []) if weapon else set()
        if preferred & wtags:
            tool_bonus = 1

    # Roll each material.
    out_mats: Dict[str, int] = {}
    for mat_key, span in salvage_spec.items():
        if isinstance(span, (tuple, list)) and len(span) == 2:
            lo, hi = int(span[0]), int(span[1])
        else:
            lo = hi = int(span)
        amt = rng.randint(min(lo, hi), max(lo, hi))
        if tool_bonus:
            amt += tool_bonus
        if amt > 0:
            out_mats[mat_key] = out_mats.get(mat_key, 0) + amt

    # Trophy roll.
    trophy_key = None
    drop = tpl.get("trophy_drop")
    if isinstance(drop, (tuple, list)) and len(drop) == 2:
        tk, chance = drop
        if rng.random() < float(chance):
            trophy_key = str(tk)

    # P26a — body-part-aware salvage. If the entity has body_parts
    # tracking (from body-aware combat), each intact zone yields its
    # `butcher_intact_bonus`; each broken zone yields its
    # `butcher_broken_bonus`. This rewards tactical maiming and
    # punishes head-shotting if you wanted the tooth.
    bp_mats = _collect_body_part_yields(corpse)
    for k, v in bp_mats.items():
        out_mats[k] = out_mats.get(k, 0) + v

    # Apply materials to character.
    if character is not None and out_mats:
        materials = getattr(character, "materials", None)
        if materials is None:
            character.materials = {}
            materials = character.materials
        for k, v in out_mats.items():
            materials[k] = materials.get(k, 0) + v

    # Mark butchered. Stripped/depleted are also set so the resolver
    # filter (backlog #6) drops this entity from ambiguous candidate
    # lists too — and ui_nav's existing fully-consumed filter hides
    # it from the action bar. We keep entity_type=corpse so inspect
    # still works.
    st["butchered"] = True
    # P29.49 — counter „kazdy_ma_imie": wszystkie ciała na piętrze
    # wypatroszone. Tracker w character.flags.
    try:
        if character is not None and getattr(character, "flags", None) is not None:
            n = int(character.flags.get("floor_butchered", 0) or 0)
            character.flags["floor_butchered"] = n + 1
    except Exception:
        pass
    st["stripped"]  = True
    corpse.state = st
    # Drop the salvage affordance so the action bar can stop offering
    # Wypatrosz / Zdemontuj — visual cue that this corpse is done
    # (backlog #5 fix).
    corpse.affordances = [a for a in (corpse.affordances or [])
                          if a != "salvage"]

    msg = "Wypatroszone."
    return ButcherResult(
        ok=True,
        materials=out_mats,
        trophy_item_key=trophy_key,
        time_min=int(tpl.get("salvage_time_min", 5)),
        noise=int(tpl.get("salvage_noise", 2)),
        title_grants=list(tpl.get("butcher_title_grants") or []),
        audience_tag=tpl.get("butcher_audience_tag"),
        desecration_tag=tpl.get("desecration_tag"),
        message=msg,
    )


# ── Eat ─────────────────────────────────────────────────────────────────

def eat(world, corpse: Entity, character) -> EatResult:
    """Eat a corpse. One-shot for now (eat consumes the corpse — eaten
    corpses can't be butchered after).

    Risk/reward:
      * hp_delta from template (signed; can heal or hurt)
      * optional status condition applied (poisoned / sick / etc)
      * audience_tag fires through tag bus
      * cannibal_tag fires if original_type=='crawler'
    """
    if corpse is None or corpse.entity_type != T_CORPSE:
        return EatResult(ok=False, message="To nie zwłoki.")
    st = corpse.state or {}
    if st.get("eaten_uses", 0) > 0:
        return EatResult(ok=False, message="Już to zjadłeś.")

    key = st.get("original_key", "")
    tpl = template_for(key)
    if not tpl.get("edible", False):
        # Refuse cleanly — eating an unmarked-edible corpse is a stop
        # rather than a hidden penalty. Players know the score.
        return EatResult(
            ok=False,
            message="Nie powinieneś tego jeść. Zdrowie ważniejsze niż zawartość.",
        )

    hp_delta = int(tpl.get("eat_hp_delta", 0))
    status   = tpl.get("eat_status")
    tag      = tpl.get("eat_audience_tag")
    cannibal = (tpl.get("cannibal_tag")
                if st.get("original_type") == T_CRAWLER else None)

    # Apply HP delta.
    if character is not None and hp_delta != 0:
        ch_hp = getattr(character, "hp", 0)
        ch_max = getattr(character, "max_hp", 0) or ch_hp
        new_hp = max(0, min(ch_max, ch_hp + hp_delta))
        character.hp = new_hp

    # Status condition (light-touch — we don't tick clocks here; combat
    # module would for combat-time statuses. Out of combat we just
    # append the condition string; consequences module already reads
    # character.conditions broadly).
    if status and character is not None:
        conds = getattr(character, "conditions", None)
        if conds is None:
            character.conditions = []
            conds = character.conditions
        if status not in conds:
            conds.append(status)

    # Mark eaten + butchered (eating consumes the body wholesale).
    st["eaten_uses"]   = st.get("eaten_uses", 0) + 1
    st["butchered"]    = True
    st["stripped"]     = True
    corpse.state = st
    corpse.affordances = [a for a in (corpse.affordances or [])
                          if a not in ("salvage", "eat_corpse")]

    return EatResult(
        ok=True,
        hp_delta=hp_delta,
        status_applied=status,
        audience_tag=tag,
        cannibal_tag=cannibal,
        message="Zjedzone.",
    )


# ── Helpers for tests / introspection ───────────────────────────────────

def _collect_body_part_yields(corpse) -> Dict[str, int]:
    """P26a — pull body-part-driven salvage from the corpse's
    `body_parts` map. Falls back to {} for entities that never had
    body-aware combat (no zones tracked)."""
    out: Dict[str, int] = {}
    bp = getattr(corpse, "body_parts", None) or {}
    if not bp:
        return out
    try:
        from ..content.data.body_plans import plan_for_entity
    except Exception:
        return out
    plan = plan_for_entity(corpse)
    for zone_key, zone_state in bp.items():
        props = plan.get(zone_key) or {}
        broken = bool(zone_state.get("broken"))
        yields_key = "butcher_broken_bonus" if broken else "butcher_intact_bonus"
        for entry in (props.get(yields_key) or []):
            if isinstance(entry, (tuple, list)) and len(entry) == 2:
                mk, qty = entry
                out[str(mk)] = out.get(str(mk), 0) + int(qty)
    return out


def is_corpse(entity) -> bool:
    return entity is not None and entity.entity_type == T_CORPSE


def is_edible(entity) -> bool:
    if not is_corpse(entity):
        return False
    key = (entity.state or {}).get("original_key", "")
    return bool(template_for(key).get("edible", False))


# ── P29.30 — Corpse decay tick ──────────────────────────────────────────

def tick_decay(world, minutes: int) -> None:
    """Decrement `decay_min_remaining` on every corpse in every room
    by `minutes`. When a corpse's clock hits 0:
      * become "decomposed" — mutate fallback_name to add "(zgniłe)"
      * clear the `salvageable` / `butcher` affordances so it can't
        be harvested anymore
      * smell_budget triggers a light log line on the room enter
        (consumed by display_first_enter / display_look in the
        future; for now we just mark the state).
    Called from engine.time_system.advance() per minute-budget.
    """
    if world is None or minutes <= 0:
        return
    floor = getattr(world, "current_floor", None)
    if floor is None:
        return
    rooms = getattr(floor, "rooms", None)
    if not rooms:
        return
    drop = int(minutes)
    for room in rooms.values():
        for ent in (getattr(room, "entities", None) or []):
            if not is_corpse(ent):
                continue
            st = ent.state or {}
            remaining = int(st.get("decay_min_remaining", 0) or 0)
            if remaining <= 0:
                continue
            new = max(0, remaining - drop)
            st["decay_min_remaining"] = new
            if new == 0 and not st.get("decomposed"):
                st["decomposed"] = True
                # Strip salvage/butcher affordances — flesh is too far
                # gone to harvest anything useful.
                ent.affordances = [a for a in (ent.affordances or [])
                                   if a not in ("salvage", "butcher")]
                # Tag the entity so visibility / display can change.
                if "decomposed" not in (ent.tags or []):
                    ent.tags = list(ent.tags or []) + ["decomposed"]
            ent.state = st


# ── P29.31 — Corpse "last words" picker ─────────────────────────────────

# Tag → list of Polish quips. The picker selects by first matching tag.
_LAST_WORDS_BY_TAG = {
    "boss": (
        "„…to nie ja… to producent…”",
        "„Drugi sezon… miałem być w drugim sezonie…”",
        "„Brawa… chociaż dla… brawa…”",
    ),
    "humanoid": (
        "„Niech to ktoś nakręci.”",
        "„Powiedz mojej matce, że…”",
        "„Kanał 7… płaci wam… na pewno…”",
    ),
    "sponsor_hunter": (
        "„Sponsor… nie zapomni…”",
        "„Spisałem cię w raporcie. Już za późno.”",
    ),
    "cult": (
        "„Cykl… się… domknie…”",
        "„Wszystko wraca do obwodu, nawet ja.”",
    ),
    "machine": (
        "(z głośnika: „Błąd 547 — kończę pracę.”)",
        "(diody migają w nieregularnym rytmie i gasną.)",
    ),
    "fungal": (
        "(grzybnia jeszcze chwilę pulsuje — bezgłośnie.)",
        "(zarodniki opadają na ciebie. Każdy z nich coś pamięta.)",
    ),
    "beast": (
        "(charczy. Patrzy. Zamyka oczy.)",
        "(machinalnie ślini się ostatni raz.)",
    ),
}

# Generic fallback when no tag matches.
_LAST_WORDS_FALLBACK = (
    "(jeszcze przez chwilę porusza ustami — nic nie wychodzi.)",
    "(coś szepcze, ale niewyraźnie.)",
    "(spojrzenie. Cisza. Koniec.)",
)


def _pick_last_words(entity, monster_key: str) -> str:
    """Pick a Polish last-words line for a freshly-killed monster.
    Routes by tag priority: boss > sponsor_hunter > cult > machine >
    fungal > humanoid > beast > generic.
    """
    import random as _r
    tags = set(entity.tags or [])
    priority = ("boss", "floor_boss", "final_boss", "sponsor_hunter",
                "cult", "machine", "drone", "fungal", "humanoid", "beast")
    for tag in priority:
        if tag in tags:
            pool = _LAST_WORDS_BY_TAG.get(tag) or \
                   _LAST_WORDS_BY_TAG.get("humanoid", ())
            if pool:
                return _r.choice(pool)
    return _r.choice(_LAST_WORDS_FALLBACK)
