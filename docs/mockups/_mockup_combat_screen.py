"""Dedicated COMBAT screen (Pokemon-style: exploration -> wipe -> battle view).

Keeps the tactical arena (so puddle/wire/push/fire combos survive) but gives
combat its own focused, detail-rich screen: body-zone targeting (VATS), status
clocks, full action bar, enemy detail, audience ticker. Renders _combat_screen.png.
"""
import os, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()
W, H = 1760, 1000
S = pygame.Surface((W, H), pygame.SRCALPHA)

BG=(10,11,16); PANEL=(20,24,32); PANEL2=(26,31,41); BORDER=(46,54,70)
GRID_L=(40,46,60); WALL=(52,60,78); WALLHI=(84,96,122)
FLOOR=(22,26,35); FLOOR2=(27,32,43)
DIM=(118,128,146); TXT=(202,211,226); BRIGHT=(240,246,255)
CYAN=(96,206,233); TEAL=(70,150,168); MAG=(224,96,188)
AMBER=(244,194,96); RED=(228,86,86); ORANGE=(240,138,70)
GREEN=(118,206,138); HPCOL=(96,202,124); WATER=(22,58,74); PURPLE=(160,130,232)

_f={}; _m={}
def font(sz,b=False):
    k=(sz,b)
    if k not in _f: _f[k]=pygame.font.SysFont("Segoe UI, Arial", sz, bold=b)
    return _f[k]
def mono(sz,b=False):
    k=(sz,b)
    if k not in _m: _m[k]=pygame.font.SysFont("Consolas, monospace", sz, bold=b)
    return _m[k]
def text(s,x,y,c=TXT,sz=17,b=False,center=False,right=False,f=None):
    img=(f or font(sz,b)).render(s,True,c); r=img.get_rect()
    if center: r.center=(x,y)
    elif right: r.topright=(x,y)
    else: r.topleft=(x,y)
    S.blit(img,r); return r
def panel(x,y,w,h,title=None,tc=CYAN,fill=PANEL):
    pygame.draw.rect(S,fill,(x,y,w,h),border_radius=8)
    pygame.draw.rect(S,BORDER,(x,y,w,h),1,border_radius=8)
    if title:
        text(title,x+12,y+9,tc,14,True)
        pygame.draw.line(S,BORDER,(x+12,y+32),(x+w-12,y+32),1)
def bar(x,y,w,h,frac,col,bg=(38,30,32)):
    pygame.draw.rect(S,bg,(x,y,w,h),border_radius=h//2)
    if frac>0: pygame.draw.rect(S,col,(x,y,max(h,int(w*frac)),h),border_radius=h//2)
def chip(x,y,label,col,filled=False,sz=13):
    w=font(sz,True).size(label)[0]+22
    if filled: pygame.draw.rect(S,col,(x,y,w,22),border_radius=11)
    else: pygame.draw.rect(S,(col[0]//4+16,col[1]//4+16,col[2]//4+16),(x,y,w,22),border_radius=11)
    pygame.draw.rect(S,col,(x,y,w,22),1,border_radius=11)
    text(label,x+w//2,y+11,(16,18,24) if filled else col,sz,True,center=True)
    return w
def arrow(p1,p2,col,wd=3,head=12):
    pygame.draw.line(S,col,p1,p2,wd)
    ang=math.atan2(p2[1]-p1[1],p2[0]-p1[0])
    for da in (math.radians(150),math.radians(-150)):
        pygame.draw.line(S,col,p2,(p2[0]+head*math.cos(ang+da),p2[1]+head*math.sin(ang+da)),wd)
def glow(rect,col,a):
    g=pygame.Surface((rect[2],rect[3]),pygame.SRCALPHA); g.fill((col[0],col[1],col[2],a)); S.blit(g,(rect[0],rect[1]))

S.fill(BG)
# arena spotlight vignette (sells "separate screen")
vg=pygame.Surface((W,H),pygame.SRCALPHA)
for i in range(60):
    a=int(2.2*i); pygame.draw.rect(vg,(0,0,0,a),(i,i,W-2*i,H-2*i),1)
S.blit(vg,(0,0))

# ===================== TOP BANNER =====================
panel(16,12,W-32,66,fill=PANEL2)
text("STARCIE",30,22,RED,24,True)
text("Tunelowy Szczurek  x2    ·    Runda 2    ·    tura GRACZA",170,30,TXT,17)
# turn order
ords=[("@",CYAN),("r",RED),("R",RED),("C",MAG)]
text("kolejnosc:",W-720,22,DIM,12,True)
for i,(g,c) in enumerate(ords):
    xx=W-630+i*34
    if i==0: pygame.draw.rect(S,(24,40,50),(xx-6,18,30,30),border_radius=6)
    text(g,xx+8,32,c,18,True,center=True,f=mono(18,True))
# audience ticker
text("WIDOWNIA",W-330,18,DIM,12,True); bar(W-330,38,210,10,0.52,MAG,(40,28,40))
text("52",W-100,16,MAG,22,True)
text("rosnie +",W-100,42,GREEN,12,True)

CY0=92; CY1=H-16

# ===================== ARENA (left) =====================
BX,BW=24,900
panel(BX,CY0,BW,CY1-CY0,"ARENA  ·  korytarz sortowni",DIM,fill=(7,9,13))
GRID=["#############","#...........#","#....$......#","#...........#","#...........#",
      "#...........#","#~~r@.......#","#~~|....R...#","#...........#","#.......G...#",
      "#..........>#","#############"]
COLS,ROWS=len(GRID[0]),len(GRID)
pad=16; TS=min((BW-pad*2)//COLS,((CY1-CY0)-44-pad)//ROWS)
gw,gh=TS*COLS,TS*ROWS; ox=BX+(BW-gw)//2; oy=CY0+40+((CY1-CY0-40)-gh)//2
def cp(gx,gy,c=False): return (ox+gx*TS+(TS//2 if c else 0),oy+gy*TS+(TS//2 if c else 0))
pcx,pcy=4,6
for gy,line in enumerate(GRID):
    for gx,ch in enumerate(line):
        px,py=cp(gx,gy)
        if ch=='#':
            pygame.draw.rect(S,WALL,(px,py,TS-1,TS-1)); pygame.draw.line(S,WALLHI,(px,py),(px+TS-1,py),1); continue
        base=FLOOR2 if (gx+gy)%2==0 else FLOOR
        pygame.draw.rect(S,base,(px,py,TS-1,TS-1)); pygame.draw.rect(S,GRID_L,(px,py,TS-1,TS-1),1)
# puddle
for (hx,hy) in [(1,6),(2,6),(1,7),(2,7)]:
    px,py=cp(hx,hy); pygame.draw.rect(S,WATER,(px+2,py+2,TS-4,TS-4),border_radius=6)
def gl(ch,gx,gy,col,ring=None):
    if ring:
        glow((ox+gx*TS+2,oy+gy*TS+2,TS-4,TS-4),ring,40)
        pygame.draw.rect(S,ring,(ox+gx*TS+2,oy+gy*TS+2,TS-5,TS-5),2,border_radius=4)
    x,y=cp(gx,gy,True); text(ch,x,y-1,col,int(TS*0.55),True,center=True,f=mono(int(TS*0.55),True))
# R intent (danger)
for (tx,ty) in [(7,7),(6,7),(5,7)]: glow((ox+tx*TS+2,oy+ty*TS+2,TS-4,TS-4),RED,32)
arrow(cp(8,7,True),cp(5,7,True),RED,3,14)
for (hx,hy) in [(1,6),(2,7)]:
    x,y=cp(hx,hy,True); text("~",x,y,TEAL,int(TS*0.5),True,center=True,f=mono(int(TS*0.5),True))
gl("|",3,7,AMBER); gl("$",5,2,AMBER); gl(">",11,10,GREEN); gl("G",8,9,ORANGE)
gl("R",8,7,RED)
# reachable dots
for dx,dy in [(0,-1),(1,0),(0,1),(1,-1),(1,1)]:
    cx,cy=pcx+dx,pcy+dy
    if GRID[cy][cx] in ".$>": x,y=cp(cx,cy,True); pygame.draw.circle(S,(74,96,120),(x,y),4)
# player + selected target
px,py=cp(pcx,pcy); pygame.draw.rect(S,(26,46,58),(px+2,py+2,TS-5,TS-5),border_radius=4); gl("@",pcx,pcy,BRIGHT)
gl("r",3,6,RED,ring=RED)
# consequence preview: shove r west onto puddle + wire arc
arrow(cp(3,6,True),cp(2,6,True),CYAN,3,12)
lpx,lpy=cp(2,6); pygame.draw.rect(S,CYAN,(lpx+2,lpy+2,TS-5,TS-5),2,border_radius=4)
for (cx,cy) in [(1,6),(2,6),(1,7),(2,7),(3,7)]: glow((ox+cx*TS+2,oy+cy*TS+2,TS-4,TS-4),CYAN,70)
# preview banner over arena
cbx,cby=ox-2,oy+gh-58
pygame.draw.rect(S,(10,30,38),(cbx,cby,372,48),border_radius=7); pygame.draw.rect(S,CYAN,(cbx,cby,372,48),1,border_radius=7)
text("PODGLAD: pchniecie -> kaluza -> luk -> 14 (prad)",cbx+12,cby+7,CYAN,14,True)
text("cicho · 0 obr. dla ciebie · widownia +6",cbx+12,cby+27,BRIGHT,13)
text("@ ty   r/R szczury   ~ kaluza   | przewod   G gaz   $ lup   > zejscie",BX+14,CY1-24,DIM,12)

# ===================== RIGHT COLUMN =====================
RX=940; RW=W-16-RX

# --- ENEMY DETAIL (body-zone targeting) ---
eh=420; panel(RX,CY0,RW,eh,"CEL  ·  Tunelowy Szczurek   (threat: spokojny)",RED)
# rat diagram (left sub)
dcx,dcy=RX+180,CY0+200
col=(96,74,76)
pygame.draw.ellipse(S,col,(dcx-78,dcy-34,150,72))                 # body
pygame.draw.circle(S,col,(dcx-92,dcy-4),30)                       # head
pygame.draw.circle(S,(70,52,54),(dcx-114,dcy-30),12)              # ear
pygame.draw.circle(S,(18,16,18),(dcx-104,dcy-10),4)               # eye
for lx in (-50,-10,30,62):                                        # legs
    pygame.draw.rect(S,col,(dcx+lx,dcy+26,12,30),border_radius=5)
pygame.draw.line(S,col,(dcx+70,dcy),(dcx+128,dcy-26),7)           # tail
# selected zone ring (head)
pygame.draw.circle(S,CYAN,(dcx-92,dcy-4),34,3)
text("wybrana strefa",dcx-92,dcy-46,CYAN,12,True,center=True)
# zone table (right sub)
tx=RX+360
text("STREFY CIALA",tx,CY0+44,DIM,13,True)
text("strefa",tx,CY0+68,DIM,12); text("traf.",tx+150,CY0+68,DIM,12); text("obr.",tx+220,CY0+68,DIM,12); text("HP",tx+290,CY0+68,DIM,12)
zones=[("Glowa","-2","x2.0","4/4",True),("Tors","+0","x1.0","12/12",False),
       ("Przednie lapy","-1","x0.8","3/3",False),("Tylne lapy","-1","x0.7","3/3",False)]
for i,(nm,th,dm,hp,sel) in enumerate(zones):
    yy=CY0+90+i*30
    if sel: pygame.draw.rect(S,(22,38,46),(tx-6,yy-3,400,26),border_radius=5)
    text(nm,tx,yy,CYAN if sel else TXT,14,b=sel); text(th,tx+150,yy,TXT,14)
    text(dm,tx+220,yy,AMBER,14); text(hp,tx+290,yy,TXT,14)
# HP + weaknesses + intent
text("HP calosc",tx,CY0+226,DIM,13); bar(tx+88,CY0+225,200,14,0.55,RED,(44,28,30)); text("12/22",tx+300,CY0+224,BRIGHT,13)
text("AC 10",tx,CY0+252,TXT,14)
text("Slaby na:",tx,CY0+284,DIM,13); chip(tx+78,CY0+281,"ogien",ORANGE); chip(tx+150,CY0+281,"prad",CYAN)
text("Gruba skora — zwykle ciosy sie slizgaja.",tx,CY0+312,DIM,12)
pygame.draw.rect(S,(50,30,30),(RX+16,CY0+eh-58,RW-32,42),border_radius=7)
text("ZAMIAR tej rundy:  rzuca sie — 3-5 obr. w tors",RX+30,CY0+eh-46,RED,15,True)

# --- YOU ---
yy0=CY0+eh+10; yhh=140; panel(RX,yy0,RW,yhh,"TY  ·  Bezimienny / Zolnierz")
text("HP",RX+14,yy0+42,DIM,14); bar(RX+44,yy0+42,260,14,0.67,HPCOL); text("67/100",RX+316,yy0+41,BRIGHT,14)
text("AC 14",RX+14,yy0+70,TXT,14); text("Postawa: defensywna (+2 AC)",RX+90,yy0+70,CYAN,14)
text("Maczeta",RX+14,yy0+98,BRIGHT,14,True); chip(RX+96,yy0+96,"powloka: kwas",AMBER)
text("Status:",RX+260,yy0+98,DIM,14); chip(RX+320,yy0+96,"ranny 2t",ORANGE)

# --- ACTIONS ---
ay0=yy0+yhh+10; ahh=150; panel(RX,ay0,RW,ahh,"DZIALANIA",GREEN)
verbs=[("A","Atak"),("H","Ciezki"),("U","Unik"),("O","Obrona"),("Q","Pchnij"),
       ("F","Rzuc"),("E","Otoczenie"),("Z","Craft"),("Tab","Cel"),("Esc","Uciekaj")]
for i,(k,d) in enumerate(verbs):
    gx=i%5; gy=i//5; cx=RX+16+gx*156; cy=ay0+42+gy*40
    pygame.draw.rect(S,(24,32,26),(cx,cy,148,32),border_radius=6); pygame.draw.rect(S,(40,60,44),(cx,cy,148,32),1,border_radius=6)
    pygame.draw.rect(S,(34,46,36),(cx+4,cy+4,40,24),border_radius=4)
    text(k,cx+24,cy+15,GREEN,13,True,center=True,f=mono(13,True)); text(d,cx+54,cy+8,TXT,14)
text("Szybkie przedmioty:",RX+16,ay0+126,DIM,12)
qx=RX+150
for i,(nm,c) in enumerate([("[1] Pulapka pradowa",CYAN),("[2] Butla gazu",ORANGE),("[3] Wabik",GREEN)]):
    w=font(12,True).size(nm)[0]+16
    pygame.draw.rect(S,(20,24,30),(qx,ay0+122,w,22),border_radius=6); pygame.draw.rect(S,c,(qx,ay0+122,w,22),1,border_radius=6)
    text(nm,qx+8,ay0+127,c,12,True); qx+=w+10

# --- LOG ---
ly0=ay0+ahh+10; panel(RX,ly0,RW,CY1-ly0,"DZIENNIK",MAG)
for i,(l,c) in enumerate([("Szczur R rusza zza filaru — zaraz dopadnie.",AMBER),
                          ("Cofasz sie, ustawiasz r przy kaluzy.",TXT),
                          ("» Wybierasz: pchniecie ku wodzie.",CYAN)]):
    text(l,RX+14,ly0+40+i*24,c,14)

pygame.image.save(S,"_combat_screen.png"); print("wrote _combat_screen.png")
