"""Image loader with procedural fallback."""
import os
from typing import Dict, Tuple

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False

from .config import IMAGE_DIR


_cache: Dict[Tuple[str,int,int], "pygame.Surface"] = {}


def _candidate_dirs():
    """Yield possible IMAGE_DIR locations (handles PyInstaller bundling)."""
    import sys as _sys
    base = getattr(_sys, "_MEIPASS", None)
    if base:
        yield os.path.join(base, IMAGE_DIR)
    yield IMAGE_DIR


def _resolve(key: str):
    for d in _candidate_dirs():
        if not os.path.isdir(d):
            continue
        for ext in (".png",".jpg",".bmp",".gif"):
            cand = os.path.join(d, f"{key}{ext}")
            if os.path.isfile(cand):
                return cand
    return None


def _fallback(key: str, w: int, h: int):
    if not _HAS_PYGAME:
        return None
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    seed = sum(ord(c) for c in key) if key else 0
    r = 60 + (seed * 37) % 140
    g = 60 + (seed * 71) % 140
    b = 60 + (seed * 113) % 140
    pygame.draw.rect(surf, (r,g,b), surf.get_rect())
    pygame.draw.rect(surf, (220,240,255), surf.get_rect(), 1)
    if key:
        try:
            font = pygame.font.SysFont(None, max(10, int(h * 0.7)))
            img = font.render(key[0].upper(), True, (220,240,255))
            surf.blit(img, ((w - img.get_width())//2, (h - img.get_height())//2))
        except pygame.error:
            pass
    return surf


def load_icon(key: str, w: int = 32, h: int = 32):
    if not _HAS_PYGAME:
        return None
    ck = (key, w, h)
    if ck in _cache:
        return _cache[ck]
    p = _resolve(key)
    if p is None:
        s = _fallback(key, w, h)
        _cache[ck] = s
        return s
    try:
        loaded = pygame.image.load(p).convert_alpha()
        if loaded.get_width() != w or loaded.get_height() != h:
            loaded = pygame.transform.smoothscale(loaded, (w, h))
        _cache[ck] = loaded
        return loaded
    except pygame.error:
        s = _fallback(key, w, h)
        _cache[ck] = s
        return s
