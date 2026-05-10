"""Image-to-video animation with voice over + background music."""
import asyncio
import math
import os
import subprocess
import threading
import uuid
import wave

import edge_tts
import imageio
import imageio_ffmpeg
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

router = APIRouter()

OUTPUT_DIR = "outputs/animations"
UPLOAD_DIR = "outputs/uploads"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

_tasks: dict = {}

STYLES = {
    "ken_burns": "Ken Burns",
    "zoom_in":   "Zoom In",
    "zoom_out":  "Zoom Out",
    "breathe":   "Breathe",
    "float":     "Float",
    "pan_right": "Pan Right",
    "pan_left":  "Pan Left",
    "cinematic": "Cinematic",
    "glitch":    "Glitch",
    "ripple":    "Ripple Wave",
    "bounce":    "Bounce",
    "rotate":    "Slow Rotate",
}

MUSIC_STYLES = {
    "none":       "No Music",
    "upbeat":     "Upbeat",
    "calm":       "Calm & Relaxing",
    "epic":       "Epic / Dramatic",
    "cinematic":  "Cinematic",
    "jazz":       "Jazz",
    "electronic": "Electronic",
}

# ─── easing helpers ────────────────────────────────────────────────────────────

def _ease_in_out(t):  return t * t * (3 - 2 * t)
def _ease_out(t):     return 1 - (1 - t) ** 3
def _clamp(v, lo, hi): return max(lo, min(hi, v))

# ─── animation functions ───────────────────────────────────────────────────────

def _ken_burns(img, t, W, H):
    zoom = 1.0 + 0.35 * _ease_in_out(t)
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox = int(_ease_in_out(t) * (nw - W))
    oy = int(_ease_in_out(t) * (nh - H))
    return r.crop((ox, oy, ox + W, oy + H))

def _zoom_in(img, t, W, H):
    zoom = 1.0 + 0.55 * _ease_in_out(t)
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox, oy = (nw - W) // 2, (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

def _zoom_out(img, t, W, H):
    zoom = 1.55 - 0.55 * _ease_in_out(t)
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox, oy = (nw - W) // 2, (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

def _breathe(img, t, W, H):
    scale = 1.0 + 0.045 * math.sin(t * 2 * math.pi)
    nw, nh = int(W * scale), int(H * scale)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox, oy = (nw - W) // 2, (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

def _float(img, t, W, H):
    amp = 14
    dy  = int(amp * math.sin(t * 2 * math.pi))
    zoom = 1.06
    nw, nh = int(W * zoom), int(H * zoom + amp * 2)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox = (nw - W) // 2
    oy = _clamp(amp + dy, 0, nh - H)
    return r.crop((ox, oy, ox + W, oy + H))

def _pan_right(img, t, W, H):
    zoom = 1.3
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox = int(_ease_in_out(t) * (nw - W))
    oy = (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

def _pan_left(img, t, W, H):
    zoom = 1.3
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox = int((1 - _ease_in_out(t)) * (nw - W))
    oy = (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

def _cinematic(img, t, W, H):
    frame = _ken_burns(img, t, W, H)
    arr = np.array(frame)
    bar = H // 9
    arr[:bar] = 0
    arr[H - bar:] = 0
    return Image.fromarray(arr)

def _glitch(img, t, W, H):
    arr = np.array(img.resize((W, H), Image.LANCZOS))
    intensity = 0.5 + 0.5 * math.sin(t * 8 * math.pi)
    for _ in range(max(1, int(6 * intensity))):
        y = np.random.randint(0, H)
        h = np.random.randint(2, max(3, H // 16))
        s = np.random.randint(-24, 24)
        arr[y: min(H, y + h)] = np.roll(arr[y: min(H, y + h)], s, axis=1)
    sr = int(math.sin(t * 9 * math.pi) * 7)
    arr[:, :, 0] = np.roll(arr[:, :, 0], sr, axis=1)
    arr[:, :, 2] = np.roll(arr[:, :, 2], -sr, axis=1)
    return Image.fromarray(arr.astype(np.uint8))

def _ripple(img, t, W, H):
    arr = np.array(img.resize((W, H), Image.LANCZOS))
    amp, freq = 9, 0.05
    phase = t * 2 * math.pi * 2
    ys, xs = np.mgrid[0:H, 0:W]
    sx = np.clip((xs + amp * np.sin(freq * ys + phase)).astype(np.int32), 0, W - 1)
    sy = np.clip((ys + amp * np.sin(freq * xs + phase * 0.7)).astype(np.int32), 0, H - 1)
    return Image.fromarray(arr[sy, sx])

def _bounce(img, t, W, H):
    amp = 22
    dy  = int(amp * abs(math.sin(t * 2 * math.pi * 1.8)))
    zoom = 1.12
    nw, nh = int(W * zoom), int(H * zoom + amp * 2)
    r = img.resize((nw, nh), Image.LANCZOS)
    ox = (nw - W) // 2
    oy = _clamp(dy, 0, nh - H)
    return r.crop((ox, oy, ox + W, oy + H))

def _rotate(img, t, W, H):
    angle = t * 6.0
    zoom  = 1.18
    nw, nh = int(W * zoom), int(H * zoom)
    r = img.resize((nw, nh), Image.LANCZOS).rotate(angle, resample=Image.BICUBIC, expand=False)
    ox, oy = (nw - W) // 2, (nh - H) // 2
    return r.crop((ox, oy, ox + W, oy + H))

_FNS = {
    "ken_burns": _ken_burns, "zoom_in":  _zoom_in,   "zoom_out": _zoom_out,
    "breathe":   _breathe,   "float":    _float,      "pan_right": _pan_right,
    "pan_left":  _pan_left,  "cinematic":_cinematic,  "glitch":   _glitch,
    "ripple":    _ripple,    "bounce":   _bounce,      "rotate":   _rotate,
}

# ─── music generation ──────────────────────────────────────────────────────────

_SR = 44100

_N = {  # full note frequency table
    "C2": 65.41, "G2": 98.00, "A2": 110.00, "Bb2": 116.54,
    "C3":130.81,"D3":146.83,"E3":164.81,"F3":174.61,"G3":196.00,"A3":220.00,"Bb3":233.08,"B3":246.94,
    "C4":261.63,"D4":293.66,"Eb4":311.13,"E4":329.63,"F4":349.23,"F#4":369.99,
    "G4":392.00,"Ab4":415.30,"A4":440.00,"Bb4":466.16,"B4":493.88,
    "C5":523.25,"D5":587.33,"Eb5":622.25,"E5":659.25,"F5":698.46,"G5":783.99,"A5":880.00,
}

# ── instrument primitives ──────────────────────────────────────────────────────

def _t(dur):
    return np.linspace(0, dur, max(1, int(dur * _SR)), endpoint=False)

def _env(n, atk_s=0.008, rel_s=0.12, decay_rate=0.0):
    """Attack + optional exponential decay + release envelope."""
    e = np.ones(n, dtype=np.float32)
    atk = min(int(atk_s * _SR), n // 4)
    rel = min(int(rel_s * _SR), n // 4)
    if atk > 0: e[:atk] = np.linspace(0, 1, atk)
    if rel > 0: e[-rel:] = np.linspace(1, 0, rel)
    if decay_rate > 0:
        t = np.linspace(0, n / _SR, n)
        e *= np.exp(-t * decay_rate).astype(np.float32)
    return e

def _piano(freq, dur, amp=0.55):
    """Piano-like tone: harmonics + exponential key-decay."""
    t = _t(dur)
    n = len(t)
    w = (np.sin(2*np.pi*freq*t)
       + 0.50*np.sin(4*np.pi*freq*t)
       + 0.25*np.sin(6*np.pi*freq*t)
       + 0.10*np.sin(8*np.pi*freq*t)).astype(np.float32)
    return w * _env(n, atk_s=0.006, rel_s=0.04, decay_rate=5.0) * amp * 0.4

def _pad(freqs, dur, amp=0.18):
    """Detuned string-pad chord: slow attack, held sustain."""
    t = _t(dur)
    n = len(t)
    w = np.zeros(n, dtype=np.float32)
    for f in freqs:
        w += np.sin(2*np.pi*f*t).astype(np.float32)
        w += (0.5*np.sin(2*np.pi*f*1.006*t)).astype(np.float32)  # detune
        w += (0.25*np.sin(4*np.pi*f*t)).astype(np.float32)
    w /= max(len(freqs), 1)
    return w * _env(n, atk_s=0.18, rel_s=0.22) * amp

def _bass(freq, dur, amp=0.50):
    """Sub-bass with quick decay."""
    t = _t(dur)
    n = len(t)
    w = (np.sin(2*np.pi*freq*t)
       + 0.6*np.sin(4*np.pi*freq*t)
       + 0.2*np.sin(6*np.pi*freq*t)).astype(np.float32)
    return w * _env(n, atk_s=0.004, rel_s=0.06, decay_rate=3.5) * amp * 0.35

def _synth_bass(freq, dur, amp=0.55):
    """Electronic saw-like bass."""
    t = _t(dur)
    n = len(t)
    # approx sawtooth with harmonics
    w = sum(np.sin(2*np.pi*freq*k*t) / k for k in range(1, 8)).astype(np.float32)
    return w * _env(n, atk_s=0.003, rel_s=0.03, decay_rate=2.0) * amp * 0.18

def _kick(dur=0.35):
    n = max(1, int(dur * _SR))
    t = np.linspace(0, dur, n, endpoint=False)
    freq = 100*np.exp(-t*35) + 45
    phase = np.cumsum(freq) * 2*np.pi / _SR
    w = np.sin(phase).astype(np.float32)
    return w * np.exp(-t*14).astype(np.float32) * 0.80

def _snare(dur=0.18):
    n = max(1, int(dur * _SR))
    t = np.linspace(0, dur, n, endpoint=False)
    noise = np.random.default_rng(42).standard_normal(n).astype(np.float32) * 0.55
    tone  = (np.sin(2*np.pi*195*t) * 0.45).astype(np.float32)
    env   = np.exp(-t*28).astype(np.float32)
    return (noise + tone) * env * 0.55

def _hihat(dur=0.04, amp=0.18):
    n = max(1, int(dur * _SR))
    t = np.linspace(0, dur, n, endpoint=False)
    noise = np.random.default_rng(7).standard_normal(n).astype(np.float32)
    return noise * np.exp(-t*55).astype(np.float32) * amp

def _place(buf, seg, pos):
    end = min(pos + len(seg), len(buf))
    if pos < end:
        buf[pos:end] += seg[:end-pos]

def _loop_melody(buf, seq, amp_fn):
    """Lay melody sequence looping across full buffer."""
    pos = 0
    idx = 0
    while pos < len(buf):
        note, dur = seq[idx % len(seq)]
        seg = amp_fn(_N[note], dur)
        _place(buf, seg, pos)
        pos += len(seg)
        idx += 1

def _loop_drums(buf, pattern_n, kick_beats, snare_beats, hat_div=None, hat_amp=0.18):
    """Lay a drum pattern that repeats every pattern_n samples."""
    k = _kick(); s = _snare()
    pos = 0
    while pos < len(buf):
        for b in kick_beats:
            _place(buf, k, pos + int(b * pattern_n))
        for b in snare_beats:
            _place(buf, s, pos + int(b * pattern_n))
        if hat_div:
            for i in range(hat_div):
                h = _hihat(amp=hat_amp)
                _place(buf, h, pos + int(i / hat_div * pattern_n))
        pos += pattern_n

def _loop_bass(buf, notes, beat_n):
    for i in range(len(buf) // beat_n + 1):
        f = _N[notes[i % len(notes)]]
        _place(buf, _bass(f, beat_n / _SR), i * beat_n)

def _loop_pad(buf, chords, chord_n):
    for i in range(len(buf) // chord_n + 1):
        freqs = chords[i % len(chords)]
        _place(buf, _pad(freqs, chord_n / _SR), i * chord_n)

# ── style renderers ────────────────────────────────────────────────────────────

def _upbeat(total):
    buf = np.zeros(total, dtype=np.float32)
    beat = int(0.5 * _SR)   # 120 BPM
    # melody: happy C-major
    mel = [("C4",.25),("E4",.25),("G4",.25),("C5",.25),
           ("B4",.25),("G4",.25),("E4",.25),("C4",.25),
           ("D4",.25),("F4",.25),("A4",.5),
           ("G4",.25),("E4",.25),("C5",.5),("G4",.5)]
    _loop_melody(buf, mel, lambda f, d: _piano(f, d, 0.60))
    # chords: C G Am F
    chords = [
        [_N["C4"],_N["E4"],_N["G4"]],
        [_N["G3"],_N["B3"],_N["D4"]],
        [_N["A3"],_N["C4"],_N["E4"]],
        [_N["F3"],_N["A3"],_N["C4"]],
    ]
    _loop_pad(buf, chords, beat * 4)
    # bass
    _loop_bass(buf, ["C3","G3","A3","F3"], beat * 2)
    # drums: kick 0,0.5 snare 0.25,0.75; 16th hats
    _loop_drums(buf, beat*2, [0, 0.5], [0.25, 0.75], hat_div=8, hat_amp=0.15)
    return buf

def _calm(total):
    buf = np.zeros(total, dtype=np.float32)
    beat = int(0.75 * _SR)  # 80 BPM
    mel = [("G4",1.0),("B4",.5),("D5",.5),
           ("E4",1.0),("G4",.5),("B4",.5),
           ("C4",1.0),("E4",.5),("G4",.5),
           ("D4",1.0),("F#4",.5),("A4",.5)]
    _loop_melody(buf, mel, lambda f, d: _piano(f, d, 0.45))
    chords = [
        [_N["G3"],_N["B3"],_N["D4"]],
        [_N["E3"],_N["G3"],_N["B3"]],
        [_N["C3"],_N["E3"],_N["G3"]],
        [_N["D3"],_N["F#4"],_N["A3"]],
    ]
    _loop_pad(buf, chords, beat * 4)
    _loop_bass(buf, ["G2","A2","C3","G2"], beat * 4)
    return buf

def _epic(total):
    buf = np.zeros(total, dtype=np.float32)
    beat = int(0.63 * _SR)  # ~95 BPM
    mel = [("D4",.5),("D4",.25),("A4",.75),
           ("Bb4",.5),("A4",.5),
           ("F4",.5),("F4",.25),("C5",.75),
           ("Bb4",.5),("A4",.5),
           ("G4",.5),("G4",.25),("D5",1.0),
           ("C5",.5),("Bb4",.5),("A4",1.0)]
    _loop_melody(buf, mel, lambda f, d: _piano(f, d, 0.70))
    chords = [
        [_N["D4"],_N["F4"],_N["A4"]],
        [_N["Bb3"],_N["D4"],_N["F4"]],
        [_N["F3"],_N["A3"],_N["C4"]],
        [_N["C4"],_N["E4"],_N["G4"]],
    ]
    _loop_pad(buf, chords, beat * 4)
    _loop_bass(buf, ["D3","Bb2","G2","C3"], beat * 2)
    # powerful drums: double kick, heavy snare
    _loop_drums(buf, beat*4, [0, 0.375, 0.5, 0.875], [0.25, 0.75], hat_div=8, hat_amp=0.12)
    return buf

def _cinematic(total):
    buf = np.zeros(total, dtype=np.float32)
    beat = int(1.09 * _SR)  # ~55 BPM
    mel = [("C4",2.0),("E4",1.5),("G4",1.5),
           ("F4",2.0),("A4",1.5),("G4",1.5),
           ("E4",2.0),("G4",1.5),("C5",3.0)]
    _loop_melody(buf, mel, lambda f, d: _piano(f, d, 0.50))
    chords = [
        [_N["C3"],_N["E4"],_N["G4"]],
        [_N["F3"],_N["A3"],_N["C4"]],
        [_N["G3"],_N["B3"],_N["D4"]],
        [_N["A3"],_N["C4"],_N["E4"]],
    ]
    _loop_pad(buf, chords, beat * 4)
    _loop_bass(buf, ["C3","F3","G3","A3"], beat * 4)
    return buf

def _jazz(total):
    np.random.seed(12)
    buf = np.zeros(total, dtype=np.float32)
    beat = int(0.60 * _SR)  # 100 BPM, swing feel
    swing = 0.67             # swing ratio
    # swing hi-hat: long-short pairs
    hat = _hihat(amp=0.14)
    pos = 0
    pair = [0.0, swing * 0.5]
    while pos < len(buf):
        for p in pair:
            _place(buf, hat, pos + int(p * beat))
        pos += beat
    mel = [("C4",.375),("E4",.125),("G4",.25),("Bb4",.25),
           ("A4",.375),("F#4",.125),("E4",.25),("G4",.25),
           ("D4",.375),("F4",.125),("Ab4",.25),("C5",.25),
           ("Bb4",.375),("G4",.125),("E4",.25),("C4",.5)]
    _loop_melody(buf, mel, lambda f, d: _piano(f, d, 0.55))
    chords = [
        [_N["C4"],_N["E4"],_N["G4"],_N["Bb4"]],  # C7
        [_N["A3"],_N["C4"],_N["E4"],_N["G4"]],   # Am7
        [_N["D4"],_N["F4"],_N["A4"],_N["C5"]],   # Dm7
        [_N["G3"],_N["B3"],_N["D4"],_N["F4"]],   # G7
    ]
    _loop_pad(buf, chords, beat * 4)
    _loop_bass(buf, ["C3","A3","D3","G3"], beat * 2)
    k = _kick()
    s = _snare()
    pos = 0
    while pos < len(buf):
        _place(buf, k, pos)
        _place(buf, s, pos + beat)
        _place(buf, k, pos + int(1.5*beat))
        _place(buf, s, pos + int(3*beat))
        pos += beat * 4
    return buf

def _electronic(total):
    np.random.seed(99)
    buf = np.zeros(total, dtype=np.float32)
    beat = int(0.469 * _SR)  # 128 BPM
    # arpeggio: C4-E4-G4-Bb4 looping 16th notes
    arp = [("C4",.125),("E4",.125),("G4",.125),("Bb4",.125),
           ("G4",.125),("E4",.125),("C5",.125),("G4",.125)]
    _loop_melody(buf, arp, lambda f, d: _piano(f, d * 0.8, 0.45))
    chords = [
        [_N["C4"],_N["G4"]],
        [_N["A3"],_N["E4"]],
        [_N["F3"],_N["C4"]],
        [_N["G3"],_N["D4"]],
    ]
    _loop_pad(buf, chords, beat * 4)
    # synth bass: pumping on every beat
    pos = 0
    while pos < len(buf):
        _place(buf, _synth_bass(_N["C3"], 0.469, 0.65), pos)
        pos += beat
    # four-on-the-floor + snare 2,4 + 8th hats
    k = _kick(); s = _snare()
    _loop_drums(buf, beat*4, [0, 0.25, 0.5, 0.75], [0.25, 0.75], hat_div=8, hat_amp=0.10)
    return buf

_RENDERERS = {
    "upbeat":     _upbeat,
    "calm":       _calm,
    "epic":       _epic,
    "cinematic":  _cinematic,
    "jazz":       _jazz,
    "electronic": _electronic,
}


def generate_music(style: str, duration_sec: float, out_path: str):
    if style == "none" or style not in _RENDERERS:
        return None

    total = int(duration_sec * _SR)
    buf   = _RENDERERS[style](total)

    # light reverb
    delay = int(0.055 * _SR)
    rev   = np.zeros(total, dtype=np.float32)
    rev[delay:] = buf[:total-delay] * 0.18

    audio = buf + rev
    # normalize to -2 dB
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio *= 0.80 / peak
    audio = np.clip(audio, -1.0, 1.0)

    with wave.open(out_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SR)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())
    return out_path


# ─── voice generation ──────────────────────────────────────────────────────────

def _fix_sign(val: str) -> str:
    """Ensure edge-tts rate/pitch strings always have an explicit sign."""
    val = val.strip()
    if val and val[0] not in ('+', '-'):
        val = '+' + val
    return val

async def _tts(text: str, voice: str, rate: str, pitch: str, out_path: str):
    communicate = edge_tts.Communicate(
        text=text, voice=voice,
        rate=_fix_sign(rate), pitch=_fix_sign(pitch),
    )
    await communicate.save(out_path)


# ─── ffmpeg combine ────────────────────────────────────────────────────────────

def _ffmpeg_combine(raw_video: str, voice_path: str | None, music_path: str | None,
                    out_path: str, music_vol: float):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    if not voice_path and not music_path:
        # no audio — just copy raw video
        os.replace(raw_video, out_path)
        return

    if voice_path and music_path:
        # step 1: mix voice + music → mixed.wav
        mixed = out_path.replace(".mp4", "_mixed.wav")
        subprocess.run([
            ffmpeg, "-y",
            "-i", voice_path,
            "-i", music_path,
            "-filter_complex",
            f"[0:a]volume=1.0[v];[1:a]volume={music_vol:.2f}[m];[v][m]amix=inputs=2:duration=longest",
            "-ac", "2", mixed,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        audio_input = mixed
    elif voice_path:
        audio_input = voice_path
    else:
        audio_input = music_path

    # step 2: mux audio with video
    subprocess.run([
        ffmpeg, "-y",
        "-i", raw_video,
        "-i", audio_input,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        out_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # cleanup
    if voice_path and music_path and os.path.exists(out_path.replace(".mp4", "_mixed.wav")):
        os.remove(out_path.replace(".mp4", "_mixed.wav"))


# ─── main render pipeline ──────────────────────────────────────────────────────

def _render(task_id: str, img_path: str, anim_style: str, duration: float,
            fps: int, W: int, H: int,
            voice_text: str, voice_name: str, voice_rate: str, voice_pitch: str,
            music_style: str, music_vol: float):
    try:
        _tasks[task_id]["status"] = "rendering"

        # 1. render video frames → raw mp4
        img = Image.open(img_path).convert("RGB").resize((W, H), Image.LANCZOS)
        total = int(duration * fps)
        raw_path = f"{OUTPUT_DIR}/{task_id}_raw.mp4"
        out_path = f"{OUTPUT_DIR}/{task_id}.mp4"
        fn = _FNS.get(anim_style, _ken_burns)
        fade_frames = max(1, int(fps * 0.4))
        black = Image.new("RGB", (W, H), (0, 0, 0))

        writer = imageio.get_writer(
            raw_path, fps=fps, codec="libx264",
            output_params=["-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p"],
        )
        for i in range(total):
            t = i / max(total - 1, 1)
            frame = fn(img, t, W, H)
            if i < fade_frames:
                frame = Image.blend(black, frame, i / fade_frames)
            elif i > total - fade_frames:
                frame = Image.blend(black, frame, (total - i) / fade_frames)
            writer.append_data(np.array(frame))
            if i % fps == 0:
                _tasks[task_id]["progress"] = int(60 * i / total)  # 0-60 for video
        writer.close()

        # 2. generate voice (edge-tts)
        voice_path = None
        if voice_text.strip():
            _tasks[task_id]["status"] = "generating voice"
            voice_path = f"{OUTPUT_DIR}/{task_id}_voice.mp3"
            asyncio.run(_tts(voice_text, voice_name, voice_rate, voice_pitch, voice_path))
        _tasks[task_id]["progress"] = 70

        # 3. generate music
        music_path = None
        if music_style != "none":
            _tasks[task_id]["status"] = "generating music"
            music_path = f"{OUTPUT_DIR}/{task_id}_music.wav"
            generate_music(music_style, duration + 1.0, music_path)
        _tasks[task_id]["progress"] = 85

        # 4. combine audio + video
        _tasks[task_id]["status"] = "mixing audio"
        _ffmpeg_combine(raw_path, voice_path, music_path, out_path, music_vol)

        # cleanup raw file
        if os.path.exists(raw_path) and raw_path != out_path:
            os.remove(raw_path)

        _tasks[task_id].update({
            "status":   "done",
            "progress": 100,
            "url":      f"/outputs/animations/{task_id}.mp4",
        })
    except Exception as exc:
        _tasks[task_id].update({"status": "error", "error": str(exc)})


# ─── prompt → settings inference ──────────────────────────────────────────────

_PROMPT_RULES = [
    # (keywords, anim_style, music_style)
    (["cinematic","film","movie","widescreen","dramatic reveal"], "cinematic",  "cinematic"),
    (["epic","battle","intense","war","power","thunder"],          "zoom_in",    "epic"),
    (["calm","peaceful","relax","meditation","zen","gentle"],      "breathe",    "calm"),
    (["nature","landscape","forest","mountain","sky","cloud"],     "ken_burns",  "calm"),
    (["ocean","wave","water","sea","rain","ripple"],               "ripple",     "calm"),
    (["glitch","digital","cyber","tech","hack","neon","matrix"],   "glitch",     "electronic"),
    (["dance","party","energy","fun","happy","festival","beat"],   "bounce",     "upbeat"),
    (["portrait","face","person","smile","people","human"],        "breathe",    "calm"),
    (["travel","journey","adventure","explore","road","city"],     "pan_right",  "upbeat"),
    (["space","galaxy","star","universe","cosmic","nebula"],       "zoom_out",   "cinematic"),
    (["float","dream","fantasy","magic","fairy","wonder"],         "float",      "cinematic"),
    (["rotate","spin","swirl","spiral","vortex"],                  "rotate",     "electronic"),
    (["zoom","close","detail","macro","focus"],                    "zoom_in",    "cinematic"),
    (["jazz","blues","swing","vintage","retro","classic"],         "pan_left",   "jazz"),
    (["electronic","synth","future","robot","sci-fi"],             "glitch",     "electronic"),
]

def infer_from_prompt(prompt: str) -> dict:
    low = prompt.lower()
    for keywords, anim, music in _PROMPT_RULES:
        if any(k in low for k in keywords):
            return {"anim_style": anim, "music_style": music}
    return {"anim_style": "ken_burns", "music_style": "upbeat"}


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("/styles")
def list_styles():
    return STYLES


@router.get("/music-styles")
def list_music_styles():
    return MUSIC_STYLES


@router.post("/suggest")
async def suggest(prompt: str = Form(...)):
    """Return inferred animation + music style for a given text prompt."""
    result = infer_from_prompt(prompt)
    return {
        **result,
        "anim_label": STYLES.get(result["anim_style"], result["anim_style"]),
        "music_label": MUSIC_STYLES.get(result["music_style"], result["music_style"]),
    }


@router.post("/generate")
async def generate(
    file:          UploadFile = File(...),
    prompt:        str   = Form(""),
    style:         str   = Form("auto"),
    duration:      float = Form(6.0),
    fps:           int   = Form(30),
    width:         int   = Form(1280),
    height:        int   = Form(720),
    voice_text:    str   = Form(""),
    voice_name:    str   = Form("en-US-AriaNeural"),
    voice_rate:    str   = Form("-5%"),
    voice_pitch:   str   = Form("+0Hz"),
    music_style:   str   = Form("auto"),
    music_vol:     float = Form(0.30),
    narrate_prompt:bool  = Form(False),
):
    task_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    upload_path = f"{UPLOAD_DIR}/{task_id}{ext}"

    data = await file.read()
    with open(upload_path, "wb") as f:
        f.write(data)

    # auto-infer style / music from prompt when not manually overridden
    inferred = infer_from_prompt(prompt) if prompt.strip() else {}
    resolved_style       = inferred.get("anim_style",  "ken_burns") if style       == "auto" else style
    resolved_music_style = inferred.get("music_style", "upbeat")    if music_style == "auto" else music_style

    # use prompt as narration if requested and no separate voice text
    effective_voice_text = prompt if (narrate_prompt and not voice_text.strip()) else voice_text

    _tasks[task_id] = {
        "status": "queued", "progress": 0,
        "resolved_style": resolved_style,
        "resolved_music": resolved_music_style,
    }
    threading.Thread(
        target=_render,
        args=(task_id, upload_path, resolved_style, duration, fps, width, height,
              effective_voice_text, voice_name, voice_rate, voice_pitch,
              resolved_music_style, music_vol),
        daemon=True,
    ).start()
    return {
        "task_id": task_id,
        "resolved_style": resolved_style,
        "resolved_music": resolved_music_style,
    }


@router.get("/task/{task_id}")
def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]
