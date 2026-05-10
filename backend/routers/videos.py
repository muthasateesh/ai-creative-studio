import os
import uuid
import threading
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
_tasks: dict = {}
_pipeline = None
_pipeline_lock = threading.Lock()


class VideoRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = "blurry, bad quality, distorted"
    num_frames: int = 24
    fps: int = 8
    width: int = 576
    height: int = 320
    steps: int = 25
    guidance_scale: float = 7.5


def _get_pipeline():
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            import torch
            from diffusers import DiffusionPipeline

            _pipeline = DiffusionPipeline.from_pretrained(
                "cerspense/zeroscope_v2_576w",
                torch_dtype=torch.float16,
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _pipeline = _pipeline.to(device)
            _pipeline.enable_attention_slicing()
            _pipeline.enable_vae_slicing()
    return _pipeline


def _run_generation(task_id: str, req: VideoRequest):
    try:
        _tasks[task_id] = {"status": "loading_model", "progress": 5, "result": None}

        pipe = _get_pipeline()
        _tasks[task_id].update({"status": "generating", "progress": 30})

        import torch
        import numpy as np

        frames = pipe(
            req.prompt,
            negative_prompt=req.negative_prompt,
            num_frames=req.num_frames,
            width=req.width,
            height=req.height,
            num_inference_steps=req.steps,
            guidance_scale=req.guidance_scale,
        ).frames[0]

        _tasks[task_id]["progress"] = 85

        output_dir = "outputs/videos"
        filename = f"{uuid.uuid4()}.mp4"
        filepath = os.path.join(output_dir, filename)

        import imageio
        writer = imageio.get_writer(filepath, fps=req.fps)
        for frame in frames:
            if hasattr(frame, "numpy"):
                frame = frame.numpy()
            writer.append_data(np.array(frame))
        writer.close()

        _tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "result": f"/outputs/videos/{filename}",
        })

    except Exception as e:
        _tasks[task_id] = {"status": "failed", "progress": 0, "error": str(e), "result": None}


@router.post("/generate")
async def generate_video(req: VideoRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued", "progress": 0, "result": None}
    background_tasks.add_task(_run_generation, task_id, req)
    return {"task_id": task_id}


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]
