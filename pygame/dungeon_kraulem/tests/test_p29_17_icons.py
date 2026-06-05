"""Prompt 29.17 — Icon asset shipping smoke suite.

Audit finding: ui/assets.py:load_icon was wired since P27 but
assets/images/ shipped empty — every call rendered the random-color
key-letter fallback. P29.17 generates 17 procedural 32×32 PNGs
matching the keys load_icon recognises and wires them into the
topbar HUD + full-map legend.

Covers:
  * Every expected key has a .png in assets/images/.
  * Each PNG is structurally valid (pygame.image.load doesn't error).
  * load_icon returns the disk image, not the fallback — verified
    by NOT having the fallback's signature center-letter pixel.
  * synthesize_all is deterministic across runs.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.init()
pygame.display.set_mode((1, 1))


PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PKG_ROOT)
ICON_DIR = os.path.join(REPO_ROOT, "assets", "images")


EXPECTED_KEYS = (
    "room_combat", "room_trap", "room_treasure", "room_rest",
    "room_merchant", "room_lore", "room_boss", "room_start",
    "room_pod", "room_safehouse",
    "weapon", "armor", "consumable", "trinket",
    "credits", "hp", "audience",
)


# ── Inventory ───────────────────────────────────────────────────────────

def test_every_expected_key_has_png():
    missing = [k for k in EXPECTED_KEYS if not os.path.exists(
        os.path.join(ICON_DIR, f"{k}.png"))]
    assert not missing, f"missing icons: {sorted(missing)}"
    print(f"  {len(EXPECTED_KEYS)} icons present on disk: OK")


def test_every_png_loads_via_pygame():
    bad = []
    for k in EXPECTED_KEYS:
        p = os.path.join(ICON_DIR, f"{k}.png")
        try:
            surf = pygame.image.load(p)
            assert surf.get_width() == 32
            assert surf.get_height() == 32
        except Exception as exc:
            bad.append((k, str(exc)))
    assert not bad, f"unloadable icons: {bad}"
    print("  every PNG loads via pygame at 32×32: OK")


def test_load_icon_returns_real_disk_image():
    """ui/assets.py:load_icon falls back to a generated key-letter
    image when the file is missing. Verify our disk PNG is what's
    being returned — by sampling a pixel known to be drawn ONLY in
    the procedural icon, not in the fallback."""
    from ..ui import assets as _ico
    # Clear the load cache from previous tests, if any.
    _ico._cache.clear()
    surf = _ico.load_icon("audience", 32, 32)
    assert surf is not None
    # The audience icon paints 3 yellow heads in the lower half — the
    # fallback fills the upper half with a single random color + a
    # capital "A" letter. Sample a known-yellow pixel from our PNG.
    px = surf.get_at((16, 12))  # middle of the central head circle
    # Our COL_YELLOW = (230, 200, 120, 255). Allow some smoothscale
    # variance via channel ranges.
    assert 200 <= px[0] <= 240, f"R channel off ({px[0]})"
    assert 170 <= px[1] <= 220, f"G channel off ({px[1]})"
    assert 90 <= px[2] <= 150, f"B channel off ({px[2]})"
    print(f"  load_icon('audience') returns disk PNG (sample pixel "
          f"{tuple(px)[:3]}): OK")


# ── Idempotency ─────────────────────────────────────────────────────────

def test_synthesize_all_idempotent():
    import tempfile
    from ..tools import synthesize_icons as _syn
    with tempfile.TemporaryDirectory() as tmp:
        sizes_a = _syn.synthesize_all(root=tmp)
        snapshot = {}
        for rel in sizes_a:
            with open(os.path.join(tmp, rel), "rb") as fh:
                snapshot[rel] = fh.read()
        sizes_b = _syn.synthesize_all(root=tmp)
        assert sizes_a == sizes_b
        for rel in sizes_b:
            with open(os.path.join(tmp, rel), "rb") as fh:
                assert fh.read() == snapshot[rel], \
                    f"{rel} changed between runs"
    print(f"  synthesize_all deterministic across {len(sizes_a)} files: OK")


# ── Topbar / legend smoke (no crash with icons) ─────────────────────────

def test_draw_topbar_doesnt_crash_with_icons():
    """The topbar audience HUD now blits an icon — ensure the draw
    path runs cleanly on an empty world too."""
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..ui.ui import draw_topbar
    w = WorldState()
    w.character = Character(name="X", audience_rating=42)
    screen = pygame.display.get_surface()
    if screen is None:
        screen = pygame.display.set_mode((1920, 1080))
    draw_topbar(screen, w)
    print("  draw_topbar with audience icon: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_every_expected_key_has_png()
    test_every_png_loads_via_pygame()
    test_load_icon_returns_real_disk_image()
    test_synthesize_all_idempotent()
    test_draw_topbar_doesnt_crash_with_icons()
    print("Prompt 29.17 icons smoke: OK")


if __name__ == "__main__":
    main()
