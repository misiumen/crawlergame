"""CRAWL PROTOCOL - Audio manager.

Wraps pygame.mixer with three guarantees:

1. The game keeps running even if pygame.mixer fails to initialize
   (no soundcard, dummy SDL driver, missing OS libs).
2. The game keeps running if every audio file is missing.
3. Call sites stay clean — `play_sfx("hit")` is all the rest of the code
   has to know.

Files searched:
    {SFX_DIR}/{key}.ogg   -> SFX (preloaded into pygame.mixer.Sound)
    {MUSIC_DIR}/{key}.ogg -> Music (streamed via pygame.mixer.music)

If a key is requested that has no file, the call is a silent no-op.
Useful while we develop without assets.
"""
import os
from typing import Dict, Optional

import pygame

from config import (AUDIO_ENABLED, MASTER_VOLUME, MUSIC_VOLUME, SFX_VOLUME,
                    SFX_DIR, MUSIC_DIR)


# ── Module state ──────────────────────────────────────────────────────────────

_initialized: bool = False
_disabled_reason: Optional[str] = None
_sfx_cache: Dict[str, "pygame.mixer.Sound"] = {}
_current_music: Optional[str] = None


# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    """
    Initialize the mixer if AUDIO_ENABLED and a sound device is available.
    Must be called *after* pygame.init() (or it auto-tries pre_init).
    Idempotent and forgiving — never raises.
    """
    global _initialized, _disabled_reason
    if _initialized:
        return
    if not AUDIO_ENABLED:
        _disabled_reason = "AUDIO_ENABLED=False"
        return

    try:
        # pre_init can be a no-op if mixer is already running; safe to call.
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        except pygame.error:
            pass

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.set_volume(MASTER_VOLUME * MUSIC_VOLUME)
        _initialized = True
    except pygame.error as e:
        _disabled_reason = f"mixer init failed: {e}"
        _initialized = False
    except Exception as e:
        _disabled_reason = f"mixer init crashed: {e}"
        _initialized = False


def is_ready() -> bool:
    return _initialized


def disabled_reason() -> Optional[str]:
    return _disabled_reason


# ── File resolution ───────────────────────────────────────────────────────────

_ACCEPTED_SFX_EXTS = (".ogg", ".wav")
_ACCEPTED_MUSIC_EXTS = (".ogg", ".mp3", ".wav")


def _resolve(directory: str, key: str, exts) -> Optional[str]:
    """Search for {key}.{ext} in directory. Return path or None."""
    if not directory or not os.path.isdir(directory):
        return None
    for ext in exts:
        candidate = os.path.join(directory, f"{key}{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


# ── SFX ───────────────────────────────────────────────────────────────────────

def preload_sfx(*keys: str) -> int:
    """Preload SFX into cache. Returns count successfully loaded."""
    if not _initialized:
        return 0
    loaded = 0
    for key in keys:
        if key in _sfx_cache:
            loaded += 1
            continue
        path = _resolve(SFX_DIR, key, _ACCEPTED_SFX_EXTS)
        if path is None:
            continue
        try:
            snd = pygame.mixer.Sound(path)
            snd.set_volume(MASTER_VOLUME * SFX_VOLUME)
            _sfx_cache[key] = snd
            loaded += 1
        except pygame.error:
            pass
    return loaded


def play_sfx(key: str, volume_mod: float = 1.0):
    """Play a one-shot SFX by key. No-op if mixer down or file missing."""
    if not _initialized:
        return
    snd = _sfx_cache.get(key)
    if snd is None:
        path = _resolve(SFX_DIR, key, _ACCEPTED_SFX_EXTS)
        if path is None:
            return
        try:
            snd = pygame.mixer.Sound(path)
            _sfx_cache[key] = snd
        except pygame.error:
            return
    try:
        snd.set_volume(MASTER_VOLUME * SFX_VOLUME * volume_mod)
        snd.play()
    except pygame.error:
        pass


# ── Music ─────────────────────────────────────────────────────────────────────

def play_music(key: str, loop: bool = True, fade_ms: int = 400):
    """Stream background music by key. No-op if mixer down or file missing."""
    global _current_music
    if not _initialized:
        return
    if _current_music == key:
        return
    path = _resolve(MUSIC_DIR, key, _ACCEPTED_MUSIC_EXTS)
    if path is None:
        return
    try:
        pygame.mixer.music.fadeout(fade_ms)
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(MASTER_VOLUME * MUSIC_VOLUME)
        pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=fade_ms)
        _current_music = key
    except pygame.error:
        pass


def stop_music(fade_ms: int = 400):
    global _current_music
    if not _initialized:
        return
    try:
        pygame.mixer.music.fadeout(fade_ms)
    except pygame.error:
        pass
    _current_music = None


def set_master_volume(value: float):
    """Adjust master volume at runtime. 0.0 - 1.0."""
    from config import MUSIC_VOLUME as MV, SFX_VOLUME as SV
    if not _initialized:
        return
    value = max(0.0, min(1.0, value))
    try:
        pygame.mixer.music.set_volume(value * MV)
        for snd in _sfx_cache.values():
            snd.set_volume(value * SV)
    except pygame.error:
        pass
