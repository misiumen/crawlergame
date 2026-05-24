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

    from . import lang, audio, settings as _settings
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

    # Check optional Ollama daemon presence — print one informational line
    from .config import USE_OLLAMA
    if USE_OLLAMA:
        from . import llm_parser
        print("[revamp] Ollama parser:",
              "available" if llm_parser.is_available() else "unavailable, falling back to deterministic")

    from .game import Game
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
