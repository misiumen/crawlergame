"""P29.5 — fog-of-war / scout layer for entities.

The player must actively `sprawdź X` to learn what something is.
No auto-promote, no time-based reveal. State machine:

    unknown    — sylwetka tylko: "coś dużego", "postać w mundurze",
                 "urządzenie". Inferred from tags.
    seen       — display_name + HP bar (no numbers / no stats).
                 Reached via first `sprawdź X` (turn-costed).
    inspected  — full card (HP/AC/dmg/threat/resists/sponsor interest).
                 Reached via second `sprawdź X` OR via landing a hit
                 in combat (you learn the numbers from combat math).

Cross-room persistence: per-entity (entity_id) survives room changes.
Cross-floor: `world.known_entity_keys` remembers entity KEYS — future
spawns of the same `key` arrive as `seen` instead of `unknown`. In
practice DCC floors should differ enough that this rarely matters,
but the flag exists for the edge cases.
"""
from __future__ import annotations
from typing import Optional


STATE_UNKNOWN   = "unknown"
STATE_SEEN      = "seen"
STATE_INSPECTED = "inspected"


# ── State queries ────────────────────────────────────────────────────────

def get_state(ent) -> str:
    """Return the entity's visibility_state, defaulting to unknown."""
    if ent is None:
        return STATE_UNKNOWN
    return getattr(ent, "visibility_state", None) or STATE_UNKNOWN


def is_unknown(ent) -> bool:
    return get_state(ent) == STATE_UNKNOWN


def is_seen_or_better(ent) -> bool:
    return get_state(ent) in (STATE_SEEN, STATE_INSPECTED)


def is_inspected(ent) -> bool:
    return get_state(ent) == STATE_INSPECTED


# ── Transitions ──────────────────────────────────────────────────────────

def mark_seen(ent) -> bool:
    """Promote unknown → seen. No-op if already seen+. Returns True
    if a transition happened."""
    if ent is None:
        return False
    cur = get_state(ent)
    if cur == STATE_UNKNOWN:
        ent.visibility_state = STATE_SEEN
        return True
    return False


def mark_inspected(world, ent) -> bool:
    """Promote any state → inspected. Records ent.key in
    world.known_entity_keys so future spawns of the same key come
    in already-seen. Returns True if a transition happened."""
    if ent is None:
        return False
    cur = get_state(ent)
    ent.visibility_state = STATE_INSPECTED
    # Remember the key for future encounters.
    if world is not None and ent.key:
        keys = getattr(world, "known_entity_keys", None)
        if keys is None:
            world.known_entity_keys = []
            keys = world.known_entity_keys
        if ent.key not in keys:
            keys.append(ent.key)
    return cur != STATE_INSPECTED


def respect_known_key_on_spawn(world, ent) -> None:
    """Called by the floor generator when spawning entities. If the
    player has previously inspected another entity with the same
    `key`, this fresh spawn starts as `seen` (recognition) instead
    of `unknown`.

    P29.39 — dorzucone: TRYWIALNE obiekty (codzienna sprzęt, meble,
    skrzynki, automaty) startują jako `seen` z automatu. User słusznie
    zauważył że marnowanie dwóch akcji `sprawdź` na ujawnienie że
    „skrzynia to skrzynia" jest bezsensownym bloat'em. Fog-of-war
    zostaje dla rzeczy podejrzanych: trap / hazard / hidden /
    sponsor_secret / disguised / puzzle / monster / npc.
    """
    if ent is None or world is None:
        return
    # Trivial promotion (działa nawet bez `ent.key`).
    if get_state(ent) == STATE_UNKNOWN and _is_trivial_entity(ent):
        ent.visibility_state = STATE_SEEN
        return
    if not ent.key:
        return
    keys = getattr(world, "known_entity_keys", None) or []
    if ent.key in keys:
        if get_state(ent) == STATE_UNKNOWN:
            ent.visibility_state = STATE_SEEN


# Tagi, które oznaczają coś co MA być przykryte fog-of-war'em. Jeśli
# entity ma którykolwiek z tych tagów, NIE jest „trywialna" — gracz
# musi ją sprawdzić by ujawnić nazwę.
_NON_TRIVIAL_TAGS = frozenset({
    "trap", "hazard", "hidden", "sponsor_secret", "disguised",
    "puzzle", "monster", "npc", "humanoid", "crawler", "drone",
    "undead", "ghost", "beast", "boss", "miniboss",
    "corpse",        # zwłoki są nietypowe — gracz nie wie kto leży
    "sponsor_owned", # podejrzane: sponsor coś tu schował
})


# Tagi codziennego sprzętu — automatyczne `seen`.
_TRIVIAL_TAGS = frozenset({
    "container", "furniture", "decoration", "environment", "fixture",
    "consumable", "food", "tool", "medical", "junk", "art",
    "vending_loot", "salvageable", "metal", "wood", "glass",
    "electrical", "plastic", "fabric",
})


def _is_trivial_entity(ent) -> bool:
    """True jeśli entity jest „codzienna" — meble, skrzynki, automaty,
    rzeczy w plecaku. Te promujemy do `seen` od razu, żeby fog-of-war
    nie zżerał dwóch akcji na rzeczy oczywiste."""
    if ent is None:
        return False
    tags = set(getattr(ent, "tags", None) or [])
    if tags & _NON_TRIVIAL_TAGS:
        return False
    return bool(tags & _TRIVIAL_TAGS)


# ── Display helpers ──────────────────────────────────────────────────────

# Polish vague descriptors keyed by tags the entity might carry. Order
# matters — earlier matches win (most specific first).
_SHAPE_BY_TAG = (
    ("humanoid",     "postać"),
    ("crawler",      "ktoś w stroju zawodnika"),
    ("npc",          "ktoś"),
    ("machine",      "urządzenie"),
    ("drone",        "drono"),
    ("undead",       "coś, co powinno leżeć"),
    ("ghost",        "półprzezroczysta sylwetka"),
    ("beast",        "zwierzę"),
    ("monster",      "kształt"),
    ("trap",         "podejrzany obiekt"),
    ("hazard",       "niebezpieczna struktura"),
    ("corpse",       "ciało"),
    ("container",    "skrzynia"),
    ("interface",    "panel"),
    ("terminal",     "panel"),
    ("furniture",    "mebel"),
    ("environment",  "obiekt"),
    ("item",         "rzecz"),
)


def shape_for_unknown(ent) -> str:
    """Return a Polish vague descriptor based on ent.tags. Used when
    state == unknown so the player sees 'coś' instead of the real
    name."""
    if ent is None:
        return "coś"
    tags = ent.tags or []
    for tag, label in _SHAPE_BY_TAG:
        if tag in tags:
            return label
    # Type-based fallback if no tag matched.
    etype = getattr(ent, "entity_type", "")
    return {
        "monster":  "kształt",
        "crawler":  "ktoś",
        "npc":      "ktoś",
        "item":     "rzecz",
        "object":   "obiekt",
        "hazard":   "coś niebezpiecznego",
        "terminal": "panel",
        "service":  "stanowisko",
    }.get(etype, "coś")


def display_name_for_player(ent) -> str:
    """Returns the entity's name as the player perceives it:
      * unknown   → vague shape
      * seen/inspected → real display_name()
    """
    if ent is None:
        return ""
    if is_unknown(ent):
        return shape_for_unknown(ent)
    try:
        return ent.display_name()
    except Exception:
        return ent.fallback_name or ent.key or "coś"


# ── Inspect block builder (used by `sprawdź X` handler) ──────────────────

def build_inspect_block(world, ent) -> list:
    """Produce the rich `sprawdź` output for an entity. Returns a list
    of log lines. Content depends on the entity type (monster vs item
    vs corpse vs terminal vs npc).
    """
    if ent is None:
        return ["Nic tu nie ma."]
    lines: list = []
    etype = getattr(ent, "entity_type", "")
    name = ent.display_name()
    sep = "─" * 36
    lines.append(sep)
    lines.append(name)

    # P29.39 — surowe tagi (container, wood, salvageable) były debug
    # info wystawionym graczowi. Zamiast nich — krótka linia
    # „Możesz spróbować:" z polskimi etykietami afordansów. Daje
    # konkretną podpowiedź zamiast korpo-metadanych.

    # ── Type-specific blocks
    if etype == "monster":
        hp = int(getattr(ent, "hp", 0))
        max_hp = int(getattr(ent, "max_hp", 0))
        ac = int(getattr(ent, "ac", 10))
        dd = getattr(ent, "damage_dice", "1d4")
        dt = getattr(ent, "damage_type", "physical")
        ab = int(getattr(ent, "attack_bonus", 0))
        thr = int(getattr(ent, "threat_level", 0) or 0)
        try:
            from . import threat as _thr
            thr_label = _thr.threat_label(thr)
        except Exception:
            thr_label = ("spokojny", "wyczulony", "czujny", "wściekły")[
                min(3, max(0, thr))]
        lines.append(f"HP {hp}/{max_hp}   AC {ac}   threat: {thr_label}")
        lines.append(f"Atak: {dd}+{ab} ({dt})")
        if ent.resists:
            lines.append("Odporny:  " + ", ".join(ent.resists))
        if ent.vulnerable_to:
            lines.append("Słaby na: " + ", ".join(ent.vulnerable_to))
        if ent.immune_to:
            lines.append("Niewrażliwy: " + ", ".join(ent.immune_to))
        # Zone status if body parts already initialized
        bp = ent.body_parts or {}
        if bp:
            zones_broken = [z for z, d in bp.items() if d.get("broken")]
            if zones_broken:
                lines.append("Złamane strefy: " + ", ".join(zones_broken))
        # Sponsor interest hint
        sponsor_hint = _sponsor_interest_for_tags(world, ent.tags or [])
        if sponsor_hint:
            lines.append(sponsor_hint)

    elif etype == "item":
        # Wearable / weapon / consumable details
        state = ent.state or {}
        # P29.43 — klasa (rarity) itemu w nagłówku, jeśli niepospolita.
        try:
            from . import rarity as _rar
            r = _rar.entity_rarity(ent)
            if r != _rar.RARITY_COMMON:
                lines.append(f"Klasa: {_rar.rarity_pl(r)}")
        except Exception:
            pass
        ac_bonus = state.get("ac_bonus", 0)
        if ac_bonus:
            lines.append(f"+{ac_bonus} AC gdy założony")
        resists = state.get("equip_resists") or []
        if resists:
            lines.append("Daje odporność na: " + ", ".join(resists))
        # Slot detect from tags
        slot_tags = [t for t in (ent.tags or [])
                     if t.startswith("slot:")]
        if slot_tags:
            slot = slot_tags[0].split(":", 1)[1]
            lines.append(f"Slot: {slot}")
        if "weapon" in (ent.tags or []):
            dd = getattr(ent, "damage_dice", None)
            if dd:
                lines.append(f"Broń: {dd}")
        if ent.fallback_desc:
            lines.append(ent.fallback_desc)

    elif etype in ("crawler", "npc"):
        rel = world.character.relationships.get(str(ent.entity_id), 0) \
            if world and world.character else 0
        rel_label = ("wrogi" if rel < -1
                     else "nieufny" if rel < 0
                     else "neutralny" if rel == 0
                     else "życzliwy" if rel < 3
                     else "przyjazny")
        lines.append(f"Relacja: {rel_label} ({rel:+d})")
        if ent.fallback_desc:
            lines.append(ent.fallback_desc)

    elif etype == "terminal":
        state = ent.state or {}
        if state.get("hacked"):
            lines.append("Stan: już zhakowany")
        else:
            lines.append("Dostęp: INT vs TT 14 (hack)")
            lines.append("Nagroda: ~8 kr + ew. odblokowanie sąsiednich drzwi")

    elif etype in ("object", "hazard", "service"):
        # Generic — show desc + key state markers
        if ent.fallback_desc:
            lines.append(ent.fallback_desc)
        state = ent.state or {}
        if state.get("stripped"):
            lines.append("Stan: zdemontowany")
        elif state.get("destroyed"):
            lines.append("Stan: zniszczony")
        elif state.get("locked"):
            lines.append("Stan: zamknięte")

    # P29.39 — krótka linia z polskimi etykietami afordansów, jako
    # konkretna podpowiedź zamiast surowych tagów. Pokazujemy max 4
    # — żeby nie zalać gracza listą.
    hints = _affordance_hints_pl(ent)
    if hints:
        lines.append("Możesz spróbować: " + ", ".join(hints[:4]) + ".")

    lines.append(sep)
    return lines


# Mapowanie afordansów na polskie etykiety w trybie podpowiedzi
# („wyłamać", „przeszukać") — INFINITIV, bo to lista możliwości, nie
# rozkaz. UI dispatcher i tak zwykle przepisuje na konkretną komendę
# z imperatywem.
_AFFORDANCE_HINT_PL = {
    "inspect":       "przyjrzeć się dokładniej",
    "search":        "przeszukać",
    "loot":          "zgarnąć co tam jest",
    "open":          "otworzyć",
    "close":         "zamknąć",
    "force":         "wyłamać",
    "lockpick":      "otworzyć wytrychem",
    "hack":          "podpiąć się pod elektronikę",
    "break":         "rozbić",
    "attack":        "zaatakować",
    "salvage":       "rozebrać na części",
    "strip":         "obedrzeć z osprzętu",
    "harvest":       "wyciągnąć surowiec",
    "use":           "użyć",
    "throw_at":      "rzucić w coś",
    "push_into":     "zepchnąć",
    "deploy":        "rozstawić",
    "talk":          "pogadać",
    "intimidate":    "zastraszyć",
    "bribe":         "przekupić",
    "lure":          "zwabić",
    "butcher":       "zarżnąć i wyciąć mięso",
}


def _affordance_hints_pl(ent) -> list:
    """Zwraca listę polskich opisów afordansów dla entity, w stylu
    podpowiedzi. Filtrujemy `inspect` (skoro gracz już to robi)."""
    if ent is None:
        return []
    affs = list(getattr(ent, "affordances", None) or [])
    out = []
    for a in affs:
        if a == "inspect":
            continue
        pl = _AFFORDANCE_HINT_PL.get(a)
        if pl and pl not in out:
            out.append(pl)
    return out


def _sponsor_interest_for_tags(world, entity_tags: list) -> str:
    """Look at every sponsor's likes_tags; if any overlap with the
    entity's tags, mention the sponsor. Returns "" when no overlap."""
    if world is None:
        return ""
    try:
        from ..content.data.sponsors import SPONSORS
    except Exception:
        return ""
    matches = []
    et = set(entity_tags or [])
    for skey, sdata in SPONSORS.items():
        likes = set(sdata.get("likes_tags") or [])
        if likes & et:
            name = sdata.get("name_fallback", skey)
            matches.append(name.split()[0])   # short form
        if len(matches) >= 2:
            break
    if matches:
        return "Sponsor:  " + " / ".join(matches) + " zwróciliby uwagę"
    return ""
