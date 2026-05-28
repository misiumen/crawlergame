"""P29.41 — drzewka dialogowe NPC.

Faza 1 (P29.41) — silnik + jedno minimalne drzewko jako smoke test.
Faza 2 (P29.43) — pełne drzewka dla wszystkich NPC z tej gry, w stylu
Dinnimana, ~10 NPC × ~300 słów drzewko.

Każde drzewko rejestruje się przez `engine.dialogue.register_tree`.

NPC entity ma w state polu `dialogue_tree_key` (np. „stary_kompas").
Jak go nie ma, fallback do starego skill check (legacy „pogadaj" path).

Konwencja:
  * tree_key = klucz NPC w snake_case (np. „stary_kompas",
    „handlarz_recyklera")
  * speaker w nodeach to display name NPC (po polsku, „Stary Kompas")
  * start_node = „start"
  * end_node = brak (option z next_node_id=None albo {"kind": "end"})
"""
from __future__ import annotations
from ...engine.dialogue import (
    DialogueTree, DialogueNode, DialogueOption, register_tree,
)


# ── Minimalne drzewko placeholdera ──────────────────────────────────
#
# Używane do testów silnika. Właściwa proza (Dinniman-style)
# przyjdzie w P29.43, w batchach do akceptu.

def _build_placeholder_tree() -> DialogueTree:
    """Drzewko-szkielet: gracz może zapytać X, zastraszyć (skill
    check), albo wyjść. Treść jest tymczasowa. Służy testowi silnika
    + integracji z game.py."""
    return DialogueTree(
        tree_key="placeholder_npc",
        start_node="start",
        nodes={
            "start": DialogueNode(
                node_id="start",
                speaker="Nieznajomy",
                text="Stoi przed tobą. Czeka, co powiesz.",
                options=[
                    DialogueOption(
                        label="Spytaj kim jest.",
                        next_node_id="introduce",
                    ),
                    DialogueOption(
                        label="Zastrasz go. (CHA, TT 12)",
                        skill_check=("CHA", 12),
                        next_node_id="intimidate_ok",
                        fail_node_id="intimidate_fail",
                    ),
                    DialogueOption(
                        label="Odejdź bez słowa.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "introduce": DialogueNode(
                node_id="introduce",
                speaker="Nieznajomy",
                text="(Tu będzie treść — P29.43.)",
                options=[
                    DialogueOption(
                        label="Skończ rozmowę.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_ok": DialogueNode(
                node_id="intimidate_ok",
                speaker="Nieznajomy",
                text="(Sukces — treść w P29.43.)",
                on_enter_consequences=[
                    {"kind": "audience", "amount": 1},
                ],
                options=[
                    DialogueOption(
                        label="Wyjdź.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
            "intimidate_fail": DialogueNode(
                node_id="intimidate_fail",
                speaker="Nieznajomy",
                text="(Porażka — treść w P29.43.)",
                on_enter_consequences=[
                    {"kind": "threat", "amount": 2},
                ],
                options=[
                    DialogueOption(
                        label="Cofnij się.",
                        next_node_id=None,
                        consequences=[{"kind": "end"}],
                    ),
                ],
            ),
        },
    )


# ── Rejestracja ──────────────────────────────────────────────────────

def register_all_trees() -> None:
    """Wywoływane raz przy starcie gry (lub lazy przed pierwszym
    użyciem)."""
    register_tree(_build_placeholder_tree())


# Idempotent register at import time.
register_all_trees()
