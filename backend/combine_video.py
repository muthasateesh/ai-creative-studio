"""Combine raw video + voice MP3 + music WAV into final MP4 using ffmpeg."""
import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import imageio_ffmpeg
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

video = "outputs/videos/humpty_raw.mp4"
voice = "outputs/voice/humpty_voice.mp3"
music = "outputs/audio/humpty_music.wav"
out   = "outputs/videos/humpty_dumpty_final.mp4"

print(f"ffmpeg: {ffmpeg}")
print(f"Combining:\n  video: {video}\n  voice: {voice}\n  music: {music}")
print(f"Output: {out}")

cmd = [
    ffmpeg, "-y",
    "-i", video,
    "-i", voice,
    "-i", music,
    "-filter_complex",
    "[1:a]apad[v];[2:a]volume=0.28,apad[m];[v][m]amix=inputs=2:duration=longest[aout]",
    "-map", "0:v",
    "-map", "[aout]",
    "-c:v", "copy",
    "-c:a", "aac",
    "-shortest",
    out
]

result = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", result.stdout[-500:] if result.stdout else "(none)")
print("STDERR:", result.stderr[-800:] if result.stderr else "(none)")
print("Return code:", result.returncode)

if result.returncode == 0:
    size = os.path.getsize(out)
    print(f"\n[OK] Final video: {out}  ({size/1024/1024:.2f} MB)")
else:
    print("\n[FAILED] ffmpeg returned non-zero exit code")
