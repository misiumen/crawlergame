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

## Phase B — The board comes alive (next)
- TileMapLayer floors/walls/props per biome (autotiling), entity sprites with
  idle/walk/attack/death frames, 2D lights + occluders (fire glows, dark halls),
  tweened movement, hit-stop, particles (sparks/blood/confetti), floor wipes.
- Asset base: 0x72 Dungeon Tileset II (CC0) + Kenney; biome palettes via shader.

## Phase C — UI/UX overhaul
- All modals → themed Control panels; icons (materials/items/spells/tiers);
  character sheet; real minimap; pixel font with Polish diacritics; full
  mouse/keyboard/controller navigation; InputMap rebinding.

## Phase D — Audio
- SFX set (hits, salvage, reel, UI), per-biome music + title + boss theme,
  combat-intensity mixing, Konferansjer text-blips.

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
