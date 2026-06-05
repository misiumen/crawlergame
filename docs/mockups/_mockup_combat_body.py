"""Combat with EMBODIMENT inside the grid.

The enemy is not a glyph and not a paper doll with slots: it's a procedural
body assembled from its tags, carrying located + persistent + systemic damage.
This frame is frozen on the instant an acid-coated machete lands on a foreleg:
the body is mid-recoil, the leg corrodes, the hide still burns from before, a
flank bleeds, a hind leg is broken. The readout IS the body. Renders _combat_body.png.
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
ACID=(156,206,92); BLOOD=(150,32,36); BLOODB=(196,44,48); CHAR=(28,24,22); FLESH=(108,88,86)

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
        text(title,x+12,y+9,tc,14,True); pygame.draw.line(S,BORDER,(x+12,y+32),(x+w-12,y+32),1)
def bar(x,y,w,h,frac,col,bg=(38,30,32)):
    pygame.draw.rect(S,bg,(x,y,w,h),border_radius=h//2)
    if frac>0: pygame.draw.rect(S,col,(x,y,max(h,int(w*frac)),h),border_radius=h//2)
def chip(x,y,label,col,filled=False,sz=13):
    w=font(sz,True).size(label)[0]+22
    if filled: pygame.draw.rect(S,col,(x,y,w,22),border_radius=11)
    else: pygame.draw.rect(S,(col[0]//4+16,col[1]//4+16,col[2]//4+16),(x,y,w,22),border_radius=11)
    pygame.draw.rect(S,col,(x,y,w,22),1,border_radius=11)
    text(label,x+w//2,y+11,(16,18,24) if filled else col,sz,True,center=True); return w
def arrow(p1,p2,col,wd=3,head=12):
    pygame.draw.line(S,col,p1,p2,wd); ang=math.atan2(p2[1]-p1[1],p2[0]-p1[0])
    for da in (math.radians(150),math.radians(-150)):
        pygame.draw.line(S,col,p2,(p2[0]+head*math.cos(ang+da),p2[1]+head*math.sin(ang+da)),wd)
def glow(rect,col,a):
    g=pygame.Surface((rect[2],rect[3]),pygame.SRCALPHA); g.fill((col[0],col[1],col[2],a)); S.blit(g,(rect[0],rect[1]))
def radial(cx,cy,r,col,a):
    g=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
    for i in range(r,0,-2):
        aa=int(a*(i/r)); pygame.draw.circle(g,(col[0],col[1],col[2],a-aa),(r,r),r-i)
    S.blit(g,(cx-r,cy-r))
def flame(x,y,s,c1=ORANGE,c2=AMBER):
    pygame.draw.polygon(S,c1,[(x,y-s),(x-s*0.55,y+s*0.2),(x,y+s*0.5),(x+s*0.55,y+s*0.2)])
    pygame.draw.polygon(S,c2,[(x,y-s*0.55),(x-s*0.3,y+s*0.15),(x,y+s*0.35),(x+s*0.3,y+s*0.15)])
def burst(x,y,r,col,spikes=10):
    pts=[]
    for i in range(spikes*2):
        ang=math.pi*i/spikes; rr=r if i%2==0 else r*0.45
        pts.append((x+rr*math.cos(ang),y+rr*math.sin(ang)))
    pygame.draw.polygon(S,col,pts)

S.fill(BG)
vg=pygame.Surface((W,H),pygame.SRCALPHA)
for i in range(60): pygame.draw.rect(vg,(0,0,0,int(2.2*i)),(i,i,W-2*i,H-2*i),1)
S.blit(vg,(0,0))

# ---------- grid tokens (procedural bodies, not letters) ----------
def rat_token(cx,cy,r,facing=-1,burning=False,bleeding=False,sel=False,col=(108,86,84)):
    if sel:
        pygame.draw.circle(S,RED,(cx,cy),r+10,2)
    pygame.draw.line(S,col,(cx-facing*r*0.6,cy),(cx-facing*r*1.5,cy-r*0.5),max(2,r//6))  # tail
    pygame.draw.ellipse(S,col,(cx-r,cy-r*0.6,r*2,r*1.2))                                  # body
    pygame.draw.circle(S,col,(cx+facing*r*0.9,cy),int(r*0.55))                            # head
    pygame.draw.circle(S,(70,54,52),(cx+facing*r*0.9,cy-r*0.45),int(r*0.22))              # ear
    pygame.draw.circle(S,(16,14,16),(int(cx+facing*r*1.05),int(cy-2)),2)                  # eye
    if burning:
        flame(cx-3,cy-r*0.7,r*0.55); flame(cx+r*0.4,cy-r*0.6,r*0.45)
    if bleeding:
        pygame.draw.circle(S,BLOODB,(int(cx-r*0.4),int(cy+r*0.5)),3)
def player_token(cx,cy,r):
    pygame.draw.circle(S,(30,52,64),(cx,cy),r+2)
    pygame.draw.circle(S,CYAN,(cx,cy),r,2)
    pygame.draw.circle(S,(60,180,210),(cx,cy-r*0.25),int(r*0.55))     # head/shoulders
    pygame.draw.line(S,BRIGHT,(cx-r*0.7,cy+r*0.3),(cx-r*1.2,cy-r*0.6),3)  # weapon glint

# ===================== TOP BANNER =====================
panel(16,12,W-32,66,fill=PANEL2)
text("STARCIE",30,22,RED,24,True)
text("Tunelowy Szczurek  x2    ·    Runda 2    ·    rozstrzygniecie ciosu",170,30,TXT,17)
text("WIDOWNIA",W-330,18,DIM,12,True); bar(W-330,38,210,10,0.58,MAG,(40,28,40))
text("58",W-100,16,MAG,22,True); text("+6 styl",W-100,42,GREEN,12,True)

CY0=92; CY1=H-16
# ===================== ARENA (left) =====================
BX,BW=24,860
panel(BX,CY0,BW,CY1-CY0,"ARENA",DIM,fill=(7,9,13))
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
for (hx,hy) in [(1,6),(2,6),(1,7),(2,7)]:
    px,py=cp(hx,hy); pygame.draw.rect(S,WATER,(px+2,py+2,TS-4,TS-4),border_radius=6)
for (hx,hy) in [(1,6),(2,7)]:
    x,y=cp(hx,hy,True); text("~",x,y,TEAL,int(TS*0.5),True,center=True,f=mono(int(TS*0.5),True))
def envg(ch,gx,gy,col):
    x,y=cp(gx,gy,True); text(ch,x,y-1,col,int(TS*0.55),True,center=True,f=mono(int(TS*0.55),True))
# R intent danger
for (tx,ty) in [(7,7),(6,7),(5,7)]: glow((ox+tx*TS+2,oy+ty*TS+2,TS-4,TS-4),RED,30)
arrow(cp(8,7,True),cp(5,7,True),RED,3,13)
envg("|",3,7,AMBER); envg("$",5,2,AMBER); envg(">",11,10,GREEN); envg("G",8,9,ORANGE)
# tokens (bodies, not letters)
rx,ry=cp(8,7,True); rat_token(rx,ry,int(TS*0.34),facing=-1,burning=True)         # R burning
sx,sy=cp(3,6,True); rat_token(sx,sy,int(TS*0.34),facing=1,bleeding=True,sel=True)# selected, hit
px,py=cp(4,6,True); player_token(px,py,int(TS*0.34))
# consequence preview
arrow(cp(3,6,True),cp(2,6,True),CYAN,3,12)
lpx,lpy=cp(2,6); pygame.draw.rect(S,CYAN,(lpx+2,lpy+2,TS-5,TS-5),2,border_radius=4)
for (cx,cy) in [(1,6),(2,6),(1,7),(2,7),(3,7)]: glow((ox+cx*TS+2,oy+cy*TS+2,TS-4,TS-4),CYAN,55)
cbx,cby=ox-2,oy+gh-54
pygame.draw.rect(S,(10,30,38),(cbx,cby,352,46),border_radius=7); pygame.draw.rect(S,CYAN,(cbx,cby,352,46),1,border_radius=7)
text("PODGLAD: pchniecie -> kaluza -> prad (14)",cbx+12,cby+7,CYAN,14,True)
text("rany zostaja — bedzie kulec do konca walki",cbx+12,cby+26,DIM,12)

# ===================== ENEMY BODY (the reacting readout) =====================
RX=900; RW=W-16-RX
eh=474; panel(RX,CY0,RW,eh,"CEL  ·  Tunelowy Szczurek",RED)
text("cialo z tagow:",RX+16,CY0+40,DIM,12)
cx=RX+118
for t in ["organiczne","czworonog","gruba skora","latwopalne"]:
    cx+=chip(cx,CY0+36,t,(120,110,130))+6
# --- the big body, mid-recoil ---
bcx,bcy=RX+330,CY0+250
# motion lines (recoil to the left from a hit on the right side)
for i in range(3):
    yy=bcy-30+i*30; pygame.draw.line(S,(120,150,170),(bcx+200+i*8,yy),(bcx+150,yy),2)
# tail
pygame.draw.line(S,FLESH,(bcx+140,bcy+6),(bcx+250,bcy-34),9)
# body
pygame.draw.ellipse(S,FLESH,(bcx-150,bcy-58,300,128))
pygame.draw.ellipse(S,(124,102,100),(bcx-140,bcy-10,280,68))          # belly
# charred + burning along the back
pygame.draw.ellipse(S,CHAR,(bcx-70,bcy-66,150,40))
flame(bcx-40,bcy-66,20); flame(bcx+4,bcy-72,24); flame(bcx+48,bcy-64,18)
# head (left), pained
pygame.draw.circle(S,FLESH,(bcx-150,bcy-2),52)
pygame.draw.polygon(S,FLESH,[(bcx-196,bcy-4),(bcx-232,bcy+4),(bcx-196,bcy+18)])  # snout
pygame.draw.circle(S,(70,54,52),(bcx-150,bcy-46),20)                  # ear
pygame.draw.arc(S,(16,14,16),(bcx-176,bcy-18,20,16),0.2,2.9,3)        # pained eye (squint)
# legs
pygame.draw.rect(S,FLESH,(bcx-96,bcy+54,22,46),border_radius=8)       # hind far (ok)
pygame.draw.rect(S,FLESH,(bcx+70,bcy+54,22,46),border_radius=8)       # front far (ok)
# --- WOUND 1: front-near leg CORRODED by acid (the just-landed hit) ---
lx,ly=bcx+18,bcy+58
pygame.draw.rect(S,(96,104,70),(lx,ly,24,48),border_radius=8)
for (dx,dy,rr) in [(4,8,5),(16,20,4),(8,32,6),(18,40,3)]:
    pygame.draw.circle(S,CHAR,(lx+dx,ly+dy),rr)                       # pitting
for (dx,dy) in [(6,52),(20,58),(12,64)]:
    pygame.draw.circle(S,ACID,(lx+dx,ly+dy),4)                        # acid drip
glow((lx-8,ly-6,40,70),ACID,40)
# --- WOUND 2: hind-near leg BROKEN (bent wrong) ---
hx,hy=bcx-44,bcy+54
pygame.draw.line(S,FLESH,(hx,hy),(hx-2,hy+24),20)
pygame.draw.line(S,FLESH,(hx-2,hy+24),(hx+26,hy+40),18)               # bent the wrong way
pygame.draw.circle(S,BLOOD,(hx-2,hy+24),6)
# --- WOUND 3: flank BLEEDING gash ---
gx,gy=bcx-10,bcy+6
pygame.draw.line(S,BLOOD,(gx-30,gy-14),(gx+18,gy+14),7)
pygame.draw.line(S,BLOODB,(gx-26,gy-10),(gx+14,gy+12),3)
for (dx,dy) in [(-18,30),(-6,42),(6,36)]:
    pygame.draw.circle(S,BLOODB,(gx+dx,gy+dy),4)
# --- IMPACT (acid machete landing on the corroded leg) ---
ix,iy=lx+12,ly+6
radial(ix,iy,70,(220,255,180),120)
burst(ix,iy,46,(240,255,210)); burst(ix,iy,30,ACID)
for ang in range(0,360,40):
    ex=ix+58*math.cos(math.radians(ang)); ey=iy+58*math.sin(math.radians(ang))
    pygame.draw.circle(S,ACID,(int(ex),int(ey)),4)
text("-14",ix+34,iy-58,BRIGHT,30,True)
text("KOROZJA!",ix+34,iy-26,ACID,16,True)
# --- status callouts with leader lines to body parts ---
def callout(tx,ty,px,py,label,col):
    pygame.draw.line(S,col,(tx,ty),(px,py),1)
    w=font(13,True).size(label)[0]+16
    bx=tx-(w if tx>bcx else 0)
    pygame.draw.rect(S,(18,18,24),(bx,ty-11,w,22),border_radius=6); pygame.draw.rect(S,col,(bx,ty-11,w,22),1,border_radius=6)
    text(label,bx+w//2,ty,col,13,True,center=True)
callout(RX+RW-40,CY0+96,bcx+10,bcy-64,"plonie  2t  (-2 HP/turę)",ORANGE)
callout(RX+RW-40,CY0+150,gx,gy,"krwawienie  3t",BLOOD if False else BLOODB)
callout(RX+40,CY0+150,hx,hy+30,"zlamana noga  -ruch",RED)
callout(RX+40,CY0+360,lx+12,ly+30,"korozja  -3 AC",ACID)
# HP + intent
text("HP",RX+16,CY0+eh-92,DIM,14); bar(RX+44,CY0+eh-92,260,16,0.32,RED,(44,28,30)); text("7/22",RX+316,CY0+eh-93,BRIGHT,14)
text("Threat: sploszony (szuka ucieczki)",RX+360,CY0+eh-92,AMBER,14)
pygame.draw.rect(S,(50,30,30),(RX+16,CY0+eh-58,RW-32,42),border_radius=7)
text("ZAMIAR: kuleje do kaluzy — chce uciec.  (dobij albo pchnij)",RX+30,CY0+eh-46,RED,15,True)

# ===================== YOU =====================
yy0=CY0+eh+10; yhh=104; panel(RX,yy0,RW,yhh,"TY")
text("HP",RX+14,yy0+42,DIM,14); bar(RX+44,yy0+42,240,14,0.67,HPCOL); text("67/100",RX+296,yy0+41,BRIGHT,14)
text("Maczeta",RX+14,yy0+70,BRIGHT,14,True); chip(RX+96,yy0+68,"powloka: kwas (2 ciosy)",AMBER)
text("Postawa: agresywna",RX+330,yy0+70,RED,14)

# ===================== ACTIONS =====================
ay0=yy0+yhh+10; ahh=132; panel(RX,ay0,RW,ahh,"DZIALANIA",GREEN)
verbs=[("A","Atak"),("H","Ciezki"),("U","Unik"),("Q","Pchnij"),
       ("F","Rzuc"),("E","Otoczenie"),("Z","Craft"),("Esc","Uciekaj")]
for i,(k,d) in enumerate(verbs):
    gx=i%4; gy=i//4; cx=RX+16+gx*200; cy=ay0+42+gy*40
    pygame.draw.rect(S,(24,32,26),(cx,cy,190,32),border_radius=6); pygame.draw.rect(S,(40,60,44),(cx,cy,190,32),1,border_radius=6)
    pygame.draw.rect(S,(34,46,36),(cx+4,cy+4,44,24),border_radius=4)
    text(k,cx+26,cy+15,GREEN,13,True,center=True,f=mono(13,True)); text(d,cx+58,cy+8,TXT,14)

# ===================== LOG =====================
ly0=ay0+ahh+10; panel(RX,ly0,RW,CY1-ly0,"DZIENNIK",MAG)
for i,(l,c) in enumerate([("Tniesz maczeta — kwas wzera sie w lape. -14, korozja.",ACID),
                          ("Szczur kuleje, jeszcze sie pali. Threat spada.",ORANGE),
                          ("Konferansjer: „To bylo paskudne. Widzowie to kochaja.”",MAG)]):
    text(l,RX+14,ly0+40+i*24,c,14)

pygame.image.save(S,"_combat_body.png"); print("wrote _combat_body.png")
