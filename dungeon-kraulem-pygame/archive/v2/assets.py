"""CRAWL PROTOCOL - Sprite/icon loader.

Same forgiveness contract as audio.py:

- Game runs with zero assets on disk.
- Missing icons return a procedural fallback Surface (a colored rect with
  the first letter of the key), so UI never crashes for missing art.
- Loaded Surfaces are cached.
"""
import os
from typing import Dict, Optional, Tuple

import pygame

from config import ICON_DIR


# ── Module state ──────────────────────────────────────────────────────────────

_cache: Dict[Tuple[str, int, int], pygame.Surface] = {}
_missing_keys_seen: set = set()
_warn_on_missing: bool = False


_ACCEPTED_EXTS = (".png", ".jpg", ".bmp", ".gif")


def set_warn_on_missing(flag: bool):
    global _warn_on_missing
    _warn_on_missing = bool(flag)


def _resolve(key: str) -> Optional[str]:
    if not ICON_DIR or not os.path.isdir(ICON_DIR):
        return None
    for ext in _ACCEPTED_EXTS:
        candidate = os.path.join(ICON_DIR, f"{key}{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


def _fallback(key: str, w: int, h: int) -> pygame.Surface:
    """Procedural fallback: colored rect derived from key hash + first letter."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # Deterministic color from key
    seed = sum(ord(c) for c in key) if key else 0
    r = 60 + (seed * 37) % 140
    g = 60 + (seed * 71) % 140
    b = 60 + (seed * 113) % 140
    pygame.draw.rect(surf, (r, g, b), surf.get_rect())
    pygame.draw.rect(surf, (220, 240, 255), surf.get_rect(), 1)
    if key:
        try:
            font = pygame.font.SysFont(None, max(10, int(h * 0.7)))
            img = font.render(key[0].upper(), True, (220, 240, 255))
            surf.blit(img, (
                (w - img.get_width()) // 2,
                (h - img.get_height()) // 2,
            ))
        except pygame.error:
            pass
    return surf


def load_icon(key: str, w: int = 32, h: int = 32) -> pygame.Surface:
    """
    Return a Surface for the given icon key, scaled to (w, h).
    Falls back to a procedural rect if the file does not exist.
    """
    cache_key = (key, w, h)
    if cache_key in _cache:
        return _cache[cache_key]

    path = _resolve(key)
    if path is None:
        if _warn_on_missing and key not in _missing_keys_seen:
            _missing_keys_seen.add(key)
            print(f"[assets] missing icon: {key}")
        surf = _fallback(key, w, h)
        _cache[cache_key] = surf
        return surf

    try:
        loaded = pygame.image.load(path).convert_alpha()
        if loaded.get_width() != w or loaded.get_height() != h:
            loaded = pygame.transform.smoothscale(loaded, (w, h))
        _cache[cache_key] = loaded
        return loaded
    except pygame.error:
        surf = _fallback(key, w, h)
        _cache[cache_key] = surf
        return surf


def has_icon(key: str) -> bool:
    return _resolve(key) is not None


def clear_cache():
    _cache.clear()
