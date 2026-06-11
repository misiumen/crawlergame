# Shipping Dungeon Kraulem

How to cut a release. Player-facing text is Polish; this doc (like all docs) is English.

## 0. Pre-flight (every release)

1. Run the full gate from `dungeon-kraulem-godot/`:
   - all test suites: `Godot --headless --path . -s res://tests/test_<name>.gd` (each must end `0 failed`)
   - windowed autotest: `Godot --path . -- --smoke` (must print `SMOKE OK` with no SCRIPT ERROR lines)
2. Bump `VERSION` in `scenes/BoardView.gd` (shown bottom-right of the title screen).
3. Commit + push.

## 1. Windows exe

Run `dungeon-kraulem-godot/build.bat` (double-click works). Produces
`dungeon-kraulem-godot/DungeonKraulem.exe` (~100 MB, self-contained, no installer).
The exe is gitignored — distribute the file itself.

## 2. Web build (itch.io)

Run `dungeon-kraulem-godot/build-web.bat`. It exports to `builds/web/` and zips it
into `builds/dungeon-kraulem-web.zip`.

Prerequisite (one-time): the 4.6.3 export templates must be installed
(`%APPDATA%\Godot\export_templates\4.6.3.stable\`) — already done on this machine.

### itch.io upload

1. Create the project at itch.io → "Upload new project".
2. Kind of project: **HTML**.
3. Upload `builds/dungeon-kraulem-web.zip`, tick **"This file will be played in the browser"**.
4. Embed options: viewport **1280 × 720**, enable the fullscreen button.
5. **SharedArrayBuffer support: NOT required** — the Web preset exports with
   `variant/thread_support=false`, so leave itch's experimental
   SharedArrayBuffer toggle OFF. (If thread support is ever enabled in the
   preset, that toggle must go ON.)
6. Saves and settings live in browser IndexedDB (`user://` maps there) — they
   survive page reloads but not a cleared cache. Mention it on the page.

Local test before upload: `python -m http.server -d builds/web` then open
`http://localhost:8000` (file:// will not work).

### Optional: butler (CI-style pushes)

```
butler push builds/web <user>/dungeon-kraulem:html5 --userversion <VERSION>
butler push DungeonKraulem.exe <user>/dungeon-kraulem:windows --userversion <VERSION>
```

## 3. Known platform notes

- Web: audio starts after the first input (browser autoplay policy) — the title
  screen click/keypress unlocks it; nothing to do.
- Web: the daily run uses the PLAYER'S local date.
- Desktop: settings persist to `%APPDATA%\Godot\app_userdata\Dungeon Kraulem\settings.json`,
  the run checkpoint to `run.json`, meta-progression to `meta.json` + `achievements.json`.
