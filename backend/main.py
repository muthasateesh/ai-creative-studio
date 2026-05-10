import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

os.makedirs("outputs/images", exist_ok=True)
os.makedirs("outputs/videos", exist_ok=True)
os.makedirs("outputs/voice", exist_ok=True)
os.makedirs("outputs/audio", exist_ok=True)

app = FastAPI(title="AI Creative Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

from routers import images, videos, voice, audio

app.include_router(images.router, prefix="/api/images", tags=["Images"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(audio.router, prefix="/api/audio", tags=["Audio"])


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "AI Creative Studio is running"}


@app.get("/api/gallery")
def gallery():
    items = []
    for category in ["images", "videos", "voice", "audio"]:
        folder = f"outputs/{category}"
        if os.path.exists(folder):
            for f in sorted(os.listdir(folder), reverse=True):
                filepath = os.path.join(folder, f)
                items.append({
                    "type": category,
                    "filename": f,
                    "url": f"/outputs/{category}/{f}",
                    "size": os.path.getsize(filepath),
                    "created": os.path.getctime(filepath),
                })
    items.sort(key=lambda x: x["created"], reverse=True)
    return {"items": items[:100]}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
