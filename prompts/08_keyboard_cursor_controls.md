# 08_keyboard_cursor_controls.md

Add keyboard cursor / menu navigation controls to the revamp UI.

Do not add mouse-only controls in this step.
Do not rewrite the whole game.
Do not bypass the parser / validator / resolution pipeline.

Context:
The game currently appears to support mostly:
- text commands
- Enter / Backspace / Escape
- number keys for menu choices, likely 1-5 or similar

Goal:
The player should be able to play comfortably with keyboard navigation:
- arrow keys
- Enter
- Escape
- Tab / Shift+Tab
- optional hotkeys
while preserving free-text input for improvisation.

The intended design is:
- text input remains the strongest mode for creative actions
- cursor navigation helps with common actions, menus, inventory, known exits, visible entities, and contextual options
- selected UI options should submit generated commands into the existing parser pipeline, not directly mutate game state

============================================================
DESIGN PRINCIPLES
============================================================

1. Keep typed commands.
The player must still be able to write natural commands.

2. Add cursor navigation as an accessibility / comfort layer.
Arrow keys should select visible options.

3. Do not create a separate logic path.
When a player selects "Przeszukaj pokój" with arrows and presses Enter, the game should internally submit the same command as typed text:
"przeszukaj pokój"

4. All selected actions must go through:
parser_core -> validation -> resolution -> consequences

5. UI should not reveal hidden information.
Cursor-selectable actions may only target visible/known objects, known exits, known NPCs, visible items, and currently available options.

6. The UI should support Polish labels first.

============================================================
CONTROL SCHEME
============================================================

Global controls:

- Up / Down:
  Move selection through current option list.

- Left / Right:
  Switch option group if multiple groups exist:
  examples:
  - Actions
  - Exits
  - Objects
  - NPCs
  - Inventory
  - Crafting
  - Journal/Map if visible

- Enter:
  Activate selected option.

- Escape:
  Back / cancel / close popup / return to previous mode.

- Tab:
  Cycle focus group forward.

- Shift+Tab:
  Cycle focus group backward.

- PageUp / PageDown:
  Scroll log or long text if supported.

- Home / End:
  Jump to first/last option if simple to implement.

- Ctrl+S:
  Save game if safe.

- F1 or ?:
  Help / controls summary.

- Slash "/" or "T":
  Focus text command input.

- M:
  Map / mapa.

- I:
  Inventory / ekwipunek.

- C:
  Character sheet / postać.

- J:
  Journal / dziennik if implemented.

- R:
  Rest / odpocznij if valid in current context.

Do not require all hotkeys if the UI cannot support them cleanly, but implement arrows, Enter, Escape, Tab, text focus at minimum.

============================================================
UI OPTION GROUPS
============================================================

Create a small UI navigation model.

Recommended structure:

SelectableOption:
- option_id
- label
- command
- group
- enabled
- tooltip
- hotkey
- target_id optional
- action_type optional

UISelectionState:
- groups: list[str]
- current_group_index
- selected_index_by_group
- options_by_group

The game/UI should build contextual options each frame or whenever state changes.

Option groups:

1. Basic Actions
Examples:
- Rozejrzyj się
  command: "rozejrzyj się"

- Przeszukaj pokój
  command: "przeszukaj pokój"

- Nasłuchuj
  command: "nasłuchuj"

- Czekaj
  command: "czekaj"

- Odpocznij
  only if context allows

2. Exits
For each known exit:
- Idź: północ
  command: "idź północ"

- Wróć: startowy korytarz
  command: "idź [exit label or room id understood by parser]"

Do not show exits that are hidden/unknown.

3. Visible Objects
For each visible object:
- Sprawdź: kamera sponsora
  command: "sprawdź kamerę sponsora"

- Przeszukaj: ciało
  command: "przeszukaj ciało"

- Zdemontuj: kamera
  command: "zdemontuj kamerę"
  only if object appears salvageable

- Rozstaw przy: drzwi
  if deployable item selected or context supports it

4. Visible Entities / NPCs / Crawlers
For each visible entity:
- Pogadaj: ranny crawler
  command: "pogadaj z rannym crawlerem"

- Pomóż: ranny crawler
  command: "pomóż rannemu crawlerowi"

- Zaatakuj: goblin
  command: "zaatakuj goblina"

- Zastrasz: crawler
  command: "zastrasz crawlera"

Only show contextually plausible options.

5. Inventory
- Użyj: mały medkit
  command: "użyj małego medkitu"

- Sprawdź: item
  command: "sprawdź [item]"

- Rozstaw: tripwire_trap
  command: "rozstaw tripwire_trap"

6. Crafting / Materials
If crafting exists:
- Materiały
  command: "materiały"

- Pomoc craftingu
  command: "pomoc craftingu"

- Crafting
  command: "crafting"

- Known recipe options if available:
  command: "zrób [recipe name]"

Do not overcrowd the list. Prefer showing top relevant options plus help.

7. Encounter Options
If an encounter is active:
- Walcz
- Uciekaj
- Negocjuj
- Zastrasz
- Pomóż
- Zignoruj
- Użyj otoczenia
- Użyj przedmiotu
Only if validator/context says it is plausible or known.

The actual selected command must still be validated.

============================================================
TEXT INPUT FOCUS
============================================================

Because the game relies on natural language input, implement clear focus behavior.

Modes:
- navigation mode
- text input mode

In navigation mode:
- arrows move selection
- Enter activates selected option
- typing normal letters may either focus input or do nothing depending existing UI

In text input mode:
- keyboard enters text as now
- Enter submits typed command
- Escape exits text mode or clears input
- Up/Down may optionally navigate command history, not UI selection

Provide a visible indicator:
- "Tryb: komendy tekstowe"
- "Tryb: wybór opcji"

Optional:
Press "/" or "T" to enter text input mode.
Press Escape to return to navigation mode.

Do not break existing typing behavior.
If uncertain, keep text input always available and allow arrows to work only when input is empty.

============================================================
MENU AND POPUP NAVIGATION
============================================================

Apply cursor navigation to:
- main menu
- character creation
- background selection
- class offer
- species offer
- dialogue choices
- crafting menu if exists
- inventory/materials menu if exists
- confirmation popups

For any numbered menu:
- keep number keys working
- add arrow selection
- Enter confirms
- Escape cancels/back

============================================================
COMMAND SUBMISSION
============================================================

Implement helper:

submit_generated_command(command: str)

It should:
- set input_text or bypass visible text safely
- pass command through the same submit_input / parser path used by typed commands
- log the command optionally:
  "> przeszukaj pokój"
- not directly call consequences

This prevents duplicate logic.

============================================================
VISUAL FEEDBACK
============================================================

Update ui.py to show selected option clearly.

Possible styling:
- selected option marker: ">"
- highlight rectangle
- inverted color
- brighter text

Do not require new image assets.

If UI is cramped:
- show only current group
- show group name
- allow Left/Right or Tab to switch groups

Example:

[Akcje]
> Rozejrzyj się
  Przeszukaj pokój
  Nasłuchuj

[Wyjścia]
  Północny korytarz
  Drzwi z symbolem toalety

============================================================
LOCALIZATION
============================================================

Add Polish/English localization keys if localization is used:
- controls.help
- controls.navigation_mode
- controls.text_mode
- controls.press_enter
- controls.press_escape
- controls.group.actions
- controls.group.exits
- controls.group.objects
- controls.group.entities
- controls.group.inventory
- controls.group.crafting
- controls.no_options

Polish labels should be natural:
- Akcje
- Wyjścia
- Obiekty
- Postacie
- Ekwipunek
- Crafting
- Materiały
- Tryb wyboru
- Tryb komend

============================================================
TESTING
============================================================

Run:
python -m py_compile revamp/*.py revamp/data/*.py

Then run:
python main_revamp.py

Manual tests:

1. Main menu:
- Up/Down changes selected option.
- Enter starts game.
- Number keys still work if they did before.

2. Character creation:
- Up/Down selects background.
- Enter confirms.
- Escape backs out if supported.
- Text input for name still works.

3. Play state:
- Arrow keys select "Rozejrzyj się" / "Przeszukaj pokój" / exits / objects.
- Enter activates option.
- The action goes through parser/validator/resolution.
- Hidden objects are not shown.
- Text commands still work.

4. Inventory/crafting:
- If available, selectable inventory actions work.
- Materials/crafting help can be opened.

5. Combat/encounter:
- Arrow keys select visible options.
- Fight/flee/talk/use item options work through parser.

6. Save/load:
- controls do not break saved state.

Report:
- files changed
- new controls
- how option groups are generated
- whether text input remains available
- known limitations
