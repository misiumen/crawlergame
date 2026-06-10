# Dungeon Kraulem — Full-Game Plan

Agreed direction (2026-06-10): turn the mechanically-complete prototype into a
shippable game. Decisions locked with the owner:

- **Art**: CC0 packs (0x72 Dungeon Tileset / Kenney) as the base, restyled with
  palette shaders + lighting + biome recolors. Swappable for custom art later.
- **Season length**: tight **6 floors** (30–45 min runs); depth comes from
  meta-progression and harder NG+ seasons, not more floors.
- **Order of work**: A → B → C → D → E → F below.

## Phase A — Presentation foundation  ✅ (started 2026-06-10)
- [x] World/UI split: `BoardView` draws the board + entities in **world space**
      under a `Camera2D`; all screen-fixed UI is painted by `UIView` on a
      `CanvasLayer` via `_draw_ui(c)` (every UI draw func takes a CanvasItem).
- [x] Camera2D: smooth follow, framing, screen-shake on `camera.offset`.
- [x] F11 fullscreen; stretch mode `canvas_items` (resolution-independent).
- [x] `--smoke` autotest: windowed run through every panel's draw path, quits 0.
- [ ] InputMap actions for all keys (rebinding + controller groundwork) → with C.

## Phase B — The board comes alive  ✅ (2026-06-10)
- [x] **B.1 Biome identities**: all 20 routes have hand-set palettes, floor
      patterns (tiles/planks/hatch/rubble/cracks/dots/stripes/puddles), floor
      props (17 kinds) + wall décor (frames/pipes/neon/bars/posters), a biome
      accent frame + HUD badge, ambient colour grade + player light. All décor
      deterministic per (seed, depth, cell). `scenes/BiomeThemes.gd`.
- [x] **B.2 Entity identity**: 83 monster templates collapse into 7 readable
      silhouettes (humanoid/beast/bug/mech/spectral/elite/boss) with stable
      per-species hues; damage bars on hurt enemies.
- [x] **B.3 Juice**: attack lunges, movement bob, particle system (damage sparks
      by element, death bursts, sever spray, heal motes, spell glitter, convert
      bursts, fire-hazard embers), floor/room transition wipes.
- [x] **B.4 World lights**: fire hazards + safehouse glow (pooled PointLight2D),
      player light scaled by biome darkness.
- **Art direction call**: the clean procedural vector-neon style proved coherent
  and is the shipped look. An external tileset/sprite swap (0x72/Kenney) remains
  an OPTIONAL later upgrade — the theme system already carries palettes/props,
  so a swap is additive, not a rework.

## Phase C — UI/UX overhaul  ✅ (2026-06-10)
- [x] Shared `_panel()` chrome (shadow, header strip, accent spine) on all 10
      modals; monospace SystemFont (Cascadia/Consolas — full PL diacritics);
      vector icon set (`_draw_icon`) on HUD materials, spellbook, safehouse.
- [x] Character sheet **[C]**: vitals, stats+mods, equipment with **unequip**
      (the missing mechanic), origin/trait/magic, known spells, pocket list.
- [x] Pause + settings **[Esc]**: Master/Music/SFX volume steppers (live audio
      buses), fullscreen toggle, quit-to-title (keeps the checkpoint); persisted
      to `user://settings.json` and applied at boot.
- [x] Controller (board actions): dpad move, A interact, B wait, X craft,
      Y spellbook, RB class active, LB companion, Start pause.
- Deferred to the optional Control-node rebuild: gamepad MENU navigation and
  key rebinding UI (menus remain mouse/keyboard).

## Phase D — Audio  ✅ (2026-06-10)
- [x] Procedural synthesizer (`scenes/Sfx.gd`) — zero external assets: 31
      chiptune SFX (hits/crits, lootbox reel ticks→snap→jackpot, fanfares,
      chimes, casts, zaps, growls, stings, UI, Konferansjer text-blips) with
      pitch variance, rendered lazily and cached.
- [x] Four seeded generative music loops (title/explore/combat/boss) crossfaded
      by game state; Master/Music/SFX buses wired to the settings menu.

## Phase E — Content & balance
- Enemy roster per biome (sprites + AI quirks), miniboss per biome, more
  dialogue trees + mid-floor events, onboarding floor, run modifiers/daily seed,
  Preacher origin + fleshed-out origins.

## Phase F — Shell & shipping
- Title/settings/pause, save slots, playtest balancing, itch.io build (web
  export preset exists), trailer GIFs; Steam if it has legs (achievements map 1:1).

## Architecture invariants (do not break)
- `sim/` stays pure logic (RefCounted, no nodes) — the 600+ GUT checks guard it.
- Presentation consumes sim **events**; new visuals replace drawing, not rules.
- All player-facing text is Polish.
- Verification gate for every change: headless suite + `--smoke` windowed pass
  + exe rebuild.
