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
    # Prompt 22: pick the monitor explicitly. By default the game opens
    # on the primary display (index 0); the user can override
    # `monitor_index` in dungeon_kraulem_settings.json. Without this,
    # SDL would place the window on whichever monitor the cursor
    # happens to be on or wherever Windows last remembered — which is
    # why playtesters saw the game open on monitor 2.
    monitor = int(s.get("monitor_index", 0) or 0)
    try:
        num_displays = pygame.display.get_num_displays()
    except Exception:
        num_displays = 1
    if monitor < 0 or monitor >= num_displays:
        if monitor != 0:
            print(f"[dungeon_kraulem] monitor_index={monitor} out of range "
                  f"(0..{num_displays-1}); falling back to primary.")
        monitor = 0
    try:
        screen = pygame.display.set_mode((w, h), flags, display=monitor)
    except (pygame.error, TypeError):
        # Older pygame builds don't accept `display=` kwarg — retry
        # without it and let SDL choose. Or set_mode failed for some
        # other reason: try the default resolution as a last resort.
        try:
            screen = pygame.display.set_mode((w, h), flags)
        except pygame.error:
            from .config import DEFAULT_RESOLUTION
            screen = pygame.display.set_mode(DEFAULT_RESOLUTION)
    pygame.key.set_repeat(400, 50)

    audio.init()

    # P27 — LLM mode permanently defaulted to performance for the
    # itch.io release (no local-model download requirement). The mode
    # field is still respected internally; only the startup probe + log
    # line are removed so a fresh game doesn't ping anything on launch.
    # Re-enable by setting `llm_mode` to enhanced/full_show manually in
    # dungeon_kraulem_settings.json and adding back this block.
    _config.apply_llm_mode("performance")

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
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                g.handle_mousedown(ev)
            elif ev.type == pygame.MOUSEMOTION:
                g.handle_mousemotion(ev)
        g.update(dt)
        g.draw()


if __name__ == "__main__":
    main()
