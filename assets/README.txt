CRAWL PROTOCOL - Assets
=======================

Drop optional audio and image files here. The game runs perfectly fine
without any of them. If a file is missing, the corresponding sound/sprite
is silently skipped or replaced with a procedural fallback.

assets/sfx/<key>.ogg       - one-shot sound effects
assets/music/<key>.ogg     - background music tracks
assets/icons/<key>.png     - small UI icons (32x32 recommended)

Accepted extensions:
    SFX:    .ogg  .wav
    Music:  .ogg  .mp3  .wav
    Icons:  .png  .jpg  .bmp  .gif

Suggested SFX keys (no audio = silence):
    hit, miss, crit, level_up, box_open, room_enter, button_click,
    dialog_start, door_close, footstep, item_pickup, dice_roll

Suggested music keys:
    title, explore, combat, safehouse, victory, defeat

Suggested icon keys:
    room_combat, room_trap, room_treasure, room_rest, room_merchant,
    room_lore, room_mutation, room_checkpoint, room_boss, room_start,
    weapon, armor, consumable, trinket, credits, hp, audience

Use chiptune / 8-bit style for music to match the game tone.
