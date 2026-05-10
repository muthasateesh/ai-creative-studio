"""Two-step combine: mix audio first, then mux with video."""
import subprocess, sys, os, imageio_ffmpeg

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd, label):
    print(f"\n[RUN] {label}")
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    err = result.stderr.decode(errors='replace')
    if result.returncode != 0:
        print(f"[FAIL] exit {result.returncode}")
        print(err[-1000:])
        sys.exit(1)
    print(f"[OK]")
    return result


# --- Step 1: mix voice + music into mixed_audio.wav ---
run([
    ffmpeg, "-y",
    "-i", "outputs/voice/humpty_voice.mp3",
    "-i", "outputs/audio/humpty_music.wav",
    "-filter_complex",
    "[0:a]volume=1.0[v];[1:a]volume=0.28[m];[v][m]amix=inputs=2:duration=longest",
    "-ac", "2",
    "outputs/audio/mixed_audio.wav"
], "Mix voice + music")

# --- Step 2: attach mixed audio to raw video ---
run([
    ffmpeg, "-y",
    "-i", "outputs/videos/humpty_raw.mp4",
    "-i", "outputs/audio/mixed_audio.wav",
    "-map", "0:v",
    "-map", "1:a",
    "-c:v", "copy",
    "-c:a", "aac",
    "-shortest",
    "outputs/videos/humpty_dumpty_final.mp4"
], "Mux video + mixed audio")

size = os.path.getsize("outputs/videos/humpty_dumpty_final.mp4")
print(f"\n[DONE] outputs/videos/humpty_dumpty_final.mp4  ({size/1024/1024:.2f} MB)")
