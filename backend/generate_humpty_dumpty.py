"""
Humpty Dumpty Nursery Rhyme Video Generator
Creates: animated video + voice over + background music -> combined MP4
"""
import asyncio
import os
import sys
import wave
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio
import edge_tts

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT_DIR = "outputs"
os.makedirs(f"{OUTPUT_DIR}/videos", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/voice",  exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/audio",  exist_ok=True)

W, H = 1280, 720
FPS  = 24

RHYME = [
    "Humpty Dumpty sat on a wall,",
    "Humpty Dumpty had a great fall.",
    "All the king's horses and all the king's men,",
    "Couldn't put Humpty together again!",
]
FULL_TEXT = "\n".join(RHYME)

LINE_DURATIONS  = [3.5, 3.5, 4.0, 4.0]
TOTAL_DURATION  = sum(LINE_DURATIONS) + 2.0   # 2s intro

# Colours
SKY_TOP    = (30,  100, 200)
SKY_BOT    = (135, 206, 250)
SUN_COL    = (255, 215,   0)
CLOUD_COL  = (255, 255, 255)
GROUND_COL = (100, 180,  70)
BRICK_COL  = (178,  89,  30)
BRICK_DARK = (140,  60,  20)
HUMPTY_COL = (255, 220, 100)
HUMPTY_EYE = (50,   50, 100)
FACE_SMILE = (200,  80,  20)
KING_COL   = (180,  30,  30)


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_sky(draw, t):
    for y in range(H):
        c = lerp_color(SKY_TOP, SKY_BOT, y / H)
        draw.line([(0, y), (W, y)], fill=c)


def draw_sun(draw, t):
    cx, cy, r = 100, 100, 55
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=SUN_COL)
    for angle in range(0, 360, 30):
        rad = math.radians(angle + t * 20)
        x1 = cx + math.cos(rad) * (r + 8)
        y1 = cy + math.sin(rad) * (r + 8)
        x2 = cx + math.cos(rad) * (r + 22)
        y2 = cy + math.sin(rad) * (r + 22)
        draw.line([(x1, y1), (x2, y2)], fill=SUN_COL, width=4)


def draw_cloud(draw, cx, cy, scale=1.0):
    for dx, dy, r in [(-40, 0, 38), (0, -15, 48), (40, 0, 38), (70, 10, 30)]:
        rr = int(r * scale)
        draw.ellipse([cx+dx-rr, cy+dy-rr, cx+dx+rr, cy+dy+rr], fill=CLOUD_COL)


def draw_ground(draw):
    draw.rectangle([0, H-130, W, H], fill=GROUND_COL)
    for x in range(0, W, 40):
        for gx in [-5, 0, 5]:
            draw.line([(x+gx, H-130), (x+gx+3, H-148)], fill=(60, 160, 40), width=3)


def draw_wall(draw, wx=440, wy=H-220):
    bw, bh = 80, 32
    for row in range(5):
        offset = (row % 2) * 40
        y = wy + row * bh
        for col in range(10):
            x = wx - offset + col * bw - bw
            draw.rectangle([x, y, x+bw-3, y+bh-3], fill=BRICK_COL)
            draw.rectangle([x, y, x+bw-3, y+3],    fill=BRICK_DARK)
            draw.rectangle([x, y, x+3,    y+bh-3], fill=BRICK_DARK)


def draw_humpty(draw, cx, cy, cracked=False):
    bw, bh = 110, 130
    draw.ellipse([cx-bw//2, cy-bh//2, cx+bw//2, cy+bh//2],
                 fill=HUMPTY_COL, outline=(180, 140, 50), width=3)
    if cracked:
        draw.line([(cx-15, cy-40), (cx+5, cy-10), (cx-10, cy+20)],
                  fill=(180, 100, 20), width=4)
        draw.line([(cx+20, cy-30), (cx, cy+10)], fill=(180, 100, 20), width=3)

    ey = cy - 20
    draw.ellipse([cx-30, ey-12, cx-8,  ey+12], fill=HUMPTY_EYE)
    draw.ellipse([cx+8,  ey-12, cx+30, ey+12], fill=HUMPTY_EYE)
    draw.ellipse([cx-24, ey-6,  cx-14, ey+6],  fill="white")
    draw.ellipse([cx+14, ey-6,  cx+24, ey+6],  fill="white")
    draw.arc([cx-25, cy-5, cx+25, cy+35], start=10, end=170, fill=FACE_SMILE, width=4)

    draw.polygon([(cx-28, cy+45), (cx, cy+55), (cx-28, cy+65)], fill=(200, 30, 30))
    draw.polygon([(cx+28, cy+45), (cx, cy+55), (cx+28, cy+65)], fill=(200, 30, 30))
    draw.ellipse([cx-8, cy+50, cx+8, cy+62], fill=(240, 50, 50))

    hat_w, hat_h = 90, 35
    brim_y = cy - bh//2 - 5
    draw.rectangle([cx-hat_w//2,    brim_y-hat_h, cx+hat_w//2,    brim_y],   fill=(50, 50, 80))
    draw.rectangle([cx-hat_w//2-15, brim_y-8,     cx+hat_w//2+15, brim_y+8], fill=(50, 50, 80))
    draw.rectangle([cx-hat_w//2,    brim_y-12,    cx+hat_w//2,    brim_y-6], fill=(200, 170, 20))

    draw.line([(cx-bw//2, cy+10), (cx-bw//2-50, cy-20)], fill=HUMPTY_COL, width=16)
    draw.line([(cx+bw//2, cy+10), (cx+bw//2+50, cy-20)], fill=HUMPTY_COL, width=16)
    draw.line([(cx-30, cy+bh//2), (cx-50, cy+bh//2+55)], fill=HUMPTY_COL, width=16)
    draw.line([(cx+30, cy+bh//2), (cx+50, cy+bh//2+55)], fill=HUMPTY_COL, width=16)


def draw_kings_men(draw):
    for x, y in [(900, H-230), (980, H-240), (1060, H-235)]:
        draw.rectangle([x-15, y,    x+15, y+80], fill=KING_COL)
        draw.ellipse(  [x-16, y-36, x+16, y],    fill=(240, 200, 160))
        draw.polygon([(x-16, y-36), (x-8, y-54), (x, y-42),
                      (x+8,  y-54), (x+16, y-36)], fill=(255, 200, 0))
        draw.line([(x+20, y-10), (x+20, y+90)], fill=(120, 80, 40), width=4)
        draw.polygon([(x+14, y-10), (x+26, y-10), (x+20, y-30)], fill=(180, 180, 200))
        hx, hy = x-30, y+40
        draw.ellipse([hx-30, hy-20, hx+30, hy+20], fill=(180, 140, 100))
        draw.ellipse([hx+15, hy-36, hx+45, hy-6],  fill=(180, 140, 100))


def draw_subtitle(img, line_idx, t_in_line):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    text = RHYME[line_idx]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 42)
    except Exception:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    px, py = 40, 22
    bx = (W - tw)//2 - px
    by = H - 110
    d.rounded_rectangle([bx, by, bx+tw+px*2, by+th+py*2], radius=16, fill=(0, 0, 0, 170))
    d.text((bx+px, by+py), text, font=font, fill=(255, 255, 200))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def build_frame(frame_idx):
    t = frame_idx / FPS
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    draw_sky(draw, t)
    draw_sun(draw, t)
    draw_cloud(draw, int(200 + t*15) % (W+200) - 100, 130, 1.2)
    draw_cloud(draw, int(600 + t*8)  % (W+200) - 100, 90,  0.9)
    draw_cloud(draw, int(900 + t*20) % (W+200) - 100, 160, 1.0)
    draw_ground(draw)

    wall_x = 440
    draw_wall(draw, wall_x, H-220)

    hx = wall_x + 120
    hy_wall = H - 290
    intro = 2.0
    scene_t = t - intro

    if t < intro:
        bounce = math.sin(t * 3) * 6
        draw_humpty(draw, hx, int(hy_wall + bounce))
    elif scene_t < LINE_DURATIONS[0] + LINE_DURATIONS[1]:
        swing = math.sin(scene_t * 2.5) * 8
        draw_humpty(draw, hx, int(hy_wall + swing))
    else:
        fall_t = scene_t - (LINE_DURATIONS[0] + LINE_DURATIONS[1])
        fall_dur = LINE_DURATIONS[2]
        if fall_t < fall_dur:
            prog = fall_t / fall_dur
            fall_y = int(hy_wall + prog * prog * 320)
            fall_x = int(hx + prog * 180)
            draw_humpty(draw, fall_x, fall_y, cracked=(prog > 0.5))
        else:
            draw_humpty(draw, hx+190, H-140, cracked=True)
            draw_kings_men(draw)

    cum = intro
    for i, dur in enumerate(LINE_DURATIONS):
        if cum <= t < cum + dur:
            img = draw_subtitle(img, i, t - cum)
            break
        cum += dur

    return img


async def generate_voice():
    print("[MIC] Generating voice over (Sonia - British English)...")
    path = f"{OUTPUT_DIR}/voice/humpty_voice.mp3"
    communicate = edge_tts.Communicate(
        text=FULL_TEXT,
        voice="en-GB-SoniaNeural",
        rate="-15%",
        pitch="+3Hz",
    )
    await communicate.save(path)
    print(f"  [OK] Voice saved: {path}")
    return path


def generate_music(duration_sec):
    print("[MUSIC] Generating nursery rhyme background music...")
    sample_rate = 44100
    notes = {
        "C3": 130.81, "G3": 196.00, "F3": 174.61,
        "C4": 261.63, "D4": 293.66, "E4": 329.63,
        "F4": 349.23, "G4": 392.00, "A4": 440.00,
        "C5": 523.25,
    }
    melody_seq = [
        ("G4",0.5),("E4",0.5),("C4",0.5),("E4",0.5),
        ("G4",0.5),("G4",0.5),("A4",1.0),
        ("G4",0.5),("E4",0.5),("C4",0.5),("E4",0.5),
        ("D4",0.5),("D4",0.5),("C4",1.0),
        ("E4",0.5),("E4",0.5),("E4",0.5),("E4",0.5),
        ("G4",0.5),("G4",0.5),("A4",1.0),
        ("G4",0.5),("E4",0.5),("G4",0.5),("E4",0.5),
        ("D4",0.5),("C4",0.5),("C4",1.0),
    ]
    bass_seq = ["C3","G3","F3","C3"]

    total_samples = int(sample_rate * duration_sec)
    melody = np.zeros(total_samples)
    pos, idx = 0, 0
    while pos < total_samples:
        freq, dur = melody_seq[idx % len(melody_seq)]
        n = int(dur * sample_rate)
        end = min(pos + n, total_samples)
        seg = np.linspace(0, dur, end-pos, endpoint=False)
        wave_seg = np.sin(2 * np.pi * notes[freq] * seg)
        env = np.ones(end-pos)
        fade = min(200, end-pos)
        env[:fade] = np.linspace(0, 1, fade)
        if end-pos > fade:
            env[-(end-pos-fade):] = np.linspace(1, 0, end-pos-fade)
        melody[pos:end] += wave_seg * env * 0.40
        pos += n
        idx += 1

    bass = np.zeros(total_samples)
    beat = int(sample_rate * 0.5)
    for i in range(total_samples // beat):
        f = notes[bass_seq[i % len(bass_seq)]]
        s = i * beat
        e = min(s + beat, total_samples)
        seg_t = np.linspace(0, (e-s)/sample_rate, e-s)
        bass[s:e] += np.sin(2 * np.pi * f * seg_t) * 0.15

    audio = np.clip(melody + bass, -1.0, 1.0)
    path = f"{OUTPUT_DIR}/audio/humpty_music.wav"
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())
    print(f"  [OK] Music saved: {path}")
    return path


def generate_video_frames():
    print("[VIDEO] Rendering animated frames (1280x720)...")
    total = int(TOTAL_DURATION * FPS)
    path = f"{OUTPUT_DIR}/videos/humpty_raw.mp4"
    writer = imageio.get_writer(path, fps=FPS, codec="libx264",
                                output_params=["-crf", "20", "-preset", "fast"])
    for i in range(total):
        frame = build_frame(i)
        writer.append_data(np.array(frame))
        if i % FPS == 0:
            pct = int(100 * i / total)
            print(f"  Frame {i}/{total}  ({pct}%)")
    writer.close()
    print(f"  [OK] Raw video: {path}")
    return path


def combine(video_path, voice_path, music_path):
    print("[COMBINE] Mixing video + voice + music...")
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

    video = VideoFileClip(video_path)
    voice = AudioFileClip(voice_path).with_end(video.duration)
    music = AudioFileClip(music_path).with_end(video.duration).with_multiply_volume(0.28)

    mixed = CompositeAudioClip([music, voice])
    final = video.with_audio(mixed)

    out = f"{OUTPUT_DIR}/videos/humpty_dumpty_final.mp4"
    final.write_videofile(out, codec="libx264", audio_codec="aac",
                          fps=FPS, logger=None)
    video.close()
    print(f"\n[OK] Final video ready: {out}")
    return out


if __name__ == "__main__":
    import time
    t0 = time.time()
    print("=" * 60)
    print("  Humpty Dumpty Nursery Rhyme Video Generator")
    print("=" * 60)

    voice_path = asyncio.run(generate_voice())
    music_path = generate_music(TOTAL_DURATION + 2)
    video_path = generate_video_frames()
    final      = combine(video_path, voice_path, music_path)

    elapsed = time.time() - t0
    print(f"\n[DONE] Completed in {elapsed:.1f}s")
    print(f"[OUTPUT] {final}")
