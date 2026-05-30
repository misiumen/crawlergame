"""P30 — VATS limb hitboxes traced onto enemy portrait art.

The VATS targeting panel draws the enemy *portrait* as the body and overlays
clickable limb zones on top of it. For that overlay to line up with the drawn
anatomy (not abstract blocks), each portrait needs hitboxes tuned to where the
figure actually stands inside its framed illustration.

Coordinates are NORMALISED to the portrait rect: each zone is
`(fx, fy, fw, fh)` with every value in 0..1, where (0,0) is the top-left of
the rect and (1,1) the bottom-right. The renderer multiplies by the rect's
pixel size, so the same data works at any panel scale.

Resolution order (see `zones_for`):
  1. exact art key   — e.g. "wrog_intake_freezer_carver" (hand-traced)
  2. visual archetype — "humanoid" / "quadruped" / "drone" / "blob"
  3. None            — caller falls back to the legacy block grid

Zone keys match the body plans in `content.data.body_plans`:
  humanoid:   head / torso / l_arm / r_arm / l_leg / r_leg
  quadruped:  head / torso / l_leg / r_leg
Left/right are the VIEWER's left/right (screen space), matching the art.
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple

Box = Tuple[float, float, float, float]


# ── Per-portrait hitboxes (hand-traced from assets/images/wrog_intake_*) ──

HITBOXES: Dict[str, Dict[str, Box]] = {
    # Big butcher, centered, broad apron torso, cleaver low-left.
    "wrog_intake_freezer_carver": {
        "head":  (0.42, 0.07, 0.17, 0.15),
        "torso": (0.35, 0.22, 0.30, 0.40),
        "l_arm": (0.26, 0.27, 0.11, 0.30),
        "r_arm": (0.63, 0.27, 0.11, 0.30),
        "l_leg": (0.39, 0.62, 0.12, 0.33),
        "r_leg": (0.51, 0.62, 0.12, 0.33),
    },
    # Armored warden, wide stance, helmet top-center, chainsaw left.
    "wrog_intake_warden": {
        "head":  (0.42, 0.06, 0.16, 0.13),
        "torso": (0.34, 0.19, 0.31, 0.41),
        "l_arm": (0.22, 0.27, 0.12, 0.30),
        "r_arm": (0.64, 0.27, 0.12, 0.30),
        "l_leg": (0.33, 0.60, 0.15, 0.37),
        "r_leg": (0.52, 0.60, 0.15, 0.37),
    },
    # Sortation overseer — narrower frame, weapon lower-left.
    "wrog_intake_nadzorca_sortowni": {
        "head":  (0.42, 0.06, 0.16, 0.13),
        "torso": (0.36, 0.19, 0.28, 0.40),
        "l_arm": (0.25, 0.25, 0.11, 0.30),
        "r_arm": (0.63, 0.25, 0.11, 0.30),
        "l_leg": (0.39, 0.59, 0.12, 0.37),
        "r_leg": (0.50, 0.59, 0.12, 0.37),
    },
    # Hazmat inspector — clipboard held at chest, slim suit.
    "wrog_intake_biotech_inspector": {
        "head":  (0.42, 0.10, 0.16, 0.13),
        "torso": (0.37, 0.24, 0.26, 0.36),
        "l_arm": (0.30, 0.30, 0.10, 0.26),
        "r_arm": (0.60, 0.30, 0.10, 0.26),
        "l_leg": (0.40, 0.60, 0.11, 0.34),
        "r_leg": (0.50, 0.60, 0.11, 0.34),
    },
    # Generic industrial humanoid — hunched, arms loose.
    "wrog_intake_humanoid_industrial": {
        "head":  (0.43, 0.08, 0.15, 0.13),
        "torso": (0.37, 0.22, 0.27, 0.38),
        "l_arm": (0.27, 0.28, 0.11, 0.28),
        "r_arm": (0.62, 0.30, 0.11, 0.26),
        "l_leg": (0.40, 0.60, 0.11, 0.34),
        "r_leg": (0.51, 0.60, 0.11, 0.34),
    },
    # Rat — side view, facing screen-left. Quadruped zones.
    "wrog_intake_tunnel_runt": {
        "head":  (0.10, 0.52, 0.22, 0.22),
        "torso": (0.30, 0.42, 0.40, 0.26),
        "l_leg": (0.28, 0.66, 0.16, 0.27),   # front legs
        "r_leg": (0.55, 0.64, 0.18, 0.30),   # hind legs
    },
    # Dog-beast — side view, facing screen-left, lunging. Quadruped.
    "wrog_intake_beast_industrial": {
        "head":  (0.10, 0.38, 0.24, 0.26),
        "torso": (0.34, 0.30, 0.40, 0.30),
        "l_leg": (0.22, 0.60, 0.18, 0.34),   # front legs
        "r_leg": (0.58, 0.58, 0.20, 0.36),   # hind legs
    },
}


# ── Archetype fallbacks (anatomical, used when no per-key data exists) ────
# These trace a "typical" figure centered in the frame — far better than a
# rectangular block grid for any art that fills the portrait.

ARCHETYPE_HITBOXES: Dict[str, Dict[str, Box]] = {
    "humanoid": {
        "head":  (0.42, 0.07, 0.16, 0.14),
        "torso": (0.36, 0.21, 0.28, 0.40),
        "l_arm": (0.26, 0.27, 0.11, 0.30),
        "r_arm": (0.63, 0.27, 0.11, 0.30),
        "l_leg": (0.39, 0.61, 0.12, 0.35),
        "r_leg": (0.51, 0.61, 0.12, 0.35),
    },
    "undead": {
        "head":  (0.42, 0.07, 0.16, 0.14),
        "torso": (0.36, 0.21, 0.28, 0.40),
        "l_arm": (0.26, 0.27, 0.11, 0.30),
        "r_arm": (0.63, 0.27, 0.11, 0.30),
        "l_leg": (0.39, 0.61, 0.12, 0.35),
        "r_leg": (0.51, 0.61, 0.12, 0.35),
    },
    # Four-legged side view (matches PLAN_SMALL_QUADRUPED zones).
    "quadruped": {
        "head":  (0.10, 0.45, 0.24, 0.26),
        "torso": (0.32, 0.36, 0.40, 0.28),
        "l_leg": (0.26, 0.62, 0.18, 0.32),
        "r_leg": (0.56, 0.60, 0.20, 0.34),
    },
    "beast": {   # alias → quadruped silhouette
        "head":  (0.10, 0.45, 0.24, 0.26),
        "torso": (0.32, 0.36, 0.40, 0.28),
        "l_leg": (0.26, 0.62, 0.18, 0.32),
        "r_leg": (0.56, 0.60, 0.20, 0.34),
    },
    # Hovering drone (matches PLAN_DRONE: sensor/body/propulsion).
    "drone": {
        "sensor":     (0.34, 0.10, 0.32, 0.24),
        "body":       (0.28, 0.34, 0.44, 0.34),
        "propulsion": (0.30, 0.68, 0.40, 0.24),
    },
    "robot": {
        "head":  (0.40, 0.08, 0.20, 0.16),
        "torso": (0.32, 0.24, 0.36, 0.38),
        "l_arm": (0.22, 0.28, 0.10, 0.30),
        "r_arm": (0.68, 0.28, 0.10, 0.30),
        "l_leg": (0.36, 0.62, 0.13, 0.34),
        "r_leg": (0.51, 0.62, 0.13, 0.34),
    },
    "blob": {
        "core": (0.20, 0.20, 0.60, 0.60),
    },
}

# Map a body-plan archetype name to the nearest hitbox set name.
_ARCH_ALIAS = {
    "aberration": "humanoid",
    "beast": "quadruped",
}


def zones_for(art_key: Optional[str], archetype: str,
              plan_zones) -> Optional[Dict[str, Box]]:
    """Return normalised hitboxes for the zones present in `plan_zones`,
    preferring per-portrait data, then the archetype fallback. Returns None
    when nothing matches (caller uses the legacy block grid).

    Only zones that exist in BOTH the hitbox set and the plan are returned,
    so a mismatched plan can never paint a stray limb."""
    want = set(plan_zones or ())
    src = None
    if art_key and art_key in HITBOXES:
        src = HITBOXES[art_key]
    else:
        name = _ARCH_ALIAS.get(archetype, archetype)
        src = ARCHETYPE_HITBOXES.get(name)
        if src is None and archetype in ARCHETYPE_HITBOXES:
            src = ARCHETYPE_HITBOXES[archetype]
    if not src:
        return None
    out = {z: box for z, box in src.items() if z in want}
    # Require coverage of the core zones; otherwise the grid is safer.
    if not out or "torso" not in out and "body" not in out and "core" not in out:
        return None
    return out
