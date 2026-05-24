# Prompt 08 — Mouse-only play layer

Add mouse-only play support without removing the text parser.

Goal:
The game should be playable with mouse only for common actions, while typed commands remain the strongest mode for deep improvisation.

Current observation:
The revamp currently has strong keyboard/text handling and Pygame UI drawing. It does not appear to have a button/click action layer yet.

Do not rewrite the UI.
Add a contextual clickable action layer.

## Required design

Mouse-only UI should support:
- main menu buttons
- character creation buttons
- clickable exits
- clickable visible objects
- clickable visible NPCs/crawlers/enemies
- contextual action buttons
- inventory/material/crafting buttons
- safehouse service buttons
- encounter resolution buttons
- common parser command buttons
- "suggested improvisations" generated from affordances

Typing remains available.

## New module

Create:
- revamp/ui_actions.py

Define:
ClickableAction:
- rect
- label
- command_text
- tooltip
- category
- enabled
- reason_disabled

Action categories:
- navigation
- inspect
- search
- object
- entity
- inventory
- safehouse
- encounter
- crafting
- system

The idea:
Mouse click should usually inject command_text into the existing input pipeline and submit it.
Example:
Button "Rozejrzyj się" -> command_text = "rozejrzyj się"
Button "Idź: północ" -> "idź północ"
Button "Sprawdź: kamera sponsora" -> "sprawdź kamerę sponsora"
Button "Pogadaj: ranny crawler" -> "pogadaj z rannym crawlerem"
Button "Zdemontuj: krzesło" -> "zdemontuj krzesło"

This preserves parser/validator/resolution.

## UI integration

Update ui.py:
- draw contextual action panel
- draw buttons with hover highlight
- draw disabled state
- draw tooltip if possible

Update game.py:
- handle MOUSEMOTION
- handle MOUSEBUTTONDOWN
- ask ui_actions for click target
- if clicked, execute command_text through the same submit pipeline

Do not duplicate game logic in mouse handlers.

## Contextual buttons

Always show:
- Pomoc
- Rozejrzyj się
- Przeszukaj
- Mapa
- Plecak
- Postać
- Zapisz

For exits:
- show buttons for visible/known exits

For visible objects:
- show inspect button
- show relevant affordance buttons:
  - open
  - loot
  - salvage
  - hack
  - repair
  - break
  - use

For visible entities:
- talk
- inspect
- attack only if context allows
- help if wounded
- trade if available

For safehouse:
- service buttons from safehouse services
- use bathroom
- buy coffee
- rest
- rumors
- rankings

For crafting:
- materials
- craft help
- known recipe buttons if crafting exists

## Suggested improvisations

Generate 3-5 suggestions from affordances when possible.

Examples:
- "Rzuć kubkiem w kamerę"
- "Zwab goblina do kwasu"
- "Zdemontuj przewody"
- "Ukryj się za ladą"
- "Pogadaj z crawlerem"

These are optional buttons; they simply send text commands.

## Mouse-only character creation

Character creation should not require typing except character name.
If possible, add:
- random name button
- background buttons
- start button

If name text is still needed, mouse-only can use default name.

## Testing

Run:
python -m py_compile revamp/*.py revamp/data/*.py
python main_revamp.py

Smoke-test:
1. start from title using mouse
2. start new game using mouse
3. choose background using mouse
4. use default/random name if supported
5. click look/search/map/inventory
6. click exit to move
7. click object inspect/salvage if available
8. click NPC talk if available
9. verify typed input still works

Report changed files and limitations.
