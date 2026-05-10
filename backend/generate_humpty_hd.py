"""
Humpty Dumpty HD Nursery Rhyme Video
Enhanced animation: particles, smooth motion, screen shake, karaoke text,
scene transitions, animated clouds/birds/stars, title card, outro.
"""
import asyncio, os, sys, wave, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio
import edge_tts

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR = "outputs"
os.makedirs(f"{OUTPUT_DIR}/videos", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/voice",  exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/audio",  exist_ok=True)

W, H  = 1280, 720
FPS   = 30

RHYME = [
    "Humpty Dumpty sat on a wall,",
    "Humpty Dumpty had a great fall.",
    "All the king's horses and all the king's men,",
    "Couldn't put Humpty together again!",
]
FULL_TEXT = (
    "Humpty Dumpty sat on a wall,\n"
    "Humpty Dumpty had a great fall.\n"
    "All the king's horses and all the king's men,\n"
    "Couldn't put Humpty together again!"
)

# Scene timing (seconds)
T_TITLE_IN   = 0.0
T_TITLE_OUT  = 2.5
T_LINE1_IN   = 2.5
T_LINE1_OUT  = 6.5
T_LINE2_IN   = 6.5
T_LINE2_OUT  = 10.5
T_FALL_START = 9.0          # Humpty starts wobbling
T_HIT_GROUND = 10.8         # impact frame
T_LINE3_IN   = 10.5
T_LINE3_OUT  = 15.0
T_LINE4_IN   = 15.0
T_LINE4_OUT  = 19.0
T_OUTRO_IN   = 18.5
T_TOTAL      = 20.5

TOTAL_FRAMES = int(T_TOTAL * FPS)

# Colours
C_SKY_TOP   = (25,  90, 195)
C_SKY_MID   = (80, 160, 230)
C_SKY_BOT   = (160, 210, 255)
C_GROUND    = (85,  170, 65)
C_GROUND2   = (60,  130, 45)
C_SUN       = (255, 220, 50)
C_SUN_GLOW  = (255, 240, 120)
C_CLOUD     = (255, 255, 255)
C_BRICK     = (190, 100, 40)
C_BRICK_D   = (140,  65, 20)
C_HUMPTY    = (255, 225, 100)
C_HUMPTY_S  = (220, 180, 60)
C_EYE       = (40,  40,  100)
C_SMILE     = (200, 60,  20)
C_HAT       = (45,  45,  80)
C_KING      = (180, 30,  30)
C_GOLD      = (255, 200, 30)
C_STAR      = (255, 255, 180)

random.seed(42)

# ── Easing ────────────────────────────────────────────────────────────────────
def ease_in_out(t): return t*t*(3-2*t)
def ease_out(t):    return 1-(1-t)**3
def ease_in(t):     return t**3
def bounce(t):
    if t < 1/2.75: return 7.5625*t*t
    elif t < 2/2.75: t-=1.5/2.75;  return 7.5625*t*t+0.75
    elif t < 2.5/2.75: t-=2.25/2.75; return 7.5625*t*t+0.9375
    else: t-=2.625/2.75; return 7.5625*t*t+0.984375

def lerp(a, b, t): return a + (b-a)*t
def lerp_c(c1, c2, t): return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))
def clamp01(t):     return max(0.0, min(1.0, t))
def fade(t, t0, t1): return clamp01((t-t0)/(t1-t0)) if t1>t0 else (1.0 if t>=t0 else 0.0)
def fade_out(t, t0, t1): return 1-fade(t, t0, t1)

# ── Stars (background) ────────────────────────────────────────────────────────
STARS = [(random.randint(0,W), random.randint(0, H//2),
          random.uniform(1,3), random.uniform(0, 2*math.pi))
         for _ in range(60)]

# ── Particles ─────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, vx, vy, life, color, size):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = life       # seconds
        self.age  = 0.0
        self.color = color
        self.size  = size
    def update(self, dt):
        self.age += dt
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += 400 * dt    # gravity
    @property
    def alive(self): return self.age < self.life
    @property
    def alpha(self): return clamp01(1 - self.age/self.life)

particles: list[Particle] = []

def spawn_debris(cx, cy, n=35):
    for _ in range(n):
        ang = random.uniform(0, 2*math.pi)
        spd = random.uniform(80, 400)
        col = random.choice([C_HUMPTY, C_HUMPTY_S, (200,80,20), (240,180,60), (255,255,255)])
        particles.append(Particle(cx, cy,
            math.cos(ang)*spd, math.sin(ang)*spd - 200,
            random.uniform(0.6, 1.4), col, random.uniform(4,14)))

def spawn_sparkles(cx, cy, n=20):
    for _ in range(n):
        ang = random.uniform(0, 2*math.pi)
        spd = random.uniform(40, 160)
        particles.append(Particle(cx, cy,
            math.cos(ang)*spd, math.sin(ang)*spd - 80,
            random.uniform(0.4, 1.0), C_STAR, random.uniform(3, 8)))

debris_spawned   = False
sparkle_spawned  = False

# ── Birds ─────────────────────────────────────────────────────────────────────
BIRDS = [(random.randint(-200, W+200), random.randint(60, 220),
          random.uniform(60, 120), random.uniform(0, 2*math.pi))
         for _ in range(6)]

def bird_x(bx, spd, t): return (bx + spd*t) % (W+400) - 200

# ── Drawing helpers ───────────────────────────────────────────────────────────
def draw_sky(draw, t):
    for y in range(H):
        p = y / H
        if p < 0.5:
            c = lerp_c(C_SKY_TOP, C_SKY_MID, p*2)
        else:
            c = lerp_c(C_SKY_MID, C_SKY_BOT, (p-0.5)*2)
        draw.line([(0,y),(W,y)], fill=c)

def draw_sun(draw, t):
    cx, cy, r = 120, 110, 60
    pulse = math.sin(t*2)*4
    # outer glow layers
    for i in range(6, 0, -1):
        rr = r + i*14 + pulse
        a  = int(30 - i*4)
        draw.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], fill=(*C_SUN_GLOW, max(0,a)))
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=C_SUN)
    # rays
    for ang in range(0, 360, 20):
        rad = math.radians(ang + t*15)
        r1, r2 = r+10, r+30+pulse
        x1,y1 = cx+math.cos(rad)*r1, cy+math.sin(rad)*r1
        x2,y2 = cx+math.cos(rad)*r2, cy+math.sin(rad)*r2
        draw.line([(x1,y1),(x2,y2)], fill=C_SUN_GLOW, width=3)

def draw_stars(draw, t, alpha):
    if alpha < 0.01: return
    for sx, sy, sr, sphase in STARS:
        tw = 0.5 + 0.5*math.sin(t*2 + sphase)
        a  = int(alpha * tw * 220)
        r  = int(sr)
        draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(255,255,200,a))

def draw_cloud(draw, cx, cy, scale=1.0, alpha=1.0):
    col = tuple(int(c*alpha + (1-alpha)*lerp_c(C_SKY_MID,C_SKY_BOT,0.5)[i])
                for i,c in enumerate(C_CLOUD))
    for dx,dy,r in [(-55,5,42),(0,-18,55),(55,5,42),(95,12,32),(-90,12,32)]:
        rr = int(r*scale)
        draw.ellipse([cx+dx-rr,cy+dy-rr,cx+dx+rr,cy+dy+rr], fill=col)

def draw_ground(draw, t):
    # Base ground
    draw.rectangle([0, H-140, W, H], fill=C_GROUND)
    draw.rectangle([0, H-140, W, H-120], fill=C_GROUND2)
    # Animated grass tufts
    for x in range(-10, W+20, 22):
        ox = x + int(math.sin(t*1.5 + x*0.05)*2)
        for gx in [-4,-1,2,5]:
            ht = 12 + int(math.sin(t*2 + x*0.1 + gx)*3)
            draw.line([(ox+gx, H-140),(ox+gx+2, H-140-ht)],
                      fill=(50,150,35), width=2)
    # Flowers
    for fx, fy, fc in [(200,H-148,(255,100,100)),(450,H-145,(255,200,50)),
                       (750,H-150,(200,100,255)),(1050,H-146,(255,150,50))]:
        draw.ellipse([fx-6,fy-6,fx+6,fy+6], fill=fc)
        draw.ellipse([fx-3,fy-3,fx+3,fy+3], fill=(255,255,100))

def draw_wall(draw, wx=400, top_y=H-230):
    bw, bh = 85, 34
    for row in range(6):
        off = (row%2)*42
        y   = top_y + row*bh
        for col in range(12):
            x = wx - off + col*bw - bw*2
            draw.rectangle([x, y, x+bw-4, y+bh-4], fill=C_BRICK)
            draw.rectangle([x, y, x+bw-4, y+5],    fill=C_BRICK_D)
            draw.rectangle([x, y, x+5,    y+bh-4], fill=C_BRICK_D)
            # mortar highlight
            draw.rectangle([x+5, y+5, x+bw-5, y+7], fill=(210,130,70))

def draw_bird(draw, cx, cy, flap):
    w = int(10 + 8*abs(math.sin(flap)))
    draw.arc([cx-w, cy-4, cx,   cy+4], 0, 180,   fill=(40,40,60), width=2)
    draw.arc([cx,   cy-4, cx+w, cy+4], 0, 180,   fill=(40,40,60), width=2)

def draw_birds(draw, t):
    for i,(bx,by,spd,phase) in enumerate(BIRDS):
        x = bird_x(bx, spd, t)
        y = by + int(math.sin(t*1.2 + phase)*12)
        flap = t*8 + phase
        draw_bird(draw, int(x), y, flap)

def draw_humpty(draw, cx, cy, scale=1.0, angle=0.0, cracked=False,
                blink=False, wobble=0.0, falling=False):
    s = scale
    bw, bh = int(115*s), int(135*s)

    # Shadow
    sx, sy = cx, H-138
    draw.ellipse([sx-bw//2, sy-10, sx+bw//2, sy+10], fill=(0,0,0,60))

    # Body
    draw.ellipse([cx-bw//2, cy-bh//2, cx+bw//2, cy+bh//2],
                 fill=C_HUMPTY, outline=C_HUMPTY_S, width=3)
    # Shading
    draw.ellipse([cx-bw//2+8, cy-bh//2+8, cx-5, cy+bh//4],
                 fill=(*C_SUN_GLOW[:3], 60))

    # Crack
    if cracked:
        pts = [(cx-18,cy-45),(cx+6,cy-12),(cx-12,cy+15),(cx+4,cy+35)]
        draw.line(pts, fill=(160,80,15), width=5)
        draw.line([(cx+22,cy-35),(cx+2,cy+8),(cx+18,cy+30)],
                  fill=(160,80,15), width=4)

    # Eyes
    ey  = cy - int(22*s)
    er  = int(13*s)
    lx, rx = cx - int(28*s), cx + int(28*s)
    draw.ellipse([lx-er, ey-er, lx+er, ey+er], fill=C_EYE)
    draw.ellipse([rx-er, ey-er, rx+er, ey+er], fill=C_EYE)
    if not blink:
        draw.ellipse([lx-int(6*s), ey-int(6*s), lx+int(6*s), ey+int(6*s)], fill="white")
        draw.ellipse([rx-int(6*s), ey-int(6*s), rx+int(6*s), ey+int(6*s)], fill="white")
    else:
        draw.line([(lx-er, ey),(lx+er, ey)], fill="white", width=3)
        draw.line([(rx-er, ey),(rx+er, ey)], fill="white", width=3)

    # Eyebrows (worried when wobbling)
    brow_off = int(-wobble * 8)
    draw.line([(lx-er, ey-er-4+brow_off),(lx+er, ey-er-4-brow_off)],
              fill=(140,80,20), width=4)
    draw.line([(rx-er, ey-er-4-brow_off),(rx+er, ey-er-4+brow_off)],
              fill=(140,80,20), width=4)

    # Mouth
    if wobble > 0.3 or cracked:
        draw.arc([cx-int(22*s), cy+int(5*s), cx+int(22*s), cy+int(30*s)],
                 190, 350, fill=C_SMILE, width=4)
    else:
        draw.arc([cx-int(22*s), cy-int(5*s), cx+int(22*s), cy+int(32*s)],
                 10, 170, fill=C_SMILE, width=4)

    # Bow tie
    bt = int(30*s)
    ty = cy + int(50*s)
    draw.polygon([(cx-bt, ty-12),(cx, ty),(cx-bt, ty+12)], fill=(210,30,30))
    draw.polygon([(cx+bt, ty-12),(cx, ty),(cx+bt, ty+12)], fill=(210,30,30))
    draw.ellipse([cx-int(9*s), ty-int(9*s), cx+int(9*s), ty+int(9*s)],
                 fill=(240,50,50))

    # Hat
    hw, hh = int(95*s), int(38*s)
    ht_y = cy - bh//2 - 8
    draw.rectangle([cx-hw//2-18, ht_y-8, cx+hw//2+18, ht_y+8], fill=C_HAT)
    draw.rectangle([cx-hw//2,    ht_y-hh, cx+hw//2,   ht_y],   fill=C_HAT)
    draw.rectangle([cx-hw//2,    ht_y-hh+4, cx+hw//2, ht_y-hh+10], fill=C_GOLD)

    # Legs (animated swing)
    leg_ang = math.sin(wobble * 5) * 0.3 if not cracked else 0.6
    lleg_x = cx - int(35*s)
    rleg_x = cx + int(35*s)
    lleg_y = cy + bh//2
    draw.line([(lleg_x, lleg_y),
               (lleg_x - int(math.sin(leg_ang)*50), lleg_y + int(math.cos(leg_ang)*60))],
              fill=C_HUMPTY, width=int(18*s))
    draw.line([(rleg_x, lleg_y),
               (rleg_x + int(math.sin(leg_ang)*50), lleg_y + int(math.cos(leg_ang)*60))],
              fill=C_HUMPTY, width=int(18*s))

    # Arms
    arm_ang = math.sin(wobble * 4) * 0.4 + 0.2
    draw.line([(cx - bw//2, cy+10),
               (cx - bw//2 - int(math.cos(arm_ang)*55), cy + 10 - int(math.sin(arm_ang)*40))],
              fill=C_HUMPTY, width=int(18*s))
    draw.line([(cx + bw//2, cy+10),
               (cx + bw//2 + int(math.cos(arm_ang)*55), cy + 10 - int(math.sin(arm_ang)*40))],
              fill=C_HUMPTY, width=int(18*s))


def draw_king(draw, x, y, march_t, idx):
    phase = march_t + idx*0.8
    leg_swing = math.sin(phase*4) * 18
    # Horse body
    hx, hy = x-35, y+55
    draw.ellipse([hx-38, hy-22, hx+38, hy+22], fill=(170,130,90))
    draw.ellipse([hx+12, hy-40, hx+44, hy-8],  fill=(170,130,90))
    # horse legs
    for lx in [-25,-8,8,25]:
        lph = math.sin(phase*4 + lx*0.2)*20
        draw.line([(hx+lx, hy+20),(hx+lx+int(lph*0.3), hy+55)],
                  fill=(140,100,60), width=6)
    # Rider
    draw.rectangle([x-18, y,    x+18, y+80], fill=C_KING)
    draw.ellipse(  [x-18, y-40, x+18, y],    fill=(240,200,160))
    # Crown
    draw.polygon([(x-18,y-40),(x-10,y-58),(x,y-46),(x+10,y-58),(x+18,y-40)],
                 fill=C_GOLD)
    draw.ellipse([x-3,y-54,x+3,y-48], fill=(255,50,50))
    # Spear
    draw.line([(x+22,y-15),(x+22,y+95)], fill=(110,70,30), width=5)
    draw.polygon([(x+16,y-15),(x+28,y-15),(x+22,y-38)], fill=(190,190,210))
    # cape
    draw.polygon([(x-18,y+10),(x-35,y+70),(x+18,y+70),(x+18,y+10)],
                 fill=(150,20,20))


def draw_particles(draw):
    for p in particles:
        if not p.alive: continue
        a   = int(p.alpha * 255)
        col = (*p.color[:3], a)
        r   = max(1, int(p.size * p.alpha))
        draw.ellipse([p.x-r, p.y-r, p.x+r, p.y+r], fill=col)


def draw_title(draw, t):
    alpha_in  = ease_out(clamp01((t - T_TITLE_IN)  / 0.8))
    alpha_out = ease_in(clamp01((t - (T_TITLE_OUT-0.6)) / 0.6))
    alpha = clamp01(alpha_in - alpha_out)
    if alpha < 0.01: return

    try: fn = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 88)
    except: fn = ImageFont.load_default()
    try: fs = ImageFont.truetype("C:/Windows/Fonts/ariali.ttf", 40)
    except: fs = fn

    title = "Humpty Dumpty"
    sub   = "A Nursery Rhyme"

    # Draw with shadow + glow
    for ox,oy in [(-3,3),(3,3),(0,4),(0,-1)]:
        draw.text((W//2+ox - draw.textlength(title,font=fn)//2, H//2-80+oy),
                  title, font=fn, fill=(0,0,0,int(alpha*160)))
    draw.text((W//2 - int(draw.textlength(title,font=fn))//2, H//2-80),
              title, font=fn, fill=(*C_GOLD, int(alpha*255)))

    draw.text((W//2 - int(draw.textlength(sub,font=fs))//2, H//2+28),
              sub, font=fs, fill=(255,255,255,int(alpha*200)))

    # Stars burst
    spawn_r = 120 + math.sin(t*3)*20
    for i in range(8):
        ang = math.radians(i*45 + t*60)
        sx  = W//2 + int(math.cos(ang)*spawn_r)
        sy  = H//2-40 + int(math.sin(ang)*spawn_r*0.5)
        sr  = int(6*alpha)
        draw.ellipse([sx-sr,sy-sr,sx+sr,sy+sr], fill=(*C_STAR,int(alpha*200)))


def draw_subtitle(draw_img, img, t, line_idx, t_in, t_out):
    if t < t_in or t > t_out: return img
    alpha_in  = ease_out(clamp01((t - t_in) / 0.35))
    alpha_out = fade_out(t, t_out-0.4, t_out)
    alpha = alpha_in * alpha_out
    if alpha < 0.01: return img

    try: font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 46)
    except: font = ImageFont.load_default()

    text = RHYME[line_idx]
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)

    tw = int(d.textlength(text, font=font))
    th = 52
    px, py = 48, 26
    bx = (W - tw)//2 - px
    by = H - 120
    slide_y = int((1-alpha_in)*30)

    # Rounded pill background
    d.rounded_rectangle(
        [bx, by+slide_y, bx+tw+px*2, by+slide_y+th+py*2],
        radius=20, fill=(10,10,30,int(alpha*200)))
    # Coloured left bar
    d.rounded_rectangle(
        [bx, by+slide_y, bx+10, by+slide_y+th+py*2],
        radius=6, fill=(*C_GOLD, int(alpha*255)))

    # Shadow text
    d.text((bx+px+2, by+slide_y+py+2), text, font=font,
           fill=(0,0,0,int(alpha*140)))
    # Main text (karaoke: progress through line)
    progress = clamp01((t - t_in) / (t_out - t_in - 0.4))
    chars_show = max(1, int(len(text) * ease_out(progress)))
    d.text((bx+px, by+slide_y+py), text[:chars_show], font=font,
           fill=(255,255,180,int(alpha*255)))
    # Remaining chars dimmer
    shown_w = int(d.textlength(text[:chars_show], font=font))
    d.text((bx+px+shown_w, by+slide_y+py), text[chars_show:], font=font,
           fill=(200,200,200,int(alpha*120)))

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def draw_outro(draw, t):
    alpha = ease_out(clamp01((t - T_OUTRO_IN) / 0.8))
    if alpha < 0.01: return
    try: fn = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 72)
    except: fn = ImageFont.load_default()
    try: fs = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
    except: fs = fn
    end_text = "The End"
    sub_text  = "Created with AI Creative Studio"
    for ox,oy in [(-2,2),(2,2)]:
        draw.text((W//2+ox - int(draw.textlength(end_text,font=fn))//2, H//2-60+oy),
                  end_text, font=fn, fill=(0,0,0,int(alpha*150)))
    draw.text((W//2 - int(draw.textlength(end_text,font=fn))//2, H//2-60),
              end_text, font=fn, fill=(*C_GOLD, int(alpha*255)))
    draw.text((W//2 - int(draw.textlength(sub_text,font=fs))//2, H//2+30),
              sub_text, font=fs, fill=(255,255,255,int(alpha*180)))


# ── Build a single frame ───────────────────────────────────────────────────────
def build_frame(fi):
    global debris_spawned, sparkle_spawned

    t   = fi / FPS
    dt  = 1 / FPS

    # Update particles
    for p in particles: p.update(dt)
    particles[:] = [p for p in particles if p.alive]

    # Screen shake offset after impact
    shake = 0
    if T_HIT_GROUND <= t <= T_HIT_GROUND + 0.5:
        shake_prog = (t - T_HIT_GROUND) / 0.5
        shake = int((1-shake_prog) * 14 * math.sin(shake_prog * 40))

    img  = Image.new("RGBA", (W, H), (0,0,0,255))
    draw = ImageDraw.Draw(img)

    draw_sky(draw, t)

    # Stars (visible in title card only, fade out)
    star_alpha = fade_out(t, 2.0, 3.0)
    draw_stars(draw, t, star_alpha)

    draw_sun(draw, t)

    # Clouds (3 at different speeds/sizes)
    cloud_alpha = fade(t, 2.0, 3.5)
    cloud_positions = [
        (int((250 + t*18)) % (W+300) - 150,  130, 1.25),
        (int((700 + t*10)) % (W+300) - 150,   95, 0.95),
        (int((1000+ t*24)) % (W+300) - 150,  165, 1.05),
    ]
    for cx,cy,sc in cloud_positions:
        draw_cloud(draw, cx, cy, sc, cloud_alpha)

    draw_birds(draw, t)
    draw_ground(draw, t)

    wall_x = 420
    draw_wall(draw, wall_x, H-235)

    # ── Humpty animation logic ─────────────────────────────────────────────────
    hx_base  = wall_x + 110
    hy_wall  = H - 305
    humpty_visible = T_TITLE_OUT - 0.3 <= t

    if humpty_visible:
        humpty_in = ease_out(clamp01((t - (T_TITLE_OUT-0.3)) / 0.5))

        if t < T_FALL_START:
            # Happy sitting: gentle bounce + leg swing
            wobble_t = (t - T_LINE1_IN)
            bounce_y = int(math.sin(t * 2.5) * 5)
            leg_w    = t * 3
            blink    = (int(t * 2) % 8 == 0)
            scale    = lerp(0.3, 1.0, humpty_in)
            draw_humpty(draw, hx_base, hy_wall + bounce_y + shake,
                        scale=scale, wobble=leg_w, blink=blink)

        elif t < T_HIT_GROUND:
            # Wobbling / tipping off wall
            wobble_prog = clamp01((t - T_FALL_START) / (T_HIT_GROUND - T_FALL_START))
            wobble_amp  = ease_in(wobble_prog) * 1.2
            tilt_x = int(math.sin(wobble_prog * math.pi * 3) * 20 * wobble_amp)
            fall_y = int(ease_in(wobble_prog) * 20)
            draw_humpty(draw, hx_base + tilt_x, hy_wall + fall_y + shake,
                        wobble=wobble_amp)

        elif t < T_LINE3_OUT:
            # Fallen on ground
            gx = hx_base + 220
            gy = H - 145
            if not debris_spawned:
                spawn_debris(gx, gy - 30, 40)
                debris_spawned = True
            draw_humpty(draw, gx, gy + shake, cracked=True, scale=0.92)

            # Ground cracks
            for i, (cx, cy) in enumerate([(gx-60,H-140),(gx+20,H-138),(gx-20,H-143)]):
                ang = math.radians(160 + i*30)
                draw.line([(cx,cy),(cx+int(math.cos(ang)*40),cy+int(math.sin(ang)*20))],
                          fill=(80,60,30), width=3)

        else:
            # Still on ground during kings scene
            draw_humpty(draw, hx_base + 220, H - 145, cracked=True, scale=0.92)

    # ── King's horses and men marching in ──────────────────────────────────────
    if t >= T_LINE3_IN:
        march_prog = clamp01((t - T_LINE3_IN) / 2.5)
        march_ease = ease_out(march_prog)
        king_start_x = W + 200
        kings = [
            (int(lerp(king_start_x, 920, march_ease)), H-250, 0),
            (int(lerp(king_start_x+80, 1020, march_ease)), H-255, 1),
            (int(lerp(king_start_x+160, 1120, march_ease)), H-248, 2),
        ]
        for kx, ky, ki in kings:
            draw_king(draw, kx, ky, t, ki)

    # Particles
    draw_particles(draw)

    # Title card overlay
    if t <= T_TITLE_OUT + 0.5:
        draw_title(draw, t)

    # Subtitles (karaoke)
    img = img.convert("RGB")
    img = draw_subtitle(draw, img, t, 0, T_LINE1_IN, T_LINE1_OUT)
    img = draw_subtitle(draw, img, t, 1, T_LINE2_IN, T_LINE2_OUT)
    img = draw_subtitle(draw, img, t, 2, T_LINE3_IN, T_LINE3_OUT)
    img = draw_subtitle(draw, img, t, 3, T_LINE4_IN, T_LINE4_OUT)

    # Outro overlay
    if t >= T_OUTRO_IN:
        img2 = img.convert("RGBA")
        d2   = ImageDraw.Draw(img2)
        draw_outro(d2, t)
        img  = img2.convert("RGB")

    # Global fade in at start / fade out at end
    img_arr = np.array(img, dtype=np.float32)
    fade_in_alpha  = clamp01(t / 0.5)
    fade_out_alpha = fade_out(t, T_TOTAL - 0.7, T_TOTAL)
    global_alpha   = fade_in_alpha * fade_out_alpha
    img_arr = img_arr * global_alpha
    return img_arr.clip(0, 255).astype(np.uint8)


# ── Voice ──────────────────────────────────────────────────────────────────────
async def gen_voice():
    print("[VOICE] Generating voice over...")
    path = f"{OUTPUT_DIR}/voice/humpty_hd_voice.mp3"
    await edge_tts.Communicate(
        text=FULL_TEXT,
        voice="en-GB-SoniaNeural",
        rate="-12%",
        pitch="+4Hz",
    ).save(path)
    print(f"  [OK] {path}")
    return path


# ── Music ──────────────────────────────────────────────────────────────────────
def gen_music(dur):
    print("[MUSIC] Generating background music...")
    sr = 44100
    notes = {
        "C3":130.81,"G3":196.00,"F3":174.61,"A3":220.00,
        "C4":261.63,"D4":293.66,"E4":329.63,"F4":349.23,
        "G4":392.00,"A4":440.00,"B4":493.88,"C5":523.25,
    }
    melody = [
        ("G4",.5),("E4",.5),("C4",.5),("E4",.5),
        ("G4",.5),("G4",.5),("A4",1.0),
        ("G4",.5),("E4",.5),("C4",.5),("E4",.5),
        ("D4",.5),("D4",.5),("C4",1.0),
        ("E4",.5),("E4",.5),("E4",.5),("E4",.5),
        ("G4",.5),("G4",.5),("A4",1.0),
        ("F4",.5),("E4",.5),("D4",.5),("C4",.5),
        ("G4",.5),("E4",.5),("C4",1.0),
    ]
    bass = ["C3","G3","F3","C3","G3","C3","F3","G3"]

    N  = int(sr * dur)
    mel= np.zeros(N)
    pos, idx = 0, 0
    while pos < N:
        f, d = melody[idx % len(melody)]
        n    = int(d * sr)
        end  = min(pos+n, N)
        seg  = np.linspace(0, d, end-pos, endpoint=False)
        w    = np.sin(2*np.pi*notes[f]*seg)
        # harmonic richness
        w   += 0.4*np.sin(4*np.pi*notes[f]*seg)
        w   += 0.15*np.sin(6*np.pi*notes[f]*seg)
        env  = np.ones(end-pos)
        fade_s = min(300, end-pos)
        env[:fade_s]  = np.linspace(0,1,fade_s)
        env[-min(fade_s,end-pos):] = np.linspace(1,0,min(fade_s,end-pos))
        mel[pos:end] += w * env * 0.30
        pos += n; idx += 1

    bs  = np.zeros(N)
    bt  = int(sr*0.5)
    for i in range(N//bt):
        f = notes[bass[i%len(bass)]]
        s,e = i*bt, min((i+1)*bt,N)
        seg = np.linspace(0,(e-s)/sr,e-s)
        bs[s:e] += np.sin(2*np.pi*f*seg)*0.12

    # Gentle reverb: mix with delayed copy
    delay_samp = int(sr*0.06)
    rev = np.zeros(N)
    rev[delay_samp:] = mel[:N-delay_samp] * 0.25
    audio = np.clip(mel + bs + rev, -1, 1)

    path = f"{OUTPUT_DIR}/audio/humpty_hd_music.wav"
    with wave.open(path,"w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((audio*32767).astype(np.int16).tobytes())
    print(f"  [OK] {path}")
    return path


# ── Render frames ──────────────────────────────────────────────────────────────
def render_frames():
    print(f"[VIDEO] Rendering {TOTAL_FRAMES} frames at {FPS}fps ({W}x{H})...")
    raw = f"{OUTPUT_DIR}/videos/humpty_hd_raw.mp4"
    writer = imageio.get_writer(raw, fps=FPS, codec="libx264",
                                output_params=["-crf","18","-preset","fast"])
    for fi in range(TOTAL_FRAMES):
        writer.append_data(build_frame(fi))
        if fi % FPS == 0:
            print(f"  {fi}/{TOTAL_FRAMES} ({int(100*fi/TOTAL_FRAMES)}%)")
    writer.close()
    print(f"  [OK] {raw}")
    return raw


# ── Combine ────────────────────────────────────────────────────────────────────
def combine(video, voice, music):
    print("[COMBINE] Mixing tracks...")
    import subprocess, imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mixed  = f"{OUTPUT_DIR}/audio/humpty_hd_mixed.wav"
    final  = f"{OUTPUT_DIR}/videos/humpty_hd_final.mp4"

    subprocess.run([
        ffmpeg,"-y","-i",voice,"-i",music,
        "-filter_complex","[0:a]volume=1.0[v];[1:a]volume=0.25[m];[v][m]amix=inputs=2:duration=longest",
        "-ac","2", mixed
    ], check=True, stderr=subprocess.DEVNULL)

    subprocess.run([
        ffmpeg,"-y","-i",video,"-i",mixed,
        "-map","0:v","-map","1:a",
        "-c:v","copy","-c:a","aac","-shortest",
        final
    ], check=True, stderr=subprocess.DEVNULL)

    size = os.path.getsize(final)
    print(f"\n[DONE] {final}  ({size/1024/1024:.2f} MB)")
    return final


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    t0 = time.time()
    print("="*60)
    print("  Humpty Dumpty HD - Enhanced Animation Generator")
    print("="*60)
    voice = asyncio.run(gen_voice())
    music = gen_music(T_TOTAL + 2)
    raw   = render_frames()
    final = combine(raw, voice, music)
    print(f"\n[TIME] {time.time()-t0:.1f}s")
    print(f"[OUT]  {final}")
