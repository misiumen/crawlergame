"""COMBAT-1 P2 — combat juice: recoil kick + persistent shake + new SFX.

The juice rides the existing combat_fx + update(dt) loop. We assert the
state plumbing (kick set on hit, decays; shake set in ms so it lasts) and
that the new SFX assets exist.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
pygame.display.set_mode((1280, 720))

from .. import config
config.apply_llm_mode("performance")

from ..engine.game import Game, STATE_PLAY


def _demo_game():
    g = Game(screen=None)
    g.start_new_game("Tester", "janitor", demo_mode=True)
    g.state = STATE_PLAY
    g._refresh_layout()
    return g


def test_kick_set_on_hit_and_decays():
    g = _demo_game()
    g._spawn_combat_fx(42, "-9", (255, 255, 255), kick=10)
    fx = g.world.combat_fx
    assert fx.get("kick", {}).get(42), "kick should be set on hit"
    off, ttl = fx["kick"][42]
    assert off == 10.0 and ttl > 0
    # Decay via update.
    g.update(250)
    assert not fx.get("kick", {}).get(42), "kick should decay away"
    print("  recoil kick set on hit + decays: OK")


def test_shake_persists_multiple_frames():
    g = _demo_game()
    g._spawn_combat_fx(7, "-12", (255, 80, 80), shake=120.0)
    fx = g.world.combat_fx
    assert fx.get("shake", 0) >= 120.0
    g.update(40)   # one frame
    assert fx.get("shake", 0) > 0, "shake should outlast a single frame now"
    print("  shake persists across frames (ms-scaled): OK")


def test_new_sfx_assets_exist():
    from ..config import SFX_DIR
    for key in ("stagger", "sever", "zap", "ignite", "finisher"):
        hit = any(os.path.exists(os.path.join(SFX_DIR, key + ext))
                  for ext in (".wav", ".ogg"))
        assert hit, f"missing generated SFX: {key}"
    print("  new combat SFX assets present: OK")


def main():
    test_kick_set_on_hit_and_decays()
    test_shake_persists_multiple_frames()
    test_new_sfx_assets_exist()
    print("COMBAT-1 P2 juice smoke: OK")


if __name__ == "__main__":
    main()
