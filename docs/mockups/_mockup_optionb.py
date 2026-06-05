"""Throwaway mockup: how Option B (spatial roguelike) could look.

Renders a single static frame to _mockup_optionb.png. NOT wired to the
game — just a visual to react to. Code-drawn tiles + the existing dark/
neon DCC palette. Run: python _mockup_optionb.py
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.font.init()

W, H = 1600, 900
surf = pygame.Surface((W, H))

# Palette (DCC dark + neon).
BG      = (10, 12, 16)
PANEL   = (18, 22, 30)
BORDER  = (44, 52, 66)
WALL    = (40, 46, 58)
WALL_HI = (70, 80, 100)
FLOOR   = (22, 26, 34)
FLOOR2  = (26, 31, 40)
DIM     = (120, 130, 145)
TXT     = (200, 210, 225)
BRIGHT  = (235, 242, 252)
CYAN    = (90, 200, 230)
MAGENTA = (220, 90, 180)
AMBER   = (240, 190, 90)
RED     = (220, 80, 80)
GREEN   = (110, 200, 130)
HPGREEN = (90, 200, 120)

def mono(sz, bold=False):
    return pygame.font.SysFont("Consolas,DejaVu Sans Mono,monospace", sz, bold=bold)

def txt(s, x, y, col=TXT, sz=18, bold=False):
    surf.blit(mono(sz, bold).render(s, True, col), (x, y))

surf.fill(BG)

# ── Top bar ──────────────────────────────────────────────────────────────
pygame.draw.rect(surf, PANEL, (0, 0, W, 40))
pygame.draw.line(surf, CYAN, (0, 40), (W, 40), 1)
txt("▣ SORTOWNIA ZAWODNIKÓW · Piętro 1", 16, 9, CYAN, 20, True)
txt("Termin: 13d 22h", 1080, 11, AMBER, 18)
txt("● WIDOWNIA 47", 1260, 11, MAGENTA, 18, True)
txt("ZIMNO", 1420, 11, CYAN, 18)

# ── Layout regions ───────────────────────────────────────────────────────
MAP_X, MAP_Y, MAP_W, MAP_H = 16, 56, 1080, 660
SIDE_X = MAP_X + MAP_W + 16
SIDE_W = W - SIDE_X - 16
LOG_Y = MAP_Y + MAP_H + 12

# ── Map (tile grid) ──────────────────────────────────────────────────────
pygame.draw.rect(surf, (8, 10, 14), (MAP_X, MAP_Y, MAP_W, MAP_H))
pygame.draw.rect(surf, BORDER, (MAP_X, MAP_Y, MAP_W, MAP_H), 1)

TS = 30  # tile size
cols = MAP_W // TS
rows = MAP_H // TS

# A hand-laid little dungeon chunk (string map). Legend:
#  '#' wall  '.' floor  '@' player  'r' rat  'C' captain(neutral)
#  '$' loot  '+' door  '~' hazard(puddle)  '=' workbench  '!' item
#  ' ' unknown/dark
MAP = [
 "                                  ",
 "   #########        ############  ",
 "   #.......#        #..........#  ",
 "   #..!....#        #...r......#  ",
 "   #.......+########+..........#  ",
 "   #...=...#.......#...$....r..#  ",
 "   #.......#...~~..#..........+##  ",
 "   ####+####...~~..#..........#.#  ",
 "       #......~~...#####+#######.#  ",
 "       #..........#     #.......#  ",
 "       #....@.....+#####+...C...#  ",
 "       #..........#.....#.......#  ",
 "       #####+######.....####+####  ",
 "           #.......+.......#       ",
 "           #...$...#...!...#       ",
 "           #.......#.......#       ",
 "           ###########+#####       ",
 "                                  ",
]

def tilecol(ch):
    return {
        '#': WALL, '.': FLOOR, '+': AMBER, '~': CYAN,
        '=': GREEN, '$': AMBER, '!': GREEN,
    }.get(ch, FLOOR)

for ry, line in enumerate(MAP):
    for rx, ch in enumerate(line):
        px = MAP_X + 30 + rx * TS
        py = MAP_Y + 20 + ry * TS
        if px > MAP_X + MAP_W - TS or py > MAP_Y + MAP_H - TS:
            continue
        if ch == ' ':
            continue
        # floor base under most things
        if ch != '#':
            c2 = FLOOR2 if (rx + ry) % 2 == 0 else FLOOR
            pygame.draw.rect(surf, c2, (px, py, TS - 1, TS - 1))
        if ch == '#':
            pygame.draw.rect(surf, WALL, (px, py, TS - 1, TS - 1))
            pygame.draw.rect(surf, WALL_HI, (px, py, TS - 1, TS - 1), 1)
        elif ch == '~':
            pygame.draw.rect(surf, (18, 40, 52), (px, py, TS - 1, TS - 1))
            txt("≈", px + 9, py + 4, CYAN, 20)
        elif ch == '+':
            txt("+", px + 9, py + 3, AMBER, 22, True)
        elif ch == '=':
            txt("⌗", px + 8, py + 3, GREEN, 22, True)
        elif ch == '$':
            txt("$", px + 9, py + 3, AMBER, 22, True)
        elif ch == '!':
            txt("!", px + 11, py + 3, GREEN, 22, True)
        elif ch == 'r':
            txt("r", px + 9, py + 3, RED, 24, True)
        elif ch == 'C':
            txt("C", px + 8, py + 3, MAGENTA, 24, True)
        elif ch == '@':
            pygame.draw.rect(surf, (30, 50, 60), (px, py, TS - 1, TS - 1))
            txt("@", px + 8, py + 2, BRIGHT, 24, True)

# soft "vision" vignette hint: dim the far rooms
veil = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
for i in range(0, MAP_W, 4):
    pass
# light glow around player
glow = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
pcx = MAP_X + 30 + 11 * TS + TS//2 - MAP_X
pcy = MAP_Y + 20 + 10 * TS + TS//2 - MAP_Y
for rad, a in ((230, 0), (240, 30), (320, 70), (420, 110)):
    pygame.draw.circle(glow, (0, 0, 0, a), (pcx, pcy), rad, 60)
surf.blit(glow, (MAP_X, MAP_Y))

# room label floating near current room
txt("Korytarz Serwisowy A", MAP_X + 30 + 7*TS, MAP_Y + 20 + 9*TS - 22, DIM, 15)

# legend strip bottom of map
ly = MAP_Y + MAP_H - 26
txt("@ ty   r wróg   C crawler(neutralny)   $ łup   ! item   "
    "⌗ warsztat   + drzwi   ≈ kałuża", MAP_X + 12, ly, DIM, 15)

# ── Right sidebar ────────────────────────────────────────────────────────
def panel(x, y, w, h, title=None, tc=CYAN):
    pygame.draw.rect(surf, PANEL, (x, y, w, h))
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1)
    if title:
        txt(title, x + 10, y + 6, tc, 15, True)

# character
panel(SIDE_X, MAP_Y, SIDE_W, 150, "BEZIMIENNY · Żołnierz")
txt("HP", SIDE_X+12, MAP_Y+34, DIM, 15)
pygame.draw.rect(surf, (40,30,30), (SIDE_X+44, MAP_Y+34, 380, 14))
pygame.draw.rect(surf, HPGREEN, (SIDE_X+44, MAP_Y+34, 255, 14))
txt("67/100", SIDE_X+300, MAP_Y+33, BRIGHT, 14)
txt("AC 14   Kredyty 25   Stan: ranny", SIDE_X+12, MAP_Y+56, TXT, 15)
txt("SIŁ 14  ZRĘ 12  KON 14", SIDE_X+12, MAP_Y+82, DIM, 15)
txt("INT 9   MĄD 11  CHA 8", SIDE_X+12, MAP_Y+102, DIM, 15)
txt("Broń: tani nóż   (krew: —)", SIDE_X+12, MAP_Y+124, AMBER, 15)

# target / look panel
ty0 = MAP_Y + 162
panel(SIDE_X, ty0, SIDE_W, 200, "POD KURSOREM ▸ Tunelowy Szczurek", RED)
txt("HP 12/22   AC 10   threat: spokojny", SIDE_X+12, ty0+30, TXT, 15)
txt("Atak: 1d4+1   Słaby na: ogień", SIDE_X+12, ty0+52, TXT, 15)
txt("„Niski, mokry, bardzo zły. Chrupie", SIDE_X+12, ty0+82, DIM, 15)
txt(" dłoń, jeśli mu pozwolisz.”", SIDE_X+12, ty0+100, DIM, 15)
txt("[Enter] atak  ·  [t] pogadaj", SIDE_X+12, ty0+136, GREEN, 15)
txt("[f] rzuć  ·  [c] cel: kończyna", SIDE_X+12, ty0+158, GREEN, 15)

# inventory quick
iy0 = ty0 + 212
panel(SIDE_X, iy0, SIDE_W, 286, "PRZY SOBIE")
inv = [("a", "tani nóż", AMBER),
       ("b", "latarka", TXT),
       ("c", "bandaż (×2)", GREEN),
       ("d", "podejrzana karta dostępu", CYAN),
       ("e", "taśma naprawcza", TXT),
       ("f", "złom metalowy ×13", DIM),
       ("g", "pęk przewodów ×3", DIM)]
for i, (k, name, col) in enumerate(inv):
    txt(f"[{k}] {name}", SIDE_X+12, iy0+30+i*26, col, 16)
txt("[i] pełny plecak   [z] crafting", SIDE_X+12, iy0+30+7*26+6, GREEN, 15)

# ── Log ──────────────────────────────────────────────────────────────────
panel(MAP_X, LOG_Y, MAP_W, H - LOG_Y - 12, "DZIENNIK")
log = [
 ("Wchodzisz w Korytarz Serwisowy A. Z rury kapie coś, co nie jest wodą.", DIM),
 ("Tunelowy Szczurek dostrzega cię — pierwszy krok w twoją stronę.", TXT),
 ("Trafiasz nożem w łeb: -6 HP. Szczurek się zachwiał.", GREEN),
 ("Kapitan Drużyny obserwuje z drugiego końca. Na razie nie rusza się.", AMBER),
 ("Konferansjer (cicho): „Krew na pierwszej minucie. Widownia to lubi.”", MAGENTA),
]
for i, (line, col) in enumerate(log):
    txt(line, MAP_X+12, LOG_Y+30+i*24, col, 16)

# input line
txt("› _", MAP_X+12, H - 40, BRIGHT, 18, True)
txt("ruch: strzałki/WSAD · czekaj: . · akcje na celu: Enter · "
    "Esc menu", MAP_X+120, H - 38, DIM, 14)

pygame.image.save(surf, "_mockup_optionb.png")
print("wrote _mockup_optionb.png")
