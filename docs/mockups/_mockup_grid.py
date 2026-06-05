"""Mockup #2: the TACTICAL GRID as the game (not a map you look at).

Shows a mid-encounter moment: @ and monsters as actors on one board,
fog-of-war, a hazard you can use by positioning, telegraphed enemy intent
drawn ON the board. The point is SPACE: distance, line, the corridor, the
puddle — tension comes from the board, not a menu.

Renders _mockup_grid.png. Throwaway. Run: python _mockup_grid.py
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

W, H = 1600, 900
surf = pygame.Surface((W, H))

BG=(10,12,16); PANEL=(18,22,30); BORDER=(44,52,66)
WALL=(48,54,68); WALLHI=(78,88,110); FLOOR=(20,24,32); FLOOR2=(25,30,39)
DIM=(120,130,145); TXT=(205,214,228); BRIGHT=(238,244,253)
CYAN=(95,205,232); MAG=(222,92,182); AMBER=(242,192,92)
RED=(224,84,84); GREEN=(112,202,132); HP=(92,200,120)
DARKVEIL=(6,7,10)

def mono(s,b=False): return pygame.font.SysFont("Consolas,DejaVu Sans Mono,monospace", s, b)
def txt(s,x,y,c=TXT,sz=18,b=False): surf.blit(mono(sz,b).render(s,True,c),(x,y))

surf.fill(BG)

# top bar
pygame.draw.rect(surf,PANEL,(0,0,W,40)); pygame.draw.line(surf,CYAN,(0,40),(W,40),1)
txt("▣ SORTOWNIA ZAWODNIKÓW · Piętro 1 · Runda 4",16,9,CYAN,20,True)
txt("Termin 13d 22h",1120,11,AMBER,18); txt("● WIDOWNIA 47",1300,11,MAG,18,True)

# board region (big, square-ish, the FOCUS)
BX,BY,BW,BH = 16,56,1180,700
pygame.draw.rect(surf,(7,9,13),(BX,BY,BW,BH)); pygame.draw.rect(surf,BORDER,(BX,BY,BW,BH),1)

TS=44
# Tactical board. legend below. Designed as a readable encounter:
#  walls form a corridor + a room; player @ in the open; rat r adjacent-ish;
#  a second rat R two tiles off; captain C far (neutral, not engaged);
#  puddle ~ + wire | next to it (shove combo); loot $; exit >
GRID = [
 "###############################",
 "#.........#..........#........#",
 "#..$......#....r.....#...C....#",
 "#.........+..........#........#",
 "#.........#...@...............#",
 "#....~~...#..........#........#",
 "#....~~|..#.....R....#....>...#",
 "#.........#..........#........#",
 "#.........###+########........#",
 "#............................##",
 "###############################",
]
# fog: reveal a radius around the player; dim/hide the rest
def find(ch):
    for y,l in enumerate(GRID):
        x=l.find(ch)
        if x>=0: return x,y
    return None
pcx,pcy = find('@')

def visible(cx,cy,px,py,r=6):
    return (cx-px)**2 + (cy-py)**2 <= r*r

ox,oy = BX+20, BY+18
for gy,line in enumerate(GRID):
    for gx,ch in enumerate(line):
        px=ox+gx*TS; py=oy+gy*TS
        if px>BX+BW-TS or py>BY+BH-TS: continue
        seen = visible(gx,gy,pcx,pcy,6)
        if not seen:
            # unexplored: near-black, faint grid
            pygame.draw.rect(surf,(11,13,18),(px,py,TS-2,TS-2))
            continue
        # distance dim for soft vignette
        d=((gx-pcx)**2+(gy-pcy)**2)**0.5
        fade=max(0.35,1.0-d/8.0)
        if ch=='#':
            c=tuple(int(v*fade) for v in WALL)
            pygame.draw.rect(surf,c,(px,py,TS-2,TS-2))
            pygame.draw.rect(surf,tuple(int(v*fade) for v in WALLHI),(px,py,TS-2,TS-2),1)
            continue
        base = FLOOR2 if (gx+gy)%2==0 else FLOOR
        pygame.draw.rect(surf,tuple(int(v*fade) for v in base),(px,py,TS-2,TS-2))
        def g(s,col,dx=12,dy=4,sz=30):
            txt(s,px+dx,py+dy,col,sz,True)
        if ch=='~': pygame.draw.rect(surf,(16,42,54),(px,py,TS-2,TS-2)); g("≈",CYAN,13,6,26)
        elif ch=='|': g("|",AMBER,18,2,30)
        elif ch=='+': g("+",AMBER)
        elif ch=='>': g(">",GREEN)
        elif ch=='$': g("$",AMBER)
        elif ch=='r': g("r",RED)
        elif ch=='R': g("R",RED)
        elif ch=='C': g("C",MAG)
        elif ch=='@':
            pygame.draw.rect(surf,(28,48,60),(px,py,TS-2,TS-2)); g("@",BRIGHT,12,2,30)

# --- on-board overlays: this is what makes it tactical, not a menu ---
def cell(gx,gy): return ox+gx*TS, oy+gy*TS
# 1) selected-target highlight ring on the near rat
rxp,ryp=cell(*find('r'))
pygame.draw.rect(surf,RED,(rxp-1,ryp-1,TS,TS),2)
# enemy intent telegraph: arrow from rat toward player + label
pgx,pgy=cell(pcx,pcy)
pygame.draw.line(surf,RED,(rxp+TS//2,ryp+TS//2),(pgx+TS//2,pgy+TS//2),2)
txt("⚔ zaraz cię ugryzie",rxp-20,ryp-22,RED,15,True)
# 2) the SHOVE combo hint: dotted line rat->puddle, label
wxp,wyp=cell(5,5)  # puddle tile
txt("↳ wepchnij w kałużę (prąd)",wxp-6,wyp+TS+2,CYAN,14,True)
# 3) movement reachable tiles (faint dots) around player — "you can step here"
for ddx,ddy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
    tx,ty=cell(pcx+ddx,pcy+ddy)
    pygame.draw.circle(surf,(70,90,110),(tx+TS//2,ty+TS//2),3)

# legend
txt("@ ty   r/R wrogowie   C crawler (neutralny — nie w walce)   "
    "$ łup   ≈ kałuża  | przewód   + drzwi   > zejście",
    BX+14, BY+BH-26, DIM, 15)

# --- right column: lean, glanceable, NO tabs ---
SX=BX+BW+16; SW=W-SX-16
def panel(x,y,w,h,title=None,tc=CYAN):
    pygame.draw.rect(surf,PANEL,(x,y,w,h)); pygame.draw.rect(surf,BORDER,(x,y,w,h),1)
    if title: txt(title,x+10,y+6,tc,15,True)

panel(SX,BY,SW,120,"BEZIMIENNY · Żołnierz")
txt("HP",SX+12,BY+32,DIM,15)
pygame.draw.rect(surf,(40,30,30),(SX+44,BY+32,300,14)); pygame.draw.rect(surf,HP,(SX+44,BY+32,200,14))
txt("67/100",SX+250,BY+31,BRIGHT,13)
txt("AC 14   tani nóż   Stan: ranny",SX+12,BY+54,TXT,15)
txt("[c] coat broń   [z] crafting   [i] plecak",SX+12,BY+82,GREEN,14)

panel(SX,BY+132,SW,160,"CEL ▸ Tunelowy Szczurek",RED)
txt("HP 12/22  AC 10  threat: spokojny",SX+12,BY+160,TXT,15)
txt("Słaby na: ogień, prąd",SX+12,BY+182,AMBER,15)
txt("Zamiar: ugryzienie (w tej rundzie)",SX+12,BY+204,RED,15)
txt("Bump = atak. Albo zagraj otoczeniem.",SX+12,BY+236,DIM,14)
txt("[strzałki] ruch/atak  [f] rzuć  [t] gadaj",SX+12,BY+258,GREEN,14)

panel(SX,BY+302,SW,398,"DZIENNIK")
log=[("Wchodzisz w korytarz. Szczurek już cię zwietrzył.",DIM),
     ("Cofasz się o krok — zwabiasz go ku kałuży.",TXT),
     ("Szczurek wchodzi na mokre kafle.",TXT),
     ("Tniesz przewód: iskra → woda → PRĄD.",GREEN),
     ("„Tunelowy Szczurek”: -14 (porażony). Drży.",GREEN),
     ("Drugi szczur (R) rusza zza filaru.",AMBER),
     ("Konferansjer: „Elegancko. Widownia +6.”",MAG)]
for i,(l,c) in enumerate(log):
    txt(l,SX+12,BY+330+i*26,c,15)

txt("› _",BX+14,H-32,BRIGHT,18,True)
txt("ruch i atak = strzałki/WSAD (jeden klawisz robi jedno) · "
    "czekaj . · Esc menu", BX+90,H-30,DIM,14)

pygame.image.save(surf,"_mockup_grid.png")
print("wrote _mockup_grid.png")
