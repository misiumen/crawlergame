"""Localization for the revamp.

Polish primary, English fallback. Uses revamp/locales/<lang>.json.

Public API:
    t(key, fallback=None, **fmt)   -> str
    set_language(code)             -> None
    get_language()                 -> str
    available_languages()          -> [str]
    reload()                       -> None
"""
import json
import os
import sys
from typing import Optional, Dict

from .config import LANGUAGE, LANG_DEBUG_MISSING, LOCALES_DIR

_LANG = LANGUAGE
_DEFAULT_LANG = "pl"
_FALLBACK_LANG = "en"
_TABLES: Dict[str, Dict[str, str]] = {}
_DEBUG = LANG_DEBUG_MISSING


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def _path(code: str) -> str:
    return os.path.join(LOCALES_DIR, f"{code}.json")


def _load(code: str) -> Dict[str, str]:
    p = _path(code)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        if _DEBUG:
            print(f"[revamp.lang] failed to load {p}: {e}", file=sys.stderr)
        return {}


def _ensure(code: str):
    if code not in _TABLES:
        _TABLES[code] = _load(code)


def reload():
    global _TABLES
    _TABLES = {}
    _ensure(_DEFAULT_LANG)
    _ensure(_FALLBACK_LANG)
    if _LANG not in (_DEFAULT_LANG, _FALLBACK_LANG):
        _ensure(_LANG)


def set_language(code: str):
    global _LANG
    if not code:
        return
    _LANG = code
    _ensure(code)


def get_language() -> str:
    return _LANG


def set_debug_missing(flag: bool):
    global _DEBUG
    _DEBUG = bool(flag)


def available_languages():
    if not os.path.isdir(LOCALES_DIR):
        return []
    return sorted(
        f[:-5] for f in os.listdir(LOCALES_DIR) if f.endswith(".json")
    )


def t(key: str, fallback: Optional[str] = None, **fmt) -> str:
    """Look up a translation key.

    Order: current_lang -> default ('pl') -> fallback ('en') -> fallback arg -> key.
    """
    _ensure(_LANG)
    _ensure(_DEFAULT_LANG)
    _ensure(_FALLBACK_LANG)

    raw = (
        _TABLES.get(_LANG, {}).get(key)
        or _TABLES.get(_DEFAULT_LANG, {}).get(key)
        or _TABLES.get(_FALLBACK_LANG, {}).get(key)
    )

    if raw is None:
        if fallback is not None:
            raw = fallback
        else:
            return f"[?{key}]" if _DEBUG else key

    if not fmt:
        return raw

    try:
        return raw.format_map(_Safe(fmt))
    except (ValueError, IndexError):
        return raw


_ensure(_DEFAULT_LANG)
_ensure(_FALLBACK_LANG)
