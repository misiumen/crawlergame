"""Role-based local-LLM façade (Prompt 13).

This is the ONLY module engine code should call when it wants flavor text
from a local LLM. It enforces the design rules in one place:

    1. Every role can be disabled independently via `config.LLM_*_ENABLED`.
    2. Every role has a default model; mismatch with installed Ollama
       models is detected and treated as "unavailable" (no HTTP retry
       storm, no freezes).
    3. Calls NEVER raise. On any failure — flag off, model missing,
       Ollama unreachable, timeout, invalid JSON — they return the
       caller-supplied fallback unchanged.
    4. Calls NEVER mutate world state. They return text or structured
       data. The caller is responsible for validating + applying.
    5. Availability is cached per process so an offline Ollama doesn't
       freeze the game on every parse.

Public API:
    ROLE_INTENT, ROLE_NARRATOR, ROLE_LOOTBOX, ROLE_DIALOGUE  — constants
    is_role_enabled(role)               → bool
    model_for_role(role)                → str
    is_model_available(model)           → bool   (cached)
    is_role_available(role)             → bool   (enabled AND model present)
    enrich_text(role, prompt, fallback) → str    (never raises)
    request_structured(role, prompt, fallback_dict) → dict
    reset_availability_cache()          — force a re-probe on next call
    summary()                           → dict   (for debug / settings UI)
"""
from __future__ import annotations
import json
import socket
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional


ROLE_INTENT   = "intent"
ROLE_NARRATOR = "narrator"
ROLE_LOOTBOX  = "lootbox"
ROLE_DIALOGUE = "dialogue"
ROLES = (ROLE_INTENT, ROLE_NARRATOR, ROLE_LOOTBOX, ROLE_DIALOGUE)


# ── Cached availability state ─────────────────────────────────────────────

_OLLAMA_REACHABLE: Optional[bool] = None     # one-shot reachability probe
_MODEL_AVAILABLE: Dict[str, bool] = {}       # per-model, evaluated lazily
_AVAILABLE_MODELS: Optional[set] = None      # set of model names from /api/tags


def reset_availability_cache() -> None:
    global _OLLAMA_REACHABLE, _MODEL_AVAILABLE, _AVAILABLE_MODELS
    _OLLAMA_REACHABLE = None
    _MODEL_AVAILABLE = {}
    _AVAILABLE_MODELS = None


# ── Config plumbing ──────────────────────────────────────────────────────

def _cfg():
    """Late import so changing config at runtime works in tests."""
    from .. import config
    return config


def is_role_enabled(role: str) -> bool:
    c = _cfg()
    flag_name = {
        ROLE_INTENT:   "LLM_INTENT_ENABLED",
        ROLE_NARRATOR: "LLM_NARRATOR_ENABLED",
        ROLE_LOOTBOX:  "LLM_LOOTBOX_ENABLED",
        ROLE_DIALOGUE: "LLM_DIALOGUE_ENABLED",
    }.get(role)
    return bool(getattr(c, flag_name, False)) if flag_name else False


def model_for_role(role: str) -> str:
    c = _cfg()
    return {
        ROLE_INTENT:   getattr(c, "LLM_INTENT_MODEL",   "qwen2.5:3b"),
        ROLE_NARRATOR: getattr(c, "LLM_NARRATOR_MODEL", "qwen3:30b"),
        ROLE_LOOTBOX:  getattr(c, "LLM_LOOTBOX_MODEL",  "qwen3:14b"),
        ROLE_DIALOGUE: getattr(c, "LLM_DIALOGUE_MODEL", "llama3.3:70b"),
    }.get(role, "")


# ── Probes ────────────────────────────────────────────────────────────────

def _is_ollama_reachable() -> bool:
    global _OLLAMA_REACHABLE
    if _OLLAMA_REACHABLE is not None:
        return _OLLAMA_REACHABLE
    c = _cfg()
    url = f"{c.OLLAMA_URL.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=c.OLLAMA_TIMEOUT_SECONDS) as r:
            ok = 200 <= r.status < 300
        _OLLAMA_REACHABLE = bool(ok)
    except (urllib.error.URLError, socket.timeout, socket.error, OSError):
        _OLLAMA_REACHABLE = False
    except Exception:
        _OLLAMA_REACHABLE = False
    return _OLLAMA_REACHABLE


def _load_available_models() -> set:
    """Hit /api/tags once and remember which model names are installed."""
    global _AVAILABLE_MODELS
    if _AVAILABLE_MODELS is not None:
        return _AVAILABLE_MODELS
    if not _is_ollama_reachable():
        _AVAILABLE_MODELS = set()
        return _AVAILABLE_MODELS
    c = _cfg()
    url = f"{c.OLLAMA_URL.rstrip('/')}/api/tags"
    out: set = set()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=c.OLLAMA_TIMEOUT_SECONDS) as r:
            payload = json.loads(r.read().decode("utf-8", errors="replace"))
        for entry in payload.get("models", []) or []:
            name = entry.get("name") or entry.get("model")
            if isinstance(name, str) and name:
                out.add(name)
    except Exception:
        pass
    _AVAILABLE_MODELS = out
    return _AVAILABLE_MODELS


def is_model_available(model: str) -> bool:
    if not model:
        return False
    if model in _MODEL_AVAILABLE:
        return _MODEL_AVAILABLE[model]
    available = _load_available_models()
    # Match either exact `model:tag` or bare `model` (Ollama lists both forms).
    ok = (model in available) or any(
        m == model or m.startswith(model + ":") or model.startswith(m + ":")
        for m in available
    )
    _MODEL_AVAILABLE[model] = ok
    return ok


def is_role_available(role: str) -> bool:
    """True iff the role is enabled in config AND its model is installed
    AND Ollama is reachable. Use this at every call site."""
    if not is_role_enabled(role):
        return False
    if not _is_ollama_reachable():
        return False
    return is_model_available(model_for_role(role))


# ── Calls ─────────────────────────────────────────────────────────────────

def _ollama_generate(model: str, prompt: str, format_json: bool = False,
                     timeout: Optional[float] = None) -> Optional[str]:
    """Low-level wrapper around /api/generate. Returns the model's raw
    response string, or None on any failure. NEVER raises."""
    c = _cfg()
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if format_json:
        body["format"] = "json"
    data = json.dumps(body).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{c.OLLAMA_URL.rstrip('/')}/api/generate",
            data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout or c.OLLAMA_TIMEOUT_SECONDS) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, socket.error, OSError):
        return None
    except Exception:
        return None
    try:
        envelope = json.loads(raw)
        if isinstance(envelope, dict):
            response = envelope.get("response", "")
            if isinstance(response, str):
                return response.strip()
    except (json.JSONDecodeError, ValueError):
        return None
    return None


def enrich_text(role: str, prompt: str, fallback: str,
                validator: Optional[Callable[[str], bool]] = None,
                timeout: Optional[float] = None) -> str:
    """Ask the role's model for a single short text response. Always
    returns a string — `fallback` on any failure path.

    Caller MUST provide `fallback`. The fallback is what the engine
    already considers canonical (a static narrator line, deterministic
    flavor text, etc.) — never a placeholder like `?`.

    `validator(text) -> bool` is an optional sanity check the engine
    runs on the model's response. If it returns False, fallback is used.
    """
    if not isinstance(fallback, str):
        fallback = str(fallback or "")
    if not is_role_available(role):
        return fallback
    model = model_for_role(role)
    if not model:
        return fallback
    out = _ollama_generate(model, prompt, format_json=False, timeout=timeout)
    if not out:
        return fallback
    # Default sanity: strip surrounding quotes the model may add, cap at
    # 600 chars so a runaway response doesn't blow the log.
    text = out.strip()
    if text.startswith(("\"", "'")) and text.endswith(("\"", "'")) and len(text) >= 2:
        text = text[1:-1].strip()
    if len(text) > 600:
        text = text[:600].rstrip() + "…"
    if not text:
        return fallback
    if validator is not None:
        try:
            if not validator(text):
                return fallback
        except Exception:
            return fallback
    return text


def request_structured(role: str, prompt: str, fallback_dict: Dict[str, Any],
                       validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
                       timeout: Optional[float] = None) -> Dict[str, Any]:
    """Ask the role's model for a JSON dict response. Always returns a
    dict — `fallback_dict` on any failure or schema mismatch.

    `validator(dict) -> bool` is an optional caller-side schema check.
    """
    if not isinstance(fallback_dict, dict):
        fallback_dict = {}
    if not is_role_available(role):
        return dict(fallback_dict)
    model = model_for_role(role)
    if not model:
        return dict(fallback_dict)
    out = _ollama_generate(model, prompt, format_json=True, timeout=timeout)
    if not out:
        return dict(fallback_dict)
    try:
        parsed = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return dict(fallback_dict)
    if not isinstance(parsed, dict):
        return dict(fallback_dict)
    if validator is not None:
        try:
            if not validator(parsed):
                return dict(fallback_dict)
        except Exception:
            return dict(fallback_dict)
    return parsed


# ── Diagnostics ──────────────────────────────────────────────────────────

def summary() -> Dict[str, Any]:
    """Return a small dict describing the current LLM state. Used by the
    settings panel + a one-shot startup log line in main_revamp.py."""
    c = _cfg()
    out = {
        "mode": getattr(c, "LLM_MODE", "performance"),
        "ollama_reachable": _is_ollama_reachable(),
        "roles": {},
    }
    if out["ollama_reachable"]:
        _load_available_models()
    for role in ROLES:
        out["roles"][role] = {
            "enabled":   is_role_enabled(role),
            "model":     model_for_role(role),
            "available": is_role_available(role),
        }
    return out
