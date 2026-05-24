"""CRAWL PROTOCOL - Localization layer.

Polish-primary, English-fallback translation system.
Module is named `lang` (not `locale`) to avoid shadowing the stdlib `locale`.

Usage:
    from lang import tr, set_language, get_language

    tr("title_new_game")              # returns Polish string by default
    tr("greet_player", name="Voss")   # supports .format() interpolation
    set_language("en")                # switch to English
    tr("title_new_game")              # now returns English

Fallback chain: current_lang -> 'pl' -> 'en' -> raw_key

Translation files live in ./locales/<lang>.json (flat key -> string dict).
Missing keys do not raise — they return the key itself, prefixed with [?]
in debug mode so you can spot untranslated strings quickly.
"""
import json
import os
import sys
from typing import Optional, Dict

# ── Module state ──────────────────────────────────────────────────────────────

_LANG: str = "pl"                # current language code
_DEFAULT_LANG: str = "pl"        # primary / source-of-truth language
_FALLBACK_LANG: str = "en"       # secondary fallback
_TABLES: Dict[str, Dict[str, str]] = {}    # lang_code -> {key: string}
_DEBUG_MISSING: bool = False     # if True, missing keys render as "[?key]"
_LOCALES_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


# ── Loading ───────────────────────────────────────────────────────────────────

def _load_lang(lang: str) -> Dict[str, str]:
    """Load a single language JSON file. Returns empty dict on failure."""
    path = os.path.join(_LOCALES_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        if _DEBUG_MISSING:
            print(f"[locale] failed to load {path}: {e}", file=sys.stderr)
        return {}


def reload():
    """Force reload of all known language tables. Call after editing JSON."""
    global _TABLES
    _TABLES = {}
    _ensure_loaded(_DEFAULT_LANG)
    _ensure_loaded(_FALLBACK_LANG)
    if _LANG not in (_DEFAULT_LANG, _FALLBACK_LANG):
        _ensure_loaded(_LANG)


def _ensure_loaded(lang: str):
    if lang not in _TABLES:
        _TABLES[lang] = _load_lang(lang)


# ── Public API ────────────────────────────────────────────────────────────────

def set_language(lang: str):
    """Switch the current language. Loads the table lazily."""
    global _LANG
    if not lang:
        return
    _LANG = lang
    _ensure_loaded(lang)


def get_language() -> str:
    return _LANG


def available_languages():
    """Return a list of language codes for which a JSON file exists."""
    if not os.path.isdir(_LOCALES_DIR):
        return []
    out = []
    for f in os.listdir(_LOCALES_DIR):
        if f.endswith(".json"):
            out.append(f[:-5])
    return sorted(out)


def set_debug_missing(flag: bool):
    """Toggle [?key] rendering for missing keys. Useful during translation."""
    global _DEBUG_MISSING
    _DEBUG_MISSING = bool(flag)


def tr(key: str, _lang: Optional[str] = None, **kwargs) -> str:
    """
    Look up a translation key. Returns the formatted string.

    Lookup order:  _lang (override) -> current -> default ('pl') -> fallback ('en') -> key

    Format kwargs are applied with str.format_map; missing format keys are
    rendered as their literal placeholder rather than raising.

    The override parameter is named `_lang` (leading underscore) so it does
    not collide with a likely `{lang}` placeholder in user strings.
    """
    target = _lang or _LANG

    _ensure_loaded(target)
    if target != _DEFAULT_LANG:
        _ensure_loaded(_DEFAULT_LANG)
    if target != _FALLBACK_LANG:
        _ensure_loaded(_FALLBACK_LANG)

    raw = (
        _TABLES.get(target, {}).get(key)
        or _TABLES.get(_DEFAULT_LANG, {}).get(key)
        or _TABLES.get(_FALLBACK_LANG, {}).get(key)
    )

    if raw is None:
        return f"[?{key}]" if _DEBUG_MISSING else key

    if not kwargs:
        return raw

    try:
        return raw.format_map(_SafeFormat(kwargs))
    except (ValueError, IndexError):
        return raw


def has_key(key: str, _lang: Optional[str] = None) -> bool:
    """Check if a key exists in any language table."""
    target = _lang or _LANG
    _ensure_loaded(target)
    _ensure_loaded(_DEFAULT_LANG)
    _ensure_loaded(_FALLBACK_LANG)
    return (
        key in _TABLES.get(target, {})
        or key in _TABLES.get(_DEFAULT_LANG, {})
        or key in _TABLES.get(_FALLBACK_LANG, {})
    )


def trn(key_singular: str, key_plural: str, count: int, **kwargs) -> str:
    """
    Pluralization helper. Polish has more plural forms than English, but for
    a fan project we approximate with two forms (1 = singular, otherwise plural)
    and rely on each language's JSON to provide context-appropriate strings.
    """
    kwargs.setdefault("count", count)
    return tr(key_singular if count == 1 else key_plural, **kwargs)


def lang_label(code: str) -> str:
    """Pretty label for a language code, used in the toggle UI."""
    return {
        "pl": "Polski",
        "en": "English",
    }.get(code, code.upper())


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SafeFormat(dict):
    """Dict that returns the literal {key} for missing format placeholders."""

    def __missing__(self, k):
        return "{" + k + "}"


# Eager-load Polish and English on import so the very first tr() call is cheap.
_ensure_loaded(_DEFAULT_LANG)
_ensure_loaded(_FALLBACK_LANG)
