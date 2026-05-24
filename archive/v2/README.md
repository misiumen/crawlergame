# CRAWL PROTOCOL — v2 (archived)

This is the **previous build** of the game (roguelite node-picker style with
a DAG room graph, fixed encounter pacing, and ~5 floors).

The current build lives one level up in `../../` and is launched with `PLAY.bat`
at the project root.

## Why this is here

Kept for reference and to preserve a playable copy of the v2 experience.
v2 was superseded by the persistent-floor exploration RPG (`revamp/` at the
project root).

## How to play v2

Double-click `PLAY.bat` inside this folder. It expects:

- Python 3.11+ on PATH
- `pygame` (auto-installs `pygame-ce` on first run)

## State of the v2 codebase

- UI, character creation, victory/defeat, character sheet, log header,
  combat hit/miss messages, room descriptions, and the narrator pool
  are routed through `lang.tr()` and resolve from `locales/pl.json` /
  `locales/en.json`.
- Item names, monster names, individual feature descriptions, and
  some inline strings in less-trafficked modules remain in English.
- Save files written by v2 use a different schema than the revamp build —
  saves are not portable between builds.

## What was here

The full v2 module set:

```
main.py           combat.py        rooms.py
character.py      monsters.py      features.py
classes.py        hybrids.py       items.py
dungeon.py        traps.py         mutations.py
merchant.py       narrator.py      parser.py
achievements.py   procgen.py       save_load.py
ui.py             utils.py         lang.py
audio.py          assets.py        config.py
dialog.py         npcs.py          environment.py
affinity.py       safehouses.py    races.py
locales/pl.json   locales/en.json
PLAY.bat
```
