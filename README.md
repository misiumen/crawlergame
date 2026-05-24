# CRAWL PROTOCOL

Polish-first text/Pygame dungeon survival RPG, dark-comedic LitRPG flavor.
Private, non-commercial fan project.

## Play

Double-click `PLAY.bat`.

It auto-installs `pygame-ce` if missing, then launches the game.

## Make a standalone .exe

One-time:
```
pip install pyinstaller pygame-ce
```

Then double-click `build_exe.bat`. Output: `dist/CrawlProtocol.exe`
(single file, ~30-60 MB, runs on any Windows machine without Python).

## Project layout

```
main.py            -- entry point that launches the revamp build
PLAY.bat           -- double-click launcher
build_exe.bat      -- one-shot PyInstaller bundler
revamp/            -- the current game build (persistent-floor RPG)
  data/            -- Floor / entity / item templates
  locales/         -- pl.json (primary), en.json (fallback)
  *.py             -- core engine
assets/            -- optional .ogg music/SFX, optional .png icons
                    (game runs silent with empty assets/)
archive/v2/        -- previous v2 build (roguelite node-picker style).
                    Self-contained — can be run from inside that folder
                    with its own PLAY.bat. Kept for reference only;
                    not part of normal play.
```

## Run from source

```
python main.py
```

To force English:

```
# edit revamp/config.py
LANGUAGE = "en"
```

## Optional: Ollama parser

The revamp supports an optional local LLM fallback for unusual commands.
Off by default. To enable, install [Ollama](https://ollama.com), pull
`qwen2.5:3b`, and set `USE_OLLAMA = True` in `revamp/config.py`.
The game still runs deterministically if Ollama is unreachable.
