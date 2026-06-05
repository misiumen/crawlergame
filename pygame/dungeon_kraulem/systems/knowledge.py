"""Knowledge model (Prompt 07b).

A lightweight store of clues, facts, routes, and passwords/access codes
the player has collected. Information must matter mechanically — every
field exposed here is referenced from `validation.py`, `game.py`, or
`memetics.py` to widen or gate resolution paths.

Storage rule:
    Knowledge lives on the `WorldState` object as simple `dict[str, dict]`
    fields, NOT as dataclasses. That keeps save/load trivial (each entry is
    a plain serializable dict) and tolerates `from_dict` calls on old saves
    that lack the new keys.

Public helpers:
    add_known_clue(world, clue)
    add_known_fact(world, fact)
    add_known_route(world, route)
    add_known_password(world, password)
    has_known_clue(world, key_or_tag)        — tag OR key match
    has_known_fact(world, key_or_tag)
    has_unlocked_path(world, path_key)
    get_known_tags(world)                    — union of all reveals_tags + tags
    get_enabled_resolution_paths(world)      — set of path keys unlocked
    summarize_for_journal(world)             — rows for the UI command
    bootstrap(world)                         — make sure all dict fields exist

`Character.flags["known_clues"]` and `["known_facts"]` already existed as
plain lists of string keys; this module mirrors that behavior and stays
backward-compatible. The structured dict fields on WorldState are the
new home for *full* clue payloads.
"""
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Set


# ── Schema helpers ───────────────────────────────────────────────────────────

def _ensure_dict(world, name: str) -> Dict[str, Dict[str, Any]]:
    """Get-or-create a dict[name] field on world; return the dict reference."""
    cur = getattr(world, name, None)
    if cur is None:
        cur = {}
        try:
            setattr(world, name, cur)
        except Exception:
            return {}
    return cur


def bootstrap(world) -> None:
    """Ensure all knowledge fields exist on `world` and on
    `world.character.flags`. Called once on save load to upgrade old saves."""
    if world is None:
        return
    for name in ("known_clues", "known_facts", "known_routes",
                 "known_passwords"):
        if getattr(world, name, None) is None:
            try:
                setattr(world, name, {})
            except Exception:
                pass
    if getattr(world, "unlocked_paths", None) is None:
        try:
            world.unlocked_paths = []
        except Exception:
            pass
    ch = getattr(world, "character", None)
    if ch is not None and ch.flags is not None:
        ch.flags.setdefault("known_clues", [])
        ch.flags.setdefault("known_facts", [])


# ── Clues ────────────────────────────────────────────────────────────────────

_CLUE_FIELDS = ("key", "title", "description", "tags", "source",
                "reliability", "floor_number", "created_time",
                "reveals_tags", "enables_paths", "related_room_ids",
                "related_entity_ids", "related_objective_keys", "used")


def add_known_clue(world, clue: Dict[str, Any]) -> bool:
    """Add a clue dict. Returns True if newly added. Idempotent by key.

    Accepts either a full structured clue dict or the bare template dict
    from `data/clue_templates.py`. Missing fields are filled with safe
    defaults.
    """
    if world is None or not clue:
        return False
    bootstrap(world)
    key = clue.get("key") or ""
    if not key:
        return False
    store = _ensure_dict(world, "known_clues")
    if key in store:
        return False
    # Normalize.
    entry = {f: clue.get(f) for f in _CLUE_FIELDS}
    entry["key"] = key
    entry["tags"] = list(clue.get("tags") or [])
    entry["reveals_tags"] = list(clue.get("reveals_tags")
                                 or clue.get("reveals") or [])
    entry["enables_paths"] = list(clue.get("enables_paths") or [])
    entry["related_room_ids"] = list(clue.get("related_room_ids") or [])
    entry["related_entity_ids"] = list(clue.get("related_entity_ids") or [])
    entry["related_objective_keys"] = list(clue.get("related_objective_keys") or [])
    entry["source"] = clue.get("source") or ""
    entry["reliability"] = float(clue.get("reliability", clue.get("truth", 1.0)))
    if entry["floor_number"] is None:
        entry["floor_number"] = getattr(world, "floor_number", 1)
    if entry["created_time"] is None:
        f = getattr(world, "current_floor", None)
        entry["created_time"] = getattr(f, "current_minute", 0) if f else 0
    entry["used"] = bool(clue.get("used", False))
    if entry["title"] is None:
        entry["title"] = clue.get("title_pl") or clue.get("title_en") or key
    if entry["description"] is None:
        entry["description"] = (clue.get("text") or clue.get("text_pl")
                                or clue.get("description") or "")
    store[key] = entry

    # Mirror to Character.flags["known_clues"] (legacy string list)
    ch = getattr(world, "character", None)
    if ch is not None and ch.flags is not None:
        kc = ch.flags.setdefault("known_clues", [])
        if key not in kc:
            kc.append(key)
        kf = ch.flags.setdefault("known_facts", [])
        for tag in entry["reveals_tags"]:
            if tag and tag not in kf:
                kf.append(tag)

    # Auto-unlock any paths the clue lists.
    for path in entry["enables_paths"]:
        unlock_path(world, path)
    return True


def has_known_clue(world, key_or_tag: str) -> bool:
    if world is None or not key_or_tag:
        return False
    bootstrap(world)
    store = _ensure_dict(world, "known_clues")
    if key_or_tag in store:
        return True
    for entry in store.values():
        if key_or_tag in (entry.get("tags") or []):
            return True
        if key_or_tag in (entry.get("reveals_tags") or []):
            return True
    # Legacy fallback
    ch = getattr(world, "character", None)
    if ch and ch.flags:
        if key_or_tag in (ch.flags.get("known_clues") or []):
            return True
        if key_or_tag in (ch.flags.get("known_facts") or []):
            return True
    return False


# ── Facts ───────────────────────────────────────────────────────────────────

_FACT_FIELDS = ("key", "text", "tags", "source", "confidence",
                "floor_number", "created_time", "enables_paths")


def add_known_fact(world, fact: Dict[str, Any]) -> bool:
    if world is None or not fact:
        return False
    bootstrap(world)
    key = fact.get("key") or ""
    if not key:
        return False
    store = _ensure_dict(world, "known_facts")
    if key in store:
        return False
    entry = {f: fact.get(f) for f in _FACT_FIELDS}
    entry["key"] = key
    entry["tags"] = list(fact.get("tags") or [])
    entry["enables_paths"] = list(fact.get("enables_paths") or [])
    entry["confidence"] = float(fact.get("confidence", 1.0))
    entry["source"] = fact.get("source") or ""
    if entry["floor_number"] is None:
        entry["floor_number"] = getattr(world, "floor_number", 1)
    if entry["created_time"] is None:
        f = getattr(world, "current_floor", None)
        entry["created_time"] = getattr(f, "current_minute", 0) if f else 0
    entry["text"] = fact.get("text") or ""
    store[key] = entry

    ch = getattr(world, "character", None)
    if ch is not None and ch.flags is not None:
        kf = ch.flags.setdefault("known_facts", [])
        if key not in kf:
            kf.append(key)
        for tg in entry["tags"]:
            if tg and tg not in kf:
                kf.append(tg)
    for path in entry["enables_paths"]:
        unlock_path(world, path)
    return True


def has_known_fact(world, key_or_tag: str) -> bool:
    if world is None or not key_or_tag:
        return False
    bootstrap(world)
    store = _ensure_dict(world, "known_facts")
    if key_or_tag in store:
        return True
    for e in store.values():
        if key_or_tag in (e.get("tags") or []):
            return True
    ch = getattr(world, "character", None)
    if ch and ch.flags:
        if key_or_tag in (ch.flags.get("known_facts") or []):
            return True
    return False


# ── Routes ──────────────────────────────────────────────────────────────────

_ROUTE_FIELDS = ("key", "from_room_id", "to_room_id", "route_type",
                 "known", "locked", "requirements", "source")


def add_known_route(world, route: Dict[str, Any]) -> bool:
    if world is None or not route:
        return False
    bootstrap(world)
    key = route.get("key") or ""
    if not key:
        return False
    store = _ensure_dict(world, "known_routes")
    if key in store:
        return False
    entry = {f: route.get(f) for f in _ROUTE_FIELDS}
    entry["key"] = key
    entry["known"] = bool(route.get("known", True))
    entry["locked"] = bool(route.get("locked", False))
    entry["requirements"] = list(route.get("requirements") or [])
    store[key] = entry
    return True


# ── Passwords / access codes ────────────────────────────────────────────────

_PWD_FIELDS = ("key", "label", "code_text", "tags", "opens",
               "source", "used")


def add_known_password(world, password: Dict[str, Any]) -> bool:
    if world is None or not password:
        return False
    bootstrap(world)
    key = password.get("key") or ""
    if not key:
        return False
    store = _ensure_dict(world, "known_passwords")
    if key in store:
        return False
    entry = {f: password.get(f) for f in _PWD_FIELDS}
    entry["key"] = key
    entry["tags"] = list(password.get("tags") or [])
    entry["opens"] = list(password.get("opens") or [])
    entry["used"] = bool(password.get("used", False))
    store[key] = entry
    # Passwords also unlock the generic 'use_password' path.
    unlock_path(world, "use_password")
    return True


def has_password_for(world, opens_tag: str) -> bool:
    if world is None or not opens_tag:
        return False
    bootstrap(world)
    store = _ensure_dict(world, "known_passwords")
    for entry in store.values():
        if opens_tag in (entry.get("opens") or []):
            return True
        if opens_tag in (entry.get("tags") or []):
            return True
    return False


# ── Unlocked resolution paths ───────────────────────────────────────────────

def unlock_path(world, path_key: str) -> bool:
    """Add a path key to world.unlocked_paths if not already there. Returns
    True if newly unlocked. Path keys are stable strings like
    `use_password`, `exploit_weakness`, `invoke_belief`, `secret_route`."""
    if world is None or not path_key:
        return False
    bootstrap(world)
    paths = getattr(world, "unlocked_paths", None)
    if paths is None:
        return False
    if path_key in paths:
        return False
    paths.append(path_key)
    return True


def has_unlocked_path(world, path_key: str) -> bool:
    if world is None or not path_key:
        return False
    bootstrap(world)
    return path_key in (getattr(world, "unlocked_paths", []) or [])


def get_enabled_resolution_paths(world) -> List[str]:
    if world is None:
        return []
    bootstrap(world)
    out = set(getattr(world, "unlocked_paths", []) or [])
    # Walk known clues / facts for paths they declared
    for entry in _ensure_dict(world, "known_clues").values():
        for p in entry.get("enables_paths") or []:
            out.add(p)
    for entry in _ensure_dict(world, "known_facts").values():
        for p in entry.get("enables_paths") or []:
            out.add(p)
    # Memetic seeds may also enable paths based on their method.
    try:
        from . import memetics
        for s in memetics.all_active(world):
            if s.strength >= 50:
                # Identity attack & logic_exploit gate `invoke_belief`.
                if s.method in ("identity_attack", "logic_exploit",
                                "mythic_comparison", "religious_framing"):
                    out.add("invoke_belief")
    except Exception:
        pass
    return sorted(out)


def get_known_tags(world) -> Set[str]:
    if world is None:
        return set()
    bootstrap(world)
    out: Set[str] = set()
    for entry in _ensure_dict(world, "known_clues").values():
        out.update(entry.get("tags") or [])
        out.update(entry.get("reveals_tags") or [])
    for entry in _ensure_dict(world, "known_facts").values():
        out.update(entry.get("tags") or [])
    # Legacy
    ch = getattr(world, "character", None)
    if ch and ch.flags:
        out.update(ch.flags.get("known_facts") or [])
    return out


# ── Memetic gating ──────────────────────────────────────────────────────────

def matching_belief_for(world, target_tags: Iterable[str],
                        min_strength: int = 40) -> Optional[Any]:
    """Return the strongest active belief seed whose target_tags intersect
    `target_tags`, or None. Used to gate `invoke_belief` validation."""
    if world is None:
        return None
    try:
        from . import memetics
    except Exception:
        return None
    needle = set(target_tags or [])
    if not needle:
        return None
    best = None
    best_strength = min_strength - 1
    for s in memetics.all_active(world):
        if s.strength < min_strength:
            continue
        if needle & set(s.target_tags or []):
            if s.strength > best_strength:
                best = s
                best_strength = s.strength
    return best


# ── Journal summary ─────────────────────────────────────────────────────────

def summarize_for_journal(world) -> List[str]:
    """Return display-ready Polish lines for the `wiedza` command."""
    if world is None:
        return []
    bootstrap(world)
    out: List[str] = []
    clues = _ensure_dict(world, "known_clues")
    facts = _ensure_dict(world, "known_facts")
    routes = _ensure_dict(world, "known_routes")
    pwds = _ensure_dict(world, "known_passwords")
    paths = list(getattr(world, "unlocked_paths", []) or [])

    if clues:
        out.append("Wskazówki:")
        for entry in clues.values():
            title = entry.get("title") or entry.get("key") or "?"
            tags = (entry.get("reveals_tags") or [])[:3]
            tag_s = (" [" + ", ".join(tags) + "]") if tags else ""
            out.append(f"  • {title}{tag_s}")
    if facts:
        out.append("Wiedza:")
        for entry in facts.values():
            txt = entry.get("text") or entry.get("key") or "?"
            out.append(f"  · {txt}")
    if pwds:
        out.append("Hasła i kody:")
        for entry in pwds.values():
            label = entry.get("label") or entry.get("key") or "?"
            code = entry.get("code_text") or ""
            opens = ", ".join(entry.get("opens") or [])
            opens_s = f"  → {opens}" if opens else ""
            code_s = f"  ({code})" if code else ""
            out.append(f"  • {label}{code_s}{opens_s}")
    if routes:
        out.append("Trasy:")
        for entry in routes.values():
            kind = entry.get("route_type") or "?"
            a = entry.get("from_room_id") or "?"
            b = entry.get("to_room_id") or "?"
            out.append(f"  • {a} → {b}  ({kind})")
    if paths:
        out.append("Odblokowane opcje:")
        out.append("  " + ", ".join(paths))
    # Active beliefs (read-only — full detail lives under `idee`)
    try:
        from . import memetics
        seeds = memetics.all_active(world)
        if seeds:
            out.append("Aktywne idee:")
            for s in seeds:
                out.append("  " + memetics.summarize_seed(s, lang="pl"))
    except Exception:
        pass

    if not out:
        out.append("Wiedza: na razie nic konkretnego.")
    return out
