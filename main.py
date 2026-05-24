"""CRAWL PROTOCOL v2 - Entry point."""
import sys

# Check pygame before anything else
try:
    import pygame
except ImportError:
    print("pygame is required. Run: pip install pygame")
    sys.exit(1)

from config import SCREEN_W, SCREEN_H, FPS, TITLE, LANGUAGE, LANG_DEBUG_MISSING
import lang
import audio


def main():
    # Initialize localization before anything renders.
    lang.set_debug_missing(LANG_DEBUG_MISSING)
    lang.set_language(LANGUAGE)

    pygame.init()
    pygame.display.set_caption(TITLE)

    # Initialize audio after pygame.init(); safe no-op if no soundcard.
    audio.init()
    audio.preload_sfx(
        "hit", "miss", "crit", "level_up", "box_open", "room_enter",
        "button_click", "dialog_start", "door_close",
        "item_pickup", "dice_roll",
    )
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

    # Enable key repeat for text editing
    pygame.key.set_repeat(400, 50)

    from game import Game
    game = Game(screen)

    clock = pygame.time.Clock()

    while True:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                game.handle_keydown(event)

            elif event.type == pygame.TEXTINPUT:
                game.handle_textinput(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_mouseclick(event.pos, event.button)

            elif event.type == pygame.MOUSEMOTION:
                game.handle_mousemotion(event.pos)

            elif event.type == pygame.MOUSEWHEEL:
                game.handle_mousewheel(event.y)

        game.update(dt)
        game.draw()


if __name__ == "__main__":
    main()
