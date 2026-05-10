"""Text-to-video: procedural animated scene renderer with agents, camera FX, voice + music."""
import asyncio, math, os, subprocess, threading, uuid, wave
from typing import Optional

import edge_tts
import imageio
import imageio_ffmpeg
import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pydantic import BaseModel

router  = APIRouter()
_tasks: dict = {}

# ── request model ─────────────────────────────────────────────────────────────

class VideoRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    num_frames: int = 240
    fps: int        = 24
    width: int      = 1280
    height: int     = 720
    steps: int      = 25          # kept for API compat, unused
    guidance_scale: float = 7.5
    # agent & camera
    agent:           str   = "auto"   # auto | cinematic | nature | cosmic | urban | abstract | fantasy | retro
    camera_movement: str   = "auto"   # auto | slow_zoom | zoom_out | pan | dolly | handheld | orbit | static
    # audio
    voice_enabled:  bool  = False
    voice_text:     str   = ""        # blank = use prompt
    voice_name:     str   = "en-US-AriaNeural"
    voice_rate:     str   = "+0%"
    voice_pitch:    str   = "+0Hz"
    music_enabled:  bool  = True
    music_style:    str   = "auto"    # auto = pick by scene
    music_volume:   float = 0.30

# ── drawing helpers ────────────────────────────────────────────────────────────

def _lc(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

def _grad(W, H, stops):
    """Vertical multi-stop gradient returned as numpy uint8 array."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    n = len(stops) - 1
    for y in range(H):
        pos = y / H * n
        idx = min(int(pos), n-1)
        c   = _lc(stops[idx], stops[idx+1], pos - idx)
        arr[y, :] = c
    return arr

def _subtitle(img, text, W, H):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        cand = (cur+" "+w).strip()
        if len(cand) <= 56: cur = cand
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    lines = lines[:2]

    ov = Image.new("RGBA", (W, H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    try:    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
    except: font = ImageFont.load_default()

    y = H - 44
    for line in lines:
        bb = d.textbbox((0,0), line, font=font)
        tw = bb[2]-bb[0]
        x  = (W-tw)//2
        d.rounded_rectangle([x-10, y-4, x+tw+10, y+18], radius=6, fill=(0,0,0,165))
        d.text((x,y), line, font=font, fill=(255,255,180,255))
        y += 22
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def _ease(t): return t*t*(3-2*t)

# ── scene: SPACE ──────────────────────────────────────────────────────────────

def _space(W, H, t):
    arr = _grad(W, H, [(0,0,8),(8,0,22),(20,0,45)])

    # nebula blobs (vectorised)
    ys, xs = np.mgrid[0:H, 0:W]
    for cx, cy, r, col in [(W*.3,H*.4,100,(90,0,130)),(W*.72,H*.3,80,(0,50,140)),(W*.5,H*.7,70,(130,20,70))]:
        d   = np.sqrt((xs-cx)**2+(ys-cy)**2)
        a   = np.clip((1-d/r)**2*0.65, 0, 1)
        for i in range(3): arr[:,:,i] = np.clip(arr[:,:,i]+col[i]*a, 0, 255).astype(np.uint8)

    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    rng = np.random.default_rng(7)
    sx,sy = rng.integers(0,W,300), rng.integers(0,H,300)
    sr,sp = rng.uniform(.5,2.5,300), rng.uniform(0,2*math.pi,300)
    ox,oy = int(t*28), int(t*12)
    for i in range(300):
        tw  = .55+.45*math.sin(t*6*math.pi+sp[i])
        bri = int(150*tw+80)
        col = (bri, bri, min(255,bri+50))
        x,y = (sx[i]+ox)%W, (sy[i]+oy)%H
        r   = max(1,int(sr[i]*tw+.3))
        draw.ellipse([x-r,y-r,x+r,y+r], fill=col)

    # planet
    px = int(W*.83+math.sin(t*math.pi)*10)
    py = int(H*.22-math.cos(t*math.pi)*8)
    for r,c in [(32,(100,60,30)),(22,(150,100,55)),(12,(180,130,70))]:
        draw.ellipse([px-r,py-r,px+r,py+r], fill=c)
    for rx in range(-48,49):
        d = abs(rx)/32
        if 1.1<d<1.55:
            ry = int(rx*.22)
            if 0<=px+rx<W and 0<=py+ry<H:
                draw.point((px+rx,py+ry), fill=(190,150,110))
    return img

# ── scene: OCEAN ──────────────────────────────────────────────────────────────

def _ocean(W, H, t):
    arr = _grad(W, H, [(25,55,140),(220,95,25),(255,175,55)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    sx,sy = int(W*.65), int(H*.46-math.sin(t*math.pi*.3)*18)
    for r in range(52,0,-1):
        c = _lc((255,255,180),(255,100,15), 1-r/52)
        draw.ellipse([sx-r,sy-r,sx+r,sy+r], fill=c)

    # reflection
    for ry in range(H//2+15,H,3):
        ww = int((ry-H//2)*.55)+4
        b  = max(0,230-(ry-H//2)*3)
        draw.line([(sx-ww,ry),(sx+ww,ry)], fill=(b,b//2,0), width=2)

    # clouds
    for cx,cy,sc,spd in [(W*.18,H*.16,1.0,.9),(W*.58,H*.10,.75,.55),(W*.84,H*.24,.8,.7)]:
        cx = int((cx+t*spd*55)%(W+120)-60)
        for dx,dy,r in [(-28,0,20),(0,-9,26),(28,0,20),(46,6,16)]:
            rr=int(r*sc); draw.ellipse([cx+dx-rr,cy+dy-rr,cx+dx+rr,cy+dy+rr],fill=(255,205,155))

    base = H//2+18
    for col,amp,wl,spd,yoff in [
        ((18,75,155), 20,.024,2.1, 0),
        ((28,98,178), 13,.034,2.9,20),
        ((48,125,198), 8,.050,3.6,38),
    ]:
        pts = [(x, base+yoff+int(amp*math.sin(x*wl+t*spd*2*math.pi))) for x in range(W)]
        draw.polygon([(0,H)]+pts+[(W,H)], fill=col)
        foam = tuple(min(255,c+85) for c in col)
        for i in range(len(pts)-1): draw.line([pts[i],pts[i+1]], fill=foam, width=2)
    return img

# ── scene: FIRE / ROCKET ──────────────────────────────────────────────────────

def _fire(W, H, t):
    arr = _grad(W, H, [(5,5,20),(10,8,30),(15,10,40)])
    rng0 = np.random.default_rng(11)
    # stars
    for _ in range(90):
        sx,sy = rng0.integers(0,W), rng0.integers(0,int(H*.6))
        arr[sy,sx] = [210,210,225]
    # ground
    arr[H-45:,:] = [25,18,5]
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    lx,ly = W//2, H-45
    draw.rectangle([lx-35,ly-12,lx+35,ly], fill=(70,70,75))   # pad

    rkt_y = int(ly-65-_ease(t)*(H//2+50))
    for dx in range(-9,9): # body
        for dy in range(-42,0):
            ry,rx = rkt_y+dy, lx+dx
            if 0<=ry<H and 0<=rx<W: draw.point((rx,ry),fill=(195,200,220))
    for dy in range(-60,-42): # nose
        w=int((dy+60)*.55)
        for dx in range(-w,w):
            ry,rx=rkt_y+dy,lx+dx
            if 0<=ry<H and 0<=rx<W: draw.point((rx,ry),fill=(215,55,55))
    draw.rectangle([lx-18,rkt_y,lx+18,rkt_y+6],fill=(180,180,200)) # nozzle

    # fire particles
    rng2 = np.random.default_rng(int(t*500)%200)
    for _ in range(150):
        age = rng2.uniform(0,1)
        px  = lx+int(rng2.uniform(-22,22)*(1+age*1.5))
        py  = rkt_y+int(age*90)+rng2.integers(-6,6)
        if 0<=py<H and 0<=px<W:
            r=max(0,int(255*(1-age*.55))); g=max(0,int(185*(1-age)))
            sz = max(1,int(3*(1-age)))
            draw.ellipse([px-sz,py-sz,px+sz,py+sz],fill=(r,g,0))

    # smoke
    rng3 = np.random.default_rng(int(t*300+50)%150)
    for _ in range(60):
        age=rng3.uniform(.3,1)
        px=lx+int(rng3.uniform(-30,30)*age*2)
        py=rkt_y+int(age*140)
        if 0<=py<H and 0<=px<W:
            g=int(80+age*70); sz=int(age*8)
            draw.ellipse([px-sz,py-sz,px+sz,py+sz],fill=(g,g,g+10))

    # exhaust glow
    for r in range(45,0,-5):
        ov=Image.new("RGBA",(W,H),(0,0,0,0))
        ImageDraw.Draw(ov).ellipse([lx-r,rkt_y-r//3,lx+r,rkt_y+r],outline=(255,140,0,int(80*(1-r/45))),width=3)
        img=Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
        draw=ImageDraw.Draw(img)
    return img

# ── scene: SNOW ───────────────────────────────────────────────────────────────

def _snow(W, H, t):
    arr = _grad(W, H, [(42,52,82),(62,72,112),(82,92,132)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    def pine(cx,base,sc=1.0,col=(15,30,15)):
        levels=4
        for lv in range(levels):
            w=int((45-lv*7)*sc); y=base-int(lv*24*sc)
            draw.polygon([(cx,y-int(32*sc)),(cx-w,y),(cx+w,y)],fill=col)
        draw.rectangle([cx-int(5*sc),base,cx+int(5*sc),base+int(22*sc)],fill=(38,22,12))

    for cx,sc in [(35,1.3),(110,.9),(190,1.1),(W-190,1.15),(W-105,.85),(W-35,1.0)]:
        pine(int(cx),H-38,sc)
    draw.ellipse([-60,H-38,W+60,H+22],fill=(200,212,232))  # ground

    rng=np.random.default_rng(42)
    sx=rng.uniform(0,W,250); sy_s=rng.uniform(-H,H,250)
    sz=rng.uniform(1.5,4,250); spd=rng.uniform(.04,.12,250); drft=rng.uniform(-.01,.01,250)
    for i in range(250):
        fy=(sy_s[i]+t*spd[i]*H*6)%H
        fx=(sx[i]+t*drft[i]*W*5+math.sin(fy*.05)*14)%W
        r=max(1,int(sz[i]))
        b=rng.integers(190,256)
        draw.ellipse([fx-r,fy-r,fx+r,fy+r],fill=(b,b,255))
    return img

# ── scene: SUNSET ─────────────────────────────────────────────────────────────

def _sunset(W, H, t):
    p   = _ease(t)
    arr = _grad(W, H, [
        _lc((10,5,42),(22,18,65),p),
        _lc((90,22,85),(130,50,110),p),
        _lc((190,65,28),(225,90,45),p),
        _lc((255,165,28),(255,205,65),p),
        _lc((255,105,18),(255,145,42),p),
    ])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    sx = int(W*.50+math.cos(t*math.pi*.3)*32)
    sy = int(H*.50-math.sin(t*math.pi*.5)*42)
    for r in range(58,0,-2):
        c=_lc((255,75,0),(255,225,85),r/58)
        draw.ellipse([sx-r,sy-r,sx+r,sy+r],fill=c)

    for cx,cy,sc,spd in [(W*.14,H*.19,1.0,.85),(W*.58,H*.13,.72,.52),(W*.83,H*.27,.88,.68)]:
        cx=int((cx+t*spd*58)%(W+110)-55)
        c=_lc((205,105,38),(255,185,105),t*.5)
        for dx,dy,r in [(-26,0,18),(0,-8,23),(26,0,18),(42,6,14)]:
            rr=int(r*sc); draw.ellipse([cx+dx-rr,cy+dy-rr,cx+dx+rr,cy+dy+rr],fill=c)

    pts=[(0,H)]
    for x in range(0,W+1,4):
        y=int(H*.68+math.sin(x*.021)*13+math.sin(x*.007+1)*22)
        pts.append((x,y))
    pts.append((W,H))
    draw.polygon(pts,fill=(14,9,4))
    return img

# ── scene: CITY ───────────────────────────────────────────────────────────────

def _city(W, H, t):
    arr = _grad(W, H, [(4,7,24),(9,14,38),(18,24,58)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    rng0=np.random.default_rng(3)
    for _ in range(130):
        sx,sy=rng0.integers(0,W),rng0.integers(0,H//2)
        b=rng0.integers(140,255); draw.point((sx,sy),fill=(b,b,min(255,b+30)))

    mx,my=int(W*.86),int(H*.11)
    draw.ellipse([mx-22,my-22,mx+22,my+22],fill=(232,232,202))
    draw.ellipse([mx-14,my-20,mx+9,my+20],fill=(8,12,30))

    # city glow overlay
    glow=Image.new("RGBA",(W,H),(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    for y in range(H-130,H-75):
        a=int((y-(H-130))/55*65)
        gd.line([(0,y),(W,y)],fill=(80,38,0,a))
    img=Image.alpha_composite(img.convert("RGBA"),glow).convert("RGB")
    draw=ImageDraw.Draw(img)

    rng=np.random.default_rng(17)
    buildings=[]
    x=0
    while x<W:
        w=rng.integers(28,68); bh=rng.integers(55,185)
        draw.rectangle([x,H-bh,x+w,H],fill=(16,20,34))
        draw.line([(x+w//2,H-bh),(x+w//2,H-bh-16)],fill=(24,28,44),width=2)
        buildings.append((x,H-bh,w,bh))
        x+=w+rng.integers(2,7)

    rng2=np.random.default_rng((int(t*28)+1)%50)
    for (bx,by,bw,bh) in buildings:
        for wy in range(by+6,H-12,13):
            for wx in range(bx+5,bx+bw-4,11):
                if rng2.random()<.62:
                    c=rng2.choice([(255,240,148),(255,215,98),(195,218,255)])
                    draw.rectangle([wx,wy,wx+5,wy+7],fill=tuple(c))

    for i,spd,col in [(0,.32,(255,242,202)),(1,.52,(255,202,182)),(2,.21,(202,182,255))]:
        cx=int((t*spd*W*2+i*W//3)%W); cy=H-14
        draw.ellipse([cx-4,cy-3,cx+4,cy+3],fill=col)
        draw.ellipse([cx+16-4,cy-3,cx+16+4,cy+3],fill=col)
    for i,spd in [(0,.27),(1,.42)]:
        cx=int(W-(t*spd*W*2+i*W//2)%W)
        draw.ellipse([cx-4,H-18,cx+4,H-12],fill=(200,28,28))
    return img

# ── scene: FOREST ─────────────────────────────────────────────────────────────

def _forest(W, H, t):
    arr = _grad(W, H, [(28,48,68),(38,58,46),(18,38,28)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    rng=np.random.default_rng(6)
    for _ in range(380):
        rx=rng.uniform(0,W); ry_s=rng.uniform(0,H)
        fy=(ry_s+t*H*2.6)%H
        fx=rx+fy*.27
        draw.line([(fx,fy),(fx+4,fy+13)],fill=(155,178,218),width=1)

    sway=math.sin(t*2*math.pi)*3.5
    def pine(cx,h,col=(13,28,13)):
        lvs=max(2,h//22)
        for lv in range(lvs):
            w=int(h*.5-lv*h/lvs*.42); y=H-28-lv*h//lvs
            draw.polygon([(cx,y-h//lvs),(cx-w,y),(cx+w,y)],fill=col)
        draw.rectangle([cx-4,H-28,cx+4,H-8],fill=(28,18,9))

    for cx,h,sh in [(28,162,(9,23,9)),(92,132,(14,28,14)),(162,182,(11,26,11)),
                    (385,172,(9,23,9)),(442,142,(14,30,14)),(532,162,(11,25,11)),(574,122,(9,22,9))]:
        pine(int(cx+sway),h,sh)

    mist=Image.new("RGBA",(W,H),(0,0,0,0))
    md=ImageDraw.Draw(mist)
    for y in range(H-48,H-8):
        a=int((y-(H-48))/40*175)
        md.line([(0,y),(W,y)],fill=(195,218,238,a))
    img=Image.alpha_composite(img.convert("RGBA"),mist).convert("RGB")
    return img

# ── scene: MUSIC ──────────────────────────────────────────────────────────────

def _music(W, H, t):
    arr = _grad(W, H, [(4,2,16),(8,4,28),(12,6,38)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    for cx,hue,sw in [(W*.25,(145,65,255),55),(W*.5,(65,195,255),40),(W*.75,(255,65,155),50)]:
        swing=math.sin(t*2*math.pi+cx)
        ov=Image.new("RGBA",(W,H),(0,0,0,0))
        ovd=ImageDraw.Draw(ov)
        for r in range(80,0,-8):
            a=int(r/80*35)
            end_x=int(cx+swing*sw)
            ovd.line([(int(cx),0),(end_x,H-80)],fill=hue+(a,),width=r)
        img=Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
        draw=ImageDraw.Draw(img)

    n_bars=22; bar_w=W//(n_bars+1)
    for i in range(n_bars):
        freq=(i+1)*.75
        h=int(abs(math.sin(t*2*math.pi*freq+i*.42))*H*.58+18)
        x=(i+1)*bar_w-bar_w//2
        hf=i/n_bars
        r=int(255*(1-hf*.7)); g=int(95+hf*160); b=int(hf*255)
        for by in range(H-80,H-80-h,-1):
            frac=(H-80-by)/max(h,1)
            c=_lc((r,g,b),(255,255,255),frac*.45)
            draw.rectangle([x-bar_w//2+2,by,x+bar_w//2-2,by+1],fill=c)
        draw.ellipse([x-bar_w//2+1,H-80-h-4,x+bar_w//2-1,H-80-h+4],fill=(r,g,b))

    rng=np.random.default_rng((int(t*200)%100)+1)
    for _ in range(45):
        px=rng.integers(0,W); py=rng.integers(H-125,H-55)
        r2=rng.integers(1,4)
        c=(rng.integers(100,255),rng.integers(50,200),rng.integers(150,255))
        draw.ellipse([px-r2,py-r2,px+r2,py+r2],fill=c)
    return img

# ── scene: DIGITAL ────────────────────────────────────────────────────────────

def _digital(W, H, t):
    arr = _grad(W, H, [(2,12,6),(4,18,10),(6,24,14)])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    for x in range(0,W,26): draw.line([(x,0),(x,H)],fill=(0,28,10),width=1)
    for y in range(0,H,20): draw.line([(0,y),(W,y)],fill=(0,28,10),width=1)

    scan_y=int(t%1.0*H)
    draw.line([(0,scan_y),(W,scan_y)],fill=(0,168,62),width=2)
    draw.line([(0,(scan_y+1)%H),(W,(scan_y+1)%H)],fill=(0,84,30),width=1)

    try:    font=ImageFont.truetype("C:/Windows/Fonts/cour.ttf",11)
    except: font=ImageFont.load_default()

    rng=np.random.default_rng(55)
    col_x=[i*14+6 for i in range(W//14)]
    col_spd=rng.uniform(.22,.92,len(col_x))
    chars="01ABCDEF@#"
    for ci,cx in enumerate(col_x):
        hy=int(col_spd[ci]*t*H*2.2)%H
        for i in range(14):
            y=(hy-i*15)%H
            a=max(0,1-i/14.0)
            g=int(a*(205 if i==0 else 115))
            ch=rng.choice(list(chars))
            draw.text((cx-4,y),ch,font=font,fill=(0,g,int(g*.4)))

    if math.sin(t*7*math.pi)>.86:
        gy=int(rng.uniform(0,H-20)); gh=rng.integers(2,12)
        strip=np.array(img.crop((0,gy,W,gy+gh)))
        strip=np.roll(strip,rng.integers(-28,28),axis=1)
        img.paste(Image.fromarray(strip),(0,gy))
        draw=ImageDraw.Draw(img)
    return img

# ── scene: ABSTRACT ───────────────────────────────────────────────────────────

def _abstract(W, H, t):
    r1=int(100+80*math.sin(t*2*math.pi));    g1=int(50+50*math.sin(t*2*math.pi+2))
    b1=int(180+60*math.sin(t*2*math.pi+4)); r2=int(60+80*math.cos(t*2*math.pi+1))
    g2=int(20+60*math.cos(t*2*math.pi+3));   b2=int(120+70*math.cos(t*2*math.pi+5))
    arr = _grad(W, H, [(r1,g1,b1),(r2,g2,b2),(max(0,r1-45),max(0,g1-45),max(0,b1-45))])
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    rng=np.random.default_rng(22)
    px=rng.uniform(0,W,110); py=rng.uniform(0,H,110)
    pph=rng.uniform(0,2*math.pi,110); psp=rng.uniform(.5,2.0,110)
    for i in range(110):
        fx=(px[i]+math.sin(t*psp[i]*2*math.pi+pph[i])*32)%W
        fy=(py[i]+math.cos(t*psp[i]*2*math.pi+pph[i]+1)*22)%H
        r=max(1,int(2+math.sin(t*3+i)*1.8))
        br=int(195+55*math.sin(t*4+i))
        draw.ellipse([fx-r,fy-r,fx+r,fy+r],fill=(min(255,br+r1-100),br//2,min(255,br+b1-100)))

    for i,(cx,cy) in enumerate([(W*.3,H*.4),(W*.7,H*.55),(W*.5,H*.22),(W*.2,H*.7)]):
        for ri in range(4):
            ph=t*2*math.pi+i*1.8+ri
            rad=int(38+22*math.sin(ph)+ri*18)
            a=int(55+28*math.sin(ph))
            c=(min(255,r1+ri*18),min(255,g1+ri*15),min(255,b2+ri*20))
            ov=Image.new("RGBA",(W,H),(0,0,0,0))
            ImageDraw.Draw(ov).ellipse([cx-rad,cy-rad,cx+rad,cy+rad],outline=c+(a,),width=2)
            img=Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
            draw=ImageDraw.Draw(img)
    return img

# ── dispatch ───────────────────────────────────────────────────────────────────

_SCENES = {
    "space":    _space,
    "ocean":    _ocean,
    "fire":     _fire,
    "snow":     _snow,
    "sunset":   _sunset,
    "city":     _city,
    "forest":   _forest,
    "music":    _music,
    "digital":  _digital,
    "abstract": _abstract,
}

def _detect(prompt: str) -> str:
    low = prompt.lower()
    # check more-specific terms first to avoid false substring matches
    if any(k in low for k in ["space","galaxy","nebula","cosmos","universe","asteroid","orbit"]): return "space"
    if any(k in low for k in ["rocket","launch","spacecraft","shuttle"]): return "fire"
    if any(k in low for k in ["city","urban","skyscraper","downtown","skyline","metropolis","cityscape"]): return "city"
    if any(k in low for k in ["ocean","wave","sea","beach","shore","underwater","splash","surf"]): return "ocean"
    if any(k in low for k in ["fire","flame","explod","burn","lava","volcanic","inferno","blaze"]): return "fire"
    if any(k in low for k in ["snow","winter","blizzard","snowflake","frozen","icy","frost"]): return "snow"
    if any(k in low for k in ["sunset","sunrise","golden hour","dusk","dawn","horizon"]): return "sunset"
    if any(k in low for k in ["forest","jungle","woodland","tree","rain","leaves","branch","nature"]): return "forest"
    if any(k in low for k in ["dance","concert","beat","stage","light show","dj","festival","performer","music video"]): return "music"
    if any(k in low for k in ["digital","cyber","matrix","glitch","neon","circuit","hack","code","tech"]): return "digital"
    if any(k in low for k in ["star","planet","cloud","sky","night","cosmic"]): return "space"
    if any(k in low for k in ["water","lake","river","stream","waterfall"]): return "ocean"
    return "abstract"

# ── scene → music mapping ──────────────────────────────────────────────────────

_SCENE_MUSIC = {
    "space":    "cinematic",
    "ocean":    "calm",
    "fire":     "epic",
    "snow":     "calm",
    "sunset":   "cinematic",
    "city":     "electronic",
    "forest":   "calm",
    "music":    "upbeat",
    "digital":  "electronic",
    "abstract": "upbeat",
}

# ── agent definitions ──────────────────────────────────────────────────────────

_AGENTS = {
    "cinematic": {
        "name": "Cinematic", "emoji": "🎬",
        "desc": "Hollywood drama, letterbox & film grain",
        "scenes": ["space","ocean","sunset","forest","city"],
        "music": "cinematic", "camera": "slow_zoom",
        "effects": ["warm_grade","vignette","film_grain","letterbox"],
    },
    "nature": {
        "name": "Nature", "emoji": "🌿",
        "desc": "Lush landscapes & soft organic light",
        "scenes": ["forest","ocean","snow","sunset"],
        "music": "calm", "camera": "pan",
        "effects": ["warm_grade","vignette"],
    },
    "cosmic": {
        "name": "Cosmic", "emoji": "🚀",
        "desc": "Deep space, galaxies & nebulae",
        "scenes": ["space"],
        "music": "cinematic", "camera": "slow_zoom",
        "effects": ["vignette","bloom"],
    },
    "urban": {
        "name": "Urban", "emoji": "🏙️",
        "desc": "City nights, neon glow & rain",
        "scenes": ["city","digital"],
        "music": "electronic", "camera": "dolly",
        "effects": ["cool_grade","vignette","film_grain"],
    },
    "abstract": {
        "name": "Abstract", "emoji": "🎨",
        "desc": "Flowing color, geometry & motion",
        "scenes": ["abstract","music"],
        "music": "upbeat", "camera": "orbit",
        "effects": ["vignette","bloom"],
    },
    "fantasy": {
        "name": "Fantasy", "emoji": "✨",
        "desc": "Magical glow, particles & wonder",
        "scenes": ["abstract","forest","sunset","snow"],
        "music": "cinematic", "camera": "slow_zoom",
        "effects": ["bloom","warm_grade","vignette"],
    },
    "retro": {
        "name": "Retro", "emoji": "📺",
        "desc": "VHS scanlines, film & vintage vibes",
        "scenes": ["sunset","city","music","ocean"],
        "music": "jazz", "camera": "handheld",
        "effects": ["vhs","film_grain"],
    },
}

# ── camera movement functions ──────────────────────────────────────────────────

def _cam_slow_zoom(img, W, H, t):
    scale = 1.0 + t * 0.10
    nw, nh = max(W, int(W*scale)), max(H, int(H*scale))
    img = img.resize((nw, nh), Image.BILINEAR)
    x, y = (nw-W)//2, (nh-H)//2
    return img.crop((x, y, x+W, y+H))

def _cam_zoom_out(img, W, H, t):
    scale = 1.10 - t * 0.10
    nw, nh = max(W, int(W*scale)), max(H, int(H*scale))
    img = img.resize((nw, nh), Image.BILINEAR)
    x, y = (nw-W)//2, (nh-H)//2
    return img.crop((x, y, x+W, y+H))

def _cam_pan(img, W, H, t):
    extra = max(1, int(W*0.12))
    img = img.resize((W+extra, H), Image.BILINEAR)
    x = int(t * extra)
    return img.crop((x, 0, x+W, H))

def _cam_dolly(img, W, H, t):
    ew, eh = max(1, int(W*0.12)), max(1, int(H*0.12))
    img = img.resize((W+ew, H+eh), Image.BILINEAR)
    x, y = int(t*ew), int(t*eh)
    return img.crop((x, y, x+W, y+H))

def _cam_handheld(img, W, H, t):
    pad = 14
    img = img.resize((W+pad*2, H+pad*2), Image.BILINEAR)
    rng = np.random.default_rng(int(t*30) % (2**31))
    dx = int(rng.integers(-pad//2, pad//2+1))
    dy = int(rng.integers(-pad//3, pad//3+1))
    return img.crop((pad+dx, pad+dy, pad+dx+W, pad+dy+H))

def _cam_orbit(img, W, H, t):
    angle = math.sin(t*2*math.pi) * 2.8
    return img.rotate(angle, resample=Image.BILINEAR, expand=False)

_CAMERAS = {
    "slow_zoom": _cam_slow_zoom,
    "zoom_out":  _cam_zoom_out,
    "pan":       _cam_pan,
    "dolly":     _cam_dolly,
    "handheld":  _cam_handheld,
    "orbit":     _cam_orbit,
    "static":    None,
}

# ── post-processing effects ────────────────────────────────────────────────────

def _fx_letterbox(img, W, H):
    draw = ImageDraw.Draw(img)
    bar = int(H * 0.115)
    draw.rectangle([0, 0, W, bar], fill=(0,0,0))
    draw.rectangle([0, H-bar, W, H], fill=(0,0,0))
    return img

def _fx_film_grain(img, W, H, seed):
    arr = np.array(img).astype(np.float32)
    grain = np.random.default_rng(seed % (2**31)).standard_normal((H,W)).astype(np.float32)*5
    for c in range(3):
        arr[:,:,c] = np.clip(arr[:,:,c]+grain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def _fx_vignette(img, W, H, strength=0.60):
    arr = np.array(img).astype(np.float32)
    cx, cy = W/2, H/2
    Y, X = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((X-cx)/cx)**2+((Y-cy)/cy)**2)
    mask = (1-np.clip(dist*strength, 0, 1))[:,:,None]
    return Image.fromarray(np.clip(arr*mask, 0, 255).astype(np.uint8))

def _fx_vhs(img, W, H, t):
    arr = np.array(img)
    sh = max(1, int(abs(math.sin(t*7.3))*4)+1)
    out = arr.copy()
    out[:, sh:,  0] = arr[:, :-sh, 0]
    out[:, :-sh, 2] = arr[:, sh:,  2]
    for y in range(0, H, 5):
        out[y] = np.clip(out[y].astype(np.int16)-20, 0, 255).astype(np.uint8)
    noise = (np.random.default_rng(int(t*100)%2**31).random((H,W))*18-9).astype(np.int16)
    for c in range(3):
        out[:,:,c] = np.clip(out[:,:,c].astype(np.int16)+noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out)

def _fx_warm_grade(img, W, H):
    arr = np.array(img).astype(np.float32)
    arr[:,:,0] = np.clip(arr[:,:,0]*1.09+8, 0, 255)
    arr[:,:,1] = np.clip(arr[:,:,1]*1.02,   0, 255)
    arr[:,:,2] = np.clip(arr[:,:,2]*0.88,   0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def _fx_cool_grade(img, W, H):
    arr = np.array(img).astype(np.float32)
    arr[:,:,0] = np.clip(arr[:,:,0]*0.88,   0, 255)
    arr[:,:,2] = np.clip(arr[:,:,2]*1.14+10, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def _fx_bloom(img, W, H):
    arr = np.array(img).astype(np.float32)
    bright = np.clip(arr-175, 0, 80).astype(np.uint8)
    glow = Image.fromarray(bright).filter(ImageFilter.GaussianBlur(radius=14))
    glow_arr = np.array(glow).astype(np.float32)*0.55
    return Image.fromarray(np.clip(arr+glow_arr, 0, 255).astype(np.uint8))

_FX = {
    "letterbox":  _fx_letterbox,
    "film_grain": _fx_film_grain,
    "vignette":   _fx_vignette,
    "vhs":        _fx_vhs,
    "warm_grade": _fx_warm_grade,
    "cool_grade": _fx_cool_grade,
    "bloom":      _fx_bloom,
}

def _apply_effects(frame, effects, W, H, t, frame_idx):
    for fx in effects:
        if fx == "film_grain":
            frame = _fx_film_grain(frame, W, H, frame_idx)
        elif fx == "vhs":
            frame = _fx_vhs(frame, W, H, t)
        elif fx in _FX:
            frame = _FX[fx](frame, W, H)
    return frame

# ── audio helpers ──────────────────────────────────────────────────────────────

_SR = 44100
_MN = {
    "C2":65.41,"G2":98.00,"A2":110.00,"Bb2":116.54,
    "C3":130.81,"D3":146.83,"E3":164.81,"F3":174.61,"G3":196.00,"A3":220.00,"Bb3":233.08,"B3":246.94,
    "C4":261.63,"D4":293.66,"Eb4":311.13,"E4":329.63,"F4":349.23,"F#4":369.99,
    "G4":392.00,"Ab4":415.30,"A4":440.00,"Bb4":466.16,"B4":493.88,
    "C5":523.25,"D5":587.33,"Eb5":622.25,"E5":659.25,"F5":698.46,"G5":783.99,"A5":880.00,
}

def _mt(dur):
    return np.linspace(0, dur, max(1, int(dur*_SR)), endpoint=False)

def _menv(n, atk=0.008, rel=0.12, dr=0.0):
    e = np.ones(n, dtype=np.float32)
    a = min(int(atk*_SR), n//4); r = min(int(rel*_SR), n//4)
    if a>0: e[:a]=np.linspace(0,1,a)
    if r>0: e[-r:]=np.linspace(1,0,r)
    if dr>0:
        t=np.linspace(0,n/_SR,n); e*=np.exp(-t*dr).astype(np.float32)
    return e

def _piano(f,d,amp=0.55):
    t=_mt(d); n=len(t)
    w=(np.sin(2*np.pi*f*t)+0.50*np.sin(4*np.pi*f*t)+0.25*np.sin(6*np.pi*f*t)+0.10*np.sin(8*np.pi*f*t)).astype(np.float32)
    return w*_menv(n,atk=0.006,rel=0.04,dr=5.0)*amp*0.4

def _pad(freqs,d,amp=0.18):
    t=_mt(d); n=len(t); w=np.zeros(n,dtype=np.float32)
    for f in freqs:
        w+=np.sin(2*np.pi*f*t).astype(np.float32)
        w+=(0.5*np.sin(2*np.pi*f*1.006*t)).astype(np.float32)
        w+=(0.25*np.sin(4*np.pi*f*t)).astype(np.float32)
    return w/max(len(freqs),1)*_menv(n,atk=0.18,rel=0.22)*amp

def _bass(f,d,amp=0.50):
    t=_mt(d); n=len(t)
    w=(np.sin(2*np.pi*f*t)+0.6*np.sin(4*np.pi*f*t)+0.2*np.sin(6*np.pi*f*t)).astype(np.float32)
    return w*_menv(n,atk=0.004,rel=0.06,dr=3.5)*amp*0.35

def _synth_bass(f,d,amp=0.55):
    t=_mt(d); n=len(t)
    w=sum(np.sin(2*np.pi*f*k*t)/k for k in range(1,8)).astype(np.float32)
    return w*_menv(n,atk=0.003,rel=0.03,dr=2.0)*amp*0.18

def _kick(dur=0.35):
    n=max(1,int(dur*_SR)); t=np.linspace(0,dur,n,endpoint=False)
    freq=100*np.exp(-t*35)+45; phase=np.cumsum(freq)*2*np.pi/_SR
    return np.sin(phase).astype(np.float32)*np.exp(-t*14).astype(np.float32)*0.80

def _snare(dur=0.18):
    n=max(1,int(dur*_SR)); t=np.linspace(0,dur,n,endpoint=False)
    noise=np.random.default_rng(42).standard_normal(n).astype(np.float32)*0.55
    tone=(np.sin(2*np.pi*195*t)*0.45).astype(np.float32)
    return (noise+tone)*np.exp(-t*28).astype(np.float32)*0.55

def _hihat(dur=0.04,amp=0.18):
    n=max(1,int(dur*_SR)); t=np.linspace(0,dur,n,endpoint=False)
    return np.random.default_rng(7).standard_normal(n).astype(np.float32)*np.exp(-t*55).astype(np.float32)*amp

def _mplace(buf,seg,pos):
    end=min(pos+len(seg),len(buf))
    if pos<end: buf[pos:end]+=seg[:end-pos]

def _mloop_mel(buf,seq,fn):
    pos=idx=0
    while pos<len(buf):
        note,dur=seq[idx%len(seq)]; seg=fn(_MN[note],dur)
        _mplace(buf,seg,pos); pos+=len(seg); idx+=1

def _mloop_drums(buf,pat_n,kicks,snares,hat_div=None,hat_amp=0.18):
    k=_kick(); s=_snare(); pos=0
    while pos<len(buf):
        for b in kicks:  _mplace(buf,k,pos+int(b*pat_n))
        for b in snares: _mplace(buf,s,pos+int(b*pat_n))
        if hat_div:
            for i in range(hat_div): _mplace(buf,_hihat(amp=hat_amp),pos+int(i/hat_div*pat_n))
        pos+=pat_n

def _mloop_bass(buf,notes,beat_n):
    for i in range(len(buf)//beat_n+1):
        _mplace(buf,_bass(_MN[notes[i%len(notes)]],beat_n/_SR),i*beat_n)

def _mloop_pad(buf,chords,chord_n):
    for i in range(len(buf)//chord_n+1):
        _mplace(buf,_pad(chords[i%len(chords)],chord_n/_SR),i*chord_n)

def _music_upbeat(tot):
    buf=np.zeros(tot,dtype=np.float32); beat=int(0.5*_SR)
    mel=[("C4",.25),("E4",.25),("G4",.25),("C5",.25),("B4",.25),("G4",.25),("E4",.25),("C4",.25),
         ("D4",.25),("F4",.25),("A4",.5),("G4",.25),("E4",.25),("C5",.5),("G4",.5)]
    _mloop_mel(buf,mel,lambda f,d:_piano(f,d,0.60))
    _mloop_pad(buf,[[_MN["C4"],_MN["E4"],_MN["G4"]],[_MN["G3"],_MN["B3"],_MN["D4"]],
                    [_MN["A3"],_MN["C4"],_MN["E4"]],[_MN["F3"],_MN["A3"],_MN["C4"]]],beat*4)
    _mloop_bass(buf,["C3","G3","A3","F3"],beat*2)
    _mloop_drums(buf,beat*2,[0,0.5],[0.25,0.75],hat_div=8,hat_amp=0.15)
    return buf

def _music_calm(tot):
    buf=np.zeros(tot,dtype=np.float32); beat=int(0.75*_SR)
    mel=[("G4",1.0),("B4",.5),("D5",.5),("E4",1.0),("G4",.5),("B4",.5),
         ("C4",1.0),("E4",.5),("G4",.5),("D4",1.0),("F#4",.5),("A4",.5)]
    _mloop_mel(buf,mel,lambda f,d:_piano(f,d,0.45))
    _mloop_pad(buf,[[_MN["G3"],_MN["B3"],_MN["D4"]],[_MN["E3"],_MN["G3"],_MN["B3"]],
                    [_MN["C3"],_MN["E3"],_MN["G3"]],[_MN["D3"],_MN["F#4"],_MN["A3"]]],beat*4)
    _mloop_bass(buf,["G2","A2","C3","G2"],beat*4)
    return buf

def _music_epic(tot):
    buf=np.zeros(tot,dtype=np.float32); beat=int(0.63*_SR)
    mel=[("D4",.5),("D4",.25),("A4",.75),("Bb4",.5),("A4",.5),("F4",.5),("F4",.25),
         ("C5",.75),("Bb4",.5),("A4",.5),("G4",.5),("G4",.25),("D5",1.0),("C5",.5),("Bb4",.5),("A4",1.0)]
    _mloop_mel(buf,mel,lambda f,d:_piano(f,d,0.70))
    _mloop_pad(buf,[[_MN["D4"],_MN["F4"],_MN["A4"]],[_MN["Bb3"],_MN["D4"],_MN["F4"]],
                    [_MN["F3"],_MN["A3"],_MN["C4"]],[_MN["C4"],_MN["E4"],_MN["G4"]]],beat*4)
    _mloop_bass(buf,["D3","Bb2","G2","C3"],beat*2)
    _mloop_drums(buf,beat*4,[0,0.375,0.5,0.875],[0.25,0.75],hat_div=8,hat_amp=0.12)
    return buf

def _music_cinematic(tot):
    buf=np.zeros(tot,dtype=np.float32); beat=int(1.09*_SR)
    mel=[("C4",2.0),("E4",1.5),("G4",1.5),("F4",2.0),("A4",1.5),("G4",1.5),("E4",2.0),("G4",1.5),("C5",3.0)]
    _mloop_mel(buf,mel,lambda f,d:_piano(f,d,0.50))
    _mloop_pad(buf,[[_MN["C3"],_MN["E4"],_MN["G4"]],[_MN["F3"],_MN["A3"],_MN["C4"]],
                    [_MN["G3"],_MN["B3"],_MN["D4"]],[_MN["A3"],_MN["C4"],_MN["E4"]]],beat*4)
    _mloop_bass(buf,["C3","F3","G3","A3"],beat*4)
    return buf

def _music_electronic(tot):
    buf=np.zeros(tot,dtype=np.float32); beat=int(0.469*_SR)
    arp=[("C4",.125),("E4",.125),("G4",.125),("Bb4",.125),("G4",.125),("E4",.125),("C5",.125),("G4",.125)]
    _mloop_mel(buf,arp,lambda f,d:_piano(f,d*0.8,0.45))
    _mloop_pad(buf,[[_MN["C4"],_MN["G4"]],[_MN["A3"],_MN["E4"]],
                    [_MN["F3"],_MN["C4"]],[_MN["G3"],_MN["D4"]]],beat*4)
    pos=0
    while pos<len(buf):
        _mplace(buf,_synth_bass(_MN["C3"],0.469,0.65),pos); pos+=beat
    _mloop_drums(buf,beat*4,[0,0.25,0.5,0.75],[0.25,0.75],hat_div=8,hat_amp=0.10)
    return buf

def _music_jazz(tot):
    np.random.seed(12); buf=np.zeros(tot,dtype=np.float32); beat=int(0.60*_SR)
    hat=_hihat(amp=0.14); pos=0
    while pos<len(buf):
        _mplace(buf,hat,pos); _mplace(buf,hat,pos+int(0.335*beat)); pos+=beat
    mel=[("C4",.375),("E4",.125),("G4",.25),("Bb4",.25),("A4",.375),("F#4",.125),("E4",.25),("G4",.25),
         ("D4",.375),("F4",.125),("Ab4",.25),("C5",.25),("Bb4",.375),("G4",.125),("E4",.25),("C4",.5)]
    _mloop_mel(buf,mel,lambda f,d:_piano(f,d,0.55))
    _mloop_pad(buf,[[_MN["C4"],_MN["E4"],_MN["G4"],_MN["Bb4"]],[_MN["A3"],_MN["C4"],_MN["E4"],_MN["G4"]],
                    [_MN["D4"],_MN["F4"],_MN["A4"],_MN["C5"]],[_MN["G3"],_MN["B3"],_MN["D4"],_MN["F4"]]],beat*4)
    _mloop_bass(buf,["C3","A3","D3","G3"],beat*2)
    return buf

_MUSIC_RENDERERS = {
    "upbeat":    _music_upbeat,
    "calm":      _music_calm,
    "epic":      _music_epic,
    "cinematic": _music_cinematic,
    "electronic":_music_electronic,
    "jazz":      _music_jazz,
}

def _gen_music(style: str, duration: float, out_path: str):
    renderer = _MUSIC_RENDERERS.get(style, _music_upbeat)
    total    = int(duration * _SR)
    buf      = renderer(total)
    delay    = int(0.055 * _SR)
    rev      = np.zeros(total, dtype=np.float32)
    rev[delay:] = buf[:total-delay] * 0.18
    audio    = buf + rev
    peak     = np.max(np.abs(audio))
    if peak > 0: audio *= 0.80 / peak
    audio = np.clip(audio, -1.0, 1.0)
    with wave.open(out_path, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(_SR)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())
    return out_path

def _fix_sign(v: str) -> str:
    v = v.strip()
    return v if v and v[0] in ("+","-") else "+"+v

async def _tts(text, voice, rate, pitch, out_path):
    await edge_tts.Communicate(text=text, voice=voice,
                                rate=_fix_sign(rate), pitch=_fix_sign(pitch)).save(out_path)

def _mix_audio(raw_video, voice_path, music_path, out_path, music_vol):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not voice_path and not music_path:
        os.replace(raw_video, out_path); return
    if voice_path and music_path:
        mixed = out_path.replace(".mp4","_mix.wav")
        subprocess.run([ffmpeg,"-y","-i",voice_path,"-i",music_path,"-filter_complex",
            f"[0:a]volume=1.0[v];[1:a]volume={music_vol:.2f}[m];[v][m]amix=inputs=2:duration=longest",
            "-ac","2",mixed], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        audio_in = mixed
    else:
        audio_in = voice_path or music_path
    subprocess.run([ffmpeg,"-y","-i",raw_video,"-i",audio_in,
        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-shortest",out_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if voice_path and music_path:
        mixed = out_path.replace(".mp4","_mix.wav")
        if os.path.exists(mixed): os.remove(mixed)

# ── generation pipeline ────────────────────────────────────────────────────────

def _run_generation(task_id: str, req: VideoRequest):
    try:
        W, H  = req.width, req.height
        total = req.num_frames

        # resolve agent
        agent_cfg = _AGENTS.get(req.agent) if req.agent != "auto" else None

        # scene detection constrained to agent's scenes
        scene = _detect(req.prompt)
        if agent_cfg and scene not in agent_cfg["scenes"]:
            scene = agent_cfg["scenes"][0]
        fn = _SCENES[scene]

        # camera function
        cam_name = "static"
        if req.camera_movement != "auto":
            cam_name = req.camera_movement
        elif agent_cfg:
            cam_name = agent_cfg.get("camera", "static")
        cam_fn = _CAMERAS.get(cam_name)

        # post-processing effects
        effects = agent_cfg["effects"] if agent_cfg else []

        uid   = str(uuid.uuid4())
        raw   = f"outputs/videos/{uid}_raw.mp4"
        final = f"outputs/videos/{uid}.mp4"

        _tasks[task_id].update({"status":"rendering","progress":5,"scene":scene,"agent":req.agent})

        writer = imageio.get_writer(raw, fps=req.fps, codec="libx264",
                    output_params=["-crf","23","-preset","medium","-pix_fmt","yuv420p"])
        for i in range(total):
            t     = i / max(total-1, 1)
            frame = fn(W, H, t)
            if cam_fn:
                frame = cam_fn(frame, W, H, t)
            frame = _apply_effects(frame, effects, W, H, t, i)
            frame = _subtitle(frame, req.prompt, W, H)
            writer.append_data(np.array(frame))
            _tasks[task_id]["progress"] = 5 + int(58 * i / total)
        writer.close()

        # voice
        voice_path = None
        if req.voice_enabled:
            _tasks[task_id].update({"status":"generating voice","progress":65})
            narrate = req.voice_text.strip() or req.prompt
            voice_path = f"outputs/videos/{uid}_voice.mp3"
            asyncio.run(_tts(narrate, req.voice_name,
                             _fix_sign(req.voice_rate), _fix_sign(req.voice_pitch), voice_path))

        # music
        music_path = None
        if req.music_enabled:
            _tasks[task_id].update({"status":"composing music","progress":75})
            if req.music_style != "auto":
                style = req.music_style
            elif agent_cfg:
                style = agent_cfg.get("music", "upbeat")
            else:
                style = _SCENE_MUSIC.get(scene, "upbeat")
            music_path = f"outputs/videos/{uid}_music.wav"
            _gen_music(style, total/req.fps + 1.5, music_path)

        # combine
        _tasks[task_id].update({"status":"mixing audio","progress":88})
        _mix_audio(raw, voice_path, music_path, final, req.music_volume)

        # cleanup raw + temp audio
        for f in [raw, voice_path, music_path]:
            if f and f != final and os.path.exists(f):
                try: os.remove(f)
                except: pass

        _tasks[task_id].update({
            "status":"completed","progress":100,
            "result":f"/outputs/videos/{uid}.mp4",
        })

    except Exception as e:
        _tasks[task_id].update({"status":"failed","progress":0,"error":str(e),"result":None})


@router.get("/agents")
def list_agents():
    return {"agents": [
        {"id": k, "name": v["name"], "emoji": v["emoji"], "desc": v["desc"],
         "music": v["music"], "camera": v["camera"], "effects": v["effects"]}
        for k, v in _AGENTS.items()
    ]}


@router.post("/generate")
async def generate_video(req: VideoRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status":"queued","progress":0,"result":None}
    background_tasks.add_task(_run_generation, task_id, req)
    return {"task_id": task_id}


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]
