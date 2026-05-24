"""Audio manager — silent if pygame.mixer or files unavailable."""
import os
from typing import Dict, Optional

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False

from .config import (AUDIO_ENABLED, MASTER_VOLUME, MUSIC_VOLUME, SFX_VOLUME,
                     SFX_DIR, MUSIC_DIR)


_initialized = False
_reason: Optional[str] = None
_sfx_cache: Dict[str, "pygame.mixer.Sound"] = {}
_current_music: Optional[str] = None


def init():
    global _initialized, _reason
    if _initialized or not _HAS_PYGAME or not AUDIO_ENABLED:
        if not _HAS_PYGAME:
            _reason = "pygame not installed"
        elif not AUDIO_ENABLED:
            _reason = "AUDIO_ENABLED=False"
        return
    try:
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except pygame.error:
            pass
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.set_volume(MASTER_VOLUME * MUSIC_VOLUME)
        _initialized = True
    except pygame.error as e:
        _reason = f"mixer init failed: {e}"


def is_ready() -> bool: return _initialized


def _candidate_dirs(directory: str):
    """Yield possible base dirs (handles PyInstaller bundling)."""
    base = getattr(__import__("sys"), "_MEIPASS", None)
    if base:
        yield os.path.join(base, directory)
    yield directory


def _find(directory: str, key: str, exts):
    for d in _candidate_dirs(directory):
        if not os.path.isdir(d):
            continue
        for ext in exts:
            cand = os.path.join(d, f"{key}{ext}")
            if os.path.isfile(cand):
                return cand
    return None


def play_sfx(key: str, volume_mod: float = 1.0):
    if not _initialized: return
    snd = _sfx_cache.get(key)
    if snd is None:
        p = _find(SFX_DIR, key, (".ogg",".wav"))
        if p is None: return
        try:
            snd = pygame.mixer.Sound(p)
            _sfx_cache[key] = snd
        except pygame.error:
            return
    try:
        snd.set_volume(MASTER_VOLUME * SFX_VOLUME * volume_mod)
        snd.play()
    except pygame.error:
        pass


def play_music(key: str, loop=True, fade_ms=400):
    global _current_music
    if not _initialized: return
    if _current_music == key: return
    p = _find(MUSIC_DIR, key, (".ogg",".mp3",".wav"))
    if p is None: return
    try:
        pygame.mixer.music.fadeout(fade_ms)
        pygame.mixer.music.load(p)
        pygame.mixer.music.set_volume(MASTER_VOLUME * MUSIC_VOLUME)
        pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=fade_ms)
        _current_music = key
    except pygame.error:
        pass
