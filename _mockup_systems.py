"""Mockups of EVERY reworked system, one frame each, shared visual language.

Throwaway. Renders a set of _sys_*.png frames so the whole game can be
imagined end-to-end in the proposed board-first UI. Run: python _mockup_systems.py

Frames:
  _sys_1_explore.png    exploration / movement / world-as-interactable
  _sys_2_salvage.png    dismantle the world into materials (Dysmantle)
  _sys_3_craft.png      tag-based crafting (known + improvised)
  _sys_4_gear.png       inventory / equipment / weapon coating (Dead Island)
  _sys_5_map.png        floor map / route gambling (FTL)
  _sys_6_dialogue.png   NPC talk, social + memetic options (no parser)
  _sys_7_memetics.png   seed a belief, watch it propagate
  _sys_8_class.png      emergent class offer (the game reads how you play)
  _sys_9_summary.png    run end / unlocks (DCC replay hook)
(combat is _mockup_ideal.png)
"""
import os, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.font.init()

W, H = 1760, 1000

BG=(12,14,19); PANEL=(20,24,32); PANEL2=(26,31,41); BORDER=(46,54,70)
GRID_L=(40,46,60); WALL=(52,60,78); WALLHI=(84,96,122)
FLOOR=(22,26,35); FLOOR2=(27,32,43); UNSEEN=(9,11,15)
DIM=(118,128,146); TXT=(202,211,226); BRIGHT=(240,246,255)
CYAN=(96,206,233); TEAL=(70,150,168); MAG=(224,96,188)
AMBER=(244,194,96); RED=(228,86,86); ORANGE=(240,138,70)
GREEN=(118,206,138); HPCOL=(96,202,124); WATER=(22,58,74)
PURPLE=(160,130,232)

S = None
_f={}
def font(sz,b=False):
    k=(sz,b)
    if k not in _f: _f[k]=pygame.font.SysFont("Segoe UI, Arial", sz, bold=b)
    return _f[k]
_m={}
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

def chip(x,y,label,col,filled=False,w=None,sz=14,pad=12):
    tw=font(sz,True).size(label)[0]; w=w or tw+pad*2
    if filled: pygame.draw.rect(S,col,(x,y,w,24),border_radius=12)
    else: pygame.draw.rect(S,(col[0]//4+18,col[1]//4+18,col[2]//4+18),(x,y,w,24),border_radius=12)
    pygame.draw.rect(S,col,(x,y,w,24),1,border_radius=12)
    text(label,x+w//2,y+12,(18,20,26) if filled else col,sz,True,center=True)
    return w

def arrow(p1,p2,col,wd=3,head=12):
    pygame.draw.line(S,col,p1,p2,wd)
    ang=math.atan2(p2[1]-p1[1],p2[0]-p1[0])
    for da in (math.radians(150),math.radians(-150)):
        S and pygame.draw.line(S,col,p2,(p2[0]+head*math.cos(ang+da),p2[1]+head*math.sin(ang+da)),wd)

def new():
    s=pygame.Surface((W,H),pygame.SRCALPHA); s.fill(BG); return s

def save(name):
    pygame.image.save(S,name); print("wrote",name)

def topbar(sub):
    panel(16,12,W-32,52,fill=PANEL2)
    text("SORTOWNIA ZAWODNIKOW",30,22,CYAN,20,True)
    text(sub,330,26,DIM,16)
    text("TERMIN",W-470,20,DIM,12,True); text("13d 22h",W-470,34,AMBER,17,True)
    text("WIDOWNIA",W-330,20,DIM,12,True); bar(W-330,38,220,10,0.47,MAG,(40,28,40))
    text("47",W-96,18,MAG,22,True)

def backdrop():
    # faint board behind modals so they feel in-game
    S.fill(BG)
    for x in range(0,W,44): pygame.draw.line(S,(16,19,26),(x,0),(x,H),1)
    for y in range(0,H,44): pygame.draw.line(S,(16,19,26),(0,y),(W,y),1)
    ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((8,10,14,150)); S.blit(ov,(0,0))

def silhouette(cx,cy,sc=1.0,col=(70,82,104)):
    pygame.draw.circle(S,col,(cx,int(cy-70*sc)),int(26*sc))          # head
    pygame.draw.rect(S,col,(cx-int(30*sc),int(cy-44*sc),int(60*sc),int(86*sc)),border_radius=12) # torso
    pygame.draw.rect(S,col,(cx-int(48*sc),int(cy-40*sc),int(16*sc),int(70*sc)),border_radius=8)   # arm L
    pygame.draw.rect(S,col,(cx+int(32*sc),int(cy-40*sc),int(16*sc),int(70*sc)),border_radius=8)   # arm R
    pygame.draw.rect(S,col,(cx-int(24*sc),int(cy+40*sc),int(18*sc),int(64*sc)),border_radius=8)   # leg L
    pygame.draw.rect(S,col,(cx+int(6*sc),int(cy+40*sc),int(18*sc),int(64*sc)),border_radius=8)    # leg R

# ============================================================ FRAME 1: EXPLORE
def frame_explore():
    global S; S=new()
    topbar("Pietro 1  ·  Eksploracja  ·  cisza")
    CY0=74; CY1=H-52
    LX,LW=16,196; BX=LX+LW+12; RW=380; RX=W-16-RW; BW=RX-12-BX
    # left rail
    panel(LX,CY0,LW,196,"MAPA PIETRA")
    for (a,b) in [((60,70),(110,100)),((110,100),(150,140)),((110,100),(70,150))]:
        pygame.draw.line(S,BORDER,(LX+a[0],CY0+a[1]),(LX+b[0],CY0+b[1]),2)
    for p,cur in [((60,70),0),((110,100),1),((150,140),0),((70,150),0)]:
        pygame.draw.circle(S,CYAN if cur else (70,80,100),(LX+p[0],CY0+p[1]),9 if cur else 6)
        if cur: pygame.draw.circle(S,CYAN,(LX+p[0],CY0+p[1]),14,2)
    panel(LX,CY0+208,LW,150,"TO POMIESZCZENIE",AMBER)
    for i,(nm,c) in enumerate([("drewniane meble",AMBER),("terminal",CYAN),
                               ("zamkniete drzwi",RED),("kamera sponsora",MAG),
                               ("Pchlip (crawler)",GREEN)]):
        text("· "+nm,LX+14,CY0+250+i*22,c,14)
    panel(LX,CY0+370,LW,CY1-(CY0+370),"OBECNE WYJSCIA",GREEN)
    for i,e in enumerate(["polnoc -> ?","wschod -> zbadane","luk w podlodze?"]):
        text(e,LX+14,CY0+410+i*24,TXT,14)
    # board
    panel(BX,CY0,BW,CY1-CY0,fill=(8,10,14))
    text("MAGAZYN CZESCI",BX+14,CY0+10,DIM,13,True)
    GRID=["###################","#........#........#","#..F.....#...T....#",
          "#........#........#","#....@...+........#","#........#.......>#",
          "#..F..N..#...$....#","#........#........#","#..L#####+#####c..#",
          "#........#........#","#........#........#","###################"]
    COLS,ROWS=len(GRID[0]),len(GRID)
    pad=16; TS=min((BW-pad*2)//COLS,((CY1-CY0)-40-pad)//ROWS)
    gw,gh=TS*COLS,TS*ROWS; ox=BX+(BW-gw)//2; oy=CY0+36+((CY1-CY0-36)-gh)//2
    def cp(gx,gy,c=False): return (ox+gx*TS+(TS//2 if c else 0),oy+gy*TS+(TS//2 if c else 0))
    pcx,pcy=5,4
    for gy,line in enumerate(GRID):
        for gx,ch in enumerate(line):
            px,py=cp(gx,gy)
            if ch=='#':
                pygame.draw.rect(S,WALL,(px,py,TS-1,TS-1))
                pygame.draw.line(S,WALLHI,(px,py),(px+TS-1,py),1); continue
            base=FLOOR2 if (gx+gy)%2==0 else FLOOR
            pygame.draw.rect(S,base,(px,py,TS-1,TS-1)); pygame.draw.rect(S,GRID_L,(px,py,TS-1,TS-1),1)
    def gl(ch,gx,gy,col,ring=None):
        if ring:
            g=pygame.Surface((TS-4,TS-4),pygame.SRCALPHA); g.fill((ring[0],ring[1],ring[2],40))
            S.blit(g,(ox+gx*TS+2,oy+gy*TS+2))
            pygame.draw.rect(S,ring,(ox+gx*TS+2,oy+gy*TS+2,TS-5,TS-5),2,border_radius=4)
        x,y=cp(gx,gy,True); text(ch,x,y-1,col,int(TS*0.55),True,center=True,f=mono(int(TS*0.55),True))
    # reachable dots
    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(1,-1),(-1,1),(1,1)]:
        cx,cy=pcx+dx,pcy+dy
        if GRID[cy][cx] in ".+$>": x,y=cp(cx,cy,True); pygame.draw.circle(S,(74,96,120),(x,y),4)
    gl("F",3,2,AMBER,ring=AMBER); gl("F",3,6,AMBER)              # salvageable
    gl("T",13,2,CYAN); gl("L",3,8,RED); gl("c",17,8,MAG)        # terminal/locked/camera
    gl("$",13,6,AMBER); gl(">",17,5,GREEN); gl("N",6,6,GREEN)   # loot/exit/npc
    gl("+",8,4,AMBER); gl("+",8,8,AMBER)
    x,y=cp(pcx,pcy); pygame.draw.rect(S,(26,46,58),(x+2,y+2,TS-5,TS-5),border_radius=4); gl("@",pcx,pcy,BRIGHT)
    # hover popover on the highlighted furniture (top-left F)
    fx,fy=cp(3,2); pop=(fx+TS+6,fy-6,250,118)
    pygame.draw.rect(S,(16,18,26),pop,border_radius=8); pygame.draw.rect(S,AMBER,pop,1,border_radius=8)
    text("drewniane meble",pop[0]+12,pop[1]+10,AMBER,15,True)
    text("[wood] [heavy] [salvageable]",pop[0]+12,pop[1]+32,DIM,12)
    for i,(k,a) in enumerate([("Spr","sprawdz"),("Roz","rozbierz -> materialy"),("Pch","pchnij")]):
        text(k,pop[0]+14,pop[1]+58+i*18,GREEN,13,True,f=mono(13,True))
        text(a,pop[0]+58,pop[1]+58+i*18,TXT,13)
    text("@ ty   F meble (rozbieralne)   T terminal   L zamek   c kamera   N crawler   $ lup   > zejscie",
         BX+14,CY1-26,DIM,13)
    # right rail
    panel(RX,CY0,RW,150,"BEZIMIENNY  ·  Zolnierz")
    text("HP",RX+14,CY0+44,DIM,14); bar(RX+44,CY0+44,230,14,0.85,HPCOL); text("85 / 100",RX+284,CY0+43,BRIGHT,14)
    text("AC 14",RX+14,CY0+72,TXT,15); text("Noz  (powlekany: kwas)",RX+100,CY0+72,AMBER,15)
    text("materialy: 3x zlom · 1x kwas · 2x szmata",RX+14,CY0+104,DIM,13)
    text("[Z] crafting   [I] plecak   [C] powlecz",RX+14,CY0+126,GREEN,14)
    panel(RX,CY0+162,RW,236,"AKCJE  (jeden klawisz = jedno)",GREEN)
    for i,(k,d) in enumerate([("strzalki/WSAD","ruch"),("[Enter]","uzyj / sprawdz cel"),
                              ("[Roz]","rozbierz obiekt"),("[F]","rzuc"),("[T]","gadaj z crawlerem"),
                              ("[Tab]","nastepny obiekt"),(". ","czekaj  ·  Esc menu")]):
        yy=CY0+206+i*26
        pygame.draw.rect(S,(30,36,30),(RX+14,yy-2,128,22),border_radius=5)
        text(k,RX+78,yy+1,GREEN,13,True,center=True,f=mono(13,True)); text(d,RX+152,yy,TXT,14)
    ly=CY0+410; panel(RX,ly,RW,CY1-ly,"DZIENNIK",MAG)
    for i,(l,c) in enumerate([("Magazyn czesci. Cisza, ktora cos ukrywa.",DIM),
                              ("Meble az sie prosza o rozbiorke.",TXT),
                              ("Pchlip macha do ciebie zza regalu.",GREEN),
                              ("Kamera sponsora obraca sie ku tobie.",MAG),
                              ("Konferansjer: „Pokaz im cos.”",MAG)]):
        text(l,RX+14,ly+42+i*24,c,14)
    pygame.draw.line(S,BORDER,(16,H-44),(W-16,H-44),1)
    text("Eksploracja to ruch po planszy. Wszystko ma afordancje (sprawdz/rozbierz/pchnij) — swiat jest surowcem.",
         24,H-36,DIM,14)
    save("_sys_1_explore.png")

# ============================================================ FRAME 2: SALVAGE
def frame_salvage():
    global S; S=new(); backdrop()
    mw,mh=1180,640; mx,my=(W-mw)//2,(H-mh)//2
    panel(mx,my,mw,mh,"ROZBIORKA  ·  swiat = surowiec",AMBER,fill=PANEL2)
    # left: object
    panel(mx+20,my+52,360,mh-72,"OBIEKT")
    pygame.draw.rect(S,(40,32,22),(mx+60,my+110,280,150),border_radius=10)
    pygame.draw.rect(S,AMBER,(mx+60,my+110,280,150),1,border_radius=10)
    text("drewniane meble",mx+200,my+285,AMBER,18,True,center=True)
    cx=mx+50
    for i,t in enumerate(["wood","heavy","salvageable"]):
        cx+=chip(cx,my+310,t,AMBER)+8
    text("Stary stol, krzeslo albo cos z tej rodziny.",mx+40,my+352,DIM,14)
    text("Trzyma sie honoru.",mx+40,my+372,DIM,14)
    # center: yields + progress
    panel(mx+400,my+52,400,mh-72,"CO ODZYSKASZ",GREEN)
    yields=[("drewno",  "1-4", GREEN),("sruby","0-2",TXT),("szmata","0-1",TXT)]
    for i,(nm,q,c) in enumerate(yields):
        yy=my+108+i*44
        pygame.draw.rect(S,(20,30,24),(mx+420,yy,360,34),border_radius=6)
        text(nm,mx+436,yy+8,c,16,True); text(q+" szt.",mx+760,yy+8,BRIGHT,15,right=True)
    text("Proba: SILA  DC 8",mx+420,my+250,TXT,15,True)
    bar(mx+420,my+278,360,16,0.7,AMBER,(40,34,24)); text("rozbieram...",mx+600,my+277,(18,20,26),13,True,center=True)
    text("Powodzenie 86%",mx+420,my+300,DIM,13)
    text("Krytyk -> bonus: caly komplet + 1 trofeum",mx+420,my+332,GREEN,13)
    # right: costs/risks
    panel(mx+820,my+52,mw-840,mh-72,"KOSZT / RYZYKO",RED)
    for i,(l,c) in enumerate([("Czas: ~2 min (termin tyka)",AMBER),
                              ("Halas +1 -> moze zwabic wroga",ORANGE),
                              ("Swiadek (crawler obok): -reputacja",RED),
                              ("Material zuzyty: brak",DIM)]):
        text("· "+l,mx+836,my+108+i*34,c,15)
    pygame.draw.rect(S,(20,40,26),(mx+836,my+mh-140,150,40),border_radius=8)
    pygame.draw.rect(S,GREEN,(mx+836,my+mh-140,150,40),1,border_radius=8)
    text("[E] Rozbierz",mx+911,my+mh-120,GREEN,15,True,center=True)
    text("[Esc] Zostaw",mx+1010,my+mh-120,DIM,15)
    text("Kazdy mebel, automat, zwloki i sciana to czesci. Z czesci robisz narzedzia. (Dysmantle)",
         mx+24,my+mh-48,DIM,14)
    save("_sys_2_salvage.png")

# ============================================================ FRAME 3: CRAFT
def frame_craft():
    global S; S=new(); backdrop()
    mw,mh=1260,680; mx,my=(W-mw)//2,(H-mh)//2
    panel(mx,my,mw,mh,"WARSZTAT POLOWY  ·  crafting z tagow",CYAN,fill=PANEL2)
    # left: materials pool
    panel(mx+20,my+52,300,mh-72,"MATERIALY (tagi)",AMBER)
    mats=[("zlom",3,"metal"),("kwas",1,"chem"),("szmata",2,"cloth"),
          ("przewod",2,"electric"),("bateria",1,"electric"),("butelka",1,"container")]
    for i,(nm,n,tag) in enumerate(mats):
        yy=my+104+i*52
        pygame.draw.rect(S,(28,26,20),(mx+34,yy,272,42),border_radius=6)
        text(nm,mx+50,yy+6,BRIGHT,16,True); text("x"+str(n),mx+50,yy+24,DIM,13)
        chip(mx+170,yy+9,tag,AMBER)
    # center: category + recipe list
    panel(mx+340,my+52,440,mh-72,"CO MOZESZ ZROBIC",GREEN)
    cats=["Pulapka","Bron","Powloka","Wabik","Narzedzie"]
    cx=mx+356
    for i,c in enumerate(cats):
        cx+=chip(cx,my+96,c,CYAN,filled=(i==0))+8
    recipes=[("Pulapka pradowa","[electric][wire]",True,GREEN),
             ("Butelka z kwasem","[chem][container]",True,GREEN),
             ("Powloka: kwas","[chem]",True,GREEN),
             ("Pulapka ogniowa","[flammable][spark]",False,DIM),
             ("Wabik dzwiekowy","[electronic][battery]",True,GREEN),
             ("Kolec na prad","[metal][electric]",True,GREEN)]
    for i,(nm,req,ok,c) in enumerate(recipes):
        yy=my+136+i*64
        sel=(i==0)
        pygame.draw.rect(S,(22,34,26) if ok else (26,24,28),(mx+356,yy,408,52),border_radius=7)
        if sel: pygame.draw.rect(S,CYAN,(mx+356,yy,408,52),2,border_radius=7)
        text(("> " if ok else "x ")+nm,mx+372,yy+8,c,16,True)
        text(req,mx+372,yy+28,DIM if ok else (90,70,70),13)
        text("OK" if ok else "brak tagow",mx+748,yy+18,GREEN if ok else RED,13,True,right=True)
    # right: selected recipe detail
    panel(mx+800,my+52,mw-820,mh-72,"PULAPKA PRADOWA",CYAN)
    text("Wymaga:",mx+820,my+100,DIM,14)
    chip(mx+900,my+96,"electric",CYAN); chip(mx+1010,my+96,"wire",CYAN)
    text("Masz: przewod x2, bateria x1  -> OK",mx+820,my+128,GREEN,14)
    text("Proba: INT  DC 13",mx+820,my+162,TXT,15,True)
    text("Wynik (podglad):",mx+820,my+198,DIM,14)
    tiers=[("krytyk","mistrzowska — +zasieg, ogluszenie",GREEN),
           ("sukces","dobra pulapka pradowa",TXT),
           ("czesc.","wadliwa (1 uzycie)",AMBER),
           ("porazka","nic — tracisz polowe mat.",RED)]
    for i,(k,d,c) in enumerate(tiers):
        yy=my+228+i*34
        text(k,mx+820,yy,c,14,True,f=mono(14,True)); text(d,mx+920,yy,c,14)
    text("Ryzyko: niestabilna (10%) -> iskrzy w plecaku",mx+820,my+372,ORANGE,13)
    pygame.draw.rect(S,(18,40,48),(mx+820,my+mh-128,200,44),border_radius=8)
    pygame.draw.rect(S,CYAN,(mx+820,my+mh-128,200,44),1,border_radius=8)
    text("[Z] Stworz",mx+920,my+mh-106,CYAN,16,True,center=True)
    text("Dwie sciezki: znane receptury + improwizacja (dobierasz tagi sam — gra nagradza eksperyment).",
         mx+24,my+mh-48,DIM,14)
    save("_sys_3_craft.png")

# ============================================================ FRAME 4: GEAR
def frame_gear():
    global S; S=new(); backdrop()
    mw,mh=1300,700; mx,my=(W-mw)//2,(H-mh)//2
    panel(mx,my,mw,mh,"EKWIPUNEK  ·  buduj swoja potege",AMBER,fill=PANEL2)
    # left: paperdoll
    panel(mx+20,my+52,380,mh-72,"POSTAC")
    silhouette(mx+210,my+260,1.15)
    slots=[("glowa","kaptur",mx+40,my+110),("tors","kamizelka",mx+40,my+200),
           ("rece","MACZETA",mx+40,my+290),("nogi","spodnie",mx+40,my+380),
           ("plecy","plecak +6",mx+40,my+470)]
    for nm,it,sx,sy in slots:
        pygame.draw.rect(S,(24,28,36),(sx,sy,150,40),border_radius=6)
        pygame.draw.rect(S,BORDER,(sx,sy,150,40),1,border_radius=6)
        text(nm,sx+10,sy+4,DIM,12); text(it,sx+10,sy+19,BRIGHT if it=="MACZETA" else TXT,14,True)
    text("HP 85/100   AC 14   SILA 13   ZRECZ 11",mx+40,my+mh-70,TXT,15)
    # center: backpack grid
    panel(mx+420,my+52,420,mh-72,"PLECAK",CYAN)
    items=["maczeta","noz","kwas x1","zlom x3","szmata","bandaz","butla gazu","wabik","mapa","-","-","-"]
    for i,it in enumerate(items):
        gx=i%3; gy=i//3; cellx=mx+440+gx*128; celly=my+108+gy*92
        pygame.draw.rect(S,(20,24,32) if it!="-" else (16,18,24),(cellx,celly,116,80),border_radius=8)
        pygame.draw.rect(S,BORDER,(cellx,celly,116,80),1,border_radius=8)
        if it!="-": text(it,cellx+58,celly+40,TXT,14,True,center=True)
    # right: selected item + coating
    panel(mx+860,my+52,mw-880,mh-72,"MACZETA",AMBER)
    text("obr. 2d6  ·  ciezka  ·  tnaca",mx+880,my+100,TXT,15)
    text("Stan: dobra (skrafiona)",mx+880,my+126,GREEN,14)
    text("POWLOKA BRONI",mx+880,my+170,DIM,14,True)
    coats=[("kwas","masz x1 — koroduje pancerz",GREEN,True),
           ("ogien","brak materialu",DIM,False),
           ("prad","masz bateria x1 — ogluszenie",CYAN,True)]
    for i,(nm,d,c,ok) in enumerate(coats):
        yy=my+204+i*54
        pygame.draw.rect(S,(28,30,22) if ok else (22,22,26),(mx+880,yy,mw-940,44),border_radius=7)
        if i==0: pygame.draw.rect(S,GREEN,(mx+880,yy,mw-940,44),2,border_radius=7)
        text(nm,mx+898,yy+6,c,16,True); text(d,mx+898,yy+24,DIM if ok else (90,70,70),13)
        text("[C]" if ok else "x",mx+mw-100,yy+12,GREEN if ok else RED,15,True,right=True)
    text("Powlekajac maczete kwasem zmieniasz JAK walczy — nie tylko liczby.",mx+880,my+400,TXT,14)
    text("To jest Dead Island: konkretne, brutalne narzedzia z czesci.",mx+880,my+424,DIM,13)
    text("Lup to wejscia do mocy: mniej +1 dmg, wiecej czesci, ktore craft zamienia w narzedzia.",
         mx+24,my+mh-48,DIM,14)
    save("_sys_4_gear.png")

# ============================================================ FRAME 5: MAP
def frame_map():
    global S; S=new()
    topbar("Mapa pietra  ·  wybierz droge")
    CY0=74; CY1=H-52
    panel(16,CY0,W-380,CY1-CY0,"MAPA PIETRA 1  ·  termin 13d 22h",CYAN,fill=(8,10,14))
    # node graph
    nodes={
      "start":(180,520,"safehouse",GREEN,"START · kafejka"),
      "combat1":(420,360,"combat",RED,"sortownia (walka)"),
      "loot":(420,640,"loot",AMBER,"magazyn (lup)"),
      "social":(700,250,"social",MAG,"bar (crawlerzy)"),
      "secret":(700,520,"secret",PURPLE,"? plotka"),
      "combat2":(960,400,"combat",RED,"hala (walka)"),
      "boss":(1180,300,"boss",ORANGE,"BOSS"),
      "exit":(1180,620,"exit",CYAN,"ZEJSCIE"),
    }
    edges=[("start","combat1",False),("start","loot",False),("combat1","social",False),
           ("combat1","secret",True),("loot","secret",False),("social","combat2",False),
           ("secret","combat2",False),("combat2","boss",False),("combat2","exit",False),
           ("secret","exit",True)]
    bx,by=24,CY0+10
    for u,v,locked in edges:
        p=(bx+nodes[u][0],by+nodes[u][1]); q=(bx+nodes[v][0],by+nodes[v][1])
        col=(70,50,50) if locked else BORDER
        pygame.draw.line(S,col,p,q,3 if not locked else 2)
        if locked:
            mxp=((p[0]+q[0])//2,(p[1]+q[1])//2); text("zamek",mxp[0],mxp[1]-8,RED,12,True,center=True)
    for k,(nx,ny,typ,col,label) in nodes.items():
        cx,cy=bx+nx,by+ny
        cur=(k=="start")
        pygame.draw.circle(S,(18,20,28),(cx,cy),30); pygame.draw.circle(S,col,(cx,cy),30,3)
        glyphs={"safehouse":"H","combat":"!","loot":"$","social":"@","secret":"?","boss":"B","exit":">"}
        text(glyphs[typ],cx,cy-2,col,26,True,center=True,f=mono(26,True))
        text(label,cx,cy+40,BRIGHT if cur else TXT,13,True,center=True)
        if cur: pygame.draw.circle(S,CYAN,(cx,cy),38,2)
        if k=="secret": text("(plotka — niepewne)",cx,cy+58,DIM,11,center=True)
    # side panel
    RX=W-360; panel(RX,CY0,344,CY1-CY0,"WYBRANA TRASA",AMBER)
    text("start -> magazyn -> ? -> hala -> zejscie",RX+14,CY0+46,TXT,14)
    text("2 niezalezne drogi do zejscia.",RX+14,CY0+72,GREEN,14)
    text("LEGENDA",RX+14,CY0+110,DIM,13,True)
    leg=[("H","safehouse — bezpiecznie, plotki",GREEN),("!","walka",RED),("$","lup",AMBER),
         ("@","crawlerzy — gadanie/handel",MAG),("?","plotka — moze pulapka, moze skarb",PURPLE),
         ("B","boss",ORANGE),(">","zejscie nizej",CYAN)]
    for i,(g,d,c) in enumerate(leg):
        yy=CY0+138+i*30
        text(g,RX+20,yy,c,16,True,f=mono(16,True)); text(d,RX+50,yy+1,TXT,13)
    panel(RX,CY0+370,344,CY1-(CY0+370),"PRESJA (FTL)",RED)
    for i,(l,c) in enumerate([("Termin tyka co ruch.",AMBER),
                              ("Im glebiej, tym wieksza widownia",MAG),
                              ("...i lepszy lup, i grozniej.",RED),
                              ("Plotka = hazard: skrot albo zguba.",PURPLE)]):
        text("· "+l,RX+14,CY0+412+i*30,c,14)
    save("_sys_5_map.png")

# ============================================================ FRAME 6: DIALOGUE
def frame_dialogue():
    global S; S=new()
    topbar("Bar „Pod Resetem”  ·  rozmowa")
    CY0=74; CY1=H-52
    # left: NPC
    panel(16,CY0,520,CY1-CY0,"PCHLIP  ·  crawler-zlomiarz",MAG)
    silhouette(16+260,CY0+260,1.3,(96,70,110))
    text("Nastawienie",16+30,CY0+440,DIM,14)
    bar(16+30,CY0+466,440,16,0.38,ORANGE,(40,30,30))
    text("nieufny",16+30,CY0+488,ORANGE,13); text("przyjazny",16+470,CY0+488,DIM,13,right=True)
    text("Wie cos o zejsciu. Boi sie sponsora.",16+30,CY0+524,DIM,14)
    text("Widownia oglada te rozmowe (+/- za styl).",16+30,CY0+548,MAG,13)
    # right: conversation
    RX=552; RW=W-16-RX
    panel(RX,CY0,RW,200,"")
    text("Pchlip mowi:",RX+18,CY0+16,DIM,13,True)
    text("„Nie znam cie. A tu kazdy, kogo nie znam,",RX+18,CY0+48,BRIGHT,19)
    text("predzej czy pozniej probuje mnie sprzedac.",RX+18,CY0+76,BRIGHT,19)
    text("Czego chcesz, swiezaku?”",RX+18,CY0+104,BRIGHT,19)
    text("trzyma reke na rurze. nie wstaje.",RX+18,CY0+148,DIM,14)
    panel(RX,CY0+216,RW,CY1-(CY0+216),"TWOJA ODPOWIEDZ  (1-5)",GREEN)
    opts=[("1","Pytam wprost o droge do zejscia.","szczere",TXT,GREEN),
          ("2","„Sam jestem zlomiarzem.” (zbliznienie)","[handel]",CYAN,CYAN),
          ("3","„Sponsor juz o tobie wie.” (blef)","[klamstwo] CHA DC 12",AMBER,AMBER),
          ("4","Zastraszam — pokazuje maczete.","[zastrasz] SILA",RED,RED),
          ("5","Zasiewam plotke: „maszyny go szukaja.”","[memetyka] -> swiat",PURPLE,PURPLE)]
    for i,(k,line,tag,tc,c) in enumerate(opts):
        yy=CY0+262+i*72
        pygame.draw.rect(S,(20,24,30),(RX+18,yy,RW-36,60),border_radius=8)
        pygame.draw.rect(S,c,(RX+18,yy,RW-36,60),1,border_radius=8)
        pygame.draw.circle(S,c,(RX+44,yy+30),16); text(k,RX+44,yy+29,(16,18,24),16,True,center=True)
        text(line,RX+76,yy+10,BRIGHT,16,True); chip(RX+76,yy+34,tag,tc)
    text("Brak parsera. Wybierasz reakcje. Opcje spoleczne i memetyczne sa rownie realne jak przemoc.",
         24,H-36,DIM,14)
    save("_sys_6_dialogue.png")

# ============================================================ FRAME 7: MEMETICS
def frame_memetics():
    global S; S=new()
    topbar("Memetyka  ·  zasiej przekonanie")
    CY0=74; CY1=H-52
    # left: compose
    panel(16,CY0,420,CY1-CY0,"ZASIEW",PURPLE)
    text("TWIERDZENIE",16+16,CY0+46,DIM,13,True)
    pygame.draw.rect(S,(24,20,32),(16+16,CY0+70,388,52),border_radius=8)
    text("„Maszyny szukaja serc w zywych.”",16+28,CY0+86,BRIGHT,16)
    text("METODA",16+16,CY0+140,DIM,13,True)
    cx=16+16
    for i,m in enumerate(["plotka","mit","klamstwo","kult"]):
        cx+=chip(cx,CY0+164,m,PURPLE,filled=(i==1))+8
    text("KANAL",16+16,CY0+208,DIM,13,True)
    cx=16+16
    for i,m in enumerate(["szept","radio","graffiti","safehouse"]):
        cx+=chip(cx,CY0+232,m,CYAN,filled=(i==2))+8
    text("Statystyka memu: WIS (mit/religia)",16+16,CY0+278,TXT,14)
    text("Wymaga: byc widzianym przy pisaniu",16+16,CY0+302,DIM,13)
    pygame.draw.rect(S,(30,22,40),(16+16,CY1-90,200,44),border_radius=8)
    pygame.draw.rect(S,PURPLE,(16+16,CY1-90,200,44),1,border_radius=8)
    text("[M] Zasiej",16+116,CY1-68,PURPLE,16,True,center=True)
    # center: propagation lifecycle
    BX=452; BW=W-16-360-BX
    panel(BX,CY0,BW,CY1-CY0,"PROPAGACJA  (zywy mem na pietrze)",PURPLE,fill=(10,9,14))
    stages=["ZASIANY","ZAUWAZONY","ROZNOSI SIE","ZNIEKSZTALCONY","INSTYTUCJA","BACKLASH"]
    n=len(stages); spacing=BW//(n); sy=CY0+120; cur=2
    for i,st in enumerate(stages):
        cxp=BX+spacing//2+i*spacing
        done=i<=cur
        if i<n-1: pygame.draw.line(S,PURPLE if i<cur else BORDER,(cxp+18,sy),(cxp+spacing-18,sy),3)
        col=PURPLE if done else (60,56,72)
        pygame.draw.circle(S,(20,16,28),(cxp,sy),18); pygame.draw.circle(S,col,(cxp,sy),18,3)
        if i==cur: pygame.draw.circle(S,BRIGHT,(cxp,sy),22,2)
        text(str(i+1),cxp,sy-1,col,15,True,center=True)
        text(st,cxp,sy+34,BRIGHT if i==cur else DIM,12,True,center=True)
    text("Aktualnie: ROZNOSI SIE  (szept + graffiti, +20% w safehouse)",BX+24,CY0+200,TXT,15)
    # stat bars
    for i,(nm,fr,c) in enumerate([("sila",0.7,PURPLE),("stabilnosc",0.4,CYAN),("znieksztalcenie",0.55,ORANGE)]):
        yy=CY0+250+i*42
        text(nm,BX+24,yy,DIM,14); bar(BX+170,yy,420,16,fr,c,(30,28,38))
        text(str(int(fr*100)),BX+600,yy-1,BRIGHT,14)
    text("MUTACJA TRESCI (rosnie ze znieksztalceniem):",BX+24,CY0+390,DIM,13,True)
    text("zasiane:  „maszyny szukaja serc w zywych”",BX+24,CY0+416,DIM,14)
    text("teraz:    „jak cie zlapia, wytna ci serce”",BX+24,CY0+440,ORANGE,15,True)
    text("Mem zmienia sie sam, gdy idzie przez tlum. Ty go tylko zaczales.",BX+24,CY1-40,DIM,14)
    # right: world effects
    RX=W-344; panel(RX,CY0,328,CY1-CY0,"EFEKT W SWIECIE",GREEN)
    for i,(l,c) in enumerate([("Wrogowie wahaja sie:",DIM),("  -1 do ataku (strach)",GREEN),
                              ("Crawlerzy powtarzaja plotke",TXT),("Sponsor zauwazyl mem",MAG),
                              ("  -> moze go wzmocnic LUB",DIM),("     uderzyc backlashem",RED)]):
        text(l,RX+16,CY0+50+i*30,c,14)
    panel(RX,CY0+260,328,CY1-(CY0+260),"KANALY",CYAN)
    for i,(l,on) in enumerate([("szept crawlerow",True),("graffiti",True),("radio maszyn",False),
                               ("replay sponsora",False),("czarny rynek",False)]):
        yy=CY0+300+i*30
        pygame.draw.circle(S,GREEN if on else (60,60,70),(RX+24,yy+8),6)
        text(l,RX+42,yy,TXT if on else DIM,14)
    save("_sys_7_memetics.png")

# ============================================================ FRAME 8: CLASS
def frame_class():
    global S; S=new(); backdrop()
    text("GRA CIE ROZGRYZLA",W//2,120,CYAN,40,True,center=True)
    text("Nie wybierasz klasy na starcie. Po kilku pietrach gra patrzy JAK grasz i proponuje, kim sie stajesz.",
         W//2,170,DIM,17,center=True)
    cards=[("SABOTER",PURPLE,[("skradanie",8),("pulapki",7),("sabotaz",6)],
            "Loch to twoja maszyna do psucia.","+pulapki w plecaku, ciche zabojstwa"),
           ("INZYNIER",CYAN,[("technika",7),("crafting",8),("elektryka",6)],
            "Czesci + prad = twoje zabawki.","+1 slot powloki, tansze crafty"),
           ("LOTR",AMBER,[("spryt",7),("gadanie",6),("zdrada",5)],
            "Wygrywasz, zanim wrog zrozumie.","+blef, +handel, +pierwsze uderzenie")]
    cw,ch=420,520; gap=40; total=cw*3+gap*2; sx=(W-total)//2; sy=240
    for i,(nm,col,aff,tag,perk) in enumerate(cards):
        x=sx+i*(cw+gap)
        sel=(i==0)
        pygame.draw.rect(S,PANEL2 if sel else PANEL,(x,sy,cw,ch),border_radius=12)
        pygame.draw.rect(S,col,(x,sy,cw,ch),3 if sel else 1,border_radius=12)
        pygame.draw.circle(S,col,(x+44,sy+44),16); text(str(i+1),x+44,sy+43,(16,18,24),18,True,center=True)
        text(nm,x+76,sy+30,col,26,True)
        text("„"+tag+"”",x+30,sy+90,TXT,16)
        text("DLACZEGO (twoje zagrania):",x+30,sy+140,DIM,13,True)
        for j,(an,av) in enumerate(aff):
            yy=sy+170+j*44
            text(an,x+30,yy,TXT,15); bar(x+150,yy+2,cw-180,14,av/10,col,(30,30,38))
            text(str(av),x+cw-30,yy,BRIGHT,14,right=True)
        pygame.draw.line(S,BORDER,(x+24,sy+330),(x+cw-24,sy+330),1)
        text("Dajemy:",x+30,sy+346,DIM,13,True)
        text(perk,x+30,sy+372,GREEN,15)
        if sel:
            pygame.draw.rect(S,(30,22,40),(x+30,sy+ch-70,cw-60,42),border_radius=8)
            text("[1] Zostan saboterem",x+cw//2,sy+ch-49,col,16,True,center=True)
    text("Klasa wyplywa z zachowania (afinity). Mozesz tez zignorowac i grac dalej bezklasowo.",
         W//2,sy+ch+50,DIM,15,center=True)
    save("_sys_8_class.png")

# ============================================================ FRAME 9: SUMMARY
def frame_summary():
    global S; S=new()
    S.fill((10,11,15))
    text("KONIEC BIEGU",W//2,90,RED,44,True,center=True)
    text("„Porazony pradem w kaluzy, ktora sam zwabiles wroga. Widownia placze ze smiechu.”",
         W//2,150,TXT,18,center=True)
    CY0=210; CY1=H-60
    # left: stats
    panel(60,CY0,500,CY1-CY0,"BILANS",AMBER)
    stats=[("Pietro","4 / ?"),("Czas zycia","41 min"),("Widownia (szczyt)","71"),
           ("Zabojstwa","9"),("  w tym sprytne","5"),("Materialy zebrane","37"),
           ("Skrafione narzedzia","6"),("Plotki zasiane","2")]
    for i,(k,v) in enumerate(stats):
        yy=CY0+56+i*44
        text(k,60+24,yy,DIM if k.startswith("  ") else TXT,16,b=not k.startswith("  "))
        text(v,60+476,yy,BRIGHT,17,True,right=True)
    # center: highlights
    panel(580,CY0,560,CY1-CY0,"MOMENTY (to ogladala widownia)",MAG)
    hi=[("Lancuch pradowy na 3 szczury naraz","+12 widowni",GREEN),
        ("Wepchnales strazaka w butle gazu","+9 widowni",GREEN),
        ("Skrafiona maczeta kwasowa z 4 czesci","styl",CYAN),
        ("Plotka „maszyny szukaja serc” urosla","sponsor zauwazyl",PURPLE),
        ("...a potem zabila cie wlasna kaluza","-ironia, +klip",ORANGE)]
    for i,(l,t,c) in enumerate(hi):
        yy=CY0+56+i*78
        pygame.draw.rect(S,(20,22,30),(580+20,yy,520,64),border_radius=8)
        pygame.draw.rect(S,c,(580+20,yy,520,64),1,border_radius=8)
        text(l,580+36,yy+12,BRIGHT,16,True); chip(580+36,yy+36,t,c)
    # right: unlocks
    panel(1160,CY0,540,CY1-CY0,"ODBLOKOWANE (do nastepnego biegu)",GREEN)
    unl=[("Cykl 2","kolejny przebieg lochu",True),
         ("Gatunek: Mutant","osiagnieto pietro 4+",True),
         ("Pochodzenie: Zlomiarz","37 materialow w 1 biegu",True),
         ("Przedmiot: Iskrownik","lancuch pradowy x3",True),
         ("Klasa: Saboter","odblokowana w biegu",True),
         ("Gatunek: Grzybica","pokonaj bossa (jeszcze nie)",False)]
    for i,(nm,d,ok) in enumerate(unl):
        yy=CY0+56+i*72
        pygame.draw.rect(S,(18,26,20) if ok else (22,20,22),(1160+20,yy,500,58),border_radius=8)
        pygame.draw.rect(S,GREEN if ok else (70,60,60),(1160+20,yy,500,58),1,border_radius=8)
        text(("+ " if ok else "x ")+nm,1160+36,yy+8,GREEN if ok else (120,100,100),17,True)
        text(d,1160+36,yy+32,DIM,13)
    pygame.draw.rect(S,(20,40,26),(W//2-160,H-48,320,36),border_radius=8)
    text("[Enter] Nowy bieg  ·  silniejszy start",W//2,H-30,GREEN,16,True,center=True)
    save("_sys_9_summary.png")

for fn in (frame_explore,frame_salvage,frame_craft,frame_gear,frame_map,
           frame_dialogue,frame_memetics,frame_class,frame_summary):
    fn()
print("done")
