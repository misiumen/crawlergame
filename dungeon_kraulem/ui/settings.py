"""User settings persistence (Prompt 09).

Stores display preferences in `settings_revamp.json` next to the game's
working directory. Kept deliberately separate from `revamp_save.json` so
that wiping a save doesn't reset the player's resolution choice.

Schema:
    {
      "resolution_width":  int,
      "resolution_height": int,
      "fullscreen":        bool,
      "ui_scale":          "auto" | float
    }

`load_settings()` always returns a dict with valid defaults — corrupt
files, missing keys, and unsupported resolutions fall back safely.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, Tuple

from ..config import (SUPPORTED_RESOLUTIONS, DEFAULT_RESOLUTION,
                     FULLSCREEN_ENABLED, UI_SCALE, LLM_MODE,
                     apply_llm_mode)


LLM_MODES = ("performance", "enhanced", "full_show")


SETTINGS_FILE = "dungeon_kraulem_settings.json"
LEGACY_SETTINGS_FILE = "settings_revamp.json"


def _resolve_settings_path() -> str:
    """Prefer the new file name; fall back to the legacy name if only
    that exists. Writes always go to the new name."""
    if os.path.exists(SETTINGS_FILE):
        return SETTINGS_FILE
    if os.path.exists(LEGACY_SETTINGS_FILE):
        return LEGACY_SETTINGS_FILE
    return SETTINGS_FILE


def _defaults() -> Dict[str, Any]:
    return {
        "resolution_width":  DEFAULT_RESOLUTION[0],
        "resolution_height": DEFAULT_RESOLUTION[1],
        "fullscreen":        bool(FULLSCREEN_ENABLED),
        "ui_scale":          UI_SCALE,
        # Prompt 13: per-machine LLM runtime mode. Defaults to
        # "performance" so a fresh install never depends on a model.
        "llm_mode":          LLM_MODE,
    }


def _is_supported(w: int, h: int) -> bool:
    try:
        return (int(w), int(h)) in [tuple(p) for p in SUPPORTED_RESOLUTIONS]
    except (TypeError, ValueError):
        return False


def load_settings() -> Dict[str, Any]:
    """Read settings, fall back to defaults on any failure."""
    out = _defaults()
    path = _resolve_settings_path()
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        print(f"[dungeon_kraulem.settings] {path} unreadable — using defaults.")
        return out
    if not isinstance(data, dict):
        return out
    # Field-by-field merge with validation.
    try:
        w = int(data.get("resolution_width", out["resolution_width"]))
        h = int(data.get("resolution_height", out["resolution_height"]))
    except (TypeError, ValueError):
        w, h = out["resolution_width"], out["resolution_height"]
    if not _is_supported(w, h):
        print(f"[revamp.settings] resolution {w}x{h} not supported — "
              f"falling back to default.")
        w, h = out["resolution_width"], out["resolution_height"]
    out["resolution_width"] = w
    out["resolution_height"] = h
    out["fullscreen"] = bool(data.get("fullscreen", out["fullscreen"]))
    scale = data.get("ui_scale", out["ui_scale"])
    if scale == "auto" or isinstance(scale, (int, float)):
        out["ui_scale"] = scale
    # Prompt 13: validate LLM mode against the known preset list.
    mode = str(data.get("llm_mode", out["llm_mode"]) or out["llm_mode"]).lower()
    if mode in LLM_MODES:
        out["llm_mode"] = mode
    return out


def set_llm_mode(mode: str) -> bool:
    """Persist a new LLM runtime mode and apply it to the live config."""
    if (mode or "").lower() not in LLM_MODES:
        return False
    s = load_settings()
    s["llm_mode"] = mode.lower()
    if not save_settings(s):
        return False
    apply_llm_mode(mode.lower())
    # Reset the availability cache so the next call re-probes Ollama
    # with the new role flags.
    try:
        from ..llm import llm_roles
        llm_roles.reset_availability_cache()
    except Exception:
        pass
    return True


def save_settings(values: Dict[str, Any]) -> bool:
    """Write settings dict to disk. Returns True on success."""
    if not isinstance(values, dict):
        return False
    merged = _defaults()
    merged.update({k: v for k, v in values.items() if k in merged})
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        return True
    except OSError:
        return False


def get_resolution() -> Tuple[int, int]:
    s = load_settings()
    return (s["resolution_width"], s["resolution_height"])


def is_fullscreen() -> bool:
    return bool(load_settings().get("fullscreen", False))


def set_resolution(w: int, h: int) -> bool:
    if not _is_supported(w, h):
        return False
    s = load_settings()
    s["resolution_width"] = int(w)
    s["resolution_height"] = int(h)
    return save_settings(s)


def set_fullscreen(enabled: bool) -> bool:
    s = load_settings()
    s["fullscreen"] = bool(enabled)
    return save_settings(s)
