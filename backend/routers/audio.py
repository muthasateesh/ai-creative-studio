import os
import uuid
import threading
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
_tasks: dict = {}
_music_model = None
_sfx_model = None
_model_lock = threading.Lock()


class AudioRequest(BaseModel):
    prompt: str
    duration: int = 10
    type: str = "music"


def _get_music_model():
    global _music_model
    with _model_lock:
        if _music_model is None:
            from audiocraft.models import MusicGen
            _music_model = MusicGen.get_pretrained("facebook/musicgen-small")
            _music_model.set_generation_params(duration=10)
    return _music_model


def _get_sfx_model():
    global _sfx_model
    with _model_lock:
        if _sfx_model is None:
            from audiocraft.models import AudioGen
            _sfx_model = AudioGen.get_pretrained("facebook/audiogen-medium")
            _sfx_model.set_generation_params(duration=5)
    return _sfx_model


def _run_generation(task_id: str, req: AudioRequest):
    try:
        _tasks[task_id] = {"status": "loading_model", "progress": 10, "result": None}

        import torch
        import torchaudio

        if req.type == "music":
            model = _get_music_model()
        else:
            model = _get_sfx_model()

        model.set_generation_params(duration=max(1, min(req.duration, 30)))
        _tasks[task_id].update({"status": "generating", "progress": 40})

        wav = model.generate([req.prompt])

        _tasks[task_id]["progress"] = 85

        output_dir = "outputs/audio"
        filename = f"{uuid.uuid4()}.wav"
        filepath = os.path.join(output_dir, filename)

        torchaudio.save(filepath, wav[0].cpu(), model.sample_rate)

        _tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "result": f"/outputs/audio/{filename}",
        })

    except Exception as e:
        _tasks[task_id] = {"status": "failed", "progress": 0, "error": str(e), "result": None}


@router.post("/generate")
async def generate_audio(req: AudioRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued", "progress": 0, "result": None}
    background_tasks.add_task(_run_generation, task_id, req)
    return {"task_id": task_id}


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]
