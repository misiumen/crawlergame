"""In-game journal data layer (Prompt 10).

The journal is a tabbed read-only overlay. This module collects journal
entries from world state and exposes a stable shape (`JournalEntry`) the
UI renderer consumes. No new save format, no parallel storage — only
formatting helpers on top of existing world / character / floor data.

Public API:
    TABS                                — tuple of stable tab keys
    tab_label(key, lang="pl")           — localized header
    JournalEntry                        — dataclass shown by the UI
    JournalState                        — current UI selection / scroll
    get_journal_entries(world, tab_key) — list[JournalEntry]
    reliability_label(value, lang)      — Polish/EN bucket name
    summarize_belief(seed, lang)        — short claim + flavor
    format_known_clue(clue, world, lang) — JournalEntry

Design rules:
    * Never expose raw `memetic:<seed_id>:<n>` keys. Always render through
      `memetics.render_rumor_key`.
    * Never reveal "this is false" mechanically — describe with in-world
      labels (Podejrzane / Zniekształcone / Skażone).
    * Tolerate missing systems and old save fields silently — empty
      tabs return an empty list and the UI shows an empty-state line.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lang import t


# ── Tab catalog ────────────────────────────────────────────────────────────

TAB_LOG          = "log"
TAB_MAP          = "map"
TAB_OBJECTIVES   = "objectives"
TAB_KNOWLEDGE    = "knowledge"
TAB_RUMORS       = "rumors"
TAB_BELIEFS      = "beliefs"
TAB_CRAWLERS     = "crawlers"
TAB_INVENTORY    = "inventory"
TAB_MATERIALS    = "materials"
TAB_CRAFTING     = "crafting"
TAB_ACHIEVEMENTS = "achievements"
TAB_SPONSORS     = "sponsors"   # Prompt 18 — sponsor / audience overview
TAB_COMPANIONS   = "companions" # Prompt 19 — Towarzysze (pets + crawler allies)

TABS = (TAB_LOG, TAB_MAP, TAB_OBJECTIVES, TAB_KNOWLEDGE, TAB_RUMORS,
        TAB_BELIEFS, TAB_CRAWLERS, TAB_COMPANIONS, TAB_SPONSORS,
        TAB_INVENTORY, TAB_MATERIALS, TAB_CRAFTING, TAB_ACHIEVEMENTS)

_TAB_LABEL_KEYS = {
    TAB_LOG:          ("journal_tab_log",          "Log"),
    TAB_MAP:          ("journal_tab_map",          "Mapa"),
    TAB_OBJECTIVES:   ("journal_tab_objectives",   "Cele"),
    TAB_KNOWLEDGE:    ("journal_tab_knowledge",    "Wiedza"),
    TAB_RUMORS:       ("journal_tab_rumors",       "Plotki"),
    TAB_BELIEFS:      ("journal_tab_beliefs",      "Mity"),
    TAB_CRAWLERS:     ("journal_tab_crawlers",     "Crawlerzy"),
    TAB_SPONSORS:     ("journal_tab_sponsors",     "Sponsorzy"),
    TAB_COMPANIONS:   ("journal_tab_companions",   "Towarzysze"),
    TAB_INVENTORY:    ("journal_tab_inventory",    "Ekwipunek"),
    TAB_MATERIALS:    ("journal_tab_materials",    "Materiały"),
    TAB_CRAFTING:     ("journal_tab_crafting",     "Crafting"),
    TAB_ACHIEVEMENTS: ("journal_tab_achievements", "Osiągnięcia"),
}


def tab_label(key: str) -> str:
    k, fb = _TAB_LABEL_KEYS.get(key, ("", key))
    return t(k, fallback=fb)


# ── Entry / state model ───────────────────────────────────────────────────

@dataclass
class JournalEntry:
    title: str = ""
    subtitle: str = ""
    body: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = ""          # localized reliability/state label
    detail: str = ""          # extended description for the detail panel
    sort_key: Any = None
    raw_ref: Any = None


@dataclass
class JournalState:
    """Persistent UI state for the journal overlay."""
    open: bool = False
    tab: str = TAB_MAP
    selected_by_tab: Dict[str, int] = field(default_factory=dict)
    scroll_by_tab: Dict[str, int] = field(default_factory=dict)
    # Prompt 11: detail-panel scrolling. Keyed by (tab, selected_idx) so
    # switching entries auto-resets to top instead of leaving the player
    # half-way down the previous entry's text.
    detail_scroll_by: Dict[tuple, int] = field(default_factory=dict)

    def selected(self, tab: Optional[str] = None) -> int:
        return self.selected_by_tab.get(tab or self.tab, 0)

    def set_selected(self, idx: int, tab: Optional[str] = None) -> None:
        tab = tab or self.tab
        old = self.selected_by_tab.get(tab, 0)
        new = max(0, idx)
        self.selected_by_tab[tab] = new
        # Reset detail scroll when selection actually changes.
        if old != new:
            self.detail_scroll_by.pop((tab, old), None)

    def scroll(self, tab: Optional[str] = None) -> int:
        return self.scroll_by_tab.get(tab or self.tab, 0)

    def bump_scroll(self, delta: int, tab: Optional[str] = None) -> None:
        tab = tab or self.tab
        self.scroll_by_tab[tab] = max(0, self.scroll_by_tab.get(tab, 0) + delta)

    def detail_scroll(self, tab: Optional[str] = None) -> int:
        tab = tab or self.tab
        sel = self.selected_by_tab.get(tab, 0)
        return self.detail_scroll_by.get((tab, sel), 0)

    def bump_detail_scroll(self, delta: int, tab: Optional[str] = None) -> None:
        tab = tab or self.tab
        sel = self.selected_by_tab.get(tab, 0)
        cur = self.detail_scroll_by.get((tab, sel), 0)
        self.detail_scroll_by[(tab, sel)] = max(0, cur + delta)

    def reset_detail_scroll(self, tab: Optional[str] = None) -> None:
        tab = tab or self.tab
        sel = self.selected_by_tab.get(tab, 0)
        self.detail_scroll_by[(tab, sel)] = 0


# ── Reliability bucketing ──────────────────────────────────────────────────

# Reliability is read from clue.reliability (0..1). Sub-buckets:
#   ≥ 0.9 → Potwierdzone / Confirmed
#   ≥ 0.7 → Niepewne     / Uncertain
#   ≥ 0.5 → Podejrzane   / Suspicious
#   ≥ 0.3 → Zniekształcone / Distorted
#   <  0.3 → Skażone     / Contaminated
# Special: if the clue carries the `contaminated` tag, force Skażone.
# Memetic-propagated facts (source="memetic_propagation") → Zasłyszane / Hearsay.

_RELIABILITY_LABELS_PL = {
    "confirmed":    "Potwierdzone",
    "uncertain":    "Niepewne",
    "suspicious":   "Podejrzane",
    "distorted":    "Zniekształcone",
    "contaminated": "Skażone",
    "hearsay":      "Zasłyszane",
}
_RELIABILITY_LABELS_EN = {
    "confirmed":    "Confirmed",
    "uncertain":    "Uncertain",
    "suspicious":   "Suspicious",
    "distorted":    "Distorted",
    "contaminated": "Contaminated",
    "hearsay":      "Hearsay",
}


def reliability_bucket(clue: Dict[str, Any]) -> str:
    """Return one of {confirmed, uncertain, suspicious, distorted,
    contaminated, hearsay}."""
    tags = (clue.get("tags") or [])
    if "contaminated" in tags:
        return "contaminated"
    if (clue.get("source") or "") == "memetic_propagation":
        return "hearsay"
    try:
        r = float(clue.get("reliability", 1.0))
    except (TypeError, ValueError):
        r = 1.0
    if r >= 0.9:  return "confirmed"
    if r >= 0.7:  return "uncertain"
    if r >= 0.5:  return "suspicious"
    if r >= 0.3:  return "distorted"
    return "contaminated"


def reliability_label(bucket: str, lang: str = "pl") -> str:
    table = _RELIABILITY_LABELS_PL if lang == "pl" else _RELIABILITY_LABELS_EN
    return table.get(bucket, bucket)


# ── Belief seed formatting ─────────────────────────────────────────────────

def _strength_label(strength: int, lang: str = "pl") -> str:
    s = int(strength or 0)
    if lang == "pl":
        if s <= 25: return "słaby"
        if s <= 50: return "zauważalny"
        if s <= 75: return "narastający"
        return "niepokojąco żywy"
    if s <= 25: return "weak"
    if s <= 50: return "noticeable"
    if s <= 75: return "growing"
    return "uncomfortably alive"


def _distortion_label(distortion: int, lang: str = "pl") -> str:
    d = int(distortion or 0)
    if lang == "pl":
        if d < 20: return "stabilny"
        if d < 50: return "lekko zniekształcony"
        if d < 75: return "mocno przekręcony"
        return "niebezpiecznie samodzielny"
    if d < 20: return "stable"
    if d < 50: return "slightly off"
    if d < 75: return "badly warped"
    return "dangerously its own thing"


def summarize_belief(seed, lang: str = "pl") -> str:
    """One-line summary of a BeliefSeed for journal display."""
    if seed is None:
        return ""
    claim = (seed.core_claim or seed.origin_text or "?").strip()
    return claim[:80] + ("…" if len(claim) > 80 else "")


# ── Clue formatting ────────────────────────────────────────────────────────

def format_known_clue(clue: Dict[str, Any], world=None,
                      lang: str = "pl") -> JournalEntry:
    bucket = reliability_bucket(clue)
    status = reliability_label(bucket, lang)
    title = (clue.get("title") or clue.get("key") or "?").strip()
    body  = (clue.get("description") or "").strip()
    tags  = list(clue.get("reveals_tags") or [])
    src   = (clue.get("source") or "").strip()
    sub_bits = []
    if src and src != "memetic_propagation":
        sub_bits.append(src)
    if bucket != "confirmed":
        sub_bits.append(status.lower())
    subtitle = " · ".join(sub_bits)
    detail_lines = []
    if body:
        detail_lines.append(body)
    if tags:
        detail_lines.append("Tagi: " + ", ".join(tags[:6]))
    return JournalEntry(
        title=title, subtitle=subtitle, body=body, tags=tags,
        status=status, detail="\n".join(detail_lines),
        sort_key=title.lower(), raw_ref=clue,
    )


# ── Tab collectors ─────────────────────────────────────────────────────────

def get_journal_entries(world, tab_key: str) -> List[JournalEntry]:
    """Dispatch to a tab-specific collector. Never raises."""
    try:
        return _COLLECTORS.get(tab_key, _empty)(world)
    except Exception:
        return []


def _empty(world) -> List[JournalEntry]:
    return []


def _collect_log(world) -> List[JournalEntry]:
    log = getattr(world, "log", None) or []
    out: List[JournalEntry] = []
    # Surface the last ~200 entries.
    for s, cat in list(log)[-200:]:
        out.append(JournalEntry(title=str(s), subtitle="", body="",
                                status=str(cat), tags=[cat],
                                sort_key=len(out)))
    return out


def _collect_map(world) -> List[JournalEntry]:
    f = getattr(world, "current_floor", None)
    if f is None:
        return []
    out = []
    for rid in sorted(f.discovered_room_ids or []):
        r = f.rooms.get(rid)
        if r is None: continue
        title = r.display_short_title()
        bits = []
        if rid == f.current_room_id:
            bits.append("aktualne")
        if r.cleared:
            bits.append("oczyszczone")
        if r.safehouse_subtype:
            bits.append("bezpieczne")
        if r.searched_depth and r.searched_depth > 0:
            bits.append("przeszukane")
        if any(ed.get("locked") for ed in (r.exits or {}).values()):
            bits.append("zamknięte wyjście")
        subtitle = " · ".join(bits) or "odwiedzone"
        # Detail: list known exits.
        exit_lines = []
        for label, ed in (r.exits or {}).items():
            if ed.get("hidden"): continue
            target = (f.rooms.get(ed.get("target", "")) if f else None)
            target_name = (target.display_short_title()
                           if target and ed.get("target") in (f.discovered_room_ids or set())
                           else "?")
            lock = "  (zamknięte)" if ed.get("locked") else ""
            exit_lines.append(f"  → {label}: {target_name}{lock}")
        detail = ("Wyjścia:\n" + "\n".join(exit_lines)) if exit_lines else ""
        out.append(JournalEntry(title=title, subtitle=subtitle, detail=detail,
                                tags=list(r.sensory_tags or []),
                                sort_key=(0 if rid == f.current_room_id else 1, title),
                                raw_ref=r))
    return out


def _collect_objectives(world) -> List[JournalEntry]:
    f = getattr(world, "current_floor", None)
    if f is None or not f.objective_key:
        return []
    title = f.objective_title_fallback or f.objective_key
    body = f.objective_description_fallback or ""
    paths = f.objective_solution_paths or []
    unlocked = list(getattr(world, "unlocked_paths", []) or [])
    bits = ["Cel:"]
    if body: bits.append(body)
    if paths:
        bits.append("Możliwe drogi: " + ", ".join(paths))
    if unlocked:
        bits.append("Odblokowane: " + ", ".join(unlocked))
    if f.deadline_minute:
        rem = f.deadline_remaining_minutes()
        d = rem // (24 * 60)
        h = (rem % (24 * 60)) // 60
        bits.append(f"Pozostały czas: {d} dni {h} godz.")
    return [JournalEntry(title=title, subtitle=f"Piętro {f.floor_number}",
                         body="\n".join(bits), detail="\n".join(bits),
                         sort_key=0)]


def _collect_knowledge(world) -> List[JournalEntry]:
    out: List[JournalEntry] = []
    for entry in (getattr(world, "known_clues", None) or {}).values():
        out.append(format_known_clue(entry, world))
    # Passwords next.
    for pw in (getattr(world, "known_passwords", None) or {}).values():
        label = pw.get("label") or pw.get("key") or "?"
        code = pw.get("code_text") or ""
        opens = ", ".join(pw.get("opens") or [])
        out.append(JournalEntry(
            title=label,
            subtitle="hasło / kod" + (f" — pasuje do: {opens}" if opens else ""),
            body=code, status="Potwierdzone",
            detail=f"Kod: {code}\nOtwiera: {opens or '?'}",
            sort_key=("z_pwd", label.lower()),
            raw_ref=pw,
        ))
    # Routes
    for r in (getattr(world, "known_routes", None) or {}).values():
        out.append(JournalEntry(
            title=f"Trasa: {r.get('from_room_id','?')} → {r.get('to_room_id','?')}",
            subtitle=r.get("route_type", ""),
            body="",
            detail=f"Typ: {r.get('route_type','?')}\nZnana: {r.get('known', True)}\n"
                   f"Zamknięta: {r.get('locked', False)}",
            sort_key=("z_route", r.get("key", "")),
            raw_ref=r,
        ))
    return out


def _collect_rumors(world) -> List[JournalEntry]:
    """Render floor.rumors entries through the memetic helper so raw
    `memetic:<seed_id>:<n>` keys never appear."""
    f = getattr(world, "current_floor", None)
    if f is None:
        return []
    out: List[JournalEntry] = []
    try:
        from ..systems import memetics
    except Exception:
        memetics = None
    try:
        from ..content.data.rumor_templates import get_rumor
    except Exception:
        get_rumor = None
    for rk in (f.rumors or [])[-40:]:
        title = ""
        body = ""
        source = ""
        reliability = 1.0
        if rk.startswith("memetic:") and memetics is not None:
            body = memetics.render_rumor_key(world, rk, language="pl") or ""
            title = "Plotka, która krąży"
            source = "memetic_propagation"
            # Pull seed if reachable for an effective reliability + label.
            parts = rk.split(":")
            seed_id = parts[1] if len(parts) >= 2 else ""
            seed = (getattr(world, "belief_seeds", {}) or {}).get(seed_id)
            if seed is not None:
                reliability = (seed.strength or 0) / 100.0
        elif get_rumor is not None:
            r = get_rumor(rk)
            if r is None:
                continue
            body = r.get("text", "")
            title = (r.get("text", "")[:60] + "…") if len(r.get("text", "")) > 60 else r.get("text", "")
            reliability = float(r.get("truth", r.get("reliability", 1.0)))
            source = r.get("category", "")
        if not body:
            continue
        bucket = reliability_bucket({"reliability": reliability,
                                     "source": source})
        out.append(JournalEntry(
            title=(body[:60] + "…") if len(body) > 60 else body,
            subtitle=source if source and source != "memetic_propagation"
                     else ("Powtarzane przez crawlerów" if source == "memetic_propagation"
                           else ""),
            body=body,
            status=reliability_label(bucket, "pl"),
            detail=body, sort_key=len(out),
            raw_ref=rk,
        ))
    return out


def _collect_beliefs(world) -> List[JournalEntry]:
    try:
        from ..systems import memetics
    except Exception:
        return []
    seeds = memetics.all_active(world) if world is not None else []
    out: List[JournalEntry] = []
    for s in seeds:
        title = summarize_belief(s, lang="pl") or "Mit"
        target = ", ".join(s.target_tags[:3]) or "?"
        strength = _strength_label(s.strength)
        distortion = _distortion_label(s.distortion)
        subtitle = f"cel: {target}  ·  zasięg: {strength}"
        detail_lines = [
            f"Pełny zarzut: {s.core_claim or s.origin_text or '?'}",
            f"Cel: {target}",
            f"Metoda: {s.method}",
            f"Siła: {strength}",
            f"Zniekształcenie: {distortion}",
            f"Etap: {s.current_stage}",
        ]
        if s.created_by == "player":
            detail_lines.append("Pierwsze źródło: ty.")
        echoes = s.spread_count or 0
        if echoes:
            detail_lines.append(f"Echo: {echoes} razy podchwycone.")
        out.append(JournalEntry(
            title=title, subtitle=subtitle,
            status=strength.capitalize(),
            detail="\n".join(detail_lines),
            sort_key=(-int(s.strength or 0), title.lower()),
            raw_ref=s,
        ))
    return out


def _collect_crawlers(world) -> List[JournalEntry]:
    """Surface crawlers we've seen through `world.entities`."""
    if world is None:
        return []
    out: List[JournalEntry] = []
    seen = set()
    for ent in (world.entities or {}).values():
        if ent.entity_type not in ("crawler", "npc"):
            continue
        if ent.entity_id in seen:
            continue
        seen.add(ent.entity_id)
        rel = (world.character.relationships or {}).get(ent.key or str(ent.entity_id), 0)
        if rel > 2:
            mood = "życzliwy"
        elif rel > 0:
            mood = "neutralny"
        elif rel == 0:
            mood = "nieznany"
        else:
            mood = "nieufny"
        status = "żywy" if ent.is_alive() else "martwy"
        loc = ent.location_id or "?"
        out.append(JournalEntry(
            title=ent.display_name(),
            subtitle=f"Nastawienie: {mood}  ·  Los: {status}",
            body="",
            detail=f"Ostatnio widziany: {loc}\nNastawienie: {mood}\nLos: {status}",
            sort_key=(0 if ent.is_alive() else 1, ent.display_name().lower()),
            raw_ref=ent,
        ))
    return out


def _collect_inventory(world) -> List[JournalEntry]:
    if world is None:
        return []
    ch = world.character
    out: List[JournalEntry] = []
    for eid in (ch.inventory_ids or []):
        ent = world.entities.get(eid)
        if ent is None:
            continue
        st = ent.state or {}
        condition = "sprawny"
        if st.get("damaged"): condition = "uszkodzony"
        if st.get("unstable"): condition = "niestabilny"
        if (st.get("quality") or "") and st["quality"] != "normal":
            condition = f"{condition} · {st['quality']}"
        tags = list(ent.tags or [])
        affs = list(ent.affordances or [])
        deployable = "trap" in tags or "deployable" in tags or "deploy" in affs
        # P29.39 — surowe tagi schowane (debug info). Sam stan + opcjonalne
        # podpowiedzi „Można rozstawić" / „użyj" niżej wystarczą graczowi.
        detail_lines = [f"Stan: {condition}"]
        if deployable:
            detail_lines.append("Można rozstawić. Przykład: rozstaw pułapkę przy drzwiach.")
        if "consumable" in tags or "medical" in tags:
            detail_lines.append("Przykład: użyj " + ent.display_name())
        out.append(JournalEntry(
            title=ent.display_name(),
            subtitle=condition + ("  ·  [do rozstawienia]" if deployable else ""),
            status=condition,
            detail="\n".join(l for l in detail_lines if l),
            sort_key=ent.display_name().lower(),
            raw_ref=ent,
        ))
    return out


_MATERIAL_CATEGORIES = {
    "metal":       "metal",
    "scrap":       "metal",
    "scrap_metal": "metal",
    "wire":        "techniczne",
    "wire_bundle": "techniczne",
    "battery":     "techniczne",
    "battery_cell":"techniczne",
    "glass":       "konstrukcyjne",
    "glass_shards":"konstrukcyjne",
    "wood":        "konstrukcyjne",
    "cloth":       "tekstylne",
    "cloth_strips":"tekstylne",
    "tape":        "tekstylne",
    "screws":      "metal",
    "meat":        "organiczne",
    "meat_chunk":  "organiczne",
    "bone":        "organiczne",
    "bone_fragments":"organiczne",
    "sinew":       "organiczne",
    "blood_sample":"organiczne",
    "disinfectant":"chemiczne",
    "cleaning_fluid":"chemiczne",
    "sponsor_chip":"sponsorowane",
    "anomalous":   "anomalne",
}


def _collect_materials(world) -> List[JournalEntry]:
    if world is None:
        return []
    ch = world.character
    mats = ch.materials or {}
    if not mats:
        return []
    try:
        from ..content import materials as _mat
    except Exception:
        _mat = None
    out: List[JournalEntry] = []
    for key, qty in mats.items():
        if qty <= 0:
            continue
        name = key
        tags: List[str] = []
        if _mat is not None:
            md = _mat.get(key)
            if md is not None:
                name = md.name() if hasattr(md, "name") else getattr(md, "fallback_name_pl", key)
                tags = list(getattr(md, "tags", []))
        cat = _MATERIAL_CATEGORIES.get(key, "")
        if not cat:
            for tg in tags:
                if tg in _MATERIAL_CATEGORIES:
                    cat = _MATERIAL_CATEGORIES[tg]; break
        cat = cat or "różne"
        # P29.39 — surowe tagi schowane. Kategoria + ilość są jedyną
        # informacją, której gracz potrzebuje w tym widoku.
        out.append(JournalEntry(
            title=f"{qty}× {name}",
            subtitle=cat,
            status=cat,
            detail=f"Kategoria: {cat}\nIlość: {qty}",
            sort_key=(cat, name.lower()),
            raw_ref=key,
        ))
    return out


def _collect_crafting(world) -> List[JournalEntry]:
    out: List[JournalEntry] = []
    try:
        from ..content import crafting as _craft
        from ..content import materials as _mat
    except Exception:
        return out
    # P28.3 (P27-UX-3/4) — polonize crafting detail. Translate category +
    # stat + material keys + (where possible) material counts to PL labels
    # so the journal reads as Polish instead of leaking English keys.
    _CATEGORY_PL = {
        "tool":     "narzędzie",
        "weapon":   "broń",
        "trap":     "pułapka",
        "explosive": "ładunek wybuchowy",
        "armor":    "pancerz",
        "medical":  "medyczne",
        "consumable": "konsumpcyjne",
        "decoy":    "wabik",
        "lure":     "wabik",
        "mechanical": "mechaniczne",
        "chemical": "chemiczne",
        "electrical": "elektryczne",
    }
    _STAT_PL = {
        "STR": "SIŁ", "DEX": "ZRĘ", "CON": "KON",
        "INT": "INT", "WIS": "MĄD", "CHA": "CHA",
    }
    def _material_pl(key: str) -> str:
        """Use the material module's PL label when available; fall back
        to the raw key with underscores swapped for spaces."""
        try:
            label = _mat.label_pl(key) if hasattr(_mat, "label_pl") else None
            if label:
                return label
        except Exception:
            pass
        return key.replace("_", " ")
    for rk, rv in _craft.all_recipes().items():
        name_pl = rv.get("name_pl", rk)
        needed = rv.get("required_materials") or {}
        have_all = _mat.has_materials(world.character, needed) if needed else True
        status = "gotowe" if have_all else "brakuje materiałów"
        if needed:
            needs_line = ", ".join(f"{v}× {_material_pl(k)}"
                                   for k, v in needed.items())
        else:
            needs_line = "—"
        aliases = ", ".join((rv.get("aliases_pl") or [])[:3])
        cat_pl = _CATEGORY_PL.get(rv.get("category", ""), rv.get("category", "?"))
        stat_pl = _STAT_PL.get(rv.get("stat", ""), rv.get("stat", "?"))
        dc = rv.get("dc", "?")
        time_min = rv.get("time_minutes", "?")
        out.append(JournalEntry(
            title=name_pl,
            subtitle=status,
            status=status,
            detail=(f"Wymaga: {needs_line}\n"
                    f"Kategoria: {cat_pl}\n"
                    f"Test: {stat_pl} vs TT {dc}\n"
                    f"Czas: {time_min} min\n"
                    + (f"Aliasy: {aliases}\n" if aliases else "")
                    + f"Przykład: zrób {name_pl.lower()}"),
            sort_key=(0 if have_all else 1, name_pl.lower()),
            raw_ref=rk,
        ))
    # Trailing entries: improvised categories + help examples.
    try:
        cats = _craft.improvised_categories()
    except Exception:
        cats = {}
    for ck, cv in cats.items():
        tagsets = " | ".join("+".join(s) for s in cv.get("required_tag_sets", []))
        out.append(JournalEntry(
            title=f"Improwizacja: {ck}",
            subtitle="wymaga: " + tagsets,
            status="kategoria",
            detail=(f"Stat: {cv.get('stat','?')}   DC: {cv.get('base_dc','?')}\n"
                    f"Tagi: {tagsets}\n"
                    f"Przykład: zrób {ck} z kabli i baterii"),
            sort_key=("z_imp", ck),
            raw_ref=ck,
        ))
    # Sample commands as final entries — helpful when nothing else is reachable.
    out.append(JournalEntry(
        title="Polecenia (przykłady)",
        subtitle="podpowiedź",
        detail=("• zrób pułapkę z kabli i szkła\n"
                "• skleć nóż z ostrych odłamków\n"
                "• rozstaw pułapkę przy drzwiach\n"
                "• napraw pancerz taśmą\n"
                "• zrób wabik z mięsa i telefonu"),
        sort_key=("z_help", ""),
    ))
    return out


def _collect_achievements(world) -> List[JournalEntry]:
    out: List[JournalEntry] = []
    try:
        from ..systems import achievements as _ach
    except Exception:
        return out
    if world is None:
        return out
    unlocked = set((world.character.unlocked_achievements or []))
    for k, ad in _ach.catalog().items():
        is_unlocked = k in unlocked
        if not is_unlocked and ad.hidden:
            out.append(JournalEntry(
                title="Ukryte",
                subtitle="",
                status="ukryte",
                detail="Wymagania nieznane.",
                sort_key=(2, k),
                raw_ref=k,
            ))
            continue
        title = ad.fallback_name_pl or k
        desc  = ad.fallback_description_pl or ""
        out.append(JournalEntry(
            title=title,
            subtitle=("odblokowane" if is_unlocked else "zablokowane"),
            status=("odblokowane" if is_unlocked else "zablokowane"),
            detail=desc + (f"\nKategoria: {ad.category}" if ad.category else ""),
            sort_key=(0 if is_unlocked else 1, title.lower()),
            raw_ref=k,
        ))
    return out


def _collect_sponsors(world) -> List[JournalEntry]:
    """Prompt 18 — list every catalog sponsor with the player's current
    mood-relationship, who's the floor primary, and recent interventions
    by that sponsor."""
    out: List[JournalEntry] = []
    try:
        from ..content.data.sponsors import SPONSORS
        from ..engine import sponsors as _sp
        from ..engine import audience as _aud
    except Exception:
        return out

    primary = _sp.current_floor_sponsor_key(world)
    # Aggregate fired interventions per sponsor for the body text.
    by_sponsor: Dict[str, List[Any]] = {}
    for rec in getattr(world, "sponsor_interventions_used", []) or []:
        by_sponsor.setdefault(rec.sponsor_key, []).append(rec)

    rating = int(world.character.audience_rating or 0)
    band = _aud.band_for(rating)
    band_label = _aud.band_label(band)

    for skey, sdata in SPONSORS.items():
        name = t(sdata.get("name_key", ""),
                 fallback=sdata.get("name_fallback", skey))
        tagline = t(sdata.get("tagline_key", ""),
                    fallback=sdata.get("tagline_fallback", ""))
        att = _sp.get_attention(world, skey)
        mood = _sp.sponsor_mood(world, skey)
        is_primary = (skey == primary)
        sub_parts = [mood, f"uwaga {att:+d}"]
        if is_primary:
            sub_parts.append("PIĘTRO")
        subtitle = "  •  ".join(sub_parts)

        body_lines = [tagline] if tagline else []
        body_lines.append(f"Tonacja: {sdata.get('tone','')}")
        likes = ", ".join(sdata.get("likes_tags") or []) or "—"
        dislikes = ", ".join(sdata.get("dislikes_tags") or []) or "—"
        body_lines.append(f"Lubi: {likes}")
        body_lines.append(f"Nie lubi: {dislikes}")
        fired = by_sponsor.get(skey, [])
        if fired:
            body_lines.append("")
            body_lines.append("Interwencje:")
            for rec in fired[-5:]:
                body_lines.append(
                    f"  • {rec.kind} @ minuta {rec.fired_at_minute}"
                )

        body_lines.append("")
        body_lines.append(
            f"Aktualna widownia: {band_label} ({rating})."
        )

        out.append(JournalEntry(
            title=name + (" ★" if is_primary else ""),
            subtitle=subtitle,
            body=tagline or "",
            detail="\n".join(body_lines),
            tags=["sponsor"] + (["primary"] if is_primary else []),
            sort_key=(0 if is_primary else 1, name),
            raw_ref=skey,
        ))
    out.sort(key=lambda e: e.sort_key)
    return out


def _collect_companions(world) -> List[JournalEntry]:
    """Prompt 19 — Towarzysze tab. Lists every Companion in
    `character.companion_ids` with state, role, abilities, and recent
    notes. Crawler-ally entries also surface here so a single tab
    covers everyone who's "with" the player."""
    out: List[JournalEntry] = []
    try:
        from ..engine import companion as _comp
        from ..content.data.pets import get_pet_template
    except Exception:
        return out
    comps = _comp.player_companions(world)
    for c in comps:
        tmpl = get_pet_template(c.species_key) if c.kind == _comp.KIND_PET else {}
        title = c.display_name_pl or c.species_key
        subtitle_parts = [
            {"pet": "Zwierzak", "crawler": "Sojusznik",
             "drone": "Dron", "summon": "Przyzwany",
             "temp_npc": "Czasowy"}.get(c.kind, c.kind),
            f"więź {c.bond}/10",
            f"stres {c.stress}/10",
        ]
        if c.status != _comp.STATUS_ACTIVE:
            # P29.38 — Polish display, not raw slug.
            subtitle_parts.append(_comp.status_pl(c.status).upper())
        subtitle = "  •  ".join(subtitle_parts)

        body_lines = []
        if tmpl.get("description_pl"):
            body_lines.append(tmpl["description_pl"])
        for label, val in (
            ("Temperament", tmpl.get("temperament", "")),
            ("Rola", tmpl.get("role", "")),
            ("Potrzebuje", tmpl.get("need", "")),
            ("Ryzyko", tmpl.get("risk", "")),
        ):
            if val:
                body_lines.append(f"{label}: {val}")
        # P29.38 — Polish-only display: route abilities + sponsor tags
        # through companion.*_pl_list helpers. Raw slugs never reach
        # the player. (_comp already imported above.)
        if c.abilities:
            body_lines.append(
                "Umiejętności: "
                + ", ".join(_comp.abilities_pl_list(c.abilities)))
        if c.sponsor_likes_tags:
            body_lines.append(
                "Tagi sponsora: "
                + ", ".join(_comp.sponsor_tags_pl_list(c.sponsor_likes_tags)))
        body_lines.append("")
        body_lines.append("Polecenia: sprawdź zwierzę, nakarm zwierzę, "
                          "uspokój zwierzę, wyślij zwierzę na zwiad, "
                          "użyj zwierzęcia jako wabika.")

        out.append(JournalEntry(
            title=title,
            subtitle=subtitle,
            body=tmpl.get("description_pl", ""),
            detail="\n".join(body_lines),
            tags=["companion", c.kind],
            sort_key=(0 if c.status == _comp.STATUS_ACTIVE else 1, title),
            raw_ref=c.companion_id,
        ))
    out.sort(key=lambda e: e.sort_key)
    return out


_COLLECTORS = {
    TAB_LOG:          _collect_log,
    TAB_MAP:          _collect_map,
    TAB_OBJECTIVES:   _collect_objectives,
    TAB_KNOWLEDGE:    _collect_knowledge,
    TAB_RUMORS:       _collect_rumors,
    TAB_BELIEFS:      _collect_beliefs,
    TAB_CRAWLERS:     _collect_crawlers,
    TAB_COMPANIONS:   _collect_companions,
    TAB_SPONSORS:     _collect_sponsors,
    TAB_INVENTORY:    _collect_inventory,
    TAB_MATERIALS:    _collect_materials,
    TAB_CRAFTING:     _collect_crafting,
    TAB_ACHIEVEMENTS: _collect_achievements,
}


# ── Empty-state lines per tab ─────────────────────────────────────────────

EMPTY_STATES = {
    TAB_LOG:          "Log jest pusty. To rzadziej jest dobra wiadomość.",
    TAB_MAP:          "Nie znasz jeszcze żadnego pokoju.",
    TAB_OBJECTIVES:   "Cel piętra jeszcze nie został wskazany.",
    TAB_KNOWLEDGE:    "Brak potwierdzonej wiedzy. Loch jest mglisty.",
    TAB_RUMORS:       "Nie znasz jeszcze żadnych plotek.",
    TAB_BELIEFS:      "Brak zapisanych mitów.",
    TAB_CRAWLERS:     "Nie znasz jeszcze żadnych crawlerów.",
    TAB_INVENTORY:    "Plecak pusty.",
    TAB_MATERIALS:    "Nie masz jeszcze materiałów. Loch pozostaje chwilowo w jednym kawałku.",
    TAB_CRAFTING:     "Brak przepisów. Spróbuj 'pomoc craftingu'.",
    TAB_ACHIEVEMENTS: "Nie odblokowano jeszcze osiągnięć.",
    TAB_SPONSORS:     "Żaden sponsor jeszcze cię nie zauważył.",
    TAB_COMPANIONS:   "Nie masz ze sobą żadnego towarzysza.",
}


def empty_state(tab_key: str) -> str:
    return EMPTY_STATES.get(tab_key, "Pusto.")
