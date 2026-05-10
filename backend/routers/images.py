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


class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = "blurry, bad quality, distorted, ugly, low resolution"
    width: int = 1024
    height: int = 1024
    steps: int = 25
    guidance_scale: float = 7.5
    num_images: int = 1
    style: Optional[str] = "realistic"


def _get_pipeline():
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            import torch
            from diffusers import StableDiffusionXLPipeline

            _pipeline = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16",
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _pipeline = _pipeline.to(device)
            _pipeline.enable_attention_slicing()
    return _pipeline


def _run_generation(task_id: str, req: ImageRequest):
    try:
        _tasks[task_id] = {"status": "loading_model", "progress": 5, "results": []}

        style_prefixes = {
            "realistic": "photorealistic, ultra detailed, 8k, ",
            "anime": "anime style, manga, detailed illustration, ",
            "oil_painting": "oil painting, artistic, textured canvas, ",
            "watercolor": "watercolor painting, soft colors, artistic, ",
            "sketch": "pencil sketch, hand drawn, detailed, ",
            "3d": "3D render, octane render, realistic lighting, ",
        }
        prefix = style_prefixes.get(req.style or "realistic", "")
        prompt = prefix + req.prompt

        pipe = _get_pipeline()
        _tasks[task_id]["status"] = "generating"
        _tasks[task_id]["progress"] = 30

        output_dir = "outputs/images"
        results = []

        for i in range(req.num_images):
            import torch
            image = pipe(
                prompt=prompt,
                negative_prompt=req.negative_prompt,
                width=req.width,
                height=req.height,
                num_inference_steps=req.steps,
                guidance_scale=req.guidance_scale,
            ).images[0]

            filename = f"{uuid.uuid4()}.png"
            image.save(os.path.join(output_dir, filename))
            results.append(f"/outputs/images/{filename}")
            _tasks[task_id]["progress"] = 30 + int(70 * (i + 1) / req.num_images)
            _tasks[task_id]["results"] = results

        _tasks[task_id].update({"status": "completed", "progress": 100, "results": results})

    except Exception as e:
        _tasks[task_id] = {"status": "failed", "progress": 0, "error": str(e), "results": []}


@router.post("/generate")
async def generate_image(req: ImageRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued", "progress": 0, "results": []}
    background_tasks.add_task(_run_generation, task_id, req)
    return {"task_id": task_id}


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@router.get("/styles")
async def get_styles():
    return {
        "styles": [
            {"id": "realistic", "name": "Photorealistic"},
            {"id": "anime", "name": "Anime / Manga"},
            {"id": "oil_painting", "name": "Oil Painting"},
            {"id": "watercolor", "name": "Watercolor"},
            {"id": "sketch", "name": "Pencil Sketch"},
            {"id": "3d", "name": "3D Render"},
        ]
    }
