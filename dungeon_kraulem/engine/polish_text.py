"""Polish text helpers — diacritic fold + stem matchers.

Prompt 19 audit fix S3: previously the codebase had three independent
matching strategies:
  * `validation._polish_match` — 5-char stem, used for exit / room names
  * `affordances.find_affordance_by_verb` — scaled 4/5/6 stem by verb len
  * `parser_core` mass-action verbs — bare `startswith` literal match

That's bug-bait. This module is the new single source. The legacy
helpers in validation.py / affordances.py now thin-delegate here so
existing callers keep working without import churn.

Why two stem functions and not one:
  - `polish_match(typed, label)` is for matching a player-typed noun
    against a known label (exit "przejście" / room "Komnata"). Both
    sides are nouns, both are diacritic-folded, and the stem cutoff
    is 5 chars — long enough to distinguish but short enough to
    forgive inflection.
  - `verb_stem_match(typed, candidate)` is for matching a player verb
    against an affordance verb list. The stem cutoff scales with
    verb length so short imperatives (`weź`, `idź`) don't over-match
    and long verbs (`przeszukaj`) don't collide with unrelated nouns
    (`przejście`).
"""
from __future__ import annotations

import re
from typing import Iterable


# ── ASCII fold ─────────────────────────────────────────────────────────────

_FOLD = str.maketrans({
    "ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ź":"z","ż":"z",
    "Ą":"a","Ć":"c","Ę":"e","Ł":"l","Ń":"n","Ó":"o","Ś":"s","Ź":"z","Ż":"z",
})


def fold(s: str) -> str:
    """Lowercase + strip Polish diacritics. Always-safe; idempotent."""
    if not s:
        return ""
    return s.lower().translate(_FOLD).strip()


# ── Movement prepositions ──────────────────────────────────────────────────

_MOVE_PREPOSITIONS = frozenset({
    "do","w","we","na","przez","ku","ku temu","w stronę","w strone","w stron",
    "to","into","through","toward","towards","at","via",
})


def strip_movement_prepositions(text: str) -> str:
    """Drop leading Polish/English movement prepositions from a phrase.
    `'idź do przejścia'` → `'przejścia'`. Tolerates extra whitespace."""
    if not text:
        return ""
    parts = [t for t in re.split(r"\s+", text.strip()) if t]
    while parts and parts[0].lower() in _MOVE_PREPOSITIONS:
        parts.pop(0)
    return " ".join(parts).strip()


# ── Stem matchers ─────────────────────────────────────────────────────────

def polish_match(typed_folded: str, label_folded: str,
                 *, stem_chars: int = 5) -> bool:
    """Loose noun match via diacritic fold + N-char stem prefix.

    Both sides expected already-folded (caller decides — keeps this
    cheap when chaining). Word-by-word: each token of `typed` must
    have a stem-length prefix that also prefixes some token of
    `label` (or vice versa). Stems shorter than 3 chars are skipped
    so short adjectives don't trigger false positives.
    """
    if not typed_folded or not label_folded:
        return False
    if typed_folded == label_folded:
        return True
    if typed_folded in label_folded or label_folded in typed_folded:
        return True
    typed_tokens  = [t for t in re.split(r"[^a-z0-9]+", typed_folded) if t]
    label_tokens  = [t for t in re.split(r"[^a-z0-9]+", label_folded) if t]
    if not typed_tokens or not label_tokens:
        return False
    for t in typed_tokens:
        stem = t[:stem_chars]
        if len(stem) < 3:
            continue
        matched_word = False
        for lt in label_tokens:
            if lt.startswith(stem) or t.startswith(lt[:stem_chars]):
                matched_word = True
                break
        if not matched_word:
            return False
    return True


def verb_stem_match(typed_folded: str, candidate_folded: str) -> bool:
    """Polish verb-stem matcher with length scaling.

    Short imperatives (`weź`, `idź`, `rzuć`) need a short stem (4) so
    conjugations match (`wezmę`, `idziemy`, `rzucam`). Long verbs
    (`przeszukaj`, `obejrzyj`) need a longer stem (6) so they don't
    over-match unrelated nouns (`przejście`).

    Returns True for exact match, substring containment, or scaled
    prefix match.
    """
    if not typed_folded or not candidate_folded:
        return False
    if candidate_folded == typed_folded:
        return True
    # Use the first word of the candidate as its stem source.
    stem = candidate_folded.split()[0] if " " in candidate_folded else candidate_folded
    if len(stem) < 3:
        return False
    # Threshold matches the Prompt-18 affordance fix: short verbs get
    # a 4-char stem (covers conjugation like "uderz"/"uderzam"); 7+ char
    # verbs need a 6-char stem so "przeszukaj" / "przejdź" don't over-
    # match unrelated nouns like "przejście".
    stem_len = 4 if len(stem) <= 6 else 6
    return typed_folded.startswith(stem[:stem_len])


# ── Any-of helper (catalog scan) ──────────────────────────────────────────

def best_verb_match(typed_raw: str, candidates: Iterable[str]) -> bool:
    """True iff `typed_raw` matches any candidate after folding both
    sides. Convenience for catalog scans."""
    typed_f = fold(typed_raw)
    for c in candidates:
        if verb_stem_match(typed_f, fold(c)):
            return True
    return False
