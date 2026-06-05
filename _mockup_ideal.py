"""Mockup: the UI I (Claude) think is BEST for Dungeon Kraulem.

Thesis: the board IS the game. It steals the best idea from Into the Breach
(perfect-information tactical telegraphing) and marries it to the immersive-sim
systems this codebase already has. The screen answers three questions at a
glance, on the board itself, BEFORE you commit:
  1. What will the enemies do this turn?  (intent arrows + red danger tiles)
  2. What can I do?                        (reachable dots, target ring)
  3. What happens if I get clever?         (the CONSEQUENCE PREVIEW — the
     systemic chain shove->puddle->wire->shock shown as a glowing plan)

The right rail keeps the DCC soul (narration + audience). The verb sprawl /
nav-tabs / parser-as-primary are gone: one key = one action.

Renders _mockup_ideal.png. Throwaway. Run: python _mockup_ideal.py
"""
import os, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

W, H = 1760, 1000
surf = pygame.Surface((W, H), pygame.SRCALPHA)

# ---- palette ---------------------------------------------------------------
BG     = (12, 14, 19)
PANEL  = (20, 24, 32)
PANEL2 = (26, 31, 41)
BORDER = (46, 54, 70)
GRID_L = (40, 46, 60)
WALL   = (52, 60, 78);  WALLHI = (84, 96, 122)
FLOOR  = (22, 26, 35);  FLOOR2 = (27, 32, 43)
UNSEEN = (9, 11, 15)
DIM    = (118, 128, 146)
TXT    = (202, 211, 226)
BRIGHT = (240, 246, 255)
CYAN   = (96, 206, 233)
TEAL   = (70, 150, 168)
MAG    = (224, 96, 188)
AMBER  = (244, 194, 96)
RED    = (228, 86, 86)
ORANGE = (240, 138, 70)
GREEN  = (118, 206, 138)
HPCOL  = (96, 202, 124)
WATER  = (22, 58, 74)

_fonts = {}
def font(sz, b=False):
    k = (sz, b)
    if k not in _fonts:
        _fonts[k] = pygame.font.SysFont("Segoe UI, Arial", sz, bold=b)
    return _fonts[k]
_mono = {}
def mono(sz, b=False):
    k = (sz, b)
    if k not in _mono:
        _mono[k] = pygame.font.SysFont("Consolas, monospace", sz, bold=b)
    return _mono[k]

def text(s, x, y, c=TXT, sz=17, b=False, center=False, right=False, f=None):
    img = (f or font(sz, b)).render(s, True, c)
    r = img.get_rect()
    if center: r.center = (x, y)
    elif right: r.topright = (x, y)
    else: r.topleft = (x, y)
    surf.blit(img, r)
    return r

def panel(x, y, w, h, title=None, tc=CYAN, fill=PANEL):
    pygame.draw.rect(surf, fill, (x, y, w, h), border_radius=8)
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1, border_radius=8)
    if title:
        text(title, x + 12, y + 9, tc, 14, True)
        pygame.draw.line(surf, (BORDER[0], BORDER[1], BORDER[2]),
                         (x + 12, y + 32), (x + w - 12, y + 32), 1)

def bar(x, y, w, h, frac, col, bg=(38, 30, 32)):
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=h // 2)
    if frac > 0:
        pygame.draw.rect(surf, col, (x, y, max(h, int(w * frac)), h), border_radius=h // 2)

def glow_tile(gx, gy, col, alpha, inset=2):
    px, py = ox + gx * TS, oy + gy * TS
    g = pygame.Surface((TS - inset * 2, TS - inset * 2), pygame.SRCALPHA)
    g.fill((col[0], col[1], col[2], alpha))
    surf.blit(g, (px + inset, py + inset))

def arrow(p1, p2, col, w=3, head=13):
    pygame.draw.line(surf, col, p1, p2, w)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for da in (math.radians(150), math.radians(-150)):
        hx = p2[0] + head * math.cos(ang + da)
        hy = p2[1] + head * math.sin(ang + da)
        pygame.draw.line(surf, col, p2, (hx, hy), w)

surf.fill(BG)

# ============================================================================
# TOP BAR
# ============================================================================
TOP_H = 52
panel(16, 12, W - 32, TOP_H, fill=PANEL2)
text("SORTOWNIA ZAWODNIKÓW", 30, 22, CYAN, 20, True)
text("Piętro 1   ·   Runda 4   ·   tura GRACZA", 320, 26, DIM, 16)
# deadline
text("TERMIN", W - 470, 20, DIM, 12, True)
text("13d 22h", W - 470, 34, AMBER, 17, True)
# audience meter
text("WIDOWNIA", W - 330, 20, DIM, 12, True)
bar(W - 330, 38, 220, 10, 0.47, MAG, (40, 28, 40))
text("47", W - 96, 18, MAG, 22, True)

CY0 = 12 + TOP_H + 10            # content top
CY1 = H - 52                     # content bottom

# layout columns
LX, LW = 16, 196
BX = LX + LW + 12
RW = 380
RX = W - 16 - RW
BW = RX - 12 - BX

# ============================================================================
# LEFT RAIL — minimap, initiative, objective
# ============================================================================
panel(LX, CY0, LW, 196, "MAPA PIĘTRA")
# tiny node graph
nodes = {"a": (60, 70), "b": (110, 60), "c": (150, 110), "d": (95, 135),
         "e": (55, 170), "cur": (110, 100)}
edges = [("a", "b"), ("b", "cur"), ("cur", "c"), ("cur", "d"), ("d", "e"), ("a", "d")]
for u, v in edges:
    p = (LX + nodes[u][0], CY0 + nodes[u][1]); q = (LX + nodes[v][0], CY0 + nodes[v][1])
    pygame.draw.line(surf, BORDER, p, q, 2)
for k, (nx, ny) in nodes.items():
    c = CYAN if k == "cur" else (DIM if k in ("a", "b") else (60, 68, 86))
    r = 8 if k == "cur" else 5
    pygame.draw.circle(surf, c, (LX + nx, CY0 + ny), r)
    if k == "cur":
        pygame.draw.circle(surf, CYAN, (LX + nx, CY0 + ny), 13, 2)
text("zbadane 3/?", LX + 12, CY0 + 168, DIM, 13)

IY = CY0 + 208
panel(LX, IY, LW, 168, "KOLEJNOŚĆ TUR")
order = [("@  Ty", CYAN, "teraz"), ("r  Szczurek", RED, "potem"),
         ("R  Szczurek 2", RED, ""), ("C  Crawler", MAG, "neutralny")]
for i, (nm, c, tag) in enumerate(order):
    yy = IY + 44 + i * 28
    if i == 0:
        pygame.draw.rect(surf, (24, 40, 50), (LX + 8, yy - 4, LW - 16, 26), border_radius=5)
    text(nm, LX + 16, yy, c, 16, b=(i == 0), f=mono(16, i == 0))
    if tag: text(tag, LX + LW - 14, yy + 1, DIM, 12, right=True)

OY = IY + 180
panel(LX, OY, LW, CY1 - OY, "CEL PIĘTRA", AMBER)
for i, l in enumerate(["Znajdź zejście", "albo: zabij bossa", "(2 drogi otwarte)"]):
    text(l, LX + 14, OY + 44 + i * 24, TXT if i < 2 else DIM, 14)

# ============================================================================
# CENTER — THE BOARD
# ============================================================================
panel(BX, CY0, BW, CY1 - CY0, fill=(8, 10, 14))
text("KORYTARZ SORTOWNI", BX + 14, CY0 + 10, DIM, 13, True)

GRID = [
    "###################",
    "#.......#.........#",
    "#..$....#....C....#",
    "#.......#.........#",
    "#.......+.........#",
    "#....@...........>#",
    "#...r.........R...#",
    "#.~~|.............#",
    "#.~~.........G....#",
    "#.......#.........#",
    "#.......###+#######",
    "#.................#",
    "#.................#",
    "###################",
]
COLS, ROWS = len(GRID[0]), len(GRID)
pad = 16
avail_w = BW - pad * 2
avail_h = (CY1 - CY0) - 40 - pad
TS = min(avail_w // COLS, avail_h // ROWS)
gw, gh = TS * COLS, TS * ROWS
ox = BX + (BW - gw) // 2
oy = CY0 + 36 + ((CY1 - CY0 - 36) - gh) // 2

def find(ch):
    for y, l in enumerate(GRID):
        x = l.find(ch)
        if x >= 0: return x, y
    return None
def cellpx(gx, gy, cx=False):
    if cx: return ox + gx * TS + TS // 2, oy + gy * TS + TS // 2
    return ox + gx * TS, oy + gy * TS

pcx, pcy = find('@')
# fog: the south corridor (below the lower door) is unexplored
UNEXPLORED = {(x, y) for y in (11, 12) for x in range(1, COLS - 1)}

for gy, line in enumerate(GRID):
    for gx, ch in enumerate(line):
        px, py = cellpx(gx, gy)
        if (gx, gy) in UNEXPLORED:
            pygame.draw.rect(surf, UNSEEN, (px, py, TS - 1, TS - 1))
            pygame.draw.rect(surf, (14, 16, 22), (px, py, TS - 1, TS - 1), 1)
            continue
        d = math.hypot(gx - pcx, gy - pcy)
        fade = max(0.55, 1.0 - d / 22.0)
        if ch == '#':
            pygame.draw.rect(surf, tuple(int(v * fade) for v in WALL), (px, py, TS - 1, TS - 1))
            pygame.draw.line(surf, tuple(int(v * fade) for v in WALLHI), (px, py), (px + TS - 1, py), 1)
            continue
        base = FLOOR2 if (gx + gy) % 2 == 0 else FLOOR
        pygame.draw.rect(surf, tuple(int(v * fade) for v in base), (px, py, TS - 1, TS - 1))
        pygame.draw.rect(surf, GRID_L, (px, py, TS - 1, TS - 1), 1)

# ---- hazards (drawn under actors) ----
for (hx, hy) in [(2, 7), (3, 7), (2, 8), (3, 8)]:
    px, py = cellpx(hx, hy)
    pygame.draw.rect(surf, WATER, (px + 2, py + 2, TS - 4, TS - 4), border_radius=6)

def glyph(ch, gx, gy, col, ring=None, sz=None):
    px, py = cellpx(gx, gy, cx=True)
    if ring:
        pygame.draw.rect(surf, ring, (ox + gx * TS + 2, oy + gy * TS + 2, TS - 5, TS - 5), 2, border_radius=4)
    text(ch, px, py - 1, col, sz or int(TS * 0.6), True, center=True, f=mono(sz or int(TS * 0.6), True))

# tokens
text("≈", *cellpx(2, 7, cx=True), CYAN); # decorative water mark via text below instead
# water shimmer marks
for (hx, hy) in [(2, 7), (3, 8)]:
    px, py = cellpx(hx, hy, cx=True)
    text("~", px, py, TEAL, int(TS * 0.5), True, center=True, f=mono(int(TS * 0.5), True))
glyph("|", 4, 7, AMBER)                                   # sparking wire
glyph("$", 3, 2, AMBER)                                   # loot
glyph(">", 17, 5, GREEN)                                  # exit
glyph("+", 7, 4, AMBER); glyph("+", 10, 10, AMBER)        # doors
glyph("G", 13, 8, ORANGE)                                 # gas canister (alt hazard)
glyph("C", 12, 2, MAG)                                    # neutral crawler

# ---- TURN-1 INFO LAYER: enemy R intent (red danger) ----
# R will move west and threaten these tiles
for (tx, ty) in [(12, 6), (11, 6), (10, 6), (9, 6)]:
    glow_tile(tx, ty, RED, 34)
Rp = cellpx(13, 6, cx=True)
arrow(Rp, cellpx(9, 6, cx=True), RED, 3, 14)
glyph("R", 13, 6, RED)
text("rusza + gryzie", cellpx(9, 6)[0] - 6, cellpx(9, 6)[1] - 20, RED, 14, True)

# ---- reachable move dots around player ----
for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1), (1, -1), (1, 1), (-1, 1)]:
    cx, cy = pcx + ddx, pcy + ddy
    if 0 <= cy < ROWS and 0 <= cx < COLS and GRID[cy][cx] in ".+$>":
        dx, dy = cellpx(cx, cy, cx=True)
        pygame.draw.circle(surf, (74, 96, 120), (dx, dy), 4)

# ---- player + selected target ----
px, py = cellpx(pcx, pcy)
pygame.draw.rect(surf, (26, 46, 58), (px + 2, py + 2, TS - 5, TS - 5), border_radius=4)
glyph("@", pcx, pcy, BRIGHT)
glyph("r", 4, 6, RED, ring=RED)                            # selected target ring

# ============================================================================
# THE CONSEQUENCE PREVIEW — the star of the show
# the plan: shove r (SW) onto puddle; sparking wire arcs through water -> shock
# ============================================================================
# 1) shove path arrow from rat to its landing tile (3,7)
arrow(cellpx(4, 6, cx=True), cellpx(3, 7, cx=True), CYAN, 3, 13)
# 2) landing tile dashed ring
lpx, lpy = cellpx(3, 7)
pygame.draw.rect(surf, CYAN, (lpx + 2, lpy + 2, TS - 5, TS - 5), 2, border_radius=4)
# 3) electrified chain glow on puddle + wire (the systemic result)
for (cx, cy) in [(2, 7), (3, 7), (2, 8), (3, 8), (4, 7)]:
    glow_tile(cx, cy, CYAN, 70)
# little spark from wire into puddle
arrow(cellpx(4, 7, cx=True), cellpx(3, 7, cx=True), BRIGHT, 2, 9)
# 4) the plan callout
cbx, cby = ox - 4, oy + 9 * TS + 6
pygame.draw.rect(surf, (10, 30, 38), (cbx, cby, 360, 56), border_radius=7)
pygame.draw.rect(surf, CYAN, (cbx, cby, 360, 56), 1, border_radius=7)
text("PODGLĄD: pchnięcie → kałuża → łuk z przewodu", cbx + 12, cby + 8, CYAN, 15, True)
text("= 14 obr. (prąd) · cicho · 0 obrażeń dla ciebie", cbx + 12, cby + 31, BRIGHT, 14)

# board legend
text("@ ty   r/R wrogowie   C crawler (neutralny)   $ łup   ~ kałuża   | przewód   "
     "G butla gazu   > zejście", BX + 14, CY1 - 26, DIM, 13)

# ============================================================================
# RIGHT RAIL — player, target, actions, log
# ============================================================================
# player card
pcard_h = 150
panel(RX, CY0, RW, pcard_h, "BEZIMIENNY  ·  Żołnierz")
text("HP", RX + 14, CY0 + 44, DIM, 14)
bar(RX + 44, CY0 + 44, 230, 14, 0.67, HPCOL)
text("67 / 100", RX + 284, CY0 + 43, BRIGHT, 14)
text("AC 14", RX + 14, CY0 + 72, TXT, 15)
text("Nóż  (powlekany: kwas)", RX + 100, CY0 + 72, AMBER, 15)
text("Stan:", RX + 14, CY0 + 98, DIM, 14)
pygame.draw.rect(surf, (60, 36, 32), (RX + 64, CY0 + 96, 70, 22), border_radius=11)
text("ranny", RX + 99, CY0 + 107, ORANGE, 13, True, center=True)
text("materiały: 3× złom · 1× kwas · 2× szmata", RX + 14, CY0 + 124, DIM, 13)

# target card
ty0 = CY0 + pcard_h + 12
tcard_h = 188
panel(RX, ty0, RW, tcard_h, "CEL  ▸  Tunelowy Szczurek", RED)
text("HP", RX + 14, ty0 + 44, DIM, 14)
bar(RX + 44, ty0 + 44, 200, 12, 0.55, RED, (44, 28, 30))
text("12 / 22", RX + 252, ty0 + 43, BRIGHT, 13)
text("AC 10        threat: spokojny", RX + 14, ty0 + 68, TXT, 14)
text("Słaby na:", RX + 14, ty0 + 94, DIM, 14)
for i, (w, c) in enumerate([("ogień", ORANGE), ("prąd", CYAN)]):
    chip = RX + 90 + i * 78
    pygame.draw.rect(surf, (40, 34, 24), (chip, ty0 + 92, 70, 22), border_radius=11)
    text(w, chip + 35, ty0 + 103, c, 14, True, center=True)
text("Gruba skóra — zwykłe ciosy się ślizgają.", RX + 14, ty0 + 122, DIM, 13)
pygame.draw.rect(surf, (50, 30, 30), (RX + 14, ty0 + 146, RW - 28, 28), border_radius=6)
text("Zamiar tej rundy:  ugryzienie (3–5 obr.)", RX + 24, ty0 + 153, RED, 14, True)

# action palette
ay0 = ty0 + tcard_h + 12
acard_h = 236
panel(RX, ay0, RW, acard_h, "DZIAŁANIA  (jeden klawisz = jedno)", GREEN)
acts = [
    ("strzałki / WSAD", "ruch — wejście na wroga = atak", BRIGHT),
    ("Q / E", "pchnij wroga (w kałużę, w gaz…)", CYAN),
    ("F", "rzuć (butla, kwas, wabik)", CYAN),
    ("C", "powlecz broń (kwas / ogień / prąd)", AMBER),
    ("Z", "crafting z materiałów", AMBER),
    ("Tab", "przełącz cel    ·    . czekaj", DIM),
    ("I", "plecak    ·    Esc menu", DIM),
]
for i, (key, desc, c) in enumerate(acts):
    yy = ay0 + 44 + i * 26
    pygame.draw.rect(surf, (30, 36, 30), (RX + 14, yy - 2, 116, 22), border_radius=5)
    text(key, RX + 72, yy + 1, GREEN, 13, True, center=True, f=mono(13, True))
    text(desc, RX + 140, yy, c, 14)

# log (the DCC soul stays)
ly0 = ay0 + acard_h + 12
panel(RX, ly0, RW, CY1 - ly0, "DZIENNIK", MAG)
log = [
    ("Wchodzisz w korytarz. Szczurek już cię zwietrzył.", DIM),
    ("Sprawdzasz go: gruba skóra, ale boi się prądu.", TXT),
    ("Obnażony przewód iskrzy tuż obok kałuży…", TXT),
    ("» Wybierasz: pchnięcie ku wodzie.", CYAN),
    ("Drugi szczur (R) rusza zza filaru.", AMBER),
    ("Konferansjer: „Widzowie czują, że coś", MAG),
    (" tu zaraz pięknie zaiskrzy. +6 widowni.”", MAG),
]
for i, (l, c) in enumerate(log):
    text(l, RX + 14, ly0 + 42 + i * 24, c, 14)

# ============================================================================
# BOTTOM HINT BAR
# ============================================================================
pygame.draw.line(surf, BORDER, (16, H - 44), (W - 16, H - 44), 1)
text("Wszystko widać na planszy: co zrobią wrogowie (czerwone pola), gdzie możesz wejść (kropki), "
     "i co da spryt (podgląd na cyan).",
     24, H - 36, DIM, 14)
text("brute działa — tylko wolniej i boli", W - 24, H - 36, AMBER, 14, right=True)

pygame.image.save(surf, "_mockup_ideal.png")
print("wrote _mockup_ideal.png")
