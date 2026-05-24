# Dungeon Kraulem — Systems Addendum: Salvage, Improvised Crafting, Memetics, Mouse-Only Play

This addendum extends `docs/CONTENT_BIBLE.md`.

## Design rule

The game is a persistent floor-survival RPG. The player should be able to treat the dungeon as a physical, social and symbolic environment, not as a menu of prewritten options.

Three new pillars:

1. **Salvage and looting**
   The dungeon is made of usable material. Furniture, corpses, machines, bathroom fixtures, cameras, vending machines, monster remains and debris can be searched, looted, stripped, harvested, dismantled or broken down when context allows.

2. **Improvised crafting**
   Materials are not just currencies. They have tags. Players can combine materials creatively into traps, tools, weapons, distractions, bait, disguises, repairs and utility items.

3. **Memetic/social-engineering effects**
   Players can seed ideas, rumors, false beliefs, logic traps, symbolic claims or panic into NPC/crawler/enemy groups. These ideas can persist, distort, spread and later affect encounters, rumors and floor events.

## Salvage principle

Do not make every object infinitely farmable. Every salvageable object must have state:

- intact
- searched
- looted
- stripped
- damaged
- depleted
- destroyed

Safehouse property can be stolen or salvaged only with consequences.

## Crafting principle

Crafting has two levels:

1. Known recipes.
2. Improvised tag-based crafting.

If a player says:

> zrób pułapkę z kabli, szkła i baterii

The engine should not require an exact recipe. It should inspect material tags:

- wire / binding
- sharp
- power / electrical

Then it can produce an improvised trap if validation passes.

## Memetic principle

Memetic effects are not factions. They are persistent ideas in the world.

Examples:

- convincing machines that someone stole their hearts
- spreading a false rumor that a boss is vulnerable to mirrors
- making crawlers believe a safehouse bathroom is a holy site
- convincing goblins that cameras steal names
- making sponsor drones search lootboxes for missing parts

A memetic effect should have:

- origin text
- target tags
- core claim
- emotional or logic hook
- spread channels
- strength
- stability
- distortion
- stage
- effects
- consequences

## Mouse-only play principle

The player should be able to play without typing, but typing remains the strongest mode.

Mouse-only should offer:

- common action buttons
- contextual object/entity buttons
- exit navigation buttons
- inventory/material/crafting buttons
- safehouse service buttons
- encounter resolution buttons
- suggested improvisation buttons

Mouse-only does not need to cover every possible creative sentence. It should cover the common viable actions and allow generated suggestions from affordances.
