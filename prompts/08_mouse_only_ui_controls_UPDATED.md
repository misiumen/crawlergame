Add mouse-first / mouse-only play support to the CRAWL PROTOCOL revamp UI.

Do not remove typed commands.
Do not bypass the parser/validator/resolution pipeline.

Goal:
The player should be able to play most of the game using only the mouse, while typed commands remain available for improvisation.

Current known state:
- The game currently uses Pygame keyboard/text input.
- UI draws panels but likely lacks clickable action targets.
- Parser/validator/action pipeline is the authoritative gameplay route.

Design:
Clickable UI elements should generate the same text-like commands or ActionIntent inputs that typed commands use.

Example:
Clicking "Przeszukaj" should submit command:
"przeszukaj pokój"

Clicking object "Kamera sponsora" -> "sprawdź kamerę sponsora" or a context menu.

Do not create separate gameplay logic for mouse clicks.

============================================================
1. CLICK TARGET SYSTEM
============================================================

Create/update UI click system.

Add dataclass or simple structure:
ClickTarget:
- rect
- label
- command
- tooltip
- enabled
- category
- target_id
- action_key

UI should maintain a list of click_targets each frame.

Mouse events:
- MOUSEBUTTONDOWN left click:
  - if target clicked, submit target.command or call mapped action
- right click:
  - optional context menu for object/entity
- mouse wheel:
  - scroll log/panels if already supported

============================================================
2. ACTION BUTTONS
============================================================

Add visible action buttons based on current context.

Global:
- Rozejrzyj się
- Przeszukaj
- Mapa
- Ekwipunek
- Postać
- Materiały
- Zapisz
- Pomoc

Room movement:
- clickable exits:
  - Idź: północ
  - Idź: drzwi do łazienki
  - Wróć: korytarz

Visible objects:
For each visible entity/object, show clickable object row.
Click opens context actions, or shows quick buttons:
- Sprawdź
- Przeszukaj
- Otwórz
- Zdemontuj / Odzyskaj części if salvageable
- Użyj
- Napraw
- Hakuj
- Rozbij
- Weź if portable

Creatures/NPC/crawlers:
- Porozmawiaj
- Pomóż
- Handluj
- Zaatakuj
- Zignoruj
- Zastrasz
- Okradnij if context allows

Safehouse:
- Kup kawę
- Łazienka
- Prysznic
- Odpocznij
- Plotki
- Ranking
- Handel

Crafting/salvage:
- Materiały
- Crafting
- Pomoc craftingu
- If object salvageable: "Zdemontuj"
- If corpse harvestable: "Pozyskaj"

Memetics:
If context includes social/machine/crowd/broadcast targets:
- Zasiej plotkę
- Wydaj fałszywy rozkaz
- Przekonaj
- Zastrasz
- Wystąp do kamery
These may open a small prompt or insert prefilled command into input field because memetic actions often require custom text.

============================================================
3. CONTEXT MENUS
============================================================

Implement simple context menu if feasible.

Left-click object:
- select object
- show context panel with actions

Right-click object:
- context menu near cursor if easy

If context menu is too large, use side panel:
"Wybrano: Kamera sponsora"
Buttons:
- Sprawdź
- Zhakuj
- Rozbij
- Wystąp do kamery
- Zdemontuj

============================================================
4. DO NOT OVERREVEAL HIDDEN INFO
============================================================

Mouse UI must not reveal hidden room types or hidden objects.

Only show:
- visible/discovered objects
- known exits
- known NPCs
- known services
- known clues

If an object is hidden, no clickable target until discovered.

============================================================
5. MOUSE-ONLY SUPPORT FOR IMPROVISATION
============================================================

Mouse-only cannot cover every possible custom phrase, but it can support structured improvisation.

Add optional "Improwizuj..." button.
Clicking it should:
- focus text input, or
- open a simple prompt/prefill:
  "Próbuję..."
This is still typed, but the rest of game remains mouse playable.

For strict mouse-only, add preset improvisation categories:
- Użyj otoczenia
- Odwróć uwagę
- Zwab
- Zasiej plotkę
- Zbuduj coś
- Zdemontuj coś
- Pomóż komuś
- Zdradź kogoś

These generate generic commands using selected object/target:
- "użyj otoczenia przeciwko [target]"
- "odwróć uwagę [target] używając [object]"
- "zdemontuj [object]"
- "zrób pułapkę z dostępnych materiałów"

The validator may reject if context lacks objects/materials.

============================================================
6. TOOLTIP / FEEDBACK
============================================================

When hovering a button:
- show tooltip
- do not expose hidden mechanics
- show if disabled and why:
  "Brak widocznych obiektów do odzyskania."
  "Nie jesteś w safehouse."
  "Nie masz materiałów."

============================================================
7. SETTINGS
============================================================

Add setting:
MOUSE_MODE = True

Optional:
- large buttons mode
- button font scaling

============================================================
8. TESTING
============================================================

Run:

python -m py_compile revamp/*.py revamp/data/*.py

Then run:

python main_revamp.py

Manual test:
1. Start game using mouse if possible.
2. Click New Game / choose background if UI supports it.
3. In play state, click "Rozejrzyj się".
4. Click an exit to move.
5. Click object -> inspect.
6. Click salvageable object -> salvage.
7. Click materials.
8. Click safehouse service if in safehouse.
9. Click NPC/crawler action if visible.
10. Verify typed commands still work.
11. Verify no hidden object appears as click target.
12. Save/load.

Report:
- files changed
- mouse controls added
- how click targets work
- actions still routed through parser/validator
- limitations
