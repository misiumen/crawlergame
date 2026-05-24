"""Revamp entry point.

Run with:
    python main_revamp.py
or:
    python -m revamp.main_revamp
"""
import sys


def main():
    try:
        import pygame
    except ImportError:
        print("pygame is required. Run: pip install pygame-ce")
        sys.exit(1)

    from .ui import lang
    from .ui import audio
    from .ui import settings as _settings
    from . import config as _config
    from .config import (FPS, TITLE, LANGUAGE, LANG_DEBUG_MISSING)

    lang.set_debug_missing(LANG_DEBUG_MISSING)
    lang.set_language(LANGUAGE)

    pygame.init()
    pygame.display.set_caption(TITLE)
    # Prompt 09: pull resolution + fullscreen from persisted settings, with
    # graceful fallback to DEFAULT_RESOLUTION on missing/corrupt file.
    s = _settings.load_settings()
    w, h = s["resolution_width"], s["resolution_height"]
    flags = pygame.FULLSCREEN if s.get("fullscreen") else 0
    try:
        screen = pygame.display.set_mode((w, h), flags)
    except pygame.error:
        from .config import DEFAULT_RESOLUTION
        screen = pygame.display.set_mode(DEFAULT_RESOLUTION)
    pygame.key.set_repeat(400, 50)

    audio.init()

    # Prompt 13: apply the persisted LLM mode + emit one short startup
    # diagnostic line. No HTTP calls happen here unless a role is enabled.
    saved_mode = s.get("llm_mode", "performance")
    _config.apply_llm_mode(saved_mode)
    from .llm import llm_roles
    info = llm_roles.summary()
    if info["mode"] == "performance":
        print(f"[revamp] LLM mode: performance (no model required)")
    else:
        enabled = [r for r, rd in info["roles"].items() if rd["enabled"]]
        present = [r for r, rd in info["roles"].items() if rd["available"]]
        print(f"[revamp] LLM mode: {info['mode']} | "
              f"reachable={info['ollama_reachable']} | "
              f"enabled={enabled} | available={present}")

    from .engine.game import Game
    g = Game(screen)
    clock = pygame.time.Clock()

    while True:
        dt = clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif ev.type == pygame.KEYDOWN:
                g.handle_keydown(ev)
            elif ev.type == pygame.TEXTINPUT:
                g.handle_textinput(ev)
        g.update(dt)
        g.draw()


if __name__ == "__main__":
    main()
