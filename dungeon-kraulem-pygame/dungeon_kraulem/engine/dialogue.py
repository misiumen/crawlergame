"""P29.41 — silnik dialog tree.

Zastępuje stary „pogadaj z X → d20 CHA → outcome line" prawdziwym
drzewkiem rozmów: NPC wypowiada linię, gracz wybiera jedną z opcji,
przechodzimy do następnego węzła. Skill check jest opcjonalny —
podczepiony pod konkretną opcję, nie pod całą rozmowę.

Architektura:

    DialogueOption — pojedyncza odpowiedź gracza.
      * label         — tekst opcji widziany przez gracza
      * next_node_id  — gdzie idziemy po wyborze (None = koniec)
      * skill_check   — opcjonalny (stat, dc) — Carl rzuca, wynik
                        zmienia next_node_id
      * consequences  — lista side-effectów (audience, sponsor,
                        give_item, set_flag, threat, log, end)
      * requires_flag — wymaga character.flags[X] żeby opcja była
                        dostępna
      * one_shot      — po wyborze opcja znika z menu (per-save)

    DialogueNode — pojedynczy „ekran" dialogu.
      * node_id       — unikalny w obrębie drzewka
      * speaker       — display name NPC w nagłówku
      * text          — co NPC mówi
      * options       — lista DialogueOption
      * on_enter_consequences — side-effekty przy wejściu do tego
                        węzła (np. „NPC widzi cię i traci 1 punkt
                        uwagi sponsora")

    DialogueTree — całość rozmowy z jednym NPC.
      * tree_key      — id (np. „stary_kompas")
      * start_node    — który węzeł otwiera rozmowę
      * nodes         — dict[node_id -> DialogueNode]

    DialogueState — runtime stan rozmowy (na Game, nie persystowane
    między run'ami, ale per dialog).
      * npc_entity_id, tree_key, current_node_id,
        visited_node_ids, picked_options (set[(node_id, opt_idx)])

Konsekwencje — każda to dict {"kind": str, ...params}:

    {"kind": "audience", "amount": +3}
    {"kind": "sponsor", "key": "kanal_7_krawedz", "amount": +2}
    {"kind": "threat", "amount": -2}
    {"kind": "give_item", "item_key": "stimpak"}
    {"kind": "set_flag", "flag": "knows_about_basement", "value": True}
    {"kind": "log", "text": "...", "severity": "normal"|"success"|"warn"|"danger"}
    {"kind": "end"}  # zamyka dialog

Wybierając opcję ze skill_check: rzucamy d20 + stat_mod vs DC. Sukces
→ next_node_id; porażka → option.fail_node_id (jeśli ustawione,
inaczej zostajemy w bieżącym węźle z log linią).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Callable, Any


@dataclass
class DialogueOption:
    label: str
    next_node_id: Optional[str] = None
    skill_check: Optional[Tuple[str, int]] = None  # (stat, dc)
    fail_node_id: Optional[str] = None             # gdzie iść przy oblanym checku
    consequences: List[Dict[str, Any]] = field(default_factory=list)
    fail_consequences: List[Dict[str, Any]] = field(default_factory=list)
    requires_flag: Optional[str] = None  # flag musi być truthy w character.flags
    forbids_flag: Optional[str] = None   # flag musi być falsy/missing
    one_shot: bool = False               # po wyborze niedostępna w tym save'ie


@dataclass
class DialogueNode:
    node_id: str
    speaker: str
    text: str
    options: List[DialogueOption] = field(default_factory=list)
    on_enter_consequences: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DialogueTree:
    tree_key: str
    start_node: str
    nodes: Dict[str, DialogueNode]

    def node(self, node_id: str) -> Optional[DialogueNode]:
        return self.nodes.get(node_id)


@dataclass
class DialogueState:
    """Runtime stan otwartego dialogu. Trzymany na Game'ie."""
    npc_entity_id: int
    tree_key: str
    current_node_id: str
    visited_node_ids: Set[str] = field(default_factory=set)
    picked_options: Set[Tuple[str, int]] = field(default_factory=set)


# ── Tree registry ─────────────────────────────────────────────────────

# tree_key → DialogueTree. Content live in content/data/npc_dialogues.py
# and registers via `register_tree`.
_TREES: Dict[str, DialogueTree] = {}


def register_tree(tree: DialogueTree) -> None:
    """Dodaj drzewko do globalnego rejestru. Walidacja kompletności
    (czy każdy next_node_id istnieje) zachodzi przy starcie dialogu."""
    _TREES[tree.tree_key] = tree


def get_tree(tree_key: str) -> Optional[DialogueTree]:
    return _TREES.get(tree_key)


def all_tree_keys() -> List[str]:
    return list(_TREES.keys())


# ── Option availability ──────────────────────────────────────────────

def _flag_truthy(world, flag: Optional[str]) -> bool:
    """Pobierz character.flags[flag] z bezpiecznym False na brak."""
    if not flag:
        return False
    ch = getattr(world, "character", None)
    if ch is None:
        return False
    flags = getattr(ch, "flags", None) or {}
    return bool(flags.get(flag))


def is_option_available(world, state: DialogueState, node_id: str,
                         opt_idx: int, opt: DialogueOption) -> bool:
    """Czy opcja jest aktualnie dostępna w danym węźle dla tego
    gracza? Gates: requires_flag, forbids_flag, one_shot+picked."""
    if opt.one_shot and (node_id, opt_idx) in state.picked_options:
        return False
    if opt.requires_flag and not _flag_truthy(world, opt.requires_flag):
        return False
    if opt.forbids_flag and _flag_truthy(world, opt.forbids_flag):
        return False
    return True


def available_options(world, state: DialogueState,
                      node: DialogueNode) -> List[Tuple[int, DialogueOption]]:
    """Lista (idx_oryginalny, option) dla opcji aktualnie dostępnych
    w bieżącym węźle. Pomijamy te, które gates wycięły."""
    out = []
    for i, opt in enumerate(node.options):
        if is_option_available(world, state, node.node_id, i, opt):
            out.append((i, opt))
    return out


# ── Skill check ──────────────────────────────────────────────────────

def _roll_skill_check(world, stat: str, dc: int) -> Tuple[bool, int, int]:
    """Zwraca (success, raw, total). Używa engine/utils_compat.roll_d20
    żeby trzymać się tej samej kostki co reszta gry. Crit fail (raw=1)
    zawsze porażka; crit success (raw=20) zawsze sukces."""
    try:
        from .utils_compat import roll_d20
        raw = roll_d20()
    except Exception:
        import random
        raw = random.randint(1, 20)
    ch = getattr(world, "character", None)
    mod = ch.stat_mod(stat) if ch else 0
    total = raw + mod
    if raw == 1:
        return False, raw, total
    if raw == 20:
        return True, raw, total
    return total >= dc, raw, total


# ── Consequence dispatch ────────────────────────────────────────────

def apply_consequences(world, npc_entity, consequences: List[Dict[str, Any]],
                        log_callback: Optional[Callable[[str, str], None]] = None
                        ) -> bool:
    """Wykonaj listę konsekwencji. Zwraca True jeśli żadna z nich
    nie zażądała zakończenia dialogu, False jeśli pojawiło się
    {"kind": "end"}.

    `log_callback(text, severity)` — funkcja Game.log używana, gdy
    konsekwencja typu „log" / „give_item" / etc. wymaga komunikatu.
    Jeśli brak, używamy world.log_msg fallback.
    """
    def _emit(text: str, sev: str = "normal"):
        if log_callback is not None:
            log_callback(text, sev)
        elif hasattr(world, "log_msg"):
            world.log_msg(text, sev)

    keep_going = True
    for c in consequences or []:
        kind = c.get("kind")
        if kind == "audience":
            try:
                from . import audience as _aud
                _aud.change_audience(world, int(c.get("amount", 0)),
                                      source=c.get("source", "dialogue"),
                                      emit_log=False)
            except Exception:
                pass
        elif kind == "sponsor":
            try:
                from . import sponsors as _sp
                _sp.adjust_attention(world, c["key"], int(c.get("amount", 0)))
            except Exception:
                pass
        elif kind == "threat":
            try:
                room = (world.current_floor.current_room()
                        if world.current_floor else None)
                if room is not None:
                    amt = int(c.get("amount", 0))
                    from . import threat as _th
                    if amt > 0:
                        _th.bump(world, room, amt, source="dialogue",
                                  log_threshold_lines=False)
                    elif amt < 0:
                        _th.de_escalate(world, room, abs(amt))
            except Exception:
                pass
        elif kind == "set_flag":
            ch = getattr(world, "character", None)
            if ch is not None:
                if ch.flags is None:
                    ch.flags = {}
                ch.flags[c["flag"]] = c.get("value", True)
        elif kind == "clear_flag":
            ch = getattr(world, "character", None)
            if ch is not None and ch.flags is not None:
                ch.flags.pop(c["flag"], None)
        elif kind == "give_item":
            try:
                from ..content.items import make_item
                it = make_item(c["item_key"],
                                location_id="inventory:player")
                world.register(it)
                world.character.inventory_ids.append(it.entity_id)
                _emit(c.get("log") or
                       f"Dostajesz: {it.display_name()}.", "success")
            except Exception:
                pass
        elif kind == "log":
            _emit(c.get("text", ""), c.get("severity", "normal"))
        elif kind == "end":
            keep_going = False
        elif kind == "relationship":
            ch = getattr(world, "character", None)
            try:
                eid_str = str(getattr(npc_entity, "entity_id", ""))
                if ch is not None and eid_str:
                    ch.relationships[eid_str] = (
                        ch.relationships.get(eid_str, 0)
                        + int(c.get("amount", 0)))
            except Exception:
                pass
    return keep_going


# ── Dialogue flow ────────────────────────────────────────────────────

def start_dialogue(world, npc_entity, tree_key: str,
                    log_callback: Optional[Callable[[str, str], None]] = None
                    ) -> Optional[DialogueState]:
    """Otwórz dialog z NPC. Zwraca DialogueState (do trzymania w
    Game) albo None jeśli drzewko nie istnieje albo gracz miał już
    zakończoną rozmowę z tym NPC (one_shot tree)."""
    tree = get_tree(tree_key)
    if tree is None:
        return None
    start_node = tree.node(tree.start_node)
    if start_node is None:
        return None
    state = DialogueState(
        npc_entity_id=getattr(npc_entity, "entity_id", -1),
        tree_key=tree_key,
        current_node_id=tree.start_node,
        visited_node_ids={tree.start_node},
        picked_options=set(),
    )
    # Uruchom on_enter_consequences dla start_node.
    apply_consequences(world, npc_entity,
                        start_node.on_enter_consequences, log_callback)
    return state


def pick_option(world, npc_entity, state: DialogueState, opt_idx: int,
                 log_callback: Optional[Callable[[str, str], None]] = None
                 ) -> Tuple[bool, Optional[str]]:
    """Gracz wybiera opcję `opt_idx` w bieżącym węźle. Zwraca
    (continue, info_line). continue=False oznacza koniec dialogu.

    Sekwencja:
      1. Sprawdź czy opcja dostępna (gates).
      2. Skill check (jeśli ustawiony) — wynik routuje do
         next_node_id albo fail_node_id, plus log z rzutem.
      3. Aplikuj consequences (lub fail_consequences).
      4. Stamp picked_options.
      5. Przejdź do next_node_id albo zamknij dialog.
    """
    tree = get_tree(state.tree_key)
    if tree is None:
        return False, None
    cur_node = tree.node(state.current_node_id)
    if cur_node is None or opt_idx < 0 or opt_idx >= len(cur_node.options):
        return False, None
    opt = cur_node.options[opt_idx]
    if not is_option_available(world, state, state.current_node_id,
                                 opt_idx, opt):
        return True, "Ta opcja nie jest teraz dostępna."

    # Stamp pickup.
    state.picked_options.add((state.current_node_id, opt_idx))

    # Skill check.
    success = True
    info_line = None
    if opt.skill_check is not None:
        stat, dc = opt.skill_check
        success, raw, total = _roll_skill_check(world, stat, dc)
        from .dice_labels import format_check as _fc
        level = ("critical_success" if raw == 20
                 else "critical_failure" if raw == 1
                 else "success" if success
                 else "failure")
        info_line = _fc("talk", stat, raw,
                         world.character.stat_mod(stat) if world.character else 0,
                         total, dc, level)

    # Apply consequences (kierunek zależny od sukcesu).
    consequences = opt.consequences if success else (
        opt.fail_consequences or opt.consequences)
    keep_going = apply_consequences(world, npc_entity, consequences,
                                      log_callback)
    if not keep_going:
        return False, info_line

    # Przejście do kolejnego węzła.
    next_id = opt.next_node_id if success else (
        opt.fail_node_id or opt.next_node_id)
    if not next_id:
        return False, info_line
    next_node = tree.node(next_id)
    if next_node is None:
        return False, info_line
    state.current_node_id = next_id
    state.visited_node_ids.add(next_id)
    apply_consequences(world, npc_entity,
                        next_node.on_enter_consequences, log_callback)
    return True, info_line


def current_node(state: DialogueState) -> Optional[DialogueNode]:
    tree = get_tree(state.tree_key)
    if tree is None:
        return None
    return tree.node(state.current_node_id)
