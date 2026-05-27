"""P29.17 — Procedural icon generator.

The icon system (ui/assets.py:load_icon) was wired in P27 but
assets/images/ shipped empty — every call rendered the random-color
key-letter fallback. P29.17 ships 16 simple 32×32 PNG icons that
match the keys load_icon recognises:

  room_combat   room_trap     room_treasure  room_rest
  room_merchant room_lore     room_boss      room_start
  room_pod      room_safehouse
  weapon        armor         consumable     trinket
  credits       hp            audience

The icons are pure pygame.draw geometry — circles, polygons, lines.
No image dependencies, no font work. Each rendered onto a SRCALPHA
surface with a 2px rounded border + a glyph in the center using a
limited palette that matches the broadcast-terminal aesthetic.

Re-run with `python -m dungeon_kraulem.tools.synthesize_icons` to
regenerate every file. Idempotent — overwrites in place.
"""
from __future__ import annotations
import os

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False

ICON_DIR = os.path.join("assets", "images")
SIZE = 32

# Broadcast-terminal palette — matches the title screen tones.
COL_BG_DARK     = (16, 20, 28, 255)
COL_BG_LIGHT    = (28, 36, 48, 255)
COL_BORDER      = (140, 200, 230, 255)
COL_RED         = (220, 80, 80, 255)
COL_GREEN       = (140, 220, 160, 255)
COL_YELLOW      = (230, 200, 120, 255)
COL_ORANGE      = (230, 160, 100, 255)
COL_PURPLE      = (190, 150, 220, 255)
COL_GRAY        = (180, 190, 210, 255)
COL_GOLD        = (230, 210, 130, 255)
COL_WHITE       = (240, 240, 240, 255)


def _new_surf() -> "pygame.Surface":
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    s.fill(COL_BG_DARK)
    # Slight inner gradient via a lighter box (cheap chiptune feel).
    pygame.draw.rect(s, COL_BG_LIGHT, (2, 2, SIZE - 4, SIZE - 4))
    pygame.draw.rect(s, COL_BORDER, (1, 1, SIZE - 2, SIZE - 2), 1)
    return s


# ── Room icons ──────────────────────────────────────────────────────────

def icon_room_combat():
    s = _new_surf()
    # Crossed swords.
    pygame.draw.line(s, COL_RED, (8, 8), (24, 24), 3)
    pygame.draw.line(s, COL_RED, (8, 24), (24, 8), 3)
    pygame.draw.circle(s, COL_WHITE, (16, 16), 2)
    return s


def icon_room_trap():
    s = _new_surf()
    # Spike pit — three triangles from the bottom.
    for x in (8, 16, 24):
        pygame.draw.polygon(s, COL_ORANGE,
                            [(x - 4, 26), (x + 4, 26), (x, 12)])
    pygame.draw.line(s, COL_BORDER, (4, 26), (28, 26), 1)
    return s


def icon_room_treasure():
    s = _new_surf()
    # Chest with a lid.
    pygame.draw.rect(s, COL_GOLD, (6, 14, 20, 14))
    pygame.draw.rect(s, COL_YELLOW, (6, 10, 20, 6))
    pygame.draw.rect(s, COL_BG_DARK, (15, 19, 2, 4))   # keyhole
    pygame.draw.line(s, COL_BG_DARK, (6, 16), (26, 16), 1)
    return s


def icon_room_rest():
    s = _new_surf()
    # Bed / pillow profile + crescent moon.
    pygame.draw.rect(s, COL_GRAY, (5, 20, 22, 6))
    pygame.draw.rect(s, COL_WHITE, (7, 17, 10, 5))
    pygame.draw.circle(s, COL_YELLOW, (22, 10), 5)
    pygame.draw.circle(s, COL_BG_LIGHT, (24, 9), 4)
    return s


def icon_room_merchant():
    s = _new_surf()
    # Stylized "$" — coin stack.
    pygame.draw.circle(s, COL_GOLD, (16, 16), 9, 2)
    pygame.draw.line(s, COL_GOLD, (16, 8), (16, 24), 2)
    pygame.draw.line(s, COL_GOLD, (12, 12), (20, 12), 2)
    pygame.draw.line(s, COL_GOLD, (12, 20), (20, 20), 2)
    return s


def icon_room_lore():
    s = _new_surf()
    # Open book.
    pygame.draw.polygon(s, COL_WHITE,
                        [(6, 10), (16, 14), (26, 10), (26, 24), (16, 28), (6, 24)])
    pygame.draw.line(s, COL_BORDER, (16, 14), (16, 28), 1)
    for y in (17, 20, 23):
        pygame.draw.line(s, COL_GRAY, (8, y), (15, y + 1), 1)
        pygame.draw.line(s, COL_GRAY, (17, y + 1), (24, y), 1)
    return s


def icon_room_boss():
    s = _new_surf()
    # Skull silhouette.
    pygame.draw.circle(s, COL_WHITE, (16, 14), 8)
    pygame.draw.rect(s, COL_WHITE, (12, 20, 8, 5))
    pygame.draw.circle(s, COL_BG_DARK, (13, 14), 2)
    pygame.draw.circle(s, COL_BG_DARK, (19, 14), 2)
    pygame.draw.line(s, COL_BG_DARK, (15, 22), (15, 25), 1)
    pygame.draw.line(s, COL_BG_DARK, (17, 22), (17, 25), 1)
    return s


def icon_room_start():
    s = _new_surf()
    # Door silhouette + arrow.
    pygame.draw.rect(s, COL_GREEN, (10, 6, 12, 20))
    pygame.draw.rect(s, COL_BG_DARK, (13, 14, 2, 4))
    pygame.draw.line(s, COL_WHITE, (4, 16), (10, 16), 2)
    pygame.draw.polygon(s, COL_WHITE,
                        [(10, 13), (10, 19), (13, 16)])
    return s


def icon_room_pod():
    s = _new_surf()
    # Sponsor drop pod — capsule with a star.
    pygame.draw.ellipse(s, COL_PURPLE, (8, 6, 16, 22))
    pygame.draw.ellipse(s, COL_BORDER, (8, 6, 16, 22), 1)
    pygame.draw.polygon(s, COL_YELLOW,
                        [(16, 12), (18, 17), (22, 17),
                         (19, 20), (20, 24), (16, 22),
                         (12, 24), (13, 20), (10, 17), (14, 17)])
    return s


def icon_room_safehouse():
    s = _new_surf()
    # House silhouette.
    pygame.draw.polygon(s, COL_GREEN,
                        [(6, 18), (16, 8), (26, 18), (26, 26), (6, 26)])
    pygame.draw.rect(s, COL_BG_DARK, (14, 18, 4, 8))    # door
    pygame.draw.rect(s, COL_YELLOW, (9, 20, 3, 3))      # window
    return s


# ── Inventory / stat icons ──────────────────────────────────────────────

def icon_weapon():
    s = _new_surf()
    # Sword pointing up-right.
    pygame.draw.line(s, COL_GRAY, (6, 26), (24, 8), 4)
    pygame.draw.line(s, COL_WHITE, (7, 26), (23, 9), 1)
    pygame.draw.line(s, COL_YELLOW, (4, 24), (12, 16), 3)  # crossguard
    pygame.draw.circle(s, COL_GOLD, (6, 26), 2)             # pommel
    return s


def icon_armor():
    s = _new_surf()
    # Shield.
    pygame.draw.polygon(s, COL_GRAY,
                        [(16, 5), (26, 9), (24, 22), (16, 28),
                         (8, 22), (6, 9)])
    pygame.draw.polygon(s, COL_BORDER,
                        [(16, 5), (26, 9), (24, 22), (16, 28),
                         (8, 22), (6, 9)], 2)
    # Cross in center.
    pygame.draw.line(s, COL_RED, (16, 11), (16, 22), 2)
    pygame.draw.line(s, COL_RED, (11, 16), (21, 16), 2)
    return s


def icon_consumable():
    s = _new_surf()
    # Potion bottle — neck + bulb.
    pygame.draw.rect(s, COL_GRAY, (13, 6, 6, 5))     # neck
    pygame.draw.rect(s, COL_BG_DARK, (13, 4, 6, 3))  # cap
    pygame.draw.ellipse(s, COL_RED, (8, 11, 16, 17))
    pygame.draw.ellipse(s, COL_BORDER, (8, 11, 16, 17), 1)
    # Bubble.
    pygame.draw.circle(s, COL_WHITE, (13, 16), 2)
    return s


def icon_trinket():
    s = _new_surf()
    # Amulet — chain + gemstone.
    pygame.draw.line(s, COL_GOLD, (10, 6), (16, 14), 2)
    pygame.draw.line(s, COL_GOLD, (22, 6), (16, 14), 2)
    pygame.draw.polygon(s, COL_PURPLE,
                        [(16, 14), (22, 20), (16, 28), (10, 20)])
    pygame.draw.polygon(s, COL_BORDER,
                        [(16, 14), (22, 20), (16, 28), (10, 20)], 1)
    pygame.draw.line(s, COL_WHITE, (13, 18), (16, 22), 1)
    return s


def icon_credits():
    s = _new_surf()
    # Stack of coins.
    for i, y in enumerate((20, 16, 12)):
        pygame.draw.ellipse(s, COL_GOLD, (6, y, 20, 6))
        pygame.draw.ellipse(s, COL_BORDER, (6, y, 20, 6), 1)
    # Top coin highlight.
    pygame.draw.line(s, COL_WHITE, (10, 14), (22, 14), 1)
    return s


def icon_hp():
    s = _new_surf()
    # Heart.
    pygame.draw.circle(s, COL_RED, (11, 13), 6)
    pygame.draw.circle(s, COL_RED, (21, 13), 6)
    pygame.draw.polygon(s, COL_RED,
                        [(5, 14), (27, 14), (16, 28)])
    # Highlight.
    pygame.draw.circle(s, COL_WHITE, (10, 11), 1)
    return s


def icon_audience():
    s = _new_surf()
    # Three stick-figure heads (silhouette crowd).
    for cx, cy, r in ((9, 14, 4), (16, 12, 5), (23, 14, 4)):
        pygame.draw.circle(s, COL_YELLOW, (cx, cy), r)
        pygame.draw.rect(s, COL_YELLOW,
                         (cx - r, cy + r - 1, r * 2, r * 2 + 1))
    # Spotlights at top corners.
    pygame.draw.line(s, COL_WHITE, (3, 4), (10, 12), 1)
    pygame.draw.line(s, COL_WHITE, (29, 4), (22, 12), 1)
    return s


# ── Driver ───────────────────────────────────────────────────────────────

ICON_REGISTRY = {
    "room_combat":     icon_room_combat,
    "room_trap":       icon_room_trap,
    "room_treasure":   icon_room_treasure,
    "room_rest":       icon_room_rest,
    "room_merchant":   icon_room_merchant,
    "room_lore":       icon_room_lore,
    "room_boss":       icon_room_boss,
    "room_start":      icon_room_start,
    "room_pod":        icon_room_pod,
    "room_safehouse":  icon_room_safehouse,
    "weapon":          icon_weapon,
    "armor":           icon_armor,
    "consumable":      icon_consumable,
    "trinket":         icon_trinket,
    "credits":         icon_credits,
    "hp":              icon_hp,
    "audience":        icon_audience,
}


def synthesize_all(*, root: str = ".") -> dict:
    """Write each icon as a 32x32 PNG into root/assets/images/.
    Returns dict[rel_path → byte_size]."""
    if not _HAS_PYGAME:
        return {}
    # Headless surface init — required for SRCALPHA / image.save in
    # some pygame builds.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
        pygame.display.set_mode((1, 1))
    out = {}
    for key, fn in ICON_REGISTRY.items():
        rel = os.path.join(ICON_DIR, f"{key}.png")
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        surf = fn()
        pygame.image.save(surf, path)
        out[rel] = os.path.getsize(path)
    return out


def main() -> None:
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sizes = synthesize_all(root=root)
    if not sizes:
        print("pygame unavailable — no icons generated.")
        return
    total = sum(sizes.values())
    for rel, sz in sorted(sizes.items()):
        print(f"  {sz:>6} B   {rel}")
    print(f"\n  total: {total / 1024:.1f} KB across {len(sizes)} files")


if __name__ == "__main__":
    main()
