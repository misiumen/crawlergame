"""Mockup: the TINKERING bench (deep, emergent, no fixed recipes, can fail).

You combine tagged scrap, not recipes. The combined TAGS suggest a function; a
skill roll decides quality; volatile combos can backfire; what you pull off once
gets remembered in your recipe book. Renders _tinker.png. Throwaway.
"""
import os, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
W, H = 1500, 900
S = pygame.Surface((W, H), pygame.SRCALPHA)

BG=(12,14,19); PANEL=(20,24,32); PANEL2=(26,31,41); BORDER=(46,54,70)
DIM=(118,128,146); TXT=(202,211,226); BRIGHT=(240,246,255)
CYAN=(96,206,233); MAG=(224,96,188); AMBER=(244,194,96)
RED=(228,86,86); ORANGE=(240,138,70); GREEN=(118,206,138); PURPLE=(160,130,232)

_f={}
def font(sz,b=False):
    k=(sz,b)
    if k not in _f: _f[k]=pygame.font.SysFont("Segoe UI, Arial", sz, bold=b)
    return _f[k]
def text(s,x,y,c=TXT,sz=17,b=False,center=False,right=False):
    img=font(sz,b).render(s,True,c); r=img.get_rect()
    if center: r.center=(x,y)
    elif right: r.topright=(x,y)
    else: r.topleft=(x,y)
    S.blit(img,r)
def panel(x,y,w,h,title=None,tc=CYAN,fill=PANEL):
    pygame.draw.rect(S,fill,(x,y,w,h),border_radius=8)
    pygame.draw.rect(S,BORDER,(x,y,w,h),1,border_radius=8)
    if title:
        text(title,x+12,y+9,tc,14,True); pygame.draw.line(S,BORDER,(x+12,y+32),(x+w-12,y+32),1)
def chip(x,y,label,col,sz=12):
    w=font(sz,True).size(label)[0]+16
    pygame.draw.rect(S,(col[0]//4+16,col[1]//4+16,col[2]//4+16),(x,y,w,20),border_radius=10)
    pygame.draw.rect(S,col,(x,y,w,20),1,border_radius=10)
    text(label,x+w//2,y+10,col,sz,True,center=True); return w
def bar(x,y,w,h,frac,col,bg=(40,30,32)):
    pygame.draw.rect(S,bg,(x,y,w,h),border_radius=h//2)
    pygame.draw.rect(S,col,(x,y,max(h,int(w*frac)),h),border_radius=h//2)

S.fill(BG)
panel(16,12,W-32,46,fill=PANEL2)
text("WARSZTAT  ·  majsterkowanie",30,22,CYAN,20,True)
text("łączysz złom, nie przepisy   ·   [I] zamknij",W-30,24,DIM,15,right=True)

CY0=72; CY1=H-58

# ---------- LEFT: materials with tags ----------
panel(16,CY0,360,CY1-CY0,"MATERIAŁY (tagi)",AMBER)
mats=[("przewód",2,[("conductive",CYAN),("electric",CYAN)]),
      ("złom",3,[("metal",DIM),("edge",DIM)]),
      ("kwas",1,[("chem",GREEN),("corrosive",GREEN)]),
      ("szmata",2,[("binding",AMBER),("soft",DIM)]),
      ("butelka",1,[("container",PURPLE),("fragile",RED)]),
      ("bateria",1,[("electric",CYAN),("power",CYAN)]),
      ("rurka",1,[("metal",DIM),("haft",DIM)])]
for i,(nm,n,tags) in enumerate(mats):
    yy=CY0+44+i*74
    sel = nm in ("przewód","butelka")
    pygame.draw.rect(S,(30,34,26) if sel else (22,26,34),(30,yy,332,62),border_radius=8)
    if sel: pygame.draw.rect(S,AMBER,(30,yy,332,62),2,border_radius=8)
    text(nm,44,yy+8,BRIGHT,17,True); text("x%d"%n,330,yy+8,DIM,14,right=True)
    cx=44
    for t,c in tags: cx+=chip(cx,yy+34,t,c)+6
text("(klik = dorzuć na stół)",30,CY1-26,DIM,12)

# ---------- CENTER: the bench ----------
BX=392; BW=470
panel(BX,CY0,BW,CY1-CY0,"STÓŁ  ·  dorzuć 2–4 rzeczy",CYAN)
slots=[("przewód",CYAN),("butelka",PURPLE),(None,None),(None,None)]
sx=BX+30
for i,(nm,c) in enumerate(slots):
    cellx=sx+(i%2)*215; celly=CY0+50+(i//2)*96
    filled = nm is not None
    pygame.draw.rect(S,(24,30,40) if filled else (16,19,26),(cellx,celly,200,82),border_radius=10)
    pygame.draw.rect(S,(c if filled else BORDER),(cellx,celly,200,82),2,border_radius=10)
    if filled: text(nm,cellx+100,celly+41,BRIGHT,18,True,center=True)
    else: text("pusty",cellx+100,celly+41,DIM,14,center=True)
text("Dobrane tagi:",BX+30,CY0+250,DIM,14,True)
cx=BX+150
for t,c in [("conductive",CYAN),("electric",CYAN),("container",PURPLE),("fragile",RED)]:
    cx+=chip(cx,CY0+248,t,c)+6
text("Próba: INT vs DC 13  (złożoność 2 + niestabilność)",BX+30,CY0+288,TXT,15)
text("Dorzuć szmatę/taśmę [binding] → stabilniej (−DC).",BX+30,CY0+312,DIM,13)
# big commit button
pygame.draw.rect(S,(18,40,48),(BX+30,CY1-86,BW-60,52),border_radius=10)
pygame.draw.rect(S,CYAN,(BX+30,CY1-86,BW-60,52),2,border_radius=10)
text("[Enter] SPRÓBUJ ZŁOŻYĆ",BX+BW//2,CY1-60,CYAN,18,True,center=True)
text("uda się… albo huknie",BX+BW//2,CY1-24,DIM,13,center=True)

# ---------- RIGHT TOP: fuzzy prediction + risk ----------
RX=878; RW=W-16-RX
panel(RX,CY0,RW,330,"PODGLĄD  (niepewny — nieodkryte)",PURPLE)
text("„Coś, co razi prądem na odległość.",RX+16,CY0+44,BRIGHT,17)
text(" Ładunek? Granat? Nie masz pewności.”",RX+16,CY0+66,BRIGHT,17)
text("Stabilność",RX+16,CY0+104,DIM,14); bar(RX+120,CY0+104,300,14,0.6,AMBER); text("60%",RX+430,CY0+103,BRIGHT,13)
text("Ryzyko",RX+16,CY0+130,DIM,14); bar(RX+120,CY0+130,300,14,0.35,RED,(40,28,30)); text("iskra",RX+430,CY0+129,RED,13,right=True)
text("MOŻLIWE WYNIKI:",RX+16,CY0+162,DIM,13,True)
tiers=[("krytyk","unikat: „+oszołomienie” (afiks)",GREEN),
       ("sukces","działający ładunek prądowy",TXT),
       ("częściowy","wadliwy — 1 użycie",AMBER),
       ("porażka","tracisz materiały",ORANGE),
       ("backfire","iskra: porażenie ciebie",RED)]
for i,(k,d,c) in enumerate(tiers):
    yy=CY0+188+i*26
    text(k,RX+20,yy,c,14,True); text(d,RX+130,yy,c,14)

# ---------- RIGHT BOTTOM: discovered recipe book ----------
RY=CY0+346
panel(RX,RY,RW,CY1-RY,"TWOJE RECEPTURY  (odkryte = pewniejsze)",GREEN)
book=[("Powłoka prądowa","przewód + szmata",True),
      ("Fiolka kwasu","kwas + butelka",True),
      ("Kolec na drzewcu","złom + rurka + szmata",True),
      ("???","nieodkryte — eksperymentuj",False),
      ("???","nieodkryte — eksperymentuj",False)]
for i,(nm,sub,known) in enumerate(book):
    yy=RY+44+i*40
    text(("+ " if known else "?  ")+nm,RX+16,yy,GREEN if known else DIM,16,True)
    text(sub,RX+40,yy+19,DIM,12)

text("Nie znasz przepisów na starcie. Eksperymentujesz tagami; co uda się raz — zapamiętujesz. "
     "Brawura = moc i ryzyko; [binding]/spokój = bezpieczniej.",
     24,H-44,DIM,14)

pygame.image.save(S,"_tinker.png"); print("wrote _tinker.png")
