"""P29.70 — Workstream C/1: proceduralny AWATAR gracza.

Zastępuje literkę „K" budowaną sylwetką, która ODBIJA wyposażenie: hełm
gdy zajęty slot głowy, kamizelka na torsie, nogawki, plecak, broń w
dłoni. Zero zewnętrznej grafiki — czysty pygame, więc działa od ręki i
skaluje się do dowolnego boksu portretu.

Self-contained paleta (bez importu ui.ui → brak cyklu). ui.ui woła
draw_avatar() w prawym sidebarze.
"""
from __future__ import annotations

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:  # pragma: no cover
    _HAS_PYGAME = False


# Minimalna paleta (kopia tonów z ui.ui, ale lokalna — bez cyklu importu).
_BG       = (26, 30, 38)
_BORDER   = (70, 84, 104)
_SKIN     = (196, 168, 142)
_SUIT     = (84, 92, 110)        # bazowy „kombinezon" gdy brak EQ
_ACCENT   = (90, 200, 220)


def _tint(seed_str: str, base) -> tuple:
    """Deterministyczny wariant koloru wg klucza (species/origin)."""
    s = sum(ord(c) for c in (seed_str or "")) if seed_str else 0
    r, g, b = base
    return (max(0, min(255, r + (s * 37) % 60 - 30)),
            max(0, min(255, g + (s * 71) % 60 - 30)),
            max(0, min(255, b + (s * 113) % 60 - 30)))


def _worn(character) -> set:
    return set((getattr(character, "worn_slots", None) or {}).keys())


def draw_avatar(surf, character, x: int, y: int, w: int, h: int, *,
                world=None) -> None:
    """Rysuje awatar gracza w boksie (x,y,w,h). Bezpieczne dla None
    character / braku pygame."""
    if not _HAS_PYGAME or surf is None:
        return
    # Tło + ramka.
    pygame.draw.rect(surf, _BG, (x, y, w, h))
    pygame.draw.rect(surf, _BORDER, (x, y, w, h), 2)
    if character is None:
        return

    worn = _worn(character)
    species = getattr(character, "species_key", "") or "baseline_human"
    origin = getattr(character, "background", "") or ""
    skin = _tint(species, _SKIN)
    suit = _tint(origin, _SUIT)
    accent = _ACCENT

    cx = x + w // 2
    pad = max(6, w // 12)
    top = y + pad

    # ── Geometria sylwetki ──
    head_r = max(6, int(w * 0.16))
    head_cy = top + head_r
    torso_w = max(10, int(w * 0.40))
    torso_h = max(14, int(h * 0.30))
    torso_x = cx - torso_w // 2
    torso_y = head_cy + head_r + max(2, h // 40)
    leg_h = max(10, int(h * 0.22))
    leg_w = max(4, torso_w // 3)
    arm_w = max(3, torso_w // 4)
    arm_h = int(torso_h * 0.9)

    # ── Plecak (za sylwetką) ──
    if "back" in worn:
        bp_w = max(6, torso_w // 2)
        pygame.draw.rect(surf, _tint("plecak", (70, 60, 50)),
                         (torso_x - bp_w // 2, torso_y + 2, bp_w,
                          int(torso_h * 0.8)), border_radius=3)

    # ── Nogi (nogawki, jeśli slot legs zajęty) ──
    leg_col = _tint("nogi", (60, 64, 74)) if "legs" in worn else skin
    pygame.draw.rect(surf, leg_col,
                     (cx - leg_w - 2, torso_y + torso_h, leg_w, leg_h))
    pygame.draw.rect(surf, leg_col,
                     (cx + 2, torso_y + torso_h, leg_w, leg_h))

    # ── Ramiona ──
    pygame.draw.rect(surf, skin,
                     (torso_x - arm_w, torso_y + 2, arm_w, arm_h))
    pygame.draw.rect(surf, skin,
                     (torso_x + torso_w, torso_y + 2, arm_w, arm_h))

    # ── Tors: kamizelka (slot torso) albo goły kombinezon ──
    torso_col = _tint("torso", (110, 120, 140)) if "torso" in worn else suit
    pygame.draw.rect(surf, torso_col,
                     (torso_x, torso_y, torso_w, torso_h), border_radius=4)
    # Akcent origin — pasek na piersi (sygnatura zawodnika).
    pygame.draw.rect(surf, accent,
                     (torso_x, torso_y + torso_h // 2 - 1, torso_w, 2))

    # ── Głowa ──
    pygame.draw.circle(surf, skin, (cx, head_cy), head_r)
    # Hełm/czapka, jeśli slot head zajęty (łuk nad górną połową głowy).
    if "head" in worn:
        helm = _tint("helm", (90, 100, 120))
        pygame.draw.circle(surf, helm, (cx, head_cy), head_r)
        pygame.draw.rect(surf, skin,
                         (cx - head_r, head_cy, head_r * 2, head_r))
        pygame.draw.circle(surf, skin, (cx, head_cy + 1),
                           max(3, head_r - 2))
        # przyłbica
        pygame.draw.arc(surf, helm,
                        (cx - head_r, head_cy - head_r,
                         head_r * 2, head_r * 2), 3.14, 6.28, 3)

    # ── Broń w prawej dłoni ──
    if getattr(character, "wielded_main_id", None) is not None:
        hand_x = torso_x + torso_w + arm_w // 2
        hand_y = torso_y + arm_h
        pygame.draw.line(surf, _tint("bron", (200, 200, 160)),
                         (hand_x, hand_y),
                         (hand_x, hand_y - int(h * 0.30)), 3)
    # ── Tarcza/przedmiot w lewej dłoni ──
    if getattr(character, "wielded_offhand_id", None) is not None:
        hand_x = torso_x - arm_w // 2
        hand_y = torso_y + arm_h - 4
        pygame.draw.circle(surf, _tint("tarcza", (150, 140, 120)),
                           (hand_x, hand_y), max(4, arm_w))

    # ── Pierścień HP (cienki, na dole boksu) ──
    try:
        hp = int(getattr(character, "hp", 0))
        mx = int(getattr(character, "max_hp", 0)) or 1
        frac = max(0.0, min(1.0, hp / mx))
        bar_w = int((w - 2 * pad) * frac)
        col = (200, 80, 70) if frac < 0.34 else (
            (210, 190, 80) if frac < 0.67 else (90, 190, 110))
        pygame.draw.rect(surf, (40, 44, 52),
                         (x + pad, y + h - 7, w - 2 * pad, 4))
        if bar_w > 0:
            pygame.draw.rect(surf, col, (x + pad, y + h - 7, bar_w, 4))
    except Exception:
        pass
